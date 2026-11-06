"""Ручной маркетинг: площадки + документы/строки расходов + Excel (один лист).

Маршруты:
  GET    /api/marketing/channels            — список площадок.
  POST   /api/marketing/channels            — создать площадку.
  PUT    /api/marketing/channels/{id}       — изменить площадку.
  DELETE /api/marketing/channels/{id}       — удалить/архивировать площадку.
  GET    /api/marketing/documents           — документы расходов.
  GET    /api/marketing/documents/{id}      — документ с позициями.
  POST   /api/marketing/documents           — создать документ со строками.
  PUT    /api/marketing/documents/{id}      — изменить документ/позиции.
  DELETE /api/marketing/documents/{id}      — удалить документ.
  POST   /api/marketing/import/preview      — разбор Excel (dry-run).
  POST   /api/marketing/import/save         — сохранить разобранный файл.
  GET    /api/marketing/export              — строки для выгрузки в Excel.

Права: чтение — viewFinance, изменение — manageSettings.
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


# ------------------------------------------------------------- площадки
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


# ------------------------------------------------------------- документы
@router.get("/cards/search")
async def cards_search(
    q: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    """Поиск карточек компании — выбор SKU в позиции расхода."""
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


@router.post("/documents/{document_id}/copy")
async def documents_copy(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    """Копия документа («по образцу») — новая запись с теми же позициями."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.copy_document(document_id)
    except MarketingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary")
async def marketing_summary(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    channel_id: int | None = Query(default=None),
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    """Сводка по окну фильтра: документы, площадки, суммы, «в отчёт» (растянуто по периодам)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.summary(date_from, date_to, channel_id, q)
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
    """Dry-run: разбор листа, ничего не сохраняем."""
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
