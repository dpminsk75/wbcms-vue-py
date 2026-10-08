"""Сборочные задания FBS: marketplace orders -> wb_orders_fbs.

Порт WbOrdersFbsController::actionSyncOrders (D3): GET .../api/v3/orders
(limit=200, next-пагинация с защитой, unix-диапазон в МСК; без параметров —
сегодня с 00:00, до 5 утра — вчера+сегодня). Цены WB в копейках → /100.
supply_id=null не затирает известное (багфикс 2026-10-05).
Токен raw без Bearer. Только stdlib.
"""
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json

ORDERS_URL = "https://marketplace-api.wildberries.ru/api/v3/orders"
TIMEOUT_S = 15
PAGE_LIMIT = 200
MSK = timezone(timedelta(hours=3))

COLS = ("company_id", "wb_order_id", "rid", "order_uid", "supply_id", "delivery_type",
        "article", "color_code", "warehouse_id", "office_id", "nm_id", "chrt_id",
        "price", "converted_price", "currency_code", "converted_currency_code",
        "scan_price", "cargo_type", "cross_border_type", "is_zero_order", "is_b2b",
        "is_pickup_point_shipment_allowed", "comment", "wb_created_at",
        "raw_address", "raw_offices", "raw_skus")


def _fnum(v):
    try:
        return round(float(v) / 100, 2)
    except (TypeError, ValueError):
        return 0.0


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


class FbsOrdersService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    def _range(self, date_from, date_to) -> tuple[int, int]:
        if date_from and date_to:
            d0 = datetime.fromisoformat(date_from).replace(tzinfo=MSK)
            d1 = datetime.fromisoformat(date_to).replace(tzinfo=MSK)
            return int(d0.timestamp()), int(d1.timestamp())
        now = datetime.now(MSK)
        start = (now - timedelta(days=1) if now.hour < 5 else now).replace(
            hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp()), int(now.timestamp())

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, progress=None) -> dict:
        plan = await company_sync_plan(
            self.db, self.company_id, "marketplace", 1,
            pause_fast_s=0, pause_slow_s=0)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        d0, d1 = self._range(date_from, date_to)
        total, nxt, pages = 0, 0, 0
        while True:
            def _log(m, _p=pages + 1):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(0, 0, st, 0, 0.0, 0.0, 0, f"стр.{_p}: {m}")

            t0 = time.monotonic()
            data = get_json(ORDERS_URL,
                            [("limit", PAGE_LIMIT), ("next", nxt),
                             ("dateFrom", d0), ("dateTo", d1)],
                            plan["token"], timeout=TIMEOUT_S,
                            log=_log if progress else None)
            el = time.monotonic() - t0
            orders = (data or {}).get("orders") or []
            if not orders:
                break
            rows = [r for r in (self._row(o) for o in orders) if r is not None]
            t1 = time.monotonic()
            if rows and not dry_run:
                for r in rows:
                    cols = [c for c in COLS if c != "supply_id" or r["supply_id"] is not None]
                    await self.db.execute(text(f"""
                        INSERT INTO wb_orders_fbs({", ".join(cols)})
                        VALUES({", ".join(":" + c for c in cols)}) AS new
                        ON DUPLICATE KEY UPDATE
                        {", ".join(f"{c} = new.{c}" for c in cols if c not in ("company_id", "wb_order_id"))}"""),
                        {c: r[c] for c in cols})
                await self.db.commit()
            el_db = time.monotonic() - t1
            total += len(rows)
            pages += 1
            if progress:
                progress(pages, 0, "pause", len(rows), el, el_db, 0)
            new_next = int((data or {}).get("next") or 0)
            if len(orders) < PAGE_LIMIT or new_next == nxt:
                break
            nxt = new_next
        return {"company_id": self.company_id, "pages": pages,
                "saved": 0 if dry_run else total, "fetched": total,
                "token_type": plan.get("token_type"), "dry_run": dry_run}

    def _row(self, o: dict) -> dict | None:
        if o.get("id") is None:
            return None
        opt = o.get("options") or {}
        js = lambda v: json.dumps(v, ensure_ascii=False) if v is not None else None
        return {
            "company_id": self.company_id, "wb_order_id": int(o["id"]),
            "rid": o.get("rid"), "order_uid": o.get("orderUid"),
            "supply_id": o.get("supplyId"), "delivery_type": o.get("deliveryType"),
            "article": o.get("article"), "color_code": o.get("colorCode"),
            "warehouse_id": o.get("warehouseId"), "office_id": o.get("officeId"),
            "nm_id": o.get("nmId"), "chrt_id": o.get("chrtId"),
            "price": _fnum(o.get("price") or 0),
            "converted_price": _fnum(o.get("convertedPrice") or 0),
            "currency_code": o.get("currencyCode"),
            "converted_currency_code": o.get("convertedCurrencyCode"),
            "scan_price": _fnum(o.get("scanPrice") or 0),
            "cargo_type": o.get("cargoType"), "cross_border_type": o.get("crossBorderType"),
            "is_zero_order": 1 if o.get("isZeroOrder") else 0,
            "is_b2b": 1 if opt.get("isB2B") else 0,
            "is_pickup_point_shipment_allowed": 1 if o.get("isPickupPointShipmentAllowed") else 0,
            "comment": o.get("comment"), "wb_created_at": _dt(o.get("createdAt")),
            "raw_address": js(o.get("address")), "raw_offices": js(o.get("offices")),
            "raw_skus": js(o.get("skus")),
        }
