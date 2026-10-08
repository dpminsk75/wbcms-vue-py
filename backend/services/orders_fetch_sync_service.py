"""Заказы WB (полные): supplier/orders -> wb_order.

Порт WbOrdersController::actionFetch (D1): GET statistics-api.../supplier/orders
у метода НЕТ dateTo — режем на своей стороне. Дефолт -3д (FAST каждые 5 мин ок).
Fill-forward barcode/chrtId (однозначный nmID) и supplier_article (vendorCode)
с кешами на прогон; chrt_id нулём не затираем. Upsert по srid, ошибки поштучно.
Токен — companies.api_key raw. Только stdlib.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json

ORDERS_URL = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
TIMEOUT_S = 15


class OrdersFetchService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id
        self._sku: dict = {}
        self._vendor: dict = {}

    async def _barcode(self, nm, barcode):
        if barcode or not nm:
            return barcode, None
        if nm not in self._sku:
            rows = (await self.db.execute(
                text("SELECT sku, chrtID FROM wbcards_sizes WHERE nmID = :nm"),
                {"nm": nm})).all()
            self._sku[nm] = rows[0] if len(rows) == 1 else None
        hit = self._sku[nm]
        if hit is None:
            return barcode, None
        return barcode or hit[0], hit[1]

    async def _vendor_code(self, nm, sa):
        if sa or not nm:
            return sa
        if nm not in self._vendor:
            v = (await self.db.execute(
                text("SELECT vendorCode FROM wbcards WHERE nmID = :nm"),
                {"nm": nm})).scalar()
            self._vendor[nm] = (str(v).strip() or None) if v is not None else None
        return self._vendor[nm] or sa

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, progress=None) -> dict:
        from datetime import date, timedelta
        df = date_from or (date.today() - timedelta(days=3)).isoformat()
        plan = await company_sync_plan(
            self.db, self.company_id, "statistics", 1,
            pause_fast_s=0, pause_slow_s=0)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        data = get_json(f"{ORDERS_URL}?dateFrom={df}", None, plan["token"],
                        timeout=TIMEOUT_S,
                        log=(lambda m: progress(0, 0,
                             "send" if m == "send" else "retry", 0, 0.0, 0.0, 0, m))
                        if progress else None)
        items = data if isinstance(data, list) else []
        saved, errors, skipped_dt = 0, 0, 0
        for x in items:
            if date_to:
                d = str(x.get("date") or "")[:10]
                if not d or d > date_to:
                    skipped_dt += 1
                    continue
            if not x.get("gNumber") or not x.get("date") \
                    or not x.get("lastChangeDate") or not x.get("srid"):
                errors += 1
                continue
            nm = x.get("nmId")
            try:
                nm = int(nm) if nm is not None else None
            except (TypeError, ValueError):
                nm = None
            barcode, chrt = await self._barcode(nm, (x.get("barcode") or None))
            sa = await self._vendor_code(nm, (x.get("supplierArticle") or None))
            cancel = bool(x.get("isCancel"))
            row = {
                "cid": self.company_id, "gn": str(x.get("gNumber") or ""),
                "d": x.get("date"), "lcd": x.get("lastChangeDate"),
                "cd": (x.get("cancelDate") or None) if cancel else None,
                "sa": sa, "ts": x.get("techSize"), "bc": barcode,
                "tp": x.get("totalPrice"), "dp": x.get("discountPercent"),
                "wh": x.get("warehouseName"), "wt": x.get("warehouseType"),
                "co": x.get("countryName"), "ob": x.get("oblastOkrugName"),
                "re": x.get("regionName"), "sale": x.get("saleID"), "od": x.get("odid"),
                "fp": x.get("forPay"), "ot": x.get("orderType"), "inc": x.get("incomeID"),
                "spp": x.get("spp"), "fin": x.get("finishedPrice"),
                "pwd": x.get("priceWithDisc"), "nm": nm,
                "sub": x.get("subject"), "cat": x.get("category"), "br": x.get("brand"),
                "isup": x.get("isSupply", 0), "irea": x.get("isRealization", 0),
                "ica": 1 if cancel else 0, "st": x.get("sticker"),
                "srid": str(x.get("srid")), "ch": chrt,
            }
            cols = ["cid", "gn", "d", "lcd", "cd", "sa", "ts", "bc", "tp", "dp",
                    "wh", "wt", "co", "ob", "re", "sale", "od", "fp", "ot", "inc",
                    "spp", "fin", "pwd", "nm", "sub", "cat", "br",
                    "isup", "irea", "ica", "st", "srid"]
            if chrt is not None:
                cols.append("ch")  # иначе затрём chrt_id от order-feed нулём
            dbcols = {"cid": "company_id", "gn": "g_number", "d": "date",
                      "lcd": "last_change_date", "cd": "cancel_date",
                      "sa": "supplier_article", "ts": "tech_size", "bc": "barcode",
                      "tp": "total_price", "dp": "discount_percent",
                      "wh": "warehouse_name", "wt": "warehouse_type",
                      "co": "country_name", "ob": "oblast_okrug_name",
                      "re": "region_name", "sale": "sale_id", "od": "odid",
                      "fp": "for_pay", "ot": "order_type", "inc": "income_id",
                      "spp": "spp", "fin": "finished_price", "pwd": "price_with_disc",
                      "nm": "nm_id", "sub": "subject", "cat": "category",
                      "br": "brand", "isup": "is_supply", "irea": "is_realization",
                      "ica": "is_cancel", "st": "sticker", "srid": "srid",
                      "ch": "chrt_id"}
            upd = ", ".join(f"{dbcols[k]} = new.{dbcols[k]}" for k in cols if k != "cid")
            try:
                if not dry_run:
                    await self.db.execute(text(f"""
                        INSERT INTO wb_order({", ".join(dbcols[k] for k in cols)})
                        VALUES({", ".join(":" + k for k in cols)}) AS new
                        ON DUPLICATE KEY UPDATE {upd}"""),
                        {"cid": self.company_id,
                         **{k: row[k] for k in cols if k != "cid"}})
                saved += 1
            except Exception:
                errors += 1
        if not dry_run:
            await self.db.commit()
        if progress:
            progress(1, errors, "pause", saved, 0.0, 0.0, 0)
        return {"company_id": self.company_id, "fetched": len(items),
                "saved": 0 if dry_run else saved, "errors": errors,
                "skipped_date": skipped_dt, "token_type": plan["token_type"],
                "dry_run": dry_run}
