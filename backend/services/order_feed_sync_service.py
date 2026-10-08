"""Заказы WB (статусы): order-feed -> wb_order.

Порт WbOrdersController::actionFetchOrderFeed (D2): POST seller-analytics.../order-feed
{selectedPeriod (МСК), pagination limit=1000/offset + snapshotTime}, пауза 200мс.
Пишет ТОЛЬКО статусные поля (на update описательные не трогаем — их залил D1);
на insert — всё + g_number=srid (NOT NULL). Upsert по srid, ошибки поштучно.
Токен — companies.api_key raw. Только stdlib.
"""
import time
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

FEED_URL = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/order-feed"
TIMEOUT_S = 15
PAGE_LIMIT = 1000

STATUS_COLS = ("company_id", "srid", "last_change_date", "status", "cancel_type",
               "is_cancel", "cancel_date", "is_mp", "is_b2b", "chrt_id",
               "destination_city")
INSERT_COLS = ("date", "nm_id", "warehouse_type", "warehouse_name",
               "oblast_okrug_name", "price_with_disc", "g_number")


def _mdt(iso) -> str | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso)).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _wh(raw: str) -> tuple:
    raw = (raw or "").strip()
    if not raw:
        return None, None
    pre = "Склад продавца"
    if raw.lower().startswith(pre.lower()):
        rest = raw[len(pre):].strip()
        return "Склад продавца", (rest or None)
    return "Склад WB", raw


class OrderFeedService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, progress=None) -> dict:
        df = date_from or (date.today() - timedelta(days=3)).isoformat()
        dt = date_to or date.today().isoformat()
        plan = await company_sync_plan(
            self.db, self.company_id, "statistics", 1,
            pause_fast_s=0, pause_slow_s=0)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        start = f"{df}T00:00:00.00000+03:00"
        end = f"{dt}T23:59:59.00000+03:00"  # период в МСК, как PHP
        offset, snap, saved, errors, pages = 0, None, 0, 0, 0
        while True:
            body = {"selectedPeriod": {"start": start, "end": end},
                    "pagination": {"limit": PAGE_LIMIT, "offset": offset}}
            if snap:
                body["pagination"]["snapshotTime"] = snap

            def _log(m, _p=pages + 1):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(0, 0, st, 0, 0.0, 0.0, 0, f"стр.{_p}: {m}")

            t0 = time.monotonic()
            data = post_json(FEED_URL, body, plan["token"], timeout=TIMEOUT_S,
                             log=_log if progress else None)
            el = time.monotonic() - t0
            d = data if isinstance(data, dict) else {}
            dd = d.get("data") or {}
            orders = dd.get("orders") or []
            if snap is None and dd.get("snapshotTime"):
                snap = dd["snapshotTime"]
            if not orders:
                break
            t1 = time.monotonic()
            for x in orders:
                srid = x.get("srid")
                if not srid or not x.get("createdAt") or not x.get("updatedAt"):
                    errors += 1
                    continue
                cancel = (x.get("status") or "") == "cancel"
                wt, wn = _wh(x.get("warehouseName") or "")
                st_vals = {
                    "company_id": self.company_id, "srid": str(srid),
                    "last_change_date": _mdt(x.get("updatedAt")),
                    "status": x.get("status"),
                    "cancel_type": x.get("cancelType"),
                    "is_cancel": 1 if cancel else 0,
                    "cancel_date": _mdt(x.get("updatedAt")) if cancel else None,
                    "is_mp": x.get("isMp"), "is_b2b": x.get("isB2b"),
                    "chrt_id": x.get("chrtId"),
                    "destination_city": (x.get("destinationCity") or "").strip() or None,
                }
                ins_vals = {
                    "date": _mdt(x.get("createdAt")), "nm_id": x.get("nmId"),
                    "warehouse_type": wt, "warehouse_name": wn,
                    "oblast_okrug_name": (x.get("destinationDistrict") or "").strip() or None,
                    "price_with_disc": x.get("sellerPrice"),
                    "g_number": str(srid),
                }
                try:
                    if not dry_run:
                        await self.db.execute(text(f"""
                            INSERT INTO wb_order({", ".join(STATUS_COLS + INSERT_COLS)})
                            VALUES({", ".join(":" + c for c in STATUS_COLS + INSERT_COLS)}) AS new
                            ON DUPLICATE KEY UPDATE
                            {", ".join(f"{c} = new.{c}" for c in STATUS_COLS if c not in ("company_id", "srid"))}"""),
                            {**st_vals, **ins_vals})
                    saved += 1
                except Exception:
                    errors += 1
            el_db = time.monotonic() - t1
            pages += 1
            if progress:
                progress(pages, 0, "pause", len(orders), el, el_db, 0)
            if len(orders) < PAGE_LIMIT or pages >= 1000:
                break
            offset += len(orders)
            time.sleep(0.2)
        if not dry_run:
            await self.db.commit()
        return {"company_id": self.company_id, "pages": pages,
                "saved": 0 if dry_run else saved, "errors": errors,
                "token_type": plan["token_type"], "dry_run": dry_run}
