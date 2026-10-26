"""Агрегаты OLAP — порт aggregate/update* (без API, только SQL).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/aggregate_sync.py
  .venv/bin/python backend/workers/aggregate_sync.py --date-from 2026-03-01 --date-to 2026-03-31
  .venv/bin/python backend/workers/aggregate_sync.py --days 3        # инкремент за 3 дня
  .venv/bin/python backend/workers/aggregate_sync.py --only summary
  .venv/bin/python backend/workers/aggregate_sync.py --explain       # план запросов, НИЧЕГО не выполняет
  DRY_RUN=1 .venv/bin/python backend/workers/aggregate_sync.py
  Дефолт -50д..сегодня (как PHP).

Таймер: wbcms-aggregate (01:30, после finance-detail 01:00 и до search-report 02:00).

ВАЖНО: пересчёт сводки идёт через INSERT ... ON DUPLICATE KEY UPDATE (как в PHP),
строки НЕ удаляются — ff_otziv/ff_adv/ff_storage_fee не теряются.

Для таймера используйте --days 3 (инкремент): полный пересчёт за 50 дней —
это минуты работы каждый день. Полный пересчёт — раз в неделю или вручную.

Вывод в консоль (flush=True — видно сразу, даже при | tee / лог):
  Агрегаты: detail_by_period → agg_* (только SQL)
  Период: 2026-01-01..2026-10-23
  → summary: agg_daily_summary (upsert, минуты) ...
  summary: ok  (123.4s)
Шаг печатается ДО выполнения + время шага после → видно, что процесс жив.
В фоне с логом:
  nohup .venv/bin/python backend/workers/aggregate_sync.py --only summary,feedbacks,adv \
    --date-from 2026-01-01 --date-to 2026-10-23 > /tmp/agg.log 2>&1 &
  tail -f /tmp/agg.log
Если висит — смотри MySQL: SHOW FULL PROCESSLIST; (шаг идёт одной транзакцией,
при ошибке — откат, agg_daily_summary остаётся прежней).

Кубы: agg_sales_daily_sku, agg_orders_daily_sku, agg_daily_summary + ff_otziv/ff_adv.
"""
import argparse
import asyncio
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Подписи шагов: что делает и сколько примерно ждать
STEP_HELP = {
    "sales": "agg_sales_daily_sku (пересчёт из detail_by_period)",
    "orders": "agg_orders_daily_sku (пересчёт из detail_by_period)",
    "summary": "agg_daily_summary (upsert — минуты)",
    "feedbacks": "ff_otziv (списание за отзывы)",
    "adv": "ff_adv (реклама)",
    "storage": "ff_storage_fee (платное хранение по позициям из wb_paid_storage)",
}


async def _explain(db, svc, steps, df, dt) -> int:
    """Печатает EXPLAIN всех запросов и НИЧЕГО не выполняет (AGENTS.md §4)."""
    from sqlalchemy import text
    params = svc.params(df, dt)
    for s in steps:
        sql = svc.STEPS.get(s)
        if not sql:
            print(f"--- EXPLAIN {s}: нет SQL ---", flush=True)
            continue
        print(f"\n--- EXPLAIN {s}: {STEP_HELP.get(s, '')} ---", flush=True)
        try:
            rows = (await db.execute(text("EXPLAIN " + sql), params)).mappings().all()
            for r in rows:
                d = dict(r)
                print(f"  id={d.get('id')} select_type={d.get('select_type')} "
                      f"table={d.get('table')} type={d.get('type')} "
                      f"key={d.get('key')} rows={d.get('rows')} "
                      f"Extra={d.get('Extra')}", flush=True)
        except Exception as e:
            print(f"  EXPLAIN не выполнился: {type(e).__name__}: {e}"[:300], flush=True)
    return 0


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.aggregate_sync_service import AggregateService
    print("Агрегаты: detail_by_period → agg_* (только SQL)", flush=True)
    df = args.date_from
    if not df and args.days:
        df = (date.today() - timedelta(days=int(args.days))).isoformat()
    df = df or (date.today() - timedelta(days=50)).isoformat()
    dt = args.date_to or date.today().isoformat()
    print(f"Период: {df}..{dt}", flush=True)
    steps = [s.strip() for s in (args.only.split(",") if args.only else
                                 ["sales", "orders", "summary", "feedbacks", "adv", "storage"])
             if s.strip()]
    if args.dry_run:
        print(f"DRY: шаги {', '.join(steps)} (ничего не выполнено)", flush=True)
        return 0
    async with get_session() as db:
        svc = AggregateService(db)
        await svc.apply_session_limits()
        if args.explain:
            return await _explain(db, svc, steps, df, dt)
        failed = 0
        for s in steps:
            if s not in STEP_HELP:
                print(f"  {s}: SKIP (неизвестный шаг)", flush=True)
                continue
            print(f"→ {s}: {STEP_HELP[s]} ...", flush=True)
            t0 = time.monotonic()
            if s == "sales":
                r = await svc.update_sales(df, dt)
            elif s == "orders":
                r = await svc.update_orders(df, dt)
            elif s == "summary":
                r = await svc.update_summary(df, dt)
            elif s == "feedbacks":
                r = await svc.update_feedbacks_cost(df, dt)
            elif s == "adv":
                r = await svc.update_adv_costs(df, dt)
            else:
                r = await svc.update_storage_costs(df, dt)
            el = time.monotonic() - t0
            for k, v in r.items():
                print(f"  {k}: {v}  ({el:.1f}s)", flush=True)
            failed += 0 if all(v == "ok" or v.startswith("ok ") for v in r.values()) else 1
        print(f"TOTAL: {'errors=' + str(failed) if failed else 'ok'}", flush=True)
        return 0 if failed == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Агрегаты OLAP (aggregate)")
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--days", type=int, default=None,
                    help="окно в днях от сегодня (для таймера: --days 3)")
    ap.add_argument("--only", default=None,
                    help="sales,orders,summary,feedbacks,adv,storage через запятую")
    ap.add_argument("--explain", action="store_true",
                    help="печатает EXPLAIN всех запросов и ничего не выполняет")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
