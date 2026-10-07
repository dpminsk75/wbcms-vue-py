"""Срез баланса ЛК WB раз в 3 часа — история в wb_finance_balance.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/finance_balance_sync.py
  DRY_RUN=1 .venv/bin/python backend/workers/finance_balance_sync.py  # опрос без записи
  .venv/bin/python backend/workers/finance_balance_sync.py --company-id 1
  Cron раз в 3 часа:
  5 */3 * * * cd /var/www/wb/wbcms-py && .venv/bin/python backend/workers/finance_balance_sync.py >> /var/log/wb-finance-balance.log 2>&1

Цикл по активным компаниям с api_key (как feedback_auto_reply).
Лимит WB 1 запр/мин — на продавца, у каждой компании свой токен,
пауза между компаниями не нужна. Без категории Finance в токене WB
вернёт 401/403 — такая компания пропускается с ошибкой в лог, остальные идут.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.finance_balance_service import FinanceBalanceService
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name FROM companies WHERE is_active = 1"
            " AND api_key IS NOT NULL AND api_key <> ''"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        ok, errors = 0, 0
        for comp in companies:
            cid = int(comp["id"])
            try:
                st = await FinanceBalanceService(db, company_id=cid).sync(dry_run=args.dry_run)
                print(f"[{comp['name'] or cid}] current={st['current']} "
                      f"for_withdraw={st['for_withdraw']} {st['currency']}")
                ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Срез баланса WB (finance-api balance)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
