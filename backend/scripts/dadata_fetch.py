#!/usr/bin/env python3
"""Локальный сбор ответов DaData (файловый шаттл, шаг 2). Без БД, только stdlib.

Сервер выгружает pending: pvz_import.py --export-pending pend.json [--country ru]
Здесь гоняем suggest (->geolocate для ru) с машины, где DaData доступна.
Результат увозим на сервер: pvz_import.py --skip-import --apply-results results.json

  python backend/scripts/dadata_fetch.py --in pend.json --out results.json
Ключ: --api-key или env DADATA_API_KEY (секрет опционально: --secret / DADATA_SECRET_KEY).
На 429 останавливаемся, хвост НЕ пишем (повторим следующим запуском).
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.request

COUNTRY_NAMES = {
    "ru": "Россия", "by": "Беларусь", "kz": "Казахстан", "uz": "Узбекистан",
    "am": "Армения", "kg": "Киргизия", "ge": "Грузия", "tj": "Таджикистан",
}


def call(url: str, payload: dict, headers: dict):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status != 200:
                return r.status, {}, True
            return r.status, json.load(r), False
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        if code == 429:
            return code, {"reason": "Forbidden"}, False
        return code or 0, {"reason": str(e)[:200]}, True


def main() -> int:
    ap = argparse.ArgumentParser(description="Сбор ответов DaData из export-JSON")
    ap.add_argument("--in", dest="inp", required=True, help="export pending (шаг 1)")
    ap.add_argument("--out", dest="out", required=True, help="куда писать результаты")
    ap.add_argument("--api-key", default=os.getenv("DADATA_API_KEY") or os.getenv("DADATA_TOKEN"))
    ap.add_argument("--secret", default=os.getenv("DADATA_SECRET_KEY"))
    ap.add_argument("--pause", type=float, default=0.2, help="пауза между запросами, сек")
    ap.add_argument("--dump-only", action="store_true",
                    help="не ходить в DaData, только выгрузить накопленное из .state.db в --out")
    ap.add_argument("--geolocate-only", action="store_true",
                    help="только geolocate по координатам, без suggest (добивка not_found)")
    args = ap.parse_args()
    if not args.api_key and not args.dump_only:
        print("ERR: нужен --api-key или DADATA_API_KEY", flush=True)
        return 1

    rows = json.load(open(args.inp, encoding="utf-8-sig"))
    # Checkpoint: <out>.state.db (wb_id -> готовый ответ). Повторный запуск продолжает, не сначала.
    state_path = args.out + ".state.db"
    st = sqlite3.connect(state_path)
    st.execute("CREATE TABLE IF NOT EXISTS results (wb_id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
    st.commit()
    done_ids = {r[0] for r in st.execute("SELECT wb_id FROM results")}
    if args.dump_only:
        all_rows = [json.loads(pl) for (pl,) in st.execute("SELECT payload FROM results")]
        json.dump(all_rows, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"DUMP {len(all_rows)} строк -> {args.out} (без запросов)", flush=True)
        return 0

    SUGGEST = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
    GEOLOC = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/geolocate/address"
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "Authorization": "Token " + args.api_key}
    if args.secret:
        headers["X-Secret"] = args.secret
    todo = [p for p in rows if p["wb_id"] not in done_ids]
    print(f"fetch: {len(rows)} строк из {args.inp} -> {args.out} "
          f"(уже готово {len(done_ids)}, осталось {len(todo)})", flush=True)
    out = []
    stopped = False
    first_err = None
    n_ok = 0
    n_nf = 0
    transport_streak = 0
    empty_streak = 0
    for (pl,) in st.execute("SELECT payload FROM results"):
        e = json.loads(pl)
        if e.get("suggestion") is not None:
            n_ok += 1
        else:
            n_nf += 1
    for i, p in enumerate(todo, 1):
        addr = (p.get("address") or "").strip()
        cc = (p.get("country") or "ru").lower()
        sug = None
        transport = None
        code = None
        res = {}
        method = None
        if addr and not args.geolocate_only:
            query = addr
            hint = COUNTRY_NAMES.get(cc)
            if cc != "ru" and hint and hint.lower() not in addr.lower():
                query = f"{hint}, {addr}"
            code, res, transport = call(SUGGEST, {"query": query, "count": 1}, headers)
            if code == 429 or res.get("reason") == "Forbidden":
                print("STOP: лимит DaData (429/Forbidden)", flush=True)
                stopped = True
                break
            if not transport:
                sug = (res.get("suggestions") or [None])[0]
                if sug is not None:
                    method = "suggest"
        if sug is None and not transport and p.get("lat") and p.get("lon"):
            for _radius in (None, 500, 1000):
                _pl = {"lat": p["lat"], "lon": p["lon"]}
                if _radius:
                    _pl["radius_meters"] = _radius
                code, res, transport = call(GEOLOC, _pl, headers)
                if code == 429 or res.get("reason") == "Forbidden":
                    break
                if not transport:
                    sug = (res.get("suggestions") or [None])[0]
                    if sug is not None:
                        method = "geolocate"
                        break
            if code == 429 or res.get("reason") == "Forbidden":
                print("STOP: лимит DaData (429/Forbidden)", flush=True)
                stopped = True
                break
        if transport or code == 403:
            transport_streak += 1
            empty_streak = 0
            if transport_streak >= 5 or code == 403:
                print(f"STOP: {transport_streak} транспортных ошибок подряд"
                      f"{' / HTTP 403' if code == 403 else ''} — дальше не долбим", flush=True)
                stopped = True
                break
        elif sug is not None:
            transport_streak = 0
            empty_streak = 0
        else:
            transport_streak = 0
            empty_streak += 1
            if empty_streak >= 30:
                print("STOP: 30 пустых ответов подряд — похоже, исчерпан дневной лимит", flush=True)
                stopped = True
                break
        if transport:
            entry = {"wb_id": p["wb_id"], "country": cc, "address": addr,
                     "lat": p.get("lat"), "lon": p.get("lon"),
                     "method": None, "suggestion": None,
                     "error": "TRANSPORT:" + str(res.get("reason", "?"))[:200]}
            # transport НЕ пишем в checkpoint — повторится следующим запуском
        elif sug is None:
            entry = {"wb_id": p["wb_id"], "country": cc, "address": addr,
                     "lat": p.get("lat"), "lon": p.get("lon"),
                     "method": None, "suggestion": None, "error": "NOT_FOUND"}
        else:
            entry = {"wb_id": p["wb_id"], "country": cc, "address": addr,
                     "lat": p.get("lat"), "lon": p.get("lon"),
                     "method": method or "suggest", "suggestion": sug, "error": None}
        if transport and first_err is None:
            first_err = res.get("reason")
            print(f"fetch: ПЕРВАЯ ошибка транспорта: {first_err} (повторится след. запуском)", flush=True)
        if entry["error"] is None or entry["error"] == "NOT_FOUND":
            st.execute("INSERT OR REPLACE INTO results (wb_id, payload) VALUES (?, ?)",
                       (p["wb_id"], json.dumps(entry, ensure_ascii=False)))
            out.append(entry)
            if entry["suggestion"] is not None:
                n_ok += 1
            else:
                n_nf += 1
        time.sleep(args.pause)
        if i == 1 or i % 10 == 0 or i == len(todo):
            st.commit()
            print(f"fetch: {i}/{len(todo)} ok={n_ok} not_found={n_nf}", flush=True)
    st.commit()
    # финал: всё накопленное (прошлые запуски + текущий) -> один JSON
    all_rows = [json.loads(pl) for (pl,) in st.execute("SELECT payload FROM results")]
    json.dump(all_rows, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE {len(all_rows)} строк -> {args.out} stopped429={stopped} "
          f"(checkpoint: {state_path})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
