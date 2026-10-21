"""Search-report WB (позиции + фразы) — порт commands/WbParserController.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/search_report_sync.py                      # вчера
  .venv/bin/python backend/workers/search_report_sync.py --date 2026-10-14    # дата
  .venv/bin/python backend/workers/search_report_sync.py --date-from 2026-10-01 --date-to 2026-10-06  # бэкфилл
  DRY_RUN=1 .venv/bin/python backend/workers/search_report_sync.py            # опрос без записи
  Таймер: wbcms-search-report (daily 02:00)

Цикл по активным компаниям с api_key. Гейт токена (analytics, протухание,
правило 2ч для базовых) — backend/services/wb_sync_base.py.
Таблицы: wb_sr_report_summary/groups/items/item_phrases + wb_phrases_directory.
"""
import argparse
import asyncio
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(kind, done, total, msg):
        print(f"  [{label}] [{kind}] {done}/{total}: {msg}", flush=True)
    return cb


def _days(args) -> list[str]:
    if args.date_from or args.date_to:
        d1 = date.fromisoformat(args.date_from or args.date_to)
        d2 = date.fromisoformat(args.date_to or args.date_from)
    else:
        d2 = date.fromisoformat(args.date) if args.date \
            else date.today() - timedelta(days=1)
        d1 = d2
    if d1 > d2:
        raise ValueError(f"date_from {d1} позже date_to {d2}")
    out, cur = [], d1
    while cur <= d2:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.search_report_service import (
        SearchReportService, update_directory)
    days = _days(args)
    print(f"WB API: POST seller-analytics.../search-report/report + "
          f"product/search-texts -> wb_sr_report_* ({', '.join(days)})",
          flush=True)
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name FROM companies WHERE is_active = 1"
            " AND api_key IS NOT NULL AND api_key <> ''"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        ok, skipped, errors = 0, 0, 0
        for n, target in enumerate(days):
            if n > 0:
                time.sleep(5)  # пауза между днями как в PHP
            for comp in companies:
                cid = int(comp["id"])
                label = comp["name"] or str(cid)
                print(f"[{label}] {target}: старт...", flush=True)
                try:
                    st = await SearchReportService(db, company_id=cid).sync_date(
                        target, dry_run=args.dry_run,
                        progress=_make_progress(f"{label} {target}"))
                    if st.get("skipped"):
                        print(f"[{label}] SKIP: {st['skipped']}")
                        skipped += 1
                    else:
                        warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                        print(f"[{label}] nm={st['nm_ids']} req={st.get('requests')} "
                              f"items={st['items']} phrases={st['phrases']} "
                              f"{st.get('token_type')}{warn}")
                        ok += 1
                except Exception as e:
                    print(f"[{label}] ERROR: {e}")
                    errors += 1
        if not args.dry_run and not args.skip_directory:
            try:
                st = await update_directory(db)
                print(f"[directory] новых фраз: {st['inserted']}, "
                      f"обновлено: {st['updated']}")
            except Exception as e:
                print(f"[directory] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} "
              f"dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Search-report WB (позиции + фразы)")
    ap.add_argument("--date", default=None, help="одна дата YYYY-MM-DD (дефолт: вчера)")
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--skip-directory", action="store_true",
                    help="не перестраивать wb_phrases_directory")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    try:
        sys.exit(asyncio.run(run(args)))
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
