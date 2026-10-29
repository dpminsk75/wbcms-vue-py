"""Разбор отзывов по карточкам — что говорит покупатель и что с этим делать.

Сценарий: пользователь смотрит карточки, у которых за период есть отзывы,
отмечает нужные и запускает анализ. ai_job (kind=review_analysis) по каждой
отмеченной карточке отдаёт модели все её отзывы (с текстом) + текущее описание
и характеристики, а модель отвечает тремя блоками:

  panel   — две колонки: о чём говорят покупатели (плюсы / проблемы).
            Главная тема (своими словами) → конкретные фразы покупателей.
            Без чисел: считать модель не просим.
  card    — что сделать с описанием: проблема, действие, что подчеркнуть из
            похвал, дописать / изменить (было → стало) / убрать, новый текст.
  product — что улучшить в самом товаре.

Модель — из «Модель (сводка)» (companies.seo_summary_model).
Промпт — настройка компании (companies.review_analysis_prompt), в коде его нет.

Источники сигнала (вывод замера 2026-10-27, компания 1, полгода):
  * отзывы wb_feedbacks — основной сигнал: ~1140 отзывов/мес, покрытие 72%
    карточек; работаем со всеми отзывами, где есть текст, независимо от оценки;
  * возвраты agg_sales_daily_sku — 0.1% от продаж, для печатной полиграфии
    бесполезны (покупатель не возвращает журнал, он ставит 1 звезду);
  * штрафы WB — логистика («невыполненный заказ»), к качеству карточки
    отношения не имеют. В разбор не входят.

Теги отзывов (wb_feedbacks.bables) идут в модель как словарь-подсказка:
«покупатели отмечали: бумага (14), качество (12)» — числа точные (SQL).
"""
import json
import re
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import llm_provider
from backend.services import openrouter_service as llm
from backend.services.feedback_common import (filter_options as fb_filter_options,
                                            resolve_card_ids)

SCENARIO = "review_analysis"

# Промпт разбора берётся ТОЛЬКО из настроек компании (companies.review_analysis_prompt).
# В коде его нет: текст — это настройка, её правит пользователь в карточке компании.
PROMPT_FIELD = "review_analysis_prompt"

_MAX_REVIEWS = 300          # отзывов на карточку в промпт (аварийный предохранитель)
_MAX_DESC = 6000            # символов описания в промпт
_MAX_REV_TEXT = 400         # символов текста отзыва в промпт
_MAX_REV_PROS = 150
_MAX_REV_CONS = 200
_MAX_EVIDENCE = 200         # символов на цитату
_MAX_PANEL_GROUPS = 6       # главных тем в одной колонке панели
_MAX_PANEL_ITEMS = 4        # фраз под одной главной темой
_MAX_TAGS_HINT = 12         # тегов WB в подсказке модели

# --- SQL -----------------------------------------------------------------------

# Текст отзыва — обязательное условие: работаем только с отзывами, где есть текст.
_TEXT = "(f.text IS NOT NULL AND f.text <> '')"

# Карточки с отзывами за период + доли «+» (оценка >= 4) и «−» (оценка <= 3).
SQL_CARDS_WITH_REVIEWS = """
SELECT f.nmID AS nm_id,
       COUNT(*) AS cnt,
       SUM(CASE WHEN f.productValuation >= 4 THEN 1 ELSE 0 END) AS pos_cnt,
       SUM(CASE WHEN f.productValuation <= 3 THEN 1 ELSE 0 END) AS neg_cnt,
       ROUND(AVG(f.productValuation), 2) AS avg_rating,
       COUNT(DISTINCT DATE(f.createdDate)) AS days_cnt,
       MAX(f.createdDate) AS last_at
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
  AND {text_where}
GROUP BY f.nmID
ORDER BY cnt DESC
LIMIT :lim OFFSET :off
"""

SQL_CARDS_WITH_REVIEWS_COUNT = """
SELECT COUNT(*) AS cnt FROM (
    SELECT f.nmID AS nm_id
    FROM wb_feedbacks f
    WHERE {cid_where}
      AND f.createdDate BETWEEN :d1 AND :d2
      AND {text_where}
    GROUP BY f.nmID
) AS t
"""

# Все отзывы карточки с текстом — и для промпта, и для раскрытия строки.
SQL_CARD_REVIEWS_ALL = """
SELECT f.id AS id,
       f.productValuation AS rating,
       f.text AS text,
       f.pros AS pros,
       f.cons AS cons,
       f.matchingSize AS size,
       f.color AS color,
       f.bables AS bables,
       f.createdDate AS created_at
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.nmID = :nm
  AND f.createdDate BETWEEN :d1 AND :d2
  AND {text_where}
ORDER BY f.productValuation ASC, f.createdDate DESC
LIMIT :lim
"""

SQL_CARD = """
SELECT nmID AS nm_id, company_id, title, brand, subjectName, vendorCode,
       description, characteristics, sizes
FROM wbcards WHERE nmID = :nm LIMIT 1
"""

SQL_INSERT_INSIGHT = """
INSERT INTO wb_feedback_insight (
    company_id, nm_id, job_id, period_from, period_to,
    reviews_cnt, neg_cnt, avg_rating,
    card_rec, product_rec, panel, summary, confidence,
    model, prompt_tokens, completion_tokens, cost, status
) VALUES (
    :c, :n, :j, :pf, :pto,
    :rc, :nc, :ar,
    :cr, :pr, :pn, :su, :cf,
    :mo, :pt_ok, :ct_ok, :co, 'new'
)
"""


def _clip(raw, limit: int) -> str:
    s = " ".join(str(raw or "").split())
    return s[:limit]


def _decode_bables(raw) -> list:
    """Теги отзыва (поле bables) — список строк."""
    if not raw:
        return []
    if isinstance(raw, list):
        items = raw
    else:
        try:
            v = json.loads(raw)
        except (TypeError, ValueError):
            return []
        items = v if isinstance(v, list) else []
    out = []
    for t in items:
        s = str(t).strip()
        if s and s not in out:
            out.append(s)
    return out


def _sql(tmpl: str, company_id: int | None, extra: str = "") -> str:
    """Подставить фильтр компании, условие «есть текст» и доп. фильтр (extra).

    extra — фрагмент вида ``AND f.nmID = :nm`` / ``AND f.nmID IN (...)``.
    Подставляется В ТЕКСТ условия, т.к. шаблон использует ``{text_where}``.
    """
    return tmpl.format(
        cid_where=("f.company_id = :cid" if company_id is not None else "1=1"),
        text_where=_TEXT + extra)


class FeedbackInsightService:
    """Список карточек с отзывами + запуск/исполнение ИИ-разбора."""

    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _params(self, date_from: str, date_to: str, nm_id: int | None = None) -> dict:
        params = {
            "d1": f"{date_from} 00:00:00",
            "d2": f"{date_to} 23:59:59",
            "nm": nm_id,
            "lim": _MAX_REVIEWS,
            "off": 0,
        }
        if self.company_id is not None:
            params["cid"] = self.company_id
        return params

    # --- фильтры -------------------------------------------------------------

    async def _resolve_card_ids(self, q: str | None, brand: str | None,
                                 category: str | None) -> list[int] | None:
        """Маска товара + бренд + категория → список nmID (общий helper)."""
        return await resolve_card_ids(self.db, self.company_id, q, brand, category)

    async def filter_options(self) -> dict:
        """Бренды и категории для выпадающих списков (общий helper)."""
        return await fb_filter_options(self.db, self.company_id)

    async def last_insights_by_card(self) -> dict:
        """nm_id → дата последнего разбора (чтобы не запускать одно и то же)."""
        where = "1=1"
        params: dict = {}
        if self.company_id is not None:
            where = "company_id = :cid"
            params["cid"] = self.company_id
        rows = (await self.db.execute(text(
            f"SELECT nm_id, MAX(created_at) AS last_at FROM wb_feedback_insight "
            f"WHERE {where} GROUP BY nm_id"), params)).mappings().all()
        return {int(r["nm_id"]): r["last_at"] for r in rows}

    # --- список карточек ------------------------------------------------------

    async def list_reviews(self, date_from: str, date_to: str,
                           nm_id: int | None = None, page: int = 1,
                           page_size: int = 50, q: str | None = None,
                           brand: str | None = None,
                           category: str | None = None) -> dict:
        """Карточки, у которых за период есть отзывы с текстом."""
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 50), 200))
        base = self._params(date_from, date_to, nm_id)
        extra = " AND f.nmID = :nm" if nm_id else ""

        card_ids = await self._resolve_card_ids(q, brand, category)
        if card_ids is not None and not card_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        if card_ids is not None:
            ph = ", ".join(f":c{i}" for i in range(len(card_ids)))
            extra += f" AND f.nmID IN ({ph})"
            base.update({f"c{i}": n for i, n in enumerate(card_ids)})

        cnt_sql = _sql(SQL_CARDS_WITH_REVIEWS_COUNT, self.company_id, extra)
        total = int((await self.db.execute(text(cnt_sql), base)).scalar() or 0)

        list_sql = _sql(SQL_CARDS_WITH_REVIEWS, self.company_id, extra)
        params = {**base, "lim": page_size, "off": (page - 1) * page_size}
        rows = (await self.db.execute(text(list_sql), params)).mappings().all()

        items = [dict(r) for r in rows]
        for it in items:
            cnt = int(it.get("cnt") or 0)
            it["pos_pct"] = round(int(it.get("pos_cnt") or 0) * 100 / cnt) if cnt else 0
            it["neg_pct"] = round(int(it.get("neg_cnt") or 0) * 100 / cnt) if cnt else 0
        # названия карточек — отдельным запросом по списку PK (wbcards без
        # индекса по company_id, JOIN на большой таблице запрещён)
        nms = [int(r["nm_id"]) for r in items if r.get("nm_id")]
        titles: dict = {}
        if nms:
            ph = ", ".join(f":n{i}" for i in range(len(nms)))
            trows = (await self.db.execute(text(
                f"SELECT nmID AS nm_id, title, vendorCode, brand, subjectName FROM wbcards "
                f"WHERE nmID IN ({ph})"),
                {f"n{i}": n for i, n in enumerate(nms)})).mappings().all()
            titles = {int(t["nm_id"]): dict(t) for t in trows}
        last = await self.last_insights_by_card()
        for it in items:
            t = titles.get(int(it["nm_id"]), {})
            it["title"] = t.get("title")
            it["vendor_code"] = t.get("vendorCode")
            it["brand"] = t.get("brand")
            it["subject_name"] = t.get("subjectName")
            it["last_insight_at"] = last.get(int(it["nm_id"]))
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def card_reviews(self, nm_id: int, date_from: str, date_to: str,
                           limit: int = 100) -> list:
        """Отзывы карточки с текстом — для раскрытия строки."""
        params = self._params(date_from, date_to, nm_id)
        params["lim"] = max(1, min(int(limit or 100), 300))
        rows = (await self.db.execute(
            text(_sql(SQL_CARD_REVIEWS_ALL, self.company_id)), params)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["text"] = _clip(d.get("text"), 1200)
            d["pros"] = _clip(d.get("pros"), 300)
            d["cons"] = _clip(d.get("cons"), 300)
            out.append(d)
        return out

    # --- промпт ---------------------------------------------------------------

    async def build_prompt(self, nm_id: int, company_id: int, date_from: str,
                           date_to: str) -> dict | None:
        """Карточка + все её отзывы с текстом → messages."""
        card = (await self.db.execute(text(SQL_CARD), {"nm": nm_id})).mappings().first()
        if not card:
            return None
        card = dict(card)
        # отзывы берём по компании карточки (она может отличаться от выбранной)
        params = {
            "cid": company_id,
            "d1": f"{date_from} 00:00:00",
            "d2": f"{date_to} 23:59:59",
            "nm": nm_id,
            "lim": _MAX_REVIEWS,
        }
        rows = (await self.db.execute(
            text(_sql(SQL_CARD_REVIEWS_ALL, company_id)), params)).mappings().all()
        if not rows:
            return None

        reviews = []
        neg = 0
        pos = 0
        rating_sum = 0
        tag_counts: dict = {}
        for r in rows:
            d = dict(r)
            try:
                rating = int(d.get("rating") or 0)
            except (TypeError, ValueError):
                rating = 0
            rating_sum += rating
            if rating >= 4:
                pos += 1
            elif rating <= 3:
                neg += 1
            for tag in _decode_bables(d.get("bables")):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            reviews.append({
                "rating": rating,
                "date": str(d.get("created_at") or "")[:10],
                "text": _clip(d.get("text"), _MAX_REV_TEXT),
                "pros": _clip(d.get("pros"), _MAX_REV_PROS),
                "cons": _clip(d.get("cons"), _MAX_REV_CONS),
                "size": _clip(d.get("size"), 40),
                "color": _clip(d.get("color"), 40),
            })

        n = len(reviews)
        user_data = {
            "nm_id": nm_id,
            "title": card.get("title") or "",
            "brand": card.get("brand") or "",
            "subject": card.get("subjectName") or "",
            "vendor_code": card.get("vendorCode") or "",
            "description": _clip(card.get("description"), _MAX_DESC),
            "characteristics": _clip(card.get("characteristics"), 1200),
            "sizes": _clip(card.get("sizes"), 400),
            "reviews_total": n,
            "avg_rating": round(rating_sum / n, 2) if n else None,
            "tags_wb": [{"tag": t, "count": c} for t, c in
                         sorted(tag_counts.items(), key=lambda kv: -kv[1])[:_MAX_TAGS_HINT]],
            "reviews": reviews,
        }
        user_text = json.dumps(user_data, ensure_ascii=False)
        # Промпт — только из настроек компании. Ничего не дописываем: формат
        # ответа и правила разбора — часть текста, который правит пользователь.
        prompt = await self.get_prompt(company_id)
        if not prompt:
            raise ValueError(
                "Промпт разбора отзывов не задан — впишите его в карточке компании "
                f"(companies.{PROMPT_FIELD})")
        prompt = await self._fill_prompt_vars(prompt, company_id)
        return {
            "card": card,
            "user_data": user_data,
            "reviews_cnt": n,
            "neg_cnt": neg,
            "pos_cnt": pos,
            "avg_rating": user_data["avg_rating"],
            "desc_old": user_data["description"],
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_text},
            ],
        }

    async def get_prompt(self, company_id: int | None) -> str:
        """Промпт разбора из настроек компании. Пусто = не задан."""
        if company_id is None:
            return ""
        row = await llm_provider.company_row(self.db, company_id)
        return str((row or {}).get(PROMPT_FIELD) or "").strip()

    async def _fill_prompt_vars(self, prompt: str, company_id: int | None) -> str:
        """Подставить {DESC_MIN}/{DESC_MAX} — как в seo_service (настройки компании)."""
        if "{DESC_MIN}" not in prompt and "{DESC_MAX}" not in prompt:
            return prompt
        row = await llm_provider.company_row(self.db, company_id) if company_id else None
        desc_min = max(300, int((row or {}).get("seo_desc_min") or 800))
        desc_max = max(desc_min + 400, int((row or {}).get("seo_desc_max") or 1200))
        return (prompt.replace("{DESC_MIN}", str(desc_min))
                      .replace("{DESC_MAX}", str(desc_max)))

    # --- запуск ---------------------------------------------------------------

    async def start_analysis(self, nm_ids: list[int], created_by: int | None,
                             background, date_from: str | None = None,
                             date_to: str | None = None) -> int:
        """Создать ai_job (kind=review_analysis) по отмеченным карточкам."""
        from backend.services import ai_job_service as jobs
        nm_ids = sorted({int(n) for n in nm_ids if int(n) > 0})[:60]
        if not nm_ids:
            raise ValueError("не отмечено ни одной карточки")
        try:
            to = date.fromisoformat(date_to) if date_to else date.today()
            frm = (date.fromisoformat(date_from) if date_from
                   else to - timedelta(days=89))
        except ValueError:
            raise ValueError("bad date, use YYYY-MM-DD")
        if frm > to:
            raise ValueError("date_from > date_to")
        if (to - frm).days > 180:
            raise ValueError("range max 180 days")
        job_id = await jobs.create_job(
            self.db, company_id=self.company_id, kind="review_analysis",
            nm_id=nm_ids[0] if len(nm_ids) == 1 else None,
            items=[{"ref_id": n, "label": f"nm {n}"} for n in nm_ids],
            created_by=created_by,
            params={"date_from": frm.isoformat(), "date_to": to.isoformat()})
        background.add_task(jobs.run_job, job_id)
        return job_id

    # --- чтение результатов ---------------------------------------------------

    async def list_insights(self, date_from: str | None = None, date_to: str | None = None,
                            nm_id: int | None = None, page: int = 1,
                            page_size: int = 50, job_id: int | None = None,
                            q: str | None = None, brand: str | None = None,
                            category: str | None = None) -> dict:
        """Готовые инсайты. Даты — по ПЕРИОДУ ОТЗЫВОВ (пересечение с запрошенным)."""
        where = ["1=1"]
        params: dict = {}
        if self.company_id is not None:
            where.append("i.company_id = :cid")
            params["cid"] = self.company_id
        if date_from:
            where.append("i.period_to >= :d1")
            params["d1"] = date_from
        if date_to:
            where.append("i.period_from <= :d2")
            params["d2"] = date_to
        if job_id:
            where.append("i.job_id = :job")
            params["job"] = int(job_id)
        if nm_id:
            where.append("i.nm_id = :nm")
            params["nm"] = int(nm_id)
        card_ids = await self._resolve_card_ids(q, brand, category)
        if card_ids is not None:
            if not card_ids:
                return {"items": [], "total": 0, "page": page, "page_size": page_size}
            ph = ", ".join(f":c{i}" for i in range(len(card_ids)))
            where.append(f"i.nm_id IN ({ph})")
            params.update({f"c{i}": n for i, n in enumerate(card_ids)})
        if brand:
            where.append("c.brand = :brand")
            params["brand"] = brand
        if category:
            where.append("c.subjectName = :cat")
            params["cat"] = category
        w = " AND ".join(where)
        total = int((await self.db.execute(text(
            f"SELECT COUNT(*) AS cnt FROM wb_feedback_insight i "
            f"LEFT JOIN wbcards c ON c.nmID = i.nm_id WHERE {w}"),
            params)).scalar() or 0)
        rows = (await self.db.execute(text(f"""
            SELECT i.id, i.nm_id, i.job_id, i.period_from, i.period_to,
                   i.reviews_cnt, i.neg_cnt, i.avg_rating,
                   i.card_rec, i.product_rec, i.panel, i.summary, i.confidence,
                   i.model, i.status, i.error, i.created_at,
                   c.title AS card_title, c.vendorCode AS vendor_code,
                   c.brand AS brand, c.subjectName AS subject_name
            FROM wb_feedback_insight i
            LEFT JOIN wbcards c ON c.nmID = i.nm_id
            WHERE {w}
            ORDER BY i.id DESC
            LIMIT :lim OFFSET :off"""),
            {**params, "lim": max(1, min(int(page_size or 50), 200)),
             "off": (max(1, int(page or 1)) - 1) * max(1, min(int(page_size or 50), 200))}
        )).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            d["card_rec"] = _json_obj(d.get("card_rec"))
            d["product_rec"] = _json_obj(d.get("product_rec"))
            d["panel"] = _json_obj(d.get("panel")) or {}
            items.append(d)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_insight(self, insight_id: int) -> dict | None:
        """Один разбор по id — для открытия по ссылке ?insight=<id>."""
        where = ["i.id = :id"]
        params: dict = {"id": int(insight_id)}
        if self.company_id is not None:
            where.append("i.company_id = :cid")
            params["cid"] = self.company_id
        row = (await self.db.execute(text(f"""
            SELECT i.id, i.nm_id, i.job_id, i.period_from, i.period_to,
                   i.reviews_cnt, i.neg_cnt, i.avg_rating,
                   i.card_rec, i.product_rec, i.panel, i.summary, i.confidence,
                   i.model, i.status, i.error, i.created_at,
                   c.title AS card_title, c.vendorCode AS vendor_code
            FROM wb_feedback_insight i
            LEFT JOIN wbcards c ON c.nmID = i.nm_id
            WHERE {" AND ".join(where)}
            LIMIT 1"""), params)).mappings().first()
        if not row:
            return None
        d = dict(row)
        d["card_rec"] = _json_obj(d.get("card_rec"))
        d["product_rec"] = _json_obj(d.get("product_rec"))
        d["panel"] = _json_obj(d.get("panel")) or {}
        return d


def _json_obj(raw) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) and v else None
    except (TypeError, ValueError):
        return None


# --- нормализация ответа модели -----------------------------------------------

def _norm_rec(raw, action_key: str) -> dict | None:
    """Одна рекомендация: {issue, <action>, evidence[], priority, ...}."""
    if not isinstance(raw, dict):
        return None
    issue = _clip(raw.get("issue"), 400)
    if not issue:
        return None
    ev = []
    for e in (raw.get("evidence") or [])[:2]:
        s = _clip(e, _MAX_EVIDENCE)
        if s:
            ev.append(s)
    pr = raw.get("priority")
    try:
        pr = int(pr)
    except (TypeError, ValueError):
        pr = 2
    out = {
        "issue": issue,
        action_key: _clip(raw.get(action_key), 600),
        "evidence": ev,
        "priority": max(1, min(pr, 3)),
    }
    if action_key == "fix":
        out["highlight"] = _clip(raw.get("highlight"), 400) or None
        out["desc_add"] = [_clip(x, 300) for x in (raw.get("desc_add") or [])[:8]
                           if _clip(x, 300)]
        changes = []
        for ch in (raw.get("desc_change") or [])[:6]:
            if isinstance(ch, dict):
                was = _clip(ch.get("was"), 300)
                now = _clip(ch.get("now"), 300)
                if was or now:
                    changes.append({"was": was, "now": now})
        out["desc_change"] = changes
        out["desc_remove"] = [_clip(x, 300) for x in (raw.get("desc_remove") or [])[:8]
                              if _clip(x, 300)]
        out["desc_new"] = _clip(raw.get("desc_new"), _MAX_DESC) or None
    return out


def _norm_panel(raw) -> dict:
    """Панель «о чём говорят покупатели»: плюсы и проблемы, без чисел.

    Страховки от типичных огрехов модели:
      * подпункт, повторяющий заголовок темы («Прислали не тот журнал» → то же
        самое) — выбрасываем;
      * один и тот же подпункт в двух темах — оставляем только в первой;
      * капы: не больше _MAX_PANEL_GROUPS тем в колонке и _MAX_PANEL_ITEMS
        фраз под темой.
    """
    out = {"plus": [], "minus": []}
    if not isinstance(raw, dict):
        return out
    seen: set = set()
    for key in ("plus", "minus"):
        groups = raw.get(key)
        if not isinstance(groups, list):
            continue
        for g in groups[:_MAX_PANEL_GROUPS]:
            if not isinstance(g, dict):
                continue
            title = _clip(g.get("title"), 200)
            if not title:
                continue
            title_key = _norm_key(title)
            items = []
            for it in (g.get("items") or [])[:_MAX_PANEL_ITEMS * 2]:
                s = _clip(it, 400)
                if not s:
                    continue
                k = _norm_key(s)
                if not k or k == title_key:
                    continue          # тавтология
                if k in seen:
                    continue          # дубль между темами
                seen.add(k)
                items.append(s)
                if len(items) >= _MAX_PANEL_ITEMS:
                    break
            if items:
                out[key].append({"title": title, "items": items})
    return out


def _norm_key(s: str) -> str:
    """Ключ для сравнения строк: без пунктуации и регистра."""
    t = " ".join(str(s or "").lower().replace("ё", "е").split())
    return re.sub(r"[^\w\s]", "", t).strip()[:80]


# --- обработчик ai_job --------------------------------------------------------

async def execute_review_job(job_id: int, db: AsyncSession) -> None:
    """Воркер kind=review_analysis: item(ref=nmID) → build_prompt → LLM →
    INSERT в wb_feedback_insight."""
    job = (await db.execute(
        text("SELECT * FROM ai_job WHERE id=:j LIMIT 1"), {"j": job_id})).mappings().first()
    if not job:
        return
    job = dict(job)

    params = job.get("params")
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {}
    if not isinstance(params, dict):
        params = {}
    p_from = params.get("date_from")
    p_to = params.get("date_to")

    items = (await db.execute(
        text("SELECT * FROM ai_job_item WHERE job_id=:j AND status='pending' ORDER BY id"),
        {"j": job_id})).mappings().all()

    async def mark(item_id: int, status: str, result: dict | None = None,
                   error: str | None = None):
        await db.execute(text("""
            UPDATE ai_job_item SET status=:s, result=:r, error=:e, note=NULL WHERE id=:i
        """), {"s": status, "r": json.dumps(result, ensure_ascii=False) if result else None,
               "e": (error or "")[:500] if error else None, "i": item_id})
        await db.execute(text("UPDATE ai_job SET done=done+1 WHERE id=:j"), {"j": job_id})
        await db.commit()

    async def progress(item_id: int, note: str) -> None:
        try:
            await db.execute(text("UPDATE ai_job_item SET note=:n WHERE id=:i"),
                             {"n": note[:500], "i": item_id})
            await db.commit()
        except Exception:
            await db.rollback()

    # Промпт — настройка компании. Проверяем один раз на задачу: незаданный
    # промпт означает, что все карточки упадут одинаково, звать модель бессмысленно.
    job_company = job.get("company_id") or 1
    svc = FeedbackInsightService(db, job_company)
    prompt = await svc.get_prompt(job_company)
    if not prompt:
        err = ("Промпт разбора отзывов не задан — впишите его в карточке компании "
               f"(companies.{PROMPT_FIELD})")
        for item in items:
            await mark(dict(item)["id"], "error", error=err)
        return

    for item in items:
        item = dict(item)
        await db.execute(text("UPDATE ai_job_item SET status='processing' WHERE id=:i"),
                         {"i": item["id"]})
        await db.commit()
        try:
            nm_id = int(item["ref_id"])
            company_id = job.get("company_id") or 1
            built = await svc.build_prompt(nm_id, company_id, p_from, p_to)
            if not built:
                await mark(item["id"], "error",
                           error="нет отзывов с текстом или карточка не найдена")
                continue

            cands = await llm.model_candidates(db, company_id, kind="summary")
            if not cands:
                await mark(item["id"], "error", error="нет доступных моделей")
                continue

            last_err = "все модели не ответили"
            ok = False
            # размер запроса в note — видно, если модель «думает» на слишком длинном
            prompt_chars = sum(len(m.get("content") or "") for m in built["messages"])
            for i, try_model in enumerate(cands):
                await progress(item["id"],
                               f"кандидат {i + 1}/{len(cands)}: {try_model}, "
                               f"промпт {prompt_chars // 1000}k симв.")
                res = await llm.chat(
                    db, built["messages"], company_id,
                    temperature=0.3, max_tokens=4000, model=try_model,
                    note=f"review_analysis, nm {nm_id}",
                    scenario=SCENARIO, user_id=job.get("created_by"),
                    nm_id=nm_id, job_id=job_id, timeout=90)
                if res.get("error"):
                    await llm.mark_model(db, try_model, False, res["error"])
                    last_err = f"model {try_model}: {res['error']}"
                    continue
                content = (res.get("content") or "").strip()
                if not content:
                    await llm.mark_model(db, try_model, False, "empty response")
                    last_err = f"model {try_model}: empty response"
                    continue
                m = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.S)
                if m:
                    content = m.group(1).strip()
                parsed = llm.safe_json_decode(content)
                if not isinstance(parsed, dict):
                    await llm.mark_model(db, try_model, False, "JSON parse failed")
                    last_err = f"JSON parse failed model={try_model}"
                    continue
                await llm.mark_model(db, try_model, True)

                card_rec = _norm_rec(parsed.get("card"), "fix")
                product_rec = _norm_rec(parsed.get("product"), "action")
                panel = _norm_panel(parsed.get("panel"))
                if card_rec and built.get("desc_old"):
                    card_rec["desc_old"] = built["desc_old"]
                confidence = parsed.get("confidence")
                conf = float(confidence) if isinstance(confidence, (int, float)) else None
                await db.rollback()
                async with db.begin():
                    await db.execute(text(SQL_INSERT_INSIGHT), {
                        "c": company_id, "n": nm_id, "j": job_id,
                        "pf": p_from, "pto": p_to,
                        "rc": built["reviews_cnt"], "nc": built["neg_cnt"],
                        "ar": built["avg_rating"],
                        "cr": json.dumps(card_rec, ensure_ascii=False) if card_rec else None,
                        "pr": json.dumps(product_rec, ensure_ascii=False) if product_rec else None,
                        "pn": json.dumps(panel, ensure_ascii=False) if panel else None,
                        "su": str(parsed.get("summary") or "")[:600] or None,
                        "cf": conf,
                        "mo": res.get("model"),
                        "pt_ok": res.get("prompt_tokens"), "ct_ok": res.get("completion_tokens"),
                        "co": res.get("cost") or 0,
                    })
                await db.commit()
                ins_id = int((await db.execute(
                    text("SELECT LAST_INSERT_ID()"))).scalar() or 0)
                await mark(item["id"], "done", result={
                    "insight_id": ins_id, "nm_id": nm_id,
                    "plus": len(panel.get("plus") or []),
                    "minus": len(panel.get("minus") or []),
                })
                ok = True
                break
            if not ok:
                await mark(item["id"], "error", error=last_err[:500])
        except Exception as exc:
            await db.rollback()
            await mark(item["id"], "error",
                       error=f"{type(exc).__name__}: {exc}"[:500])
            continue
