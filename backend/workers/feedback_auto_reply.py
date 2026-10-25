"""Фоновый воркер автоответов — порт commands/WbAutoReplyController (process/process-range/reply).

Запуск (на сервере, после переноса cron):
  python3 backend/workers/feedback_auto_reply.py --date 2026-09-18
  python3 backend/workers/feedback_auto_reply.py --date-from 2026-09-10 --date-to 2026-09-17
  python3 backend/workers/feedback_auto_reply.py --feedback-id jB4SVlEFyWfyyvKhTvst [--force]
  DRY_RUN=1 python3 backend/workers/feedback_auto_reply.py ...  # только sync+select+match+build, без POST

Цикл по активным компаниям с api_key (как processPeriod:84-97):
sync (wb_feedbacks/sync — отдельно, см. feedback_sync_service) уже должен
прогнать отзывы; воркер делает: select_pending → match+build → send → verify → mark.
Идемпотентность: повторный прогон видит is_auto_replied=1/answer и пропускает.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def process_company(db, company: dict, date_from: str, date_to: str, dry_run: bool) -> dict:
    from backend.services.feedback_process_service import FeedbackProcessService
    from backend.services.feedback_reply_service import FeedbackReplyService
    from backend.services.feedback_wb_sender import FeedbackWbSender
    cid = int(company["id"])
    pending = await FeedbackProcessService(db, company_id=cid).select_pending(date_from, date_to)
    print(f"[{company['name']}] pending: {len(pending)}")
    stats = {"pending": len(pending), "sent": 0, "skipped": 0, "errors": 0}
    if not pending:
        return stats
    matcher = FeedbackReplyService(db, company_id=cid)
    sender = FeedbackWbSender(db, api_key=company.get("api_key") or "")
    for fb in pending:
        gen = await matcher.generate_text(dict(fb), seed=None)
        if not gen["text"]:
            reason = f"stop={gen.get('stop_hit')}" if gen.get("stop_hit") else f"rating={fb.get('productValuation')}"
            print(f"  skip {fb['id']}: no rule ({reason})")
            stats["skipped"] += 1
            continue
        if dry_run:
            print(f"  [dry] {fb['id']} rule={gen['rule']['id']}: {gen['text'][:80]}")
            continue
        res = await sender.send_answer(dict(fb), gen["text"], gen["rule"]["id"])
        if res["ok"]:
            print(f"  [sent] {fb['id']} rule={gen['rule']['id']}")
            stats["sent"] += 1
        else:
            print(f"  [error] {fb['id']} stage={res['stage']} http={res.get('http_code')}")
            stats["errors"] += 1
    await db.commit()
    return stats


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    if args.date:
        args.date_from = args.date_to = args.date
    if not args.date_from:
        from datetime import date as _date
        args.date_from = args.date_to = _date.today().isoformat()
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name, api_key FROM companies WHERE is_active = 1"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        companies = [c for c in companies if c.get("api_key")]
        if args.feedback_id:
            from backend.services.feedback_reply_service import FeedbackReplyService
            from backend.services.feedback_wb_sender import FeedbackWbSender
            row = (await db.execute(text(
                "SELECT f.*, c.title AS card_title, c.brand AS card_brand FROM wb_feedbacks f"
                " LEFT JOIN wbcards c ON c.nmID = f.nmID WHERE f.id=:id LIMIT 1"),
                {"id": args.feedback_id})).mappings().first()
            if not row:
                print(f"not found: {args.feedback_id}")
                return 2
            fb = dict(row)
            comp = next((c for c in companies if int(c["id"]) == int(fb.get("company_id") or 0)), None)
            if not comp:
                print(f"company inactive/no key for feedback {args.feedback_id}")
                return 2
            if str(fb.get("answer") or "").strip() not in ("", "null") and not args.force:
                print("already answered (use --force)")
                return 2
            gen = await FeedbackReplyService(db, company_id=int(comp["id"])).generate_text(fb)
            if not gen["text"]:
                print("no rule matched")
                return 2
            print(f"rule={gen['rule']['id']}: {gen['text']}")
            if args.dry_run:
                return 0
            sender = FeedbackWbSender(db, api_key=comp["api_key"])
            res = await sender.send_answer(fb, gen["text"], gen["rule"]["id"])
            print(res)
            await db.commit()
            return 0 if res["ok"] else 1
        total = {"pending": 0, "sent": 0, "skipped": 0, "errors": 0}
        for comp in companies:
            st = await process_company(
                db, dict(comp), args.date_from, args.date_to, args.dry_run)
            for k in total:
                total[k] += st[k]
        print("TOTAL:", total)
        return 0 if total["errors"] == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Автоответы на отзывы WB (порт wb-auto-reply)")
    ap.add_argument("--date", default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--feedback-id", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
