"""Агрегаты OLAP: detail_by_period -> agg_* + ff_otziv/ff_adv.

Порт AggregateController (update/sales/orders/summary + update-feedbacks-cost +
update-adv-costs + update-storage-costs): все запросы 1в1 с PHP, VALUES()
переписан на alias-синтаксис (deprecation MySQL 8). Дефолт -50д..сегодня.
Без API, только SQL. Только stdlib.

ВАЖНО (правка 2026-10-26): пересчёт сводки сделан через
`INSERT ... SELECT * FROM (...) AS dt ON DUPLICATE KEY UPDATE` — как в PHP
(AggregateController.php:263). Раньше здесь был DELETE+INSERT, из-за чего
ff_otziv/ff_adv/ff_storage_fee стирались, а строки, созданные storage-шагом
для товаров без продаж в этот день, удалялись и не пересоздавались.
Теперь поведение = PHP: строки не удаляются, ff_* перезаписываются
последующими шагами (feedbacks/adv/storage).
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SALES_SQL = """
INSERT INTO agg_sales_daily_sku (
    company_id, sale_date, nmID, subject_name, brand_name,
    sales_qty, returns_qty, retail_amount_sum,
    ppvz_for_pay_sum, delivery_rub_sum, penalty_sum)
SELECT * FROM (
    SELECT company_id AS company_id, DATE(sale_dt) AS sale_date, nm_id AS nmID,
           MAX(subject_name) AS subject_name, MAX(brand_name) AS brand_name,
           SUM(CASE WHEN doc_type_name = 'Продажа' THEN quantity ELSE 0 END) AS sales_qty,
           SUM(CASE WHEN doc_type_name = 'Возврат' THEN quantity ELSE 0 END) AS returns_qty,
           SUM(retail_amount) AS retail_amount_sum,
           SUM(ppvz_for_pay) AS ppvz_for_pay_sum,
           SUM(delivery_rub) AS delivery_rub_sum,
           SUM(penalty) AS penalty_sum
    FROM detail_by_period
    WHERE sale_dt BETWEEN :fr AND :to AND company_id IS NOT NULL
    GROUP BY company_id, DATE(sale_dt), nm_id
) AS dt
ON DUPLICATE KEY UPDATE
    sales_qty = dt.sales_qty,
    returns_qty = dt.returns_qty,
    retail_amount_sum = dt.retail_amount_sum,
    ppvz_for_pay_sum = dt.ppvz_for_pay_sum,
    delivery_rub_sum = dt.delivery_rub_sum,
    penalty_sum = dt.penalty_sum"""

ORDERS_SQL = """
INSERT INTO agg_orders_daily_sku (
    company_id, order_date, nmID, subject_name, brand_name, site_country,
    orders_qty, retail_price_avg, retail_amount_sum,
    retail_with_disc_sum, ppvz_for_pay_sum, delivery_forecast_rub)
SELECT * FROM (
    SELECT company_id AS company_id, DATE(order_dt) AS order_date, nm_id AS nmID,
           MAX(subject_name) AS subject_name, MAX(brand_name) AS brand_name,
           site_country AS site_country,
           SUM(quantity) AS orders_qty,
           /* retail_price_avg — decimal(10,2), а AVG(retail_price) округляется вверх
              на границе диапазона → «Data truncated». Clamp в диапазон колонки. */
           CAST(LEAST(GREATEST(AVG(retail_price), -99999999.99), 99999999.99) AS DECIMAL(10,2)) AS retail_price_avg,
           SUM(retail_amount) AS retail_amount_sum,
           SUM(retail_price_withdisc_rub) AS retail_with_disc_sum,
           SUM(ppvz_for_pay) AS ppvz_for_pay_sum,
           SUM(quantity * dlv_prc) AS delivery_forecast_rub
    FROM detail_by_period
    WHERE order_dt BETWEEN :fr AND :to AND doc_type_name = 'Продажа'
      AND company_id IS NOT NULL
    GROUP BY company_id, DATE(order_dt), nm_id, site_country
) AS dt
ON DUPLICATE KEY UPDATE
    orders_qty = dt.orders_qty,
    retail_price_avg = dt.retail_price_avg,
    retail_amount_sum = dt.retail_amount_sum,
    retail_with_disc_sum = dt.retail_with_disc_sum,
    ppvz_for_pay_sum = dt.ppvz_for_pay_sum,
    delivery_forecast_rub = dt.delivery_forecast_rub"""

SUMMARY_SQL = """
INSERT INTO `agg_daily_summary` (
    company_id, sdate, nm_id, qnt, sales_qnt, return_qnt, amount, `return`,
    commission, f_retail_amount, f_acquiring_fee, f_acceptance, f_delivery,
    f_storage_fee, f_penalty, f_deduction, f_otziv, f_adv, f_cashback,
    net_profit, f_nds, f_cost_price)
SELECT * FROM (
    SELECT p.company_id AS company_id, DATE(p.sale_dt) AS sdate, p.nm_id AS nm_id,
    SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN 1
             WHEN p.supplier_oper_name = 'Возврат' THEN -1 ELSE 0 END) AS qnt,
    SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN COALESCE(p.quantity, 0) ELSE 0 END) AS sales_qnt,
    SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN COALESCE(p.quantity, 0) ELSE 0 END) AS return_qnt,
    ROUND(SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub ELSE 0 END), 2) AS amount,
    ROUND(SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN p.retail_price_withdisc_rub ELSE 0 END), 2) AS `return`,
    ROUND(SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub * p.commission_percent / 100 ELSE 0 END), 2) AS commission,
    ROUND(SUM(p.retail_amount), 2) AS f_retail_amount,
    ROUND(SUM(p.acquiring_fee), 2) AS f_acquiring_fee,
    ROUND(SUM(p.acceptance), 2) AS f_acceptance,
    ROUND(SUM(p.delivery_rub), 2) AS f_delivery,
    ROUND(SUM(p.storage_fee), 2) AS f_storage_fee,
    ROUND(SUM(p.penalty), 2) AS f_penalty,
    ROUND(SUM(p.deduction), 2) AS f_deduction,
    ROUND(SUM(CASE WHEN p.bonus_type_name LIKE 'Списание за отзыв%' THEN p.deduction ELSE 0 END), 2) AS f_otziv,
    ROUND(SUM(CASE WHEN p.bonus_type_name LIKE '%WB Продвижение%' THEN p.deduction ELSE 0 END), 2) AS f_adv,
    ROUND(SUM(p.cashback_amount), 2) AS f_cashback,
    ROUND((
        SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub ELSE 0 END)
        - SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN p.retail_price_withdisc_rub ELSE 0 END)
        - SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub * p.commission_percent / 100 ELSE 0 END)
        - SUM(p.acquiring_fee) - SUM(p.acceptance) - SUM(p.delivery_rub)
        - SUM(p.storage_fee) - SUM(p.penalty) - SUM(p.deduction) - SUM(p.cashback_amount)
    ), 2) AS net_profit,
    CASE WHEN MAX(DATE(p.sale_dt)) < '2026-01-01' THEN 0.00
         ELSE ROUND(
             GREATEST(COALESCE(
                 (SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN p.retail_price_withdisc_rub ELSE 0 END) -
                  SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN p.retail_price_withdisc_rub ELSE 0 END))
                 - ((SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN 1 ELSE 0 END) -
                     SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN 1 ELSE 0 END))
                    * COALESCE((SELECT c.price FROM wbcards_costs c
                        WHERE c.nmID = p.nm_id AND c.load_date <= MAX(DATE(p.sale_dt))
                        ORDER BY c.load_date DESC, c.id DESC LIMIT 1), 0))
             , 0), 0)
             * COALESCE((SELECT n.nds FROM wbcards_nds n
                 WHERE n.nmID = p.nm_id AND n.load_date <= MAX(DATE(p.sale_dt))
                 ORDER BY n.load_date DESC, n.id DESC LIMIT 1), 0)
             / (100 + COALESCE((SELECT n.nds FROM wbcards_nds n
                 WHERE n.nmID = p.nm_id AND n.load_date <= MAX(DATE(p.sale_dt))
                 ORDER BY n.load_date DESC, n.id DESC LIMIT 1), 0)), 2) END AS f_nds,
    ROUND((
        SUM(CASE WHEN p.supplier_oper_name = 'Продажа' THEN 1 ELSE 0 END) -
        SUM(CASE WHEN p.supplier_oper_name = 'Возврат' THEN 1 ELSE 0 END))
        * COALESCE((SELECT c.price FROM wbcards_costs c
            WHERE c.nmID = p.nm_id AND c.load_date <= MAX(DATE(p.sale_dt))
            ORDER BY c.load_date DESC, c.id DESC LIMIT 1), 0), 2) AS f_cost_price
    FROM `detail_by_period` p
    WHERE p.sale_dt BETWEEN :fr AND :to AND p.company_id IS NOT NULL
    GROUP BY p.company_id, DATE(p.sale_dt), p.nm_id
) AS dt
ON DUPLICATE KEY UPDATE
    qnt = dt.qnt,
    sales_qnt = dt.sales_qnt,
    return_qnt = dt.return_qnt,
    amount = dt.amount,
    `return` = dt.`return`,
    commission = dt.commission,
    f_retail_amount = dt.f_retail_amount,
    f_acquiring_fee = dt.f_acquiring_fee,
    f_acceptance = dt.f_acceptance,
    f_delivery = dt.f_delivery,
    f_storage_fee = dt.f_storage_fee,
    f_penalty = dt.f_penalty,
    f_deduction = dt.f_deduction,
    f_otziv = dt.f_otziv,
    f_adv = dt.f_adv,
    f_cashback = dt.f_cashback,
    net_profit = dt.net_profit,
    f_nds = dt.f_nds,
    f_cost_price = dt.f_cost_price"""

ADV_SQL = """
INSERT INTO `agg_daily_summary` (company_id, sdate, nm_id, ff_adv)
SELECT * FROM (
    SELECT nms.`company_id` AS company_id, s.`date` AS sdate,
           nms.`nm_id` AS nm_id, SUM(nms.`sum`) AS ff_adv
    FROM `wb_campaign_stats_nms` nms
    INNER JOIN `wb_campaign_stats` s
      ON nms.`parent_id` = s.`id` AND nms.`company_id` = s.`company_id`
    WHERE s.`date` BETWEEN :fr AND :to
    GROUP BY nms.`company_id`, s.`date`, nms.`nm_id`
) AS dt
ON DUPLICATE KEY UPDATE
    ff_adv = dt.ff_adv"""

# Платное хранение по позициям (отчёт WB «Платное хранение» → wb_paid_storage).
# В отчётах по товарам хранение = ff_storage_fee; f_storage_fee (детализация продаж) —
# для месячных отчётов, смешивать нельзя.
# INSERT создаёт строки куба там, где по товару не было продаж (qnt=0),
# иначе месячные начисления (1-го числа) терялись бы.
STORAGE_SQL = """
INSERT INTO `agg_daily_summary` (company_id, sdate, nm_id, ff_storage_fee)
SELECT * FROM (
    SELECT company_id AS company_id, `date` AS sdate, nmId AS nm_id,
           SUM(warehousePrice) AS ff_storage_fee
    FROM wb_paid_storage
    WHERE `date` BETWEEN :fr AND :to AND nmId IS NOT NULL
    GROUP BY company_id, `date`, nmId
) AS dt
ON DUPLICATE KEY UPDATE
    ff_storage_fee = dt.ff_storage_fee"""

# Основной SELECT шага «feedbacks» — по нему ищем списания за отзывы.
FEEDBACKS_SQL = """
SELECT company_id, sale_dt, deduction, bonus_type_name
FROM `detail_by_period`
WHERE sale_dt BETWEEN :fr AND :to
  AND `supplier_oper_name` = 'Удержание'
  AND `bonus_type_name` LIKE 'Списание за отзыв%'"""

# Лимиты сессии (AGENTS.md §4). Таймаут тут большой: шаг summary по design
# идёт минуты (это ночная/внепиковая задача, а не интерактивный запрос).
# Глобальные настройки MySQL НЕ трогаем — только сессионные.
SESSION_LIMITS = [
    "SET SESSION max_execution_time = 900000",
    "SET SESSION temptable_max_ram = 67108864",
    "SET SESSION tmp_table_size = 33554432",
    "SET SESSION max_heap_table_size = 33554432",
    "SET SESSION sort_buffer_size = 1048576",
    "SET SESSION join_buffer_size = 1048576",
    "SET SESSION read_rnd_buffer_size = 524288",
    "SET SESSION lock_wait_timeout = 5",
    "SET SESSION innodb_lock_wait_timeout = 5",
    "SET SESSION sql_safe_updates = 1",
]


class AggregateService:
    """Пересчёт кубов. Шаги независимы, каждый в своей транзакции."""

    STEPS = {
        "sales": SALES_SQL,
        "orders": ORDERS_SQL,
        "summary": SUMMARY_SQL,
        "feedbacks": FEEDBACKS_SQL,
        "adv": ADV_SQL,
        "storage": STORAGE_SQL,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def apply_session_limits(self) -> None:
        for stmt in SESSION_LIMITS:
            try:
                await self.db.execute(text(stmt))
            except Exception:
                pass
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()

    @staticmethod
    def params(df: str, dt: str) -> dict:
        return {"fr": df + " 00:00:00", "to": dt + " 23:59:59"}

    async def _upsert(self, name: str, sql: str, df: str, dt: str) -> dict:
        """Пересчёт куба: INSERT ... SELECT ... ON DUPLICATE KEY UPDATE.

        Строки не удаляются (как в PHP) — поэтому ff_otziv/ff_adv/
        ff_storage_fee не теряются, а доливаются шагами feedbacks/adv/storage.
        """
        try:
            await self.db.rollback()
            async with self.db.begin():
                await self.db.execute(text(sql), self.params(df, dt))
            return {name: "ok"}
        except Exception as e:
            await self.db.rollback()
            return {name: f"ERROR: {type(e).__name__}: {e}"[:300]}

    async def update_sales(self, df: str, dt: str) -> dict:
        return await self._upsert("sales", SALES_SQL, df, dt)

    async def update_orders(self, df: str, dt: str) -> dict:
        return await self._upsert("orders", ORDERS_SQL, df, dt)

    async def update_summary(self, df: str, dt: str) -> dict:
        return await self._upsert("summary", SUMMARY_SQL, df, dt)

    async def update_adv_costs(self, df: str, dt: str) -> dict:
        # Только ff_adv в строках с полными метриками — upsert (не DELETE),
        # остаётся как в PHP.
        try:
            await self.db.execute(text(ADV_SQL), {"fr": df, "to": dt})
            await self.db.commit()
            return {"adv": "ok"}
        except Exception as e:
            await self.db.rollback()
            return {"adv": f"ERROR: {type(e).__name__}: {e}"[:300]}

    async def update_storage_costs(self, df: str, dt: str) -> dict:
        """ff_storage_fee — платное хранение по позициям из отчёта WB (wb_paid_storage).

        Upsert: обновляет существующие строки куба и создаёт новые там, где по товару
        не было продаж в этот день (начисления месячные — их нельзя терять).
        """
        try:
            await self.db.execute(text(STORAGE_SQL), {"fr": df, "to": dt})
            await self.db.commit()
            return {"storage": "ok"}
        except Exception as e:
            await self.db.rollback()
            return {"storage": f"ERROR: {type(e).__name__}: {e}"[:300]}

    async def update_feedbacks_cost(self, df: str, dt: str) -> dict:
        import re
        try:
            rows = (await self.db.execute(text(FEEDBACKS_SQL),
                                          self.params(df, dt))).mappings().all()
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
