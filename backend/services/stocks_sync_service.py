"""Остатки WB по складам: stocks-report/wb-warehouses -> wb_stocks.

Порт WbStockController (B1): limit/offset=1000, снепшот date=today, пауза 21с
(лимит 1 запр/20с). Нового отчёта нет tech_size текстом — кладём chrtId
(как PHP), пустые поля — нулями. Batch-upsert пачками 500 (в PHP построчно).
Токен — companies.api_key (категория analytics). Только stdlib.
"""
import time
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

STOCKS_URL = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses"
TIMEOUT_S = 15
PAGE_LIMIT = 1000
PAUSE_S = 21


def _i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


class StocksSyncService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, dry_run: bool = False, progress=None) -> dict:
        plan = await company_sync_plan(
            self.db, self.company_id, "analytics", 1,
            pause_fast_s=PAUSE_S, pause_slow_s=PAUSE_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth = f"Bearer {plan['token']}"
        today = date.today().isoformat()
        now = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        offset, total, pages = 0, 0, 0
        while True:
            def _log(m, _p=pages + 1):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(0, 0, st, 0, 0.0, 0.0, PAUSE_S, m)

            t0 = time.monotonic()
            data = post_json(STOCKS_URL, {"locale": "ru", "offset": offset, "limit": PAGE_LIMIT},
                             auth, timeout=TIMEOUT_S, log=_log if progress else None)
            el = time.monotonic() - t0
            body = data if isinstance(data, dict) else {}
            items = ((body.get("data") or {}).get("items")) or (body.get("items") or [])
            if not items:
                break
            rows = [{
                "cid": self.company_id, "d": today, "now": now,
                "wh": x.get("warehouseName"), "nm": int(x.get("nmId")),
                "q": _i(x.get("quantity")), "itc": _i(x.get("inWayToClient")),
                "ifc": _i(x.get("inWayFromClient")), "ch": str(x.get("chrtId") or ""),
            } for x in items if x.get("nmId") is not None]
            t1 = time.monotonic()
            if rows and not dry_run:
                await self.db.execute(text("""
                    INSERT INTO wb_stocks(company_id, date, last_change_date,
                        warehouse_name, supplier_article, nm_id, barcode,
                        quantity, in_way_to_client, in_way_from_client, quantity_full,
                        category, subject, brand, tech_size, price, discount,
                        is_supply, is_realization, sc_code)
                    VALUES(:cid, :d, :now, :wh, NULL, :nm, NULL,
                        :q, :itc, :ifc, :q + :itc + :ifc,
                        NULL, NULL, NULL, :ch, 0, 0, 0, 0, NULL) AS new
                    ON DUPLICATE KEY UPDATE
                        last_change_date = new.last_change_date,
                        quantity = new.quantity,
                        in_way_to_client = new.in_way_to_client,
                        in_way_from_client = new.in_way_from_client,
                        quantity_full = new.quantity_full"""), rows)
                await self.db.commit()
            el_db = time.monotonic() - t1
            total += len(rows)
            pages += 1
            if progress:
                progress(pages, 0, "pause", len(rows), el, el_db, PAUSE_S)
            if len(items) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
            time.sleep(max(0.0, PAUSE_S - el - el_db))
        out = {"company_id": self.company_id, "rows": 0 if dry_run else total,
               "fetched": total, "token_type": plan["token_type"], "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out
