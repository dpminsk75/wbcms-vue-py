"""FastAPI dashboard routes."""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.dashboard_service import DashboardService
from backend.services.kpi_service import KpiService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/shell")
async def shell(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    company_id: int | None = Depends(get_current_company),
):
    df = date_from or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or date.today().isoformat()
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


@router.get("/today-stats")
async def today_stats(
    period: Literal["today", "yesterday", "week_to_date", "last_week", "month_to_date", "last_month"] = "today",
    tab: Literal["orders", "sales"] = "orders",
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    table = "wb_order" if tab == "orders" else "wb_sales"
    sum_field = "price_with_disc" if tab == "orders" else "priceWithDisc"
    svc = DashboardService(db, company_id=company_id)
    data = await svc.build_period_stats(period, table, sum_field)
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
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = DashboardService(db, company_id=company_id)
    df = date_from or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or date.today().isoformat()
    return await svc.get_adv(df, dt)


@router.get("/last-orders")
async def last_orders(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = DashboardService(db, company_id=company_id)
    df = date_from or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or date.today().isoformat()
    return await svc.get_last_orders(df, dt)


@router.get("/last-sales")
async def last_sales(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = DashboardService(db, company_id=company_id)
    df = date_from or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or date.today().isoformat()
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
    title: str = Query(default=""),
    sort: str = Query(default="created_desc"),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = DashboardService(db, company_id=company_id)
    return await svc.get_new_cards(date_from, date_to, title, sort)
