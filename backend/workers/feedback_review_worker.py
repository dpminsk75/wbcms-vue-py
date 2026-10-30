"""Фоновый разбор отзывов через ИИ (эмоциональность / конструктивность / тональность).

Запуск (на сервере, в venv):
  .venv/bin/python backend/workers/feedback_review_worker.py                       # новые отзывы
  .venv/bin/python backend/workers/feedback_review_worker.py --limit 200           # порция за прогон
  .venv/bin/python backend/workers/feedback_review_worker.py --backfill           # всё накопленное
  .venv/bin/python backend/workers/feedback_review_worker.py --backfill --date-from 2026-05-01
  .venv/bin/python backend/workers/feedback_review_worker.py --company-id 1
  DRY_RUN=1 .venv/bin/python backend/workers/feedback_review_worker.py --limit 5  # только показать очередь

Очередь: отзывы с текстом, для которых нет строки в wb_feedback_ai_review
(или status='pending'). Разбор — по одному отзыву за вызов модели.

Обычный прогон (таймер) берёт только компании с feedback_auto_review=1.
--backfill разбирает всё накопленное (период ограничивается --date-from/--date-to).

Ошибки разбора пишутся status='error' и больше не обрабатываются: вернуть в очередь
можно вручную (кнопка «Вернуть в очередь» на /wb-feedback-answers).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run(args) -> int:
    from backend.database import get_session
    from backend.services.feedback_review_service import FeedbackReviewService
    from sqlalchemy import text

    async with get_session() as db:
        cid_sql = "" if args.company_id is None else " AND id = :cid"
        # обычный прогон — только компании с включённым авторазбором
        auto_sql = "" if args.backfill else " AND feedback_auto_review = 1"
        try:
            companies = (await db.execute(text(
                "SELECT id, name FROM companies WHERE is_active = 1"
                " AND api_key IS NOT NULL AND api_key <> ''"
                + cid_sql + auto_sql
                + " ORDER BY id"),
                ({"cid": args.company_id} if args.company_id is not None else {})
            )).mappings().all()
        except Exception as e:
            # чаще всего — не применена миграция 20261041 (нет колонки feedback_auto_review)
            print(f"Не удалось получить список компаний: {type(e).__name__}: {e}", flush=True)
            print("Проверь, применена ли миграция backend/migrations/20261041_feedback_ai_review.sql",
                  flush=True)
            return 1
        if not companies:
            print("Нет компаний к обработке"
                  + (" (авторазбор выключен — feedback_auto_review=0)" if not args.backfill else ""),
                  flush=True)
            return 0

        total_ok = 0
        total_err = 0
        for comp in companies:
            cid = int(comp["id"])
            svc = FeedbackReviewService(db, company_id=cid)
            print(f"[{comp['name'] or cid}] разбор отзывов"
                  f"{' (backfill)' if args.backfill else ''}:", flush=True)
            try:
                if args.dry_run:
                    st = await svc.queue_preview(limit=args.limit,
                                                 date_from=args.date_from,
                                                 date_to=args.date_to)
                    print(f"  очередь: показано {len(st['items'])}"
                          f"{' (ещё есть)' if st['has_more'] else ''}", flush=True)
                    for it in st["items"]:
                        print(f"  - {it['created_at']} nm {it['nm_id']}: "
                              f"{(it['text'] or '')[:80]}", flush=True)
                    continue
                st = await svc.review_pending(limit=args.limit,
                                              date_from=args.date_from,
                                              date_to=args.date_to)
                print(f"  взято={st['taken']} разобрано={st['ok']} ошибок={st['errors']}", flush=True)
                if st.get("balance_error"):
                    print(f"  STOP: нет токенов у ИИ ({st.get('balance_reason')}) — "
                          f"батч остановлен, разбор продолжится после паузы", flush=True)
                    break
                if st.get("fatal"):
                    print(f"  STOP: {st['fatal']} — батч остановлен, "
                          f"проверь промпт и модель компании", flush=True)
                    break
                total_ok += st["ok"]
                total_err += st["errors"]
            except Exception as e:
                print(f"  ERROR: {type(e).__name__}: {e}", flush=True)
        if not args.dry_run:
            print(f"TOTAL: ok={total_ok} errors={total_err}", flush=True)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Разбор отзывов через ИИ (фон)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--limit", type=int, default=50, help="отзывов за один прогон (1…500)")
    ap.add_argument("--backfill", action="store_true",
                    help="разбирать всё накопленное (в т.ч. компании без авторазбора)")
    ap.add_argument("--date-from", default=None, help="YYYY-MM-DD (только с --backfill)")
    ap.add_argument("--date-to", default=None, help="YYYY-MM-DD (только с --backfill)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
