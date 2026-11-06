"""Полный синк рекламы WB: count → v2/adverts → budget → fullstats v3.

Порт WbAdvSyncController::actionIndex + actionStats (крон `10 */4 * * *`).
Фазы: count (upsert wb_campaign type/status/change_time — статусы питают
фильтр status=9 в queries) → details (имена + тип ставки + места размещения +
состав wb_campaign_item + ставки карточек; состав питает queries) →
budget (остаток бюджета кампании) → stats (upsert wb_campaign_stats + nms
через parent_id).
Токен — companies.api_key БЕЗ Bearer (как PHP WbHttpClient.php:88),
гейт promotion. Паузы по методам (из PHP): details 2с, budget 2с, stats 21с
на personal/service; basic — 5мин/60мин + правило 2ч.
CUTOFF один вместо двух php-хардкодов (2026-01-01 ×3 и 2025-12-01).
Только stdlib.
"""
import time
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json, post_json

COUNT_URL = "https://advert-api.wildberries.ru/adv/v1/promotion/count"
ADVERTS_URL = "https://advert-api.wildberries.ru/api/advert/v2/adverts"
FULLSTATS_URL = "https://advert-api.wildberries.ru/adv/v3/fullstats"
BUDGET_URL = "https://advert-api.wildberries.ru/api/advert/v2/budget"
TIMEOUT_S = 30
CHUNK = 50
CUTOFF = "2025-12-01"  # один вместо '2026-01-01' ×3 + '2025-12-01' в PHP
# Stats/details по живым и paused: status 9/11 + смена за 7д (добираем
# финал только что завершённых). Трупы (7) дают пустой fullstats (проверено 2026-10-07).
IDS_WHERE = """company_id = :cid
  AND (status IN (9, 11) OR change_time >= DATE_SUB(NOW(), INTERVAL 7 DAY))"""
DETAILS_FAST_S, DETAILS_SLOW_S = 2, 300
STATS_FAST_S, STATS_SLOW_S = 21, 3600
BUDGET_FAST_S, BUDGET_SLOW_S = 3, 900


def _pick(d, *names, default=None):
    """Взять поле по любому из вариантов написания (camElCase и snake_case).

    advert/v2/adverts в WB отдаёт часть полей в snake_case, хотя в спеке
    они camelCase — поэтому читаем оба варианта.
    """
    if not isinstance(d, dict):
        return default
    for n in names:
        v = d.get(n)
        if v is not None:
            return v
    return default


def _dt(v) -> str | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(
            str(v).replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


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


class AdvIndexService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    def _netlog(self, phase, progress, pause):
        def _log(m):
            if progress and m != "send":  # send не шумим, только ретраи
                progress("retry", 0, 0, f"{phase}: {m}")
        return _log if progress else None

    async def sync_count(self, token: str, dry_run: bool, progress=None) -> list[int]:
        """Шаг 1: promotion/count → upsert type/status/change_time. Возвращает ids."""
        data = get_json(COUNT_URL, None, token, timeout=TIMEOUT_S,
                        log=self._netlog("count", progress, 0))
        found: dict[int, dict] = {}
        for g in ((data or {}).get("adverts") or []):
            for it in (g.get("advert_list") or []):
                try:
                    aid = int(it["advertId"])
                except (TypeError, ValueError, KeyError):
                    continue
                found[aid] = {"t": _i(g.get("type")), "s": _i(g.get("status")),
                              "ct": _dt(it.get("changeTime"))}
        if found and not dry_run:
            ph = ",".join(f":f{j}" for j in range(len(found)))
            have = {int(r[0]) for r in (await self.db.execute(text(f"""
                SELECT campaign_id FROM wb_campaign
                WHERE company_id = :cid AND campaign_id IN ({ph})"""),
                {"cid": self.company_id,
                 **{f"f{j}": aid for j, aid in enumerate(found)}})).all()
                if r[0] is not None}
            new = [{"cid": self.company_id, "c": aid, "n": f"New Campaign {aid}",
                    "t": v["t"], "s": v["s"], "ct": v["ct"]}
                   for aid, v in found.items() if aid not in have]
            if new:
                await self.db.execute(text("""
                    INSERT INTO wb_campaign(company_id, campaign_id, name, type, status, change_time)
                    VALUES(:cid, :c, :n, :t, :s, :ct)"""), new)
            old = [{"t": v["t"], "s": v["s"], "ct": v["ct"],
                    "cid": self.company_id, "c": aid}
                   for aid, v in found.items() if aid in have]
            if old:
                await self.db.execute(text("""
                    UPDATE wb_campaign SET type = :t, status = :s, change_time = :ct
                    WHERE company_id = :cid AND campaign_id = :c"""), old)
            await self.db.commit()
        if progress:
            progress("phase", 1, 1, f"count: кампаний {len(found)}")
        return sorted(found)

    async def sync_details(self, token: str, ids: list[int], pause: int,
                           dry_run: bool, progress=None) -> dict:
        """Шаг 2: v2/adverts чанками 50 → имена, тип ставки, места размещения,
        состав wb_campaign_item и текущие ставки карточек."""
        chunks = [ids[i:i + CHUNK] for i in range(0, len(ids), CHUNK)]
        items_n, names_n, bids_n = 0, 0, 0
        for i, ch in enumerate(chunks):
            params = [(f"id[{j}]", v) for j, v in enumerate(ch)]  # как Yii http_build_query
            data = get_json(ADVERTS_URL, params, token, timeout=TIMEOUT_S,
                            log=self._netlog(f"details {i + 1}/{len(chunks)}", progress, pause))
            for ad in ((data or {}).get("adverts") or []):
                try:
                    aid = int(ad["id"])
                except (TypeError, ValueError, KeyError):
                    continue
                settings = _pick(ad, "settings", default={}) or {}
                nm = settings.get("name") or "Без названия"
                # тип ставки: manual (ручная) | unified (единая)
                bid_type = str(_pick(ad, "bidType", "bid_type", default="")
                        or _pick(settings, "bidType", "bid_type", default="") or "")[:10]
                # тип оплаты: cpm (за показы) | cpc (за клик) — нужен для daily-limits
                payment_type = str(_pick(settings, "paymentType", "payment_type", default="")
                        or _pick(ad, "paymentType", "payment_type", default="") or "")[:8]
                # места размещения: search | recommendations
                places = settings.get("placements") or {}
                place_search = 1 if places.get("search") else 0
                place_recommend = 1 if places.get("recommendations") else 0
                if not dry_run:
                    await self.db.execute(text("""
                        UPDATE wb_campaign SET name = :n, bid_type = :bt,
                            payment_type = :pt, place_search = :ps, place_recommend = :pr
                        WHERE company_id = :cid AND campaign_id = :c"""),
                        {"n": nm[:255], "bt": bid_type, "pt": payment_type,
                         "ps": place_search, "pr": place_recommend,
                         "cid": self.company_id, "c": aid})
                names_n += 1
                nm_settings = _pick(ad, "nmSettings", "nm_settings", default=[]) or []
                rows = [{"cid": self.company_id, "c": aid,
                         "nm": int(_pick(x, "nm_id", "nmId")),
                         "n": str(((_pick(x, "subject", default={}) or {}).get("name")) or "")[:255]}
                        for x in nm_settings if _pick(x, "nm_id", "nmId")]
                if rows and not dry_run:
                    await self.db.execute(text("""
                        INSERT INTO wb_campaign_item(company_id, campaign_id, nm_id, name)
                        VALUES(:cid, :c, :nm, :n) AS new
                        ON DUPLICATE KEY UPDATE name = new.name"""), rows)
                    await self.db.commit()
                items_n += len(rows)
                # текущие ставки карточек (поиск / рекомендации) — в копейках
                card_bids = []
                for x in nm_settings:
                    nm_id = _pick(x, "nm_id", "nmId")
                    bk = _pick(x, "bidsKopecks", "bids_kopecks", default={}) or {}
                    if nm_id is None:
                        continue
                    for placement in ("search", "recommendations"):
                        val = bk.get(placement)
                        if val is None:
                            continue
                        try:
                            card_bids.append({
                                "cid": self.company_id, "c": aid, "nm": int(nm_id),
                                "pl": placement, "v": int(val),
                                "cur": str(_pick(ad, "currency", default="RUB") or "RUB")[:8],
                            })
                        except (TypeError, ValueError):
                            continue
                if card_bids and not dry_run:
                    await self.db.execute(text("""
                        INSERT INTO wb_adv_card_bid(company_id, campaign_id, nm_id,
                            placement, bid_kopecks, currency)
                        VALUES(:cid, :c, :nm, :pl, :v, :cur) AS new
                        ON DUPLICATE KEY UPDATE
                            bid_kopecks = new.bid_kopecks, currency = new.currency"""),
                        card_bids)
                    await self.db.commit()
                bids_n += len(card_bids)
            if progress:
                progress("phase", i + 1, len(chunks),
                         f"details: товаров {items_n}, ставок карточек {bids_n}")
            if i + 1 < len(chunks):
                time.sleep(pause)
        return {"campaigns": names_n, "items": items_n, "card_bids": bids_n}

    async def sync_budget(self, token: str, ids: list[int], pause: int,
                          dry_run: bool, progress=None) -> dict:
        """Шаг: POST /api/advert/v2/budget — остаток бюджета кампаний (пачкой).

        GET /adv/v1/budget не используем: там параметр называется `id`
        (а не advertId) и метод отключается 16 ноября.
        Ответ: {"adverts": [{"advertId":…, "currency":"RUB", "total":…}]};
        кампании не из статусов 4/9/11 в ответе просто отсутствуют.
        """
        rows = []
        chunks = [ids[i:i + CHUNK] for i in range(0, len(ids), CHUNK)]
        for i, ch in enumerate(chunks):
            try:
                data = post_json(BUDGET_URL, {"advertIds": ch}, token, timeout=TIMEOUT_S,
                                 log=self._netlog(f"budget {i + 1}/{len(chunks)}", progress, pause))
            except RuntimeError as e:
                if progress:
                    progress("retry", i + 1, len(chunks), f"budget: {e}")
                continue
            for a in ((data or {}).get("adverts") or []):
                try:
                    cid = int(a.get("advertId"))
                except (TypeError, ValueError):
                    continue
                rows.append({"cid": self.company_id, "c": cid,
                             "tot": round(float(a.get("total") or 0), 2)})
            if i + 1 < len(chunks):
                time.sleep(pause)
        if rows and not dry_run:
            await self.db.execute(text("""
                UPDATE wb_campaign SET budget_total = :tot, budget_updated_at = NOW()
                WHERE company_id = :cid AND campaign_id = :c"""), rows)
            await self.db.commit()
        return {"budgets": len(rows)}

    async def sync_stats(self, token: str, ids: list[int], df: str, dt: str,
                         pause: int, dry_run: bool, progress=None) -> dict:
        """Шаг 3: fullstats v3 чанками 50 → wb_campaign_stats + nms."""
        chunks = [ids[i:i + CHUNK] for i in range(0, len(ids), CHUNK)]
        apps_n, nms_n = 0, 0
        for i, ch in enumerate(chunks):
            tag = f"stats {i + 1}/{len(chunks)}"
            try:
                data = get_json(
                    f"{FULLSTATS_URL}?ids={','.join(map(str, ch))}&beginDate={df}&endDate={dt}",
                    None, token, timeout=TIMEOUT_S, log=self._netlog(tag, progress, pause))
            except RuntimeError as e:
                if "ids" not in str(e):
                    raise
                data = get_json(FULLSTATS_URL, [("ids", ch), ("beginDate", df), ("endDate", dt)],
                                token, timeout=TIMEOUT_S, log=self._netlog(tag, progress, pause))
            a, n = await self._save_stats(data if isinstance(data, list) else [], df, dry_run)
            apps_n, nms_n = apps_n + a, nms_n + n
            if progress:
                got = len(data) if isinstance(data, list) else 0
                progress("phase", i + 1, len(chunks),
                         f"stats: ответов {got} app {apps_n} / nms {nms_n}")
            if i + 1 < len(chunks):
                time.sleep(pause)
        return {"apps": apps_n, "nms": nms_n}

    async def _save_stats(self, data: list, df: str, dry_run: bool) -> tuple[int, int]:
        parents, nms = [], []
        for cs in data:
            try:
                cid = int(cs["advertId"])
            except (TypeError, ValueError, KeyError):
                continue
            for day in (cs.get("days") or []):
                try:
                    d = date.fromisoformat(str(day.get("date"))[:10]).isoformat()
                except (ValueError, TypeError):
                    continue
                for app in (day.get("apps") or []):
                    at = str(app.get("appType") or "0")
                    parents.append({
                        "c": cid, "comp": self.company_id, "d": d, "a": at,
                        "v": _i(app.get("views")), "cl": _i(app.get("clicks")),
                        "ctr": _f(app.get("ctr")), "cpc": _f(app.get("cpc")),
                        "cr": _f(app.get("cr")), "at": _i(app.get("atbs")),
                        "o": _i(app.get("orders")), "cn": _i(app.get("canceled")),
                        "sh": _i(app.get("shks")), "s": _f(app.get("sum")),
                        "sp": _f(app.get("sum_price")),
                        "_nms": [({"nm": int(x["nmId"]),
                                   "n": str(x.get("name") or "")[:255],
                                   "v": _i(x.get("views")), "cl": _i(x.get("clicks")),
                                   "at": _i(x.get("atbs")), "o": _i(x.get("orders")),
                                   "sh": _i(x.get("shks")), "s": _f(x.get("sum")),
                                   "sp": _f(x.get("sum_price")),
                                   "cn": _i(x.get("canceled"))})
                                 for x in (app.get("nms") or []) if x.get("nmId")]})
        if parents and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_campaign_stats(
                    campaign_id, company_id, date, nm_id, app_type,
                    views, clicks, ctr, cpc, cr, atbs, orders, canceled, shks, `sum`, sum_price)
                VALUES(:c, :comp, :d, 0, :a,
                    :v, :cl, :ctr, :cpc, :cr, :at, :o, :cn, :sh, :s, :sp) AS new
                ON DUPLICATE KEY UPDATE
                    views = new.views, clicks = new.clicks, ctr = new.ctr,
                    cpc = new.cpc, cr = new.cr, atbs = new.atbs, orders = new.orders,
                    canceled = new.canceled, shks = new.shks,
                    `sum` = new.`sum`, sum_price = new.sum_price"""),
                [{k: v for k, v in p.items() if not k.startswith("_")} for p in parents])
            await self.db.commit()
            pmap = {(r["campaign_id"], str(r["date"])[:10], r["app_type"]): int(r["id"])
                    for r in (await self.db.execute(text("""
                        SELECT id, campaign_id, date, app_type FROM wb_campaign_stats
                        WHERE company_id = :cid AND date >= :df"""),
                        {"cid": self.company_id, "df": df})).mappings().all()}
            rows = []
            for p in parents:
                pid = pmap.get((p["c"], p["d"], p["a"]))
                if not pid:
                    continue
                rows += [{"comp": self.company_id, "p": pid, **x} for x in p["_nms"]]
            if rows:
                await self.db.execute(text("""
                    INSERT INTO wb_campaign_stats_nms(
                        company_id, parent_id, nm_id, name,
                        views, clicks, atbs, orders, shks, `sum`, sum_price, canceled)
                    VALUES(:comp, :p, :nm, :n,
                        :v, :cl, :at, :o, :sh, :s, :sp, :cn) AS new
                    ON DUPLICATE KEY UPDATE
                        name = new.name, views = new.views, clicks = new.clicks,
                        atbs = new.atbs, orders = new.orders, shks = new.shks,
                        `sum` = new.`sum`, sum_price = new.sum_price,
                        canceled = new.canceled"""), rows)
                await self.db.commit()
        nms_total = sum(len(p["_nms"]) for p in parents)
        return len(parents), nms_total  # в dry_run это «распарсено», запись скипнута выше

    async def sync_index(self, date_from: str | None = None, date_to: str | None = None,
                         dry_run: bool = False, stats_only: bool = False,
                         progress=None) -> dict:
        """Весь index (крон): count → ids из БД → details → stats за 3д.
        stats_only (wb-adv-sync/stats): только stats за даты."""
        df = date_from or (date.today() - timedelta(days=3)).isoformat()
        dt = date_to or date.today().isoformat()
        rows = (await self.db.execute(text(f"""
            SELECT campaign_id FROM wb_campaign WHERE {IDS_WHERE}
            ORDER BY change_time DESC"""),
            {"cid": self.company_id})).all()
        ids = [int(r[0]) for r in rows if r[0] is not None]
        chunks_n = max(1, (len(ids) + CHUNK - 1) // CHUNK)
        # оценка объёма для правила 2ч: details (чанки) + budget (по кампании) + stats (чанки)
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion",
            chunks_n * 2 + len(ids), pause_fast_s=STATS_FAST_S, pause_slow_s=STATS_SLOW_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token, pause = plan["token"], plan["pause_s"]  # raw, без Bearer (как PHP)
        d_pause = DETAILS_FAST_S if pause == STATS_FAST_S else DETAILS_SLOW_S
        b_pause = BUDGET_FAST_S if pause == STATS_FAST_S else BUDGET_SLOW_S
        out = {"company_id": self.company_id, "token_type": plan["token_type"],
               "dry_run": dry_run}
        if not stats_only:
            found = await self.sync_count(token, dry_run, progress)
            rows = (await self.db.execute(text(f"""
                SELECT campaign_id FROM wb_campaign WHERE {IDS_WHERE}
                ORDER BY change_time DESC"""),
                {"cid": self.company_id})).all()
            ids = [int(r[0]) for r in rows if r[0] is not None] or found
            out["count"] = len(ids)
            out["details"] = await self.sync_details(token, ids, d_pause, dry_run, progress)
            out["budget"] = await self.sync_budget(token, ids, b_pause, dry_run, progress)
        out["stats"] = await self.sync_stats(token, ids, df, dt, pause, dry_run, progress)
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out
