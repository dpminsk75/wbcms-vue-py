"""Цены и скидки WB: discounts-prices-api -> wb_price_history.

Порт commands/WbPriceController.php:
  GET https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter
      ?limit=300&offset=N  (+ filterNmID — точечно по артикулу)
  Авторизация — raw api_key (БЕЗ Bearer, как в PHP), пауза 6с между
  страницами (у discounts-prices свой лимит, не stocks-report).

Логика (1в1 с PHP):
  * карта текущих цен «nmId_sizeId» -> строка (is_latest=1);
  * для каждого размера сравниваем 5 полей (price, discounted_price,
    club_discounted_price, discount, club_discount);
  * совпало  -> подтверждаем только updated_at;
  * изменилось -> закрываем старую запись (is_latest=0) и вставляем новую;
  * нового размера -> вставляем.

Отличие от PHP: PHP писал по одному UPDATE/INSERT на размер (для магазина
с 1500 карточек это ~7k round-trip'ов). Здесь — батчи: UPDATE по списку id
(по 500) + executemany INSERT.

ТАБЛИЦА БЕЗ UNIQUE на (company_id, nm_id, size_id) — upsert невозможен,
поэтому история цен и пишется «закрыл + вставил». Из-за этого возможен
дубль is_latest=1 при гонке двух прогонов — воркер берёт flock на pid-файл.

Токен — companies.api_key (категория prices). Только stdlib.
"""
import os
import time
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json

PRICES_URL = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"
TIMEOUT_S = 20
PAGE_LIMIT = 300
PAUSE_S = 6
BATCH = 500


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class PriceSyncService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    # --- служебное -------------------------------------------------------

    async def _load_current(self) -> dict:
        """Карта текущих цен: "nmId_sizeId" -> строка (is_latest=1)."""
        rows = (await self.db.execute(text(
            "SELECT id, nm_id, size_id, price, discounted_price,"
            " club_discounted_price, discount, club_discount"
            " FROM wb_price_history WHERE company_id = :cid AND is_latest = 1"),
            {"cid": self.company_id})).mappings().all()
        out: dict[str, dict] = {}
        for r in rows:
            out[f"{int(r['nm_id'])}_{int(r['size_id'])}"] = dict(r)
        return out

    @staticmethod
    def _same(existing: dict, price: float, discounted: float,
              club_discounted, discount: int, club_discount: int) -> bool:
        return (_f(existing["price"]) == price
                and _f(existing["discounted_price"]) == discounted
                and _f(existing["club_discounted_price"]) == _f(club_discounted)
                and _i(existing["discount"]) == discount
                and _i(existing["club_discount"]) == club_discount)

    # --- основное --------------------------------------------------------

    async def sync(self, dry_run: bool = False, nm_id: int | None = None,
                   progress=None) -> dict:
        plan = await company_sync_plan(
            self.db, self.company_id, "prices", 1,
            pause_fast_s=PAUSE_S, pause_slow_s=PAUSE_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token = plan["token"]
        current = await self._load_current()
        stats = {"fetched": 0, "new": 0, "changed": 0, "same": 0, "pages": 0}
        offset = 0
        while True:
            params = [("limit", PAGE_LIMIT), ("offset", offset)]
            if nm_id is not None:
                params.append(("filterNmID", nm_id))
            t0 = time.monotonic()
            data = get_json(PRICES_URL, params, token, timeout=TIMEOUT_S)
            el = time.monotonic() - t0
            if not isinstance(data, dict):
                raise RuntimeError("WB prices: неожиданный формат ответа")
            if data.get("error"):
                raise RuntimeError(
                    f"WB prices: {data.get('errorText') or data.get('error')}")
            goods = ((data.get("data") or {}).get("listGoods")) or []
            if not goods:
                break
            await self._process(goods, current, stats, dry_run)
            stats["fetched"] += len(goods)
            stats["pages"] += 1
            if progress:
                progress(stats["pages"], len(goods), "pause", el, PAUSE_S)
            if len(goods) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
            time.sleep(PAUSE_S)
        out = {"company_id": self.company_id, "rows": 0 if dry_run else stats["fetched"],
               "fetched": stats["fetched"], "new": stats["new"],
               "changed": stats["changed"], "same": stats["same"],
               "pages": stats["pages"], "token_type": plan["token_type"],
               "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    async def _process(self, goods: list, current: dict, stats: dict,
                       dry_run: bool) -> None:
        """Обрабатывает страницу товаров и пишет пачками."""
        now = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        to_close: list[int] = []     # цена изменилась — закрыть старую запись
        to_touch: list[int] = []     # цена не изменилась — только updated_at
        to_insert: list[dict] = []   # новая запись (новый размер или новая цена)

        for item in goods:
            nm = _i(item.get("nmID"))
            if not nm:
                continue
            vendor_code = item.get("vendorCode")
            currency = item.get("currencyIsoCode4217")
            discount = _i(item.get("discount"))
            club_discount = _i(item.get("clubDiscount"))
            bad_turnover = 1 if item.get("isBadTurnover") else 0
            for size in (item.get("sizes") or []):
                size_id = _i(size.get("sizeID"))
                if not size_id:
                    continue
                price = _f(size.get("price"))
                discounted = _f(size.get("discountedPrice"))
                cd_raw = size.get("clubDiscountedPrice")
                club_discounted = _f(cd_raw) if cd_raw is not None else None
                tech = size.get("techSizeName")
                tech = str(tech)[:20] if tech is not None else None
                vc = str(vendor_code)[:255] if vendor_code is not None else None
                cur = str(currency)[:3] if currency is not None else None
                row = {
                    "cid": self.company_id, "nm": nm, "vc": vc,
                    "sid": size_id, "ts": tech, "price": price,
                    "disc": discounted, "cdisc": club_discounted,
                    "cur": cur, "d": discount, "cd": club_discount,
                    "bt": bad_turnover, "now": now,
                }
                key = f"{nm}_{size_id}"
                existing = current.get(key)
                if existing is None:
                    to_insert.append(row)
                    stats["new"] += 1
                    continue
                if self._same(existing, price, discounted, club_discounted,
                              discount, club_discount):
                    to_touch.append(int(existing["id"]))
                    stats["same"] += 1
                    continue
                to_close.append(int(existing["id"]))
                to_insert.append(row)
                stats["changed"] += 1

        if dry_run or not (to_close or to_touch or to_insert):
            return

        # 1) Закрываем старые записи (цена изменилась) — по id из карты.
        for chunk in _chunks(to_close, BATCH):
            ph = ",".join(f":i{n}" for n in range(len(chunk)))
            await self.db.execute(text(
                f"UPDATE wb_price_history SET is_latest = 0, updated_at = :now"
                f" WHERE id IN ({ph}) AND company_id = :cid"),
                {"now": now, "cid": self.company_id,
                 **{f"i{n}": v for n, v in enumerate(chunk)}})
        # 2) Подтверждаем неизменившиеся (только updated_at) — тоже по id.
        for chunk in _chunks(to_touch, BATCH):
            ph = ",".join(f":i{n}" for n in range(len(chunk)))
            await self.db.execute(text(
                f"UPDATE wb_price_history SET updated_at = :now"
                f" WHERE id IN ({ph}) AND company_id = :cid"),
                {"now": now, "cid": self.company_id,
                 **{f"i{n}": v for n, v in enumerate(chunk)}})
        # 3) Вставляем новые записи.
        inserted_keys: list[tuple[int, int]] = []
        for chunk in _chunks(to_insert, BATCH):
            await self.db.execute(text("""
                INSERT INTO wb_price_history
                  (company_id, nm_id, vendor_code, size_id, tech_size_name, price,
                   discounted_price, club_discounted_price, currency_code, discount,
                   club_discount, is_bad_turnover, is_latest, created_at, updated_at)
                VALUES(:cid, :nm, :vc, :sid, :ts, :price, :disc, :cdisc, :cur,
                       :d, :cd, :bt, 1, :now, :now)"""), chunk)
            inserted_keys.extend((int(r["nm"]), int(r["sid"])) for r in chunk)
        await self.db.commit()

        # 4) Возвращаем в карту реальные id вставленных строк: без них повторное
        #    появление того же размера в этом же прогоне нельзя было бы закрыть
        #    (id был бы 0 → UPDATE ... WHERE id IN (0) не попал бы ни в одну строку,
        #    и осталось бы два is_latest=1 на пару nm_id+size_id).
        if inserted_keys:
            for chunk in _chunks(inserted_keys, 200):
                cond = " OR ".join(f"(nm_id = :n{n} AND size_id = :z{n})"
                                   for n in range(len(chunk)))
                p = {"cid": self.company_id}
                for n, (nm, sid) in enumerate(chunk):
                    p[f"n{n}"] = nm
                    p[f"z{n}"] = sid
                fresh = (await self.db.execute(text(
                    "SELECT id, nm_id, size_id, price, discounted_price,"
                    " club_discounted_price, discount, club_discount"
                    f" FROM wb_price_history WHERE company_id = :cid"
                    f" AND is_latest = 1 AND ({cond})"),
                    p)).mappings().all()
                for r in fresh:
                    current[f"{int(r['nm_id'])}_{int(r['size_id'])}"] = dict(r)


def acquire_lock(path: str) -> "object | None":
    """flock на pid-файле — защита от двух одновременных прогонов.

    Без него два воркера успеют вставить по одной записи is_latest=1
    на одну пару (company_id, nm_id, size_id) — таблица без UNIQUE.
    """
    try:
        import fcntl
    except ImportError:      # windows — блокировки нет
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    f = open(path, "a+")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f
