"""Поисковая аналитика WB — порт WbSearchController."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.wb_search_service import WbSearchService

router = APIRouter(prefix="/api/wb-search", tags=["wb-search"])


@router.get("/card")
async def search_card(
    nm_id: int = Query(..., ge=1),
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = WbSearchService(db, company_id=company_id)
    models, unique_dates = await svc.card_matrix(nm_id, date_from, date_to)
    return {
        "cardInfo": await svc.card_info(nm_id),
        "models": models,
        "uniqueDates": unique_dates,
        "nm_id": nm_id,
        "date_from": date_from,
        "date_to": date_to,
    }


@router.get("/trend")
async def search_trend(
    phrase_text: str | None = Query(default=None),
    date_from: str = Query(...),
    date_to: str = Query(...),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = WbSearchService(db, company_id=company_id)
    data = await svc.trend(phrase_text, date_from, date_to, page, 50)
    return {**data, "phrase_text": phrase_text, "date_from": date_from, "date_to": date_to}


@router.get("/phrases")
async def search_phrases(
    q: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = WbSearchService(db, company_id=company_id)
    return await svc.phrases_directory(q, limit)


@router.get("/phrase")
async def search_phrase(
    phrase_id: int | None = Query(default=None),
    phrase: str | None = Query(default=None),
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = WbSearchService(db, company_id=company_id)
    pid, text = await svc.resolve_phrase(phrase_id, phrase)
    if not text:
        return {"phrase": None, "phrase_id": None, "models": [], "uniqueDates": [], "chartData": [], "top5Info": {}}
    models, unique_dates = await svc.phrase_matrix(text, date_from, date_to)
    chart, top5 = await svc.phrase_chart(text, date_from, date_to)
    return {
        "phrase": text,
        "phrase_id": pid,
        "models": models,
        "uniqueDates": unique_dates,
        "chartData": chart,
        "top5Info": top5,
        "date_from": date_from,
        "date_to": date_to,
    }
