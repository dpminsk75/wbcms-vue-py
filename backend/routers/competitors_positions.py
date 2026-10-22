"""Отчёты по собранной выдаче WB — /api/competitors/positions.

Две сводки (план «2026-10-21_extension_passive_mode.md», §UI для позиций):
1. `GET /phrases` — какие запросы сохранены, когда, кем;
   `GET /phrase` — выдача по фразе (как сохранена) + кто сохранил.
2. `GET /cards` — наши карточки с наблюдениями;
   `GET /card` — по карточке: запросы, наши позиции, топ конкурентов.

Гейт — require_seo (viewSeo|admin), скоуп по компании.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, require_seo
from backend.services.competitors_positions_service import CompetitorsPositionsService

router = APIRouter(prefix="/api/competitors/positions", tags=["competitors-positions"])


@router.get("/phrases")
async def positions_phrases(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    q: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Сохранённые запросы: даты, число сохранений, наши карточки в выдаче, кто сохранил."""
    return await CompetitorsPositionsService(db, company_id).phrases(
        date_from or None, date_to or None, q, limit
    )


@router.get("/phrase")
async def positions_phrase(
    phrase: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    day: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Выдача по фразе — как она была сохранена (последний срез, если `day` не задан)."""
    return await CompetitorsPositionsService(db, company_id).phrase(
        phrase, date_from or None, date_to or None, day or None
    )


@router.get("/cards")
async def positions_cards(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    limit: int = Query(default=300, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Наши карточки, по которым есть наблюдения выдачи."""
    return await CompetitorsPositionsService(db, company_id).cards(
        date_from or None, date_to or None, limit
    )


@router.get("/niches")
async def positions_niches(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    limit: int = Query(default=300, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Профиль ниш по фразам (разбор `resultset=filters`): цены, бренды, продавцы, акции."""
    return await CompetitorsPositionsService(db, company_id).niches(
        date_from or None, date_to or None, limit
    )


@router.get("/ads")
async def positions_ads(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Реклама и брендовые полки В ПОИСКЕ (разбор `banners/shelfs/search`)."""
    return await CompetitorsPositionsService(db, company_id).ads(
        date_from or None, date_to or None, limit
    )


@router.get("/card")
async def positions_card(
    nm_id: int = Query(..., ge=1),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    top: int = Query(default=12, ge=0, le=500),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """По нашей карточке: запросы, наши позиции, топ конкурентов (`top=0` — все)."""
    return await CompetitorsPositionsService(db, company_id).card(
        nm_id, date_from or None, date_to or None, top
    )
