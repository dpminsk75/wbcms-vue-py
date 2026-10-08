"""Агрегаты OLAP: detail_by_period -> agg_* + ff_otziv/ff_adv.

Порт AggregateController (update/sales/orders/summary + update-feedbacks-cost +
update-adv-costs): все запросы 1в1, VALUES() переписан на alias-синтаксис
(deprecation MySQL 8). Дефолт -50д..сегодня. Без API, только SQL. Только stdlib.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SALES_SQL = """
INSERT INTO agg_sales_daily_sku (
    company_id, sale_date, nmID, subject_name, brand_name,
    sales_qty, returns_qty, retail_amount_sum,
    ppvz_for_pay_sum, delivery_rub_sum, penalty_sum)
SELECT company_id, DATE(sale_dt), nm_id, MAX(subject_name), MAX(brand_name),
    SUM(CASE WHEN doc_type_name = 'Продажа' THEN quantity ELSE 0 END),
    SUM(CASE WHEN doc_type_name = 'Возврат' THEN quantity ELSE 0 END),
    ROUND(SUM(retail_amount), 2), ROUND(SUM(ppvz_for_pay), 2),
    ROUND(SUM(delivery_rub), 2), ROUND(SUM(penalty), 2)
FROM detail_by_period
WHERE sale_dt BETWEEN :fr AND :to AND company_id IS NOT NULL
GROUP BY company_id, DATE(sale_dt), nm_id"""

ORDERS_SQL = """
INSERT INTO agg_orders_daily_sku (
    company_id, order_date, nmID, subject_name, brand_name, site_country,
    orders_qty, retail_price_avg, retail_amount_sum,
    retail_with_disc_sum, ppvz_for_pay_sum, delivery_forecast_rub)
SELECT company_id, DATE(order_dt), nm_id, MAX(subject_name), MAX(brand_name),
                    site_country, SUM(quantity), ROUND(AVG(retail_price), 2), ROUND(SUM(retail_amount), 2),
    ROUND(SUM(retail_price_withdisc_rub), 2), ROUND(SUM(ppvz_for_pay), 2), ROUND(SUM(quantity * dlv_prc), 2)
FROM detail_by_period
WHERE order_dt BETWEEN :fr AND :to AND doc_type_name = 'Продажа'
  AND company_id IS NOT NULL
GROUP BY company_id, DATE(order_dt), nm_id, site_country"""

SUMMARY_SQL = """
INSERT INTO `agg_daily_summary` (
    company_id, sdate, nm_id, qnt, sales_qnt, return_qnt, amount, `return`,
    commission, f_retail_amount, f_acquiring_fee, f_acceptance, f_delivery,
    f_storage_fee, f_penalty, f_deduction, f_otziv, f_adv, f_cashback,
    net_profit, f_nds, f_cost_price)
SELECT p.company_id, DATE(p.sale_dt), p.nm_id,
    SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN 1
             WHEN p.supplier_oper_name = 'Возврат' THEN -1 ELSE 0 END),
    SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN COALESCE(p.quantity, 0) ELSE 0 END),
    SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN COALESCE(p.quantity, 0) ELSE 0 END),
    ROUND(SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub ELSE 0 END), 2),
    ROUND(SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN p.retail_price_withdisc_rub ELSE 0 END), 2),
    ROUND(SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub * p.commission_percent / 100 ELSE 0 END), 2),
    ROUND(SUM(p.retail_amount), 2), ROUND(SUM(p.acquiring_fee), 2),
    ROUND(SUM(p.acceptance), 2), ROUND(SUM(p.delivery_rub), 2),
    ROUND(SUM(p.storage_fee), 2), ROUND(SUM(p.penalty), 2), ROUND(SUM(p.deduction), 2),
    ROUND(SUM(CASE WHEN p.bonus_type_name LIKE 'Списание за отзыв%' THEN p.deduction ELSE 0 END), 2),
    ROUND(SUM(CASE WHEN p.bonus_type_name LIKE '%WB Продвижение%' THEN p.deduction ELSE 0 END), 2),
    ROUND(SUM(p.cashback_amount), 2),
    ROUND((
        SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub ELSE 0 END)
        - SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN p.retail_price_withdisc_rub ELSE 0 END)
        - SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub * p.commission_percent / 100 ELSE 0 END)
        - SUM(p.acquiring_fee) - SUM(p.acceptance) - SUM(p.delivery_rub)
        - SUM(p.storage_fee) - SUM(p.penalty) - SUM(p.deduction) - SUM(p.cashback_amount)
    ), 2),
    CASE WHEN MAX(DATE(p.sale_dt)) < '2026-01-01' THEN 0.00
         ELSE ROUND((
             SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub ELSE 0 END) -
             SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN p.retail_price_withdisc_rub ELSE 0 END))
             * COALESCE((SELECT n.nds FROM wbcards_nds n
                 WHERE n.nmID = p.nm_id AND n.load_date <= MAX(DATE(p.sale_dt))
                 ORDER BY n.load_date DESC, n.id DESC LIMIT 1), 0)
             / (100 + COALESCE((SELECT n.nds FROM wbcards_nds n
                 WHERE n.nmID = p.nm_id AND n.load_date <= MAX(DATE(p.sale_dt))
                 ORDER BY n.load_date DESC, n.id DESC LIMIT 1), 0)), 2) END,
    ROUND((
        SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN 1 ELSE 0 END) -
        SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN 1 ELSE 0 END))
        * COALESCE((SELECT c.price FROM wbcards_costs c
            WHERE c.nmID = p.nm_id AND c.load_date <= MAX(DATE(p.sale_dt))
            ORDER BY c.load_date DESC, c.id DESC LIMIT 1), 0), 2)
FROM `detail_by_period` p
WHERE p.sale_dt BETWEEN :fr AND :to AND p.company_id IS NOT NULL
GROUP BY p.company_id, DATE(p.sale_dt), p.nm_id"""

ADV_SQL = """
INSERT INTO `agg_daily_summary` (company_id, sdate, nm_id, ff_adv)
SELECT nms.`company_id`, s.`date`, nms.`nm_id`, SUM(nms.`sum`)
FROM `wb_campaign_stats_nms` nms
INNER JOIN `wb_campaign_stats` s
  ON nms.`parent_id` = s.`id` AND nms.`company_id` = s.`company_id`
WHERE s.`date` BETWEEN :fr AND :to
GROUP BY nms.`company_id`, s.`date`, nms.`nm_id`
ON DUPLICATE KEY UPDATE
    ff_adv = VALUES(ff_adv)"""

class AggregateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _run(self, name: str, delete_sql: str, insert_sql: str,
                   fr: str, to: str) -> dict:
        """Кубы — полный пересчёт: DELETE периода + INSERT в одной транзакции
        (атомарно, без VALUES()-шума; SELECT-форме alias не встаёт)."""
        try:
            await self.db.rollback()
            async with self.db.begin():
                await self.db.execute(text(delete_sql),
                                      {"fr": fr + " 00:00:00", "to": to + " 23:59:59"})
                await self.db.execute(text(insert_sql),
                                      {"fr": fr + " 00:00:00", "to": to + " 23:59:59"})
            return {name: "ok"}
        except Exception as e:
            await self.db.rollback()
            return {name: f"ERROR: {type(e).__name__}: {e}"[:300]}

    async def update_sales(self, df: str, dt: str) -> dict:
        return await self._run(
            "sales",
            "DELETE FROM agg_sales_daily_sku WHERE sale_date BETWEEN DATE(:fr) AND DATE(:to)",
            SALES_SQL, df, dt)

    async def update_orders(self, df: str, dt: str) -> dict:
        return await self._run(
            "orders",
            "DELETE FROM agg_orders_daily_sku WHERE order_date BETWEEN DATE(:fr) AND DATE(:to)",
            ORDERS_SQL, df, dt)

    async def update_summary(self, df: str, dt: str) -> dict:
        return await self._run(
            "summary",
            "DELETE FROM `agg_daily_summary` WHERE sdate BETWEEN DATE(:fr) AND DATE(:to)",
            SUMMARY_SQL, df, dt)

    async def update_adv_costs(self, df: str, dt: str) -> dict:
        # Только ff_adv в строках с полными метриками — DELETE невозможен,
        # остаётся upsert (4 ворнинга VALUES() на прогон, рабочие).
        try:
            await self.db.execute(text(ADV_SQL), {"fr": df, "to": dt})
            await self.db.commit()
            return {"adv": "ok"}
        except Exception as e:
            await self.db.rollback()
            return {"adv": f"ERROR: {type(e).__name__}: {e}"[:300]}

    async def update_feedbacks_cost(self, df: str, dt: str) -> dict:
        import re
        try:
            rows = (await self.db.execute(text("""
                SELECT company_id, sale_dt, deduction, bonus_type_name
                FROM `detail_by_period`
                WHERE sale_dt BETWEEN :fr AND :to
                  AND `supplier_oper_name` = 'Удержание'
                  AND `bonus_type_name` LIKE 'Списание за отзыв%'"""),
                {"fr": df + " 00:00:00", "to": dt + " 23:59:59"})).mappings().all()
            if not rows:
                return {"feedbacks": "ok (пусто)"}
            cids = sorted({int(r["company_id"]) for r in rows if r["company_id"] is not None})
            if cids:
                ph = ",".join(f":c{i}" for i in range(len(cids)))
                await self.db.execute(text(f"""
                    UPDATE `agg_daily_summary` SET `ff_otziv` = 0.00
                    WHERE `sdate` BETWEEN :fr AND :to AND `company_id` IN ({ph})"""),
                    {"fr": df, "to": dt, **{f"c{i}": c for i, c in enumerate(cids)}})
            sums: dict[tuple, float] = {}
            linked = 0
            for r in rows:
                m = re.search(r"Списание за отзыв\s+([^:]+):\s+акция\s+№(\d+)",
                              str(r["bonus_type_name"] or ""), re.U)
                if not m:
                    continue
                fb = (await self.db.execute(text("""
                    SELECT `nmID` FROM `wb_feedbacks`
                    WHERE `id` = :i AND `company_id` = :c"""),
                    {"i": m.group(1).strip(), "c": r["company_id"]})).first()
                if not fb:
                    continue
                await self.db.execute(text("""
                    UPDATE `wb_feedbacks` SET `is_pay` = 1, `f_cost` = :cost,
                        `f_action` = :act WHERE `id` = :i AND `company_id` = :c"""),
                    {"cost": r["deduction"], "act": m.group(2).strip(),
                     "i": m.group(1).strip(), "c": r["company_id"]})
                key = (int(r["company_id"]), str(r["sale_dt"])[:10], int(fb[0]))
                sums[key] = sums.get(key, 0.0) + float(r["deduction"] or 0)
                linked += 1
            for (c, d, nm), cost in sums.items():
                await self.db.execute(text("""
                    INSERT INTO `agg_daily_summary` (company_id, sdate, nm_id, ff_otziv)
                    VALUES (:c, :d, :nm, :cost) AS new
                    ON DUPLICATE KEY UPDATE `ff_otziv` = new.`ff_otziv`"""),
                    {"c": c, "d": d, "nm": nm, "cost": round(cost, 2)})
            await self.db.commit()
            return {"feedbacks": f"ok (отзывов {linked})"}
        except Exception as e:
            await self.db.rollback()
            return {"feedbacks": f"ERROR: {type(e).__name__}: {e}"[:300]}
