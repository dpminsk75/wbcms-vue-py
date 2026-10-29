#!/usr/bin/env python3
"""Замер «массы отзывов»: сколько отзывов пишут за неделю/месяц.

Зачем: перед тем как строить фичу «ИИ-разбор отзывов -> рекомендации по карточке
и по товару», нужно понять, есть ли вообще масса отзывов, на которой ИИ что-то
найдёт. Если отзывов 20 в месяц на 1000 карточек — фичу можно не делать, а
основным сигналом взять возвраты/брак из detail_by_period.

Только SELECT. Никаких DML, никаких изменений схемы.

Что меряет:
  A. Объём таблиц (information_schema) + индексы wb_feedbacks/detail_by_period/wbcards
  B. Отзывы по месяцам: всего / негатив (оценка <= 3) / с заполненным «cons» /
     от реальных покупок (f_cost > 0 или is_pay > 0) / средняя оценка /
     сколько разных карточек
  C. Отзывы по неделям — «масса в неделю»
  D. Карточки с жалобами (оценка <= 3 или заполнен «cons») + распределение
     «1 / 2 / 3+ жалоб» = знаменатель отбора для ИИ
  E. Покрытие: карточек компании / из них с отзывами / %
  F. Возвраты/продажи/штрафы — из КУБА agg_sales_daily_sku (sales_qty,
     returns_qty, penalty_sum): по месяцам, ТОП по количеству возвратов,
     ТОП по % возвратов (отсев --min-sales), корзины % возвратов,
     ТОП карточек по штрафам
  G. Брак И ШТРАФЫ — из detail_by_period, ТОЛЬКО за узкий срез
     (--defects-months, по умолчанию 3 мес):
       G1/G2 — брак по карточкам + словарь doc_type/bonus_type
       G3 — ШТРАФЫ РАЗБОР ПО ПРИЧИНАМ (bonus_type_name + supplier_oper_name)
       G4 — ТОП карточек по штрафам
  H. Тексты жалоб (выборка) — глазами проверить, есть ли пригодный сигнал
  I. EXPLAIN всех запросов + оценка просмотренных строк (отдельно по
     «дешёвым» и по тяжёлым)

Важно про фильтр «реальная покупка»:
  f_cost/is_pay заполнены у единиц отзывов (~0.3% в замере 2026-10-27),
  поэтому как обязательный критерий они отсекают почти всю массу.
  По умолчанию фильтр ВЫКЛЮЧЕН; включить — --require-bought.

Почему возвраты из куба, а не из detail_by_period:
  detail_by_period — тяжёлая таблица (≈881k строк, 730MB + 1GB индексов);
  полный год по компании — это ~440k строк на КАЖДЫЙ запрос. Возвраты и
  штрафы уже посчитаны в кубе agg_sales_daily_sku (его строит воркер
  wbcms-aggregate), поэтому читаем куб, а большую таблицу трогаем только
  ради брака/причин штрафов и только узким срезом.
  В запросах к detail_by_period стоит FORCE INDEX (idx_company_rr_dt):
  без него оптимизатор берёт idx_company_nm_sale и сканирует ВСЕ строки
  компании (440k) независимо от периода.

Запуск (на сервере, из корня /var/www/wb/wbcms-py):
  .venv/bin/python backend/scripts/feedback_volume_probe.py --company-id 1 --explain
  .venv/bin/python backend/scripts/feedback_volume_probe.py --company-id 1 --months 6
  .venv/bin/python backend/scripts/feedback_volume_probe.py --company-id 1 --months 12
  .venv/bin/python backend/scripts/feedback_volume_probe.py --company-id 1 \
      --date-from 2026-04-01 --date-to 2026-09-30
  .venv/bin/python backend/scripts/feedback_volume_probe.py --all-companies --months 12
  .venv/bin/python backend/scripts/feedback_volume_probe.py --company-id 1 \
      --defects-months 1 --min-sales 5
  .venv/bin/python backend/scripts/feedback_volume_probe.py --company-id 1 --require-bought

Период задаётся либо --months N (глубина в месяцах от сегодня), либо явным
--date-from/--date-to (произвольный диапазон, в т.ч. за год и больше).
--weeks N ограничивает недельный срез; при явном --date-from недельный срез
берёт тот же период, что и месячный (чтобы «за год по неделям»).

Безопасность:
  * SESSION_LIMITS из AGENTS.md (max_execution_time, temptable_max_ram, ...);
  * LIMIT везде, срез ограничен --months / --defects-months;
  * лог времени и числа строк каждого запроса;
  * предупреждение, если оценка просмотренных строк > 500 000 (дешёвые)
    или > 300 000 (detail_by_period);
  * раздел G пропускается целиком, если оценка detail_by_period > 300 000
    (--force — чтобы выполнить);
  * если wb_feedbacks большой и нет индекса с company_id первым —
    запросы B/C/D пропускаются, пока не задан --force;
  * --explain печатает план и НИЧЕГО не выполняет (кроме information_schema).
"""
import argparse
import asyncio
import pathlib
import re
import sys
import time
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:  # чтобы кириллица не ломалась в консоли Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from sqlalchemy import bindparam, text  # noqa: E402

from backend.database import get_session  # noqa: E402

SESSION_LIMITS = [
    "SET SESSION max_execution_time = 15000",
    "SET SESSION temptable_max_ram = 67108864",
    "SET SESSION tmp_table_size = 33554432",
    "SET SESSION max_heap_table_size = 33554432",
    "SET SESSION sort_buffer_size = 1048576",
    "SET SESSION join_buffer_size = 1048576",
    "SET SESSION read_rnd_buffer_size = 524288",
    "SET SESSION lock_wait_timeout = 5",
    "SET SESSION innodb_lock_wait_timeout = 5",
    "SET SESSION sql_safe_updates = 1",
]

TABLES = ("wb_feedbacks", "detail_by_period", "wbcards", "wb_order",
          "product_wb_card", "wb_sales", "agg_sales_daily_sku", "agg_daily_summary")

# «Есть жалоба»: оценка <= 3 ИЛИ заполнен pros/cons
CONS_EXPR = "(f.cons IS NOT NULL AND f.cons <> '' AND f.cons <> 'null')"
# «Реальная покупка» — иначе в отзыве может быть школа/мусор
BOUGHT_EXPR = "(f.f_cost > 0 OR f.is_pay > 0)"

# Фильтр по компании: либо конкретная (с индексом), либо все компании разом
CID_WHERE_FB = "f.company_id = :cid"
CID_WHERE_ALL_FB = "1=1"
CID_WHERE_DBP = "d.company_id = :cid"
CID_WHERE_ALL_DBP = "1=1"
# wbcards без алиаса
CID_WHERE_CARDS = "company_id = :cid"
CID_WHERE_ALL_CARDS = "1=1"
# куб agg_sales_daily_sku (алиас s)
CID_WHERE_CUBE = "s.company_id = :cid"
CID_WHERE_ALL_CUBE = "1=1"

SQL_BY_MONTH = """
SELECT DATE_FORMAT(f.createdDate, '%Y-%m') AS ym,
       COUNT(*) AS cnt,
       SUM(CASE WHEN f.productValuation <= 3 THEN 1 ELSE 0 END) AS neg_cnt,
       SUM(CASE WHEN {cons} THEN 1 ELSE 0 END) AS cons_cnt,
       SUM(CASE WHEN {bought} THEN 1 ELSE 0 END) AS bought_cnt,
       ROUND(AVG(f.productValuation), 2) AS avg_rating,
       COUNT(DISTINCT f.nmID) AS cards_cnt
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
GROUP BY DATE_FORMAT(f.createdDate, '%Y-%m')
ORDER BY ym
"""

SQL_BY_WEEK = """
SELECT YEARWEEK(f.createdDate, 3) AS yw,
       DATE_FORMAT(MIN(f.createdDate), '%Y-%m-%d') AS week_start,
       COUNT(*) AS cnt,
       SUM(CASE WHEN f.productValuation <= 3 THEN 1 ELSE 0 END) AS neg_cnt,
       SUM(CASE WHEN {cons} THEN 1 ELSE 0 END) AS cons_cnt,
       SUM(CASE WHEN {bought} THEN 1 ELSE 0 END) AS bought_cnt,
       COUNT(DISTINCT f.nmID) AS cards_cnt
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
GROUP BY YEARWEEK(f.createdDate, 3)
ORDER BY yw
"""

SQL_CANDIDATES = """
SELECT f.nmID AS nm_id,
       COUNT(*) AS cnt,
       SUM(CASE WHEN f.productValuation <= 3 THEN 1 ELSE 0 END) AS neg_cnt,
       SUM(CASE WHEN {cons} THEN 1 ELSE 0 END) AS cons_cnt,
       ROUND(AVG(f.productValuation), 2) AS avg_rating,
       MAX(f.createdDate) AS last_at
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
  AND (f.productValuation <= 3 OR {cons})
  {bought_filter}
GROUP BY f.nmID
ORDER BY cnt DESC
LIMIT :lim
"""

# --- СИГНАЛ: карточки с жалобами (без фильтра «реальная покупка») ---
# f_cost/is_pay заполнены у единиц отзывов — как обязательный критерий они
# отсекают 99% масс. Оставляем опционально (--require-bought).

SQL_SIGNAL_CARDS = """
SELECT f.nmID AS nm_id,
       COUNT(*) AS cnt,
       SUM(CASE WHEN f.productValuation <= 3 THEN 1 ELSE 0 END) AS neg_cnt,
       SUM(CASE WHEN {cons} THEN 1 ELSE 0 END) AS cons_cnt,
       ROUND(AVG(f.productValuation), 2) AS avg_rating,
       COUNT(DISTINCT DATE(f.createdDate)) AS days_cnt,
       MAX(f.createdDate) AS last_at
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
  AND (f.productValuation <= 3 OR {cons})
GROUP BY f.nmID
ORDER BY cnt DESC
LIMIT :lim
"""

# Распределение: сколько карточек с 1 / 2 / 3+ жалобами (знаменатель отбора)
SQL_SIGNAL_DISTRIBUTION = """
SELECT SUM(CASE WHEN cnt >= 3 THEN 1 ELSE 0 END) AS c3plus,
       SUM(CASE WHEN cnt = 2 THEN 1 ELSE 0 END) AS c2,
       SUM(CASE WHEN cnt = 1 THEN 1 ELSE 0 END) AS c1,
       COUNT(*) AS cards_cnt
FROM (
    SELECT f.nmID AS nm_id, COUNT(*) AS cnt
    FROM wb_feedbacks f
    WHERE {cid_where}
      AND f.createdDate BETWEEN :d1 AND :d2
      AND (f.productValuation <= 3 OR {cons})
    GROUP BY f.nmID
) AS t
"""

# Выборка текстов жалоб — чтобы глазами понять, есть ли пригодный сигнал
SQL_SAMPLE_COMPLAINTS = """
SELECT f.nmID AS nm_id,
       f.productValuation AS rating,
       f.text AS body,
       f.pros AS pros,
       f.cons AS cons,
       f.matchingSize AS size,
       f.color AS color,
       f.f_cost AS f_cost,
       f.is_pay AS is_pay,
       f.createdDate AS created_at,
       f.bables AS bables
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
  AND (f.productValuation <= 3 OR {cons})
ORDER BY f.createdDate DESC
LIMIT :lim
"""

SQL_CARDS_TOTAL = """
SELECT COUNT(*) AS rows_cnt, COUNT(DISTINCT nmID) AS nm_cnt
FROM wbcards WHERE {cid_where}
"""

SQL_CARDS_WITH_FB = """
SELECT COUNT(DISTINCT f.nmID) AS nm_cnt
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
"""

# --- detail_by_period: ТОЛЬКО брак, узкий срез (--defects-months) ---
# Возвраты/штрафы берём из куба agg_sales_daily_sku, большую таблицу не трогаем.
# Один проход группировки по карточке; словарь — одним проходом (doc+bonus).

SQL_DBP_DEFECTS_TOP = """
SELECT d.nm_id AS nm_id,
       SUM(CASE WHEN d.bonus_type_name LIKE '%Брак%' THEN 1 ELSE 0 END) AS defect_cnt,
       SUM(CASE WHEN d.doc_type_name = 'Возврат' THEN d.quantity ELSE 0 END) AS returns_qty
FROM detail_by_period d FORCE INDEX (idx_company_rr_dt)
WHERE {cid_where}
  AND d.rr_dt BETWEEN :d1 AND :d2
  AND d.nm_id > 0
GROUP BY d.nm_id
ORDER BY defect_cnt DESC, returns_qty DESC
LIMIT :lim
"""

SQL_DBP_VOCAB = """
SELECT COALESCE(d.doc_type_name, '—') AS doc_type,
       COALESCE(d.bonus_type_name, '—') AS bonus_type,
       COUNT(*) AS cnt
FROM detail_by_period d FORCE INDEX (idx_company_rr_dt)
WHERE {cid_where} AND d.rr_dt BETWEEN :d1 AND :d2
GROUP BY COALESCE(d.doc_type_name, '—'), COALESCE(d.bonus_type_name, '—')
ORDER BY cnt DESC
LIMIT :lim
"""

# --- ШТРАФЫ WB: разбор по причинам -------------------------------------
# Штраф = строка с penalty <> 0. Причина — в bonus_type_name
# («Отгрузка не в срок», «Ненадлежащая упаковка», «Неверное описание»...),
# вид операции — в supplier_oper_name («Продажа», «Возврат», «Штраф»).
# FORCE INDEX обязателен: без него оптимизатор берёт idx_company_nm_sale
# и сканирует ВСЕ строки компании (440k) независимо от периода.

SQL_DBP_PENALTY_REASONS = """
SELECT COALESCE(d.bonus_type_name, '—') AS bonus_type,
       COALESCE(d.supplier_oper_name, '—') AS oper,
       COUNT(*) AS cnt,
       ROUND(SUM(d.penalty), 2) AS penalty_sum,
       COUNT(DISTINCT d.nm_id) AS cards_cnt
FROM detail_by_period d FORCE INDEX (idx_company_rr_dt)
WHERE {cid_where}
  AND d.rr_dt BETWEEN :d1 AND :d2
  AND d.penalty <> 0
GROUP BY COALESCE(d.bonus_type_name, '—'), COALESCE(d.supplier_oper_name, '—')
ORDER BY penalty_sum DESC
LIMIT :lim
"""

SQL_DBP_PENALTY_TOP = """
SELECT d.nm_id AS nm_id,
       COALESCE(d.bonus_type_name, '—') AS bonus_type,
       COUNT(*) AS cnt,
       ROUND(SUM(d.penalty), 2) AS penalty_sum
FROM detail_by_period d FORCE INDEX (idx_company_rr_dt)
WHERE {cid_where}
  AND d.rr_dt BETWEEN :d1 AND :d2
  AND d.penalty <> 0
  AND d.nm_id > 0
GROUP BY d.nm_id, COALESCE(d.bonus_type_name, '—')
ORDER BY penalty_sum DESC
LIMIT :lim
"""

# --- КУБЫ (OLAP): возвраты/продажи/штрафы без сканирования detail_by_period ---
# agg_sales_daily_sku: company_id, sale_date, nmID, subject_name, brand_name,
#                       sales_qty, returns_qty, retail_amount_sum,
#                       ppvz_for_pay_sum, delivery_rub_sum, penalty_sum
# sale_date — DATE (не datetime), поэтому отдельные плейсхолдеры :sd1/:sd2.

SQL_CUBE_FRESH = """
SELECT MAX(s.sale_date) AS max_date, COUNT(*) AS rows_cnt
FROM agg_sales_daily_sku s WHERE {cid_where}
"""

SQL_CUBE_BY_MONTH = """
SELECT DATE_FORMAT(s.sale_date, '%Y-%m') AS ym,
       SUM(s.sales_qty) AS sales_qty,
       SUM(s.returns_qty) AS returns_qty,
       ROUND(SUM(s.returns_qty) / NULLIF(SUM(s.sales_qty), 0) * 100, 1) AS returns_pct,
       ROUND(SUM(s.penalty_sum), 2) AS penalty_sum,
       COUNT(DISTINCT s.nmID) AS cards_cnt
FROM agg_sales_daily_sku s
WHERE {cid_where}
  AND s.sale_date BETWEEN :sd1 AND :sd2
GROUP BY DATE_FORMAT(s.sale_date, '%Y-%m')
ORDER BY ym
"""

SQL_CUBE_TOP_RETURNS = """
SELECT s.nmID AS nm_id,
       SUM(s.sales_qty) AS sales_qty,
       SUM(s.returns_qty) AS returns_qty,
       ROUND(SUM(s.returns_qty) / NULLIF(SUM(s.sales_qty), 0) * 100, 1) AS returns_pct,
       ROUND(SUM(s.penalty_sum), 2) AS penalty_sum
FROM agg_sales_daily_sku s
WHERE {cid_where}
  AND s.sale_date BETWEEN :sd1 AND :sd2
  AND s.nmID > 0
GROUP BY s.nmID
ORDER BY returns_qty DESC
LIMIT :lim
"""

# Проблемные товары: высокий % возвратов при достаточных продажах
SQL_CUBE_TOP_RATE = """
SELECT s.nmID AS nm_id,
       SUM(s.sales_qty) AS sales_qty,
       SUM(s.returns_qty) AS returns_qty,
       ROUND(SUM(s.returns_qty) / NULLIF(SUM(s.sales_qty), 0) * 100, 1) AS returns_pct,
       ROUND(SUM(s.penalty_sum), 2) AS penalty_sum
FROM agg_sales_daily_sku s
WHERE {cid_where}
  AND s.sale_date BETWEEN :sd1 AND :sd2
  AND s.nmID > 0
GROUP BY s.nmID
HAVING SUM(s.sales_qty) >= :min_sales
ORDER BY returns_pct DESC
LIMIT :lim
"""

# Сколько карточек с % возвратов выше порога (сигнал проблемы с товаром)
SQL_CUBE_RATE_BUCKETS = """
SELECT SUM(CASE WHEN returns_pct >= 20 THEN 1 ELSE 0 END) AS ge20,
       SUM(CASE WHEN returns_pct >= 10 AND returns_pct < 20 THEN 1 ELSE 0 END) AS ge10,
       SUM(CASE WHEN returns_pct >= 5 AND returns_pct < 10 THEN 1 ELSE 0 END) AS ge5,
       COUNT(*) AS cards_cnt
FROM (
    SELECT s.nmID AS nm_id,
           SUM(s.returns_qty) / NULLIF(SUM(s.sales_qty), 0) * 100 AS returns_pct
    FROM agg_sales_daily_sku s
    WHERE {cid_where}
      AND s.sale_date BETWEEN :sd1 AND :sd2
      AND s.nmID > 0
    GROUP BY s.nmID
    HAVING SUM(s.sales_qty) >= :min_sales
) AS t
"""

# Денежный сигнал: карточки со штрафами WB (из куба)
SQL_CUBE_PENALTY_TOP = """
SELECT s.nmID AS nm_id,
       ROUND(SUM(s.penalty_sum), 2) AS penalty_sum,
       SUM(s.sales_qty) AS sales_qty,
       SUM(s.returns_qty) AS returns_qty
FROM agg_sales_daily_sku s
WHERE {cid_where}
  AND s.sale_date BETWEEN :sd1 AND :sd2
  AND s.nmID > 0
GROUP BY s.nmID
HAVING SUM(s.penalty_sum) > 0
ORDER BY penalty_sum DESC
LIMIT :lim
"""

# Карточки по списку PK (wbcards без индекса по company_id — JOIN на большой
# таблице запрещён, поэтому только IN-список, как в sku_resolver).
SQL_CARD_TITLES = """
SELECT nmID AS nm_id, title, vendorCode, brand, subjectName
FROM wbcards WHERE nmID IN :nms
"""

# Покрытие сигналов: сколько отзывов с текстом / тегами / pros / cons.
# Проверяет гипотезу «cons = '[]'» (пустой JSON-массив вместо NULL):
# из-за него фильтр «cons заполнен» считал почти все отзывы жалобами.
SQL_COVERAGE = """
SELECT f.productValuation AS rating,
       COUNT(*) AS cnt,
       SUM(CASE WHEN f.text IS NOT NULL AND f.text <> '' THEN 1 ELSE 0 END) AS with_text,
       SUM(CASE WHEN f.bables IS NOT NULL AND f.bables NOT IN ('','null','[]') THEN 1 ELSE 0 END) AS with_tags,
       SUM(CASE WHEN f.pros IS NOT NULL AND f.pros NOT IN ('','null','[]') THEN 1 ELSE 0 END) AS with_pros,
       SUM(CASE WHEN f.cons IS NOT NULL AND f.cons NOT IN ('','null','[]') THEN 1 ELSE 0 END) AS cons_real,
       SUM(CASE WHEN f.cons IS NOT NULL AND f.cons <> '' AND f.cons <> 'null' THEN 1 ELSE 0 END) AS cons_old
FROM wb_feedbacks f
WHERE {cid_where}
  AND f.createdDate BETWEEN :d1 AND :d2
GROUP BY f.productValuation
ORDER BY cnt DESC
"""


def _fb_sql(tmpl: str, all_companies: bool, require_bought: bool = False) -> str:
    """Подставить шаблон запроса по wb_feedbacks (алиас f).

    require_bought — добавлять ли фильтр «реальная покупка» (f_cost/is_pay).
    По умолчанию выключен: в текущих данных он заполнен у 0.3% отзывов и
    отсекает почти всю массу.
    """
    bought_filter = f"AND {BOUGHT_EXPR}" if require_bought else ""
    return tmpl.format(
        cons=CONS_EXPR, bought=BOUGHT_EXPR, bought_filter=bought_filter,
        cid_where=CID_WHERE_ALL_FB if all_companies else CID_WHERE_FB)


def _cards_sql(tmpl: str, all_companies: bool) -> str:
    """Подставить шаблон запроса по wbcards (без алиаса)."""
    return tmpl.format(
        cid_where=CID_WHERE_ALL_CARDS if all_companies else CID_WHERE_CARDS)


def _cover_sql(tmpl: str, all_companies: bool) -> str:
    """Подставить шаблон запроса по wb_feedbacks (алиас f)."""
    return tmpl.format(
        cid_where=CID_WHERE_ALL_FB if all_companies else CID_WHERE_FB)


def _cube_sql(tmpl: str, all_companies: bool) -> str:
    """Подставить шаблон запроса по кубу agg_sales_daily_sku (алиас s)."""
    return tmpl.format(
        cid_where=CID_WHERE_ALL_CUBE if all_companies else CID_WHERE_CUBE)


def _dbp_sql(tmpl: str, all_companies: bool, dcol: str = "rr_dt") -> str:
    """Подставить шаблон запроса по detail_by_period (алиас d)."""
    return tmpl.format(
        cid_where=CID_WHERE_ALL_DBP if all_companies else CID_WHERE_DBP, dcol=dcol)


def _h(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def _used_params(sql: str, params: dict) -> dict:
    """Оставить только те параметры, что реально есть в тексте запроса.

    Иначе в режиме --all-companies (нет :cid) или для запросов без :lim
    драйверу уходят лишние ключи.
    """
    used = set(re.findall(r":(\w+)", sql))
    return {k: v for k, v in params.items() if k in used}


async def _run(db, label: str, sql: str, params: dict) -> list:
    """Выполнить запрос, напечатать время и число строк."""
    t0 = time.perf_counter()
    rows = (await db.execute(text(sql), _used_params(sql, params))).mappings().all()
    ms = (time.perf_counter() - t0) * 1000
    print(f"  [{label}] строк={len(rows)}  время={ms:.0f} мс")
    return [dict(r) for r in rows]


async def _explain(db, label: str, sql: str, params: dict) -> int:
    """EXPLAIN запроса, печать плана, вернуть оценку просмотренных строк."""
    print("-" * 100)
    print(label)
    print("  " + " ".join(sql.split()))
    pr = _used_params(sql, params)
    try:
        plan = (await db.execute(text("EXPLAIN " + sql), pr)).mappings().all()
    except Exception as e:
        print(f"  EXPLAIN FAILED: {type(e).__name__}: {e}")
        return 0
    est = 0
    for p in plan:
        try:
            est += int(p.get("rows") or 0)
        except (TypeError, ValueError):
            pass
        print(f"  type={p.get('type')} key={p.get('key')} rows≈{p.get('rows')} "
              f"extra={p.get('Extra')}")
    print(f"  оценка просмотренных строк: {est}")
    return est


def _fb_index_state(idx_rows: list) -> tuple:
    """(есть индекс с company_id первым, есть ли (company_id, createdDate)).

    Первого достаточно, чтобы не было full scan по wb_feedbacks: оптимизатор
    берёт idx_company_feedbacks (company_id, nmID) и дофильтровывает по дате.
    Второй — идеал, но не обязателен: таблица маленькая.
    """
    has_company = False
    has_company_date = False
    for r in idx_rows:
        if str(r.get("tbl") or "") != "wb_feedbacks":
            continue
        cols = [c.strip() for c in str(r.get("cols") or "").split(",")]
        if cols and cols[0] == "company_id":
            has_company = True
            if "createdDate" in cols:
                has_company_date = True
    return has_company, has_company_date


def _verdict(month_rows: list, week_rows: list, cand: list,
             total_cards: int, cards_with_fb: int,
             cube_month_rows: list, buckets: dict,
             signal_cards: int = 0) -> list:
    """Итоговая сводка + решение по объёму."""
    out = []
    months = max(1, len(month_rows))
    total_fb = sum(int(r.get("cnt") or 0) for r in month_rows)
    total_neg = sum(int(r.get("neg_cnt") or 0) for r in month_rows)
    total_cons = sum(int(r.get("cons_cnt") or 0) for r in month_rows)
    total_bought = sum(int(r.get("bought_cnt") or 0) for r in month_rows)
    fb_per_month = total_fb / months
    weeks = max(1, len(week_rows))
    fb_per_week = (sum(int(r.get("cnt") or 0) for r in week_rows) / weeks) if week_rows else 0

    ret_total = sum(int(r.get("returns_qty") or 0) for r in cube_month_rows)
    sales_total = sum(int(r.get("sales_qty") or 0) for r in cube_month_rows)
    penalty_total = sum(float(r.get("penalty_sum") or 0) for r in cube_month_rows)
    cmonths = max(1, len(cube_month_rows))
    ret_per_month = ret_total / cmonths
    ret_pct = (ret_total / sales_total * 100) if sales_total else 0

    out.append("ОТЗЫВЫ")
    out.append(f"  отзывов за период:            {total_fb}")
    out.append(f"  в среднем в месяц:            {fb_per_month:.1f}")
    out.append(f"  в среднем в неделю:           {fb_per_week:.1f}")
    out.append(f"  негативных (оценка <= 3):      {total_neg}  ({total_neg / max(1, total_fb) * 100:.0f}%)")
    out.append(f"  с заполненным «cons»:         {total_cons}  ({total_cons / max(1, total_fb) * 100:.0f}%)")
    out.append(f"  от реальных покупок:           {total_bought}  ({total_bought / max(1, total_fb) * 100:.0f}%)")
    out.append(f"  карточек с отзывами:           {cards_with_fb} из {total_cards} "
               f"({(cards_with_fb / total_cards * 100) if total_cards else 0:.1f}%)")
    out.append(f"  карточек с жалобами:            {signal_cards}")
    out.append(f"  карточек в ТОПе (жалоб):        {len(cand)}")
    out.append("")
    out.append("ВОЗВРАТЫ (куб agg_sales_daily_sku)")
    out.append(f"  продаж за период:              {sales_total}")
    out.append(f"  возвратов за период:           {ret_total}  ({ret_pct:.1f}% от продаж)")
    out.append(f"  возвратов в среднем в месяц:   {ret_per_month:.1f}")
    out.append(f"  штрафов за период:             {penalty_total:.0f} ₽")
    if buckets:
        out.append(f"  карточек с возвратами >=20%:   {int(buckets.get('ge20') or 0)}")
        out.append(f"  карточек с возвратами 10-20%:  {int(buckets.get('ge10') or 0)}")
        out.append(f"  карточек с возвратами 5-10%:   {int(buckets.get('ge5') or 0)}")
        out.append(f"  всего карточек в анализе:      {int(buckets.get('cards_cnt') or 0)}")
    out.append("")

    signal = total_neg + total_cons
    bad_cards = int((buckets or {}).get("ge20") or 0) + int((buckets or {}).get("ge10") or 0)
    if fb_per_month >= 100 and len(cand) >= 15:
        out.append("  ВЕРДИКТ: массы отзывов ХВАТАЕТ. Период — месяц, отбор карточек по сигналу.")
        out.append("           Фичу «ИИ-разбор отзывов» имеет смысл делать.")
    elif fb_per_month >= 30:
        out.append("  ВЕРДИКТ: масса отзывов пограничная. Считать помесячно, копить инсайты;")
        out.append("           отбор жёсткий (только карточки с негативом).")
    else:
        out.append("  ВЕРДИКТ: отзывы как ОСНОВНОЙ источник НЕ катят (мало).")
        out.append("           Основной сигнал — возвраты (куб) + брак, отзывы — как текст.")
    if signal_cards:
        out.append(f"           Для ИИ пригодно {signal_cards} карточек с жалобами "
                   f"({signal_cards / max(1, total_cards) * 100:.0f}% каталога).")
    if bad_cards:
        out.append(f"           Плюс есть товарный сигнал: {bad_cards} карточек с возвратами >=10% —")
        out.append("           по ним ИИ можно делать блок «что улучшить в товаре».")
    if signal == 0 and total_fb:
        out.append("  ВНИМАНИЕ: нет ни одного негативного отзыва — ИИ нечего анализировать.")
    if total_cards and cards_with_fb and cards_with_fb / total_cards < 0.1:
        out.append(f"  ВНИМАНИЕ: отзывы есть менее чем у 10% карточек "
                   f"({cards_with_fb} из {total_cards}).")
    return out


async def main() -> int:
    ap = argparse.ArgumentParser(
        description="Замер массы отзывов (неделя/месяц) — только SELECT")
    ap.add_argument("--company-id", type=int, default=1,
                    help="id компании (по умолчанию 1)")
    ap.add_argument("--all-companies", action="store_true",
                    help="без фильтра по компании (общая масса по всем карточкам)")
    ap.add_argument("--months", type=int, default=6,
                    help="глубина среза в месяцах от сегодня (по умолчанию 6)")
    ap.add_argument("--defects-months", type=int, default=3,
                    help="глубина среза для detail_by_period (брак). Таблица тяжёлая "
                         "(881k строк) — держим срез узким, по умолчанию 3 мес")
    ap.add_argument("--min-sales", type=int, default=10,
                    help="минимум продаж у карточки, чтобы считать % возвратов "
                         "значимым (по умолчанию 10)")
    ap.add_argument("--weeks", type=int, default=8,
                    help="глубина недельного среза (по умолчанию 8; при явном "
                         "--date-from берётся весь период)")
    ap.add_argument("--limit", type=int, default=30,
                    help="сколько строк в ТОПах (кандидаты/возвраты)")
    ap.add_argument("--date-from", default=None,
                    help="YYYY-MM-DD — начало периода (перекрывает --months)")
    ap.add_argument("--date-to", default=None,
                    help="YYYY-MM-DD — конец периода (по умолчанию сегодня)")
    ap.add_argument("--require-bought", action="store_true",
                    help="отбирать только отзывы реальных покупок (f_cost>0 или "
                         "is_pay>0). ВНИМАНИЕ: в данных заполнено у ~0.3% отзывов, "
                         "фильтр отсекает почти всю массу — по умолчанию выключен")
    ap.add_argument("--explain", action="store_true",
                    help="только EXPLAIN + information_schema, ничего не выполнять")
    ap.add_argument("--force", action="store_true",
                    help="выполнять тяжёлые запросы даже без индекса (company_id, createdDate)")
    args = ap.parse_args()

    all_companies = bool(args.all_companies)
    today = date.today()
    d_to = args.date_to or today.isoformat()
    d_from = args.date_from or (today - timedelta(days=31 * max(1, args.months))).isoformat()

    # Недельный срез: при явном --date-from — тот же период (хотим «за год по неделям»),
    # иначе — последние N недель.
    if args.date_from:
        w_from = d_from
    else:
        w_from = (today - timedelta(days=7 * max(1, args.weeks))).isoformat()

    d1 = f"{d_from} 00:00:00"
    d2 = f"{d_to} 23:59:59"
    w1 = f"{w_from} 00:00:00"

    # Узкий срез для detail_by_period (брак) — большая таблица, 881k строк.
    df_to = d_to
    df_from = (today - timedelta(days=31 * max(1, args.defects_months))).isoformat()
    if args.date_from and args.defects_months >= args.months:
        df_from = d_from
    df1 = f"{df_from} 00:00:00"
    df2 = f"{df_to} 23:59:59"

    lim = max(1, args.limit)
    params = {"cid": args.company_id, "d1": d1, "d2": d2, "lim": lim}
    wparams = {"cid": args.company_id, "d1": w1, "d2": d2, "lim": lim}
    # куб: sale_date — тип DATE, поэтому даты без времени
    cparams = {"cid": args.company_id, "sd1": d_from, "sd2": d_to, "lim": lim,
               "min_sales": max(1, args.min_sales)}
    # detail_by_period (брак) — отдельный узкий срез
    fparams = {"cid": args.company_id, "d1": df1, "d2": df2, "lim": lim}

    scope = "ВСЕ КОМПАНИИ" if all_companies else f"компания {args.company_id}"
    print(f"Срез: {scope}   период: {d_from} … {d_to}   недельный срез: {w_from} … {d_to}")
    print(f"Срез брака (detail_by_period): {df_from} … {df_to}")
    if args.explain:
        print("РЕЖИМ: --explain (запросы НЕ выполняются)")

    async with get_session() as db:
        for stmt in SESSION_LIMITS:
            try:
                await db.execute(text(stmt))
            except Exception:
                pass
        await db.rollback()

        # --- A. объём таблиц -------------------------------------------------
        _h("A. ОБЪЁМ ТАБЛИЦ (information_schema)")
        rows = (await db.execute(text("""
            SELECT table_name AS tbl, table_rows AS tr,
                   ROUND(data_length/1024/1024,1) AS data_mb,
                   ROUND(index_length/1024/1024,1) AS idx_mb
            FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name IN :tbls
            ORDER BY table_rows DESC""").bindparams(
            bindparam("tbls", expanding=True)), {"tbls": tuple(TABLES)})).mappings().all()
        tbl_rows = {}
        for r in rows:
            tbl_rows[str(r["tbl"])] = int(r["tr"] or 0)
            print(f"  {r['tbl']:<26} rows≈{int(r['tr'] or 0):>9}  "
                  f"data={r['data_mb']}MB  idx={r['idx_mb']}MB")

        _h("A2. ИНДЕКСЫ wb_feedbacks / detail_by_period / wbcards")
        idx_rows = (await db.execute(text("""
            SELECT table_name AS tbl, index_name AS idx,
                   GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name IN ('wb_feedbacks','detail_by_period','wbcards',
                                 'wb_sales','wb_order')
            GROUP BY table_name, index_name ORDER BY table_name, index_name"""),
            {})).mappings().all()
        idx_list = [dict(r) for r in idx_rows]
        for r in idx_list:
            print(f"  {r['tbl']:<26} {r['idx']:<38} ({r['cols']})")

        fb_rows = tbl_rows.get("wb_feedbacks", 0)
        has_company_idx, has_company_date = _fb_index_state(idx_list)
        heavy_ok = True
        if not has_company_idx and fb_rows > 200_000:
            heavy_ok = False
            print()
            print(f"  ⚠ wb_feedbacks ≈ {fb_rows} строк и нет индекса с company_id первым")
            print("    → тяжёлые запросы B/C/D пропущены. Нужен индекс, либо --force")
            print("      (--force — на свой страх и риск, срез можно сузить --months).")
        elif not has_company_date:
            print()
            print("  ⚠ на wb_feedbacks нет индекса (company_id, createdDate) —")
            print("    фильтр по компании+дате пойдёт по idx_company_feedbacks + дофильтр.")
            print("    Таблица маленькая, приемлемо; при росте — добавить индекс.")
        if all_companies:
            print("  ⚠ режим --all-companies: сканируется вся таблица, а не срез одной компании.")

        # --- G. EXPLAIN ------------------------------------------------------
        _h("G. EXPLAIN ВСЕХ ЗАПРОСОВ")
        est_total = 0
        est_fb = 0
        est_dbp = 0
        plan_defs = [
            ("B. отзывы по месяцам", _fb_sql(SQL_BY_MONTH, all_companies), params, "fb"),
            ("C. отзывы по неделям", _fb_sql(SQL_BY_WEEK, all_companies), wparams, "fb"),
            ("D. карточки-кандидаты", _fb_sql(SQL_CANDIDATES, all_companies, args.require_bought), params, "fb"),
            ("D2. карточки с жалобами (без фильтра «покупка»)",
             _fb_sql(SQL_SIGNAL_CARDS, all_companies), params, "fb"),
            ("D3. распределение жалоб по карточкам",
             _fb_sql(SQL_SIGNAL_DISTRIBUTION, all_companies), params, "fb"),
            ("D4. выборка текстов жалоб",
             _fb_sql(SQL_SAMPLE_COMPLAINTS, all_companies), params, "fb"),
            ("E1. всего карточек", _cards_sql(SQL_CARDS_TOTAL, all_companies), params, "fb"),
            ("E2. карточек с отзывами", _fb_sql(SQL_CARDS_WITH_FB, all_companies), params, "fb"),
            ("F1. куб: возвраты/продажи/штрафы по месяцам",
             _cube_sql(SQL_CUBE_BY_MONTH, all_companies), cparams, "fb"),
            ("F2. куб: ТОП карточек по возвратам",
             _cube_sql(SQL_CUBE_TOP_RETURNS, all_companies), cparams, "fb"),
            ("F3. куб: ТОП карточек по % возвратов",
             _cube_sql(SQL_CUBE_TOP_RATE, all_companies), cparams, "fb"),
            ("F4. куб: корзины % возвратов",
             _cube_sql(SQL_CUBE_RATE_BUCKETS, all_companies), cparams, "fb"),
            ("F5. куб: ТОП карточек по штрафам",
             _cube_sql(SQL_CUBE_PENALTY_TOP, all_companies), cparams, "fb"),
            ("G1. брак: ТОП карточек (detail_by_period, узкий срез)",
             _dbp_sql(SQL_DBP_DEFECTS_TOP, all_companies), fparams, "dbp"),
            ("G2. брак: словарь doc_type/bonus_type (detail_by_period, узкий срез)",
             _dbp_sql(SQL_DBP_VOCAB, all_companies), fparams, "dbp"),
            ("G3. ШТРАФЫ: разбор по причинам",
             _dbp_sql(SQL_DBP_PENALTY_REASONS, all_companies), fparams, "dbp"),
            ("G4. ШТРАФЫ: ТОП карточек",
             _dbp_sql(SQL_DBP_PENALTY_TOP, all_companies), fparams, "dbp"),
        ]
        for label, sql, pr, kind in plan_defs:
            est = await _explain(db, label, sql, pr)
            est_total += est
            if kind == "fb":
                est_fb += est
            else:
                est_dbp += est
        print()
        print(f"  Суммарная оценка просмотренных строк: {est_total}")
        print(f"    из них дешёвые (отзывы + кубы): {est_fb}")
        print(f"    из них тяжёлые (detail_by_period): {est_dbp}")
        if est_fb > 500_000:
            print("  ⚠ отзывы/кубы > 500 000 — сузьте срез (--months).")
        if est_dbp > 300_000:
            print("  ⚠ detail_by_period > 300 000 — сузьте --defects-months "
                  "(по умолчанию 3).")
        if est_total > 500_000 and est_dbp <= 300_000:
            print("  ⚠ суммарно > 500 000, но тяжёлая часть в бюджете — можно выполнять.")

        # Предохранитель: detail_by_period — тяжёлая таблица (881k строк).
        # Если срез всё равно велик, раздел G пропускается (--force, чтобы выполнить).
        dbp_ok = est_dbp <= 300_000 or args.force
        if not dbp_ok:
            print()
            print("  ⚠ раздел G (брак, detail_by_period) ПРОПУЩЕН: оценка "
                  f"{est_dbp} строк > 300 000.")
            print("    Сузьте срез: --defects-months 1 (или 2). --force — на свой риск.")

        if args.explain:
            print()
            print("Готово. Запросы не выполнялись — только EXPLAIN и information_schema.")
            return 0

        # --- B. отзывы по месяцам --------------------------------------------
        month_rows: list = []
        week_rows: list = []
        cand: list = []
        total_cards = 0
        cards_with_fb = 0
        cube_month_rows: list = []
        buckets: dict = {}
        signal_cards = 0
        penalty_rows: list = []

        if heavy_ok:
            _h("B0. ПОКРЫТИЕ СИГНАЛОВ: сколько отзывов с текстом / тегами / pros / cons")
            print(f"  {'оценка':<8} {'отзывов':>8} {'с текстом':>10} {'с тегами':>10} "
                  f"{'с pros':>8} {'cons (без [])':>14} {'cons (старый)':>14}")
            for r in await _run(db, "B0", _cover_sql(SQL_COVERAGE, all_companies), params):
                print(f"  {str(r['rating'] or ''):<8} {int(r['cnt'] or 0):>8} "
                      f"{int(r['with_text'] or 0):>10} {int(r['with_tags'] or 0):>10} "
                      f"{int(r['with_pros'] or 0):>8} {int(r['cons_real'] or 0):>14} "
                      f"{int(r['cons_old'] or 0):>14}")
            print("  (если cons (старый) >> cons (без []) — пустой массив '[]' проходит")
            print("   фильтр «cons заполнен», и все отзывы считаются жалобами)")

            _h("B. ОТЗЫВЫ ПО МЕСЯЦАМ")
            month_rows = await _run(db, "B", _fb_sql(SQL_BY_MONTH, all_companies), params)
            print(f"  {'месяц':<10} {'отзывов':>8} {'негат.':>8} {'с cons':>8} "
                  f"{'покупки':>8} {'ср.оц.':>8} {'карточек':>9}")
            for r in month_rows:
                print(f"  {r['ym']:<10} {int(r['cnt'] or 0):>8} {int(r['neg_cnt'] or 0):>8} "
                      f"{int(r['cons_cnt'] or 0):>8} {int(r['bought_cnt'] or 0):>8} "
                      f"{str(r['avg_rating'] or ''):>8} {int(r['cards_cnt'] or 0):>9}")

            _h("C. ОТЗЫВЫ ПО НЕДЕЛЯМ (масса в неделю)")
            week_rows = await _run(db, "C", _fb_sql(SQL_BY_WEEK, all_companies), wparams)
            print(f"  {'неделя':<8} {'с':<12} {'отзывов':>8} {'негат.':>8} "
                  f"{'с cons':>8} {'покупки':>8} {'карточек':>9}")
            for r in week_rows:
                print(f"  {r['yw']:<8} {r['week_start']:<12} {int(r['cnt'] or 0):>8} "
                      f"{int(r['neg_cnt'] or 0):>8} {int(r['cons_cnt'] or 0):>8} "
                      f"{int(r['bought_cnt'] or 0):>8} {int(r['cards_cnt'] or 0):>9}")

            _h("D. КАРТОЧКИ С ЖАЛОБАМИ (оценка <= 3 или заполнен «cons»)")
            cand = await _run(db, "D2", _fb_sql(SQL_SIGNAL_CARDS, all_companies), params)
            nms = [int(r["nm_id"]) for r in cand if r.get("nm_id")]
            titles: dict = {}
            if nms:
                trows = (await db.execute(text(SQL_CARD_TITLES).bindparams(
                    bindparam("nms", expanding=True)), {"nms": tuple(nms)})).mappings().all()
                titles = {int(t["nm_id"]): dict(t) for t in trows}
            print(f"  {'nmID':>10} {'жалоб':>6} {'негат.':>7} {'cons':>6} "
                  f"{'ср.оц.':>7} {'дней':>5}  {'последний':<12} карточка")
            for r in cand:
                t = titles.get(int(r["nm_id"]), {})
                title = str(t.get("title") or "(нет в wbcards)")[:44]
                vendor = t.get("vendorCode") or ""
                print(f"  {int(r['nm_id'] or 0):>10} {int(r['cnt'] or 0):>6} "
                      f"{int(r['neg_cnt'] or 0):>7} {int(r['cons_cnt'] or 0):>6} "
                      f"{str(r['avg_rating'] or ''):>7} {int(r['days_cnt'] or 0):>5}  "
                      f"{str(r['last_at'] or ''):<12} {title} {vendor}")

            dist = (await _run(db, "D3", _fb_sql(SQL_SIGNAL_DISTRIBUTION, all_companies),
                               params) or [{}])[0]
            dist = dict(dist or {})
            signal_cards = int(dist.get("cards_cnt") or 0)
            print()
            print(f"  карточек с жалобами:            {signal_cards}")
            print(f"    из них с 3+ жалобами:         {int(dist.get('c3plus') or 0)}")
            print(f"    с 2 жалобами:                 {int(dist.get('c2') or 0)}")
            print(f"    с 1 жалобой:                  {int(dist.get('c1') or 0)}")
            if args.require_bought:
                bought = await _run(db, "D (с фильтром «реальная покупка»)",
                                    _fb_sql(SQL_CANDIDATES, all_companies, True), params)
                print(f"  карточек при фильтре «покупка»: {len(bought)} "
                      f"(f_cost/is_pay заполнены у единиц отзывов)")

            _h("E. ПОКРЫТИЕ КАРТОЧЕК")
            t1 = (await _run(db, "E1", _cards_sql(SQL_CARDS_TOTAL, all_companies), params)
                  or [{}])[0]
            t2 = (await _run(db, "E2", _fb_sql(SQL_CARDS_WITH_FB, all_companies), params)
                  or [{}])[0]
            total_cards = int(t1.get("nm_cnt") or 0)
            cards_with_fb = int(t2.get("nm_cnt") or 0)
            print(f"  карточек компании (nmID):      {total_cards}")
            print(f"  из них с отзывами за период:  {cards_with_fb} "
                  f"({(cards_with_fb / total_cards * 100) if total_cards else 0:.1f}%)")
        else:
            print()
            print("  B/C/D/E пропущены (см. предупреждение выше). Для замера нужен")
            print("  индекс (company_id, createdDate) на wb_feedbacks, либо --force.")

        # --- F. возвраты (куб) + брак (узкий detail_by_period) ----------------
        _h("F. ВОЗВРАТЫ И ШТРАФЫ — куб agg_sales_daily_sku (дёшево)")
        try:
            fresh = (await _run(db, "F0. свежесть куба",
                                 _cube_sql(SQL_CUBE_FRESH, all_companies), cparams) or [{}])[0]
            print(f"  максимальная sale_date в кубе: {fresh.get('max_date')}   "
                  f"строк по компании: {int(fresh.get('rows_cnt') or 0)}")

            cube_month_rows = await _run(db, "F1. возвраты/продажи по месяцам",
                                         _cube_sql(SQL_CUBE_BY_MONTH, all_companies), cparams)
            print(f"  {'месяц':<10} {'продаж':>9} {'возвратов':>10} {'%':>7} "
                  f"{'штрафы ₽':>12} {'карточек':>9}")
            for r in cube_month_rows:
                print(f"  {r['ym']:<10} {int(r['sales_qty'] or 0):>9} "
                      f"{int(r['returns_qty'] or 0):>10} {str(r['returns_pct'] or ''):>7} "
                      f"{str(r['penalty_sum'] or ''):>12} {int(r['cards_cnt'] or 0):>9}")

            buckets = (await _run(db, "F4. корзины % возвратов",
                                   _cube_sql(SQL_CUBE_RATE_BUCKETS, all_companies), cparams)
                       or [{}])[0]

            top = await _run(db, "F2. ТОП карточек по возвратам (кол-во)",
                              _cube_sql(SQL_CUBE_TOP_RETURNS, all_companies), cparams)
            top_rate = await _run(db, "F3. ТОП карточек по % возвратов",
                                  _cube_sql(SQL_CUBE_TOP_RATE, all_companies), cparams)
            penalty_rows = await _run(db, "F5. ТОП карточек по штрафам",
                                      _cube_sql(SQL_CUBE_PENALTY_TOP, all_companies), cparams)
        except Exception as e:
            print(f"  ⚠ куб agg_sales_daily_sku недоступен: {type(e).__name__}: {e}")
            print("    (нет таблицы или нет данных). Возвраты/штрафы тогда — из G (detail_by_period).")
            await db.rollback()
            top, top_rate, buckets = [], [], {}

        top_nms = [int(r["nm_id"]) for r in (top + top_rate) if r.get("nm_id")]
        top_titles: dict = {}
        if top_nms:
            trows = (await db.execute(text(SQL_CARD_TITLES).bindparams(
                bindparam("nms", expanding=True)), {"nms": tuple(top_nms)})).mappings().all()
            top_titles = {int(t["nm_id"]): dict(t) for t in trows}
        if top:
            print(f"  {'nmID':>10} {'продаж':>8} {'возвратов':>10} {'%':>7} {'штрафы':>10}  карточка")
            for r in top:
                t = top_titles.get(int(r["nm_id"]), {})
                print(f"  {int(r['nm_id'] or 0):>10} {int(r['sales_qty'] or 0):>8} "
                      f"{int(r['returns_qty'] or 0):>10} {str(r['returns_pct'] or ''):>7} "
                      f"{str(r['penalty_sum'] or ''):>10}  "
                      f"{str(t.get('title') or '(нет в wbcards)')[:44]}")
        if top_rate:
            print()
            print("  --- карточки с высоким % возвратов (товарный сигнал) ---")
            for r in top_rate:
                t = top_titles.get(int(r["nm_id"]), {})
                print(f"  {int(r['nm_id'] or 0):>10} {int(r['sales_qty'] or 0):>8} "
                      f"{int(r['returns_qty'] or 0):>10} {str(r['returns_pct'] or ''):>7} "
                      f"{str(r['penalty_sum'] or ''):>10}  "
                      f"{str(t.get('title') or '(нет в wbcards)')[:44]}")

        _h("G. БРАК И ШТРАФЫ — detail_by_period (узкий срез, тяжёлая таблица)")
        if not dbp_ok:
            print("  ПРОПУЩЕНО (см. предупреждение выше).")
        else:
            _h("G3. ШТРАФЫ: РАЗБОР ПО ПРИЧИНАМ (что именно штрафуют)")
            for r in await _run(db, "G3", _dbp_sql(SQL_DBP_PENALTY_REASONS, all_companies),
                                fparams):
                print(f"    причина={str(r['bonus_type'])[:44]:<44} "
                      f"операция={str(r['oper'])[:12]:<12} "
                      f"штраф={str(r['penalty_sum'] or ''):>12} "
                      f"строк={int(r['cnt'] or 0):>5} карточек={int(r['cards_cnt'] or 0):>4}")

            _h("G4. ШТРАФЫ: ТОП КАРТОЧЕК")
            ptop = await _run(db, "G4", _dbp_sql(SQL_DBP_PENALTY_TOP, all_companies), fparams)
            pnms = [int(r["nm_id"]) for r in ptop if r.get("nm_id")]
            ptitles: dict = {}
            if pnms:
                trows = (await db.execute(text(SQL_CARD_TITLES).bindparams(
                    bindparam("nms", expanding=True)), {"nms": tuple(pnms)})).mappings().all()
                ptitles = {int(t["nm_id"]): dict(t) for t in trows}
            print(f"  {'nmID':>10} {'штраф ₽':>11} {'строк':>6}  причина / карточка")
            for r in ptop:
                t = ptitles.get(int(r["nm_id"]), {})
                print(f"  {int(r['nm_id'] or 0):>10} {str(r['penalty_sum'] or ''):>11} "
                      f"{int(r['cnt'] or 0):>6}  {str(r['bonus_type'])[:32]:<32} "
                      f"{str(t.get('title') or '(нет в wbcards)')[:38]}")

            _h("G1/G2. БРАК И СЛОВАРЬ")
            for label, tmpl in (("G1. ТОП карточек по браку", SQL_DBP_DEFECTS_TOP),
                                ("G2. словарь doc_type/bonus_type", SQL_DBP_VOCAB)):
                for r in await _run(db, label, _dbp_sql(tmpl, all_companies), fparams):
                    if label.startswith("G2"):
                        print(f"    doc={str(r['doc_type']):<22} bonus={str(r['bonus_type']):<42} "
                              f"{int(r['cnt'] or 0):>8}")
                    else:
                        t = top_titles.get(int(r["nm_id"]), {})
                        print(f"    nmID={int(r['nm_id'] or 0):>10} брак={int(r['defect_cnt'] or 0):>5} "
                              f"возвратов={int(r['returns_qty'] or 0):>6}  "
                              f"{str(t.get('title') or '(нет в wbcards)')[:44]}")

        _h("H. ТЕКСТЫ ЖАЛОБ (выборка) — есть ли в них пригодный сигнал")
        samples = await _run(db, "H", _fb_sql(SQL_SAMPLE_COMPLAINTS, all_companies), params)
        snms = sorted({int(r["nm_id"]) for r in samples if r.get("nm_id")})
        stitles: dict = {}
        if snms:
            trows = (await db.execute(text(SQL_CARD_TITLES).bindparams(
                bindparam("nms", expanding=True)), {"nms": tuple(snms)})).mappings().all()
            stitles = {int(t["nm_id"]): dict(t) for t in trows}
        for r in samples:
            body = " ".join(str(r.get("body") or "").split())[:220]
            cons = " ".join(str(r.get("cons") or "").split())[:80]
            pros = " ".join(str(r.get("pros") or "").split())[:60]
            t = stitles.get(int(r["nm_id"] or 0), {})
            print(f"  nmID={int(r['nm_id'] or 0):>10} оценка={int(r['rating'] or 0)} "
                  f"куплен={r.get('f_cost')} размер={str(r.get('size') or '')[:12]!s:<12} "
                  f"цвет={str(r.get('color') or '')[:14]!s:<14} {str(r.get('created_at') or '')[:10]}")
            print(f"    карточка: {str(t.get('title') or '')[:70]}")
            print(f"    текст:    {body or '(пусто)'}")
            if pros:
                print(f"    плюсы:    {pros}")
            if cons:
                print(f"    минусы:   {cons}")

        # --- вердикт ---------------------------------------------------------
        _h("ИТОГ")
        for line in _verdict(month_rows, week_rows, cand, total_cards,
                             cards_with_fb, cube_month_rows, buckets, signal_cards):
            print(line)

    return 0


if __name__ == "__main__":
    asyncio.run(main())
