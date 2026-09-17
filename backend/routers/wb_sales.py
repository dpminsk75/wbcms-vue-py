"""Сырые продажи — порт WbSalesController::actionIndex/View (образец: routers/cost.py)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.wb_sales_service import WbSalesService

router = APIRouter(prefix="/api/wb-sales", tags=["wb-sales"])


@router.get("")
async def wb_sales_list(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    nm_id: int | None = Query(default=None, ge=1),
    income_id: int | None = Query(default=None),
    is_supply: int | None = Query(default=None, ge=0, le=1),
    is_realization: int | None = Query(default=None, ge=0, le=1),
    total_price: float | None = Query(default=None),
    finished_price: float | None = Query(default=None),
    sale_id: str | None = Query(default=None),
    srid: str | None = Query(default=None),
    number: str | None = Query(default=None),
    supplier_article: str | None = Query(default=None),
    barcode: str | None = Query(default=None),
    warehouse_name: str | None = Query(default=None),
    warehouse_type: str | None = Query(default=None),
    country_name: str | None = Query(default=None),
    oblast_name: str | None = Query(default=None),
    region_name: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    category: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    card_title: str | None = Query(default=None),
    geo: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = WbSalesService(db, company_id=company_id)
    return await svc.list(date_from, date_to, nm_id, income_id, is_supply,
                          is_realization, total_price, finished_price, sale_id,
                          srid, number, supplier_article, barcode,
                          warehouse_name, warehouse_type, country_name,
                          oblast_name, region_name, subject, category, brand,
                          card_title, geo, sort, page, page_size)


@router.get("/{sale_id}")
async def wb_sales_detail(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = WbSalesService(db, company_id=company_id)
    row = await svc.get(sale_id)
    if not row:
        raise HTTPException(status_code=404, detail="Продажа не найдена")
    return row
