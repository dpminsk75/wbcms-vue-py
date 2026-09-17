"""Сырые заказы — порт WbOrderController::actionIndex/View (образец: routers/cost.py)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.wb_orders_service import WbOrdersService

router = APIRouter(prefix="/api/wb-orders", tags=["wb-orders"])


@router.get("")
async def wb_orders_list(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    nm_id: str | None = Query(default=None),
    supplier_article: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    card_title: str | None = Query(default=None),
    g_number: str | None = Query(default=None),
    is_cancel: int | None = Query(default=None, ge=0, le=1),
    sort: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = WbOrdersService(db, company_id=company_id)
    return await svc.list(date_from, date_to, nm_id, supplier_article, brand,
                          category, card_title, g_number, is_cancel,
                          sort, page, page_size)


@router.get("/{order_id}")
async def wb_orders_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = WbOrdersService(db, company_id=company_id)
    row = await svc.get(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return row
