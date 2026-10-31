"""Синхронизация вопросов WB (feedbacks-api: /api/v1/questions).

Запуск (на сервере, только venv; в таймере — см. deploy/wbcms-questions-sync.service):
  .venv/bin/python backend/workers/questions_sync.py                        # свежие, 10 дней
  .venv/bin/python backend/workers/questions_sync.py --company-id 1
  .venv/bin/python backend/workers/questions_sync.py --mode fresh --date-from -7
  .venv/bin/python backend/workers/questions_sync.py --mode full            # вся история
  .venv/bin/python backend/workers/questions_sync.py --mode full --window-days 30
  .venv/bin/python backend/workers/questions_sync.py --one 2ncBtX4B9I0UHoornoqG
  DRY_RUN=1 .venv/bin/python backend/workers/questions_sync.py --mode full  # без записи в БД

Даты вида «-2» = N дней назад.

API:
  GET feedbacks-api.../api/v1/questions?isAnswered=false|true&take=500&skip=N&order=dateAsc&dateFrom=&dateTo=
  GET feedbacks-api.../api/v1/question?id=<id>
Таблица: wb_questions (PK (company_id, id)), upsert по алиасу строки.
Границы суток — МСК. Гейтинг: категория «feedbacks» в company_wb_tokens.
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


_T0 = time.monotonic()


def _progress(stage: str, sub: str, count: int):
    el = int(time.monotonic() - _T0)
    print(f"  [{stage} {sub}] вопросов: {count}  (+{el // 60}м{el % 60:02d}с)",
          flush=True)


async def run(args) -> int:
    from backend.database import get_session
    from sqlalchemy import text

    print("WB API: GET feedbacks-api.../api/v1/questions → wb_questions", flush=True)
    ok, skipped, errors = 0, 0, 0
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name FROM companies WHERE is_active = 1"
            " AND api_key IS NOT NULL AND api_key <> ''"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        # только чтение — закрываем транзакцию, дальше воркер идёт в сеть к WB
        await db.commit()
    for comp in companies:
        cid = int(comp["id"])
        print(f"[{comp['name'] or cid}] режим {args.mode}"
              f"{' (dry-run)' if args.dry_run else ''}", flush=True)
        # попытка 2 — с НОВОЙ сессией: mysql мог перезапуститься посреди прогона
        for attempt in (1, 2):
            try:
                async with get_session() as db:
                    from backend.services.questions_sync_service import QuestionsSyncService
                    svc = QuestionsSyncService(db, company_id=cid)
                    res = await _run_company(svc, comp, cid, args)
                if res == "skipped":
                    skipped += 1
                else:
                    ok += 1
                break
            except Exception as e:
                if attempt == 1:
                    print(f"[{comp['name'] or cid}] сбой: {e} — новая сессия и повтор",
                          flush=True)
                    await asyncio.sleep(5)
                    continue
                print(f"[{comp['name'] or cid}] ERROR: {e}", flush=True)
                errors += 1
    print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}",
          flush=True)
    return 0 if errors == 0 else 1


async def _run_company(svc, comp, cid, args) -> str:
    """Один прогон по компании. Возвращает 'ok' или 'skipped'."""
    from backend.services.wb_sync_base import company_sync_plan
    if args.one:
        plan = await company_sync_plan(svc.db, cid, "feedbacks", 1)
        if plan.get("skip"):
            print(f"[{comp['name'] or cid}] SKIP: {plan['skip']}", flush=True)
            return "skipped"
        st = await svc.sync_one(plan["token"], args.one, dry_run=args.dry_run)
        print(f"[{comp['name'] or cid}] один вопрос: {st}", flush=True)
        return "ok"
    st = await svc.sync(
        mode=args.mode, date_from=args.date_from, date_to=args.date_to,
        nm_id=args.nm_id, window_days=args.window_days,
        max_windows=args.max_windows, dry_run=args.dry_run,
        progress=_progress)
    if st.get("skipped"):
        print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}", flush=True)
        return "skipped"
    fresh, full = st.get("fresh") or {}, st.get("full") or {}
    cnt = st.get("wb_count") or {}
    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
    parts = []
    if fresh:
        parts.append(f"{fresh.get('period')}: fetched={fresh.get('fetched')} "
                     f"saved={fresh.get('saved')}")
    if full:
        parts.append(f"{full.get('period')}: fetched={full.get('fetched')} "
                     f"saved={full.get('saved')} окон={full.get('windows')} "
                     f"стоп={full.get('stopped')}")
    if cnt:
        parts.append(f"WB считает: без ответа={cnt.get('unanswered')} "
                     f"с ответом={cnt.get('answered')}")
    print(f"[{comp['name'] or cid}] {' | '.join(parts)}{warn}", flush=True)
    return "ok"


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
    ap = argparse.ArgumentParser(description="Синк вопросов WB (feedbacks-api)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None,
                    help="YYYY-MM-DD или «-N» (N дней назад; деф: −10 дней)")
    ap.add_argument("--date-to", default=None, help="YYYY-MM-DD (деф: сегодня)")
    ap.add_argument("--mode", choices=("fresh", "full"), default="fresh",
                    help="fresh — окно дат (по умолчанию), full — вся история окнами")
    ap.add_argument("--window-days", type=int, default=90,
                    help="размер окна в днях для режима full (деф: 90)")
    ap.add_argument("--max-windows", type=int, default=200,
                    help="страховка по числу окон в режиме full (деф: 200)")
    ap.add_argument("--nm-id", type=int, default=None,
                    help="только по одной карточке (nmID)")
    ap.add_argument("--one", default=None,
                    help="дозагрузить один вопрос по id (GET /api/v1/question)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    args.date_from = _rel_date(args.date_from)
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
