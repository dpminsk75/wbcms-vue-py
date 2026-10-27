#!/usr/bin/env python3
"""EXPLAIN + оценка объёма для запросов расшифровки колонок маржи.

НЕ выполняет сами запросы — только EXPLAIN и счётчики из information_schema.
Запуск (на сервере, из корня /var/www/wb/wbcms-py):

    .venv/bin/python backend/scripts/margin_breakdown_explain.py
    .venv/bin/python backend/scripts/margin_breakdown_explain.py --company-id 1 --nm-id 12345

Что проверяем:
  1) agg_daily_summary — «По дням» (PK company_id+sdate+nm_id, выборка должна быть точечной);
  2) detail_by_period — детализация по товару за месяц (нужен ли индекс nm_id+sale_dt);
  3) wb_paid_storage — хранение по позициям;
  4) wb_campaign_stats_nms ⋈ wb_campaign_stats — реклама;
  5) wb_feedbacks — отзывы;
  6) agg_daily_summary + wbcards — «Топ/Худшие 20» на странице /wb-profit;
  7) штрафы (п. 10-12) — медленная расшифровка: смотрим, сканируется ли
     sale_dt-диапазон по всем компаниям (нужен индекс company_id+sale_dt+nm_id).

По результату решаем, нужен ли индекс (detail_by_period: nm_id, sale_dt).
"""
import argparse
import asyncio
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

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

TABLES = ["agg_daily_summary", "detail_by_period", "wb_paid_storage",
          "wb_campaign_stats", "wb_campaign_stats_nms", "wb_feedbacks", "wbcards"]


def build_queries(company_id, nm_id, d1, d2):
    cid = ":company_id"
    nm = ":nm_id"
    return [
        ("1. «По дням» — куб agg_daily_summary (товар)", f"""
            SELECT p.sdate AS d, SUM(p.ff_adv) AS s
            FROM agg_daily_summary p
            WHERE p.sdate BETWEEN '{d1}' AND '{d2}' AND p.company_id = {cid} AND p.nm_id = {nm}
            GROUP BY p.sdate HAVING SUM(p.ff_adv) <> 0 ORDER BY p.sdate"""),

        ("2. Детализация — detail_by_period (логистика, товар)", f"""
            SELECT DATE(d.sale_dt) AS d, d.office_name AS office,
                   COALESCE(d.bonus_type_name, '—') AS reason,
                   SUM(d.quantity) AS qty, COUNT(*) AS cnt, SUM(d.delivery_rub) AS amount
            FROM detail_by_period d
            WHERE d.sale_dt BETWEEN '{d1} 00:00:00' AND '{d2} 23:59:59'
              AND d.delivery_rub <> 0 AND d.company_id = {cid} AND d.nm_id = {nm}
            GROUP BY DATE(d.sale_dt), d.office_name, COALESCE(d.bonus_type_name, '—')
            ORDER BY DATE(d.sale_dt) DESC, amount DESC LIMIT 300"""),

        ("3. Итоги по причинам — detail_by_period (логистика)", f"""
            SELECT COALESCE(d.bonus_type_name, '—') AS reason, COUNT(*) AS cnt,
                   SUM(d.quantity) AS qty, SUM(d.delivery_rub) AS amount
            FROM detail_by_period d
            WHERE d.sale_dt BETWEEN '{d1} 00:00:00' AND '{d2} 23:59:59'
              AND d.delivery_rub <> 0 AND d.company_id = {cid}
            GROUP BY COALESCE(d.bonus_type_name, '—') ORDER BY amount DESC"""),

        ("4. Приёмка — detail_by_period (операция/склад/поставка)", f"""
            SELECT DATE(d.sale_dt) AS d,
                   COALESCE(d.supplier_oper_name, '—') AS oper,
                   COALESCE(NULLIF(d.ppvz_office_name, ''), NULLIF(d.office_name, ''), '—') AS office,
                   d.gi_id AS gi, COUNT(*) AS cnt, SUM(d.acceptance) AS amount
            FROM detail_by_period d
            WHERE d.sale_dt BETWEEN '{d1} 00:00:00' AND '{d2} 23:59:59'
              AND d.acceptance <> 0 AND d.company_id = {cid} AND d.nm_id = {nm}
            GROUP BY DATE(d.sale_dt), COALESCE(d.supplier_oper_name, '—'),
                     COALESCE(NULLIF(d.ppvz_office_name, ''), NULLIF(d.office_name, ''), '—'), d.gi_id
            ORDER BY amount DESC LIMIT 300"""),

        ("5. Хранение — wb_paid_storage (товар)", f"""
            SELECT ps.date AS d, ps.warehouse AS warehouse, ps.calcType AS calc_type,
                   SUM(ps.barcodesCount) AS units, SUM(ps.volume) AS volume,
                   SUM(ps.warehousePrice) AS amount
            FROM wb_paid_storage ps
            WHERE ps.date BETWEEN '{d1}' AND '{d2}' AND ps.company_id = {cid} AND ps.nmId = {nm}
            GROUP BY ps.date, ps.warehouse, ps.calcType
            ORDER BY ps.date DESC, amount DESC LIMIT 300"""),

        ("6. Реклама — список кампаний (селект фильтра)", f"""
            SELECT s.campaign_id AS campaign_id, SUM(n.views) AS views,
                   SUM(n.clicks) AS clicks, SUM(n.orders) AS orders, SUM(n.`sum`) AS cost
            FROM wb_campaign_stats_nms n
            INNER JOIN wb_campaign_stats s ON n.parent_id = s.id AND n.company_id = s.company_id
            WHERE s.date BETWEEN '{d1}' AND '{d2}' AND n.nm_id = {nm} AND n.company_id = {cid}
            GROUP BY s.campaign_id ORDER BY cost DESC LIMIT 500"""),

        ("7. Реклама — строки по дате × кампании", f"""
            SELECT s.date AS d, s.campaign_id AS campaign_id,
                   SUM(n.views) AS views, SUM(n.clicks) AS clicks, SUM(n.orders) AS orders,
                   SUM(n.`sum`) AS cost
            FROM wb_campaign_stats_nms n
            INNER JOIN wb_campaign_stats s ON n.parent_id = s.id AND n.company_id = s.company_id
            WHERE s.date BETWEEN '{d1}' AND '{d2}' AND n.nm_id = {nm} AND n.company_id = {cid}
            GROUP BY s.date, s.campaign_id ORDER BY s.date DESC, cost DESC LIMIT 300"""),

        ("8. Отзывы — wb_feedbacks (товар, только списанные)", f"""
            SELECT DATE(f.createdDate) AS d, f.id AS fb_id, f.f_cost AS cost
            FROM wb_feedbacks f
            WHERE f.createdDate BETWEEN '{d1} 00:00:00' AND '{d2} 23:59:59'
              AND (f.is_pay > 0 OR f.f_cost > 0) AND f.company_id = {cid} AND f.nmID = {nm}
            ORDER BY f.createdDate DESC LIMIT 300"""),

        ("9. «Топ/Худшие 20» — agg_daily_summary + wbcards (/wb-profit)", f"""
            SELECT p.nm_id AS nm_id, c.title AS title, SUM(p.qnt) AS qnt,
                   SUM(p.net_profit) - SUM(IFNULL(p.ff_otziv,0)) - SUM(IFNULL(p.ff_adv,0))
                     - SUM(IFNULL(p.ff_storage_fee,0)) AS net_profit
            FROM agg_daily_summary p
            LEFT JOIN wbcards c ON c.nmID = p.nm_id
            WHERE p.sdate BETWEEN '{d1}' AND '{d2}' AND p.company_id = {cid}
            GROUP BY p.nm_id, c.title, c.brand, c.vendorCode
            ORDER BY net_profit DESC LIMIT 20"""),

        ("10. Штрафы — detail_by_period (товар) — медленный запрос", f"""
            SELECT DATE(d.sale_dt) AS d, d.supplier_oper_name AS oper,
                   COUNT(*) AS cnt, SUM(d.penalty) AS amount
            FROM detail_by_period d
            WHERE d.sale_dt BETWEEN '{d1} 00:00:00' AND '{d2} 23:59:59'
              AND d.penalty <> 0 AND d.company_id = {cid} AND d.nm_id = {nm}
            GROUP BY DATE(d.sale_dt), d.supplier_oper_name
            ORDER BY amount DESC LIMIT 300"""),

        ("11. Штрафы — detail_by_period (без товара, месяц)", f"""
            SELECT DATE(d.sale_dt) AS d, d.supplier_oper_name AS oper,
                   COUNT(*) AS cnt, SUM(d.penalty) AS amount
            FROM detail_by_period d
            WHERE d.sale_dt BETWEEN '{d1} 00:00:00' AND '{d2} 23:59:59'
              AND d.penalty <> 0 AND d.company_id = {cid}
            GROUP BY DATE(d.sale_dt), d.supplier_oper_name
            ORDER BY amount DESC LIMIT 300"""),

        ("12. Штрафы — detail_by_period по supplier_oper_name (вариант с индексом)", f"""
            SELECT DATE(d.sale_dt) AS d, COUNT(*) AS cnt, SUM(d.penalty) AS amount
            FROM detail_by_period d
            WHERE d.sale_dt BETWEEN '{d1} 00:00:00' AND '{d2} 23:59:59'
              AND d.penalty <> 0 AND d.company_id = {cid}
              AND d.supplier_oper_name LIKE '%Штраф%'
            GROUP BY DATE(d.sale_dt) ORDER BY amount DESC LIMIT 300"""),
    ]


async def main():
    ap = argparse.ArgumentParser(description="EXPLAIN запросов расшифровки маржи (ничего не выполняет)")
    ap.add_argument("--company-id", type=int, default=1)
    ap.add_argument("--nm-id", type=int, default=0)
    ap.add_argument("--date-from", default="2026-08-28")
    ap.add_argument("--date-to", default="2026-10-27")
    args = ap.parse_args()

    nm_id = args.nm_id or 0
    params = {"company_id": args.company_id, "nm_id": nm_id}

    async with get_session() as db:
        for stmt in SESSION_LIMITS:
            try:
                await db.execute(text(stmt))
            except Exception:
                pass
        await db.rollback()

        print("=" * 100)
        print("ОБЪЁМ ТАБЛИЦ (information_schema)")
        print("=" * 100)
        # Явные алиасы: в information_schema колонки названы капсом (TABLE_NAME),
        # без AS драйвер отдаёт ключ в верхнем регистре и поиск по ключу падает.
        rows = (await db.execute(text("""
            SELECT table_name AS tbl, table_rows AS tr,
                   ROUND(data_length/1024/1024,1) AS data_mb,
                   ROUND(index_length/1024/1024,1) AS idx_mb
            FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name IN :tbls
            ORDER BY table_rows DESC""").bindparams(
                bindparam("tbls", expanding=True)), {"tbls": tuple(TABLES)})).mappings().all()
        for r in rows:
            print(f"  {r['tbl']:<26} rows≈{int(r['tr'] or 0):>9}  "
                  f"data={r['data_mb']}MB  idx={r['idx_mb']}MB")
        print()

        print("=" * 100)
        print("ИНДЕКСЫ detail_by_period / agg_daily_summary")
        print("=" * 100)
        rows = (await db.execute(text("""
            SELECT table_name AS tbl, index_name AS idx,
                   GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name IN ('detail_by_period','agg_daily_summary','wb_paid_storage',
                                 'wb_campaign_stats_nms','wb_feedbacks')
            GROUP BY table_name, index_name ORDER BY table_name, index_name"""), {})).mappings().all()
        for r in rows:
            print(f"  {r['tbl']:<26} {r['idx']:<38} ({r['cols']})")
        print()

        print("=" * 100)
        print("PROBE: приёмка — какая колонка заполнена (ppvz_office_name / office_name) "
              "и какие операции встречаются")
        print("=" * 100)
        probe = (await db.execute(text(f"""
            SELECT COUNT(*) AS rows_cnt,
                   SUM(CASE WHEN d.ppvz_office_name IS NOT NULL AND d.ppvz_office_name <> ''
                            THEN 1 ELSE 0 END) AS has_ppvz,
                   SUM(CASE WHEN d.office_name IS NOT NULL AND d.office_name <> ''
                            THEN 1 ELSE 0 END) AS has_office,
                   SUM(CASE WHEN d.gi_id IS NOT NULL THEN 1 ELSE 0 END) AS has_gi
            FROM detail_by_period d
            WHERE d.sale_dt BETWEEN '{args.date_from} 00:00:00' AND '{args.date_to} 23:59:59'
              AND d.acceptance <> 0 AND d.company_id = :company_id"""),
            {"company_id": args.company_id})).mappings().first()
        p = dict(probe or {})
        print(f"  строк приёмки: {int(p.get('rows_cnt') or 0)} | "
              f"с ppvz_office_name: {int(p.get('has_ppvz') or 0)} | "
              f"с office_name: {int(p.get('has_office') or 0)} | "
              f"с gi_id: {int(p.get('has_gi') or 0)}")
        ops = (await db.execute(text(f"""
            SELECT COALESCE(d.supplier_oper_name, '—') AS oper, COUNT(*) AS cnt,
                   SUM(d.acceptance) AS amount
            FROM detail_by_period d
            WHERE d.sale_dt BETWEEN '{args.date_from} 00:00:00' AND '{args.date_to} 23:59:59'
              AND d.acceptance <> 0 AND d.company_id = :company_id
            GROUP BY COALESCE(d.supplier_oper_name, '—') ORDER BY amount DESC LIMIT 20"""),
            {"company_id": args.company_id})).mappings().all()
        for o in ops:
            print(f"  операция: {o['oper']:<40} записей={int(o['cnt']):>6}  сумма={o['amount']}")
        print()

        for title, sql in build_queries(args.company_id, nm_id, args.date_from, args.date_to):
            print("=" * 100)
            print(title)
            print("-" * 100)
            print(" ".join(sql.split()))
            try:
                plan = (await db.execute(text("EXPLAIN " + sql), params)).mappings().all()
                for p in plan:
                    print(f"  type={p.get('type')} key={p.get('key')} rows≈{p.get('rows')} "
                          f"extra={p.get('Extra')}")
            except Exception as e:
                print(f"  EXPLAIN FAILED: {type(e).__name__}: {e}")
            print()

    print("Готово. Запросы не выполнялись — только EXPLAIN и information_schema.")


if __name__ == "__main__":
    asyncio.run(main())
