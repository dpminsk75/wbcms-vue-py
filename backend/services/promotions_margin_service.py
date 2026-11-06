"""Подбор товаров в акцию WB: маржа на новой цене.

Идея: маржа считается по ТОЙ ЖЕ формуле, что и в отчёте «Маржа» по товарам
(`profit_columns.MARGIN_SELECT`), но выручка подменяется новой (акционной) ценой.
История берётся из куба `agg_daily_summary` за окно N дней и пересчитывается
на единицу проданного товара; всё, что не зависит от цены, остаётся историческим.

Тумблеры:
  include_cashback  — кэшбек лежит внутри net_profit куба, вычитается или нет;
  include_penalties — штрафы лежат внутри net_profit куба, вычитаются или нет;
  include_reviews   — «списания за отзыв» (ff_otziv) вычитаются поверх net_profit;
  include_adv       — реклама (ff_adv) вычитается поверх net_profit;
  платное хранение (ff_storage_fee) вычитается всегда — так же, как в profit_columns.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.like_mask import escape_like

ID_CHUNK = 500


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _i(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


DEFAULT_PARAMS = {
    "days": 30,
    "min_margin_pct": 10.0,
    "min_margin_rub": 0.0,
    "max_drop_pp": None,
    "min_stock_wb": 0,
    # по умолчанию ВЫКЛЮЧЕНЫ: в отчёте «Маржа» отзывы и реклама вычитаются
    # всегда, но здесь считаем «чистую» маржу — статьи включаются по желанию
    "include_reviews": False,
    "include_adv": False,
    "include_cashback": False,
    "include_penalties": False,
    "tax_rate": 0.07,
    # уровень скидки автоакции, % — через API не отдаётся, задаётся вручную
    "auto_discount": 30,
    # окно истории: даты (если заданы) либо последние N дней
    "date_from": None,
    "date_to": None,
    # фильтр по товару: nmID или маска (vendorCode / название / часть nmID)
    "nm_id": None,
    "q": None,
}


def normalize_params(raw: dict | None) -> dict:
    """Привести параметры расчёта к безопасным значениям."""
    p = dict(DEFAULT_PARAMS)
    for k, v in (raw or {}).items():
        if k in p:
            p[k] = v
    p["days"] = max(1, min(int(p["days"] or 30), 365))
    p["min_margin_pct"] = max(-100.0, min(float(p["min_margin_pct"] or 0), 100.0))
    p["min_margin_rub"] = max(0.0, float(p["min_margin_rub"] or 0))
    p["min_stock_wb"] = max(0, int(p["min_stock_wb"] or 0))
    p["auto_discount"] = max(0, min(99, int(p["auto_discount"] or 0)))
    for k in ("date_from", "date_to", "nm_id", "q"):
        v = p.get(k)
        p[k] = str(v).strip() if v not in (None, "") else None
    if p["date_from"] and not p["date_to"]:
        p["date_to"] = None
    p["tax_rate"] = max(0.0, min(float(p["tax_rate"] or 0.07), 0.5))
    if p.get("max_drop_pp") is not None:
        p["max_drop_pp"] = max(0.0, float(p["max_drop_pp"]))
    else:
        p["max_drop_pp"] = None
    for k in ("include_reviews", "include_adv", "include_cashback", "include_penalties"):
        p[k] = bool(p[k])
    return p


# ------------------------------------------------------------------ цены

def resolve_prices(row: dict) -> dict:
    """Разобрать цены строки номенклатуры.

    WB отдаёт: price (розничная цена), discount (текущая скидка продавца, %),
    planPrice (плановая цена в акции), planDiscount (рекомендуемая скидка, %).

    По данным WB (проверено на стенде): planPrice ≈ price × (1 − planDiscount/100)
    с округлением WB (напр. price=347, plan_discount=75 → 86,75, WB отдаёт 89).
    Поэтому **плановую цену берём от WB** — это фактическая цена в акции,
    а расчётную используем как запасной вариант и как признак расхождения
    (больше 10% — значит цену в акции задаёт не скидка продавца).

    price_now — текущая цена со скидкой продавца (та же шкала, что и planPrice).

    Для отчёта WB (source='report') плановые цены считаем по шкале WB и с
    пересчёту не равны — расхождение не показываем, цену акции берём от WB.
    """
    price = _f(row.get("price"))
    discount = _i(row.get("discount")) or 0
    plan_price = _f(row.get("plan_price"))
    plan_discount = _i(row.get("plan_discount")) or 0
    is_report = str(row.get("source") or "") == "report"
    price_now = round(price * (1 - discount / 100.0), 2) if price > 0 else None
    expected = round(price * (1 - plan_discount / 100.0), 2) if price > 0 else None
    mismatch = False
    if plan_price and plan_price > 0:
        price_new = float(plan_price)
        if expected and not is_report:
            mismatch = abs(price_new - expected) / expected > 0.10
    else:
        price_new = expected
    return {
        "price": price or None,
        "discount": discount,
        "price_now": price_now,
        "plan_price": plan_price,
        "plan_discount": plan_discount,
        "price_new": price_new,
        "price_mismatch": mismatch,
    }


# ------------------------------------------------------------------ маржа

def unit_economics(cube: dict) -> dict:
    """Юнит-экономика за окно: на единицу ПРОДАННОГО товара."""
    sold = _f(cube.get("sales_qnt"))
    if sold <= 0:
        return {}
    amount = _f(cube.get("amount"))
    cost = _f(cube.get("cost"))
    nds = _f(cube.get("nds"))
    base = amount - cost
    if base > 0 and nds > 0:
        rate = min(100.0, max(0.0, nds * 100.0 / max(1e-9, base - nds)))
    else:
        rate = 0.0
    return {
        "sold": sold,
        "amount": amount / sold,
        "comm": _f(cube.get("commission")) / sold,
        "acq": _f(cube.get("acq")) / sold,
        "acc": _f(cube.get("acc")) / sold,
        "del": _f(cube.get("del")) / sold,
        "stor": _f(cube.get("stor")) / sold,
        "pen": _f(cube.get("pen")) / sold,
        "ded": _f(cube.get("ded")) / sold,
        "cb": _f(cube.get("cb")) / sold,
        "cost": cost / sold,
        "otziv": _f(cube.get("ff_otziv")) / sold,
        "adv": _f(cube.get("ff_adv")) / sold,
        "ffstor": _f(cube.get("ff_stor")) / sold,
        "nds_factor": rate / (100.0 + rate),
    }


def calc_at_price(u: dict, price: float, p: dict) -> dict:
    """Структура экономики на ЕДИНИЦУ товара при заданной цене продажи.

    Возвращает и итог маржи, и разложение по статьям — чтобы в таблице
    было видно, из чего сложилась маржа (как в отчёте «Маржа»).
    Статьи, вычитаемые из выручки, помечены знаком «−».
    """
    empty = {
        "revenue": None, "commission": None, "acquiring": None, "acceptance": None,
        "delivery": None, "storage": None, "penalty": None, "deduction": None,
        "cashback": None, "nds": None, "cost": None, "reviews": None, "adv": None,
        "storage_paid": None, "net_profit": None, "profit_before_tax": None,
        "tax": None, "margin_rub": None, "margin_pct": None,
    }
    if not u or price <= 0:
        return empty
    amount_u = u["amount"]

    def share(key: str) -> float:
        return price * (u[key] / amount_u) if amount_u > 0 else 0.0

    commission = share("comm")
    acquiring = share("acq")
    cashback = share("cb") if p["include_cashback"] else 0.0
    penalty = u["pen"] if p["include_penalties"] else 0.0
    net_profit = (price - commission - acquiring - u["acc"] - u["del"] - u["stor"]
                  - penalty - u["ded"] - cashback)
    nds = max(0.0, price - u["cost"]) * u["nds_factor"]
    reviews = u["otziv"] if p["include_reviews"] else 0.0
    adv = u["adv"] if p["include_adv"] else 0.0
    storage_paid = u["ffstor"]
    pbt = net_profit - nds - u["cost"] - reviews - adv - storage_paid
    tax = max(0.0, pbt) * p["tax_rate"]
    rub = pbt - tax
    r2 = lambda v: round(v, 2)
    return {
        "revenue": r2(price),
        "commission": r2(commission),
        "acquiring": r2(acquiring),
        "acceptance": r2(u["acc"]),
        "delivery": r2(u["del"]),
        "storage": r2(u["stor"]),
        "penalty": r2(penalty),
        "deduction": r2(u["ded"]),
        "cashback": r2(cashback),
        "nds": r2(nds),
        "cost": r2(u["cost"]),
        "reviews": r2(reviews),
        "adv": r2(adv),
        "storage_paid": r2(storage_paid),
        "net_profit": r2(net_profit),
        "profit_before_tax": r2(pbt),
        "tax": r2(tax),
        "margin_rub": r2(rub),
        "margin_pct": round(rub / price * 100.0, 2) if price > 0 else None,
    }


def min_price_for_margin(u: dict, p: dict) -> float | None:
    """Минимальная цена продажи, при которой маржа ещё держится порога.

    Нужна для автоакций: WB не даёт плановой цены, а продавец может защитить
    товар «минимальной ценой» (только через Excel-шаблон ЛК). Считаем цену,
    при которой маржа в процентах и в рублях на штуку не ниже порогов.
    Маржа в процентах ВОСРАСТИТ с ростом цены: постоянные затраты на единицу
    (приёмка, логистика, хранение, себестоимость) размывают процент, поэтому
    при низкой цене маржа в процентах падает. Значит ищем нижнюю границу —
    наименьшую цену, при которой оба порога (в % и в ₽) выполнены.
    """
    if not u or u["amount"] <= 0:
        return None
    limit_pct = p["min_margin_pct"]
    limit_rub = p["min_margin_rub"]
    if limit_pct <= 0 and limit_rub <= 0:
        return None

    def ok(price: float) -> bool:
        m = calc_at_price(u, price, p)
        pct = m.get("margin_pct")
        rub = m.get("margin_rub")
        if pct is None or rub is None:
            return False
        if pct < limit_pct:
            return False
        if limit_rub > 0 and rub < limit_rub:
            return False
        return True

    lo, hi = 0.01, u["amount"]
    if not ok(hi):
        return None  # порог недостижим ни при какой цене
    for _ in range(48):
        mid = (lo + hi) / 2.0
        if ok(mid):
            hi = mid
        else:
            lo = mid
    # WB принимает минимальную цену только целым числом — округляем вверх.
    return float(int(hi) + (1 if hi > int(hi) else 0))


def margin_at_price(u: dict, price: float, p: dict) -> dict:
    """Итог маржи при заданной цене (совместимость со старым вызовом)."""
    c = calc_at_price(u, price, p)
    return {
        "net_profit": c["net_profit"],
        "profit_before_tax": c["profit_before_tax"],
        "tax": c["tax"],
        "margin_rub": c["margin_rub"],
        "margin_pct": c["margin_pct"],
    }


def verdict(margin_now: dict, margin_new: dict, p: dict,
            stock_wb: float, has_history: bool) -> tuple[bool, str]:
    """Рекомендовать ли товар в акцию + причина отказа.

    Пустая причина = товар проходит пороги (в таблице ничего не пишем).
    """
    if not has_history:
        return False, ""
    if margin_new.get("margin_pct") is None:
        return False, "Нет цены акции — маржа не считается"
    pct = margin_new["margin_pct"]
    rub = margin_new["margin_rub"]
    reasons = []
    if pct < p["min_margin_pct"]:
        reasons.append(f"Маржа {pct:.1f} % ниже порога {p['min_margin_pct']:.1f} %")
    if p["min_margin_rub"] > 0 and rub < p["min_margin_rub"]:
        reasons.append(f"Маржа {rub:.0f} ₽/шт ниже порога {p['min_margin_rub']:.0f} ₽")
    if p["max_drop_pp"] is not None and margin_now.get("margin_pct") is not None:
        drop = margin_now["margin_pct"] - pct
        if drop > p["max_drop_pp"]:
            reasons.append(f"Маржа упала на {drop:.1f} п.п. — больше порога {p['max_drop_pp']:.1f} п.п.")
    if p["min_stock_wb"] > 0 and stock_wb < p["min_stock_wb"]:
        reasons.append(f"Остаток на складах WB {stock_wb:.0f} шт. — меньше минимума {p['min_stock_wb']}")
    if reasons:
        return False, "; ".join(reasons)
    return True, ""


# ------------------------------------------------------------------ сервис

class PromotionsMarginService:
    """Считает маржу товаров на новой цене и собирает готовые строки таблицы."""

    CUBE_SQL = """
        SELECT nm_id,
               SUM(sales_qnt) AS sales_qnt, SUM(return_qnt) AS return_qnt,
               SUM(amount) AS amount, SUM(`return`) AS ret,
               SUM(commission) AS commission, SUM(f_acquiring_fee) AS acq,
               SUM(f_acceptance) AS acc, SUM(f_delivery) AS del,
               SUM(f_storage_fee) AS stor, SUM(f_penalty) AS pen,
               SUM(f_deduction) AS ded, SUM(f_cashback) AS cb,
               SUM(f_otziv) AS otziv, SUM(ff_otziv) AS ff_otziv,
               SUM(f_adv) AS f_adv, SUM(ff_adv) AS ff_adv,
               SUM(ff_storage_fee) AS ff_stor,
               SUM(f_nds) AS nds, SUM(f_cost_price) AS cost,
               SUM(net_profit) AS net_profit
        FROM agg_daily_summary
        WHERE company_id = :cid AND sdate BETWEEN :d1 AND :d2
          AND nm_id IN ({ids})
        GROUP BY nm_id"""

    CARDS_SQL = """
        SELECT nmID, MAX(vendorCode) AS vendorCode, MAX(title) AS title,
               MAX(brand) AS brand, MAX(subjectName) AS subjectName,
               MAX(photos) AS photos
        FROM wbcards
        WHERE nmID IN ({ids}) AND (company_id = :cid OR company_id IS NULL)
        GROUP BY nmID"""

    BARCODES_SQL = """
        SELECT nmID, GROUP_CONCAT(DISTINCT sku SEPARATOR ', ') AS skus
        FROM wbcards_sizes WHERE nmID IN ({ids}) GROUP BY nmID"""

    # снимок остатков WB: агрегат по всей компании за дату (индекс company_id+date),
    # фильтр по nm делаем в Python — колонка nm_id строковая, IN с числами
    # заставил бы MySQL приводить колонку к числу и выключить индекс
    STOCK_SQL = """
        SELECT nm_id, SUM(quantity) AS qty
        FROM wb_stocks WHERE company_id = :cid AND date = :snap
        GROUP BY nm_id"""

    FBS_STOCK_SQL = """
        SELECT nmID, SUM(amount) AS qty FROM wb_fbs_stock
        WHERE company_id = :cid AND nmID IN ({ids}) GROUP BY nmID"""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def _window(self, days: int, date_from: str | None = None,
                      date_to: str | None = None) -> tuple[str, str]:
        """Окно истории.

        Если переданы даты — берём их (это то, что выбрал пользователь в фильтре).
        Иначе — последние N дней от последней даты в кубе (данные обновляются ночью).
        """
        if date_from and date_to:
            return date_from, date_to
        row = (await self.db.execute(text(
            "SELECT MAX(sdate) FROM agg_daily_summary WHERE company_id = :cid"),
            {"cid": self.company_id})).first()
        d2 = row[0] if row and row[0] else None
        if not d2:
            d2 = date.today()
        if isinstance(d2, datetime):
            d2 = d2.date()
        d1 = d2 - timedelta(days=days - 1)
        return d1.isoformat(), d2.isoformat()

    async def _resolve_product_ids(self, nm_id: str | None,
                                    q: str | None) -> list[int] | None:
        """Маска/номер товара -> список nmID через wbcards.

        Как в geo_sales_service: число — подстрока nmID, иначе vendorCode/title.
        None — фильтр не задан (все товары); [] — задан, но ничего не нашлось.
        """
        if nm_id:
            try:
                return [int(nm_id)]
            except (TypeError, ValueError):
                pass
        if not q:
            return None
        mask = escape_like(str(q).strip())
        rows = (await self.db.execute(text(
            "SELECT DISTINCT nmID FROM wbcards"
            " WHERE (CAST(nmID AS CHAR) LIKE :q OR vendorCode LIKE :q OR title LIKE :q)"
            " AND (company_id = :cid OR company_id IS NULL) LIMIT 500"),
            {"q": f"%{mask}%", "cid": self.company_id})).scalars().all()
        return sorted({int(x) for x in rows if x})

    async def _cube(self, nm_ids: list[int], d1: str, d2: str) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for i in range(0, len(nm_ids), ID_CHUNK):
            chunk = nm_ids[i:i + ID_CHUNK]
            ids = ", ".join(f":n{j}" for j in range(len(chunk)))
            params = {"cid": self.company_id, "d1": d1, "d2": d2}
            params.update({f"n{j}": v for j, v in enumerate(chunk)})
            sql = self.CUBE_SQL.format(ids=ids)
            rows = (await self.db.execute(text(sql), params)).mappings().all()
            for r in rows:
                out[int(r["nm_id"])] = dict(r)
        return out

    async def _cards(self, nm_ids: list[int]) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for i in range(0, len(nm_ids), ID_CHUNK):
            chunk = nm_ids[i:i + ID_CHUNK]
            ids = ", ".join(f":n{j}" for j in range(len(chunk)))
            params = {"cid": self.company_id}
            params.update({f"n{j}": v for j, v in enumerate(chunk)})
            rows = (await self.db.execute(text(self.CARDS_SQL.format(ids=ids)),
                                         params)).mappings().all()
            for r in rows:
                out[int(r["nmID"])] = dict(r)
        return out

    async def _barcodes(self, nm_ids: list[int]) -> dict[int, str]:
        out: dict[int, str] = {}
        for i in range(0, len(nm_ids), ID_CHUNK):
            chunk = nm_ids[i:i + ID_CHUNK]
            ids = ", ".join(f":n{j}" for j in range(len(chunk)))
            params = {f"n{j}": v for j, v in enumerate(chunk)}
            rows = (await self.db.execute(text(self.BARCODES_SQL.format(ids=ids)),
                                         params)).mappings().all()
            for r in rows:
                out[int(r["nmID"])] = str(r.get("skus") or "")
        return out

    async def _stocks(self) -> dict[int, float]:
        row = (await self.db.execute(text(
            "SELECT MAX(date) FROM wb_stocks WHERE company_id = :cid"),
            {"cid": self.company_id})).first()
        snap = row[0] if row else None
        if not snap:
            return {}
        rows = (await self.db.execute(text(self.STOCK_SQL),
                                     {"cid": self.company_id, "snap": snap})).mappings().all()
        out = {}
        for r in rows:
            nm = _i(r.get("nm_id"))
            if nm is None:
                continue
            out[nm] = out.get(nm, 0.0) + _f(r.get("qty"))
        return out

    async def _fbs_stock(self, nm_ids: list[int]) -> dict[int, float]:
        if not nm_ids:
            return {}
        out: dict[int, float] = {}
        for i in range(0, len(nm_ids), ID_CHUNK):
            chunk = nm_ids[i:i + ID_CHUNK]
            ids = ", ".join(f":n{j}" for j in range(len(chunk)))
            params = {"cid": self.company_id}
            params.update({f"n{j}": v for j, v in enumerate(chunk)})
            rows = (await self.db.execute(text(self.FBS_STOCK_SQL.format(ids=ids)),
                                         params)).mappings().all()
            for r in rows:
                nm = _i(r.get("nmID"))
                if nm is None:
                    continue
                out[nm] = out.get(nm, 0.0) + _f(r.get("qty"))
        return out

    async def analyze(self, rows: list[dict], params: dict | None = None) -> dict:
        """Обогатить строки номенклатуры и посчитать маржу на новой цене."""
        p = normalize_params(params)
        items = []
        for r in rows or []:
            nm = _i(r.get("nm_id") or r.get("id"))
            if nm is None:
                continue
            items.append((nm, dict(r)))
        # фильтр по товару (маска из WbUniversalFilter)
        wanted = await self._resolve_product_ids(p.get("nm_id"), p.get("q"))
        if wanted is not None:
            keep = set(wanted)
            items = [(nm, src) for nm, src in items if nm in keep]
        nm_ids = [nm for nm, _ in items]
        d1, d2 = await self._window(p["days"], p.get("date_from"), p.get("date_to"))
        cube = await self._cube(nm_ids, d1, d2) if nm_ids else {}
        cards = await self._cards(nm_ids) if nm_ids else {}
        barcodes = await self._barcodes(nm_ids) if nm_ids else {}
        stocks = await self._stocks()
        fbs = await self._fbs_stock(nm_ids) if nm_ids else {}

        out_rows = []
        for nm, src in items:
            prices = resolve_prices(src)
            c = cube.get(nm) or {}
            u = unit_economics(c)
            has_history = bool(u)
            stock_wb = stocks.get(nm, 0.0)
            stock_fbs = fbs.get(nm, 0.0)
            sold = _f(c.get("sales_qnt"))
            card = cards.get(nm) or {}
            # Свои данные приоритетнее, отчёт WB — запасной источник.
            if nm not in stocks and src.get("stock_wb") is not None:
                stock_wb = _f(src.get("stock_wb")) or 0.0
            if nm not in fbs and src.get("stock_fbs") is not None:
                stock_fbs = _f(src.get("stock_fbs")) or 0.0
            speed = sold / p["days"] if p["days"] > 0 else 0.0
            days_left = (stock_wb / speed) if speed > 0 else None
            m_now = calc_at_price(u, prices.get("price_now") or 0.0, p) if has_history else {}
            m_new = calc_at_price(u, prices.get("price_new") or 0.0, p) if has_history else {}
            ok, reason = verdict(m_now, m_new, p, stock_wb, has_history)
            floor_price = min_price_for_margin(u, p) if has_history else None
            # Минимальная цена: если загружен отчёт WB — берём её (цену из карточки),
            # иначе считаем порог по марже.
            wb_min = _f(src.get("min_price"))
            if wb_min is not None and wb_min > 0:
                min_price = float(wb_min)
            else:
                min_price = floor_price
            # Статус и блокировка из отчёта WB — это вердикт WB, он важнее порогов.
            wb_notes = []
            if src.get("blocked"):
                wb_notes.append("WB: стоит блокировка применения скидки")
            wb_status = str(src.get("status") or "").strip()
            if wb_status:
                wb_notes.append(wb_status)
            if wb_notes:
                if wb_status.lower().startswith("не участвует"):
                    ok = False
                reason = "; ".join(wb_notes) + (("; " + reason) if reason else "")
            turnover = round(days_left, 1) if days_left is not None else _f(src.get("turnover_days"))
            barcode = barcodes.get(nm, "") or str(src.get("barcode") or "")
            drop = None
            if m_now.get("margin_pct") is not None and m_new.get("margin_pct") is not None:
                drop = round(m_now["margin_pct"] - m_new["margin_pct"], 2)
            out_rows.append({
                "nm_id": nm,
                "in_action": bool(src.get("in_action")),
                "title": card.get("title") or src.get("title"),
                "vendor_code": card.get("vendorCode") or src.get("vendor_code"),
                "brand": card.get("brand") or src.get("brand"),
                "subject": card.get("subjectName") or src.get("subject"),
                "photos": card.get("photos"),
                "barcodes": barcode,
                "stock_wb": round(stock_wb, 0),
                "stock_fbs": round(stock_fbs, 0),
                "sold_qty": round(sold, 0),
                "speed": round(speed, 3),
                "turnover_days": turnover,
                "price": prices["price"],
                "discount": prices["discount"],
                "price_now": prices["price_now"],
                "plan_price": prices["plan_price"],
                "plan_discount": prices["plan_discount"],
                "price_new": prices["price_new"],
                "price_mismatch": prices["price_mismatch"],
                # минимальная цена для шаблона WB («Мин. цена и блокировки в автоакциях»)
                "min_price": min_price,
                # структура экономики на единицу: при текущей цене и при цене акции
                "unit_now": m_now,
                "unit": m_new,
                "margin_now_pct": m_now.get("margin_pct"),
                "margin_now_rub": m_now.get("margin_rub"),
                "margin_new_pct": m_new.get("margin_pct"),
                "margin_new_rub": m_new.get("margin_rub"),
                "margin_drop_pp": drop,
                "recommend": ok,
                "reason": reason,
            })
        return {
            "rows": out_rows,
            "params": p,
            "window": {"date_from": d1, "date_to": d2, "days": p["days"]},
            "summary": {
                "total": len(out_rows),
                "recommend": sum(1 for r in out_rows if r["recommend"]),
                "reject": sum(1 for r in out_rows if not r["recommend"]),
            },
        }
