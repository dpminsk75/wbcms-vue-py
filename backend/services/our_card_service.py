"""Полки и баджи НАШЕЙ карточки — модалка «Полки и баджи» на /wb/detail.

Данные лежат в тех же таблицах, что и у конкурента, просто по nmID нашей
карточки:

- полки — `wb_competitor_cards_shelf` (+ `..._shelf_item`): их пишет
  расширение пассивно, когда открывает страницу карточки
  (`content_shelf.js` → `/api/ext/shelves`), и `nm_id` там = карточка, на
  которой полку увидели. Два направления:
    * блоки НА нашей карточке («Смотрите также», «Продавец рекомендует»);
    * блоки ЧУЖИХ карточек, в которых видели нас (`items.nm_id` = наша);
- баджи/цена — `wb_competitor_details`: их пишет расширение, когда собирает
  карточку (`/api/ext/result`). Пока карточку не собрали — баджей нет;
  история бейджей — `wb_card_badges_history` (снимок при смене набора).

Очередь сбора — `wb_enrich_queue`, очередь SEO-мониторинга (`source='watch'`):
расширение в режиме «Из SEO-мониторинг» берёт оттуда строки, свои карточки
не исключены, правок расширения для этого не нужно.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Ограничения ответа: блок полки — это десятки карточек, а блоков на карточке
# бывает несколько. Режем, чтобы модалка не превратилась в простыню.
MAX_BLOCKS = 12
MAX_ITEMS_PER_BLOCK = 60
# Сколько чужих карточек показывать в «Где мы на полках».
MAX_ANCHORS = 60


def _badges(raw: Any) -> list[str]:
    """Колонка badges (JSON) -> список строк."""
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        try:
            v = json.loads(raw)
        except (ValueError, TypeError):
            return []
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
    return []


def _d(v: Any) -> str:
    """DATE/DATETIME -> 'YYYY-MM-DD'."""
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10]
    return str(v)[:10]


def _clean_shelf_title(t: Any) -> str:
    """Подпись блока из DOM — только если это правда подпись блока.

    В словаре пресетов остался мусор от старых версий расширения: названия
    товаров в формате WB «Бренд/Название» (например «Город Медиа Софт/Дневник
    садовода…»). Такое отсекаем — подпись блока без «/» и «₽», до 60 символов
    (те же правила, что в расширении).
    """
    s = str(t or "").strip()
    if not s or len(s) > 60:
        return ""
    if "/" in s or "₽" in s:
        return ""
    return s


class OurCardService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # ------------------------------------------------------------------ utils

    def _scope(self) -> tuple[str, dict]:
        """Скоуп полок по компании (company_id = NULL — глобальный админ)."""
        if self.company_id is None:
            return "", {}
        return "AND s.company_id = :cid", {"cid": int(self.company_id)}

    @staticmethod
    def _inlist(prefix: str, values: list) -> tuple[str, dict]:
        if not values:
            return "", {}
        ph = ",".join(f":{prefix}{i}" for i in range(len(values)))
        return ph, {f"{prefix}{i}": v for i, v in enumerate(values)}

    async def is_ours(self, nm_id: int) -> bool:
        """Карточка наша? (wbcards компании; `company_id IS NULL` — легаси-своя)."""
        n = int(nm_id or 0)
        if n <= 0:
            return False
        row = (await self.db.execute(text("""
            SELECT company_id FROM wbcards WHERE nmID=:n LIMIT 1
        """), {"n": n})).first()
        if not row:
            return False
        if self.company_id is None:
            return True
        return row[0] is None or int(row[0]) == int(self.company_id)

    # --------------------------------------------------------------- карточка

    async def _details_row(self, nm_id: int) -> dict | None:
        row = (await self.db.execute(text("""
            SELECT title, price, old_price, badges, sold_out, is_resale,
                   COALESCE(collected_at, first_collected_at) AS collected_at,
                   full_collected_at
            FROM wb_competitor_details
            WHERE nm_id=:n
            ORDER BY COALESCE(collected_at, first_collected_at) DESC, id DESC LIMIT 1
        """), {"n": int(nm_id)})).mappings().first()
        return dict(row) if row else None

    async def card(self, nm_id: int) -> dict:
        """Всё для модалки: бейджи/цена + блоки нашей карточки + где мы на полках."""
        n = int(nm_id or 0)
        if n <= 0:
            return {"nm_id": 0, "badges": [], "blocks": [], "where": []}

        row = await self._details_row(n)
        badges = _badges(row.get("badges")) if row else []
        if row and row.get("is_resale") and "ресейл" not in badges:
            badges = badges + ["ресейл"]

        queue = (await self.db.execute(text("""
            SELECT status, source, requested_at FROM wb_enrich_queue
            WHERE nm_id=:n AND (company_id=:c OR company_id IS NULL)
            ORDER BY id DESC LIMIT 1
        """), {"n": n, "c": self.company_id})).mappings().first()

        blocks = await self.blocks(n)
        return {
            "nm_id": n,
            "title": (row.get("title") if row else "") or "",
            "price": row.get("price") if row else None,
            "old_price": row.get("old_price") if row else None,
            "badges": badges,
            "sold_out": 1 if (row and row.get("sold_out")) else 0,
            "is_resale": 1 if (row and row.get("is_resale")) else 0,
            "collected": bool(row),
            "full_collected": bool(row and row.get("full_collected_at")),
            "collected_at": row.get("collected_at") if row else None,
            "full_collected_at": row.get("full_collected_at") if row else None,
            "in_queue": bool(queue and str(queue.get("status") or "") == "pending"),
            "queue_status": str(queue.get("status") or "") if queue else "",
            "queue_requested_at": queue.get("requested_at") if queue else None,
            "blocks": blocks,
        }

    async def badge_history(self, nm_id: int) -> list[dict]:
        """История бейджей карточки (снимки при смене набора)."""
        try:
            rows = (await self.db.execute(text("""
                SELECT badges, price, at FROM wb_card_badges_history
                WHERE nm_id=:n AND (company_id=:c OR company_id=0)
                ORDER BY at DESC, id DESC LIMIT 50
            """), {"n": int(nm_id), "c": self.company_id})).mappings().all()
        except Exception:
            # Миграция 20261038 ещё не применена — истории просто нет.
            await self.db.rollback()
            return []
        out: list[dict] = []
        for r in rows:
            b = _badges(r.get("badges"))
            if not b:
                continue
            out.append({"badges": b, "price": r.get("price"),
                        "at": r.get("at").isoformat(sep=" ", timespec="seconds")
                        if isinstance(r.get("at"), datetime) else str(r.get("at") or "")})
        return out

    # ------------------------------------------------------------------ полки

    async def _shelf_headers(self, shelf_ids: list[int]) -> dict[int, dict]:
        """Шапки блоков: карточка-якорь + подпись блока."""
        if not shelf_ids:
            return {}
        ph, cp = self._inlist("h", shelf_ids)
        scope, sparams = self._scope()
        rows = (await self.db.execute(text(f"""
            SELECT s.id AS shelf_id, s.nm_id AS anchor_nm, s.preset_id, s.preset_type,
                   s.kind, s.is_partial, s.total_candidates, s.dest, s.last_seen_at,
                   s.title AS title_snap, p.title AS title_dict
            FROM wb_competitor_cards_shelf s
            LEFT JOIN wb_competitor_cards_shelf_preset p ON p.preset_id = s.preset_id
            WHERE s.id IN ({ph}) {scope}
        """), {**cp, **sparams})).mappings().all()
        out: dict[int, dict] = {}
        for r in rows:
            h = dict(r)
            h["title_clean"] = (_clean_shelf_title(h.get("title_snap"))
                                or _clean_shelf_title(h.get("title_dict")))
            h["title"] = h["title_clean"] or f"#{int(h.get('preset_id') or 0)}"
            out[int(r["shelf_id"])] = h
        return out

    async def _items(self, shelf_ids: list[int], dates: list[str]) -> dict[tuple[int, str], list[dict]]:
        """Позиции блоков за указанные снимки: (shelf_id, дата) -> позиции."""
        if not shelf_ids or not dates:
            return {}
        sph, sp = self._inlist("s", shelf_ids)
        dph, dp = self._inlist("d", dates)
        sql = f"""
            SELECT i.shelf_id, i.snapshot_date, i.nm_id, i.position, i.name, i.price,
                   i.price_basic, i.seller, i.brand, i.rating, i.review_rating,
                   i.feedbacks, i.cashback, i.is_new, i.is_own, i.image_url, i.badges
            FROM wb_competitor_cards_shelf_item i
            WHERE i.shelf_id IN ({sph}) AND i.snapshot_date IN ({dph})
            ORDER BY i.shelf_id, i.position
        """
        try:
            rows = (await self.db.execute(text(sql), {**sp, **dp})).mappings().all()
        except Exception:
            # Миграции 20261037/20261039 (image_url, badges) ещё не применены —
            # читаем без них.
            await self.db.rollback()
            sql_old = sql.replace(", i.image_url", "").replace(", i.badges", "")
            rows = (await self.db.execute(text(sql_old), {**sp, **dp})).mappings().all()
        if not rows:
            return {}
        nms = sorted({int(r["nm_id"] or 0) for r in rows if int(r["nm_id"] or 0)})
        meta = await self._cards_meta(nms)
        out: dict[tuple[int, str], list[dict]] = {}
        for r in rows:
            nm = int(r["nm_id"] or 0)
            extra = meta.get(nm, {})
            key = (int(r["shelf_id"]), _d(r["snapshot_date"]))
            # бейджи: сперва из DOM полки («−48%», «за отзыв 200»), потом из
            # реестра конкурентов («Хорошая цена» из выдачи) — без дублей.
            badges = _badges(r.get("badges"))
            for b in (extra.get("badges") or []):
                if b not in badges:
                    badges.append(b)
            out.setdefault(key, []).append({
                "nm_id": nm,
                "position": int(r["position"] or 0),
                "title": r.get("name") or "",
                "brand": r.get("brand") or "",
                "seller": r.get("seller") or "",
                "price": r.get("price"),
                "old_price": r.get("price_basic"),
                "rating": r.get("rating"),
                "review_rating": r.get("review_rating"),
                "feedbacks": r.get("feedbacks"),
                "cashback": r.get("cashback"),
                "is_new": 1 if r.get("is_new") else 0,
                "is_own": 1 if r.get("is_own") else 0,
                "image_url": r.get("image_url") or extra.get("image_url") or "",
                "badges": badges,
            })
        for items in out.values():
            items.sort(key=lambda x: x["position"])
            del items[MAX_ITEMS_PER_BLOCK:]
        return out

    async def _cards_meta(self, nm_ids: list[int]) -> dict[int, dict]:
        """Название/фото/бейджи карточек из реестра конкурентов (наблюдения выдачи)."""
        out: dict[int, dict] = {}
        ids = sorted({int(n) for n in nm_ids if n})
        for i in range(0, len(ids), 400):
            ch = ids[i:i + 400]
            ph, cp = self._inlist("m", ch)
            try:
                rows = (await self.db.execute(text(f"""
                    SELECT nm_id, title, badges, image_url FROM wb_competitor_cards
                    WHERE nm_id IN ({ph})
                      AND (COALESCE(image_url,'') <> '' OR COALESCE(badges,'') NOT IN ('', '[]')
                           OR COALESCE(title,'') <> '')
                    ORDER BY id
                """), cp)).mappings().all()
            except Exception:
                await self.db.rollback()
                continue
            for r in rows:
                nm = int(r["nm_id"] or 0)
                cur = out.setdefault(nm, {"badges": [], "image_url": "", "title": ""})
                b = _badges(r.get("badges"))
                if b:
                    cur["badges"] = b
                if r.get("image_url"):
                    cur["image_url"] = r["image_url"]
                if r.get("title"):
                    cur["title"] = r["title"]
        return out

    async def blocks(self, nm_id: int, snap: str = "") -> list[dict]:
        """Блоки (полки) НА нашей карточке: заголовок, даты срезов, позиции.

        `snap` — показать снимок за дату (иначе — последний).
        """
        n = int(nm_id or 0)
        if n <= 0:
            return []
        scope, sparams = self._scope()
        rows = (await self.db.execute(text(f"""
            SELECT s.id AS shelf_id, s.preset_id, s.preset_type, s.kind, s.is_partial,
                   s.total_candidates, s.dest, s.last_seen_at,
                   s.title AS title_snap, p.title AS title_dict
            FROM wb_competitor_cards_shelf s
            LEFT JOIN wb_competitor_cards_shelf_preset p ON p.preset_id = s.preset_id
            WHERE s.nm_id = :n {scope}
            ORDER BY s.preset_id, s.id
            LIMIT :lim
        """), {"n": n, "lim": MAX_BLOCKS, **sparams})).mappings().all()
        shelves = [dict(r) for r in rows]
        for s in shelves:
            s["title"] = (_clean_shelf_title(s.get("title_snap"))
                           or _clean_shelf_title(s.get("title_dict"))
                           or f"#{int(s.get('preset_id') or 0)}")
            s["title_fresh"] = _clean_shelf_title(s.get("title_snap"))
        if not shelves:
            return []
        ids = [int(s["shelf_id"]) for s in shelves]

        # снимки (даты) по каждому блоку
        sph, sp = self._inlist("b", ids)
        drows = (await self.db.execute(text(f"""
            SELECT shelf_id, snapshot_date, COUNT(*) AS items_cnt
            FROM wb_competitor_cards_shelf_item
            WHERE shelf_id IN ({sph})
            GROUP BY shelf_id, snapshot_date
            ORDER BY snapshot_date DESC
        """), sp)).mappings().all()
        dates: dict[int, list[str]] = {}
        counts: dict[tuple[int, str], int] = {}
        for r in drows:
            sid = int(r["shelf_id"])
            d = _d(r["snapshot_date"])
            dates.setdefault(sid, []).append(d)
            counts[(sid, d)] = int(r["items_cnt"] or 0)

        # какой снимок показываем
        chosen: dict[int, str] = {}
        for s in shelves:
            sid = int(s["shelf_id"])
            ds = dates.get(sid) or []
            if not ds:
                continue
            if snap and snap in ds:
                chosen[sid] = snap
            else:
                chosen[sid] = ds[0]
        want_dates = sorted(set(chosen.values()))
        items = await self._items(ids, want_dates)

        out: list[dict] = []
        for s in shelves:
            sid = int(s["shelf_id"])
            ds = dates.get(sid) or []
            if not ds:
                continue
            cur = chosen.get(sid) or ds[0]
            out.append({
                "shelf_id": sid,
                "preset_id": s.get("preset_id"),
                "preset_type": s.get("preset_type") or "",
                "kind": s.get("kind") or "",
                "title": s.get("title") or "",
                # подпись блока, выученная из DOM (пусто — словарь/пресет)
                "title_fresh": s.get("title_fresh") or "",
                "is_partial": 1 if s.get("is_partial") else 0,
                "total_candidates": s.get("total_candidates"),
                "last_seen_at": s.get("last_seen_at").isoformat(sep=" ", timespec="seconds")
                if isinstance(s.get("last_seen_at"), datetime) else None,
                "dates": ds,
                "date": cur,
                "items_cnt": counts.get((sid, cur), 0),
                "items": items.get((sid, cur), []),
            })
        return out

    async def where(self, nm_id: int, date_from: str, date_to: str) -> list[dict]:
        """Где мы на полках: карточки КОНКУРЕНТОВ, в чьих полках нас видели.

        Только чужие карточки: наши собственные страницы — это первая вкладка
        («Полки в нашей карточке»), в «где мы» они бы дублировались (блок
        «Продавец рекомендует» висит на страницах всех наших карточек, и там
        нас тоже видно).

        По каждой чужой карточке — наша позиция в её блоке и дата среза.
        """
        n = int(nm_id or 0)
        if n <= 0:
            return []
        scope, sparams = self._scope()
        rows = (await self.db.execute(text(f"""
            SELECT i.shelf_id, i.snapshot_date, i.position
            FROM wb_competitor_cards_shelf_item i
            JOIN wb_competitor_cards_shelf s ON s.id = i.shelf_id
            WHERE i.nm_id = :n {scope}
              AND i.snapshot_date BETWEEN :d1 AND :d2
            ORDER BY i.snapshot_date DESC, i.position
            LIMIT 2000
        """), {"n": n, "d1": date_from, "d2": date_to, **sparams})).mappings().all()
        if not rows:
            return []
        # по странице (shelf_id) — последний снимок периода (строки по дате DESC)
        latest: dict[int, tuple[str, int]] = {}
        for r in rows:
            sid = int(r["shelf_id"])
            if sid not in latest:
                latest[sid] = (_d(r["snapshot_date"]), int(r["position"] or 0))
        headers = await self._shelf_headers(sorted(latest))

        anchors: list[dict] = []
        nms: list[int] = []
        for sid, (d, pos) in latest.items():
            h = headers.get(sid)
            if not h:
                continue
            anchor_nm = int(h.get("anchor_nm") or 0)
            if anchor_nm:
                nms.append(anchor_nm)
            anchors.append({
                "shelf_id": sid,
                "anchor_nm": anchor_nm,
                # Подпись блока — только если она похожа на подпись блока
                # (в словаре остался мусор — названия товаров «Бренд/Название»).
                "shelf_title": h.get("title_clean") or "",
                "preset_id": h.get("preset_id"),
                "kind": h.get("kind") or "",
                "date": d,
                "position": pos,
            })
        if not anchors:
            return []

        # Наши карточки из «где мы» убираем — они в первой вкладке.
        ours = await self._own_nms(nms)
        if ours:
            anchors = [a for a in anchors if a["anchor_nm"] not in ours]
        if not anchors:
            return []

        meta = await self._cards_meta([a["anchor_nm"] for a in anchors])
        # карточка конкурента: заголовок/цена/рейтинг — из собранного контента
        details = await self._details_by_nm([a["anchor_nm"] for a in anchors])
        for a in anchors:
            nm = a["anchor_nm"]
            m = meta.get(nm, {})
            det = details.get(nm, {})
            a["title"] = det.get("title") or m.get("title") or ""
            a["image_url"] = m.get("image_url") or det.get("image_url") or ""
            a["badges"] = m.get("badges") or det.get("badges") or []
            a["price"] = det.get("price")
            a["old_price"] = det.get("old_price")
            a["seller"] = det.get("seller") or ""
            a["brand"] = det.get("brand") or ""
            a["rating"] = det.get("rating")
            a["review_rating"] = det.get("review_rating")
            a["feedbacks"] = det.get("feedbacks")
        # свежие срезы сверху; внутри даты — по позиции (порядок из запроса)
        anchors.sort(key=lambda x: x["date"], reverse=True)
        return anchors[:MAX_ANCHORS]

    async def _own_nms(self, nm_ids: list[int]) -> set[int]:
        """Наши карточки среди nm (wbcards компании; `company_id IS NULL` — легаси)."""
        ids = sorted({int(n) for n in nm_ids if n})
        if not ids:
            return set()
        out: set[int] = set()
        for i in range(0, len(ids), 400):
            ch = ids[i:i + 400]
            ph, cp = self._inlist("o", ch)
            params = dict(cp)
            cond = ""
            if self.company_id is not None:
                cond = " AND (company_id=:cid OR company_id IS NULL)"
                params["cid"] = int(self.company_id)
            try:
                rows = (await self.db.execute(text(f"""
                    SELECT nmID FROM wbcards WHERE nmID IN ({ph}){cond}
                """), params)).mappings().all()
            except Exception:
                await self.db.rollback()
                continue
            for r in rows:
                out.add(int(r["nmID"] or 0))
        return out

    async def _details_by_nm(self, nm_ids: list[int]) -> dict[int, dict]:
        """Собранный контент карточек: nm -> {title, price, seller, rating...}."""
        out: dict[int, dict] = {}
        ids = sorted({int(n) for n in nm_ids if n})
        for i in range(0, len(ids), 400):
            ch = ids[i:i + 400]
            ph, cp = self._inlist("d", ch)
            try:
                rows = (await self.db.execute(text(f"""
                    SELECT nm_id, title, price, old_price, seller, brand, rating,
                           review_rating, feedbacks, images, badges
                    FROM wb_competitor_details
                    WHERE nm_id IN ({ph})
                    ORDER BY COALESCE(collected_at, first_collected_at) DESC, id DESC
                """), cp)).mappings().all()
            except Exception:
                await self.db.rollback()
                continue
            for r in rows:
                nm = int(r["nm_id"] or 0)
                if nm in out:
                    continue
                out[nm] = {
                    "title": r.get("title") or "",
                    "price": r.get("price"),
                    "old_price": r.get("old_price"),
                    "seller": r.get("seller") or "",
                    "brand": r.get("brand") or "",
                    "rating": r.get("rating"),
                    "review_rating": r.get("review_rating"),
                    "feedbacks": r.get("feedbacks"),
                    "badges": _badges(r.get("badges")),
                    "image_url": _first_image(r.get("images")),
                }
        return out

    async def block_items(self, shelf_id: int, snap: str = "") -> dict:
        """Вся собранная полка (блок) конкурента на снимок."""
        sid = int(shelf_id or 0)
        if sid <= 0:
            return {"shelf_id": 0, "items": []}
        headers = await self._shelf_headers([sid])
        h = headers.get(sid)
        if not h:
            return {"shelf_id": sid, "items": []}
        sph, sp = self._inlist("b", [sid])
        drows = (await self.db.execute(text(f"""
            SELECT DISTINCT snapshot_date FROM wb_competitor_cards_shelf_item
            WHERE shelf_id IN ({sph}) ORDER BY snapshot_date DESC
        """), sp)).mappings().all()
        dates = [_d(r["snapshot_date"]) for r in drows]
        date = snap if (snap and snap in dates) else (dates[0] if dates else "")
        items = (await self._items([sid], [date] if date else [])).get((sid, date), []) if date else []
        anchor_nm = int(h.get("anchor_nm") or 0)
        details = await self._details_by_nm([anchor_nm]) if anchor_nm else {}
        meta = await self._cards_meta([anchor_nm]) if anchor_nm else {}
        ad = details.get(anchor_nm, {})
        am = meta.get(anchor_nm, {})
        return {
            "shelf_id": sid,
            "title": h.get("title") or "",
            "preset_id": h.get("preset_id"),
            "anchor_nm": anchor_nm,
            "anchor_title": ad.get("title") or "",
            "anchor_image_url": ad.get("image_url") or am.get("image_url") or "",
            "dates": dates,
            "date": date,
            "items": items,
        }

    # ------------------------------------------------------------------ очередь

    async def enqueue(self, nm_id: int) -> dict:
        """Карточка → очередь сбора (очередь SEO-мониторинга, source='watch').

        Явный запрос менеджера на конкретную карточку: правило 12 ч здесь НЕ
        действует (собираем, даже если карточку брали час назад) — ждать сутки
        ради свежих баджей и полок смысла нет.
        """
        n = int(nm_id or 0)
        if n <= 0:
            raise ValueError("bad nm_id")
        if not await self.is_ours(n):
            raise ValueError("Карточка не ваша")
        cur = (await self.db.execute(text("""
            SELECT status FROM wb_enrich_queue
            WHERE nm_id=:n AND (company_id=:c OR company_id IS NULL) LIMIT 1
        """), {"n": n, "c": self.company_id})).mappings().first()
        status = str(cur.get("status") or "") if cur else ""
        if status == "processing":
            return {"ok": True, "queued": False, "status": status,
                    "detail": "карточка уже в работе"}
        await self.db.execute(text("""
            INSERT INTO wb_enrich_queue
              (nm_id, company_id, status, source, requested_at)
            VALUES (:n, :cid, 'pending', 'watch', NOW())
            ON DUPLICATE KEY UPDATE
              status=IF(status IN ('done','error','gone'), 'pending', status),
              source='watch', requested_at=NOW(), claimed_at=NULL,
              company_id=COALESCE(company_id, :cid)
        """), {"n": n, "cid": self.company_id})
        await self.db.commit()
        return {"ok": True, "queued": True, "status": "pending"}


def _first_image(raw: Any) -> str:
    """Колонка images (JSON со списком URL) -> первая ссылка."""
    if isinstance(raw, str) and raw.strip():
        try:
            v = json.loads(raw)
        except (ValueError, TypeError):
            return ""
        if isinstance(v, list):
            for x in v:
                if isinstance(x, str) and x.strip():
                    return x[:512]
    return ""
