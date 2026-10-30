"""Полки / дубликаты / клипы WB: приём наблюдений от расширения (v1).

Источник — перехваченные ответы самой страницы WB (hook_wb_api.js):
  * u-recom/recom/*/v9/search  -> полка «Смотрите также» (kind=recom);
  * meta/duplicates/*/v8/search -> кластер одинаковых товаров (kind=duplicates);
  * api-wibes/esearch/v2/nms   -> UGC-клипы.

Модуль идемпотентный: повторная отправка того же снимка обновляет строки
(UNIQUE-ключи в 20261028_competitor_cards_shelves.sql), а не плодит дубли.
Цены приходят уже в рублях (перевод из копеек — на границе парсера).

Сырой ответ полок карточки (u-recom) тоже сохраняем файлом — тем же
механизмом, что и поисковые ответы (`search_raw_service`): файл в
`runtime/seo_search_raw/<company_id>/<YYYY-MM-DD>/`. Нужен, чтобы позже
переразобрать блок без нового захода на карточку (WB меняет API).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import search_raw_service

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


def _trim_strings(val: Any, limit: int = 300) -> Any:
    """Строки внутри вложенных структур режем по значению (не всей JSON-строке)."""
    if isinstance(val, str):
        return val[:limit]
    if isinstance(val, dict):
        return {k: _trim_strings(v, limit) for k, v in val.items()}
    if isinstance(val, list):
        return [_trim_strings(v, limit) for v in val]
    return val


def _fit_extra(extra: dict, max_len: int = 4000) -> str | None:
    """JSON для колонки `extra` БЕЗ обрыва сериализованной строки: резка посреди
    JSON даёт битый текст и MySQL errno 3140 на JSON-колонке (весь /shelves 500).
    Сначала режем длинные строковые значения, если всё равно не влезает —
    дропаем поля с конца, наконец None (лучше без extra, чем без всей полки)."""
    if not isinstance(extra, dict) or not extra:
        return None
    try:
        d = _trim_strings(extra)
        s = json.dumps(d, ensure_ascii=False)
        if len(s) <= max_len:
            return s
        keys = list(d.keys())
        while keys:
            keys.pop()
            s = json.dumps({k: d[k] for k in keys}, ensure_ascii=False)
            if len(s) <= max_len:
                return s
    except (TypeError, ValueError):
        return None
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
       :subject_id, :parent_subject_id, :dest, :spp, :route, :url_key, :created_by) AS new
    ON DUPLICATE KEY UPDATE
      id = LAST_INSERT_ID(id),
      preset_type = IF(new.preset_type='', wb_competitor_cards_shelf.preset_type, new.preset_type),
      title = IF(new.title='', wb_competitor_cards_shelf.title, new.title),
      title_source = IF(new.title_source='none', wb_competitor_cards_shelf.title_source, new.title_source),
      is_partial = new.is_partial,
      total_candidates = COALESCE(new.total_candidates, wb_competitor_cards_shelf.total_candidates),
      pages_loaded = GREATEST(wb_competitor_cards_shelf.pages_loaded, new.pages_loaded),
      shard_key = COALESCE(new.shard_key, wb_competitor_cards_shelf.shard_key),
      shard_query = COALESCE(new.shard_query, wb_competitor_cards_shelf.shard_query),
      imt_id = COALESCE(new.imt_id, wb_competitor_cards_shelf.imt_id),
      subject_id = COALESCE(new.subject_id, wb_competitor_cards_shelf.subject_id),
      parent_subject_id = COALESCE(new.parent_subject_id, wb_competitor_cards_shelf.parent_subject_id),
      spp = COALESCE(new.spp, wb_competitor_cards_shelf.spp),
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
       preset_type, semantic_id, sale_conditions, dtype_mask, image_url, badges)
    VALUES
      (:shelf_id, :nm_id, :snapshot_date, :page, :position, :sort_score, :name, :price, :price_basic,
       :cashback, :seller_id, :seller, :seller_rating, :brand_id, :brand, :subject_id, :root_id,
       :match_id, :rating, :review_rating, :feedbacks, :feedback_points, :total_qty, :time1, :time2,
       :wh, :dist, :volume, :weight, :pics, :pics_update, :option_id, :is_new, :is_own, :promo_panel_id,
       :preset_type, :semantic_id, :sale_conditions, :dtype_mask, :image_url, :badges) AS new
    ON DUPLICATE KEY UPDATE
      page = new.page,
      position = new.position,
      sort_score = new.sort_score,
      name = IF(new.name='', wb_competitor_cards_shelf_item.name, new.name),
      price = COALESCE(new.price, wb_competitor_cards_shelf_item.price),
      price_basic = COALESCE(new.price_basic, wb_competitor_cards_shelf_item.price_basic),
      cashback = COALESCE(new.cashback, wb_competitor_cards_shelf_item.cashback),
      seller_id = COALESCE(new.seller_id, wb_competitor_cards_shelf_item.seller_id),
      seller = IF(new.seller='', wb_competitor_cards_shelf_item.seller, new.seller),
      seller_rating = COALESCE(new.seller_rating, wb_competitor_cards_shelf_item.seller_rating),
      total_qty = COALESCE(new.total_qty, wb_competitor_cards_shelf_item.total_qty),
      time1 = COALESCE(new.time1, wb_competitor_cards_shelf_item.time1),
      time2 = COALESCE(new.time2, wb_competitor_cards_shelf_item.time2),
      rating = COALESCE(new.rating, wb_competitor_cards_shelf_item.rating),
      review_rating = COALESCE(new.review_rating, wb_competitor_cards_shelf_item.review_rating),
      feedbacks = COALESCE(new.feedbacks, wb_competitor_cards_shelf_item.feedbacks),
      is_new = new.is_new,
      is_own = new.is_own,
      match_id = COALESCE(new.match_id, wb_competitor_cards_shelf_item.match_id),
      image_url = IF(new.image_url='', wb_competitor_cards_shelf_item.image_url, new.image_url),
      badges = IF(new.badges IS NULL, wb_competitor_cards_shelf_item.badges, new.badges),
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
       :dest, :spp, :snapshot_date, :created_by) AS new
    ON DUPLICATE KEY UPDATE
      id = LAST_INSERT_ID(id),
      anchor_supplier_id = COALESCE(new.anchor_supplier_id, wb_competitor_cards_offer_run.anchor_supplier_id),
      anchor_price = COALESCE(new.anchor_price, wb_competitor_cards_offer_run.anchor_price),
      min_price = COALESCE(new.min_price, wb_competitor_cards_offer_run.min_price),
      min_price_nm_id = COALESCE(new.min_price_nm_id, wb_competitor_cards_offer_run.min_price_nm_id),
      offers_total = COALESCE(new.offers_total, wb_competitor_cards_offer_run.offers_total),
      benefit = IF(new.benefit='', wb_competitor_cards_offer_run.benefit, new.benefit),
      shard_key = COALESCE(new.shard_key, wb_competitor_cards_offer_run.shard_key),
      shard_query = COALESCE(new.shard_query, wb_competitor_cards_offer_run.shard_query),
      response_type = IF(new.response_type='', wb_competitor_cards_offer_run.response_type, new.response_type),
      spp = COALESCE(new.spp, wb_competitor_cards_offer_run.spp),
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
       :volume, :weight, :pics, :dtype_mask, :is_anchor, :is_min_price, :price_gap_pct, :is_own) AS new
    ON DUPLICATE KEY UPDATE
      position = new.position,
      name = IF(new.name='', wb_competitor_cards_offer.name, new.name),
      price = COALESCE(new.price, wb_competitor_cards_offer.price),
      price_basic = COALESCE(new.price_basic, wb_competitor_cards_offer.price_basic),
      seller_id = COALESCE(new.seller_id, wb_competitor_cards_offer.seller_id),
      seller = IF(new.seller='', wb_competitor_cards_offer.seller, new.seller),
      seller_rating = COALESCE(new.seller_rating, wb_competitor_cards_offer.seller_rating),
      total_qty = COALESCE(new.total_qty, wb_competitor_cards_offer.total_qty),
      rating = COALESCE(new.rating, wb_competitor_cards_offer.rating),
      feedbacks = COALESCE(new.feedbacks, wb_competitor_cards_offer.feedbacks),
      is_anchor = new.is_anchor,
      is_min_price = new.is_min_price,
      price_gap_pct = new.price_gap_pct,
      is_own = new.is_own,
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
       :author_slug, :author_name, :author_verified, :author_code, :preview_url, :public_url, :nm_count, :extra) AS new
    ON DUPLICATE KEY UPDATE
      type = new.type,
      slug = IF(new.slug='', wb_competitor_cards_clip.slug, new.slug),
      name = IF(new.name='', wb_competitor_cards_clip.name, new.name),
      description = IF(new.description='', wb_competitor_cards_clip.description, new.description),
      duration_s = COALESCE(new.duration_s, wb_competitor_cards_clip.duration_s),
      publication_date = COALESCE(new.publication_date, wb_competitor_cards_clip.publication_date),
      author_name = IF(new.author_name='', wb_competitor_cards_clip.author_name, new.author_name),
      author_verified = new.author_verified,
      author_code = COALESCE(new.author_code, wb_competitor_cards_clip.author_code),
      preview_url = IF(new.preview_url='', wb_competitor_cards_clip.preview_url, new.preview_url),
      public_url = IF(new.public_url='', wb_competitor_cards_clip.public_url, new.public_url),
      extra = COALESCE(new.extra, wb_competitor_cards_clip.extra),
      nm_count = new.nm_count,
      last_seen_at = CURRENT_TIMESTAMP
    """
)

CLIP_NM_SQL = text(
    """
    INSERT INTO wb_competitor_cards_clip_nm (clip_id, nm_id, cluster_idx)
    VALUES (:clip_id, :nm_id, :cluster_idx) AS new
    ON DUPLICATE KEY UPDATE cluster_idx = new.cluster_idx
    """
)

PRESET_SQL = text(
    """
    INSERT INTO wb_competitor_cards_shelf_preset
      (preset_id, preset_type, title, title_norm, confidence, hits, first_nm_id, last_nm_id)
    VALUES
      (:preset_id, :preset_type, :title, :title_norm, :confidence, 1, :nm_id, :nm_id) AS new
    ON DUPLICATE KEY UPDATE
      preset_type = IF(new.preset_type='', wb_competitor_cards_shelf_preset.preset_type, new.preset_type),
      title = IF(new.title='', wb_competitor_cards_shelf_preset.title,
                  IF(:src='dom', new.title, wb_competitor_cards_shelf_preset.title)),
      title_norm = IF(:src='dom' AND new.title<>'', new.title_norm, wb_competitor_cards_shelf_preset.title_norm),
      confidence = GREATEST(wb_competitor_cards_shelf_preset.confidence, new.confidence),
      hits = wb_competitor_cards_shelf_preset.hits + 1,
      last_nm_id = new.last_nm_id,
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
        # Фото товара в полке: в ответах WB его нет (проверено на сыром
        # ответе каталога — только счётчик pics), поэтому расширение берёт
        # его из DOM страницы и присылает сюда.
        "image_url": _str(it.get("image_url"), 512),
        # Бейджи позиции («−48%», «за отзыв 200») — тоже только из DOM.
        "badges": _json(it.get("badges")),
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
                    "src": title_source,
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
        extra_json = _fit_extra(extra)
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

    # Блоки как мы их увидели в DOM → файл dom_*.json (рядом с сырыми ответами).
    dom_file = save_dom_blocks(
        company_id, nm_id, str(data.get("page_url") or ""),
        [b for b in (data.get("dom_blocks") or []) if isinstance(b, dict)],
        str(data.get("stamp") or ""),
    )

    return {
        "nm_id": nm_id,
        "shelves": n_shelves,
        "items": n_items,
        "offer_runs": n_runs,
        "offers": n_offers,
        "clips": n_clips,
        "presets": n_presets,
        "dom_file": dom_file,
    }


# --------------------------------------------------------------------------
# Сырой ответ полок карточки (u-recom) — файлом, как поисковые ответы
# --------------------------------------------------------------------------

def _stamp_now() -> str:
    """Метка момента в формате search_stamp: 20261027_162147."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_dom_blocks(company_id: int, nm_id: int, page_url: str,
                    blocks: list[dict], stamp: str = "") -> dict:
    """Блоки полок, как мы их увидели в DOM → файл `dom_*.json` + `.meta.json`.

    Сырой ответ API (`recom_*.json`) не содержит фото и бейджей — их нет в
    ответе WB. DOM-снимок — то, что реально показал пользователю WB: подписи
    блоков, фото, бейджи, цены, рейтинги. Рядом с сырыми ответами, в том же
    каталоге `runtime/seo_search_raw/<company_id>/<YYYY-MM-DD>/`.

    Файл пишется, только если скан что-то нашёл (иначе копим пустышки).
    """
    blocks = [b for b in (blocks or []) if isinstance(b, dict)]
    cards = [c for b in blocks for c in (b.get("cards") or []) if isinstance(c, dict)]
    if not cards:
        return {"saved": False, "reason": "no_blocks"}
    stamp = stamp or _stamp_now()
    if not re.match(r"^\d{8}_\d{6}$", stamp):
        stamp = _stamp_now()
    day = datetime.now().strftime("%Y-%m-%d")
    payload = {
        "nm_id": int(nm_id or 0),
        "page_url": str(page_url or "")[:500],
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "blocks": blocks,
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=1)
    with_photo = sum(1 for c in cards if c.get("image_url"))
    meta = {
        "kind": "dom",
        "nm_id": int(nm_id or 0),
        "url": str(page_url or "")[:500],
        "collected_at": payload["collected_at"],
        "size": len(raw),
        "blocks": len(blocks),
        "cards": len(cards),
        "with_photo": with_photo,
        "titles": [str(b.get("title") or "") for b in blocks][:10],
    }
    try:
        rel = search_raw_service._write_file(
            int(company_id), day, stamp, "dom", str(int(nm_id or 0)), raw, meta)
    except OSError as exc:
        return {"saved": False, "reason": str(exc)[:120]}
    return {"saved": True, "file": rel, "blocks": len(blocks), "cards": len(cards)}


async def save_shelf_raw(
    db: AsyncSession,
    company_id: int,
    user_id: int | None,
    data: dict,
) -> dict:
    """Сырой ответ WB по полкам карточки → файл + .meta.json.

    Расширение присылает тело ответа u-recom «как пришло» (0,3–0,6 МБ на
    блок). Файл нужен, чтобы позже переразобрать блок, не открывая карточку
    заново: WB меняет ответы, а товары в полке меняются каждый день.

    Сохраняем только по НАШИМ карточкам: у конкурентов сырых ответов было бы
    30–60 МБ на прогон сбора, а нужны они для наших блоков.
    """
    raw = str((data or {}).get("raw") or "")
    nm_id = _int((data or {}).get("nm_id")) or 0
    if not raw or not nm_id:
        raise ValueError("raw and nm_id required")
    own = await _own_nms(db, company_id, [nm_id])
    if not own:
        return {"ok": True, "skipped": True, "reason": "not_ours", "nm_id": nm_id}

    kind = _str(data.get("kind"), 16) or "recom"
    stamp = _str(data.get("stamp"), 20) or _stamp_now()
    if not re.match(r"^\d{8}_\d{6}$", stamp):
        stamp = _stamp_now()
    day = datetime.now().strftime("%Y-%m-%d")
    url = _str(data.get("url"), 2000)

    # Счётчики для meta — без открытия большого файла. Товары у WB лежат в
    # корне ответа (не в data), id пресета — в metadata.catalog_value.
    products_cnt = 0
    preset = 0
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for key in ("products", "items", "cards"):
                v = parsed.get(key)
                if isinstance(v, list):
                    products_cnt = len(v)
                    break
            md = parsed.get("metadata") or {}
            m = re.search(r"preset=(\d+)", str(md.get("catalog_value") or ""))
            if m:
                preset = int(m.group(1))
    except (ValueError, TypeError):
        parsed = None

    # В имени файла — id пресета: два ответа в одну секунду (два блока) не
    # должны перетирать друг друга.
    slug = f"{nm_id}_{preset}" if preset else str(nm_id)

    meta = {
        "kind": kind,
        "nm_id": nm_id,
        "preset_id": preset,
        "url": url,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "size": len(raw),
        "ext_token_id": data.get("ext_token_id"),
        "created_by": user_id,
        "products": products_cnt,
    }
    try:
        rel = search_raw_service._write_file(
            int(company_id), day, stamp, kind, slug, raw, meta)
    except OSError as exc:
        raise ValueError(f"Не удалось сохранить сырой ответ: {exc}") from exc
    return {"ok": True, "file": rel, "nm_id": nm_id, "products": products_cnt}
