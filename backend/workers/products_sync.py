"""Аналитика товаров — порт wb-product-analytics/sync (B3).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/products_sync.py
  .venv/bin/python backend/workers/products_sync.py --days 7
  DRY_RUN=1 .venv/bin/python backend/workers/products_sync.py
  Таймер: wbcms-products-sync (04:40)

Окно days=30, limit/offset=1000, пауза 20с. Таблица: wb_products_analytics.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(i, n, stage, k, api, db, wait, msg=""):
        if stage == "send":
            print(f"  [{label}] страница {i}: отправляю...", end=" ", flush=True)
        elif stage == "retry":
            print(f"[{msg}]", end=" ", flush=True)
        elif stage == "pause":
            print(f"api {api:.1f}с → запись {db:.1f}с → пауза {wait:.0f}с, строк {k}",
                  flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.products_sync_service import ProductsSyncService
    print("WB API: POST seller-analytics.../stocks-report/products/products"
          " → wb_products_analytics", flush=True)
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
                st = await ProductsSyncService(db, company_id=cid).sync(
                    days=args.days, dry_run=args.dry_run,
                    stock_type=args.stock_type,
                    progress=_make_progress(comp["name"] or str(cid)))
                if st.get("skipped"):
                    print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                    skipped += 1
                else:
                    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                    print(f"[{comp['name'] or cid}] fetched={st['fetched']} "
                          f"(записано {st['rows']}) {st.get('token_type')}{warn}")
                    ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Аналитика товаров WB (stocks-report)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--stock-type", default="")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
