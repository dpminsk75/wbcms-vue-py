"""Справочник складов (/api/warehouses) - порт OurWarehouseController (Yii2).

Доступ: перм manageFbsStocks (роли fbsManager/admin в Yii2).
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, require_manage_fbs_stocks
from backend.services.warehouse_service import WarehouseService

router = APIRouter(prefix="/api/warehouses", tags=["warehouses"])


@router.get("")
async def warehouses_list(
    active_only: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    _user: dict = Depends(require_manage_fbs_stocks),
):
    """Список своих складов."""
    svc = WarehouseService(db, company_id=company_id)
    rows = await svc.list(active_only=bool(active_only))
    return {
        "rows": rows,
        "central_id": await svc.central_id(),
        "fbs_id": await svc.fbs_id(),
        "company_id": company_id,
    }


@router.post("")
async def warehouses_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    _user: dict = Depends(require_manage_fbs_stocks),
):
    """Создать склад."""
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if company_id is None:
        raise HTTPException(status_code=400, detail="company_id is required")
    svc = WarehouseService(db, company_id=company_id)
    try:
        row = await svc.create(
            name=name,
            code=payload.get("code"),
            is_central=payload.get("is_central", 0),
            is_fbs=payload.get("is_fbs", 0),
            consider_orders=payload.get("consider_orders", 0),
            is_active=payload.get("is_active", 1),
            address=payload.get("address"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return row


@router.put("/{wh_id}")
async def warehouses_update(
    wh_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    _user: dict = Depends(require_manage_fbs_stocks),
):
    """Изменить склад."""
    svc = WarehouseService(db, company_id=company_id)
    row = await svc.get(wh_id)
    if not row:
        raise HTTPException(status_code=404, detail="warehouse not found")
    if company_id is not None and int(row["company_id"] or 0) != int(company_id):
        raise HTTPException(status_code=404, detail="warehouse not found")
    return await svc.update(wh_id, payload)


@router.post("/{wh_id}/toggle")
async def warehouses_toggle(
    wh_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    _user: dict = Depends(require_manage_fbs_stocks),
):
    """Переключить флаг склада (is_central / is_fbs / consider_orders / is_active)."""
    field = str(payload.get("field") or "").strip()
    svc = WarehouseService(db, company_id=company_id)
    row = await svc.get(wh_id)
    if not row:
        raise HTTPException(status_code=404, detail="warehouse not found")
    if company_id is not None and int(row["company_id"] or 0) != int(company_id):
        raise HTTPException(status_code=404, detail="warehouse not found")
    try:
        return await svc.toggle(wh_id, field)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{wh_id}")
async def warehouses_delete(
    wh_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    _user: dict = Depends(require_manage_fbs_stocks),
):
    """Удалить склад (если по нему нет остатков/движений/документов)."""
    svc = WarehouseService(db, company_id=company_id)
    row = await svc.get(wh_id)
    if not row:
        raise HTTPException(status_code=404, detail="warehouse not found")
    if company_id is not None and int(row["company_id"] or 0) != int(company_id):
        raise HTTPException(status_code=404, detail="warehouse not found")
    cnt = await svc.balances_count(wh_id)
    if cnt["balances"] or cnt["ledger"] or cnt["docs"]:
        raise HTTPException(
            status_code=400,
            detail=("склад используется: остатков {balances}, движений {ledger}, "
                    "документов {docs} - сначала разберитесь с ними").format(**cnt))
    await svc.delete(wh_id)
    return {"ok": True, "id": wh_id}
