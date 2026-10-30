"""Отчеты склада (/api/stock-reports) - порт WbDocReportController (Yii2).

Доступ: перм manageFbsStocks.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_manage_fbs_stocks
from backend.services.stock_report_service import StockReportService

router = APIRouter(prefix="/api/stock-reports", tags=["stock-reports"])


def _svc(db: AsyncSession, company_id) -> StockReportService:
    return StockReportService(db, company_id=company_id)


@router.get("/warehouses")
async def report_warehouses(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Свои склады для фильтра отчетов."""
    svc = _svc(db, company_id)
    return {"rows": await svc.warehouses()}


@router.get("/balance")
async def report_balance(
    warehouse_id: str = Query(default="all"),
    date: str | None = Query(default=None),
    q: str | None = Query(default=None),
    only_available: int = Query(default=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Наличие: текущие остатки или остатки на дату (история по ledger)."""
    svc = _svc(db, company_id)
    return await svc.balance(warehouse_id, date, q, bool(only_available), page, page_size)


@router.get("/turnover")
async def report_turnover(
    warehouse_id: str = Query(default="all"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Оборотная ведомость: начальный/конечный остаток + статьи периода."""
    svc = _svc(db, company_id)
    return await svc.turnover(warehouse_id, date_from, date_to, q, page, page_size)


@router.get("/card")
async def report_card(
    sku: str = Query(default=""),
    warehouse_id: str = Query(default="all"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Карточка товара: журнал проводок по SKU."""
    svc = _svc(db, company_id)
    return await svc.card(sku, warehouse_id, date_from, date_to, limit)


@router.get("/nonliquid")
async def report_nonliquid(
    warehouse_id: str = Query(default="all"),
    days: int = Query(default=30, ge=1, le=365),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Неликвиды: остаток есть, движений нет дольше N дней."""
    svc = _svc(db, company_id)
    return await svc.nonliquid(warehouse_id, days, q, page, page_size)
