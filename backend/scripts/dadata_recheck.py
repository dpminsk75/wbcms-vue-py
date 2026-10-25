#!/usr/bin/env python3
"""Локальная перепроверка mismatch-строк (файловый шаттл). Без БД, только stdlib.

Вход: export mismatch c сервера (pvz_check.py --export-mismatch).
На строку: suggest -> проверка города в адресе -> сошёлся: ok;
не сошёлся: geolocate по координатам -> запись с method='geolocate'.
Выход везём на сервер: pvz_import.py --skip-import --apply-results (статус geo).

  python backend/scripts/dadata_recheck.py --in pend_mm.json --out res_mm.json --api-key KEY
  python backend/scripts/dadata_recheck.py --in pend_mm.json --out res_mm.json --dump-only
Каждая строка подробно в консоль. Checkpoint: <out>.state.db (продолжение с места остановки).
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request

COUNTRY_NAMES = {
    "ru": "Россия", "by": "Беларусь", "kz": "Казахстан", "uz": "Узбекистан",
    "am": "Армения", "kg": "Киргизия", "ge": "Грузия", "tj": "Таджикистан",
}

_NONWORD = re.compile(r"[^\w]+", re.UNICODE)
_DROP = frozenset({
    "г", "гор", "город", "ул", "улица", "у", "д", "дом", "пр", "проспект", "пр-т",
    "пер", "переулок", "бул", "бульвар", "ш", "шоссе", "мкр", "микрорайон", "кв",
    "квартал", "обл", "область", "р-н", "район", "округ", "край", "респ", "республика",
    "ао", "стр", "строение", "корп", "корпус", "пом", "офис",
})


def _norm(s):
    return (_NONWORD.sub(" ", (s or "").lower().replace("ё", "е")) + " ").strip()


def _toks(s):
    return {t for t in _NONWORD.sub(" ", (s or "").lower().replace("ё", "е")).split()
            if t and t not in _DROP}


def city_match(sug, address):
    """Город/посёлок из suggestion есть в адресе? (как pvz_check.py)."""
    d = (sug.get("data") or {}) if isinstance(sug, dict) else {}
    addr = _norm(address)
    for val in (d.get("city"), d.get("settlement"), d.get("city_district")):
        hit = [t for t in _toks(val) if len(t) >= 3 and t in addr]
        if hit:
            return True, hit[0]
    return False, ""


def call(url, payload, headers):
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
    ap = argparse.ArgumentParser(description="Перепроверка mismatch: suggest->город->geolocate")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--api-key", default=os.getenv("DADATA_API_KEY") or os.getenv("DADATA_TOKEN"))
    ap.add_argument("--secret", default=os.getenv("DADATA_SECRET_KEY"))
    ap.add_argument("--pause", type=float, default=0.2)
    ap.add_argument("--dump-only", action="store_true",
                    help="не ходить в DaData, только выгрузить накопленное")
    ap.add_argument("--geolocate-only", action="store_true",
                    help="сразу geolocate по координатам, без suggest")
    args = ap.parse_args()

    rows = json.load(open(args.inp, encoding="utf-8-sig"))
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
    if not args.api_key:
        print("ERR: нужен --api-key или DADATA_API_KEY", flush=True)
        return 1

    SUGGEST = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
    GEOLOC = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/geolocate/address"
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "Authorization": "Token " + args.api_key}
    if args.secret:
        headers["X-Secret"] = args.secret

    todo = [p for p in rows if p["wb_id"] not in done_ids]
    print(f"recheck: {len(rows)} строк (уже готово {len(done_ids)}, осталось {len(todo)})", flush=True)
    transport_streak = 0
    empty_streak = 0
    n_ok = n_geo = n_nf = 0
    for (pl,) in st.execute("SELECT payload FROM results"):
        e = json.loads(pl)
        if e.get("method") == "geolocate":
            n_geo += 1
        elif e.get("suggestion") is not None:
            n_ok += 1
        else:
            n_nf += 1
    transport_streak = 0
    stopped = False
    for i, p in enumerate(todo, 1):
        addr = (p.get("address") or "").strip()
        cc = (p.get("country") or "ru").lower()
        tag = f"{p['wb_id']} {cc}"
        sug = None
        method = None
        # шаг 1: подсказки (+страна для не-RU), пропуск при --geolocate-only
        query = addr
        hint = COUNTRY_NAMES.get(cc)
        if not args.geolocate_only and addr:
            if cc != "ru" and hint and hint.lower() not in addr.lower():
                query = f"{hint}, {addr}"
        sug_keep = None
        if args.geolocate_only:
            print(f"{tag} | suggest пропущен (--geolocate-only)", flush=True)
        else:
            code, res, transport = call(SUGGEST, {"query": query, "count": 1}, headers)
            if code == 429 or res.get("reason") == "Forbidden":
                print("STOP: лимит DaData (429/Forbidden)", flush=True)
                stopped = True
                break
            if code == 403 or transport:
                transport_streak += 1
                empty_streak = 0
                if transport_streak >= 5 or code == 403:
                    print(f"STOP: транспорт dead x{transport_streak}", flush=True)
                    stopped = True
                    break
                print(f"{tag} | suggest TRANSPORT ({res.get('reason')}) — пропуск, повторится", flush=True)
                continue
            transport_streak = 0
            sug = (res.get("suggestions") or [None])[0]
            if sug is not None:
                ok, how = city_match(sug, addr)
                d = sug.get("data") or {}
                print(f"{tag} | suggest: {d.get('city') or d.get('settlement')!r} "
                      f"{'MATCH(' + how + ')' if ok else 'NOMATCH'} <- {(addr or '')[:70]!r}", flush=True)
                if ok:
                    method = "suggest"
                    sug_keep = sug
            else:
                print(f"{tag} | suggest: пусто <- {(addr or '')[:70]!r}", flush=True)
        # шаг 2: координаты (если подсказки не сошлись), радиус 100 -> 500 -> 1000
        if sug_keep is None and p.get("lat") and p.get("lon"):
            for radius in (None, 500, 1000):
                pl = {"lat": p["lat"], "lon": p["lon"]}
                if radius:
                    pl["radius_meters"] = radius
                code2, res2, tr2 = call(GEOLOC, pl, headers)
                if code2 == 429 or res2.get("reason") == "Forbidden":
                    print("STOP: лимит DaData (429/Forbidden)", flush=True)
                    stopped = True
                    break
                if tr2:
                    print(f"{tag} | geolocate[{radius or 100}]: TRANSPORT — пропуск, повторится", flush=True)
                    break
                sug2 = (res2.get("suggestions") or [None])[0]
                if sug2 is not None:
                    print(f"{tag} | geolocate[{radius or 100}]: {sug2.get('value')!r} => GEO", flush=True)
                    method = "geolocate"
                    sug_keep = sug2
                    break
                print(f"{tag} | geolocate[{radius or 100}]: пусто", flush=True)
            else:
                print(f"{tag} | geolocate: пусто на всех радиусах => NOT_FOUND", flush=True)
            if stopped:
                break
            empty_streak = 0 if sug_keep is not None else empty_streak + 1
            if empty_streak >= 30:
                print("STOP: 30 пустых ответов подряд — похоже, исчерпан дневной лимит", flush=True)
                stopped = True
                break
        if sug_keep is not None:
            entry = {"wb_id": p["wb_id"], "country": cc, "address": addr,
                     "lat": p.get("lat"), "lon": p.get("lon"),
                     "method": method or "suggest", "suggestion": sug_keep, "error": None}
            empty_streak = 0
            st.execute("INSERT OR REPLACE INTO results (wb_id, payload) VALUES (?, ?)",
                       (p["wb_id"], json.dumps(entry, ensure_ascii=False)))
            if method == "geolocate":
                n_geo += 1
            else:
                n_ok += 1
        else:
            entry = {"wb_id": p["wb_id"], "country": cc, "address": addr,
                     "lat": p.get("lat"), "lon": p.get("lon"),
                     "method": None, "suggestion": None, "error": "NOT_FOUND"}
            st.execute("INSERT OR REPLACE INTO results (wb_id, payload) VALUES (?, ?)",
                       (p["wb_id"], json.dumps(entry, ensure_ascii=False)))
            n_nf += 1
        time.sleep(args.pause)
        if i % 10 == 0 or i == len(todo):
            st.commit()
    st.commit()
    all_rows = [json.loads(pl) for (pl,) in st.execute("SELECT payload FROM results")]
    json.dump(all_rows, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE {len(all_rows)} строк -> {args.out} ok={n_ok} geo={n_geo} not_found={n_nf} "
          f"stopped={stopped}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
