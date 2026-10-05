"""«FBS Заказы» (/fbs-orders): экономика + динамика + очередь сборки.

ТЗ: 2026-10-05_fbs-orders-tz.md. Только FBS (warehouse_type='Склад продавца').
Бакеты статусов — из fbs_report_service (BUCKET_CASE, порядок важен).
Пороги очереди и сетка комиссий — backend/config/fbs_assembly_tariffs.json
(значения TODO-confirm, см. ТЗ §8).
"""
import json
import os
from bisect import bisect_right
from datetime import datetime
from statistics import median

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.fbs_report_service import BUCKET_CASE, BUCKETS

_TARIFFS_PATH = os.path.join(os.path.dirname(__file__), "..", "config",
                             "fbs_assembly_tariffs.json")

with open(_TARIFFS_PATH, encoding="utf-8") as _fh:
    TARIFFS = json.load(_fh)


class FbsOrdersService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # --- общий скоуп ---
    def _params(self, date_from: str, date_to: str, warehouse_id: int | None,
                brand: str | None, category: str | None) -> dict:
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if self.company_id is not None:
            params["company_id"] = self.company_id
        if warehouse_id:
            params["wid"] = warehouse_id
        if brand:
            params["brand"] = brand
        if category:
            params["category"] = category
        return params

    def _extra(self, fbs_only: bool, warehouse_id: int | None,
               brand: str | None, category: str | None) -> str:
        w = ""
        if self.company_id is not None:
            w += " AND o.company_id = :company_id"
        if fbs_only:
            w += " AND o.warehouse_type = 'Склад продавца'"
        if warehouse_id:
            w += " AND f.warehouse_id = :wid"
        if brand:
            w += " AND o.brand = :brand"
        if category:
            w += " AND o.category = :category"
        return w

    def _latest_status_join(self) -> str:
        comp = "WHERE company_id = :company_id" if self.company_id is not None else ""
        outer = ("WHERE s1.company_id = :company_id"
                 if self.company_id is not None else "")
        return f"""LEFT JOIN (
            SELECT s1.wb_order_id, s1.supplier_status, s1.wb_status
            FROM wb_orders_fbs_statuses s1
            JOIN (SELECT wb_order_id, MAX(id) AS max_id
                  FROM wb_orders_fbs_statuses {comp} GROUP BY wb_order_id) m
              ON m.wb_order_id = s1.wb_order_id AND m.max_id = s1.id
            {outer}
        ) ls ON ls.wb_order_id = f.wb_order_id"""

    def _from(self) -> str:
        return f"""FROM wb_order o
            LEFT JOIN wb_orders_fbs f ON f.rid = o.srid AND f.company_id = o.company_id
            {self._latest_status_join()}"""

    # --- склады для селектора ---
    async def warehouses(self) -> list:
        comp = "WHERE company_id = :company_id" if self.company_id is not None else ""
        params = {"company_id": self.company_id} if self.company_id is not None else {}
        rows = (await self.db.execute(text(
            f"SELECT warehouseId AS wid, name FROM wb_fbs_warehouse "
            f"{comp} ORDER BY name"), params)).mappings().all()
        return [{"warehouse_id": r["wid"], "name": r["name"]} for r in rows]

    # --- экономика периода ---
    async def economy(self, date_from: str, date_to: str, warehouse_id: int | None,
                      brand: str | None, category: str | None) -> dict:
        bucket_sums = ",\n".join(
            f"SUM(CASE WHEN {BUCKET_CASE} = '{b}' THEN 1 ELSE 0 END) AS {b}"
            for b in BUCKETS)
        params = self._params(date_from, date_to, warehouse_id, brand, category)
        base = (f"o.date BETWEEN :d1 AND :d2"
                f"{self._extra(True, warehouse_id, brand, category)}")
        row = (await self.db.execute(text(f"""SELECT COUNT(*) AS cnt,
                COALESCE(SUM(o.price_with_disc), 0) AS revenue_gross,
                COALESCE(SUM(o.finished_price), 0) AS revenue_net,
                {bucket_sums}
            {self._from()} WHERE {base}"""), params)).mappings().first()
        all_base = (f"o.date BETWEEN :d1 AND :d2"
                    f"{self._extra(False, None, brand, category)}")
        all_row = (await self.db.execute(text(f"""SELECT COUNT(*) AS cnt,
                COALESCE(SUM(o.price_with_disc), 0) AS revenue_gross
            FROM wb_order o WHERE {all_base}"""), params)).mappings().first()
        g = lambda k: int(row[k] or 0)
        sold, declined, buyer, seller = (g("sold"), g("declined"),
                                        g("buyer_cancel"), g("seller_cancel"))
        canceled = declined + buyer + seller
        alive_cnt = g("cnt") - canceled
        alive_sum = 0.0
        if alive_cnt:
            alive_sum = float(row["revenue_gross"] or 0)
            canc = (await self.db.execute(text(f"""SELECT COALESCE(SUM(o.price_with_disc), 0) AS s
                {self._from()} WHERE {base}
                AND ({BUCKET_CASE} IN ('declined', 'buyer_cancel', 'seller_cancel'))"""),
                params)).mappings().first()
            alive_sum = float(row["revenue_gross"] or 0) - float(canc["s"] or 0)
        canceled_sum_row = (await self.db.execute(text(f"""SELECT COALESCE(SUM(o.price_with_disc), 0) AS s
            {self._from()} WHERE {base}
            AND ({BUCKET_CASE} IN ('declined', 'buyer_cancel', 'seller_cancel'))"""),
            params)).mappings().first()
        canceled_sum = float(canceled_sum_row["s"] or 0)
        all_cnt = int(all_row["cnt"] or 0)
        all_sum = float(all_row["revenue_gross"] or 0)
        cnt = g("cnt")
        rev = float(row["revenue_gross"] or 0)
        rev_net = float(row["revenue_net"] or 0)
        return {
            "orders_cnt": cnt,
            "revenue_gross": rev,
            "revenue_net": rev_net,
            "avg_check_gross": round(rev / cnt, 2) if cnt else 0,
            "avg_check_net": round(rev_net / cnt, 2) if cnt else 0,
            "canceled_cnt": canceled,
            "canceled_sum": canceled_sum,
            "alive_cnt": alive_cnt,
            "alive_sum": round(alive_sum, 2),
            "fbs_share_cnt_pct": round(cnt / all_cnt * 100, 1) if all_cnt else 0,
            "fbs_share_money_pct": round(rev / all_sum * 100, 1) if all_sum else 0,
        }

    # --- динамика по дням: заказы + выручка + сдача по интервалам сборки ---
    async def dynamics(self, date_from: str, date_to: str, warehouse_id: int | None,
                       brand: str | None, category: str | None) -> dict:
        params = self._params(date_from, date_to, warehouse_id, brand, category)
        base = (f"o.date BETWEEN :d1 AND :d2"
                f"{self._extra(True, warehouse_id, brand, category)}")
        comp = "WHERE company_id = :company_id" if self.company_id is not None else ""
        # v4: только статусы, scanDt не учитываем (может отсутствовать).
        eff = "fh.first_handover_at"
        h = ("TIMESTAMPDIFF(HOUR, "
             "CASE WHEN f.wb_created_at > '1000-01-01 00:00:00' THEN f.wb_created_at END, "
             f"({eff}))")
        ok = (f"({eff}) > '1000-01-01 00:00:00' "
              "AND f.wb_created_at > '1000-01-01 00:00:00' "
              f"AND ({eff}) > f.wb_created_at")
        lo = [0, 13, 42, 48, 54, 60]
        conds = []
        for i in range(len(lo)):
            if i < len(lo) - 1:
                conds.append(
                    f"SUM(CASE WHEN {ok} AND {h} >= {lo[i]} AND {h} < {lo[i + 1]} "
                    f"THEN 1 ELSE 0 END) AS b{i}")
            else:
                conds.append(
                    f"SUM(CASE WHEN {ok} AND {h} >= {lo[i]} "
                    f"THEN 1 ELSE 0 END) AS b{i}")
        rows = (await self.db.execute(text(f"""SELECT DATE(o.date) AS d,
                COUNT(*) AS cnt, COALESCE(SUM(o.price_with_disc), 0) AS revenue_gross,
                SUM(CASE WHEN NOT ({ok}) THEN 1 ELSE 0 END) AS un_cnt,
                {', '.join(conds)}
            {self._from()}
            LEFT JOIN (
                SELECT wb_order_id,
                    MIN(CASE WHEN supplier_status IN ('confirm', 'complete')
                              AND created_at > '1000-01-01 00:00:00'
                        THEN created_at END) AS first_handover_at
                FROM wb_orders_fbs_statuses {comp} GROUP BY wb_order_id
            ) fh ON fh.wb_order_id = f.wb_order_id
            WHERE {base}
            GROUP BY d ORDER BY d ASC"""), params)).mappings().all()
        return {"days": [{"d": str(r["d"]), "orders_cnt": int(r["cnt"]),
                          "revenue_gross": float(r["revenue_gross"] or 0),
                          "un_cnt": int(r["un_cnt"] or 0),
                          "b0": int(r["b0"] or 0), "b1": int(r["b1"] or 0),
                          "b2": int(r["b2"] or 0), "b3": int(r["b3"] or 0),
                          "b4": int(r["b4"] or 0), "b5": int(r["b5"] or 0)}
                         for r in rows]}

    # --- очередь и скорость сборки ---
    async def assembly(self, date_from: str, date_to: str, warehouse_id: int | None,
                       brand: str | None, category: str | None,
                       now: datetime | None = None) -> dict:
        now = now or datetime.now()
        cfg = TARIFFS
        params = self._params(date_from, date_to, warehouse_id, brand, category)
        base = (f"o.date BETWEEN :d1 AND :d2"
                f"{self._extra(True, warehouse_id, brand, category)}")
        # живые (без сдачи) + все с бакетами, в разрезе складов
        bucket_sums = ",\n".join(
            f"SUM(CASE WHEN {BUCKET_CASE} = '{b}' THEN 1 ELSE 0 END) AS {b}"
            for b in BUCKETS)
        per_wh = (await self.db.execute(text(f"""SELECT f.warehouse_id AS wid,
                COALESCE(wh.name, '—') AS wname, COUNT(*) AS cnt,
                SUM(CASE WHEN ls.wb_status = 'sorted' THEN 1 ELSE 0 END) AS sorted_cnt,
                {bucket_sums}
            {self._from()}
            LEFT JOIN wb_fbs_warehouse wh
                ON wh.warehouseId = f.warehouse_id AND wh.company_id = o.company_id
            WHERE {base}
            GROUP BY f.warehouse_id, wh.name"""), params)).mappings().all()
        # живые задания: возраст + цена + предмет (для денег и медиан риска)
        live = (await self.db.execute(text(f"""SELECT f.wb_order_id AS oid,
                CASE WHEN f.wb_created_at > '1000-01-01 00:00:00'
                     THEN f.wb_created_at END AS created_at,
                f.warehouse_id AS wid,
                COALESCE(wh.name, '—') AS wname,
                o.price_with_disc AS price, o.date AS odate, c.subjectID AS subject_id,
                o.g_number AS g_number, o.srid AS srid, o.nm_id AS order_nm_id,
                c.title AS card_title, c.vendorCode AS vendor_code,
                o.tech_size AS tech_size, o.barcode AS barcode
            {self._from()}
            LEFT JOIN wb_fbs_warehouse wh
                ON wh.warehouseId = f.warehouse_id AND wh.company_id = o.company_id
            LEFT JOIN wbcards c ON c.nmID = o.nm_id
                {('AND c.company_id = o.company_id') if self.company_id is not None else ''}
            WHERE {base}
              AND ({BUCKET_CASE} IN ('new', 'assembling'))"""),
            params)).mappings().all()
        # сданные за период: часы сборки для медиан
        # Нулевые даты '0000-00-00' режем через валидный порог '1000-01-01:
        # сам литерал '0000-00-00' в NULLIF MySQL отвергает (1525, journalctl 2026-10-05).
        # v4: только статусы (scanDt не учитываем — его может не быть).
        eff = "fh.first_handover_at"
        handed = (await self.db.execute(text(f"""SELECT f.warehouse_id AS wid,
                TIMESTAMPDIFF(MINUTE,
                    CASE WHEN f.wb_created_at > '1000-01-01 00:00:00'
                         THEN f.wb_created_at END,
                    ({eff})) / 60.0 AS h,
                o.price_with_disc AS price
            FROM wb_orders_fbs f
            JOIN wb_order o ON o.srid = f.rid AND o.company_id = f.company_id
            JOIN (SELECT wb_order_id,
                    MIN(CASE WHEN supplier_status IN ('confirm', 'complete')
                              AND created_at > '1000-01-01 00:00:00'
                        THEN created_at END) AS first_handover_at
                  FROM wb_orders_fbs_statuses
                  {('WHERE company_id = :company_id') if self.company_id is not None else ''}
                  GROUP BY wb_order_id) fh ON fh.wb_order_id = f.wb_order_id
            WHERE o.company_id = {(':company_id') if self.company_id is not None else 'o.company_id'}
              AND o.warehouse_type = 'Склад продавца'
              AND o.date BETWEEN :d1 AND :d2
              {('AND f.warehouse_id = :wid') if warehouse_id else ''}
              AND f.wb_created_at > '1000-01-01 00:00:00'
              AND ({eff}) > '1000-01-01 00:00:00'
              AND ({eff}) > f.wb_created_at"""),
            params)).mappings().all()
        tariffs = await self._tariff_map([r["subject_id"] for r in live
                                         if r["subject_id"]])
        live_h = []
        for r in live:
            created = r["created_at"]
            if not created:
                continue
            h = (now - created).total_seconds() / 3600
            live_h.append({"wid": r["wid"], "wname": r["wname"], "h": round(h, 1),
                           "price": float(r["price"] or 0),
                           "odate": str(r["odate"])[:16],
                           "subject_id": r["subject_id"],
                           "wb_order_id": r["oid"],
                           "g_number": r["g_number"],
                           "srid": r["srid"],
                           "nm_id": r["order_nm_id"],
                           "title": r["card_title"],
                           "vendor_code": r["vendor_code"],
                           "tech_size": r["tech_size"],
                           "barcode": r["barcode"]})
        quota = self._quota(live_h, tariffs)
        scan_hand = [(float(r["h"]), float(r["price"] or 0)) for r in handed
                     if r["h"] is not None and r["h"] >= 0]
        # Всего заданий FBS в скоупе — знаменатель для доли измеренных
        # (диагностика 2026-10-05: JOIN по скану молча резал выборку 69 -> 17).
        tasks_cnt = (await self.db.execute(text(f"""SELECT COUNT(*) AS cnt
            FROM wb_order o
            LEFT JOIN wb_orders_fbs f ON f.rid = o.srid AND f.company_id = o.company_id
            WHERE o.date BETWEEN :d1 AND :d2
              {self._extra(True, warehouse_id, brand, category)}"""),
            params)).scalar() or 0
        quota["economy"] = self._economy_stats(scan_hand, int(tasks_cnt))
        wh_cards = self._warehouse_cards(per_wh, live_h, handed)
        return {"now": now.strftime("%H:%M"), "quota": quota,
                "risk": quota["risk"], "warehouses": wh_cards}

    async def _tariff_map(self, subject_ids: list) -> dict:
        """subject_id -> [(tariff_date, base)] по возрастанию даты."""
        sids = sorted({int(s) for s in subject_ids if s})
        if not sids:
            return {}
        base_col = {"kgvp_marketplace": "kgvp_marketplace"}.get(
            TARIFFS.get("base_field", "kgvp_marketplace"), "kgvp_marketplace")
        ph = ", ".join(f":s{i}" for i in range(len(sids)))
        prm = {f"s{i}": v for i, v in enumerate(sids)}
        rows = (await self.db.execute(text(
            f"SELECT subject_id, tariff_date, {base_col} AS base "
            f"FROM wb_commission_tariffs WHERE subject_id IN ({ph}) "
            f"ORDER BY subject_id, tariff_date"), prm)).mappings().all()
        out: dict = {}
        for r in rows:
            out.setdefault(int(r["subject_id"]), []).append(
                (str(r["tariff_date"]), float(r["base"] or 0)))
        return out

    @staticmethod
    def _base_for(tariff_list: list | None, order_date: str) -> float:
        if not tariff_list:
            return 0.0
        dates = [d for d, _ in tariff_list]
        i = bisect_right(dates, order_date) - 1
        if i < 0:
            i = 0
        return tariff_list[i][1]

    def _commission_pct(self, base: float, h: float) -> float:
        for b in TARIFFS["buckets"]:
            upto = b["upto_h"]
            if upto is not None and h < upto:
                kind, v = b["kind"], b["value"]
                break
        else:
            kind, v = "penalty_pct_per_h", TARIFFS["buckets"][-1]["value"]
        if kind == "discount_pp":
            return base + v
        if kind == "penalty_pct_per_h":
            return base + v * max(0.0, h - TARIFFS["overdue_from_h"])
        return base

    def _quota(self, live: list, tariffs: dict) -> dict:
        cfg = TARIFFS
        n = len(live)
        # «Комиссия уже растёт» = дольше базового срока 18 ч (оферта WB, тултип 10X).
        overdue_h = cfg.get("quota_overdue_h", cfg.get("base_sla_h", 18))
        over = [x for x in live if x["h"] > overdue_h]
        soon = [x for x in live
                if cfg["base_sla_h"] - cfg["warn_h"] <= x["h"] <= cfg["base_sla_h"]]
        pre = [x for x in live if x["h"] > cfg["pre_cancel_h"]]
        growing = [x for x in live if x["h"] > cfg["overdue_from_h"]]
        ok = [x for x in live if x["h"] <= cfg["base_sla_h"] - cfg["warn_h"]]
        row = lambda x: {"wb_order_id": x["wb_order_id"], "g_number": x["g_number"],
                         "srid": x["srid"],
                         "date": x["odate"], "warehouse": x["wname"],
                         "nm_id": x["nm_id"], "title": x["title"],
                         "vendor_code": x["vendor_code"],
                         "tech_size": x["tech_size"], "barcode": x["barcode"],
                         "price": x["price"], "age_h": x["h"]}
        comm_sum = 0.0
        for x in growing:
            base = self._base_for(tariffs.get(x["subject_id"]), x["odate"])
            comm_sum += self._commission_pct(base, x["h"]) / 100 * x["price"]
        risk_sum = round(sum(x["price"] for x in over), 2)
        return {
            "overdue_cnt": len(over),
            "overdue_pct": round(len(over) / n * 100, 1) if n else 0,
            "overdue_sum": risk_sum,
            "commission_growing_sum": round(comm_sum, 2),
            "soon2h_cnt": len(soon),
            "pre_cancel_cnt": len(pre),
            "ok_cnt": len(ok),
            "ok_pct": round(len(ok) / n * 100, 1) if n else 0,
            "ok_sum": round(sum(x["price"] for x in ok), 2),
            "risk": {"sum": risk_sum,
                     "waiting_scan_cnt": len(live),
                     "stuck_cnt": len(over)},
            "orders": {"overdue": [row(x) for x in over],
                       "soon": [row(x) for x in soon],
                       "pre_cancel": [row(x) for x in pre],
                       "ok": [row(x) for x in ok]},
        }

    @staticmethod
    def _discount_pp(h: float) -> float:
        """Скидка с комиссии за быструю сдачу: <13 ч −5 п.п., <42 ч −3,5 п.п."""
        if h < 13:
            return 5.0
        if h < 42:
            return 3.5
        return 0.0

    @classmethod
    def _economy_stats(cls, items: list, tasks: int = 0) -> dict:
        """items: [(h, price)] со сканом. Сдано с экономией (h<42): шт,
        % от измеренных, % от ВСЕХ заданий (tasks), сумма скидки."""
        measured = len(items)
        eco = [(h, p) for h, p in items if h < 42]
        disc = round(sum(cls._discount_pp(h) / 100 * p for h, p in eco), 2)
        return {"cnt": len(eco),
                "pct": round(len(eco) / measured * 100, 1) if measured else 0,
                "share_pct": round(len(eco) / tasks * 100, 1) if tasks else 0,
                "discount_sum": disc, "measured": measured, "tasks": tasks}

    @classmethod
    def _warehouse_cards(cls, per_wh, live: list, handed) -> list:
        over_h = TARIFFS.get("quota_overdue_h", TARIFFS.get("base_sla_h", 18))
        live_by_wh: dict = {}
        for x in live:
            live_by_wh.setdefault(x["wid"], []).append(x)
        hand_by_wh: dict = {}
        scan_by_wh: dict = {}
        for r in handed:
            if r["h"] is not None and r["h"] >= 0:
                hand_by_wh.setdefault(r["wid"], []).append(float(r["h"]))
                scan_by_wh.setdefault(r["wid"], []).append(
                    (float(r["h"]), float(r["price"] or 0)))
        cards = []
        for r in per_wh:
            g = lambda k: int(r[k] or 0)
            wid = r["wid"]
            wl = live_by_wh.get(wid, [])
            over_w = [x for x in wl if x["h"] > over_h]
            hh = hand_by_wh.get(wid, [])
            med = round(median(hh), 1) if hh else None
            tasks_wh = g("cnt")
            eco = cls._economy_stats(scan_by_wh.get(wid, []), tasks_wh)
            cards.append({
                "warehouse_id": wid, "warehouse_name": r["wname"],
                "new": g("new"), "assembling": g("assembling"),
                "transit": g("handed") + g("transit"),
                "sorted": g("sorted_cnt"),
                "median_to_handover_h": med,
                "measured_cnt": len(hh),
                "tasks_cnt": tasks_wh,
                "live_cnt": len(wl),
                "growing_cnt": len(over_w),
                "growing_sum": round(sum(x["price"] for x in over_w), 2),
                "stuck_cnt": len(over_w),
                "economy_cnt": eco["cnt"],
                "economy_pct": eco["pct"],
                "economy_share": eco["share_pct"],
                "economy_discount": eco["discount_sum"],
            })
        cards.sort(key=lambda c: (c["warehouse_id"] is None, -(c["new"] + c["live_cnt"])))
        return cards
