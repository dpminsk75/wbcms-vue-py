"""Сырые заказы wb_order — порт WbOrderSearch::search (только рабочие фильтры, вариант А).

Рабочие фильтры (WbOrderSearch.php:55-65): nm_id (=), is_cancel (=),
g_number/supplier_article/brand/category (LIKE), cardTitle (LIKE wbcards.title),
date — DateRange BETWEEN (в Yii2 хрупкий LIKE по datetime, здесь BETWEEN).
Мертвые (total_price, finished_price, discount_percent, subject) — ввода нет, только чтение.
Сортировки whitelist: date, nm_id, finished_price, cardTitle (WbOrderSearch.php:31-42).
Пагинация: pageSize=100, дефолт date DESC. Company-scope обязателен.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SORT_MAP = {
    "date": "o.date",
    "nm_id": "o.nm_id",
    "finished_price": "o.finished_price",
    "cardTitle": "c.title",
    "card_title": "c.title",
}


def parse_sort(raw: str | None) -> str:
    """'-date' / 'date,-finished_price' → ORDER BY. Неизвестное → date DESC."""
    if not raw or not raw.strip():
        return "o.date DESC"
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
    return ", ".join(parts) if parts else "o.date DESC"


class WbOrdersService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND o.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    def _filters(self, date_from, date_to, nm_id, supplier_article, brand,
                 category, card_title, g_number, is_cancel) -> tuple[str, dict]:
        where = ["1=1" + self._company_where()]
        params: dict = {**self._company_params()}
        if date_from and date_to:
            where.append("o.date BETWEEN :d1 AND :d2")
            params["d1"] = f"{date_from} 00:00:00"
            params["d2"] = f"{date_to} 23:59:59"
        elif date_from:
            where.append("o.date >= :d1")
            params["d1"] = f"{date_from} 00:00:00"
        elif date_to:
            where.append("o.date <= :d2")
            params["d2"] = f"{date_to} 23:59:59"
        if nm_id not in (None, ""):
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = str(nm_id)
        if is_cancel is not None:
            where.append("o.is_cancel = :is_cancel")
            params["is_cancel"] = is_cancel
        if g_number:
            where.append("o.g_number LIKE :g_number")
            params["g_number"] = f"%{g_number}%"
        if supplier_article:
            where.append("o.supplier_article LIKE :supplier_article")
            params["supplier_article"] = f"%{supplier_article}%"
        if brand:
            where.append("o.brand LIKE :brand")
            params["brand"] = f"%{brand}%"
        if category:
            where.append("o.category LIKE :category")
            params["category"] = f"%{category}%"
        if card_title:
            where.append("c.title LIKE :card_title")
            params["card_title"] = f"%{card_title}%"
        return " AND ".join(where), params

    @staticmethod
    def _serialize(row: dict) -> dict:
        d = dict(row)
        for k in ("date", "last_change_date", "cancel_date", "sale_date", "created_at"):
            if d.get(k) is not None:
                d[k] = str(d[k])
        for k in ("total_price", "price_with_disc", "spp", "finished_price", "for_pay",
                  "delivery_rub", "return_rub", "commission_percent", "commission_fee",
                  "acquiring_percent", "acquiring_fee", "cashback_amount"):
            if d.get(k) is not None:
                try:
                    d[k] = float(d[k])
                except (TypeError, ValueError):
                    pass
        return d

    async def list(self, date_from=None, date_to=None, nm_id=None,
                   supplier_article=None, brand=None, category=None,
                   card_title=None, g_number=None, is_cancel=None,
                   sort=None, page=1, page_size=100) -> dict:
        where_sql, params = self._filters(
            date_from, date_to, nm_id, supplier_article, brand,
            category, card_title, g_number, is_cancel)
        order_sql = parse_sort(sort)
        total = (await self.db.execute(text(
            f"""SELECT COUNT(*) AS cnt FROM wb_order o
                LEFT JOIN wbcards c ON c.nmID = o.nm_id
                WHERE {where_sql}"""), params)).scalar() or 0
        rows = (await self.db.execute(text(
            f"""SELECT o.*, c.title AS card_title
                FROM wb_order o
                LEFT JOIN wbcards c ON c.nmID = o.nm_id
                WHERE {where_sql}
                ORDER BY {order_sql} LIMIT :lim OFFSET :off"""),
            {**params, "lim": page_size, "off": (page - 1) * page_size})).mappings().all()
        return {"items": [self._serialize(r) for r in rows],
                "total": int(total), "page": page, "page_size": page_size}

    async def get(self, order_id: int) -> dict | None:
        where_sql, params = self._filters(None, None, None, None, None, None, None, None, None)
        # detail: тот же company-scope, без фильтров (30 полей view.php:35-87 маппятся 1-в-1)
        row = (await self.db.execute(text(
            f"""SELECT o.*, c.title AS card_title
                FROM wb_order o
                LEFT JOIN wbcards c ON c.nmID = o.nm_id
                WHERE {where_sql} AND o.id = :id LIMIT 1"""),
            {**params, "id": order_id})).mappings().first()
        return self._serialize(row) if row else None
