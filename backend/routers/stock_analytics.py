"""Анализ остатков WB (/api/stock-analytics).

Раздел «Анализ остатков»: вкладки «Оборачиваемость» и «По складам».
Доступ: перм viewOrders (тот же, что у пункта меню).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_perm
from backend.services.stock_analytics_service import (
    DEFAULT_DEFICIT_DAYS,
    DEFAULT_DAYS,
    DEFAULT_EXCESS_DAYS,
    StockAnalyticsService,
)

router = APIRouter(prefix="/api/stock-analytics", tags=["stock-analytics"])


def _svc(db: AsyncSession, company_id) -> StockAnalyticsService:
    return StockAnalyticsService(db, company_id=company_id)


@router.get("/turnover")
async def stock_turnover(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    threshold: int = Query(default=DEFAULT_DEFICIT_DAYS, ge=1, le=365),
    excess_days: int = Query(default=DEFAULT_EXCESS_DAYS, ge=1, le=3650),
    fbo_only: int = Query(default=1),
    price_mode: str = Query(default="wb", pattern="^(wb|cost)$"),
    limit: int = Query(default=100, ge=1, le=500),
    product: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewOrders")),
):
    """Оборачиваемость: дефицит / нет в наличии / излишки + KPI."""
    if company_id is None:
        raise HTTPException(status_code=400, detail="Выберите компанию")
    svc = _svc(db, company_id)
    return await svc.turnover(
        date_from=date_from, date_to=date_to, threshold=threshold,
        excess_days=excess_days, fbo_only=bool(fbo_only),
        price_mode=price_mode, limit=limit,
        product=product, brand=brand, category=category,
    )


@router.get("/sklads")
async def stock_sklads(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    top: int = Query(default=50, ge=1, le=500),
    mode: str = Query(default="all", pattern="^(all|top)$"),
    price_mode: str = Query(default="wb", pattern="^(wb|cost)$"),
    threshold: int = Query(default=DEFAULT_DEFICIT_DAYS, ge=1, le=365),
    excess_days: int = Query(default=DEFAULT_EXCESS_DAYS, ge=1, le=3650),
    product: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewOrders")),
):
    """Спрос по складам + ТОП товаров по остатку."""
    if company_id is None:
        raise HTTPException(status_code=400, detail="Выберите компанию")
    svc = _svc(db, company_id)
    return await svc.sklads(
        date_from=date_from, date_to=date_to, top=top, mode=mode,
        price_mode=price_mode, threshold=threshold, excess_days=excess_days,
        product=product, brand=brand, category=category,
    )


@router.get("/options")
async def stock_options(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewOrders")),
):
    """Дефолты и справочники для фильтров."""
    svc = _svc(db, company_id)
    brands: list[str] = []
    categories: list[str] = []
    if company_id is not None:
        rows = await svc._rows(
            "SELECT DISTINCT c.brand AS brand FROM wbcards c "
            "WHERE (c.company_id = :cid OR c.company_id IS NULL) "
            "AND c.brand IS NOT NULL AND c.brand <> '' ORDER BY c.brand",
            {"cid": company_id},
        )
        brands = [str(r["brand"]) for r in rows]
        rows = await svc._rows(
            "SELECT DISTINCT sc.parent_name AS parent_name FROM wbcards c "
            "JOIN wb_subject_catalog sc ON sc.subject_id = c.subjectID "
            "WHERE (c.company_id = :cid OR c.company_id IS NULL) "
            "AND sc.parent_name IS NOT NULL AND sc.parent_name <> '' "
            "ORDER BY sc.parent_name",
            {"cid": company_id},
        )
        categories = [str(r["parent_name"]) for r in rows]
    return {
        "days": [7, 14, 30, 90, 365],
        "default_days": DEFAULT_DAYS,
        "deficit_days": [3, 7, 14, 30],
        "default_deficit_days": DEFAULT_DEFICIT_DAYS,
        "excess_days": DEFAULT_EXCESS_DAYS,
        "top": [20, 50, 100, 500],
        "default_top": 50,
        "price_mode": [{"value": "wb", "label": "Со скидкой"},
                       {"value": "cost", "label": "Себестоимость"}],
        "demand": [{"value": "fbo", "label": "FBO"},
                   {"value": "all", "label": "FBO+FBS"}],
        "brands": brands,
        "categories": categories,
        "company_id": company_id,
    }
