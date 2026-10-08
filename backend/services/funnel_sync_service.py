"""Воронка продаж WB: sales-funnel history -> wb_sales_funnel_history.

Порт commands/WbFunnelController (sync + sync-missing). Разовый бэкфилл —
флагами --date-from/--date-to (sync-history отдельно не переносим).
Токен — companies.api_key (категория analytics в company_wb_tokens),
гейт + паузы — wb_sync_base (personal/service 20с, basic 30мин, правило 2ч).
Только stdlib.
"""
import time
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

HISTORY_URL = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history"
TIMEOUT_S = 15  # ответы реально ~0.2с; 15с — чтобы stall хендшейка стоил 15с, а не 30
CHUNK = 20  # жёсткий лимит WB: nmIds [1..20] для /history (доки 2026-10-07)


def _num(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _fnum(v):
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


class FunnelSyncService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def _nm_ids(self, missing_only: bool, date_from: str,
                      include_inactive: bool = False) -> tuple[list[int], int]:
        """nmId компании; по дефолту только «живые»: заказы в wb_order за 30д
        до date_from или карточка создана за те же 30д (новинки без продаж).
        Возвращает (активные, всего). IN-списками по idx_nm_date — подзапрос
        DISTINCT по всей wb_order (11М) висит минутами, так не делаем."""
        from datetime import datetime
        cutoff = (date.fromisoformat(date_from) - timedelta(days=30)).isoformat()
        cards = (await self.db.execute(text("""
            SELECT nmID, created_at FROM wbcards WHERE company_id = :cid"""),
            {"cid": self.company_id})).all()
        cards = [(int(r[0]), r[1]) for r in cards if r[0] is not None]
        if include_inactive:
            ids = [nm for nm, _ in cards]
        else:
            fresh = []
            rest = []
            for nm, ca in cards:
                cas = ca.isoformat() if isinstance(ca, datetime) else str(ca or "")
                (fresh if cas >= cutoff else rest).append(nm)
            hit = set(fresh)
            for i in range(0, len(rest), 500):
                batch = [str(x) for x in rest[i:i + 500]]
                ph = ",".join(f":n{j}" for j in range(len(batch)))
                rows = (await self.db.execute(text(f"""
                    SELECT DISTINCT nm_id FROM wb_order
                    WHERE company_id = :cid AND date >= :cutoff
                      AND nm_id IN ({ph})"""),
                    {"cid": self.company_id, "cutoff": cutoff,
                     **{f"n{j}": v for j, v in enumerate(batch)}})).all()
                hit.update(int(r[0]) for r in rows if r[0] is not None
                           and str(r[0]).isdigit())
            ids = [nm for nm, _ in cards if nm in hit]
        if missing_only:
            have = {int(r[0]) for r in (await self.db.execute(text("""
                SELECT DISTINCT nmID FROM wb_sales_funnel_history
                WHERE company_id = :cid AND date >= :df"""),
                {"cid": self.company_id, "df": date_from})).all()
                if r[0] is not None}
            ids = [nm for nm in ids if nm not in have]
        return ids, len(cards)

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, missing_only: bool = False,
                   include_inactive: bool = False, progress=None) -> dict:
        df = date_from or (date.today() - timedelta(days=7)).isoformat()
        dt = date_to or date.today().isoformat()
        nm_ids, total_nm = await self._nm_ids(missing_only, df, include_inactive)
        if not nm_ids:
            return {"company_id": self.company_id, "nm_ids": 0, "total_nm_ids": total_nm,
                    "upserted": 0, "dry_run": dry_run, "missing_only": missing_only}
        chunks = [nm_ids[i:i + CHUNK] for i in range(0, len(nm_ids), CHUNK)]
        plan = await company_sync_plan(
            self.db, self.company_id, "analytics", len(chunks),
            pause_fast_s=20, pause_slow_s=1800)
        if plan.get("skip"):
            return {"company_id": self.company_id, "nm_ids": len(nm_ids),
                    "skipped": plan["skip"], "token_type": plan.get("token_type"),
                    "dry_run": dry_run, "missing_only": missing_only}
        auth, pause = f"Bearer {plan['token']}", plan["pause_s"]
        upserted = 0
        for i, chunk in enumerate(chunks):
            t0 = time.monotonic()

            def _log(m, _i=i, _n=len(chunks)):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(_i + 1, _n, st, 0, 0.0, 0.0, pause, m)

            data = post_json(HISTORY_URL, {
                "selectedPeriod": {"start": df, "end": dt},
                "nmIds": [int(x) for x in chunk],
                "aggregationLevel": "day",
            }, auth, timeout=TIMEOUT_S, log=_log if progress else None)
            el = time.monotonic() - t0
            rows = self._rows(data if isinstance(data, list) else [])
            if progress:
                progress(i + 1, len(chunks), "api", len(rows), el, 0.0, pause)
            t1 = time.monotonic()
            if rows and not dry_run:
                await self.db.execute(text("""
                    INSERT INTO wb_sales_funnel_history(
                        company_id, nmID, date,
                        openCount, cartCount, orderCount, orderSum, buyoutCount, buyoutSum)
                    VALUES(:cid, :nm, :d, :o, :c, :oc, :os, :bc, :bs) AS new
                    ON DUPLICATE KEY UPDATE
                        openCount = new.openCount, cartCount = new.cartCount,
                        orderCount = new.orderCount, orderSum = new.orderSum,
                        buyoutCount = new.buyoutCount, buyoutSum = new.buyoutSum"""), rows)
                await self.db.commit()
            upserted += len(rows)
            el_db = time.monotonic() - t1
            wait = max(0.0, pause - el - el_db)  # цикл держим ~pause: 20 − потраченное
            if progress:
                progress(i + 1, len(chunks), "db", len(rows), el, el_db, wait)
                progress(i + 1, len(chunks), "pause", len(rows), el, el_db, wait)
            if i + 1 < len(chunks):
                time.sleep(wait)
        out = {"company_id": self.company_id, "nm_ids": len(nm_ids),
               "total_nm_ids": total_nm,
               "chunks": len(chunks), "upserted": 0 if dry_run else upserted,
               "token_type": plan["token_type"], "dry_run": dry_run,
               "missing_only": missing_only}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    def _rows(self, data: list) -> list[dict]:
        rows = []
        for item in data:
            prod = (item or {}).get("product") or {}
            hist = (item or {}).get("history") or []
            try:
                nm = int(prod.get("nmId"))
            except (TypeError, ValueError):
                continue
            for d in hist:
                if not (d or {}).get("date"):
                    continue
                rows.append({
                    "cid": self.company_id, "nm": nm, "d": d["date"],
                    "o": _num(d.get("openCount")), "c": _num(d.get("cartCount")),
                    "oc": _num(d.get("orderCount")), "os": _fnum(d.get("orderSum")),
                    "bc": _num(d.get("buyoutCount")), "bs": _fnum(d.get("buyoutSum")),
                })
        return rows
