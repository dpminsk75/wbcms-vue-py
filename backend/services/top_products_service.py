from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.profit_columns import MARGIN_DIMENSIONS, MARGIN_SELECT, default_period, validate_sort

class TopProductsService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self, alias: str = "p") -> str:
        return "" if self.company_id is None else f" AND {alias}.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def get_top_products(self, date_from: str | None = None, date_to: str | None = None, 
                               sort_by: str = "qnt", limit: int = 20):
        # 1. Валидация и дефолты (формулы — только в profit_columns.MARGIN_SELECT)
        date_from, date_to = default_period(date_from, date_to)
        sort_by = validate_sort(sort_by)
            
        allowed_limits = {20, 50, 200, 500, 1000}
        if limit not in allowed_limits:
            limit = 20

        # 2. SQL запрос (адаптирован из WbProfitController.php:30 actionTopProducts)
        # В FastAPI используем алиасы для возвращаемых полей, чтобы соответствовать frontend ожиданиям
        cols = ",\n                ".join([*MARGIN_DIMENSIONS, *MARGIN_SELECT])
        sql = text(f"""
            SELECT
                {cols}
            FROM agg_daily_summary p
            LEFT JOIN wbcards c ON c.nmID = p.nm_id
            WHERE p.sdate BETWEEN :d1 AND :d2 {self._company_where("p")}
            GROUP BY p.nm_id, c.title, c.brand, c.vendorCode
            ORDER BY {sort_by} DESC
            LIMIT :limit
        """)

        params = {"d1": date_from, "d2": date_to, "limit": limit, **self._company_params()}
        result = await self.db.execute(sql, params)
        return [dict(r._mapping) for r in result.fetchall()]
