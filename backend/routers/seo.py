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


@router.get("/recommendations/{rec_id}/phrases")
async def seo_phrases(
    rec_id: int = Path(..., ge=1),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Живой пересчёт блока 'Поисковые фразы из расчета' за даты (дефолт 30д до вчера)."""
    from datetime import date as _date, timedelta
    try:
        to = _date.fromisoformat(date_to) if date_to else _date.today() - timedelta(days=1)
        frm = _date.fromisoformat(date_from) if date_from else to - timedelta(days=29)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad date, use YYYY-MM-DD")
    if frm > to:
        raise HTTPException(status_code=400, detail="date_from > date_to")
    if (to - frm).days > 180:
        raise HTTPException(status_code=400, detail="range max 180 days")
    data = await SeoService(db, company_id).get_phrases_period(rec_id, frm.isoformat(), to.isoformat())
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


@router.get("/targets")
async def seo_list_targets(
    nm_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Целевые фразы карточки (модалка «Целевые» на /wb/detail)."""
    data = await SeoService(db, company_id).list_targets(nm_id)
    if data is None:
        raise HTTPException(status_code=404, detail="card not found")
    return data


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
    """Вариант B: job на 1..100 nmID (item = карточка), фронт поллит /api/ai-jobs/{id}.
    Даты окна фраз (дефолт 30д до вчера) и fallback=1 (общие модели после confirm) — в params job."""
    raw = payload.get("nm_ids") or payload.get("nmID") or payload.get("nm_id")
    nm_ids = raw if isinstance(raw, list) else [raw]
    try:
        job_id = await SeoService(db, company_id).start_process(
            nm_ids, user["id"], background,
            date_from=payload.get("date_from"), date_to=payload.get("date_to"),
            allow_global=bool(payload.get("fallback") or payload.get("allow_global")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job_id": job_id}


@router.get("/ai-usage")
async def seo_ai_usage(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    scenario: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    nm_id: int | None = Query(default=None, ge=1),
    user_id: int | None = Query(default=None, ge=1),
    company_id: int | None = Query(default=None, ge=1),
    group_by: str = Query(default="model"),
    sort: str = Query(default="tokens"),
    direction: str = Query(default="desc"),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id_from_selector: int | None = Depends(get_current_company),
):
    """Журнал расхода ИИ: токены/стоимость по компаниям, моделям, сценариям.

    Колонка «$» — только глобальному админу (can_see_cost).
    company_id — из селектора топ-бара; None = «все компании» (глобальный админ).
    """
    from backend.services import ai_usage_service
    from backend.services import auth_service
    is_global = await auth_service.is_global_admin(db, user["id"])
    if not is_global:
        perms = await auth_service.effective_perms(db, user["id"])
        if "viewSeo" not in perms:
            raise HTTPException(status_code=403, detail="viewSeo required")
    # фильтр по конкретной компании — только глобальному админу
    scope_cid = company_id if (is_global and company_id) else company_id_from_selector
    data = await ai_usage_service.summary(
        db, date_from=date_from, date_to=date_to, company_id=scope_cid,
        group_by=group_by, scenario=scenario, provider=provider, model=model,
        nm_id=nm_id, user_id=user_id, sort=sort, direction=direction,
        limit=limit, offset=offset)
    data["can_see_cost"] = is_global
    data["group_by_options"] = ai_usage_service.GROUP_LABELS
    return data


@router.get("/ai-usage/artifacts")
async def seo_ai_usage_artifacts(
    scenario: str = Query(...),
    nm_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """«Что сгенерировали» — артефакт из таблицы сценария по карточке."""
    from backend.services import ai_usage_service
    return {"items": await ai_usage_service.artifacts(db, scenario, nm_id, company_id)}
