#!/usr/bin/env python3
"""РАЗОВАЯ заливка регионов по координатам (reverse-geocode своими полигонами).

DaData для am/kg/ge/tj/uz адрес не разбирает (ни suggest, ни geolocate), а у нас
есть полигоны областей + координаты каждой точки: ставим регион сами.
Статус — 'fix' (НЕ 'geo': там полный разбор DaData, а тут только регион;
миграция backend/migrations/20261020_pvz_status_fix.sql).

Что делает:
  1. Берёт строки со статусом --status (по умолч. not_found) и координатами.
  2. Ищет содержащий полигон своей страны (bbox-фильтр + ray casting).
  3. Точка глубже --min-inside-km от границы (по умолч. 1.0; шум упрощения
     границ не должен порождать ложные привязки к соседям).
  4. Пишет region/city=NULL, dadata_status='geo', norms (city_norm=NULL).

После: отчеты видят именованные регионы сразу (нормы пишутся тем же апдейтом).

Запуск (файлы границ уже лежат рядом с вебом):
  .venv/bin/python backend/scripts/pvz_geo_fill_once.py --geo-dir /var/www/wb/wbcms-web/geo --dry-run
  .venv/bin/python backend/scripts/pvz_geo_fill_once.py --geo-dir /var/www/wb/wbcms-web/geo
  .venv/bin/python backend/scripts/pvz_geo_fill_once.py --geo-dir ... --country uz --status pending
"""
import argparse
import asyncio
import json
import math
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from backend.database import get_session  # noqa: E402
from backend.services.geo_names import normalize_region  # noqa: E402

# Полигон -> русская норма региона. Только для заливки (разовый скрипт),
# финальный словарь живет здесь же — править при расхождениях.
POLY_RU = {
    ("by", "Brest", "Oblast"): "Брестская область",
    ("by", "Gomel", "Oblast"): "Гомельская область",
    ("by", "Grodno", "Oblast"): "Гродненская область",
    ("by", "Minsk", "Oblast"): "Минская область",
    ("by", "Minsk", "City"): "Минск",
    ("by", "Mogilev", "Oblast"): "Могилевская область",
    ("by", "Vitebsk", "Oblast"): "Витебская область",
    ("kz", "Almaty"): "Алматинская область",
    ("kz", "Aqmola"): "Акмолинская область",
    ("kz", "Aqtöbe"): "Актюбинская область",
    ("kz", "Atyrau"): "Атырауская область",
    ("kz", "EastKazakhstan"): "Восточно-Казахстанская область",
    ("kz", "Mangghystau"): "Мангистауская область",
    ("kz", "NorthKazakhstan"): "Северо-Казахстанская область",
    ("kz", "Pavlodar"): "Павлодарская область",
    ("kz", "Qaraghandy"): "Карагандинская область",
    ("kz", "Qostanay"): "Костанайская область",
    ("kz", "Qyzylorda"): "Кызылординская область",
    ("kz", "SouthKazakhstan"): "Туркестанская область",
    ("kz", "WestKazakhstan"): "Западно-Казахстанская область",
    ("kz", "Zhambyl"): "Жамбылская область",
    ("am", "Aragatsotn"): "Арагацотнская область",
    ("am", "Ararat"): "Араратская область",
    ("am", "Armavir"): "Армавирская область",
    ("am", "Erevan"): "Ереван",
    ("am", "Gegharkunik"): "Гехаркуникская область",
    ("am", "Kotayk"): "Котайская область",
    ("am", "Lori"): "Лорийская область",
    ("am", "Shirak"): "Ширакская область",
    ("am", "Syunik"): "Сюникская область",
    ("am", "Tavush"): "Тавушская область",
    ("am", "VayotsDzor"): "Вайоцдзорская область",
    ("ge", "Abkhazia"): "Абхазия",
    ("ge", "Ajaria"): "Аджария",
    ("ge", "Guria"): "Гурия",
    ("ge", "Imereti"): "Имеретия",
    ("ge", "Kakheti"): "Кахетия",
    ("ge", "KvemoKartli"): "Квемо-Картли",
    ("ge", "Mtskheta-Mtianeti"): "Мцхета-Мтианети",
    ("ge", "Racha-Lechkhumi-KvemoSvaneti"): "Рача-Лечхуми и Квемо-Сванети",
    ("ge", "Samegrelo-ZemoSvaneti"): "Самегрело-Земо Сванети",
    ("ge", "Samtskhe-Javakheti"): "Самцхе-Джавахети",
    ("ge", "ShidaKartli"): "Шида-Картли",
    ("ge", "Tbilisi"): "Тбилиси",
    ("kg", "Batken"): "Баткенская область",
    ("kg", "Biškek"): "Бишкек",
    ("kg", "Chüy"): "Чуйская область",
    ("kg", "Jalal-Abad"): "Джалал-Абадская область",
    ("kg", "Naryn"): "Нарынская область",
    ("kg", "Osh"): "Ошская область",
    ("kg", "Talas"): "Таласская область",
    ("kg", "Ysyk-Köl"): "Иссык-Кульская область",
    ("tj", "DistrictsofRepublicanSubordin"): "Районы республиканского подчинения",
    ("tj", "Dushanbe"): "Душанбе",
    ("tj", "Gorno-Badakhshan"): "Горно-Бадахшанская автономная область",
    ("tj", "Khatlon"): "Хатлонская область",
    ("tj", "Sughd"): "Согдийская область",
    ("uz", "Andijon"): "Андижанская область",
    ("uz", "Buxoro"): "Бухарская область",
    ("uz", "Farg'ona"): "Ферганская область",
    ("uz", "Jizzax"): "Джизакская область",
    ("uz", "Namangan"): "Наманганская область",
    ("uz", "Navoiy"): "Навоийская область",
    ("uz", "Qaraqalpaqstan"): "Республика Каракалпакстан",
    ("uz", "Qashqadaryo"): "Кашкадарьинская область",
    ("uz", "Samarqand'"): "Самаркандская область",
    ("uz", "Sirdaryo"): "Сырдарьинская область",
    ("uz", "Surxondaryo"): "Сурхандарьинская область",
    ("uz", "Toshkent"): "Ташкентская область",
    ("uz", "ToshkentShahri"): "Ташкент",
    ("uz", "Xorazm"): "Хорезмская область",
}


def _rings(geom):
    t = geom.get("type")
    coords = geom.get("coordinates") or []
    if t == "Polygon":
        return [coords[0]] if coords and coords[0] else []
    if t == "MultiPolygon":
        return [p[0] for p in coords if p and p[0]]
    return []


def _in_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi, xj, yj = ring[i][0], ring[i][1], ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _dist_km(lon, lat, rings):
    kx = 111.32 * math.cos(math.radians(lat))
    best = float("inf")
    for ring in rings:
        for i in range(len(ring)):
            x1, y1 = ring[i][0], ring[i][1]
            x2, y2 = ring[(i + 1) % len(ring)][0], ring[(i + 1) % len(ring)][1]
            dx, dy = (x2 - x1) * kx, (y2 - y1) * 110.57
            px, py = (lon - x1) * kx, (lat - y1) * 110.57
            seg2 = dx * dx + dy * dy
            t = max(0.0, min(1.0, (px * dx + py * dy) / seg2)) if seg2 else 0.0
            dd = math.hypot(px - dx * t, py - dy * t)
            if dd < best:
                best = dd
    return best


def _load(geo_dir):
    """[(cc, rus, rings, boxes)] — только со словарными именами."""
    out = []
    for fn, cc in (("ru_regions_simple.geojson", "ru"),
                   ("by_regions_simple.geojson", "by"),
                   ("kz_regions_simple.geojson", "kz"),
                   ("uz_regions_simple.geojson", "uz"),
                   ("am_regions_simple.geojson", "am"),
                   ("kg_regions_simple.geojson", "kg"),
                   ("ge_regions_simple.geojson", "ge"),
                   ("tj_regions_simple.geojson", "tj")):
        path = pathlib.Path(geo_dir) / fn
        if not path.exists():
            print(f"geo: НЕТ ФАЙЛА {path}", flush=True)
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            print(f"geo: НЕ ЧИТАЕТСЯ {path}: {type(e).__name__} {e}", flush=True)
            continue
        feats = d.get("features", [])
        n_ok = 0
        for f in feats:
            p = f.get("properties") or {}
            if cc == "ru":
                rus = p.get("name", "")
            else:
                # ключи словаря тройки (с пустым типом), поэтому пробуем все формы
                n, t = p.get("NAME_1", ""), p.get("TYPE_1", "")
                rus = (POLY_RU.get((cc, n, t))
                       or POLY_RU.get((cc, n, ""))
                       or POLY_RU.get((cc, n))
                       or "")
            if not rus:
                continue
            rings = _rings(f.get("geometry") or {})
            if rings:
                boxes = [(min(x[0] for x in r), min(x[1] for x in r),
                          max(x[0] for x in r), max(x[1] for x in r)) for r in rings]
                out.append((cc, rus, rings, boxes))
                n_ok += 1
        print(f"geo: {fn}: фич={len(feats)}, со словарем={n_ok}", flush=True)
    return out


async def main() -> int:
    ap = argparse.ArgumentParser(description="Разовая заливка регионов по координатам")
    ap.add_argument("--geo-dir", required=True)
    ap.add_argument("--status", default="not_found", help="какой статус разбирать")
    ap.add_argument("--country", default=None, help="только страна (uz/am/...)")
    ap.add_argument("--min-inside-km", type=float, default=1.0,
                    help="глубже границы — пишем, мельче — пропускаем (шум упрощения)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-size", type=int, default=2000)
    args = ap.parse_args()

    polys = _load(args.geo_dir)
    print(f"polygons: {len(polys)} (cc,rus)", flush=True)
    by_cc: dict = {}
    for cc, rus, rings, boxes in polys:
        by_cc.setdefault(cc, []).append((rus, rings, boxes))

    scanned = assigned = 0
    per_region: Counter = Counter()
    async with get_session() as db:
        last = 0
        while True:
            rows = (await db.execute(text("""
                SELECT wb_id, lat, lon, country FROM pvz_all
                WHERE dadata_status = :st AND lat IS NOT NULL AND lon IS NOT NULL
                AND (:cc IS NULL OR country = :cc) AND wb_id > :last
                ORDER BY wb_id LIMIT :lim
            """), {"st": args.status, "cc": args.country,
                   "last": last, "lim": args.batch_size})).mappings().all()
            if not rows:
                break
            batch = []
            for r in rows:
                scanned += 1
                cc = str(r["country"] or "").lower()
                lon, lat = float(r["lon"]), float(r["lat"])
                # из всех содержащих полигонов берем самый глубокий (упрощенные
                # границы на стыках перекрываются)
                best, best_d = None, 0.0
                for rus, rings, boxes in by_cc.get(cc, []):
                    if not any(b[0] <= lon <= b[2] and b[1] <= lat <= b[3] for b in boxes):
                        continue
                    if not any(_in_ring(lon, lat, ring) for ring in rings):
                        continue
                    dd = _dist_km(lon, lat, rings)
                    if dd > best_d:
                        best, best_d = rus, dd
                if best is not None and best_d >= args.min_inside_km:
                    rn = normalize_region(best)
                    batch.append({"w": r["wb_id"], "reg": best, "rn": rn})
                    per_region[best] += 1
            if batch and not args.dry_run:
                for b in batch:
                    await db.execute(text("""
                        UPDATE pvz_all SET region=:reg, city=NULL, dadata_status='fix',
                          dadata_error='poly:reverse-geocode', dadata_at=NOW(),
                          region_norm=:rn, city_norm=NULL
                        WHERE wb_id=:w
                    """), b)
                await db.commit()
                assigned += len(batch)
            elif args.dry_run:
                assigned += len(batch)
            last = rows[-1]["wb_id"]
    print(f"FILL scanned={scanned} "
          f"{'would_assign' if args.dry_run else 'assigned'}={assigned} status={args.status}",
          flush=True)
    for reg, cnt in per_region.most_common(30):
        print(f"  {reg}: {cnt}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
