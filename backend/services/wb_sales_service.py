"""Сырые продажи wb_sales — порт WbSalesSearch::search (только рабочие фильтры, вариант А).

Рабочие фильтры (WbSalesSearch.php:59-82): nmId/incomeID/isSupply/isRealization/
totalPrice/finishedPrice (=); saleID/srid/number/supplierArticle/barcode/
warehouseName/warehouseType/countryName/oblastOkrugName/regionName/subject/
category/brand (LIKE); date — DateRange BETWEEN (в Yii2 хрупкий LIKE, здесь BETWEEN).
Мертвые (discountPercent, priceWithDisc, forPay, paymentSaleAmount, techSize,
lastChangeDate, orderType, gNumber) — ввода нет. Баг `andFilterWhere nmId до load()`
(:44) — здесь фильтр применяется после парсинга, один раз.
Сортировка whitelist: date, nmId, supplierArticle, totalPrice, spp (дефолт date DESC).
Пагинация: pageSize=20. PK-строка saleID (S…=продажа, R…=возврат), srid неуникален.
Company-scope обязателен.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SORT_MAP = {
    "date": "s.date",
    "nmId": "s.nmId", "nm_id": "s.nmId",
    "supplierArticle": "s.supplierArticle", "supplier_article": "s.supplierArticle",
    "totalPrice": "s.totalPrice", "total_price": "s.totalPrice",
    "spp": "s.spp",
}


def parse_sort(raw: str | None) -> str:
    """'-date' / 'date,-totalPrice' → ORDER BY. Неизвестное → date DESC."""
    if not raw or not raw.strip():
        return "s.date DESC"
    parts = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        desc = token.startswith("-")
        key = token[1:] if desc else token
        col = SORT_MAP.get(key)
        if not col:
            continue
        parts.append(f"{col} {'DESC' if desc else 'ASC'}")
    return ", ".join(parts) if parts else "s.date DESC"


class WbSalesService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND s.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    def _filters(self, date_from, date_to, nm_id, income_id, is_supply,
                 is_realization, total_price, finished_price, sale_id, srid,
                 number, supplier_article, barcode, warehouse_name, warehouse_type,
                 country_name, oblast_name, region_name, subject, category,
                 brand, card_title, geo=None) -> tuple[str, dict]:
        where = ["1=1" + self._company_where()]
        params: dict = {**self._company_params()}
        if date_from and date_to:
            where.append("s.date BETWEEN :d1 AND :d2")
            params["d1"] = f"{date_from} 00:00:00"
            params["d2"] = f"{date_to} 23:59:59"
        elif date_from:
            where.append("s.date >= :d1")
            params["d1"] = f"{date_from} 00:00:00"
        elif date_to:
            where.append("s.date <= :d2")
            params["d2"] = f"{date_to} 23:59:59"
        if nm_id is not None:
            where.append("s.nmId = :nm_id")
            params["nm_id"] = nm_id
        if income_id is not None:
            where.append("s.incomeID = :income_id")
            params["income_id"] = income_id
        if is_supply is not None:
            where.append("s.isSupply = :is_supply")
            params["is_supply"] = is_supply
        if is_realization is not None:
            where.append("s.isRealization = :is_realization")
            params["is_realization"] = is_realization
        if total_price is not None:
            where.append("s.totalPrice = :total_price")
            params["total_price"] = total_price
        if finished_price is not None:
            where.append("s.finishedPrice = :finished_price")
            params["finished_price"] = finished_price
        likes = {
            "saleID": sale_id, "srid": srid, "number": number,
            "supplierArticle": supplier_article, "barcode": barcode,
            "warehouseName": warehouse_name, "warehouseType": warehouse_type,
            "countryName": country_name, "oblastOkrugName": oblast_name,
            "regionName": region_name, "subject": subject,
            "category": category, "brand": brand,
        }
        for col, val in likes.items():
            if val:
                key = f"like_{col}"
                where.append(f"s.{col} LIKE :{key}")
                params[key] = f"%{val}%"
        if card_title:
            where.append("c.title LIKE :card_title")
            params["card_title"] = f"%{card_title}%"
        if geo:
            # один поиск по подстроке сразу по трем geo-полям (шапка «Регион покупки»)
            where.append("(s.countryName LIKE :geo OR s.oblastOkrugName LIKE :geo OR s.regionName LIKE :geo)")
            params["geo"] = f"%{geo}%"
        return " AND ".join(where), params

    @staticmethod
    def _serialize(row: dict) -> dict:
        d = dict(row)
        for k in ("date", "lastChangeDate", "created_at"):
            if d.get(k) is not None:
                d[k] = str(d[k])
        for k in ("totalPrice", "priceWithDisc", "spp", "finishedPrice",
                  "paymentSaleAmount", "forPay"):
            if d.get(k) is not None:
                try:
                    d[k] = float(d[k])
                except (TypeError, ValueError):
                    pass
        return d

    async def list(self, date_from=None, date_to=None, nm_id=None,
                   income_id=None, is_supply=None, is_realization=None,
                   total_price=None, finished_price=None, sale_id=None,
                   srid=None, number=None, supplier_article=None, barcode=None,
                   warehouse_name=None, warehouse_type=None, country_name=None,
                   oblast_name=None, region_name=None, subject=None,
                   category=None, brand=None, card_title=None, geo=None,
                   sort=None, page=1, page_size=20) -> dict:
        where_sql, params = self._filters(
            date_from, date_to, nm_id, income_id, is_supply, is_realization,
            total_price, finished_price, sale_id, srid, number,
            supplier_article, barcode, warehouse_name, warehouse_type,
            country_name, oblast_name, region_name, subject, category,
            brand, card_title, geo)
        order_sql = parse_sort(sort)
        total = (await self.db.execute(text(
            f"""SELECT COUNT(*) AS cnt FROM wb_sales s
                LEFT JOIN wbcards c ON c.nmID = s.nmId
                WHERE {where_sql}"""), params)).scalar() or 0
        rows = (await self.db.execute(text(
            f"""SELECT s.*, c.nmID AS card_nmid, c.title AS cardTitle
                FROM wb_sales s
                LEFT JOIN wbcards c ON c.nmID = s.nmId
                WHERE {where_sql}
                ORDER BY {order_sql} LIMIT :lim OFFSET :off"""),
            {**params, "lim": page_size, "off": (page - 1) * page_size})).mappings().all()
        return {"items": [self._serialize(r) for r in rows],
                "total": int(total), "page": page, "page_size": page_size}

    async def get(self, sale_id: str) -> dict | None:
        where_scope = self._company_where()
        params: dict = {**self._company_params(), "sid": sale_id}
        row = (await self.db.execute(text(
            f"""SELECT s.*, c.nmID AS card_nmid, c.title AS cardTitle
                FROM wb_sales s
                LEFT JOIN wbcards c ON c.nmID = s.nmId
                WHERE 1=1{where_scope} AND s.saleID = :sid LIMIT 1"""),
            params)).mappings().first()
        return self._serialize(row) if row else None
