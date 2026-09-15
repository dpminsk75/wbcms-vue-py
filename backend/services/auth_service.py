"""Auth helpers for FastAPI prototype."""
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGO = "HS256"
EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "720"))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        h = password_hash
        if h.startswith("$2y$"):
            h = "$2b$" + h[4:]
        return bcrypt.checkpw(plain.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: int, username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MIN)
    return jwt.encode({"sub": str(user_id), "username": username, "exp": exp}, SECRET_KEY, algorithm=ALGO)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
    except Exception:
        return None


def _fernet():
    key = os.getenv("INVITE_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("INVITE_ENCRYPTION_KEY is not set")
    return Fernet(key.encode("utf-8"))


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_user_by_username(db: AsyncSession, username: str) -> dict | None:
    q = text("SELECT id, username, email, password_hash, blocked_at FROM `user` WHERE username=:u LIMIT 1")
    r = (await db.execute(q, {"u": username})).mappings().first()
    return dict(r) if r else None


async def get_user_by_email(db: AsyncSession, email: str) -> dict | None:
    q = text("SELECT id, username, email, password_hash, blocked_at FROM `user` WHERE email=:e LIMIT 1")
    r = (await db.execute(q, {"e": normalize_email(email)})).mappings().first()
    return dict(r) if r else None


async def get_user_by_id(db: AsyncSession, user_id: int) -> dict | None:
    q = text("SELECT id, username, email, blocked_at FROM `user` WHERE id=:i LIMIT 1")
    r = (await db.execute(q, {"i": user_id})).mappings().first()
    return dict(r) if r else None


async def create_user(db: AsyncSession, username: str, email: str, password: str) -> dict:
    username = username.strip()
    email = normalize_email(email)
    if not username or not email or not password:
        raise ValueError("username, email and password are required")
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")
    if await get_user_by_username(db, username) or await get_user_by_email(db, email):
        raise ValueError("username or email already exists")

    now = int(time.time())
    await db.execute(text("""
        INSERT INTO `user` (
          username, email, password_hash, auth_key, confirmed_at, blocked_at,
          created_at, updated_at, flags
        )
        VALUES (:username, :email, :password_hash, :auth_key, :confirmed_at, NULL, :now, :now, 0)
    """), {
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "auth_key": secrets.token_urlsafe(18)[:32],
        "confirmed_at": now,
        "now": now,
    })
    user_id = (await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()
    return await get_user_by_id(db, int(user_id))


async def update_user_password(db: AsyncSession, user_id: int, password: str) -> None:
    # Смена пароля при первой активации: юзер предсоздан инвайтом со случайным паролем,
    # свой пароль он задаёт в форме регистрации — молча игнорировать его нельзя (иначе 200 + вечный 401).
    if not password or len(password) < 6:
        raise ValueError("password must be at least 6 characters")
    await db.execute(text("UPDATE `user` SET password_hash=:h WHERE id=:i"), {
        "h": hash_password(password), "i": user_id,
    })


async def get_user_perms(db: AsyncSession, user_id: int) -> dict:
    rows = (await db.execute(
        text("SELECT item_name FROM auth_assignment WHERE user_id=:u"), {"u": str(user_id)}
    )).all()
    assigned = [r[0] for r in rows]
    all_names: set[str] = set(assigned)
    frontier = list(assigned)

    for _ in range(10):
        if not frontier:
            break
        placeholders = ",".join(f":p{i}" for i in range(len(frontier)))
        params = {f"p{i}": v for i, v in enumerate(frontier)}
        kids = (await db.execute(
            text(f"SELECT child FROM auth_item_child WHERE parent IN ({placeholders})"), params
        )).all()
        nxt = [k[0] for k in kids if k[0] not in all_names]
        if not nxt:
            break
        all_names.update(nxt)
        frontier = nxt

    try:
        types = (await db.execute(text("SELECT name, type FROM auth_item"))).all()
        tmap = {n: t for n, t in types}
        roles = sorted(n for n in all_names if tmap.get(n) == 1)
        perms = sorted(n for n in all_names if tmap.get(n) != 1)
    except Exception:
        roles = sorted(assigned)
        perms = sorted(all_names - set(assigned))

    # v2: derived-пермы из ролей в компаниях (без записей — read-time).
    # Мелкий админ/owner: база + управление своими; member: отчёты; viewer: дашборд.
    # viewSeo/manageFbsStocks — только явными грантами. На require_admin/isAdmin не влияет.
    derived = await get_derived_perms(db, user_id)
    all_names |= derived
    perms = sorted(set(perms) | derived)
    return {"roles": roles, "perms": perms, "all": sorted(all_names), "derived": sorted(derived)}


# База по роли в компании. manageCompanyUsers — кастомный перм только для menu.json
# (пункты «Пользователи (SPA)» своих компаний); в yii2 такого нет, прод его игнорирует.
COMPANY_ROLE_PERMS: dict[str, tuple[str, ...]] = {
    "owner": ("viewReports", "viewOrders", "manageCompanyUsers"),
    "admin": ("viewReports", "viewOrders", "manageCompanyUsers"),
    "member": ("viewReports", "viewOrders"),
    "viewer": ("viewDashboard",),
}

# Что вообще можно выдавать через инвайты/карточку компании (помимо базы).
# admin/manageUsers/manageCompanies/global_admin и роли (type 1) — только global через /admin.
GRANTABLE_PERMS = ("viewDashboard", "viewReports", "viewOrders", "viewSeo", "manageFbsStocks")
PROTECTED_ITEMS = ("global_admin", "admin", "manageUsers", "manageCompanies")


async def get_active_company_roles(db: AsyncSession, user_id: int) -> list[str]:
    rows = (await db.execute(
        text("SELECT DISTINCT role FROM company_members WHERE user_id=:u AND status='active'"),
        {"u": user_id},
    )).all()
    return [r[0] for r in rows]


async def get_derived_perms(db: AsyncSession, user_id: int) -> set[str]:
    out: set[str] = set()
    for role in await get_active_company_roles(db, user_id):
        out.update(COMPANY_ROLE_PERMS.get(role, ()))
    return out


async def effective_perms(db: AsyncSession, user_id: int) -> set[str]:
    pp = await get_user_perms(db, user_id)
    return set(pp.get("all", []))


async def validate_grant(db: AsyncSession, granter_id: int, perms: list[str]) -> list[str]:
    # Проверка выдачи пермов: существуют, не защищены, выдающий ими владеет
    # (global_admin — всеми кроме PROTECTED). Возвращает очищенный список.
    clean = sorted({(p or "").strip() for p in (perms or []) if (p or "").strip()})
    if not clean:
        return []
    for p in clean:
        if p in PROTECTED_ITEMS:
            raise ValueError(f"permission '{p}' requires global_admin via /admin")
    placeholders = ",".join(f":p{i}" for i in range(len(clean)))
    rows = (await db.execute(
        text(f"SELECT name, type FROM auth_item WHERE name IN ({placeholders})"),
        {f"p{i}": v for i, v in enumerate(clean)},
    )).mappings().all()
    found = {r["name"]: r["type"] for r in rows}
    for p in clean:
        if p not in found:
            raise ValueError(f"unknown permission '{p}'")
        if found[p] == 1:
            raise ValueError(f"'{p}' is a role — roles are granted only via /admin")
    if await is_global_admin(db, granter_id):
        return clean
    mine = await effective_perms(db, granter_id)
    for p in clean:
        if p not in GRANTABLE_PERMS or p not in mine:
            raise ValueError(f"cannot grant '{p}' — not available to you")
    return clean


async def _existing_items(db: AsyncSession, perms: list[str]) -> list[str]:
    clean = sorted({(p or "").strip() for p in (perms or []) if (p or "").strip()})
    if not clean:
        return []
    placeholders = ",".join(f":p{i}" for i in range(len(clean)))
    rows = (await db.execute(
        text(f"SELECT name FROM auth_item WHERE name IN ({placeholders})"),
        {f"p{i}": v for i, v in enumerate(clean)},
    )).all()
    found = {r[0] for r in rows}
    unknown = [p for p in clean if p not in found]
    if unknown:
        raise ValueError(f"unknown permission '{unknown[0]}'")
    return clean


async def grant_perms(db: AsyncSession, user_id: int, perms: list[str]) -> list[str]:
    # Низкоуровневая выдача (проверку «можно ли» делает вызыватель через validate_grant
    # или global-гарды). INSERT IGNORE — повтор безопасен.
    clean = await _existing_items(db, perms)
    if not clean:
        return []
    now = int(time.time())
    placeholders = ",".join(f"(:n{i}, :u, :t)" for i in range(len(clean)))
    params: dict = {"u": str(user_id), "t": now}
    params.update({f"n{i}": v for i, v in enumerate(clean)})
    await db.execute(
        text(f"INSERT IGNORE INTO auth_assignment (item_name, user_id, created_at) VALUES {placeholders}"),
        params,
    )
    return clean


async def revoke_perms(db: AsyncSession, user_id: int, perms: list[str]) -> list[str]:
    clean = sorted({(p or "").strip() for p in (perms or []) if (p or "").strip()})
    if not clean:
        return []
    placeholders = ",".join(f":p{i}" for i in range(len(clean)))
    params: dict = {"u": str(user_id)}
    params.update({f"p{i}": v for i, v in enumerate(clean)})
    await db.execute(
        text(f"DELETE FROM auth_assignment WHERE user_id=:u AND item_name IN ({placeholders})"),
        params,
    )
    return clean


async def get_user_explicit_items(db: AsyncSession, user_id: int) -> list[dict]:
    rows = (await db.execute(
        text("SELECT a.item_name AS name, i.type AS type, i.description AS description "
             "FROM auth_assignment a LEFT JOIN auth_item i ON i.name=a.item_name "
             "WHERE a.user_id=:u ORDER BY a.item_name"),
        {"u": str(user_id)},
    )).mappings().all()
    return [dict(r) for r in rows]


async def is_global_admin(db: AsyncSession, user_id: int) -> bool:
    pp = await get_user_perms(db, user_id)
    return "global_admin" in pp["roles"] or "admin" in pp["roles"]


async def get_company_by_id(db: AsyncSession, company_id: int) -> dict | None:
    row = (await db.execute(
        text("SELECT id, name, abbreviation, inn FROM companies WHERE id=:id LIMIT 1"),
        {"id": company_id},
    )).mappings().first()
    return dict(row) if row else None


async def get_company_full(db: AsyncSession, company_id: int) -> dict | None:
    # Полная запись для формы редактирования (порт yii2 company/update).
    # Секреты (api_key, seo_openrouter_key) отдаём только менеджерам компании —
    # эндпоинт под require_company_admin, в списках их нет.
    row = (await db.execute(
        text("SELECT * FROM companies WHERE id=:id LIMIT 1"),
        {"id": company_id},
    )).mappings().first()
    if not row:
        return None
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


async def get_company_member(db: AsyncSession, company_id: int, user_id: int) -> dict | None:
    row = (await db.execute(
        text("""
            SELECT cm.role, cm.status, cm.invited_by
            FROM company_members cm
            WHERE cm.company_id=:company_id AND cm.user_id=:user_id
            LIMIT 1
        """),
        {"company_id": company_id, "user_id": user_id},
    )).mappings().first()
    return dict(row) if row else None


async def can_manage_company(db: AsyncSession, user_id: int, company_id: int) -> bool:
    if await is_global_admin(db, user_id):
        return True
    member = await get_company_member(db, company_id, user_id)
    return bool(member and member.get("status") == "active" and member.get("role") in ("owner", "admin"))


async def get_user_companies(db: AsyncSession, user_id: int) -> list[dict]:
    if await is_global_admin(db, user_id):
        rows = (await db.execute(
            text("SELECT id, name, abbreviation FROM companies WHERE is_active=1 ORDER BY id")
        )).mappings().all()
    else:
        rows = (await db.execute(
            text("""
                SELECT c.id, c.name, c.abbreviation
                FROM company_members cm
                JOIN companies c ON c.id=cm.company_id
                WHERE cm.user_id=:user_id AND cm.status='active' AND c.is_active=1
                ORDER BY c.id
            """),
            {"user_id": user_id},
        )).mappings().all()
    return [dict(r) for r in rows]


async def get_company_members(db: AsyncSession, company_id: int) -> list[dict]:
    rows = (await db.execute(
        text("""
            SELECT u.id, u.username, u.email, cm.role, cm.status, cm.invited_by
            FROM company_members cm
            JOIN `user` u ON u.id=cm.user_id
            WHERE cm.company_id=:company_id
            ORDER BY CASE cm.role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END, u.id
        """),
        {"company_id": company_id},
    )).mappings().all()
    out = [dict(r) for r in rows]
    if out:
        ids = [r["id"] for r in out]
        placeholders = ",".join(f":u{i}" for i in range(len(ids)))
        pr = (await db.execute(
            text(f"SELECT a.user_id AS uid, a.item_name AS name FROM auth_assignment a "
                 f"WHERE a.user_id IN ({placeholders})"),
            {f"u{i}": str(v) for i, v in enumerate(ids)},
        )).mappings().all()
        by_user: dict[int, list[str]] = {}
        for r in pr:
            by_user.setdefault(int(r["uid"]), []).append(r["name"])
        for r in out:
            r["perms"] = sorted(by_user.get(int(r["id"]), []))
    return out


async def upsert_company_member(
    db: AsyncSession,
    company_id: int,
    user_id: int,
    role: str,
    status: str,
    invited_by: int | None,
):
    if role not in ("owner", "admin", "member", "viewer"):
        raise ValueError("invalid member role")
    if status not in ("active", "blocked", "invited"):
        raise ValueError("invalid member status")
    await db.execute(text("""
        INSERT INTO company_members (company_id, user_id, role, status, invited_by, created_at, updated_at)
        VALUES (:company_id, :user_id, :role, :status, :invited_by, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
          role=VALUES(role),
          status=VALUES(status),
          invited_by=VALUES(invited_by),
          updated_at=NOW()
    """), {
        "company_id": company_id,
        "user_id": user_id,
        "role": role,
        "status": status,
        "invited_by": invited_by,
    })


async def update_company_member(
    db: AsyncSession,
    company_id: int,
    user_id: int,
    role: str,
    status: str,
):
    if role not in ("owner", "admin", "member", "viewer"):
        raise ValueError("invalid member role")
    if status not in ("active", "blocked", "invited"):
        raise ValueError("invalid member status")
    result = await db.execute(text("""
        UPDATE company_members
        SET role=:role, status=:status, updated_at=NOW()
        WHERE company_id=:company_id AND user_id=:user_id
    """), {"role": role, "status": status, "company_id": company_id, "user_id": user_id})
    if result.rowcount == 0:
        raise ValueError("member not found")


async def delete_company_member(db: AsyncSession, company_id: int, user_id: int):
    result = await db.execute(text("""
        DELETE FROM company_members
        WHERE company_id=:company_id AND user_id=:user_id
    """), {"company_id": company_id, "user_id": user_id})
    if result.rowcount == 0:
        raise ValueError("member not found")


async def create_company(
    db: AsyncSession,
    owner_id: int,
    name: str,
    abbreviation: str | None = None,
    inn: str | None = None,
    seo_model: str | None = None,
    seo_summary_model: str | None = None,
    seo_summary_max_tokens: int | None = None,
    seo_daily_limit: int | None = None,
    seo_desc_min: int | None = None,
    seo_desc_max: int | None = None,
    seo_anti_spam_days: int | None = None,
    seo_openrouter_key: str | None = None,
    seo_openrouter_referer: str | None = None,
    seo_openrouter_title: str | None = None,
    seo_prompt: str | None = None,
    seo_competitor_prompt: str | None = None,
    seo_summary_prompt: str | None = None,
) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("company name is required")

    await db.execute(text("""
        INSERT INTO companies (
          name, abbreviation, inn, api_key, seo_model, seo_summary_model, seo_summary_max_tokens,
          seo_daily_limit, seo_desc_min, seo_desc_max, seo_anti_spam_days, seo_openrouter_key,
          seo_openrouter_referer, seo_openrouter_title, seo_prompt, seo_competitor_prompt,
          seo_summary_prompt, is_active, fbs_deduct_enabled, fbs_deduct_test
        )
        VALUES (
          :name, :abbreviation, :inn, NULL, :seo_model, :seo_summary_model, :seo_summary_max_tokens,
          :seo_daily_limit, :seo_desc_min, :seo_desc_max, :seo_anti_spam_days, :seo_openrouter_key,
          :seo_openrouter_referer, :seo_openrouter_title, :seo_prompt, :seo_competitor_prompt,
          :seo_summary_prompt, 1, 0, 1
        )
    """), {
        "name": name,
        "abbreviation": abbreviation.strip() if abbreviation else None,
        "inn": inn.strip() if inn else None,
        "seo_model": seo_model,
        "seo_summary_model": seo_summary_model,
        "seo_summary_max_tokens": seo_summary_max_tokens,
        "seo_daily_limit": seo_daily_limit,
        "seo_desc_min": seo_desc_min,
        "seo_desc_max": seo_desc_max,
        "seo_anti_spam_days": seo_anti_spam_days,
        "seo_openrouter_key": seo_openrouter_key,
        "seo_openrouter_referer": seo_openrouter_referer,
        "seo_openrouter_title": seo_openrouter_title,
        "seo_prompt": seo_prompt,
        "seo_competitor_prompt": seo_competitor_prompt,
        "seo_summary_prompt": seo_summary_prompt,
    })

    company_id = (await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()
    await upsert_company_member(db, int(company_id), owner_id, "owner", "active", owner_id)
    return await get_company_by_id(db, int(company_id)) or {"id": int(company_id), "name": name}


COMPANY_UPDATE_FIELDS = (
    "name", "abbreviation", "inn", "api_key", "is_active",
    "fbs_deduct_enabled", "fbs_deduct_test",
    "seo_model", "seo_summary_model", "seo_summary_max_tokens",
    "seo_daily_limit", "seo_desc_min", "seo_desc_max", "seo_anti_spam_days",
    "seo_openrouter_key", "seo_openrouter_referer", "seo_openrouter_title",
    "seo_prompt", "seo_competitor_prompt", "seo_summary_prompt",
)

# Поля yii2 company/_form.php с ограниченным доступом (п.4 пользователя):
FBS_FIELDS = ("fbs_deduct_enabled", "fbs_deduct_test")
SEO_FIELDS = (
    "seo_model", "seo_summary_model", "seo_summary_max_tokens",
    "seo_daily_limit", "seo_desc_min", "seo_desc_max", "seo_anti_spam_days",
    "seo_openrouter_key", "seo_openrouter_referer", "seo_openrouter_title",
    "seo_prompt", "seo_competitor_prompt", "seo_summary_prompt",
)


async def update_company(db: AsyncSession, company_id: int, fields: dict) -> dict:
    # Белый список полей (как yii2 CompanyController update, но api_key/seo правят
    # только через этот метод — в public_company наружу они не отдаются).
    sets: dict = {}
    for k in COMPANY_UPDATE_FIELDS:
        if k in fields and fields[k] is not None:
            v = fields[k]
            sets[k] = v.strip() if isinstance(v, str) else v
    if "name" in sets and not sets["name"]:
        raise ValueError("company name is required")
    if sets.get("inn"):
        import re as _re
        if not _re.match(r"^\d{10,12}$", str(sets["inn"])):
            raise ValueError("inn must be 10 or 12 digits")
    if not sets:
        raise ValueError("nothing to update")
    cols = ", ".join(f"{k}=:{k}" for k in sets)
    result = await db.execute(
        text(f"UPDATE companies SET {cols}, updated_at=NOW() WHERE id=:id"),
        {**sets, "id": company_id},
    )
    if result.rowcount == 0:
        raise ValueError("company not found")
    company = await get_company_by_id(db, company_id)
    if not company:
        raise ValueError("company not found")
    return company


def _invite_payload(
    token_type: str,
    company_id: int | None,
    target_user_id: int | None,
    target_email: str | None,
    role: str | None,
    company_name: str | None,
    raw_token: str,
    expires_at: datetime,
    perms: list[str] | None = None,
) -> dict:
    return {
        "token": raw_token,
        "type": token_type,
        "company_id": company_id,
        "target_user_id": target_user_id,
        "target_email": normalize_email(target_email) if target_email else None,
        "role": role,
        "company_name": company_name.strip() if company_name else None,
        "perms": sorted(set(perms or [])),
        "iat": int(time.time()),
        "exp": int(expires_at.replace(tzinfo=timezone.utc).timestamp()),
    }


async def create_invite_token(
    db: AsyncSession,
    token_type: str,
    company_id: int | None = None,
    target_user_id: int | None = None,
    target_email: str | None = None,
    role: str | None = None,
    company_name: str | None = None,
    created_by: int | None = None,
    expires_at: datetime | None = None,
    expires_in_days: int = 7,
    perms: list[str] | None = None,
) -> str:
    if token_type not in ("company", "user"):
        raise ValueError("invalid token type")
    expires_at = expires_at or (_now_utc_naive() + timedelta(days=expires_in_days))
    raw_token = secrets.token_urlsafe(32)
    payload = _invite_payload(
        token_type=token_type,
        company_id=company_id,
        target_user_id=target_user_id,
        target_email=target_email,
        role=role,
        company_name=company_name,
        raw_token=raw_token,
        expires_at=expires_at,
        perms=perms,
    )
    token_ciphertext = _fernet().encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    await db.execute(text("""
        INSERT INTO auth_invite_tokens (
          token_ciphertext, token_type, company_id, target_user_id, target_email, role,
          company_name, expires_at, created_by
        )
        VALUES (:token_ciphertext, :token_type, :company_id, :target_user_id, :target_email, :role,
                :company_name, :expires_at, :created_by)
    """), {
        "token_ciphertext": token_ciphertext,
        "token_type": token_type,
        "company_id": company_id,
        "target_user_id": target_user_id,
        "target_email": normalize_email(target_email) if target_email else None,
        "role": role,
        "company_name": company_name.strip() if company_name else None,
        "expires_at": expires_at,
        "created_by": created_by,
    })
    return raw_token


async def resolve_invite_token(db: AsyncSession, raw_token: str) -> tuple[dict, dict]:
    if not raw_token:
        raise ValueError("invite_token is required")
    rows = (await db.execute(text("""
        SELECT id, token_ciphertext, expires_at, used_at
        FROM auth_invite_tokens
        WHERE used_at IS NULL AND expires_at > NOW()
    """))).mappings().all()

    for row in rows:
        try:
            payload = json.loads(_fernet().decrypt(row["token_ciphertext"].encode("utf-8")).decode("utf-8"))
        except InvalidToken:
            continue
        if payload.get("token") == raw_token:
            return dict(row), payload
    raise ValueError("invalid or expired invite token")


async def consume_invite_token(db: AsyncSession, token_id: int, user_id: int | None = None) -> bool:
    # used_by (миграция 20260915) — кто погасил токен, для колонки «Использовал» в /admin/invites.
    result = await db.execute(text("""
        UPDATE auth_invite_tokens
        SET used_at=NOW(), used_by=:uid
        WHERE id=:id AND used_at IS NULL AND expires_at > NOW()
    """), {"id": token_id, "uid": user_id})
    return bool(result.rowcount)


async def create_user_invite_token(
    db: AsyncSession,
    created_by: int,
    company_id: int,
    email: str,
    role: str = "member",
    expires_in_days: int = 7,
    perms: list[str] | None = None,
) -> str:
    user = await get_user_by_email(db, email)
    return await create_invite_token(
        db=db,
        token_type="user",
        company_id=company_id,
        target_user_id=user["id"] if user else None,
        target_email=email,
        role=role,
        created_by=created_by,
        expires_in_days=expires_in_days,
        perms=perms,
    )


async def create_company_invite_token(
    db: AsyncSession,
    created_by: int,
    company_name: str,
    abbreviation: str | None = None,
    inn: str | None = None,
    expires_in_days: int = 30,
) -> str:
    # Токен — разрешение на регистрацию с зарезервированным именем (вариант A, 2026-09-15).
    # Компанию НЕ предсоздаём: раньше тут создавался shell на global_admin, а register
    # создавал вторую компанию с тем же именем — оставался сирота. Компания создаётся
    # один раз в POST /api/auth/register, новый пользователь становится её owner.
    company_name = (company_name or "").strip()
    if not company_name:
        raise ValueError("company name is required")
    return await create_invite_token(
        db=db,
        token_type="company",
        company_id=None,
        target_email=None,
        role=None,
        company_name=company_name,
        created_by=created_by,
        expires_in_days=expires_in_days,
    )


def public_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {"id": user["id"], "username": user["username"], "email": user.get("email")}


def public_company(company: dict | None) -> dict | None:
    if not company:
        return None
    return {
        "id": company["id"],
        "name": company["name"],
        "abbreviation": company.get("abbreviation"),
        "inn": company.get("inn"),
    }


async def touch_login(db: AsyncSession, user_id: int, ip: str | None) -> None:
    try:
        await db.execute(
            text("UPDATE `user` SET last_login_at=:t, last_login_ip=:ip WHERE id=:i"),
            {"t": int(time.time()), "ip": ip, "i": user_id},
        )
        await db.commit()
    except Exception:
        await db.rollback()
