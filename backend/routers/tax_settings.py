"""РќР°СЃС‚СЂРѕР№РєРё РЅР°Р»РѕРіРѕРІ РєРѕРјРїР°РЅРёРё (СЃС‚СЂР°РЅРёС†Р° В«РќР°СЃС‚СЂРѕР№РєР° СЃРёСЃС‚РµРјС‹В» + РїРѕРєСЂС‹С‚РёРµ РќР”РЎ).

РњР°СЂС€СЂСѓС‚С‹:
  GET  /api/tax-settings/versions      вЂ” РІСЃРµ РІРµСЂСЃРёРё РЅР°СЃС‚СЂРѕРµРє (РёСЃС‚РѕСЂРёСЏ).
  GET  /api/tax-settings/current       вЂ” РґРµР№СЃС‚РІСѓСЋС‰Р°СЏ РІРµСЂСЃРёСЏ РЅР° РґР°С‚Сѓ.
  POST /api/tax-settings/versions      вЂ” СЃРѕР·РґР°С‚СЊ РЅРѕРІСѓСЋ РІРµСЂСЃРёСЋ (СЃС‚Р°СЂР°СЏ Р·Р°РєСЂС‹РІР°РµС‚СЃСЏ).
  GET  /api/tax-settings/nds-coverage  вЂ” РїРѕРєСЂС‹С‚РёРµ РќР”РЎ РїРѕ РєР°СЂС‚РѕС‡РєР°Рј (wbcards_nds).
  GET  /api/tax-settings/nds-missing   вЂ” РєР°СЂС‚РѕС‡РєРё Р±РµР· СЃС‚Р°РІРєРё (РґР»СЏ Excel).
  POST /api/tax-settings/preview       вЂ” В«Р¶РёРІРѕР№ РїСЂРёРјРµСЂВ» СЂР°СЃС‡С‘С‚Р°; РѕС‚С‡С‘С‚С‹ РЅРµ РјРµРЅСЏРµС‚.

РџСЂР°РІР°: С‡С‚РµРЅРёРµ вЂ” viewFinance, РёР·РјРµРЅРµРЅРёРµ вЂ” manageSettings.
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
    """РЎРїСЂР°РІРѕС‡РЅРёРєРё РґР»СЏ С„РѕСЂРјС‹: СЂРµР¶РёРјС‹, РёСЃС‚РѕС‡РЅРёРєРё РќР”РЎ, СЃС‚Р°РІРєРё."""
    return {
        "modes": [{"value": m, "label": MODE_LABELS[m]} for m in MODES],
        "vat_sources": [{"value": "cards", "label": "РќР”РЎ Р·Р°Р»РѕР¶РµРЅ РІ С‚РѕРІР°СЂРµ (wbcards_nds)"},
                        {"value": "none", "label": "РќР”РЎ РЅРµ РёСЃС‡РёСЃР»СЏРµС‚СЃСЏ"}],
        "main_rates": [1, 3, 6, 7, 8, 12, 15, 20, 25, 30],
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
    """Р–РёРІРѕР№ РїСЂРёРјРµСЂ: РїСЂРѕРґР°Р¶Рё в†’ РќР”РЎ РїРѕ РєР°СЂС‚РѕС‡РєР°Рј в†’ РЅР°Р»РѕРі. РќРёС‡РµРіРѕ РЅРµ СЃРѕС…СЂР°РЅСЏРµС‚."""
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
