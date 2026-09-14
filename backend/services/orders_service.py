"""Порт WbOrderFeedSearch.php:238 — лента заказов"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

STATUS_MAP = ['Новый','Сборка','В пути','На ПВЗ','Выкуплен','Отменён','Отмена клиентом','Брак']

def build_status_where(status: str):
    # упрощенная версия buildStatusCondition:145 — пока фильтрация по вычисляемому статусу в Python, не SQL
    # для прототипа возвращаем None (без фильтра), позже добавим точный SQL
    return None

class OrdersService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def feed(self, nm_id: int | None, date_from: str, date_to: str, status: str | None, warehouse_name: str | None, region_name: str | None, page: int = 1, page_size: int = 50):
        # базовый запрос как в buildBaseQuery:200 + search:244
        where = ["o.date BETWEEN :d1 AND :d2"]
        params = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59", "off": (page-1)*page_size, "lim": page_size}
        if nm_id:
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = nm_id
        if warehouse_name:
            where.append("o.warehouse_name = :wh")
            params["wh"] = warehouse_name
        if region_name:
            where.append("o.region_name = :rg")
            params["rg"] = region_name

        where_sql = " AND ".join(where)
        # total + summary как getSummaryStats:112
        cnt_sql = text(f"SELECT COUNT(*) as cnt, SUM(o.price_with_disc) as sum_price, AVG(o.spp) as avg_spp, SUM(CASE WHEN o.warehouse_type='Склад продавца' THEN 1 ELSE 0 END) as fbs_cnt, SUM(CASE WHEN o.warehouse_type<>'Склад продавца' OR o.warehouse_type IS NULL THEN 1 ELSE 0 END) as fbo_cnt FROM wb_order o WHERE {where_sql}")
        srow = (await self.db.execute(cnt_sql, params)).mappings().first()
        total = int(srow["cnt"] or 0) if srow else 0
        summary = {"count": total, "sum": float(srow["sum_price"] or 0) if srow else 0, "avg_spp": float(srow["avg_spp"] or 0) if srow else 0, "fbs_count": int(srow["fbs_cnt"] or 0), "fbo_count": int(srow["fbo_cnt"] or 0)}

        sql = text(f"""
            SELECT o.*, c.title as card_title, c.vendorCode as card_vendor_code, c.subjectName as card_subject_name, c.brand as card_brand, c.photos as card_photos,
                   f.supply_id as fbs_supply_id, wh.name as fbs_warehouse_name,
                   ls.supplier_status as fbs_supplier_status, ls.wb_status as fbs_wb_status, ls.created_at as fbs_status_changed_at,
                   o.warehouse_name, o.region_name, o.warehouse_type, o.price_with_disc, o.spp, o.total_price, o.discount_percent, o.finished_price, o.commission_fee, o.commission_percent, o.acquiring_fee, o.acquiring_percent, o.cashback_amount, o.delivery_rub, o.return_rub, o.is_cancel, o.sale_date, o.last_change_date, o.category, o.destination_city
            FROM wb_order o
            LEFT JOIN wbcards c ON c.nmID = o.nm_id
            LEFT JOIN wb_orders_fbs f ON f.rid = o.srid
            LEFT JOIN (
                SELECT s1.wb_order_id, s1.supplier_status, s1.wb_status, s1.created_at FROM wb_orders_fbs_statuses s1
                JOIN (SELECT wb_order_id, MAX(id) as max_id FROM wb_orders_fbs_statuses GROUP BY wb_order_id) m ON m.wb_order_id=s1.wb_order_id AND m.max_id=s1.id
            ) ls ON ls.wb_order_id = f.wb_order_id
            LEFT JOIN wb_fbs_warehouse wh ON wh.warehouseId = f.warehouse_id AND wh.company_id = o.company_id
            WHERE {where_sql}
            ORDER BY o.date DESC LIMIT :lim OFFSET :off
        """)
        rows = (await self.db.execute(sql, params)).mappings().all()
        items = [dict(r) for r in rows]
        return {"total": total, "page": page, "page_size": page_size, "items": items, "summary": summary}

    async def feed_options(self, nm_id, date_from, date_to, status, warehouse_name, region_name):
        # distinct списки как getWarehouseOptions/getRegionOptions
        where = ["o.date BETWEEN :d1 AND :d2"]
        params = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if nm_id:
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = nm_id
        where_sql = " AND ".join(where) if where else "1=1"
        wh_sql = text(f"SELECT DISTINCT o.warehouse_name FROM wb_order o WHERE {where_sql} AND o.warehouse_name IS NOT NULL ORDER BY o.warehouse_name")
        rg_sql = text(f"SELECT DISTINCT o.region_name FROM wb_order o WHERE {where_sql} AND o.region_name IS NOT NULL ORDER BY o.region_name")
        wh = [r[0] for r in (await self.db.execute(wh_sql, params)).all()]
        rg = [r[0] for r in (await self.db.execute(rg_sql, params)).all()]
        return {"warehouses": wh, "regions": rg, "statuses": STATUS_MAP}
