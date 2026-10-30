"""Анализ остатков WB (раздел «Анализ остатков», /wb-stock).

Единый источник спроса — детализация продаж WB (`detail_by_period`):
операция «Продажа», разрез склада = `office_name`
(«Склад WB» = FBO — обслуживается остатками `wb_stocks`;
 «Склад поставщика — везу на склад WB» = FBS — везёт продавец, остатки складов WB его не касаются).

Остатки — дневной срез `wb_stocks` (по компании, последняя доступная дата).

`wb_order` / `wb_sales` НЕ используются: 17 млн строк без индекса по дате
(полный скан на проде) + отключаемые WB методы supplier/orders и supplier/sales.

Формулы — 1в1 из Yii2 (`WbStockController::actionAnalytics`, `models/WbStocks.php`):
  daily_speed = продажи / дни окна
  days_left   = остаток / daily_speed (999 = «нет продаж»)
Срезы: дефицит (остаток > 0, спрос > 0, дней <= порога),
       нет в наличии (остаток = 0, спрос > 0),
       излишки (остаток > 0 и (дней > порога излишков или спрос = 0)).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

# office_name: FBO — товар лежит на складах WB; FBS — продавец везёт сам.
OFFICE_FBO = "Склад WB"
OFFICE_FBS_PREFIX = "Склад поставщика"

# Пороги Yii2: дефицит ≤ 7 дней, излишки > 60 дней, окно спроса 14 дней.
DEFAULT_DAYS = 14
DEFAULT_DEFICIT_DAYS = 7
DEFAULT_EXCESS_DAYS = 60
DEFAULT_LIMIT = 100
MAX_LIMIT = 500

# Сколько дней назад ищем предыдущий снимок остатков для дельты KPI.
DELTA_LOOKBACK_DAYS = 7

SORT_KEYS = {
    "days_left": "days_left",
    "speed": "speed",
    "stock": "stock",
    "sold": "sold_qty",
    "money": "sold_money",
}


def _d(value) -> str | None:
    """datetime/date → 'YYYY-MM-DD'."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


class StockAnalyticsService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # ---------- служебное ----------

    def _cid(self) -> int:
        if self.company_id is None:
            raise ValueError("company_id required")
        return int(self.company_id)

    async def _scalar(self, sql: str, params: dict):
        return (await self.db.execute(text(sql), params)).scalar()

    async def _rows(self, sql: str, params: dict) -> list[dict]:
        res = await self.db.execute(text(sql), params)
        return [dict(r) for r in res.mappings().all()]

    async def _rows_in(self, sql: str, params: dict, ids: list, key: str = "ids") -> list[dict]:
        if not ids:
            return []
        res = await self.db.execute(
            text(sql).bindparams(bindparam(key, expanding=True)),
            {**params, key: ids},
        )
        return [dict(r) for r in res.mappings().all()]

    # ---------- даты ----------

    async def snapshot_date(self, before: str | None = None) -> str | None:
        """Последний снимок остатков (по компании). before — не новее этой даты."""
        cid = self._cid()
        if before:
            sql = ("SELECT MAX(s.date) FROM wb_stocks s "
                   "WHERE s.company_id = :cid AND s.date <= :before")
            return _d(await self._scalar(sql, {"cid": cid, "before": before}))
        sql = "SELECT MAX(s.date) FROM wb_stocks s WHERE s.company_id = :cid"
        return _d(await self._scalar(sql, {"cid": cid}))

    async def data_date(self) -> str | None:
        """Последняя дата продаж в детализации — на неё обрезаем окно."""
        cid = self._cid()
        sql = ("SELECT MAX(d.sale_dt) FROM detail_by_period d "
               "WHERE d.company_id = :cid AND d.supplier_oper_name = 'Продажа'")
        return _d(await self._scalar(sql, {"cid": cid}))

    async def cost_date(self) -> str | None:
        """Последняя загрузка себестоимости (загружается пачками — одна дата на фай��)."""
        return _d(await self._scalar("SELECT MAX(c.load_date) FROM wbcards_costs c", {}))

    # ---------- остатки ----------

    async def _stocks(self, snap: str) -> dict[str, float]:
        """{nm_id: количество} на снимке остатков."""
        cid = self._cid()
        rows = await self._rows(
            "SELECT s.nm_id AS nm_id, SUM(s.quantity) AS stock "
            "FROM wb_stocks s WHERE s.company_id = :cid AND s.date = :d "
            "GROUP BY s.nm_id",
            {"cid": cid, "d": snap},
        )
        return {str(r["nm_id"]): float(r["stock"] or 0) for r in rows}

    async def _stock_money(self, snap: str, price_mode: str) -> dict[str, float]:
        """{nm_id: сумма остатка в рублях} — по цене со скидкой WB или по себестоимости."""
        cid = self._cid()
        if price_mode == "cost":
            cost_date = await self.cost_date()
            if not cost_date:
                return {}
            rows = await self._rows(
                "SELECT c.nmID AS nm_id, SUM(s.quantity * c.price) AS money "
                "FROM wb_stocks s "
                "JOIN wbcards_costs c "
                "  ON c.nmID = CAST(s.nm_id AS UNSIGNED) "
                " AND c.chrtID = CAST(s.tech_size AS UNSIGNED) "
                " AND c.load_date = :cost_date "
                "WHERE s.company_id = :cid AND s.date = :d "
                "GROUP BY c.nmID",
                {"cid": cid, "d": snap, "cost_date": cost_date},
            )
        else:
            rows = await self._rows(
                "SELECT p.nm_id AS nm_id, SUM(s.quantity * p.discounted_price) AS money "
                "FROM wb_stocks s "
                "JOIN wb_price_history p "
                "  ON p.company_id = s.company_id "
                " AND p.nm_id = CAST(s.nm_id AS UNSIGNED) "
                " AND p.size_id = CAST(s.tech_size AS UNSIGNED) "
                " AND p.is_latest = 1 "
                "WHERE s.company_id = :cid AND s.date = :d "
                "GROUP BY p.nm_id",
                {"cid": cid, "d": snap},
            )
        return {str(r["nm_id"]): float(r["money"] or 0) for r in rows}

    async def _stock_total(self, snap: str) -> tuple[float, float, int]:
        """(сумма остатка в штуках, изменение за сутки, число товаров) — по двум снимкам."""
        cid = self._cid()
        prev = await self.snapshot_date(before=(date.fromisoformat(snap) - timedelta(days=1)).isoformat())
        total = await self._scalar(
            "SELECT SUM(s.quantity) FROM wb_stocks s WHERE s.company_id = :cid AND s.date = :d",
            {"cid": cid, "d": snap},
        )
        items = int(await self._scalar(
            "SELECT COUNT(DISTINCT s.nm_id) FROM wb_stocks s WHERE s.company_id = :cid AND s.date = :d",
            {"cid": cid, "d": snap},
        ) or 0)
        prev_total = None
        if prev:
            prev_total = await self._scalar(
                "SELECT SUM(s.quantity) FROM wb_stocks s WHERE s.company_id = :cid AND s.date = :d",
                {"cid": cid, "d": prev},
            )
        delta = 0.0
        if total is not None and prev_total is not None:
            delta = float(total) - float(prev_total)
        return float(total or 0), delta, items

    # ---------- спрос (продажи) ----------

    async def _demand(self, frm: str, to: str, fbo_only: bool) -> dict[int, dict]:
        """{nm_id: {qty, money}} — продажи за окно [frm, to)."""
        cid = self._cid()
        office = " AND d.office_name = :office" if fbo_only else ""
        params = {"cid": cid, "frm": f"{frm} 00:00:00", "to": f"{to} 00:00:00"}
        if fbo_only:
            params["office"] = OFFICE_FBO
        rows = await self._rows(
            "SELECT d.nm_id AS nm_id, SUM(d.quantity) AS qty, "
            "SUM(d.retail_price_withdisc_rub) AS money "
            "FROM detail_by_period d "
            "WHERE d.company_id = :cid AND d.supplier_oper_name = 'Продажа' "
            "AND d.nm_id IS NOT NULL "
            "AND d.sale_dt >= :frm AND d.sale_dt < :to" + office +
            " GROUP BY d.nm_id",
            params,
        )
        return {
            int(r["nm_id"]): {"qty": float(r["qty"] or 0), "money": float(r["money"] or 0)}
            for r in rows
        }

    async def _demand_by_office(self, frm: str, to: str) -> list[dict]:
        """Продажи по складам (office_name): qty, money, товаров."""
        cid = self._cid()
        return await self._rows(
            "SELECT d.office_name AS office, SUM(d.quantity) AS qty, "
            "SUM(d.retail_price_withdisc_rub) AS money, COUNT(DISTINCT d.nm_id) AS nm_cnt "
            "FROM detail_by_period d "
            "WHERE d.company_id = :cid AND d.supplier_oper_name = 'Продажа' "
            "AND d.nm_id IS NOT NULL "
            "AND d.sale_dt >= :frm AND d.sale_dt < :to "
            "GROUP BY d.office_name",
            {"cid": cid, "frm": f"{frm} 00:00:00", "to": f"{to} 00:00:00"},
        )

    async def _demand_split(self, frm: str, to: str) -> dict[int, dict]:
        """{nm_id: {fbo, fbs, other}} — разрез продаж по типу склада."""
        cid = self._cid()
        rows = await self._rows(
            "SELECT d.nm_id AS nm_id, d.office_name AS office, SUM(d.quantity) AS qty "
            "FROM detail_by_period d "
            "WHERE d.company_id = :cid AND d.supplier_oper_name = 'Продажа' "
            "AND d.nm_id IS NOT NULL "
            "AND d.sale_dt >= :frm AND d.sale_dt < :to "
            "GROUP BY d.nm_id, d.office_name",
            {"cid": cid, "frm": f"{frm} 00:00:00", "to": f"{to} 00:00:00"},
        )
        out: dict[int, dict] = {}
        for r in rows:
            bucket = out.setdefault(int(r["nm_id"]), {"fbo": 0.0, "fbs": 0.0, "other": 0.0})
            office = (r["office"] or "").strip()
            qty = float(r["qty"] or 0)
            if office == OFFICE_FBO:
                bucket["fbo"] += qty
            elif office.startswith(OFFICE_FBS_PREFIX):
                bucket["fbs"] += qty
            else:
                bucket["other"] += qty
        return out

    # ---------- цены и карточки ----------

    async def _avg_prices(self, nm_ids: list[int]) -> dict[int, float]:
        """{nm_id: средняя цена со скидкой} — среднее арифметическое по актуальным размерам."""
        cid = self._cid()
        rows = await self._rows_in(
            "SELECT p.nm_id AS nm_id, AVG(p.discounted_price) AS avg_price "
            "FROM wb_price_history p "
            "WHERE p.company_id = :cid AND p.is_latest = 1 AND p.nm_id IN :ids "
            "GROUP BY p.nm_id",
            {"cid": cid},
            [int(i) for i in nm_ids],
        )
        return {int(r["nm_id"]): float(r["avg_price"] or 0) for r in rows}

    async def _cards(self, nm_ids: list[int]) -> dict[int, dict]:
        """{nm_id: {title, brand, vendorCode, photos, category}}."""
        cid = self._cid()
        rows = await self._rows_in(
            "SELECT c.nmID AS nm_id, c.title AS title, c.brand AS brand, "
            "c.vendorCode AS vendor_code, c.photos AS photos, "
            "sc.parent_name AS category "
            "FROM wbcards c "
            "LEFT JOIN wb_subject_catalog sc ON sc.subject_id = c.subjectID "
            "WHERE c.nmID IN :ids AND (c.company_id = :cid OR c.company_id IS NULL)",
            {"cid": cid},
            [int(i) for i in nm_ids],
        )
        return {int(r["nm_id"]): r for r in rows}

    def _filter_metrics(self, metrics: list[dict], cards: dict[int, dict],
                        product: str | None, brand: str | None,
                        category: str | None) -> list[dict]:
        """Фильтры страницы (товар/бренд/категория) — по данным карточек, без LIKE в SQL."""
        p = str(product or "").strip().lower()
        b = str(brand or "").strip().lower()
        c = str(category or "").strip().lower()
        if not (p or b or c):
            return metrics
        out = []
        for m in metrics:
            card = cards.get(m["nm_id"], {})
            if b and str(card.get("brand") or "").strip().lower() != b:
                continue
            if c and str(card.get("category") or "").strip().lower() != c:
                continue
            if p:
                nm = str(m["nm_id"])
                vc = str(card.get("vendor_code") or "").strip().lower()
                ti = str(card.get("title") or "").strip().lower()
                if not (nm == p or vc == p or (ti and p in ti)):
                    continue
            out.append(m)
        return out

    # ---------- расчёт срезов ----------

    def _metrics(self, stock: dict[str, float], demand: dict[int, dict],
                 days: int, stock_money: dict[str, float]) -> list[dict]:
        """Метрики по товарам: остаток, продажи, скорость, дней до 0."""
        rows: list[dict] = []
        nm_ids = set(int(k) for k in demand.keys())
        for k in stock.keys():
            try:
                nm_ids.add(int(k))
            except (TypeError, ValueError):
                continue  # мусорный nm_id в снимке — пропускаем
        for nm in sorted(nm_ids):
            key = str(nm)
            st = float(stock.get(key, 0) or 0)
            dem = demand.get(nm, {"qty": 0.0, "money": 0.0})
            qty = float(dem.get("qty") or 0)
            money = float(dem.get("money") or 0)
            speed = qty / days if days > 0 else 0.0
            days_left = (st / speed) if speed > 0 else None
            rows.append({
                "nm_id": nm,
                "stock": st,
                "stock_money": float(stock_money.get(key, 0) or 0),
                "sold_qty": qty,
                "sold_money": money,
                "speed": round(speed, 4),
                "days_left": round(days_left, 2) if days_left is not None else None,
                "avg_price": round(money / qty, 2) if qty > 0 else None,
            })
        return rows

    def _slices(self, metrics: list[dict], deficit_days: int, excess_days: int) -> dict:
        deficit, out_of_stock, excess = [], [], []
        for m in metrics:
            stock = m["stock"]
            speed = m["speed"]
            days_left = m["days_left"]
            if stock > 0 and speed > 0 and days_left is not None and days_left <= deficit_days:
                m = {**m, "status": "deficit"}
                deficit.append(m)
            elif stock <= 0 and speed > 0:
                m = {**m, "status": "out_of_stock"}
                out_of_stock.append(m)
            elif stock > 0 and (speed <= 0 or days_left is None or days_left > excess_days):
                m = {**m, "status": "no_sales" if speed <= 0 else "excess"}
                excess.append(m)
        deficit.sort(key=lambda r: (r["days_left"] if r["days_left"] is not None else 1e9))
        out_of_stock.sort(key=lambda r: -r["speed"])
        excess.sort(key=lambda r: -r["stock"])
        return {"deficit": deficit, "out_of_stock": out_of_stock, "excess": excess}

    def _apply_cards(self, rows: list[dict], cards: dict[int, dict]) -> list[dict]:
        out = []
        for r in rows:
            card = cards.get(r["nm_id"], {})
            out.append({
                **r,
                "title": card.get("title") or "",
                "brand": card.get("brand") or "",
                "vendor_code": card.get("vendor_code") or "",
                "photos": card.get("photos"),
            })
        return out

    async def _deficit_delta(self, snap: str, days: int, fbo_only: bool,
                             deficit_days: int, product: str | None,
                             brand: str | None, category: str | None) -> dict:
        """Дельта числа дефицитных товаров.

        Сравниваем с ближайшим снимком остатков ≤ 7 дней назад от текущего снимка;
        окно продаж той же длины заканчивается датой этого снимка
        (спрос на 22.10 полон, как и на 28.10).
        """
        limit = (date.fromisoformat(snap) - timedelta(days=DELTA_LOOKBACK_DAYS)).isoformat()
        prev_snap = await self.snapshot_date(before=limit)
        if not prev_snap:
            return {"prev_date": None, "prev_count": None}
        prev_from = (date.fromisoformat(prev_snap) - timedelta(days=days - 1)).isoformat()
        prev_stock = await self._stocks(prev_snap)
        prev_demand = await self._demand(prev_from, prev_snap, fbo_only)
        prev_metrics = self._metrics(prev_stock, prev_demand, days, {})
        prev_cards = await self._cards([m["nm_id"] for m in prev_metrics])
        prev_metrics = self._filter_metrics(prev_metrics, prev_cards, product, brand, category)
        prev_slices = self._slices(prev_metrics, deficit_days, DEFAULT_EXCESS_DAYS)
        return {"prev_date": prev_snap, "prev_count": len(prev_slices["deficit"])}

    # ---------- публичное API ----------

    async def turnover(self, date_from: str | None = None, date_to: str | None = None,
                       threshold: int = DEFAULT_DEFICIT_DAYS,
                       excess_days: int = DEFAULT_EXCESS_DAYS,
                       fbo_only: bool = True, price_mode: str = "wb",
                       limit: int = DEFAULT_LIMIT, product: str | None = None,
                       brand: str | None = None, category: str | None = None) -> dict:
        """Оборачиваемость: три среза + KPI + дельта."""
        cid = self._cid()
        limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))

        data_date = await self.data_date()
        snap = await self.snapshot_date()
        if not data_date or not snap:
            return {
                "empty": True, "data_date": data_date, "snapshot_date": snap,
                "period": {"from": date_from, "to": date_to, "days": 0},
                "kpi": {"deficit": 0, "out_of_stock": 0, "excess": 0,
                        "stock_total": 0, "stock_delta": 0, "deficit_delta": None},
                "deficit": {"total": 0, "rows": []},
                "out_of_stock": {"total": 0, "rows": []},
                "excess": {"total": 0, "rows": []},
            }

        # Окно: конец обрезаем датой данных, начало — по календарю пользователя.
        to_eff = date_to or data_date
        if to_eff > data_date:
            to_eff = data_date
        from_eff = date_from or (date.fromisoformat(to_eff) - timedelta(days=DEFAULT_DAYS - 1)).isoformat()
        if from_eff > to_eff:
            from_eff = to_eff
        days = (date.fromisoformat(to_eff) - date.fromisoformat(from_eff)).days + 1

        stock = await self._stocks(snap)
        stock_money = await self._stock_money(snap, price_mode)
        demand = await self._demand(from_eff, to_eff, fbo_only)
        metrics = self._metrics(stock, demand, days, stock_money)

        nm_ids = [m["nm_id"] for m in metrics]
        cards = await self._cards(nm_ids)
        metrics = self._filter_metrics(metrics, cards, product, brand, category)

        avg_prices = await self._avg_prices(nm_ids)        # «Упущено, ₽/день» = потенциал × средняя цена со скидкой (fallback — средняя цена продаж).
        for m in metrics:
            price = avg_prices.get(m["nm_id"]) or m["avg_price"] or 0.0
            m["price_used"] = round(price, 2)
            m["lost_per_day"] = round(m["speed"] * price, 2)

        slices = self._slices(metrics, threshold, excess_days)

        stock_total, stock_delta, stock_items = await self._stock_total(snap)
        delta = await self._deficit_delta(snap, days, fbo_only, threshold, product, brand, category)
        deficit_delta = None
        if delta.get("prev_date") and delta.get("prev_count") is not None:
            deficit_delta = len(slices["deficit"]) - int(delta["prev_count"])

        return {
            "empty": False,
            "data_date": data_date,
            "snapshot_date": snap,
            "prev_snapshot_date": delta.get("prev_date"),
            "period": {"from": from_eff, "to": to_eff, "days": days},
            "kpi": {
                "deficit": len(slices["deficit"]),
                "out_of_stock": len(slices["out_of_stock"]),
                "excess": len(slices["excess"]),
                "stock_total": stock_total,
                "stock_delta": stock_delta,
                "stock_items": stock_items,
                "deficit_delta": deficit_delta,
            },
            "deficit": {"total": len(slices["deficit"]),
                        "rows": self._apply_cards(slices["deficit"][:limit], cards)},
            "out_of_stock": {"total": len(slices["out_of_stock"]),
                             "rows": self._apply_cards(slices["out_of_stock"][:limit], cards)},
            "excess": {"total": len(slices["excess"]),
                       "rows": self._apply_cards(slices["excess"][:limit], cards)},
        }

    async def sklads(self, date_from: str | None = None, date_to: str | None = None,
                     top: int = 50, mode: str = "all", price_mode: str = "wb",
                     threshold: int = DEFAULT_DEFICIT_DAYS,
                     excess_days: int = DEFAULT_EXCESS_DAYS,
                     product: str | None = None, brand: str | None = None,
                     category: str | None = None) -> dict:
        """Спрос по складам + ТОП товаров по остатку."""
        cid = self._cid()
        top = max(1, min(int(top or 50), MAX_LIMIT))

        data_date = await self.data_date()
        snap = await self.snapshot_date()
        if not data_date or not snap:
            return {"empty": True, "data_date": data_date, "snapshot_date": snap,
                    "warehouses": [], "warehouses_total": {}, "top": {"rows": [], "total": 0}}

        to_eff = date_to or data_date
        if to_eff > data_date:
            to_eff = data_date
        from_eff = date_from or (date.fromisoformat(to_eff) - timedelta(days=DEFAULT_DAYS - 1)).isoformat()
        if from_eff > to_eff:
            from_eff = to_eff
        days = (date.fromisoformat(to_eff) - date.fromisoformat(from_eff)).days + 1

        offices = await self._demand_by_office(from_eff, to_eff)
        total_qty = sum(float(o["qty"] or 0) for o in offices)
        total_money = sum(float(o["money"] or 0) for o in offices)
        total_nm = int(await self._scalar(
            "SELECT COUNT(DISTINCT d.nm_id) FROM detail_by_period d "
            "WHERE d.company_id = :cid AND d.supplier_oper_name = 'Продажа' "
            "AND d.nm_id IS NOT NULL AND d.sale_dt >= :frm AND d.sale_dt < :to",
            {"cid": cid, "frm": f"{from_eff} 00:00:00", "to": f"{to_eff} 00:00:00"},
        ) or 0)

        warehouses = []
        for o in offices:
            name = (o["office"] or "").strip() or "(без склада)"
            qty = float(o["qty"] or 0)
            warehouses.append({
                "name": name,
                "kind": self._office_kind(name),
                "qty": qty,
                "money": float(o["money"] or 0),
                "share": round(qty / total_qty * 100, 2) if total_qty > 0 else 0.0,
                "nm_cnt": int(o["nm_cnt"] or 0),
                "is_other": False,
            })
        warehouses.sort(key=lambda w: -w["qty"])

        # Складов меньше 20 — не группируем. Больше 20 — режим «top»: ТОП-20 своими
        # названиями, остальные в «Прочие». В режиме «all» — все строки как есть.
        if len(warehouses) > 20 and mode == "top":
            head, tail = warehouses[:20], warehouses[20:]
            if tail:
                warehouses = head + [{
                    "name": f"Прочие склады ({len(tail)})",
                    "kind": "other",
                    "qty": sum(w["qty"] for w in tail),
                    "money": sum(w["money"] for w in tail),
                    "share": round(sum(w["qty"] for w in tail) / total_qty * 100, 2) if total_qty > 0 else 0.0,
                    "nm_cnt": sum(w["nm_cnt"] for w in tail),
                    "is_other": True,
                }]

        # ТОП товаров по остатку
        stock = await self._stocks(snap)
        stock_money = await self._stock_money(snap, price_mode)
        demand = await self._demand(from_eff, to_eff, True)
        split = await self._demand_split(from_eff, to_eff)
        metrics = self._metrics(stock, demand, days, stock_money)
        cards = await self._cards([m["nm_id"] for m in metrics])
        metrics = self._filter_metrics(metrics, cards, product, brand, category)

        top_rows = []
        for m in sorted(metrics, key=lambda r: -r["stock"])[:top]:
            s = split.get(m["nm_id"], {"fbo": 0.0, "fbs": 0.0, "other": 0.0})
            card = cards.get(m["nm_id"], {})
            status = "normal"
            if m["stock"] <= 0 and m["speed"] > 0:
                status = "out_of_stock"
            elif m["stock"] > 0 and m["speed"] > 0 and m["days_left"] is not None and m["days_left"] <= threshold:
                status = "critical"
            elif m["stock"] > 0 and (m["speed"] <= 0 or m["days_left"] is None or m["days_left"] > excess_days):
                status = "no_sales" if m["speed"] <= 0 else "excess"
            top_rows.append({
                **m,
                "fbo_qty": s["fbo"],
                "fbs_qty": s["fbs"],
                "title": card.get("title") or "",
                "brand": card.get("brand") or "",
                "vendor_code": card.get("vendor_code") or "",
                "photos": card.get("photos"),
                "status": status,
            })

        return {
            "empty": False,
            "data_date": data_date,
            "snapshot_date": snap,
            "period": {"from": from_eff, "to": to_eff, "days": days},
            "warehouses": warehouses,
            "warehouses_total": {
                "qty": total_qty,
                "money": total_money,
                "nm_cnt": total_nm,
                "count": len([w for w in warehouses if not w["is_other"]]),
            },
            "top": {"rows": top_rows, "total": len(metrics), "limit": top},
        }

    @staticmethod
    def _office_kind(name: str) -> str:
        if name == OFFICE_FBO:
            return "fbo"
        if name.startswith(OFFICE_FBS_PREFIX):
            return "fbs"
        return "other"
