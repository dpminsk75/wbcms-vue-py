"""Детализация затрат для попапов «Финансовой аналитики».

Порт Yii2:
- DetailController::actionGetPopupReport (type shf/udr) — строки detail_by_period
  по supplier_oper_name + итог; в PHP без скоупа компании, здесь строгий company_id.
- Хранение/приёмка — в PHP детализации не было (plain text); новые разрезы:
  хранение — wb_paid_storage по дате × складу, приёмка — wb_acceptance_report
  по дате × поставке (incomeId), без разбивки по товарам.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LIMIT = 150


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
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
                        **self._company_params()}
        if kind == "shf":
            filt, sum_field = "d.supplier_oper_name = :oper", "d.penalty"
            params["oper"] = "Штраф"
        elif kind == "udr":
            filt, sum_field = "d.supplier_oper_name = :oper", "d.deduction"
            params["oper"] = "Удержание"
        else:
            filt, sum_field = "d.bonus_type_name LIKE :pat", "d.deduction"
            params["pat"] = "%WB Продвижение%"
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
