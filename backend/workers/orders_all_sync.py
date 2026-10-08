"""Заказы целиком: fetch → feed → fbs orders → fbs statuses → deduct (D1-D5 подряд).

Мета для 5-мин таймера (как wb-sync-all): FAST вчера→сегодня по всем компаниям.
Флаг --full = 3 дня (ночной проход). Ручное тестирование — отдельными воркерами.
"""
import argparse
import asyncio
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.orders_fetch_sync_service import OrdersFetchService
    from backend.services.order_feed_sync_service import OrderFeedService
    from backend.services.fbs_orders_sync_service import FbsOrdersService
    from backend.services.fbs_statuses_sync_service import FbsStatusesService
    from backend.services.deduct_sync_service import DeductService
    if args.full:
        df, dt = None, None  # дефолты сервисов = 3 дня
    else:
        df = (date.today() - timedelta(days=1)).isoformat()
        dt = date.today().isoformat()  # вчера 00:00 → сегодня 00:00, как PHP meta
    print(f"WB API: заказы связкой (fetch+feed+fbs+статусы+вычет) {df or '-3д'}..{dt or 'today'}",
          flush=True)
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
                a = await OrdersFetchService(db, company_id=cid).sync(
                    date_from=df, date_to=dt, dry_run=args.dry_run)
                print(f"  fetch: {a.get('saved', a.get('skipped', '?'))}")
                b = await OrderFeedService(db, company_id=cid).sync(
                    date_from=df, date_to=dt, dry_run=args.dry_run)
                print(f"  feed: {b.get('saved', b.get('skipped', '?'))}")
                c = await FbsOrdersService(db, company_id=cid).sync(
                    date_from=df, date_to=dt, dry_run=args.dry_run)
                print(f"  fbs: {c.get('saved', c.get('skipped', '?'))}")
                d = await FbsStatusesService(db, company_id=cid).sync(
                    dry_run=args.dry_run)
                print(f"  statuses: {d.get('changed', d.get('skipped', '?'))}")
                e = await DeductService(db, company_id=cid).sync(
                    dry_run=args.dry_run)
                print(f"  deduct: {e.get('ok', e.get('skipped', '?'))}")
                ok += 1
            except Exception as ex:
                print(f"[{comp['name'] or cid}] ERROR: {ex}")
                errors += 1
        print(f"TOTAL: ok={ok} errors={errors} dry_run={args.dry_run} full={args.full}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Заказы целиком (meta D1-D5)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--full", action="store_true",
                    help="полный проход 3 дня (иначе FAST вчера→сегодня)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
