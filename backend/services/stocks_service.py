"""Остатки WB по складам (Склад WB) — общий сервис для отчётов по товарам.

Дата снимка: MAX(date) WHERE date <= date_to (фолбэк на ближайший доступный снимок).
nm_id в wb_stocks — varchar, поэтому биндим строки (иначе индекс idx-wb_stocks-nm_id
не используется — MySQL конвертирует колонку в число).

Используют: TopProductsService (ТОП товаров), TagMarginService (Маржа по тегам).
"""
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


class StocksService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    async def get_stocks(self, date_to: str, nm_ids: list) -> tuple[dict, str | None]:
        """Остатки на дату «по».

        Возвращает ({nm_id: quantity}, дата снимка ISO). Даты снимка нет — пустые остатки.
        """
        if not nm_ids:
            return {}, None

        cid = "" if self.company_id is None else " AND s.company_id = :company_id"
        params: dict = {"d": date_to}
        if self.company_id is not None:
            params["company_id"] = self.company_id

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
