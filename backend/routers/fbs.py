"""FBS-дашборд «Продажа со своего склада», вкладка Сводка (образец: routers/cost.py)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.fbs_report_service import FbsReportService

router = APIRouter(prefix="/api/fbs", tags=["fbs"])


def _check_dates(date_from: str, date_to: str) -> None:
    try:
        d1 = date.fromisoformat(date_from)
        d2 = date.fromisoformat(date_to)
    except ValueError:
        raise HTTPException(status_code=400,
                            detail="Даты — формат YYYY-MM-DD")
    if d2 < d1:
        raise HTTPException(status_code=400,
                            detail="date_to раньше date_from")


@router.get("/summary")
async def fbs_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    _check_dates(date_from, date_to)
    svc = FbsReportService(db, company_id=company_id)
    return await svc.summary(date_from, date_to, nm_id, brand, category)


@router.get("/breakdown")
async def fbs_breakdown(
    mode: str = Query(default="products", pattern="^(products|warehouses)$"),
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    _check_dates(date_from, date_to)
    svc = FbsReportService(db, company_id=company_id)
    return await svc.breakdown(mode, date_from, date_to, nm_id, brand, category, limit)


@router.get("/options")
async def fbs_options(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    _check_dates(date_from, date_to)
    svc = FbsReportService(db, company_id=company_id)
    return await svc.options(date_from, date_to)
