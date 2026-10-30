"""Управление виртуальными складами FBS (/api/fbs-virtual) - порт WbFbsVirtualController.

Доступ: перм manageFbsStocks.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_manage_fbs_stocks
from backend.services.fbs_virtual_service import (
    QTY_FILTERS, FbsVirtualError, FbsVirtualService)

router = APIRouter(prefix="/api/fbs-virtual", tags=["fbs-virtual"])


def _svc(db: AsyncSession, company_id, user) -> FbsVirtualService:
    return FbsVirtualService(db, company_id=company_id, user_id=(user or {}).get("id"))


def _err(e: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


@router.get("/stocks")
async def stocks(
    q: str | None = Query(default=None),
    qty: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F1. Таблица остатков: центральный + виртуальный, фильтры, пагинация."""
    if qty not in QTY_FILTERS:
        raise HTTPException(status_code=400, detail=f"unknown qty filter: {qty}")
    svc = _svc(db, company_id, user)
    try:
        return await svc.stocks(q, qty, page, page_size)
    except FbsVirtualError as e:
        raise _err(e)


@router.get("/warehouses")
async def warehouses(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F2. Склады WB с флагами is_virtual / consider_orders."""
    svc = _svc(db, company_id, user)
    return {"rows": await svc.warehouses()}


@router.post("/warehouses/{wh_id}/toggle")
async def toggle_warehouse(
    wh_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F2. Переключить флаг склада WB (is_virtual / consider_orders)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.toggle(wh_id, str(payload.get("field") or ""))
    except FbsVirtualError as e:
        raise _err(e)


@router.post("/parse")
async def parse(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F3. Разбор Excel (фронт шлет строки) -> matched/skipped."""
    rows = payload.get("rows") or []
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=400, detail="rows is required")
    svc = _svc(db, company_id, user)
    return await svc.parse(rows)


@router.post("/save-central")
async def save_central(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F3. Записать остатки центрального склада (doc_type=fbs_central_adjust)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.save_central(payload.get("changes") or [])
    except FbsVirtualError as e:
        raise _err(e)


@router.post("/save-virtual")
async def save_virtual(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F3. Правка виртуальных остатков - TRANSFER (doc_type=fbs_virtual_adjust)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.save_virtual(payload.get("changes") or [])
    except FbsVirtualError as e:
        raise _err(e)


@router.post("/delete-virtual")
async def delete_virtual(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F4. Очистить позицию виртуальных остатков (возврат на центральный)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.delete_virtual(str(payload.get("sku") or ""))
    except FbsVirtualError as e:
        raise _err(e)


@router.post("/upload-all")
async def upload_all(
    payload: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F4. Выгрузить все остатки в виртуальные склады WB (test=1 - без запроса)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.upload_all(
            test=bool(payload.get("test", True)),
            wh_filter=payload.get("warehouse_id") or payload.get("wh"))
    except FbsVirtualError as e:
        raise _err(e)


@router.post("/upload-one")
async def upload_one(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F4. Выгрузить один SKU в виртуальные склады WB."""
    amount_raw = payload.get("amount")
    try:
        amount = float(amount_raw) if amount_raw not in (None, "") else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="amount должен быть числом")
    svc = _svc(db, company_id, user)
    try:
        return await svc.upload_one(
            str(payload.get("sku") or ""),
            amount=amount,
            test=bool(payload.get("test", True)),
            wh_filter=payload.get("warehouse_id") or payload.get("wh"))
    except FbsVirtualError as e:
        raise _err(e)


@router.get("/deduct-log")
async def deduct_log(
    limit: int = Query(default=200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """F4. Лог списаний FBS-заказов (из ledger, не из файлов)."""
    svc = _svc(db, company_id, user)
    return await svc.deduct_log(limit)
