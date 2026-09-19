"""Правила автоответов — порт WbReplyRulesController (образец: routers/cost.py)."""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.reply_rules_service import ReplyRulesService

# Инициализируем роутер ВВЕРХУ файла
router = APIRouter(prefix="/api/reply-rules", tags=["reply-rules"])


@router.get("")
async def rules_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = ReplyRulesService(db, company_id=company_id)
    return await svc.list(page, page_size)


@router.get("/test-generation")
async def rules_test_generation(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """100 последних отзывов + сгенерированные ответы. Ничего не отправляет.
    Shared-матчинг с будущим cron-воркером (feedback_reply_service)."""
    from backend.services.feedback_reply_service import FeedbackReplyService
    svc = FeedbackReplyService(db, company_id=company_id)
    return await svc.preview()


@router.get("/stop-words")
async def stop_words_list(
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from backend.services.stop_words_service import StopWordsService
    return await StopWordsService(db, company_id=company_id).list()


@router.post("/stop-words")
async def stop_words_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from backend.services.stop_words_service import StopWordsService
    try:
        return await StopWordsService(db, company_id=company_id).create(
            str(payload.get("word") or ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/stop-words/{word_id}/active")
async def stop_words_toggle(
    word_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from backend.services.stop_words_service import StopWordsService
    new = await StopWordsService(db, company_id=company_id).toggle(word_id)
    if new is None:
        raise HTTPException(status_code=404, detail="Слово не найдено")
    return {"ok": True, "is_active": new}


@router.delete("/stop-words/{word_id}")
async def stop_words_delete(
    word_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from backend.services.stop_words_service import StopWordsService
    if not await StopWordsService(db, company_id=company_id).remove(word_id):
        raise HTTPException(status_code=404, detail="Слово не найдено")
    return {"ok": True}


@router.get("/product-list")
async def rules_product_list(
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = ReplyRulesService(db, company_id=company_id)
    return {"results": await svc.product_list(q)}


@router.get("/brand-list")
async def rules_brand_list(
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = ReplyRulesService(db, company_id=company_id)
    return {"results": await svc.brand_list(q)}


@router.get("/{rule_id}")
async def rules_get(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = ReplyRulesService(db, company_id=company_id)
    d = await svc.get(rule_id)
    if not d:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return d


@router.post("")
async def rules_create(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = ReplyRulesService(db, company_id=company_id)
    try:
        rule_id = await svc.save(None, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "id": rule_id}


@router.put("/{rule_id}")
async def rules_update(
    rule_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = ReplyRulesService(db, company_id=company_id)
    try:
        await svc.save(rule_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return {"ok": True, "id": rule_id}


@router.patch("/{rule_id}/active")
async def rules_toggle(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = ReplyRulesService(db, company_id=company_id)
    new = await svc.toggle(rule_id)
    if new is None:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return {"ok": True, "is_active": new}


@router.delete("/{rule_id}")
async def rules_delete(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = ReplyRulesService(db, company_id=company_id)
    if not await svc.delete(rule_id):
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return {"ok": True}