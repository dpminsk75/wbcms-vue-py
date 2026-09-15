from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_user, require_admin
from backend.services import auth_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    id: int
    username: str
    email: str
    blocked: bool
    companies: list[dict]


class AdminCompanyToggleIn(BaseModel):
    is_active: bool


class PasswordSetIn(BaseModel):
    password: str


@router.patch("/users/{user_id}/password")
async def set_user_password(
    user_id: int = Path(..., ge=1),
    payload: PasswordSetIn = Body(...),
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    # Смена пароля любому пользователю — только global_admin. Минимум 6 символов.
    try:
        await auth_service.update_user_password(db, user_id, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    check = await auth_service.get_user_by_id(db, user_id)
    if not check:
        raise HTTPException(status_code=404, detail="user not found")
    await db.commit()
    return {"id": user_id}


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    # Global admin видит всех; админ компании (owner/admin) — только членов своих компаний.
    # Чистый member/viewer без управляемых компаний → 403.
    scope_ids: list[int] | None = None
    if not await auth_service.is_global_admin(db, user["id"]):
        rows = (await db.execute(text(
            "SELECT company_id FROM company_members "
            "WHERE user_id=:u AND status='active' AND role IN ('owner','admin')"
        ), {"u": user["id"]})).all()
        scope_ids = [r[0] for r in rows]
        if not scope_ids:
            raise HTTPException(status_code=403, detail="company admin access denied")
    if scope_ids is None:
        rows = (await db.execute(text(
            "SELECT id, username, email, blocked_at FROM `user` WHERE gdpr_deleted=0 ORDER BY id"
        ))).mappings().all()
    else:
        placeholders = ",".join(f":c{i}" for i in range(len(scope_ids)))
        rows = (await db.execute(text(
            "SELECT DISTINCT u.id, u.username, u.email, u.blocked_at FROM `user` u "
            f"JOIN company_members cm ON cm.user_id=u.id WHERE u.gdpr_deleted=0 AND cm.company_id IN ({placeholders}) "
            "ORDER BY u.id"
        ), {f"c{i}": v for i, v in enumerate(scope_ids)})).mappings().all()
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    placeholders = ",".join(f":i{i}" for i in range(len(ids)))
    cm = (await db.execute(text(
        f"SELECT cm.user_id, cm.role, cm.status, c.id AS company_id, c.name AS company_name "
        f"FROM company_members cm JOIN companies c ON c.id=cm.company_id "
        f"WHERE cm.user_id IN ({placeholders}) ORDER BY cm.user_id, c.id"
    ), {f"i{i}": v for i, v in enumerate(ids)})).mappings().all()
    by_user: dict[int, list[dict]] = {}
    for r in cm:
        by_user.setdefault(r["user_id"], []).append({
            "company_id": r["company_id"],
            "company_name": r["company_name"],
            "role": r["role"],
            "status": r["status"],
        })
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "username": r["username"],
            "email": r["email"],
            "blocked": r["blocked_at"] is not None,
            "companies": by_user.get(r["id"], []),
        })
    return out


@router.patch("/users/{user_id}/blocked")
async def set_user_blocked(user_id: int = Path(..., ge=1), blocked: bool = Body(...), db: AsyncSession = Depends(get_db), _admin: dict = Depends(require_admin)):
    now = int(__import__("time").time()) if blocked else None
    result = await db.execute(text(
        "UPDATE `user` SET blocked_at=:ts, updated_at=:upd WHERE id=:i AND gdpr_deleted=0"
    ), {"ts": now, "upd": int(__import__("time").time()), "i": user_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="user not found")
    await db.commit()
    return {"id": user_id, "blocked": blocked}


@router.get("/companies")
async def list_companies(db: AsyncSession = Depends(get_db), _admin: dict = Depends(require_admin)):
    rows = (await db.execute(text(
        "SELECT c.id, c.name, c.abbreviation, c.inn, c.is_active, "
        "(SELECT COUNT(*) FROM company_members cm WHERE cm.company_id=c.id) AS members_count "
        "FROM companies c ORDER BY c.id"
    ))).mappings().all()
    return [dict(r) for r in rows]


@router.patch("/companies/{company_id}/active")
async def set_company_active(company_id: int = Path(..., ge=1), payload: AdminCompanyToggleIn = Body(...), db: AsyncSession = Depends(get_db), _admin: dict = Depends(require_admin)):
    result = await db.execute(text(
        "UPDATE companies SET is_active=:ia, updated_at=NOW() WHERE id=:i"
    ), {"ia": 1 if payload.is_active else 0, "i": company_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="company not found")
    await db.commit()
    return {"id": company_id, "is_active": payload.is_active}