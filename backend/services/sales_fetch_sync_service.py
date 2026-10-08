"""Продажи WB: supplier/sales -> wb_sales + линковка wb_order.

Порт WbSalesController::actionFetch (S): GET statistics-api.../supplier/sales
(flag=0 — параметр URL, не CLI; дефолт -3д), пауза 1с между компаниями.
Fill-forward barcode (однозначный nmID) и supplierArticle (vendorCode) с кешами.
Upsert по PK saleID (глобальный), company_id пишем всегда. Связка:
UPDATE wb_order SET sale_id/income_id/sale_date по srid.
Токен — companies.api_key raw. Только stdlib.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json

SALES_URL = "https://statistics-api.wildberries.ru/api/v1/supplier/sales"
TIMEOUT_S = 15

COLS = ("saleID", "company_id", "nmId", "supplierArticle", "barcode", "date",
        "warehouseName", "warehouseType", "countryName", "regionName",
        "oblastOkrugName", "category", "subject", "brand", "techSize",
        "totalPrice", "discountPercent", "priceWithDisc", "spp", "finishedPrice",
        "paymentSaleAmount", "forPay", "saleEvents", "orderType", "isSupply",
        "isRealization", "sticker", "gNumber", "number", "lastChangeDate",
        "incomeID", "srid")


class SalesFetchService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id
        self._sku: dict = {}
        self._vendor: dict = {}

    async def _barcode(self, nm, barcode):
        if barcode or not nm:
            return barcode
        if nm not in self._sku:
            rows = (await self.db.execute(
                text("SELECT sku FROM wbcards_sizes WHERE nmID = :nm"),
                {"nm": nm})).all()
            self._sku[nm] = rows[0][0] if len(rows) == 1 else None
        return self._sku[nm] or barcode

    async def _vendor_code(self, nm, sa):
        if sa or not nm:
            return sa
        if nm not in self._vendor:
            v = (await self.db.execute(
                text("SELECT vendorCode FROM wbcards WHERE nmID = :nm"),
                {"nm": nm})).scalar()
            self._vendor[nm] = (str(v).strip() or None) if v is not None else None
        return self._vendor[nm] or sa

    async def sync(self, date_from: str | None = None, dry_run: bool = False,
                   progress=None) -> dict:
        from datetime import date, timedelta
        df = date_from or (date.today() - timedelta(days=3)).isoformat()
        plan = await company_sync_plan(
            self.db, self.company_id, "statistics", 1,
            pause_fast_s=0, pause_slow_s=0)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        data = get_json(f"{SALES_URL}?flag=0&dateFrom={df}", None, plan["token"],
                        timeout=TIMEOUT_S,
                        log=(lambda m: progress(0, 0,
                             "send" if m == "send" else "retry", 0, 0.0, 0.0, 0, m))
                        if progress else None)
        items = data if isinstance(data, list) else []
        saved, errors, linked, notfound = 0, 0, 0, 0
        for x in items:
            try:
                nm = x.get("nmId")
                try:
                    nm = int(nm) if nm is not None else None
                except (TypeError, ValueError):
                    nm = None
                row = {
                    "saleID": x.get("saleID"), "company_id": self.company_id,
                    "nmId": nm,
                    "supplierArticle": await self._vendor_code(
                        nm, (x.get("supplierArticle") or None)),
                    "barcode": await self._barcode(nm, (x.get("barcode") or None)),
                    "date": x.get("date"), "warehouseName": x.get("warehouseName"),
                    "warehouseType": x.get("warehouseType"),
                    "countryName": x.get("countryName"), "regionName": x.get("regionName"),
                    "oblastOkrugName": x.get("oblastOkrugName"),
                    "category": x.get("category"), "subject": x.get("subject"),
                    "brand": x.get("brand"), "techSize": x.get("techSize"),
                    "totalPrice": x.get("totalPrice"),
                    "discountPercent": x.get("discountPercent"),
                    "priceWithDisc": x.get("priceWithDisc"), "spp": x.get("spp"),
                    "finishedPrice": x.get("finishedPrice"),
                    "paymentSaleAmount": x.get("paymentSaleAmount"),
                    "forPay": x.get("forPay"), "saleEvents": x.get("saleEvents"),
                    "orderType": x.get("orderType"), "isSupply": x.get("isSupply"),
                    "isRealization": x.get("isRealization"), "sticker": x.get("sticker"),
                    "gNumber": x.get("gNumber"), "number": x.get("number"),
                    "lastChangeDate": x.get("lastChangeDate"),
                    "incomeID": x.get("incomeID"), "srid": x.get("srid"),
                }
                if not row["saleID"]:
                    errors += 1
                    continue
                if not dry_run:
                    await self.db.execute(text(f"""
                        INSERT INTO wb_sales({", ".join(COLS)})
                        VALUES({", ".join(":" + c for c in COLS)}) AS new
                        ON DUPLICATE KEY UPDATE
                        {", ".join(f"{c} = new.{c}" for c in COLS if c != "saleID")}"""),
                        row)
                    if x.get("srid"):
                        r = await self.db.execute(text("""
                            UPDATE wb_order SET sale_id = :sale, income_id = :inc,
                                sale_date = :d
                            WHERE srid = :srid AND company_id = :cid"""),
                            {"sale": x.get("saleID"), "inc": x.get("incomeID"),
                             "d": x.get("date"), "srid": x.get("srid"),
                             "cid": self.company_id})
                        if (r.rowcount or 0) > 0:
                            linked += 1
                        else:
                            notfound += 1
                saved += 1
            except Exception:
                errors += 1
        if not dry_run:
            await self.db.commit()
        if progress:
            progress(1, errors, "pause", saved, 0.0, 0.0, 0)
        return {"company_id": self.company_id, "fetched": len(items),
                "saved": 0 if dry_run else saved, "errors": errors,
                "linked": linked, "orders_not_found": notfound,
                "token_type": plan.get("token_type"), "dry_run": dry_run}
