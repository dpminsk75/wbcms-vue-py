"""WB-токен компании: статус (из company_wb_tokens, без сети), проверка
(decode+ping+профиль продавца) и профиль.

Токен читаем сервером из companies.api_key — наружу сырой токен не отдаём.
POST /check принимает опциональный {"api_key"} — черновик из формы (проверить
до сохранения, пишется с is_active=0). Троттлинг живых проверок — 60с на компанию.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import require_admin, require_company_admin
from backend.services import wb_token_service as svc

router = APIRouter(prefix="/api/companies/{company_id}/wb-token", tags=["wb-token"])
expiring_router = APIRouter(prefix="/api/wb-tokens", tags=["wb-token"])

_last_check: dict[int, float] = {}
_last_profile: dict[int, float] = {}


async def _saved_token(db: AsyncSession, company_id: int) -> str | None:
    row = (await db.execute(
        text("SELECT api_key FROM companies WHERE id=:id LIMIT 1"),
        {"id": company_id},
    )).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="company not found")
    return row["api_key"] or None


def _row_to_status(row: dict) -> dict[str, Any]:
    """Строка company_wb_tokens -> тот же формат, что decode_token + ping."""
    try:
        stored_cats = json.loads(row["categories"]) if isinstance(row.get("categories"), str) else (row.get("categories") or [])
    except Exception:
        stored_cats = []
    in_set = set(stored_cats) if isinstance(stored_cats, list) else set()
    cats = [{k: c[k] for k in ("key", "bit", "letter", "name")} | {"in_token": c["key"] in in_set}
            for c in svc.CATEGORIES]
    try:
        ping = json.loads(row["ping"]) if isinstance(row.get("ping"), str) else row.get("ping")
    except Exception:
        ping = None
    exp_at = row.get("exp_at")
    if hasattr(exp_at, "isoformat"):
        exp_iso = exp_at.isoformat()
        days_left = int((exp_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() // 86400)
    else:
        exp_iso, days_left = None, None
    return {
        "has_token": True,
        "source": "saved",
        "valid": True,
        "token_id": row.get("wb_token_id"),
        "sid": row.get("sid"),
        "exp_at": exp_iso,
        "days_left": days_left,
        "expired": days_left is not None and days_left < 0,
        "s_mask": row.get("s_mask"),
        "is_test": bool(row.get("is_test")),
        "is_readonly": bool(row.get("is_readonly")),
        "token_type": row.get("token_type") or "unknown",
        "token_type_ru": svc.TOKEN_TYPES.get(row.get("token_type") or "unknown", "Неизвестный"),
        "categories": cats,
        "ping": ping,
        "checked_at": row["last_check_at"].isoformat() if hasattr(row.get("last_check_at"), "isoformat") else row.get("last_check_at"),
    }


def _row_to_profile(row: dict) -> dict[str, Any]:
    out = {"has_profile": True, "company_id": row.get("company_id")}
    for k in ("sid", "seller_name", "tin", "trademark", "rating", "reviews_count", "fetched_at", "last_error"):
        v = row.get(k)
        out[k] = v.isoformat() if hasattr(v, "isoformat") else v
    out["has_jam"] = None if row.get("has_jam") is None else bool(row.get("has_jam"))
    for k in ("seller_info", "jam", "tariffs"):
        v = row.get(k)
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                v = None
        out[k] = v
    return out


async def _active_row(db: AsyncSession, company_id: int) -> dict | None:
    try:
        row = (await db.execute(
            text("SELECT * FROM company_wb_tokens WHERE company_id=:c AND is_active=1 LIMIT 1"),
            {"c": company_id},
        )).mappings().first()
    except Exception:
        await db.rollback()
        return None  # таблицы ещё нет (миграция не применена) — fallback на decode
    return dict(row) if row else None


@router.get("/status")
async def wb_token_status(
    company_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_company_admin),
) -> dict[str, Any]:
    row = await _active_row(db, company_id)
    if row:
        return _row_to_status(row)
    raw = await _saved_token(db, company_id)
    if not raw:
        return {"has_token": False}
    out = svc.decode_token(raw)
    return {"has_token": True, "source": "saved", **out, "ping": None}


@router.post("/check")
async def wb_token_check(
    company_id: int = Path(..., ge=1),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_company_admin),
) -> dict[str, Any]:
    draft = ((payload or {}).get("api_key") or "").strip()
    saved_raw = await _saved_token(db, company_id)
    if draft:
        raw: str | None = draft
        # Черновик, совпадающий с сохранённым токеном, — это сохранённый (иначе
        # поле формы, подставляющее api_key при загрузке, вечно давало бы draft
        # и активная строка в company_wb_tokens никогда не появлялась бы).
        if saved_raw and hashlib.sha256(saved_raw.encode("utf-8")).hexdigest() == hashlib.sha256(draft.encode("utf-8")).hexdigest():
            source = "saved"
        else:
            source = "draft"
    else:
        raw = saved_raw
        source = "saved"
    if not raw:
        raise HTTPException(status_code=400, detail="no token: fill WB API key first")
    now = time.monotonic()
    if now - _last_check.get(company_id, 0.0) < svc.CHECK_THROTTLE_S:
        raise HTTPException(status_code=429, detail="check throttled: retry in a minute")
    _last_check[company_id] = now
    out = await svc.ping_token(raw, only_in_token=True)
    saved = await svc.save_check(db, company_id, raw, out, active=(source == "saved"))
    return {"has_token": True, "source": source, "db_saved": saved, **out}


def _resolve_raw(saved_raw: str | None, draft: str) -> tuple[str | None, str]:
    if draft:
        # Черновик, совпадающий с сохранённым токеном, — это сохранённый (иначе
        # поле формы, подставляющее api_key при загрузке, вечно давало бы draft
        # и активная строка в company_wb_tokens никогда не появлялась бы).
        if saved_raw and hashlib.sha256(saved_raw.encode("utf-8")).hexdigest() == hashlib.sha256(draft.encode("utf-8")).hexdigest():
            return draft, "saved"
        return draft, "draft"
    return saved_raw, "saved"


@router.post("/profile/refresh")
async def wb_token_profile_refresh(
    company_id: int = Path(..., ge=1),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_company_admin),
) -> dict[str, Any]:
    """Этап 2 проверки: профиль продавца (4 метода common-api с паузами, ~10-15с).
    Отдельно от /check, чтобы фронт показывал честный прогресс по этапам."""
    draft = ((payload or {}).get("api_key") or "").strip()
    saved_raw = await _saved_token(db, company_id)
    raw, source = _resolve_raw(saved_raw, draft)
    if not raw:
        raise HTTPException(status_code=400, detail="no token: fill WB API key first")
    now = time.monotonic()
    if now - _last_profile.get(company_id, 0.0) < svc.CHECK_THROTTLE_S:
        raise HTTPException(status_code=429, detail="profile refresh throttled: retry in a minute")
    _last_profile[company_id] = now
    dec = svc.decode_token(raw)
    if not dec.get("valid"):
        raise HTTPException(status_code=400, detail=dec.get("error") or "invalid token")
    profile = await svc.fetch_seller_profile(raw)
    profile_saved = await svc.save_profile(db, company_id, dec.get("sid"), profile)
    return {"profile": profile, "profile_saved": profile_saved, "source": source}


@router.get("/profile")
async def wb_token_profile(
    company_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_company_admin),
) -> dict[str, Any]:
    try:
        row = (await db.execute(
            text("SELECT * FROM company_wb_profile WHERE company_id=:c LIMIT 1"),
            {"c": company_id},
        )).mappings().first()
    except Exception:
        await db.rollback()
        return {"has_profile": False}
    if not row:
        return {"has_profile": False}
    return _row_to_profile(dict(row))


@expiring_router.get("/expiring")
async def wb_tokens_expiring(
    days: int = Query(default=14, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Активные токены с exp_at ближе days дней — для баннера глобального админа."""
    try:
        rows = (await db.execute(
            text("""
                SELECT t.company_id, c.name AS company_name, t.exp_at,
                       TIMESTAMPDIFF(DAY, NOW(), t.exp_at) AS days_left,
                       t.is_readonly, t.last_check_at
                FROM company_wb_tokens t
                JOIN companies c ON c.id=t.company_id
                WHERE t.is_active=1 AND t.exp_at IS NOT NULL
                  AND t.exp_at < NOW() + INTERVAL :days DAY
                ORDER BY t.exp_at
            """),
            {"days": days},
        )).mappings().all()
    except Exception:
        await db.rollback()
        return []  # таблицы ещё нет — пусто, не 500
    out = []
    for r in rows:
        d = dict(r)
        for k in ("exp_at", "last_check_at"):
            if hasattr(d.get(k), "isoformat"):
                d[k] = d[k].isoformat()
        d["is_readonly"] = bool(d.get("is_readonly"))
        out.append(d)
    return out
