"""Capture «текущей страницы» (§8 плана 2026-10-20): контент конкурента без привязок.

Пишем ТОЛЬКО:
- `wb_competitor_details`         — контент, один на nm (UNIQUE nm_id), общий для всех компаний;
- `wb_competitor_capture`         — видимость nm × company (m:n), кто первым/последним видел;
- `wb_competitor_details_history` — снимок при новом content_hash (дедуп по md5, без ретеншна);
- `wb_enrich_queue`                — только `need_update` → `done` (контент уже обновлён).

НЕ трогаем: `wb_competitor_cards`, `wb_competitor_analysis` — привязка только вручную
на /competitor/captured (§8.5). В `wb_enrich_queue` закрываем только `need_update`:
успешный capture уже обновил контент, повторный обход не нужен.

Правила:
- своя карточка (`wbcards.company_id` = наша или NULL-легаси) → skip `own_card`, если нет `allow_own`;
- свежесть 24 ч → skip `fresh`, если нет `force`;
- `recommendations` / `characteristics` пустыми не затираем;
- `first_collected_at` / `captured_company_id` / `captured_by` — только при первой вставке.
"""

import hashlib
import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

FRESH_HOURS = 24


def _norm_chars(raw) -> str:
    """Характеристики в канонической строке JSON.

    MySQL отдаёт JSON-колонку нормализованной (ключи объектов отсортированы), Python — нет.
    Приводим к одному виду (sort_keys), чтобы хэш контента совпадал на всех путях записи
    (capture / enrich) и история не плодила дубли снимков.
    """
    val = raw
    if isinstance(val, (bytes, bytearray)):
        val = val.decode("utf-8", "replace")
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return "[]"
        try:
            val = json.loads(s)
        except (TypeError, ValueError):
            return s
    try:
        return json.dumps(val or [], ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return "[]"


def content_hash(title: str, description: str, characteristics: str,
                 price: str, old_price: str) -> str:
    """md5 от значимых полей контента (порядок фиксирован, json — стабильный)."""
    payload = json.dumps(
        [title or "", description or "", _norm_chars(characteristics), price or "", old_price or ""],
        ensure_ascii=False,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _json_list(raw) -> str:
    return json.dumps(raw or [], ensure_ascii=False)


def _cnt(raw) -> int:
    return len(raw) if isinstance(raw, list) else 0


async def capture(db: AsyncSession, company_id: int, user_id: int | None, payload: dict) -> dict:
    """Сохранить карточку, открытую в браузере. Возвращает {skipped} или {ok}.

    Raises ValueError на кривой payload (роутер отдаёт 400).
    """
    try:
        nm_id = int((payload or {}).get("nm_id") or 0)
    except (TypeError, ValueError):
        raise ValueError("bad nm_id")
    if nm_id <= 0:
        raise ValueError("nm_id required")

    allow_own = bool(payload.get("allow_own"))
    force = bool(payload.get("force"))
    explicit = bool(payload.get("explicit"))  # явный клик: снимает is_hidden

    # 1. Своя ли карточка? (PK wbcards = nmID; company_id NULL — легаси, считаем своей)
    own_row = (await db.execute(text("""
        SELECT company_id FROM wbcards WHERE nmID=:n LIMIT 1
    """), {"n": nm_id})).first()
    is_own = bool(own_row) and (own_row[0] is None or int(own_row[0]) == int(company_id))
    if is_own and not allow_own:
        return {"skipped": True, "reason": "own_card", "nm_id": nm_id, "is_own": True}

    # 2. Свежесть 24 ч (force обходит)
    existing = (await db.execute(text("""
        SELECT collected_at FROM wb_competitor_details WHERE nm_id=:n
    """), {"n": nm_id})).mappings().first()
    age_h = None
    if existing and existing["collected_at"]:
        try:
            age_h = round((datetime.now() - existing["collected_at"]).total_seconds() / 3600, 1)
        except TypeError:
            age_h = None
    if existing and not force and age_h is not None and age_h < FRESH_HOURS:
        if explicit:
            # Явный клик возвращает карточку из «скрытых», даже если контент свежий.
            await db.execute(text("""
                INSERT INTO wb_competitor_capture
                  (nm_id, company_id, is_own, is_hidden, first_seen_by, last_seen_by)
                VALUES (:n, :cid, :own, 0, :uid, :uid)
                ON DUPLICATE KEY UPDATE
                  last_seen_at=NOW(), last_seen_by=:uid, is_own=:own, is_hidden=0
            """), {"n": nm_id, "cid": company_id, "uid": user_id, "own": 1 if is_own else 0})
        # Контент уже свежий — назначенное обновление считаем выполненным.
        await db.execute(text("""
            UPDATE wb_enrich_queue SET status='done', processed_at=NOW()
            WHERE nm_id=:n AND status='need_update'
        """), {"n": nm_id})
        await db.commit()
        return {"skipped": True, "reason": "fresh", "nm_id": nm_id, "age_h": age_h,
                "collected_at": _iso(existing["collected_at"]), "is_own": is_own}

    # 3. Нормализация payload
    title = str(payload.get("title") or "")[:500]
    description = str(payload.get("description") or "")
    chars_raw = payload.get("characteristics") or []
    chars = _json_list(chars_raw)
    recs = _json_list(payload.get("recommendations"))
    images = _json_list(payload.get("images"))
    price = str(payload.get("price") or "")[:50]
    old_price = str(payload.get("old_price") or "")[:50]
    brand = str(payload.get("brand") or "")[:255]
    seller = str(payload.get("seller") or "")[:255]
    url = str(payload.get("url") or "")[:500]
    subject = str(payload.get("subject_name") or "")[:255]

    h = content_hash(title, description, chars, price, old_price)

    params = {
        "n": nm_id, "t": title, "d": description, "recs": recs, "u": url,
        "b": brand, "s": seller, "p": price, "o": old_price, "img": images,
        "chars": chars, "subj": subject, "cid": company_id, "uid": user_id,
        "own": 1 if is_own else 0, "exp": 1 if explicit else 0,
    }

    await db.rollback()
    async with db.begin():
        # 4. Контент: один на nm, пустым не затираем.
        # SELECT+UPDATE/INSERT, а не ON DUPLICATE KEY: у wb_competitor_details
        # уникальность nm_id не гарантирована миграцией (так же пишет /api/ext/result).
        row = (await db.execute(text("""
            SELECT id FROM wb_competitor_details WHERE nm_id=:n LIMIT 1
        """), {"n": nm_id})).first()
        if row:
            await db.execute(text("""
                UPDATE wb_competitor_details SET
                  title=IF(:t='', title, :t),
                  description=IF(:d='', description, :d),
                  recommendations=IF(:recs='[]', recommendations, :recs),
                  url=IF(:u='', url, :u),
                  brand=IF(:b='', brand, :b),
                  seller=IF(:s='', seller, :s),
                  price=IF(:p='', price, :p),
                  old_price=IF(:o='', old_price, :o),
                  images=IF(:img='[]', images, :img),
                  characteristics=IF(:chars='[]', characteristics, :chars),
                  subject_name=IF(:subj='', subject_name, :subj),
                  collected_at=NOW()
                WHERE id=:id
            """), {**params, "id": row[0]})
        else:
            await db.execute(text("""
                INSERT INTO wb_competitor_details
                  (nm_id, title, description, recommendations, url, brand, seller, price, old_price, images,
                   characteristics, subject_name, collected_at, first_collected_at,
                   captured_company_id, captured_by)
                VALUES (:n, :t, :d, :recs, :u, :b, :s, :p, :o, :img, :chars, :subj,
                        NOW(), NOW(), :cid, :uid)
            """), params)

        # 5. Видимость по компании (m:n). Явный клик возвращает скрытую карточку.
        await db.execute(text("""
            INSERT INTO wb_competitor_capture
              (nm_id, company_id, is_own, is_hidden, first_seen_by, last_seen_by)
            VALUES (:n, :cid, :own, 0, :uid, :uid)
            ON DUPLICATE KEY UPDATE
              last_seen_at=NOW(),
              last_seen_by=:uid,
              is_own=:own,
              is_hidden=IF(:exp=1, 0, is_hidden)
        """), params)

        # 6. История: только при новом content_hash
        last = (await db.execute(text("""
            SELECT content_hash FROM wb_competitor_details_history
            WHERE nm_id=:n ORDER BY id DESC LIMIT 1
        """), {"n": nm_id})).first()
        history = "same"
        if not last or last[0] != h:
            await db.execute(text("""
                INSERT INTO wb_competitor_details_history
                  (nm_id, title, description, characteristics, brand, seller, price, old_price,
                   images, content_hash, captured_company_id, captured_by, source)
                VALUES (:n, :t, :d, :chars, :b, :s, :p, :o, :img, :h, :cid, :uid, 'capture')
            """), {**params, "h": h})
            history = "inserted"

        # Успешный capture обновил контент — закрываем назначенное обновление.
        await db.execute(text("""
            UPDATE wb_enrich_queue SET status='done', processed_at=NOW()
            WHERE nm_id=:n AND status='need_update'
        """), {"n": nm_id})

    return {
        "ok": True, "skipped": False, "nm_id": nm_id, "is_own": is_own,
        "content_hash": h, "history": history,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "desc_len": len(description), "chars_cnt": _cnt(chars_raw),
    }
