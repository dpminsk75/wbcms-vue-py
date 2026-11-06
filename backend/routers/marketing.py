"""Р СѓС‡РЅРѕР№ РјР°СЂРєРµС‚РёРЅРі: РїР»РѕС‰Р°РґРєРё + РґРѕРєСѓРјРµРЅС‚С‹/СЃС‚СЂРѕРєРё СЂР°СЃС…РѕРґРѕРІ + Excel (РѕРґРёРЅ Р»РёСЃС‚).

РњР°СЂС€СЂСѓС‚С‹:
  GET    /api/marketing/channels            вЂ” СЃРїРёСЃРѕРє РїР»РѕС‰Р°РґРѕРє.
  POST   /api/marketing/channels            вЂ” СЃРѕР·РґР°С‚СЊ РїР»РѕС‰Р°РґРєСѓ.
  PUT    /api/marketing/channels/{id}       вЂ” РёР·РјРµРЅРёС‚СЊ РїР»РѕС‰Р°РґРєСѓ.
  DELETE /api/marketing/channels/{id}       вЂ” СѓРґР°Р»РёС‚СЊ/Р°СЂС…РёРІРёСЂРѕРІР°С‚СЊ РїР»РѕС‰Р°РґРєСѓ.
  GET    /api/marketing/documents           вЂ” РґРѕРєСѓРјРµРЅС‚С‹ СЂР°СЃС…РѕРґРѕРІ.
  GET    /api/marketing/documents/{id}      вЂ” РґРѕРєСѓРјРµРЅС‚ СЃ РїРѕР·РёС†РёСЏРјРё.
  POST   /api/marketing/documents           вЂ” СЃРѕР·РґР°С‚СЊ РґРѕРєСѓРјРµРЅС‚ СЃРѕ СЃС‚СЂРѕРєР°РјРё.
  PUT    /api/marketing/documents/{id}      вЂ” РёР·РјРµРЅРёС‚СЊ РґРѕРєСѓРјРµРЅС‚/РїРѕР·РёС†РёРё.
  DELETE /api/marketing/documents/{id}      вЂ” СѓРґР°Р»РёС‚СЊ РґРѕРєСѓРјРµРЅС‚.
  POST   /api/marketing/import/preview      вЂ” СЂР°Р·Р±РѕСЂ Excel (dry-run).
  POST   /api/marketing/import/save         вЂ” СЃРѕС…СЂР°РЅРёС‚СЊ СЂР°Р·РѕР±СЂР°РЅРЅС‹Р№ С„Р°Р№Р».
  GET    /api/marketing/export              вЂ” СЃС‚СЂРѕРєРё РґР»СЏ РІС‹РіСЂСѓР·РєРё РІ Excel.

РџСЂР°РІР°: С‡С‚РµРЅРёРµ вЂ” viewFinance, РёР·РјРµРЅРµРЅРёРµ вЂ” manageSettings.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_manage_settings, require_perm
from backend.services.marketing_service import (
    CHANNEL_TYPE_LABELS,
    CHANNEL_TYPES,
    DOC_TYPE_LABELS,
    DOC_TYPES,
    XLSX_COLUMNS,
    MarketingError,
    MarketingService,
)

router = APIRouter(prefix="/api/marketing", tags=["marketing"])


def _svc(db: AsyncSession, company_id, user) -> MarketingService:
    return MarketingService(db, company_id=company_id, user_id=(user or {}).get("id"))


@router.get("/meta")
async def marketing_meta(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    return {
        "channel_types": [{"value": t, "label": CHANNEL_TYPE_LABELS[t]} for t in CHANNEL_TYPES],
        "doc_types": [{"value": t, "label": DOC_TYPE_LABELS[t]} for t in DOC_TYPES],
        "xlsx_columns": XLSX_COLUMNS,
    }


# ------------------------------------------------------------- РїР»РѕС‰Р°РґРєРё
@router.get("/channels")
async def channels_list(
    q: str = Query(default=""),
    include_archived: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    svc = _svc(db, company_id, user)
    try:
        return {"rows": await svc.list_channels(q, bool(include_archived))}
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/channels")
async def channels_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.create_channel(payload)
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/channels/{channel_id}")
async def channels_update(
    channel_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.update_channel(channel_id, payload)
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/channels/{channel_id}")
async def channels_delete(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.delete_channel(channel_id)
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------- РґРѕРєСѓРјРµРЅС‚С‹
@router.get("/cards/search")
async def cards_search(
    q: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    """РџРѕРёСЃРє РєР°СЂС‚РѕС‡РµРє РєРѕРјРїР°РЅРёРё вЂ” РІС‹Р±РѕСЂ SKU РІ РїРѕР·РёС†РёРё СЂР°СЃС…РѕРґР°."""
    svc = _svc(db, company_id, user)
    try:
        return {"rows": await svc.search_cards(q, limit)}
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents")
async def documents_list(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    channel_id: int | None = Query(default=None),
    q: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    svc = _svc(db, company_id, user)
    try:
        return {"rows": await svc.list_documents(date_from, date_to, channel_id, q, limit)}
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents/{document_id}")
async def documents_get(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.get_document(document_id)
    except MarketingError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/documents")
async def documents_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.create_document(payload)
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/documents/{document_id}")
async def documents_update(
    document_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.update_document(document_id, payload)
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/documents/{document_id}")
async def documents_delete(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.delete_document(document_id)
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------- Excel
@router.post("/import/preview")
async def import_preview(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    """Dry-run: СЂР°Р·Р±РѕСЂ Р»РёСЃС‚Р°, РЅРёС‡РµРіРѕ РЅРµ СЃРѕС…СЂР°РЅСЏРµРј."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.import_preview(payload.get("rows") or [])
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/save")
async def import_save(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.import_save(payload.get("documents") or [])
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export")
async def export_rows(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    channel_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    svc = _svc(db, company_id, user)
    try:
        return {"rows": await svc.export_rows(date_from, date_to, channel_id)}
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))
