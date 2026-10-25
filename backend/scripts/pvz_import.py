#!/usr/bin/env python3
"""Импорт ПВЗ Wildberries из групповых файлов all-poo-fr-v*.json в `pvz_all`.

Только групповой формат (страна = ключ группы). Плоский all-poo.json НЕ берём:
там country INT/битмаска без маппинга — наплодим ошибок.

Порядок: файлы от старой версии к новой, upsert по wb_id (он глобально уникален
между странами — проверено на v12, 0 пересечений). Точки, которых нет в свежей
версии, помечаются is_closed=1.

DaData по умолчанию НЕ дёргаем (лимит 10к/день): сначала переиспользуем готовые
ответы из dadata_address_cache.full_json по md5(address). Живые запросы —
только с флагом --live-dadata.

Алерты о неразобранных адресах (оба):
  1. stdout: строки `UNRESOLVED <wb_id> ...` + итоговая SUMMARY (этот скрипт);
  2. SQL: view `pvz_unresolved` (см. backend/migrations/20261004_pvz_all.sql).

Запуск из корня проекта:
  .venv/bin/python backend/scripts/pvz_import.py --dir /opt/wbcms/pvz
  .venv/bin/python backend/scripts/pvz_import.py --dir /opt/wbcms/pvz --live-dadata --dadata-limit 5000
"""

import argparse
import asyncio
import hashlib
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ALLOWED_COUNTRIES = ("ru", "by", "kz", "uz", "am", "kg", "ge", "tj")
# Подсказка страны для suggest: для не-RU групп адрес без страны ("г Апрелевка, ...")
# DaData иначе ищет в России. geolocate при этом — только для ru (покрытие DaData).
COUNTRY_NAMES = {
    "ru": "Россия", "by": "Беларусь", "kz": "Казахстан", "uz": "Узбекистан",
    "am": "Армения", "kg": "Киргизия", "ge": "Грузия", "tj": "Таджикистан",
}

FNAME_RE = re.compile(r"all-poo-fr-v(\d+)\.json$")


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
    if v != v or v < lo or v > hi:  # NaN / вне диапазона
        return None
    return v


def _int(x):
    try:
        if x is None or isinstance(x, bool):
            return None
        return int(x)
    except (TypeError, ValueError):
        return None


def _bool(x):
    """isWb в старом 2022 — строка 'True'/'False', в остальных — bool/int."""
    if x is None:
        return None
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, (int, float)):
        return int(bool(x))
    if isinstance(x, str):
        s = x.strip().lower()
        if s in ("true", "1", "yes", "y", "да"):
            return 1
        if s in ("false", "0", "no", "n", "нет", ""):
            return 0
    return None


def _coords(item):
    """coordinates: [lat, lon] массивом (v2+, 2023) или строкой '[lat, lon]' (2022)."""
    c = item.get("coordinates")
    if isinstance(c, str):
        s = c.strip()
        try:
            c = json.loads(s)
        except json.JSONDecodeError:
            c = [p.strip(" []") for p in s.split(",")]
    if not isinstance(c, (list, tuple)) or len(c) < 2:
        return None, None
    lat = _num(c[0], -90, 90)
    lon = _num(c[1], -180, 180) if len(c) > 1 else None
    lat = round(lat, 8) if lat is not None else None
    lon = round(lon, 8) if lon is not None else None
    return lat, lon


def normalize_item(item: dict, country: str, version: int) -> dict | None:
    """Групповой формат v0..v12 -> строка pvz_all. None = пропуск.
    v0/v1 (2022/2023): workTime, dtype, isWb, pickupType, deliveryPrice.
    v2+: typePoint, props, dest*, rate (v11+), timeTableV2 (v12)."""
    wb_id = _int(item.get("id"))
    if not wb_id:
        return None
    lat, lon = _coords(item)
    # timeTableV2 в файле — JSON-строка, приводим к объекту
    timetable = None
    tt = item.get("timeTableV2")
    if isinstance(tt, str) and tt.strip():
        try:
            timetable = json.loads(tt)
        except json.JSONDecodeError:
            timetable = None
    elif isinstance(tt, (list, dict)):
        timetable = tt
    rate = _num(item.get("rate"), 0, 5)
    address = item.get("address")
    wt = item.get("workTime")
    work_time = wt if isinstance(wt, str) and wt.strip() else None
    return {
        "wb_id": wb_id,
        "country": country,
        "address": address,
        "lat": lat,
        "lon": lon,
        "timetable": json.dumps(timetable, ensure_ascii=False) if timetable is not None else None,
        "work_time": work_time,
        "rate": rate,
        "fitting_rooms": _int(item.get("fittingRooms")),
        "type_point": _int(item.get("typePoint")),
        "pickup_type": _int(item.get("pickupType")),
        "is_wb": _bool(item.get("isWb")),
        "dtype": _int(item.get("dtype")),
        "delivery_price": _int(item.get("deliveryPrice")),
        "wb_status": _int(item.get("status")),
        "props": _int(item.get("props")),
        "radius": _int(item.get("radius")),
        "dest": _int(item.get("dest")),
        "dest2": _int(item.get("dest2")),
        "dest3": _int(item.get("dest3")),
        "is_new": 1 if item.get("isNew") is True else 0,
        "source_version": version,
        "addr_hash": hashlib.md5((address or "").encode("utf-8")).hexdigest(),
        "raw_data": json.dumps(item, ensure_ascii=False),
    }


# --- DaData: разбор готового ответа (формат как в dadata_address_cache.full_json) ---

def parse_dadata_suggestion(sug) -> dict | None:
    """Нормализация одного suggestion {value, unrestricted_value, data} + фиксы
    Москвы/СПб/Севастополя (как mapDadataFields в AddressProcessorController)."""
    if isinstance(sug, str):
        try:
            sug = json.loads(sug, strict=False)  # в строках встречается \x01
        except json.JSONDecodeError:
            return None
    if not isinstance(sug, dict):
        return None
    if isinstance(sug.get("suggestions"), list):  # сырой ответ API целиком
        if not sug["suggestions"]:
            return None
        sug = sug["suggestions"][0]
    d = sug.get("data")
    if not isinstance(d, dict):
        return None
    city = d.get("city")
    city_type = d.get("city_type")
    city_type_full = d.get("city_type_full")
    if not city and d.get("region") in ("Москва", "Санкт-Петербург", "Севастополь"):
        city, city_type, city_type_full = d["region"], "г", "город"
    return {
        "dadata_result": sug.get("unrestricted_value") or sug.get("value"),
        "postal_code": d.get("postal_code"),
        "federal_district": d.get("federal_district"),
        "region": d.get("region_with_type") or d.get("region"),
        "region_iso_code": d.get("region_iso_code"),
        "area": d.get("area_with_type") or d.get("area"),
        "city": city,
        "city_type": city_type,
        "settlement": d.get("settlement_with_type") or d.get("settlement"),
        "city_district": d.get("city_district_with_type") or d.get("city_district"),
        "city_area": d.get("city_area"),
        "street": d.get("street_with_type") or d.get("street"),
        "street_type": d.get("street_type"),
        "house": d.get("house"),
        "block": d.get("block"),
        "fias_id": d.get("fias_id"),
        "kladr_id": d.get("kladr_id"),
        "qc_geo": _int(d.get("qc_geo")),
        "okato": d.get("okato"),
        "oktmo": d.get("oktmo"),
        "timezone": d.get("timezone"),
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description="Импорт all-poo-fr-v*.json в pvz_all")
    ap.add_argument("--dir", default="/opt/wbcms/pvz",
                    help="каталог с all-poo-fr-v*.json (по умолч. /opt/wbcms/pvz)")
    ap.add_argument("--min-version", type=int, default=0,
                    help="брать файлы только с этой версии (напр. 12 — только v12)")
    ap.add_argument("--batch-size", type=int, default=1000)
    ap.add_argument("--live-dadata", action="store_true",
                    help="добивать pending живыми запросами DaData (по умолч. выкл: только кэш)")
    ap.add_argument("--dadata-limit", type=int, default=9000,
                    help="макс. живых запросов за прогон (по умолч. 9000, фри-лимит 10000/день)")
    ap.add_argument("--skip-import", action="store_true",
                    help="пропустить файлы, выполнить только кэш-DaData + live + UNRESOLVED")
    ap.add_argument("--country", default=None,
                    help="только эта страна в live-фазе (напр. --country by). Кэш-фаза всегда по всем")
    ap.add_argument("--geolocate-only", action="store_true",
                    help="в live-фазе только geolocate по координатам, без suggest")
    ap.add_argument("--export-pending", default=None, metavar="FILE",
                    help="выгрузить строки для обработки вне сервера и выйти (файловый шаттл при битом egress)")
    ap.add_argument("--sales-priority", action="store_true",
                    help="с --export-pending: только офисы, встречающиеся в продажах (detail_by_period)")
    ap.add_argument("--export-status", default="pending",
                    help="какой статус выгружать (по умолч. pending; для добивки moved: moved)")
    ap.add_argument("--limit", type=int, default=None,
                    help="чанк экспорта: сколько строк (с --export-pending)")
    ap.add_argument("--offset", type=int, default=0,
                    help="чанк экспорта: пропуск первых N (с --export-pending)")
    ap.add_argument("--apply-results", default=None, metavar="FILE", action="append",
                    help="применить JSON с ответами DaData (можно несколько раз, по возрастанию даты;"
                    " маска /tmp/res_*.json тоже работает)")
    ap.add_argument("--raw-only", action="store_true",
                    help="с --apply-results: обновить ТОЛЬКО dadata_raw, колонки и статусы не трогать")
    args = ap.parse_args()

    _load_dotenv(ROOT / ".env")
    from backend.database import SessionLocal  # noqa: E402
    from sqlalchemy import text  # noqa: E402

    src = pathlib.Path(args.dir)
    files = sorted(
        ((int(FNAME_RE.search(p.name).group(1)), p) for p in src.glob("all-poo-fr-v*.json")
         if FNAME_RE.search(p.name)),
        key=lambda t: t[0],
    )
    if args.min_version:
        files = [(v, p) for v, p in files if v >= args.min_version]
    if not files and not args.skip_import:
        print(f"ERR: в {src} нет all-poo-fr-v*.json", flush=True)
        return 1
    if args.skip_import:
        files = []  # только кэш-DaData + live + UNRESOLVED, без перебора файлов
    if files:
        print(f"Файлы (старые -> новые): {', '.join(p.name for _, p in files)}", flush=True)

    inserted = updated = filtered = skipped = moved = 0
    from collections import Counter  # noqa: E402
    filtered_by: Counter = Counter()
    closed = 0
    max_version = files[-1][0] if files else 0

    async with SessionLocal() as db:
        # Файловый шаттл, шаг 1: выгрузка строк для обработки вне сервера
        if args.export_pending:
            q = """SELECT p.wb_id, p.country, p.address, p.lat, p.lon FROM pvz_all p
                WHERE p.dadata_status=:stt"""
            prm: dict = {"stt": args.export_status}
            if args.sales_priority:
                q += (" AND EXISTS (SELECT 1 FROM detail_by_period d"
                      " WHERE d.ppvz_office_id = p.wb_id)")
            if args.country:
                q += " AND p.country=:cc"
                prm["cc"] = args.country
            q += " ORDER BY p.wb_id"
            if args.limit:
                q += " LIMIT :lim OFFSET :off"
                prm["lim"] = args.limit
                prm["off"] = args.offset
            rows = (await db.execute(text(q), prm)).mappings().all()
            out = [{"wb_id": r["wb_id"], "country": r["country"], "address": r["address"],
                    "lat": float(r["lat"]) if r["lat"] is not None else None,
                    "lon": float(r["lon"]) if r["lon"] is not None else None} for r in rows]
            with open(args.export_pending, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            print(f"EXPORT pending: {len(out)} -> {args.export_pending}", flush=True)
            return 0
        if not files:
            max_version = (await db.execute(
                text("SELECT COALESCE(MAX(source_version), 0) AS mv FROM pvz_all"))).mappings().first()["mv"]
            print(f"--skip-import: файлы пропущены, max_version в таблице = {max_version}", flush=True)
        # Карта существующих: wb_id -> (address, hash, first_ver, country, lat, lon)
        existing = {}
        rows = (await db.execute(
            text("SELECT wb_id, address, dadata_hash, first_seen_version, country, lat, lon"
                 " FROM pvz_all"))).mappings().all()
        for r in rows:
            existing[r["wb_id"]] = (r["address"], r["dadata_hash"], r["first_seen_version"],
                                    (r["country"] or "").lower(), r["lat"], r["lon"])
        print(f"В таблице уже: {len(existing)}", flush=True)

        ins_sql = text("""
            INSERT INTO pvz_all (wb_id, country, address, lat, lon, timetable, work_time, rate,
              fitting_rooms, type_point, pickup_type, is_wb, dtype, delivery_price,
              wb_status, props, radius, `dest`, dest2, dest3,
              is_new, source_version, first_seen_version, last_seen_at, is_closed, closed_at,
              dadata_hash, raw_data)
            VALUES (:wb_id, :country, :address, :lat, :lon, CAST(:timetable AS JSON), :work_time, :rate,
              :fitting_rooms, :type_point, :pickup_type, :is_wb, :dtype, :delivery_price,
              :wb_status, :props, :radius, :dest, :dest2, :dest3,
              :is_new, :source_version, :source_version, NOW(), 0, NULL, :addr_hash, CAST(:raw_data AS JSON))
        """)
        upd_base_sql = text("""
            UPDATE pvz_all SET country=:country, address=:address, lat=:lat, lon=:lon,
              timetable=CAST(:timetable AS JSON), rate=:rate, fitting_rooms=:fitting_rooms,
              type_point=:type_point, wb_status=:wb_status, props=:props, radius=:radius,
              `dest`=:dest, dest2=:dest2, dest3=:dest3, is_new=:is_new,
              /* legacy-поля только из старых файлов — новые их не затирают */
              work_time=COALESCE(:work_time, work_time),
              pickup_type=COALESCE(:pickup_type, pickup_type),
              is_wb=COALESCE(:is_wb, is_wb),
              dtype=COALESCE(:dtype, dtype),
              delivery_price=COALESCE(:delivery_price, delivery_price),
              source_version=:source_version, last_seen_at=NOW(), is_closed=0, closed_at=NULL,
              dadata_hash=:addr_hash, raw_data=CAST(:raw_data AS JSON)
              /* dadata_status трогаем только при смене адреса, отдельным запросом */
            WHERE wb_id=:wb_id
        """)

        async def safe_batch(stmt, batch, label):
            """Пакетная вставка; при ошибке — построчно, битые строки в SKIP-лог, не валим весь прогон."""
            nonlocal skipped
            try:
                await db.execute(stmt, batch)
                await db.commit()
                return len(batch)
            except Exception as e:  # noqa: BLE001
                print(f"BATCH-FAIL {label} ({len(batch)} шт.): {str(e)[:200]} — разбираю построчно",
                      flush=True)
                await db.rollback()
                ok = 0
                for row in batch:
                    try:
                        await db.execute(stmt, [row])
                        await db.commit()
                        ok += 1
                    except Exception as e2:  # noqa: BLE001
                        skipped += 1
                        print(f"SKIP {label} wb_id={row.get('wb_id')} "
                              f"lat={row.get('lat')} lon={row.get('lon')} rate={row.get('rate')} "
                              f"addr={(row.get('address') or '')[:60]!r}: {str(e2)[:200]}",
                              flush=True)
                        await db.rollback()
                return ok

        upd_moved_sql = text("""
            UPDATE pvz_all SET country=:country, address=:address, lat=:lat, lon=:lon,
              timetable=CAST(:timetable AS JSON), rate=:rate, fitting_rooms=:fitting_rooms,
              type_point=:type_point, wb_status=:wb_status, props=:props, radius=:radius,
              `dest`=:dest, dest2=:dest2, dest3=:dest3, is_new=:is_new,
              work_time=COALESCE(:work_time, work_time),
              pickup_type=COALESCE(:pickup_type, pickup_type),
              is_wb=COALESCE(:is_wb, is_wb),
              dtype=COALESCE(:dtype, dtype),
              delivery_price=COALESCE(:delivery_price, delivery_price),
              source_version=:source_version, last_seen_at=NOW(), is_closed=0, closed_at=NULL,
              first_seen_version=:source_version, first_seen_at=NOW(),
              dadata_hash=:addr_hash, raw_data=CAST(:raw_data AS JSON),
              dadata_status='moved', dadata_error='recycled-id', dadata_at=NULL,
              dadata_result=NULL, postal_code=NULL, federal_district=NULL, region=NULL,
              region_iso_code=NULL, area=NULL, city=NULL, city_type=NULL, settlement=NULL,
              city_district=NULL, city_area=NULL, street=NULL, street_type=NULL, house=NULL,
              `block`=NULL, fias_id=NULL, kladr_id=NULL, qc_geo=NULL, okato=NULL, oktmo=NULL,
              timezone=NULL
            WHERE wb_id=:wb_id
        """)

        def _is_recycle(prev_country, prev_lat, prev_lon, row) -> bool:
            """Реюз ID под другую точку: смена страны или сдвиг координат > ~1 км (0.01°)."""
            if (prev_country or "") != (row["country"] or ""):
                return True
            try:
                if prev_lat is not None and prev_lon is not None \
                        and row["lat"] is not None and row["lon"] is not None:
                    if abs(float(prev_lat) - row["lat"]) > 0.01 \
                            or abs(float(prev_lon) - row["lon"]) > 0.01:
                        return True
            except (TypeError, ValueError):
                return True
            return False

        async def flush_batches():
            nonlocal inserted, updated, moved, ins_batch, upd_batch
            if ins_batch:
                inserted += await safe_batch(ins_sql, ins_batch, "ins")
                ins_batch = []
            if upd_batch:
                same = [u for u in upd_batch if not u.get("_recycle")]
                recy = [u for u in upd_batch if u.get("_recycle")]
                if same:
                    n = await safe_batch(upd_base_sql, [{k: v for k, v in u.items()
                                                         if k not in ("dadata_status", "dadata_error", "_recycle")}
                                                        for u in same], "upd")
                    updated += n
                if recy:
                    n = await safe_batch(upd_moved_sql, [{k: v for k, v in u.items()
                                                          if k not in ("dadata_status", "dadata_error", "_recycle")}
                                                         for u in recy], "mov")
                    moved += n
                upd_batch = []

        for version, path in files:
            print(f"-- {path.name} ...", flush=True)
            with open(path, encoding="utf-8") as f:
                data = json.load(f, strict=False)  # в строках WB встречается \\x01
            ins_batch, upd_batch = [], []
            n_file = n_flush = 0
            for group in data:
                cc = (group.get("country") or "").lower()
                items = group.get("items") or []
                if cc not in ALLOWED_COUNTRIES:
                    filtered += len(items)
                    filtered_by[cc or "?"] += len(items)
                    continue
                for item in items:
                    row = normalize_item(item, cc, version)
                    if row is None:
                        filtered += 1
                        continue
                    n_file += 1
                    prev = existing.get(row["wb_id"])
                    if prev is None:
                        ins_batch.append(row)
                        existing[row["wb_id"]] = (row["address"], row["addr_hash"], version,
                                                  row["country"], row["lat"], row["lon"])
                    else:
                        prev_addr, prev_hash, prev_first, prev_cc, prev_lat, prev_lon = prev
                        # переформат (та же страна+точка): адрес обновляем, разбор НЕ трогаем.
                        # реюз ID (другая страна/точка): статус moved, разбор сносим (в upd_moved_sql).
                        row["_recycle"] = _is_recycle(prev_cc, prev_lat, prev_lon, row)
                        upd_batch.append(row)
                        first = version if row["_recycle"] else prev_first
                        existing[row["wb_id"]] = (row["address"], row["addr_hash"], first,
                                                  row["country"], row["lat"], row["lon"])
                    if len(ins_batch) >= args.batch_size or len(upd_batch) >= args.batch_size:
                        await flush_batches()
                        n_flush += 1
                        if n_flush % 10 == 0:
                            print(f"   ...{path.name}: строк {n_file}, ins={inserted} upd={updated} moved={moved}",
                                  flush=True)
            # сброс остатков файла
            await flush_batches()
            await db.commit()
            fb = "{" + ", ".join(f"{k}:{v}" for k, v in sorted(filtered_by.items())) + "}" if filtered_by else "{}"
            print(f"   +ins={inserted} ~upd={updated} moved={moved} skip-country={filtered} {fb}", flush=True)

        # Закрытые: не виделись в свежей версии (только при прогоне файлов)
        if files:
            closed = (await db.execute(text("""
                UPDATE pvz_all SET is_closed=1, closed_at=NOW()
                WHERE source_version < :mv AND is_closed=0
            """), {"mv": max_version})).rowcount
            await db.commit()
            print(f"CLOSED (нет в v{max_version}): {closed}", flush=True)

        # --- DaData из кэша (без API) ---
        pend = (await db.execute(text("""
            SELECT wb_id, address FROM pvz_all WHERE dadata_status='pending'
        """))).mappings().all()
        print(f"pending DaData: {len(pend)}", flush=True)
        from_cache = 0
        CHUNK = 1000
        from sqlalchemy import bindparam as _bp  # noqa: E402
        ok_sql = text("""
            UPDATE pvz_all SET dadata_status='ok', dadata_error=:derr, dadata_at=NOW(),
              dadata_hash=:hh, dadata_raw=CAST(:draw AS JSON),
              dadata_result=:dadata_result, postal_code=:postal_code,
              federal_district=:federal_district, region=:region,
              region_iso_code=:region_iso_code, area=:area, city=:city,
              city_type=:city_type, settlement=:settlement, city_district=:city_district,
              city_area=:city_area, street=:street, street_type=:street_type,
              house=:house, `block`=:block, fias_id=:fias_id, kladr_id=:kladr_id,
              qc_geo=:qc_geo, okato=:okato, oktmo=:oktmo, timezone=:timezone
            WHERE wb_id=:w
        """)
        notfound_sql = text("""
            UPDATE pvz_all SET dadata_status='not_found',
              dadata_error='cache:NOT_FOUND', dadata_at=NOW() WHERE wb_id=:w
        """)
        nodata_sql = text("""
            UPDATE pvz_all SET dadata_error='cache:no-data' WHERE wb_id=:w
        """)

        async def apply_cache_row(wid: int, c) -> None:
            """Трёхветка: full_json -> ok | region/city -> ok partial | мусор -> not_found/pending."""
            raw = c["full_json"]
            if isinstance(raw, (bytes, bytearray)):
                raw = bytes(raw).decode("utf-8", errors="replace")
            if isinstance(raw, str):
                # бывает двойное кодирование (JSON-строка в JSON-строке) — снимаем до 3 слоёв
                for _ in range(3):
                    if not isinstance(raw, str):
                        break
                    try:
                        raw = json.loads(raw, strict=False)  # в строках встречается \x01
                    except json.JSONDecodeError:
                        raw = None
                        break
            sug_obj = None
            if isinstance(raw, dict):
                sug_obj = raw["suggestions"][0] if isinstance(raw.get("suggestions"), list) and raw["suggestions"] else raw
            fields = parse_dadata_suggestion(sug_obj) if sug_obj else None
            draw = json.dumps(sug_obj, ensure_ascii=False) if sug_obj else None
            if fields is not None:
                fields.update({"w": wid, "derr": None, "draw": draw})
                await db.execute(ok_sql, {**fields, "hh": c["hash"]})
            elif c.get("region") or c.get("city"):
                # full_json нет, но регион/город заполнены из других источников (wb_sales/ручной маппинг)
                # NB: street/house в кэше нет как колонок — только из full_json (ветка выше)
                await db.execute(ok_sql, {
                    "w": wid, "derr": "cache:partial", "hh": c.get("hash"), "draw": draw,
                    "dadata_result": c.get("result"), "postal_code": c.get("postal_code"),
                    "federal_district": c.get("federal_district"), "region": c.get("region"),
                    "region_iso_code": c.get("region_iso_code"), "area": None,
                    "city": c.get("city"), "city_type": c.get("city_type"),
                    "settlement": c.get("settlement"), "city_district": c.get("city_district"),
                    "city_area": c.get("city_area"), "street": None,
                    "street_type": None, "house": None, "block": None,
                    "fias_id": None, "kladr_id": None, "qc_geo": None,
                    "okato": None, "oktmo": None, "timezone": None})
            elif c["is_error"] == 1 or (c.get("result") in (None, "NOT_FOUND")):
                await db.execute(notfound_sql, {"w": wid})
            else:
                await db.execute(nodata_sql, {"w": wid})

        cache_cols = """`hash`, ppvz_office_id, is_error, result, full_json, postal_code,
          federal_district, region, region_iso_code, city, city_type, settlement,
          city_district, city_area"""

        # Проход 1 (точный): ppvz_office_id = wb_id. ~38% покрытия, строки не зависят от формата адреса.
        for i in range(0, len(pend), CHUNK):
            ids = tuple(r["wb_id"] for r in pend[i:i + CHUNK])
            cache = (await db.execute(text(f"""
                SELECT {cache_cols} FROM dadata_address_cache WHERE ppvz_office_id IN :ids
            """).bindparams(_bp("ids", expanding=True)), {"ids": ids})).mappings().all()
            for c in cache:
                await apply_cache_row(c["ppvz_office_id"], c)
                from_cache += 1
        await db.commit()
        print(f"Из кэша по ID: {from_cache}", flush=True)

        # Проход 2 (строчный): md5(address) — для тех, кого не было в проходе 1.
        pend2 = (await db.execute(text("""
            SELECT wb_id, address FROM pvz_all WHERE dadata_status='pending'
        """))).mappings().all()
        md5hits = 0
        for i in range(0, len(pend2), CHUNK):
            chunk = pend2[i:i + CHUNK]
            hashes = {hashlib.md5((r["address"] or "").encode("utf-8")).hexdigest(): r["wb_id"]
                      for r in chunk}
            cache = (await db.execute(text(f"""
                SELECT {cache_cols} FROM dadata_address_cache WHERE `hash` IN :hh
            """).bindparams(_bp("hh", expanding=True)), {"hh": tuple(hashes)})).mappings().all()
            for c in cache:
                await apply_cache_row(hashes[c["hash"]], c)
                md5hits += 1
        await db.commit()
        print(f"Из кэша по md5: {md5hits}", flush=True)

        # --- Живые запросы (опционально) ---
        if args.live_dadata:
            from_cache_live = await _live_dadata(db, args.dadata_limit, args.country,
                                                 args.geolocate_only)
            print(f"Живых запросов DaData: {from_cache_live}", flush=True)

        # --- Файловый шаттл, шаг 3: применение ответов, собранных вне сервера ---
        # Файлов можно несколько (повтор флага) или маской; идут от старых к свежим по mtime.
        # --raw-only: обновить ТОЛЬКО dadata_raw (replay старых res-файлов без трогания колонок).
        if args.apply_results:
            import glob as _glob  # noqa: E402
            import gzip as _gz  # noqa: E402
            _files: list[str] = []
            for _pat in args.apply_results:
                _hit = sorted(_glob.glob(_pat))
                if not _hit:
                    print(f"APPLY: по маске {_pat} ничего не найдено — пропускаю", flush=True)
                _files.extend(_hit)
            _files.sort(key=lambda p: os.path.getmtime(p))
            if not _files:
                print("APPLY: нет файлов, нечего делать", flush=True)
                return 0
            n_ok = n_nf = n_tr = n_raw = 0
            for _af in _files:
                opener = _gz.open if str(_af).endswith(".gz") else open
                with opener(_af, "rt", encoding="utf-8-sig") as f:
                    results = json.load(f)
                print(f"APPLY: {len(results)} строк из {_af}"
                      + (" [только raw]" if args.raw_only else ""), flush=True)
                for j, e in enumerate(results, 1):
                    if args.raw_only:
                        if e.get("suggestion") is not None:
                            # перезаписываем всегда: старый raw мог быть ошибочным (ID-джойн),
                            # побеждает более поздний файл
                            await db.execute(text("""
                                UPDATE pvz_all SET dadata_raw=CAST(:raw AS JSON)
                                WHERE wb_id=:w
                            """), {"raw": json.dumps(e["suggestion"], ensure_ascii=False),
                                    "w": e["wb_id"]})
                            n_raw += 1
                        if j % 100 == 0:
                            await db.commit()
                        if j % 500 == 0:
                            print(f"APPLY-raw: {j}/{len(results)}", flush=True)
                        continue
                    err = e.get("error")
                    if e.get("suggestion") is not None:
                        st = await _store_live(db, e["wb_id"], e.get("address") or "", e["suggestion"],
                                               ok_status="geo" if e.get("method") == "geolocate" else "ok")
                    elif err in (None, "NOT_FOUND"):
                        st = await _store_live(db, e["wb_id"], e.get("address") or "", None)
                    else:  # TRANSPORT*: сеть/429 на локальной машине — оставить pending для повтора
                        st = await _store_live(db, e["wb_id"], e.get("address") or "", None,
                                               transport_err=str(err))
                    await db.commit()
                    if st in ("ok", "geo"):
                        n_ok += 1
                    elif st == "not_found":
                        n_nf += 1
                    else:
                        n_tr += 1
                    if j % 500 == 0:
                        print(f"APPLY: {j}/{len(results)} ok={n_ok} not_found={n_nf}", flush=True)
            if args.raw_only:
                await db.commit()
                print(f"APPLY-raw итог: записано raw={n_raw}", flush=True)
            else:
                print(f"APPLY итог: ok={n_ok} not_found={n_nf} transport-retry={n_tr}",
                      flush=True)

        # --- Алерт №1: UNRESOLVED в stdout (ok и geo — хорошие разборы) ---
        # Полный список — в view pvz_unresolved; в консоль только первые 20 для образца.
        bad = (await db.execute(text("""
            SELECT wb_id, country, address, dadata_status, dadata_error
            FROM pvz_all WHERE dadata_status NOT IN ('ok', 'geo') ORDER BY country, wb_id
        """))).mappings().all()
        for b in bad[:20]:
            print(f"UNRESOLVED {b['wb_id']} {b['country']} {b['dadata_status']} "
                  f"{b['dadata_error'] or '-'} | {(b['address'] or '')[:120]}", flush=True)
        if len(bad) > 20:
            print(f"... всего неразобранных: {len(bad)} (SELECT * FROM pvz_unresolved)",
                  flush=True)
        by_status = (await db.execute(text("""
            SELECT dadata_status, COUNT(*) c FROM pvz_all GROUP BY dadata_status
        """))).mappings().all()
        print("SUMMARY " + " ".join(f"{r['dadata_status']}={r['c']}" for r in by_status)
              + f" closed={closed} moved={moved} filtered_country={filtered} skipped_bad={skipped} "
              f"cache_id={from_cache} cache_md5={md5hits} max_version={max_version}",
              flush=True)
        return 2 if bad else 0


async def _store_live(db, wb_id: int, addr: str, sug, transport_err: str | None = None,
                    ok_status: str = "ok") -> str:
    """Сохранить результат живого запроса ТОЛЬКО в pvz_all. Возвращает итог.
    dadata_address_cache НЕ ТРОГАЕМ (только чтение в кэш-проходе).
    ok_status: 'ok' (обычно) или 'geo' (разобрано по координатам, apply --recheck)."""
    from sqlalchemy import text  # noqa: E402
    h = hashlib.md5((addr or "").encode("utf-8")).hexdigest()
    if transport_err:
        await db.execute(text("""
            UPDATE pvz_all SET dadata_error=:e WHERE wb_id=:w AND dadata_status='pending'
        """), {"e": f"live:transport:{transport_err}"[:500], "w": wb_id})
        return "transport"
    if sug is None:
        await db.execute(text("""
            UPDATE pvz_all SET dadata_status='not_found', dadata_error='live:NOT_FOUND',
              dadata_at=NOW() WHERE wb_id=:w
        """), {"w": wb_id})
        return "not_found"
    fields = parse_dadata_suggestion(sug)
    if fields is None:
        await db.execute(text("""
            UPDATE pvz_all SET dadata_status='error', dadata_error='live:parse',
              dadata_at=NOW() WHERE wb_id=:w
        """), {"w": wb_id})
        return "parse_error"
    fields.update({"w": wb_id, "hh": h, "stt": ok_status,
                   "draw": json.dumps(sug, ensure_ascii=False)})
    await db.execute(text("""
        UPDATE pvz_all SET dadata_status=:stt, dadata_error=NULL, dadata_at=NOW(),
          dadata_hash=:hh, dadata_raw=CAST(:draw AS JSON),
          dadata_hash=:hh, dadata_result=:dadata_result, postal_code=:postal_code,
          federal_district=:federal_district, region=:region,
          region_iso_code=:region_iso_code, area=:area, city=:city,
          city_type=:city_type, settlement=:settlement, city_district=:city_district,
          city_area=:city_area, street=:street, street_type=:street_type,
          house=:house, `block`=:block, fias_id=:fias_id, kladr_id=:kladr_id,
          qc_geo=:qc_geo, okato=:okato, oktmo=:oktmo, timezone=:timezone
        WHERE wb_id=:w
    """), fields)
    return ok_status


async def _live_dadata(db, limit: int, only_country: str | None = None,
                     geolocate_only: bool = False) -> int:
    """Добивка pending живыми suggest->geolocate. Останавливаемся на 429/Forbidden.
    suggest: для не-ru групп префикс страны (адреса WB без страны). geolocate: только ru."""
    import urllib.request
    import socket as _socket
    # Сервер с битым IPv6-egress: urllib перебирает AAAA->A медленно (по timeout на адрес),
    # а curl/PHP переключаются мгновенно. Принудительно IPv4 первым.
    _orig_gai = _socket.getaddrinfo

    def _gai_ipv4_first(*a, **k):
        try:
            res = _orig_gai(*a, **k)
        except Exception:
            raise
        return sorted(res, key=lambda r: r[0] != _socket.AF_INET)

    _socket.getaddrinfo = _gai_ipv4_first
    key = os.getenv("DADATA_API_KEY") or os.getenv("DADATA_TOKEN")
    secret = os.getenv("DADATA_SECRET_KEY")  # как dadataSecretApiKey в PHP; для suggest/geolocate не обязателен
    if not key:
        print("ERR: нет DADATA_API_KEY в .env — живые запросы пропущены", flush=True)
        return 0
    from sqlalchemy import text  # noqa: E402
    q = """SELECT wb_id, country, address, lat, lon FROM pvz_all
        WHERE dadata_status='pending'"""
    params: dict = {}
    if only_country:
        q += " AND country=:cc"
        params["cc"] = only_country
    q += " ORDER BY wb_id LIMIT :lim"
    params["lim"] = limit
    pend = (await db.execute(text(q), params)).mappings().all()

    def call(method: str, payload: dict):
        url = ("https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
               if method == "suggest" else
               "https://suggestions.dadata.ru/suggestions/api/4_1/rs/geolocate/address")
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "Authorization": "Token " + key}
        if secret:
            headers["X-Secret"] = secret
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status != 200:
                    return r.status, {}, True  # транспортная ошибка — повторим позже
                return r.status, json.load(r), False
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code == 429:
                return code, {"reason": "Forbidden"}, False
            return code or 0, {"reason": str(e)[:200]}, True

    done = 0
    ok_n = 0
    transport_streak = 0
    empty_streak = 0
    print(f"live: {len(pend)} строк в работе (лимит {limit})", flush=True)
    for p in pend:
        addr = (p["address"] or "").strip()
        cc = (p["country"] or "ru").lower()
        sug = None
        fields = None
        transport = None
        res = {}
        code = None
        if addr and not geolocate_only:
            query = addr
            hint = COUNTRY_NAMES.get(cc)
            # страну подсказываем только не-RU и только если её нет в строке
            if cc != "ru" and hint and hint.lower() not in addr.lower():
                query = f"{hint}, {addr}"
            code, res, transport = call("suggest", {"query": query, "count": 1})
            if code == 429 or res.get("reason") == "Forbidden":
                print("STOP: лимит DaData исчерпан (429/Forbidden)", flush=True)
                break
            if not transport:
                sug = (res.get("suggestions") or [None])[0]
        if sug is None and not transport and (cc == "ru" or geolocate_only) and p["lat"] and p["lon"]:
            for _radius in (None, 500, 1000):
                _pl = {"lat": float(p["lat"]), "lon": float(p["lon"])}
                if _radius:
                    _pl["radius_meters"] = _radius
                code, res, transport = call("geolocate", _pl)
                if code == 429 or res.get("reason") == "Forbidden":
                    break
                if not transport:
                    sug = (res.get("suggestions") or [None])[0]
                    if sug is not None:
                        break
            if code == 429 or res.get("reason") == "Forbidden":
                print("STOP: лимит DaData исчерпан (429/Forbidden)", flush=True)
                break
        st = await _store_live(db, p["wb_id"], addr, sug, transport_err=(res.get("reason") if transport else None))
        if transport or code == 403:
            transport_streak += 1
            empty_streak = 0
            if transport_streak >= 5 or code == 403:
                print(f"STOP: {transport_streak} транспортных ошибок подряд"
                      f"{' / HTTP 403' if code == 403 else ''} — дальше не долбим", flush=True)
                await db.commit()
                break
        elif st == "ok":
            ok_n += 1
            transport_streak = 0
            empty_streak = 0
        else:
            # sug нет обеими методами. Для ru с координатами 30 пустых подряд =
            # почти наверняка кончилась квота (сервис молча пустит), а не 30 плохих адресов
            transport_streak = 0
            empty_streak += 1
            if empty_streak >= 30:
                print("STOP: 30 пустых ответов подряд — похоже, исчерпан дневной лимит", flush=True)
                await db.commit()
                break
        done += 1
        await db.commit()
        await asyncio.sleep(0.15)  # пауза как в AddressController
        if done % 10 == 0:
            print(f"live: {done}/{len(pend)} ok={ok_n} last_wb_id={p['wb_id']}", flush=True)
    await db.commit()
    print(f"live: итого {done}, разобрано ok={ok_n}", flush=True)
    return done


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
