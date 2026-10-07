"""Новости WB: лента дашборда + полный список + прочитанные."""

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user
from backend.services.news_service import NewsService

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
async def news_feed(
    days: int = Query(default=3, ge=1, le=30),
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Лента для NewsBlock (фильтр типов компании уже внутри)."""
    return await NewsService(db).feed(user["id"], company_id, days, limit)


@router.get("/all")
async def news_all(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    types: str | None = Query(default=None, description="id через запятую"),
    limit: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(default=None, description="поиск по заголовку и тексту"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    tids = [int(x) for x in (types or "").split(",") if x.strip().isdigit()]
    return await NewsService(db).search(
        user["id"], company_id, date_from, date_to, tids or None, limit, q)


@router.get("/types")
async def news_types(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await NewsService(db).type_list()


@router.post("/{news_id}/read")
async def news_read(
    news_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await NewsService(db).mark_read(user["id"], news_id)
