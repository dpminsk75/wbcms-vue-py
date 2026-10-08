"""Блок остатков целиком: stocks → offices → products (B1+B2+B3 подряд).

Одна связка для таймера (как meta в cron/sync-all): по компаниям,
три фазы последовательно. Ручное тестирование — отдельными воркерами.
Таймер: wbcms-stocks-all (04:30).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.stocks_sync_service import StocksSyncService
    from backend.services.offices_sync_service import OfficesSyncService
    from backend.services.products_sync_service import ProductsSyncService
    print("WB API: stocks-report (wb-warehouses + offices + products)"
          " → wb_stocks, wb_stocks_offices, wb_products_analytics", flush=True)
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
            label = comp["name"] or str(cid)
            print(f"[{label}] старт...", flush=True)
            try:
                s = await StocksSyncService(db, company_id=cid).sync(dry_run=args.dry_run)
                if s.get("skipped"):
                    print(f"[{label}] stocks SKIP: {s['skipped']}")
                else:
                    print(f"[{label}] stocks: fetched={s['fetched']} {s.get('token_type')}")
                o = await OfficesSyncService(db, company_id=cid).sync(dry_run=args.dry_run)
                if o.get("skipped"):
                    print(f"[{label}] offices SKIP: {o['skipped']}")
                else:
                    print(f"[{label}] offices: regions={o['regions']} fetched={o['fetched']}")
                p = await ProductsSyncService(db, company_id=cid).sync(
                    days=args.days, dry_run=args.dry_run)
                if p.get("skipped"):
                    print(f"[{label}] products SKIP: {p['skipped']}")
                else:
                    print(f"[{label}] products: fetched={p['fetched']}")
                if s.get("skipped") and o.get("skipped") and p.get("skipped"):
                    skipped += 1
                else:
                    ok += 1
            except Exception as e:
                print(f"[{label}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Блок остатков целиком (stocks+offices+products)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
