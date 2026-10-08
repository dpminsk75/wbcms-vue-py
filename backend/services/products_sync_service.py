"""Аналитика товаров: stocks-report/products -> wb_products_analytics.

Порт WbProductAnalyticsController (B3): limit/offset=1000, окно days=30
(--days), skipDeletedNm=true, orderBy avgOrders desc, availabilityFilters все.
Снепшот date=today, пауза 20с. Batch-upsert (в PHP построчно).
Токен — companies.api_key (категория analytics). Только stdlib.
"""
import json
import time
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

PRODUCTS_URL = "https://seller-analytics-api.wildberries.ru/api/v2/stocks-report/products/products"
TIMEOUT_S = 15
PAGE_LIMIT = 1000
PAUSE_S = 20
FILTERS = ["deficient", "actual", "balanced", "nonActual", "nonLiquid", "invalidData"]


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


class ProductsSyncService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, days: int = 30, dry_run: bool = False,
                   stock_type: str = "", progress=None) -> dict:
        plan = await company_sync_plan(
            self.db, self.company_id, "analytics", 1,
            pause_fast_s=PAUSE_S, pause_slow_s=PAUSE_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth = f"Bearer {plan['token']}"
        today = date.today().isoformat()
        start = (date.today() - timedelta(days=days - 1)).isoformat()
        offset, total, pages = 0, 0, 0
        while True:
            def _log(m, _p=pages + 1):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(0, 0, st, 0, 0.0, 0.0, PAUSE_S, m)

            t0 = time.monotonic()
            data = post_json(PRODUCTS_URL, {
                "nmIDs": [],
                "currentPeriod": {"start": start, "end": today},
                "stockType": stock_type,
                "skipDeletedNm": True,
                "orderBy": {"field": "avgOrders", "mode": "desc"},
                "availabilityFilters": FILTERS,
                "limit": PAGE_LIMIT, "offset": offset,
            }, auth, timeout=TIMEOUT_S, log=_log if progress else None)
            el = time.monotonic() - t0
            body = data if isinstance(data, dict) else {}
            items = ((body.get("data") or {}).get("items")) or (body.get("items") or [])
            if not items:
                break
            rows = [self._row(today, x) for x in items if x.get("nmID") is not None]
            t1 = time.monotonic()
            if rows and not dry_run:
                await self.db.execute(text("""
                    INSERT INTO wb_products_analytics(company_id, date, nm_id, vendor_code,
                        brand_name, subject_name, name, main_photo, has_sizes, is_deleted,
                        orders_count, orders_sum, avg_orders, avg_orders_by_month,
                        buyout_count, buyout_sum, buyout_percent, stock_count, stock_sum,
                        sale_rate_days, sale_rate_hours, avg_stock_turnover_days,
                        avg_stock_turnover_hours, to_client_count, from_client_count,
                        office_missing_days, office_missing_hours, lost_orders_count,
                        lost_orders_sum, lost_buyouts_count, lost_buyouts_sum,
                        min_price, max_price, availability)
                    VALUES(:cid, :d, :nm, :vc, :br, :sub, :n, :ph, :hs, :dl,
                        :oc, :os, :ao, :aom, :bc, :bs, :bp, :sc, :ss,
                        :srd, :srh, :tod, :toh, :tc, :fc, :omd, :omh,
                        :loc, :los, :lbc, :lbs, :mip, :map, :av) AS new
                    ON DUPLICATE KEY UPDATE
                        vendor_code = new.vendor_code, brand_name = new.brand_name,
                        subject_name = new.subject_name, name = new.name,
                        main_photo = new.main_photo, has_sizes = new.has_sizes,
                        is_deleted = new.is_deleted, orders_count = new.orders_count,
                        orders_sum = new.orders_sum, avg_orders = new.avg_orders,
                        avg_orders_by_month = new.avg_orders_by_month,
                        buyout_count = new.buyout_count, buyout_sum = new.buyout_sum,
                        buyout_percent = new.buyout_percent, stock_count = new.stock_count,
                        stock_sum = new.stock_sum, sale_rate_days = new.sale_rate_days,
                        sale_rate_hours = new.sale_rate_hours,
                        avg_stock_turnover_days = new.avg_stock_turnover_days,
                        avg_stock_turnover_hours = new.avg_stock_turnover_hours,
                        to_client_count = new.to_client_count,
                        from_client_count = new.from_client_count,
                        office_missing_days = new.office_missing_days,
                        office_missing_hours = new.office_missing_hours,
                        lost_orders_count = new.lost_orders_count,
                        lost_orders_sum = new.lost_orders_sum,
                        lost_buyouts_count = new.lost_buyouts_count,
                        lost_buyouts_sum = new.lost_buyouts_sum,
                        min_price = new.min_price, max_price = new.max_price,
                        availability = new.availability"""), rows)
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

    def _row(self, today: str, x: dict) -> dict:
        m = x.get("metrics") or {}
        sr = m.get("saleRate") or {}
        to = m.get("avgStockTurnover") or {}
        om = m.get("officeMissingTime") or {}
        cp = m.get("currentPrice") or {}
        try:
            aom = json.dumps(m.get("avgOrdersByMonth") or [], ensure_ascii=False)
        except (TypeError, ValueError):
            aom = "[]"
        return {
            "cid": self.company_id, "d": today, "nm": int(x["nmID"]),
            "vc": x.get("vendorCode"), "br": x.get("brandName"), "sub": x.get("subjectName"),
            "n": x.get("name"), "ph": x.get("mainPhoto"),
            "hs": 1 if x.get("hasSizes") else 0, "dl": 1 if x.get("isDeleted") else 0,
            "oc": _i(m.get("ordersCount")), "os": _f(m.get("ordersSum")),
            "ao": _f(m.get("avgOrders")), "aom": aom,
            "bc": _i(m.get("buyoutCount")), "bs": _f(m.get("buyoutSum")),
            "bp": _f(m.get("buyoutPercent")),
            "sc": _i(m.get("stockCount")), "ss": _f(m.get("stockSum")),
            "srd": sr.get("days"), "srh": sr.get("hours"),
            "tod": to.get("days"), "toh": to.get("hours"),
            "tc": _i(m.get("toClientCount")), "fc": _i(m.get("fromClientCount")),
            "omd": _i(om.get("days")), "omh": _i(om.get("hours")),
            "loc": _i(m.get("lostOrdersCount")), "los": _f(m.get("lostOrdersSum")),
            "lbc": _i(m.get("lostBuyoutsCount")), "lbs": _f(m.get("lostBuyoutsSum")),
            "mip": _f(cp.get("minPrice")), "map": _f(cp.get("maxPrice")),
            "av": m.get("availability"),
        }
