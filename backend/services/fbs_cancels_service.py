"""«FBS Отмены» (/fbs-cancels): отморожено только статусами FBS + суммами.

Анализ §9 (2026-10-05_fbs-report-analysis.md): продавец/покупатель/отказ
(шт + ≈₽ до СПП), всего (% от заданий + ₽), по складам. Без штрафов,
без таблицы по товарам (v1), без фильтра склада. Бакеты — из fbs_report_service.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.fbs_report_service import BUCKET_CASE


class FbsCancelsService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _params(self, date_from: str, date_to: str, nm_id: int | None,
                brand: str | None, category: str | None) -> dict:
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if self.company_id is not None:
            params["company_id"] = self.company_id
        if nm_id:
            params["nm_id"] = nm_id
        if brand:
            params["brand"] = brand
        if category:
            params["category"] = category
        return params

    def _extra(self, nm_id: int | None, brand: str | None,
               category: str | None) -> str:
        w = " AND o.warehouse_type = 'Склад продавца'"
        if self.company_id is not None:
            w += " AND o.company_id = :company_id"
        if nm_id:
            w += " AND o.nm_id = :nm_id"
        if brand:
            w += " AND o.brand = :brand"
        if category:
            w += " AND o.category = :category"
        return w

    def _latest_status_join(self) -> str:
        comp = "WHERE company_id = :company_id" if self.company_id is not None else ""
        outer = ("WHERE s1.company_id = :company_id"
                 if self.company_id is not None else "")
        return f"""LEFT JOIN (
            SELECT s1.wb_order_id, s1.supplier_status, s1.wb_status
            FROM wb_orders_fbs_statuses s1
            JOIN (SELECT wb_order_id, MAX(id) AS max_id
                  FROM wb_orders_fbs_statuses {comp} GROUP BY wb_order_id) m
              ON m.wb_order_id = s1.wb_order_id AND m.max_id = s1.id
            {outer}
        ) ls ON ls.wb_order_id = f.wb_order_id"""

    def _from(self) -> str:
        return f"""FROM wb_order o
            LEFT JOIN wb_orders_fbs f ON f.rid = o.srid AND f.company_id = o.company_id
            {self._latest_status_join()}"""

    async def summary(self, date_from: str, date_to: str, nm_id: int | None = None,
                      brand: str | None = None, category: str | None = None) -> dict:
        params = self._params(date_from, date_to, nm_id, brand, category)
        where = (f"o.date BETWEEN :d1 AND :d2"
                 f"{self._extra(nm_id, brand, category)}")
        sums = ",\n".join(
            f"SUM(CASE WHEN {BUCKET_CASE} = '{b}' THEN 1 ELSE 0 END) AS {b}_cnt,"
            f" SUM(CASE WHEN {BUCKET_CASE} = '{b}' "
            f"THEN COALESCE(o.price_with_disc, 0) ELSE 0 END) AS {b}_sum"
            for b in ("seller_cancel", "buyer_cancel", "declined"))
        row = (await self.db.execute(text(f"""SELECT COUNT(*) AS tasks_cnt,
                {sums}
            {self._from()} WHERE {where}"""), params)).mappings().first()
        g = lambda k: int(row[k] or 0)
        f = lambda k: float(row[k] or 0)
        sc, bc, dc = g("seller_cancel_cnt"), g("buyer_cancel_cnt"), g("declined_cnt")
        canceled = sc + bc + dc
        csum = f("seller_cancel_sum") + f("buyer_cancel_sum") + f("declined_sum")
        tasks = g("tasks_cnt")
        return {
            "seller": {"cnt": sc, "sum": f("seller_cancel_sum")},
            "buyer": {"cnt": bc, "sum": f("buyer_cancel_sum")},
            "declined": {"cnt": dc, "sum": f("declined_sum")},
            "total": {"tasks_cnt": tasks, "canceled_cnt": canceled,
                      "canceled_sum": round(csum, 2),
                      "pct": round(canceled / tasks * 100, 1) if tasks else 0},
        }

    async def orders(self, bucket: str, date_from: str, date_to: str,
                     nm_id: int | None = None, brand: str | None = None,
                     category: str | None = None,
                     warehouse_id: int | None = None,
                     limit: int = 500) -> dict:
        """Списки отменённых для попапа: bucket =
        seller_cancel|buyer_cancel|declined|all (+опционально склад)."""
        buckets = ("seller_cancel", "buyer_cancel", "declined")
        if bucket != "all" and bucket not in buckets:
            raise ValueError("bucket: all|seller_cancel|buyer_cancel|declined")
        wanted = buckets if bucket == "all" else (bucket,)
        params = self._params(date_from, date_to, nm_id, brand, category)
        params["lim"] = max(1, min(limit, 1000))
        cond = " OR ".join(f"{BUCKET_CASE} = '{b}'" for b in wanted)
        wh = ""
        if warehouse_id:
            # NULL-склад (без сборочного задания): пропустить нельзя — фильтруем IS NULL
            if int(warehouse_id) == 0:
                wh = " AND f.warehouse_id IS NULL"
            else:
                wh = " AND f.warehouse_id = :wid"
                params["wid"] = warehouse_id
        card_comp = ("AND c.company_id = o.company_id"
                     if self.company_id is not None else "")
        rows = (await self.db.execute(text(f"""SELECT f.wb_order_id AS oid,
                o.g_number AS g_number, o.srid AS srid, o.date AS odate,
                COALESCE(wh.name, '—') AS wname,
                o.nm_id AS order_nm_id, c.title AS card_title,
                c.vendorCode AS vendor_code,
                o.tech_size AS tech_size, o.barcode AS barcode,
                o.price_with_disc AS price,
                {BUCKET_CASE} AS bucket
            {self._from()}
            LEFT JOIN wb_fbs_warehouse wh
                ON wh.warehouseId = f.warehouse_id AND wh.company_id = o.company_id
            LEFT JOIN wbcards c ON c.nmID = o.nm_id {card_comp}
            WHERE o.date BETWEEN :d1 AND :d2{self._extra(nm_id, brand, category)}{wh}
              AND ({cond})
            ORDER BY o.date DESC LIMIT :lim"""), params)).mappings().all()
        return {"bucket": bucket, "items": [{
            "wb_order_id": r["oid"], "g_number": r["g_number"], "srid": r["srid"],
            "date": str(r["odate"])[:16], "warehouse": r["wname"],
            "nm_id": r["order_nm_id"], "title": r["card_title"],
            "vendor_code": r["vendor_code"],
            "tech_size": r["tech_size"], "barcode": r["barcode"],
            "price": float(r["price"] or 0), "bucket": r["bucket"],
        } for r in rows]}

    async def by_warehouse(self, date_from: str, date_to: str, nm_id: int | None = None,
                           brand: str | None = None,
                           category: str | None = None) -> dict:
        params = self._params(date_from, date_to, nm_id, brand, category)
        where = (f"o.date BETWEEN :d1 AND :d2"
                 f"{self._extra(nm_id, brand, category)}")
        sums = ",\n".join(
            f"SUM(CASE WHEN {BUCKET_CASE} = '{b}' THEN 1 ELSE 0 END) AS {b}_cnt"
            for b in ("seller_cancel", "buyer_cancel", "declined"))
        rows = (await self.db.execute(text(f"""SELECT f.warehouse_id AS wid,
                COALESCE(wh.name, '—') AS wname, COUNT(*) AS tasks_cnt,
                COALESCE(SUM(CASE WHEN {BUCKET_CASE} = 'seller_cancel'
                    THEN o.price_with_disc ELSE 0 END), 0) AS lost_sum,
                COALESCE(SUM(CASE WHEN {BUCKET_CASE} IN
                    ('seller_cancel', 'buyer_cancel', 'declined')
                    THEN o.price_with_disc ELSE 0 END), 0) AS total_sum,
                {sums}
            {self._from()}
            LEFT JOIN wb_fbs_warehouse wh
                ON wh.warehouseId = f.warehouse_id AND wh.company_id = o.company_id
            WHERE {where}
            GROUP BY f.warehouse_id, wh.name
            ORDER BY lost_sum DESC"""), params)).mappings().all()
        return {"items": [{
            "warehouse_id": r["wid"], "warehouse_name": r["wname"],
            "seller_cnt": int(r["seller_cancel_cnt"] or 0),
            "buyer_cnt": int(r["buyer_cancel_cnt"] or 0),
            "declined_cnt": int(r["declined_cnt"] or 0),
            "lost_sum": float(r["lost_sum"] or 0),
            "total_sum": float(r["total_sum"] or 0),
        } for r in rows]}
