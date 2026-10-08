"""Остатки WB по складам — порт wb-stock/sync (B1).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/stocks_sync.py
  DRY_RUN=1 .venv/bin/python backend/workers/stocks_sync.py
  Таймер: wbcms-stocks-sync (04:30, после cards)

Снепшот date=today, limit/offset=1000, пауза 21с. Таблица: wb_stocks (upsert).
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
    from backend.services.stocks_sync_service import StocksSyncService
    print("WB API: POST seller-analytics.../stocks-report/wb-warehouses"
          " → wb_stocks", flush=True)
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
                st = await StocksSyncService(db, company_id=cid).sync(
                    dry_run=args.dry_run,
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
    ap = argparse.ArgumentParser(description="Остатки WB по складам (stocks-report)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
