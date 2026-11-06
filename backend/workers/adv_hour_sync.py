"""Почасовые дельты рекламы WB: снимок накопительных счётчиков минус предыдущий.

WB отдаёт суточные счётчики накопительно с 00:00 — значит разница между
двумя снимками (час назад и сейчас) и есть трафик за прошедший час.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/adv_hour_sync.py
  .venv/bin/python backend/workers/adv_hour_sync.py --company-id 1
  DRY_RUN=1 .venv/bin/python backend/workers/adv_hour_sync.py
  Таймер: wbcms-adv-hour (каждый час, :55)

Таблицы: wb_adv_campaign_hour (бакеты), wb_adv_campaign_hour_snap (снимки).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(kind, i, n, text):
        if kind == "retry":
            print(f"  [{label}] [{text}]", flush=True)
        else:
            print(f"  [{label}] {text}", flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.adv_hour_sync_service import AdvHourSyncService
    print("WB API: GET advert.../fullstats (сегодня) → почасовые дельты", flush=True)
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
            name = comp["name"] or str(cid)
            print(f"[{name}] старт...", flush=True)
            try:
                st = await AdvHourSyncService(db, company_id=cid).sync(
                    dry_run=args.dry_run, progress=_make_progress(name))
                if st.get("skipped"):
                    print(f"[{name}] SKIP: {st['skipped']}")
                    skipped += 1
                    continue
                print(f"[{name}] кампаний={st.get('campaigns')} "
                      f"бакетов={st.get('buckets')} снимков={st.get('snaps')} "
                      f"отрицательных пропущено={st.get('negative_skipped')} "
                      f"пропусков часов={st.get('gaps')}")
                ok += 1
            except Exception as e:
                print(f"[{name}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Почасовые дельты рекламы WB")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
