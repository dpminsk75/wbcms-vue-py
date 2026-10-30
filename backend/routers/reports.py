"""Сравнительные отчёты (год к году) — /api/reports/*."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.year_compare_service import MAX_YEARS, YearCompareService

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _parse_years(raw: str | None) -> list[int]:
    """'2024,2025,2026' → [2024, 2025, 2026]. Пустая строка — пустой список."""
    if not raw:
        return []
    out: list[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise HTTPException(status_code=400, detail=f"bad year: {part}")
        y = int(part)
        if not (2000 <= y <= 2100):
            raise HTTPException(status_code=400, detail=f"bad year: {part}")
        out.append(y)
    return sorted(set(out))[-MAX_YEARS:]


@router.get("/year-compare")
async def year_compare(
    tab: str = Query(default="orders"),
    years: str | None = Query(default=None),
    nm_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Сравнение заказов/продаж по годам (порты Yii2 AggOrders/AggSalesReportController).

    tab=orders — куб agg_orders_daily_sku (по дате заказа),
    tab=sales  — куб agg_sales_daily_sku (по дате продажи).
    Фильтр nm_id (карточка) влияет на все таблицы и графики.
    """
    if tab not in ("orders", "sales"):
        raise HTTPException(status_code=400, detail="tab must be 'orders' or 'sales'")
    svc = YearCompareService(db, company_id=company_id)
    return await svc.compare(tab=tab, years=_parse_years(years), nm_id=nm_id)
