"""Документы склада (/api/stock-docs) - порт WbDocController (Yii2).

Доступ: перм manageFbsStocks.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_manage_fbs_stocks
from backend.services.sku_resolver import SkuResolver
from backend.services.stock_doc_service import (
    TYPES, TYPE_LABELS, DocError, StockDocService)

router = APIRouter(prefix="/api/stock-docs", tags=["stock-docs"])


def _svc(db: AsyncSession, company_id, user) -> StockDocService:
    return StockDocService(db, company_id=company_id, user_id=(user or {}).get("id"))


@router.get("")
async def docs_list(
    type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Список документов компании."""
    if type and type not in TYPES:
        raise HTTPException(status_code=400, detail=f"unknown type: {type}")
    svc = _svc(db, company_id, user)
    return await svc.list(type, page, page_size)


@router.get("/meta")
async def docs_meta(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Склады для форм + справочник типов документов."""
    svc = _svc(db, company_id, user)
    return {
        "warehouses": await svc.warehouses(),
        "types": [{"value": t, "label": TYPE_LABELS[t]} for t in TYPES],
    }


@router.get("/search-product")
async def docs_search_product(
    term: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Поиск карточки по баркоду/артикулу/названию."""
    svc = _svc(db, company_id, user)
    return {"rows": await svc.search_product(term, limit)}


@router.get("/balance")
async def docs_balance(
    sku: str = Query(...),
    warehouse_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Текущий остаток по SKU на складе."""
    svc = _svc(db, company_id, user)
    return await svc.balance(sku, warehouse_id)


@router.get("/inventory-data")
async def docs_inventory_data(
    warehouse_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Список всех карточек компании с остатком по складу (для инвентаризации)."""
    svc = _svc(db, company_id, user)
    return {"rows": await svc.inventory_data(warehouse_id)}


@router.post("/parse")
async def docs_parse(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Разбор Excel (фронт шлет строки): {rows: [[...], ...]} -> matched/skipped."""
    rows = payload.get("rows") or []
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=400, detail="rows is required")
    resolver = SkuResolver(db, company_id)
    matched, skipped = await resolver.parse_rows(rows)
    return {
        "success": True,
        "matched": [{"sku": m.sku, "nm_id": m.nm_id, "chrt_id": m.chrt_id, "qty": m.qty}
                    for m in matched],
        "skipped": skipped,
    }


@router.get("/{doc_id}")
async def docs_get(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Документ с составом."""
    svc = _svc(db, company_id, user)
    doc = await svc.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc


@router.post("")
async def docs_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Создать документ (черновик)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.create(payload)
    except DocError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{doc_id}")
async def docs_update(
    doc_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Изменить документ (только черновик/отмененный)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.update(doc_id, payload)
    except DocError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{doc_id}")
async def docs_delete(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Удалить черновик."""
    svc = _svc(db, company_id, user)
    try:
        await svc.delete(doc_id)
    except DocError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "id": doc_id}


@router.post("/{doc_id}/post")
async def docs_post(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Провести документ (остатки изменятся)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.post(doc_id)
    except DocError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{doc_id}/cancel")
async def docs_cancel(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_fbs_stocks),
):
    """Отменить проведенный документ (сторно)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.cancel(doc_id)
    except DocError as e:
        raise HTTPException(status_code=400, detail=str(e))
