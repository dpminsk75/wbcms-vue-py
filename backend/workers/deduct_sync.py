"""Вычет FBS-заказов из виртуалки — порт deductVirtualStocks (D5, без API кроме выгрузки).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/deduct_sync.py
  .venv/bin/python backend/workers/deduct_sync.py --test   # dry-run PUT (дефолт из компании)
  DRY_RUN=1 .venv/bin/python backend/workers/deduct_sync.py

Гейты: fbs_deduct_enabled, склад is_fbs, consider_orders. Лог — journal.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.deduct_sync_service import DeductService
    print("Вычет FBS: wb_orders_fbs → wb_stock_balance/ledger → PUT stocks",
          flush=True)
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name FROM companies WHERE is_active = 1"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        ok, skipped, errors = 0, 0, 0
        for comp in companies:
            cid = int(comp["id"])
            print(f"[{comp['name'] or cid}] старт...", flush=True)
            try:
                st = await DeductService(db, company_id=cid).sync(
                    test=args.test, dry_run=args.dry_run)
                if st.get("skipped"):
                    print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                    skipped += 1
                else:
                    print(f"[{comp['name'] or cid}] заказов={st.get('orders')} "
                          f"ok={st.get('ok')} fail={st.get('fail')} "
                          f"выгружено={st.get('uploaded_skus')} "
                          f"test={st.get('test_mode')}")
                    if st.get("fail_sample"):
                        print(f"  пример ошибки: {st['fail_sample']}")
                    ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Вычет FBS-заказов из виртуалки")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--test", action="store_true", default=None,
                    help="dry-run PUT (дефолт — из companies.fbs_deduct_test)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
