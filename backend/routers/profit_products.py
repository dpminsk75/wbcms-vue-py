"""Отчёт «Маржа по продуктам» (/wb-profit/products).

Роутеры:
  * GET /api/wb-profit/products            - свод по линейкам (product) за период;
  * GET /api/wb-profit/products/{id}/cards - состав линейки (карточки, q/p, вклад в себ-ть).

Существующую маржу по карточкам (profit.py / profit_index_service) НЕ трогаем.
"""
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.profit_products_service import (
    MAX_DAYS, ProfitProductsService, validate_sort)

router = APIRouter(prefix="/api/wb-profit", tags=["profit"])

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_range(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    if not (date_from and date_to):
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD")
    if not (DATE_RE.match(date_from) and DATE_RE.match(date_to)):
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD")
    try:
        d1 = date.fromisoformat(date_from)
        d2 = date.fromisoformat(date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad date")
    if d2 < d1:
        raise HTTPException(status_code=400, detail="date_to < date_from")
    if (d2 - d1).days > MAX_DAYS:
        raise HTTPException(status_code=400, detail=f"period too long (max {MAX_DAYS} days)")
    return date_from, date_to


@router.get("/products")
async def profit_products(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort_by: str = Query(default="amount"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Маржа по линейкам за период.

    Выручка/статьи = суммы по карточкам линейки без весов; себестоимость линейки:
    product.cost (ручная) либо производная от состава (q * p_norm).
    """
    d1, d2 = _check_range(date_from, date_to)
    svc = ProfitProductsService(db, company_id=company_id)
    data = await svc.report(date_from=d1, date_to=d2, sort_by=validate_sort(sort_by), limit=limit)
    return data


@router.get("/products/{product_id}/cards")
async def profit_product_cards(
    product_id: int,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Состав линейки: карточки, q/p (нормированные) и вклад каждой в себестоимость."""
    d1, d2 = _check_range(date_from, date_to)
    svc = ProfitProductsService(db, company_id=company_id)
    data = await svc.product_cards(product_id, date_from=d1, date_to=d2)
    if not data.get("rows"):
        raise HTTPException(status_code=404, detail="product not found or has no cards")
    return data
