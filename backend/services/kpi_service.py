"""Замена SiteController.php:189 actionDashboardTopMetrics — agg_daily_summary 30д"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class KpiService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    async def get_30d_chart(self):
        sql = text("""
            SELECT sdate as date, SUM(amount) as amount, SUM(net_profit) as net_profit,
                   SUM(qnt) as qnt,
                   SUM(commission)+SUM(f_acquiring_fee)+SUM(f_acceptance)+SUM(f_delivery)+SUM(f_storage_fee)+SUM(f_penalty)+SUM(f_deduction)+SUM(f_otziv)+SUM(f_adv)+SUM(f_cashback) as total_expenses,
                   SUM(f_nds) as total_nds, SUM(f_cost_price) as total_cost,
                   (SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price))*0.07 as tax_amount,
                   (SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price)) - GREATEST(0, SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price))*0.07 as clean_margin
            FROM agg_daily_summary
            WHERE sdate BETWEEN CURDATE() - INTERVAL 30 DAY AND CURDATE() - INTERVAL 1 DAY
            GROUP BY sdate ORDER BY sdate
        """)
        rows = (await self.db.execute(sql)).mappings().all()
        return [dict(r) for r in rows]

    async def get_30d_kpi(self):
        sql = text("""
            SELECT SUM(amount) as total_sales_rub, SUM(`return`) as total_return_rub, SUM(net_profit) as total_profit_rub,
                   SUM(commission)+SUM(f_acquiring_fee)+SUM(f_acceptance)+SUM(f_delivery)+SUM(f_storage_fee)+SUM(f_penalty)+SUM(f_deduction)+SUM(f_otziv)+SUM(f_adv)+SUM(f_cashback) as total_expenses,
                   SUM(f_delivery) as total_delivery, SUM(f_adv) as total_adv, SUM(f_cashback) as total_cashback,
                   SUM(f_nds) as total_nds, SUM(f_cost_price) as total_cost,
                   SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price) as profit_before_tax,
                   GREATEST(0, SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price))*0.07 as tax_amount,
                   (SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price)) - GREATEST(0, SUM(net_profit)-SUM(f_nds)-SUM(f_cost_price))*0.07 as clean_margin
            FROM agg_daily_summary
            WHERE sdate BETWEEN CURDATE() - INTERVAL 30 DAY AND CURDATE() - INTERVAL 1 DAY
        """)
        row = (await self.db.execute(sql)).mappings().first()
        # count orders — как SiteController.php:232
        cnt = (await self.db.execute(text("SELECT COUNT(*) as cnt FROM wb_order WHERE date BETWEEN CURDATE() - INTERVAL 30 DAY AND CURDATE() - INTERVAL 1 DAY"))).scalar()
        d = dict(row) if row else {}
        d["total_orders_cnt"] = int(cnt or 0)
        return d
