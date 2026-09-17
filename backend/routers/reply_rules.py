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