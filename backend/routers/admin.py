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


class AdminUserCreateIn(BaseModel):
    username: str
    email: str
    password: str
    # global: опционально сразу в компанию; мелкий админ: company_id обязателен из своих.
    company_id: int | None = None
    role: str = "member"
    perms: list[str] = []


@router.post("/users")
async def create_user(
    payload: AdminUserCreateIn, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
):
    # Создание пользователя напрямую (кнопка в /admin/users). Global — кого угодно +/без компании;
    # мелкий админ — только в свои компании (роль member/viewer/admin, пермы делегированные).
    if payload.role not in ("member", "viewer", "admin"):
        raise HTTPException(status_code=400, detail="invalid role")
    glob = await auth_service.is_global_admin(db, user["id"])
    company = None
    if payload.company_id is not None:
        company = await auth_service.get_company_by_id(db, payload.company_id)
        if not company:
            raise HTTPException(status_code=404, detail="company not found")
        if not glob and not await auth_service.can_manage_company(db, user["id"], payload.company_id):
            raise HTTPException(status_code=403, detail="company access denied")
    elif not glob:
        raise HTTPException(status_code=400, detail="company_id is required")
    try:
        granted = await auth_service.validate_grant(db, user["id"], payload.perms)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        await db.rollback()  # сбрасываем autobegin от deps перед begin (B6)
        async with db.begin():
            try:
                new_user = await auth_service.create_user(db, payload.username, payload.email, payload.password)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
            if company is not None:
                await auth_service.upsert_company_member(
                    db, company["id"], new_user["id"], payload.role, "active", user["id"]
                )
            if granted:
                await auth_service.grant_perms(db, new_user["id"], granted)
            return {
                "user": auth_service.public_user(new_user),
                "company": auth_service.public_company(company),
                "role": payload.role if company is not None else None,
                "perms": granted,
            }
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="username or email already exists")


class RolesSetIn(BaseModel):
    add: list[str] = []
    remove: list[str] = []


async def _need_global(db: AsyncSession, user: dict) -> None:
    # Управление ролями — только global_admin (замена yii2 /admin/assignment).
    if not await auth_service.is_global_admin(db, user["id"]):
        raise HTTPException(status_code=403, detail="global_admin required")


@router.get("/rbac-items")
async def rbac_items(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await _need_global(db, user)
    if auth_service.AUTH_V3:
        # v3: словарь прав из perms.json + системные роли из таблицы role.
        roles = (await db.execute(text("SELECT name, description FROM role ORDER BY name"))).mappings().all()
        out = [{"name": r["name"], "type": 1, "description": r["description"]} for r in roles]
        for name, meta in auth_service.PERMS_META.items():
            out.append({"name": name, "type": 2, "description": meta.get("label")})
        return out
    rows = (await db.execute(text(
        "SELECT name, type, description FROM auth_item ORDER BY type, name"
    ))).mappings().all()
    return [dict(r) for r in rows]


# --- v3: роли (CRUD) — страница «Роли» ---

class RoleCreateIn(BaseModel):
    name: str
    description: str | None = None
    perms: list[str] = []


class RoleUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None


class RolePermsIn(BaseModel):
    perms: list[str] = []


class UserRolesIn(BaseModel):
    add: list[str] = []
    remove: list[str] = []


@router.get("/perms")
async def perms_catalog(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """Словарь прав (perms.json) — для чекбоксов в админке. Список имён без секретов."""
    # Только global_admin (потребитель — страница «Роли»); описания пермов для
    # инвайтов/членств идут через /api/auth/grantable-perms (там свой скоуп).
    await _need_global(db, user)
    return [{"name": n, **{k: v for k, v in m.items() if k != "name"}}
            for n, m in auth_service.PERMS_META.items()]


@router.get("/roles")
async def list_roles(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await _need_global(db, user)
    return await auth_service.list_roles(db)


@router.post("/roles")
async def create_role(payload: RoleCreateIn, db: AsyncSession = Depends(get_db),
                      user: dict = Depends(get_current_user)):
    await _need_global(db, user)
    try:
        role = await auth_service.create_role(db, payload.name, payload.description, payload.perms)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return role


@router.patch("/roles/{role_id}")
async def update_role(role_id: int = Path(..., ge=1), payload: RoleUpdateIn = Body(...),
                      db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await _need_global(db, user)
    try:
        role = await auth_service.update_role(db, role_id, payload.name, payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return role


@router.put("/roles/{role_id}/perms")
async def set_role_perms(role_id: int = Path(..., ge=1), payload: RolePermsIn = Body(...),
                          db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await _need_global(db, user)
    try:
        clean = await auth_service.set_role_perms(db, role_id, payload.perms)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"id": role_id, "perms": clean}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int = Path(..., ge=1), db: AsyncSession = Depends(get_db),
                      user: dict = Depends(get_current_user)):
    await _need_global(db, user)
    try:
        await auth_service.delete_role(db, role_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"id": role_id, "deleted": True}


@router.post("/users/{user_id}/v3-roles")
async def set_user_roles_v3(
    user_id: int = Path(..., ge=1),
    payload: UserRolesIn = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Назначить/снять роли пользователю (v3). Только global_admin.

    Роли раньше имели доступ админы компаний, но проверка «чьи пермы у роли»
    не закрывала эскалацию (роль без пермов = global_admin), поэтому эндпоинт
    ужесточён до global_admin — как и все остальные /api/admin/roles*.
    """
    await _need_global(db, user)
    target = await auth_service.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    # global_admin (как и раньше) управляется только через БД/seed, не через API.
    if "global_admin" in (payload.add or []) or "global_admin" in (payload.remove or []):
        raise HTTPException(status_code=400, detail="global_admin is managed only via DB")
    try:
        roles = await auth_service.set_user_roles_v3(db, user_id, payload.add, payload.remove)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"id": user_id, "roles": roles}


@router.post("/users/{user_id}/roles")
async def set_user_roles(
    user_id: int = Path(..., ge=1),
    payload: RolesSetIn = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await _need_global(db, user)
    target = await auth_service.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    add = sorted({(p or "").strip() for p in (payload.add or []) if (p or "").strip()})
    remove = sorted({(p or "").strip() for p in (payload.remove or []) if (p or "").strip()})
    if "global_admin" in add or "global_admin" in remove:
        raise HTTPException(status_code=400, detail="global_admin is managed only via DB")
    if auth_service.AUTH_V3:
        # v3: роли — в user_role, права — напрямую в user_perm.
        add_roles = await auth_service.split_role_names(db, add)
        remove_roles = await auth_service.split_role_names(db, remove)
        add_perms = [p for p in add if p not in add_roles]
        remove_perms = [p for p in remove if p not in remove_roles]
        try:
            if add_roles or remove_roles:
                await auth_service.set_user_roles_v3(db, user_id, add_roles, remove_roles)
            if add_perms:
                await auth_service.grant_perms(db, user_id, add_perms)
            if remove_perms:
                await auth_service.revoke_perms(db, user_id, remove_perms)
        except ValueError as exc:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        await db.commit()
        return {"id": user_id, "items": await auth_service.get_user_explicit_items(db, user_id)}
    try:
        if add:
            await auth_service.grant_perms(db, user_id, add)
        if remove:
            await auth_service.revoke_perms(db, user_id, remove)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"id": user_id, "items": await auth_service.get_user_explicit_items(db, user_id)}


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
    items_by_user: dict[int, list[dict]] = {}
    if auth_service.AUTH_V3:
        # v3: роли из user_role, прямые права из user_perm; auth_* не читаем.
        items_by_user = await auth_service.get_users_items_v3(db, ids)
    else:
        ai = (await db.execute(text(
            "SELECT a.user_id AS uid, a.item_name AS name, i.type AS type "
            "FROM auth_assignment a LEFT JOIN auth_item i ON i.name=a.item_name "
            f"WHERE a.user_id IN ({placeholders})"
        ), {f"i{i}": str(v) for i, v in enumerate(ids)})).mappings().all()
        for r in ai:
            items_by_user.setdefault(int(r["uid"]), []).append({"name": r["name"], "type": r["type"]})
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "username": r["username"],
            "email": r["email"],
            "blocked": r["blocked_at"] is not None,
            "companies": by_user.get(r["id"], []),
            "items": sorted(items_by_user.get(r["id"], []), key=lambda x: x["name"]),
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


@router.get("/fbs-tariffs")
async def get_fbs_tariffs(_admin: dict = Depends(require_admin)):
    """Сетка сборки FBS (backend/config/fbs_assembly_tariffs.json) — чтение."""
    from backend.services import assembly_grid
    return assembly_grid.TARIFFS


@router.put("/fbs-tariffs")
async def put_fbs_tariffs(payload: dict = Body(...), _admin: dict = Depends(require_admin)):
    """Сетка сборки FBS — запись с валидацией + hot-reload без рестарта."""
    from backend.services import assembly_grid
    try:
        return assembly_grid.save(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))