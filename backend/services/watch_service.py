"""Набор мониторинга «SEO-мониторинг» (/seo-watch) — расчёт watch set.

Задача (план 2026-10-23): ТОП-N карточек по заказам за месяц + ТОП-M
поисковых фраз «приносящих заказы» для каждой карточки. Далее бекенд
мониторит по этим фразам выдачу (`wb_competitor_position`) и события.

Считаем прямо в SQL на запрос без таймеров и витринных таблиц:
- карточки  — куб `agg_orders_daily_sku` (уже агрегат: дата × nmID), миллисекунды;
- фразы     — `wb_sr_report_item_phrases` по 20 nmID с индексом, доля секунды.
Если когда-нибудь упрётся — добавим таблицу-кеш одной итерацией, интерфейс
не меняется (EXPLAIN проверить на Percona перед боем, план §Шаг 3).

Пороги — настройки компании (`companies.watch_*`, миграция 20261033).
Пока колонок нет — дефолты, как fallback `llm_provider.company_row` (:145).
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Нормализация фразы — единая с отчётом «Выдача WB» (competitors_positions_service),
# чтобы наши фразы из Search Reports и фразы из срезов выдачи сравнивались одинаково.
from backend.services.competitors_positions_service import _norm_phrase
from backend.services import capture_service

# Кэш матрицы в процессе: /summary и /matrix считают одно и то же, а фронт зовёт их
# параллельно. Без кэша тяжёлый расчёт выполняется дважды.
# Значение: (monotonic, wall_time, dict) — wall_time нужен ревалидации против БД:
# вместо слепого TTL перед отдачей снапшота проверяем, не изменились ли очередь/срезы.
_CACHE: dict[tuple, tuple[float, datetime, dict]] = {}
_CACHE_TTL = 60.0

# Запас на время расчёта снапшота: изменения, уложившиеся в последние 2 с перед
# записью кэша, могли не попасть в прочитанные данные — ревалидация ловит и их.
_CACHE_MARGIN = 2.0

# Дефолты, пока не применена миграция 20261033 (или company_id=None).
DEFAULT_SETTINGS = {
    "top_cards_n": 20,
    "top_phrases_n": 5,
    "stale_days": 7,
    "price_delta_pct": 5,
    "phrases_limit": 40,
    "card_stale_days": 30,
}

SETTINGS_SQL = """
    SELECT watch_top_cards_n, watch_top_phrases_n, watch_stale_days, watch_price_delta_pct
    FROM companies WHERE id=:c LIMIT 1
"""

# Лимит числа анализируемых фраз — отдельной колонкой (может отсутствовать).
SETTINGS_LIMIT_SQL = """
    SELECT watch_phrases_limit FROM companies WHERE id=:c LIMIT 1
"""

# Порог «устаревшей» карточки — отдельной колонкой (может отсутствовать).
SETTINGS_CARD_SQL = """
    SELECT watch_card_stale_days FROM companies WHERE id=:c LIMIT 1
"""


def _cache_put(key: tuple, value: dict) -> None:
    """Положить матрицу в кэш; попутно чистим просроченное (ключей мало, но пусть не растёт)."""
    now = time.monotonic()
    if len(_CACHE) > 20:
        for k in [k for k, v in _CACHE.items() if now - v[0] > _CACHE_TTL]:
            _CACHE.pop(k, None)
    _CACHE[key] = (now, datetime.now(), value)


async def _cache_outdated(db: AsyncSession, company_id: int | None,
                          wall: datetime) -> bool:
    """Снапшот кэша разошёлся с БД? Две быстрые проверки (только на hit-пути):

    1) очередь фраз менялась после записи кэша — covers «в очереди» гаснет сразу
       после сбора (все переходы обновляют updated_at);
    2) появился срез выдачи свежее кэша — метки вида 20261025_083705 сравнимы
       строкой, достаточно LIMIT 1 (индекс idx_position_slice).

    «Обновилось» — сигналом назад: ошибку запроса тоже считаем признаком
    устаревания — честный пересчёт надёжнее прокисшего кэша.
    """
    ts = wall - timedelta(seconds=_CACHE_MARGIN)
    stamp = ts.strftime("%Y%m%d_%H%M%S")
    try:
        q = (await db.execute(text("""
            SELECT COUNT(*) AS c FROM wb_search_phrase_queue
            WHERE company_id=:cid AND updated_at > :ts
        """), {"cid": company_id, "ts": ts})).mappings().first() or {}
        if int(q.get("c") or 0) > 0:
            return True
        s = (await db.execute(text("""
            SELECT 1 FROM wb_competitor_position FORCE INDEX (idx_position_slice)
            WHERE company_id=:cid AND slice_stamp<>'' AND slice_stamp > :s LIMIT 1
        """), {"cid": company_id, "s": stamp})).first()
        return s is not None
    except Exception as exc:  # noqa: BLE001 — любой сбой проверки = пересчёт
        _warn("cache_revalidate", company_id, exc)
        return True


def _cache_drop_company(company_id: int | None) -> None:
    """Сброс кэша матрицы компании: после requeue/refresh статусы в матрице
    должны обновиться сразу, а не когда догорит TTL (60 c)."""
    for k in [k for k in _CACHE if k[0] == company_id]:
        _CACHE.pop(k, None)


def _warn(tag: str, company_id: int | None, exc: Exception) -> None:
    """Падение SELECT настроек — предупреждение в лог (шаблон llm_provider.company_row)."""
    try:
        print(json.dumps(
            {tag: True, "company_id": company_id,
             "error": f"{type(exc).__name__}: {exc}"[:400]},
            ensure_ascii=False), flush=True)
    except Exception:
        pass


def _norm_rank(rank_by: str) -> str:
    """Ранг фраз: 'freq' (по частотности) или 'orders' (по заказам, по умолчанию)."""
    r = (rank_by or "").strip().lower()
    return "freq" if r in ("freq", "frequency", "частотность") else "orders"


def _period_days(date_from: str, date_to: str) -> int:
    """Дней в периоде — для метрики «запросов» (как в /wb-search/analytics)."""
    try:
        d1 = date.fromisoformat(date_from)
        d2 = date.fromisoformat(date_to) if date_to else date.today()
        return max(1, (d2 - d1).days + 1)
    except ValueError:
        return 30


class WatchService:
    # Не больше стольких фраз берём в одну очередь enrich (расширение обходит
    # очередь по одной — много карточек = долго и капча).
    REFRESH_PHRASES_LIMIT = 30
    # Сколько верхних позиций выдачи берём в анализ (в сборе WB лист ~100
    # карточек — работаем с ТОП-40, решение менеджера 2026-10-23).
    TOP_POSITIONS = 40
    # Порог «контент есть»: длина описания. Тот же, что DESC_MIN_LEN в
    # competitors_newcard_service.py:28 и MIN_DESC_LEN в phrase_miner_service.py:51.
    DESC_MIN_LEN = 50
    # Глубины, для которых матрица считает корзины карточек (селектор «из:»).
    DEPTH_BUCKETS = (10, 20, 40)
    # Код состояния контента в `pool` строки матрицы (лерды карточек окна фронт
    # дедупит сам — счётчик кнопки должен быть ровно тем, что уйдёт в очередь).
    POOL_CODE = {"fresh": 0, "stale": 1, "missing": 2}

    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # ---------------------------------------------------------------- настройки

    async def settings(self) -> dict:
        """Пороги мониторинга компании; нет колонок → дефолты (см. модуль docstring)."""
        if not self.company_id:
            return dict(DEFAULT_SETTINGS)
        try:
            row = (await self.db.execute(
                text(SETTINGS_SQL), {"c": self.company_id})).mappings().first()
        except Exception as exc:
            await self.db.rollback()
            _warn("watch_settings_default", self.company_id, exc)
            return dict(DEFAULT_SETTINGS)
        if not row:
            return dict(DEFAULT_SETTINGS)
        d = dict(DEFAULT_SETTINGS)
        for key, col in (
            ("top_cards_n", "watch_top_cards_n"),
            ("top_phrases_n", "watch_top_phrases_n"),
            ("stale_days", "watch_stale_days"),
            ("price_delta_pct", "watch_price_delta_pct"),
        ):
            v = row.get(col)
            if isinstance(v, int) and v > 0:
                d[key] = v
        # лимит числа фраз в анализе — отдельная колонка (миграция может не быть применена)
        try:
            row2 = (await self.db.execute(
                text(SETTINGS_LIMIT_SQL), {"c": self.company_id})).mappings().first()
        except Exception:
            await self.db.rollback()
            row2 = None
        if row2:
            v = row2.get("watch_phrases_limit")
            if isinstance(v, int) and v > 0:
                d["phrases_limit"] = v
        # порог «устаревшей» карточки — тоже отдельная колонка (миграция может не быть применена)
        try:
            row3 = (await self.db.execute(
                text(SETTINGS_CARD_SQL), {"c": self.company_id})).mappings().first()
        except Exception:
            await self.db.rollback()
            row3 = None
        if row3:
            v = row3.get("watch_card_stale_days")
            if isinstance(v, int) and v > 0:
                d["card_stale_days"] = v
        return d

    # ---------------------------------------------------------------- watch set

    async def top_cards(self, date_from: str, limit: int) -> list[dict]:
        """ТОП карточек по чистым заказам за период.

        Куб `agg_orders_daily_sku` = detail_by_period (`doc_type_name='Продажа'`,
        «чистые заказы», решение 2026-10-23 п.3) по (company_id, order_date, nmID,
        site_country) — поэтому SUM по дням/странам даёт итог карточки.

        ONLY_FULL_GROUP_BY: nmID в SELECT = GROUP BY; subject/brand — агрегаты.
        """
        stmt = text("""
            SELECT nmID, SUM(orders_qty) AS orders,
                   MAX(subject_name) AS subject_name, MAX(brand_name) AS brand_name
            FROM agg_orders_daily_sku
            WHERE company_id = :cid AND order_date >= :d1 AND nmID > 0
            GROUP BY nmID
            ORDER BY orders DESC, nmID ASC
            LIMIT :lim
        """)
        rows = (await self.db.execute(
            stmt, {"cid": self.company_id or 0, "d1": date_from,
                   "lim": max(1, int(limit))})).mappings().all()
        return [
            {"nm_id": int(r["nmID"]), "orders": int(r["orders"] or 0),
             "subject_name": r["subject_name"] or "", "brand_name": r["brand_name"] or ""}
            for r in rows
        ]

    async def top_phrases(self, card_nms: list[int], date_from: str,
                          per_card: int, rank_by: str = "orders",
                          date_to: str = "") -> dict:
        """ТОП-M фраз для каждой карточки + словарь уникальных.

        Источник — Search Reports (`wb_sr_report_item_phrases.company_id` — колонка
        есть, инсерт `search_report_service.py:281`). Ранжирование `rank_by`:
        - 'orders' — SUM(orders), ничья — SUM(clicks) (как раньше);
        - 'freq'   — «запросов» ровно как в /wb-search/analytics: по (фраза, день)
          MAX(week_frequency), AVG по дням присутствия × N дней периода.
        Дедуп nmID обязателен для фразы: она приходит по нескольким артикулам.
        pair (карточка, фраза) — единица мониторинга; одна фраза может приносить
        заказы нескольким карточкам → в `unique` она собирается в один элемент
        со списком `cards`.

        Returns:
            {"per_card": [{nm_id, phrases: [...]}], "unique": [{phrase, cards, freq, ...}]}
        """
        rank = _norm_rank(rank_by)
        n_days = _period_days(date_from, date_to)
        nms = sorted({int(n) for n in (card_nms or []) if int(n) > 0})
        if not nms:
            return {"per_card": [], "unique": []}
        ph = ",".join(f":n{j}" for j in range(len(nms)))
        params = {"cid": self.company_id or 0, "d1": date_from,
                  **{f"n{j}": n for j, n in enumerate(nms)}}
        # Гранулярность день: «запросов» считается по дням (MAX week_frequency),
        # заказы/клики складываются в Python. Тот же FORCE INDEX, что и раньше
        # (без него планировщик на сервере 1 ГБ берёт scan по компании).
        stmt = text(f"""
            SELECT p.nmID, p.phrase, p.`date`,
                   SUM(p.orders) AS orders, SUM(p.clicks) AS clicks,
                   MAX(p.week_frequency) AS wfreq
            FROM wb_sr_report_item_phrases p FORCE INDEX (idx_company_date_phrase)
            WHERE p.company_id = :cid AND p.nmID IN ({ph}) AND p.`date` >= :d1
            GROUP BY p.nmID, p.phrase, p.`date`
        """)  # ONLY_FULL_GROUP_BY: nmID+phrase+date в GROUP BY; остальное — агрегаты.
        rows = (await self.db.execute(stmt, params)).mappings().all()

        # агрегаты в Python: per (карточка, фраза) — заказы/клики+дни частотности;
        #     per (фраза, день)      — MAX по nmID (дедуп, как в analytics)
        agg: dict[tuple[int, str], dict] = {}
        ph_days: dict[str, dict[str, int]] = {}
        for r in rows:
            nm = int(r["nmID"])
            d = str(r["date"])
            # фразу нормализуем сразу: в wb_competitor_position она уже лежит
            # нормализованной (дефисы -> пробелы), иначе наши фразы не совпадут со срезами
            phrase = _norm_phrase(r["phrase"])
            if not _is_watch_phrase(phrase):
                continue
            wf = int(r["wfreq"] or 0)
            a = agg.setdefault(
                (nm, phrase), {"orders": 0, "clicks": 0, "days": {}})
            a["orders"] += int(r["orders"] or 0)
            a["clicks"] += int(r["clicks"] or 0)
            a["days"][d] = max(a["days"].get(d, 0), wf)
            pd = ph_days.setdefault(phrase, {})
            pd[d] = max(pd.get(d, 0), wf)

        def _total(days: dict[str, int]) -> int:
            """AVG по дням присутствия × N дней периода (формула analytics)."""
            return int(round(sum(days.values()) / len(days) * n_days)) if days else 0

        phrase_freq = {p: _total(days) for p, days in ph_days.items()}
        by_nm: dict[int, list[dict]] = {}
        for (nm, phrase), a in agg.items():
            by_nm.setdefault(nm, []).append({
                "phrase": phrase,
                "orders": a["orders"],
                "clicks": a["clicks"],
                # «запросов» по конкретной карточке — её собственные строки
                # (вот фильтр по одной карточке это и есть искомая метрика)
                "freq": _total(a["days"]),
            })
        limit_per_card = max(1, int(per_card))
        for lst in by_nm.values():
            if rank == "freq":
                lst.sort(key=lambda x: (-x["freq"], -x["orders"]))
            else:
                lst.sort(key=lambda x: (-x["orders"], -x["clicks"]))
        rows_per_card: list[dict] = []
        merged: dict[str, dict] = {}
        for nm, lst in by_nm.items():
            top = lst[:limit_per_card]
            rows_per_card.append({"nm_id": nm, "phrases": top})
            for p in top:
                merged.setdefault(p["phrase"], {
                    "phrase": p["phrase"], "cards": [], "orders_max": 0,
                    "freq": 0,
                })
                card = merged[p["phrase"]]
                card["cards"].append(
                    {"nm_id": nm, "orders": p["orders"], "clicks": p["clicks"]})
                card["orders_max"] = max(card["orders_max"], p["orders"])
                # по фразе — метрика analytics (дедуп MAX по nmID за день)
                card["freq"] = max(card["freq"], phrase_freq.get(p["phrase"], 0))
        rows_per_card.sort(key=lambda c: next(
            (i for i, x in enumerate(card_nms or []) if int(x or 0) == c["nm_id"]), 10**9))
        if rank == "freq":
            unique = sorted(merged.values(), key=lambda x: (-x["freq"], -x["orders_max"]))
        else:
            unique = sorted(merged.values(), key=lambda x: -x["orders_max"])
        return {"per_card": rows_per_card, "unique": unique}

    async def _is_company_card(self, nm_id: int) -> bool:
        """nmID принадлежит карточкам компании (`wbcards`) — валидация фильтра."""
        if int(nm_id or 0) <= 0:
            return False
        row = (await self.db.execute(text("""
            SELECT nmID FROM wbcards WHERE company_id = :cid AND nmID = :nm LIMIT 1
        """), {"cid": self.company_id or 0, "nm": int(nm_id)})).first()
        return bool(row)

    def _parse_filter(self, card_nm: int, rank_by: str,
                      queries_n: int) -> dict:
        """Разбор фильтров панели в ключи watch set / кэша матрицы.

        card_nm  — фильтр «наша карточка» (0 = все наши);
        rank     — ранг фраз: 'orders' | 'freq';
        queries  — сколько верхних запросов карточки берём (0 = порог компании).
        """
        return {"card_nm": int(card_nm or 0),
                "rank": _norm_rank(rank_by),
                "queries": max(0, min(int(queries_n or 0), 50))}

    async def watch_set(self, date_from: str, card_nm: int = 0,
                        rank_by: str = "orders", queries_n: int = 0,
                        date_to: str = "") -> dict:
        """Watch set целиком: настройки + карточки + фразы (по карточкам и уникальные).

        Фильтры панели (card_nm/rank_by/queries_n) меняют НАБОР фраз, но не
        список карточек: `cards` всегда полный (селект фильтра на фронте), а
        `cards_cnt` уже показывает срез (1 в карточном фильтре — как в KPI).
        """
        st = await self.settings()
        f = self._parse_filter(card_nm, rank_by, queries_n)
        cards = await self.top_cards(date_from, st["top_cards_n"])
        if f["card_nm"] and not await self._is_company_card(f["card_nm"]):
            raise ValueError(f"card {f['card_nm']} не входит в карточки компании")
        watch_nms = [c["nm_id"] for c in cards]
        per = st["top_phrases_n"]
        if f["card_nm"]:
            watch_nms = [f["card_nm"]]
            per = f["queries"] or per
        ph = await self.top_phrases(watch_nms, date_from, per,
                                    rank_by=f["rank"], date_to=date_to)
        return {
            "settings": st,
            "filter": {**f, "queries_n": per},
            "date_from": date_from,
            "cards": cards,
            "cards_cnt": 1 if f["card_nm"] else len(cards),
            "per_card": ph["per_card"],
            "phrases": ph["unique"],
            "phrases_cnt": len(ph["unique"]),
        }

    # ---------------------------------------------------------------- матрица

    @staticmethod
    def _inlist(prefix: str, values: list) -> tuple[str, dict]:
        """Плейсхолдеры IN (:p0,:p1,...) + параметры.

        Пустой список → пустая строка: вызывающий обязан проверить это ДО SQL
        (иначе будет `IN ()` — синтаксическая ошибка MySQL).
        """
        if not values:
            return "", {}
        ph = ",".join(f":{prefix}{i}" for i in range(len(values)))
        return ph, {f"{prefix}{i}": v for i, v in enumerate(values)}

    async def _slice_items(self, phrases: list[str], stamps: list[str],
                           top: int | None = None) -> dict:
        """Строки заходов: (фраза, stamp) -> позиции карточек.

        Выборка по МЕТКАМ ЗАХОДА (`slice_stamp`) через индекс
        `idx_position_slice (company_id, query_phrase, slice_stamp)` — точечно,
        только нужные заходы. FORCE INDEX обязателен: без него планировщик на
        сервере 1 ГБ выбирал scan по компании, и страница висела десятки минут.

        В Python приезжает только ТОП-N позиций выдачи (`top`) — по ТЗ работаем
        с видом покупателя, а в выдаче он видит первые 40. Что показываем, то и
        выгружаем: срезы большие (замер 2026-10-24: среднее 689 строк на заход,
        максимум 8740). Строки без меток (`slice_stamp=''`) не нужны: всё легаси
        перезалито псевдо-метками UPDATE'ом 2026-10-24.
        """
        if not phrases:
            return {}
        rows: list = []
        stamps = [s for s in (stamps or []) if s and not s.startswith("date:")]
        if stamps:
            # режем срез в SQL: ТОП-N позиций выдачи
            top = max(1, int(top or self.TOP_POSITIONS))
            sph, sp = self._inlist("s", stamps)
            pph, pp = self._inlist("p", phrases)
            rows += (await self.db.execute(text(f"""
                SELECT p.query_phrase AS phrase, p.slice_stamp, p.collected_at, p.nm_id,
                       p.title, p.brand, p.seller, p.position, p.position_api,
                       p.price, p.price_api, p.old_price, p.old_price_api,
                       p.rating, p.review_rating, p.reviews, p.feedbacks, p.badges,
                       -- срез хранит превью из DOM выдачи не всегда (лейзи-лоад
                       -- в момент захода) → дубль из сборов контента
                       COALESCE(NULLIF(p.image_url, ''), d.preview_image) AS image_url,
                       p.source_nm_id
                FROM wb_competitor_position p FORCE INDEX (idx_position_slice)
                LEFT JOIN wb_competitor_details d ON d.nm_id = p.nm_id
                WHERE p.company_id = :cid AND p.slice_stamp IN ({sph})
                  AND p.query_phrase IN ({pph})
                  AND p.position BETWEEN 1 AND {top}
            """), {"cid": self.company_id or 0, **sp, **pp})).mappings().all()
        # один товар в заходе — одна строка (привязка к нескольким нашим карточкам
        # даёт дубли; оставляем вариант с лучшей позицией)
        best: dict[tuple[str, str, int], dict] = {}
        for r in rows:
            stamp = r["slice_stamp"] or ("date:" + _d(r["collected_at"]))
            key = (_norm_phrase(r["phrase"]), stamp, int(r["nm_id"] or 0))
            prev = best.get(key)
            if prev is None or int(r["position"] or 999999) < int(prev["position"] or 999999):
                best[key] = dict(r)
        slices: dict[tuple[str, str], list[dict]] = {}
        for (phrase, stamp, _nm), r in best.items():
            pos = r["position"] if r["position"] else 999999
            slices.setdefault((phrase, stamp), []).append({
                "nm_id": int(r["nm_id"] or 0),
                "at": _d(r["collected_at"]),
                "title": r["title"] or "",
                "brand": r["brand"] or "",
                "seller": r["seller"] or "",
                "position": int(r["position"] or 0),
                "position_api": r["position_api"],
                "price": r["price"],
                "price_api": r["price_api"],
                "old_price": r["old_price"],
                "old_price_api": r["old_price_api"],
                "rating": r["rating"],
                "review_rating": r["review_rating"],
                "reviews": r["reviews"],
                "feedbacks": r["feedbacks"],
                "badges": _json_list(r["badges"]),
                "image_url": r["image_url"] or "",
                "source_nm_id": int(r["source_nm_id"] or 0),
                "_pos": pos,
            })
        for lst in slices.values():
            lst.sort(key=lambda x: x["_pos"])
        return slices

    async def _queue_status(self, phrases: list[str]) -> dict[str, dict]:
        """Статус очереди пересборки выдачи (`wb_search_phrase_queue`) по нашим фразам."""
        if not phrases:
            return {}
        pph, pp = self._inlist("p", phrases)
        rows = (await self.db.execute(text(f"""
            SELECT query_phrase, status, updated_at, last_error
            FROM wb_search_phrase_queue
            WHERE company_id = :cid AND query_phrase IN ({pph})
        """), {"cid": self.company_id or 0, **pp})).mappings().all()
        return {_norm_phrase(r["query_phrase"]): {
            "status": r["status"] or "", "updated_at": _d(r["updated_at"]),
            "last_error": r["last_error"] or ""} for r in rows}

    async def _slice_counts(self, phrases: list[str],
                            stamps: list[str]) -> dict[tuple[str, str], int]:
        """Сколько УНИКАЛЬНЫХ карточек в каждом заходе — для `cards_cnt`.

        Считает без выгрузки строк: `COUNT(DISTINCT nm_id)` по тем же меткам
        заходов, что и в `_slice_items` (агрегат по индексу ~0.1-0.5 с на 80
        срезов, замер 2026-10-24). В матрице срезы режутся по ТОП-N и нашим
        карточкам, поэтому `len()` выгруженного списка карточкам больше не равен.
        """
        phs = [p for p in (phrases or []) if p]
        sts = [s for s in (stamps or []) if s]
        if not phs or not sts:
            return {}
        sph, sp = self._inlist("s", sts)
        pph, pp = self._inlist("p", phs)
        rows = (await self.db.execute(text(f"""
            SELECT p.query_phrase AS phrase, p.slice_stamp,
                   COUNT(DISTINCT p.nm_id) AS cnt
            FROM wb_competitor_position p FORCE INDEX (idx_position_slice)
            WHERE p.company_id = :cid AND p.slice_stamp IN ({sph})
              AND p.query_phrase IN ({pph})
            GROUP BY p.query_phrase, p.slice_stamp
        """), {"cid": self.company_id or 0, **sp, **pp})).mappings().all()
        return {(_norm_phrase(r["phrase"]), r["slice_stamp"]): int(r["cnt"] or 0)
                for r in rows}

    async def _slice_stamps(self, phrases: list[str], limit: int = 2) -> dict[str, list[str]]:
        """Последние метки заходов по каждой фразе (DESC по времени).

        DISTINCT по индексу `idx_position_slice (company_id, query_phrase, slice_stamp)`:
        MySQL делает loose index scan — индекс-only, без чтения строк. Сканить
        срез по периоду нельзя: индекса (company, date, phrase) у этой таблицы
        нет, и такой GROUP BY уводил сервер 1 ГБ в своп.
        """
        if not phrases:
            return {}
        pph, pp = self._inlist("p", phrases)
        stmt = text(f"""
            SELECT DISTINCT p.query_phrase AS phrase, p.slice_stamp
            FROM wb_competitor_position p FORCE INDEX (idx_position_slice)
            WHERE p.company_id = :cid AND p.query_phrase IN ({pph})
              AND p.slice_stamp <> ''
            ORDER BY p.query_phrase, p.slice_stamp DESC
        """)
        rows = (await self.db.execute(stmt, {"cid": self.company_id or 0,
                                            **pp})).mappings().all()
        out: dict[str, list[str]] = {}
        for r in rows:
            lst = out.setdefault(_norm_phrase(r["phrase"]), [])
            if len(lst) < limit:
                lst.append(r["slice_stamp"])
        return out

    async def _our_cards(self) -> dict[int, str]:
        """Наши карточки компании: nmID → vendorCode (из `wbcards`).

        «Наш товар в выдаче» = строка `wb_competitor_position`, у которой nm_id
        есть в wbcards этой компании. Всё остальное — конкуренты.
        vendorCode — артикул для показа на фронте (тултип позиции).
        """
        rows = (await self.db.execute(text("""
            SELECT nmID, vendorCode FROM wbcards WHERE company_id = :cid AND nmID > 0
        """), {"cid": self.company_id or 0})).mappings().all()
        return {int(r["nmID"]): (r["vendorCode"] or "") for r in rows if r["nmID"]}

    async def _our_photos(self) -> dict[int, str]:
        """Наши карточки: nmID → фото[0] из `wbcards.photos` (синк карточек).

        Фолбэк для позиций наших карточек, у которых превью в срезе не
        уцелело: шаблоны photo пишет синк, и ссылка на WB-CDN всегда живая
        (модалку «Наша карточка» этот же источник и рисует).
        """
        rows = (await self.db.execute(text("""
            SELECT nmID, photos FROM wbcards
            WHERE company_id = :cid AND nmID > 0 AND photos <> '' AND photos <> '[]'
        """), {"cid": self.company_id or 0})).mappings().all()
        out: dict[int, str] = {}
        for r in rows:
            nm = int(r["nmID"] or 0)
            if not nm:
                continue
            lst = _json_list(r["photos"])
            if isinstance(lst, str):
                # двойное кодирование — разбираем ещё раз
                lst = _json_list(lst)
            u = lst[0] if isinstance(lst, list) and lst else ""
            if isinstance(u, dict):
                u = u.get("big") or u.get("c246x328") or u.get("url") or ""
            if u:
                out[nm] = str(u) if str(u).startswith("http") else ("https:" + str(u))
        return out

    async def _content_state(self, nm_ids: list[int]) -> dict[int, tuple[bool, str, str]]:
        """nm → (есть описание, дата полного сбора, дата первого сбора).

        «Контент есть» = описание не короче `DESC_MIN_LEN` символов. Лёгкие строки,
        которые создаёт наблюдение выдачи (`ext.py:634-662`: цена/рейтинг/превью),
        описания не содержат — значит контента по карточке ещё нет.

        Дата контента — `full_collected_at` (полный сбор: описание + характеристики),
        иначе `first_collected_at` (строки, собранные до миграции 20261021).

        НЕ `collected_at`: его двигает пассивное наблюдение выдачи (`ext.py:653`) —
        карточка, у которой описание никто не собирал, выглядела бы «свежей», и
        кнопки сбора не видели бы кандидатов.

        Чанки по 400 — больших IN не делаем (сервер 1 ГБ).
        """
        ids = sorted({int(n) for n in nm_ids if n})
        out: dict[int, tuple[bool, str, str]] = {}
        for i in range(0, len(ids), 400):
            ch = ids[i:i + 400]
            cph, cp = self._inlist("c", ch)
            rows = (await self.db.execute(text(f"""
                SELECT nm_id,
                       MAX(full_collected_at) AS full_at,
                       MAX(first_collected_at) AS first_at,
                       MAX(CHAR_LENGTH(COALESCE(description, ''))) AS dlen
                FROM wb_competitor_details WHERE nm_id IN ({cph}) GROUP BY nm_id
            """), cp)).mappings().all()
            for r in rows:
                full_at = _d(r["full_at"]) if r["full_at"] else ""
                first_at = _d(r["first_at"]) if r["first_at"] else ""
                has = int(r["dlen"] or 0) >= self.DESC_MIN_LEN
                out[int(r["nm_id"] or 0)] = (has, full_at, first_at)
        return out

    async def matrix(self, date_from: str, date_to: str,
                     card_nm: int = 0, rank_by: str = "orders",
                     queries_n: int = 0) -> dict:
        """Матрица мониторинга: строка = фраза watch set.

        По каждой фразе — последний срез выдачи и предыдущий: наши позиции, новые
        карточки (последний минус предыдущий), сдвиги цен (порог компании),
        свежесть сбора (порог `watch_stale_days`) и статус очереди пересборки.

        Фильтры панели (card_nm/rank_by/queries_n) — параметрами вызова (не
        настройки компании): меняют набор фраз и порядок строк, все три входят
        в ключ кэша.

        Результат кэшируется на минуту (`/summary` и `/events` — производные от
        той же матрицы). Фронт запрашивает только `/matrix`: параллельные
        Promise.all кэшу не подчинялись (обе проверки до первого await) и расчёт
        выполнялся дважды.
        """
        f = self._parse_filter(card_nm, rank_by, queries_n)
        key = (self.company_id, date_from, date_to, f["card_nm"], f["rank"],
               f["queries"])
        hit = _CACHE.get(key)
        if hit and (time.monotonic() - hit[0]) < _CACHE_TTL:
            # Ревалидация против БД: очередь обновилась или лёг новый срез —
            # пересчитываем сразу (после сбора F5 должен показывать свежее,
            # а не доклевать 60-секундный снапшот).
            if await _cache_outdated(self.db, self.company_id, hit[1]):
                _CACHE.pop(key, None)
            else:
                return hit[2]

        # Тайминги по фазам — в stdout (journalctl) и в поле timings ответа:
        # на сервере 1 ГБ сразу видно, какая фаза встала.
        t_start = time.monotonic()
        timings: dict[str, float] = {}
        _t = time.monotonic()

        def _done(tag: str) -> None:
            nonlocal _t
            timings[tag] = round(time.monotonic() - _t, 3)
            _t = time.monotonic()

        st = await self.settings()
        _done("settings")
        ws = await self.watch_set(date_from, card_nm=f["card_nm"],
                                  rank_by=f["rank"], queries_n=f["queries"],
                                  date_to=date_to)
        _done("watch_set")
        # Сколько фраз анализируем: каждый анализ это скан срезов выдачи по всем
        # фразам. Лимит берём из настроек компании (watch_phrases_limit), по
        # умолчанию 40; ради «до 100 фраз» лимит поднимают в самой компании
        # (2026-10-23: индексы срезов оптимизированы, полный набор ~1.5 с).
        limit_phrases = max(1, int(st.get("phrases_limit") or 40))
        phrases_all = [p["phrase"] for p in ws["phrases"]]
        phrases = phrases_all[:limit_phrases]
        cards_by_phrase = {p["phrase"]: p for p in ws["phrases"]}
        if not phrases:
            res = {"settings": st, "filter": ws["filter"],
                   "date_from": date_from, "date_to": date_to,
                   "cards": ws["cards"], "items": [], "total": 0,
                   "cards_cnt": ws["cards_cnt"], "phrases_cnt": 0,
                   "phrases_total": len(phrases_all),
                   "timings": timings}
            _cache_put(key, res)
            return res

        # Наши карточки (nmID → vendorCode) — для разметки «наше/конкурент»
        # и артикулов в колонке «Наши позиции» (SQL-срез уже режется по ТОП-40).
        our_cards = await self._our_cards()
        our_ids = set(our_cards)
        _done("our_ids")
        # Два последних захода по фразе — из индекса (DISTINCT, index-only).
        # Заход = один заход в поиск: за сутки их бывает два, и это разные выдачи.
        stamps_map = await self._slice_stamps(phrases, 2)
        _done("stamps")
        last_pair: dict[str, tuple[str, str]] = {}
        all_stamps: set[str] = set()
        for ph, sl in stamps_map.items():
            last_pair[ph] = (sl[0], sl[1] if len(sl) > 1 else "")
            all_stamps.update(sl)
        # ТОП-40 позиций выдачи — остальное из MySQL не выгружаем.
        slices = await self._slice_items(list(last_pair.keys()), sorted(all_stamps))
        _done("slices")
        # Честное cards_cnt («сколько всего карточек в заходе») — без выгрузки строк.
        slice_counts = await self._slice_counts(list(last_pair.keys()), sorted(all_stamps))
        _done("counts")
        # Состояние контента карточек («Актуальные / Устаревшие / Нет содержимого»):
        # есть ли описание и когда был полный сбор. Точечно — чанки по 400, только
        # nm из выгруженных срезов; критерий тот же, что у кнопок сбора.
        cutoff = (date.today() - timedelta(days=int(st["card_stale_days"]))).isoformat()
        content_state = await self._content_state(
            [it["nm_id"] for lst in slices.values() for it in lst])
        _done("fresh")
        queue = await self._queue_status(list(last_pair.keys()))
        _done("queue")

        today = date.today()
        items: list[dict] = []
        for ph in phrases:
            meta = cards_by_phrase.get(ph, {})
            last_stamp, prev_stamp = last_pair.get(ph, ("", ""))
            last_slice = slices.get((ph, last_stamp), []) if last_stamp else []
            prev_slice = slices.get((ph, prev_stamp), []) if prev_stamp else []
            # дата захода — из самих строк среза
            last_d = last_slice[0]["at"] if last_slice else ""
            prev_d = prev_slice[0]["at"] if prev_slice else ""

            def _evt_fresh(nm: int) -> bool:
                """Событие уже отражено в контенте карточки? — тогда не собираем.

                «Свежее» = описание есть и контент собрали НЕ РАНЬШЕ старого
                захода (prev_at) — т.е. позже события «новая в выдаче»/«сдвиг
                цены». Повторный сбор по такой карточке не добавит ничего
                (решение менеджера 2026-10-25: «кнопку "Собрать новые и изм."
                жмёшь, а там снова те же 21»).
                """
                has, full_at, first_at = content_state.get(int(nm), (False, "", ""))
                at = full_at or first_at
                return bool(has and at and prev_d and at >= prev_d)

            # Топ-часть выдачи — окно анализа: вид покупателя (первые 40 позиций).
            top_items = [it for it in last_slice
                         if int(it["position"] or 999) <= self.TOP_POSITIONS]

            # Цены против медианы ТОП-40: конкуренты того же захода, наши исключены.
            comp_prices: list[float] = []
            for it in top_items:
                if it["nm_id"] in our_ids:
                    continue
                try:
                    p = float(it["price"] or it["price_api"])
                except (TypeError, ValueError):
                    continue
                if p > 0:
                    comp_prices.append(p)
            comp_prices.sort()
            price_median = round(statistics.median(comp_prices), 2) if comp_prices else None
            price_min = comp_prices[0] if comp_prices else None

            # «Наш товар» — строка выдачи, у которой nm_id есть в wbcards компании.
            # source_nm_id — контекст захода (наша карточка, чей запрос собирали),
            # по нему «наше» НЕ определяется.
            # Позиция — DOM (что видит покупатель в выдаче). position_api — это
            # номер в JSON-каталоге WB, он другой: наша карточка №1 в списке
            # бывает №100 в каталоге. В одной колонке их мешать нельзя.
            # Для каждой нашей карточки — дельта к медиане и сколько конкурентов
            # дешевле (основа колонки «Цена vs ТОП-40»).
            ours = []
            for it in last_slice:
                if it["nm_id"] not in our_ids:
                    continue
                o_price = it["price"] or it["price_api"]
                delta = None
                cheaper = None
                if price_median is not None:
                    try:
                        of = float(o_price)
                    except (TypeError, ValueError):
                        of = None
                    if of is not None and of > 0:
                        delta = round((of - price_median) / price_median * 100, 1)
                        cheaper = sum(1 for p in comp_prices if p < of)
                ours.append({"nm_id": it["nm_id"],
                             "position": it["position"],
                             "price": o_price,
                             "vendor_code": our_cards.get(it["nm_id"], ""),
                             "price_delta_pct": delta,
                             "cheaper_cnt": cheaper})
            best_pos = min((o["position"] for o in ours if o["position"]), default=None)
            top_ours = [it for it in top_items if it["nm_id"] in our_ids]

            # «Новые» = есть в последнем заходе, но не было в предыдущем
            # (то, что влетело в выдачу с прошлого сбора). Сравниваем по ТОП-N
            # позициям — тем же, что показываем в раскрытии, иначе «новых: 6»
            # в строке и карточки в выдаче не совпадут.
            prev_top = {it["nm_id"]: it for it in prev_slice
                        if int(it["position"] or 999) <= self.TOP_POSITIONS}
            new_items = [it for it in top_items
                         if prev_stamp and it["nm_id"] not in prev_top]

            moves: list[dict] = []
            if prev_stamp:
                for it in top_items:
                    was = prev_top.get(it["nm_id"])
                    if not was:
                        continue
                    p_now = it["price"] or it["price_api"]
                    p_old = was["price"] or was["price_api"]
                    try:
                        p_now_f, p_old_f = float(p_now), float(p_old)
                    except (TypeError, ValueError):
                        continue
                    if p_old_f <= 0:
                        continue
                    pct = (p_now_f - p_old_f) / p_old_f * 100
                    if abs(pct) >= st["price_delta_pct"]:
                        moves.append({"nm_id": it["nm_id"], "title": it["title"],
                                      "from": p_old_f, "to": p_now_f,
                                      "pct": round(pct, 1),
                                      "fresh": _evt_fresh(it["nm_id"])})

            days_old = (today - date.fromisoformat(last_d)).days if last_d else None
            fresh = bool(days_old is not None and days_old <= st["stale_days"])
            # «Актуальные / Устаревшие / Нет содержимого» — по КОНТЕНТУ карточек
            # ТОП-40 последнего захода:
            #   А — описание есть и полный сбор не старше порога компании;
            #   У — описание есть, но старше порога (watch_card_stale_days);
            #   Н — описания нет (контент не собирали ни разу).
            # Те же цифры, что и у кнопок сбора: «Собрать отсутствующие» берёт Н,
            # «Обновить устаревшие» — У+Н.
            cards_fresh = 0
            cards_stale = 0
            cards_missing = 0
            # Корзины по глубине (селектор «из: ТОП-10/20/40») — счётчик кнопки
            # должен совпадать с тем, что реально соберётся.
            depth_buckets: dict[str, dict[str, int]] = {
                str(d): {"fresh": 0, "stale": 0, "missing": 0}
                for d in self.DEPTH_BUCKETS
            }
            # Пул окна для фронта: список карточек [nm, позиция, статус контента],
            # статус — POOL_CODE (0 актуальный / 1 устаревший / 2 без описания).
            # Фронт считает по нему УНИКАЛЬНЫЕ карточки любых выбранных фраз и
            # любой глубины — суммы по фразам завышали кнопки (953 реального 22).
            pool_cards: list[list[int]] = []
            for it in top_items:
                nm = int(it["nm_id"] or 0)
                if not nm:
                    continue
                has, full_at, first_at = content_state.get(nm, (False, "", ""))
                at = full_at or first_at
                if not has:
                    kind = "missing"
                elif at and at >= cutoff:
                    kind = "fresh"
                else:
                    kind = "stale"
                if kind == "fresh":
                    cards_fresh += 1
                elif kind == "stale":
                    cards_stale += 1
                else:
                    cards_missing += 1
                pos = int(it["position"] or 0)
                pool_cards.append([nm, pos, self.POOL_CODE[kind]])
                for d in self.DEPTH_BUCKETS:
                    if pos <= d:
                        depth_buckets[str(d)][kind] += 1
            items.append({
                "phrase": ph,
                "orders_max": meta.get("orders_max", 0),
                # «Запросов» за период — метрика /wb-search/analytics (MAX по
                # nmID за день → AVG × дней периода); ранг 'freq' идёт по ней
                "freq": int(meta.get("freq") or 0),
                "cards": meta.get("cards", []),
                "last_at": last_d,
                "prev_at": prev_d,
                "last_stamp": last_stamp,
                "slices_cnt": 2 if prev_stamp else (1 if last_stamp else 0),
                "days_old": days_old,
                "fresh": fresh,
                "stale_days": st["stale_days"],
                "cards_cnt": slice_counts.get((ph, last_stamp), 0),
                "cards_fresh": cards_fresh,
                "cards_stale": cards_stale,
                "cards_missing": cards_missing,
                "cards_by_depth": depth_buckets,
                "pool": pool_cards,
                "ours_cnt": len(ours),
                "top_cnt": len(top_items),
                "top_ours_cnt": len(top_ours),
                "price_median": price_median,
                "price_min": price_min,
                "price_cnt": len(comp_prices),
                "our_positions": ours,
                "best_position": best_pos,
                "new_cnt": len(new_items),
                "new_items": [{"nm_id": it["nm_id"], "title": it["title"],
                               "position": it["position"],
                               "price": it["price"] or it["price_api"],
                               # «свежее события» — пересбор не нужен, см. _evt_fresh
                               "fresh": _evt_fresh(it["nm_id"])}
                              for it in new_items[:50]],
                "price_moves": moves[:50],
                "price_moves_cnt": len(moves),
                "requeue_status": (queue.get(ph) or {}).get("status", ""),
                "requeue_at": (queue.get(ph) or {}).get("updated_at", ""),
            })
        if f["rank"] == "freq":
            items.sort(key=lambda x: (-x["freq"], -x["orders_max"]))
        else:
            items.sort(key=lambda x: -x["orders_max"])
        _done("build")
        timings["total"] = round(time.monotonic() - t_start, 3)
        # Тайминги в stdout — их видно в journalctl сразу, без открытия страницы.
        print(json.dumps({"watch_matrix": True, "company_id": self.company_id,
                          "total_s": timings["total"], "phases": timings,
                          "phrases": len(phrases),
                          "filter": ws["filter"],
                          "rows": sum(len(v) for v in slices.values())},
                         ensure_ascii=False), flush=True)
        res = {"settings": st, "filter": ws["filter"],
               "date_from": date_from, "date_to": date_to,
               "cards": ws["cards"], "cards_cnt": ws["cards_cnt"],
               "items": items, "total": len(items),
               "phrases_cnt": len(phrases),
               "phrases_total": len(phrases_all),
               "timings": timings}
        _cache_put(key, res)
        return res

    async def summary(self, date_from: str, date_to: str,
                      card_nm: int = 0, rank_by: str = "orders",
                      queries_n: int = 0) -> dict:
        """KPI сводки — производная от матрицы."""
        m = await self.matrix(date_from, date_to, card_nm, rank_by, queries_n)
        items = m["items"]
        fresh = [i for i in items if i["fresh"]]
        positions = [i["best_position"] for i in items if i["best_position"]]
        in_top3 = sum(1 for p in positions if p and p <= 3)
        in_top10 = sum(1 for p in positions if p and p <= 10)
        return {
            "settings": m["settings"],
            "date_from": date_from,
            "date_to": date_to,
            "cards_cnt": m["cards_cnt"],
            "phrases_cnt": len(items),
            "phrases_total": m.get("phrases_total", len(items)),
            "fresh_cnt": len(fresh),
            "stale_cnt": len(items) - len(fresh),
            "with_position_cnt": len(positions),
            "top3_cnt": in_top3,
            "top10_cnt": in_top10,
            "top3_pct": round(in_top3 / len(items) * 100) if items else 0,
            "top10_pct": round(in_top10 / len(items) * 100) if items else 0,
            "avg_position": round(sum(positions) / len(positions), 1) if positions else None,
            "new_cnt": sum(i["new_cnt"] for i in items),
            "price_moves_cnt": sum(i["price_moves_cnt"] for i in items),
            "filter": m.get("filter", {}),
        }

    async def events(self, date_from: str, date_to: str,
                     type: str = "", limit: int = 200,
                     card_nm: int = 0, rank_by: str = "orders",
                     queries_n: int = 0) -> dict:
        """Лента событий по фразам мониторинга: новые карточки и сдвиги цен."""
        m = await self.matrix(date_from, date_to, card_nm, rank_by, queries_n)
        new_rows: list[dict] = []
        price_rows: list[dict] = []
        for it in m["items"]:
            for n in it["new_items"]:
                new_rows.append({"type": "new", "phrase": it["phrase"],
                                 "last_at": it["last_at"], **n})
            for mv in it["price_moves"]:
                price_rows.append({"type": "price", "phrase": it["phrase"],
                                   "last_at": it["last_at"], "prev_at": it["prev_at"], **mv})
        out: dict = {"date_from": date_from, "date_to": date_to}
        if type in ("", "new"):
            out["new"] = new_rows[:limit]
        if type in ("", "price"):
            out["price"] = price_rows[:limit]
        return out

    async def phrase_detail(self, phrase: str, date_from: str, date_to: str,
                            days: int = 14) -> dict:
        """Срезы выдачи по одной фразе (последние N заходов) — раскрытие строки матрицы.

        Заход = один заход в поиск (`slice_stamp`); в нём — позиции/цены карточек.
        """
        ph = _norm_phrase(phrase)
        if not ph:
            return {"phrase": "", "days": []}
        days = max(1, min(int(days or 14), 60))
        # Заходы — из индекса (DISTINCT, index-only), позиции — точечно по меткам.
        stamps_map = await self._slice_stamps([ph], days)
        sl_list = stamps_map.get(ph, [])
        stamps = list(sl_list)
        # наши карточки — только для разметки is_ours (срез уже режется по ТОП-40)
        our_ids = set(await self._our_cards())
        our_photos = await self._our_photos()
        slices = await self._slice_items([ph], stamps)
        st = await self.settings()
        # sl_list — от свежих к старым: показываем новые первыми, «предыдущий»
        # заход = следующий в списке (он старее).
        total = len(sl_list)
        out_days = []
        for idx, stamp in enumerate(sl_list):
            # ТОП-N позиций выдачи: в сборе лист ~100 карточек, работаем с верхом
            items = [it for it in slices.get((ph, stamp), [])
                     if int(it["position"] or 999) <= self.TOP_POSITIONS]
            prev_stamp = sl_list[idx + 1] if idx + 1 < total else ""
            # сравниваем тоже по ТОП-N: карточка, что была на 50-й позиции, не
            # должна считаться «новой», если сейчас она на 20-й
            prev_items = [it for it in slices.get((ph, prev_stamp), [])
                          if int(it["position"] or 999) <= self.TOP_POSITIONS] \
                if prev_stamp else []
            prev_by_nm = {it["nm_id"]: it for it in prev_items}
            out = []
            for it in items:
                was = prev_by_nm.get(it["nm_id"])
                price_now = it["price"] if it["price"] else it["price_api"]
                price_old = None
                pct = None
                if was:
                    price_old = was["price"] if was["price"] else was["price_api"]
                    try:
                        pn = float(price_now) if price_now is not None else None
                        po = float(price_old) if price_old is not None else None
                        if pn is not None and po is not None and po > 0:
                            pct = round((pn - po) / po * 100, 1)
                    except (TypeError, ValueError):
                        pct = None
                # «новая» — есть в этом заходе, но не было в предыдущем
                is_new = 1 if (prev_stamp and not was) else 0
                # фото: срез нередко приходит без превью (лейзи-лоад в момент
                # захода) → для наших подставляем фото из wbcards (синк);
                # превью конкурентов уже подставлено в _slice_items из деталей
                img = it["image_url"] or our_photos.get(int(it["nm_id"] or 0), "")
                out.append({
                    **it,
                    "image_url": img,
                    "is_ours": 1 if it["nm_id"] in our_ids else 0,
                    "is_new": is_new,
                    "price_prev": price_old,
                    "price_pct": pct,
                    "price_changed": 1 if (pct is not None and abs(pct) >= st["price_delta_pct"]) else 0,
                })
            out_days.append({
                "date": items[0]["at"] if items else "",
                "time": _stamp_time(stamp),
                "cards_cnt": len(items),
                "items": out,
            })
        return {"phrase": ph, "days": out_days, "days_cnt": len(out_days)}

    async def requeue(self, phrases: list[str], user_id: int | None = None,
                      date_from: str = "", card_nm: int = 0,
                      rank_by: str = "orders", queries_n: int = 0) -> dict:
        """Фразы на пересборку выдачи — очередь `wb_search_phrase_queue`.

        Её читает расширение («Поисковые фразы» в попапе): фраза → заход в поиск
        WB → новый срез выдачи (позиции, цены, рейтинги).

        Без лимита: сколько отметил менеджер — столько и встаёт в очередь
        (расширение обходит её по одной, с паузами).

        Фразу привязываем к НАШЕЙ карточке (из watch set): `source_nm_id` — это
        карточка, относительно которой меряются позиции. Без привязки расширение
        соберёт сырьё по нише, и «наши» позиции не появятся.
        """
        cid = int(self.company_id or 0)
        if not cid:
            return {"queued": 0, "phrases": [], "skipped": []}

        # фраза -> наша карточка (фраза приносит заказы конкретной карточке ТОП)
        src_of: dict[str, int] = {}
        if date_from:
            ws = await self.watch_set(date_from, card_nm=card_nm,
                                      rank_by=rank_by, queries_n=queries_n)
            for card in ws["per_card"]:
                for p in card["phrases"]:
                    src_of.setdefault(p["phrase"], card["nm_id"])

        wanted: list[str] = []
        seen: set[str] = set()
        for raw in (phrases or []):
            ph = _norm_phrase(raw)
            if ph and ph not in seen:
                seen.add(ph)
                wanted.append(ph)
        if not wanted:
            return {"queued": 0, "phrases": [], "skipped": []}

        # пачкой, алиасом строки (MySQL 8.0.19+; VALUES() в UPDATE запрещён)
        for ph in wanted:
            await self.db.execute(text("""
                INSERT INTO wb_search_phrase_queue
                  (company_id, source_nm_id, query_phrase, phrase_raw, status, priority, source, created_by)
                VALUES (:cid, :nm, :ph, :ph, 'pending', 10, 'watch', :uid) AS new
                ON DUPLICATE KEY UPDATE
                  status='pending', source_nm_id=new.source_nm_id,
                  source=new.source, updated_at=NOW(), last_error=NULL
            """), {"cid": cid, "nm": src_of.get(ph, 0), "ph": ph, "uid": user_id})
        _cache_drop_company(cid)
        await self.db.commit()

        return {"queued": len(wanted), "phrases": wanted, "skipped": []}

    async def refresh_top(self, phrases: list[str], top: int = 10,
                          date_from: str = "", date_to: str = "",
                          card_nm: int = 0,
                          rank_by: str = "orders", queries_n: int = 0) -> dict:
        """«Обновить ТОП-N»: карточки ТОП-N последнего среза → очередь enrich.

        Пул — первые `top` позиций выдачи (по умолчанию ТОП-10) последнего захода
        по целевым фразам. Пропускаем только то, что полным сбором взяли СЕГОДНЯ
        (решение менеджера 2026-10-25: «не пропускать наши и свежие карточки,
        если они не были собраны сегодня ранее») — то есть обновляем и вчерашние.

        Свои карточки НЕ пропускаем: менеджеру нужны их бэджи и цены из выдачи,
        а контент нашей карточки в `wb_competitor_details` — тоже (общий кэш по nm).

        Целевые фразы: отмеченные в матрице, а если не отмечено ни одной — весь
        watch set (как у «Собрать отсутствующие»/«Обновить устаревшие»).

        Очередь помечается `source='watch'` — расширение берёт её отдельным
        режимом («SEO-мониторинг»), как и остальные кнопки блока «Действия».
        Статус `need_update` здесь не годится: `ext.py:259-261` отдаёт такие
        строки только в общем режиме «Обновление» (source=''/NULL), а строки
        `need_update` + `source='watch'` не берёт ни один режим.

        Фраз за раз — не больше REFRESH_PHRASES_LIMIT: расширение обходит очередь
        по одной, сотня карточек в очереди = надолго и капча.
        """
        st = await self.settings()
        top = max(1, min(int(top or 10), 50))
        norm = [p for p in dict.fromkeys(_norm_phrase(x) for x in (phrases or []) if _norm_phrase(x))]
        if not norm:
            ws = await self.watch_set(date_from, card_nm=card_nm,
                                      rank_by=rank_by, queries_n=queries_n,
                                      date_to=date_to)
            limit_phrases = max(1, int(st.get("phrases_limit") or 40))
            norm = [p["phrase"] for p in ws["phrases"]][:limit_phrases]
        overflow = norm[self.REFRESH_PHRASES_LIMIT:]
        norm = norm[:self.REFRESH_PHRASES_LIMIT]
        if not norm:
            return {"requested": 0, "assigned": 0, "skipped": 0, "candidates": 0,
                    "top": top, "overflow": 0, "phrases_cnt": 0,
                    "skipped_today": 0, "stale_days": st["stale_days"]}
        # последний заход каждой фразы — из индекса (index-only), позиции — точечно
        stamps_map = await self._slice_stamps(norm, 1)
        last_stamps = [sl[0] for sl in stamps_map.values() if sl]
        slices = await self._slice_items(norm, sorted(set(last_stamps)), top)
        cand: set[int] = set()
        for ph in norm:
            sl = stamps_map.get(ph, [])
            if not sl:
                continue
            for it in slices.get((ph, sl[0]), []):
                if int(it["position"] or 999) <= top:
                    cand.add(int(it["nm_id"] or 0))
        cand = {n for n in cand if n > 0}
        if not cand:
            return {"requested": len(norm), "assigned": 0, "skipped": 0,
                    "candidates": 0, "top": top, "overflow": len(overflow),
                    "phrases_cnt": len(norm), "skipped_today": 0,
                    "stale_days": st["stale_days"]}

        # «Собрано сегодня» (полный сбор) — такие не трогаем.
        today_iso = date.today().isoformat()
        state = await self._content_state(sorted(cand))
        skipped_today = {n for n in cand
                          if (state.get(n) or (False, "", ""))[1] == today_iso}
        cand -= skipped_today

        assigned, skipped = await self._enqueue_watch(cand)
        _cache_drop_company(self.company_id)
        await self.db.commit()
        return {"requested": len(norm), "assigned": assigned, "skipped": skipped,
                "candidates": len(cand), "top": top, "overflow": len(overflow),
                "phrases_cnt": len(norm), "skipped_today": len(skipped_today),
                "stale_days": st["stale_days"]}

    async def collect_nm_ids(self, nm_ids: list[int]) -> dict:
        """Перечисленные карточки → очередь enrich (`source='watch'`).

        Кнопка «Собрать» на странице собранных карточек (одна или помеченные).
        Карточки, исключённые из сбора (`wb_competitor_capture.is_hidden`), не
        ставятся — счётчиком `excluded`. Повторный вызов идемпотентен
        (`uq_nm_id` + `ON DUPLICATE KEY` в `_enqueue_watch`).
        """
        norm: list[int] = []
        for x in nm_ids or []:
            try:
                n = int(x)
            except (TypeError, ValueError):
                continue
            if n > 0:
                norm.append(n)
        norm = list(dict.fromkeys(norm))[:500]
        if not norm:
            return {"requested": 0, "assigned": 0, "skipped": 0, "excluded": 0}

        cl, cp = self._inlist("e", norm)
        cond = f"AND c.company_id=:cid" if self.company_id is not None else ""
        iparams: dict = dict(cp)
        if self.company_id is not None:
            iparams["cid"] = self.company_id
        rows = (await self.db.execute(text(f"""
            SELECT c.nm_id FROM wb_competitor_capture c
            WHERE c.nm_id IN ({cl}) AND c.is_hidden=1 {cond}
        """), iparams)).scalars().all()
        excluded = set(int(x) for x in rows)

        cand = [n for n in norm if n not in excluded]
        assigned, skipped = await self._enqueue_watch(set(cand))
        await self.db.commit()
        return {"requested": len(norm), "assigned": assigned,
                "skipped": skipped, "excluded": len(excluded)}

    async def _enqueue_watch(self, cand: set[int]) -> tuple[int, int]:
        """Карточки → `wb_enrich_queue` (pending, source='watch').

        Возвращает (assigned, skipped). Карточки в работе (`processing`) не
        трогаем — их уже собрало расширение; остальные возвращаем в pending.
        """
        assigned = 0
        skipped = 0
        if not cand:
            return 0, 0
        cl = sorted(n for n in cand if isinstance(n, int) and n > 0)
        # Исключённые из сбора (is_hidden, §19.4) в очередь не возвращаем:
        # /next их всё равно не отдаст, а строка зря висела бы «в очереди».
        if self.company_id is not None and cl:
            hid = await capture_service.excluded_nms(self.db, self.company_id, cl)
            if hid:
                cl = [n for n in cl if n not in hid]
        # что уже есть в очереди: статус
        cur: dict[int, str] = {}
        for i in range(0, len(cl), 400):
            ch = cl[i:i + 400]
            cph, cp = self._inlist("q", ch)
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, status FROM wb_enrich_queue WHERE nm_id IN ({cph})
            """), cp)).mappings().all()
            for r in rows:
                cur[int(r["nm_id"] or 0)] = str(r["status"] or "")
        for n in cl:
            if cur.get(n, "") == "processing":
                skipped += 1
                continue
            if cur.get(n):
                # своя строка уже есть: возвращаем её в pending и помечаем
                # источником watch (в общей куче она больше не числится)
                await self.db.execute(text("""
                    UPDATE wb_enrich_queue
                    SET status='pending', source='watch', requested_at=NOW(),
                        claimed_at=NULL, company_id=COALESCE(company_id, :cid)
                    WHERE nm_id=:n
                """), {"n": n, "cid": self.company_id})
            else:
                await self.db.execute(text("""
                    INSERT INTO wb_enrich_queue
                      (nm_id, company_id, status, source, requested_at)
                    VALUES (:n, :cid, 'pending', 'watch', NOW())
                    ON DUPLICATE KEY UPDATE
                      status='pending', source='watch', requested_at=NOW(),
                      claimed_at=NULL, company_id=COALESCE(company_id, :cid)
                """), {"n": n, "cid": self.company_id})
            assigned += 1
        return assigned, skipped

    # ------------------------------------------------- сбор карточек (enrich)

    async def collect_cards(self, date_from: str, date_to: str, mode: str,
                            phrases: list[str] | None = None, top: int = 40,
                            card_nm: int = 0, rank_by: str = "orders",
                            queries_n: int = 0) -> dict:
        """Карточки SEO-мониторинга → очередь enrich (`wb_enrich_queue`, source='watch').

        mode:
        - `changed` — карточки из событий матрицы: новые в выдаче и сдвиги цены.
                      Карточки, чей контент собран не раньше старого захода
                      (флаг `fresh` события), пропускаются — пересбор ничего
                      не даст;
        - `stale`   — карточки, чей контент старше `watch_card_stale_days` ИЛИ его
                      нет: пул = ТОП-`top` последнего захода каждой фразы;
        - `missing` — только карточки БЕЗ описания (контент не собирали ни разу);
                      пул тот же ТОП-`top`.

        «Контент есть» = описание не короче 50 символов (см. `DESC_MIN_LEN`).
        Лёгкая строка из наблюдения выдачи (цена/рейтинг/превью, без описания)
        контентом не считается.

        `phrases` — отмеченные в матрице фразы: если заданы, пул собирается только
        по ним; иначе — весь watch set (как у «Пересобрать выдачу»).

        Свои карточки тоже собираем: менеджеру нужны их бэджи и цены из выдачи,
        а контент нашей карточки в `wb_competitor_details` — общий кэш по nm_id.
        Очередь помечается `source='watch'`, чтобы расширение брало её отдельным
        режимом («SEO-мониторинг»), а не в общей куче конкурентов.
        """
        st = await self.settings()
        mode = (mode or "").strip().lower()
        if mode not in ("changed", "stale", "missing"):
            raise ValueError("mode must be 'changed', 'stale' or 'missing'")
        top = max(1, min(int(top or 40), 100))
        cand: set[int] = set()
        phrases_used: list[str] = []

        if mode == "changed":
            # события матрицы: «новые в выдаче» + «сдвиги цены». Карточки, чей
            # контент собрали не раньше старого захода (fresh=true — флаг
            # считает матрица), уже отражают текущее состояние выдачи — их не
            # трогаем, иначе одна и та же карточка вставала в очередь на каждый
            # клик (2026-10-25: «собрал, и снова там 21»).
            m = await self.matrix(date_from, date_to, card_nm, rank_by, queries_n)
            for it in m["items"]:
                for n in it["new_items"]:
                    if not n.get("fresh"):
                        cand.add(int(n["nm_id"] or 0))
                for mv in it["price_moves"]:
                    if not mv.get("fresh"):
                        cand.add(int(mv["nm_id"] or 0))
        else:
            # «устаревшие»/«отсутствующие»: ТОП-top карточек последнего захода каждой фразы
            sel = [p for p in dict.fromkeys(
                _norm_phrase(x) for x in (phrases or []) if _norm_phrase(x))]
            if sel:
                phrases_used = sel
            else:
                ws = await self.watch_set(date_from, card_nm=card_nm,
                                          rank_by=rank_by, queries_n=queries_n,
                                          date_to=date_to)
                limit_phrases = max(1, int(st.get("phrases_limit") or 40))
                phrases_used = [p["phrase"] for p in ws["phrases"]][:limit_phrases]
            if not phrases_used:
                return {"mode": mode, "requested": 0, "assigned": 0, "skipped": 0,
                        "candidates": 0, "top": top, "phrases_cnt": 0,
                        "stale_days": st["card_stale_days"]}
            stamps_map = await self._slice_stamps(phrases_used, 1)
            # top режем прямо в SQL (p.position BETWEEN 1 AND top) — не выгружаем лишнее
            slices = await self._slice_items(
                phrases_used, sorted({sl[0] for sl in stamps_map.values() if sl}), top)
            for ph in phrases_used:
                sl = stamps_map.get(ph, [])
                if not sl:
                    continue
                for it in slices.get((ph, sl[0]), []):
                    if int(it["position"] or 999) <= top:
                        cand.add(int(it["nm_id"] or 0))

        cand = {n for n in cand if n > 0}
        skipped = 0
        if mode in ("stale", "missing") and cand:
            # «контента нет» = описание не собрано (пустая лёгкая строка из
            # наблюдения выдачи описания не содержит — это не контент).
            # «устарел» = описание есть, но полный сбор старше порога компании.
            cutoff = (date.today() - timedelta(days=int(st["card_stale_days"]))).isoformat()
            state = await self._content_state(sorted(cand))
            if mode == "stale":
                # берём тех, у кого контента нет ИЛИ он старше порога
                fresh = {n for n in cand
                         if (state.get(n) or (False, "", ""))[0]
                         and _content_at(state.get(n)) >= cutoff}
                skipped += len(fresh)
                cand -= fresh
            else:
                # missing: только те, у кого описания нет вовсе
                have = {n for n in cand if (state.get(n) or (False, "", ""))[0]}
                skipped += len(have)
                cand -= have

        assigned, skipped_q = await self._enqueue_watch(cand)
        skipped += skipped_q
        _cache_drop_company(self.company_id)
        await self.db.commit()
        return {"mode": mode, "requested": len(cand) + skipped, "assigned": assigned,
                "skipped": skipped, "candidates": len(cand), "top": top,
                "phrases_cnt": len(phrases_used),
                "stale_days": st["card_stale_days"]}


def _is_watch_phrase(phrase: str) -> bool:
    """Фраза годится для мониторинга?

    Отсекаем:
    - без слов («264750923», «1380504209» — это артикулы/номера, а не запросы);
    - из одного слова («календарь» — слишком общо, выдача не про наш товар).

    Считаем слова через буквы/цифры: «календарь садовода огородника 2027» — 4 слова,
    «чехол iphone 15 pro max» — 5; «2027 лунный календарь садовода» — 4.
    """
    words = [w for w in str(phrase or "").split() if w]
    if len(words) < 2:
        return False
    # хотя бы одно слово должно содержать букву (кириллицу/латиницу)
    return any(any(ch.isalpha() for ch in w) for w in words)


def _json_list(raw) -> list:
    """JSON-колонка (badges) -> список. MySQL отдаёт строку."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            v = json.loads(raw)
        except (ValueError, TypeError):
            return []
        return v if isinstance(v, list) else []
    return []


def _d(v) -> str:
    """DATE/DATETIME -> 'YYYY-MM-DD'."""
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v)[:10]


def _content_at(state) -> str:
    """Состояние контента (`_content_state`) -> дата контента 'YYYY-MM-DD'.

    Полный сбор (`full_collected_at`), иначе первый сбор (`first_collected_at`) —
    для строк, собранных до миграции 20261021. `collected_at` не берём: его
    двигает пассивное наблюдение выдачи.
    """
    if not state:
        return ""
    full_at = state[1] if len(state) > 1 else ""
    first_at = state[2] if len(state) > 2 else ""
    return full_at or first_at


def _stamp_time(stamp: str) -> str:
    """Метка захода 20261022_131023 -> «13:10» (как в отчёте «Выдача WB»)."""
    s = str(stamp or "")
    if len(s) >= 15 and s[8] == "_":
        return s[9:11] + ":" + s[11:13]
    return ""
