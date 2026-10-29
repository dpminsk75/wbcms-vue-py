"""Дашборд «Отзывы» — сводка по отзывам и обзор наших товаров.

Роутер живёт в /api/feedback/dashboard — в одном пространстве с ответами и
тегами (сам /api/feedback занят ими).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.feedback_dashboard_service import FeedbackDashboardService

router = APIRouter(prefix="/api/feedback/dashboard", tags=["feedback-dashboard"])


def _check_dates(date_from: str, date_to: str) -> None:
    import re
    if not (re.match(r"^\d{4}-\d{2}-\d{2}$", date_from or "")
            and re.match(r"^\d{4}-\d{2}-\d{2}$", date_to or "")):
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD")
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from > date_to")


@router.get("/summary")
async def dashboard_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    period: str = Query(default="day", pattern="^(day|week|month)$"),
    rev_mode: str = Query(default="all", pattern="^(all|content|rated)$"),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """KPI, распределение по звёздам, тональность, динамика."""
    _check_dates(date_from, date_to)
    svc = FeedbackDashboardService(db, company_id=company_id)
    return await svc.summary(date_from, date_to, nm_id, brand, category, period, q,
                             rev_mode)


@router.get("/cards")
async def dashboard_cards(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    rev_mode: str = Query(default="all", pattern="^(all|content|rated)$"),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """ТОП наших карточек по заказам (только те, у которых есть отзывы)."""
    _check_dates(date_from, date_to)
    svc = FeedbackDashboardService(db, company_id=company_id)
    return await svc.cards(date_from, date_to, nm_id, brand, category, limit, q, rev_mode)


@router.get("/options")
async def dashboard_options(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Бренды и категории для фильтра."""
    svc = FeedbackDashboardService(db, company_id=company_id)
    return await svc.options()
