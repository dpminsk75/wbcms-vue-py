"""Ext-токены (§10 md): несколько на компанию (на сотрудника/машину), отзыв по одному.

Сырой токен (`ext_...`) показываем один раз при выдаче, храним только sha256.
Сами /ext/* принимают только токен — он и есть доказательство, что выдавший имел viewSeo.
"""

import hashlib
import secrets

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TOKEN_PREFIX = "ext_"


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def list_tokens(db: AsyncSession, company_id: int) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT id, company_id, name, token_prefix, is_active, last_used_at, created_by, created_at
        FROM ext_tokens WHERE company_id=:c ORDER BY id
    """), {"c": company_id})).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("created_at", "last_used_at"):
            if hasattr(d.get(k), "isoformat"):
                d[k] = d[k].isoformat()
        d["is_active"] = bool(d.get("is_active"))
        out.append(d)
    return out


async def create_token(db: AsyncSession, company_id: int, name: str, created_by: int | None) -> dict:
    """Генерирует токен, пишет sha256, возвращает сырьё ОДИН раз (повторно не показываем)."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    name = (name or "").strip()[:100]
    await db.rollback()  # сбрасываем autobegin от deps/gates перед begin (как в companies.py)
    async with db.begin():
        await db.execute(text("""
            INSERT INTO ext_tokens (company_id, name, token_sha256, token_prefix, created_by)
            VALUES (:c, :n, :h, :p, :u)
        """), {"c": company_id, "n": name or "расширение",
               "h": _sha(raw), "p": raw[:9], "u": created_by})
        row = (await db.execute(text("""
            SELECT id, company_id, name, token_prefix, is_active, last_used_at, created_at
            FROM ext_tokens WHERE token_sha256=:h LIMIT 1
        """), {"h": _sha(raw)})).mappings().first()
    d = dict(row)
    for k in ("created_at", "last_used_at"):
        if hasattr(d.get(k), "isoformat"):
            d[k] = d[k].isoformat()
    d["is_active"] = True
    d["token"] = raw  # только сейчас; в списке его больше нет
    return d


async def revoke_token(db: AsyncSession, company_id: int, token_id: int) -> bool:
    await db.rollback()
    async with db.begin():
        r = await db.execute(text("""
            UPDATE ext_tokens SET is_active=0 WHERE id=:t AND company_id=:c AND is_active=1
        """), {"t": token_id, "c": company_id})
    return bool(r.rowcount)


async def lookup_token(db: AsyncSession, raw: str) -> dict | None:
    """Проверка Bearer из require_ext_token: только активные."""
    if not raw or not raw.startswith(TOKEN_PREFIX):
        return None
    try:
        row = (await db.execute(text("""
            SELECT id, company_id, name FROM ext_tokens
            WHERE token_sha256=:h AND is_active=1 LIMIT 1
        """), {"h": _sha(raw.strip())})).mappings().first()
    except Exception:
        await db.rollback()
        raise
    return dict(row) if row else None


async def touch_token(db: AsyncSession, token_id: int) -> None:
    try:
        await db.execute(text("""
            UPDATE ext_tokens SET last_used_at=NOW() WHERE id=:t
        """), {"t": token_id})
        await db.commit()
    except Exception:
        await db.rollback()
