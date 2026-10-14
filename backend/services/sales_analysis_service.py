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

"""Порт WbSalesAnalysisController.php:15 actionIndex + depdrop 179-248.

ТОП считается из detail_by_period (финдетализация WB, метод sales API deprecated):
  priceWithDisc -> retail_price_withdisc_rub (выручка акта),
  finishedPrice -> retail_amount, forPay -> ppvz_for_pay, spp -> ppvz_spp_prc,
  знак строк: supplier_oper_name Продажа + / Возврат -.
Категория в деталке отсутствует: фильтр — словарем nmID через wb_sales,
отображение — вторым запросом только для строк топа.
Гео — нативно через ppvz_office_id -> pvz_all (region_norm/city_norm).
Фронт не менялся: ключи ответа те же (total_sum/disc_sum выпилены — их никто не ел).
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

from backend.services.geo_names import NAME2CODE, COUNTRY_NAMES, regions_of_fo

DISTRICTS_RU = [
    "Центральный федеральный округ",
    "Приволжский федеральный округ",
    "Сибирский федеральный округ",
    "Южный федеральный округ",
    "Северо-Западный федеральный округ",
    "Уральский федеральный округ",
    "Дальневосточный федеральный округ",
    "Северо-Кавказский федеральный округ",
]


class SalesAnalysisService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self, alias: str = "d") -> str:
        return "" if self.company_id is None else f" AND {alias}.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def _subjects(self) -> list[str]:
        """Предметы только своих карточек (а не всего каталога WB)."""
        rows = (await self.db.execute(text(
            "SELECT DISTINCT c.subject_name as v FROM wb_subject_catalog c "
            "JOIN wbcards w ON w.subjectID = c.subject_id "
            "WHERE c.subject_name IS NOT NULL" + self._company_where("w") + " ORDER BY v"),
            self._company_params())).scalars().all()
        return [r for r in rows if r]

    async def _categories(self) -> list[str]:
        """Категории только своих карточек: parent_name каталога через subjectID."""
        rows = (await self.db.execute(text(
            "SELECT DISTINCT c.parent_name as v FROM wb_subject_catalog c "
            "JOIN wbcards w ON w.subjectID = c.subject_id "
            "WHERE c.parent_name IS NOT NULL" + self._company_where("w") + " ORDER BY v"),
            self._company_params())).scalars().all()
        return [r for r in rows if r]

    async def _category_nm_ids(self, category: str) -> list[int]:
        """nmID карточек категории: wbcards.subjectID -> каталог.parent_name."""
        rows = (await self.db.execute(text(
            "SELECT DISTINCT w.nmID FROM wbcards w "
            "JOIN wb_subject_catalog c ON c.subject_id = w.subjectID "
            "WHERE c.parent_name = :cat" + self._company_where("w")),
            {"cat": category, **self._company_params()})).scalars().all()
        return sorted({int(x) for x in rows if x})

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

        where = ["d.sale_dt BETWEEN :d1 AND :d2" + self._company_where("d"),
                 "d.supplier_oper_name IN ('Продажа', 'Возврат')"]
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
                        **self._company_params()}
        if brand:
            where.append("d.brand_name = :brand"); params["brand"] = brand
        if type_:
            where.append("d.subject_name = :type"); params["type"] = type_
        if category:
            # категория = parent_name каталога -> nmID через subjectID карточек
            ids = await self._category_nm_ids(category)
            if not ids:
                return []
            where.append(f"d.nm_id IN ({','.join(str(x) for x in ids)})")
        joins = ["JOIN wbcards c ON c.nmID = d.nm_id"]
        if country or region or oblast:
            joins.append("LEFT JOIN pvz_all p ON p.wb_id = d.ppvz_office_id")
            if country:
                code = NAME2CODE.get(str(country).strip().lower())
                if not code:
                    return []  # неизвестная страна — честно пусто, а не молча все
                # коды в нижнем регистре (чистит pvz_norm.py) — прямое равенство по индексу
                where.append("p.country = :cc"); params["cc"] = code.lower()
            if oblast:
                regs = regions_of_fo(oblast)
                if not regs:
                    return []
                in_list = ",".join("'" + r.replace("'", "''") + "'" for r in regs)
                where.append(f"p.region_norm IN ({in_list})")
            if region:
                where.append("p.region_norm = :region"); params["region"] = region

        where_sql = " AND ".join(where)
        join_sql = " ".join(joins)
        sql = text(f"""
            SELECT d.nm_id as nm_id, MAX(c.title) as card_name, MAX(c.vendorCode) as vendorCode,
                   MAX(c.photos) as photos,
                   MAX(c.brand) as brand, MAX(c.subjectName) as subject,
                   SUM(CASE WHEN d.supplier_oper_name = 'Продажа' THEN 1
                            WHEN d.supplier_oper_name = 'Возврат' THEN -1 ELSE 0 END) as sales_qty,
                   SUM(CASE WHEN d.supplier_oper_name = 'Продажа' THEN d.retail_amount
                            ELSE -d.retail_amount END) as finished_sum,
                   SUM(CASE WHEN d.supplier_oper_name = 'Продажа' THEN d.ppvz_for_pay
                            ELSE -d.ppvz_for_pay END) as for_pay_sum,
                   AVG(CASE WHEN d.supplier_oper_name = 'Продажа' THEN d.retail_price_withdisc_rub
                            ELSE -d.retail_price_withdisc_rub END) as apwd,
                   AVG(d.ppvz_spp_prc) as aspp,
                   AVG(CASE WHEN d.supplier_oper_name = 'Продажа' THEN d.retail_amount
                            ELSE -d.retail_amount END) as afp,
                   AVG(CASE WHEN d.supplier_oper_name = 'Продажа' THEN d.ppvz_for_pay
                            ELSE -d.ppvz_for_pay END) as aforPay
            FROM detail_by_period d
            {join_sql}
            WHERE {where_sql}
            GROUP BY d.nm_id
            ORDER BY {order_by}
            LIMIT :lim
        """)
        rows = [dict(r) for r in (await self.db.execute(sql, {**params, "lim": top_limit})).mappings().all()]
        if rows:
            # категория = parent_name каталога через subjectID (в деталке колонки нет)
            nm_ids = [int(r["nm_id"]) for r in rows if r.get("nm_id")]
            from sqlalchemy import bindparam
            cat_rows = (await self.db.execute(
                text("SELECT w.nmID as nmID, MAX(c.parent_name) AS category FROM wbcards w "
                     "LEFT JOIN wb_subject_catalog c ON c.subject_id = w.subjectID "
                     "WHERE w.nmID IN :ids GROUP BY w.nmID").bindparams(bindparam("ids", expanding=True)),
                {"ids": nm_ids})).mappings().all() if nm_ids else []
            cat_map = {int(r["nmID"]): r["category"] for r in cat_rows}
            for r in rows:
                r["category"] = cat_map.get(int(r["nm_id"])) if r.get("nm_id") else None
        return rows

    async def get_brands(self):
        rows = (await self.db.execute(text(
            "SELECT DISTINCT d.brand_name as v FROM detail_by_period d "
            "WHERE d.brand_name IS NOT NULL" + self._company_where("d") + " ORDER BY d.brand_name"),
            self._company_params())).scalars().all()
        return [r for r in rows if r]

    async def get_districts(self, country: str):
        # значения 1в1 как oblastOkrugName WB (проверено срезом: 8 ФО полными именами)
        if country != "Россия":
            return []
        return DISTRICTS_RU

    async def get_regions(self, country: str, oblast: str | None = None):
        if not country:
            return []
        code = NAME2CODE.get(str(country).strip().lower())
        if not code:
            return []
        where = "p.country = :code"
        params: dict = {"code": code.lower()}
        if country == "Россия" and oblast:
            regs = regions_of_fo(oblast)
            if not regs:
                return []
            in_list = ",".join("'" + r.replace("'", "''") + "'" for r in regs)
            where += f" AND p.region_norm IN ({in_list})"
        sql = text(f"SELECT DISTINCT p.region_norm as v FROM pvz_all p "
                   f"WHERE {where} AND p.region_norm IS NOT NULL ORDER BY v")
        rows = (await self.db.execute(sql, params)).scalars().all()
        return [r for r in rows if r]

    async def get_types(self, category: str):
        # предметы выбранной категории, только своих карточек
        if not category:
            return []
        rows = (await self.db.execute(text(
            "SELECT DISTINCT c.subject_name as v FROM wb_subject_catalog c "
            "JOIN wbcards w ON w.subjectID = c.subject_id "
            "WHERE c.parent_name = :cat AND c.subject_name IS NOT NULL"
            + self._company_where("w") + " ORDER BY v"),
            {"cat": category, **self._company_params()})).scalars().all()
        return [r for r in rows if r]

    async def get_filter_data(self):
        # для начальной загрузки — как в php filterData; бренды из деталки,
        # категории/предметы из каталога, страны фиксированные (wb_sales не трогаем)
        brands = await self.get_brands()
        subjects = await self._subjects()
        return {"brands": brands, "categories": await self._categories(), "types": subjects,
                "countries": list(COUNTRY_NAMES.values())}
