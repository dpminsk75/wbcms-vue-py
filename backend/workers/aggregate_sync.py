"""Агрегаты OLAP — порт aggregate/update* (без API, только SQL).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/aggregate_sync.py
  .venv/bin/python backend/workers/aggregate_sync.py --date-from 2026-03-01 --date-to 2026-03-31
  .venv/bin/python backend/workers/aggregate_sync.py --only summary
  DRY_RUN=1 .venv/bin/python backend/workers/aggregate_sync.py  (только покажет план)
  Дефолт -50д..сегодня (как PHP).

ВАЖНО: шаг summary делает DELETE+INSERT за период → стирает ff_otziv/ff_adv/ff_storage_fee.
Поэтому после него обязательно идут feedbacks, adv, storage (в дефолтной цепочке они есть).
Ручной пересчёт только куба: --only summary,feedbacks,adv,storage.

Вывод в консоль (flush=True — видно сразу, даже при | tee / лог):
  Агрегаты: detail_by_period → agg_* (только SQL)
  Период: 2026-01-01..2026-10-23
  → summary: agg_daily_summary (DELETE+INSERT за период — самый долгий, минуты) ...
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
    "summary": "agg_daily_summary (DELETE+INSERT за период — самый долгий, минуты)",
    "feedbacks": "ff_otziv (списание за отзывы)",
    "adv": "ff_adv (реклама)",
    "storage": "ff_storage_fee (платное хранение по позициям из wb_paid_storage)",
}


async def run(args) -> int:
    from backend.database import get_session
    from backend.services.aggregate_sync_service import AggregateService
    print("Агрегаты: detail_by_period → agg_* (только SQL)", flush=True)
    df = args.date_from or (date.today() - timedelta(days=50)).isoformat()
    dt = args.date_to or date.today().isoformat()
    print(f"Период: {df}..{dt}", flush=True)
    if args.dry_run:
        print(f"DRY: шаги {args.only or 'sales,orders,summary,feedbacks,adv,storage'}", flush=True)
        return 0
    async with get_session() as db:
        svc = AggregateService(db)
        steps = args.only.split(",") if args.only else [
            "sales", "orders", "summary", "feedbacks", "adv", "storage"]
        failed = 0
        for s in steps:
            s = s.strip()
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
    ap.add_argument("--only", default=None,
                    help="sales,orders,summary,feedbacks,adv через запятую")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
