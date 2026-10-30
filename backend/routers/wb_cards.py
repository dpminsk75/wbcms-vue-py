"""Витрина карточек WB (В11а, /wb/cards) — список wbcards с фильтрами.

Порт WbController::actionCards + WbCardSearch; view для вошедших
(в PHP AccessControl был roles ['@']).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user
from backend.services.wb_cards_service import WbCardsService

router = APIRouter(prefix="/api/wb-cards", tags=["wb-cards"])


@router.get("")
async def wb_cards_search(
    nm_id: int | None = Query(default=None, ge=1),
    imt_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    vendor: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    subject_name: str | None = Query(default=None),
    title: str | None = Query(default=None),
    description: str | None = Query(default=None),
    only_unused: int = Query(default=0, ge=0, le=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    _user: dict = Depends(get_current_user),
):
    svc = WbCardsService(db, company_id=company_id)
    return await svc.search(nm_id=nm_id, imt_id=imt_id, subject_id=subject_id,
                            vendor=vendor, brand=brand, subject_name=subject_name,
                            title=title, description=description,
                            only_unused=only_unused, page=page, page_size=page_size)


@router.get("/filters")
async def wb_cards_filters(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    _user: dict = Depends(get_current_user),
):
    svc = WbCardsService(db, company_id=company_id)
    return await svc.filters()
