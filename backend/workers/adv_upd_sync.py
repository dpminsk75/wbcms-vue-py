"""История списаний по рекламе WB (adv/v1/upd) — факт списаний с баланса,
бонусов, счёта и кэшбэка. Нужен, чтобы сверять «расход по статистике» с
реальным списанием и считать чистые расходы.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/adv_upd_sync.py
  .venv/bin/python backend/workers/adv_upd_sync.py --date-from 2026-11-01 --date-to 2026-11-05
  DRY_RUN=1 .venv/bin/python backend/workers/adv_upd_sync.py
  Таймер: wbcms-adv-upd (ежедневно, утром)

Таблица: wb_adv_upd.
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
    from backend.services.adv_upd_sync_service import AdvUpdSyncService
    print("WB API: GET advert.../v1/upd → wb_adv_upd", flush=True)
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
                st = await AdvUpdSyncService(db, company_id=cid).sync(
                    date_from=args.date_from, date_to=args.date_to,
                    dry_run=args.dry_run, progress=_make_progress(name))
                if st.get("skipped"):
                    print(f"[{name}] SKIP: {st['skipped']}")
                    skipped += 1
                    continue
                print(f"[{name}] {st.get('date_from')}..{st.get('date_to')} "
                      f"списаний={st.get('rows')} на {st.get('total')} ₽ "
                      f"(кэшбэк {st.get('cashback')} ₽)")
                pay = st.get("payments") or {}
                if pay.get("error"):
                    print(f"  [{name}] payments: ОШИБКА — {pay['error']}")
                elif pay.get("skipped"):
                    print(f"  [{name}] payments: SKIP — {pay['skipped']}")
                elif pay.get("rows") is not None:
                    print(f"  [{name}] пополнений={pay.get('rows')} "
                          f"на {pay.get('total')} ₽")
                ok += 1
            except Exception as e:
                print(f"[{name}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="История списаний по рекламе WB (adv/v1/upd)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
