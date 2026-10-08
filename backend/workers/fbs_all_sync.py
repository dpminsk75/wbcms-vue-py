"""FBS-связка: заказы → статусы → вычет (D3+D4+D5 подряд).

Мета для 5-мин таймера. Ручное тестирование — отдельными воркерами.
Таймер: wbcms-fbs-all (каждые 5 мин).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.fbs_orders_sync_service import FbsOrdersService
    from backend.services.fbs_statuses_sync_service import FbsStatusesService
    from backend.services.deduct_sync_service import DeductService
    from backend.services.fbs_supplies_service import FbsSuppliesService
    print("WB API: FBS-связка (заказы+статусы+вычет+поставки)", flush=True)
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
            print(f"[{comp['name'] or cid}] старт...", flush=True)
            try:
                a = await FbsOrdersService(db, company_id=cid).sync(
                    dry_run=args.dry_run)
                print(f"  fbs: {a.get('saved', a.get('skipped', '?'))}")
                b = await FbsStatusesService(db, company_id=cid).sync(
                    dry_run=args.dry_run)
                print(f"  statuses: {b.get('changed', b.get('skipped', '?'))}")
                c = await DeductService(db, company_id=cid).sync(
                    dry_run=args.dry_run)
                print(f"  deduct: {c.get('ok', c.get('skipped', '?'))}"
                      f" test={c.get('test_mode')}")
                s = await FbsSuppliesService(db, company_id=cid).sync_incremental(
                    dry_run=args.dry_run)
                print(f"  supplies: {s}")
                ok += 1
            except Exception as ex:
                print(f"[{comp['name'] or cid}] ERROR: {ex}")
                errors += 1
        print(f"TOTAL: ok={ok} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="FBS-связка (meta D3-D5)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
