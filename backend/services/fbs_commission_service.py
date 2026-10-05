"""«FBS Комиссия» (/fbs-commission): скорость сборки в деньгах.

Анализ §10: шкала = JSON-сетка (скидки −5/−3,5 п.п., штрафы по тирам).
Время сдачи = scanDt поставки (точно); нет скана — fallback first
confirm/complete (оценка, в деньги НЕ идёт — как у 10X).
«Можно забрать ещё» v1: все измеренные со сканом как при ≤13 ч (−5 п.п.)
минус фактически заработанная скидка (TODO-confirm формулу, §10.4 п.2).
p90 считаем в Python. Только FBS.
"""
from statistics import mean, quantiles

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LO, MAXH = [0, 13, 42, 48, 54, 60], 10**9


def _bucket(h: float) -> int:
    bounds = LO + [MAXH]
    for i in range(len(LO)):
        if bounds[i] <= h < bounds[i + 1]:
            return i
    return len(LO) - 1


def _discount_pp(h: float) -> float:
    if h < 13:
        return 5.0
    if h < 42:
        return 3.5
    return 0.0


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
                o.price_with_disc AS price,
                TIMESTAMPDIFF(MINUTE,
                    CASE WHEN f.wb_created_at > '1000-01-01 00:00:00'
                         THEN f.wb_created_at END,
                    fh.first_handover_at) / 60.0 AS h_scan,
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
            h_scan = float(r["h_scan"]) if r["h_scan"] is not None else None
            h_est = float(r["h_est"]) if r["h_est"] is not None else None
            price = float(r["price"] or 0)
            item = {"wid": r["wid"], "wname": r["wname"], "price": price,
                    "h_scan": h_scan if self._valid(h_scan) else None,
                    "h_est": h_est if self._valid(h_est) else None}
            est_all.append(item)
            if item["h_scan"] is not None:
                scan.append(item)
        earned = sum(_discount_pp(x["h_scan"]) / 100 * x["price"] for x in scan)
        lost = 0.0
        for x in scan:
            h = x["h_scan"]
            if h >= 60:
                rate = 0.45
            elif h >= 54:
                rate = 0.35
            elif h >= 48:
                rate = 0.30
            else:
                continue
            lost += rate / 100 * max(0.0, h - 48) * x["price"]
        potential = (sum(5.0 / 100 * x["price"] for x in scan) - earned)
        fast = sum(1 for x in scan if x["h_scan"] <= 13)
        # Карточки — по ВСЕМ заданиям склада (как у 10X), деньги/скан — только
        # по измеренным со сканом; оценка — по всем с меткой сдачи.
        wh_all: dict = {}
        for x in est_all:
            wh_all.setdefault((x["wid"], x["wname"]), []).append(x)
        wh: dict = {}
        for x in scan:
            wh.setdefault((x["wid"], x["wname"]), []).append(x)
        wh_est: dict = {}
        for x in est_all:
            if x["h_est"] is not None:
                wh_est.setdefault((x["wid"], x["wname"]), []).append(x["h_est"])
        cards = []
        for (wid, wname) in wh_all.keys() | wh.keys():
            items = wh.get((wid, wname), [])
            hs = sorted(x["h_scan"] for x in items)
            n = len(hs)
            # Зоны — по единому правилу (скан → fallback оценка) + серая «без сдачи»,
            # чтобы сходилось с «Заданий» и динамикой «FBS Заказы». Деньги — только скан.
            eff_all = wh_all.get((wid, wname), [])
            eff_hs = [(x["h_scan"] if x["h_scan"] is not None else x["h_est"])
                      for x in eff_all]
            eff_hs = [h for h in eff_hs if h is not None and h >= 0]
            total_w = len(eff_all)
            zones = [0] * 7
            for h in eff_hs:
                zones[_bucket(h)] += 1
            zones[6] = total_w - len(eff_hs)
            e = sum(_discount_pp(x["h_scan"]) / 100 * x["price"] for x in items)
            est_hs = wh_est.get((wid, wname), [])
            cards.append({
                "warehouse_id": wid, "warehouse_name": wname,
                "tasks_cnt": len(wh_all.get((wid, wname), [])),
                "scan_avg_h": round(mean(hs), 1) if hs else None,
                "scan_measured": n,
                "est_avg_h": round(mean(est_hs), 1) if est_hs else None,
                "est_measured": len(est_hs),
                "p90_h": (round(quantiles(hs, n=10)[-1], 1) if n >= 10
                          else round(hs[-1], 1)) if hs else None,
                "zones": [round(z / total_w * 100, 1) if total_w else 0
                          for z in zones],
                "earned": round(e, 2),
                "lost": 0.0,
                "potential": 0.0,
            })
        for c in cards:
            items = wh.get((c["warehouse_id"], c["warehouse_name"]), [])
            l = 0.0
            for x in items:
                h = x["h_scan"]
                if h >= 60:
                    rate = 0.45
                elif h >= 54:
                    rate = 0.35
                elif h >= 48:
                    rate = 0.30
                else:
                    continue
                l += rate / 100 * max(0.0, h - 48) * x["price"]
            c["lost"] = round(l, 2)
            c["potential"] = round(
                sum(5.0 / 100 * x["price"] for x in items)
                - sum(_discount_pp(x["h_scan"]) / 100 * x["price"] for x in items), 2)
        cards.sort(key=lambda c: -c["earned"])
        return {
            "earned": round(earned, 2),
            "lost": round(lost, 2),
            "net": round(earned - lost, 2),
            "potential": round(potential, 2),
            "fast_cnt": fast,
            "measured_cnt": len(scan),
            "tasks_cnt": tasks_cnt,
            "warehouses": cards,
        }
