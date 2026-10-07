"""«FBS Комиссия» (/fbs-commission): скорость сборки в деньгах.

Анализ §10 + v4: шкала = JSON-сетка (assembly_grid — единый источник
границ/ставок). Время сдачи ТОЛЬКО по статусам (first confirm/complete);
scanDt не учитываем (может отсутствовать). Деньги ≈ по измеренным.
«Можно забрать ещё» v1: все измеренные как при ≤13 ч (−5 п.п.) минус факт
(TODO-confirm формулу, §10.4 п.2). p90 считаем в Python. Только FBS.
"""
from statistics import mean, quantiles

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.assembly_grid import (
    bucket_index,
    discount_pp,
    labels as grid_labels,
    penalty_pct,
)


class FbsCommissionService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _params(self, date_from: str, date_to: str, nm_id: int | None,
                brand: str | None, category: str | None) -> dict:
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if self.company_id is not None:
            params["company_id"] = self.company_id
        if nm_id:
            params["nm_id"] = nm_id
        if brand:
            params["brand"] = brand
        if category:
            params["category"] = category
        return params

    def _extra(self, nm_id: int | None, brand: str | None,
               category: str | None) -> str:
        w = " AND o.warehouse_type = 'Склад продавца'"
        if self.company_id is not None:
            w += " AND o.company_id = :company_id"
        if nm_id:
            w += " AND o.nm_id = :nm_id"
        if brand:
            w += " AND o.brand = :brand"
        if category:
            w += " AND o.category = :category"
        return w

    async def summary(self, date_from: str, date_to: str,
                      nm_id: int | None = None, brand: str | None = None,
                      category: str | None = None) -> dict:
        params = self._params(date_from, date_to, nm_id, brand, category)
        comp = "WHERE company_id = :company_id" if self.company_id is not None else ""
        # v4: время сдачи ТОЛЬКО по статусам (scanDt не учитываем — его может
        # не быть). Деньги ≈ по измеренным со статусом.
        rows = (await self.db.execute(text(f"""SELECT
                f.warehouse_id AS wid, COALESCE(wh.name, '—') AS wname,
                o.price_with_disc AS price, o.date AS odate,
                TIMESTAMPDIFF(MINUTE,
                    CASE WHEN f.wb_created_at > '1000-01-01 00:00:00'
                         THEN f.wb_created_at END,
                    fh.first_handover_at) / 60.0 AS h_est
            FROM wb_orders_fbs f
            JOIN wb_order o ON o.srid = f.rid AND o.company_id = f.company_id
            LEFT JOIN (
                SELECT wb_order_id,
                    MIN(CASE WHEN supplier_status IN ('confirm', 'complete')
                              AND created_at > '1000-01-01 00:00:00'
                        THEN created_at END) AS first_handover_at
                FROM wb_orders_fbs_statuses {comp} GROUP BY wb_order_id
            ) fh ON fh.wb_order_id = f.wb_order_id
            LEFT JOIN wb_fbs_warehouse wh
                ON wh.warehouseId = f.warehouse_id AND wh.company_id = o.company_id
            WHERE o.company_id = {(':company_id') if self.company_id is not None else 'o.company_id'}
              AND o.date BETWEEN :d1 AND :d2{self._extra(nm_id, brand, category)}
              AND f.wb_created_at > '1000-01-01 00:00:00'"""),
            params)).mappings().all()
        # tasks_cnt = все задания периода (включая несданные)
        tasks = (await self.db.execute(text(f"""SELECT COUNT(*) AS cnt
            FROM wb_order o
            WHERE o.company_id = {(':company_id') if self.company_id is not None else 'o.company_id'}
              AND o.date BETWEEN :d1 AND :d2{self._extra(nm_id, brand, category)}"""),
            params)).scalar() or 0
        return self._assemble(rows, int(tasks))

    @staticmethod
    def _valid(h) -> bool:
        return h is not None and h >= 0

    def _assemble(self, rows, tasks_cnt: int) -> dict:
        scan, est_all = [], []
        for r in rows:
            h_est = float(r["h_est"]) if r["h_est"] is not None else None
            price = float(r["price"] or 0)
            item = {"wid": r["wid"], "wname": r["wname"], "price": price,
                    "odate": str(r["odate"])[:10],
                    "h": h_est if self._valid(h_est) else None}
            est_all.append(item)
            if item["h"] is not None:
                scan.append(item)
        earned = sum(discount_pp(x["h"], x["odate"]) / 100 * x["price"]
                       for x in scan)
        lost = sum(penalty_pct(x["h"], x["odate"]) / 100 * x["price"]
                   for x in scan)
        potential = (sum(discount_pp(0.0, x["odate"]) / 100 * x["price"]
                         for x in scan) - earned)
        fast = sum(1 for x in scan if x["h"] <= 13)
        # Карточки — по ВСЕМ заданиям склада; время/деньги — по статусам (v4).
        wh_all: dict = {}
        for x in est_all:
            wh_all.setdefault((x["wid"], x["wname"]), []).append(x)
        cards = []
        for (wid, wname), all_items in sorted(
                wh_all.items(), key=lambda kv: -len(kv[1])):
            items = [x for x in all_items if x["h"] is not None]
            hs = sorted(x["h"] for x in items)
            n = len(hs)
            total_w = len(all_items)
            zones = [0] * 7
            for h in hs:
                zones[bucket_index(h)] += 1
            zones[6] = total_w - n
            e = sum(discount_pp(x["h"], x["odate"]) / 100 * x["price"]
                      for x in items)
            l = sum(penalty_pct(x["h"], x["odate"]) / 100 * x["price"]
                    for x in items)
            cards.append({
                "warehouse_id": wid, "warehouse_name": wname,
                "tasks_cnt": total_w,
                "avg_h": round(mean(hs), 1) if hs else None,
                "measured_cnt": n,
                "p90_h": (round(quantiles(hs, n=10)[-1], 1) if n >= 10
                          else round(hs[-1], 1)) if hs else None,
                "zones": [round(z / total_w * 100, 1) if total_w else 0
                          for z in zones],
                "earned": round(e, 2),
                "lost": round(l, 2),
                "potential": round(
                    sum(discount_pp(0.0, x["odate"]) / 100 * x["price"] for x in items) - e, 2),
            })
        cards.sort(key=lambda c: -c["earned"])
        return {
            "bucket_labels": grid_labels(),
            "earned": round(earned, 2),
            "lost": round(lost, 2),
            "net": round(earned - lost, 2),
            "potential": round(potential, 2),
            "fast_cnt": fast,
            "measured_cnt": len(scan),
            "tasks_cnt": tasks_cnt,
            "warehouses": cards,
        }
