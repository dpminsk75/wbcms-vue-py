"""Управление очередями сбора — /api/queue (страница «Очередь»).

Гейт — require_seo (viewSeo|admin), company-scope через get_current_company.
Глобальный админ (company_id=None) смотрит/удаляет всё; добавлять и
блокировать может только компания (правило per-company, §19.4).
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, require_seo
from backend.services import queue_service

router = APIRouter(prefix="/api/queue", tags=["queue"])


def _err(exc: ValueError):
    raise HTTPException(status_code=409, detail=str(exc))


# ---------- Сбор карточек ----------

@router.get("/cards")
async def queue_cards(
    queue: str = Query(default="all"),
    status: str = Query(default=""),
    q: str = Query(default=""),
    hidden: bool = Query(default=False),
    limit: int = Query(default=50, ge=0, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Строки очереди сбора карточек + счётчики (логика /api/ext/status).

    queue: watch (SEO-мониторинг) | plain (общая куча) | all (обе очереди —
    дефолт бэка; интерфейс по умолчанию открывается на watch).
    limit=0 — «Все» (без LIMIT).
    """
    qv = (queue or "").strip().lower()
    source = "watch" if qv == "watch" else ("all" if qv == "all" else "")
    try:
        counts = await queue_service.enrich_counts(db, company_id, source)
    except ValueError as e:
        _err(e)
    try:
        data = await queue_service.enrich_list(
            db, company_id, status=status, q=q, hidden=hidden, source=source,
            limit=limit, offset=offset)
    except ValueError as e:
        _err(e)
    return {**data, "counts": counts}


@router.get("/cards/counts")
async def queue_cards_counts(
    queue: str = Query(default="all"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Только счётчики «Сбора карточек» — лёгкий запрос для смены очереди
    (список страницы грузится по «Применить»). queue: watch|plain|all."""
    qv = (queue or "").strip().lower()
    source = "watch" if qv == "watch" else ("all" if qv == "all" else "")
    try:
        return await queue_service.enrich_counts(db, company_id, source)
    except ValueError as e:
        _err(e)


@router.get("/cards/competitors-count")
async def queue_cards_competitors_count(
    source_nm_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Сколько конкурентов у нашей карточки (для кнопки «Добавить (N)»)."""
    try:
        return await queue_service.enrich_competitors_count(db, company_id, source_nm_id)
    except ValueError as e:
        _err(e)


@router.post("/cards/seed")
async def queue_cards_seed(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Конкуренты нашей карточки → очередь: {source_nm_id}.

    Скрытые (is_hidden) не сеются; дублей нет; ответ {checked, added,
    skipped_hidden, already} — честный расклад по карточке.
    """
    try:
        nm = int((payload or {}).get("source_nm_id") or 0)
    except (TypeError, ValueError):
        nm = 0
    try:
        return await queue_service.enrich_seed(db, company_id, nm)
    except ValueError as e:
        _err(e)


@router.post("/cards")
async def queue_cards_add(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Добавить конкурента в очередь: {nm_id}. Только конкуренты наших карточек."""
    try:
        nm = int((payload or {}).get("nm_id") or 0)
    except (TypeError, ValueError):
        nm = 0
    try:
        return await queue_service.enrich_add(db, company_id, nm)
    except ValueError as e:
        _err(e)


@router.post("/cards/{queue_id}/requeue")
async def queue_cards_requeue(
    queue_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Вернуть строку в ожидание: done/error/gone/need_update → pending."""
    try:
        return await queue_service.enrich_requeue(db, company_id, queue_id)
    except ValueError as e:
        _err(e)


@router.delete("/cards/{queue_id}")
async def queue_cards_delete(
    queue_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Просто удалить из очереди. Card вернётся при следующем seed, если не заблокирована."""
    deleted = await queue_service.enrich_delete(db, company_id, queue_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="queue row not found")
    return {"ok": True, "deleted": deleted}


@router.post("/cards/block")
async def queue_cards_block(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Блокировать будущее добавление карточки в очередь / вернуть.

    {nm_id, hidden} — upsert `wb_competitor_capture.is_hidden` (§19.4).
    blocked строки в списке не отдаёт /next и не сеет — «заблокировано навсегда».
    """
    try:
        nm = int((payload or {}).get("nm_id") or 0)
        hidden = bool((payload or {}).get("hidden", True))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad payload")
    try:
        return await queue_service.enrich_block(
            db, company_id, nm, hidden, _user.get("id"))
    except ValueError as e:
        _err(e)


# ---------- Сбор поисковой выдачи ----------

@router.get("/search")
async def queue_search(
    source: str = Query(default="seo"),
    status: str = Query(default=""),
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=0, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Строки очереди поисковой выдачи: source=seo|compquery|phrases|all + счётчики.

    all — «Все» на странице: UNION трёх управляемых очередей (счётчики
    всё равно отдаём по всем трём — фронт суммирует сам).
    limit=0 — «Все» (без LIMIT).
    """
    try:
        counts = await queue_service.search_counts(db, company_id)
    except ValueError as e:
        _err(e)
    try:
        data = await queue_service.search_list(
            db, company_id, source, status=status, q=q, limit=limit, offset=offset)
    except ValueError as e:
        _err(e)
    return {**data, "counts": counts}


@router.get("/search/counts")
async def queue_search_counts(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Только счётчики по трём очередям выдачи (для смены «Очереди» на странице)."""
    try:
        return await queue_service.search_counts(db, company_id)
    except ValueError as e:
        _err(e)


@router.post("/search")
async def queue_search_add(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Добавить в очередь выдачи: {source, nm_id, phrase, priority}."""
    p = payload or {}
    try:
        nm = int(p.get("nm_id") or 0)
        pr = int(p.get("priority") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad payload")
    try:
        return await queue_service.search_add(
            db, company_id, str(p.get("source") or "seo"),
            nm_id=nm, phrase=str(p.get("phrase") or ""), priority=pr,
            user_id=_user.get("id"))
    except ValueError as e:
        _err(e)


@router.post("/search/{source}/{queue_id}/requeue")
async def queue_search_requeue(
    source: str,
    queue_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    try:
        return await queue_service.search_requeue(db, company_id, source, queue_id)
    except ValueError as e:
        _err(e)


@router.delete("/search/{source}/{queue_id}")
async def queue_search_delete(
    source: str,
    queue_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Удалить из очереди (seo = удаление целевой фразы, как на странице SEO)."""
    deleted = await queue_service.search_delete(db, company_id, source, queue_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="queue row not found")
    return {"ok": True, "deleted": deleted}
