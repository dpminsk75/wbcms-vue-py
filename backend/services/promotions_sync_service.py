"""Акции WB — синк календаря акций (dp-calendar-api) в БД.

По конвенции проекта (WB_API_SYNC.md): вся работа с WB живёт здесь, а
`promotions_service.py` только читает кэш.

Методы календаря акций (категория токена «Цены и скидки», НЕ «Продвижение»):
  GET  /api/v1/calendar/promotions             — список акций
  GET  /api/v1/calendar/promotions/details     — детали (promotionIDs, до 100 за раз)
  GET  /api/v1/calendar/promotions/nomenclatures — товары акции (ТОЛЬКО регулярные акции)
  POST /api/v1/calendar/promotions/upload      — добавить номенклатуру (ТОЛЬКО регулярные)

Ограничения WB:
  * nomenclatures/upload для автоакций неприменимы — спека WB: «Not applicable for
    auto promotions», staff на форуме подтвердил: методов для автоакций не будет;
  * лимиты категории «Календарь акций»: 10 запросов / 6 сек, интервал 600 мс;
    базовый токен — 1 запрос / час.

Поэтому: (1) всё кэшируем в БД, страница читает кэш; (2) для базового токена
режем число запросов до одной пачки (company_sync_plan + max_chunks).

Время WB в ответе — UTC с суффиксом Z. ЛК продавца показывает московское время,
поэтому в БД пишем naive-время МСК (UTC+3, перехода на летнее время нет).

Таблицы: wb_promotions (календарь+детали), wb_promotion_products (номенклатура).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.sql_bulk import exec_bulk_insert
from backend.services.wb_sync_base import company_sync_plan, get_json, post_json

CALENDAR_URL = "https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions"
DETAILS_URL = "https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions/details"
NOMENCLATURES_URL = "https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions/nomenclatures"
UPLOAD_URL = "https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions/upload"

# Категория токена: «Цены и скидки» (в проекте — ключ "prices" в company_wb_tokens).
TOKEN_CATEGORY = "prices"

PAGE_LIMIT = 1000          # limit методов календаря: 1..1000
DETAILS_BATCH = 100        # promotionIDs: 1..100 за запрос
PAUSE_FAST_S = 1           # personal/service: интервал 600 мс между запросами
PAUSE_SLOW_S = 3600        # базовый токен: 1 запрос / час
TIMEOUT_S = 20
MSK = timezone(timedelta(hours=3))

DEFAULT_DAYS_BACK = 30
DEFAULT_DAYS_FORWARD = 90

PROMO_COLS = [
    "company_id", "promo_id", "name", "promo_type", "start_dt", "end_dt",
    "description", "advantages", "in_promo_leftovers", "in_promo_total",
    "not_in_promo_leftovers", "not_in_promo_total", "participation_percentage",
    "exception_products_count", "ranging", "fetched_at",
]
PROMO_UPSERT = (
    "AS new ON DUPLICATE KEY UPDATE "
    "name = new.name, promo_type = new.promo_type, start_dt = new.start_dt, "
    "end_dt = new.end_dt, description = new.description, advantages = new.advantages, "
    "in_promo_leftovers = new.in_promo_leftovers, in_promo_total = new.in_promo_total, "
    "not_in_promo_leftovers = new.not_in_promo_leftovers, "
    "not_in_promo_total = new.not_in_promo_total, "
    "participation_percentage = new.participation_percentage, "
    "exception_products_count = new.exception_products_count, "
    "ranging = new.ranging, fetched_at = new.fetched_at"
)

PRODUCT_COLS = [
    "company_id", "promo_id", "nm_id", "in_action", "price", "plan_price",
    "currency_code", "discount", "plan_discount", "fetched_at",
]
PRODUCT_UPSERT = (
    "AS new ON DUPLICATE KEY UPDATE "
    "in_action = new.in_action, price = new.price, plan_price = new.plan_price, "
    "currency_code = new.currency_code, discount = new.discount, "
    "plan_discount = new.plan_discount, fetched_at = new.fetched_at"
)


class PromotionsError(RuntimeError):
    """Ошибка, понятная пользователю (WB-ошибка, лимит, нет категории токена)."""


def _dt(value) -> datetime | None:
    """ISO-строка WB (UTC) → naive-время МСК. None, если разобрать не удалось."""
    if not value:
        return None
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(str(value)[:19], fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MSK).replace(tzinfo=None)


def _i(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _j(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def wb_range(days_back: int = DEFAULT_DAYS_BACK,
             days_forward: int = DEFAULT_DAYS_FORWARD) -> tuple[str, str]:
    """Диапазон дат для WB API: сегодня минус N и плюс M (UTC, формат WB)."""
    today = datetime.now(timezone.utc).date()
    d1 = today - timedelta(days=days_back)
    d2 = today + timedelta(days=days_forward)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime(d1.year, d1.month, d1.day).strftime(fmt),
            datetime(d2.year, d2.month, d2.day, 23, 59, 59).strftime(fmt))


class PromotionsSyncService:
    """Синк календаря акций WB → wb_promotions / wb_promotion_products."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id
        self._last_plan: dict = {}

    # ------------------------------------------------------------- гейт/токен

    async def _plan(self, chunks: int) -> dict:
        """Гейт по токену. Базовый токен — 1 запрос/час, поэтому режем chunks."""
        plan = await company_sync_plan(
            self.db, self.company_id, TOKEN_CATEGORY, chunks,
            pause_fast_s=PAUSE_FAST_S, pause_slow_s=PAUSE_SLOW_S)
        self._last_plan = plan
        if plan.get("skip"):
            return plan
        ttype = plan.get("token_type") or "unknown"
        if ttype in ("personal", "service"):
            plan["max_chunks"] = chunks
            plan["fast"] = True
        else:
            plan["max_chunks"] = 1
            plan["fast"] = False
            warn = plan.get("warning") or f"токен {ttype}"
            plan["warning"] = f"{warn}; базовый токен — 1 запрос/час"
        return plan

    def _token(self, plan: dict) -> str:
        if plan.get("skip"):
            skip = str(plan["skip"])
            if "категории" in skip:
                raise PromotionsError(
                    "в токене WB нет категории «Цены и скидки» — "
                    "без неё методы календаря акций не работают")
            raise PromotionsError(skip)
        return plan.get("token") or ""

    # ----------------------------------------------------------------- запросы

    async def fetch_promotions(self, date_from: str, date_to: str,
                               all_promo: bool = True) -> tuple[list[dict], dict]:
        """Список акций из WB (даты — в формате WB)."""
        plan = await self._plan(1)
        token = self._token(plan)
        rows: list[dict] = []
        offset = 0
        while offset < plan["max_chunks"] * PAGE_LIMIT:
            params = [
                ("startDateTime", date_from), ("endDateTime", date_to),
                ("allPromo", "true" if all_promo else "false"),
                ("limit", PAGE_LIMIT), ("offset", offset),
            ]
            data = get_json(CALENDAR_URL, params, token, timeout=TIMEOUT_S)
            items = ((data or {}).get("data") or {}).get("promotions") or []
            if not items:
                break
            rows.extend(items)
            if len(items) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
            time.sleep(PAUSE_FAST_S)
        return rows, plan

    async def fetch_details(self, promo_ids: list[int]) -> list[dict]:
        """Детали по акциям (promotionIDs — до 100 за запрос)."""
        ids = [int(x) for x in promo_ids if x is not None]
        if not ids:
            return []
        batches = (len(ids) + DETAILS_BATCH - 1) // DETAILS_BATCH
        plan = await self._plan(batches)
        token = self._token(plan)
        out: list[dict] = []
        # базовый токен — 1 запрос/час: лишние пачки деталей не запрашиваем
        limit = min(batches, plan.get("max_chunks") or batches)
        for i in range(0, limit * DETAILS_BATCH, DETAILS_BATCH):
            chunk = ids[i:i + DETAILS_BATCH]
            if not chunk:
                break
            params = [("promotionIDs", str(x)) for x in chunk]
            data = get_json(DETAILS_URL, params, token, timeout=TIMEOUT_S)
            out.extend(((data or {}).get("data") or {}).get("promotions") or [])
            if i + DETAILS_BATCH < len(ids):
                time.sleep(PAUSE_FAST_S)
        return out

    async def fetch_nomenclatures(self, promo_id: int,
                                  in_action: bool | None = None) -> list[dict]:
        """Товары акции. in_action=None — оба списка (2 запроса к WB)."""
        plan = await self._plan(1 if in_action is not None else 2)
        token = self._token(plan)
        flags = [True, False] if in_action is None else [bool(in_action)]
        if not plan.get("fast") and len(flags) > 1:
            # базовый токен — 1 запрос/час: забираем только первый список
            flags = flags[:1]
        rows: list[dict] = []
        for flag in flags:
            offset = 0
            while offset < plan["max_chunks"] * PAGE_LIMIT:
                params = [
                    ("promotionID", int(promo_id)),
                    ("inAction", "true" if flag else "false"),
                    ("limit", PAGE_LIMIT), ("offset", offset),
                ]
                data = get_json(NOMENCLATURES_URL, params, token, timeout=TIMEOUT_S)
                items = ((data or {}).get("data") or {}).get("nomenclatures") or []
                if not items:
                    break
                for it in items:
                    it = dict(it)
                    it["inAction"] = bool(it.get("inAction", flag))
                    rows.append(it)
                if len(items) < PAGE_LIMIT:
                    break
                offset += PAGE_LIMIT
                time.sleep(PAUSE_FAST_S)
            if flag is not flags[-1]:
                time.sleep(PAUSE_FAST_S)
        return rows

    async def upload(self, promo_id: int, nm_ids: list[int]) -> dict:
        """Добавить номенклатуру в акцию (только регулярные акции)."""
        plan = await self._plan(1)
        token = self._token(plan)
        payload = {
            "data": {
                "promotionID": int(promo_id),
                "uploadNow": True,
                "nomenclatures": [int(x) for x in nm_ids],
            }
        }
        data = post_json(UPLOAD_URL, payload, token, timeout=TIMEOUT_S)
        body = data if isinstance(data, dict) else {}
        if body.get("errorText"):
            raise PromotionsError(str(body["errorText"]))
        return body.get("data") or {}

    # ------------------------------------------------------------------ запись

    async def sync_calendar(self, date_from: str, date_to: str,
                            all_promo: bool = True, dry_run: bool = False,
                            progress=None) -> dict:
        """Забрать календарь + детали из WB и положить в кэш."""
        rows, plan = await self.fetch_promotions(date_from, date_to, all_promo)
        ids = [int(r["id"]) for r in rows if r.get("id") is not None]
        details: dict[int, dict] = {}
        detail_error = ""
        if ids:
            try:
                for det in await self.fetch_details(ids):
                    if det.get("id") is not None:
                        details[int(det["id"])] = det
            except Exception as e:  # детали не критичны — календарь сохраняем без них
                detail_error = str(e)[:200]
                if progress:
                    progress("details", len(ids), "error", detail_error)
        now = datetime.now().replace(microsecond=0)
        out_rows = []
        for r in rows:
            pid = _i(r.get("id"))
            if pid is None:
                continue
            det = details.get(pid, {})
            out_rows.append({
                "company_id": self.company_id,
                "promo_id": pid,
                "name": str(r.get("name") or "")[:255],
                "promo_type": str(r.get("type") or "")[:16],
                "start_dt": _dt(r.get("startDateTime")),
                "end_dt": _dt(r.get("endDateTime")),
                "description": det.get("description") or r.get("description"),
                "advantages": _j(det.get("advantages") or r.get("advantages")),
                "in_promo_leftovers": _i(det.get("inPromoActionLeftovers")),
                "in_promo_total": _i(det.get("inPromoActionTotal")),
                "not_in_promo_leftovers": _i(det.get("notInPromoActionLeftovers")),
                "not_in_promo_total": _i(det.get("notInPromoActionTotal")),
                "participation_percentage": _i(det.get("participationPercentage")),
                "exception_products_count": _i(det.get("exceptionProductsCount")),
                "ranging": _j(det.get("ranging") or r.get("ranging")),
                "fetched_at": now,
            })
        if not dry_run and out_rows:
            await exec_bulk_insert(self.db, "wb_promotions", PROMO_COLS, out_rows,
                                   suffix=PROMO_UPSERT)
            await self.db.commit()
        if progress:
            progress("calendar", len(out_rows), "ok", f"акций {len(out_rows)}, деталей {len(details)}")
        return {"fetched": len(out_rows), "details": len(details),
                "token_type": plan.get("token_type"),
                "warning": plan.get("warning", ""), "detail_error": detail_error}

    async def fetch_products(self, promo_id: int, in_action: bool | None = None) -> list[dict]:
        """Сырые товары акции из WB (без записи в БД)."""
        return await self.fetch_nomenclatures(promo_id, in_action)

    async def write_products(self, promo_id: int, rows: list[dict],
                             dry_run: bool = False) -> int:
        """Записать товары акции в кэш."""
        now = datetime.now().replace(microsecond=0)
        out_rows = []
        for r in rows:
            nm = _i(r.get("id"))
            if nm is None:
                continue
            out_rows.append({
                "company_id": self.company_id,
                "promo_id": int(promo_id),
                "nm_id": nm,
                "in_action": 1 if r.get("inAction") else 0,
                "price": _f(r.get("price")),
                "plan_price": _f(r.get("planPrice")),
                "currency_code": str(r.get("currencyCode") or "")[:8] or None,
                "discount": _i(r.get("discount")),
                "plan_discount": _i(r.get("planDiscount")),
                "fetched_at": now,
            })
        if not dry_run and out_rows:
            await exec_bulk_insert(self.db, "wb_promotion_products", PRODUCT_COLS,
                                   out_rows, suffix=PRODUCT_UPSERT)
            await self.db.commit()
        return len(out_rows)

    async def sync_products(self, promo_id: int, in_action: bool | None = None,
                            dry_run: bool = False, progress=None) -> dict:
        """Забрать номенклатуру акции из WB и положить в кэш."""
        rows = await self.fetch_products(promo_id, in_action)
        count = await self.write_products(promo_id, rows, dry_run=dry_run)
        if progress:
            progress("products", count, "ok", f"акция {promo_id}: товаров {count}")
        return {"fetched": count}

    async def sync_all(self, days_back: int = DEFAULT_DAYS_BACK,
                       days_forward: int = DEFAULT_DAYS_FORWARD,
                       with_products: bool = True, probe_auto: bool = False,
                       horizon_days: int = 14,
                       dry_run: bool = False, progress=None) -> dict:
        """Полный прогон компании: календарь → номенклатура активных регулярных акций.

        probe_auto — разовая проверка: пробуем номенклатуру для АВТОАКЦИЙ.
        Спека WB говорит «Not applicable for auto promotions», но если метод
        заработает — приложение автоматически перейдёт на данные API.
        """
        df, dt_ = wb_range(days_back, days_forward)
        st = await self.sync_calendar(df, dt_, all_promo=True, dry_run=dry_run,
                                       progress=progress)
        st["products"] = 0
        st["probed_auto"] = []
        if not with_products:
            return st
        # акции, которые идут или скоро стартуют
        rows = await self._relevant_promos(horizon_days=horizon_days)
        if probe_auto:
            # расширенная проверка: все автоакции окна, а не только актуальные
            rows = await self._all_promos()
        # Проба автоакций: по спеке WB номенклатура автоакций недоступна
        # («Not applicable for auto promotions»), но если метод заработал —
        # приложение должно перейти на данные API. Пробуем первый автоакцией
        # один раз; ответ 422 означает, что и остальные не дадут — дальше
        # не тратим лимит.
        auto_supported: bool | None = None
        auto_probed = 0
        for p in rows:
            pid = int(p["promo_id"])
            is_auto = (p.get("promo_type") or "") == "auto"
            if is_auto and auto_supported is False:
                continue
            # базовый токен — 1 запрос/час: пробуем только одну автоакцию
            if is_auto and not (self._last_plan or {}).get("fast", True) and auto_probed:
                continue
            try:
                if is_auto:
                    auto_probed += 1
                    # один запрос: хватает, чтобы понять — работает метод или нет
                    one = await self.fetch_products(pid, True)
                    auto_supported = True
                    if (self._last_plan or {}).get("fast", True):
                        one = one + await self.fetch_products(pid, False)
                    count = await self.write_products(pid, one, dry_run=dry_run)
                    st["products"] += count
                    st["probed_auto"].append({"promo_id": pid, "ok": True,
                                             "products": count})
                    if progress:
                        progress("products", count, "ok",
                                  f"автоакция {pid}: номенклатура доступна ({count} шт.)")
                    continue
                res = await self.sync_products(pid, None, dry_run=dry_run,
                                               progress=progress)
                st["products"] += res.get("fetched", 0)
            except Exception as e:
                msg = str(e)[:200]
                if is_auto:
                    auto_probed += 1
                    auto_supported = False
                    st["probed_auto"].append({"promo_id": pid, "ok": False, "error": msg})
                    if progress:
                        progress("probe", pid, "error",
                                 f"автоакция {pid}: номенклатура недоступна ({msg})")
                    continue
                raise
        return st

    async def _all_promos(self) -> list[dict]:
        """Все акции из кэша (для расширенной проверки автоакций)."""
        from sqlalchemy import text
        rows = (await self.db.execute(text("""
            SELECT promo_id, name, promo_type, start_dt, end_dt
            FROM wb_promotions WHERE company_id = :cid
            ORDER BY promo_id"""),
            {"cid": self.company_id})).mappings().all()
        return [dict(r) for r in rows]

    async def _relevant_promos(self, horizon_days: int = 14) -> list[dict]:
        """Акции из кэша, которые идут сейчас или скоро стартуют.

        Номенклатура нужна и для активных акций, и для тех, что стартуют в
        ближайшие дни (список «подходящих» WB формирует до старта).
        """
        from sqlalchemy import text
        now = datetime.now().replace(microsecond=0)
        horizon = now + timedelta(days=horizon_days)
        rows = (await self.db.execute(text("""
            SELECT promo_id, name, promo_type, start_dt, end_dt
            FROM wb_promotions
            WHERE company_id = :cid
              AND (end_dt IS NULL OR end_dt >= :now)
              AND (start_dt IS NULL OR start_dt <= :horizon)
            ORDER BY promo_id"""),
            {"cid": self.company_id, "now": now, "horizon": horizon})).mappings().all()
        return [dict(r) for r in rows]
