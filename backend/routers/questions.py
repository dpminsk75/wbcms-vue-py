"""Вопросы покупателей WB — страница «Вопросы».

Данные — таблица wb_questions (наполняется воркером backend/workers/questions_sync.py).
Литеральные пути (/stats, /sync/status) объявлены ПЕРЕД /{qid} — иначе FastAPI
отдаст их в обработчик вопроса.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services import questions_sync_service as sync_svc
from backend.services.questions_service import QuestionsService

router = APIRouter(prefix="/api/questions", tags=["questions"])


@router.get("")
async def questions_list(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    nm_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    sort: str = Query(default="created_date"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Список вопросов + счётчики для KPI-плиток."""
    svc = QuestionsService(db, company_id=company_id)
    data = await svc.list(date_from, date_to, nm_id, status, q, sort, order,
                          page, page_size)
    data["stats"] = await svc.stats(date_from, date_to)
    return data


@router.get("/stats")
async def questions_stats(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = QuestionsService(db, company_id=company_id)
    return await svc.stats(date_from, date_to)


@router.get("/sync/status")
async def questions_sync_status():
    """Состояние фонового синка (запущенного кнопкой на странице)."""
    return sync_svc.sync_state()


@router.post("/sync")
async def questions_sync(
    payload: dict | None = None,
    company_id: int | None = Depends(get_current_company),
):
    """Запустить синк в фоне: fresh — окно дат, full — вся история."""
    p = payload or {}
    mode = str(p.get("mode") or "fresh")
    if mode not in ("fresh", "full"):
        raise HTTPException(status_code=400, detail="mode: fresh или full")
    cid = p.get("company_id")
    if cid and int(cid) != company_id:
        raise HTTPException(status_code=403, detail="чужую компанию синхронизировать нельзя")
    if company_id is None:
        raise HTTPException(status_code=400, detail="выберите компанию (X-Company-Id)")
    res = sync_svc.start_sync(
        company_id, mode=mode, date_from=p.get("date_from"), date_to=p.get("date_to"),
        nm_id=int(p["nm_id"]) if p.get("nm_id") else None,
        window_days=int(p.get("window_days") or 30),
        dry_run=bool(p.get("dry_run")),
    )
    if not res.get("started"):
        raise HTTPException(status_code=409, detail=str(res.get("error") or "не запустилось"))
    return res


@router.get("/{qid}")
async def questions_get(
    qid: str,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Один вопрос (с ответом продавца)."""
    svc = QuestionsService(db, company_id=company_id)
    item = await svc.get(qid)
    if not item:
        raise HTTPException(status_code=404, detail="вопрос не найден")
    return item
