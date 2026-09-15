"""Порт WbSalesAnalysisController.php:15 actionIndex + depdrop 179-248"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

class SalesAnalysisService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND s.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def get_top(self, date_from: str, date_to: str, report_type: str = "revenue", top_limit: int = 20,
                      brand: str | None = None, category: str | None = None, type_: str | None = None,
                      country: str | None = None, region: str | None = None, oblast: str | None = None):
        if report_type not in ("revenue", "qty"):
            report_type = "revenue"
        top_limit = max(1, min(int(top_limit or 20), 100))
        # дефолты как в php: 1 числа текущего месяца .. вчера
        if not date_from:
            date_from = date.today().replace(day=1).isoformat()
        if not date_to:
            date_to = (date.today() - timedelta(days=1)).isoformat()

        order_by = "sales_qty DESC" if report_type == "qty" else "finished_sum DESC"

        where = ["s.date BETWEEN :d1 AND :d2" + self._company_where()]
        params: dict = {"d1": date_from, "d2": date_to, "lim": top_limit, **self._company_params()}
        if brand:
            where.append("s.brand = :brand"); params["brand"] = brand
        if category:
            where.append("s.category = :category"); params["category"] = category
        if type_:
            where.append("s.subject = :type"); params["type"] = type_
        if country:
            where.append("s.countryName = :country"); params["country"] = country
        if region:
            where.append("s.regionName = :region"); params["region"] = region
        if oblast:
            where.append("s.oblastOkrugName = :oblast"); params["oblast"] = oblast

        where_sql = " AND ".join(where)
        sql = text(f"""
            SELECT s.nmId as nm_id, c.title as card_name, c.vendorCode as vendorCode,
                   s.brand, s.subject, s.category,
                   AVG(s.spp) as aspp,
                   SUM(s.totalPrice) as total_sum,
                   SUM(s.finishedPrice) as finished_sum,
                   SUM(s.forPay) as for_pay_sum,
                   SUM(s.priceWithDisc) as disc_sum,
                   AVG(s.priceWithDisc) as apwd,
                   AVG(s.finishedPrice) as afp,
                   AVG(s.forPay) as aforPay,
                   SUM(CASE WHEN s.totalPrice > 0 THEN 1 WHEN s.totalPrice < 0 THEN -1 ELSE 0 END) as sales_qty
            FROM wb_sales s
            INNER JOIN wbcards c ON s.nmId = c.nmID
            WHERE {where_sql}
            GROUP BY s.nmId, c.title, c.vendorCode, s.brand, s.subject, s.category
            ORDER BY {order_by}
            LIMIT :lim
        """)
        rows = (await self.db.execute(sql, params)).mappings().all()
        return [dict(r) for r in rows]

    async def get_unique(self, column: str):
        # column: brand, category, subject, countryName
        allowed = {"brand", "category", "subject", "countryName"}
        if column not in allowed:
            return []
        where_extra = self._company_where()
        sql = text(f"SELECT DISTINCT {column} as v FROM wb_sales WHERE {column} IS NOT NULL{where_extra} ORDER BY {column}")
        rows = (await self.db.execute(sql, self._company_params())).scalars().all()
        return [r for r in rows if r]

    async def get_districts(self, country: str):
        if country != "Россия":
            return []
        sql = text(f"SELECT DISTINCT oblastOkrugName as v FROM wb_sales WHERE countryName='Россия' AND oblastOkrugName IS NOT NULL{self._company_where()} ORDER BY v")
        rows = (await self.db.execute(sql, self._company_params())).scalars().all()
        return [r for r in rows if r]

    async def get_regions(self, country: str, oblast: str | None = None):
        if not country:
            return []
        params: dict = {"country": country, **self._company_params()}
        where = "countryName = :country" + self._company_where()
        if country == "Россия" and oblast:
            where += " AND oblastOkrugName = :oblast"
            params["oblast"] = oblast
        sql = text(f"SELECT DISTINCT regionName as v FROM wb_sales WHERE {where} AND regionName IS NOT NULL ORDER BY v")
        rows = (await self.db.execute(sql, params)).scalars().all()
        return [r for r in rows if r]

    async def get_types(self, category: str):
        if not category:
            return []
        sql = text(f"SELECT DISTINCT subject as v FROM wb_sales WHERE category = :cat AND subject IS NOT NULL{self._company_where()} ORDER BY v")
        rows = (await self.db.execute(sql, {"cat": category, **self._company_params()})).scalars().all()
        return [r for r in rows if r]

    async def get_filter_data(self):
        # для начальной загрузки — как в php filterData
        brands = await self.get_unique("brand")
        categories = await self.get_unique("category")
        types = await self.get_unique("subject")
        countries = await self.get_unique("countryName")
        return {"brands": brands, "categories": categories, "types": types, "countries": countries}
