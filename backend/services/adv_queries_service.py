"""Поисковые запросы рекламы WB (normquery) — порт wb-adv-sync/queries.

Версия API: v1 (`adv/v1/normquery/stats`) — ОДИН запрос на весь период с
детализацией по дням (v0 требовал по запросу на каждый день). В ответе v1
есть `avgPos` — средняя позиция кластера, её пишем в `wb_campaign_query.avg_pos`.
Если v1 не даёт ожидаемый формат — автоматический откат на v0 (по дням).

Два режима:
  * sync()       — суточные данные (окно дат) → wb_campaign_query;
  * sync_hourly() — часовой СНИМОК за сегодня → wb_campaign_query_hour
                    (снимок, а не дельта: почасовой профиль = разности
                    соседних строк; так не важно, отдаёт ли WB накопильные
                    значения или итог за день).

Выборка пар campaign×nm — ОДИН SELECT до цикла (в PHP — на каждый день).
Пары берём из wb_campaign_stats_nms (карточки, реально крутившиеся в
рекламе): в wb_campaign_item по одной карточке на кампанию, а в рекламе
крутятся десятки.
Токен — companies.api_key (категория promotion), гейт + паузы — wb_sync_base
(personal/service 20с, basic 60мин, правило 2ч). Только stdlib.
"""
import time
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

NORMQUERY_URL_V0 = "https://advert-api.wildberries.ru/adv/v0/normquery/stats"
NORMQUERY_URL_V1 = "https://advert-api.wildberries.ru/adv/v1/normquery/stats"
TIMEOUT_S = 15  # ответы быстрые; 15с — чтобы stall стоил 15с, а не 30
CHUNK_ITEMS = 100
PAIRS_DAYS = 30         # окно, за которое берём карточки из статистики (суточный режим)
PAIRS_HOURLY_DAYS = 3   # часовой режим: хватает недавних активных пар
PAUSE_FAST_S = 20       # пауза для суточного режима (v0/v1 по дням)
PAUSE_HOURLY_S = 6      # v1 stats: лимит 10 запросов/мин, интервал 6 с
PAUSE_SLOW_S = 3600


def _i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _f(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _pick(d, *names, default=None):
    """Взять поле по любому из вариантов написания (camelCase и snake_case).

    В семействе normquery WB фактически отдаёт snake_case (norm_query,
    advert_id) — это видно по работающему v0, — но в спецификации те же
    поля названы camelCase (normQuery, advertId). Читаем оба варианта.
    """
    if not isinstance(d, dict):
        return default
    for n in names:
        v = d.get(n)
        if v is not None:
            return v
    return default


class AdvQueriesService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def _items(self, days: int = PAIRS_DAYS) -> list[dict]:
        """Пары campaign×nm — один запрос (не в цикле по дням).

        Источник пар — wb_campaign_stats_nms (карточки, РЕАЛЬНО участвующие
        в рекламе), а не wb_campaign_item: в item по одной карточке на
        кампанию (это примеры по предметам из nm_settings), а в рекламе
        крутятся десятки карточек на кампанию. На staging разница была
        21 пара против 1409 за 30 дней (проверено 06.11).

        Только идущие РК (status=9): завершённые/пауза показов не дают,
        normquery по ним пустой (проверено 2026-10-07: кампания 8951580,
        status=7 с марта — 396 пар вхолостую). Пауза оживёт → change_time
        обновится и пара вернётся в выборку следующим прогоном."""
        rows = (await self.db.execute(text(f"""
            SELECT DISTINCT s.campaign_id, n.nm_id
            FROM wb_campaign_stats s
            JOIN wb_campaign_stats_nms n
              ON n.parent_id = s.id AND n.company_id = s.company_id
            JOIN wb_campaign c ON c.campaign_id = s.campaign_id
              AND c.company_id = :cid
            WHERE s.company_id = :cid AND n.nm_id > 0
              AND c.status = 9 AND c.change_time > '2025-12-01'
              AND s.date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
            ORDER BY s.campaign_id, n.nm_id"""),
            {"cid": self.company_id})).mappings().all()
        return [{"advert_id": int(r["campaign_id"]), "nm_id": int(r["nm_id"])}
                for r in rows if r["campaign_id"] and r["nm_id"]]

    @staticmethod
    def _days(df: str, dt: str) -> list[str]:
        d0 = date.fromisoformat(df)
        d1 = date.fromisoformat(dt)
        out, cur = [], d0
        while cur <= d1:
            out.append(cur.isoformat())
            cur += timedelta(days=1)
        return out

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, progress=None,
                   api_version: str = "v1") -> dict:
        df = date_from or (date.today() - timedelta(days=1)).isoformat()
        dt = date_to or df
        days = self._days(df, dt)
        # пары берём по окну запроса (минимум 3 дня) — иначе на бэкфилле за
        # месяц тянем 900+ пар, а нужны только активные в этом окне
        items = await self._items(days=max(3, len(days)))
        if not items:
            return {"company_id": self.company_id, "items": 0, "upserted": 0,
                    "dry_run": dry_run}
        per_day = (len(items) + CHUNK_ITEMS - 1) // CHUNK_ITEMS
        reqs_estimate = per_day if api_version == "v1" else len(days) * per_day
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion", reqs_estimate,
            pause_fast_s=PAUSE_FAST_S, pause_slow_s=PAUSE_SLOW_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "items": len(items),
                    "days": len(days), "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth, pause = plan["token"], plan["pause_s"]
        upserted, reqs = 0, 0
        used_v1 = api_version == "v1"
        if used_v1:
            rows, reqs = await self._sync_v1(auth, items, df, dt, dry_run, pause, progress)
            if rows is None:
                # v1 не дал ожидаемый формат — откат на v0 по дням
                used_v1 = False
                rows, reqs = [], 0
        if not used_v1:
            rows, reqs = await self._sync_v0(auth, items, days, dry_run, pause, progress)
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_campaign_query(
                    campaign_id, company_id, nm_id, date, query,
                    views, clicks, ctr, `sum`, atbs, orders, shks, avg_pos)
                VALUES(:c, :comp, :nm, :d, :q,
                    :v, :cl, :ctr, :s, :a, :o, :sh, :ap) AS new
                ON DUPLICATE KEY UPDATE
                    views = new.views, clicks = new.clicks, ctr = new.ctr,
                    `sum` = new.`sum`, atbs = new.atbs,
                    orders = new.orders, shks = new.shks, avg_pos = new.avg_pos"""),
                rows)
            await self.db.commit()
            upserted = len(rows)
        out = {"company_id": self.company_id, "items": len(items), "days": len(days),
               "requests": reqs, "upserted": upserted, "api": "v1" if used_v1 else "v0",
               "token_type": plan["token_type"], "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    # ---------- v1: один запрос на период, детализация по дням ----------

    async def _sync_v1(self, auth: str, items: list[dict], df: str, dt: str,
                       dry_run: bool, pause: int, progress=None):
        """POST /adv/v1/normquery/stats → items[].dailyStats[].stat.
        Возвращает (rows, requests) либо (None, 0), если формат неожиданный."""
        rows: list[dict] = []
        reqs = 0
        chunks = [items[i:i + CHUNK_ITEMS] for i in range(0, len(items), CHUNK_ITEMS)]
        for i, ch in enumerate(chunks):
            t0 = time.monotonic()

            def _log(m, _r=reqs, _n=len(chunks)):
                if progress:
                    progress(_r + 1, _n, "retry" if m != "send" else "send", 0, 0.0, 0.0, 0, m)

            # в items шлём оба написания полей: фактически WB ждёт snake_case
            # (как в v0), в спеке указано camelCase — лишние поля WB обычно
            # игнорирует; если нет — запрос вернёт 400 и мы откатимся на v0
            payload = {"from": df, "to": dt, "items": [
                {"advert_id": it["advert_id"], "nm_id": it["nm_id"],
                 "advertId": it["advert_id"], "nmId": it["nm_id"]}
                for it in ch]}
            try:
                data = post_json(NORMQUERY_URL_V1, payload, auth, timeout=TIMEOUT_S,
                                 log=_log if progress else None)
            except RuntimeError as e:
                if progress:
                    progress(reqs + 1, len(chunks), "retry", 0, 0.0, 0.0, 0,
                             f"v1: {e} — откат на v0")
                return None, 0
            el = time.monotonic() - t0
            got = _pick(data, "items", default=None) if isinstance(data, dict) else None
            if got is None:
                if progress:
                    progress(reqs + 1, len(chunks), "retry", 0, 0.0, 0.0, 0,
                             "v1: неожиданный формат ответа, откат на v0")
                return None, 0
            for it in got:
                cid = _i(_pick(it, "advert_id", "advertId"))
                nm = _i(_pick(it, "nm_id", "nmId"))
                if not cid or not nm:
                    continue
                for day in (_pick(it, "dailyStats", "daily_stats", default=[]) or []):
                    d = str(_pick(day, "date", default="") or "")[:10]
                    stat = _pick(day, "stat", "stats", default={}) or {}
                    q = str(_pick(stat, "norm_query", "normQuery", default="") or "").strip()
                    if not q or not d:
                        continue
                    views = _i(_pick(stat, "views"))
                    clicks = _i(_pick(stat, "clicks"))
                    avg_pos = _pick(stat, "avg_pos", "avgPos")
                    rows.append({
                        "c": cid, "comp": self.company_id, "nm": nm, "d": d, "q": q[:255],
                        "v": views, "cl": clicks,
                        "ctr": round(clicks / views * 100, 2) if views else 0,
                        "s": _f(_pick(stat, "spend")), "a": _i(_pick(stat, "atbs")),
                        "o": _i(_pick(stat, "orders")), "sh": _i(_pick(stat, "shks")),
                        "ap": _f(avg_pos) if avg_pos is not None else None,
                    })
            reqs += 1
            if progress:
                progress(reqs, len(chunks), "api", len(rows), el, 0.0, pause)
            if i + 1 < len(chunks):
                time.sleep(pause)
        return rows, reqs

    # ---------- v0: по одному запросу на день (fallback) ----------

    async def _sync_v0(self, auth: str, items: list[dict], days: list[str],
                       dry_run: bool, pause: int, progress=None):
        rows: list[dict] = []
        reqs = 0
        total = len(days) * ((len(items) + CHUNK_ITEMS - 1) // CHUNK_ITEMS)
        for day in days:
            for i in range(0, len(items), CHUNK_ITEMS):
                t0 = time.monotonic()

                def _log(m, _r=reqs, _n=total):
                    if progress:
                        st = "send" if m == "send" else "retry"
                        progress(_r + 1, _n, st, 0, 0.0, 0.0, 0, m)

                data = post_json(NORMQUERY_URL_V0, {
                    "from": day, "to": day, "items": items[i:i + CHUNK_ITEMS],
                }, auth, timeout=TIMEOUT_S, log=_log if progress else None)
                el = time.monotonic() - t0
                rows += self._rows(data.get("stats") if isinstance(data, dict) else [], day)
                reqs += 1
                if progress:
                    progress(reqs, total, "api", len(rows), el, 0.0, 0)
                if i + CHUNK_ITEMS < len(items):
                    time.sleep(pause)
        return rows, reqs

    async def sync_hourly(self, day: str | None = None, dry_run: bool = False,
                          progress=None) -> dict:
        """Часовой снимок статистики по поисковым кластерам.

        GET normquery/stats за СЕГОДНЯ одним запросом на батч пар и складываем
        в wb_campaign_query_hour СНИМОК (значение на конец часа), а не дельту.
        Тогда:
          * почасовой профиль = разности соседних строк (считаются на чтении);
          * суточные данные = последняя строка за день;
          * результат не зависит от того, отдаёт WB накопительные значения
            или итог за день: если итог — строки за день одинаковы и разности
            нулевые (безвредно).
        """
        day = day or datetime.now().date().isoformat()
        # для часового режима берём только недавние активные пары (окно 3 дня):
        # за 30 дней набирается 900+ пар — лишние запросы к WB
        items = await self._items(days=PAIRS_HOURLY_DAYS)
        if not items:
            return {"company_id": self.company_id, "pairs": 0, "rows": 0,
                    "dry_run": dry_run}
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion",
            (len(items) + CHUNK_ITEMS - 1) // CHUNK_ITEMS,
            pause_fast_s=PAUSE_HOURLY_S, pause_slow_s=PAUSE_SLOW_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth, pause = plan["token"], plan["pause_s"]
        hour = datetime.now().hour
        provisional = 1 if day == datetime.now().date().isoformat() else 0
        rows: list[dict] = []
        reqs = 0
        chunks = [items[i:i + CHUNK_ITEMS] for i in range(0, len(items), CHUNK_ITEMS)]
        for i, ch in enumerate(chunks, 1):
            t0 = time.monotonic()

            def _log(m, _r=reqs, _n=len(chunks)):
                if progress:
                    progress(_r + 1, _n, "retry" if m != "send" else "send", 0, 0.0, 0.0, 0, m)

            try:
                data = post_json(NORMQUERY_URL_V1, {
                    "from": day, "to": day,
                    "items": [{"advertId": it["advert_id"], "nmId": it["nm_id"]}
                              for it in ch],
                }, auth, timeout=TIMEOUT_S, log=_log if progress else None)
            except RuntimeError as e:
                if progress:
                    progress(reqs + 1, len(chunks), "retry", 0, 0.0, 0.0, 0,
                             f"normquery hourly: {e}")
                continue
            el = time.monotonic() - t0
            rows += self._hour_rows(data, day, hour, provisional)
            reqs += 1
            if progress:
                progress(reqs, len(chunks), "api", len(rows), el, 0.0, pause)
            if i + 1 < len(chunks):
                time.sleep(pause)
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_campaign_query_hour(company_id, campaign_id, nm_id,
                    date, hour, query, views, clicks, atbs, orders, shks,
                    `sum`, avg_pos, is_provisional)
                VALUES(:cid, :c, :nm, :d, :h, :q, :v, :cl, :a, :o, :sh,
                       :s, :ap, :prov) AS new
                ON DUPLICATE KEY UPDATE
                    views = new.views, clicks = new.clicks, atbs = new.atbs,
                    orders = new.orders, shks = new.shks, `sum` = new.`sum`,
                    avg_pos = new.avg_pos, is_provisional = new.is_provisional"""),
                rows)
            await self.db.commit()
        if progress:
            progress(reqs, reqs, "api", len(rows), 0.0, 0.0, 0,
                     f"часовой снимок {day} {hour:02d}:00: {len(rows)} строк")
        return {"company_id": self.company_id, "pairs": len(items), "rows": len(rows),
                "requests": reqs, "date": day, "hour": hour,
                "token_type": plan.get("token_type"), "dry_run": dry_run}

    def _hour_rows(self, data, day: str, hour: int, provisional: int) -> list[dict]:
        """Разбор ответа v1 в строки часового снимка."""
        rows = []
        for it in (_pick(data, "items", default=[]) or []):
            cid = _i(_pick(it, "advert_id", "advertId"))
            nm = _i(_pick(it, "nm_id", "nmId"))
            if not cid or not nm:
                continue
            for d in (_pick(it, "dailyStats", "daily_stats", default=[]) or []):
                ddate = str(_pick(d, "date", default="") or "")[:10]
                stat = _pick(d, "stat", "stats", default={}) or {}
                q = str(_pick(stat, "norm_query", "normQuery", default="") or "").strip()
                if not q or (ddate and ddate != day):
                    continue
                views = _i(_pick(stat, "views"))
                clicks = _i(_pick(stat, "clicks"))
                avg_pos = _pick(stat, "avg_pos", "avgPos")
                rows.append({
                    "cid": self.company_id, "c": cid, "nm": nm, "d": day, "h": hour,
                    "q": q[:255], "v": views, "cl": clicks,
                    "a": _i(_pick(stat, "atbs")), "o": _i(_pick(stat, "orders")),
                    "sh": _i(_pick(stat, "shks")), "s": _f(_pick(stat, "spend")),
                    "ap": _f(avg_pos) if avg_pos is not None else None,
                    "prov": provisional,
                })
        return rows

    def _rows(self, stats: list, day: str) -> list[dict]:
        """Разбор ответа v0 (snake_case): norm_query, views, clicks, atbs,
        orders, shks, spend, avg_pos, cpc, cpm, currency.

        avg_pos в v0 тоже есть (проверено по спецификации WB) — читаем,
        чтобы при откате с v1 на v0 позиция не терялась.
        """
        rows = []
        for it in stats or []:
            try:
                cid, nm = int(it.get("advert_id")), int(it.get("nm_id"))
            except (TypeError, ValueError):
                continue
            for q in (it.get("stats") or []):
                txt = (q or {}).get("norm_query")
                if not txt:
                    continue
                views = _i(q.get("views"))
                clicks = _i(q.get("clicks"))
                avg_pos = q.get("avg_pos")
                rows.append({
                    "c": cid, "comp": self.company_id, "nm": nm, "d": day,
                    "q": str(txt)[:255], "v": views, "cl": clicks,
                    "ctr": round(clicks / views * 100, 2) if views else 0,
                    "s": _f(q.get("spend")), "a": _i(q.get("atbs")),
                    "o": _i(q.get("orders")), "sh": _i(q.get("shks")),
                    "ap": _f(avg_pos) if avg_pos is not None else None,
                })
        return rows
