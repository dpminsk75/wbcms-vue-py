"""«FBS Отмены» (/fbs-cancels): сводка + разрезы отмен (только статусы FBS)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.fbs_cancels_service import FbsCancelsService

router = APIRouter(prefix="/api/fbs/cancels", tags=["fbs-cancels"])


def _svc(db, company_id):
    return FbsCancelsService(db, company_id=company_id)


@router.get("/summary")
async def fbs_cancels_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    return await _svc(db, company_id).summary(
        date_from, date_to, nm_id, brand, category)


@router.get("/orders")
async def fbs_cancels_orders(
    bucket: str = Query(default="all",
                         pattern="^(all|seller_cancel|buyer_cancel|declined)$"),
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    warehouse_id: int | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    return await _svc(db, company_id).orders(
        bucket, date_from, date_to, nm_id, brand, category, warehouse_id, limit)


@router.get("/by-warehouse")
async def fbs_cancels_by_warehouse(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    return await _svc(db, company_id).by_warehouse(
        date_from, date_to, nm_id, brand, category)
