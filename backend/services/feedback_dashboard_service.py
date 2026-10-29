"""Дашборд «Отзывы» — сводка по отзывам за период + обзор наших товаров.

Считаем всё из wb_feedbacks (отзывы) и agg_orders_daily_sku (заказы):
  * KPI: отзывов, из них с текстом, средняя оценка, NPS, ▲ к прошлому периоду;
  * распределение по звёздам 5…1;
  * тональность: позитив (оценка >= 4) / негатив (1–3) / без оценки;
  * динамика по дням / неделям / месяцам;
  * обзор товаров: ТОП по заказам (только среди карточек, у которых есть отзывы).

Один проход агрегации на срез; никаких COUNT(DISTINCT) по тексту и JOIN на
wbcards (там нет индекса по company_id) — названия карточек берём отдельным
запросом по списку PK.
"""
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.feedback_common import (delta_pct, delta_pp, filter_options,
                                            nps, resolve_card_ids)

# Выражение периода для GROUP BY — и в SELECT, и в GROUP BY одно и то же
# (иначе ONLY_FULL_GROUP_BY ругается).
PERIOD_EXPR = {
    "day": "DATE(f.createdDate)",
    "week": "DATE_SUB(DATE(f.createdDate), INTERVAL WEEKDAY(f.createdDate) DAY)",
    "month": "DATE_FORMAT(f.createdDate, '%Y-%m-01')",
}

# Фильтр по отзывам (что считаем «отзывом»):
#   all     — все отзывы;
#   content — с текстом или с тегами (bables) — то, что реально полезно читать;
#   rated   — только с оценкой (productValuation > 0).
REV_MODES = {
    "all": "",
    "content": (" AND ((f.text IS NOT NULL AND f.text <> '') "
                "OR (f.bables IS NOT NULL AND f.bables NOT IN ('','null','[]')))"),
    "rated": " AND f.productValuation IS NOT NULL AND f.productValuation > 0",
}

SQL_TOTALS = """
SELECT COUNT(*) AS cnt,
       SUM(CASE WHEN f.text IS NOT NULL AND f.text <> '' THEN 1 ELSE 0 END) AS with_text,
       SUM(CASE WHEN f.bables IS NOT NULL AND f.bables NOT IN ('','null','[]') THEN 1 ELSE 0 END) AS with_tags,
       SUM(CASE WHEN f.productValuation IS NOT NULL AND f.productValuation > 0 THEN 1 ELSE 0 END) AS rated,
       SUM(CASE WHEN f.productValuation >= 4 THEN 1 ELSE 0 END) AS pos,
       SUM(CASE WHEN f.productValuation BETWEEN 1 AND 3 THEN 1 ELSE 0 END) AS neg,
       SUM(CASE WHEN f.productValuation = 5 THEN 1 ELSE 0 END) AS c5,
       SUM(CASE WHEN f.productValuation = 4 THEN 1 ELSE 0 END) AS c4,
       SUM(CASE WHEN f.productValuation = 3 THEN 1 ELSE 0 END) AS c3,
       SUM(CASE WHEN f.productValuation = 2 THEN 1 ELSE 0 END) AS c2,
       SUM(CASE WHEN f.productValuation = 1 THEN 1 ELSE 0 END) AS c1,
       ROUND(AVG(NULLIF(f.productValuation, 0)), 2) AS avg_rating
FROM wb_feedbacks f
WHERE 1=1 {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
"""

SQL_DAILY = """
SELECT {period_expr} AS d,
       COUNT(*) AS cnt,
       SUM(CASE WHEN f.productValuation >= 4 THEN 1 ELSE 0 END) AS pos,
       SUM(CASE WHEN f.productValuation BETWEEN 1 AND 3 THEN 1 ELSE 0 END) AS neg,
       ROUND(AVG(NULLIF(f.productValuation, 0)), 2) AS avg_rating
FROM wb_feedbacks f
WHERE 1=1 {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
GROUP BY d
ORDER BY d ASC
"""

# Агрегат отзывов по карточкам — и набор nmID с отзывами для ТОПа по заказам.
SQL_BY_CARD = """
SELECT f.nmID AS nm_id,
       COUNT(*) AS reviews_cnt,
       SUM(CASE WHEN f.text IS NOT NULL AND f.text <> '' THEN 1 ELSE 0 END) AS with_text,
       SUM(CASE WHEN f.bables IS NOT NULL AND f.bables NOT IN ('','null','[]') THEN 1 ELSE 0 END) AS with_tags,
       SUM(CASE WHEN f.productValuation >= 4 THEN 1 ELSE 0 END) AS pos,
       SUM(CASE WHEN f.productValuation BETWEEN 1 AND 3 THEN 1 ELSE 0 END) AS neg,
       SUM(CASE WHEN f.productValuation = 5 THEN 1 ELSE 0 END) AS c5,
       SUM(CASE WHEN f.productValuation IN (1,2,3) THEN 1 ELSE 0 END) AS c13,
       ROUND(AVG(NULLIF(f.productValuation, 0)), 2) AS avg_rating
FROM wb_feedbacks f
WHERE 1=1 {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
GROUP BY f.nmID
"""

# Заказы по карточкам из куба agg_orders_daily_sku — как в /seo-watch
# (watch_service.top_cards): нижняя граница по дате, без верхней, nmID > 0.
# Без JOIN с отзывами: отзывы и заказы считаются двумя отдельными проходами,
# склейка — в Python. Так не теряется ни одна строка из-за плана запроса.
SQL_ORDERS_BY_CARD = """
SELECT s.nmID AS nm_id, SUM(s.orders_qty) AS orders_cnt
FROM agg_orders_daily_sku s
WHERE {s_cid_where}
  AND s.order_date >= :od1
  AND s.nmID > 0
GROUP BY s.nmID
ORDER BY orders_cnt DESC, s.nmID ASC
LIMIT {lim}
"""


def _i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class FeedbackDashboardService:
    """Сводка по отзывам за период."""

    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # --- служебное ---------------------------------------------------------

    def _cid_where(self) -> str:
        """Фильтр по компании. Вставляется в «WHERE 1=1 {cid_where}»."""
        return "" if self.company_id is None else " AND f.company_id = :cid"

    def _params(self, date_from: str, date_to: str) -> dict:
        p = {
            "d1": f"{date_from} 00:00:00",
            "d2": f"{date_to} 23:59:59",
        }
        if self.company_id is not None:
            p["cid"] = self.company_id
        return p

    def _card_filter(self, nm_id: int | None,
                     card_ids: list[int] | None) -> tuple[str, dict]:
        """Фильтр отзывов по товарам: точный nmID или список из маски/бренда/категории."""
        if nm_id:
            return " AND f.nmID = :nm_id", {"nm_id": int(nm_id)}
        if card_ids is not None:
            ph = ", ".join(f":c{i}" for i in range(len(card_ids)))
            return (f" AND f.nmID IN ({ph})",
                    {f"c{i}": n for i, n in enumerate(card_ids)})
        return "", {}

    @staticmethod
    def _rev_filter(rev_mode: str | None) -> str:
        """Фрагмент «какие отзывы считаем» (all / content / rated)."""
        return REV_MODES.get(rev_mode or "all", REV_MODES["all"])

    async def _orders_by_card(self, date_from: str) -> dict[int, int]:
        """Заказы по карточкам из куба agg_orders_daily_sku.

        Как в /seo-watch: нижняя граница по дате (куб пересчитывается по таймеру
        и может отставать, поэтому верхнюю не ставим), nmID > 0.
        Возвращает {nm_id: заказов}.
        """
        params: dict = {"od1": f"{date_from} 00:00:00"}
        if self.company_id is not None:
            params["cid"] = self.company_id
        rows = (await self.db.execute(text(
            SQL_ORDERS_BY_CARD.format(
                s_cid_where=("s.company_id = :cid" if self.company_id is not None else "1=1"),
                lim=2000)),
            params)).mappings().all()
        out: dict[int, int] = {}
        for r in rows:
            try:
                out[int(r["nm_id"])] = _i(r.get("orders_cnt"))
            except (TypeError, ValueError):
                continue
        return out

    async def _totals(self, date_from: str, date_to: str, extra: str = "",
                       extra_params: dict | None = None) -> dict:
        params = {**self._params(date_from, date_to), **(extra_params or {})}
        row = (await self.db.execute(text(
            SQL_TOTALS.format(cid_where=self._cid_where() + extra)),
            params)).mappings().first()
        d = dict(row or {})
        rated = _i(d.get("rated"))
        c5 = _i(d.get("c5"))
        c13 = _i(d.get("c1")) + _i(d.get("c2")) + _i(d.get("c3"))
        cnt = _i(d.get("cnt"))
        with_text = _i(d.get("with_text"))
        return {
            "reviews_cnt": cnt,
            "with_text_cnt": with_text,
            "with_text_pct": round(with_text * 100 / cnt) if cnt else 0,
            "with_tags_cnt": _i(d.get("with_tags")),
            "rated_cnt": rated,
            "avg_rating": _f(d.get("avg_rating")),
            "nps": nps(c5, c13, rated),
            "pos_cnt": _i(d.get("pos")),
            "neg_cnt": _i(d.get("neg")),
            "no_rating_cnt": max(0, cnt - rated),
            "c5": c5, "c4": _i(d.get("c4")), "c3": _i(d.get("c3")),
            "c2": _i(d.get("c2")), "c1": _i(d.get("c1")),
        }

    # --- основное ----------------------------------------------------------

    async def summary(self, date_from: str, date_to: str, nm_id: int | None = None,
                       brand: str | None = None, category: str | None = None,
                       period: str = "day", q: str | None = None,
                       rev_mode: str = "all") -> dict:
        """KPI + распределение + тональность + динамика."""
        period = period if period in PERIOD_EXPR else "day"
        d1 = date.fromisoformat(date_from)
        d2 = date.fromisoformat(date_to)
        days = max(1, (d2 - d1).days + 1)
        prev_to = d1 - timedelta(days=1)
        prev_from = prev_to - timedelta(days=days - 1)

        card_ids = await resolve_card_ids(self.db, self.company_id, q, brand, category)
        if card_ids is not None and not card_ids:
            return self._empty_summary(date_from, date_to, days, prev_from, prev_to, period)
        extra, extra_params = self._card_filter(nm_id, card_ids)
        extra += self._rev_filter(rev_mode)

        cur = await self._totals(date_from, date_to, extra, extra_params)
        prev = await self._totals(prev_from.isoformat(), prev_to.isoformat(),
                                  extra, extra_params)

        params = {**self._params(date_from, date_to), **extra_params}
        daily_sql = SQL_DAILY.format(period_expr=PERIOD_EXPR[period],
                                     cid_where=self._cid_where() + extra)
        rows = (await self.db.execute(text(daily_sql), params)).mappings().all()
        daily = []
        for r in rows:
            d = dict(r)
            daily.append({
                "d": str(d.get("d") or "")[:10],
                "cnt": _i(d.get("cnt")),
                "pos": _i(d.get("pos")),
                "neg": _i(d.get("neg")),
                "avg_rating": _f(d.get("avg_rating")),
            })

        rated = cur["rated_cnt"]
        ratings = []
        for star in (5, 4, 3, 2, 1):
            c = cur[f"c{star}"]
            ratings.append({"rating": star, "cnt": c,
                            "pct": round(c * 100 / rated) if rated else 0})

        ai_sentiment = await self._ai_sentiment(date_from, date_to)

        return {
            "period": {"from": date_from, "to": date_to, "days": days,
                       "prev_from": prev_from.isoformat(),
                       "prev_to": prev_to.isoformat()},
            "period_kind": period,
            "kpi": cur,
            "prev": prev,
            "delta": {
                "reviews_cnt_pct": delta_pct(cur["reviews_cnt"], prev["reviews_cnt"]),
                "avg_rating_pp": delta_pp(cur["avg_rating"], prev["avg_rating"]),
                "nps_pp": delta_pp(cur["nps"], prev["nps"]),
            },
            "ratings": ratings,
            "sentiment": {"positive": cur["pos_cnt"], "negative": cur["neg_cnt"],
                          "no_rating": cur["no_rating_cnt"]},
            "ai_sentiment": ai_sentiment,
            "daily": daily,
        }

    def _empty_summary(self, date_from, date_to, days, prev_from, prev_to, period) -> dict:
        empty = {"reviews_cnt": 0, "with_text_cnt": 0, "with_text_pct": 0,
                 "with_tags_cnt": 0, "rated_cnt": 0, "avg_rating": None, "nps": None,
                 "pos_cnt": 0, "neg_cnt": 0, "no_rating_cnt": 0, "c5": 0}
        return {
            "period": {"from": date_from, "to": date_to, "days": days,
                       "prev_from": prev_from.isoformat(), "prev_to": prev_to.isoformat()},
            "period_kind": period,
            "kpi": empty, "prev": dict(empty),
            "delta": {"reviews_cnt_pct": None, "avg_rating_pp": None, "nps_pp": None},
            "ratings": [{"rating": s, "cnt": 0, "pct": 0} for s in (5, 4, 3, 2, 1)],
            "sentiment": {"positive": 0, "negative": 0, "no_rating": 0},
            "daily": [],
        }

    async def _ai_sentiment(self, date_from: str, date_to: str) -> dict:
        """Метки ИИ-разбора отзывов за период: эмоциональность / конструктивность / тон.

        Пусто, если разбора ещё не было (или таблицы разбора нет) — дашборд
        покажет заглушку.
        """
        empty = {"total": 0, "parsed": 0, "errors": 0,
                 "emotion": [], "constructiveness": [], "tone": []}
        try:
            from backend.services.feedback_review_service import FeedbackReviewService
            svc = FeedbackReviewService(self.db, self.company_id)
            return await svc.stats(date_from, date_to)
        except Exception:
            return empty

    # --- обзор товаров -------------------------------------------------------

    async def cards(self, date_from: str, date_to: str, nm_id: int | None = None,
                    brand: str | None = None, category: str | None = None,
                    limit: int = 20, q: str | None = None,
                    rev_mode: str = "all") -> dict:
        """ТОП наших карточек по заказам — только те, у которых есть отзывы.

        Два независимых прохода, склейка в Python (без JOIN куба с отзывами):
          1) заказы по карточкам из куба agg_orders_daily_sku (как в /seo-watch);
          2) агрегат отзывов за период по карточкам.
        """
        limit = max(1, min(int(limit or 20), 200))
        card_ids = await resolve_card_ids(self.db, self.company_id, q, brand, category)
        if card_ids is not None and not card_ids:
            return {"items": [], "total": 0, "limit": limit,
                    "cards_total": 0, "cards_with_reviews": 0, "orders_missing": False}
        extra, extra_params = self._card_filter(nm_id, card_ids)
        extra += self._rev_filter(rev_mode)
        params = {**self._params(date_from, date_to), **extra_params}

        # 1) заказы по карточкам из куба
        orders_by_card = await self._orders_by_card(date_from)

        # 2) агрегат отзывов по карточкам с отзывами
        rev_rows = (await self.db.execute(text(
            SQL_BY_CARD.format(cid_where=self._cid_where() + extra)),
            params)).mappings().all()
        by_card: dict = {}
        for r in rev_rows:
            d = dict(r)
            nm = d.get("nm_id")
            if nm is None:
                continue
            rated = _i(d.get("pos")) + _i(d.get("neg"))
            by_card[int(nm)] = {
                "reviews_cnt": _i(d.get("reviews_cnt")),
                "with_text_cnt": _i(d.get("with_text")),
                "with_tags_cnt": _i(d.get("with_tags")),
                "pos_cnt": _i(d.get("pos")),
                "neg_cnt": _i(d.get("neg")),
                "avg_rating": _f(d.get("avg_rating")),
                "nps": nps(_i(d.get("c5")), _i(d.get("c13")), rated),
            }

        # карточки без отзывов в обзор не идут; сортировка — по заказам
        picked = [(nm, orders_by_card.get(nm, 0)) for nm in by_card]
        picked.sort(key=lambda x: (-x[1], -by_card[x[0]]["reviews_cnt"], x[0]))
        # заказов в кубе нет → идёт сортировка по количеству отзывов
        orders_missing = bool(by_card) and not any(oc > 0 for _, oc in picked)
        picked = picked[:limit]

        titles: dict = {}
        if picked:
            nms = [nm for nm, _ in picked]
            ph = ", ".join(f":n{i}" for i in range(len(nms)))
            trows = (await self.db.execute(text(
                f"SELECT nmID AS nm_id, title, vendorCode, brand, subjectName, photos "
                f"FROM wbcards WHERE nmID IN ({ph})"),
                {f"n{i}": n for i, n in enumerate(nms)})).mappings().all()
            titles = {int(t["nm_id"]): dict(t) for t in trows}

        items = []
        for nm, orders_cnt in picked:
            stat = by_card[nm]
            t = titles.get(nm, {})
            items.append({
                "nm_id": nm,
                "title": t.get("title"),
                "vendor_code": t.get("vendorCode"),
                "brand": t.get("brand"),
                "subject_name": t.get("subjectName"),
                "photos": t.get("photos"),
                "orders_cnt": orders_cnt,
                **stat,
            })
        return {
            "items": items,
            "total": len(items),
            "limit": limit,
            "cards_total": len(orders_by_card),
            "cards_with_reviews": len(by_card),
            "orders_missing": orders_missing,
        }

    # --- справочники ---------------------------------------------------------

    async def options(self) -> dict:
        return await filter_options(self.db, self.company_id)
