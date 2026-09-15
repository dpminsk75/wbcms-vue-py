from typing import Literal

import json
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from backend.database import get_db
from backend.deps import get_current_user, require_admin
from backend.services import auth_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterInviteIn(BaseModel):
    username: str
    email: str
    password: str
    company_name: str | None = None
    abbreviation: str | None = None
    inn: str | None = None
    invite_token: str


class InviteCreateIn(BaseModel):
    company_id: int | None = None
    company_name: str | None = None
    abbreviation: str | None = None
    inn: str | None = None
    email: str | None = None
    role: Literal["admin", "member"] = "member"
    # v2: явные пермы сверх базы (делегирование — см. validate_grant)
    perms: list[str] = []
    expires_in_days: int = 7


class CompanyCreateIn(BaseModel):
    name: str
    abbreviation: str | None = None
    inn: str | None = None
    seo_model: str | None = None
    seo_summary_model: str | None = None
    seo_summary_max_tokens: int | None = None
    seo_daily_limit: int | None = None
    seo_desc_min: int | None = None
    seo_desc_max: int | None = None
    seo_anti_spam_days: int | None = None
    seo_openrouter_key: str | None = None
    seo_openrouter_referer: str | None = None
    seo_openrouter_title: str | None = None
    seo_prompt: str | None = None
    seo_competitor_prompt: str | None = None
    seo_summary_prompt: str | None = None


class MemberInviteIn(BaseModel):
    email: str
    role: Literal["admin", "member"] = "member"


class MemberUpdateIn(BaseModel):
    role: Literal["owner", "admin", "member", "viewer"]
    status: Literal["active", "blocked", "invited"] = "active"


async def _make_unique_username(db: AsyncSession, email: str) -> str:
    local = email.split("@", 1)[0].strip().lower()
    username = "".join(ch if ch.isalnum() or ch in ("_", ".") else "_" for ch in local)[:50].strip(".")
    username = username or "user"
    candidate = username
    suffix = 2
    while await auth_service.get_user_by_username(db, candidate):
        candidate = f"{username[:45]}_{suffix}"
        suffix += 1
    return candidate


@router.post("/register")
async def register(payload: RegisterInviteIn, db: AsyncSession = Depends(get_db)):
    try:
        # deps (require_admin/get_current_user) уже открыли autobegin-транзакцию SELECT'ами —
        # сбрасываем её, иначе db.begin() упадёт "A transaction is already begun". До begin только чтения.
        await db.rollback()
        async with db.begin():
            # resolve возвращает (row, payload): id токена — в row, данные — в payload
            token_row, token_payload = await auth_service.resolve_invite_token(db, payload.invite_token)

            if token_payload.get("type") == "company":
                # Имя компании НЕ сверяем с инвайтом (2026-09-15): пользователь может править
                # название при регистрации, сохраняем новое. Из токена — только подсказка.
                company_name = (payload.company_name or "").strip() or (token_payload.get("company_name") or "").strip()
                if not company_name:
                    raise HTTPException(status_code=400, detail="company_name is required")
                user = await auth_service.create_user(
                    db,
                    payload.username,
                    payload.email,
                    payload.password,
                )
                company = await auth_service.create_company(
                    db,
                    owner_id=user["id"],
                    name=company_name,
                    abbreviation=payload.abbreviation,
                    inn=payload.inn,
                )
            else:
                target_email = (token_payload.get("target_email") or "").strip().lower()
                if auth_service.normalize_email(payload.email) != target_email:
                    raise HTTPException(status_code=400, detail="email doesn't match invite")

                user = await auth_service.get_user_by_email(db, payload.email)
                if not user:
                    user = await auth_service.create_user(
                        db,
                        payload.username,
                        payload.email,
                        payload.password,
                    )
                else:
                    if user.get("blocked_at") is not None:
                        raise HTTPException(status_code=403, detail="user is blocked")
                    member = await auth_service.get_company_member(db, token_payload["company_id"], user["id"])
                    if member and member.get("status") == "active":
                        raise HTTPException(status_code=409, detail="user is already an active company member")
                    if member and member.get("status") == "invited":
                        # Первая активация: аккаунт предсоздан инвайтом со случайным паролем —
                        # сохраняем пароль из формы, иначе человек не войдёт (200 + вечный 401).
                        # Владение email доказано самим токеном. Уже активных нигде не трогаем.
                        await auth_service.update_user_password(db, int(user["id"]), payload.password)

                await auth_service.upsert_company_member(
                    db,
                    token_payload["company_id"],
                    user["id"],
                    token_payload.get("role") or "member",
                    "active",
                    None,
                )
                # v2: явные пермы из инвайта (проверены при выпуске, payload запечатан Fernet)
                try:
                    await auth_service.grant_perms(db, user["id"], token_payload.get("perms") or [])
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))

            consumed = await auth_service.consume_invite_token(db, token_row["id"], int(user["id"]))
            if not consumed:
                raise HTTPException(status_code=409, detail="invite token was already used or expired")

            return {
                "token": auth_service.create_token(user["id"], user["username"]),
                "user": auth_service.public_user(user),
                "company": auth_service.public_company(company if token_payload.get("type") == "company" else await auth_service.get_company_by_id(db, token_payload["company_id"])),
            }
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="username or email already exists")
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


def _mask_email(email: str) -> str:
    # Маскировка для публичного peek: наружу только первая буква + домен.
    email = (email or "").strip()
    if "@" not in email:
        return (email[:1] + "***") if email else ""
    local, _, domain = email.partition("@")
    return (local[:1] + "***@" + domain) if local else "***@" + domain


@router.get("/grantable-perms")
async def grantable_perms(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    # Что текущий юзер может выдавать (для чекбоксов в UI инвайта).
    if await auth_service.is_global_admin(db, user["id"]):
        allowed = list(auth_service.GRANTABLE_PERMS)
    else:
        mine = await auth_service.effective_perms(db, user["id"])
        allowed = [p for p in auth_service.GRANTABLE_PERMS if p in mine]
    if not allowed:
        return []
    placeholders = ",".join(f":p{i}" for i in range(len(allowed)))
    rows = (await db.execute(
        text(f"SELECT name, description FROM auth_item WHERE name IN ({placeholders}) ORDER BY name"),
        {f"p{i}": v for i, v in enumerate(allowed)},
    )).mappings().all()
    return [dict(r) for r in rows]


@router.get("/invites/{token}/info")
async def invite_info(token: str = Path(...), db: AsyncSession = Depends(get_db)):
    # Публичный peek для RegisterPage (B1): тип токена и не-секреты, чтобы показать
    # поле компании / маску email до регистрации. Сам токен не раскрываем, не тратим.
    try:
        _, payload = await auth_service.resolve_invite_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="invalid or expired invite token")
    exp = payload.get("exp")
    expires_at = None
    if exp:
        try:
            expires_at = datetime.fromtimestamp(int(exp)).replace(microsecond=0).isoformat() + "Z"
        except (TypeError, ValueError):
            expires_at = None
    if payload.get("type") == "company":
        return {
            "type": "company",
            "company_name": payload.get("company_name"),
            "expires_at": expires_at,
        }
    company = await auth_service.get_company_by_id(db, payload.get("company_id") or -1)
    return {
        "type": "user",
        "company_id": payload.get("company_id"),
        "company": auth_service.public_company(company),
        "email_masked": _mask_email(payload.get("target_email") or ""),
        "role": payload.get("role") or "member",
        "expires_at": expires_at,
    }


@router.get("/invites")
async def list_invites(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    # Список токенов со статусами для страницы /admin/invites. Сырых токенов в БД нет
    # (только Fernet-шифр), поэтому показать можно только метаданные + статус.
    # global_admin видит все, обычный admin — только выпущенные им.
    from sqlalchemy import text as _text
    is_global = await auth_service.is_global_admin(db, user["id"])
    rows = (await db.execute(_text("""
        SELECT t.id, t.token_type, t.company_id, c.name AS company_label,
               t.target_email, t.role, t.company_name,
               t.expires_at, t.created_at, t.used_at, t.created_by, u.username AS created_by_name,
               t.used_by, w.username AS used_by_name
        FROM auth_invite_tokens t
        LEFT JOIN companies c ON c.id = t.company_id
        LEFT JOIN `user` u ON u.id = t.created_by
        LEFT JOIN `user` w ON w.id = t.used_by
        WHERE (:all = 1 OR t.created_by = :me)
        ORDER BY t.created_at DESC
        LIMIT 200
    """), {"all": 1 if is_global else 0, "me": user["id"]})).mappings().all()
    now = datetime.utcnow()
    out = []
    for r in rows:
        d = dict(r)
        exp = d.get("expires_at")
        if d.get("used_at") is not None:
            d["status"] = "used"
        elif exp is not None and exp < now:
            d["status"] = "expired"
        else:
            d["status"] = "active"
        for k in ("expires_at", "created_at", "used_at"):
            if d.get(k) is not None:
                d[k] = d[k].isoformat()
        out.append(d)
    return out


@router.get("/invites/by-id/{token_id}/link")
async def invite_link(token_id: int = Path(..., ge=1), db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    # Раскрытие ссылки активного токена для кнопки «Копировать» в таблице /admin/invites.
    # Сырые токены не хранятся — расшифровываем Fernet-шифр на лету. Только неиспользованные
    # и непросроченные; обычный admin — только свои.
    from sqlalchemy import text as _text2
    from cryptography.fernet import InvalidToken as _InvalidToken
    row = (await db.execute(_text2("""
        SELECT id, token_ciphertext, expires_at, used_at, created_by
        FROM auth_invite_tokens WHERE id=:id
    """), {"id": token_id})).mappings().first()
    if not row or row["used_at"] is not None:
        raise HTTPException(status_code=404, detail="invite token not found or already used")
    if row["expires_at"] is not None and row["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=410, detail="invite token expired")
    if not await auth_service.is_global_admin(db, user["id"]) and row["created_by"] != user["id"]:
        raise HTTPException(status_code=403, detail="access denied")
    try:
        payload = json.loads(auth_service._fernet().decrypt(row["token_ciphertext"].encode("utf-8")).decode("utf-8"))
    except _InvalidToken:
        raise HTTPException(status_code=500, detail="cannot decrypt invite token")
    raw = payload.get("token")
    if not raw:
        raise HTTPException(status_code=500, detail="cannot decrypt invite token")
    return {"invite_token": raw, "register_path": f"/register?invite={raw}"}


@router.post("/invites")
async def create_invite(payload: InviteCreateIn, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    try:
        # см. register выше: сбрасываем autobegin-транзакцию от deps перед db.begin()
        await db.rollback()
        async with db.begin():
            if payload.company_name:
                if not await auth_service.is_global_admin(db, user["id"]):
                    raise HTTPException(status_code=403, detail="only global_admin can create company invites")
                token = await auth_service.create_company_invite_token(
                    db,
                    created_by=user["id"],
                    company_name=payload.company_name,
                    abbreviation=payload.abbreviation,
                    inn=payload.inn,
                    expires_in_days=payload.expires_in_days,
                )
                company = None
            elif payload.company_id:
                if not await auth_service.can_manage_company(db, user["id"], payload.company_id):
                    raise HTTPException(status_code=403, detail="company access denied")
                company = await auth_service.get_company_by_id(db, payload.company_id)
                if not company:
                    raise HTTPException(status_code=404, detail="company not found")

                target = await auth_service.get_user_by_email(db, payload.email or "")
                if target and target.get("blocked_at") is not None:
                    raise HTTPException(status_code=403, detail="user is blocked")
                if target:
                    member = await auth_service.get_company_member(db, payload.company_id, target["id"])
                    if member and member.get("status") == "active":
                        raise HTTPException(status_code=409, detail="user is already an active company member")
                else:
                    target = await auth_service.create_user(
                        db,
                        await _make_unique_username(db, payload.email or ""),
                        payload.email or "",
                        secrets.token_urlsafe(12),
                    )

                try:
                    granted = await auth_service.validate_grant(db, user["id"], payload.perms)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))
                if granted:
                    await auth_service.grant_perms(db, target["id"], granted)

                token = await auth_service.create_user_invite_token(
                    db,
                    created_by=user["id"],
                    company_id=payload.company_id,
                    email=payload.email or "",
                    role=payload.role,
                    expires_in_days=payload.expires_in_days,
                    perms=granted,
                )
            else:
                raise HTTPException(status_code=400, detail="company_id or company_name is required")

            return {
                "invite_token": token,
                # срок = создание + expires_in_days (раньше ошибочно отдавался utcnow())
                "expires_at": (datetime.utcnow() + timedelta(days=payload.expires_in_days)).replace(microsecond=0).isoformat() + "Z",
                "company": auth_service.public_company(company),
            }
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="username or email already exists")
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": auth_service.public_user(user), "roles": user.get("roles", []), "perms": user.get("perms", [])}


@router.get("/memberships")
async def my_memberships(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    # Свои членства для фронта (гард /admin/users пускает админов компаний, не только global).
    rows = (await db.execute(
        text(
            "SELECT cm.company_id, c.name AS company_name, cm.role, cm.status "
            "FROM company_members cm JOIN companies c ON c.id=cm.company_id "
            "WHERE cm.user_id=:u ORDER BY c.id"
        ), {"u": user["id"]})).mappings().all()
    return [dict(r) for r in rows]
