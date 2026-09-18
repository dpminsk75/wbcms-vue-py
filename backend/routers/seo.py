"""SEO рекомендации (порт SeoController). Гейт — require_seo (viewSeo|admin)."""

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_seo
from backend.services.seo_service import SeoService

router = APIRouter(prefix="/api/seo", tags=["seo"])


@router.get("/recommendations")
async def seo_list(
    status: str = Query(default="new"),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = SeoService(db, company_id)
    return {**await svc.search(status, q.strip(), page),
            "counts": await svc.counts(), "status": status, "q": q.strip()}


@router.get("/unprocessed")
async def seo_unprocessed(
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    return {"items": await SeoService(db, company_id).unprocessed(q.strip())}


@router.get("/cards")
async def seo_cards(
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="q required")
    return await SeoService(db, company_id).cards_search(q.strip())


@router.get("/recommendations/{rec_id}")
async def seo_view(
    rec_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    data = await SeoService(db, company_id).get_view(rec_id)
    if not data:
        raise HTTPException(status_code=404, detail="recommendation not found")
    return data


@router.post("/recommendations/{rec_id}/viewed")
async def seo_viewed(
    rec_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    if not await SeoService(db, company_id).set_viewed(rec_id, user["id"]):
        raise HTTPException(status_code=404, detail="recommendation not found")
    return {"ok": True}


@router.post("/recommendations/{rec_id}/requeue")
async def seo_requeue(
    rec_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    if not await SeoService(db, company_id).set_requeue(rec_id):
        raise HTTPException(status_code=404, detail="recommendation not found")
    return {"ok": True}


@router.post("/targets")
async def seo_add_target(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    try:
        return await SeoService(db, company_id).add_target(
            int(payload.get("nmID") or 0), str(payload.get("phrase") or ""), user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/targets/{tid}")
async def seo_remove_target(
    tid: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    _ = user
    if not await SeoService(db, company_id).remove_target(tid):
        raise HTTPException(status_code=404, detail="target not found")
    return {"ok": True}


@router.post("/process")
async def seo_process(
    background: BackgroundTasks,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Вариант B: job на 1..100 nmID (item = карточка), фронт поллит /api/ai-jobs/{id}."""
    raw = payload.get("nm_ids") or payload.get("nmID") or payload.get("nm_id")
    nm_ids = raw if isinstance(raw, list) else [raw]
    try:
        job_id = await SeoService(db, company_id).start_process(nm_ids, user["id"], background)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job_id": job_id}
