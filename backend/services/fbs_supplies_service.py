"""Синк поставок FBS (скан приёмки): GET /api/v3/supplies -> wb_orders_fbs_supplies.

Ответ: {"next": int, "supplies": [{id, name, createdAt, closedAt, scanDt,
done, cargoType, destinationOfficeId, ...}]}. Пагинация по next (0 — конец).
Храним только нужное для времени сдачи (см. миграцию 20261005).
Свежесть внутри дня — запуск каждые 30 мин (cron */30). Только stdlib.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SUPPLIES_URL = "https://marketplace-api.wildberries.ru/api/v3/supplies"
TIMEOUT_S = 15


def _dt(v):
    """RFC3339/дата -> 'YYYY-MM-DD HH:MM:SS' UTC-naive (как wb_created_at) или None."""
    if not v:
        return None
    try:
        s = str(v).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = datetime.fromisoformat(s)
        if d.tzinfo is not None:
            d = d.astimezone(timezone.utc).replace(tzinfo=None)
        return d.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


class FbsSuppliesService:
    def __init__(self, db: AsyncSession, company_id: int = 1):
        self.db = db
        self.company_id = company_id

    async def _token(self) -> str:
        row = (await self.db.execute(
            text("SELECT api_key FROM companies WHERE id = :cid"),
            {"cid": self.company_id})).first()
        key = (row[0] if row else "") or ""
        if not key.strip():
            raise RuntimeError(f"companies.api_key пуст (id={self.company_id})")
        return key.strip()

    @staticmethod
    def _get(url: str, token: str) -> dict:
        req = urllib.request.Request(url, headers={"Authorization": token})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                body = ""
            raise RuntimeError(f"WB {e.code} {url} :: {body}") from None

    @staticmethod
    def _row(s: dict) -> dict | None:
        sid = s.get("id")
        if not sid:
            return None
        return {
            "sid": str(sid),
            "nm": (s.get("name") or "")[:255],
            "ca": _dt(s.get("createdAt")),
            "cl": _dt(s.get("closedAt")),
            "sc": _dt(s.get("scanDt")),
            "done": 1 if s.get("done") else 0,
            "ct": s.get("cargoType"),
            "dst": s.get("destinationOfficeId"),
        }

    async def _upsert(self, rows: list, dry_run: bool) -> int:
        if not dry_run and rows:
            await self.db.execute(text("""
                INSERT INTO wb_orders_fbs_supplies(supply_id, name, created_at, closed_at,
                    scan_dt, done, cargo_type, destination_office_id)
                VALUES(:sid, :nm, :ca, :cl, :sc, :done, :ct, :dst) AS new
                ON DUPLICATE KEY UPDATE
                    name = new.name, created_at = new.created_at,
                    closed_at = new.closed_at, scan_dt = new.scan_dt,
                    done = new.done, cargo_type = new.cargo_type,
                    destination_office_id = new.destination_office_id"""), rows)
            await self.db.commit()
        return 0 if dry_run else len(rows)

    async def sync_full(self, dry_run: bool = False) -> dict:
        """Разовый бэкфилл: вся пагинация next. Тяжёлый — только вручную."""
        token = await self._token()
        fetched, rows, pages = 0, [], 0
        cursor = 0
        while True:
            # limit+next оба required (swagger): первый запрос next=0
            qs = {"limit": 1000, "next": cursor}
            url = SUPPLIES_URL + "?" + urllib.parse.urlencode(qs)
            data = self._get(url, token)
            chunk = data.get("supplies") or []
            fetched += len(chunk)
            pages += 1
            for s in chunk:
                r = self._row(s)
                if r:
                    rows.append(r)
            cursor = int(data.get("next") or 0)
            if cursor <= 0 or pages > 500:
                break
        upserted = await self._upsert(rows, dry_run)
        return {"mode": "full", "fetched": fetched, "upserted": upserted,
                "with_scan": sum(1 for r in rows if r["sc"]),
                "pages": pages, "dry_run": dry_run}

    async def sync_incremental(self, dry_run: bool = False,
                               limit: int = 500) -> dict:
        """Крон каждые 30 мин: новые supply_id из wb_orders_fbs (которых нет
        в таблице) + открытые/без скана (done=0 OR scan_dt IS NULL).
        Точечно GET /api/v3/supplies/{id} — дёшево."""
        token = await self._token()
        new_rows = (await self.db.execute(text("""
            SELECT DISTINCT f.supply_id AS sid
            FROM wb_orders_fbs f
            LEFT JOIN wb_orders_fbs_supplies s ON s.supply_id = f.supply_id
            WHERE f.supply_id IS NOT NULL AND f.supply_id <> ''
              AND s.supply_id IS NULL
            LIMIT :lim"""), {"lim": limit})).all()
        open_rows = (await self.db.execute(text("""
            SELECT supply_id AS sid FROM wb_orders_fbs_supplies
            WHERE done = 0 OR scan_dt IS NULL
            LIMIT :lim"""), {"lim": limit})).all()
        targets = [r[0] for r in new_rows] + [r[0] for r in open_rows
                                             if r[0] not in {x[0] for x in new_rows}]
        rows, errors = [], 0
        for sid in targets:
            try:
                s = self._get(
                    SUPPLIES_URL + "/" + urllib.parse.quote(str(sid), safe=""),
                    token)
                if isinstance(s, dict) and "supplies" in s:
                    continue
                r = self._row(s if isinstance(s, dict) else {})
                if r:
                    rows.append(r)
            except Exception:
                errors += 1
        upserted = await self._upsert(rows, dry_run)
        return {"mode": "incremental", "targets": len(targets),
                "new": len(new_rows), "recheck": len(open_rows),
                "upserted": upserted, "errors": errors, "dry_run": dry_run}
