"""Tags API — замена TagController (Yii2) + Tag::afterSave связей. MySQL/asyncmy."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagIn(BaseModel):
    name: str
    tag_group: str | None = None
    color: str = "#337ab7"
    priority: int = 0
    wbCardIds: list[int] = []


async def _save_links(db: AsyncSession, tag_id: int, ids: list[int]) -> None:
    await db.execute(text("DELETE FROM tag_card_links WHERE tag_id=:id"), {"id": tag_id})
    clean = [int(x) for x in (ids or []) if int(x) > 0]
    if clean:
        await db.execute(
            text("INSERT INTO tag_card_links(tag_id, nmID) VALUES(:t, :n)"),
            [{"t": tag_id, "n": nm} for nm in clean],
        )


@router.get("")
async def list_tags(db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    rows = (await db.execute(text(
        "SELECT t.id, t.name, t.tag_group, t.color, t.priority, t.company_id,"
        " COUNT(l.nmID) AS cards_count"
        " FROM tags t LEFT JOIN tag_card_links l ON l.tag_id=t.id"
        + ("" if company_id is None else " WHERE t.company_id = :cid")
        + " GROUP BY t.id, t.name, t.tag_group, t.color, t.priority, t.company_id"
        + " ORDER BY t.priority DESC, t.id"
    ), {} if company_id is None else {"cid": company_id})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{tag_id}")
async def get_tag(tag_id: int, db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    sql = "SELECT * FROM tags WHERE id=:id" + ("" if company_id is None else " AND company_id=:cid")
    params: dict = {"id": tag_id}
    if company_id is not None:
        params["cid"] = company_id
    tag = (await db.execute(text(sql), params)).mappings().first()
    if not tag:
        raise HTTPException(status_code=404, detail="tag not found")
    links = (await db.execute(text("SELECT nmID FROM tag_card_links WHERE tag_id=:id"), {"id": tag_id})).scalars().all()
    ids = [int(x) for x in links]
    cards: list[dict] = []
    if ids:
        stmt = text("SELECT nmID, vendorCode, title FROM wbcards WHERE nmID IN :ids"
                    + ("" if company_id is None else " AND (company_id = :cid OR company_id IS NULL)")).bindparams(
            bindparam("ids", expanding=True)
        )
        card_params: dict = {"ids": ids}
        if company_id is not None:
            card_params["cid"] = company_id
        cards = [dict(c) for c in (await db.execute(stmt, card_params)).mappings().all()]
    d = dict(tag)
    d["wbCardIds"] = ids
    d["cards"] = cards
    d["cards_count"] = len(ids)
    return d


@router.post("")
async def create_tag(payload: TagIn, db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    if company_id is None:
        raise HTTPException(status_code=400, detail="Выберите компанию для создания тега")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name пуст")
    await db.execute(text(
        "INSERT INTO tags(name, tag_group, color, priority, company_id) VALUES(:n,:g,:c,:p,:cid)"
    ), {"n": payload.name.strip(), "g": payload.tag_group, "c": payload.color, "p": payload.priority, "cid": company_id})
    tag_id = int((await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar() or 0)
    await _save_links(db, tag_id, payload.wbCardIds)
    await db.commit()
    return {"ok": True, "id": tag_id}


@router.put("/{tag_id}")
async def update_tag(tag_id: int, payload: TagIn, db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    sql = "SELECT id FROM tags WHERE id=:id" + ("" if company_id is None else " AND company_id=:cid")
    params: dict = {"id": tag_id}
    if company_id is not None:
        params["cid"] = company_id
    ok = (await db.execute(text(sql), params)).scalar()
    if not ok:
        raise HTTPException(status_code=404, detail="tag not found")
    await db.execute(text("UPDATE tags SET name=:n, tag_group=:g, color=:c, priority=:p WHERE id=:id"),
                     {"n": payload.name.strip(), "g": payload.tag_group, "c": payload.color, "p": payload.priority, "id": tag_id})
    await _save_links(db, tag_id, payload.wbCardIds)
    await db.commit()
    return {"ok": True, "id": tag_id}


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    tag_ids: list[int]
    if company_id is None:
        tag_ids = [tag_id]
    else:
        tags = (await db.execute(text("SELECT id FROM tags WHERE id=:id AND company_id=:cid"),
                                 {"id": tag_id, "cid": company_id})).scalars().all()
        if not tags:
            raise HTTPException(status_code=404, detail="tag not found")
        tag_ids = [int(t) for t in tags]
    for tid in tag_ids:
        await db.execute(text("DELETE FROM tag_card_links WHERE tag_id=:id"), {"id": tid})
    ph = ",".join(f":t{i}" for i in range(len(tag_ids)))
    await db.execute(text(f"DELETE FROM tags WHERE id IN ({ph})"),
                     {f"t{i}": t for i, t in enumerate(tag_ids)})
    await db.commit()
    return {"ok": True}


@router.get("/{tag_id}/margin")
async def tag_margin(
    tag_id: int,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort_by: str = Query(default="qnt"),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Маржа товаров тега — математика TopProductsService (profit_columns), фильтр по связям тега."""
    from backend.services.tag_margin_service import TagMarginService
    sql = "SELECT id FROM tags WHERE id=:id" + ("" if company_id is None else " AND company_id=:cid")
    params: dict = {"id": tag_id}
    if company_id is not None:
        params["cid"] = company_id
    exists = (await db.execute(text(sql), params)).scalar()
    if not exists:
        raise HTTPException(status_code=404, detail="tag not found")
    svc = TagMarginService(db, company_id=company_id)
    return await svc.get_margin(tag_id, date_from, date_to, sort_by)


@router.get("/{tag_id}/analytics")
async def tag_analytics(
    tag_id: int,
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Порт TagController::actionView — облако + related + сводки + данные графика."""
    from backend.services.tag_service import TagService
    tag = await get_tag(tag_id, db, company_id)
    all_tags = await list_tags(db, company_id)
    svc = TagService(db, company_id=company_id)
    data = await svc.analytics(tag, date_from, date_to)
    return {
        "tag": tag,
        "allTags": all_tags,
        **data,
        "date_from": date_from,
        "date_to": date_to,
    }
