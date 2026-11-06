"""Настройки налогов компании (страница «Настройка системы» + покрытие НДС).

Маршруты:
  GET  /api/tax-settings/versions      — все версии настроек (история).
  GET  /api/tax-settings/current       — действующая версия на дату.
  POST /api/tax-settings/versions      — создать новую версию (старая закрывается).
  GET  /api/tax-settings/nds-coverage  — покрытие НДС по карточкам (wbcards_nds).
  GET  /api/tax-settings/nds-missing   — карточки без ставки (для Excel).
  POST /api/tax-settings/preview       — «живой пример» расчёта; отчёты не меняет.

Права: чтение — viewFinance, изменение — manageSettings.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_manage_settings, require_perm
from backend.services.tax_settings_service import (
    MODE_LABELS,
    MODES,
    VAT_SOURCES,
    TaxSettingsError,
    TaxSettingsService,
)

router = APIRouter(prefix="/api/tax-settings", tags=["tax-settings"])


def _svc(db: AsyncSession, company_id, user) -> TaxSettingsService:
    return TaxSettingsService(db, company_id=company_id, user_id=(user or {}).get("id"))


@router.get("/meta")
async def tax_meta(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    """Справочники для формы: режимы и источник НДС."""
    return {
        "modes": [{"value": m, "label": MODE_LABELS[m]} for m in MODES],
        "vat_sources": [{"value": "cards", "label": "По ставке карточки (wbcards_nds)"},
                        {"value": "none", "label": "НДС не выделять"}],
    }


@router.get("/versions")
async def tax_versions(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    svc = _svc(db, company_id, user)
    try:
        return {"rows": await svc.list_versions()}
    except TaxSettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/current")
async def tax_current(
    on_date: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    svc = _svc(db, company_id, user)
    try:
        return {"row": await svc.current(on_date)}
    except TaxSettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/versions")
async def tax_create_version(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.create_version(payload)
    except TaxSettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/versions/{version_id}")
async def tax_update_version(
    version_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    """Изменить версию настроек (ставка/режим/НДС/причина/даты)."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.update_version(version_id, payload)
    except TaxSettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/versions/{version_id}")
async def tax_delete_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_manage_settings),
):
    """Удалить версию настроек."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.delete_version(version_id)
    except TaxSettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nds-coverage")
async def tax_nds_coverage(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    svc = _svc(db, company_id, user)
    try:
        return await svc.nds_coverage()
    except TaxSettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nds-missing")
async def tax_nds_missing(
    q: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    svc = _svc(db, company_id, user)
    try:
        return {"rows": await svc.nds_missing_cards(q, limit)}
    except TaxSettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preview")
async def tax_preview(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    _u: dict = Depends(require_perm("viewFinance")),
):
    """Живой пример: продажи → НДС по карточкам → налог. Ничего не сохраняет."""
    svc = _svc(db, company_id, user)
    try:
        return await svc.preview(
            payload.get("date_from") or "",
            payload.get("date_to") or "",
            mode=payload.get("mode"),
            main_rate=payload.get("main_rate"),
            vat_source=payload.get("vat_source"),
        )
    except TaxSettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))
