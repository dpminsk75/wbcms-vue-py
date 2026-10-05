"""Синк базовых комиссий WB + справочника предметов (см. commission_tariffs_service).

Запуск (на сервере):
  .venv/bin/python backend/workers/commission_tariffs_sync.py  # только venv! системный python3 без зависимостей
  DRY_RUN=1 .venv/bin/python backend/workers/commission_tariffs_sync.py  # проверка без записи
  .venv/bin/python backend/workers/commission_tariffs_sync.py --tariffs-only
  .venv/bin/python backend/workers/commission_tariffs_sync.py --subjects-only
  Cron: 0 4 * * * cd /var/www/wb/wbcms-py && .venv/bin/python backend/workers/commission_tariffs_sync.py >> /var/log/fbs-tariffs.log 2>&1

Токен — companies.api_key компании id=1. Тарифы глобальные, срезы пишутся
только при изменениях (PK tariff_date+subject_id).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run(args) -> int:
    from backend.database import get_session
    from backend.services.commission_tariffs_service import CommissionTariffsService
    async with get_session() as db:
        svc = CommissionTariffsService(db, company_id=args.company_id)
        try:
            if not args.tariffs_only:
                st = await svc.sync_subjects(dry_run=args.dry_run)
                print("subjects:", st)
            if not args.subjects_only:
                st = await svc.sync_tariffs(dry_run=args.dry_run)
                print("tariffs:", st)
        except Exception as e:
            print(f"ERROR: {e}")
            return 1
        return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Синк комиссий WB (tariffs/commission)")
    ap.add_argument("--company-id", type=int, default=1)
    ap.add_argument("--subjects-only", action="store_true")
    ap.add_argument("--tariffs-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
