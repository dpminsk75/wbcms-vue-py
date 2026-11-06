"""Загрузка цен и скидок в WB (действие «Передать цены и скидки на WB»).

Метод WB: POST https://discounts-prices-api.wildberries.ru/api/v2/upload/task
  тело {"data": [{"nmID", "price", "discount"}]} — до 1000 товаров за запрос;
  загрузка АСИНХРОННАЯ: ответ даёт id задачи, статус позже —
  GET /api/v2/history/tasks, детализация ошибок /api/v2/history/goods/task.

Карантин («порог 33 %»): если новая цена товара со скидкой меньше трети
текущей цены со скидкой, товар попадёт в карантин и будет продаваться по
старой цене. Поэтому перед отправкой сверяем цену со скидкой, которую
отправляем, с текущей:
  * текущие цены — из wb_price_history (синк каждые 6 ч); если запись
    старее 12 ч или товара в кэше нет — товарная стоимость догоняется
    одним POST /api/v2/list/goods/filter {"nmList": [...]} и пишется в
    wb_price_history (переиспользуем PriceSyncService._process);
  * рисковые товары показываем пользователю и отправляем только после
    его подтверждения;
  * после загрузки список реально попавших в карантин —
    GET /api/v2/quarantine/goods.

Структура отправки: цена = розничная цена (но не ниже минимальной цены WB),
скидка — целое число процентов, при которой цена со скидкой ≈ плановая
цена акции (round вверх — не дороже плана). Токен — категория prices
(«Цены и скидки»). Только stdlib.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.price_sync_service import PriceSyncService
from backend.services.wb_sync_base import company_sync_plan, get_json, post_json

UPLOAD_URL = "https://discounts-prices-api.wildberries.ru/api/v2/upload/task"
FILTER_URL = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"
QUARANTINE_URL = "https://discounts-prices-api.wildberries.ru/api/v2/quarantine/goods"

TIMEOUT_S = 20
MAX_PER_TASK = 1000     # лимит WB на один upload/task
FRESH_HOURS = 12        # кэш цен свежее этого возраста не обновляем
QUARANTINE_DIVISOR = 3.0  # новое price-with-discount < старое / 3 → карантин


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _i(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class PricesUploadService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    # ------------------------------------------------- текущие цены (кэш+WB)

    async def current_prices(self, nm_ids: list[int]) -> dict:
        """Текущие цены/скидки по номенклатуре: кэш wb_price_history.

        Кэш не должен быть старее FRESH_HOURS: если есть устаревшие или
        отсутствующие товары — догоняем их живым POST /api/v2/list/goods/filter
        и сохраняем в кэш. Возвращает карту nm_id -> {price, discounted_price,
        discount, updated_at}.
        """
        prices: dict[int, dict] = {}
        stale: list[int] = []
        for chunk in _chunks(nm_ids, 500):
            ids = ", ".join(f":n{j}" for j in range(len(chunk)))
            params = {"cid": self.company_id}
            params.update({f"n{j}": v for j, v in enumerate(chunk)})
            rows = (await self.db.execute(text(
                "SELECT nm_id, price, discounted_price, discount, updated_at"
                " FROM wb_price_history WHERE company_id = :cid AND is_latest = 1"
                f" AND nm_id IN ({ids})"), params)).mappings().all()
            border = datetime.now() - timedelta(hours=FRESH_HOURS)
            for r in rows:
                nm = int(r["nm_id"])
                item = {
                    "price": _f(r.get("price")),
                    "discounted_price": _f(r.get("discounted_price")),
                    "discount": _i(r.get("discount")),
                    "updated_at": r.get("updated_at"),
                }
                if nm not in prices:
                    prices[nm] = item
                    if not item["updated_at"] or item["updated_at"] < border:
                        stale.append(nm)
        missing = [nm for nm in nm_ids if nm not in prices]
        if missing or stale:
            await self._refresh_prices(sorted(set(missing) | set(stale)))
            # перечитываем освежённый кэш
            prices = await self._reread(nm_ids)
        return prices

    async def _refresh_prices(self, nm_ids: list[int]) -> None:
        """Догнать цены по списку артикулов и записать в wb_price_history."""
        chunks_n = max(1, (len(nm_ids) + MAX_PER_TASK - 1) // MAX_PER_TASK)
        plan = await company_sync_plan(
            self.db, self.company_id, "prices", chunks_n,
            pause_fast_s=1, pause_slow_s=2)
        if plan.get("skip"):
            raise RuntimeError(f"WB prices: {plan['skip']}")
        sync = PriceSyncService(self.db, self.company_id)
        current = await sync._load_current()
        stats = {"fetched": 0, "new": 0, "changed": 0, "same": 0, "pages": 0}
        for chunk in _chunks(nm_ids, MAX_PER_TASK):
            data = post_json(FILTER_URL, {"nmList": [int(x) for x in chunk]},
                             plan["token"], timeout=TIMEOUT_S)
            if not isinstance(data, dict):
                raise RuntimeError("WB prices: неожиданный формат ответа")
            if data.get("error"):
                raise RuntimeError(
                    f"WB prices: {data.get('errorText') or data.get('error')}")
            goods = ((data.get("data") or {}).get("listGoods")) or []
            if not goods:
                continue
            await sync._process(goods, current, stats, False)

    async def _reread(self, nm_ids: list[int]) -> dict:
        prices: dict[int, dict] = {}
        for chunk in _chunks(nm_ids, 500):
            ids = ", ".join(f":n{j}" for j in range(len(chunk)))
            params = {"cid": self.company_id}
            params.update({f"n{j}": v for j, v in enumerate(chunk)})
            rows = (await self.db.execute(text(
                "SELECT nm_id, price, discounted_price, discount, updated_at"
                " FROM wb_price_history WHERE company_id = :cid AND is_latest = 1"
                f" AND nm_id IN ({ids})"), params)).mappings().all()
            for r in rows:
                nm = int(r["nm_id"])
                if nm in prices:
                    continue
                prices[nm] = {
                    "price": _f(r.get("price")),
                    "discounted_price": _f(r.get("discounted_price")),
                    "discount": _i(r.get("discount")),
                    "updated_at": r.get("updated_at"),
                }
        return prices

    # ------------------------------------------------------- подготовка

    def item_for_row(self, row: dict, old: dict | None) -> dict:
        """Позиция для upload/task по строке расчёта + сверка с карантином.

        Отправляем розничную цену (но не ниже минимальной цены WB — WB всегда
        продаёт не дешевле её) и целую скидку, при которой цена со скидкой
        ≈ плановая цена акции (округление вверх — не дороже плана).

        Карантин: новая цена со скидкой < 1/3 текущей цены со скидкой
        (из кэша цен) → товар попадёт в карантин, помечаем риском.
        """
        nm = _i(row.get("nm_id"))
        retail = _f(row.get("price"))
        min_price = _f(row.get("min_price"))
        if min_price > retail:
            retail = min_price
        target = _f(row.get("price_new")) or _f(row.get("price_now"))
        discount = 0
        if target > 0 and retail > 0 and target < retail:
            discount = int(math.ceil((1 - target / retail) * 100.0 - 1e-9))
            discount = max(0, min(99, discount))
        new_discounted = round(retail * (1 - discount / 100.0), 2)
        old_discounted = _f((old or {}).get("discounted_price"))
        if not old_discounted and old and old.get("price"):
            # в кэше нет «цены со скидкой» — считаем сами по цене и скидке
            old_discounted = round(
                _f(old.get("price")) * (1 - _i(old.get("discount")) / 100.0), 2)
        risky = bool(old_discounted > 0
                     and new_discounted < old_discounted / QUARANTINE_DIVISOR - 1e-9)
        return {
            "nm_id": nm,
            "title": row.get("title") or "",
            "vendor_code": row.get("vendor_code") or "",
            "price": _i(math.ceil(retail)) if retail > 0 else 0,
            "discount": discount,
            "new_discounted": new_discounted,
            "old_discounted": old_discounted or None,
            "risky": risky,
        }

    async def prepare(self, rows: list[dict]) -> dict:
        """Собрать позиции для отправки + список рисков карантина.

        rows — строки расчёта (результата analyze), из них берём nm_id, цену,
        минимальную цену, плановую цену (target для скидки).
        """
        items = list(rows or [])
        nm_ids = [_i(r.get("nm_id")) for r in items if _i(r.get("nm_id"))]
        prices = await self.current_prices(nm_ids) if nm_ids else {}
        out: list[dict] = []
        for row in items:
            nm = _i(row.get("nm_id"))
            if not nm:
                continue
            it = self.item_for_row(row, prices.get(nm))
            if row.get("blocked"):
                it["blocked"] = True
            out.append(it)
        risky = [x for x in out if x["risky"] or x.get("blocked")]
        return {"items": out, "risky": risky,
                "prices_source": "cache+wb" if nm_ids else "none"}

    async def upload(self, rows: list[dict], with_risky: bool = False) -> dict:
        """Отправить цены и скидки в WB (upload/task, чанками по 1000).

        with_risky=False — рискованные (карантин/блокировка) не отправляем.
        Возвращает id задач WB; загрузка в WB асинхронная — итог виден через
        /api/v2/history/tasks и GET /api/promotions/quarantine.
        """
        prep = await self.prepare(rows)
        send = prep["items"]
        if not with_risky:
            send = [x for x in send if not x["risky"] and not x.get("blocked")]
        if not send:
            return {"sent": 0, "tasks": [], "skipped_risky": len(prep["risky"]),
                    "prepare": {"risky": prep["risky"], "items": prep["items"]}}
        payload = {"data": [{"nmID": x["nm_id"], "price": x["price"],
                             "discount": x["discount"],
                             "currencyCode": "RUB"} for x in send]}
        chunks_n = max(1, (len(payload["data"]) + MAX_PER_TASK - 1) // MAX_PER_TASK)
        plan = await company_sync_plan(
            self.db, self.company_id, "prices", chunks_n,
            pause_fast_s=1, pause_slow_s=2)
        if plan.get("skip"):
            raise RuntimeError(f"WB upload: {plan['skip']}")
        tasks: list[dict] = []
        errors: list[str] = []
        for chunk in _chunks(payload["data"], MAX_PER_TASK):
            data = post_json(UPLOAD_URL, {"data": chunk}, plan["token"],
                             timeout=TIMEOUT_S)
            if not isinstance(data, dict) or data.get("error"):
                et = (data or {}).get("errorText") if isinstance(data, dict) else None
                errors.append(f"{(data or {}).get('error') if isinstance(data, dict) else ''} {et or 'ошибка WB'}".strip())
                continue
            d = data.get("data") or {}
            tasks.append({"id": d.get("id"), "count": len(chunk),
                          "already_exists": bool(d.get("alreadyExists"))})
        self.db.commit()
        out = {"sent": sum(t["count"] for t in tasks), "tasks": tasks}
        if errors:
            out["errors"] = errors
        out["skipped_risky"] = len(prep["risky"]) if not with_risky else 0
        out["prepare"] = {"risky": prep["risky"], "items": prep["items"]}
        return out

    # ------------------------------------------------------------ карантин

    async def quarantine(self, limit: int = 1000) -> dict:
        """Список товаров в карантине WB (GET /api/v2/quarantine/goods).

        Полезно после загрузки: кто всё-таки ушёл в карантин и продаётся
        по старой цене (ошибка также приходит в детализации загрузки).
        """
        plan = await company_sync_plan(
            self.db, self.company_id, "prices", 1, pause_fast_s=1, pause_slow_s=2)
        if plan.get("skip"):
            raise RuntimeError(f"WB quarantine: {plan['skip']}")
        rows: list[dict] = []
        offset = 0
        for _ in range(20):  # защита от бесконечного цикла
            data = get_json(QUARANTINE_URL,
                            [("limit", limit), ("offset", offset)],
                            plan["token"], timeout=TIMEOUT_S)
            if not isinstance(data, dict):
                raise RuntimeError("WB quarantine: неожиданный формат ответа")
            if data.get("error"):
                raise RuntimeError(
                    f"WB quarantine: {data.get('errorText') or data.get('error')}")
            goods = ((data.get("data") or {}).get("goods")) or []
            rows += [
                {"nm_id": _i(g.get("nmID")),
                 "old_price": _f(g.get("oldPrice")),
                 "new_price": _f(g.get("newPrice")),
                 "old_discount": _i(g.get("oldDiscount")),
                 "new_discount": _i(g.get("newDiscount")),
                 "price_diff": _f(g.get("priceDiff"))}
                for g in goods if g.get("nmID")]
            if len(goods) < limit:
                break
            offset += limit
        return {"rows": rows, "count": len(rows)}
