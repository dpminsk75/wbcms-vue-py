"""Продажи на карте (/geo/sales-map): точки + таблица одним GROUP BY."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.geo_sales_service import GeoSalesService

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.get("/sales-map")
async def geo_sales_map(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None),
    q: str | None = Query(default=None, description="маска: часть nm_id/vendorCode/названия"),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None, description="предмет (wbcards.subjectName)"),
    metric: str = Query(default="qty"),
    level: str = Query(default="region"),
    bbox: str | None = Query(default=None, description="s,w,n,e"),
    world: bool = Query(default=False),
    parent_country: str | None = Query(default=None),
    parent_okrug: str | None = Query(default=None),
    parent_region: str | None = Query(default=None),
    parent_city: str | None = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = GeoSalesService(db, company_id=company_id)
    return await svc.sales_map(nm_id=nm_id, q=q, brand=brand, category=category,
                               date_from=date_from, date_to=date_to, metric=metric,
                               level=level, bbox=bbox, world=world,
                               parent_country=parent_country, parent_okrug=parent_okrug,
                               parent_region=parent_region, parent_city=parent_city,
                               limit=limit)


@router.get("/options")
async def geo_options(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Бренды + предметы для селектов универсального фильтра."""
    svc = GeoSalesService(db, company_id=company_id)
    return await svc.options()
