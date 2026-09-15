"""Порт UnclaimedOrdersController.php:12-74 — невыкупленные товары."""
from datetime import date, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class UnclaimedOrdersService:
    PAGE_SIZE = 50
    SORT_COLUMNS = {
        "nm_id": "o.nm_id",
        "card_name": "c.title",
        "vendorCode": "c.vendorCode",
        "rate": "(SUM(o.is_cancel) / NULLIF(SUM(o.is_realization), 0))",
        "alls": "SUM(o.is_realization)",
        "cancel": "SUM(o.is_cancel)",
    }

    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND o.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    @staticmethod
    def default_params() -> dict:
        today = date.today()
        return {
            "date_from": (today - timedelta(days=14)).isoformat(),
            "date_to": today.isoformat(),
            "percent": 20.0,
            "min_orders": 5,
        }

    async def search(
        self,
        date_from: str | None,
        date_to: str | None,
        nm_id: int | None,
        percent: float | None,
        min_orders: int | None,
        sort: str,
        sort_dir: str,
        page: int,
        page_size: int,
    ) -> dict:
        defaults = self.default_params()
        date_from = date_from or defaults["date_from"]
        date_to = date_to or defaults["date_to"]
        percent = defaults["percent"] if percent is None else float(percent)
        min_orders = defaults["min_orders"] if min_orders is None else int(min_orders)
        sort = sort if sort in self.SORT_COLUMNS else "rate"
        sort_dir = "DESC" if sort_dir is None else ("ASC" if sort_dir.lower() == "asc" else "DESC")
        offset = (page - 1) * page_size
        rate_threshold = percent / 100

        where = ["o.date BETWEEN :d1 AND :d2" + self._company_where()]
        params: dict = {
            "d1": f"{date_from} 00:00:00",
            "d2": f"{date_to} 23:59:59",
            "min_orders": min_orders,
            "rate_threshold": rate_threshold,
            **self._company_params(),
        }
        if nm_id is not None and nm_id != '':
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = nm_id

        base_query = f"""
            SELECT
                o.nm_id,
                c.title AS card_name,
                c.vendorCode,
                SUM(o.is_realization) AS alls,
                SUM(o.finished_price) AS sLO,
                SUM(o.is_cancel) AS cancel,
                SUM(CASE WHEN s.saleID IS NULL THEN 1 ELSE 0 END) AS notb,
                SUM(CASE WHEN s.saleID IS NULL THEN 0 ELSE 1 END) AS bought,
                SUM(s.finishedPrice) AS sum_price,
                SUM(s.forPay) AS sFP,
                SUM(o.is_cancel) / NULLIF(SUM(o.is_realization), 0) AS rate
            FROM wb_order AS o
            INNER JOIN wbcards AS c ON o.nm_id = c.nmID
            LEFT JOIN wb_sales AS s ON o.srid = s.srid
            WHERE {' AND '.join(where)}
            GROUP BY o.nm_id, c.title, c.vendorCode
            HAVING SUM(o.is_cancel) > 1
               AND SUM(o.is_realization) > :min_orders
               AND (SUM(o.is_cancel) / NULLIF(SUM(o.is_realization), 0)) > :rate_threshold
        """

        order_by = f"{self.SORT_COLUMNS[sort]} {sort_dir}"
        data_params = {**params, "limit": page_size, "offset": offset}
        rows = (
            await self.db.execute(
                text(f"{base_query}\nORDER BY {order_by}\nLIMIT :limit OFFSET :offset"),
                data_params,
            )
        ).mappings().all()
        items = [dict(row) for row in rows]

        count_row = (
            await self.db.execute(
                text(f"SELECT COUNT(*) AS total FROM ({base_query}) AS unclaimed_groups"),
                {key: value for key, value in params.items() if key not in {"limit", "offset"}},
            )
        ).mappings().first()
        total = int(count_row["total"] or 0) if count_row else 0

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "params": {
                "date_from": date_from,
                "date_to": date_to,
                "percent": percent,
                "min_orders": min_orders,
                "sort": sort,
                "dir": sort_dir.lower(),
            },
        }
