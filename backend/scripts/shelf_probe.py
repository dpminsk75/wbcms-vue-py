#!/usr/bin/env python3
"""Разведка полок WB: что реально собрано по нашей карточке.

Задача (2026-10-28): модалка «Полки и баджи» показывает блоки «Смотрите
также» / «Продавец рекомендует» на нашей карточке и места, где нас видели
в чужих полках. Скрипт показывает, что лежит в базе:
  * блоки на нашей карточке (`wb_competitor_cards_shelf` + `..._shelf_item`);
  * где мы на полках (нас как позиция в чужом блоке);
  * покрытие фото (в позициях полки фото пишет расширение из DOM — до
    миграции 20261037 там пусто, фото брались из реестра конкурентов);
  * бейджи карточки и их историю (`wb_card_badges_history`).

Скрипт ТОЛЬКО ЧИТАЕТ (сессия ставит `sql_safe_updates=1` — UPDATE/DELETE
заблокированы). Запускается на боевой БД, поэтому у каждого SELECT есть LIMIT,
а у сессии — лимиты и таймаут (правила AGENTS.md).

  cd /var/www/wb/wbcms-py
  .venv/bin/python backend/scripts/shelf_probe.py --company-id 1 --nm 52644366
  .venv/bin/python backend/scripts/shelf_probe.py --company-id 1 --nm 52644366 --json
  .venv/bin/python backend/scripts/shelf_probe.py --company-id 1 --nm 52644366 --explain
"""

import argparse
import asyncio
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from backend.database import get_session  # noqa: E402

# Лимиты сессии — по правилам AGENTS.md (тяжёлые выборки на боевой БД).
# temptable_max_ram в MySQL 8 — переменная ТОЛЬКО GLOBAL (SET SESSION на ней
# даёт ошибку 1229), поэтому её тут нет: глобальные настройки не трогаем.
SESSION_LIMITS = (
    "SET SESSION max_execution_time = 15000",
    "SET SESSION tmp_table_size = 33554432",
    "SET SESSION max_heap_table_size = 33554432",
    "SET SESSION sort_buffer_size = 1048576",
    "SET SESSION join_buffer_size = 1048576",
    "SET SESSION read_rnd_buffer_size = 524288",
    "SET SESSION lock_wait_timeout = 5",
    "SET SESSION innodb_lock_wait_timeout = 5",
    "SET SESSION sql_safe_updates = 1",
)


def _h(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _f(v, width: int = 0) -> str:
    """Число в колонку; None — как «—»."""
    if v is None:
        return "—" if not width else " " * (width - 1) + "—"
    return f"{v:>{width}}" if width else str(v)


def _d(v) -> str:
    if v is None:
        return "—"
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v)[:10]


# Запросы скрипта — отдельно, чтобы в режиме --explain показать план.
SQL_BLOCKS = """
    SELECT s.id AS shelf_id, s.preset_id, s.preset_type, s.kind, s.is_partial,
           s.total_candidates, s.title, s.title_source, s.last_seen_at,
           COALESCE(NULLIF(s.title,''), NULLIF(p.title,''),
                    CONCAT('#', s.preset_id)) AS shown_title,
           (SELECT MAX(i.snapshot_date) FROM wb_competitor_cards_shelf_item i
             WHERE i.shelf_id = s.id) AS last_date,
           (SELECT COUNT(DISTINCT i.snapshot_date) FROM wb_competitor_cards_shelf_item i
             WHERE i.shelf_id = s.id) AS dates_cnt,
           (SELECT COUNT(*) FROM wb_competitor_cards_shelf_item i
             WHERE i.shelf_id = s.id) AS items_cnt
    FROM wb_competitor_cards_shelf s
    LEFT JOIN wb_competitor_cards_shelf_preset p ON p.preset_id = s.preset_id
    WHERE s.nm_id = :n AND s.company_id = :c
    ORDER BY s.preset_id, s.id
    LIMIT 20
"""

SQL_ITEMS = """
    SELECT i.nm_id, i.position, i.name, i.price, i.price_basic, i.seller,
           i.is_own, i.image_url
    FROM wb_competitor_cards_shelf_item i
    WHERE i.shelf_id = :sid AND i.snapshot_date = :d
    ORDER BY i.position LIMIT :lim
"""

SQL_WHERE = """
    SELECT i.shelf_id, i.snapshot_date, i.position, s.nm_id AS anchor_nm,
           s.title AS shelf_title, s.preset_id
    FROM wb_competitor_cards_shelf_item i
    JOIN wb_competitor_cards_shelf s ON s.id = i.shelf_id
    WHERE i.nm_id = :n AND s.company_id = :c
    ORDER BY i.snapshot_date DESC, i.position
    LIMIT 100
"""

SQL_COVER = """
    SELECT COUNT(*) AS total,
           SUM(CASE WHEN image_url <> '' THEN 1 ELSE 0 END) AS with_img
    FROM wb_competitor_cards_shelf_item
    WHERE nm_id = :n
"""


def _short(s, n: int = 46) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


async def _run(db, sql: str, params: dict | None = None) -> list[dict]:
    rows = (await db.execute(text(sql), params or {})).mappings().all()
    return [dict(r) for r in rows]


async def main() -> int:
    ap = argparse.ArgumentParser(description="Разведка полок WB по нашей карточке")
    ap.add_argument("--company-id", type=int, required=True)
    ap.add_argument("--nm", type=int, required=True, help="nmID нашей карточки")
    ap.add_argument("--items", type=int, default=8, help="сколько позиций показывать (макс 50)")
    ap.add_argument("--json", action="store_true", help="вывод в JSON")
    ap.add_argument("--explain", action="store_true", help="только EXPLAIN, ничего не выполнять")
    args = ap.parse_args()

    cid = int(args.company_id)
    nm = int(args.nm)
    lim = max(1, min(int(args.items), 50))

    out: dict = {"company_id": cid, "nm_id": nm}

    async with get_session() as db:
        t0 = time.monotonic()
        for stmt in SESSION_LIMITS:
            try:
                await db.execute(text(stmt))
            except Exception:
                pass

        if args.explain:
            # Только план: ничего не выполняем.
            plans = (
                ("блоки на карточке", SQL_BLOCKS, {"n": nm, "c": cid}),
                ("позиции среза", SQL_ITEMS, {"sid": 0, "d": "2000-01-01", "lim": lim}),
                ("где мы на полках", SQL_WHERE, {"n": nm, "c": cid}),
                ("покрытие фото", SQL_COVER, {"n": nm}),
            )
            for name, sql, params in plans:
                _h(f"EXPLAIN: {name}")
                try:
                    rows = (await db.execute(text("EXPLAIN " + sql), params)).mappings().all()
                    for r in rows:
                        print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()
                                             if k in ("id", "select_type", "table", "type",
                                                     "possible_keys", "key", "rows", "Extra")))
                except Exception as exc:
                    print(f"  не получилось: {exc}")
            return 0

        _h(f"Карточка {nm} (компания {cid})")
        own = await _run(db, """
            SELECT nmID, company_id, title FROM wbcards WHERE nmID=:n LIMIT 1
        """, {"n": nm})
        if not own:
            print("карточки нет в wbcards — это не наша карточка?")
        else:
            print(f"наша: {own[0]['title']}")

        # 1. бейджи и цена (текущие) + история
        det = await _run(db, """
            SELECT title, price, old_price, badges, sold_out, is_resale,
                   COALESCE(collected_at, first_collected_at) AS collected_at,
                   full_collected_at
            FROM wb_competitor_details
            WHERE nm_id=:n
            ORDER BY COALESCE(collected_at, first_collected_at) DESC, id DESC LIMIT 1
        """, {"n": nm})
        out["details"] = det[0] if det else None
        if det:
            d = det[0]
            print(f"бейджи: {d.get('badges')}")
            print(f"цена: {d.get('price')} (было {d.get('old_price')}) · сбор: {d.get('collected_at')}")
            print(f"полный сбор: {d.get('full_collected_at')} · ресейл: {d.get('is_resale')}")
        else:
            print("строки в wb_competitor_details нет — карточка не собрана")

        try:
            hist = await _run(db, """
                SELECT badges, price, at FROM wb_card_badges_history
                WHERE nm_id=:n AND (company_id=:c OR company_id=0)
                ORDER BY id DESC LIMIT 20
            """, {"n": nm, "c": cid})
        except Exception as exc:
            hist = []
            print(f"история бейджей недоступна: {exc}")
        out["badge_history"] = hist
        print(f"снимков истории бейджей: {len(hist)}")

        # 2. блоки на нашей карточке
        blocks = await _run(db, SQL_BLOCKS, {"n": nm, "c": cid})
        out["blocks"] = blocks
        _h(f"Блоки на нашей карточке: {len(blocks)}")
        for b in blocks:
            print(f"  shelf={b['shelf_id']} preset={b['preset_id']} kind={b['kind']} "
                  f"«{_short(b['shown_title'], 40)}» (в базе: «{_short(b['title'], 30)}») "
                  f"снимков дат: {b['dates_cnt']} последний: {_d(b['last_date'])} "
                  f"позиций всего: {b['items_cnt']}")

        # 3. позиции последнего среза + покрытие фото
        for b in blocks:
            if not b["last_date"]:
                continue
            items = await _run(db, SQL_ITEMS,
                               {"sid": b["shelf_id"], "d": b["last_date"], "lim": lim})
            with_img = sum(1 for i in items if i.get("image_url"))
            print(f"\n  — блок {b['shelf_id']} «{_short(b['shown_title'], 30)}» срез {_d(b['last_date'])}: "
                  f"позиций показано {len(items)}, с фото {with_img}")
            for i in items[:lim]:
                print(f"      #{i['position']:>3} {i['nm_id']:>11} "
                      f"{_f(i['price'], 7)} ₽  фото: {'да' if i.get('image_url') else 'нет '}  "
                      f"{_short(i['name'], 38)}")

        # 4. где мы на полках
        where = await _run(db, SQL_WHERE, {"n": nm, "c": cid})
        out["where"] = where
        _h(f"Где мы на полках: {len(where)} записей")
        for w in where[:30]:
            print(f"  {w['snapshot_date']} поз.{w['position']:>3} "
                  f"якорь {w['anchor_nm']:>11} полка «{_short(w['shelf_title'], 34)}»")

        # 5. покрытие фото по всем позициям, где мы встречаемся
        cover = await _run(db, SQL_COVER, {"n": nm})
        out["cover"] = cover[0] if cover else None
        if cover:
            c = cover[0]
            print(f"\nнаши позиции в чужих полках: {c['total']}, с фото: {c['with_img']}")

        out["elapsed"] = round(time.monotonic() - t0, 2)
        print(f"\nвремя: {out['elapsed']} с")

    if args.json:
        print("\n" + json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
