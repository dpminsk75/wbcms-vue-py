"""Поисковые запросы рекламы WB (normquery) — порт wb-adv-sync/queries.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/adv_queries_sync.py
  .venv/bin/python backend/workers/adv_queries_sync.py --date-from 2026-10-01 --date-to 2026-10-06  # бэкфилл
  DRY_RUN=1 .venv/bin/python backend/workers/adv_queries_sync.py  # опрос без записи
  Таймер: wbcms-adv-queries (03:45, окно 3д по дефолту)

Цикл по активным компаниям с api_key. Гейт токена (promotion, протухание,
правило 2ч для базовых) — backend/services/wb_sync_base.py.
Таблица: wb_campaign_query (upsert).
"""
import argparse
import asyncio
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    """Одна строка на запрос, дописывается по фазам (без \\r)."""
    def cb(i, n, stage, k, api, db, wait, msg=""):
        if stage == "send":
            print(f"  [{label}] запрос {i}/{n}: отправляю...", end=" ", flush=True)
        elif stage == "retry":
            print(f"[{msg}]", end=" ", flush=True)
        elif stage == "pause":
            left = (n - i) * (wait + api + db) / 60
            print(f"api {api:.1f}с → запись {db:.1f}с → пауза {wait:.0f}с, "
                  f"фраз {k} (осталось ~{left:.0f} мин)", flush=True)
        # api/db молчим — всё влезет в итоговую строку
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.adv_queries_service import AdvQueriesService
    if args.date_from is None and args.date_to is None:
        args.date_to = (date.today() - timedelta(days=1)).isoformat()
        args.date_from = (date.fromisoformat(args.date_to) - timedelta(days=2)).isoformat()
    print("WB API: POST advert.../normquery/stats → wb_campaign_query",
          flush=True)
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
                st = await AdvQueriesService(db, company_id=cid).sync(
                    date_from=args.date_from, date_to=args.date_to,
                    dry_run=args.dry_run,
                    progress=_make_progress(comp["name"] or str(cid)))
                if st.get("skipped"):
                    print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                    skipped += 1
                else:
                    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                    print(f"[{comp['name'] or cid}] items={st['items']} days={st['days']} "
                          f"upserted={st['upserted']} {st.get('token_type')}{warn}")
                    ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Поисковые запросы рекламы WB (normquery)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
