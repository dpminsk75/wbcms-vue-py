"""Продажи WB — порт wb-sales/fetch (S).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/sales_fetch_sync.py
  .venv/bin/python backend/workers/sales_fetch_sync.py --date-from 2024-01-01
  DRY_RUN=1 .venv/bin/python backend/workers/sales_fetch_sync.py
  Дефолт -3д. Таймер: wbcms-sales-fetch (hourly :15).

Таблица: wb_sales (upsert saleID) + линковка wb_order.
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(i, n, stage, k, api, db, wait, msg=""):
        if stage in ("send", "retry"):
            print(f"  [{label}] [{msg}]", flush=True)
        elif stage == "pause":
            print(f"  [{label}] строк {k}, ошибок {n}", flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.sales_fetch_sync_service import SalesFetchService
    print("WB API: GET statistics.../supplier/sales → wb_sales (+wb_order link)",
          flush=True)
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name FROM companies WHERE is_active = 1"
            " AND api_key IS NOT NULL AND api_key <> ''"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        ok, skipped, errors = 0, 0, 0
        for comp in companies:
            cid = int(comp["id"])
            print(f"[{comp['name'] or cid}] старт...", flush=True)
            try:
                st = await SalesFetchService(db, company_id=cid).sync(
                    date_from=args.date_from, dry_run=args.dry_run,
                    progress=_make_progress(comp["name"] or str(cid)))
                if st.get("skipped"):
                    print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                    skipped += 1
                else:
                    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                    print(f"[{comp['name'] or cid}] fetched={st['fetched']} "
                          f"(записано {st['saved']}, ошибок {st['errors']}, "
                          f"линков {st['linked']}) {st.get('token_type')}{warn}")
                    ok += 1
                    errors += 1 if st["errors"] else 0
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
            time.sleep(1)
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Продажи WB (supplier/sales)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
