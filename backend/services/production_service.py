"""Производство, ступень 1: план печати + отчет «когда печатать».

Таблица production_plan_item (уже в БД):
  id, nm_id (UNIQUE), production_days, logistics_smolensk_days, logistics_wb_days,
  buffer_days, target_coverage_days, sort_order, created_at, updated_at.
company_id в таблице нет - принадлежность определяется через wbcards.company_id.

Источники данных: wb_stocks (дневные срезы остатков WB), wb_order (заказы).
Смоленск (stock_snapshot/stock_movement) - ступень 2.

Остатки: срез по КОМПАНИИ на последнее доступное число (StocksService):
сначала MAX(date) <= даты, затем SUM(quantity) только этого снимка.
Карточки, которых нет в снимке, = 0.

Агрегация: по одному проходу на источник (не N+1), nm_id передаются списком.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.like_mask import escape_like

DEFAULTS = {
    "production_days": 20,
    "logistics_smolensk_days": 5,
    "logistics_wb_days": 5,
    "buffer_days": 7,
    "target_coverage_days": 90,
}

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_DANGER = "danger"
STATUS_UNKNOWN = "unknown"


class ProductionService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # --- план -----------------------------------------------------------
    async def plan(self) -> list[dict]:
        rows = (await self.db.execute(text("""
            SELECT p.id, p.nm_id, p.production_days, p.logistics_smolensk_days,
                   p.logistics_wb_days, p.buffer_days, p.target_coverage_days,
                   p.sort_order,
                   c.vendorCode, c.title, c.company_id
            FROM production_plan_item p
            LEFT JOIN wbcards c ON c.nmID = p.nm_id
            WHERE (:cid IS NULL OR c.company_id = :cid)
            ORDER BY p.sort_order ASC, p.id ASC"""),
            {"cid": self.company_id})).mappings().all()
        return [dict(r) for r in rows]

    async def save_plan(self, items: list[dict]) -> dict:
        """Полная замена списка плана (как в PHP ProductionPlanController::saveItems)."""
        if self.company_id is None:
            raise ValueError("Не выбрана компания")
        await self.db.execute(text("""
            DELETE p FROM production_plan_item p
            INNER JOIN wbcards c ON c.nmID = p.nm_id
            WHERE c.company_id = :cid"""), {"cid": self.company_id})
        order = 0
        saved = 0
        for it in items or []:
            try:
                nm_id = int(it.get("nm_id"))
            except (TypeError, ValueError):
                continue
            if nm_id <= 0:
                continue
            card = (await self.db.execute(text(
                "SELECT nmID FROM wbcards WHERE nmID = :nm AND company_id = :cid LIMIT 1"),
                {"nm": nm_id, "cid": self.company_id})).first()
            if not card:
                continue  # товар чужой компании - молча пропускаем (как в PHP)
            await self.db.execute(text("""
                INSERT INTO production_plan_item(nm_id, production_days,
                    logistics_smolensk_days, logistics_wb_days, buffer_days,
                    target_coverage_days, sort_order, created_at, updated_at)
                VALUES(:nm, :pd, :ls, :lw, :bf, :tc, :so, :now, :now)"""),
                {"nm": nm_id,
                 "pd": int(it.get("production_days") or DEFAULTS["production_days"]),
                 "ls": int(it.get("logistics_smolensk_days") or DEFAULTS["logistics_smolensk_days"]),
                 "lw": int(it.get("logistics_wb_days") or DEFAULTS["logistics_wb_days"]),
                 "bf": int(it.get("buffer_days") or DEFAULTS["buffer_days"]),
                 "tc": int(it.get("target_coverage_days") or DEFAULTS["target_coverage_days"]),
                 "so": order, "now": int(datetime.now().timestamp())})
            order += 1
            saved += 1
        await self.db.commit()
        return {"ok": True, "saved": saved}

    async def available_cards(self, q: str | None = None, limit: int = 30) -> list[dict]:
        """Карточки компании, которых еще нет в плане."""
        where = " AND c.company_id = :cid"
        params: dict = {"cid": self.company_id, "lim": limit}
        q = (q or "").strip()
        if q:
            where += (" AND (c.vendorCode LIKE :like OR c.title LIKE :like"
                      " OR CAST(c.nmID AS CHAR) LIKE :like)")
            params["like"] = f"%{escape_like(q)}%"
        rows = (await self.db.execute(text(f"""
            SELECT c.nmID, c.vendorCode, c.title
            FROM wbcards c
            WHERE c.company_id = :cid
              AND c.nmID NOT IN (SELECT nm_id FROM production_plan_item){where}
            ORDER BY c.vendorCode ASC
            LIMIT :lim"""), params)).mappings().all()
        return [dict(r) for r in rows]

    # --- Смоленск (ступень 2) --------------------------------------------
    def _sml_svc(self) -> "SmolenskStockService":
        from backend.services.smolensk_stock_service import SmolenskStockService
        return SmolenskStockService(self.db, company_id=self.company_id)

    async def _smolensk_start(self, pd: str, nm_ids: list[int]) -> dict[int, int]:
        """qty_start последнего снапшота <= начала периода (порт ProductionReportService).

        Один проход; таблицы малые; скоп через wbcards.company_id.
        """
        cid = "" if self.company_id is None else " AND c.company_id = :cid"
        params: dict = {"pd": pd, "ids": nm_ids,
                        **({} if self.company_id is None else {"cid": self.company_id})}
        rows = (await self.db.execute(text(f"""
            SELECT s.nm_id, s.qty_start
            FROM stock_snapshot s
            INNER JOIN wbcards c ON c.nmID = s.nm_id{cid}
            INNER JOIN (
                SELECT nm_id, MAX(period_date) AS mx FROM stock_snapshot
                WHERE period_date <= :pd GROUP BY nm_id
            ) t ON t.nm_id = s.nm_id AND t.mx = s.period_date
            WHERE s.period_date <= :pd AND s.nm_id IN :ids""").bindparams(
            bindparam("ids", expanding=True)), params)).mappings().all()
        return {int(r["nm_id"]): int(r["qty_start"] or 0) for r in rows}

    async def _smolensk_movements(self, pd: str, day: str,
                                  nm_ids: list[int]) -> dict[int, dict[str, int]]:
        """Движения Смоленска за период [pd..day] по типам (один проход)."""
        cid = "" if self.company_id is None else " AND c.company_id = :cid"
        params: dict = {"pd": pd, "d": day, "ids": nm_ids,
                        **({} if self.company_id is None else {"cid": self.company_id})}
        rows = (await self.db.execute(text(f"""
            SELECT m.nm_id, m.type, SUM(m.qty) AS q
            FROM stock_movement m
            INNER JOIN wbcards c ON c.nmID = m.nm_id{cid}
            WHERE m.movement_date >= :pd AND m.movement_date <= :d AND m.nm_id IN :ids
            GROUP BY m.nm_id, m.type""").bindparams(bindparam("ids", expanding=True)),
            params)).mappings().all()
        out: dict[int, dict[str, int]] = {}
        for r in rows:
            out.setdefault(int(r["nm_id"]), {})[r["type"]] = int(r["q"] or 0)
        return out

    # --- отчет ----------------------------------------------------------
    async def _slice(self, dt: str, nm_ids: list[int]) -> tuple[dict[str, float], str | None]:
        """Остатки WB на последнем доступном снимке <= dt (срез по компании).

        Схема StocksService (stocks_service.py:31-45): сначала MAX(date),
        затем суммы только по этому снимку (date = :d AND nm_id IN ...).
        Карточки, отсутствующие в снимке, = 0 (синк пишет только nmId,
        пришедшие из отчёта WB - пропавших карточек в свежем снимке нет).
        Возвращает ({nm_id: quantity}, дата среза ISO | None).
        """
        params: dict = {"d": dt}
        cid = "" if self.company_id is None else " AND s.company_id = :cid"
        if self.company_id is not None:
            params["cid"] = self.company_id
        d = (await self.db.execute(text(
            f"SELECT MAX(s.date) FROM wb_stocks s WHERE s.date <= :d{cid}"), params)).scalar()
        if not d:
            return {}, None
        rows = (await self.db.execute(text(f"""
            SELECT s.nm_id, SUM(s.quantity) AS qty
            FROM wb_stocks s
            WHERE s.date = :d{cid} AND s.nm_id IN :ids
            GROUP BY s.nm_id""").bindparams(bindparam("ids", expanding=True)),
            {**params, "ids": [str(n) for n in nm_ids]})).mappings().all()
        stocks = {str(r["nm_id"]): float(r["qty"] or 0) for r in rows}
        return stocks, (d.isoformat() if hasattr(d, "isoformat") else str(d))

    async def report(self, period: str | None = None) -> dict:
        """Отчет «когда печатать»: остатки WB + скорость продаж + статус."""
        plan = await self.plan()
        if not plan:
            return {"rows": [], "period": period or date.today().strftime("%Y-%m"),
                    "wb_start_date": None, "wb_now_date": None, "totals": {}}
        if not period or len(period) != 7:
            period = date.today().strftime("%Y-%m")
        period_date = f"{period}-01"
        nm_ids = [int(p["nm_id"]) for p in plan if p.get("nm_id")]
        if not nm_ids:
            return {"rows": [], "period": period, "wb_start_date": None,
                    "wb_now_date": None, "totals": {}}

        cid_sql = "" if self.company_id is None else " AND company_id = :cid"
        cid = {} if self.company_id is None else {"cid": self.company_id}

        # 1/2) остатки WB: срез на последнее доступное число <= period_date / <= сегодня
        # (срез по КОМПАНИИ, как StocksService в ТОП товаров; карточки, отсутствующие
        # в снимке, = 0: синк пишет только nmId из отчёта WB)
        wb_start, start_dt = await self._slice(period_date, nm_ids)
        wb_now, now_dt = await self._slice(date.today().isoformat(), nm_ids)

        # 2b) Смоленск (ступень 2): снапшот начала периода + движения за период
        # + расчётный баланс на сегодня (порт ProductionReportService / StockBalanceService).
        sml_start = await self._smolensk_start(period_date, nm_ids)
        sml_moves = await self._smolensk_movements(period_date, date.today().isoformat(), nm_ids)
        sml_now = await self._sml_svc()._batch_base_balances(nm_ids, date.today().isoformat())

        # 3) заказы с начала периода (не отмененные)
        since_rows = (await self.db.execute(text(f"""
            SELECT nm_id, COUNT(*) AS cnt
            FROM wb_order
            WHERE nm_id IN :ids AND date >= :pd AND date <= :now
              AND (is_cancel IS NULL OR is_cancel = 0){cid_sql}
            GROUP BY nm_id""").bindparams(bindparam("ids", expanding=True)),
            {"ids": [str(n) for n in nm_ids], "pd": f"{period_date} 00:00:00",
             "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **cid}
        )).mappings().all()
        orders_since = {str(r["nm_id"]): int(r["cnt"] or 0) for r in since_rows}

        # 4) заказы за последние 30 дней - скорость
        d30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        last_rows = (await self.db.execute(text(f"""
            SELECT nm_id, COUNT(*) AS cnt
            FROM wb_order
            WHERE nm_id IN :ids AND date >= :d30 AND date <= :now
              AND (is_cancel IS NULL OR is_cancel = 0){cid_sql}
            GROUP BY nm_id""").bindparams(bindparam("ids", expanding=True)),
            {"ids": [str(n) for n in nm_ids], "d30": d30,
             "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **cid}
        )).mappings().all()
        orders_30 = {str(r["nm_id"]): int(r["cnt"] or 0) for r in last_rows}

        rows = []
        total_recommended = 0.0
        for p in plan:
            nm = int(p["nm_id"])
            key = str(nm)
            stock = wb_now.get(key, 0.0)
            avg_daily = orders_30.get(key, 0) / 30.0
            days_left = (stock / avg_daily) if avg_daily > 0 else None
            cycle = int(p["production_days"] or 0) + int(p["logistics_smolensk_days"] or 0) \
                + int(p["logistics_wb_days"] or 0)
            reorder_point = cycle + int(p["buffer_days"] or 0)
            target = int(p["target_coverage_days"] or 0)
            if days_left is None:
                status = STATUS_UNKNOWN
            elif stock <= 0 or days_left <= reorder_point:
                status = STATUS_DANGER
            elif days_left <= reorder_point * 1.3:
                status = STATUS_WARN
            else:
                status = STATUS_OK
            recommended = max(0.0, avg_daily * target - stock)
            total_recommended += recommended
            eta = None
            if days_left is not None:
                eta = (date.today() + timedelta(days=int(round(days_left)))).isoformat()
            rows.append({
                "nm_id": nm,
                "vendor_code": p.get("vendorCode") or "",
                "title": p.get("title") or "",
                "wb_start": round(wb_start.get(key, 0.0), 2),
                "wb_now": round(stock, 2),
                "smolensk_start": sml_start.get(nm, 0),
                "smolensk_in": sml_moves.get(nm, {}).get("production_in", 0),
                "smolensk_movements": sum(sml_moves.get(nm, {}).values()),
                "smolensk_now": sml_now.get(nm, 0),
                "smolensk_coverage_days": round(
                    sml_now.get(nm, 0) / avg_daily, 1) if avg_daily > 0 else None,
                "orders_since_period": orders_since.get(key, 0),
                "orders_last_30": orders_30.get(key, 0),
                "avg_daily": round(avg_daily, 2),
                "days_left": round(days_left, 1) if days_left is not None else None,
                "eta_date": eta,
                "cycle_days": cycle,
                "reorder_point_days": reorder_point,
                "target_coverage_days": target,
                "recommended_qty": round(recommended, 1),
                "status": status,
                "production_days": int(p["production_days"] or 0),
                "logistics_smolensk_days": int(p["logistics_smolensk_days"] or 0),
                "logistics_wb_days": int(p["logistics_wb_days"] or 0),
                "buffer_days": int(p["buffer_days"] or 0),
            })
        # сортировка: сначала «в печать», потом по дате конца
        order = {STATUS_DANGER: 0, STATUS_WARN: 1, STATUS_OK: 2, STATUS_UNKNOWN: 3}
        rows.sort(key=lambda r: (order.get(r["status"], 3),
                                 r["eta_date"] or "9999-12-31"))
        return {
            "rows": rows,
            "period": period,
            "wb_start_date": start_dt,
            "wb_now_date": now_dt,
            "totals": {"recommended_qty": round(total_recommended, 1),
                       "items": len(rows)},
        }
