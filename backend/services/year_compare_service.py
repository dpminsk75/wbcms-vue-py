"""«Сравнение по годам» — порт Yii2 AggOrdersReportController / AggSalesReportController.

ОДНО окно с двумя закладками:
  * tab=orders — «Заказы»: куб agg_orders_daily_sku, ось даты order_date (дата заказа),
    плюс разбивка по site_country (страна заказа) — измерения нет ни в одном другом кубе;
  * tab=sales  — «Продажи»: куб agg_sales_daily_sku, ось даты sale_date, плюс возвраты
    и «к перечислению» (ppvz_for_pay_sum).

Оба куба строятся из detail_by_period (один источник данных) и наполняются воркером
aggregate_sync (backend/workers/aggregate_sync.py) — см. aggregate_sync_service.py:19,45.

ЧТО ИСПРАВЛЕНО ПРИ ПЕРЕНОСЕ (Yii2 → py):
  * + фильтр по company_id: в Yii2 запросы шли сырым SQL по всем компаниям
    (CompanyScopedTrait на raw SQL не действует) — здесь company_id обязателен;
  * годы больше не зашиты в SQL ('IN (2024,2025,2026)') — берём из данных;
  * YEAR()/MONTH()/DAY() по дате больше не используются в WHERE — только диапазоны
    BETWEEN, иначе теряется префикс PK (company_id, <дата>, …);
  * ТОП-20 больше не через 6 подзапросов UNION — по одному запросу на (месяц, год);
  * деление на ноль в средней цене — через NULLIF;
  * добавлен фильтр по карточке (nm_id) — он влияет на все таблицы и графики;
  * в сводках добавлена колонка «К перечислению» для продаж и возвраты.

СЕМАНТИКА ДЕНЕГ И ВОЗВРАТОВ (2026-11-02 / 2026-11-03):
  * СУММЫ — оборот по цене со скидкой продавца, ДО СПП (retail_price_withdisc_rub):
    это база, по которой WB считает комиссию, т.е. «наш оборот». Раньше отчёт
    брал retail_amount (цена продажи ПОСЛЕ СПП) — из-за этого расходился с
    «Финансовой аналитикой» (agg_daily_summary.amount) на ~34%
    (окт. 2026: 1 487 934,44 против 2 245 122 — разница ≈ СПП 33,7%).
  * В кубе продаж добавлены sales_withdisc_sum (оборот по продажам, без
    возвратов) и returns_withdisc_sum (возвраты в той же базе); в кубе заказов
    уже была retail_with_disc_sum (structure.sql:81).
  * Отчёт отдаёт NET: qty = sales_qty - returns_qty (штуки),
    amount = sales_withdisc_sum - returns_withdisc_sum (см. _net_amount),
    возвраты видны отдельной колонкой (returns_qty / returns_amount).
  * КОЛИЧЕСТВО в отчёте — ШТУКИ (SUM(quantity) по doc_type_name='Продажа'),
    а в «Финансовой аналитике» — ПОЗИЦИИ (COUNT строк по supplier_oper_name).
    Разница = строки с quantity != 1 (окт. 2026: 5 511 против 5 510).
  * В кубе заказов возвратов нет (doc_type_name='Продажа') — там всё как было.

БЮДЖЕТ: кубы за 3 года — 111k (orders) / 191k (sales) строк на компанию,
15 запросов на страницу, суммарно < 250k просмотренных строк — в бюджете
AGENTS.md (500k строк / 60 с) с запасом.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

# Потолок выбора: столько лет набирает палитра серий V2 (theme.md 5.9).
MAX_YEARS = 3

TABLES = {
    "orders": {
        "table": "agg_orders_daily_sku",
        "date": "order_date",
        "qty": "orders_qty",
        # Оборот: цена со скидкой продавца (ДО СПП) — колонка уже есть в кубе
        # заказов (structure.sql:81, заполняется aggregate_sync_service.py:59).
        "amount": "retail_with_disc_sum",
        # В кубе заказов возвратов нет (doc_type_name='Продажа') — заказ был,
        # даже если его потом вернули.
        "returns_qty": None,
        "returns_amount": None,
        # PHP усреднял среднюю цену по странам внутри группы (nmID, title, m, y) —
        # воспроизводим site_country в группировке внутреннего запроса.
        "group_extra": ", site_country",
    },
    "sales": {
        "table": "agg_sales_daily_sku",
        "date": "sale_date",
        "qty": "sales_qty",
        # Оборот по продажам (до СПП), без возвратов; возвраты — отдельно.
        "amount": "sales_withdisc_sum",
        "returns_qty": "returns_qty",
        "returns_amount": "returns_withdisc_sum",
        "group_extra": "",
    },
}

TOP_LIMIT = 20


def _net_amount(amount: float, returns: float) -> float:
    """Net-сумма: оборот (продажи) минус возвраты.

    В кубе продаж sales_withdisc_sum — оборот по продажам (цена со скидкой
    продавца, ДО СПП) БЕЗ возвратов, а returns_withdisc_sum — возвраты в той
    же базе. Поэтому net = оборот − возвраты (одно вычитание).

    Проверено на nmID 526443466, окт. 2026:
        2 245 122,00 − 4 484,05 = 2 240 637,95 → /wb-sales-analysis «Выручка».
    """
    return round(float(amount or 0) - float(returns or 0), 2)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


class YearCompareService:
    """Сравнение заказов/продаж по годам на кубах агрегатов."""

    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # ------------------------------------------------------------------ утилиты

    def _cid(self) -> str:
        return "" if self.company_id is None else " AND company_id = :cid"

    def _params(self) -> dict:
        return {} if self.company_id is None else {"cid": self.company_id}

    @staticmethod
    def _change(cur: float, prev: float) -> float | None:
        """Δ% к предыдущему выбранному году. None — если базы нет."""
        if not prev:
            return None
        return round((cur - prev) / abs(prev) * 100, 1)

    # ------------------------------------------------------------------ годы

    async def available_years(self) -> list[int]:
        """Годы, за которые есть данные (полные). 2023 отсеется — там 20 дней."""
        sql = text(f"""
            SELECT YEAR(sdate) AS y, COUNT(DISTINCT sdate) AS days
            FROM agg_daily_summary
            WHERE 1=1{self._cid()}
            GROUP BY YEAR(sdate)
            ORDER BY y
        """)
        rows = (await self.db.execute(sql, self._params())).mappings().all()
        years = [int(r["y"]) for r in rows if int(r["days"] or 0) >= 180]
        return years[-MAX_YEARS:] if years else []

    # ------------------------------------------------------------------ основной метод

    async def compare(self, tab: str = "orders", years: list[int] | None = None,
                      nm_id: int | None = None) -> dict:
        cfg = TABLES.get(tab) or TABLES["orders"]
        tab = tab if tab in TABLES else "orders"
        tbl, dcol, qcol, acol = cfg["table"], cfg["date"], cfg["qty"], cfg["amount"]
        r_qty_col, r_amt_col = cfg["returns_qty"], cfg["returns_amount"]
        # Возвраты есть только в кубе продаж; в кубе заказов их нет.
        has_returns = bool(r_qty_col and r_amt_col)
        extra_sel = (f", SUM({r_qty_col}) AS r_qty, SUM({r_amt_col}) AS r_amount"
                     if has_returns else ", 0 AS r_qty, 0 AS r_amount")

        available = await self.available_years()
        if not available:
            return {"tab": tab, "available_years": [], "years": [],
                    "meta": {}, "summary_prev": [], "summary_curr": [],
                    "summary_year": [],
                    "months": [], "top_prev": [], "top_curr": []}

        sel = [int(y) for y in (years or []) if int(y) in available]
        if not sel:
            sel = list(available)
        sel = sorted(set(sel))[-MAX_YEARS:]

        # --- календарные границы (как в PHP: за вчерашнее число)
        yesterday = date.today() - timedelta(days=1)
        day = yesterday.day
        month = yesterday.month
        prev_month_num = month - 1 if month > 1 else 12
        # В январе «прошлый месяц» — декабрь предыдущего года.
        pm_year_shift = -1 if month == 1 else 0

        params = {**self._params()}
        nm_where = ""
        if nm_id:
            nm_where = " AND nmID = :nm"
            params["nm"] = int(nm_id)

        # --- 1. месячная сетка за выбранные годы (график + таблица месяцев)
        d1 = date(sel[0], 1, 1)
        d2 = date(sel[-1], 12, 31)
        grid_sql = text(f"""
            SELECT YEAR({dcol}) AS y, MONTH({dcol}) AS m,
                   SUM({qcol}) AS qty, SUM({acol}) AS amount{extra_sel}
            FROM {tbl}
            WHERE 1=1{self._cid()} AND {dcol} BETWEEN :d1 AND :d2{nm_where} AND nmID > 0
            GROUP BY YEAR({dcol}), MONTH({dcol})
        """)
        grid = (await self.db.execute(
            grid_sql, {**params, "d1": d1.isoformat(), "d2": d2.isoformat()})).mappings().all()
        grid_map = {(int(r["y"]), int(r["m"])): r for r in grid}

        months = []
        for m in range(1, 13):
            row: dict = {"m": m, "name": MONTH_NAMES[m - 1]}
            for y in sel:
                r = grid_map.get((y, m))
                g_qty = int(r["qty"] or 0) if r else 0
                g_amt = float(r["amount"] or 0) if r else 0.0
                r_qty = int(r["r_qty"] or 0) if r else 0
                r_amt = float(r["r_amount"] or 0) if r else 0.0
                # NET: минус возвраты (в кубе оборот — по продажам, без возвратов).
                row[f"qty_{y}"] = g_qty - r_qty
                row[f"amount_{y}"] = _net_amount(g_amt, r_amt)
                row[f"returns_qty_{y}"] = r_qty
                row[f"returns_amount_{y}"] = round(r_amt, 2)
            months.append(row)

        # --- 2. сводки: полный прошлый месяц, текущий месяц (MTD) и год целиком
        summary_prev = await self._summary(
            tbl, dcol, qcol, acol, r_qty_col, r_amt_col, sel, prev_month_num,
            pm_year_shift, nm_where, params)
        summary_curr = await self._summary(
            tbl, dcol, qcol, acol, r_qty_col, r_amt_col, sel, month, 0,
            nm_where, params, mtd=True, day=day)
        summary_year = await self._summary(
            tbl, dcol, qcol, acol, r_qty_col, r_amt_col, sel, month, 0,
            nm_where, params, full_year=True)

        # --- 3. ТОП товаров: по каждому (месяц, год) — свой запрос
        top_prev = await self._top(
            tbl, dcol, qcol, acol, cfg["group_extra"], r_qty_col, r_amt_col, sel,
            prev_month_num, pm_year_shift, nm_where, params)
        top_curr = await self._top(
            tbl, dcol, qcol, acol, cfg["group_extra"], r_qty_col, r_amt_col, sel,
            month, 0, nm_where, params, mtd=True, day=day)

        # --- 4. товары (для карточки в таблице)
        nms = sorted({int(r["nm_id"]) for r in top_prev} | {int(r["nm_id"]) for r in top_curr})
        cards = await self._cards(nms)

        return {
            "tab": tab,
            "available_years": available,
            "years": sel,
            "meta": {
                "prev_month": {
                    "num": prev_month_num,
                    "name": MONTH_NAMES[prev_month_num - 1],
                    "years": [y + pm_year_shift for y in sel],
                },
                "curr_month": {"num": month, "name": MONTH_NAMES[month - 1], "day": day},
                "today": date.today().isoformat(),
                "nm_id": nm_id,
                # Показывать ли колонку «Возвраты» (в кубе заказов возвратов нет).
                "has_returns": has_returns,
                # ИНДИКАЦИЯ ИСТОЧНИКА (2026-11-03): в отчёте должно быть видно,
                # ОТКУДА взяты цифры — какой куб, какая денежная величина, что
                # с возвратами. generated_at — время снимка: если база пересчитана
                # позже, страница покажет старое время и это будет заметно.
                "source": {
                    "table": tbl,
                    "table_title": ("Куб продаж agg_sales_daily_sku" if tab == "sales"
                                    else "Куб заказов agg_orders_daily_sku"),
                    "amount_title": ("Оборот: цена со скидкой продавца, до СПП "
                                    "(retail_price_withdisc_rub)" if tab == "sales" else
                                    "Сумма заказов: цена со скидкой продавца, до СПП "
                                    "(retail_price_withdisc_rub)"),
                    "qty_title": ("Количество: штуки продаж (SUM quantity)" if tab == "sales"
                                  else "Количество: заказанные единицы"),
                    "returns_title": ("Возвраты вычтены из оборота и количества"
                                      if has_returns else "Возвратов в этом кубе нет"),
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            },
            "summary_prev": summary_prev,
            "summary_curr": summary_curr,
            "summary_year": summary_year,
            "months": months,
            "top_prev": [self._merge(r, sel, cards) for r in top_prev],
            "top_curr": [self._merge(r, sel, cards) for r in top_curr],
        }

    # ------------------------------------------------------------------ части

    async def _summary(self, tbl: str, dcol: str, qcol: str, acol: str,
                        r_qty_col: str | None, r_amt_col: str | None,
                        sel: list[int], month: int, year_shift: int,
                        nm_where: str, params: dict,
                        mtd: bool = False, day: int = 0,
                        full_year: bool = False) -> list[dict]:
        """Сводка по годам: количество, сумма и Δ% к предыдущему выбранному году.

        Количество и сумма — NET (минус возвраты). Возвраты отдаются отдельно
        (returns_qty / returns_amount): в кубе оборот посчитан по продажам.
        """
        extra_sel = (f", SUM({r_qty_col}) AS r_qty, SUM({r_amt_col}) AS r_amount"
                     if r_qty_col and r_amt_col else ", 0 AS r_qty, 0 AS r_amount")
        out: list[dict] = []
        prev_amt: float | None = None
        for y in sel:
            yy = y + year_shift
            if full_year:
                d1 = date(yy, 1, 1)
                d2 = date(yy, 12, 31)
            elif mtd:
                d1 = date(yy, month, 1)
                d2 = date(yy, month, min(day, _days_in_month(yy, month)))
            else:
                d1 = date(yy, month, 1)
                d2 = date(yy, month, _days_in_month(yy, month))
            sql = text(f"""
                SELECT SUM({qcol}) AS qty, SUM({acol}) AS amount{extra_sel}
                FROM {tbl}
                WHERE 1=1{self._cid()} AND {dcol} BETWEEN :d1 AND :d2{nm_where} AND nmID > 0
            """)
            r = (await self.db.execute(
                sql, {**params, "d1": d1.isoformat(), "d2": d2.isoformat()})).mappings().first()
            g_qty = int(r["qty"] or 0) if r else 0
            g_amt = float(r["amount"] or 0) if r else 0.0
            r_qty = int(r["r_qty"] or 0) if r else 0
            r_amt = float(r["r_amount"] or 0) if r else 0.0
            qty = g_qty - r_qty
            amount = _net_amount(g_amt, r_amt)
            change = None if prev_amt is None else self._change(amount, prev_amt)
            out.append({"year": y, "qty": qty, "amount": amount,
                        "returns_qty": r_qty, "returns_amount": round(r_amt, 2),
                        "change": change})
            prev_amt = amount
        return out

    async def _top(self, tbl: str, dcol: str, qcol: str, acol: str, group_extra: str,
                   r_qty_col: str | None, r_amt_col: str | None,
                   sel: list[int], month: int, year_shift: int,
                   nm_where: str, params: dict,
                   mtd: bool = False, day: int = 0) -> list[dict]:
        """ТОП товаров: по каждому году — свои значения, объединённые по nmID.

        Средняя цена — как в PHP: среднее по дням от (amount / qty) внутри группы;
        количество и сумма — NET (минус возвраты), возвраты — отдельными полями.
        Для orders группировка дополнительно включает site_country (как в PHP).
        """
        if r_qty_col and r_amt_col:
            rq_expr = f"SUM({r_qty_col})"
            ra_expr = f"SUM({r_amt_col})"
        else:
            rq_expr = "0"
            ra_expr = "0"
        per_year: dict[int, dict[int, dict]] = {}
        for y in sel:
            yy = y + year_shift
            if mtd:
                d1 = date(yy, month, 1)
                d2 = date(yy, month, min(day, _days_in_month(yy, month)))
            else:
                d1 = date(yy, month, 1)
                d2 = date(yy, month, _days_in_month(yy, month))
            sql = text(f"""
                SELECT nmID, SUM(qty) AS qty, SUM(amount) AS amount,
                       SUM(r_qty) AS r_qty, SUM(r_amount) AS r_amount,
                       AVG(avg_price) AS avg_price
                FROM (
                    SELECT nmID, {dcol} AS d,
                           SUM({qcol}) AS qty, SUM({acol}) AS amount,
                           {rq_expr} AS r_qty, {ra_expr} AS r_amount,
                           CASE WHEN SUM({qcol}) - ({rq_expr}) > 0
                                THEN (SUM({acol}) - ({ra_expr})) / (SUM({qcol}) - ({rq_expr}))
                           END AS avg_price
                    FROM {tbl}
                    WHERE 1=1{self._cid()} AND {dcol} BETWEEN :d1 AND :d2{nm_where} AND nmID > 0
                    GROUP BY nmID, {dcol}{group_extra}
                ) x
                GROUP BY nmID
            """)
            rows = (await self.db.execute(
                sql, {**params, "d1": d1.isoformat(), "d2": d2.isoformat()})).mappings().all()
            bucket: dict[int, dict] = {}
            for r in rows:
                g_qty = int(r["qty"] or 0)
                g_amt = float(r["amount"] or 0)
                r_qty = int(r["r_qty"] or 0)
                r_amt = float(r["r_amount"] or 0)
                bucket[int(r["nmID"])] = {
                    "qty": g_qty - r_qty,
                    "amount": _net_amount(g_amt, r_amt),
                    "returns_qty": r_qty,
                    "returns_amount": round(r_amt, 2),
                    "avg_price": round(float(r["avg_price"]), 2) if r["avg_price"] is not None else 0.0,
                }
            per_year[y] = bucket

        # ТОП-20 каждого года → объединение (как в PHP: UNION шести выборок).
        chosen: set[int] = set()
        for y in sel:
            bucket = per_year.get(y, {})
            for nm, v in sorted(bucket.items(), key=lambda kv: kv[1]["amount"], reverse=True)[:TOP_LIMIT]:
                chosen.add(nm)

        out: list[dict] = []
        for nm in chosen:
            row: dict = {"nm_id": nm}
            for y in sel:
                v = per_year.get(y, {}).get(nm, {
                    "qty": 0, "amount": 0.0, "returns_qty": 0,
                    "returns_amount": 0.0, "avg_price": 0.0})
                row[f"qty_{y}"] = v["qty"]
                row[f"amount_{y}"] = v["amount"]
                row[f"returns_qty_{y}"] = v["returns_qty"]
                row[f"returns_amount_{y}"] = v["returns_amount"]
                row[f"avg_price_{y}"] = v["avg_price"]
            # сортировка как в PHP — по сумме последнего (текущего) года, убыванию
            last = sel[-1]
            out.append(row)
        out.sort(key=lambda r: r.get(f"amount_{last}", 0), reverse=True)
        return out

    async def _cards(self, nms: list[int]) -> dict[int, dict]:
        """Название/артикул/бренд/предмет/фото товаров — одним запросом (без N+1)."""
        if not nms:
            return {}
        ph = ",".join(f":n{i}" for i in range(len(nms)))
        params = {f"n{i}": v for i, v in enumerate(nms)}
        sql = text(f"""
            SELECT nmID, title, vendorCode, brand, subjectName AS subject, photos
            FROM wbcards
            WHERE nmID IN ({ph})
        """)
        rows = (await self.db.execute(sql, params)).mappings().all()
        return {int(r["nmID"]): {
            "title": r["title"] or "",
            "vendor_code": r["vendorCode"] or "",
            "brand": r["brand"] or "",
            "subject": r["subject"] or "",
            "photos": r["photos"],
        } for r in rows}

    @staticmethod
    def _merge(row: dict, sel: list[int], cards: dict[int, dict]) -> dict:
        """Дополнить строку ТОП данными карточки."""
        c = cards.get(int(row["nm_id"]), {})
        out = {"nm_id": row["nm_id"]}
        out.update(c)
        for y in sel:
            out[f"qty_{y}"] = row.get(f"qty_{y}", 0)
            out[f"amount_{y}"] = row.get(f"amount_{y}", 0.0)
            out[f"returns_qty_{y}"] = row.get(f"returns_qty_{y}", 0)
            out[f"returns_amount_{y}"] = row.get(f"returns_amount_{y}", 0.0)
            out[f"avg_price_{y}"] = row.get(f"avg_price_{y}", 0.0)
        return out
