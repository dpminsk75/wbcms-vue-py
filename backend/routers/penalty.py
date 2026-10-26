"""Отчёт «Штрафы и потери на доставке» — порт WbPenaltyController (Yii2).

Раньше это была страница без ссылки в меню; сейчас — отдельный отчёт
(/wb-penalty/logistics + /wb-penalty/detail) и попап-расшифровка «Логистики».

Данные — срез detail_by_period по операциям доставки
(«Логистика» + «Доставка», см. backend/services/wb_ops.py).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.penalty_service import PenaltyService, reason_bucket

router = APIRouter(prefix="/api/penalty", tags=["penalty"])


@router.get("/logistics")
async def penalty_logistics(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None, ge=1),
    office_name: str | None = Query(default=None),
    bonus_type_name: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Сводный отчёт: по причинам, по товарам + штрафы WB."""
    svc = PenaltyService(db, company_id=company_id)
    period = await svc.summary_by_period(date_from, date_to, office_name, bonus_type_name, nm_id)
    products = await svc.product_summary(date_from, date_to, page, page_size,
                                         office_name, bonus_type_name, nm_id)
    penalties = await svc.wb_penalties(date_from, date_to)
    total_sum = round(sum(float(r["total_sum"] or 0) for r in period), 2)
    buckets = {"to_client_cancel": 0.0, "from_client_cancel": 0.0,
               "from_client_return": 0.0, "defect": 0.0, "other": 0.0}
    for r in period:
        b = reason_bucket(r.get("bonus_type_name") or "")
        buckets[b] = round(buckets[b] + float(r.get("total_sum") or 0), 2)
    return {
        "date_from": date_from,
        "date_to": date_to,
        "period": period,
        "products": products,
        "penalties": penalties,
        "totals": {
            "total_sum": total_sum,
            "total_count": sum(int(r["items_count"] or 0) for r in period),
            "to_client_cancel_sum": buckets["to_client_cancel"],
            "from_client_cancel_sum": buckets["from_client_cancel"],
            "from_client_return_sum": buckets["from_client_return"],
            "defect_sum": buckets["defect"],
            "other_sum": buckets["other"],
            "penalty_sum": penalties["total_sum"],
        },
    }


@router.get("/detail")
async def penalty_detail(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None, ge=1),
    office_name: str | None = Query(default=None),
    bonus_type_name: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Построчная детализация потерь на доставке."""
    svc = PenaltyService(db, company_id=company_id)
    return await svc.detail(date_from, date_to, nm_id, office_name,
                            bonus_type_name, page, page_size)


@router.get("/filter-lists")
async def penalty_filter_lists(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Склады и причины для фильтров + диагностика doc_type_name."""
    svc = PenaltyService(db, company_id=company_id)
    return await svc.filter_lists(date_from, date_to)


@router.get("/popup")
async def penalty_popup(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Попап-расшифровка «Логистики»: по причинам + по товарам за период."""
    svc = PenaltyService(db, company_id=company_id)
    return await svc.popup(date_from, date_to, nm_id)
