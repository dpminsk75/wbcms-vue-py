"""Справочник линеек (В8) — /api/products, /api/product-types, /api/brands.

View: любой вошедший (в PHP было roles ['@']); мутации: admin —
коммитят глобальные справочники и состав линеек.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_admin
from backend.services.product_catalog_service import ProductCatalogService


def _svc(db: AsyncSession, company_id) -> ProductCatalogService:
    return ProductCatalogService(db, company_id=company_id)


router = APIRouter(tags=["product-catalog"])


# --- линейки ----------------------------------------------------------------
@router.get("/api/products")
async def products_list(
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
):
    return await _svc(db, company_id).list_products(q)


@router.post("/api/products")
async def products_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).product_create(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/products/{product_id}")
async def products_update(
    product_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).product_update(product_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/products/{product_id}")
async def products_delete(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    return await _svc(db, company_id).product_delete(product_id)


# --- состав линейки ---------------------------------------------------
@router.get("/api/products/{product_id}/links")
async def products_links(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
):
    try:
        return await _svc(db, company_id).product_links(product_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/products/{product_id}/links")
async def products_links_save(
    product_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).product_links_save(product_id, payload.get("items") or [])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- справочники: типы и бренды -------------------------------------------------
@router.get("/api/product-types")
async def product_types(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
):
    return await _svc(db, company_id).product_types()


@router.post("/api/product-types")
async def product_types_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).product_type_save(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/product-types/{item_id}")
async def product_types_update(
    item_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).product_type_save(payload, item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/product-types/{item_id}")
async def product_types_delete(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).product_type_delete(item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/brands")
async def brands(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
):
    return await _svc(db, company_id).brands()


@router.post("/api/brands")
async def brands_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).brand_save(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/brands/{item_id}")
async def brands_update(
    item_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).brand_save(payload, item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/brands/{item_id}")
async def brands_delete(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _a: dict = Depends(require_admin),
):
    try:
        return await _svc(db, company_id).brand_delete(item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
