"""Новости портала продавцов WB — hourly-синк в wb_news.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/news_sync.py
  DRY_RUN=1 .venv/bin/python backend/workers/news_sync.py  # опрос без записи
  Таймер: wbcms-news (hourly в :05)

Новости глобальные: один прогон любым живым токеном (доки — любая категория).
Таблица: wb_news (upsert по id WB).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress():
    def cb(kind, i, n, text):
        print(f"  [news] [{text}]" if kind == "retry" else f"  [news] {text}",
              flush=True)
    return cb


async def run(args) -> int:
    from backend.database import get_session
    from backend.services.news_service import NewsService
    async with get_session() as db:
        try:
            st = await NewsService(db).sync(
                dry_run=args.dry_run, since=args.since, progress=_make_progress())
            print(f"TOTAL: via_company={st['via_company']} pages={st['pages']} "
                  f"upserted={st['upserted']} dates={st.get('min_date')}..{st.get('max_date')} "
                  f"dry_run={args.dry_run}")
            return 0
        except Exception as e:
            print(f"ERROR: {e}")
            return 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Новости WB (communications/news)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    ap.add_argument("--since", default=None,
                    help="стартовая дата бэкфилла YYYY-MM-DD (дефолт: MAX(date)-1д, пустая таблица: -30д)")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
