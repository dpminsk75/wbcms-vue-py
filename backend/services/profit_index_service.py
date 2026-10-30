"""Маржинальный учёт (/wb-profit) — порт Yii2 WbProfitService::getSkuProvider.

Страница Yii2 (`views/wb-profit/index.php`) = три блока:
  1. «Финансовая аналитика (с 2025 года)» — месячная сводка (портирована как
     KpiService.get_monthly_profit, используется на дашборде);
  2. «Топ 20 товаров за последние 60 дней»  — getSkuProvider(SORT_DESC);
  3. «Худшие 20 товаров за последние 60 дней» — getSkuProvider(SORT_ASC, filterZeroQnt).

Здесь — блоки 2 и 3 (сводка по товарам за N дней).

ЧТО ПОПРАВЛЕНО ПРИ ПЕРЕНОСЕ (Yii2 → py):
  * + фильтр по company_id: в Yii2 запрос шёл по всем компаниям (в py это обязательное
    правило, см. AGENTS.md);
  * период: в Yii2 `WHERE p.sdate >= CURDATE() - INTERVAL 60 DAY` (без верхней границы)
    → здесь `sdate BETWEEN :d1 AND :d2` (d1 = сегодня − days, d2 = сегодня);
  * GROUP BY: в Yii2 только `p.nm_id`, хотя в SELECT есть c.title/c.vendorCode —
    это ломается на ONLY_FULL_GROUP_BY → здесь в GROUP BY те же выражения, что в SELECT.

МАТЕМАТИКА 1в1 с Yii2 (важно!):
  * «Общий итог» (net_profit) = SUM(p.net_profit) — БЕЗ вычета ff_otziv/ff_adv/ff_storage_fee.
    В /wb-profit/top-products (profit_columns.MARGIN_SELECT) — С вычетом. Разница намеренная,
    здесь повторяем Yii2.
  * «Прибыль»/«Маржа» считаются из raw net_profit с вычетом ff_* — как в Yii2 и как в top-products.
  * Отзывы = ff_otziv, Реклама = ff_adv, Хранение = ff_storage_fee (отчёт WB по позициям).
"""
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Прибыль до налога = raw net_profit − НДС − себестоимость − отзывы − реклама − хранение.
_PROFIT = (
    "SUM(p.net_profit) - SUM(IFNULL(p.f_nds,0)) - SUM(IFNULL(p.f_cost_price,0))"
    " - SUM(IFNULL(p.ff_otziv,0)) - SUM(IFNULL(p.ff_adv,0)) - SUM(IFNULL(p.ff_storage_fee,0))"
)

SELECT_SQL = f"""
    SELECT p.nm_id AS nm_id,
           c.title AS title,
           c.brand AS brand,
           c.vendorCode AS vendor_code,
           MAX(c.subjectName) AS subject,
           MAX(c.photos) AS photos,
           SUM(p.qnt) AS qnt,
           SUM(p.amount) AS amount,
           SUM(p.`return`) AS return_sum,
           SUM(p.commission) AS commission,
           SUM(p.f_acquiring_fee) AS f_acquiring_fee,
           SUM(p.f_acceptance) AS f_acceptance,
           SUM(p.f_delivery) AS f_delivery,
           SUM(IFNULL(p.ff_storage_fee,0)) AS f_storage_fee,
           SUM(p.f_penalty) AS f_penalty,
           SUM(p.f_deduction) AS f_deduction,
           SUM(IFNULL(p.ff_otziv,0)) AS f_otziv,
           SUM(IFNULL(p.ff_adv,0)) AS f_adv,
           SUM(p.f_cashback) AS f_cashback,
           SUM(p.net_profit) AS net_profit,
           SUM(p.net_profit) - SUM(IFNULL(p.ff_otziv,0)) - SUM(IFNULL(p.ff_adv,0))
             - SUM(IFNULL(p.ff_storage_fee,0)) AS net_profit_net,
           SUM(IFNULL(p.f_nds,0)) AS total_nds,
           SUM(IFNULL(p.f_cost_price,0)) AS total_cost,
           ({_PROFIT}) AS profit_before_tax,
           GREATEST(0, ({_PROFIT})) * 0.07 AS tax_amount,
           ({_PROFIT}) - (GREATEST(0, ({_PROFIT})) * 0.07) AS clean_margin,
           SUM(p.amount) / NULLIF(SUM(p.qnt),0) AS amount_per_item,
           SUM(p.net_profit) / NULLIF(SUM(p.qnt),0) AS profit_per_item,
           (({_PROFIT}) - (GREATEST(0, ({_PROFIT})) * 0.07)) / NULLIF(SUM(p.qnt),0) AS clear_per_item,
           SUM(IFNULL(p.f_cost_price,0)) / NULLIF(SUM(p.qnt),0) AS cost_per_item
    FROM agg_daily_summary p
    LEFT JOIN wbcards c ON c.nmID = p.nm_id
    WHERE p.sdate BETWEEN :d1 AND :d2{{company_where}}
    GROUP BY p.nm_id, c.title, c.brand, c.vendorCode
"""

ALLOWED_LIMITS = (20, 50, 200, 500, 1000)


class ProfitIndexService:
    """Топ / худшие товары за N дней — блоки 2 и 3 страницы «Маржинальный учёт»."""

    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND p.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def sku_rank(self, order: str = "desc", days: int = 60,
                       limit: int = 20, date_from: str | None = None,
                       date_to: str | None = None) -> dict:
        """order: 'desc' — топ по марже, 'asc' — худшие (только товары с продажами)."""
        desc = str(order or "desc").lower() != "asc"
        if limit not in ALLOWED_LIMITS:
            limit = 20
        try:
            days = max(1, min(int(days or 60), 400))
        except (TypeError, ValueError):
            days = 60
        d2 = date_to or date.today().isoformat()
        d1 = date_from or (date.fromisoformat(d2) - timedelta(days=days)).isoformat()

        # Худшие — только товары, у которых были продажи (Yii2: HAVING SUM(qnt) > 0).
        having = "" if desc else " HAVING SUM(p.qnt) > 0"
        sql = text(SELECT_SQL.format(company_where=self._company_where())
                   + having
                   + f" ORDER BY clean_margin {'DESC' if desc else 'ASC'}, p.nm_id ASC"
                   + " LIMIT :limit")
        params = {"d1": d1, "d2": d2, "limit": int(limit), **self._company_params()}
        rows = (await self.db.execute(sql, params)).mappings().all()
        return {
            "date_from": d1,
            "date_to": d2,
            "days": days,
            "order": "desc" if desc else "asc",
            "rows": [dict(r) for r in rows],
        }
