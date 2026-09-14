"""Auth поверх прод-таблиц Yii2: `user` + `auth_assignment` + `auth_item_child`.

Yii2 хранит bcrypt `$2y$`, python `bcrypt` понимает `$2b$` — конвертим префикс.
`auth_assignment.user_id` — varchar, сравниваем как строку (как m260828_000001:139).
"""
import os
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGO = "HS256"
EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "720"))  # 12ч


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


async def get_user_by_username(db: AsyncSession, username: str) -> dict | None:
    q = text("SELECT id, username, email, password_hash, blocked_at FROM `user` WHERE username=:u LIMIT 1")
    r = (await db.execute(q, {"u": username})).mappings().first()
    return dict(r) if r else None


async def get_user_by_id(db: AsyncSession, user_id: int) -> dict | None:
    q = text("SELECT id, username, email, blocked_at FROM `user` WHERE id=:i LIMIT 1")
    r = (await db.execute(q, {"i": user_id})).mappings().first()
    return dict(r) if r else None


async def get_user_perms(db: AsyncSession, user_id: int) -> dict:
    """Возвращает {roles, perms, all} — all = roles+perms с раскрытием иерархии auth_item_child."""
    rows = (await db.execute(
        text("SELECT item_name FROM auth_assignment WHERE user_id=:u"), {"u": str(user_id)}
    )).all()
    assigned = [r[0] for r in rows]
    all_names: set[str] = set(assigned)
    frontier = list(assigned)
    # BFS вниз по иерархии admin->manager->viewer->perms (глубина маленькая, 10 итераций с запасом)
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
    # роли = auth_item.type=1, остальное — пермишены (если таблица пуста — считаем всё пермишенами)
    try:
        types = (await db.execute(text("SELECT name, type FROM auth_item"))).all()
        tmap = {n: t for n, t in types}
        roles = sorted(n for n in all_names if tmap.get(n) == 1)
        perms = sorted(n for n in all_names if tmap.get(n) != 1)
    except Exception:
        roles = sorted(assigned)
        perms = sorted(all_names - set(assigned))
    return {"roles": roles, "perms": perms, "all": sorted(all_names)}


async def touch_login(db: AsyncSession, user_id: int, ip: str | None):
    try:
        await db.execute(
            text("UPDATE `user` SET last_login_at=:t, last_login_ip=:ip WHERE id=:i"),
            {"t": int(time.time()), "ip": ip, "i": user_id},
        )
        await db.commit()
    except Exception:
        await db.rollback()
