#!/usr/bin/env python3
"""Что ещё есть в сыром ответе WB — для диагностики заполняемости полей.

Показывает ключи товара из `resultset=catalog` и — по каждому ключу — сколько
товаров его имеют и пример значения. Нужно, чтобы понять, что можно записать
в `wb_competitor_position` (бейджи/акции, картинка и т.п.).

  cd /var/www/wb/wbcms-py
  .venv/bin/python backend/scripts/inspect_search_raw.py --company-id 1
  .venv/bin/python backend/scripts/inspect_search_raw.py --company-id 1 --kind catalog --limit 2
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RAW_ROOT = ROOT / "backend" / "runtime" / "seo_search_raw"

INTERESTING = (
    "actions", "action", "badges", "badge", "discount", "promo", "panelPromoId",
    "image", "images", "imageUrl", "photourl", "vol", "part", "bigImage",
    "rating", "reviewRating", "feedbacks", "feedbackPoints",
    "saleConditions", "dtypeMask", "semanticId", "totalQuantity", "isNew",
    "supplierRating", "supplierId", "matchId", "time1", "time2", "wh", "dist",
    "pics", "sizes", "logistics", "stocks", "volume", "weight",
)


def _short(v, limit: int = 220) -> str:
    try:
        s = json.dumps(v, ensure_ascii=False)
    except Exception:
        s = str(v)
    return s[:limit] + ("…" if len(s) > limit else "")


def _scan(raw_path: pathlib.Path, kind: str) -> None:
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"!! {raw_path.name}: {e}")
        return

    print(f"\n=== {raw_path.name} ({raw_path.stat().st_size} байт) ===")
    if isinstance(data, dict):
        print("ключи ответа:", ", ".join(sorted(data.keys())))
        d = data.get("data")
        if isinstance(d, dict):
            print("ключи data:", ", ".join(sorted(d.keys())))
        products = data.get("products")
    else:
        products = data

    if not isinstance(products, list) or not products:
        print("товаров нет")
        return

    print(f"товаров: {len(products)}")
    first = products[0] if isinstance(products[0], dict) else {}
    print("ключи товара:", ", ".join(sorted(first.keys())))

    # какие ключи есть и сколько товаров их имеют
    cnt: dict[str, int] = {}
    sample: dict[str, object] = {}
    for p in products:
        if not isinstance(p, dict):
            continue
        for k, v in p.items():
            if v in (None, "", [], {}):
                continue
            cnt[k] = cnt.get(k, 0) + 1
            if k not in sample:
                sample[k] = v

    print("\nключ | товаров | пример")
    for k in sorted(cnt, key=lambda x: (-cnt[x], x)):
        mark = " *" if k.lower() in {i.lower() for i in INTERESTING} else ""
        print(f"{k}{mark} | {cnt[k]} | {_short(sample[k])}")

    # размеры товара — там цена/опции
    for p in products[:1]:
        if not isinstance(p, dict):
            continue
        sz = p.get("sizes")
        if isinstance(sz, list) and sz and isinstance(sz[0], dict):
            print("\nключи sizes[0]:", ", ".join(sorted(sz[0].keys())))
            print("sizes[0]:", _short(sz[0], 600))


def main() -> None:
    ap = argparse.ArgumentParser(description="Что есть в сырых ответах WB (выдача)")
    ap.add_argument("--company-id", type=int, required=True)
    ap.add_argument("--date", default="", help="день (ГГГГ-ММ-ДД); пусто — последний день")
    ap.add_argument("--kind", default="catalog", help="вид: catalog / filters / shelfs")
    ap.add_argument("--limit", type=int, default=1, help="сколько файлов показать")
    a = ap.parse_args()

    base = RAW_ROOT / str(a.company_id)
    if not base.exists():
        print(f"нет папки {base}")
        return
    days = sorted([d for d in base.iterdir() if d.is_dir()])
    if a.date:
        days = [d for d in days if d.name == a.date]
    if not days:
        print("нет файлов")
        return

    day = days[-1]
    files = sorted(day.glob(f"*_{a.kind}_*.json"))
    files = [f for f in files if not f.name.endswith(".meta.json")]
    if not files:
        print(f"в {day.name} нет файлов вида {a.kind}")
        return

    for f in files[-a.limit:]:
        _scan(f, a.kind)


if __name__ == "__main__":
    main()
