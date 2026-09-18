"""Конкуренты (порт CompetitorController). Гейт — require_seo (viewSeo|admin)."""

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_seo
from backend.services.competitor_service import CompetitorService

router = APIRouter(prefix="/api/competitors", tags=["competitors"])


@router.get("")
async def competitor_index(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    return await CompetitorService(db, company_id).list_sources()


@router.get("/{nm_id}/phrases")
async def competitor_phrases(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    return await CompetitorService(db, company_id).get_phrases(nm_id)


@router.post("/{nm_id}/select")
async def competitor_select(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    try:
        return await CompetitorService(db, company_id).save_selection(
            nm_id, payload.get("phrases") or [], int(payload.get("position_max") or 0))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{nm_id}/selected")
async def competitor_selected(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    return await CompetitorService(db, company_id).get_selected(nm_id)


@router.get("/{nm_id}/results")
async def competitor_results(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    return await CompetitorService(db, company_id).get_results(nm_id)


@router.post("/remove")
async def competitor_remove(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    _ = company_id
    ok = await CompetitorService(db, None).remove_selected(
        int(payload.get("source_nm_id") or 0), int(payload.get("nm_id") or 0))
    if not ok:
        raise HTTPException(status_code=404, detail="Не найдено")
    return {"success": True}


@router.post("/analyze")
async def competitor_analyze(
    background: BackgroundTasks,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Вариант B: job из 1 item по analysis.id (порт actionAnalyze)."""
    try:
        job_id = await CompetitorService(db, company_id).start_analyze_one(
            int(payload.get("id") or 0), user["id"], background)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job_id": job_id}


@router.post("/analyze-direct")
async def competitor_analyze_direct(
    background: BackgroundTasks,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    try:
        job_id = await CompetitorService(db, company_id).start_analyze_direct(
            int(payload.get("source_nm_id") or 0), int(payload.get("competitor_nm_id") or 0),
            user["id"], background)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job_id": job_id}


@router.post("/{nm_id}/analyze-all")
async def competitor_analyze_all(
    background: BackgroundTasks,
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Вариант B: запускает фоновый job (item = 1 конкурент), фронт поллит /api/ai-jobs/{id}."""
    try:
        job_id = await CompetitorService(db, company_id).start_analyze_all(nm_id, user["id"], background)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job_id": job_id}


@router.post("/{nm_id}/summary")
async def competitor_summary(
    nm_id: int = Path(..., ge=1),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Сводка: кэш 30д, force-пересчёт только admin (порт actionSummary)."""
    from backend.services import auth_service
    is_admin = await auth_service.is_global_admin(db, user["id"])
    return await CompetitorService(db, company_id).get_summary(
        nm_id, bool((payload or {}).get("force")), is_admin)
