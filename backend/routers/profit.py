"""Расшифровка колонок маржи + маржинальный учёт (/wb-profit).

Роутеры:
  * /api/profit/breakdown        — «По дням» + «Детализация» по любой колонке затрат;
  * /api/wb-profit/sku-rank      — «Топ 20» / «Худшие 20» товаров (порт Yii2 getSkuProvider).
"""
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.margin_breakdown_service import (
    MAX_DAYS, TITLES, MarginBreakdownService)
from backend.services.profit_index_service import ProfitIndexService

profit_router = APIRouter(prefix="/api/profit", tags=["profit"])
wb_profit_router = APIRouter(prefix="/api/wb-profit", tags=["profit"])

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BASES = ("month", "product")


def _check_range(date_from: str, date_to: str) -> None:
    if not (date_from and date_to and DATE_RE.match(date_from) and DATE_RE.match(date_to)):
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


@profit_router.get("/breakdown")
async def breakdown(
    kind: str = Query(...),
    basis: str = Query(default="product"),
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None, ge=1),
    detail: int = Query(default=1),
    campaign_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Расшифровка колонки затрат: вкладка «По дням» (всегда) + «Детализация» (detail=1).

    campaign_id — фильтр по рекламной кампании (только kind=adv).
    Фильтр по company_id — штатный (deps.get_current_company читает query-параметр).
    """
    if kind not in TITLES:
        raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")
    if basis not in BASES:
        raise HTTPException(status_code=400, detail=f"unknown basis: {basis}")
    _check_range(date_from, date_to)

    svc = MarginBreakdownService(db, company_id=company_id)
    tabs = []
    try:
        tabs = await svc.build_tabs(kind, basis, date_from, date_to, nm_id,
                                    detail=bool(detail), campaign_id=campaign_id)
    except Exception:
        # Детализация — дополнение: её отсутствие не должно ломать разбивку по дням.
        tabs = await svc.by_day(kind, basis, date_from, date_to, nm_id)
    return {
        "kind": kind,
        "basis": basis,
        "title": TITLES[kind],
        "date_from": date_from,
        "date_to": date_to,
        "nm_id": nm_id,
        "campaign_id": campaign_id,
        "tabs": tabs,
    }


@wb_profit_router.get("/sku-rank")
async def wb_profit_sku_rank(
    order: str = Query(default="desc"),
    days: int = Query(default=60),
    limit: int = Query(default=20),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """«Топ 20» / «Худшие 20» товаров за последние N дней (порт Yii2 getSkuProvider)."""
    if date_from or date_to:
        _check_range(date_from or date.today().isoformat(), date_to or date.today().isoformat())
    svc = ProfitIndexService(db, company_id=company_id)
    return await svc.sku_rank(order=order, days=days, limit=limit,
                              date_from=date_from, date_to=date_to)
