"""Полки / дубликаты / клипы WB: приём наблюдений от расширения (v1).

Источник — перехваченные ответы самой страницы WB (hook_wb_api.js):
  * u-recom/recom/*/v9/search  -> полка «Смотрите также» (kind=recom);
  * meta/duplicates/*/v8/search -> кластер одинаковых товаров (kind=duplicates);
  * api-wibes/esearch/v2/nms   -> UGC-клипы.

Модуль идемпотентный: повторная отправка того же снимка обновляет строки
(UNIQUE-ключи в 20261028_competitor_cards_shelves.sql), а не плодит дубли.
Цены приходят уже в рублях (перевод из копеек — на границе парсера).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_SHELVES = 20
MAX_ITEMS_PER_SHELF = 300
MAX_OFFER_RUNS = 10
MAX_OFFERS_PER_RUN = 100
MAX_CLIPS = 200
CHUNK = 400

_INT_RE = re.compile(r"-?\d+")


def _int(v: Any, default: int | None = None) -> int | None:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        try:
            return int(v)
        except (ValueError, OverflowError):
            return default
    m = _INT_RE.search(str(v).replace("\xa0", " ").replace(" ", ""))
    if not m:
        return default
    try:
        return int(m.group(0))
    except ValueError:
        return default


def _str(v: Any, n: int) -> str:
    return str(v or "")[:n]


def _norm_title(v: Any) -> str:
    s = str(v or "").lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]+", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()[:255]


def _dt(v: Any) -> datetime | None:
    s = str(v or "").strip()
    if not s:
        return None
    s = s.replace("T", " ").replace("Z", "")
    s = s.split("+")[0].strip()
    try:
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None


def _json(v: Any) -> str | None:
    if v in (None, "", [], {}):
        return None
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def url_key(kind: str, preset_id: int, subject_id: int | None, parent_subject_id: int | None, dest: int) -> str:
    """Ключ полки: без `page`, иначе каждая страница стала бы новой полкой."""
    raw = f"{kind}|{int(preset_id or 0)}|{int(subject_id or 0)}|{int(parent_subject_id or 0)}|{int(dest or 0)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


async def _own_nms(db: AsyncSession, company_id: int, ids: Iterable[int]) -> set[int]:
    """Наши карточки: company_id = компания (NULL в wbcards = «наша» карточка)."""
    uniq = sorted({int(i) for i in ids if i})
    if not uniq:
        return set()
    out: set[int] = set()
    for i in range(0, len(uniq), CHUNK):
        part = uniq[i : i + CHUNK]
        ph = ",".join(f":i{j}" for j in range(len(part)))
        rows = (
            await db.execute(
                text(f"SELECT nmID, company_id FROM wbcards WHERE nmID IN ({ph})"),
                {f"i{j}": v for j, v in enumerate(part)},
            )
        ).all()
        for nm, cid in rows:
            if cid is None or int(cid) == int(company_id):
                out.add(int(nm))
    return out


async def _last_id(db: AsyncSession) -> int:
    return int((await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar() or 0)


SHELF_SQL = text(
    """
    INSERT INTO wb_competitor_cards_shelf
      (company_id, nm_id, kind, preset_id, preset_type, title, title_source,
       is_partial, total_candidates, pages_loaded, shard_key, shard_query, imt_id,
       subject_id, parent_subject_id, dest, spp, route, url_key, created_by)
    VALUES
      (:company_id, :nm_id, :kind, :preset_id, :preset_type, :title, :title_source,
       :is_partial, :total_candidates, :pages_loaded, :shard_key, :shard_query, :imt_id,
       :subject_id, :parent_subject_id, :dest, :spp, :route, :url_key, :created_by)
    ON DUPLICATE KEY UPDATE
      id = LAST_INSERT_ID(id),
      preset_type = IF(VALUES(preset_type)='', preset_type, VALUES(preset_type)),
      title = IF(VALUES(title)='', title, VALUES(title)),
      title_source = IF(VALUES(title_source)='none', title_source, VALUES(title_source)),
      is_partial = VALUES(is_partial),
      total_candidates = COALESCE(VALUES(total_candidates), total_candidates),
      pages_loaded = GREATEST(pages_loaded, VALUES(pages_loaded)),
      shard_key = COALESCE(VALUES(shard_key), shard_key),
      shard_query = COALESCE(VALUES(shard_query), shard_query),
      imt_id = COALESCE(VALUES(imt_id), imt_id),
      subject_id = COALESCE(VALUES(subject_id), subject_id),
      parent_subject_id = COALESCE(VALUES(parent_subject_id), parent_subject_id),
      spp = COALESCE(VALUES(spp), spp),
      last_seen_at = CURRENT_TIMESTAMP
    """
)

ITEM_SQL = text(
    """
    INSERT INTO wb_competitor_cards_shelf_item
      (shelf_id, nm_id, snapshot_date, page, position, sort_score, name, price, price_basic,
       cashback, seller_id, seller, seller_rating, brand_id, brand, subject_id, root_id,
       match_id, rating, review_rating, feedbacks, feedback_points, total_qty, time1, time2,
       wh, dist, volume, weight, pics, pics_update, option_id, is_new, is_own, promo_panel_id,
       preset_type, semantic_id, sale_conditions, dtype_mask)
    VALUES
      (:shelf_id, :nm_id, :snapshot_date, :page, :position, :sort_score, :name, :price, :price_basic,
       :cashback, :seller_id, :seller, :seller_rating, :brand_id, :brand, :subject_id, :root_id,
       :match_id, :rating, :review_rating, :feedbacks, :feedback_points, :total_qty, :time1, :time2,
       :wh, :dist, :volume, :weight, :pics, :pics_update, :option_id, :is_new, :is_own, :promo_panel_id,
       :preset_type, :semantic_id, :sale_conditions, :dtype_mask)
    ON DUPLICATE KEY UPDATE
      page = VALUES(page),
      position = VALUES(position),
      sort_score = VALUES(sort_score),
      name = IF(VALUES(name)='', name, VALUES(name)),
      price = COALESCE(VALUES(price), price),
      price_basic = COALESCE(VALUES(price_basic), price_basic),
      cashback = COALESCE(VALUES(cashback), cashback),
      seller_id = COALESCE(VALUES(seller_id), seller_id),
      seller = IF(VALUES(seller)='', seller, VALUES(seller)),
      seller_rating = COALESCE(VALUES(seller_rating), seller_rating),
      total_qty = COALESCE(VALUES(total_qty), total_qty),
      time1 = COALESCE(VALUES(time1), time1),
      time2 = COALESCE(VALUES(time2), time2),
      rating = COALESCE(VALUES(rating), rating),
      review_rating = COALESCE(VALUES(review_rating), review_rating),
      feedbacks = COALESCE(VALUES(feedbacks), feedbacks),
      is_new = VALUES(is_new),
      is_own = VALUES(is_own),
      match_id = COALESCE(VALUES(match_id), match_id),
      captured_at = CURRENT_TIMESTAMP
    """
)

RUN_SQL = text(
    """
    INSERT INTO wb_competitor_cards_offer_run
      (company_id, match_id, anchor_nm_id, anchor_supplier_id, anchor_price, min_price,
       min_price_nm_id, offers_total, benefit, shard_key, shard_query, response_type,
       dest, spp, snapshot_date, created_by)
    VALUES
      (:company_id, :match_id, :anchor_nm_id, :anchor_supplier_id, :anchor_price, :min_price,
       :min_price_nm_id, :offers_total, :benefit, :shard_key, :shard_query, :response_type,
       :dest, :spp, :snapshot_date, :created_by)
    ON DUPLICATE KEY UPDATE
      id = LAST_INSERT_ID(id),
      anchor_supplier_id = COALESCE(VALUES(anchor_supplier_id), anchor_supplier_id),
      anchor_price = COALESCE(VALUES(anchor_price), anchor_price),
      min_price = COALESCE(VALUES(min_price), min_price),
      min_price_nm_id = COALESCE(VALUES(min_price_nm_id), min_price_nm_id),
      offers_total = COALESCE(VALUES(offers_total), offers_total),
      benefit = IF(VALUES(benefit)='', benefit, VALUES(benefit)),
      shard_key = COALESCE(VALUES(shard_key), shard_key),
      shard_query = COALESCE(VALUES(shard_query), shard_query),
      response_type = IF(VALUES(response_type)='', response_type, VALUES(response_type)),
      spp = COALESCE(VALUES(spp), spp),
      captured_at = CURRENT_TIMESTAMP
    """
)

OFFER_SQL = text(
    """
    INSERT INTO wb_competitor_cards_offer
      (run_id, nm_id, position, name, price, price_basic, seller_id, seller, seller_rating,
       brand_id, brand, total_qty, rating, review_rating, feedbacks, time1, time2, wh, dist,
       volume, weight, pics, dtype_mask, is_anchor, is_min_price, price_gap_pct, is_own)
    VALUES
      (:run_id, :nm_id, :position, :name, :price, :price_basic, :seller_id, :seller, :seller_rating,
       :brand_id, :brand, :total_qty, :rating, :review_rating, :feedbacks, :time1, :time2, :wh, :dist,
       :volume, :weight, :pics, :dtype_mask, :is_anchor, :is_min_price, :price_gap_pct, :is_own)
    ON DUPLICATE KEY UPDATE
      position = VALUES(position),
      name = IF(VALUES(name)='', name, VALUES(name)),
      price = COALESCE(VALUES(price), price),
      price_basic = COALESCE(VALUES(price_basic), price_basic),
      seller_id = COALESCE(VALUES(seller_id), seller_id),
      seller = IF(VALUES(seller)='', seller, VALUES(seller)),
      seller_rating = COALESCE(VALUES(seller_rating), seller_rating),
      total_qty = COALESCE(VALUES(total_qty), total_qty),
      rating = COALESCE(VALUES(rating), rating),
      feedbacks = COALESCE(VALUES(feedbacks), feedbacks),
      is_anchor = VALUES(is_anchor),
      is_min_price = VALUES(is_min_price),
      price_gap_pct = VALUES(price_gap_pct),
      is_own = VALUES(is_own),
      captured_at = CURRENT_TIMESTAMP
    """
)

CLIP_SQL = text(
    """
    INSERT INTO wb_competitor_cards_clip
      (clip_id, type, slug, name, description, duration_s, publication_date, author_id,
       author_slug, author_name, author_verified, author_code, preview_url, public_url, nm_count, extra)
    VALUES
      (:clip_id, :type, :slug, :name, :description, :duration_s, :publication_date, :author_id,
       :author_slug, :author_name, :author_verified, :author_code, :preview_url, :public_url, :nm_count, :extra)
    ON DUPLICATE KEY UPDATE
      type = VALUES(type),
      slug = IF(VALUES(slug)='', slug, VALUES(slug)),
      name = IF(VALUES(name)='', name, VALUES(name)),
      description = IF(VALUES(description)='', description, VALUES(description)),
      duration_s = COALESCE(VALUES(duration_s), duration_s),
      publication_date = COALESCE(VALUES(publication_date), publication_date),
      author_name = IF(VALUES(author_name)='', author_name, VALUES(author_name)),
      author_verified = VALUES(author_verified),
      author_code = COALESCE(VALUES(author_code), author_code),
      preview_url = IF(VALUES(preview_url)='', preview_url, VALUES(preview_url)),
      public_url = IF(VALUES(public_url)='', public_url, VALUES(public_url)),
      extra = COALESCE(VALUES(extra), extra),
      nm_count = VALUES(nm_count),
      last_seen_at = CURRENT_TIMESTAMP
    """
)

CLIP_NM_SQL = text(
    """
    INSERT INTO wb_competitor_cards_clip_nm (clip_id, nm_id, cluster_idx)
    VALUES (:clip_id, :nm_id, :cluster_idx)
    ON DUPLICATE KEY UPDATE cluster_idx = VALUES(cluster_idx)
    """
)

PRESET_SQL = text(
    """
    INSERT INTO wb_competitor_cards_shelf_preset
      (preset_id, preset_type, title, title_norm, confidence, hits, first_nm_id, last_nm_id)
    VALUES
      (:preset_id, :preset_type, :title, :title_norm, :confidence, 1, :nm_id, :nm_id)
    ON DUPLICATE KEY UPDATE
      preset_type = IF(VALUES(preset_type)='', preset_type, VALUES(preset_type)),
      title = IF(title='', VALUES(title), title),
      title_norm = IF(title_norm='', VALUES(title_norm), title_norm),
      confidence = GREATEST(confidence, VALUES(confidence)),
      hits = hits + 1,
      last_nm_id = VALUES(last_nm_id),
      last_seen_at = CURRENT_TIMESTAMP
    """
)


def _item_row(it: dict, shelf_id: int, day: date, own: set[int]) -> dict:
    nm = _int(it.get("nm_id")) or 0
    return {
        "shelf_id": shelf_id,
        "nm_id": nm,
        "snapshot_date": day,
        "page": _int(it.get("page"), 1) or 1,
        "position": _int(it.get("position"), 1) or 1,
        "sort_score": _int(it.get("sort_score")),
        "name": _str(it.get("name"), 500),
        "price": _int(it.get("price")),
        "price_basic": _int(it.get("price_basic")),
        "cashback": _int(it.get("cashback")),
        "seller_id": _int(it.get("seller_id")),
        "seller": _str(it.get("seller"), 255),
        "seller_rating": it.get("seller_rating") if isinstance(it.get("seller_rating"), (int, float)) else None,
        "brand_id": _int(it.get("brand_id")),
        "brand": _str(it.get("brand"), 255),
        "subject_id": _int(it.get("subject_id")),
        "root_id": _int(it.get("root_id")),
        "match_id": _int(it.get("match_id")),
        "rating": it.get("rating") if isinstance(it.get("rating"), (int, float)) else None,
        "review_rating": it.get("review_rating") if isinstance(it.get("review_rating"), (int, float)) else None,
        "feedbacks": _int(it.get("feedbacks")),
        "feedback_points": _int(it.get("feedback_points")),
        "total_qty": _int(it.get("total_qty")),
        "time1": _int(it.get("time1")),
        "time2": _int(it.get("time2")),
        "wh": _int(it.get("wh")),
        "dist": _int(it.get("dist")),
        "volume": _int(it.get("volume")),
        "weight": it.get("weight") if isinstance(it.get("weight"), (int, float)) else None,
        "pics": _int(it.get("pics")),
        "pics_update": _int(it.get("pics_update")),
        "option_id": _int(it.get("option_id")),
        "is_new": 1 if it.get("is_new") else 0,
        "is_own": 1 if nm in own else 0,
        "promo_panel_id": _int(it.get("promo_panel_id")),
        "preset_type": _str(it.get("preset_type"), 32),
        "semantic_id": _json(it.get("semantic_id")),
        "sale_conditions": _int(it.get("sale_conditions")),
        "dtype_mask": _int(it.get("dtype_mask")),
    }


async def _chunks(db: AsyncSession, sql, rows: list[dict]) -> int:
    n = 0
    for i in range(0, len(rows), CHUNK):
        await db.execute(sql, rows[i : i + CHUNK])
        n += len(rows[i : i + CHUNK])
    return n


async def save_shelves(
    db: AsyncSession,
    company_id: int,
    user_id: int | None,
    data: dict,
) -> dict:
    day = date.today()
    dest = _int(data.get("dest"), 0) or 0
    spp = _int(data.get("spp"))
    nm_id = _int(data.get("nm_id")) or 0
    shelves_in = [s for s in (data.get("shelves") or []) if isinstance(s, dict)][:MAX_SHELVES]
    offers_in = [o for o in (data.get("offers") or []) if isinstance(o, dict)][:MAX_OFFER_RUNS]
    clips_in = [c for c in (data.get("clips") or []) if isinstance(c, dict)][:MAX_CLIPS]

    # Клипы глобальны: их можно присылать без карточки (лента Wibes, поиск).
    # Полки/дубликаты без nm_id смысла не имеют.
    if not nm_id:
        if not clips_in:
            raise ValueError("nm_id required")
        shelves_in = []
        offers_in = []

    # --- наши карточки одним запросом (is_own для полок и офферов)
    ids: set[int] = set()
    for s in shelves_in:
        for it in (s.get("items") or [])[:MAX_ITEMS_PER_SHELF]:
            i = _int((it or {}).get("nm_id"))
            if i:
                ids.add(i)
    for o in offers_in:
        for it in (o.get("items") or [])[:MAX_OFFERS_PER_RUN]:
            i = _int((it or {}).get("nm_id"))
            if i:
                ids.add(i)
    own = await _own_nms(db, company_id, ids)

    n_shelves = n_items = n_runs = n_offers = n_clips = n_presets = 0

    # --- полки
    for s in shelves_in:
        kind = _str(s.get("kind"), 16) or "unknown"
        items = [it for it in (s.get("items") or []) if isinstance(it, dict)][:MAX_ITEMS_PER_SHELF]
        if not items:
            continue
        preset_id = _int(s.get("preset_id"), 0) or 0
        subject_id = _int(s.get("subject_id"))
        parent_subject_id = _int(s.get("parent_subject_id"))
        total = _int(s.get("total_candidates"))
        title = _str(s.get("title"), 255)
        title_source = _str(s.get("title_source"), 8) or "none"
        if title_source not in {"dom", "dict", "none"}:
            title_source = "none"
        is_partial = 1 if (total and len(items) < total) else 0

        await db.execute(
            SHELF_SQL,
            {
                "company_id": company_id,
                "nm_id": nm_id,
                "kind": kind,
                "preset_id": preset_id,
                "preset_type": _str(s.get("preset_type"), 32),
                "title": title,
                "title_source": title_source,
                "is_partial": is_partial,
                "total_candidates": total,
                "pages_loaded": _int(s.get("pages_loaded"), 1) or 1,
                "shard_key": _str(s.get("shard_key"), 64) or None,
                "shard_query": _str(s.get("shard_query"), 64) or None,
                "imt_id": _int(s.get("imt_id")),
                "subject_id": subject_id,
                "parent_subject_id": parent_subject_id,
                "dest": dest,
                "spp": spp,
                "route": _str(s.get("route"), 32),
                "url_key": url_key(kind, preset_id, subject_id, parent_subject_id, dest),
                "created_by": user_id,
            },
        )
        shelf_id = await _last_id(db)
        if not shelf_id:
            continue
        n_shelves += 1

        rows = [_item_row(it, shelf_id, day, own) for it in items]
        n_items += await _chunks(db, ITEM_SQL, rows)

        # словарь подписей учим и на сервере (переиспользуется в отчётах)
        if preset_id and title:
            await db.execute(
                PRESET_SQL,
                {
                    "preset_id": preset_id,
                    "preset_type": _str(s.get("preset_type"), 32),
                    "title": title,
                    "title_norm": _norm_title(title),
                    "confidence": 1.0 if title_source == "dom" else 0.5,
                    "nm_id": nm_id,
                },
            )
            n_presets += 1

    # --- дубликаты
    for run in offers_in:
        match_id = _int(run.get("match_id"))
        items = [it for it in (run.get("items") or []) if isinstance(it, dict)][:MAX_OFFERS_PER_RUN]
        if not match_id or not items:
            continue
        anchor_nm = _int(run.get("anchor_nm_id")) or nm_id
        anchor_price = _int(run.get("anchor_price"))
        if anchor_price is None:
            anchor_price = _int(
                (
                    await db.execute(
                        text("SELECT price FROM wb_competitor_details WHERE nm_id=:n"),
                        {"n": anchor_nm},
                    )
                ).scalar()
            )
        min_nm = _int(run.get("min_price_nm_id"))
        await db.execute(
            RUN_SQL,
            {
                "company_id": company_id,
                "match_id": match_id,
                "anchor_nm_id": anchor_nm,
                "anchor_supplier_id": _int(run.get("anchor_supplier_id")),
                "anchor_price": anchor_price,
                "min_price": _int(run.get("min_price")),
                "min_price_nm_id": min_nm,
                "offers_total": _int(run.get("offers_total")),
                "benefit": _str(run.get("benefit"), 32),
                "shard_key": _str(run.get("shard_key"), 64) or None,
                "shard_query": _str(run.get("shard_query"), 64) or None,
                "response_type": _str(run.get("response_type"), 16),
                "dest": dest,
                "spp": spp,
                "snapshot_date": day,
                "created_by": user_id,
            },
        )
        run_id = await _last_id(db)
        if not run_id:
            continue
        n_runs += 1

        anchor_supplier = _int(run.get("anchor_supplier_id"))
        rows = []
        for idx, it in enumerate(items, 1):
            nm = _int(it.get("nm_id")) or 0
            if not nm:
                continue
            price = _int(it.get("price"))
            gap = None
            if price is not None and anchor_price:
                gap = round((price - anchor_price) / anchor_price * 100)
            rows.append(
                {
                    "run_id": run_id,
                    "nm_id": nm,
                    "position": _int(it.get("position"), idx) or idx,
                    "name": _str(it.get("name"), 500),
                    "price": price,
                    "price_basic": _int(it.get("price_basic")),
                    "seller_id": _int(it.get("seller_id")),
                    "seller": _str(it.get("seller"), 255),
                    "seller_rating": it.get("seller_rating")
                    if isinstance(it.get("seller_rating"), (int, float))
                    else None,
                    "brand_id": _int(it.get("brand_id")),
                    "brand": _str(it.get("brand"), 255),
                    "total_qty": _int(it.get("total_qty")),
                    "rating": it.get("rating") if isinstance(it.get("rating"), (int, float)) else None,
                    "review_rating": it.get("review_rating")
                    if isinstance(it.get("review_rating"), (int, float))
                    else None,
                    "feedbacks": _int(it.get("feedbacks")),
                    "time1": _int(it.get("time1")),
                    "time2": _int(it.get("time2")),
                    "wh": _int(it.get("wh")),
                    "dist": _int(it.get("dist")),
                    "volume": _int(it.get("volume")),
                    "weight": it.get("weight") if isinstance(it.get("weight"), (int, float)) else None,
                    "pics": _int(it.get("pics")),
                    "dtype_mask": _int(it.get("dtype_mask")),
                    "is_anchor": 1
                    if (nm == anchor_nm or (anchor_supplier and _int(it.get("seller_id")) == anchor_supplier))
                    else 0,
                    "is_min_price": 1 if (min_nm and nm == min_nm) else 0,
                    "price_gap_pct": gap,
                    "is_own": 1 if nm in own else 0,
                }
            )
        n_offers += await _chunks(db, OFFER_SQL, rows)

    # --- клипы
    for c in clips_in:
        clip_id = _int(c.get("clip_id"))
        if not clip_id:
            continue
        slug = _str(c.get("slug"), 255)
        groups = c.get("nms") or []
        nms: list[tuple[int, int]] = []
        for gi, group in enumerate(groups if isinstance(groups, list) else []):
            if not isinstance(group, list):
                continue
            for nm in group:
                v = _int(nm)
                if v:
                    nms.append((v, gi))
        # Публичная ссылка: только реальная (в ответе это `link` = wibes.ru/clips/<id>).
        # Шаблонов не придумываем — раньше из slug получался битый URL.
        public_url = _str(c.get("public_url"), 512)
        if public_url and not public_url.startswith("http"):
            public_url = ""
        if not public_url:
            for k in ("link", "url", "web_url", "share_url", "short_url", "permalink"):
                v = c.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    public_url = v[:512]
                    break

        author = c.get("author") if isinstance(c.get("author"), dict) else {}
        extra = c.get("extra")
        extra = dict(extra) if isinstance(extra, dict) else {}
        # Блок автора целиком (профиль, аватар, описание, флаги) — как JSON.
        if author:
            extra.setdefault(
                "author",
                {k: (v[:300] if isinstance(v, str) else v) for k, v in list(author.items())[:20]},
            )
        # Прямая ссылка на видео — если публичного URL WB не отдал.
        if c.get("video_url"):
            extra.setdefault("video_url", str(c["video_url"])[:512])
        extra_json = json.dumps(extra, ensure_ascii=False)[:4000] if extra else None
        await db.execute(
            CLIP_SQL,
            {
                "clip_id": clip_id,
                "type": _str(c.get("type"), 16) or "video",
                "slug": slug,
                "name": _str(c.get("name"), 255),
                "description": _str(c.get("description"), 2000),
                "duration_s": c.get("duration_s") if isinstance(c.get("duration_s"), (int, float)) else None,
                "publication_date": _dt(c.get("publication_date")),
                "author_id": _int(c.get("author_id")) or _int(author.get("id")),
                "author_slug": _str(c.get("author_slug"), 255) or _str(author.get("slug"), 255),
                "author_name": _str(c.get("author_name"), 255) or _str(author.get("name"), 255),
                "author_verified": 1 if (c.get("author_verified") or author.get("is_verified")) else 0,
                "author_code": _int(c.get("author_code")),
                "preview_url": _str(c.get("preview_url"), 512),
                "public_url": public_url,
                "nm_count": len({v for v, _ in nms}),
                "extra": extra_json,
            },
        )
        n_clips += 1
        if nms:
            await db.execute(
                CLIP_NM_SQL,
                [{"clip_id": clip_id, "nm_id": v, "cluster_idx": gi} for v, gi in nms],
            )

    return {
        "nm_id": nm_id,
        "shelves": n_shelves,
        "items": n_items,
        "offer_runs": n_runs,
        "offers": n_offers,
        "clips": n_clips,
        "presets": n_presets,
    }
