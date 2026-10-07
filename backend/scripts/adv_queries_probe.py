"""Разовый зонд normquery: сколько пар, что отвечает WB на 2 пары, как парсится.

Только чтение БД + 1 POST (1 запрос из лимита). Запуск:
  .venv/bin/python backend/scripts/adv_queries_probe.py 1 2026-10-06
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def main() -> None:
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    day = sys.argv[2] if len(sys.argv) > 2 else None
    if day is None:
        from datetime import date, timedelta
        day = (date.today() - timedelta(days=1)).isoformat()
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.adv_queries_service import AdvQueriesService, NORMQUERY_URL
    from backend.services.wb_sync_base import post_json
    async with get_session() as db:
        key = (await db.execute(
            text("SELECT api_key FROM companies WHERE id=:c"), {"c": cid})).first()
        token = ((key[0] if key else "") or "").strip()
        svc = AdvQueriesService(db, cid)
        items = await svc._items()
        print(f"items={len(items)} sample={items[:3]}")
        if not items:
            return
        data = post_json(NORMQUERY_URL, {"from": day, "to": day, "items": items[:2]},
                         token, log=print)
        s = json.dumps(data, ensure_ascii=False)
        print(f"keys={list(data.keys()) if isinstance(data, dict) else type(data)} len={len(s)}")
        print(s[:2000])
        rows = svc._rows(data.get("stats") if isinstance(data, dict) else [], day)
        print(f"parsed_rows={len(rows)} sample={rows[:2]}")


if __name__ == "__main__":
    asyncio.run(main())
