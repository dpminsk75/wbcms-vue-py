"""Разбор отзывов по карточкам — список карточек, запуск ИИ-разбора, результаты.

Поток работы пользователя:
  1) GET  /api/review-insights/reviews      — карточки с отзывами за период
  2) GET  /api/review-insights/reviews/{id} — отзывы карточки (раскрытие строки)
  3) POST /api/review-insights/run          — запустить разбор отмеченных → job_id
  4) GET  /api/review-insights              — готовые разборы
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_company_admin, require_seo
from backend.services.feedback_insight_service import FeedbackInsightService

router = APIRouter(prefix="/api/feedback-insights", tags=["feedback-insights"])


def _check_dates(date_from: str, date_to: str) -> None:
    import re
    if not (re.match(r"^\d{4}-\d{2}-\d{2}$", date_from or "")
            and re.match(r"^\d{4}-\d{2}-\d{2}$", date_to or "")):
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD")
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from > date_to")


def _default_range(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    """Пустые даты → последние 30 дней (как в фильтре по умолчанию)."""
    from datetime import date as _date, timedelta as _td
    try:
        to = _date.fromisoformat(date_to) if date_to else _date.today()
    except ValueError:
        to = _date.today()
    try:
        frm = _date.fromisoformat(date_from) if date_from else to - _td(days=29)
    except ValueError:
        frm = to - _td(days=29)
    if frm > to:
        frm = to - _td(days=29)
    return frm.isoformat(), to.isoformat()


@router.get("/filters")
async def review_filters(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Бренды и категории для фильтра (как в /geo/sales-map)."""
    svc = FeedbackInsightService(db, company_id=company_id)
    return await svc.filter_options()


@router.get("/reviews")
async def review_reviews(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    nm_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Карточки, у которых за период есть отзывы с текстом. Даты по умолчанию — 30 дней."""
    d_from, d_to = _default_range(date_from, date_to)
    _check_dates(d_from, d_to)
    svc = FeedbackInsightService(db, company_id=company_id)
    return await svc.list_reviews(d_from, d_to, nm_id, page, page_size,
                                 q, brand, category)


@router.get("/reviews/{nm_id}")
async def review_card_reviews(
    nm_id: int,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Отзывы карточки с текстом — для раскрытия строки."""
    d_from, d_to = _default_range(date_from, date_to)
    _check_dates(d_from, d_to)
    svc = FeedbackInsightService(db, company_id=company_id)
    return {"items": await svc.card_reviews(nm_id, d_from, d_to, limit)}


@router.post("/run")
async def review_run(
    payload: dict,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Запустить ИИ-разбор по отмеченным карточкам → {job_id}."""
    nm_ids = payload.get("nm_ids") or []
    if not isinstance(nm_ids, list) or not nm_ids:
        raise HTTPException(status_code=400, detail="nm_ids: не отмечено ни одной карточки")
    date_from = payload.get("date_from")
    date_to = payload.get("date_to")
    if date_from and date_to:
        _check_dates(date_from, date_to)
    svc = FeedbackInsightService(db, company_id=company_id)
    try:
        job_id = await svc.start_analysis(
            nm_ids, user_id_of(user), background,
            date_from=date_from, date_to=date_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"job_id": job_id}


@router.get("")
async def feedback_insights(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    nm_id: int | None = Query(default=None, ge=1),
    job_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Готовые инсайты (свежие сверху). Даты — по периоду отзывов, по умолчанию 30 дней."""
    d_from, d_to = _default_range(date_from, date_to)
    _check_dates(d_from, d_to)
    svc = FeedbackInsightService(db, company_id=company_id)
    return await svc.list_insights(d_from, d_to, nm_id, page, page_size,
                                   job_id, q, brand, category)


@router.get("/prompt")
async def review_get_prompt(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Промпт разбора отзывов из настроек компании. Пусто = не задан."""
    svc = FeedbackInsightService(db, company_id=company_id)
    prompt = await svc.get_prompt(company_id)
    return {"prompt": prompt, "is_custom": bool(prompt)}


@router.put("/prompt")
async def review_put_prompt(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_company_admin),
    company_id: int | None = Depends(get_current_company),
):
    """Сохранить промпт разбора отзывов в настройках компании."""
    from backend.services import auth_service
    if company_id is None:
        raise HTTPException(status_code=400, detail="компания не определена")
    value = payload.get("prompt")
    if value is None:
        raise HTTPException(status_code=400, detail="prompt: обязательное поле")
    value = str(value).strip()
    if len(value) > 20000:
        raise HTTPException(status_code=400, detail="prompt: слишком длинный")
    try:
        await auth_service.update_company(db, company_id,
                                          {"review_analysis_prompt": value})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "is_custom": bool(value)}


def user_id_of(user: dict) -> int | None:
    try:
        return int(user["id"])
    except (KeyError, TypeError, ValueError):
        return None


# ВАЖНО: путь с параметром идёт последним — иначе перехватит /reviews и /prompt.
@router.get("/{insight_id}")
async def feedback_insight(
    insight_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Один разбор по id — открытие по ссылке ?insight=<id>."""
    svc = FeedbackInsightService(db, company_id=company_id)
    item = await svc.get_insight(insight_id)
    if not item:
        raise HTTPException(status_code=404, detail="разбор не найден")
    return item
