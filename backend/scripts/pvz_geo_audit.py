#!/usr/bin/env python3
"""Аудит «координаты против региона»: лежит ли ПВЗ внутри полигона своего региона.

Использует упрощенные GeoJSON (public/geo/*_regions_simple.geojson).
Упрощение сдвигает границы (~км), поэтому несовпадением считаем только точку
дальше --max-ok-km от границы своего региона. Меньше — шум симплификации.

Покрытие полигонов: RU (без Крыма/Севастополя — их нет в файле 2013г),
BY (области + г.Минск), KZ (только области старого деления: без Астаны/Алматы/
Шымкента/Абайской/Жетысу/Улытауской/Туркестанской-в-новых-границах).
Нет полигона / нет координат / нет нормы — строка пропускается (статистика).

Запуск из корня проекта (нужны файлы границ):
  .venv/bin/python backend/scripts/pvz_geo_audit.py --geo-dir /var/www/wb/wbcms-web/geo
  .venv/bin/python backend/scripts/pvz_geo_audit.py --geo-dir ... --country ru --limit 5000
  .venv/bin/python backend/scripts/pvz_geo_audit.py --geo-dir ... --csv /tmp/mismatch.csv
  .venv/bin/python backend/scripts/pvz_geo_audit.py --geo-dir ... --mark --export-shuttle /tmp/audit_mm.json

Переработка найденного — штатным шаттлом (тот же формат, что pvz_check.py):
  --mark: dadata_status='mismatch' + снос *_norm (отчет сразу перестанет врать,
    нормы вернутся следующим прогоном pvz_norm.py после перепроверки);
  --export-shuttle FILE: JSON [{wb_id,country,address,lat,lon}] для локального
    dadata_recheck.py -> apply-results на сервере (статус geo).
  Дальше как обычно:
    python backend/scripts/dadata_recheck.py --in /tmp/audit_mm.json --out /tmp/res_mm.json --api-key KEY
    (на сервере) .venv/bin/python backend/scripts/pvz_import.py --dir ... --skip-import --apply-results /tmp/res_mm.json
    .venv/bin/python backend/scripts/pvz_norm.py
"""
import argparse
import asyncio
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from backend.database import get_session  # noqa: E402

_DROP = frozenset({"область", "обл", "край", "республика", "респ",
                   "автономный", "автономная", "ао", "округ"})


def _stem(s):
    import re
    toks = [t for t in re.sub(r"[^\w]+", " ", (s or "").lower().replace("ё", "е")).split()
            if t and t not in _DROP]
    return " ".join(toks)


# Полигон RU (имена 2013г) -> стем нормы. Остальное сходится стем-в-стем.
RU_POLY_FIX = {
    "ханты мансийский югра": "ханты мансийский",
    "еврейская": "еврейская автономная",
}

# GADM (BY/KZ): NAME_1|TYPE_1 -> русская норма как в отчете.
GADM_RU = {
    "Brest|Oblast": "Брестская область",
    "Gomel|Oblast": "Гомельская область",
    "Grodno|Oblast": "Гродненская область",
    "Minsk|Oblast": "Минская область",
    "Minsk|City": "Минск",
    "Mogilev|Oblast": "Могилевская область",
    "Vitebsk|Oblast": "Витебская область",
    "Almaty": "Алматинская область",
    "Aqmola": "Акмолинская область",
    "Aqtöbe": "Актюбинская область",
    "Atyrau": "Атырауская область",
    "EastKazakhstan": "Восточно-Казахстанская область",
    "Mangghystau": "Мангистауская область",
    "NorthKazakhstan": "Северо-Казахстанская область",
    "Pavlodar": "Павлодарская область",
    "Qaraghandy": "Карагандинская область",
    "Qostanay": "Костанайская область",
    "Qyzylorda": "Кызылординская область",
    "SouthKazakhstan": "Туркестанская область",  # старые границы (с Шымкентом) — приблизительно
    "WestKazakhstan": "Западно-Казахстанская область",
    "Zhambyl": "Жамбылская область",
}


def _rings(geom):
    t = geom.get("type")
    coords = geom.get("coordinates") or []
    if t == "Polygon":
        return [coords[0]] if coords and coords[0] else []
    if t == "MultiPolygon":
        return [p[0] for p in coords if p and p[0]]
    return []


def _bbox(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _dist_to_rings_km(lon, lat, rings):
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
    """-> dict[(country, normstem)] = list[(rings, bbox)]."""
    idx: dict = {}

    def add(cc, key, rings):
        if not rings:
            return
        boxes = [_bbox(r) for r in rings]
        idx.setdefault((cc, key), []).append((rings, boxes))

    ru = json.load(open(pathlib.Path(geo_dir) / "ru_regions_simple.geojson", encoding="utf-8"))
    for f in ru.get("features", []):
        nm = (f.get("properties") or {}).get("name", "")
        key = RU_POLY_FIX.get(_stem(nm), _stem(nm))
        add("ru", key, _rings(f.get("geometry") or {}))
    for fn, cc in (("by_regions_simple.geojson", "by"), ("kz_regions_simple.geojson", "kz")):
        try:
            d = json.load(open(pathlib.Path(geo_dir) / fn, encoding="utf-8"))
        except FileNotFoundError:
            continue
        for f in d.get("features", []):
            p = f.get("properties") or {}
            rus = GADM_RU.get(f"{p.get('NAME_1')}|{p.get('TYPE_1')}", GADM_RU.get(p.get("NAME_1"), ""))
            if rus:
                add(cc, _stem(rus), _rings(f.get("geometry") or {}))
    return idx


async def main() -> int:
    ap = argparse.ArgumentParser(description="Аудит координат ПВЗ против полигона региона")
    ap.add_argument("--geo-dir", required=True, help="каталог с *_regions_simple.geojson")
    ap.add_argument("--country", default=None, help="только ru/by/kz (по умолч. все три)")
    ap.add_argument("--limit", type=int, default=0, help="проверить только первые N (0 = все)")
    ap.add_argument("--max-ok-km", type=float, default=2.0,
                    help="точка ближе границы считается шумом симплификации")
    ap.add_argument("--csv", default=None, help="куда записать mismatches")
    ap.add_argument("--mark", action="store_true",
                    help="пометить найденное mismatch + снести *_norm (см. шапку)")
    ap.add_argument("--export-shuttle", default=None, metavar="FILE",
                    help="выгрузить найденное в JSON шаттла (формат pvz_check.py) для dadata_recheck.py")
    ap.add_argument("--batch-size", type=int, default=5000)
    args = ap.parse_args()

    polys = _load(args.geo_dir)
    n_poly = sum(len(v) for v in polys.values())
    print(f"polygons: {n_poly} regn-stems", flush=True)

    total = ok = bad = skipped = 0
    bad_rows = []
    async with get_session() as db:
        offset = 0
        while True:
            rows = (await db.execute(text("""
                SELECT wb_id, lat, lon, region_norm, country, address FROM pvz_all
                WHERE lat IS NOT NULL AND lon IS NOT NULL AND region_norm IS NOT NULL
                ORDER BY wb_id LIMIT :lim OFFSET :off
            """), {"lim": args.batch_size, "off": offset})).mappings().all()
            if not rows:
                break
            for r in rows:
                if args.limit and total >= args.limit:
                    break
                total += 1
                cc = str(r["country"] or "").lower()
                if args.country and cc != args.country:
                    skipped += 1
                    continue
                cands = polys.get((cc, _stem(r["region_norm"])))
                if not cands:
                    skipped += 1
                    continue
                lon, lat = float(r["lon"]), float(r["lat"])
                inside = False
                for rings, boxes in cands:
                    hit_box = any(b[0] <= lon <= b[2] and b[1] <= lat <= b[3] for b in boxes)
                    if hit_box and any(_in_ring(lon, lat, ring) for ring in rings):
                        inside = True
                        break
                if inside:
                    ok += 1
                    continue
                dist = min(_dist_to_rings_km(lon, lat, rings) for rings, _ in cands)
                if dist <= args.max_ok_km:
                    ok += 1
                    continue
                bad += 1
                bad_rows.append((r["wb_id"], cc, r["region_norm"], lat, lon, round(dist, 1),
                                 r["address"]))
            if args.limit and total >= args.limit:
                break
            offset += args.batch_size
    print(f"AUDIT total={total} ok={ok} mismatch={bad} skipped(no-poly/coords/filter)={skipped}",
          flush=True)
    by_region: dict = {}
    for _, cc, reg, lat, lon, dist, _ in bad_rows:
        by_region.setdefault((cc, reg), []).append(dist)
    for (cc, reg), ds in sorted(by_region.items(), key=lambda x: -len(x[1]))[:20]:
        print(f"  {cc} | {reg}: n={len(ds)} max_out={max(ds)}km", flush=True)
    if args.csv:
        import csv
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["wb_id", "country", "region_norm", "lat", "lon", "km_outside", "address"])
            w.writerows(bad_rows)
        print(f"csv: {args.csv} rows={len(bad_rows)}", flush=True)
    if args.mark:
        params = [{"w": b[0],
                   "e": f"geo-audit:outside {b[2]} {b[5]}km"[:500]} for b in bad_rows]
        async with get_session() as db2:
            if params:
                await db2.execute(text("""
                    UPDATE pvz_all SET dadata_status='mismatch', dadata_error=:e,
                      region_norm=NULL, city_norm=NULL
                    WHERE wb_id=:w
                """), params)
                await db2.commit()
        print(f"MARK mismatch: {len(params)} (нормы снесены, дальше --export-shuttle -> recheck -> norm)",
              flush=True)
    if args.export_shuttle:
        import json as _json
        if args.mark:
            # выгружаем только помеченное этим прогоном (как pvz_check.py),
            # а не весь исторический mismatch
            bad_ids = {b[0] for b in bad_rows}
            # выгружаем свежепомеченное из БД (как pvz_check.py --export-mismatch)
            async with get_session() as db3:
                rows3 = (await db3.execute(text("""
                    SELECT wb_id, country, address, lat, lon FROM pvz_all
                    WHERE dadata_status='mismatch'
                """))).mappings().all()
            rows3 = [r for r in rows3 if r["wb_id"] in bad_ids]
        else:
            # без --mark: только найденное этим прогоном
            rows3 = [{"wb_id": b[0], "country": b[1], "address": b[6],
                      "lat": b[3], "lon": b[4]} for b in bad_rows]
        out = [{"wb_id": r["wb_id"], "country": r["country"], "address": r["address"],
                "lat": float(r["lat"]) if r["lat"] is not None else None,
                "lon": float(r["lon"]) if r["lon"] is not None else None} for r in rows3]
        with open(args.export_shuttle, "w", encoding="utf-8") as f:
            _json.dump(out, f, ensure_ascii=False)
        print(f"EXPORT shuttle: {len(out)} -> {args.export_shuttle}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
