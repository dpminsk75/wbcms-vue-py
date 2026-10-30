"""Производство, ступень 1 (/api/production): план печати + отчет «когда печатать».

Доступ: перм manageFbsStocks (как складской контур).
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_manage_fbs_stocks
from backend.services.production_service import DEFAULTS, ProductionService

router = APIRouter(prefix="/api/production", tags=["production"])


def _svc(db: AsyncSession, company_id) -> ProductionService:
    return ProductionService(db, company_id=company_id)


@router.get("/report")
async def production_report(
    period: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Отчет «когда печатать» за месяц (YYYY-MM)."""
    svc = _svc(db, company_id)
    return await svc.report(period)


@router.get("/plan")
async def production_plan(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Текущий список плана (товары + параметры цикла)."""
    svc = _svc(db, company_id)
    return {"rows": await svc.plan(), "defaults": DEFAULTS}


@router.put("/plan")
async def production_plan_save(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Сохранить список плана (полная замена)."""
    svc = _svc(db, company_id)
    try:
        return await svc.save_plan(payload.get("items") or [])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/available")
async def production_available(
    q: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Карточки компании, которых нет в плане (для добавления)."""
    svc = _svc(db, company_id)
    return {"rows": await svc.available_cards(q, limit)}
