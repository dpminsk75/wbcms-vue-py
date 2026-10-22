"""Отчёты по собранной поисковой выдаче WB — таблица `wb_competitor_position`.

Что собирает расширение: каждый заход человека в поиск WB даёт «срез» выдачи —
фраза, позиции, цены, бейджи акций. Срезы — дневные (`collected_at` DATE),
привязаны к компании и к нашим карточкам (`source_nm_id`, 0 = наших в выдаче не было).

Две сводки:
1. **По запросам** — какие фразы сохранены, когда, кем, и как выглядела выдача.
2. **По нашим товарам** — по карточке: запросы, наши позиции, топ конкурентов.

Скоуп — по компании (`company_id`), как в остальных отчётах.
"""

from __future__ import annotations

import json
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _norm_phrase(raw) -> str:
    """Нормализация фразы — как при записи (capture_service._norm_phrase)."""
    s = str(raw or "").lower()
    s = re.sub(r"[-_]+", " ", s)
    s = " ".join(s.split())
    s = s.strip(" .,;:!?'\"()[]{}«»—–")
    return s[:500]


# Нормализация фразы в SQL (MySQL 8): нижний регистр, дефисы/подчёркивания -> пробелы.
# Нужна, потому что WB отдаёт одну и ту же фразу и с дефисами (`search=` в URL страницы),
# и с пробелами (`query=` внутренних API) — а в БД это две разные строки.
# Переименовать старые строки нельзя: UNIQUE (company_id, source_nm_id, query_phrase, nm_id, collected_at).
# Поэтому объединяем варианты прямо в отчёте.
_NORM_SQL = (
    "LOWER(TRIM(REGEXP_REPLACE(REGEXP_REPLACE("
    "REPLACE(REPLACE(p.query_phrase, '-', ' '), '_', ' '), ' +', ' ')))"
)


def _json_list(v) -> list:
    """JSON-колонка → список (MySQL отдаёт str)."""
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip():
        try:
            d = json.loads(v)
        except Exception:
            return []
        return d if isinstance(d, list) else []
    return []


def _json_dict(v) -> dict:
    """JSON-колонка → словарь (MySQL отдаёт str)."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip():
        try:
            d = json.loads(v)
        except Exception:
            return {}
        return d if isinstance(d, dict) else {}
    return {}


def _d(v) -> str:
    """DATE → 'YYYY-MM-DD'."""
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v)[:10]


class CompetitorsPositionsService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # ---------- служебное ----------

    def _scope(self) -> tuple[str, dict]:
        if self.company_id is None:
            return "", {}
        return "AND p.company_id=:cid", {"cid": self.company_id}

    def _period(self, date_from: str | None, date_to: str | None) -> tuple[list[str], dict]:
        where = ["1=1"]
        params: dict = {}
        if date_from:
            where.append("p.collected_at >= :dfrom")
            params["dfrom"] = date_from
        if date_to:
            where.append("p.collected_at <= :dto")
            params["dto"] = date_to
        return where, params

    async def _users(self, ids: list[int]) -> dict[int, str]:
        ids = [int(i) for i in {int(x) for x in ids if x}]
        if not ids:
            return {}
        ph = ",".join(f":u{i}" for i in range(len(ids)))
        rows = (await self.db.execute(
            text(f"SELECT id, username FROM `user` WHERE id IN ({ph})"),
            {f"u{i}": v for i, v in enumerate(ids)},
        )).mappings().all()
        return {int(r["id"]): (r["username"] or "") for r in rows}

    # ---------- 1. сводка по запросам ----------

    async def phrases(self, date_from=None, date_to=None, q: str = "", limit: int = 200) -> dict:
        """Какие запросы сохранены: даты, число сохранений, наши карточки, кто сохранил."""
        scope, sparams = self._scope()
        where, params = self._period(date_from, date_to)
        if q:
            where.append(f"{_NORM_SQL} LIKE :q")
            params["q"] = f"%{_norm_phrase(q)}%"
        params.update(sparams)
        params["lim"] = max(1, min(int(limit or 200), 1000))

        rows = (await self.db.execute(text(f"""
            SELECT {_NORM_SQL} AS phrase,
                   GROUP_CONCAT(DISTINCT p.query_phrase) AS phrase_variants,
                   COUNT(*) AS rows_cnt,
                   COUNT(DISTINCT p.collected_at) AS days,
                   COUNT(DISTINCT p.nm_id) AS products,
                   MIN(p.collected_at) AS first_at,
                   MAX(p.collected_at) AS last_at,
                   GROUP_CONCAT(DISTINCT p.created_by) AS user_ids,
                   GROUP_CONCAT(DISTINCT p.ext_token_id) AS token_ids,
                   GROUP_CONCAT(DISTINCT p.source_nm_id) AS source_ids
            FROM wb_competitor_position p
            WHERE {' AND '.join(where)} {scope}
            GROUP BY {_NORM_SQL}
            ORDER BY last_at DESC, phrase
            LIMIT :lim
        """), params)).mappings().all()

        items: list[dict] = []
        all_users: list[int] = []
        all_tokens: list[int] = []
        all_sources: list[int] = []
        for r in rows:
            uids = [int(x) for x in (r.get("user_ids") or "").split(",") if x.strip().isdigit()]
            tids = [int(x) for x in (r.get("token_ids") or "").split(",") if x.strip().isdigit()]
            sids = [int(x) for x in (r.get("source_ids") or "").split(",") if x.strip().lstrip("-").isdigit()]
            all_users += uids
            all_tokens += tids
            all_sources += [s for s in sids if s > 0]
            items.append({
                "phrase": r["phrase"],
                "phrase_variants": [v for v in (r.get("phrase_variants") or "").split(",") if v],
                "rows": int(r["rows_cnt"] or 0),
                "days": int(r["days"] or 0),
                "products": int(r["products"] or 0),
                "first_at": _d(r["first_at"]),
                "last_at": _d(r["last_at"]),
                "user_ids": uids,
                "token_ids": tids,
                "source_ids": [s for s in sids if s > 0],
                "sources": [],
            })

        titles = await self._card_titles(all_sources)
        users = await self._users(all_users)
        tokens = await self._tokens(all_tokens)
        for it in items:
            it["sources"] = [
                {"nm_id": s, "title": titles.get(s, "")} for s in it["source_ids"]
            ]
            it["saved_by"] = [
                {
                    "id": u,
                    "username": users.get(u, ""),
                    "token_ids": it["token_ids"],
                    "tokens": [tokens.get(t, "") for t in it["token_ids"] if t in tokens],
                }
                for u in it["user_ids"]
            ]

        return {"items": items, "total": len(items)}

    async def _card_titles(self, nm_ids: list[int]) -> dict[int, str]:
        nm_ids = [int(i) for i in {int(x) for x in nm_ids if x}]
        if not nm_ids:
            return {}
        ph = ",".join(f":c{i}" for i in range(len(nm_ids)))
        rows = (await self.db.execute(
            text(f"SELECT nmID, title FROM wbcards WHERE nmID IN ({ph})"),
            {f"c{i}": v for i, v in enumerate(nm_ids)},
        )).mappings().all()
        return {int(r["nmID"]): (r["title"] or "") for r in rows}

    async def _tokens(self, token_ids: list[int]) -> dict[int, str]:
        """Имена ext-токенов (машин/авторов парсинга) по их id."""
        ids = [int(i) for i in {int(x) for x in token_ids if x}]
        if not ids:
            return {}
        ph = ",".join(f":t{i}" for i in range(len(ids)))
        rows = (await self.db.execute(
            text(f"SELECT id, name, token_prefix FROM ext_tokens WHERE id IN ({ph})"),
            {f"t{i}": v for i, v in enumerate(ids)},
        )).mappings().all()
        return {int(r["id"]): (r["name"] or r["token_prefix"] or "") for r in rows}

    # ---------- 2. выдача по фразе ----------

    async def phrase(self, phrase: str, date_from=None, date_to=None, day: str | None = None) -> dict:
        """Выдача по фразе — как она была сохранена (последний срез, если день не задан)."""
        # фраза в БД нормализованная (дефисы -> пробелы) — приводим и входящую
        phrase = _norm_phrase(phrase)
        if not phrase:
            return {"phrase": "", "date": "", "days": [], "items": [], "saved_by": []}
        scope, sparams = self._scope()
        where, params = self._period(date_from, date_to)
        where.append(f"{_NORM_SQL}=:ph")
        params["ph"] = phrase
        params.update(sparams)

        days = [ _d(r["d"]) for r in (await self.db.execute(text(f"""
            SELECT DISTINCT p.collected_at AS d
            FROM wb_competitor_position p
            WHERE {' AND '.join(where)} {scope}
            ORDER BY p.collected_at DESC
        """), params)).mappings().all() ]
        if not days:
            return {"phrase": phrase, "date": "", "days": [], "items": [], "saved_by": []}

        chosen = day if day in days else days[0]

        rows = (await self.db.execute(text(f"""
            SELECT p.position, p.position_api, p.nm_id, p.title, p.brand, p.seller,
                   p.price, p.old_price, p.price_api, p.old_price_api,
                   p.rating, p.review_rating, p.feedbacks, p.reviews, p.badges,
                   p.promo_id, p.is_adv, p.match_id, p.seller_id, p.seller_rating,
                   p.source_nm_id, p.created_by, p.ext_token_id, p.collected_at,
                   w.title AS source_title, w.vendorCode AS source_vendor
            FROM wb_competitor_position p
            LEFT JOIN wbcards w ON w.nmID = p.source_nm_id
            WHERE {' AND '.join(where)} {scope} AND p.collected_at=:day
            ORDER BY p.position, p.id
        """), {**params, "day": chosen})).mappings().all()

        users = await self._users([r["created_by"] for r in rows])
        items = []
        for r in rows:
            items.append({
                "position": int(r["position"] or 0),
                "position_api": r["position_api"],
                "nm_id": int(r["nm_id"] or 0),
                "title": r["title"] or "",
                "brand": r["brand"] or "",
                "seller": r["seller"] or "",
                "seller_id": r["seller_id"],
                "seller_rating": r["seller_rating"],
                "price": r["price"],
                "old_price": r["old_price"],
                "price_api": r["price_api"],
                "old_price_api": r["old_price_api"],
                "rating": r["rating"],
                "review_rating": r["review_rating"],
                "feedbacks": r["feedbacks"],
                "reviews": r["reviews"],
                "badges": _json_list(r["badges"]),
                "promo_id": r["promo_id"],
                "is_adv": int(r["is_adv"] or 0),
                "match_id": r["match_id"],
                "source_nm_id": int(r["source_nm_id"] or 0),
                "source_title": r["source_title"] or "",
                "source_vendor": r["source_vendor"] or "",
                "created_by": r["created_by"],
                "ext_token_id": r["ext_token_id"],
                "username": users.get(int(r["created_by"] or 0), "") if r["created_by"] else "",
                "at": _d(r["collected_at"]),
            })

        ours = sorted({i["source_nm_id"] for i in items if i["source_nm_id"]})
        titles = await self._card_titles(ours)
        tokens = await self._tokens([i["ext_token_id"] for i in items])
        for i in items:
            i["token_name"] = tokens.get(int(i["ext_token_id"] or 0), "")

        # Одна строка на товар: если наших карточек в выдаче несколько, конкурент
        # записан по каждой (привязка ко всем) — в отчёте это дубли, склеиваем.
        merged: dict[int, dict] = {}
        order: list[int] = []
        for it in items:
            nm = int(it["nm_id"] or 0)
            if nm not in merged:
                it = dict(it)
                it["source_nm_ids"] = [it["source_nm_id"]] if it["source_nm_id"] else []
                merged[nm] = it
                order.append(nm)
                continue
            m = merged[nm]
            if it["source_nm_id"] and it["source_nm_id"] not in m["source_nm_ids"]:
                m["source_nm_ids"].append(it["source_nm_id"])
            # оставляем вариант с более полными данными (position_api из JSON)
            if m.get("position_api") is None and it.get("position_api") is not None:
                keep = m["source_nm_ids"]
                m.update(it)
                m["source_nm_ids"] = keep
        items = [merged[nm] for nm in order]

        saved_by = {}
        for it in items:
            if it["created_by"]:
                saved_by.setdefault(int(it["created_by"]), {"id": int(it["created_by"]),
                                                            "username": it["username"],
                                                            "token_name": it["token_name"]})

        return {
            "phrase": phrase,
            "date": chosen,
            "days": days,
            "items": items,
            "sources": [{"nm_id": s, "title": titles.get(s, "")} for s in ours],
            "saved_by": list(saved_by.values()),
        }
    # ---------- 3. сводка по нашим карточкам ----------

    async def cards(self, date_from=None, date_to=None, limit: int = 300) -> dict:
        """Наши карточки, по которым есть наблюдения выдачи."""
        scope, sparams = self._scope()
        where, params = self._period(date_from, date_to)
        where.append("p.source_nm_id > 0")
        params.update(sparams)
        params["lim"] = max(1, min(int(limit or 300), 1000))

        rows = (await self.db.execute(text(f"""
            SELECT p.source_nm_id AS nm_id, w.title AS title, w.vendorCode AS vendor,
                   w.brand AS brand,
                   COUNT(DISTINCT {_NORM_SQL}) AS phrases,
                   COUNT(DISTINCT p.collected_at) AS days,
                   MIN(p.collected_at) AS first_at,
                   MAX(p.collected_at) AS last_at,
                   MIN(COALESCE(p.position_api, p.position)) AS best_position
            FROM wb_competitor_position p
            LEFT JOIN wbcards w ON w.nmID = p.source_nm_id
            WHERE {' AND '.join(where)} {scope}
            GROUP BY p.source_nm_id, w.title, w.vendorCode, w.brand
            ORDER BY last_at DESC
            LIMIT :lim
        """), params)).mappings().all()

        items = [{
            "nm_id": int(r["nm_id"] or 0),
            "title": r["title"] or "",
            "vendor": r["vendor"] or "",
            "brand": r["brand"] or "",
            "phrases": int(r["phrases"] or 0),
            "days": int(r["days"] or 0),
            "first_at": _d(r["first_at"]),
            "last_at": _d(r["last_at"]),
            "best_position": r["best_position"],
        } for r in rows]
        return {"items": items, "total": len(items)}

    # ---------- 5. профиль ниш (фильтры выдачи) ----------

    def _scope_plain(self) -> tuple[str, dict]:
        """Скоуп по компании для таблиц без алиаса p (профиль ниш, реклама)."""
        if self.company_id is None:
            return "", {}
        return "AND company_id=:cid", {"cid": self.company_id}

    def _period_plain(self, date_from, date_to) -> tuple[list[str], dict]:
        """Период по snapshot_date (дневной срез) для таблиц без алиаса p."""
        where = ["1=1"]
        params: dict = {}
        if date_from:
            where.append("snapshot_date >= :dfrom")
            params["dfrom"] = date_from
        if date_to:
            where.append("snapshot_date <= :dto")
            params["dto"] = date_to
        return where, params

    async def niches(self, date_from=None, date_to=None, limit: int = 300) -> dict:
        """Профиль ниши по фразе: рамки цен, бренды, продавцы, категории, акции.

        Источник — `wb_seo_search_filters` (разбор `resultset=filters`).
        """
        scope, sparams = self._scope_plain()
        where, params = self._period_plain(date_from, date_to)
        params.update(sparams)
        params["lim"] = max(1, min(int(limit or 300), 1000))
        rows = (await self.db.execute(text(f"""
            SELECT query_phrase, phrase_norm, snapshot_date, collected_at, file_name, total,
                   price_min, price_max, delivery_min, delivery_max,
                   brands, sellers, subjects, sale_factions, countries, ages, delivery_types,
                   flags, facets, created_by, ext_token_id
            FROM wb_seo_search_filters
            WHERE {' AND '.join(where)} {scope}
            ORDER BY collected_at DESC
            LIMIT :lim
        """), params)).mappings().all()

        items = []
        for r in rows:
            items.append({
                "phrase": _norm_phrase(r["query_phrase"]),
                "phrase_norm": r["phrase_norm"] or "",
                "date": _d(r["snapshot_date"]),
                "collected_at": _d(r["collected_at"]),
                "file_name": r["file_name"] or "",
                "total": r["total"],
                "price_min": r["price_min"],
                "price_max": r["price_max"],
                "delivery_min": r["delivery_min"],
                "delivery_max": r["delivery_max"],
                "brands": _json_list(r["brands"]),
                "sellers": _json_list(r["sellers"]),
                "subjects": _json_list(r["subjects"]),
                "sale_factions": _json_list(r["sale_factions"]),
                "countries": _json_list(r["countries"]),
                "ages": _json_list(r["ages"]),
                "delivery_types": _json_list(r["delivery_types"]),
                "flags": _json_list(r["flags"]),
                "facets": _json_dict(r["facets"]),
                "created_by": r["created_by"],
                "ext_token_id": r["ext_token_id"],
            })
        items = _merge_by_phrase(items)
        return {"items": items, "total": len(items)}

    # ---------- 6. реклама и полки в поиске ----------

    async def ads(self, date_from=None, date_to=None, limit: int = 200) -> dict:
        """Баннеры (реклама продавцов) и брендовые полки В ПОИСКЕ.

        Источник — `wb_seo_search_shelfs` (разбор `banners/shelfs/search`).
        """
        scope, sparams = self._scope_plain()
        where, params = self._period_plain(date_from, date_to)
        params.update(sparams)
        params["lim"] = max(1, min(int(limit or 200), 1000))
        rows = (await self.db.execute(text(f"""
            SELECT query_phrase, snapshot_date, collected_at, file_name,
                   banners, shelfs, banner_cnt, shelf_cnt, shelf_products_cnt, sellers, created_by
            FROM wb_seo_search_shelfs
            WHERE {' AND '.join(where)} {scope}
            ORDER BY collected_at DESC
            LIMIT :lim
        """), params)).mappings().all()

        items = []
        for r in rows:
            banners = _json_list(r["banners"])
            shelfs = _json_list(r["shelfs"])
            items.append({
                "phrase": r["query_phrase"] or "",
                "date": _d(r["snapshot_date"]),
                "collected_at": _d(r["collected_at"]),
                "file_name": r["file_name"] or "",
                "banner_cnt": int(r["banner_cnt"] or 0),
                "shelf_cnt": int(r["shelf_cnt"] or 0),
                "shelf_products_cnt": int(r["shelf_products_cnt"] or 0),
                "banners": banners,
                "shelfs": [
                    {
                        "title": s.get("title") or "",
                        "url": s.get("url") or "",
                        "mark": s.get("mark") or "",
                        "cpm": s.get("cpm") or "",
                        "products": s.get("products") or [],
                    }
                    for s in shelfs if isinstance(s, dict)
                ],
                "sellers": _json_list(r["sellers"]),
                "created_by": r["created_by"],
            })
        items = _merge_by_phrase(items)
        return {"items": items, "total": len(items)}

    # ---------- 4. отчёт по одной нашей карточке ----------

    async def card(self, nm_id: int, date_from=None, date_to=None, top: int = 12) -> dict:
        """По нашей карточке: запросы, наши позиции, топ конкурентов по каждой фразе.

        `top` — сколько конкурентов показывать (0 = все).
        """
        scope, sparams = self._scope()
        where, params = self._period(date_from, date_to)
        params.update(sparams)

        card_row = (await self.db.execute(
            text("SELECT nmID, title, vendorCode, brand FROM wbcards WHERE nmID=:n LIMIT 1"),
            {"n": nm_id},
        )).mappings().first()

        # все строки выдачи, привязанные к нашей карточке
        rows = (await self.db.execute(text(f"""
            SELECT p.query_phrase, p.collected_at, p.position, p.position_api,
                   p.nm_id, p.title, p.brand, p.seller, p.seller_id, p.seller_rating,
                   p.price, p.old_price, p.price_api, p.old_price_api,
                   p.rating, p.review_rating, p.feedbacks, p.reviews,
                   p.badges, p.promo_id, p.match_id, p.created_by, p.source_nm_id
            FROM wb_competitor_position p
            WHERE {' AND '.join(where)} {scope} AND p.source_nm_id=:our
            ORDER BY p.query_phrase, p.collected_at, p.position
        """), {**params, "our": nm_id})).mappings().all()

        # фраза может прийти двумя способами (с дефисами / с пробелами) — в отчёте это одна фраза
        by_phrase: dict[str, list] = {}
        for r in rows:
            by_phrase.setdefault(_norm_phrase(r["query_phrase"]), []).append(r)

        users = await self._users([r["created_by"] for r in rows])
        phrases: list[dict] = []
        our_history: list[dict] = []

        for phrase, items in by_phrase.items():
            days = sorted({_d(r["collected_at"]) for r in items})
            last_day = days[-1] if days else ""
            last_items = [r for r in items if _d(r["collected_at"]) == last_day]

            competitors = []
            for r in last_items:
                if int(r["nm_id"] or 0) == int(nm_id):
                    continue
                competitors.append({
                    "position": int(r["position"] or 0),
                    "position_api": r["position_api"],
                    "nm_id": int(r["nm_id"] or 0),
                    "title": r["title"] or "",
                    "brand": r["brand"] or "",
                    "seller": r["seller"] or "",
                    "seller_id": r["seller_id"],
                    "seller_rating": r["seller_rating"],
                    "price": r["price"],
                    "old_price": r["old_price"],
                    "price_api": r["price_api"],
                    "old_price_api": r["old_price_api"],
                    "rating": r["rating"],
                    "review_rating": r["review_rating"],
                    "feedbacks": r["feedbacks"],
                    "reviews": r["reviews"],
                    "badges": _json_list(r["badges"]),
                    "promo_id": r["promo_id"],
                    "match_id": r["match_id"],
                    "username": users.get(int(r["created_by"] or 0), "") if r["created_by"] else "",
                })
            competitors.sort(key=lambda x: x["position"])
            if top:
                competitors = competitors[: int(top)]

            our_positions = []
            for d in days:
                pos = None
                price = None
                for r in items:
                    if _d(r["collected_at"]) != d:
                        continue
                    if int(r["nm_id"] or 0) == int(nm_id):
                        pos = int(r["position"] or 0)
                        price = r["price"]
                        our_history.append({
                            "phrase": phrase,
                            "date": d,
                            "position": pos,
                            "price": price,
                        })
                our_positions.append({"date": d, "position": pos, "price": price})

            positions = [p["position"] for p in our_positions if p["position"]]
            phrases.append({
                "phrase": phrase,
                "days": days,
                "last_day": last_day,
                "our_positions": our_positions,
                "last_position": positions[-1] if positions else None,
                "best_position": min(positions) if positions else None,
                "competitors": competitors,
                "products": len({int(r["nm_id"] or 0) for r in last_items}),
            })

        phrases.sort(key=lambda x: (x["last_day"], x["phrase"]), reverse=True)
        return {
            "card": {
                "nm_id": int(nm_id),
                "title": (card_row["title"] if card_row else "") or "",
                "vendor": (card_row["vendorCode"] if card_row else "") or "",
                "brand": (card_row["brand"] if card_row else "") or "",
            },
            "phrases": phrases,
            "our_history": sorted(our_history, key=lambda x: (x["date"], x["phrase"])),
        }
