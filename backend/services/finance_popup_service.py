"""Детализация затрат для попапов «Финансовой аналитики».

Порт Yii2:
- DetailController::actionGetPopupReport (type shf/udr) — строки detail_by_period
  по supplier_oper_name + итог; в PHP без скоупа компании, здесь строгий company_id.
- Хранение/приёмка — в PHP детализации не было (plain text); новые разрезы:
  хранение — wb_paid_storage по дате × складу, приёмка — wb_acceptance_report
  по дате × поставке (incomeId), без разбивки по товарам.

Тип udr (удержания) разбит на три корзины — по тем же шаблонам, что куб
(aggregate_sync_service.SUMMARY_SQL:104-105):
  adv   — «%WB Продвижение%»          (учтено в колонке «Реклама»)
  otziv — «Списание за отзыв%»       (учтено в колонке «Отзывы»)
  rest  — все прочие                 (это и есть статья «Удержан.» отчёта)
Так сумма в попапе совпадает с ячейкой «Удержан.» (= f_deduction − f_adv − f_otziv).
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LIMIT = 150

# Шаблоны bonus_type_name — как в кубе (если WB переименует причину, правим здесь).
ADV_PATTERN = "%WB Продвижение%"
OTZIV_PATTERN = "Списание за отзыв%"


class FinancePopupService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self, alias: str = "") -> str:
        prefix = f"{alias}." if alias else ""
        return "" if self.company_id is None else f" AND {prefix}company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def get_detail(self, kind: str, date_from: str, date_to: str):
        """Штрафы (shf) / удержания (udr) / реклама (adv) — порт DetailController.

        adv — тот же фильтр, что считает f_adv в aggregate_sync_service.py:55
        (bonus_type_name LIKE '%WB Продвижение%', сумма deduction)."""
        if kind == "udr":
            return await self._get_deduction(date_from, date_to)
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
                        **self._company_params()}
        if kind == "shf":
            filt, sum_field = "d.supplier_oper_name = :oper", "d.penalty"
            params["oper"] = "Штраф"
        else:
            filt, sum_field = "d.bonus_type_name LIKE :pat", "d.deduction"
            params["pat"] = ADV_PATTERN
        base = (f"FROM detail_by_period d LEFT JOIN wbcards c ON c.nmID = d.nm_id"
                f" WHERE d.sale_dt BETWEEN :d1 AND :d2"
                f" AND {filt}{self._company_where('d')}")
        # Итог — без JOIN (wbcards может хранить nmID нескольких компаний и задвоить суммы).
        agg_base = (f"FROM detail_by_period d WHERE d.sale_dt BETWEEN :d1 AND :d2"
                    f" AND {filt}{self._company_where('d')}")
        agg = (await self.db.execute(
            text(f"SELECT COALESCE(SUM({sum_field}),0) as s, COUNT(*) as c {agg_base}"),
            params)).mappings().first()
        rows = (await self.db.execute(
            text(f"""SELECT d.sale_dt as row_date, d.nm_id as nmID, {sum_field} as amount,
                            d.bonus_type_name as reason, c.title as card_title
                     {base}
                     ORDER BY d.sale_dt DESC LIMIT :lim"""),
            {**params, "lim": LIMIT})).mappings().all()
        return {"kind": kind,
                "total_sum": float(agg["s"] or 0),
                "total_count": int(agg["c"] or 0),
                "items": [dict(r) for r in rows], "limit": LIMIT}

    async def _get_deduction(self, date_from: str, date_to: str):
        """Удержания — три корзины по bonus_type_name (как куб, SUMMARY_SQL:104-105).

        rest  — прочие удержания; их сумма = статья «Удержан.» отчёта
                (= f_deduction − f_adv − f_otziv), т.е. «вошло в сумму»;
        adv   — «%WB Продвижение%»  → учтено в колонке «Реклама»;
        otziv — «Списание за отзыв%» → учтено в колонке «Отзывы».

        Фильтр строк — deduction <> 0 (все удержания WB, независимо от операции):
        так набор строк совпадает с тем, что считает куб (f_deduction).
        """
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
                        "adv": ADV_PATTERN, "otziv": OTZIV_PATTERN,
                        **self._company_params()}
        # COALESCE(bonus_type_name,'') — иначе NOT LIKE по NULL даёт NULL и строка
        # выпала бы из «прочих» (в кубе f_deduction такие строки учитывает).
        bn = "COALESCE(d.bonus_type_name, '')"
        is_adv = f"{bn} LIKE :adv"
        is_otziv = f"{bn} LIKE :otziv"
        is_rest = f"{bn} NOT LIKE :adv AND {bn} NOT LIKE :otziv"
        where = ("WHERE d.sale_dt BETWEEN :d1 AND :d2 AND d.deduction <> 0"
                 f"{self._company_where('d')}")
        # Итоги — без JOIN (wbcards может хранить nmID нескольких компаний и задвоить суммы).
        # s_rest считаем ровно как куб: f_deduction − f_adv − f_otziv (не набором строк) —
        # тогда сумма попапа гарантированно совпадает с ячейкой отчёта.
        agg = (await self.db.execute(text(f"""
            SELECT COALESCE(SUM(d.deduction),0) as s_total, COUNT(*) as c_total,
                   COALESCE(SUM(CASE WHEN {is_adv} THEN d.deduction ELSE 0 END),0) as s_adv,
                   COALESCE(SUM(CASE WHEN {is_otziv} THEN d.deduction ELSE 0 END),0) as s_otziv,
                   SUM(CASE WHEN {is_adv} THEN 1 ELSE 0 END) as c_adv,
                   SUM(CASE WHEN {is_otziv} THEN 1 ELSE 0 END) as c_otziv,
                   SUM(CASE WHEN {is_rest} THEN 1 ELSE 0 END) as c_rest
            FROM detail_by_period d {where}"""), params)).mappings().first()
        # Фильтр по корзине — тем же текстом, что и в агрегате.
        async def rows_for(cond: str) -> list:
            q = text(f"""SELECT d.sale_dt as row_date, d.nm_id as nmID, d.deduction as amount,
                              d.bonus_type_name as reason, c.title as card_title
                       FROM detail_by_period d LEFT JOIN wbcards c ON c.nmID = d.nm_id
                       {where} AND {cond}
                       ORDER BY d.sale_dt DESC LIMIT :lim""")
            rs = (await self.db.execute(q, {**params, "lim": LIMIT})).mappings().all()
            return [dict(r) for r in rs]
        rest_rows = await rows_for(is_rest)
        adv_rows = await rows_for(is_adv)
        otziv_rows = await rows_for(is_otziv)
        s_total = float(agg["s_total"] or 0)
        s_adv = float(agg["s_adv"] or 0)
        s_otziv = float(agg["s_otziv"] or 0)
        return {"kind": "udr",
                "total_sum": round(s_total - s_adv - s_otziv, 2),
                "total_count": int(agg["c_rest"] or 0),
                "all_sum": s_total,
                "all_count": int(agg["c_total"] or 0),
                "items": rest_rows,
                "separate": {
                    "adv": {"sum": s_adv,
                            "count": int(agg["c_adv"] or 0),
                            "items": adv_rows},
                    "otziv": {"sum": s_otziv,
                              "count": int(agg["c_otziv"] or 0),
                              "items": otziv_rows},
                },
                "limit": LIMIT}

    async def get_storage(self, date_from: str, date_to: str):
        """Хранение — общей суммой по дате в разрезе складов (LIMIT 150)."""
        base = (f"FROM wb_paid_storage WHERE date BETWEEN :d1 AND :d2"
                f"{self._company_where()}")
        params = {"d1": date_from, "d2": date_to, **self._company_params()}
        total = (await self.db.execute(
            text(f"SELECT COALESCE(SUM(warehousePrice),0) as s {base}"),
            params)).scalar()
        rows = (await self.db.execute(
            text(f"""SELECT date, warehouse, SUM(warehousePrice) as total_price,
                            SUM(barcodesCount) as total_units
                     {base} GROUP BY date, warehouse
                     ORDER BY date DESC, total_price DESC LIMIT :lim"""),
            {**params, "lim": LIMIT})).mappings().all()
        return {"total_sum": float(total or 0),
                "items": [dict(r) for r in rows], "limit": LIMIT}

    async def get_acceptance(self, date_from: str, date_to: str):
        """Приёмка — агрегация по дате (тот же источник, что месячная ячейка
        через agg_daily_summary). Без разбивки по карточкам."""
        agg_base = (f"FROM detail_by_period d WHERE d.sale_dt BETWEEN :d1 AND :d2"
                    f" AND d.acceptance <> 0{self._company_where('d')}")
        params = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
                  **self._company_params()}
        agg = (await self.db.execute(
            text(f"SELECT COALESCE(SUM(d.acceptance),0) as s, COUNT(*) as c {agg_base}"),
            params)).mappings().first()
        rows = (await self.db.execute(
            text(f"""SELECT DATE(d.sale_dt) as date, SUM(d.acceptance) as total,
                            COUNT(*) as cnt
                     {agg_base} GROUP BY DATE(d.sale_dt)
                     ORDER BY date DESC LIMIT :lim"""),
            {**params, "lim": LIMIT})).mappings().all()
        return {"total_sum": float(agg["s"] or 0),
                "total_count": int(agg["c"] or 0),
                "items": [dict(r) for r in rows], "limit": LIMIT}
