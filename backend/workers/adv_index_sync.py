"""Полный синк рекламы WB (count → details → fullstats) — порт wb-adv-sync.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/adv_index_sync.py
  .venv/bin/python backend/workers/adv_index_sync.py --stats-only --date-from 2026-07-24 --date-to 2026-07-25  # wb-adv-sync/stats
  DRY_RUN=1 .venv/bin/python backend/workers/adv_index_sync.py
  Таймер: wbcms-adv-index (каждые 4ч в :10, как крон `10 */4 * * *`)

Цикл по активным компаниям с api_key. Гейт promotion + паузы по методам
(details 2с, stats 21с; basic — 5мин/60мин + правило 2ч).
Таблицы: wb_campaign, wb_campaign_item, wb_campaign_stats(+nms).
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
            print(f"  [{label}] {text} [{i}/{n}]", flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.adv_index_service import AdvIndexService
    print("WB API: GET advert.../promotion/count + .../advert/v2/adverts"
          " + .../fullstats → wb_campaign(+item,+stats)", flush=True)
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
                st = await AdvIndexService(db, company_id=cid).sync_index(
                    date_from=args.date_from, date_to=args.date_to,
                    dry_run=args.dry_run, stats_only=args.stats_only,
                    progress=_make_progress(comp["name"] or str(cid)))
                if st.get("skipped"):
                    print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                    skipped += 1
                else:
                    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                    det = st.get("details") or {}
                    stats = st.get("stats") or {}
                    print(f"[{comp['name'] or cid}] campaigns={st.get('count')} "
                          f"items={det.get('items')} apps={stats.get('apps')} "
                          f"nms={stats.get('nms')} {st.get('token_type')}{warn}")
                    ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Полный синк рекламы WB (index)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--stats-only", action="store_true",
                    help="только fullstats за даты (wb-adv-sync/stats)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
