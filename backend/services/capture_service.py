"""Capture «текущей страницы» (§8 плана 2026-10-20): контент конкурента без привязок.

Пишем ТОЛЬКО:
- `wb_competitor_details`         — контент, один на nm (UNIQUE nm_id), общий для всех компаний;
- `wb_competitor_capture`         — видимость nm × company (m:n), кто первым/последним видел;
- `wb_competitor_details_history` — снимок при новом content_hash (дедуп по md5, без ретеншна);
- `wb_enrich_queue`                — только `need_update` → `done` (контент уже обновлён).

НЕ трогаем: `wb_competitor_cards`, `wb_competitor_analysis` — привязка только вручную
на /competitor/captured (§8.5). В `wb_enrich_queue` закрываем только `need_update`:
успешный capture уже обновил контент, повторный обход не нужен.

Два режима:
- `partial` — фоновое НАБЛЮДЕНИЕ (человек сам открыл карточку): пишем то, что уже видно;
  обновляем изменяемые поля (цена, рейтинг, бейджи…), контент — только если он непустой;
  `full_collected_at` НЕ двигаем (пассив не должен блокировать очередь) и TTL 24 ч НЕ применяем;
- обычный — полный сбор (кнопка «Собрать», либо авто-fallback после 403):
  двигает `full_collected_at`, TTL 24 ч считается по нему.

Правила:
- своя карточка (`wbcards.company_id` = наша или NULL-легаси) → skip `own_card`, если нет `allow_own`;
- `recommendations` / `characteristics` / `description` пустыми не затираем;
- `first_collected_at` / `captured_company_id` / `captured_by` — только при первой вставке.
"""

import hashlib
import json
import re
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

FRESH_HOURS = 24


def _norm_chars(raw) -> str:
    """Характеристики в канонической строке JSON.

    MySQL отдаёт JSON-колонку нормализованную (ключи объектов отсортированы), Python — нет.
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
                 price, old_price) -> str:
    """md5 от значимых полей контента (порядок фиксирован, json — стабильный)."""
    payload = json.dumps(
        [title or "", description or "", _norm_chars(characteristics),
         str(price or ""), str(old_price or "")],
        ensure_ascii=False,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _json_list(raw) -> str:
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s == "null":
            return "[]"
        try:
            json.loads(s)
            return s
        except (TypeError, ValueError):
            return "[]"
    return json.dumps(raw or [], ensure_ascii=False)


def _cnt(raw) -> int:
    return len(raw) if isinstance(raw, list) else 0


def _norm_phrase(raw) -> str:
    """Нормализация фразы: нижний регистр, дефисы/подчёркивания -> пробелы, один пробел.

    WB отдаёт одну и ту же фразу двумя способами (с дефисами в URL страницы и
    с пробелами в query= внутренних API) — без нормализации это две разные фразы.
    """
    s = str(raw or "").lower()
    s = re.sub(r"[-_]+", " ", s)
    s = " ".join(s.split())
    s = s.strip(" .,;:!?'\"()[]{}«»—–")
    return s[:500]


def _stamp_dt(stamp: str):
    """Метка среза 20261022_190412 -> datetime(2026-10-22 19:04:12).

    Важно: без подчёркивания это не «секунды» (там ЧЧММСС), поэтому сравнивать
    надо именно дату-время, а не числа.
    """
    s = str(stamp or "")
    if len(s) == 15 and s[8] == "_":
        try:
            return datetime.strptime(s, "%Y%m%d_%H%M%S")
        except ValueError:
            return None
    return None


async def resolve_slice_stamp(db, cid: int, phrase: str, stamp: str,
                               window_min: int = 60) -> str:
    """Метка среза с «склейкой» по окну — чтобы не плодить срезы.

    Если по этой фразе уже есть срез, отстоящий от текущего меньше чем на
    window_min минут, переиспользуем ЕГО метку: данные перезапишутся, а в
    отчёте останется одна строка на фразу в час вместо десяти.

    Метки сравнимы между собой (YYYYMMDD_HHMMSS), поэтому «ближе часа» — это
    просто разница чисел.
    """
    s = str(stamp or "")[:20]
    cur = _stamp_dt(s)
    if not cur:
        return s
    try:
        row = (await db.execute(text("""
            SELECT slice_stamp FROM wb_competitor_position
            WHERE company_id=:cid AND query_phrase=:ph AND slice_stamp<>''
            ORDER BY slice_stamp DESC LIMIT 1
        """), {"cid": cid, "ph": _norm_phrase(phrase)})).mappings().first()
    except Exception:
        return s
    if not row:
        return s
    prev_s = str(row["slice_stamp"] or "")
    prev = _stamp_dt(prev_s)
    if prev and 0 <= (cur - prev).total_seconds() < window_min * 60:
        return prev_s
    return s


def _to_int(v):
    """«1 490 ₽» / 1490 / '1490' → 1490; пусто/мусор/0 → None (0 = «не знаем»)."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(round(v)) or None
    s = str(v).replace("\xa0", " ").strip()
    m = re.search(r"\d[\d\s]*", s)
    if not m:
        return None
    n = int(re.sub(r"[^\d]", "", m.group(0)))
    return n if n else None


def _to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace("\xa0", " ").replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _pick(new, old):
    """Новое значение, если оно «непустое», иначе старое (не затираем пустыми)."""
    if new is None:
        return old
    if isinstance(new, str) and not new.strip():
        return old
    if isinstance(new, (list, dict)) and not new:
        return old
    return new


def _json_len(raw) -> int:
    """Сколько элементов в JSON-списке (с учётом двойного кодирования, мусор → 0)."""
    try:
        val = raw if isinstance(raw, (list, dict)) else json.loads(raw or "[]")
        if isinstance(val, str):
            val = json.loads(val or "[]")
    except (TypeError, ValueError):
        return 0
    return len(val) if isinstance(val, list) else 0


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
    partial = bool(payload.get("partial"))    # фоновое наблюдение

    # 1. Своя ли карточка? (PK wbcards = nmID; company_id NULL — легаси, считаем своей)
    own_row = (await db.execute(text("""
        SELECT company_id FROM wbcards WHERE nmID=:n LIMIT 1
    """), {"n": nm_id})).first()
    is_own = bool(own_row) and (own_row[0] is None or int(own_row[0]) == int(company_id))
    if is_own and not allow_own:
        return {"skipped": True, "reason": "own_card", "nm_id": nm_id, "is_own": True}

    # 2. Нормализация payload
    title = str(payload.get("title") or "")[:500]
    description = str(payload.get("description") or "")
    chars_raw = payload.get("characteristics") or []
    recs_raw = payload.get("recommendations") or []
    images_raw = payload.get("images") or []
    badges_raw = payload.get("badges") or []
    price = _to_int(payload.get("price"))
    old_price = _to_int(payload.get("old_price"))
    rating = _to_float(payload.get("rating"))
    feedbacks = _to_int(payload.get("feedbacks"))
    questions = _to_int(payload.get("questions"))
    brand = str(payload.get("brand") or "")[:255]
    seller = str(payload.get("seller") or "")[:255]
    url = str(payload.get("url") or "")[:500].split("?")[0]
    subject = str(payload.get("subject_name") or "")[:255]
    # «Нет в наличии»: поле пришло — обновляем флаг, нет поля — не трогаем
    if "sold_out" in (payload or {}):
        sold_out = 1 if payload.get("sold_out") else 0
    else:
        sold_out = None

    # полный сбор = есть описание И характеристики
    is_full = bool(description.strip()) and bool(chars_raw)

    # 3. Текущее состояние
    row = (await db.execute(text("""
        SELECT id, title, description, characteristics, recommendations, images, badges,
               brand, seller, price, old_price, rating, feedbacks, questions,
               sold_out, subject_name, url, collected_at, full_collected_at
        FROM wb_competitor_details WHERE nm_id=:n LIMIT 1
    """), {"n": nm_id})).mappings().first()

    if row:
        # 4. Свежесть полного сбора (TTL 24 ч). Наблюдение TTL не применяет.
        if not partial and not force and row["full_collected_at"]:
            age_h = None
            try:
                age_h = (datetime.now() - row["full_collected_at"]).total_seconds() / 3600
            except TypeError:
                age_h = None
            if age_h is not None and age_h < FRESH_HOURS:
                if explicit:
                    await db.execute(text("""
                        INSERT INTO wb_competitor_capture
                          (nm_id, company_id, is_own, is_hidden, first_seen_by, last_seen_by)
                        VALUES (:n, :cid, 0, 0, :uid, :uid)
                        ON DUPLICATE KEY UPDATE
                          last_seen_at=NOW(), last_seen_by=:uid, is_hidden=0
                    """), {"n": nm_id, "cid": company_id, "uid": user_id})
                await db.execute(text("""
                    UPDATE wb_enrich_queue SET status='done', processed_at=NOW()
                    WHERE nm_id=:n AND status='need_update'
                """), {"n": nm_id})
                await db.commit()
                return {"skipped": True, "reason": "fresh", "nm_id": nm_id, "age_h": round(age_h, 1),
                        "collected_at": _iso(row["collected_at"]), "is_own": is_own}

        # 5. Слияние: изменяемое — всегда, контент — только непустой
        m_title = _pick(title, row["title"])
        m_desc = _pick(description, row["description"])
        m_chars = _pick(_json_list(chars_raw) if chars_raw else None, _json_list(row["characteristics"]))
        m_recs = _pick(_json_list(recs_raw) if recs_raw else None, _json_list(row["recommendations"]))
        new_images = _json_list(images_raw) if images_raw else None
        old_images = _json_list(row["images"])
        # Пассивное наблюдение видит только отрисованные миниатюры — не даём ему
        # заменить полную галерею (собранную полным проходом) более короткой.
        if new_images is not None and partial and _json_len(new_images) < _json_len(old_images):
            m_images = old_images
        else:
            m_images = _pick(new_images, old_images)
        m_badges = _pick(_json_list(badges_raw) if badges_raw else None, _json_list(row["badges"]))
        m_price = _pick(price, row["price"])
        m_old = _pick(old_price, row["old_price"])
        m_rating = _pick(rating, row["rating"])
        m_fb = _pick(feedbacks, row["feedbacks"])
        m_q = _pick(questions, row["questions"])
        m_brand = _pick(brand, row["brand"])
        m_seller = _pick(seller, row["seller"])
        m_subject = _pick(subject, row["subject_name"])
        m_url = _pick(url, row["url"])
        # sold_out: None — поле не пришло, держим прошлое значение
        m_sold = _pick(sold_out, 1 if row["sold_out"] else 0)

        changed = (
            m_title != (row["title"] or "") or m_desc != (row["description"] or "") or
            # characteristics: MySQL сортирует ключи в JSON → сравниваем канонически
            _norm_chars(m_chars) != _norm_chars(row["characteristics"]) or
            m_recs != _json_list(row["recommendations"]) or
            m_images != _json_list(row["images"]) or
            m_badges != _json_list(row["badges"]) or
            m_price != row["price"] or m_old != row["old_price"] or
            m_rating != row["rating"] or m_fb != row["feedbacks"] or
            m_q != row["questions"] or m_brand != (row["brand"] or "") or
            m_seller != (row["seller"] or "") or m_subject != (row["subject_name"] or "") or
            m_url != (row["url"] or "") or
            (1 if m_sold else 0) != (1 if row["sold_out"] else 0)
        )
    else:
        row = None
        m_title = title
        m_desc = description
        m_chars = _json_list(chars_raw)
        m_recs = _json_list(recs_raw)
        m_images = _json_list(images_raw)
        m_badges = _json_list(badges_raw)
        m_price = price
        m_old = old_price
        m_rating = rating
        m_fb = feedbacks
        m_q = questions
        m_brand = brand
        m_seller = seller
        m_subject = subject
        m_url = url
        m_sold = sold_out if sold_out is not None else 0
        changed = True

    # 6. Запись контента (только если что-то изменилось — иначе collected_at «ползёт»)
    if changed:
        await db.rollback()
        async with db.begin():
            if row:
                await db.execute(text("""
                    UPDATE wb_competitor_details SET
                      title=:t, description=:d, characteristics=:ch, recommendations=:recs,
                      images=:img, badges=:bg,
                      brand=:b, seller=:s, price=:p, old_price=:o,
                      rating=:r, feedbacks=:fb, questions=:q, subject_name=:subj, url=:u,
                      sold_out=:so,
                      collected_at=NOW(),
                      full_collected_at=IF(:full=1, NOW(), full_collected_at)
                    WHERE id=:id
                """), {
                    "id": row["id"], "t": m_title, "d": m_desc, "ch": m_chars, "recs": m_recs,
                    "img": m_images, "bg": m_badges, "b": m_brand, "s": m_seller,
                    "p": m_price, "o": m_old, "r": m_rating, "fb": m_fb, "q": m_q,
                    "subj": m_subject, "u": m_url, "so": 1 if m_sold else 0,
                    "full": 1 if is_full else 0,
                })
            else:
                await db.execute(text("""
                    INSERT INTO wb_competitor_details
                      (nm_id, title, description, characteristics, recommendations, images, badges,
                       brand, seller, price, old_price, rating, feedbacks, questions, subject_name, url,
                       sold_out, collected_at, first_collected_at, full_collected_at,
                       captured_company_id, captured_by)
                    VALUES (:n, :t, :d, :ch, :recs, :img, :bg,
                            :b, :s, :p, :o, :r, :fb, :q, :subj, :u, :so,
                            NOW(), NOW(), IF(:full=1, NOW(), NULL),
                            :cid, :uid)
                """), {
                    "n": nm_id, "t": m_title, "d": m_desc, "ch": m_chars, "recs": m_recs,
                    "img": m_images, "bg": m_badges, "b": m_brand, "s": m_seller,
                    "p": m_price, "o": m_old, "r": m_rating, "fb": m_fb, "q": m_q,
                    "subj": m_subject, "u": m_url, "so": 1 if m_sold else 0,
                    "cid": company_id, "uid": user_id,
                    "full": 1 if is_full else 0,
                })

            # 7. Видимость по компании (m:n). Явный клик возвращает скрытую карточку.
            await db.execute(text("""
                INSERT INTO wb_competitor_capture
                  (nm_id, company_id, is_own, is_hidden, first_seen_by, last_seen_by)
                VALUES (:n, :cid, :own, 0, :uid, :uid)
                ON DUPLICATE KEY UPDATE
                  last_seen_at=NOW(),
                  last_seen_by=:uid,
                  is_own=:own,
                  is_hidden=IF(:exp=1, 0, is_hidden)
            """), {"n": nm_id, "cid": company_id, "own": 1 if is_own else 0, "uid": user_id,
                   "exp": 1 if explicit else 0})

            # 8. История: снимок при новом content_hash (по ИТОГОВОЙ строке, не по payload)
            h = content_hash(m_title, m_desc, m_chars, m_price, m_old)
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
                    VALUES (:n, :t, :d, :ch, :b, :s, :p, :o, :img, :h, :cid, :uid, :src)
                """), {"n": nm_id, "t": m_title, "d": m_desc, "ch": m_chars, "b": m_brand,
                       "s": m_seller, "p": m_price, "o": m_old, "img": m_images, "h": h,
                       "cid": company_id, "uid": user_id,
                       "src": "observe" if partial else "capture"})
                history = "inserted"

            # 9. Контент обновлён — закрываем назначенное обновление.
            await db.execute(text("""
                UPDATE wb_enrich_queue SET status='done', processed_at=NOW()
                WHERE nm_id=:n AND status='need_update'
            """), {"n": nm_id})
        return {
            "ok": True, "skipped": False, "nm_id": nm_id, "is_own": is_own,
            "content_hash": h, "history": history, "changed": changed, "partial": partial,
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "desc_len": len(m_desc or ""), "chars_cnt": _cnt(chars_raw),
            "price": m_price, "old_price": m_old, "rating": m_rating,
            "feedbacks": m_fb, "questions": m_q, "badges": _cnt(json.loads(m_badges or "[]")),
        }

    # Ничего не изменилось — только отмечаем «мы видели» (last_seen_at)
    await db.execute(text("""
        INSERT INTO wb_competitor_capture
          (nm_id, company_id, is_own, is_hidden, first_seen_by, last_seen_by)
        VALUES (:n, :cid, :own, 0, :uid, :uid)
        ON DUPLICATE KEY UPDATE
          last_seen_at=NOW(), last_seen_by=:uid, is_own=:own,
          is_hidden=IF(:exp=1, 0, is_hidden)
    """), {"n": nm_id, "cid": company_id, "own": 1 if is_own else 0, "uid": user_id,
           "exp": 1 if explicit else 0})
    await db.commit()
    return {
        "ok": True, "skipped": False, "nm_id": nm_id, "is_own": is_own, "changed": False,
        "partial": partial, "history": "same",
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "desc_len": len(m_desc or ""), "chars_cnt": _cnt(chars_raw),
        "price": m_price, "old_price": m_old, "rating": m_rating,
        "feedbacks": m_fb, "questions": m_q, "badges": 0,
    }
