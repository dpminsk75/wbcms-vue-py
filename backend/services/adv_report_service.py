"""Порт WbAdvReportController.php:18 actionIndex — аналитика рекламы WB"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

STATUS_MAP = {-1:"Удалена",4:"Готова к запуску",7:"Завершена",8:"Отклонена",9:"Активна",11:"Пауза"}
TYPE_MAP = {4:"Каталог",5:"Карточка товара",6:"Поиск",7:"Рекомендации",8:"Автоматическая (old)",9:"Поиск + Каталог / Авто"}
STATUS_PRIORITY = [9,11,7,4,8,-1]

class AdvReportService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self, alias: str = "c") -> str:
        prefix = f"{alias}." if alias else ""
        return "" if self.company_id is None else f" AND {prefix}company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def get_campaign_list(self):
        # как в php:213 active ids = distinct wb_campaign_stats.campaign_id
        sql = text(f"""
            SELECT c.campaign_id, c.name, c.status FROM wb_campaign c
            WHERE c.campaign_id IN (SELECT DISTINCT campaign_id FROM wb_campaign_stats){self._company_where('c')}
            ORDER BY FIELD(c.status, 9,11,7,4,8,-1), c.name ASC
        """)
        rows = (await self.db.execute(sql, self._company_params())).mappings().all()
        out = []
        for r in rows:
            label = STATUS_MAP.get(r["status"], "???")
            out.append({"campaign_id": r["campaign_id"], "name": r["name"], "status": r["status"], "label": f"({label}) — {r['name']} [ID: {r['campaign_id']}]"})
        return out

async def get_detail(self, campaign_id: int, date_from: str, date_to: str):
        # кампания
        camp_sql = text(f"SELECT campaign_id, name, status, type, daily_budget, change_time FROM wb_campaign WHERE campaign_id=:id{self._company_where('')}")
        camp = (await self.db.execute(camp_sql, {"id": campaign_id, **self._company_params()})).mappings().first()
        if not camp:
            return None
        campaign = dict(camp)

        # items
        items_sql = text(f"""
            SELECT i.*, c.title as card_name, c.brand, c.vendorCode
            FROM wb_campaign_item i
            LEFT JOIN wbcards c ON c.nmID = i.nm_id
            WHERE i.campaign_id=:id{self._company_where('i')}
        """)
        items = [dict(r) for r in (await self.db.execute(items_sql, {"id": campaign_id, **self._company_params()})).mappings().all()]

        # stats per date+nm_id (для таблицы Общая статистика по дням)
        stats_sql = text(f"""
            SELECT c.campaign_id, i.nm_id, s.date, w.title, w.vendorCode,
                   SUM(n.views) as views, SUM(n.clicks) as clicks, SUM(n.atbs) as atbs,
                   SUM(n.orders) as orders, SUM(n.shks) as shks, SUM(n.sum) as sum,
                   SUM(n.sum_price) as sum_price, SUM(n.canceled) as canceled
            FROM wb_campaign c
            INNER JOIN wb_campaign_item i ON c.campaign_id=i.campaign_id
            INNER JOIN wb_campaign_stats s ON c.campaign_id=s.campaign_id
            INNER JOIN wb_campaign_stats_nms n ON s.id=n.parent_id AND i.nm_id=n.nm_id
            INNER JOIN wbcards w ON n.nm_id=w.nmID
            WHERE c.campaign_id=:id AND s.date BETWEEN :d1 AND :d2{self._company_where('c')}
            GROUP BY c.campaign_id, i.nm_id, s.date, w.title, w.vendorCode
            ORDER BY s.date DESC
        """)
        stats = [dict(r) for r in (await self.db.execute(stats_sql, {"id": campaign_id, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()]

        # ShortStats per nm_id (Сводные показатели)
        short_sql = text(f"""
            SELECT c.campaign_id, i.nm_id, w.title, w.vendorCode,
                   SUM(n.views) as views, SUM(n.clicks) as clicks, SUM(n.atbs) as atbs,
                   SUM(n.orders) as orders, SUM(n.shks) as shks, SUM(n.sum) as sum,
                   SUM(n.sum_price) as sum_price, SUM(n.canceled) as canceled
            FROM wb_campaign c
            INNER JOIN wb_campaign_item i ON c.campaign_id=i.campaign_id
            INNER JOIN wb_campaign_stats s ON c.campaign_id=s.campaign_id
            INNER JOIN wb_campaign_stats_nms n ON s.id=n.parent_id AND i.nm_id=n.nm_id
            INNER JOIN wbcards w ON n.nm_id=w.nmID
            WHERE c.campaign_id=:id AND s.date BETWEEN :d1 AND :d2{self._company_where('c')}
            GROUP BY c.campaign_id, i.nm_id, w.title, w.vendorCode
            ORDER BY i.nm_id ASC
        """)
        short = [dict(r) for r in (await self.db.execute(short_sql, {"id": campaign_id, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()]

        # AnotherGoods — товары в заказах но не в кампании, только с orders>0 и i.nm_id IS NULL left join
        another_sql = text(f"""
            SELECT c.campaign_id, n.nm_id, w.title, w.vendorCode,
                   SUM(n.views) as views, SUM(n.clicks) as clicks, SUM(n.atbs) as atbs,
                   SUM(n.orders) as orders, SUM(n.shks) as shks, SUM(n.sum) as sum,
                   SUM(n.sum_price) as sum_price, SUM(n.canceled) as canceled
            FROM wb_campaign c
            INNER JOIN wb_campaign_stats s ON c.campaign_id=s.campaign_id
            INNER JOIN wb_campaign_stats_nms n ON s.id=n.parent_id
            LEFT JOIN wb_campaign_item i ON c.campaign_id=s.campaign_id AND n.nm_id=i.nm_id
            INNER JOIN wbcards w ON n.nm_id=w.nmID
            WHERE c.campaign_id=:id AND s.date BETWEEN :d1 AND :d2{self._company_where('c')}
              AND i.nm_id IS NULL AND n.orders > 0
            GROUP BY c.campaign_id, n.nm_id, w.title, w.vendorCode
            ORDER BY SUM(n.orders) DESC, n.nm_id ASC
        """)
        another = [dict(r) for r in (await self.db.execute(another_sql, {"id": campaign_id, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()]

        # ChartStats per date (timeline)
        chart_sql = text(f"""
            SELECT s.date as odate,
                   SUM(n.views) as views, SUM(n.clicks) as clicks, SUM(n.atbs) as atbs,
                   SUM(n.orders) as orders, SUM(n.shks) as shks, SUM(n.sum) as sum,
                   SUM(n.sum_price) as sum_price, SUM(n.canceled) as canceled,
                   SUM(n.sum) / NULLIF(SUM(n.views),0) *1000 as CPM,
                   SUM(n.sum) / NULLIF(SUM(n.clicks),0) as CPC,
                   SUM(n.sum) / NULLIF(SUM(n.orders),0) as CPO,
                   SUM(n.clicks)/NULLIF(SUM(n.views),0)*100 as CTR,
                   SUM(n.atbs)/NULLIF(SUM(n.clicks),0)*100 as CR
            FROM wb_campaign c
            INNER JOIN wb_campaign_item i ON c.campaign_id=i.campaign_id
            INNER JOIN wb_campaign_stats s ON c.campaign_id=s.campaign_id
            INNER JOIN wb_campaign_stats_nms n ON s.id=n.parent_id AND i.nm_id=n.nm_id
            INNER JOIN wbcards w ON n.nm_id=w.nmID
            WHERE c.campaign_id=:id AND s.date BETWEEN :d1 AND :d2{self._company_where('c')}
            GROUP BY s.date ORDER BY s.date ASC
        """)
        chart = [dict(r) for r in (await self.db.execute(chart_sql, {"id": campaign_id, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()]
        for r in chart:
            # normalize date to string yyyy-mm-dd
            if r.get("odate") is not None:
                try:
                    r["odate"] = str(r["odate"])[:10]
                except:
                    pass

        # ChartAppStats — устр-ва: app_type 1/32/64
        app_sql = text(f"""
            SELECT app_type, date, SUM(views) as views, SUM(clicks) as clicks, SUM(atbs) as atbs,
                   SUM(orders) as orders, SUM(sum_price) as sum_price
            FROM wb_campaign_stats WHERE campaign_id=:id AND date BETWEEN :d1 AND :d2{self._company_where('')}
            GROUP BY date, app_type ORDER BY date ASC, app_type DESC
        """)
        app_rows = [dict(r) for r in (await self.db.execute(app_sql, {"id": campaign_id, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()]
        # flatten как в php: flatData[date][metric_type]
        flat = {}
        types = [32,64,1]
        metrics = ["clicks","orders","atbs","views","sum_price"]
        for row in app_rows:
            d = str(row["date"])[:10]
            t = row["app_type"]
            if d not in flat:
                flat[d] = {"date": d}
                for tt in types:
                    for m in metrics:
                        flat[d][f"{m}_{tt}"] = 0
            flat[d][f"clicks_{t}"] = int(row["clicks"] or 0)
            flat[d][f"orders_{t}"] = int(row["orders"] or 0)
            flat[d][f"atbs_{t}"] = int(row["atbs"] or 0)
            flat[d][f"views_{t}"] = int(row["views"] or 0)
            flat[d][f"sum_price_{t}"] = float(row["sum_price"] or 0)
        app_flat = list(flat.values())
        app_flat.sort(key=lambda x: x["date"])

        # queries (WbCampaignQuery)
        try:
            q_sql = text("SELECT * FROM wb_campaign_query WHERE campaign_id=:id AND date BETWEEN :d1 AND :d2 ORDER BY date DESC")
            queries = [dict(r) for r in (await self.db.execute(q_sql, {"id": campaign_id, "d1": date_from, "d2": date_to})).mappings().all()]
        except Exception:
            queries = []

        return {
            "campaign": campaign,
            "statusLabel": STATUS_MAP.get(campaign.get("status"), "???"),
            "typeLabel": TYPE_MAP.get(campaign.get("type"), f"Код {campaign.get('type')}"),
            "items": items,
            "stats": stats,
            "shortStats": short,
            "another": another,
            "chart": chart,
            "appChart": app_flat,
            "queries": queries,
        }
