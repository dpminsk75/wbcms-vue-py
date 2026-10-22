"""Сырые ответы поисковой выдачи WB: файлы + разбор в таблицы.

План: `2026-10-22_wb_search_json.md` (шаги Ш4а/Ш4б).

Что приходит из расширения (content_search.js -> background -> POST /api/ext/search_raw):
    { phrase, search_stamp: "20261022_143512", raw: { kind: {url, raw} } }
где kind в catalog | filters | shelfs | suggest, а raw — тело ответа WB «как пришло».

Что делаем:
  1) файл ответа: runtime/seo_search_raw/<company_id>/<YYYY-MM-DD>/<stamp>_<kind>_<slug>.json
     + рядом <stamp>_<kind>_<slug>.meta.json — компактные метаданные (без открытия большого файла);
  2) каталог -> дополняем `wb_competitor_position` полями из JSON
     (position_api/price_api/old_price_api/seller/match_id/... — НЕ трогаем DOM-поля:
     position, price, old_price, badges, image_url, rating, feedbacks);
  3) фильтры -> `wb_seo_search_filters` (профиль ниши: цены, бренды, продавцы, категории);
  4) баннеры/полки поиска -> `wb_seo_search_shelfs`;
  5) подсказки WB -> только файл (таблицы под них нет — по решению заказчика).
"""

from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import capture_service

RAW_ROOT = pathlib.Path(__file__).resolve().parents[1] / "runtime" / "seo_search_raw"

KINDS = ("catalog", "filters", "shelfs", "suggest")

# Буквы, которые оставляем в имени файла: латиница, цифры, кириллица, дефис.
_SLUG_RE = re.compile(r"[^0-9a-zA-Zа-яА-ЯёЁ]+")


# --------------------------------------------------------------------------
# Файлы
# --------------------------------------------------------------------------

def _slug(phrase: str) -> str:
    s = _SLUG_RE.sub("-", str(phrase or "").lower()).strip("-")
    return s[:40] or "no-phrase"


def _norm_phrase(raw: Any) -> str:
    """Нормализация фразы — общий хелпер (capture_service._norm_phrase)."""
    return capture_service._norm_phrase(raw)


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _day_of(stamp: str) -> str:
    s = re.sub(r"[^0-9]", "", str(stamp or ""))
    if len(s) >= 8:
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return datetime.now().strftime("%Y-%m-%d")


def _page_offset(url: str) -> int:
    """Смещение выдачи по URL ответа WB: (page-1) * limit.

    JSON-выдача приходит постранично: индекс в products[] — позиция ТОЛЬКО
    внутри страницы (каждый envelope перезаписывает предыдущий в
    content_search.js, на сервер доезжает последний page). Без поправки товар
    со страницы 2 получал бы position_api=1..N своей страницы, а не ранг в
    выдаче. page/limit лежат в query самого API-URL (u = ?query=..&page=2&limit=100);
    нет параметров — считаем первой страницей (offset 0, прежнее поведение).
    """
    try:
        q = parse_qs(urlparse(str(url or "")).query)
        page = int(str(q.get("page", ["1"])[0] or 1))
        limit = int(str(q.get("limit", ["100"])[0] or 100))
        if page < 1:
            page = 1
        if limit < 1:
            limit = 100
        return (page - 1) * limit
    except (TypeError, ValueError):
        return 0


def _raw_dir(cid: int, day: str) -> pathlib.Path:
    d = RAW_ROOT / str(int(cid)) / day
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_file(cid: int, day: str, stamp: str, kind: str, slug: str, raw: str, meta: dict) -> str:
    d = _raw_dir(cid, day)
    name = f"{stamp}_{kind}_{slug}.json"
    (d / name).write_text(raw, encoding="utf-8")
    (d / f"{stamp}_{kind}_{slug}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return str((d / name).relative_to(RAW_ROOT))


# --------------------------------------------------------------------------
# Разбор ответов
# --------------------------------------------------------------------------

def _loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _kop_to_rub(v: Any) -> int | None:
    """Копейки WB -> рубли (канон в базе — целые рубли)."""
    n = capture_service._to_int(v)
    if n is None:
        return None
    return int(round(n / 100))


def _num(v: Any) -> int | None:
    return capture_service._to_int(v)


def _items_of(fl: dict) -> list:
    items = fl.get("items")
    return items if isinstance(items, list) else []


def _parse_filters(data: dict) -> dict:
    """Профиль ниши по фразе: рамки цен, бренды, продавцы, категории, акции.

    WB меняет ключи фасетов (`ffbrand` -> `fbrand`, `f14177451` -> `ff14177451` и т.п.)
    и добавляет новые (`f1180`, `fpublisher`, `f1000000xxx`...) -> разбираем ЛЮБОЙ фильтр:
      - `priceU` / `fdlvr` -> отдельные числа;
      - фильтр со списком значений -> «фасет»: попадает в `facets` (всё как есть) и,
        если ключ известный, в именованную колонку;
      - переключатель-одиночка («Да»/«Нет») -> флаг.
    """
    d = data.get("data") or {}
    filters = d.get("filters") if isinstance(d.get("filters"), list) else []
    out: dict[str, Any] = {
        "total": _num(d.get("total")),
        "price_min": None,
        "price_max": None,
        "delivery_min": None,
        "delivery_max": None,
        "brands": [],
        "sellers": [],
        "subjects": [],
        "sale_factions": [],
        "countries": [],
        "ages": [],
        "delivery_types": [],
        "flags": [],
        "facets": {},
    }
    facets: dict[str, dict] = {}

    for fl in filters:
        if not isinstance(fl, dict):
            continue
        key = str(fl.get("key") or "")
        name = fl.get("name")
        items = _items_of(fl)
        if key == "priceU":
            out["price_min"] = _kop_to_rub(fl.get("minPriceU"))
            out["price_max"] = _kop_to_rub(fl.get("maxPriceU"))
            continue
        if key == "fdlvr":
            out["delivery_min"] = _num(fl.get("minTime"))
            out["delivery_max"] = _num(fl.get("maxTime"))
            continue
        if not items:
            out["flags"].append({
                "key": key, "name": name, "type": fl.get("type"),
                "maxselect": _num(fl.get("maxselect")), "items": 0,
            })
            continue
        vals = []
        for i in items:
            if not isinstance(i, dict):
                continue
            v: dict[str, Any] = {"id": _num(i.get("id")), "name": i.get("name")}
            if i.get("parentId") is not None:
                v["parentId"] = _num(i.get("parentId"))
                v["parentName"] = i.get("parentName")
            vals.append(v)
        # Переключатель вроде frating — это одно значение «Да», а не список брендов.
        if len(vals) == 1 and str(vals[0].get("name") or "").strip() in ("Да", "Нет"):
            out["flags"].append({
                "key": key, "name": name, "type": fl.get("type"),
                "maxselect": _num(fl.get("maxselect")), "items": 1,
            })
            continue
        facets[key] = {"name": name, "items": vals}

    out["facets"] = facets

    def pick(*keys: str) -> list:
        res: list = []
        for k in keys:
            f = facets.get(k)
            if f:
                res.extend(f.get("items") or [])
        return res

    out["brands"] = pick("fbrand", "ffbrand")
    out["sellers"] = pick("fsupplier")
    out["subjects"] = pick("xsubject")
    out["sale_factions"] = pick("faction")
    out["countries"] = pick("f14177451", "ff14177451")
    out["ages"] = pick("f392409", "ff392409")
    out["delivery_types"] = pick("fdtype")
    return out


def _thin_product(p: dict) -> dict:
    """Товар полки — только нужные поля (полка целиком в JSON-поле нечитаемо)."""
    if not isinstance(p, dict):
        return {}
    sizes = p.get("sizes") or []
    sz = sizes[0] if isinstance(sizes, list) and sizes and isinstance(sizes[0], dict) else {}
    pr = sz.get("price") or p.get("price") or {}
    return {
        "id": _num(p.get("id")),
        "name": (p.get("name") or "")[:300],
        "brand": (p.get("brand") or "")[:120],
        "brand_id": _num(p.get("brandId")),
        "seller": (p.get("supplier") or "")[:120],
        "seller_id": _num(p.get("supplierId")),
        "price": _kop_to_rub(pr.get("product")),
        "price_basic": _kop_to_rub(pr.get("basic")),
        "rating": capture_service._to_float(p.get("rating")),
        "review_rating": capture_service._to_float(p.get("reviewRating")),
        "feedbacks": _num(p.get("feedbacks")),
        "match_id": _num(p.get("matchId")),
        "promo_panel_id": _num(p.get("panelPromoId")),
    }


def _parse_shelfs(data: dict) -> dict:
    """Баннеры и брендовые полки В ПОИСКЕ (не полки карточки — это u-recom)."""
    d = data.get("data") or {}
    banners_raw = (d.get("banners") or {}).get("data") or []
    shelfs_raw = (d.get("shelfs") or {}).get("data") or []
    banners = []
    for b in banners_raw if isinstance(banners_raw, list) else []:
        if not isinstance(b, dict):
            continue
        adv = b.get("advParams") or {}
        banners.append({
            "uid": b.get("UID"),
            "cpm": b.get("cpm"),
            "type": b.get("Type"),
            "mark": b.get("OrdBannerMark"),
            "erid": b.get("ordBannerErid"),
            "url": (b.get("Href") or "")[:500],
            "src": (b.get("Src") or "")[:500],
            "is_commercial": bool(adv.get("is_commercial")) if isinstance(adv, dict) else None,
            "creative_type": adv.get("creative_type") if isinstance(adv, dict) else None,
            "ts": adv.get("timestamp") if isinstance(adv, dict) else None,
            "column": _num(b.get("column")),
        })
    shelfs = []
    products_cnt = 0
    sellers: dict[str, dict] = {}
    for sh in shelfs_raw if isinstance(shelfs_raw, list) else []:
        if not isinstance(sh, dict):
            continue
        prods = []
        for p in (sh.get("products") or []) if isinstance(sh.get("products"), list) else []:
            tp = _thin_product(p)
            if not tp.get("id"):
                continue
            prods.append(tp)
            products_cnt += 1
            name = tp.get("seller")
            if name:
                sellers.setdefault(name, {"name": name, "mark": sh.get("ordMark")})
        shelfs.append({
            "uid": sh.get("UID"),
            "title": (sh.get("title") or "")[:200],
            "url": (sh.get("href") or "")[:500],
            "mark": sh.get("ordMark"),
            "cpm": sh.get("cpm"),
            "type": sh.get("type"),
            "params": sh.get("params"),
            "products": prods,
        })
    for b in banners:
        mark = b.get("mark")
        if mark:
            sellers.setdefault(str(mark), {"name": str(mark), "mark": str(mark)})
    return {
        "banners": banners,
        "shelfs": shelfs,
        "banner_cnt": len(banners),
        "shelf_cnt": len(shelfs),
        "shelf_products_cnt": products_cnt,
        "sellers": list(sellers.values()),
    }


def _parse_suggest(data: Any) -> dict:
    """Подсказки/связанные запросы WB: [{sa, t, el:[{idx, st, q, txt}]}]."""
    groups = data if isinstance(data, list) else []
    out_groups = []
    total = 0
    for g in groups:
        if not isinstance(g, dict):
            continue
        el = g.get("el") if isinstance(g.get("el"), list) else []
        items = []
        for e in el:
            if not isinstance(e, dict):
                continue
            items.append({
                "idx": _num(e.get("idx")),
                "st": e.get("st"),
                "q": e.get("q"),
                "txt": e.get("txt"),
            })
        total += len(items)
        out_groups.append({"sa": _num(g.get("sa")), "t": g.get("t"), "items": items})
    return {"groups": out_groups, "suggestions": total}


def _catalog_summary(data: dict) -> dict:
    products = data.get("products") if isinstance(data.get("products"), list) else []
    prices: list[int] = []
    brands = set()
    sellers = set()
    promo = 0
    for p in products:
        if not isinstance(p, dict):
            continue
        if p.get("brand"):
            brands.add(p["brand"])
        if p.get("supplier"):
            sellers.add(p["supplier"])
        if p.get("panelPromoId"):
            promo += 1
        sizes = p.get("sizes") or []
        if isinstance(sizes, list) and sizes and isinstance(sizes[0], dict):
            pr = sizes[0].get("price") or {}
            r = _kop_to_rub(pr.get("product"))
            if r:
                prices.append(r)
    return {
        "products": len(products),
        "total": _num(data.get("total")),
        "brands": len(brands),
        "sellers": len(sellers),
        "promo_cnt": promo,
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
    }


# --------------------------------------------------------------------------
# Запись в таблицы
# --------------------------------------------------------------------------

async def _our_nms(db: AsyncSession, cid: int, ids: list) -> list:
    """Какие из товаров в выдаче — наши (по wbcards компании)."""
    ids = [int(i) for i in ids if i]
    if not ids:
        return []
    ph = ",".join(f":i{i}" for i in range(len(ids)))
    rows = (await db.execute(
        text(f"SELECT nmID FROM wbcards WHERE company_id=:cid AND nmID IN ({ph})"),
        {**{"cid": cid}, **{f"i{i}": v for i, v in enumerate(ids)}},
    )).scalars().all()
    return sorted({int(x) for x in rows})


async def _enrich_positions(
    db: AsyncSession, cid: int, uid: int | None, tok: int | None,
    phrase: str, products: list, day: str | None = None, offset: int = 0
) -> int:
    """Дополняем строки наблюдений полями из JSON-выдачи.

    DOM-поля (position, price, old_price, badges, image_url, rating, feedbacks) НЕ трогаем —
    их пишет /observe_search и /search_result. Здесь только то, чего в DOM нет.

    `offset` — поправка постраничности: (page-1)*limit из URL ответа, чтобы
    position_api был рангом в выдаче, а не индексом внутри страницы.
    """
    if not products:
        return 0
    ids = [int(p.get("id") or 0) for p in products if isinstance(p, dict) and p.get("id")]
    ours = await _our_nms(db, cid, ids)
    sources = ours if ours else [0]

    rows: list[dict] = []
    for idx, p in enumerate(products, 1):
        if not isinstance(p, dict):
            continue
        nm_id = int(p.get("id") or 0)
        if not nm_id:
            continue
        sizes = p.get("sizes") or []
        sz = sizes[0] if isinstance(sizes, list) and sizes and isinstance(sizes[0], dict) else {}
        pr = sz.get("price") or {}
        semantic = p.get("semanticId")
        rows.append({
            "nm_id": nm_id,
            # ранг в выдаче = позиция в странице + смещение страницы
            "position_api": idx + offset,
            "title": (p.get("name") or "")[:500],
            "brand": (p.get("brand") or "")[:255],
            "brand_id": _num(p.get("brandId")),
            "subject_id": _num(p.get("subjectId")),
            "root_id": _num(p.get("root")),
            "match_id": _num(p.get("matchId")),
            "seller": (p.get("supplier") or "")[:255],
            "seller_id": _num(p.get("supplierId")),
            "seller_rating": capture_service._to_float(p.get("supplierRating")),
            "price_api": _kop_to_rub(pr.get("product")),
            "old_price_api": _kop_to_rub(pr.get("basic")),
            # rating/feedbacks в JSON и в DOM — одно и то же, поэтому заполняем
            # и «DOM»-колонки: у товаров, которых не было в DOM (позиции 41+),
            # иначе эти поля пустые.
            "rating": capture_service._to_float(p.get("rating")),
            "review_rating": capture_service._to_float(p.get("reviewRating")),
            "reviews": _num(p.get("feedbacks")),
            "feedbacks": _num(p.get("feedbacks")),
            "feedback_points": _num(p.get("feedbackPoints")),
            "total_qty": _num(p.get("totalQuantity")),
            "time1": _num(p.get("time1")),
            "time2": _num(p.get("time2")),
            "wh": _num(p.get("wh")),
            "dist": _num(p.get("dist")),
            "volume": _num(p.get("volume")),
            "weight": capture_service._to_float(p.get("weight")),
            "pics": _num(p.get("pics")),
            "is_new": 1 if p.get("isNew") else 0,
            "promo_id": _num(p.get("panelPromoId")),
            # saleConditions лежит в sizes[0], а не в корне товара
            "sale_conditions": _num(sz.get("saleConditions", p.get("saleConditions"))),
            "dtype_mask": _num(p.get("dtypeMask")),
            # сырые флаги WB — как есть, без расшифровки битов
            "mtype": _num(p.get("mtype")),
            "supplier_flags": _num(p.get("supplierFlags")),
            "view_flags": _num(p.get("viewFlags")),
            "semantic_id": json.dumps(semantic) if isinstance(semantic, list) else None,
            "option_id": _num(sz.get("optionId")),
        })

    saved = 0
    for src in sources:
        for r in rows:
            await db.execute(text("""
                INSERT INTO wb_competitor_position
                  (company_id, source_nm_id, query_phrase, position, position_api, nm_id, title, brand,
                   brand_id, subject_id, root_id, match_id, seller, seller_id, seller_rating,
                   price, old_price, price_api, old_price_api, rating, review_rating, reviews, feedbacks, feedback_points, total_qty,
                   time1, time2, wh, dist, volume, weight, pics, is_new, promo_id, sale_conditions,
                   dtype_mask, semantic_id, option_id, mtype, supplier_flags, view_flags,
                   created_by, ext_token_id, collected_at)
                VALUES (:cid, :src, :ph, :pos, :pos_api, :nm, :t, :b,
                        :brand_id, :subject_id, :root_id, :match_id, :seller, :seller_id, :seller_rating,
                        :price, :old_price, :price_api, :old_price_api,
                        :rating, :review_rating, :reviews, :feedbacks,
                        :feedback_points, :total_qty,
                        :time1, :time2, :wh, :dist, :volume, :weight, :pics, :is_new, :promo_id,
                        :sale_conditions, :dtype_mask, :semantic_id, :option_id,
                        :mtype, :supplier_flags, :view_flags,
                        :uid, :tok, COALESCE(:day, CURDATE()))
                ON DUPLICATE KEY UPDATE
                  position_api=VALUES(position_api),
                  brand_id=VALUES(brand_id), subject_id=VALUES(subject_id), root_id=VALUES(root_id),
                  match_id=VALUES(match_id),
                  seller=IF(VALUES(seller)='', seller, VALUES(seller)),
                  seller_id=VALUES(seller_id), seller_rating=VALUES(seller_rating),
                  price=IF(price IS NULL OR price=0, VALUES(price), price),
                  old_price=IF(old_price IS NULL OR old_price=0, VALUES(old_price), old_price),
                  price_api=VALUES(price_api), old_price_api=VALUES(old_price_api),
                  rating=IF(VALUES(rating)>0, VALUES(rating), rating),
                  review_rating=IF(VALUES(review_rating)>0, VALUES(review_rating), review_rating),
                  reviews=IF(VALUES(reviews)>0, VALUES(reviews), reviews),
                  feedbacks=IF(VALUES(feedbacks)>0, VALUES(feedbacks), feedbacks),
                  feedback_points=VALUES(feedback_points), total_qty=VALUES(total_qty),
                  time1=VALUES(time1), time2=VALUES(time2), wh=VALUES(wh), dist=VALUES(dist),
                  volume=VALUES(volume), weight=VALUES(weight), pics=VALUES(pics),
                  is_new=VALUES(is_new), promo_id=VALUES(promo_id),
                  sale_conditions=VALUES(sale_conditions), dtype_mask=VALUES(dtype_mask),
                  semantic_id=VALUES(semantic_id), option_id=VALUES(option_id),
                  mtype=VALUES(mtype), supplier_flags=VALUES(supplier_flags),
                  view_flags=VALUES(view_flags)
            """), {
                "cid": cid, "src": src, "ph": _norm_phrase(phrase)[:500],
                "pos": r["position_api"], "pos_api": r["position_api"],
                "nm": r["nm_id"], "t": r["title"], "b": r["brand"],
                "brand_id": r["brand_id"], "subject_id": r["subject_id"], "root_id": r["root_id"],
                "match_id": r["match_id"], "seller": r["seller"], "seller_id": r["seller_id"],
                "seller_rating": r["seller_rating"],
                # price/old_price — цена из WB-каталога; если DOM уже записал свою,
                # не перетираем (см. ON DUPLICATE KEY UPDATE)
                "price": r["price_api"], "old_price": r["old_price_api"],
                "price_api": r["price_api"],
                "old_price_api": r["old_price_api"], "rating": r["rating"],
                "review_rating": r["review_rating"],
                "reviews": r["reviews"], "feedbacks": r["feedbacks"],
                "feedback_points": r["feedback_points"],
                "total_qty": r["total_qty"], "time1": r["time1"], "time2": r["time2"], "wh": r["wh"],
                "dist": r["dist"], "volume": r["volume"], "weight": r["weight"], "pics": r["pics"],
                "is_new": r["is_new"], "promo_id": r["promo_id"], "sale_conditions": r["sale_conditions"],
                "dtype_mask": r["dtype_mask"], "semantic_id": r["semantic_id"], "option_id": r["option_id"],
                "mtype": r["mtype"], "supplier_flags": r["supplier_flags"], "view_flags": r["view_flags"],
                "uid": uid, "tok": tok, "day": day,
            })
            saved += 1
    return saved


async def _save_filters(
    db: AsyncSession, cid: int, uid: int | None, tok: int | None,
    phrase: str, data: dict, file_name: str, day: str | None = None
) -> bool:
    f = _parse_filters(data)
    await db.execute(text("""
        INSERT INTO wb_seo_search_filters
          (company_id, query_phrase, phrase_norm, snapshot_date, collected_at, file_name, total,
           price_min, price_max, delivery_min, delivery_max, brands, sellers, subjects,
           sale_factions, countries, ages, delivery_types, flags, facets, created_by, ext_token_id)
        VALUES (:cid, :ph, :pn, COALESCE(:day, CURDATE()), NOW(), :fn, :total,
                :pmin, :pmax, :dmin, :dmax, :brands, :sellers, :subjects,
                :factions, :countries, :ages, :dtypes, :flags, :facets, :uid, :tok)
        ON DUPLICATE KEY UPDATE
          phrase_norm=VALUES(phrase_norm), collected_at=NOW(), file_name=VALUES(file_name),
          total=VALUES(total), price_min=VALUES(price_min), price_max=VALUES(price_max),
          delivery_min=VALUES(delivery_min), delivery_max=VALUES(delivery_max),
          brands=VALUES(brands), sellers=VALUES(sellers), subjects=VALUES(subjects),
          sale_factions=VALUES(sale_factions), countries=VALUES(countries),
          ages=VALUES(ages), delivery_types=VALUES(delivery_types), flags=VALUES(flags),
          facets=VALUES(facets),
          created_by=COALESCE(created_by, VALUES(created_by)),
          ext_token_id=COALESCE(ext_token_id, VALUES(ext_token_id))
    """), {
        "cid": cid, "ph": _norm_phrase(phrase)[:500], "pn": _norm_phrase(phrase),
        "fn": file_name, "day": day,
        "total": f["total"], "pmin": f["price_min"], "pmax": f["price_max"],
        "dmin": f["delivery_min"], "dmax": f["delivery_max"],
        "brands": json.dumps(f["brands"], ensure_ascii=False),
        "sellers": json.dumps(f["sellers"], ensure_ascii=False),
        "subjects": json.dumps(f["subjects"], ensure_ascii=False),
        "factions": json.dumps(f["sale_factions"], ensure_ascii=False),
        "countries": json.dumps(f["countries"], ensure_ascii=False),
        "ages": json.dumps(f["ages"], ensure_ascii=False),
        "dtypes": json.dumps(f["delivery_types"], ensure_ascii=False),
        "flags": json.dumps(f["flags"], ensure_ascii=False),
        "facets": json.dumps(f["facets"], ensure_ascii=False),
        "uid": uid, "tok": tok,
    })
    return True


async def _save_shelfs(
    db: AsyncSession, cid: int, uid: int | None, tok: int | None,
    phrase: str, data: dict, file_name: str, day: str | None = None
) -> bool:
    s = _parse_shelfs(data)
    await db.execute(text("""
        INSERT INTO wb_seo_search_shelfs
          (company_id, query_phrase, phrase_norm, snapshot_date, collected_at, file_name,
           banners, shelfs, banner_cnt, shelf_cnt, shelf_products_cnt, sellers, created_by,
           ext_token_id)
        VALUES (:cid, :ph, :pn, COALESCE(:day, CURDATE()), NOW(), :fn,
                :banners, :shelfs, :bcnt, :scnt, :pcnt, :sellers, :uid, :tok)
        ON DUPLICATE KEY UPDATE
          phrase_norm=VALUES(phrase_norm), collected_at=NOW(), file_name=VALUES(file_name),
          banners=VALUES(banners), shelfs=VALUES(shelfs),
          banner_cnt=VALUES(banner_cnt), shelf_cnt=VALUES(shelf_cnt),
          shelf_products_cnt=VALUES(shelf_products_cnt), sellers=VALUES(sellers),
          created_by=COALESCE(created_by, VALUES(created_by)),
          ext_token_id=COALESCE(ext_token_id, VALUES(ext_token_id))
    """), {
        "cid": cid, "ph": _norm_phrase(phrase)[:500], "pn": _norm_phrase(phrase),
        "fn": file_name, "day": day,
        "banners": json.dumps(s["banners"], ensure_ascii=False),
        "shelfs": json.dumps(s["shelfs"], ensure_ascii=False),
        "bcnt": s["banner_cnt"], "scnt": s["shelf_cnt"], "pcnt": s["shelf_products_cnt"],
        "sellers": json.dumps(s["sellers"], ensure_ascii=False),
        "uid": uid, "tok": tok,
    })
    return True


# --------------------------------------------------------------------------
# Точка входа
# --------------------------------------------------------------------------

async def save_search_raw(db: AsyncSession, ext: dict, payload: dict) -> dict:
    cid = int(ext["company_id"])
    uid = ext.get("created_by")
    tok = ext.get("id")
    token_name = str(ext.get("name") or "")[:64]
    data = payload or {}
    phrase = str(data.get("phrase") or "").strip()[:500]
    stamp = re.sub(r"[^0-9_]", "", str(data.get("search_stamp") or ""))[:15] or _now_stamp()
    raw_parts = data.get("raw") if isinstance(data.get("raw"), dict) else {}
    if not raw_parts:
        return {"ok": True, "saved": 0, "files": [], "note": "пусто"}

    day = _day_of(stamp)
    slug = _slug(phrase)
    files: list[str] = []
    positions = 0
    filters_saved = False
    shelfs_saved = False

    for kind, part in raw_parts.items():
        if kind not in KINDS or not isinstance(part, dict):
            continue
        raw = part.get("raw")
        if not isinstance(raw, str) or not raw:
            continue
        url = str(part.get("url") or "")[:2000]
        parsed = _loads(raw)

        meta = {
            "kind": kind,
            "phrase": phrase,
            "url": url,
            "search_stamp": stamp,
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "size": len(raw),
            # автор парсинга: какой токен/машина собрала
            "ext_token_id": tok,
            "ext_token_name": token_name,
            "created_by": uid,
        }

        if kind == "catalog":
            meta.update(_catalog_summary(parsed if isinstance(parsed, dict) else {}))
            file_name = _write_file(cid, day, stamp, kind, slug, raw, meta)
            products = parsed.get("products") if isinstance(parsed, dict) else []
            positions = await _enrich_positions(db, cid, uid, tok, phrase, products or [], day,
                                                offset=_page_offset(url))
        elif kind == "filters":
            f = _parse_filters(parsed if isinstance(parsed, dict) else {})
            meta.update({
                "total": f["total"],
                "brands": len(f["brands"]),
                "sellers": len(f["sellers"]),
                "subjects": len(f["subjects"]),
                "sale_factions": len(f["sale_factions"]),
            })
            file_name = _write_file(cid, day, stamp, kind, slug, raw, meta)
            filters_saved = await _save_filters(db, cid, uid, tok, phrase, parsed if isinstance(parsed, dict) else {}, file_name, day)
        elif kind == "shelfs":
            sh = _parse_shelfs(parsed if isinstance(parsed, dict) else {})
            meta.update({
                "banner_cnt": sh["banner_cnt"],
                "shelf_cnt": sh["shelf_cnt"],
                "shelf_products_cnt": sh["shelf_products_cnt"],
            })
            file_name = _write_file(cid, day, stamp, kind, slug, raw, meta)
            shelfs_saved = await _save_shelfs(db, cid, uid, tok, phrase, parsed if isinstance(parsed, dict) else {}, file_name, day)
        else:  # suggest — только файл
            sg = _parse_suggest(parsed)
            meta.update({"suggestions": sg["suggestions"], "groups": len(sg["groups"])})
            file_name = _write_file(cid, day, stamp, kind, slug, raw, meta)

        files.append(file_name)

    await db.commit()
    return {
        "ok": True,
        "saved": len(files),
        "files": files,
        "positions": positions,
        "filters": filters_saved,
        "shelfs": shelfs_saved,
        "phrase": phrase,
        "search_stamp": stamp,
    }
