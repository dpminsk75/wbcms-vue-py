"""Синк поставок FBS (скан приёмки) — свежие сдачи внутри дня.

Режим по умолчанию — инкремент: новые supply_id из wb_orders_fbs +
открытые/без скана (точечно GET /supplies/{id}). Поставок за годы много,
полную пагинацию гоняем ОДИН раз вручную (--full).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/fbs_supplies_sync.py
  DRY_RUN=1 .venv/bin/python backend/workers/fbs_supplies_sync.py  # без записи
  .venv/bin/python backend/workers/fbs_supplies_sync.py --full     # разовый бэкфилл
  Cron каждые 30 мин (инкремент):
  */30 * * * * cd /var/www/wb/wbcms-py && .venv/bin/python backend/workers/fbs_supplies_sync.py >> /var/log/fbs-supplies.log 2>&1

Токен companies.api_key id=1. Таблица: wb_orders_fbs_supplies (upsert).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run(args) -> int:
    from backend.database import get_session
    from backend.services.fbs_supplies_service import FbsSuppliesService
    async with get_session() as db:
        svc = FbsSuppliesService(db, company_id=args.company_id)
        try:
            if args.full:
                st = await svc.sync_full(dry_run=args.dry_run)
            else:
                st = await svc.sync_incremental(dry_run=args.dry_run)
            print("supplies:", st)
        except Exception as e:
            print(f"ERROR: {e}")
            return 1
        return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Синк поставок FBS (scanDt)")
    ap.add_argument("--company-id", type=int, default=1)
    ap.add_argument("--full", action="store_true",
                    help="разовый бэкфилл всей пагинации (по умолчанию — инкремент)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
