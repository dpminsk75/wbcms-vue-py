from sqlalchemy import bindparam, text
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
                               sort_by: str = "qnt", limit: int = 20, with_stock: bool = False):
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
        rows = [dict(r._mapping) for r in result.fetchall()]

        # 3. Остатки по складам WB (Склад WB) — опционально, чекбокс «выводить остаток»
        if with_stock:
            stocks, stock_date = await self._get_stocks(date_to, [r["nm_id"] for r in rows])
            for r in rows:
                r["stock"] = stocks.get(str(r["nm_id"]), 0)
                r["stock_date"] = stock_date

        return rows

    async def _get_stocks(self, date_to: str, nm_ids: list) -> tuple[dict, str | None]:
        """Остатки из wb_stocks (склады WB = «Склад WB»).

        Дата снимка: MAX(date) WHERE date <= date_to (фолбэк, если на date_to снимка нет).
        nm_id в wb_stocks — varchar, поэтому биндим строки (иначе индекс idx-wb_stocks-nm_id не используется).
        Возвращает (map nm_id -> quantity, дата снимка ISO).
        """
        if not nm_ids:
            return {}, None

        cid = "" if self.company_id is None else " AND s.company_id = :company_id"
        params = {"d": date_to, **self._company_params()}

        res = await self.db.execute(
            text(f"SELECT MAX(s.date) FROM wb_stocks s WHERE s.date <= :d{cid}"), params)
        stock_date = res.scalar()
        if not stock_date:
            return {}, None

        ids = [str(int(n)) for n in nm_ids]
        sql = text(f"""
            SELECT s.nm_id, SUM(s.quantity) AS stock
            FROM wb_stocks s
            WHERE s.date = :d{cid} AND s.nm_id IN :ids
            GROUP BY s.nm_id
        """).bindparams(bindparam("ids", expanding=True))
        res = await self.db.execute(sql, {**params, "ids": ids})
        stocks = {str(r[0]): int(r[1] or 0) for r in res.fetchall()}
        return stocks, stock_date.isoformat() if hasattr(stock_date, "isoformat") else str(stock_date)
