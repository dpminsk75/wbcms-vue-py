"""Смоленск — снапшоты остатков и движения (/api/production/smolensk).

Доступ: перм manageFbsStocks (как складской контур). Порт
StockSnapshotController / StockMovementController.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_manage_fbs_stocks
from backend.services.smolensk_stock_service import SmolenskStockService

router = APIRouter(prefix="/api/production/smolensk", tags=["smolensk"])


def _svc(db: AsyncSession, company_id, user: dict) -> SmolenskStockService:
    return SmolenskStockService(db, company_id=company_id, user_id=user.get("id"))


# --- снапшоты -------------------------------------------------------------
@router.get("/snapshots")
async def snapshots_list(
    period: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    return await _svc(db, company_id, user).snapshots(period, q, page, page_size)


@router.post("/snapshots")
async def snapshots_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    try:
        return await _svc(db, company_id, user).snapshot_create(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/snapshots/{snap_id}")
async def snapshots_update(
    snap_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    try:
        return await _svc(db, company_id, user).snapshot_update(snap_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/snapshots/{snap_id}")
async def snapshots_delete(
    snap_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    return await _svc(db, company_id, user).snapshot_delete(snap_id)


# --- наличия из Excel -------------------------------------------------------
@router.post("/snapshots/parse-availability")
async def parse_availability(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Разбор xlsx в соответствия (без записи) — порт actionParseAvailability."""
    rows, err = SmolenskStockService.parse_grid(payload.get("grid") or [])
    if err:
        raise HTTPException(status_code=400, detail=err)
    return await _svc(db, company_id, user).parse_availability(rows)


@router.post("/snapshots/save-availability")
async def save_availability(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Upsert снапшотов по собранным из Excel строкам."""
    return await _svc(db, company_id, user).save_availability(payload.get("rows") or [])


# --- движения -----------------------------------------------------------------
@router.get("/movements")
async def movements_list(
    type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    nm_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    return await _svc(db, company_id, user).movements(type, date_from, date_to, nm_id, q, page, page_size)


@router.post("/movements")
async def movements_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    try:
        return await _svc(db, company_id, user).movement_create(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/movements/{mov_id}")
async def movements_update(
    mov_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    try:
        return await _svc(db, company_id, user).movement_update(mov_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/movements/{mov_id}")
async def movements_delete(
    mov_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    return await _svc(db, company_id, user).movement_delete(mov_id)


@router.post("/movements/import")
async def movements_import(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Импорт движений из Excel: 2 режима — «приход» и «сверка»."""
    rows, err = SmolenskStockService.parse_grid(payload.get("grid") or [])
    if err:
        raise HTTPException(status_code=400, detail=err)
    try:
        return await _svc(db, company_id, user).import_movements(
            rows, payload.get("type") or "production_in", payload.get("movement_date"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- сверка и баланс -------------------------------------------------------------
@router.post("/reconcile")
async def reconcile(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    try:
        return await _svc(db, company_id, user).reconcile(
            int(payload.get("nm_id") or 0), payload.get("period_date"),
            payload.get("actual_qty") if payload.get("actual_qty") not in (None, "") else None)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reconcile-bulk")
async def reconcile_bulk(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    return await _svc(db, company_id, user).reconcile_bulk(payload.get("changes") or [])


@router.get("/balance")
async def balance(
    nm_id: int = Query(..., ge=1),
    on_date: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Расчётный баланс Смоленска на дату (порт StockBalanceService)."""
    return await _svc(db, company_id, user).balance(nm_id, on_date)
