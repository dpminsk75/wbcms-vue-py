#!/usr/bin/env python3
"""Проверка разборов DaData в `pvz_all`: город из разбора ищем в адресе WB.

Совпал -> не трогаем. Нет -> статус mismatch (старый ok затираем осознанно).
dadata_address_cache НЕ ТРОГАЕМ (ни чтения, ни записи здесь нет вообще).

  .venv/bin/python backend/scripts/pvz_check.py
  .venv/bin/python backend/scripts/pvz_check.py --export-mismatch /tmp/pend_mm.json
  .venv/bin/python backend/scripts/pvz_check.py --status geo --export-mismatch /tmp/pend_mm2.json
"""

import argparse
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_NONWORD = re.compile(r"[^\w]+", re.UNICODE)
_DROP = frozenset({
    "г", "гор", "город", "ул", "улица", "у", "д", "дом", "пр", "проспект", "пр-т",
    "пер", "переулок", "бул", "бульвар", "ш", "шоссе", "мкр", "микрорайон", "кв",
    "квартал", "обл", "область", "р-н", "район", "округ", "край", "респ", "республика",
    "ао", " Moss", "стр", "строение", "корп", "корпус", "лит", "литера", "пом", "офис",
})


def _norm(s: str | None) -> str:
    return (_NONWORD.sub(" ", (s or "").lower().replace("ё", "е")) + " ").strip()


def _tokens(s: str) -> set[str]:
    return {t for t in _NONWORD.sub(" ", s.lower().replace("ё", "е")).split()
            if t and t not in _DROP}


def city_in_address(city: str | None, settlement: str | None,
                    district: str | None, address: str | None) -> tuple[bool, str]:
    """Ищем город/посёлок/район подстрокой в адресе. Возврат (ок, чем_нашли)."""
    addr = _norm(address)
    for label, val in (("city", city), ("settlement", settlement), ("district", district)):
        if not val:
            continue
        toks = _tokens(val)
        if not toks:
            continue
        # значимый токен (3+ букв: Уфа/Реж/Зея тоже города) должен встретиться в адресе
        hit = [t for t in toks if len(t) >= 3 and t in addr]
        if hit:
            return True, f"{label}:{hit[0]}"
    return False, ""


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


async def main() -> int:
    ap = argparse.ArgumentParser(description="Проверка город-в-адресе для pvz_all")
    ap.add_argument("--status", default="ok",
                    help="какой статус проверять (по умолч. ok; можно geo для перепроверки)")
    ap.add_argument("--country", default=None, help="только эта страна (напр. ru)")
    ap.add_argument("--export-mismatch", default=None, metavar="FILE",
                    help="выгрузить mismatch-строки в JSON для dadata_recheck.py")
    ap.add_argument("--export-notfound", default=None, metavar="FILE",
                    help="отдельно выгрузить not_found-строки в JSON (для добивки геолокацией)")
    ap.add_argument("--apply", action="store_true",
                    help="БЕЗ флага — только отчёт (dry-run). С флагом — писать mismatch в БД")
    ap.add_argument("--restore-ok", action="store_true",
                    help="проверяемый статус (напр. mismatch): сошедшиеся вернуть в ok (для ложных mismatch)")
    args = ap.parse_args()

    _load_dotenv(ROOT / ".env")
    from backend.database import SessionLocal  # noqa: E402
    from sqlalchemy import text  # noqa: E402

    q = """SELECT wb_id, country, address, city, settlement, city_district
           FROM pvz_all WHERE dadata_status=:st"""
    prm: dict = {"st": args.status}
    if args.country:
        q += " AND country=:cc"
        prm["cc"] = args.country
    q += " ORDER BY wb_id"

    mism = []
    total = 0
    matched_ids = []
    async with SessionLocal() as db:
        rows = (await db.execute(text(q), prm)).mappings().all()
        for r in rows:
            total += 1
            ok, how = city_in_address(r["city"], r["settlement"], r["city_district"], r["address"])
            if not ok:
                if not (r["city"] or r["settlement"] or r["city_district"]):
                    reason = "check:no-city"
                else:
                    reason = "check:city-mismatch"
                mism.append({"wb_id": r["wb_id"], "country": r["country"],
                             "address": r["address"], "city": r["city"],
                             "settlement": r["settlement"], "reason": reason})
                print(f"MISMATCH {r['wb_id']} {r['country']} {reason} "
                      f"city={r['city']!r} addr={(r['address'] or '')[:100]!r}", flush=True)
            if total % 10000 == 0:
                print(f"check: {total}/{len(rows)} mismatch={len(mism)}", flush=True)
            elif ok and args.restore_ok:
                matched_ids.append(r["wb_id"])
        if args.restore_ok and matched_ids:
            for i in range(0, len(matched_ids), 1000):
                chunk = matched_ids[i:i + 1000]
                from sqlalchemy import bindparam  # noqa: E402
                await db.execute(text("""
                    UPDATE pvz_all SET dadata_status='ok', dadata_error='recheck:fixed',
                      dadata_at=NOW() WHERE wb_id IN :ids
                """).bindparams(bindparam("ids", expanding=True)), {"ids": tuple(chunk)})
            await db.commit()
            print(f"Возвращено в ok: {len(matched_ids)}", flush=True)
        if args.apply and mism:
            for i in range(0, len(mism), 1000):
                chunk = mism[i:i + 1000]
                await db.execute(text("""
                    UPDATE pvz_all SET dadata_status='mismatch', dadata_error=:re,
                      dadata_at=NOW() WHERE wb_id=:w
                """), [{"re": m["reason"], "w": m["wb_id"]} for m in chunk])
            await db.commit()
            print(f"Помечено mismatch: {len(mism)}", flush=True)
        elif mism and not args.apply:
            print(f"DRY-RUN: найдено {len(mism)} (без --apply ничего не писалось)", flush=True)
        if args.export_mismatch:
            full = (await db.execute(text("""
                SELECT wb_id, country, address, lat, lon FROM pvz_all
                WHERE dadata_status=:st2
            """), {"st2": "mismatch" if args.apply else args.status})).mappings().all()
            # при dry-run выгружаем найденных (ещё ok), при apply — уже mismatch
            ids = {m["wb_id"] for m in mism}
            out = [{"wb_id": r["wb_id"], "country": r["country"], "address": r["address"],
                    "lat": float(r["lat"]) if r["lat"] is not None else None,
                    "lon": float(r["lon"]) if r["lon"] is not None else None}
                   for r in full if r["wb_id"] in ids]
            with open(args.export_mismatch, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            print(f"EXPORT mismatch: {len(out)} -> {args.export_mismatch}", flush=True)
        if args.export_notfound:
            nf = (await db.execute(text("""
                SELECT wb_id, country, address, lat, lon FROM pvz_all
                WHERE dadata_status='not_found'
            """))).mappings().all()
            out_nf = [{"wb_id": r["wb_id"], "country": r["country"], "address": r["address"],
                       "lat": float(r["lat"]) if r["lat"] is not None else None,
                       "lon": float(r["lon"]) if r["lon"] is not None else None} for r in nf]
            with open(args.export_notfound, "w", encoding="utf-8") as f:
                json.dump(out_nf, f, ensure_ascii=False)
            print(f"EXPORT not_found: {len(out_nf)} -> {args.export_notfound}", flush=True)
        print(f"CHECK итог: всего={total} mismatch={len(mism)}", flush=True)
    return 2 if mism else 0


if __name__ == "__main__":
    sys.exit(__import__("asyncio").run(main()))
