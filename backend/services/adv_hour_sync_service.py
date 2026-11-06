"""Почасовые дельты рекламы WB: снимок накопительных счётчиков минус предыдущий.

WB отдаёт суточные счётчики НАКОПИТЕЛЬНО с 00:00. Значит разница между двумя
снимками — это трафик за прошедший между ними интервал. Снимаем раз в час,
получаем почасовой профиль.

Логика:
  * тянем fullstats за ВЧЕРА и СЕГОДНЯ (нужно, чтобы закрыть последний
    интервал вчерашнего дня — он заканчивается в 00:00 сегодня);
  * снимок каждого ключа (кампания, карточка, площадка) храним ОТДЕЛЬНО в
    wb_adv_campaign_hour_snap — иначе дельты забирал бы adv_index_sync, который
    пишет в те же таблицы накопительные значения;
  * бакет = текущий накопительный − снимок на момент прошлого прогона;
    часом помечаем интервал по часу, в который он ЗАКОНЧИЛСЯ (прогон в 01:55
    закрывает 00:55→01:55 → час 1), поэтому каждый час получает ровно один
    бакет и бакеты не затирают друг друга;
  * если снимка за сегодня ещё нет — первый прогон дня: весь накопленный
    объём попадает в бакет 0 (это первые ~55 минут дня, помечаем provisional);
  * последний час вчерашнего дня закрывается на следующих прогонах (интервал
    до 00:00) и помечается часом 23;
  * отрицательная дельта (пересчёт WB) в бакет не пишем, но снимок обновляем;
  * если между прогонами были пропущенные часы — считаем их и пишем в лог;
  * последний бакет текущего дня помечаем is_provisional=1.

Таблицы: wb_adv_campaign_hour (бакеты), wb_adv_campaign_hour_snap (снимки).
"""
import time
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json

FULLSTATS_URL = "https://advert-api.wildberries.ru/adv/v3/fullstats"
CHUNK = 50
PAUSE_S = 21.0
TIMEOUT_S = 30

METRICS = ("views", "clicks", "atbs", "orders", "canceled", "shks", "sum", "sum_price")


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


class AdvHourSyncService:
    """Считает почасовые бакеты рекламы по разнице снимков."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def _campaign_ids(self) -> list[int]:
        rows = (await self.db.execute(text(
            "SELECT campaign_id FROM wb_campaign WHERE company_id = :cid"
            " AND status IN (9, 11) ORDER BY campaign_id"),
            {"cid": self.company_id})).all()
        return [int(r[0]) for r in rows if r[0]]

    async def _fetch(self, token: str, ids: list[int], df: str, dt: str) -> dict:
        """Кумулятивные значения по ключу (campaign, nm, app_type) → метрики."""
        out: dict[tuple, dict] = {}
        chunks = [ids[i:i + CHUNK] for i in range(0, len(ids), CHUNK)]
        for i, ch in enumerate(chunks, 1):
            url = (f"{FULLSTATS_URL}?ids={','.join(map(str, ch))}"
                   f"&beginDate={df}&endDate={dt}")
            data = get_json(url, None, token, timeout=TIMEOUT_S)
            for cs in (data if isinstance(data, list) else []):
                try:
                    cid = int(cs["advertId"])
                except (TypeError, ValueError, KeyError):
                    continue
                for day in (cs.get("days") or []):
                    d = str(day.get("date") or "")[:10]
                    for app in (day.get("apps") or []):
                        at = _i(app.get("appType"))
                        base = {
                            "views": _i(app.get("views")), "clicks": _i(app.get("clicks")),
                            "atbs": _i(app.get("atbs")), "orders": _i(app.get("orders")),
                            "canceled": _i(app.get("canceled")), "shks": _i(app.get("shks")),
                            "sum": _f(app.get("sum")), "sum_price": _f(app.get("sum_price")),
                        }
                        out[(cid, 0, at, d)] = base
                        for n in (app.get("nms") or []):
                            try:
                                nm = int(n["nmId"])
                            except (TypeError, ValueError, KeyError):
                                continue
                            out[(cid, nm, at, d)] = {
                                "views": _i(n.get("views")), "clicks": _i(n.get("clicks")),
                                "atbs": _i(n.get("atbs")), "orders": _i(n.get("orders")),
                                "canceled": _i(n.get("canceled")), "shks": _i(n.get("shks")),
                                "sum": _f(n.get("sum")), "sum_price": _f(n.get("sum_price")),
                            }
            if i < len(chunks):
                time.sleep(PAUSE_S)
        return out

    async def sync(self, dry_run: bool = False, progress=None) -> dict:
        """Один почасовой срез: считает бакеты и обновляет снимки."""
        ids = await self._campaign_ids()
        if not ids:
            return {"company_id": self.company_id, "campaigns": 0, "dry_run": dry_run}
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion", len(ids),
            pause_fast_s=PAUSE_S, pause_slow_s=3600)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token = plan["token"]
        today = date.today()
        yest = today - timedelta(days=1)
        cur = await self._fetch(token, ids, yest.isoformat(), today.isoformat())

        # снимки: ключ (campaign, nm, app_type) → {date: (hour, метрики)}
        snaps: dict[tuple, dict] = {}
        rows = (await self.db.execute(text(
            "SELECT campaign_id, nm_id, app_type, date, hour_taken, views, clicks,"
            " atbs, orders, canceled, shks, `sum`, sum_price"
            " FROM wb_adv_campaign_hour_snap WHERE company_id = :cid"
            " AND date >= :d2"),
            {"cid": self.company_id, "d2": (today - timedelta(days=2)).isoformat()})).all()
        for r in rows:
            key = (int(r[0]), int(r[1]), int(r[2]))
            snaps.setdefault(key, {})[str(r[3])[:10]] = (
                int(r[4]), {m: r[5 + i] for i, m in enumerate(METRICS)})

        hour_now = datetime.now().hour
        buckets: list[dict] = []
        new_snaps: list[dict] = []
        skipped_neg = 0
        gaps = 0

        # группируем накопленные значения по ключу и дате
        by_key: dict[tuple, dict] = {}
        for (cid, nm, at, d), vals in cur.items():
            by_key.setdefault((cid, nm, at), {})[d] = vals

        for (cid, nm, at), days in by_key.items():
            key = (cid, nm, at)
            snap_days = snaps.get(key, {})
            # --- закрываем вчерашний последний интервал ---
            y = days.get(yest.isoformat())
            sy = snap_days.get(yest.isoformat())
            if y is not None and sy is not None:
                delta = {m: round(float(y[m]) - float(sy[1][m]), 2) for m in METRICS}
                # закрываем последний час вчерашнего дня: интервал идёт до 00:00,
                # значит помечаем часом 23 (последний час суток)
                if 23 - sy[0] > 0:
                    gaps += 1
                if any(delta[m] < 0 for m in METRICS):
                    skipped_neg += 1
                elif any(delta[m] for m in METRICS):
                    buckets.append(self._bucket(cid, nm, at, yest.isoformat(),
                                                 23, delta, 0))
            # --- сегодня ---
            t = days.get(today.isoformat())
            st = snap_days.get(today.isoformat())
            if t is not None:
                if st is None:
                    # первый снимок дня: всё накопленное с 00:00 — в бакет 0
                    buckets.append(self._bucket(cid, nm, at, today.isoformat(), 0,
                                                 {m: t[m] for m in METRICS}, 1))
                else:
                    delta = {m: round(float(t[m]) - float(st[1][m]), 2) for m in METRICS}
                    # бакет помечаем часом, в который интервал ЗАКОНЧИЛСЯ:
                    # прогон в 01:55 закрывает интервал 00:55→01:55 → час 1.
                    # Так каждый час получает ровно один бакет и они не затирают
                    # друг друга (при старой разметке бакет 0 перетирался).
                    if hour_now - st[0] > 1:
                        gaps += 1
                    if any(delta[m] < 0 for m in METRICS):
                        skipped_neg += 1
                    else:
                        buckets.append(self._bucket(cid, nm, at, today.isoformat(),
                                                     hour_now, delta, 1))
                new_snaps.append(self._snap(cid, nm, at, today.isoformat(), hour_now, t))

        if not dry_run and buckets:
            await self.db.execute(text("""
                INSERT INTO wb_adv_campaign_hour(company_id, campaign_id, nm_id,
                    app_type, date, hour, views, clicks, atbs, orders, canceled, shks,
                    `sum`, sum_price, is_provisional)
                VALUES(:cid, :c, :nm, :at, :d, :h, :views, :clicks, :atbs, :orders,
                       :canceled, :shks, :sum, :sum_price, :prov) AS new
                ON DUPLICATE KEY UPDATE
                    views = new.views, clicks = new.clicks, atbs = new.atbs,
                    orders = new.orders, canceled = new.canceled, shks = new.shks,
                    `sum` = new.`sum`, sum_price = new.sum_price,
                    is_provisional = new.is_provisional"""), buckets)
            await self.db.commit()
        if not dry_run and new_snaps:
            await self.db.execute(text("""
                INSERT INTO wb_adv_campaign_hour_snap(company_id, campaign_id, nm_id,
                    app_type, date, hour_taken, views, clicks, atbs, orders, canceled,
                    shks, `sum`, sum_price)
                VALUES(:cid, :c, :nm, :at, :d, :h, :views, :clicks, :atbs, :orders,
                       :canceled, :shks, :sum, :sum_price) AS new
                ON DUPLICATE KEY UPDATE
                    hour_taken = new.hour_taken, views = new.views, clicks = new.clicks,
                    atbs = new.atbs, orders = new.orders, canceled = new.canceled,
                    shks = new.shks, `sum` = new.`sum`, sum_price = new.sum_price"""),
                new_snaps)
            await self.db.commit()
            # чистим старые снимки (держим 3 дня)
            await self.db.execute(text(
                "DELETE FROM wb_adv_campaign_hour_snap WHERE company_id = :cid"
                " AND date < :d2"),
                {"cid": self.company_id,
                 "d2": (today - timedelta(days=3)).isoformat()})
            await self.db.commit()
        if progress:
            progress("phase", 1, 1,
                     f"часовые бакеты: {len(buckets)} (отрицательных пропущено "
                     f"{skipped_neg}, пропусков часов {gaps})")
        return {"campaigns": len(ids), "buckets": len(buckets),
                "snaps": len(new_snaps), "negative_skipped": skipped_neg,
                "gaps": gaps, "dry_run": dry_run}

    def _bucket(self, cid: int, nm: int, at: int, d: str, hour: int,
                delta: dict, provisional: int) -> dict:
        return {
            "cid": self.company_id, "c": cid, "nm": nm, "at": at, "d": d, "h": hour,
            "views": int(delta["views"]), "clicks": int(delta["clicks"]),
            "atbs": int(delta["atbs"]), "orders": int(delta["orders"]),
            "canceled": int(delta["canceled"]), "shks": int(delta["shks"]),
            "sum": delta["sum"], "sum_price": delta["sum_price"],
            "prov": provisional,
        }

    def _snap(self, cid: int, nm: int, at: int, d: str, hour: int, vals: dict) -> dict:
        return {
            "cid": self.company_id, "c": cid, "nm": nm, "at": at, "d": d, "h": hour,
            "views": int(vals["views"]), "clicks": int(vals["clicks"]),
            "atbs": int(vals["atbs"]), "orders": int(vals["orders"]),
            "canceled": int(vals["canceled"]), "shks": int(vals["shks"]),
            "sum": vals["sum"], "sum_price": vals["sum_price"],
        }
