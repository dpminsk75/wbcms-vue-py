#!/usr/bin/env python3
"""Бэкфилл ресейла по историческим выдачам (задача 2026-10-27).

Признак ресейла (товар от частного лица) — из JSON-каталога WB:
    supplier_flags = 12224 AND sale_conditions = 1074790400 AND dtype_mask = 4096
Проверен на выдаче 2026-10-25..27: 31 карточка / 26 продавцов, все с личными
именами; ни у одного магазина/издательства таких значений нет.

Что делает:
  1) `wb_competitor_position.is_resale = 1` — метка в выдаче (по ней карточка
     не попадает в пулы кнопок сбора и не в «А|У|Н»);
  2) `badges` += "ресейл" — бейдж в выдаче сразу, без нового среза;
  3) `wb_competitor_details.is_resale = 1` — факт по карточке;
  4) `wb_competitor_capture.is_hidden = 1` — карточка исключена из сбора и из
     разбора фраз (снять может только явная кнопка «Вернуть»).

По умолчанию — ПЛАН (ничего не пишем). Запись — только с `--apply`.
Запись идёт ПО ДНЯМ (срез за срезом) — индекс `idx_position_company
(company_id, collected_at)`; на день приходится десятки тысяч строк, не вся
таблица. Каждый UPDATE — с LIMIT и таймаутом сессии.

  cd /var/www/wb/wbcms-py
  .venv/bin/python backend/scripts/resale_backfill.py --company-id 1
  .venv/bin/python backend/scripts/resale_backfill.py --company-id 1 --apply
"""

import argparse
import asyncio
import pathlib
import sys
import time
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from backend.database import get_session  # noqa: E402

# Лимиты сессии (правила AGENTS.md). temptable_max_ram — переменная только
# GLOBAL, её не трогаем.
SESSION_LIMITS = (
    "SET SESSION max_execution_time = 30000",
    "SET SESSION tmp_table_size = 33554432",
    "SET SESSION max_heap_table_size = 33554432",
    "SET SESSION sort_buffer_size = 1048576",
    "SET SESSION join_buffer_size = 1048576",
    "SET SESSION read_rnd_buffer_size = 524288",
    "SET SESSION lock_wait_timeout = 5",
    "SET SESSION innodb_lock_wait_timeout = 5",
    "SET SESSION sql_safe_updates = 1",
)

# Признак ресейла — как в hook_wb_api.js (расширение) и в миграции 20261036.
RULE = "supplier_flags = 12224 AND sale_conditions = 1074790400 AND dtype_mask = 4096"

# Пачка за шаг (строк выдачи) — чтобы UPDATE не висел на всю таблицу.
BATCH = 2000
# Максимум строк за один проход (страховка от бесконечного цикла).
MAX_ROWS = 200000


def _h(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


async def _days(db, cid: int, days: int) -> list[str]:
    """Дни, за которые есть выдача (по индексу company_id+collected_at)."""
    dfrom = (date.today() - timedelta(days=max(1, days))).isoformat()
    rows = (await db.execute(text("""
        SELECT DISTINCT collected_at AS d
        FROM wb_competitor_position
        WHERE company_id = :cid AND collected_at >= :dfrom
        ORDER BY d DESC
        LIMIT 400
    """), {"cid": cid, "dfrom": dfrom})).mappings().all()
    return [str(r["d"]) for r in rows]


async def _count(db, cid: int, day: str) -> int:
    row = (await db.execute(text(f"""
        SELECT COUNT(*) AS c
        FROM wb_competitor_position
        WHERE company_id = :cid AND collected_at = :d AND is_resale = 0 AND {RULE}
    """), {"cid": cid, "d": day})).first()
    return int(row[0] or 0) if row else 0


async def _cards(db, cid: int, day: str, limit: int) -> list[dict]:
    """Карточки дня-кандидата (ДО пометки — потом фильтр is_resale=0 их не отдаст)."""
    rows = (await db.execute(text(f"""
        SELECT nm_id, MAX(seller) AS seller, MAX(query_phrase) AS phrase,
               MIN(position) AS best_pos, COUNT(*) AS rows_cnt
        FROM wb_competitor_position
        WHERE company_id = :cid AND collected_at = :d AND is_resale = 0 AND {RULE}
        GROUP BY nm_id
        ORDER BY best_pos ASC
        LIMIT {limit}
    """), {"cid": cid, "d": day})).mappings().all()
    return [dict(r) for r in rows]


async def _mark_positions(db, cid: int, day: str) -> int:
    """Пометить строки выдачи дня: is_resale=1."""
    upd = await db.execute(text(f"""
        UPDATE wb_competitor_position
        SET is_resale = 1
        WHERE company_id = :cid AND collected_at = :d AND is_resale = 0 AND {RULE}
        LIMIT {BATCH}
    """), {"cid": cid, "d": day})
    return int(upd.rowcount or 0)


async def _mark_badges(db, cid: int, day: str) -> int:
    """Дописать бейдж «ресейл» в badges строк дня (уже помеченных is_resale=1)."""
    upd = await db.execute(text(f"""
        UPDATE wb_competitor_position
        SET badges = CASE
              WHEN badges IS NULL OR badges = '' OR badges = '[]' THEN '["ресейл"]'
              WHEN badges LIKE '%"ресейл"%' THEN badges
              ELSE JSON_ARRAY_APPEND(badges, '$', 'ресейл')
            END
        WHERE company_id = :cid AND collected_at = :d AND is_resale = 1 AND {RULE}
          AND (badges IS NULL OR badges NOT LIKE '%"ресейл"%')
        LIMIT {BATCH}
    """), {"cid": cid, "d": day})
    return int(upd.rowcount or 0)


async def _mark_details(db, nms: list[int]) -> int:
    if not nms:
        return 0
    ph = ",".join(f":n{i}" for i in range(len(nms)))
    params = {f"n{i}": n for i, n in enumerate(nms)}
    upd = await db.execute(text(f"""
        UPDATE wb_competitor_details SET is_resale = 1
        WHERE nm_id IN ({ph}) AND is_resale = 0
    """), params)
    return int(upd.rowcount or 0)


async def _block(db, cid: int, nms: list[int]) -> int:
    """Исключить карточки из сбора (is_hidden=1) — по одному, через сервис."""
    from backend.services import capture_service
    n = 0
    for nm in nms:
        try:
            await capture_service.set_hidden(db, cid, int(nm), True, None)
            n += 1
        except Exception as e:  # noqa: BLE001 — одна карточка не должна ронять прогон
            print(f"  ! set_hidden({nm}): {type(e).__name__}: {e}")
    return n


async def main() -> None:
    ap = argparse.ArgumentParser(description="Бэкфилл ресейла по историческим выдачам")
    ap.add_argument("--company-id", type=int, default=1)
    ap.add_argument("--days", type=int, default=14, help="сколько дней смотреть назад")
    ap.add_argument("--apply", action="store_true", help="писать (без флага — только план)")
    ap.add_argument("--sample", type=int, default=15, help="сколько карточек показать в плане")
    a = ap.parse_args()

    t0 = time.monotonic()
    async with get_session() as db:
        for lim in SESSION_LIMITS:
            try:
                await db.execute(text(lim))
            except Exception as e:  # noqa: BLE001
                print(f"  ! {lim} — {type(e).__name__}: {str(e)[:110]}")
        print(f"company_id={a.company_id}  дней={a.days}  режим="
              f"{'ЗАПИСЬ' if a.apply else 'ПЛАН (ничего не пишем)'}")

        days = await _days(db, a.company_id, a.days)
        if not days:
            print("выдачи за эти дни нет")
            return

        _h("1. План по дням (сколько строк ждёт пометки)")
        total_rows = 0
        all_cards: set[int] = set()
        plan: list[tuple[str, int, list[dict]]] = []
        for d in days:
            c = await _count(db, a.company_id, d)
            cards = await _cards(db, a.company_id, d, 500)
            for r in cards:
                all_cards.add(int(r["nm_id"]))
            total_rows += c
            plan.append((d, c, cards))
            print(f"  {d}: строк {c:>7}  карточек {len(cards):>4}")

        _h("2. Итог плана")
        print(f"  дней: {len(days)}")
        print(f"  строк выдачи к пометке: {total_rows}")
        print(f"  уникальных карточек: {len(all_cards)}")

        _h("3. Пример карточек (день с наибольшим объёмом)")
        if plan:
            d0, _, sample = max(plan, key=lambda x: x[1])
            print(f"  день {d0}:")
            for r in sample[:a.sample]:
                print(f"    nm {r['nm_id']:>12}  pos={r['best_pos']:>3}  "
                      f"seller={r['seller']!r}  строк={r['rows_cnt']}")

        if not a.apply:
            _h("Это был план. Запись — с --apply")
            print("  .venv/bin/python backend/scripts/resale_backfill.py "
                  f"--company-id {a.company_id} --apply")
            print(f"\nитого: {time.monotonic() - t0:.1f} с")
            return

        _h("4. Запись (по дням, пачками)")
        marked = 0
        badged = 0
        det = 0
        blocked = 0
        for d in days:
            t1 = time.monotonic()
            # карточки дня берём ДО пометки (после — фильтр is_resale=0 пуст)
            cards = await _cards(db, a.company_id, d, 500)
            nms = [int(r["nm_id"]) for r in cards]
            day_rows = 0
            while True:
                n = await _mark_positions(db, a.company_id, d)
                if not n:
                    break
                day_rows += n
                marked += n
                await db.commit()
                if marked > MAX_ROWS:
                    print("  ! достигнут MAX_ROWS — останавливаюсь")
                    break
            try:
                while True:
                    n = await _mark_badges(db, a.company_id, d)
                    if not n:
                        break
                    badged += n
                    await db.commit()
            except Exception as e:  # noqa: BLE001 — бейдж не критичен, флаг уже стоит
                await db.rollback()
                print(f"  ! бейджи за {d}: {type(e).__name__}: {e}")
            det += await _mark_details(db, nms)
            blocked += await _block(db, a.company_id, nms)
            await db.commit()
            print(f"  {d}: строк {day_rows:>7}, карточек {len(nms):>4}, "
                  f"{time.monotonic() - t1:.2f} с")

        _h("5. Итог")
        print(f"  строк выдачи помечено: {marked}")
        print(f"  строк с бейджем «ресейл»: {badged}")
        print(f"  карточек в details помечено: {det}")
        print(f"  карточек исключено из сбора: {blocked}")
        print(f"\nитого: {time.monotonic() - t0:.1f} с")


if __name__ == "__main__":
    asyncio.run(main())
