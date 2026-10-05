"""«FBS Заказы» (/fbs-orders): экономика + динамика + очередь сборки."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.fbs_orders_service import FbsOrdersService

router = APIRouter(prefix="/api/fbs/orders", tags=["fbs-orders"])


def _svc(db, company_id):
    return FbsOrdersService(db, company_id=company_id)


@router.get("/warehouses")
async def fbs_orders_warehouses(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    return await _svc(db, company_id).warehouses()


@router.get("/economy")
async def fbs_orders_economy(
    date_from: str = Query(...),
    date_to: str = Query(...),
    warehouse_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    return await _svc(db, company_id).economy(
        date_from, date_to, warehouse_id, brand, category)


@router.get("/dynamics")
async def fbs_orders_dynamics(
    date_from: str = Query(...),
    date_to: str = Query(...),
    warehouse_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    return await _svc(db, company_id).dynamics(
        date_from, date_to, warehouse_id, brand, category)


@router.get("/assembly")
async def fbs_orders_assembly(
    date_from: str = Query(...),
    date_to: str = Query(...),
    warehouse_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    return await _svc(db, company_id).assembly(
        date_from, date_to, warehouse_id, brand, category)
