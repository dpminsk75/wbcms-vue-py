"""Поисковые запросы рекламы WB: normquery/stats -> wb_campaign_query.

Порт WbAdvSyncController::syncQueries/parseQueryBatch (actionQueries).
Выборка пар campaign×nm — ОДИН SELECT до дневного цикла (в PHP — на каждый день).
Токен — companies.api_key (категория promotion), гейт + паузы — wb_sync_base
(personal/service 20с, basic 60мин, правило 2ч). Только stdlib.
"""
import time
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

NORMQUERY_URL = "https://advert-api.wildberries.ru/adv/v0/normquery/stats"
TIMEOUT_S = 15  # ответы быстрые; 15с — чтобы stall стоил 15с, а не 30
CHUNK_ITEMS = 100


class AdvQueriesService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def _items(self) -> list[dict]:
        """Пары campaign×nm — один запрос (не в цикле по дням).
        Только идущие РК (status=9): завершённые/пауза показов не дают,
        normquery по ним пустой (проверено 2026-10-07: кампания 8951580,
        status=7 с марта — 396 пар вхолостую). Пауза оживёт → change_time
        обновится и пара вернётся в выборку следующим прогоном."""
        rows = (await self.db.execute(text("""
            SELECT i.campaign_id, i.nm_id FROM wb_campaign_item i
            INNER JOIN wb_campaign c ON c.campaign_id = i.campaign_id
              AND c.company_id = :cid
            WHERE i.company_id = :cid AND c.status = 9
              AND c.change_time > '2025-12-01'"""),
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
                   dry_run: bool = False, progress=None) -> dict:
        df = date_from or (date.today() - timedelta(days=1)).isoformat()
        dt = date_to or df
        days = self._days(df, dt)
        items = await self._items()
        if not items:
            return {"company_id": self.company_id, "items": 0, "upserted": 0,
                    "dry_run": dry_run}
        per_day = (len(items) + CHUNK_ITEMS - 1) // CHUNK_ITEMS
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion", len(days) * per_day,
            pause_fast_s=20, pause_slow_s=3600)
        if plan.get("skip"):
            return {"company_id": self.company_id, "items": len(items),
                    "days": len(days), "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth, pause = plan["token"], plan["pause_s"]
        upserted, reqs = 0, 0
        total_reqs = len(days) * per_day
        for day in days:
            for i in range(0, len(items), CHUNK_ITEMS):
                t0 = time.monotonic()

                def _log(m, _r=reqs, _n=total_reqs):
                    if progress:
                        st = "send" if m == "send" else "retry"
                        progress(_r + 1, _n, st, 0, 0.0, 0.0, pause, m)

                data = post_json(NORMQUERY_URL, {
                    "from": day, "to": day, "items": items[i:i + CHUNK_ITEMS],
                }, auth, timeout=TIMEOUT_S, log=_log if progress else None)
                el = time.monotonic() - t0
                rows = self._rows(data.get("stats") if isinstance(data, dict) else [], day)
                if progress:
                    progress(reqs + 1, total_reqs, "api", len(rows), el, 0.0, pause)
                t1 = time.monotonic()
                if rows and not dry_run:
                    await self.db.execute(text("""
                        INSERT INTO wb_campaign_query(
                            campaign_id, company_id, nm_id, date, query,
                            views, clicks, ctr, `sum`, atbs, orders, shks)
                        VALUES(:c, :comp, :nm, :d, :q,
                            :v, :cl, :ctr, :s, :a, :o, :sh) AS new
                        ON DUPLICATE KEY UPDATE
                            views = new.views, clicks = new.clicks, ctr = new.ctr,
                            `sum` = new.`sum`, atbs = new.atbs,
                            orders = new.orders, shks = new.shks"""), rows)
                    await self.db.commit()
                upserted += len(rows)
                reqs += 1
                el_db = time.monotonic() - t1
                wait = max(0.0, pause - el - el_db)  # цикл держим ~pause
                if progress:
                    progress(reqs, total_reqs, "db", len(rows), el, el_db, wait)
                    progress(reqs, total_reqs, "pause", len(rows), el, el_db, wait)
                time.sleep(wait)  # пауза без условий — и между днями тоже
        out = {"company_id": self.company_id, "items": len(items), "days": len(days),
               "requests": reqs, "upserted": 0 if dry_run else upserted,
               "token_type": plan["token_type"], "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    def _rows(self, stats: list, day: str) -> list[dict]:
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
                v = int(q.get("views") or 0)
                cl = int(q.get("clicks") or 0)
                rows.append({
                    "c": cid, "comp": self.company_id, "nm": nm, "d": day,
                    "q": str(txt)[:255], "v": v, "cl": cl,
                    "ctr": round(cl / v * 100, 2) if v else 0,
                    "s": float(q.get("spend") or 0), "a": int(q.get("atbs") or 0),
                    "o": int(q.get("orders") or 0), "sh": int(q.get("shks") or 0),
                })
        return rows
