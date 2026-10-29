"""Синхронизация отзывов WB — порт wb-feedbacks/sync (WbFeedbacksController).

Запуск (на сервере, только venv; в таймере — см. deploy/wbcms-feedback-sync.service):
  .venv/bin/python backend/workers/feedback_sync.py                     # порт: последние 10 дней
  .venv/bin/python backend/workers/feedback_sync.py --company-id 1
  .venv/bin/python backend/workers/feedback_sync.py --date-from 2026-10-01 --date-to 2026-10-26
  .venv/bin/python backend/workers/feedback_sync.py --current-only --date-from -2  # для таймера
  .venv/bin/python backend/workers/feedback_sync.py --archive-only      # только архив
  .venv/bin/python backend/workers/feedback_sync.py --no-current        # только архив
  DRY_RUN=1 .venv/bin/python backend/workers/feedback_sync.py           # без записи в БД

Даты вида «-2» = N дней назад (удобно для таймера: каждый раз тянуть только
свежие отзывы, без архива).

API:
  GET feedbacks-api.../api/v1/feedbacks?isAnswered=false|true&take=500&skip=N&dateFrom=<unix>&dateTo=<unix>
  GET feedbacks-api.../api/v1/feedbacks/archive?take=500&skip=N&order=dateDesc
Таблица: wb_feedbacks (PK id varchar(64)), upsert по алиасу строки.
Границы суток — МСК. Гейтинг: категория «feedbacks» в company_wb_tokens.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _progress(stage: str, sub: str, count: int):
    print(f"  [{stage} {sub}] страниц/отзывов: {count}", flush=True)


async def run(args) -> int:
    from backend.database import get_session
    from backend.services.feedback_sync_service import FeedbackSyncService
    from sqlalchemy import text

    print("WB API: GET feedbacks-api.../api/v1/feedbacks (+/archive) → wb_feedbacks",
          flush=True)
    ok, skipped, errors = 0, 0, 0
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name FROM companies WHERE is_active = 1"
            " AND api_key IS NOT NULL AND api_key <> ''"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        for comp in companies:
            cid = int(comp["id"])
            print(f"[{comp['name'] or cid}] период {args.date_from or '−10д'} … "
                  f"{args.date_to or 'сегодня'}", flush=True)
            try:
                st = await FeedbackSyncService(db, company_id=cid).sync(
                    date_from=args.date_from, date_to=args.date_to,
                    include_current=not args.no_current,
                    include_archive=not args.current_only,
                    max_archive_pages=args.max_archive_pages,
                    dry_run=args.dry_run,
                    progress=_progress)
                if st.get("skipped"):
                    print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}", flush=True)
                    skipped += 1
                    continue
                cur, arch = st.get("current") or {}, st.get("archive") or {}
                warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                sample = f" first_created={cur['first_created']}" if cur.get("first_created") else ""
                print(f"[{comp['name'] or cid}] current: fetched={cur.get('fetched')} "
                      f"saved={cur.get('saved')} стр.{cur.get('pages')}{sample} | "
                      f"archive: fetched={arch.get('fetched')} saved={arch.get('saved')} "
                      f"стр.{arch.get('pages')} stop={arch.get('stopped_by_date')}"
                      f"{warn}", flush=True)
                ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}", flush=True)
                errors += 1
    print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}",
          flush=True)
    return 0 if errors == 0 else 1


def _rel_date(value):
    """«-2» → дата 2 дня назад (YYYY-MM-DD). Остальное — как есть."""
    if not value:
        return None
    s = str(value).strip()
    if s.startswith("-") and s[1:].isdigit():
        from datetime import date, timedelta
        return (date.today() - timedelta(days=int(s[1:]))).isoformat()
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description="Синк отзывов WB (feedbacks-api)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None,
                    help="YYYY-MM-DD или «-N» (N дней назад; деф: −10 дней)")
    ap.add_argument("--date-to", default=None, help="YYYY-MM-DD (деф: сегодня)")
    ap.add_argument("--archive-only", action="store_true",
                    help="синоним --no-current (как в PHP)")
    ap.add_argument("--no-current", action="store_true",
                    help="не синкать актуальные, только архив")
    ap.add_argument("--current-only", action="store_true",
                    help="только актуальные, без архива (для таймера)")
    ap.add_argument("--max-archive-pages", type=int, default=200,
                    help="страховка от бесконечного цикла архива (def 200)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    if args.archive_only:
        args.no_current = True
    if args.current_only:
        args.no_current = False
    args.date_from = _rel_date(args.date_from)
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
