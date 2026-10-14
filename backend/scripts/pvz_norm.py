#!/usr/bin/env python3
"""Сервис нормализации названий ПВЗ: region/city -> region_norm/city_norm.

ЧТО ДЕЛАЕТ (по шагам):
  1. Читает пачками (wb_id, region, city, region_norm, city_norm) из pvz_all.
  2. Считает нормы функциями backend.services.geo_names
     (сначала словарь ручных правок REGION_OVERRIDES/CITY_OVERRIDES, потом алгоритм).
  3. Если норма отличается от записанной — UPDATE строки.
  4. В конце печатает итог + топ замен «было -> стало» (что именно поменялось).

Отдельный шаг конвейера (pvz_import.py НЕ трогаем): DaData/geolocate пишут сырые
строки, этот скрипт раскладывает нормы для группировок в отчетах.

Режимы:
  (по умолчанию) — только строки с region_norm IS NULL (догонка новых разборов);
  --all         — пересчитать всё (после правок geo_names: алгоритм/overrides);
  --dry-run     — ничего не писать, только показать, что поменялось бы.

Запуск из корня проекта:
  .venv/bin/python backend/scripts/pvz_norm.py --dry-run
  .venv/bin/python backend/scripts/pvz_norm.py
  .venv/bin/python backend/scripts/pvz_norm.py --all --batch-size 5000

Гонять после каждого прогона импорта/шаттла (можно в cron следом за ними).
"""
import argparse
import asyncio
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from backend.database import get_session  # noqa: E402
from backend.services.geo_names import normalize_city, normalize_country, normalize_region  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser(description="Нормализация region/city ПВЗ в *_norm")
    ap.add_argument("--all", action="store_true",
                    help="пересчитать все строки, а не только с region_norm IS NULL")
    ap.add_argument("--dry-run", action="store_true",
                    help="только показать замены, ничего не писать")
    ap.add_argument("--batch-size", type=int, default=2000)
    args = ap.parse_args()

    # Основной путь: только NULL-нормы (саргабельно, keyset по PK).
    # Регистр country чиним отдельно разовым проходом ниже: OR с CAST убивал
    # индекс и превращал каждый батч в фулскан (висело по 300с).
    where = "" if args.all else "WHERE region_norm IS NULL"
    scanned = updated = 0
    shown: Counter = Counter()  # (поле, было, стало) -> строк
    seen_cc: Counter = Counter()  # сырые коды стран (контроль мусора)
    # NB: keyset-пагинация (wb_id > last), НЕ OFFSET: выборка сжимается по мере
    # записи норм, OFFSET пропускал бы каждый второй батч.
    async with get_session() as db:
        codes = [r[0] for r in (await db.execute(
            text("SELECT DISTINCT country FROM pvz_all"))).all()]
        seen_cc.update({c: 0 for c in codes})
        # разовая чистка регистра: UPDATE бьет прямо по idx_pvz_country
        for c in codes:
            if c != (c or "").strip().lower():
                r = await db.execute(text("""
                    UPDATE pvz_all SET country=:nc
                    WHERE country=:oc
                """), {"nc": (c or "").strip().lower() or "ru", "oc": c})
                await db.commit()
                if r.rowcount:
                    shown[("country", c, (c or "").strip().lower() or "ru")] += r.rowcount
                    updated += r.rowcount
        last = 0
        while True:
            rows = (await db.execute(text(f"""
                SELECT wb_id, region, city, region_norm, city_norm, country
                FROM pvz_all {where} {'AND' if where else 'WHERE'} wb_id > :last
                ORDER BY wb_id LIMIT :lim
            """), {"lim": args.batch_size, "last": last})).mappings().all()
            if not rows:
                break
            batch = []
            for r in rows:
                scanned += 1
                seen_cc[r["country"]] += 1
                rn = normalize_region(r["region"])
                cn = normalize_city(r["city"])
                cc = normalize_country(r["country"]) or "ru"  # country NOT NULL
                if rn != r["region_norm"] or cn != r["city_norm"] or cc != r["country"]:
                    batch.append({"w": r["wb_id"], "rn": rn, "cn": cn, "cc": cc})
                    if rn != r["region_norm"]:
                        shown[("region", r["region"], rn)] += 1
                    if cn != r["city_norm"]:
                        shown[("city", r["city"], cn)] += 1
                    if cc != r["country"]:
                        shown[("country", r["country"], cc)] += 1
            if batch and not args.dry_run:
                for b in batch:
                    await db.execute(text("""
                        UPDATE pvz_all SET region_norm=:rn, city_norm=:cn, country=:cc
                        WHERE wb_id=:w
                    """), b)
                await db.commit()
                updated += len(batch)
            elif args.dry_run:
                updated += len(batch)
            last = rows[-1]["wb_id"]
    print(f"NORM scanned={scanned} "
          f"{'would_update' if args.dry_run else 'updated'}={updated} "
          f"mode={'all' if args.all else 'nulls'}{' dry-run' if args.dry_run else ''}",
          flush=True)
    for (fld, old, new), cnt in shown.most_common(30):
        print(f"  {fld}: {old!r} -> {new!r} (строк: {cnt})", flush=True)
    if len(shown) > 30:
        print(f"  ... ещё {len(shown) - 30} вариантов", flush=True)
    print(f"  коды стран в выборке: {dict(seen_cc)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
