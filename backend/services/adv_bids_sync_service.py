"""Снимки состояния рекламы WB: ставки кластеров, список кластеров, минус-фразы,
конфиг аккаунта, баланс, дневные лимиты, остаток бюджета кампаний.

ТОЛЬКО ЧТЕНИЕ из advert-api — в кабинет продавца ничего не пишем.
Гейт токена (promotion, тип токена, протухание, правило 2ч) — wb_sync_base.

Методы (все read-only):
  POST /adv/v0/normquery/get-bids   -> wb_adv_bid (+ wb_adv_bid_history)
  POST /adv/v0/normquery/list      -> wb_adv_cluster
  POST /adv/v0/normquery/get-minus -> wb_adv_minus_phrase
  GET  /api/advert/v1/config       -> wb_adv_account (шаги ставок, валюта)
  GET  /adv/v1/balance             -> wb_adv_account (баланс/нетто/бонусы)
  GET  /api/advert/v0/daily-limits -> wb_adv_daily_limit   (только CPC)
  POST /api/advert/v2/budget       -> wb_campaign.budget_total (остатки бюджетов)

Ловушки:
  * У методов normquery РАЗНЫЙ формат тела:
      normquery/list      — только camelCase (advertId/nmId), snake → пусто;
      normquery/get-bids  — только snake_case (advert_id/nm_id), camel → пусто;
      normquery/get-minus — только snake_case (advert_id/nm_id);
    пустой ответ при неверном регистре выглядит как «данных нет»;
  * ответы тоже в том же регистре, что и запрос — читаем через _pick();
  * пары (кампания, карточка) берём из wb_campaign_stats_nms, а НЕ из
    wb_campaign_item: в item по одной карточке на кампанию (это примеры
    по предметам), а в рекламе крутятся десятки карточек;
  * остатки бюджетов берём из POST /api/advert/v2/budget (пачкой), а НЕ из
    GET /adv/v1/budget: там параметр называется `id` (а не advertId) и метод
    отключается 16 ноября;
  * config и daily-limits доступны ТОЛЬКО на персональном/сервисном токене;
  * ставка в get-bids приходит в двух единицах: `bid` (базовые) и `bidKopecks`.
"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json, post_json

ADVERT = "https://advert-api.wildberries.ru"
BIDS_URL = f"{ADVERT}/adv/v0/normquery/get-bids"
LIST_URL = f"{ADVERT}/adv/v0/normquery/list"
MINUS_URL = f"{ADVERT}/adv/v0/normquery/get-minus"
CONFIG_URL = f"{ADVERT}/api/advert/v1/config"
LIMITS_URL = f"{ADVERT}/api/advert/v0/daily-limits"
BALANCE_URL = f"{ADVERT}/adv/v1/balance"
# Минимальные ставки для карточек (read-only метод, но вызывается POST)
MIN_BIDS_URL = f"{ADVERT}/api/advert/v1/bids/min"
# Остатки бюджетов кампаний — пачкой. GET /adv/v1/budget больше не используем:
# там параметр называется `id` (а не advertId) и метод отключается 16 ноября.
BUDGET_URL = f"{ADVERT}/api/advert/v2/budget"

PAIRS_CHUNK = 100       # пар (кампания, карточка) за один запрос
BUDGET_CHUNK = 100      # кампаний за один запрос бюджета
PAIRS_DAYS = 30         # окно, за которое берём карточки из статистики
CLEANUP_DAYS = 7        # состояния старше этого срока вычищаем (пары ушли в рекламу)
PAUSE_FAST_S = 0.35     # get-bids / list / get-minus (лимит WB — 200 мс, берём с запасом)
PAUSE_BUDGET_S = 3.0    # budget — интервал WB 3 с
PAUSE_MIN_BIDS_S = 3.0  # bids/min — интервал WB 3 с
MIN_BIDS_MAX_REQS = 60   # запросов bids/min за один прогон (≈3 мин); остальное — в следующих
PAUSE_LIMITS_S = 12.0   # daily-limits
TIMEOUT_S = 20
PERSONAL_TYPES = ("personal", "service")

# Места размещения в разных ответах WB называются по-разному:
# bids/min отдаёт "recommendation" (ед. ч.), advert/v2/adverts — "recommendations".
PLACEMENT_ALIASES = {
    "search": "search",
    "recommendation": "recommendations",
    "recommendations": "recommendations",
    "combined": "combined",
}


def _placement(value) -> str:
    return PLACEMENT_ALIASES.get(str(value or "").lower(), str(value or "")[:16])


def _chunks(items: list, size: int):
    return [items[i:i + size] for i in range(0, len(items), size)]


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


class AdvBidsSyncService:
    """Снимает «состояние сейчас» по рекламе и раскладывает по таблицам."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    # ---------- служебное ----------

    async def _personal_token(self) -> str | None:
        """Токен типа personal/service (config/daily-limits) либо None."""
        row = (await self.db.execute(text(
            "SELECT token_type FROM company_wb_tokens"
            " WHERE company_id = :c AND is_active = 1 LIMIT 1"),
            {"c": self.company_id})).first()
        ttype = (row[0] or "") if row else ""
        return ttype if ttype in PERSONAL_TYPES else None

    async def _pairs(self) -> list[tuple[int, int]]:
        """Пары (кампания, карточка), которые РЕАЛЬНО участвуют в рекламе.

        Брать из wb_campaign_item нельзя: там по ОДНОЙ карточке на кампанию
        (это примеры карточек по предметам из nm_settings), а в рекламе
        крутятся десятки карточек на кампанию (проверено на staging: 21
        пара из item против 1409 реальных пар за 30 дней).

        Источник — wb_campaign_stats_nms (карточки с показами/заказами).
        """
        rows = (await self.db.execute(text(f"""
            SELECT DISTINCT s.campaign_id, n.nm_id
            FROM wb_campaign_stats s
            JOIN wb_campaign_stats_nms n
              ON n.parent_id = s.id AND n.company_id = s.company_id
            WHERE s.company_id = :cid AND n.nm_id > 0
              AND s.date >= DATE_SUB(CURDATE(), INTERVAL {PAIRS_DAYS} DAY)
            ORDER BY s.campaign_id, n.nm_id"""),
            {"cid": self.company_id})).all()
        return [(int(r[0]), int(r[1])) for r in rows if r[0] and r[1]]

    async def _campaign_nms(self, campaign_id: int) -> list[int]:
        """Карточки кампании, реально участвующие в рекламе.

        Порядок — «кругом»: сначала карточки, у которых минимальная ставка
        ещё неизвестна (min_kopecks = 0), потом самые старые по updated_at.
        Так за несколько прогонов обходим все карточки, а не топчемся
        на первых.
        """
        rows = (await self.db.execute(text(f"""
            SELECT n.nm_id
            FROM wb_campaign_stats s
            JOIN wb_campaign_stats_nms n
              ON n.parent_id = s.id AND n.company_id = s.company_id
            LEFT JOIN wb_adv_card_bid cb
              ON cb.company_id = n.company_id
             AND cb.campaign_id = s.campaign_id
             AND cb.nm_id = n.nm_id
            WHERE s.company_id = :cid AND s.campaign_id = :c AND n.nm_id > 0
              AND s.date >= DATE_SUB(CURDATE(), INTERVAL {PAIRS_DAYS} DAY)
            GROUP BY n.nm_id
            ORDER BY (COALESCE(MIN(cb.min_kopecks), 0) = 0) DESC,
                     MIN(cb.updated_at) ASC, n.nm_id"""),
            {"cid": self.company_id, "c": campaign_id})).all()
        return [int(r[0]) for r in rows if r[0]]

    async def _campaign_ids(self, payment_type: str | None = None) -> list[int]:
        """Живые кампании (статус 9/11). payment_type — фильтр по типу оплаты."""
        sql = ("SELECT campaign_id FROM wb_campaign WHERE company_id = :cid"
               " AND status IN (9, 11)")
        params = {"cid": self.company_id}
        if payment_type:
            sql += " AND payment_type = :pt"
            params["pt"] = payment_type
        sql += " ORDER BY campaign_id"
        rows = (await self.db.execute(text(sql), params)).all()
        return [int(r[0]) for r in rows if r[0]]

    async def _campaign_types(self) -> dict:
        """Сколько живых кампаний с ручной/единой ставкой и какого типа оплата."""
        rows = (await self.db.execute(text(
            "SELECT COALESCE(NULLIF(bid_type, ''), '?') AS bt,"
            " COALESCE(NULLIF(payment_type, ''), '?') AS pt, COUNT(*)"
            " FROM wb_campaign WHERE company_id = :cid AND status IN (9, 11)"
            " GROUP BY bt, pt"),
            {"cid": self.company_id})).all()
        out = {"bid_type": {}, "payment_type": {}}
        for bt, pt, n in rows:
            out["bid_type"][str(bt)] = out["bid_type"].get(str(bt), 0) + int(n)
            out["payment_type"][str(pt)] = out["payment_type"].get(str(pt), 0) + int(n)
        return out

    # ---------- sync ----------

    async def sync(self, dry_run: bool = False, progress=None) -> dict:
        """Полный снимок состояния. Возвращает сводку для воркера.

        Каждый шаг обёрнут: ошибка одного метода не должна ронять весь
        прогон — остальные методы отдают своё, а упавший — причину.
        """
        pairs = await self._pairs()
        campaigns = await self._campaign_ids()
        chunks = len(_chunks(pairs, PAIRS_CHUNK)) * 3 + len(campaigns) * 2
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion", chunks,
            pause_fast_s=PAUSE_FAST_S, pause_slow_s=60)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token = plan["token"]
        out = {"company_id": self.company_id, "token_type": plan.get("token_type"),
               "pairs": len(pairs), "campaigns": len(campaigns), "dry_run": dry_run}
        out["types"] = await self._campaign_types()
        if plan.get("warning"):
            out["warning"] = plan["warning"]

        async def step(name, coro_factory):
            """Выполнить шаг; при ошибке — записать её и идти дальше."""
            try:
                out[name] = await coro_factory()
            except Exception as e:  # noqa: BLE001 — шаг не должен ронять прогон
                out[name] = {"error": str(e)[:200]}
                if progress:
                    progress("retry", 0, 0, f"{name}: {e}")
            return out[name]

        await step("config", lambda: self._sync_config(token, dry_run, progress))
        await step("balance", lambda: self._sync_balance(token, dry_run, progress))
        await step("budget", lambda: self._sync_budget(token, campaigns, dry_run, progress))
        await step("min_bids", lambda: self._sync_min_bids(token, dry_run, progress))
        await step("limits", lambda: self._sync_daily_limits(token, campaigns, dry_run, progress))
        await step("clusters", lambda: self._sync_clusters(token, pairs, dry_run, progress))
        await step("bids", lambda: self._sync_bids(token, pairs, dry_run, progress))
        await step("minus", lambda: self._sync_minus(token, pairs, dry_run, progress))
        if not dry_run:
            out["cleanup"] = await self._cleanup()
        return out

    async def _cleanup(self) -> dict:
        """Вычистить состояния, которых больше нет (карточка ушла из рекламы).

        Таблицы wb_adv_bid / wb_adv_cluster / wb_adv_minus_phrase хранят
        «состояние сейчас»: если пары больше нет, записи надо удалить, иначе
        в интерфейсе останутся фразы и ставки мёртвых карточек.
        """
        out = {}
        for tbl in ("wb_adv_bid", "wb_adv_cluster", "wb_adv_minus_phrase",
                    "wb_adv_card_bid"):
            res = await self.db.execute(text(
                f"DELETE FROM {tbl} WHERE company_id = :cid"
                f" AND updated_at < DATE_SUB(NOW(), INTERVAL {CLEANUP_DAYS} DAY)"),
                {"cid": self.company_id})
            out[tbl] = res.rowcount or 0
        await self.db.commit()
        return out

    # ---------- минимальные ставки карточек ----------

    async def _sync_min_bids(self, token: str, dry_run: bool, progress=None) -> dict:
        """POST /api/advert/v1/bids/min — минимальные ставки по карточкам.

        Тело: {advert_id, nm_ids[], payment_type: cpm|cpc, placement_types[]}.
        Ответ: {"bids": [{"nmId":…, "bids": [{"type": "search", "value": N, "currency":…}]}]}.
        value — минимальная ставка в копейках; кладём в wb_adv_card_bid.min_kopecks.

        ФАКТ (проба на staging 06.11): WB принимает **один артикул за запрос** —
        с 1 nm ответ 200, с 5 nm — 400, хотя в спеке написано maxLength: 100.
        Поэтому ходим по одному артикулу и ограничиваем число запросов на
        прогон (MIN_BIDS_MAX_REQS), а порядок берём так, чтобы за круг обойти
        все карточки: сначала те, у которых минимум ещё неизвестен
        (min_kopecks = 0), потом самые старые по updated_at.

        Фактические минимумы (стадия, копейки): search 35 000 · recommendation
        12 000 · combined 9 000.
        """
        camps = (await self.db.execute(text(
            "SELECT campaign_id, payment_type, bid_type FROM wb_campaign"
            " WHERE company_id = :cid AND status IN (9, 11)"
            " AND payment_type IN ('cpm', 'cpc') ORDER BY campaign_id"),
            {"cid": self.company_id})).all()
        if not camps:
            return {"cards": 0}
        rows = []
        reqs = 0
        errors = 0
        for cid, ptype, btype in camps:
            if reqs >= MIN_BIDS_MAX_REQS:
                break
            nm_ids = await self._campaign_nms(int(cid))
            if not nm_ids:
                continue
            # ручная ставка — поиск и рекомендации отдельно, единая — combined
            placements = (["search", "recommendation"] if (btype or "") == "manual"
                          else ["combined"])
            for nm in nm_ids:
                if reqs >= MIN_BIDS_MAX_REQS:
                    break
                body = {"advert_id": int(cid), "nm_ids": [nm],
                        "payment_type": ptype, "placement_types": placements}
                try:
                    data = post_json(MIN_BIDS_URL, body, token, timeout=TIMEOUT_S)
                except RuntimeError as e:
                    errors += 1
                    if progress:
                        progress("retry", reqs + 1, MIN_BIDS_MAX_REQS,
                                 f"bids/min {cid}/{nm}: {e}")
                    break  # кампания не прошла — по её карточкам дальше тоже нет смысла
                reqs += 1
                for b in (_pick(data, "bids", default=[]) or []):
                    try:
                        nm_id = int(_pick(b, "nm_id", "nmId"))
                    except (TypeError, ValueError):
                        continue
                    for mb in (b.get("bids") or []):
                        val = _pick(mb, "value", default=None)
                        if val is None:
                            continue
                        try:
                            rows.append({
                                "cid": self.company_id, "c": int(cid), "nm": nm_id,
                                "pl": _placement(_pick(mb, "type")),
                                "v": int(val),
                                "cur": str(_pick(mb, "currency", default="RUB"))[:8],
                            })
                        except (TypeError, ValueError):
                            continue
                time.sleep(PAUSE_MIN_BIDS_S)
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_card_bid(company_id, campaign_id, nm_id,
                    placement, min_kopecks, currency)
                VALUES(:cid, :c, :nm, :pl, :v, :cur) AS new
                ON DUPLICATE KEY UPDATE
                    min_kopecks = new.min_kopecks, currency = new.currency"""), rows)
            await self.db.commit()
        if progress:
            progress("phase", reqs, MIN_BIDS_MAX_REQS,
                     f"bids/min: {len(rows)} минимальных ставок "
                     f"({reqs} запросов, ошибок {errors})")
        return {"cards": len(rows), "requests": reqs}

    # ---------- config / balance ----------

    async def _sync_config(self, token: str, dry_run: bool, progress=None) -> dict:
        """GET /api/advert/v1/config — валюта, шаги ставок, минимумы."""
        if not await self._personal_token():
            return {"skipped": "config доступен только на personal/service токене"}
        data = get_json(CONFIG_URL, None, token, timeout=TIMEOUT_S)
        if not isinstance(data, dict):
            return {"skipped": "config: неожиданный ответ"}
        row = {
            "cid": self.company_id,
            "cur": str(_pick(data, "currency", default="RUB"))[:8],
            "ccode": int(_pick(data, "currencyCode", "currency_code", default=0) or 0),
            "cpm": int(_pick(data, "cpmStep", "cpm_step", default=0) or 0),
            "cpc": int(_pick(data, "cpcStep", "cpc_step", default=0) or 0),
            "mindl": int(_pick(data, "minDailyLimit", "min_daily_limit", default=0) or 0),
            "mintop": int(_pick(data, "minTopUp", "min_top_up", default=0) or 0),
        }
        if not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_account(company_id, currency, currency_code,
                    cpm_step, cpc_step, min_daily_limit, min_top_up)
                VALUES(:cid, :cur, :ccode, :cpm, :cpc, :mindl, :mintop) AS new
                ON DUPLICATE KEY UPDATE
                    currency = new.currency, currency_code = new.currency_code,
                    cpm_step = new.cpm_step, cpc_step = new.cpc_step,
                    min_daily_limit = new.min_daily_limit,
                    min_top_up = new.min_top_up"""), [row])
            await self.db.commit()
        if progress:
            progress("phase", 1, 1, f"config: валюта {row['cur']}, cpmStep {row['cpm']}")
        return {"currency": row["cur"], "cpm_step": row["cpm"], "cpc_step": row["cpc"]}

    async def _sync_balance(self, token: str, dry_run: bool, progress=None) -> dict:
        """GET /adv/v1/balance — баланс, нетто, бонусы."""
        data = get_json(BALANCE_URL, None, token, timeout=TIMEOUT_S)
        if not isinstance(data, dict):
            return {"skipped": "balance: неожиданный ответ"}
        bal = float(_pick(data, "balance", default=0) or 0)
        net = float(_pick(data, "net", default=0) or 0)
        bon = float(_pick(data, "bonus", default=0) or 0)
        if not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_account(company_id, balance_base, net_base, bonus_base)
                VALUES(:cid, :bal, :net, :bon) AS new
                ON DUPLICATE KEY UPDATE
                    balance_base = new.balance_base, net_base = new.net_base,
                    bonus_base = new.bonus_base"""),
                [{"cid": self.company_id, "bal": bal, "net": net, "bon": bon}])
            await self.db.commit()
        if progress:
            progress("phase", 1, 1, f"balance: {bal:.2f} {data.get('currency') or ''}")
        return {"balance": bal, "net": net, "bonus": bon}

    # ---------- бюджет кампаний ----------

    async def _sync_budget(self, token: str, campaigns: list[int],
                           dry_run: bool, progress=None) -> dict:
        """POST /api/advert/v2/budget — остаток бюджета кампаний (пачкой).

        Ответ: {"adverts": [{"advertId":…, "currency":"RUB", "total":…}]}.
        Кампании не из статусов 4/9/11 в ответе просто отсутствуют.
        """
        rows = []
        chunks = _chunks(campaigns, BUDGET_CHUNK)
        for i, ch in enumerate(chunks, 1):
            try:
                data = post_json(BUDGET_URL, {"advertIds": ch}, token, timeout=TIMEOUT_S)
            except RuntimeError as e:
                if progress:
                    progress("retry", i, len(chunks), f"budget: {e}")
                continue
            for a in (_pick(data, "adverts", default=[]) or []):
                try:
                    cid = int(_pick(a, "advertId", "advert_id"))
                except (TypeError, ValueError):
                    continue
                rows.append({"cid": self.company_id, "c": cid,
                             "tot": float(_pick(a, "total", default=0) or 0)})
            if i < len(chunks):
                time.sleep(PAUSE_BUDGET_S)
        if rows and not dry_run:
            await self.db.execute(text("""
                UPDATE wb_campaign SET budget_total = :tot, budget_updated_at = NOW()
                WHERE company_id = :cid AND campaign_id = :c"""), rows)
            await self.db.commit()
        if progress:
            progress("phase", len(chunks), len(chunks),
                     f"budget: остаток у {len(rows)} кампаний")
        return {"campaigns": len(rows)}

    # ---------- дневные лимиты (CPC) ----------

    async def _sync_daily_limits(self, token: str, campaigns: list[int],
                                 dry_run: bool, progress=None) -> dict:
        """GET /api/advert/v0/daily-limits?advertIds= — лимиты CPC-кампаний.

        Важно: метод работает ТОЛЬКО для кампаний с оплатой за клик (cpc).
        Если в списке есть CPM-кампании, WB отвечает 400
        «daily limit is not available for CPM campaigns» и роняет весь
        запрос — поэтому шлём только кампании с известным payment_type='cpc'.
        """
        cpc = await self._campaign_ids(payment_type="cpc")
        if not cpc:
            return {"campaigns": 0,
                    "skipped": "нет CPC-кампаний (payment_type не заполнен "
                               "или все кампании CPM)"}
        if not await self._personal_token():
            return {"skipped": "daily-limits доступен только на personal/service токене"}
        rows = []
        for i in range(0, len(cpc), 100):
            part = cpc[i:i + 100]
            try:
                data = get_json(LIMITS_URL, [("advertIds", ",".join(map(str, part)))],
                                token, timeout=TIMEOUT_S)
            except RuntimeError as e:
                return {"skipped": f"daily-limits: {e}"}
            for a in (_pick(data, "adverts", default=[]) or []):
                try:
                    cid = int(_pick(a, "advertId", "advert_id"))
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "cid": self.company_id, "c": cid,
                    "en": 1 if _pick(a, "enabled") else 0,
                    "lim": int(_pick(a, "dailyLimit", "daily_limit", default=0) or 0),
                    "spent": int(_pick(a, "spentToday", "spent_today", default=0) or 0),
                    "carry": 1 if _pick(a, "carryOverEnabled", "carry_over_enabled") else 0,
                    "valid": 1 if _pick(a, "valid") else 0,
                    "req": int(_pick(a, "requiredLimit", "required_limit", default=0) or 0),
                    "cur": str(_pick(a, "currency", default="RUB"))[:8],
                })
            if i + 100 < len(campaigns):
                time.sleep(PAUSE_LIMITS_S)
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_daily_limit(company_id, campaign_id, enabled,
                    daily_limit, spent_today, carry_over, is_valid, required_limit, currency)
                VALUES(:cid, :c, :en, :lim, :spent, :carry, :valid, :req, :cur) AS new
                ON DUPLICATE KEY UPDATE
                    enabled = new.enabled, daily_limit = new.daily_limit,
                    spent_today = new.spent_today, carry_over = new.carry_over,
                    is_valid = new.is_valid, required_limit = new.required_limit,
                    currency = new.currency"""), rows)
            await self.db.commit()
        if progress:
            progress("phase", len(rows), len(rows), f"daily-limits: {len(rows)} кампаний")
        return {"campaigns": len(rows)}

    # ---------- кластеры ----------

    async def _sync_clusters(self, token: str, pairs: list[tuple[int, int]],
                             dry_run: bool, progress=None) -> dict:
        """POST /adv/v0/normquery/list — active/excluded/archived по каждой паре."""
        rows = []
        chunks = _chunks(pairs, PAIRS_CHUNK)
        for i, ch in enumerate(chunks, 1):
            payload = {"items": [{"advertId": c, "nmId": n} for c, n in ch]}
            data = post_json(LIST_URL, payload, token, timeout=TIMEOUT_S)
            for it in (_pick(data, "items", default=[]) or []):
                try:
                    cid = int(_pick(it, "advertId", "advert_id"))
                    nm = int(_pick(it, "nmId", "nm_id"))
                except (TypeError, ValueError):
                    continue
                nq = _pick(it, "normQueries", "norm_queries", default={}) or {}
                for state in ("active", "excluded", "archived"):
                    for q in (nq.get(state) or []):
                        q = str(q).strip()
                        if q:
                            rows.append({"cid": self.company_id, "c": cid, "nm": nm,
                                         "q": q[:255], "st": state})
            if i < len(chunks):
                time.sleep(PAUSE_FAST_S)
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_cluster(company_id, campaign_id, nm_id, norm_query, state)
                VALUES(:cid, :c, :nm, :q, :st) AS new
                ON DUPLICATE KEY UPDATE state = new.state"""), rows)
            await self.db.commit()
        if progress:
            progress("phase", len(chunks), len(chunks), f"cluster-list: {len(rows)} кластеров")
        return {"clusters": len(rows)}

    # ---------- ставки кластеров ----------

    async def _sync_bids(self, token: str, pairs: list[tuple[int, int]],
                         dry_run: bool, progress=None) -> dict:
        """POST /adv/v0/normquery/get-bids — текущие ставки + история изменений.

        ВАЖНО: этот метод принимает ТОЛЬКО snake_case (`advert_id`/`nm_id`).
        С camelCase WB отвечает 200 с пустым массивом — выглядит как «ставок
        нет», хотя они есть (проверено на staging 06.11).
        normquery/list, наоборот, принимает только camelCase — у методов
        разные форматы, см. ловушки в шапке модуля.
        """
        rows = []
        chunks = _chunks(pairs, PAIRS_CHUNK)
        for i, ch in enumerate(chunks, 1):
            payload = {"items": [{"advert_id": c, "nm_id": n} for c, n in ch]}
            data = post_json(BIDS_URL, payload, token, timeout=TIMEOUT_S)
            for b in (_pick(data, "bids", default=[]) or []):
                try:
                    cid = int(_pick(b, "advert_id", "advertId"))
                    nm = int(_pick(b, "nm_id", "nmId"))
                except (TypeError, ValueError):
                    continue
                q = str(_pick(b, "norm_query", "normQuery", default="") or "").strip()
                if not q:
                    continue
                rows.append({"cid": self.company_id, "c": cid, "nm": nm, "q": q[:255],
                             "base": float(_pick(b, "bid", default=0) or 0),
                             "kop": int(_pick(b, "bid_kopecks", "bidKopecks", default=0) or 0),
                             "cur": str(_pick(b, "currency", default="RUB"))[:8]})
            if i < len(chunks):
                time.sleep(PAUSE_FAST_S)
        if not rows:
            return {"bids": 0}
        # предыдущие значения — чтобы поймать изменение и записать историю
        prev: dict[tuple, int] = {}
        if not dry_run:
            old = (await self.db.execute(text(
                "SELECT campaign_id, nm_id, norm_query, bid_kopecks"
                " FROM wb_adv_bid WHERE company_id = :cid"),
                {"cid": self.company_id})).all()
            prev = {(int(r[0]), int(r[1]), str(r[2])[:190]): int(r[3] or 0) for r in old}
        hist = []
        for r in rows:
            k = (r["c"], r["nm"], r["q"][:190])
            old_kop = prev.get(k)
            if old_kop is not None and old_kop != r["kop"]:
                hist.append({"cid": self.company_id, "c": r["c"], "nm": r["nm"],
                             "q": r["q"][:255], "kop": r["kop"], "prev": old_kop,
                             "by": "sync"})
        if not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_bid(company_id, campaign_id, nm_id, norm_query,
                    bid_base, bid_kopecks, currency)
                VALUES(:cid, :c, :nm, :q, :base, :kop, :cur) AS new
                ON DUPLICATE KEY UPDATE
                    bid_base = new.bid_base, bid_kopecks = new.bid_kopecks,
                    currency = new.currency"""), rows)
            if hist:
                await self.db.execute(text("""
                    INSERT INTO wb_adv_bid_history(company_id, campaign_id, nm_id,
                        norm_query, bid_kopecks, prev_kopecks, changed_by)
                    VALUES(:cid, :c, :nm, :q, :kop, :prev, :by)"""), hist)
            await self.db.commit()
        if progress:
            progress("phase", len(chunks), len(chunks),
                     f"bids: {len(rows)} ставок, изменилось {len(hist)}")
        # ставки кластеров бывают только у кампаний с РУЧНОЙ ставкой — если их нет,
        # пустой ответ от get-bids это не ошибка, а отсутствие самих ставок
        manual = await self.db.execute(text(
            "SELECT COUNT(*) FROM wb_campaign_item i"
            " INNER JOIN wb_campaign c ON c.campaign_id = i.campaign_id"
            "   AND c.company_id = :cid"
            " WHERE i.company_id = :cid AND c.status IN (9, 11)"
            "   AND c.bid_type = 'manual' AND i.nm_id > 0"),
            {"cid": self.company_id})
        manual_pairs = int(manual.first()[0] or 0) if manual else 0
        return {"bids": len(rows), "changed": len(hist),
                "manual_pairs": manual_pairs}

    # ---------- минус-фразы ----------

    async def _sync_minus(self, token: str, pairs: list[tuple[int, int]],
                          dry_run: bool, progress=None) -> dict:
        """POST /adv/v0/normquery/get-minus — текущие минус-фразы.

        Внимание: здесь ключи `advert_id`/`nm_id` (с подчёркиванием),
        в get-bids и list — `advertId`/`nmId`.
        """
        rows = []
        chunks = _chunks(pairs, PAIRS_CHUNK)
        for i, ch in enumerate(chunks, 1):
            payload = {"items": [{"advert_id": c, "nm_id": n} for c, n in ch]}
            data = post_json(MINUS_URL, payload, token, timeout=TIMEOUT_S)
            for it in (_pick(data, "items", default=[]) or []):
                try:
                    cid = int(_pick(it, "advert_id", "advertId"))
                    nm = int(_pick(it, "nm_id", "nmId"))
                except (TypeError, ValueError):
                    continue
                for q in (_pick(it, "norm_queries", "normQueries", default=[]) or []):
                    q = str(q).strip()
                    if q:
                        rows.append({"cid": self.company_id, "c": cid, "nm": nm, "q": q[:255]})
            if i < len(chunks):
                time.sleep(PAUSE_FAST_S)
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_minus_phrase(company_id, campaign_id, nm_id,
                    norm_query, in_wb, added_by)
                VALUES(:cid, :c, :nm, :q, 1, 'wb') AS new
                ON DUPLICATE KEY UPDATE in_wb = 1"""), rows)
            await self.db.commit()
        if progress:
            progress("phase", len(chunks), len(chunks), f"minus: {len(rows)} фраз")
        return {"minus": len(rows)}
