"""Расшифровка колонок маржи: вкладка «По дням» (куб) + «Детализация» (исходные таблицы).

Главное правило: сумма в модалке и сумма в ячейке таблицы берутся из ОДНОГО источника,
иначе цифры расходятся. Отсюда два «basis»:

  basis="month"   — «Финансовая аналитика» дашборда: f_* из detail_by_period
                    (f_storage_fee / f_otziv / f_adv — см. aggregate_sync_service.SUMMARY_SQL);
  basis="product" — отчёты по товарам: ff_* из куба agg_daily_summary
                    (ff_storage_fee / ff_otziv / ff_adv — см. profit_columns.MARGIN_SELECT).

Детализация берётся из той же таблицы, из которой куб считает ячейку:
  * ff_adv        → wb_campaign_stats_nms ⋈ wb_campaign_stats (+ wb_campaign — только имена);
  * ff_otziv      → wb_feedbacks (только оплаченные/списанные: is_pay>0 OR f_cost>0);
  * ff_storage_fee→ wb_paid_storage;
  * f_*           → detail_by_period, фильтр построчно повторяет куб
                    (acceptance/delivery_rub/storage_fee/penalty/deduction/cashback_amount <> 0,
                     f_otziv = bonus_type_name LIKE 'Списание за отзыв%',
                     f_adv  = bonus_type_name LIKE '%WB Продвижение%').

ДИСЦИПЛИНА SQL (AGENTS.md):
  * company_id обязателен (global admin — фильтр не ставится, как в остальном коде);
  * всегда период + LIMIT, без SELECT *;
  * GROUP BY — дословно те же выражения, что в SELECT (ONLY_FULL_GROUP_BY);
  * имена колонок — только из whitelist, из пользовательского ввода не подставляются;
  * «Виды логистики» считаются по шаблонам причин (services/wb_ops.py), т.к. WB их переименовывает.

Индексы (structure.sql):
  * agg_daily_summary       PK (company_id, sdate, nm_id) — выборка по товару точечная;
  * detail_by_period        idx-nm_id (nm_id), idx_sale_dt (sale_dt),
                            idx_detail_geo (company_id, supplier_oper_name, sale_dt, nm_id, …);
  * wb_paid_storage         idx_date_company_nm (date, company_id, nmId) — с 2026-10-26;
  * wb_campaign_stats_nms   idx_nms_nm_id (nm_id);
  * wb_feedbacks            idx_company_feedbacks (company_id, nmID), idx_wb_feedbacks_createdDate.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.penalty_service import reason_bucket
from backend.services.wb_ops import REASON_DELIVERY_PLAIN

# Сколько строк детализации отдаём за раз (дальше — «показаны первые N из M»).
MAX_ROWS = 300
# Сколько рекламных кампаний отдаём в селект фильтра.
MAX_CAMPAIGNS = 500
# Максимальное окно дней (страховка от «год за раз»).
MAX_DAYS = 800

TITLES = {
    "acceptance": "Приёмка",
    "delivery": "Логистика",
    "storage": "Хранение",
    "penalty": "Штрафы",
    "deduction": "Удержания",
    "otziv": "Отзывы",
    "adv": "Реклама",
    "cashback": "Кэшбек",
}

# Колонка куба agg_daily_summary для каждой статьи. Из запроса не подставляется —
# только по ключу из этого словаря.
CUBE_COLUMN = {
    "month": {
        "acceptance": "f_acceptance",
        "delivery": "f_delivery",
        "storage": "f_storage_fee",
        "penalty": "f_penalty",
        "deduction": "f_deduction",
        "otziv": "f_otziv",
        "adv": "f_adv",
        "cashback": "f_cashback",
    },
    "product": {
        "acceptance": "f_acceptance",
        "delivery": "f_delivery",
        "storage": "ff_storage_fee",
        "penalty": "f_penalty",
        "deduction": "f_deduction",
        "otziv": "ff_otziv",
        "adv": "ff_adv",
        "cashback": "f_cashback",
    },
}

# Детализация из detail_by_period: поле, фильтр и «разрезы» (GROUP BY).
# Фильтр повторяет куб (aggregate_sync_service.SUMMARY_SQL) — иначе сумма не сойдётся.
DBP_SPEC = {
    "acceptance": {
        "field": "acceptance",
        "filter": "d.acceptance <> 0",
        # «Где именно принято»: операция (Приёмка/Утилизация…), склад приёмки (ppvz_office_name,
        # иначе office_name) и поставка (gi_id).
        "dims": ["DATE(d.sale_dt)",
                 "COALESCE(d.supplier_oper_name, '—')",
                 "COALESCE(NULLIF(d.ppvz_office_name, ''), NULLIF(d.office_name, ''), '—')",
                 "d.gi_id"],
        "sel": ["DATE(d.sale_dt) AS d",
                "COALESCE(d.supplier_oper_name, '—') AS oper",
                "COALESCE(NULLIF(d.ppvz_office_name, ''), NULLIF(d.office_name, ''), '—') AS office",
                "d.gi_id AS gi"],
        "columns": [
            {"k": "d", "label": "Дата", "type": "date"},
            {"k": "oper", "label": "Операция", "type": "text"},
            {"k": "office", "label": "Склад приёмки", "type": "text"},
            {"k": "gi", "label": "Поставка", "type": "text"},
            {"k": "cnt", "label": "Записей", "type": "int"},
            {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
        ],
    },
    "delivery": {
        "field": "delivery_rub",
        "filter": "d.delivery_rub <> 0",
        "dims": ["DATE(d.sale_dt)", "d.office_name", "COALESCE(d.bonus_type_name, '—')"],
        "sel": ["DATE(d.sale_dt) AS d", "d.office_name AS office",
                "COALESCE(d.bonus_type_name, '—') AS reason"],
        # колонки «Штук» нет: WB не заполняет quantity в операциях доставки
        "columns": [
            {"k": "d", "label": "Дата", "type": "date"},
            {"k": "office", "label": "Склад", "type": "text"},
            {"k": "reason", "label": "Причина", "type": "text"},
            {"k": "cnt", "label": "Записей", "type": "int"},
            {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
        ],
    },
    "storage": {
        "field": "storage_fee",
        "filter": "d.storage_fee <> 0",
        "dims": ["DATE(d.sale_dt)", "d.office_name"],
        "sel": ["DATE(d.sale_dt) AS d", "d.office_name AS office"],
        "columns": [
            {"k": "d", "label": "Дата", "type": "date"},
            {"k": "office", "label": "Склад", "type": "text"},
            {"k": "cnt", "label": "Записей", "type": "int"},
            {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
        ],
    },
    "penalty": {
        "field": "penalty",
        "filter": "d.penalty <> 0",
        "dims": ["DATE(d.sale_dt)", "COALESCE(d.bonus_type_name, '—')"],
        "sel": ["DATE(d.sale_dt) AS d", "COALESCE(d.bonus_type_name, '—') AS reason"],
        "columns": [
            {"k": "d", "label": "Дата", "type": "date"},
            {"k": "reason", "label": "Причина", "type": "text"},
            {"k": "cnt", "label": "Записей", "type": "int"},
            {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
        ],
    },
    "deduction": {
        "field": "deduction",
        "filter": "d.deduction <> 0",
        "dims": ["DATE(d.sale_dt)", "COALESCE(d.bonus_type_name, '—')"],
        "sel": ["DATE(d.sale_dt) AS d", "COALESCE(d.bonus_type_name, '—') AS reason"],
        "columns": [
            {"k": "d", "label": "Дата", "type": "date"},
            {"k": "reason", "label": "Причина", "type": "text"},
            {"k": "cnt", "label": "Записей", "type": "int"},
            {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
        ],
    },
    "otziv": {
        "field": "deduction",
        "filter": "d.deduction <> 0 AND d.bonus_type_name LIKE 'Списание за отзыв%'",
        "dims": ["DATE(d.sale_dt)", "COALESCE(d.bonus_type_name, '—')"],
        "sel": ["DATE(d.sale_dt) AS d", "COALESCE(d.bonus_type_name, '—') AS reason"],
        "columns": [
            {"k": "d", "label": "Дата", "type": "date"},
            {"k": "reason", "label": "Причина", "type": "text"},
            {"k": "cnt", "label": "Записей", "type": "int"},
            {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
        ],
    },
    "adv": {
        "field": "deduction",
        "filter": "d.deduction <> 0 AND d.bonus_type_name LIKE '%WB Продвижение%'",
        "dims": ["DATE(d.sale_dt)", "COALESCE(d.bonus_type_name, '—')"],
        "sel": ["DATE(d.sale_dt) AS d", "COALESCE(d.bonus_type_name, '—') AS reason"],
        "columns": [
            {"k": "d", "label": "Дата", "type": "date"},
            {"k": "reason", "label": "Причина", "type": "text"},
            {"k": "cnt", "label": "Записей", "type": "int"},
            {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
        ],
    },
    "cashback": {
        "field": "cashback_amount",
        # только начисления (сумма > 0): начисления WB покупателю и возвраты
        # в детализации кэшбека не нужны
        "filter": "d.cashback_amount > 0",
        "dims": ["DATE(d.sale_dt)", "COALESCE(d.bonus_type_name, '—')"],
        "sel": ["DATE(d.sale_dt) AS d", "COALESCE(d.bonus_type_name, '—') AS reason"],
        "columns": [
            {"k": "d", "label": "Дата", "type": "date"},
            {"k": "reason", "label": "Причина", "type": "text"},
            {"k": "cnt", "label": "Записей", "type": "int"},
            {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
        ],
    },
}


def _dstr(v) -> str:
    """datetime/date → 'YYYY-MM-DD' (None → '')."""
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v)[:10]


class MarginBreakdownService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # --- фильтр компании -------------------------------------------------
    def _cw(self, alias: str = "") -> str:
        prefix = f"{alias}." if alias else ""
        return "" if self.company_id is None else f" AND {prefix}company_id = :company_id"

    def _cp(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    @staticmethod
    def _cube_column(kind: str, basis: str) -> str:
        table = CUBE_COLUMN.get(basis) or CUBE_COLUMN["month"]
        col = table.get(kind)
        if not col:
            raise ValueError(f"unknown kind: {kind}")
        return col

    # --- вкладка «По дням» (куб agg_daily_summary) -----------------------
    async def by_day(self, kind: str, basis: str, date_from: str, date_to: str,
                     nm_id: int | None = None, campaign_id: int | None = None) -> dict:
        # Реклама с выбранной кампанией: куб не делит расход по кампаниям,
        # поэтому дневные суммы считаем из рекламной статистики — это тот же
        # источник, что и детализация, поэтому суммы бьются точно.
        if kind == "adv" and campaign_id and nm_id:
            return await self._adv_days_by_campaign(date_from, date_to, nm_id, campaign_id)
        col = self._cube_column(kind, basis)
        params: dict = {"d1": date_from, "d2": date_to, **self._cp()}
        where = f"WHERE p.sdate BETWEEN :d1 AND :d2{self._cw('p')}"
        if nm_id:
            where += " AND p.nm_id = :nm_id"
            params["nm_id"] = int(nm_id)
        # GROUP BY = то же выражение, что в SELECT (ONLY_FULL_GROUP_BY).
        # HAVING <> 0 — в «По дням» только дни с ненулевой суммой (нули не показываем).
        sql = text(f"""SELECT p.sdate AS d, SUM(p.{col}) AS s
                       FROM agg_daily_summary p
                       {where}
                       GROUP BY p.sdate
                       HAVING SUM(p.{col}) <> 0
                       ORDER BY p.sdate""")
        rows = (await self.db.execute(sql, params)).mappings().all()
        days = [{"date": _dstr(r["d"]), "sum": float(r["s"] or 0)} for r in rows]
        total = round(sum(d["sum"] for d in days), 2)
        return {
            "key": "days",
            "label": "По дням",
            "sum": total,
            "totals": [
                {"k": "amount", "label": "Сумма за период", "type": "money", "value": total},
            ],
            "breakdown": [],
            "campaigns": [],
            "footer": {},
            "truncated": False,
            "columns": [
                {"k": "date", "label": "Дата", "type": "date"},
                {"k": "sum", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
            ],
            "rows": days,
            "shown": len(days),
            "total_rows": len(days),
        }

    # --- «По дням» по выбранной рекламной кампании ------------------------
    async def _adv_days_by_campaign(self, date_from: str, date_to: str,
                                    nm_id: int, campaign_id: int) -> dict:
        """Дневной расход по одной рекламной кампании.

        Источник — таблицы рекламной статистики (как у детализации), без куба:
        куб считает расход по товару целиком и не делит его по кампаниям.
        """
        params: dict = {"d1": date_from, "d2": date_to, "nm_id": int(nm_id),
                        "campaign_id": int(campaign_id), **self._cp()}
        sql = text(f"""SELECT s.date AS d, SUM(n.`sum`) AS s
                       FROM wb_campaign_stats_nms n
                       INNER JOIN wb_campaign_stats s
                         ON n.parent_id = s.id AND n.company_id = s.company_id
                       WHERE s.date BETWEEN :d1 AND :d2
                         AND n.nm_id = :nm_id AND s.campaign_id = :campaign_id{self._cw('n')}
                       GROUP BY s.date
                       HAVING SUM(n.`sum`) <> 0
                       ORDER BY s.date""")
        rows = (await self.db.execute(sql, params)).mappings().all()
        days = [{"date": _dstr(r["d"]), "sum": float(r["s"] or 0)} for r in rows]
        total = round(sum(d["sum"] for d in days), 2)
        return {
            "key": "days",
            "label": "По дням",
            "sum": total,
            "totals": [
                {"k": "amount", "label": "Сумма за период", "type": "money", "value": total},
            ],
            "breakdown": [],
            "campaigns": [],
            "footer": {},
            "truncated": False,
            "columns": [
                {"k": "date", "label": "Дата", "type": "date"},
                {"k": "sum", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
            ],
            "rows": days,
            "shown": len(days),
            "total_rows": len(days),
        }

    # --- вкладка «Детализация» -------------------------------------------
    async def by_detail(self, kind: str, basis: str, date_from: str, date_to: str,
                        nm_id: int | None = None, campaign_id: int | None = None) -> dict:
        if kind == "adv" and basis == "product":
            return await self._detail_adv_campaigns(date_from, date_to, nm_id, campaign_id)
        if kind == "otziv" and basis == "product":
            return await self._detail_feedbacks(date_from, date_to, nm_id)
        if kind == "storage" and basis == "product":
            return await self._detail_storage(date_from, date_to, nm_id)
        return await self._detail_dbp(kind, date_from, date_to, nm_id)

    # --- сборка вкладок модалки ------------------------------------------
    async def build_tabs(self, kind: str, basis: str, date_from: str, date_to: str,
                         nm_id: int | None = None, detail: bool = True,
                         campaign_id: int | None = None) -> list:
        """Вкладки модалки: «По дням» (всегда) + «Детализация» (detail=1).

        Для рекламы с выбранной кампанией «По дням» считается из рекламной
        статистики (не из куба) — иначе дневные суммы были бы по всем
        кампаниям товара и не сошлись бы с отфильтрованной детализацией.
        Хранение, как и остальные статьи, показывается двумя вкладками:
        «По дням» (куб) + «Детализация» (склады/штуки).
        """
        tabs = []
        tabs.append(await self.by_day(kind, basis, date_from, date_to, nm_id, campaign_id))
        if detail:
            tabs.append(await self.by_detail(kind, basis, date_from, date_to, nm_id, campaign_id))
        return tabs

    # --- detail_by_period (5 статей одним кодом) -------------------------
    async def _detail_dbp(self, kind: str, date_from: str, date_to: str,
                          nm_id: int | None = None) -> dict:
        spec = DBP_SPEC[kind]
        field = spec["field"]
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
                        **self._cp()}
        where = (f"WHERE d.sale_dt BETWEEN :d1 AND :d2 AND {spec['filter']}"
                 f"{self._cw('d')}")
        if nm_id:
            where += " AND d.nm_id = :nm_id"
            params["nm_id"] = int(nm_id)

        sel = ", ".join(spec["sel"])
        dims = ", ".join(spec["dims"])
        sql = text(f"""SELECT {sel}, COUNT(*) AS cnt, SUM(d.{field}) AS amount
                       FROM detail_by_period d
                       {where}
                       GROUP BY {dims}
                       ORDER BY DATE(d.sale_dt) DESC, amount DESC
                       LIMIT :lim""")
        rows = (await self.db.execute(sql, {**params, "lim": MAX_ROWS})).mappings().all()
        out_rows = []
        for r in rows:
            d = dict(r)
            d["d"] = _dstr(d.get("d"))
            d["amount"] = float(d.get("amount") or 0)
            d["cnt"] = int(d.get("cnt") or 0)
            out_rows.append(d)

        # Итоги — отдельным проходом без LIMIT (иначе итог считался бы по обрезанным строкам).
        agg = (await self.db.execute(
            text(f"""SELECT COUNT(*) AS cnt, SUM(d.{field}) AS amount
                     FROM detail_by_period d {where}"""),
            params)).mappings().first()
        a = dict(agg or {})
        total = float(a.get("amount") or 0)
        cnt = int(a.get("cnt") or 0)

        # Сколько строк в полной выборке (групп), а не сырых записей.
        groups = (await self.db.execute(
            text(f"""SELECT COUNT(*) AS g FROM (
                        SELECT {dims} FROM detail_by_period d {where}
                        GROUP BY {dims}) t"""),
            params)).scalar()

        totals = [
            {"k": "amount", "label": "Сумма за период", "type": "money", "value": round(total, 2)},
            {"k": "cnt", "label": "Записей", "type": "int", "value": cnt},
        ]
        breakdown = []
        bd_title = ""
        bd_columns: list = []
        if kind == "delivery":
            breakdown = await self._delivery_breakdown(date_from, date_to, nm_id)
            plain = round(sum(b["amount"] for b in breakdown if b["section"] == "Штатная доставка"), 2)
            loss = round(sum(b["amount"] for b in breakdown if b["section"] != "Штатная доставка"), 2)
            totals += [
                {"k": "plain", "label": "Штатная доставка", "type": "money", "value": plain},
                {"k": "loss", "label": "Потери на доставке", "type": "money", "value": loss},
            ]
            bd_title = "Итоги по причинам"
            bd_columns = [
                {"k": "label", "label": "Причина", "type": "text"},
                {"k": "cnt", "label": "Записей", "type": "int", "cls": "text-end"},
                {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
            ]
        return {
            "key": "detail",
            "label": "Детализация",
            "sum": round(total, 2),
            "totals": totals,
            "breakdown": breakdown,
            "breakdown_title": bd_title,
            "breakdown_columns": bd_columns,
            "campaigns": [],
            "footer": {},
            "truncated": len(out_rows) < int(groups or 0),
            "columns": spec["columns"],
            "rows": out_rows,
            "shown": len(out_rows),
            "total_rows": int(groups or 0),
        }

    async def _delivery_breakdown(self, date_from: str, date_to: str,
                                  nm_id: int | None) -> list:
        """Итоги доставки ПО ПРИЧИНАМ (точные названия bonus_type_name) + раздел.

        Раздел (штатная доставка / потери) определяем по шаблонам причин
        (services/wb_ops.py): WB их переименовывает, поэтому показываем исходное
        название причины, а классификация идёт отдельной колонкой.
        """
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
                        **self._cp()}
        where = ("WHERE d.sale_dt BETWEEN :d1 AND :d2 AND d.delivery_rub <> 0"
                 f"{self._cw('d')}")
        if nm_id:
            where += " AND d.nm_id = :nm_id"
            params["nm_id"] = int(nm_id)
        sql = text(f"""SELECT COALESCE(d.bonus_type_name, '—') AS reason,
                              COUNT(*) AS cnt, SUM(d.delivery_rub) AS amount
                       FROM detail_by_period d {where}
                       GROUP BY COALESCE(d.bonus_type_name, '—')
                       ORDER BY amount DESC""")
        rows = (await self.db.execute(sql, params)).mappings().all()
        out = []
        for r in rows:
            reason = str(r["reason"] or "")
            out.append({
                "label": reason,
                "section": "Штатная доставка" if reason == REASON_DELIVERY_PLAIN else "Потери на доставке",
                "bucket": reason_bucket(reason),
                "cnt": int(r["cnt"] or 0),
                "amount": round(float(r["amount"] or 0), 2),
            })
        # Штатная доставка — первой, потери — по убыванию суммы.
        out.sort(key=lambda b: (0 if b["section"] == "Штатная доставка" else 1, -b["amount"]))
        return out

    # --- Реклама: кампании WB --------------------------------------------
    async def _detail_adv_campaigns(self, date_from: str, date_to: str,
                                     nm_id: int | None,
                                     campaign_id: int | None = None) -> dict:
        """Расход по рекламе — из таблиц рекламы WB.

        ВАЖНО: джойна на wb_campaign_item НЕТ — так же считает куб
        (aggregate_sync_service.ADV_SQL), иначе сумма разойдётся с ячейкой.

        campaign_id — фильтр по рекламной кампании (для селекта в шапке модалки):
        применяется и к строкам, и к итогам. Список кампаний всегда считается
        по всему периоду (без фильтра), чтобы селект не «схлопывался».
        """
        if not nm_id:
            return {"key": "detail", "label": "Детализация", "sum": 0.0, "totals": [],
                    "breakdown": [], "campaigns": [], "footer": {}, "truncated": False,
                    "columns": [], "rows": [], "shown": 0, "total_rows": 0}
        params: dict = {"d1": date_from, "d2": date_to, "nm_id": int(nm_id), **self._cp()}

        # 1. Свод по кампаниям за период (без фильтра) — список для селекта.
        #    HAVING: только кампании с реальным расходом (нулевые не показываем).
        camp_sql = text(f"""SELECT s.campaign_id AS campaign_id,
                              SUM(n.views) AS views, SUM(n.clicks) AS clicks,
                              SUM(n.atbs) AS atbs, SUM(n.orders) AS orders,
                              SUM(n.`sum`) AS cost, SUM(n.sum_price) AS sum_price,
                              SUM(n.canceled) AS canceled
                       FROM wb_campaign_stats_nms n
                       INNER JOIN wb_campaign_stats s
                         ON n.parent_id = s.id AND n.company_id = s.company_id
                       WHERE s.date BETWEEN :d1 AND :d2 AND n.nm_id = :nm_id{self._cw('n')}
                       GROUP BY s.campaign_id
                       HAVING SUM(n.`sum`) <> 0
                       ORDER BY cost DESC
                       LIMIT :lim""")
        camps = (await self.db.execute(camp_sql, {**params, "lim": MAX_CAMPAIGNS})).mappings().all()

        # Названия кампаний — отдельным запросом (MAX + GROUP BY: без дублей строк).
        names: dict[int, dict] = {}
        ids = sorted({int(r["campaign_id"]) for r in camps if r["campaign_id"] is not None})
        if ids:
            ph = ",".join(f":c{i}" for i in range(len(ids)))
            nparams = {f"c{i}": cid for i, cid in enumerate(ids)}
            nsql = text(f"""SELECT campaign_id, MAX(name) AS name, MAX(status) AS status
                            FROM wb_campaign
                            WHERE campaign_id IN ({ph}){self._cw()}
                            GROUP BY campaign_id""")
            for r in (await self.db.execute(nsql, {**nparams, **self._cp()})).mappings().all():
                names[int(r["campaign_id"])] = {"name": r["name"], "status": r["status"]}

        campaigns = []
        for r in camps:
            cid = int(r["campaign_id"])
            campaigns.append({
                "campaign_id": cid,
                "name": names.get(cid, {}).get("name") or f"Кампания {cid}",
                "cost": round(float(r["cost"] or 0), 2),
                "views": int(r["views"] or 0),
                "clicks": int(r["clicks"] or 0),
                "atbs": int(r["atbs"] or 0),
                "orders": int(r["orders"] or 0),
                "sum_price": float(r["sum_price"] or 0),
                "canceled": int(r["canceled"] or 0),
            })

        # 2. Итоги по срезу: сумма всех кампаний или только выбранной.
        #    Выбранная кампания берётся из того же списка (без дополнительного запроса):
        #    список кампаний считается по всему периоду и содержит все метрики.
        if campaign_id:
            one = next((c for c in campaigns if c["campaign_id"] == int(campaign_id)), None)
            av = int(one["views"]) if one else 0
            ac = int(one["clicks"]) if one else 0
            ao = int(one["orders"]) if one else 0
            acost = float(one["cost"]) if one else 0.0
            acanceled = int(one["canceled"]) if one else 0
            groups_cnt = 1 if one else 0
        else:
            av = sum(int(r["views"] or 0) for r in camps)
            ac = sum(int(r["clicks"] or 0) for r in camps)
            ao = sum(int(r["orders"] or 0) for r in camps)
            acost = sum(float(r["cost"] or 0) for r in camps)
            acanceled = sum(int(r["canceled"] or 0) for r in camps)
            groups_cnt = len(camps)

        # 3. Строки детализации (по дате × кампании), с фильтром по кампании.
        #    HAVING: строки без расхода (Расход = 0) не показываем.
        filt = "" if not campaign_id else " AND s.campaign_id = :campaign_id"
        sql = text(f"""SELECT s.date AS d, s.campaign_id AS campaign_id,
                              SUM(n.views) AS views, SUM(n.clicks) AS clicks,
                              SUM(n.atbs) AS atbs, SUM(n.orders) AS orders,
                              SUM(n.shks) AS shks, SUM(n.`sum`) AS cost,
                              SUM(n.sum_price) AS sum_price, SUM(n.canceled) AS canceled
                       FROM wb_campaign_stats_nms n
                       INNER JOIN wb_campaign_stats s
                         ON n.parent_id = s.id AND n.company_id = s.company_id
                       WHERE s.date BETWEEN :d1 AND :d2 AND n.nm_id = :nm_id{filt}{self._cw('n')}
                       GROUP BY s.date, s.campaign_id
                       HAVING SUM(n.`sum`) <> 0
                       ORDER BY s.date DESC, cost DESC
                       LIMIT :lim""")
        rows = (await self.db.execute(
            sql, {**params, "lim": MAX_ROWS, **({"campaign_id": int(campaign_id)} if campaign_id else {})}
        )).mappings().all()

        out_rows = []
        for r in rows:
            d = dict(r)
            meta = names.get(int(d["campaign_id"]) or 0, {})
            views = int(d.get("views") or 0)
            clicks = int(d.get("clicks") or 0)
            orders = int(d.get("orders") or 0)
            cost = float(d.get("cost") or 0)
            out_rows.append({
                "d": _dstr(d.get("d")),
                "campaign_id": d.get("campaign_id"),
                "campaign": meta.get("name") or "—",
                "status": meta.get("status"),
                "views": views,
                "clicks": clicks,
                "atbs": int(d.get("atbs") or 0),
                "orders": orders,
                "cost": round(cost, 2),
                "sum_price": float(d.get("sum_price") or 0),
                "canceled": int(d.get("canceled") or 0),
                "cpm": round(cost / views * 1000, 2) if views else 0.0,
                "cpc": round(cost / clicks, 2) if clicks else 0.0,
                "cpo": round(cost / orders, 2) if orders else 0.0,
            })

        totals = [
            {"k": "cost", "label": "Расход", "type": "money", "value": round(acost, 2)},
            {"k": "views", "label": "Показы", "type": "int", "value": av},
            {"k": "clicks", "label": "Клики", "type": "int", "value": ac},
            {"k": "orders", "label": "Заказы", "type": "int", "value": ao},
            {"k": "cpm", "label": "CPM", "type": "money", "value": round(acost / av * 1000, 2) if av else 0.0},
            {"k": "cpc", "label": "CPC", "type": "money", "value": round(acost / ac, 2) if ac else 0.0},
            {"k": "cpo", "label": "CPO", "type": "money", "value": round(acost / ao, 2) if ao else 0.0},
            {"k": "ctr", "label": "CTR", "type": "pct", "value": round(ac / av * 100, 2) if av else 0.0},
            {"k": "cr", "label": "CR", "type": "pct", "value": round(ao / ac * 100, 2) if ac else 0.0},
        ]
        # Итоговая строка таблицы (по всему срезу, не по LIMIT-выборке).
        footer = {
            "d": "Итого",
            "campaign": "",
            "views": av,
            "clicks": ac,
            "orders": ao,
            "cost": round(acost, 2),
            "cpm": round(acost / av * 1000, 2) if av else 0.0,
            "cpc": round(acost / ac, 2) if ac else 0.0,
            "cpo": round(acost / ao, 2) if ao else 0.0,
            "canceled": acanceled,
        }
        return {
            "key": "detail",
            "label": "Детализация",
            "sum": round(acost, 2),
            "totals": totals,
            "breakdown": [],
            "campaigns": campaigns,
            "footer": footer,
            "truncated": len(out_rows) >= MAX_ROWS,
            "columns": [
                {"k": "d", "label": "Дата", "type": "date"},
                {"k": "campaign", "label": "Кампания", "type": "campaign"},
                {"k": "views", "label": "Показы", "type": "int", "cls": "text-end"},
                {"k": "clicks", "label": "Клики", "type": "int", "cls": "text-end"},
                {"k": "orders", "label": "Заказы", "type": "int", "cls": "text-end"},
                {"k": "cost", "label": "Расход", "type": "money", "cls": "text-end fw-bold"},
                {"k": "cpm", "label": "CPM", "type": "money", "cls": "text-end"},
                {"k": "cpc", "label": "CPC", "type": "money", "cls": "text-end"},
                {"k": "cpo", "label": "CPO", "type": "money", "cls": "text-end"},
                {"k": "canceled", "label": "Отмены", "type": "int", "cls": "text-end"},
            ],
            "rows": out_rows,
            "shown": len(out_rows),
            "total_rows": groups_cnt,
        }

    # --- Отзывы: wb_feedbacks (только списанные) --------------------------
    async def _detail_feedbacks(self, date_from: str, date_to: str,
                                 nm_id: int | None) -> dict:
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
                        **self._cp()}
        where = ("WHERE f.createdDate BETWEEN :d1 AND :d2"
                 " AND (f.is_pay > 0 OR f.f_cost > 0)"
                 f"{self._cw('f')}")
        if nm_id:
            where += " AND f.nmID = :nm_id"
            params["nm_id"] = int(nm_id)
        sql = text(f"""SELECT DATE(f.createdDate) AS d, f.id AS fb_id,
                              f.productValuation AS rating, f.userName AS user_name,
                              f.f_cost AS cost, f.is_pay AS is_pay, f.f_action AS f_action,
                              f.text AS text, f.pros AS pros, f.cons AS cons
                       FROM wb_feedbacks f
                       {where}
                       ORDER BY f.createdDate DESC
                       LIMIT :lim""")
        rows = (await self.db.execute(sql, {**params, "lim": MAX_ROWS})).mappings().all()
        out_rows = []
        for r in rows:
            d = dict(r)
            out_rows.append({
                "d": _dstr(d.get("d")),
                "fb_id": d.get("fb_id"),
                "rating": d.get("rating"),
                "user_name": d.get("user_name") or "Аноним",
                "cost": float(d.get("cost") or 0),
                "is_pay": int(d.get("is_pay") or 0),
                "f_action": d.get("f_action"),
                "text": d.get("text") or "",
                "pros": d.get("pros") or "",
                "cons": d.get("cons") or "",
            })

        agg = (await self.db.execute(
            text(f"""SELECT COUNT(*) AS cnt, SUM(f.f_cost) AS amount,
                            AVG(f.productValuation) AS avg_rating,
                            SUM(CASE WHEN f.is_pay > 0 THEN 1 ELSE 0 END) AS paid_cnt
                     FROM wb_feedbacks f {where}"""),
            params)).mappings().first()
        a = dict(agg or {})
        cnt = int(a.get("cnt") or 0)
        amount = float(a.get("amount") or 0)
        totals = [
            {"k": "amount", "label": "Списано за отзывы", "type": "money", "value": round(amount, 2)},
            {"k": "cnt", "label": "Отзывов", "type": "int", "value": cnt},
            {"k": "paid_cnt", "label": "Из них платных", "type": "int", "value": int(a.get("paid_cnt") or 0)},
            {"k": "avg_rating", "label": "Средняя оценка", "type": "rating",
             "value": round(float(a.get("avg_rating") or 0), 2)},
        ]
        return {
            "key": "detail",
            "label": "Детализация",
            "sum": round(amount, 2),
            "totals": totals,
            "breakdown": [],
            "campaigns": [],
            "footer": {},
            "truncated": len(out_rows) < cnt,
            "columns": [
                {"k": "d", "label": "Дата", "type": "date"},
                {"k": "rating", "label": "Оценка", "type": "rating"},
                {"k": "user_name", "label": "Пользователь", "type": "text"},
                {"k": "cost", "label": "Стоимость", "type": "money", "cls": "text-end fw-bold"},
                {"k": "f_action", "label": "Акция", "type": "text"},
                {"k": "text", "label": "Отзыв", "type": "text"},
            ],
            "rows": out_rows,
            "shown": len(out_rows),
            "total_rows": cnt,
        }

    # --- Хранение: wb_paid_storage ---------------------------------------
    async def _detail_storage(self, date_from: str, date_to: str,
                               nm_id: int | None) -> dict:
        params: dict = {"d1": date_from, "d2": date_to, **self._cp()}
        where = f"WHERE ps.date BETWEEN :d1 AND :d2{self._cw('ps')}"
        if nm_id:
            where += " AND ps.nmId = :nm_id"
            params["nm_id"] = int(nm_id)
        dims = "ps.date, ps.warehouse, ps.calcType"
        sql = text(f"""SELECT ps.date AS d, ps.warehouse AS warehouse,
                              ps.calcType AS calc_type,
                              SUM(ps.barcodesCount) AS units, SUM(ps.volume) AS volume,
                              SUM(ps.warehousePrice) AS amount
                       FROM wb_paid_storage ps
                       {where}
                       GROUP BY {dims}
                       ORDER BY ps.date DESC, amount DESC
                       LIMIT :lim""")
        rows = (await self.db.execute(sql, {**params, "lim": MAX_ROWS})).mappings().all()
        out_rows = []
        for r in rows:
            d = dict(r)
            out_rows.append({
                "d": _dstr(d.get("d")),
                "warehouse": d.get("warehouse") or "—",
                "calc_type": d.get("calc_type") or "—",
                "units": int(d.get("units") or 0),
                "volume": float(d.get("volume") or 0),
                "amount": float(d.get("amount") or 0),
            })

        agg = (await self.db.execute(
            text(f"""SELECT COUNT(*) AS cnt, SUM(ps.barcodesCount) AS units,
                            SUM(ps.warehousePrice) AS amount
                     FROM wb_paid_storage ps {where}"""),
            params)).mappings().first()
        a = dict(agg or {})
        units = int(a.get("units") or 0)
        amount = float(a.get("amount") or 0)
        groups = (await self.db.execute(
            text(f"""SELECT COUNT(*) AS g FROM (
                        SELECT {dims} FROM wb_paid_storage ps {where}
                        GROUP BY {dims}) t"""),
            params)).scalar()
        totals = [
            {"k": "amount", "label": "Сумма за период", "type": "money", "value": round(amount, 2)},
            {"k": "units", "label": "Штук", "type": "int", "value": units},
            {"k": "per_unit", "label": "За штуку", "type": "money",
             "value": round(amount / units, 2) if units else 0.0},
        ]

        # Свод по складам и типам расчёта (как «Итоги по причинам» в логистике).
        # Один проход агрегации по тому же срезу, без функций над колонками.
        bd_sql = text(f"""SELECT ps.warehouse AS warehouse, ps.calcType AS calc_type,
                                 SUM(ps.barcodesCount) AS units, SUM(ps.volume) AS volume,
                                 SUM(ps.warehousePrice) AS amount
                          FROM wb_paid_storage ps {where}
                          GROUP BY ps.warehouse, ps.calcType
                          ORDER BY amount DESC
                          LIMIT :lim""")
        bd_rows = (await self.db.execute(bd_sql, {**params, "lim": MAX_ROWS})).mappings().all()
        breakdown = []
        for r in bd_rows:
            breakdown.append({
                "label": r.get("warehouse") or "—",
                "calc_type": r.get("calc_type") or "—",
                "units": int(r.get("units") or 0),
                "volume": float(r.get("volume") or 0),
                "amount": round(float(r.get("amount") or 0), 2),
            })

        return {
            "key": "detail",
            "label": "Детализация",
            "sum": round(amount, 2),
            "totals": totals,
            "breakdown": breakdown,
            "breakdown_title": "Итоги по складам",
            "breakdown_columns": [
                {"k": "label", "label": "Склад", "type": "text"},
                {"k": "calc_type", "label": "Тип расчёта", "type": "text", "cls": "text-end"},
                {"k": "units", "label": "Штук", "type": "int", "cls": "text-end"},
                {"k": "volume", "label": "Объём", "type": "num", "cls": "text-end"},
                {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
            ],
            "campaigns": [],
            "footer": {},
            "truncated": len(out_rows) < int(groups or 0),
            "columns": [
                {"k": "d", "label": "Дата", "type": "date"},
                {"k": "warehouse", "label": "Склад", "type": "text"},
                {"k": "calc_type", "label": "Тип расчёта", "type": "text"},
                {"k": "units", "label": "Штук", "type": "int", "cls": "text-end"},
                {"k": "volume", "label": "Объём", "type": "num", "cls": "text-end"},
                {"k": "amount", "label": "Сумма", "type": "money", "cls": "text-end fw-bold"},
            ],
            "rows": out_rows,
            "shown": len(out_rows),
            "total_rows": int(groups or 0),
        }
