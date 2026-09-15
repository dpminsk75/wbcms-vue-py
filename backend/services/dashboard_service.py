"""Полный перенос SiteController.php:238-413 + 469-784"""
from datetime import date, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import calendar

class DashboardService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    # --- buildPeriodStats dispatcher ---
    async def build_period_stats(self, period: str, table: str, sum_field: str):
        if period == "yesterday":
            return await self.build_hourly_comparison(table, sum_field, [
                {"key":"a","label":"Вчера","daysAgo":1},
                {"key":"b","label":"Позавчера","daysAgo":2},
                {"key":"c","label":"8 дней назад","daysAgo":8},
            ])
        if period == "week_to_date":
            return await self.build_daily_week_comparison(table, sum_field, 0)
        if period == "last_week":
            return await self.build_daily_week_comparison(table, sum_field, 1)
        if period == "month_to_date":
            return await self.build_daily_month_comparison(table, sum_field, 0)
        if period == "last_month":
            return await self.build_daily_month_comparison(table, sum_field, 1)
        return await self.build_hourly_comparison(table, sum_field, [
            {"key":"a","label":"Сегодня","daysAgo":0},
            {"key":"b","label":"Вчера","daysAgo":1},
            {"key":"c","label":"Неделю назад","daysAgo":7},
        ])

    async def build_hourly_comparison(self, table, sum_field, series_config):
        categories = [f"{h:02d}" for h in range(24)]
        series, totals = {}, {}
        for cfg in series_config:
            d = (date.today() - timedelta(days=cfg["daysAgo"])).isoformat()
            series[cfg["key"]] = await self.query_period_by_hour(table, sum_field, d, d)
            totals[cfg["key"]] = await self.query_period_agg(table, sum_field, f"{d} 00:00:00", f"{d} 23:59:59")
        return {"granularity":"hour","categories":categories,"seriesMeta":[{"key":c["key"],"name":c["label"]} for c in series_config],"series":series,"totals":totals}

    async def build_daily_week_comparison(self, table, sum_field, weeksAgoStart: int):
        is_current = weeksAgoStart == 0
        today = date.today()
        monday_a = today - timedelta(days=today.weekday() + weeksAgoStart*7)
        monday_b = monday_a - timedelta(days=7)
        sunday_a = monday_a + timedelta(days=6)
        sunday_b = monday_b + timedelta(days=6)
        end_a = today if is_current else sunday_a
        data_a = await self.query_period_by_day(table, sum_field, monday_a.isoformat(), end_a.isoformat())
        data_b = await self.query_period_by_day(table, sum_field, monday_b.isoformat(), sunday_b.isoformat())
        day_names = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
        series_a, series_b = [], []
        for i in range(7):
            d_a = monday_a + timedelta(days=i)
            d_b = monday_b + timedelta(days=i)
            r_a = data_a.get(d_a.isoformat())
            r_b = data_b.get(d_b.isoformat())
            series_a.append({"category":day_names[i],"sum":round(r_a["sum"],2) if r_a else (0 if d_a <= end_a else None),"cnt":r_a["cnt"] if r_a else (0 if d_a <= end_a else None),"spp":round(r_a["spp"],1) if r_a else (0 if d_a <= end_a else None),"date":d_a.isoformat()})
            series_b.append({"category":day_names[i],"sum":round(r_b["sum"],2) if r_b else 0,"cnt":r_b["cnt"] if r_b else 0,"spp":round(r_b["spp"],1) if r_b else 0,"date":d_b.isoformat()})
        totals_a = await self.query_period_agg(table, sum_field, f"{monday_a} 00:00:00", f"{end_a} 23:59:59")
        totals_b = await self.query_period_agg(table, sum_field, f"{monday_b} 00:00:00", f"{sunday_b} 23:59:59")
        label_a = "Текущая неделя" if is_current else "Прошлая неделя"
        label_b = "Неделю назад" if is_current else "Позапрошлая неделя"
        return {"granularity":"day","categories":day_names,"seriesMeta":[{"key":"a","name":label_a},{"key":"b","name":label_b}],"series":{"a":series_a,"b":series_b},"totals":{"a":totals_a,"b":totals_b}}

    async def build_daily_month_comparison(self, table, sum_field, monthsAgoStart: int):
        is_current = monthsAgoStart == 0
        today = date.today()
        year_a = today.year + (today.month -1 - monthsAgoStart)//12
        month_a = (today.month -1 - monthsAgoStart) %12 +1
        first_a = date(year_a, month_a, 1)
        year_b = first_a.year + (first_a.month -2)//12
        month_b = (first_a.month -2) %12 +1
        first_b = date(year_b, month_b, 1)
        days_a = calendar.monthrange(first_a.year, first_a.month)[1]
        days_b = calendar.monthrange(first_b.year, first_b.month)[1]
        last_a = date(first_a.year, first_a.month, days_a)
        last_b = date(first_b.year, first_b.month, days_b)
        end_a = today if is_current else last_a
        data_a = await self.query_period_by_day(table, sum_field, first_a.isoformat(), end_a.isoformat())
        data_b = await self.query_period_by_day(table, sum_field, first_b.isoformat(), last_b.isoformat())
        max_days = max(days_a, days_b)
        categories = [str(d) for d in range(1, max_days+1)]
        series_a, series_b = [], []
        for d in range(1, max_days+1):
            date_a = first_a + timedelta(days=d-1) if d <= days_a else None
            date_b = first_b + timedelta(days=d-1) if d <= days_b else None
            r_a = data_a.get(date_a.isoformat()) if date_a else None
            r_b = data_b.get(date_b.isoformat()) if date_b else None
            in_range_a = date_a is not None and date_a <= end_a
            series_a.append({"category":str(d),"sum":None if date_a is None else (round(r_a["sum"],2) if r_a else (0 if in_range_a else None)),"cnt":None if date_a is None else (r_a["cnt"] if r_a else (0 if in_range_a else None)),"spp":None if date_a is None else (round(r_a["spp"],1) if r_a else (0 if in_range_a else None)),"date":date_a.isoformat() if date_a else None})
            series_b.append({"category":str(d),"sum":None if date_b is None else (round(r_b["sum"],2) if r_b else 0),"cnt":None if date_b is None else (r_b["cnt"] if r_b else 0),"spp":None if date_b is None else (round(r_b["spp"],1) if r_b else 0),"date":date_b.isoformat() if date_b else None})
        totals_a = await self.query_period_agg(table, sum_field, f"{first_a} 00:00:00", f"{end_a} 23:59:59")
        totals_b = await self.query_period_agg(table, sum_field, f"{first_b} 00:00:00", f"{last_b} 23:59:59")
        label_a = "Текущий месяц" if is_current else "Прошлый месяц"
        label_b = "Прошлый месяц" if is_current else "Позапрошлый месяц"
        return {"granularity":"day","categories":categories,"axisCaption":f"{first_a.strftime('%B %Y')} / {first_b.strftime('%B %Y')}","seriesMeta":[{"key":"a","name":label_a},{"key":"b","name":label_b}],"series":{"a":series_a,"b":series_b},"totals":{"a":totals_a,"b":totals_b}}

    async def query_period_by_hour(self, table, sum_field, d: str, date_label=None):
        where = f"date BETWEEN :d1 AND :d2{self._company_where()}"
        params = {"d1": f"{d} 00:00:00", "d2": f"{d} 23:59:59", **self._company_params()}
        sql = text(f"SELECT HOUR(date) as hour, COUNT(*) as cnt, SUM({sum_field}) as sum, AVG(spp) as spp FROM {table} WHERE {where} GROUP BY hour")
        rows = (await self.db.execute(sql, params)).mappings().all()
        by_hour = {int(r["hour"]): r for r in rows}
        return [{"category":f"{h:02d}","sum":round(float(by_hour.get(h,{}).get("sum") or 0),2),"cnt":int(by_hour.get(h,{}).get("cnt") or 0),"spp":round(float(by_hour.get(h,{}).get("spp") or 0),1),"date":date_label} for h in range(24)]

    async def query_period_by_day(self, table, sum_field, date_from, date_to):
        where = f"date BETWEEN :d1 AND :d2{self._company_where()}"
        params = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59", **self._company_params()}
        sql = text(f"SELECT DATE(date) as d, COUNT(*) as cnt, SUM({sum_field}) as sum, AVG(spp) as spp FROM {table} WHERE {where} GROUP BY d")
        rows = (await self.db.execute(sql, params)).mappings().all()
        return {str(r["d"]): {"cnt":int(r["cnt"]),"sum":float(r["sum"] or 0),"spp":float(r["spp"] or 0)} for r in rows}

    async def query_period_agg(self, table, sum_field, d1, d2):
        sql = text(f"SELECT COUNT(*) cnt, SUM({sum_field}) sum, AVG(spp) spp FROM {table} WHERE date BETWEEN :d1 AND :d2")
        row = (await self.db.execute(sql, {"d1":d1,"d2":d2})).mappings().first()
        return {"cnt":int(row["cnt"] or 0),"sum":round(float(row["sum"] or 0),2),"spp":round(float(row["spp"] or 0),1)}

    # --- 5 оставшихся слотов ---
    async def get_adv(self, date_from: str, date_to: str):
        # SiteController.php:238 4 JOIN + GROUP BY campaign_id
        sql = text("""
            SELECT c.campaign_id, c.name, c.status,
                   CASE WHEN c.status=9 THEN 1 WHEN c.status=11 THEN 2 WHEN c.status=7 THEN 4 WHEN c.status=4 THEN 5 WHEN c.status=-1 THEN 6 ELSE 5 END as status_priority,
                   SUM(n.views) as views, SUM(n.clicks) as clicks, SUM(n.atbs) as atbs,
                   SUM(n.orders) as orders, SUM(n.shks) as shks, SUM(n.sum) as sum, SUM(n.sum_price) as sum_price, SUM(n.canceled) as canceled
            FROM wb_campaign c
            INNER JOIN wb_campaign_item i ON c.campaign_id=i.campaign_id
            INNER JOIN wb_campaign_stats s ON c.campaign_id=s.campaign_id
            INNER JOIN wb_campaign_stats_nms n ON s.id=n.parent_id AND i.nm_id=n.nm_id
            INNER JOIN wbcards w ON n.nm_id=w.nmID
            WHERE s.date BETWEEN :d1 AND :d2
            GROUP BY c.campaign_id, c.name, c.status
            ORDER BY status_priority, c.name
            LIMIT 50
        """)
        rows = (await self.db.execute(sql, {"d1":f"{date_from} 00:00:00","d2":f"{date_to} 23:59:59"})).mappings().all()
        return [dict(r) for r in rows]

    async def get_orders_summary(self):
        # SiteController.php:279 4 UNION — порядок как в PHP: Количество, Без скидок, Цена со скидкой, Цена в заказе
        sql = text("""
            SELECT 'Количество заказов' as price_type,
                   COUNT(CASE WHEN DATE(date)=CURDATE()-INTERVAL 1 DAY THEN 1 END) as ieri,
                   COUNT(CASE WHEN DATE(date)=CURDATE()-INTERVAL 2 DAY THEN 1 END) as pazyera,
                   COUNT(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 7 DAY AND date<CURDATE() THEN 1 END) as past_7_days,
                   COUNT(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 14 DAY AND date<CURDATE()-INTERVAL 7 DAY THEN 1 END) as week_before,
                   COUNT(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 30 DAY AND date<CURDATE() THEN 1 END) as past_30_days
            FROM wb_order WHERE date >= CURDATE()-INTERVAL 30 DAY
            UNION ALL
            SELECT 'Без скидок',
                   SUM(CASE WHEN DATE(date)=CURDATE()-INTERVAL 1 DAY THEN total_price ELSE 0 END),
                   SUM(CASE WHEN DATE(date)=CURDATE()-INTERVAL 2 DAY THEN total_price ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 7 DAY AND date<CURDATE() THEN total_price ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 14 DAY AND date<CURDATE()-INTERVAL 7 DAY THEN total_price ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 30 DAY AND date<CURDATE() THEN total_price ELSE 0 END)
            FROM wb_order WHERE date >= CURDATE()-INTERVAL 30 DAY
            UNION ALL
            SELECT 'Цена со скидкой',
                   SUM(CASE WHEN DATE(date)=CURDATE()-INTERVAL 1 DAY THEN price_with_disc ELSE 0 END),
                   SUM(CASE WHEN DATE(date)=CURDATE()-INTERVAL 2 DAY THEN price_with_disc ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 7 DAY AND date<CURDATE() THEN price_with_disc ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 14 DAY AND date<CURDATE()-INTERVAL 7 DAY THEN price_with_disc ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 30 DAY AND date<CURDATE() THEN price_with_disc ELSE 0 END)
            FROM wb_order WHERE date >= CURDATE()-INTERVAL 30 DAY
            UNION ALL
            SELECT 'Цена в заказе',
                   SUM(CASE WHEN DATE(date)=CURDATE()-INTERVAL 1 DAY THEN finished_price ELSE 0 END),
                   SUM(CASE WHEN DATE(date)=CURDATE()-INTERVAL 2 DAY THEN finished_price ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 7 DAY AND date<CURDATE() THEN finished_price ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 14 DAY AND date<CURDATE()-INTERVAL 7 DAY THEN finished_price ELSE 0 END),
                   SUM(CASE WHEN DATE(date)>=CURDATE()-INTERVAL 30 DAY AND date<CURDATE() THEN finished_price ELSE 0 END)
            FROM wb_order WHERE date >= CURDATE()-INTERVAL 30 DAY
        """)
        rows = (await self.db.execute(sql)).mappings().all()
        return [dict(r) for r in rows]

    async def get_last_orders(self, date_from: str, date_to: str, limit: int = 500):
        # Итоги по всем заказам за период (не по срезу ТОП) — отдельный agg как queryPeriodAgg
        totals_sql = text("SELECT COUNT(*) as cnt, COALESCE(SUM(price_with_disc),0) as pwd, COALESCE(SUM(finished_price),0) as fp FROM wb_order WHERE date BETWEEN :d1 AND :d2")
        totals_row = (await self.db.execute(totals_sql, {"d1":f"{date_from} 00:00:00","d2":f"{date_to} 23:59:59"})).mappings().first()
        totals = {"cnt": int(totals_row["cnt"] or 0), "pwd": float(totals_row["pwd"] or 0), "fp": float(totals_row["fp"] or 0)}
        sql = text("""
            SELECT c.title, c.nmID as nm_id, c.vendorCode,
                   COUNT(o.nm_id) as cnt,
                    SUM(CASE WHEN DATE(date)=CURDATE() THEN 1 ELSE 0 END) as cnt_0,
                    SUM(CASE WHEN DATE(date)=DATE_SUB(CURDATE(),INTERVAL 1 DAY) THEN 1 ELSE 0 END) as cnt_1,
                    SUM(CASE WHEN DATE(date)=DATE_SUB(CURDATE(),INTERVAL 2 DAY) THEN 1 ELSE 0 END) as cnt_2,
                    SUM(CASE WHEN DATE(date)=DATE_SUB(CURDATE(),INTERVAL 3 DAY) THEN 1 ELSE 0 END) as cnt_3,
                    SUM(o.price_with_disc) as pwd, SUM(o.finished_price) as fp,
                    AVG(o.price_with_disc) as apwd, AVG(o.spp) as aspp, AVG(o.finished_price) as afp
            FROM wb_order o INNER JOIN wbcards c ON o.nm_id=c.nmID
            WHERE o.date BETWEEN :d1 AND :d2
            GROUP BY c.title, c.nmID, c.vendorCode
            ORDER BY cnt DESC LIMIT :lim
        """)
        rows = (await self.db.execute(sql, {"d1":f"{date_from} 00:00:00","d2":f"{date_to} 23:59:59","lim":limit})).mappings().all()
        items = [dict(r) for r in rows]
        return {"items": items, "totals": totals, "total_items": len(items)}

    async def get_last_sales(self, date_from: str, date_to: str, limit: int = 500):
        totals_sql = text("SELECT COUNT(*) as cnt, COALESCE(SUM(priceWithDisc),0) as pwd, COALESCE(SUM(finishedPrice),0) as fp, COALESCE(SUM(forPay),0) as forpay FROM wb_sales WHERE date BETWEEN :d1 AND :d2")
        totals_row = (await self.db.execute(totals_sql, {"d1":f"{date_from} 00:00:00","d2":f"{date_to} 23:59:59"})).mappings().first()
        totals = {"cnt": int(totals_row["cnt"] or 0), "pwd": float(totals_row["pwd"] or 0), "fp": float(totals_row["fp"] or 0), "forpay": float(totals_row["forpay"] or 0)}
        sql = text("""
            SELECT c.title, c.nmID as nm_id, c.vendorCode,
                   COUNT(o.nmId) as cnt,
                    SUM(CASE WHEN DATE(date)=CURDATE() THEN 1 ELSE 0 END) as cnt_0,
                    SUM(CASE WHEN DATE(date)=DATE_SUB(CURDATE(),INTERVAL 1 DAY) THEN 1 ELSE 0 END) as cnt_1,
                    SUM(CASE WHEN DATE(date)=DATE_SUB(CURDATE(),INTERVAL 2 DAY) THEN 1 ELSE 0 END) as cnt_2,
                    SUM(CASE WHEN DATE(date)=DATE_SUB(CURDATE(),INTERVAL 3 DAY) THEN 1 ELSE 0 END) as cnt_3,
                    SUM(o.totalPrice) as tp, SUM(o.priceWithDisc) as pwd, SUM(o.finishedPrice) as fp, SUM(o.forPay) as forpay,
                    AVG(o.priceWithDisc) as apwd, AVG(o.spp) as aspp, AVG(o.finishedPrice) as afp, AVG(o.forPay) as aforpay, AVG(o.discountPercent) as adp
            FROM wb_sales o INNER JOIN wbcards c ON o.nmId=c.nmID
            WHERE o.date BETWEEN :d1 AND :d2
            GROUP BY c.title, c.nmID, c.vendorCode
            ORDER BY cnt DESC LIMIT :lim
        """)
        rows = (await self.db.execute(sql, {"d1":f"{date_from} 00:00:00","d2":f"{date_to} 23:59:59","lim":limit})).mappings().all()
        items = [dict(r) for r in rows]
        return {"items": items, "totals": totals, "total_items": len(items)}

    async def get_monthly_finance(self):
        # WbProfitService.php:18
        sql = text("""
            SELECT DATE_FORMAT(sdate,'%Y-%m') as month, SUM(qnt) as qnt, SUM(amount) as amount, SUM(`return`) as `return`,
                   SUM(commission) as commission, SUM(f_acquiring_fee) as f_acquiring_fee, SUM(f_acceptance) as f_acceptance,
                   SUM(f_delivery) as f_delivery, SUM(f_storage_fee) as f_storage_fee, SUM(f_penalty) as f_penalty,
                   SUM(f_deduction) as f_deduction, SUM(f_otziv) as f_otziv, SUM(f_adv) as f_adv, SUM(f_cashback) as f_cashback,
                   SUM(net_profit) as net_profit, SUM(f_nds) as total_nds, SUM(f_cost_price) as total_cost,
                   SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price) as profit_before_tax,
                   GREATEST(0, SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price))*0.07 as tax_amount,
                   (SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price)) - GREATEST(0, SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price))*0.07 as clean_margin
            FROM agg_daily_summary WHERE sdate >= '2025-01-01'
            GROUP BY DATE_FORMAT(sdate,'%Y-%m') ORDER BY month DESC
        """)
        rows = (await self.db.execute(sql)).mappings().all()
        return [dict(r) for r in rows]

    async def get_new_cards(self, date_from: str | None = None, date_to: str | None = None, title: str = "", sort: str = "created_desc"):
        # SiteController.php:792 + _new_cards.php:10 — последние 14 дней, сортировка по vendorCode-приоритету
        from datetime import date as dt_date, timedelta
        if not date_from or not __import__('re').match(r'^\d{4}-\d{2}-\d{2}$', date_from):
            date_from = (dt_date.today() - timedelta(days=14)).isoformat()
        if not date_to or not __import__('re').match(r'^\d{4}-\d{2}-\d{2}$', date_to):
            date_to = dt_date.today().isoformat()
        allowed = {'created_desc','created_asc','nmid_asc','nmid_desc','title_asc','title_desc'}
        if sort not in allowed:
            sort = 'created_desc'
        base_where = "created_at BETWEEN :d1 AND :d2"
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        title_clause = ""
        if title:
            title_clause = " AND title LIKE :title"
            params["title"] = f"%{title}%"
        order_map = {
            'created_asc': "created_at ASC",
            'nmid_asc': "nmID ASC, created_at DESC",
            'nmid_desc': "nmID DESC, created_at DESC",
            'title_asc': "title ASC, created_at DESC",
            'title_desc': "title DESC, created_at DESC",
        }
        if sort in order_map:
            order_by = order_map[sort]
        else:
            order_by = "CASE WHEN vendorCode LIKE '!%' THEN 1 WHEN vendorCode LIKE '$%' THEN 2 WHEN vendorCode LIKE '#%' THEN 3 ELSE 4 END ASC, created_at DESC"
        sql = text(f"SELECT nmID, vendorCode, title, brand, photos, created_at FROM wbcards WHERE {base_where}{title_clause} ORDER BY {order_by}")
        rows = (await self.db.execute(sql, params)).mappings().all()
        return [dict(r) for r in rows]

    async def get_last_order_time(self) -> str | None:
        row = (await self.db.execute(text("SELECT MAX(date) as d FROM wb_order"))).scalar()
        if row is None:
            return None
        # row может быть datetime или str
        try:
            return row.isoformat(sep=' ')  # '2026-09-12 17:38:00'
        except Exception:
            return str(row)
