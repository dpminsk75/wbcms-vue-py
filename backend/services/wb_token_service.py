"""WB API token: decode (без секрета) + ping-карта категорий.

JWT WB — RFC 7519, публичные поля: id, s (битмаска), sid, exp.
Биты s: 0 — песочница, 1 — Контент, 2 — Аналитика, 3 — Цены и скидки,
4 — Маркетплейс, 5 — Статистика, 6 — Продвижение, 7 — Вопросы и отзывы,
8 — Рекомендации, 9 — Чат с покупателями, 10 — Поставки, 11 — Возвраты,
12 — Документы, 13 — Финансы, 16 — Пользователи, 30 — только чтение.
Тип токена — по полям payload: acc=1 без for + t=false → базовый;
acc=2 без for + t=true → тестовый; acc=3 for=self → персональный;
acc=4 for=asid:{ID} → сервисный.
Подписи WB у нас нет — декодируем с verify_signature=False и читаем exp вручную.
Ping — только живым GET /ping на домен категории (urllib из stdlib, новых
зависимостей нет). Сырой токен не логируем.
"""

import asyncio
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TIMEOUT_S = 6
CHECK_THROTTLE_S = 60

TOKEN_TYPES = {
    "basic": "Базовый",
    "test": "Тестовый",
    "personal": "Персональный",
    "service": "Сервисный",
    "unknown": "Неизвестный",
}


def detect_token_type(payload: dict) -> tuple[str, str | None]:
    """Тип токена по acc/for/t. Возвращает (key, ru)."""
    acc = payload.get("acc")
    for_value = payload.get("for")
    t = payload.get("t")
    try:
        acc = int(acc) if acc is not None else None
    except (TypeError, ValueError):
        acc = None
    if t is True or acc == 2:
        return "test", TOKEN_TYPES["test"]
    if acc == 1 and not for_value:
        return "basic", TOKEN_TYPES["basic"]
    if acc == 3 and for_value == "self":
        return "personal", TOKEN_TYPES["personal"]
    if acc == 4 and isinstance(for_value, str) and for_value.startswith("asid:"):
        return "service", TOKEN_TYPES["service"]
    return "unknown", TOKEN_TYPES["unknown"]

CATEGORIES: list[dict] = [
    {"key": "content", "bit": 1, "letter": "К", "name": "Контент",
     "ping": "https://content-api.wildberries.ru/ping"},
    {"key": "analytics", "bit": 2, "letter": "А", "name": "Аналитика",
     "ping": "https://seller-analytics-api.wildberries.ru/ping"},
    {"key": "prices", "bit": 3, "letter": "Ц", "name": "Цены и скидки",
     "ping": "https://discounts-prices-api.wildberries.ru/ping"},
    {"key": "marketplace", "bit": 4, "letter": "М", "name": "Маркетплейс",
     "ping": "https://marketplace-api.wildberries.ru/ping"},
    {"key": "statistics", "bit": 5, "letter": "С", "name": "Статистика",
     "ping": "https://statistics-api.wildberries.ru/ping"},
    {"key": "promotion", "bit": 6, "letter": "П", "name": "Продвижение",
     "ping": "https://advert-api.wildberries.ru/ping"},
    {"key": "feedbacks", "bit": 7, "letter": "В", "name": "Вопросы и отзывы",
     "ping": "https://feedbacks-api.wildberries.ru/ping"},
    {"key": "recommendations", "bit": 8, "letter": "Р", "name": "Рекомендации",
     "ping": "https://recommend-api.wildberries.ru/ping"},
    {"key": "chat", "bit": 9, "letter": "Ч", "name": "Чат с покупателями",
     "ping": "https://buyer-chat-api.wildberries.ru/ping"},
    {"key": "supplies", "bit": 10, "letter": "Пс", "name": "Поставки",
     "ping": "https://supplies-api.wildberries.ru/ping"},
    {"key": "returns", "bit": 11, "letter": "Вз", "name": "Возвраты покупателями",
     "ping": "https://returns-api.wildberries.ru/ping"},
    {"key": "documents", "bit": 12, "letter": "Д", "name": "Документы",
     "ping": "https://documents-api.wildberries.ru/ping"},
    {"key": "finance", "bit": 13, "letter": "Ф", "name": "Финансы",
     "ping": "https://finance-api.wildberries.ru/ping"},
    {"key": "users", "bit": 16, "letter": "Пл", "name": "Пользователи",
     "ping": "https://user-management-api.wildberries.ru/ping"},
]


def decode_token(raw: str) -> dict:
    """Только разбор payload. Не ходит в сеть. Не бросает исключений наружу."""
    token = (raw or "").strip()
    if not token or token.count(".") != 2:
        return {"valid": False, "error": "not a JWT (need 3 parts)"}
    try:
        payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
    except Exception as exc:
        return {"valid": False, "error": f"jwt decode failed: {type(exc).__name__}"}
    if not isinstance(payload, dict):
        return {"valid": False, "error": "jwt payload is not an object"}
    try:
        s_mask = int(payload.get("s", 0))
    except (TypeError, ValueError):
        return {"valid": False, "error": "field 's' is not an int"}
    exp = payload.get("exp")
    exp_at = None
    days_left = None
    try:
        exp_at = datetime.fromtimestamp(int(exp), tz=timezone.utc) if exp is not None else None
    except (TypeError, ValueError):
        exp_at = None
    if exp_at is not None:
        days_left = int((exp_at - datetime.now(timezone.utc)).total_seconds() // 86400)
    cats = [
        {**c, "in_token": bool(s_mask & (1 << c["bit"]))}
        for c in CATEGORIES
    ]
    token_type, token_type_ru = detect_token_type(payload)
    return {
        "valid": True,
        "token_id": payload.get("id"),
        "sid": payload.get("sid"),
        "exp_at": exp_at.isoformat() if exp_at else None,
        "days_left": days_left,
        "expired": days_left is not None and days_left < 0,
        "s_mask": s_mask,
        "is_test": bool(s_mask & 1),
        "is_readonly": bool(s_mask & (1 << 30)),
        "token_type": token_type,
        "token_type_ru": token_type_ru,
        "acc": payload.get("acc"),
        "for": payload.get("for"),
        "categories": [{k: c[k] for k in ("key", "bit", "letter", "name", "in_token")} for c in cats],
    }


def _ping_one(url: str, token: str, timeout: int = TIMEOUT_S) -> dict:
    t0 = time.monotonic()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"http": int(resp.status), "ok": 200 <= int(resp.status) < 300,
                    "ms": int((time.monotonic() - t0) * 1000)}
    except urllib.error.HTTPError as exc:
        ms = int((time.monotonic() - t0) * 1000)
        out: dict = {"http": int(exc.code), "ok": False, "ms": ms}
        if int(exc.code) == 403:
            try:
                body = exc.read(300).decode("utf-8", "replace").lower()
            except Exception:
                body = ""
            out["no_jam"] = ("jam" in body or "джем" in body)
        return out
    except Exception as exc:
        return {"http": 0, "ok": False,
                "ms": int((time.monotonic() - t0) * 1000),
                "error": type(exc).__name__}


async def ping_token(raw: str, only_in_token: bool = True) -> dict:
    """Параллельный ping по доменам (лимит WB — на хост, хосты разные).
    only_in_token=True — не дёргаем категории, которых нет в s."""
    token = (raw or "").strip()
    status = decode_token(token)
    if not status.get("valid"):
        return {"valid": False, "error": status.get("error")}
    targets = [c for c in CATEGORIES
               if (not only_in_token or (status["s_mask"] & (1 << c["bit"])))]
    results = await asyncio.gather(*[
        asyncio.to_thread(_ping_one, c["ping"], token) for c in targets
    ])
    ping = {c["key"]: r for c, r in zip(targets, results)}
    for c in CATEGORIES:
        if c["key"] not in ping:
            ping[c["key"]] = {"http": None, "ok": False, "ms": None, "skipped": True}
    return {**status, "ping": ping,
            "checked_at": datetime.now(timezone.utc).isoformat()}


async def save_check(db: AsyncSession, company_id: int, raw: str, out: dict, active: bool) -> bool:
    """UPSERT результата проверки в company_wb_tokens. False — нечего/некуда писать
    (невалидный токен, нет таблицы). Используется и роутером, и daily-скриптом."""
    if not out.get("valid"):
        return False
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    exp_at = None
    try:
        exp_at = datetime.fromisoformat(out["exp_at"]) if out.get("exp_at") else None
    except ValueError:
        exp_at = None
    cats = json.dumps([c["key"] for c in (out.get("categories") or []) if c.get("in_token")], ensure_ascii=False)
    ping = json.dumps(out.get("ping"), ensure_ascii=False) if out.get("ping") else None
    try:
        await db.rollback()  # сбрасываем autobegin от deps перед begin (как в companies.py)
        async with db.begin():
            if active:
                await db.execute(
                    text("UPDATE company_wb_tokens SET is_active=0 WHERE company_id=:c"),
                    {"c": company_id},
                )
            else:
                await db.execute(
                    text("UPDATE company_wb_tokens SET is_active=0 WHERE company_id=:c AND token_sha256=:h"),
                    {"c": company_id, "h": digest},
                )
            await db.execute(text("""
                INSERT INTO company_wb_tokens (
                  company_id, wb_token_id, sid, token_sha256, exp_at, days_left, s_mask,
                  is_test, is_readonly, token_type, categories, ping, last_check_at, last_error, is_active
                )
                VALUES (:c, :tid, :sid, :h, :exp, :days, :s, :t, :ro, :tt, :cats, :ping, NOW(), :err, :active)
                ON DUPLICATE KEY UPDATE
                  wb_token_id=VALUES(wb_token_id), sid=VALUES(sid), exp_at=VALUES(exp_at),
                  days_left=VALUES(days_left), s_mask=VALUES(s_mask), is_test=VALUES(is_test),
                  is_readonly=VALUES(is_readonly), token_type=VALUES(token_type),
                  categories=VALUES(categories), ping=VALUES(ping),
                  last_check_at=NOW(), last_error=VALUES(last_error), is_active=VALUES(is_active),
                  updated_at=NOW()
            """), {
                "c": company_id,
                "tid": out.get("token_id"),
                "sid": out.get("sid"),
                "h": digest,
                "exp": exp_at,
                "days": out.get("days_left"),
                "s": out.get("s_mask"),
                "t": 1 if out.get("is_test") else 0,
                "ro": 1 if out.get("is_readonly") else 0,
                "tt": out.get("token_type"),
                "cats": cats,
                "ping": ping,
                "err": out.get("error"),
                "active": 1 if active else 0,
            })
    except Exception:
        await db.rollback()
        return False
    return True


COMMON_API = "https://common-api.wildberries.ru"
# Пути подтверждены живым ретестом 2026-09-18:
# - rating — ТОЛЬКО https://feedbacks-api.wildberries.ru/api/common/v1/rating -> {feedbackCount, valuation};
# - subscriptions/tariffs — https://common-api.wildberries.ru/api/common/v1/*, но строго сервисный
#   токен (персональный -> 403). Пока отключаем — вернём, когда будет сервисный токен.
PROFILE_URLS = {
    "seller_info": f"{COMMON_API}/api/v1/seller-info",
    "rating": "https://feedbacks-api.wildberries.ru/api/common/v1/rating",
    "subscriptions": f"{COMMON_API}/api/common/v1/subscriptions",
    "tariffs": f"{COMMON_API}/api/common/v1/tariff-constructor/options",
}
PROFILE_DISABLED = {"rating", "subscriptions", "tariffs"}
PROFILE_TIMEOUT_S = 8
PROFILE_PAUSE_S = 2  # пауза между методами (лимиты 1 запр/мин на каждый)


def _get_json(url: str, token: str, timeout: int = PROFILE_TIMEOUT_S) -> dict:
    """Один GET к common-api. Возвращает {http, data, empty, error}."""
    t0 = time.monotonic()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(1_000_000).decode("utf-8", "replace")
            ms = int((time.monotonic() - t0) * 1000)
            if not body.strip():
                return {"http": int(resp.status), "data": None, "empty": True, "ms": ms}
            try:
                return {"http": int(resp.status), "data": json.loads(body), "empty": False, "ms": ms}
            except ValueError:
                return {"http": int(resp.status), "data": None, "empty": False, "ms": ms,
                        "error": "non-json response"}
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(500).decode("utf-8", "replace")
        except Exception:
            body = ""
        out: dict = {"http": int(exc.code), "data": None, "empty": False,
                     "ms": int((time.monotonic() - t0) * 1000)}
        snippet = " ".join(body.split())[:200]
        if body.strip():
            try:
                out["data"] = json.loads(body)
            except ValueError:
                pass
            # WB отдаёт application/problem+json {title,detail,...} — тащим detail в диагностику
            detail = ""
            if isinstance(out.get("data"), dict):
                detail = str(out["data"].get("detail") or out["data"].get("title") or "")
            out["error"] = (detail or snippet)[:200]
        return out
    except Exception as exc:
        return {"http": 0, "data": None, "empty": False,
                "ms": int((time.monotonic() - t0) * 1000), "error": type(exc).__name__}


def _num(data: object, *keys: str) -> float | int | None:
    if isinstance(data, dict):
        for k in keys:
            v = data.get(k)
            if isinstance(v, (int, float)):
                return v
    return None


async def fetch_seller_profile(raw: str) -> dict:
    """Профиль продавца: seller-info + rating + subscriptions(Джем) + tariff-constructor.
    Токен любой категории. 429/403 по отдельному методу — поле null, добьёт daily-скрипт."""
    token = (raw or "").strip()
    got: dict[str, dict] = {}
    for key in ("seller_info", "rating", "subscriptions", "tariffs"):
        if key in PROFILE_DISABLED:
            got[key] = {"http": None, "data": None, "empty": False, "ms": None, "skipped": True}
            continue
        got[key] = await asyncio.to_thread(_get_json, PROFILE_URLS[key], token)
        await asyncio.sleep(PROFILE_PAUSE_S)
    errors = {}
    for k, v in got.items():
        if v.get("skipped") or v.get("http") == 200:
            continue
        err = f"{k}:{v.get('http')}"
        if v.get("error"):
            err += f":{v['error'][:120]}"
        errors[k] = err

    def _ok_data(key: str) -> Any:
        v = got[key]
        return v.get("data") if v.get("http") == 200 else None

    seller_info = _ok_data("seller_info")
    seller_info = seller_info if isinstance(seller_info, dict) else None
    rating_data = _ok_data("rating")
    subs = got["subscriptions"]
    tariffs = _ok_data("tariffs")
    return {
        "seller_info": seller_info,
        "seller_name": (seller_info or {}).get("name") or (seller_info or {}).get("sellerName"),
        "rating": _num(rating_data, "valuation", "rating", "value", "score"),
        "reviews_count": _num(rating_data, "feedbackCount", "reviewsCount", "reviewCount", "feedbacksCount"),
        # Пустой 200 по subscriptions = Джема не было никогда; непустой = был/есть (даты в jam).
        "has_jam": (not subs.get("empty")) if subs.get("http") == 200 else None,
        "jam": subs.get("data"),
        "tariffs": tariffs if isinstance(tariffs, dict) else None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "last_error": (", ".join(f"{v}" for v in errors.values()) or None),
    }


async def save_profile(db: AsyncSession, company_id: int, sid: str | None, prof: dict) -> bool:
    """UPSERT company_wb_profile. False — некуда писать (нет таблицы)."""
    info = prof.get("seller_info") if isinstance(prof.get("seller_info"), dict) else {}
    try:
        await db.rollback()
        async with db.begin():
            await db.execute(text("""
                INSERT INTO company_wb_profile (
                  company_id, sid, seller_name, tin, trademark, seller_info, rating, reviews_count,
                  has_jam, jam, tariffs, fetched_at, last_error
                )
                VALUES (:c, :sid, :name, :tin, :tm, :info, :rating, :rc, :jam_flag, :jam, :tariffs, NOW(), :err)
                ON DUPLICATE KEY UPDATE
                  sid=VALUES(sid), seller_name=VALUES(seller_name), tin=VALUES(tin),
                  trademark=VALUES(trademark), seller_info=VALUES(seller_info),
                  rating=VALUES(rating), reviews_count=VALUES(reviews_count),
                  has_jam=VALUES(has_jam), jam=VALUES(jam), tariffs=VALUES(tariffs),
                  fetched_at=NOW(), last_error=VALUES(last_error)
            """), {
                "c": company_id,
                "sid": sid,
                "name": prof.get("seller_name"),
                "tin": info.get("tin"),
                "tm": info.get("tradeMark"),
                "info": json.dumps(prof.get("seller_info"), ensure_ascii=False) if prof.get("seller_info") else None,
                "rating": prof.get("rating"),
                "rc": prof.get("reviews_count"),
                "jam_flag": (None if prof.get("has_jam") is None else (1 if prof.get("has_jam") else 0)),
                "jam": json.dumps(prof.get("jam"), ensure_ascii=False) if prof.get("jam") else None,
                "tariffs": json.dumps(prof.get("tariffs"), ensure_ascii=False) if prof.get("tariffs") else None,
                "err": prof.get("last_error"),
            })
    except Exception:
        await db.rollback()
        return False
    return True
