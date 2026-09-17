"""Отзывы и ответы — порт WbFeedbackAnswersController (образец: routers/cost.py)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.feedback_service import FeedbackService

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


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


@router.post("/tags/sync")
async def feedback_tags_sync(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = FeedbackService(db, company_id=company_id)
    return await svc.sync_tags()
