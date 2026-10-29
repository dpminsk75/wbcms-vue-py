"""Отзывы и ответы — порт WbFeedbackAnswersController (образец: routers/cost.py)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user
from backend.services.feedback_review_service import SCENARIO, FeedbackReviewService
from backend.services.feedback_service import FeedbackService

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def _strip(tot: dict, can_see: bool) -> dict:
    """Колонка «$» — только глобальному админу (can_see_cost), остальным скрыта."""
    d = {}
    for k, v in (tot or {}).items():
        d[k] = round(v, 2) if isinstance(v, float) else v
    if not can_see:
        d.pop("cost", None)
    return d


def _cost_block(day_rows: list[dict], day_totals: dict, model_rows: list[dict],
                can_see: bool) -> dict:
    """Блок «Затраты ИИ»: сегодня / 7 дней / 30 дней + разрез по моделям."""
    from datetime import date

    def sum_days(rows: list[dict], max_age: int) -> dict:
        tot = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
               "total_tokens": 0, "cost": 0.0, "failed": 0}
        for r in rows:
            try:
                d = date.fromisoformat(str(r.get("grp") or "")[:10])
            except Exception:
                continue
            if (date.today() - d).days >= max_age:
                continue
            for k in ("calls", "prompt_tokens", "completion_tokens", "total_tokens", "failed"):
                tot[k] += int(r.get(k) or 0)
            tot["cost"] += float(r.get("cost") or 0.0)
        return tot

    return {
        "today": _strip(sum_days(day_rows, 1), can_see),
        "week": _strip(sum_days(day_rows, 7), can_see),
        "month": _strip(day_totals or {}, can_see),
        "by_model": [_strip(dict(r), can_see) for r in (model_rows or [])],
    }


@router.get("/answers")
async def feedback_answers(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    nm_id: int | None = Query(default=None),
    rating: int | None = Query(default=None, ge=1, le=5),
    status: str | None = Query(default=None),
    has_media: bool = Query(default=False),
    paid_only: bool = Query(default=False),
    sort: str = Query(default="createdDate"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = FeedbackService(db, company_id=company_id)
    data = await svc.list(date_from, date_to, nm_id, rating, status,
                          has_media, paid_only, sort, order, page, page_size)
    data["tags_sentiment"] = await svc.tags_sentiment()
    data["rules"] = await svc.rules_options()
    return data


@router.get("/tags")
async def feedback_tags(
    filt: str = Query(default="unclassified", alias="filter"),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """wb_feedback_tags — глобальный справочник, company_id нет (structure.sql:1637)."""
    svc = FeedbackService(db, company_id=company_id)
    return await svc.list_tags("all" if filt == "all" else "unclassified")


@router.post("/tags/{tag_id}/sentiment")
async def feedback_tag_sentiment(
    tag_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = FeedbackService(db, company_id=company_id)
    ok = await svc.set_sentiment(tag_id, str(payload.get("sentiment") or ""))
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Некорректные данные")
    return {"ok": True}


@router.get("/popup-report")
async def feedback_popup_report(
    date_from: str = Query(...),
    date_to: str = Query(...),
    paid_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Попап Отзывы из «Финансовой аналитики» — порт FeedbackController::actionGetPopupReport."""
    import re
    if not (re.match(r"^\d{4}-\d{2}-\d{2}$", date_from or "") and re.match(r"^\d{4}-\d{2}-\d{2}$", date_to or "")):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD")
    svc = FeedbackService(db, company_id=company_id)
    return await svc.popup_report(date_from, date_to, paid_only)


@router.post("/tags/sync")
async def feedback_tags_sync(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = FeedbackService(db, company_id=company_id)
    return await svc.sync_tags()


# --- разбор отзыва через ИИ (эмоциональность / конструктивность / тональность) ---


@router.post("/review/{feedback_id}")
async def feedback_review_one(
    feedback_id: str,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Разобрать один отзыв (синхронно) — кнопка «Разобрать» в «Отзывах и ответах»."""
    svc = FeedbackReviewService(db, company_id=company_id)
    res = await svc.review_one(feedback_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=str(res.get("error") or "не удалось разобрать"))
    return res


@router.get("/review/errors")
async def feedback_review_errors(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Отзывы с ошибкой разбора — список для модалки «Вернуть в очередь»."""
    svc = FeedbackReviewService(db, company_id=company_id)
    return await svc.errors(limit)


@router.post("/review/{feedback_id}/retry")
async def feedback_review_retry(
    feedback_id: str,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Вернуть отзыв в очередь разбора (после ошибки)."""
    svc = FeedbackReviewService(db, company_id=company_id)
    res = await svc.retry(feedback_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail="отзыв не найден среди ошибок разбора")
    return res


@router.get("/review/prompt")
async def feedback_review_prompt(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Промпт разбора отзыва — настройка компании."""
    svc = FeedbackReviewService(db, company_id=company_id)
    return {"prompt": await svc.get_prompt()}


@router.put("/review/prompt")
async def feedback_review_prompt_save(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Сохранить промпт разбора отзыва."""
    svc = FeedbackReviewService(db, company_id=company_id)
    try:
        return await svc.set_prompt(str((payload or {}).get("prompt") or ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/review/settings")
async def feedback_review_settings(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Настройки авторазбора: включён ли, порция за прогон, промпт."""
    svc = FeedbackReviewService(db, company_id=company_id)
    return await svc.get_settings()


@router.put("/review/settings")
async def feedback_review_settings_save(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Сохранить настройки авторазбора (авто/порция)."""
    svc = FeedbackReviewService(db, company_id=company_id)
    p = payload or {}
    try:
        return await svc.set_settings(auto=p.get("auto"), batch=p.get("batch"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/review/status")
async def feedback_review_status(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Статус фонового разбора: флаги цикла, счётчики, очередь, настройки, расходы."""
    from backend.services import ai_usage_service
    from datetime import date, timedelta

    svc = FeedbackReviewService(db, company_id=company_id)
    data = await svc.get_status()
    scen = SCENARIO
    d30 = (date.today() - timedelta(days=29)).isoformat()
    day = await ai_usage_service.summary(db, group_by="day", scenario=scen,
                                         company_id=company_id, date_from=d30, limit=60)
    model_cut = await ai_usage_service.summary(db, group_by="model", scenario=scen,
                                                company_id=company_id, date_from=d30, limit=50)
    can_see_cost = "global_admin" in (user.get("roles") or []) or \
        "global_admin" in (user.get("perms") or []) or \
        "admin" in (user.get("roles") or []) or "admin" in (user.get("perms") or [])
    data["ai_usage"] = _cost_block(day.get("rows") or [], day.get("totals") or {},
                                   model_cut.get("rows") or [], can_see_cost)
    data["can_see_cost"] = can_see_cost
    return data


@router.get("/review/queue")
async def feedback_review_queue(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Очередь неразобранных отзывов."""
    svc = FeedbackReviewService(db, company_id=company_id)
    data = await svc.queue_preview(limit=limit + offset)
    items = data["items"][offset:]
    return {"items": items, "has_more": data["has_more"], "limit": limit, "offset": offset}


@router.get("/review/log")
async def feedback_review_log(
    level: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Журнал фонового разбора."""
    svc = FeedbackReviewService(db, company_id=company_id)
    return await svc.get_log(limit=limit, offset=offset, level=level)


@router.post("/review/pause")
async def feedback_review_pause(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Пауза/снятие паузы фонового разбора (в памяти процесса)."""
    from backend.services import feedback_review_service as svc_mod
    paused = bool((payload or {}).get("paused"))
    svc_mod.set_paused(paused)
    return svc_mod.status_flags()


@router.post("/review/run")
async def feedback_review_run(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Разобрать порцию отзывов прямо сейчас (кнопка «Разобрать порцию»)."""
    svc = FeedbackReviewService(db, company_id=company_id)
    limit = max(1, min(int((payload or {}).get("limit") or 20), 200))
    return await svc.run_now(limit=limit)


@router.post("/review/retry-all")
async def feedback_review_retry_all(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Вернуть все отзывы с ошибкой разбора в очередь."""
    svc = FeedbackReviewService(db, company_id=company_id)
    return await svc.retry_all()
