"""Карточки WB связкой A1+A2+A3+A4 — порт wb/sync-cards.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/cards_sync.py
  .venv/bin/python backend/workers/cards_sync.py --list-only       # только A1
  .venv/bin/python backend/workers/cards_sync.py --nds-only        # только A2
  .venv/bin/python backend/workers/cards_sync.py --sizes-backfill  # только A3 бэкфилл
  DRY_RUN=1 .venv/bin/python backend/workers/cards_sync.py
  Таймер: wbcms-cards-sync (daily 04:10)

Фазы на компанию: list (cursor API -> wbcards+history+sizes, деактивация
пропавших) -> nds (БД) -> subjects (глобальные, один раз).
Таблицы: wbcards, wbcards_history, wbcards_nds, wbcards_sizes, wb_subject_catalog.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(kind, i, n, text):
        print(f"  [{label}] [{text}]" if kind == "retry" else f"  [{label}] {text} [{i}/{n}]",
              flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.cards_sync_service import CardsSyncService
    print("WB API: POST content.../get/cards/list → wbcards(+history,nds,sizes)"
          " + subjects", flush=True)
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name FROM companies WHERE is_active = 1"
            " AND api_key IS NOT NULL AND api_key <> ''"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        ok, skipped, errors = 0, 0, 0
        first_cid = None
        for comp in companies:
            cid = int(comp["id"])
            if first_cid is None:
                first_cid = cid
            print(f"[{comp['name'] or cid}] старт...", flush=True)
            try:
                svc = CardsSyncService(db, company_id=cid)
                if args.sizes_backfill:
                    st = await svc.sync_sizes_backfill()
                    print(f"[{comp['name'] or cid}] sizes: cards={st['cards']} skus={st['skus']}")
                else:
                    if not args.nds_only:
                        st = await svc.sync_list(
                            dry_run=args.dry_run,
                            progress=_make_progress(comp["name"] or str(cid)))
                        if st.get("skipped"):
                            print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                            skipped += 1
                            continue
                        print(f"[{comp['name'] or cid}] cards={st['fetched']} "
                              f"deactivated={st['deactivated']} {st.get('token_type')}")
                    if not args.list_only:
                        nd = await svc.sync_nds(dry_run=args.dry_run)
                        print(f"[{comp['name'] or cid}] nds: processed={nd['processed']} "
                              f"updated={nd['updated']}")
                ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        if first_cid is not None and not args.nds_only and not args.sizes_backfill \
                and not args.list_only:
            from backend.services.commission_tariffs_service import CommissionTariffsService
            try:
                st = await CommissionTariffsService(db, company_id=first_cid).sync_subjects(
                    dry_run=args.dry_run)
                print(f"[subjects] {st}")
            except Exception as e:
                print(f"[subjects] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Карточки WB связкой (list+nds+sizes+subjects)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--nds-only", action="store_true")
    ap.add_argument("--sizes-backfill", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
