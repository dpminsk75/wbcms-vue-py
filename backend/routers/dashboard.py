"""FastAPI dashboard routes."""
import re
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.dashboard_service import DashboardService
from backend.services.finance_balance_service import FinanceBalanceService
from backend.services.finance_popup_service import FinancePopupService
from backend.services.kpi_service import KpiService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_range(date_from: str, date_to: str) -> None:
    if not (date_from and date_to and DATE_RE.match(date_from) and DATE_RE.match(date_to)):
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD")


@router.get("/shell")
async def shell(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    dateFrom: str = Query(default=None),
    dateTo: str = Query(default=None),
    company_id: int | None = Depends(get_current_company),
):
    df = date_from or dateFrom or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or dateTo or date.today().isoformat()
    return {"dateFrom": df, "dateTo": dt, "source": "py proto", "company_id": company_id}


@router.get("/top-metrics")
async def top_metrics(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = KpiService(db, company_id=company_id)
    chart = await svc.get_30d_chart()
    kpi = await svc.get_30d_kpi()
    return {"chart45Data": chart, "kpi45Data": kpi}


@router.get("/top-metrics-day")
async def top_metrics_day(
    date: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Попап дня из графика TopMetrics: тот же KPI-набор, что top-metrics, но за одну дату."""
    if not DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    svc = KpiService(db, company_id=company_id)
    return {"date": date, "kpi": await svc.get_day_kpi(date)}


@router.get("/finance-detail")
async def finance_detail(
    type: Literal["shf", "udr", "adv"] = Query(...),
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Попап Штрафы/Удержания/Реклама из «Финансовой аналитики» — порт DetailController."""
    _check_range(date_from, date_to)
    svc = FinancePopupService(db, company_id=company_id)
    return await svc.get_detail(type, date_from, date_to)


@router.get("/finance-storage")
async def finance_storage(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Попап Хранение из «Финансовой аналитики»: сумма по дате × складу."""
    _check_range(date_from, date_to)
    svc = FinancePopupService(db, company_id=company_id)
    return await svc.get_storage(date_from, date_to)


@router.get("/finance-acceptance")
async def finance_acceptance(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Попап Приёмка из «Финансовой аналитики»: строки detail_by_period с acceptance."""
    _check_range(date_from, date_to)
    svc = FinancePopupService(db, company_id=company_id)
    return await svc.get_acceptance(date_from, date_to)


@router.get("/finance-balance")
async def finance_balance(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Последний срез баланса ЛК WB (пишет cron finance_balance_sync.py, раз в 3 часа)."""
    return await FinanceBalanceService(db, company_id=company_id).latest()


@router.get("/today-stats")
async def today_stats(
    period: Literal["today", "yesterday", "week_to_date", "last_week", "month_to_date", "last_month"] = "today",
    tab: Literal["orders", "sales"] = "orders",
    trim_past: int = Query(default=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    table = "wb_order" if tab == "orders" else "wb_sales"
    sum_field = "price_with_disc" if tab == "orders" else "priceWithDisc"
    svc = DashboardService(db, company_id=company_id)
    data = await svc.build_period_stats(period, table, sum_field, trim_past=bool(trim_past))
    try:
        updated = await svc.get_last_order_time()
        data["updated_at"] = updated
    except Exception:
        data["updated_at"] = None
    return data


@router.get("/orders-summary")
async def orders_summary(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = DashboardService(db, company_id=company_id)
    return await svc.get_orders_summary()


@router.get("/adv")
async def adv(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    dateFrom: str = Query(default=None),
    dateTo: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = DashboardService(db, company_id=company_id)
    df = date_from or dateFrom or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or dateTo or date.today().isoformat()
    return await svc.get_adv(df, dt)


@router.get("/last-orders")
async def last_orders(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    dateFrom: str = Query(default=None),
    dateTo: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = DashboardService(db, company_id=company_id)
    df = date_from or dateFrom or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or dateTo or date.today().isoformat()
    return await svc.get_last_orders(df, dt)


@router.get("/last-sales")
async def last_sales(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    dateFrom: str = Query(default=None),
    dateTo: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = DashboardService(db, company_id=company_id)
    df = date_from or dateFrom or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or dateTo or date.today().isoformat()
    return await svc.get_last_sales(df, dt)


@router.get("/monthly-finance")
async def monthly_finance(
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = KpiService(db, company_id=company_id)
    if refresh:
        await svc.invalidate_monthly_cache()
    return await svc.get_monthly_profit()


@router.get("/new-cards")
async def new_cards(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
    title: str = Query(default=""),
    sort: str = Query(default="created_desc"),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    # Фронт шлёт camelCase (dashboardApi.newCards, прямые вызовы из фильтров) —
    # принимаем оба, иначе даты молча заменяются дефолтом (баг 2026-10-05).
    svc = DashboardService(db, company_id=company_id)
    return await svc.get_new_cards(date_from or dateFrom, date_to or dateTo,
                                   title, sort)
