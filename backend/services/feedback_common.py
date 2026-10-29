"""Общие помощники блока «Отзывы»: резолв фильтра по товарам и списки брендов.

Фильтр «товар / бренд / категория» применяется к отзывам через wbcards:
в wb_feedbacks нет ни бренда, ни категории, поэтому сначала резолвим список
nmID, а потом фильтруем по нему. Логика — как в geo_sales_service.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.like_mask import escape_like


async def resolve_card_ids(db: AsyncSession, company_id: int | None,
                           q: str | None = None, brand: str | None = None,
                           category: str | None = None) -> list[int] | None:
    """Маска товара + бренд + категория → список nmID из wbcards.

    None — фильтров нет (все карточки); [] — фильтры заданы, но совпадений нет
    (не «все»!). Пустой список обязан отсекать всё, а не показывать всё.
    """
    conds: list[str] = []
    params: dict = {}
    if q and str(q).strip():
        raw = str(q).strip()
        # Выбор карточки из подсказок приходит чистым nmID — ищем его точно,
        # а не LIKE '%...%' (иначе «526443466» поймает и «1526443466»).
        if raw.isdigit():
            exact = await db.execute(text(
                "SELECT nmID FROM wbcards WHERE nmID = :nid"
                + (" AND company_id = :cid" if company_id is not None else "")
                + " LIMIT 1"),
                {"nid": int(raw), **({"cid": company_id} if company_id is not None else {})})
            hit = exact.scalars().first()
            if hit is not None:
                return [int(hit)]
        # экранируем спецсимволы LIKE, иначе '...' рвёт запрос (1064),
        # а '_' в артикуле («ДС_СВ_Амигуруми_25$») ищется как wildcard
        mask = escape_like(raw)
        conds.append("(CAST(nmID AS CHAR) LIKE :q ESCAPE '\\\\' "
                     "OR vendorCode LIKE :q ESCAPE '\\\\' "
                     "OR title LIKE :q ESCAPE '\\\\')")
        params["q"] = f"%{mask}%"
    if brand:
        conds.append("brand = :b")
        params["b"] = brand
    if category:
        conds.append("subjectName = :c")
        params["c"] = category
    if not conds:
        return None
    if company_id is not None:
        conds.append("company_id = :cid")
        params["cid"] = company_id
    rows = (await db.execute(text(
        "SELECT nmID FROM wbcards WHERE " + " AND ".join(conds) + " LIMIT 2000"),
        params)).scalars().all()
    return sorted({int(x) for x in rows if x})


async def filter_options(db: AsyncSession, company_id: int | None) -> dict:
    """Бренды и категории для выпадающих списков (из wbcards)."""
    comp = "" if company_id is None else " AND company_id = :cid"
    p = {} if company_id is None else {"cid": company_id}
    br = (await db.execute(text(
        f"SELECT DISTINCT brand FROM wbcards WHERE brand IS NOT NULL AND brand <> ''{comp} "
        f"ORDER BY brand LIMIT 500"), p)).scalars().all()
    ct = (await db.execute(text(
        f"SELECT DISTINCT subjectName FROM wbcards WHERE subjectName IS NOT NULL "
        f"AND subjectName <> ''{comp} ORDER BY subjectName LIMIT 500"), p)).scalars().all()
    return {"brands": [str(x) for x in br if x],
            "categories": [str(x) for x in ct if x]}


def nps(c5: int, c13: int, rated: int) -> float | None:
    """NPS: промоутеры (оценка 5) минус детракторы (1–3), делим на оценённые.

    Оценка 4 — пассивный, в NPS не входит (как у WB).
    """
    if not rated:
        return None
    return round(100.0 * (c5 - c13) / rated, 1)


def delta_pct(cur: float | None, prev: float | None) -> float | None:
    """Изменение в процентах; None, если базы нет (делить на ноль нельзя)."""
    if cur is None or prev in (None, 0):
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


def delta_pp(cur: float | None, prev: float | None) -> float | None:
    """Изменение в процентных пунктах (для оценки и NPS)."""
    if cur is None or prev is None:
        return None
    return round(cur - prev, 1)
