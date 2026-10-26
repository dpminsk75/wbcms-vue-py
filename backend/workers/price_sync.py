"""Цены и скидки WB — порт wb-price/sync.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/price_sync.py
  .venv/bin/python backend/workers/price_sync.py --company-id 1
  .venv/bin/python backend/workers/price_sync.py --nm-id 526443466
  DRY_RUN=1 .venv/bin/python backend/workers/price_sync.py
  Таймер: wbcms-price-sync (4 раза в сутки: 00:30, 06:30, 12:30, 18:30)

GET discounts-prices-api.../list/goods/filter?limit=300&offset=N,
Authorization = raw companies.api_key, пауза 6с между страницами.
Таблица: wb_price_history (история цен — при смене цены старая запись
закрывается is_latest=0, появляется новая is_latest=1).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(page: int, rows: int, stage: str, api: float, wait: float):
        print(f"  [{label}] стр.{page}: товаров {rows}, api {api:.1f}с, "
              f"пауза {wait:.0f}с", flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.price_sync_service import PriceSyncService, acquire_lock

    lock = None
    if not args.no_lock:
        lock = acquire_lock(args.lock_file)
        if lock is None:
            print("Другой прогон уже работает — выходим.", flush=True)
            return 0
    print("WB API: GET discounts-prices.../list/goods/filter → wb_price_history",
          flush=True)
    ok, skipped, errors = 0, 0, 0
    try:
        async with get_session() as db:
            companies = (await db.execute(text(
                "SELECT id, name FROM companies WHERE is_active = 1"
                " AND api_key IS NOT NULL AND api_key <> ''"
                + (" AND id = :cid" if args.company_id else "")
                + " ORDER BY id"),
                ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
            for comp in companies:
                cid = int(comp["id"])
                print(f"[{comp['name'] or cid}] старт...", flush=True)
                try:
                    st = await PriceSyncService(db, company_id=cid).sync(
                        dry_run=args.dry_run, nm_id=args.nm_id,
                        progress=_make_progress(comp["name"] or str(cid)))
                    if st.get("skipped"):
                        print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                        skipped += 1
                        continue
                    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                    print(f"[{comp['name'] or cid}] fetched={st['fetched']} "
                          f"новых={st['new']} изменилось={st['changed']} "
                          f"без изменений={st['same']} стр.={st['pages']} "
                          f"{st.get('token_type')}{warn}", flush=True)
                    ok += 1
                except Exception as e:
                    print(f"[{comp['name'] or cid}] ERROR: {e}", flush=True)
                    errors += 1
    finally:
        if lock is not None:
            try:
                lock.close()
            except Exception:
                pass
    print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
    return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Цены и скидки WB (discounts-prices)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--nm-id", type=int, default=None,
                    help="точечно один артикул (filterNmID)")
    ap.add_argument("--lock-file", default="/tmp/wbcms-price-sync.lock")
    ap.add_argument("--no-lock", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
