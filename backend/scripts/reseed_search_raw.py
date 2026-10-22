#!/usr/bin/env python3
"""Пересборка наблюдений выдачи WB из сохранённых файлов сырья.

Зачем: расширение уже сложило файлы в
`backend/runtime/seo_search_raw/<company_id>/<YYYY-MM-DD>/<stamp>_<kind>_<slug>.json`
(+ `.meta.json` с фразой, видом и автором). Если мы поменяли правила разбора
(новые ключи фасетов, автор в JSON-пути и т.п.) — данные можно пересобрать
из файлов, **не заставляя человека искать заново**.

  cd /var/www/wb/wbcms-py
  .venv/bin/python backend/scripts/reseed_search_raw.py --company-id 1
  .venv/bin/python backend/scripts/reseed_search_raw.py --company-id 1 --date 2026-10-22
  .venv/bin/python backend/scripts/reseed_search_raw.py --company-id 1 --dry-run
"""

import argparse
import asyncio
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal  # noqa: E402
from backend.services import search_raw_service as svc  # noqa: E402
from sqlalchemy import text  # noqa: E402

RAW_ROOT = ROOT / "backend" / "runtime" / "seo_search_raw"


def _meta_files(base: pathlib.Path) -> list:
    return sorted(base.glob("*.meta.json"))


async def _run(company_id: int, date: str | None, dry_run: bool) -> None:
    base = RAW_ROOT / str(company_id)
    if not base.exists():
        print(f"нет папки {base}")
        return
    days = [base / date] if date else sorted([d for d in base.iterdir() if d.is_dir()])
    total = {"catalog": 0, "filters": 0, "shelfs": 0}
    async with SessionLocal() as db:
        for day in days:
            for meta_path in _meta_files(day):
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"  !! {meta_path.name}: {e}")
                    continue
                raw_path = meta_path.with_name(meta_path.name[: -len(".meta.json")] + ".json")
                if not raw_path.exists():
                    print(f"  !! нет тела ответа: {raw_path.name}")
                    continue
                kind = str(meta.get("kind") or "")
                phrase = str(meta.get("phrase") or "")
                uid = meta.get("created_by")
                tok = meta.get("ext_token_id")
                if uid is None or tok is None:
                    # в старых файлах автора нет (добавили позже) — берём из уже
                    # записанных строк по этой фразе
                    row = (await db.execute(text(
                        "SELECT created_by, ext_token_id FROM wb_competitor_position "
                        "WHERE company_id=:cid AND query_phrase=:ph "
                        "AND (ext_token_id IS NOT NULL OR created_by IS NOT NULL) "
                        "ORDER BY id DESC LIMIT 1"
                    ), {"cid": company_id, "ph": svc.capture_service._norm_phrase(phrase)})).mappings().first()
                    if row:
                        uid = uid if uid is not None else row["created_by"]
                        tok = tok if tok is not None else row["ext_token_id"]
                raw = raw_path.read_text(encoding="utf-8")
                try:
                    data = json.loads(raw)
                except Exception as e:
                    print(f"  !! {raw_path.name}: битый JSON: {e}")
                    continue
                file_name = str(raw_path.relative_to(svc.RAW_ROOT))
                if dry_run:
                    print(f"  {day.name} {kind:8} «{phrase}» → {raw_path.name}")
                    continue
                try:
                    if kind == "catalog":
                        products = data.get("products") if isinstance(data, dict) else []
                        n = await svc._enrich_positions(db, company_id, uid, tok, phrase, products or [], day.name)
                        total["catalog"] += 1
                        print(f"  {day.name} catalog «{phrase}»: позиций {n}")
                    elif kind == "filters":
                        await svc._save_filters(db, company_id, uid, tok, phrase, data, file_name, day.name)
                        total["filters"] += 1
                        print(f"  {day.name} filters «{phrase}»: ok")
                    elif kind == "shelfs":
                        await svc._save_shelfs(db, company_id, uid, tok, phrase, data, file_name, day.name)
                        total["shelfs"] += 1
                        print(f"  {day.name} shelfs «{phrase}»: ok")
                    else:
                        print(f"  {day.name} {kind}: пропускаем (вид неизвестен)")
                except Exception as e:
                    print(f"  !! {raw_path.name}: {e}")
                    await db.rollback()
        if not dry_run:
            await db.commit()
    print("итого:", total)


def main() -> None:
    ap = argparse.ArgumentParser(description="Пересборка наблюдений выдачи WB из файлов сырья")
    ap.add_argument("--company-id", type=int, required=True)
    ap.add_argument("--date", default="", help="день (ГГГГ-ММ-ДД); пусто — все дни")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    asyncio.run(_run(a.company_id, a.date or None, a.dry_run))


if __name__ == "__main__":
    main()
