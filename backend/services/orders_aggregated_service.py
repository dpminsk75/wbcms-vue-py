"""Порт WbOrderFeedAggregatedSearch.php:19 — сводка по товарам (группировка wb_order по nm_id)"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta


class OrdersAggregatedService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- summary карточки над таблицей ---
    async def get_summary_stats(self, nm_id: int | None, date_from: str, date_to: str) -> dict:
        where = ["o.date BETWEEN :d1 AND :d2"]
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if nm_id:
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = nm_id
        where_sql = " AND ".join(where)
        sql = text(f"""
            SELECT COUNT(*) AS cnt,
                   SUM(o.price_with_disc) AS sum_price_with_disc,
                   AVG(o.spp) AS avg_spp,
                   SUM(CASE WHEN o.warehouse_type = 'Склад продавца' THEN 1 ELSE 0 END) AS fbs_count,
                   SUM(CASE WHEN o.warehouse_type <> 'Склад продавца' OR o.warehouse_type IS NULL THEN 1 ELSE 0 END) AS fbo_count
            FROM wb_order o WHERE {where_sql}
        """)
        row = (await self.db.execute(sql, params)).mappings().first()
        return {
            "count": int(row["cnt"] or 0) if row else 0,
            "sum": float(row["sum_price_with_disc"] or 0) if row else 0,
            "avg_spp": float(row["avg_spp"] or 0) if row else 0,
            "fbs_count": int(row["fbs_count"] or 0) if row else 0,
            "fbo_count": int(row["fbo_count"] or 0) if row else 0,
        }

    # --- воронка заказов ---
    async def get_funnel_stats(self, nm_id: int | None, date_from: str, date_to: str) -> dict:
        where = ["o.date BETWEEN :d1 AND :d2"]
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if nm_id:
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = nm_id
        where_sql = " AND ".join(where)
        sql = text(f"""
            SELECT
                COUNT(*) AS total_cnt,
                SUM(COALESCE(o.finished_price, o.price_with_disc, 0)) AS total_sum,
                SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM wb_sales sr WHERE sr.srid=o.srid AND sr.saleID LIKE 'R%') AND EXISTS (SELECT 1 FROM wb_sales ss WHERE ss.srid=o.srid AND ss.saleID NOT LIKE 'R%') THEN 1 ELSE 0 END) AS bought_cnt,
                SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM wb_sales sr WHERE sr.srid=o.srid AND sr.saleID LIKE 'R%') AND EXISTS (SELECT 1 FROM wb_sales ss WHERE ss.srid=o.srid AND ss.saleID NOT LIKE 'R%') THEN COALESCE((SELECT COALESCE(ss.finishedPrice, ss.priceWithDisc,0) FROM wb_sales ss WHERE ss.srid=o.srid AND ss.saleID NOT LIKE 'R%' LIMIT 1),0) ELSE 0 END) AS bought_sum,
                SUM(CASE WHEN o.is_cancel = 0 AND NOT EXISTS (SELECT 1 FROM wb_sales sd WHERE sd.srid=o.srid) THEN 1 ELSE 0 END) AS delivery_cnt,
                SUM(CASE WHEN o.is_cancel = 0 AND NOT EXISTS (SELECT 1 FROM wb_sales sd WHERE sd.srid=o.srid) THEN COALESCE(o.finished_price, o.price_with_disc, 0) ELSE 0 END) AS delivery_sum,
                SUM(CASE WHEN o.is_cancel = 1 THEN 1 ELSE 0 END) AS cancel_cnt,
                SUM(CASE WHEN o.is_cancel = 1 THEN COALESCE(o.finished_price, o.price_with_disc, 0) ELSE 0 END) AS cancel_sum,
                SUM(CASE WHEN EXISTS (SELECT 1 FROM wb_sales sr WHERE sr.srid=o.srid AND sr.saleID LIKE 'R%') THEN 1 ELSE 0 END) AS returns_cnt,
                SUM(COALESCE((SELECT COALESCE(sr.finishedPrice, sr.priceWithDisc,0) FROM wb_sales sr WHERE sr.srid=o.srid AND sr.saleID LIKE 'R%' LIMIT 1),0)) AS returns_sum
            FROM wb_order o WHERE {where_sql}
        """)
        row = (await self.db.execute(sql, params)).mappings().first()
        total_cnt = int(row["total_cnt"] or 0) if row else 0
        bought_cnt = int(row["bought_cnt"] or 0) if row else 0
        delivery_cnt = int(row["delivery_cnt"] or 0) if row else 0
        cancel_cnt = int(row["cancel_cnt"] or 0) if row else 0
        returns_cnt = int(row["returns_cnt"] or 0) if row else 0
        total_sum = float(row["total_sum"] or 0) if row else 0
        bought_sum = float(row["bought_sum"] or 0) if row else 0
        delivery_sum = float(row["delivery_sum"] or 0) if row else 0
        cancel_sum = float(row["cancel_sum"] or 0) if row else 0
        returns_sum = float(row["returns_sum"] or 0) if row else 0

        def pct(part, whole):
            return round(part / whole * 100, 2) if whole else 0

        bought_pct = pct(bought_cnt, total_cnt)
        delivery_pct = pct(delivery_cnt, total_cnt)
        cancel_pct = pct(cancel_cnt, total_cnt)
        returns_pct = pct(returns_cnt, total_cnt)
        buyout_denom = bought_cnt + cancel_cnt + returns_cnt
        buyout_pct = round(bought_cnt / buyout_denom * 100, 2) if buyout_denom else 0

        return {
            "total_cnt": total_cnt, "total_sum": total_sum,
            "bought_cnt": bought_cnt, "bought_sum": bought_sum, "bought_pct": bought_pct,
            "delivery_cnt": delivery_cnt, "delivery_sum": delivery_sum, "delivery_pct": delivery_pct,
            "cancel_cnt": cancel_cnt, "cancel_sum": cancel_sum, "cancel_pct": cancel_pct,
            "returns_cnt": returns_cnt, "returns_sum": returns_sum, "returns_pct": returns_pct,
            "buyout_pct": buyout_pct,
        }

    # --- ежедневная разбивка для stacked-Bar ---
    async def get_daily_status_chart_data(self, nm_id: int | None, date_from: str, date_to: str) -> list:
        where = ["o.date BETWEEN :d1 AND :d2"]
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if nm_id:
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = nm_id
        where_sql = " AND ".join(where)
        sql = text(f"""
            SELECT DATE(o.date) AS d,
                   COUNT(*) AS total_cnt,
                   SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM wb_sales sr WHERE sr.srid=o.srid AND sr.saleID LIKE 'R%') AND EXISTS (SELECT 1 FROM wb_sales ss WHERE ss.srid=o.srid AND ss.saleID NOT LIKE 'R%') THEN 1 ELSE 0 END) AS bought_cnt,
                   SUM(CASE WHEN o.is_cancel = 0 AND NOT EXISTS (SELECT 1 FROM wb_sales sd WHERE sd.srid=o.srid) THEN 1 ELSE 0 END) AS delivery_cnt,
                   SUM(CASE WHEN o.is_cancel = 1 THEN 1 ELSE 0 END) AS cancel_cnt,
                   SUM(CASE WHEN EXISTS (SELECT 1 FROM wb_sales sr WHERE sr.srid=o.srid AND sr.saleID LIKE 'R%') THEN 1 ELSE 0 END) AS returns_cnt,
                   SUM(COALESCE(o.finished_price, o.price_with_disc, 0)) AS total_sum,
                   SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM wb_sales sr WHERE sr.srid=o.srid AND sr.saleID LIKE 'R%') AND EXISTS (SELECT 1 FROM wb_sales ss WHERE ss.srid=o.srid AND ss.saleID NOT LIKE 'R%') THEN COALESCE((SELECT COALESCE(ss.finishedPrice, ss.priceWithDisc,0) FROM wb_sales ss WHERE ss.srid=o.srid AND ss.saleID NOT LIKE 'R%' LIMIT 1),0) ELSE 0 END) AS bought_sum,
                   SUM(CASE WHEN o.is_cancel = 0 AND NOT EXISTS (SELECT 1 FROM wb_sales sd WHERE sd.srid=o.srid) THEN COALESCE(o.finished_price, o.price_with_disc, 0) ELSE 0 END) AS delivery_sum,
                   SUM(CASE WHEN o.is_cancel = 1 THEN COALESCE(o.finished_price, o.price_with_disc, 0) ELSE 0 END) AS cancel_sum,
                   SUM(COALESCE((SELECT COALESCE(sr.finishedPrice, sr.priceWithDisc,0) FROM wb_sales sr WHERE sr.srid=o.srid AND sr.saleID LIKE 'R%' LIMIT 1),0)) AS returns_sum
            FROM wb_order o WHERE {where_sql}
            GROUP BY d ORDER BY d ASC
        """)
        raw = (await self.db.execute(sql, params)).mappings().all()
        by_date = {str(r["d"]): r for r in raw}
        result = []
        cur = date.fromisoformat(date_from)
        end = date.fromisoformat(date_to)
        while cur <= end:
            d_str = cur.isoformat()
            r = by_date.get(d_str)
            if r:
                result.append({
                    "date": d_str,
                    "total_cnt": int(r["total_cnt"] or 0),
                    "bought_cnt": int(r["bought_cnt"] or 0),
                    "delivery_cnt": int(r["delivery_cnt"] or 0),
                    "cancel_cnt": int(r["cancel_cnt"] or 0),
                    "returns_cnt": int(r["returns_cnt"] or 0),
                    "total_sum": float(r["total_sum"] or 0),
                    "bought_sum": float(r["bought_sum"] or 0),
                    "delivery_sum": float(r["delivery_sum"] or 0),
                    "cancel_sum": float(r["cancel_sum"] or 0),
                    "returns_sum": float(r["returns_sum"] or 0),
                })
            else:
                result.append({
                    "date": d_str,
                    "total_cnt": 0, "bought_cnt": 0, "delivery_cnt": 0, "cancel_cnt": 0, "returns_cnt": 0,
                    "total_sum": 0, "bought_sum": 0, "delivery_sum": 0, "cancel_sum": 0, "returns_sum": 0,
                })
            cur += timedelta(days=1)
        return result

    # --- главный запрос: GROUP BY nm_id ---
    async def search(self, nm_id: int | None, date_from: str, date_to: str, sort_by: str = "count", page: int = 1, page_size: int = 50) -> dict:
        if sort_by not in ("count", "sum"):
            sort_by = "count"
        where = ["o.date BETWEEN :d1 AND :d2"]
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59", "off": (page - 1) * page_size, "lim": page_size}
        if nm_id:
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = nm_id
        where_sql = " AND ".join(where)
        order_sql = "orders_cnt DESC" if sort_by == "count" else "sum_price_with_disc DESC"
        forecast_base = "COALESCE(o.price_with_disc, o.finished_price, 0)"
        sql = text(f"""
            SELECT o.nm_id,
                   c.title AS card_title, c.vendorCode AS card_vendor_code, c.subjectName AS card_subject_name, c.brand AS card_brand, c.photos AS card_photos,
                   COUNT(*) AS orders_cnt,
                   SUM(CASE WHEN o.is_cancel > 0 THEN 1 ELSE 0 END) AS cancelled_cnt,
                   AVG(o.total_price) AS avg_total_price,
                   AVG(o.discount_percent) AS avg_discount,
                   SUM(o.price_with_disc) AS sum_price_with_disc,
                   AVG(o.price_with_disc) AS avg_price_with_disc,
                   AVG(CASE WHEN o.spp > 0 THEN o.spp END) AS avg_spp,
                   SUM(o.finished_price) AS sum_finished,
                   AVG(o.finished_price) AS avg_finished,
                   SUM(COALESCE(o.commission_fee, ROUND(fcst.forecast_commission_pct * {forecast_base}, 2))) AS sum_commission,
                   AVG(COALESCE(o.commission_fee, ROUND(fcst.forecast_commission_pct * {forecast_base}, 2))) AS avg_commission,
                   AVG(COALESCE(o.commission_percent, fcst.forecast_commission_pct*100)) AS avg_commission_pct,
                   SUM(COALESCE(o.acquiring_fee, ROUND(fcst.forecast_acquiring_pct * {forecast_base}, 2))) AS sum_acquiring,
                   AVG(COALESCE(o.acquiring_fee, ROUND(fcst.forecast_acquiring_pct * {forecast_base}, 2))) AS avg_acquiring,
                   AVG(COALESCE(o.acquiring_percent, fcst.forecast_acquiring_pct*100)) AS avg_acquiring_pct,
                   SUM(COALESCE(o.delivery_rub, fcst.forecast_delivery_rub)) AS sum_delivery,
                   AVG(COALESCE(o.delivery_rub, fcst.forecast_delivery_rub)) AS avg_delivery
            FROM wb_order o
            LEFT JOIN wbcards c ON c.nmID = o.nm_id
            LEFT JOIN (
                SELECT company_id, warehouse_type, warehouse_name, region_name, category,
                       SUM(sum_sales_commission) / NULLIF(SUM(sum_retail_amount), 0) AS forecast_commission_pct,
                       SUM(sum_delivery_rub) / NULLIF(SUM(orders_count), 0) AS forecast_delivery_rub,
                       SUM(sum_acquiring_fee) / NULLIF(SUM(sum_retail_amount), 0) AS forecast_acquiring_pct
                FROM detail_by_period_forecast
                WHERE stat_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 10 DAY) AND DATE_SUB(CURDATE(), INTERVAL 1 DAY)
                GROUP BY company_id, warehouse_type, warehouse_name, region_name, category
            ) fcst ON fcst.company_id = o.company_id
                   AND fcst.warehouse_type = o.warehouse_type
                   AND fcst.warehouse_name = o.warehouse_name
                   AND fcst.region_name = o.region_name
                   AND fcst.category = o.category
            WHERE {where_sql}
            GROUP BY o.nm_id
            ORDER BY {order_sql}
            LIMIT :lim OFFSET :off
        """)
        rows = (await self.db.execute(sql, params)).mappings().all()
        items = [dict(r) for r in rows]

        # total групп для пагинации
        cnt_sql = text(f"SELECT COUNT(DISTINCT o.nm_id) AS cnt FROM wb_order o WHERE {where_sql}")
        # cnt_sql использует те же ключи, но без off/lim
        cnt_params = {k: v for k, v in params.items() if k not in ("off", "lim")}
        total_row = (await self.db.execute(cnt_sql, cnt_params)).mappings().first()
        total = int(total_row["cnt"] or 0) if total_row else 0

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # --- комбинированный ответ для фронта (как php рендер) ---
    async def feed_aggregated(self, nm_id: int | None, date_from: str, date_to: str, sort_by: str = "count", page: int = 1, page_size: int = 50) -> dict:
        summary = await self.get_summary_stats(nm_id, date_from, date_to)
        funnel = await self.get_funnel_stats(nm_id, date_from, date_to)
        chart = await self.get_daily_status_chart_data(nm_id, date_from, date_to)
        data = await self.search(nm_id, date_from, date_to, sort_by, page, page_size)
        return {**data, "summary": summary, "funnel": funnel, "chart": chart}
