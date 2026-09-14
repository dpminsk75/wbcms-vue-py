"""
FastAPI — замена SiteController.php (905 строк)
1 роут = 1 слот index_dashboard.php:58 -> /api/dashboard/*
"""
from fastapi import APIRouter, Depends, Query
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.dashboard_service import DashboardService
from ..services.kpi_service import KpiService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Depends — замена Yii::$app->companyManager
async def get_current_company(company_id: int = Query(...)) -> int:
    # TODO: JWT + проверка is_active, как SiteController.php:878
    return company_id

@router.get("/shell")
async def shell(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    company_id: int = Depends(get_current_company),
):
    """Замена renderDashboard:177 — только даты, как index_dashboard.php:17 shell"""
    from datetime import date, timedelta
    df = date_from or (date.today() - timedelta(days=3)).isoformat()
    dt = date_to or date.today().isoformat()
    return {"dateFrom": df, "dateTo": dt}

@router.get("/top-metrics")
async def top_metrics(
    db: AsyncSession = Depends(get_db),
    company_id: int = Depends(get_current_company),
):
    """Замена actionDashboardTopMetrics:189 — agg_daily_summary 30д"""
    svc = KpiService(db)
    chart = await svc.get_30d_chart()  # was chart45Query:195
    kpi = await svc.get_30d_kpi()      # was kpi45Query:213 + count orders:232
    return {"chart45Data": chart, "kpi45Data": kpi}

@router.get("/adv")
async def adv(
    date_from: str, date_to: str,
    db: AsyncSession = Depends(get_db),
    company_id: int = Depends(get_current_company),
):
    """Замена actionDashboardAdv:238 — wb_campaign 4 JOIN"""
    svc = DashboardService(db)
    return await svc.get_adv(date_from, date_to)

@router.get("/orders-summary")
async def orders_summary(
    db: AsyncSession = Depends(get_db),
    company_id: int = Depends(get_current_company),
):
    """Замена actionDashboardOrdersSummary:279 — 4 UNION по wb_order"""
    svc = DashboardService(db)
    return await svc.get_orders_summary()

@router.get("/last-orders")
async def last_orders(
    date_from: str, date_to: str,
    db: AsyncSession = Depends(get_db),
    company_id: int = Depends(get_current_company),
):
    """Замена actionDashboardLastOrders:324 — итоги по всем заказам, таблица ТОП-20"""
    svc = DashboardService(db)
    return await svc.get_last_orders(date_from, date_to, 500)

@router.get("/last-sales")
async def last_sales(
    date_from: str, date_to: str,
    db: AsyncSession = Depends(get_db),
    company_id: int = Depends(get_current_company),
):
    """Замена actionDashboardLastSales:363 — итоги по всем продажам, таблица ТОП-20"""
    svc = DashboardService(db)
    return await svc.get_last_sales(date_from, date_to, 500)

@router.get("/monthly-finance")
async def monthly_finance(
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    company_id: int = Depends(get_current_company),
):
    """Замена actionDashboardMonthlyFinance:406 — WbProfitService"""
    svc = KpiService(db)
    if refresh:
        await svc.invalidate_monthly_cache()
    return await svc.get_monthly_profit()

@router.get("/today-stats")
async def today_stats(
    period: Literal["today","yesterday","week_to_date","last_week","month_to_date","last_month"] = "today",
    tab: Literal["orders","sales"] = "orders",
    db: AsyncSession = Depends(get_db),
    company_id: int = Depends(get_current_company),
):
    """
    Замена actionDashboardTodayWidget:416 + actionTodayStatsData:435
    Возвращает единую структуру buildPeriodStats:469
    { granularity, categories, seriesMeta, series, totals, axisCaption? }
    """
    svc = DashboardService(db)
    table = "wb_order" if tab == "orders" else "wb_sales"
    sum_field = "price_with_disc" if tab == "orders" else "priceWithDisc"
    return await svc.build_period_stats(period, table, sum_field)

@router.get("/new-cards")
async def new_cards(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    title: str = Query(default=""),
    sort: str = Query(default="created_desc"),
    db: AsyncSession = Depends(get_db),
    company_id: int = Depends(get_current_company),
):
    """Замена actionNewCards:792 + _new_cards.php:10 — новые карточки 14д"""
    svc = DashboardService(db)
    return await svc.get_new_cards(date_from, date_to, title, sort)
