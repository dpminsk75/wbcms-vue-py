#!/usr/bin/env python3
"""Разведка «ресейла»: как отличить товары частных лиц в сохранённой выдаче.

Задача (2026-10-27): в выдаче много товаров, которые продают физлица (ресейл).
Их не нужно парсить — это не наши конкуренты. Признак ищем в том, что уже
сохранено: `wb_competitor_position` (поля из JSON-каталога WB) и сырые ответы
WB в `backend/runtime/seo_search_raw`.

Скрипт ТОЛЬКО ЧИТАЕТ (сессия ставит `sql_safe_updates=1` — UPDATE/DELETE
заблокированы). Запускается на боевой БД, поэтому у каждого SELECT есть LIMIT,
а у сессии — лимиты и таймаут (правила AGENTS.md).

  cd /var/www/wb/wbcms-py
  .venv/bin/python backend/scripts/resale_probe.py --company-id 1
  .venv/bin/python backend/scripts/resale_probe.py --company-id 1 --json --json-days 3
  .venv/bin/python backend/scripts/resale_probe.py --company-id 1 --explain --stamps 20261026_131647
"""

import argparse
import asyncio
import json
import pathlib
import sys
import time
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from backend.database import get_session  # noqa: E402

# Товары, про которые известно, что их продают физлица (пример из задачи).
DEFAULT_SEED = (1824993198, 1689764801, 749158652, 840053556)

RAW_ROOT = ROOT / "backend" / "runtime" / "seo_search_raw"

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

# Поля-кандидаты признака ресейла (всё, что пришло из JSON-каталога WB).
SIGN_FIELDS = ("supplier_flags", "sale_conditions", "dtype_mask", "mtype")

# Ключи товара WB, которые в отчёте не печатаем (большие/неинформативные).
SKIP_KEYS = {"sizes", "images", "variants", "colors", "prices", "stocks", "wh",
             "volumes", "swatches", "suppliers", "goods", "imgs", "logistics",
             "seo", "tags", "options", "colorsV2", "extra"}

def _h(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _ph(rows) -> str:
    return ", ".join(f":p{i}" for i in range(len(rows)))


def _f(v, width: int = 0) -> str:
    """Число в колонку; None — как «—» (поля бывают пустыми)."""
    if v is None:
        return "—" if not width else " " * (width - 1) + "—"
    return f"{v:>{width}}" if width else str(v)


def _sql_slices(cid: int, dfrom: str, lim: int) -> str:
    return f"""
        SELECT slice_stamp, COUNT(*) AS c
        FROM wb_competitor_position
        WHERE company_id = :cid AND collected_at >= :dfrom AND slice_stamp <> ''
        GROUP BY slice_stamp
        ORDER BY slice_stamp DESC
        LIMIT {lim}
    """


def _sql_seed(cid: int, seed: list[int], lim: int) -> str:
    ph = _ph(seed)
    return f"""
        SELECT nm_id, seller, seller_id, supplier_flags, sale_conditions,
               dtype_mask, mtype, total_qty, feedbacks, position, query_phrase,
               collected_at, slice_stamp
        FROM wb_competitor_position
        WHERE company_id = :cid AND nm_id IN ({ph})
        ORDER BY collected_at DESC, position ASC
        LIMIT {lim}
    """


def _sql_dist(cid: int, stamps: list[str], lim: int) -> str:
    ph = _ph(stamps)
    return f"""
        SELECT supplier_flags, sale_conditions, dtype_mask, mtype,
               COUNT(DISTINCT nm_id) AS cards,
               COUNT(DISTINCT seller_id) AS sellers_cnt,
               SUM(total_qty = 1) AS qty_eq_1,
               GROUP_CONCAT(DISTINCT LEFT(seller, 14) ORDER BY seller SEPARATOR ', ') AS sellers
        FROM wb_competitor_position
        WHERE company_id = :cid AND slice_stamp IN ({ph})
        GROUP BY supplier_flags, sale_conditions, dtype_mask, mtype
        ORDER BY cards DESC
        LIMIT {lim}
    """


def _sql_pool(cid: int, stamps: list[str], lim: int) -> str:
    ph = _ph(stamps)
    return f"""
        SELECT nm_id, MAX(seller) AS seller, MAX(seller_id) AS seller_id,
               MAX(total_qty) AS qty, MAX(feedbacks) AS fb,
               MIN(position) AS best_pos, COUNT(DISTINCT query_phrase) AS phrases_cnt,
               GROUP_CONCAT(DISTINCT LEFT(title, 40) SEPARATOR ' | ') AS titles
        FROM wb_competitor_position
        WHERE company_id = :cid AND slice_stamp IN ({ph})
          AND supplier_flags = :sf AND sale_conditions = :sc
          AND dtype_mask = :dm AND mtype <=> :mtype
        GROUP BY nm_id
        ORDER BY best_pos ASC
        LIMIT {lim}
    """


def _sql_per_slice(cid: int, stamps: list[str], lim: int) -> str:
    ph = _ph(stamps)
    return f"""
        SELECT slice_stamp, COUNT(DISTINCT nm_id) AS cards,
               GROUP_CONCAT(DISTINCT LEFT(seller, 12) ORDER BY seller SEPARATOR ', ') AS sellers
        FROM wb_competitor_position
        WHERE company_id = :cid AND slice_stamp IN ({ph})
          AND supplier_flags = :sf AND sale_conditions = :sc
          AND dtype_mask = :dm AND mtype <=> :mtype
        GROUP BY slice_stamp
        ORDER BY slice_stamp DESC
        LIMIT {lim}
    """


async def _run(db, sql: str, params: dict | None, label: str) -> list[dict]:
    """Запрос с замером времени и числа строк (правила AGENTS.md: лог фактического)."""
    t0 = time.monotonic()
    rows = (await db.execute(text(sql), params or {})).mappings().all()
    print(f"  [{label}] {time.monotonic() - t0:.2f} с, строк: {len(rows)}")
    return [dict(r) for r in rows]


async def _explain(db, sql: str, params: dict, label: str) -> None:
    try:
        plan = (await db.execute(text("EXPLAIN " + sql), params)).mappings().all()
        print(f"\n--- EXPLAIN {label} ---")
        for r in plan:
            print("   ", {k: r[k] for k in ("table", "type", "key", "rows", "Extra")
                          if k in r.keys()})
    except Exception as e:  # noqa: BLE001 — EXPLAIN не должен ронять скрипт
        print(f"  ! EXPLAIN {label}: {type(e).__name__}: {e}")


# --------------------------------------------------------------------------
# Сырой JSON WB: ищем ЯВНЫЙ признак ресейла (для проверки в расширении)
# --------------------------------------------------------------------------

def _scalar(v) -> object:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, list):
        return f"[{len(v)} шт]"
    if isinstance(v, dict):
        return "{...}"
    return str(v)[:60]


def _flat(p: dict) -> dict:
    return {k: _scalar(v) for k, v in p.items() if k not in SKIP_KEYS}


def _raw_files(cid: int, days: int) -> list[pathlib.Path]:
    base = RAW_ROOT / str(cid)
    if not base.exists():
        return []
    out: list[pathlib.Path] = []
    for d in sorted([x for x in base.iterdir() if x.is_dir()])[-days:]:
        out += sorted(f for f in d.glob("*_catalog_*.json")
                      if not f.name.endswith(".meta.json"))
    return out


def _scan_raw(cid: int, days: int, seed: list[int], max_files: int) -> None:
    _h("СЫРОЙ JSON WB: все поля товара (ищем явный признак ресейла)")
    files = _raw_files(cid, days)
    if not files:
        print(f"нет файлов в {RAW_ROOT / str(cid)} — расширение их ещё не клало")
        return
    print(f"файлов: {len(files)} (из {len(_raw_files(cid, days))}), смотрю последние {max_files}")
    found = 0
    for f in files[-max_files:]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"!! {f.name}: {e}")
            continue
        products = data.get("products") if isinstance(data, dict) else None
        if not isinstance(products, list):
            continue
        ids = set(seed)
        hits = [p for p in products if isinstance(p, dict) and p.get("id") in ids]
        if not hits:
            continue
        ctrl = max((p for p in products if isinstance(p, dict)),
                   key=lambda p: int(p.get("feedbacks") or 0), default=None)
        cflat = _flat(ctrl) if ctrl else {}
        for p in hits:
            found += 1
            pflat = _flat(p)
            _h(f"{f.name} · товар {p.get('id')}")
            print(f"  supplier={p.get('supplier')!r} supplierId={p.get('supplierId')} "
                  f"feedbacks={p.get('feedbacks')} totalQuantity={p.get('totalQuantity')}")
            print("  поля товара (значение | значение у обычного товара):")
            for k in sorted(pflat):
                cv = cflat.get(k, "—(нет у обычного)")
                same = "=" if cflat.get(k) == pflat[k] else "≠"
                print(f"    {k:28} {str(pflat[k])[:52]:54} {same} {str(cv)[:40]}")
    if not found:
        print("ресейл-товаров в этих файлах нет — откройте в WB поиск, где они есть,")
        print("и повторите (расширение само положит новые файлы)")


# --------------------------------------------------------------------------


async def main() -> None:
    ap = argparse.ArgumentParser(description="Разведка ресейла в сохранённой выдаче")
    ap.add_argument("--company-id", type=int, default=1)
    ap.add_argument("--seed", default="", help="nmID через запятую (по умолчанию — примеры из задачи)")
    ap.add_argument("--days", type=int, default=3, help="сколько дней смотреть")
    ap.add_argument("--slices", type=int, default=8, help="сколько последних срезов взять")
    ap.add_argument("--limit", type=int, default=200, help="потолок строк в выдаче")
    ap.add_argument("--json", action="store_true", help="дополнительно разобрать сырой JSON WB")
    ap.add_argument("--json-days", type=int, default=2)
    ap.add_argument("--json-files", type=int, default=8)
    ap.add_argument("--explain", action="store_true", help="напечатать SQL и EXPLAIN, данные не читать")
    ap.add_argument("--stamps", default="", help="метки заходов через запятую (для --explain)")
    a = ap.parse_args()

    seed = [int(x) for x in a.seed.split(",") if x.strip().isdigit()] or list(DEFAULT_SEED)
    dfrom = (date.today() - timedelta(days=max(1, a.days))).isoformat()
    t0 = time.monotonic()

    async with get_session() as db:
        for lim in SESSION_LIMITS:
            try:
                await db.execute(text(lim))
            except Exception as e:  # noqa: BLE001 — лимит не ставится — предупреждаем, но идём дальше
                print(f"  ! {lim} — {type(e).__name__}: {str(e)[:120]}")
        print(f"company_id={a.company_id}  seed={seed}  дней={a.days} (с {dfrom})  "
              f"срезов={a.slices}  limit={a.limit}")

        sql_slices = _sql_slices(a.company_id, dfrom, a.slices)
        sql_seed = _sql_seed(a.company_id, seed, a.limit)
        p_seed = {"cid": a.company_id, **{f"p{i}": n for i, n in enumerate(seed)}}

        if a.explain:
            _h("SQL запросов (для ручного EXPLAIN)")
            for name, sql in (("срезы", sql_slices), ("ресейл-товары", sql_seed)):
                print(f"\n-- {name} --\n{sql.strip()}")
            await _explain(db, sql_slices, {"cid": a.company_id, "dfrom": dfrom}, "срезы")
            await _explain(db, sql_seed, p_seed, "ресейл-товары")
            stamps = [s for s in a.stamps.split(",") if s.strip()]
            if stamps:
                for name, builder in (("распределение", _sql_dist), ("пул", _sql_pool)):
                    sql = builder(a.company_id, stamps, 50)
                    print(f"\n-- {name} --\n{sql.strip()}")
                    await _explain(db, sql, {"cid": a.company_id, "sf": 0, "sc": 0, "dm": 0,
                                             "mtype": None,
                                             **{f"p{i}": s for i, s in enumerate(stamps)}},
                                   name)
            print("\nрежим --explain: данные не читались")
            return

        _h("1. Срезы выдачи")
        rows = await _run(db, sql_slices, {"cid": a.company_id, "dfrom": dfrom}, "срезы")
        stamps = [r["slice_stamp"] for r in rows]
        for s in stamps:
            print(f"  {s}")
        if not stamps:
            print("срезов не найдено")
            return

        _h("2. Известные ресейл-товары: их комбинация признаков")
        seed_rows = await _run(db, sql_seed, p_seed, "ресейл-товары")
        seen: set[int] = set()
        for r in seed_rows:
            if r["nm_id"] in seen:
                continue
            seen.add(r["nm_id"])
            print(f"  nm {_f(r['nm_id'], 12)}  seller={r['seller']!r} id={r['seller_id']} "
                  f"sf={r['supplier_flags']} sc={r['sale_conditions']} "
                  f"dm={r['dtype_mask']} mtype={r['mtype']} qty={r['total_qty']} "
                  f"fb={r['feedbacks']} pos={r['position']}")
        combos = {(r["supplier_flags"], r["sale_conditions"], r["dtype_mask"], r["mtype"])
                  for r in seed_rows}
        print(f"\n  разных комбинаций у {len(seen)} товаров: {len(combos)}")
        for c in combos:
            print(f"    {c}")
        if combos:
            # сортируем по строковому виду: mtype бывает NULL — простое sorted() упадёт
            combo = dict(zip(SIGN_FIELDS, min(combos, key=lambda c: tuple(str(x) for x in c))))
        else:
            combo = {}
        if len(combos) != 1 or not seen:
            print("  ⚠ комбинация не единственная — выберите её по распределению (п.3) "
                  "и поправьте --seed/поля вручную")

        _h("3. Распределение комбинаций по срезам (контрольная группа)")
        p_stamps = {"cid": a.company_id, **{f"p{i}": s for i, s in enumerate(stamps)}}
        dist = await _run(db, _sql_dist(a.company_id, stamps, 50), p_stamps, "распределение")
        print(f"  {'supplier_flags':>14} {'sale_conditions':>16} {'dtype_mask':>11} "
              f"{'mtype':>6} {'карточек':>9} {'продавцов':>9}  продавцы")
        for r in dist:
            mark = " <-- ресейл" if (r["supplier_flags"], r["sale_conditions"],
                                     r["dtype_mask"], r["mtype"]) in combos else ""
            print(f"  {str(r['supplier_flags']):>14} {str(r['sale_conditions']):>16} "
                  f"{str(r['dtype_mask']):>11} {str(r['mtype']):>6} {r['cards']:>9} "
                  f"{r['sellers_cnt']:>9}  {(r.get('sellers') or '')[:100]}{mark}")

        if combo:
            p_combo = {"cid": a.company_id, "sf": combo.get("supplier_flags"),
                       "sc": combo.get("sale_conditions"), "dm": combo.get("dtype_mask"),
                       "mtype": combo.get("mtype"), **p_stamps}
            _h("4. Пул карточек с комбинацией ресейла")
            pool = await _run(db, _sql_pool(a.company_id, stamps, a.limit), p_combo, "пул")
            total_cards = sum(int(r["cards"] or 0) for r in dist)
            share = (len(pool) * 100.0 / total_cards) if total_cards else 0
            print(f"  карточек в пуле: {len(pool)}  (из {total_cards} в срезах — {share:.1f}%)")
            for r in pool[:60]:
                print(f"  nm {_f(r['nm_id'], 12)}  pos={_f(r['best_pos'], 3)}  qty={_f(r['qty'], 5)} "
                      f"fb={_f(r['fb'], 5)}  фраз={_f(r['phrases_cnt'], 2)}  seller={r['seller']!r}")
                print(f"      {(r['titles'] or '')[:120]}")

            _h("5. Пул по срезам (признак стабилен?)")
            per = await _run(db, _sql_per_slice(a.company_id, stamps, 50), p_combo, "пул по срезам")
            for r in per:
                print(f"  {r['slice_stamp']}  карточек={r['cards']:>3}  "
                      f"{(r['sellers'] or '')[:100]}")
            if not per:
                print("  в выбранных срезах пула нет")

    if a.json:
        _scan_raw(a.company_id, a.json_days, seed, a.json_files)

    print(f"\nитого: {time.monotonic() - t0:.1f} с")


if __name__ == "__main__":
    asyncio.run(main())
