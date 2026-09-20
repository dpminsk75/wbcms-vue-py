"""CMS-блоки: мелкие тексты страниц в БД (Markdown). Чтение — залогиненным,
запись — только global_admin (решение 19.09)."""

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_user
from backend.services import auth_service

router = APIRouter(prefix="/api/cms", tags=["cms"])


@router.get("/blocks/{key}")
async def cms_block_get(
    key: str = Path(..., min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    row = (await db.execute(text("""
        SELECT `key`, title, body_md, updated_at FROM cms_blocks WHERE `key`=:k LIMIT 1
    """), {"k": key})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="block not found")
    d = dict(row)
    if hasattr(d.get("updated_at"), "isoformat"):
        d["updated_at"] = d["updated_at"].isoformat()
    return d


@router.put("/blocks/{key}")
async def cms_block_put(
    key: str = Path(..., min_length=1, max_length=100),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    if not await auth_service.is_global_admin(db, user["id"]):
        raise HTTPException(status_code=403, detail="only global_admin can edit cms blocks")
    data = payload or {}
    body = str(data.get("body_md") or "")
    title = str(data.get("title") or "")[:200]
    if len(body) > 200000:
        raise HTTPException(status_code=400, detail="body too large")
    await db.rollback()
    async with db.begin():
        await db.execute(text("""
            INSERT INTO cms_blocks (`key`, title, body_md, updated_by)
            VALUES (:k, :t, :b, :u)
            ON DUPLICATE KEY UPDATE title=VALUES(title), body_md=VALUES(body_md), updated_by=VALUES(updated_by)
        """), {"k": key, "t": title, "b": body, "u": user["id"]})
        row = (await db.execute(text("""
            SELECT `key`, title, body_md, updated_at FROM cms_blocks WHERE `key`=:k LIMIT 1
        """), {"k": key})).mappings().first()
    d = dict(row)
    if hasattr(d.get("updated_at"), "isoformat"):
        d["updated_at"] = d["updated_at"].isoformat()
    return d
