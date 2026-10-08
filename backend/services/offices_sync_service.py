"""Остатки по офисам/регионам: stocks-report/offices -> wb_stocks_offices.

Порт WbStockOfficesController (B2): один запрос на компанию
(currentPeriod сегодня, stockType '' + флаг --stock-type, skipDeletedNm=false).
Регион без складов (Маркетплейс) — строкой с office_id=0. Batch-upsert.
Токен — companies.api_key (категория analytics). Только stdlib.
"""
import time
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

OFFICES_URL = "https://seller-analytics-api.wildberries.ru/api/v2/stocks-report/offices"
TIMEOUT_S = 15


def _i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _f(v):
    try:
        return round(float(v), 2) if v is not None else None
    except (TypeError, ValueError):
        return None


class OfficesSyncService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, dry_run: bool = False, stock_type: str = "",
                   progress=None) -> dict:
        plan = await company_sync_plan(
            self.db, self.company_id, "analytics", 1,
            pause_fast_s=0, pause_slow_s=0)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth = f"Bearer {plan['token']}"
        today = date.today().isoformat()

        def _log(m):
            if progress:
                st = "send" if m == "send" else "retry"
                progress(1, 1, st, 0, 0.0, 0.0, 0, m)

        t0 = time.monotonic()
        data = post_json(OFFICES_URL, {
            "nmIDs": [],
            "currentPeriod": {"start": today, "end": today},
            "stockType": stock_type,
            "skipDeletedNm": False,
        }, auth, timeout=TIMEOUT_S, log=_log if progress else None)
        el = time.monotonic() - t0
        regions = ((data or {}).get("data") or {}).get("regions") or []
        rows = []
        for reg in regions:
            rn = reg.get("regionName")
            offices = reg.get("offices") or []
            if not offices:
                rows.append(self._row(today, rn, 0, None, reg.get("metrics") or {}))
                continue
            for of in offices:
                try:
                    oid = int(of.get("officeID"))
                except (TypeError, ValueError):
                    continue
                rows.append(self._row(today, rn, oid, of.get("officeName"),
                                      of.get("metrics") or {}))
        t1 = time.monotonic()
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_stocks_offices(company_id, date, region_name, office_id,
                    office_name, stock_count, stock_sum, sale_rate_days, sale_rate_hours,
                    to_client_count, from_client_count)
                VALUES(:cid, :d, :rn, :oid, :on, :sc, :ss, :srd, :srh, :tc, :fc) AS new
                ON DUPLICATE KEY UPDATE
                    office_name = new.office_name, stock_count = new.stock_count,
                    stock_sum = new.stock_sum, sale_rate_days = new.sale_rate_days,
                    sale_rate_hours = new.sale_rate_hours,
                    to_client_count = new.to_client_count,
                    from_client_count = new.from_client_count"""), rows)
            await self.db.commit()
        el_db = time.monotonic() - t1
        if progress:
            progress(1, 1, "pause", len(rows), el, el_db, 0)
        out = {"company_id": self.company_id, "regions": len(regions),
               "rows": 0 if dry_run else len(rows), "fetched": len(rows),
               "token_type": plan["token_type"], "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    def _row(self, today: str, rn, oid: int, on, m: dict) -> dict:
        sr = m.get("saleRate") or {}
        return {
            "cid": self.company_id, "d": today, "rn": rn, "oid": oid, "on": on,
            "sc": _i(m.get("stockCount")), "ss": _f(m.get("stockSum")),
            "srd": sr.get("days"), "srh": sr.get("hours"),
            "tc": _i(m.get("toClientCount")), "fc": _i(m.get("fromClientCount")),
        }
