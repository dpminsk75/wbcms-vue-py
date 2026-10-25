#!/usr/bin/env python3
"""Продажные офисы, которых нет в pvz_all, — добираем из имён в detail_by_period.

Проход 1: офис есть в dadata_address_cache (джойн по ppvz_office_id, точный) —
  вставляем строку origin='sales': адрес = имя из продаж, координаты из
  full_json.geo_lat/geo_lon (если есть), разбор и сырец — из кэша.
Проход 2: офиса нет и в кэше, но имя в продажах есть —
  вставляем скелет (address=имя, pending) под обычный шаттл.
dadata_address_cache НЕ ТРОГАЕМ (только SELECT). Без --apply — dry-run.

  .venv/bin/python backend/scripts/pvz_sales_import.py
  .venv/bin/python backend/scripts/pvz_sales_import.py --apply
"""

import argparse
import hashlib
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# legacy-метка сводных строк (как pvz_2026_99): источник не файл версий
SALES_VERSION = 99


def _load_dotenv(path: pathlib.Path) -> None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass


def _num(x, lo: float, hi: float):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v < lo or v > hi:
        return None
    return round(v, 8)


def _parse_suggestion(sug) -> dict | None:
    """Минимум mapDadataFields: город/регион/улица/дом/коды + нормализация столиц."""
    if isinstance(sug, str):
        try:
            sug = json.loads(sug)
        except json.JSONDecodeError:
            return None
    if not isinstance(sug, dict):
        return None
    if isinstance(sug.get("suggestions"), list):
        if not sug["suggestions"]:
            return None
        sug = sug["suggestions"][0]
    d = sug.get("data")
    if not isinstance(d, dict):
        return None
    city = d.get("city")
    if not city and d.get("region") in ("Москва", "Санкт-Петербург", "Севастополь"):
        city = d["region"]
    return {
        "dadata_result": sug.get("unrestricted_value") or sug.get("value"),
        "postal_code": d.get("postal_code"),
        "federal_district": d.get("federal_district"),
        "region": d.get("region_with_type") or d.get("region"),
        "region_iso_code": d.get("region_iso_code"),
        "city": city,
        "city_type": d.get("city_type"),
        "settlement": d.get("settlement_with_type") or d.get("settlement"),
        "city_district": d.get("city_district_with_type") or d.get("city_district"),
        "city_area": d.get("city_area"),
        "street": d.get("street_with_type") or d.get("street"),
        "house": d.get("house"),
        "fias_id": d.get("fias_id"),
        "kladr_id": d.get("kladr_id"),
        "qc_geo": d.get("qc_geo"),
        "geo_lat": d.get("geo_lat"),
        "geo_lon": d.get("geo_lon"),
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description="Добор продажных ПВЗ, отсутствующих в pvz_all")
    ap.add_argument("--apply", action="store_true",
                    help="БЕЗ флага — dry-run (только посчитать). С флагом — вставить")
    ap.add_argument("--limit", type=int, default=None, help="не более N офисов (для пробы)")
    args = ap.parse_args()

    _load_dotenv(ROOT / ".env")
    from backend.database import SessionLocal  # noqa: E402
    from sqlalchemy import text  # noqa: E402

    async with SessionLocal() as db:
        # Офисы продаж, которых нет в pvz_all: oid -> самое частое имя
        rows = (await db.execute(text("""
            SELECT d.ppvz_office_id AS oid, d.ppvz_office_name AS name, COUNT(*) AS c
            FROM detail_by_period d
            LEFT JOIN pvz_all p ON p.wb_id = d.ppvz_office_id
            WHERE d.ppvz_office_id IS NOT NULL AND d.ppvz_office_id <> 0
              AND p.wb_id IS NULL
            GROUP BY d.ppvz_office_id, d.ppvz_office_name
            ORDER BY d.ppvz_office_id, c DESC
        """))).mappings().all()
        offices: dict[int, str] = {}
        for r in rows:
            if r["oid"] not in offices and (r["name"] or "").strip():
                offices[r["oid"]] = r["name"].strip()
        empty_names = sum(1 for r in rows if not (r["name"] or "").strip())
        print(f"Офисов продаж без pvz_all: {len(offices)} (пустых имён пропущено: {empty_names})",
              flush=True)
        if args.limit:
            offices = dict(list(offices.items())[:args.limit])
            print(f"Проба: беру первые {args.limit}", flush=True)
        if not offices:
            return 0

        # Кэш по этим oid (точным джойном, как весь скрипт — только чтение)
        cache: dict[int, dict] = {}
        ids = list(offices)
        for i in range(0, len(ids), 1000):
            chunk = tuple(ids[i:i + 1000])
            from sqlalchemy import bindparam as _bp  # noqa: E402
            for c in (await db.execute(text("""
                    SELECT ppvz_office_id, is_error, result, full_json, postal_code,
                      federal_district, region, region_iso_code, city, city_type,
                      settlement, city_district, city_area
                    FROM dadata_address_cache WHERE ppvz_office_id IN :ids
                """).bindparams(_bp("ids", expanding=True)), {"ids": chunk})).mappings().all():
                cache[c["ppvz_office_id"]] = dict(c)
        print(f"Из них есть в кэше: {len(cache)}, скелетов под шаттл: {len(offices) - len(cache)}",
              flush=True)

        ins_cached = 0
        ins_skel = 0
        stat_json_found = 0
        stat_json_parsed = 0
        stat_json_null = 0
        for oid, name in offices.items():
            h = hashlib.md5(name.encode("utf-8")).hexdigest()
            c = cache.get(oid)
            if c is not None:
                raw = c["full_json"]
                if raw is None:
                    stat_json_null += 1
                    print(f"wb_id={oid}: full_json IS NULL в кэше", flush=True)
                else:
                    stat_json_found += 1
                if isinstance(raw, (bytes, bytearray)):
                    raw = bytes(raw).decode("utf-8", errors="replace")
                parse_err = None
                if isinstance(raw, (str, bytes, bytearray)):
                    # бывает двойное кодирование (JSON-строка в JSON-строке) — снимаем до 3 слоёв
                    for _ in range(3):
                        if not isinstance(raw, (str, bytes, bytearray)):
                            break
                        if isinstance(raw, (bytes, bytearray)):
                            raw = bytes(raw).decode("utf-8", errors="replace")
                        try:
                            raw = json.loads(raw, strict=False)  # в строках встречается \x01
                        except json.JSONDecodeError as e:
                            parse_err = str(e)[:120]
                            raw = None
                            break
                sug = None
                if isinstance(raw, dict):
                    sug = raw["suggestions"][0] if isinstance(raw.get("suggestions"), list) and raw["suggestions"] else raw
                f = _parse_suggestion(sug) if sug else None
                if f is not None:
                    stat_json_parsed += 1
                elif raw is not None:
                    print(f"wb_id={oid}: json есть ({len(json.dumps(raw, ensure_ascii=False))} симв.), "
                          f"но нет data: ключи={list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__}",
                          flush=True)
                elif parse_err:
                    print(f"wb_id={oid}: json НЕ парсится: {parse_err}", flush=True)
                if f is not None:
                    lat = _num(f.pop("geo_lat", None), -90, 90)
                    lon = _num(f.pop("geo_lon", None), -180, 180)
                    row = {"wb_id": oid, "address": name, "lat": lat, "lon": lon,
                           "status": "ok", "derr": None, **f,
                           "draw": json.dumps(sug, ensure_ascii=False), "hh": h}
                elif c.get("region") or c.get("city"):
                    lat = lon = None
                    row = {"wb_id": oid, "address": name, "lat": None, "lon": None,
                           "status": "ok", "derr": "cache:partial",
                           "dadata_result": c.get("result"), "postal_code": c.get("postal_code"),
                           "federal_district": c.get("federal_district"), "region": c.get("region"),
                           "region_iso_code": c.get("region_iso_code"), "area": None,
                           "city": c.get("city"), "city_type": c.get("city_type"),
                           "settlement": c.get("settlement"),
                           "city_district": c.get("city_district"), "city_area": c.get("city_area"),
                           "street": None, "street_type": None, "house": None, "block": None,
                           "fias_id": None, "kladr_id": None, "qc_geo": None,
                           "okato": None, "oktmo": None, "timezone": None,
                           "draw": None, "hh": h}
                elif c.get("is_error") == 1 or c.get("result") in (None, "NOT_FOUND"):
                    row = {"wb_id": oid, "address": name, "status": "not_found"}
                else:
                    row = {"wb_id": oid, "address": name, "status": "pending"}
                row["kind"] = "cached"
            else:
                row = {"wb_id": oid, "address": name, "status": "pending", "kind": "skeleton"}
            if args.apply:
                if row["kind"] == "skeleton" or row["status"] in ("pending", "not_found"):
                    await db.execute(text("""
                        INSERT INTO pvz_all (wb_id, country, address, origin,
                          source_version, first_seen_version, last_seen_at,
                          dadata_status, dadata_error, dadata_hash)
                        VALUES (:wb_id, 'ru', :address, 'sales',
                          :sv, :sv, NOW(), :stt,
                          :derr, :hh)
                    """), {"wb_id": oid, "address": name, "sv": SALES_VERSION,
                            "stt": row["status"],
                            "derr": ("cache:NOT_FOUND" if row["status"] == "not_found" else None),
                            "hh": h})
                    ins_skel += 1
                else:
                    await db.execute(text("""
                        INSERT INTO pvz_all (wb_id, country, address, lat, lon, origin,
                          source_version, first_seen_version, last_seen_at,
                          dadata_status, dadata_error, dadata_hash, dadata_raw, dadata_at,
                          dadata_result, postal_code, federal_district, region, region_iso_code,
                          area, city, city_type, settlement, city_district, city_area,
                          street, street_type, house, `block`, fias_id, kladr_id, qc_geo,
                          okato, oktmo, timezone)
                        VALUES (:wb_id, 'ru', :address, :lat, :lon, 'sales',
                          :sv, :sv, NOW(), 'ok', :derr, :hh, CAST(:draw AS JSON), NOW(),
                          :dadata_result, :postal_code, :federal_district, :region,
                          :region_iso_code, :area, :city, :city_type, :settlement,
                          :city_district, :city_area, :street, :street_type, :house,
                          :block, :fias_id, :kladr_id, :qc_geo, :okato, :oktmo, :timezone)
                    """), {"wb_id": oid, "address": name, "sv": SALES_VERSION, **{
                        k: row.get(k) for k in (
                            "lat", "lon", "derr", "hh", "draw", "dadata_result", "postal_code",
                            "federal_district", "region", "region_iso_code", "area", "city",
                            "city_type", "settlement", "city_district", "city_area", "street",
                            "street_type", "house", "block", "fias_id", "kladr_id", "qc_geo",
                            "okato", "oktmo", "timezone")}})
                    ins_cached += 1
            else:
                if row["kind"] == "skeleton" or row.get("status") in ("pending", "not_found"):
                    ins_skel += 1
                else:
                    ins_cached += 1
        if args.apply:
            await db.commit()
            print(f"Вставлено: с разбором={ins_cached} скелетов={ins_skel}", flush=True)
        else:
            print(f"DRY-RUN: с разбором={ins_cached} скелетов={ins_skel} (без --apply ничего не писалось)",
                  flush=True)
        print(f"JSON-статистика: найден={stat_json_found} распарсен={stat_json_parsed} "
              f"NULL={stat_json_null} (всего офисов с кэшем: {len([o for o in offices if o in cache])})",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(__import__("asyncio").run(main()))
