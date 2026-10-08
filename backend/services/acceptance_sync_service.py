"""Приёмка WB: async acceptance_report -> wb_acceptance_report.

Порт WbAcceptanceReportController (C2): чанки 31д, дефолт вчера,
65с между чанками, 2с между компаниями. Upsert пачками 500
(ключ company+income+nm+giDate+shkDate), пропуск без incomeId/nmId.
Токен — companies.api_key (категория analytics). Только stdlib.
"""
import time
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, run_async_report

BASE = "https://seller-analytics-api.wildberries.ru"
CHUNK_DAYS = 31
PAUSE_CHUNK_S = 65


def _dt(v):
    if not v:
        return None
    s = str(v)[:10]
    try:
        date.fromisoformat(s)
        return s
    except ValueError:
        return None


def _days(df: str, dt: str, n: int = CHUNK_DAYS):
    d0, out = date.fromisoformat(df), []
    d1 = date.fromisoformat(dt)
    while d0 <= d1:
        e = min(d0 + timedelta(days=n - 1), d1)
        out.append((d0.isoformat(), e.isoformat()))
        d0 = e + timedelta(days=1)
    return out


class AcceptanceService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, progress=None) -> dict:
        yd = (date.today() - timedelta(days=1)).isoformat()
        df, dt = date_from or yd, date_to or date_from or yd
        chunks = _days(df, dt)
        plan = await company_sync_plan(
            self.db, self.company_id, "analytics", len(chunks),
            pause_fast_s=PAUSE_CHUNK_S, pause_slow_s=PAUSE_CHUNK_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth = plan["token"]
        total = 0
        for i, (cf, ct) in enumerate(chunks):
            def _log(m, _i=i, _n=len(chunks)):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(0, 0, st, 0, 0.0, 0.0, 0, f"кусок {_i + 1}/{_n}: {m}")

            t0 = time.monotonic()
            rows = run_async_report(BASE, "acceptance_report", auth, cf, ct,
                                    log=_log if progress else None)
            el = time.monotonic() - t0
            mapped = [r for r in (self._row(x) for x in rows) if r is not None]
            if mapped and not dry_run:
                await self._save(mapped)
            total += len(mapped)
            if progress:
                progress(i + 1, len(chunks), "pause", len(mapped), el, 0.0, PAUSE_CHUNK_S)
            if i + 1 < len(chunks):
                time.sleep(PAUSE_CHUNK_S)
        out = {"company_id": self.company_id, "chunks": len(chunks),
               "rows": 0 if dry_run else total, "fetched": total,
               "token_type": plan["token_type"], "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    def _row(self, x: dict) -> dict | None:
        nm, inc = x.get("nmID", x.get("nmId")), x.get("incomeId")
        try:
            nm, inc = int(nm), int(inc)
        except (TypeError, ValueError):
            return None
        return {
            "cid": self.company_id, "inc": inc, "nm": nm,
            "c": x.get("count"), "gi": _dt(x.get("giCreateDate")),
            "shk": _dt(x.get("shkCreateDate")), "sub": x.get("subjectName"),
            "t": x.get("total"),
        }

    async def _save(self, rows: list) -> None:
        for i in range(0, len(rows), 500):
            try:
                await self.db.execute(text("""
                    INSERT INTO wb_acceptance_report(company_id, incomeId, nmId, count,
                        giCreateDate, shkCreateDate, subjectName, total)
                    VALUES(:cid, :inc, :nm, :c, :gi, :shk, :sub, :t) AS new
                    ON DUPLICATE KEY UPDATE
                        count = new.count, subjectName = new.subjectName,
                        total = new.total"""), rows[i:i + 500])
            except Exception:
                for r in rows[i:i + 500]:
                    try:
                        await self.db.execute(text("""
                            INSERT INTO wb_acceptance_report(company_id, incomeId, nmId, count,
                                giCreateDate, shkCreateDate, subjectName, total)
                            VALUES(:cid, :inc, :nm, :c, :gi, :shk, :sub, :t) AS new
                            ON DUPLICATE KEY UPDATE
                                count = new.count, subjectName = new.subjectName,
                                total = new.total"""), r)
                    except Exception:
                        pass
        await self.db.commit()
