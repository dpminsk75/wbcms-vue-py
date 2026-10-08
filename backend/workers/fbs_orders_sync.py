"""Сборочные задания FBS — порт wb-orders-fbs/sync-orders (D3).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/fbs_orders_sync.py
  .venv/bin/python backend/workers/fbs_orders_sync.py --date-from 2026-07-01 --date-to 2026-07-10
  DRY_RUN=1 .venv/bin/python backend/workers/fbs_orders_sync.py
  Дефолт: сегодня с 00:00 МСК (до 5 утра — вчера+сегодня).

Таблица: wb_orders_fbs (upsert, supply_id null не затирает).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(i, n, stage, k, api, db, wait, msg=""):
        if stage in ("send", "retry"):
            print(f"  [{label}] [{msg}]", flush=True)
        elif stage == "pause":
            print(f"  [{label}] страница {i}: строк {k} (api {api:.1f}с)",
                  flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.fbs_orders_sync_service import FbsOrdersService
    print("WB API: GET marketplace.../orders → wb_orders_fbs", flush=True)
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
                st = await FbsOrdersService(db, company_id=cid).sync(
                    date_from=args.date_from, date_to=args.date_to,
                    dry_run=args.dry_run,
                    progress=_make_progress(comp["name"] or str(cid)))
                if st.get("skipped"):
                    print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                    skipped += 1
                else:
                    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                    print(f"[{comp['name'] or cid}] pages={st['pages']} "
                          f"(записано {st['saved']}) {st.get('token_type')}{warn}")
                    ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Сборочные задания FBS (marketplace/orders)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
