"""«FBS Путь до ПВЗ» (/fbs-pvz): два отрезка пути заказа.

Анализ §11: отрезок 1 (наша зона) = wb_created_at → first confirm/complete;
отрезок 2 (зона WB) = first handover → first ready_for_pickup СТРОГО
(без fallback на sold). В замере — только заказы С ready_for_pickup
(в пути не учитываются). Направления БЕЗ маппинга: Россия →
country + oblast_okrug, остальные → country + region.
"""
from statistics import mean

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DIRECTION_SQL = """CASE
  WHEN o.country_name = 'Россия'
       AND o.oblast_okrug_name IS NOT NULL AND o.oblast_okrug_name <> ''
    THEN CONCAT(o.country_name, ', ', o.oblast_okrug_name)
  WHEN o.country_name = 'Россия'
    THEN o.country_name
  WHEN o.region_name IS NOT NULL AND o.region_name <> ''
    THEN CONCAT(COALESCE(o.country_name, ''), ', ', o.region_name)
  WHEN o.country_name IS NOT NULL AND o.country_name <> ''
    THEN o.country_name
  ELSE '—'
END"""


class FbsPvzService:
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
                      category: str | None = None,
                      top_dirs: int = 7) -> dict:
        top_dirs = 1000 if top_dirs <= 0 else max(1, min(top_dirs, 100))
        params = self._params(date_from, date_to, nm_id, brand, category)
        comp = "WHERE company_id = :company_id" if self.company_id is not None else ""
        card_comp = ("AND c.company_id = o.company_id"
                     if self.company_id is not None else "")
        rows = (await self.db.execute(text(f"""SELECT
                f.warehouse_id AS wid, COALESCE(wh.name, '—') AS wname,
                ({DIRECTION_SQL}) AS direction,
                o.nm_id AS nm_id, MAX(c.title) AS title,
                MAX(c.photos) AS photos, MAX(c.vendorCode) AS vendor_code,
                MAX(c.brand) AS card_brand, MAX(c.subjectName) AS subject_name,
                TIMESTAMPDIFF(MINUTE,
                    CASE WHEN f.wb_created_at > '1000-01-01 00:00:00'
                         THEN f.wb_created_at END,
                    fh.first_handover_at) / 60.0 AS h1,
                TIMESTAMPDIFF(MINUTE,
                    fh.first_handover_at, fp.first_pickup_at) / 60.0 AS h2
            FROM wb_orders_fbs f
            JOIN wb_order o ON o.srid = f.rid AND o.company_id = f.company_id
            JOIN (SELECT wb_order_id,
                    MIN(CASE WHEN supplier_status IN ('confirm', 'complete')
                              AND created_at > '1000-01-01 00:00:00'
                        THEN created_at END) AS first_handover_at
                  FROM wb_orders_fbs_statuses {comp} GROUP BY wb_order_id
            ) fh ON fh.wb_order_id = f.wb_order_id
            JOIN (SELECT wb_order_id,
                    MIN(CASE WHEN wb_status = 'ready_for_pickup'
                              AND created_at > '1000-01-01 00:00:00'
                        THEN created_at END) AS first_pickup_at
                  FROM wb_orders_fbs_statuses {comp} GROUP BY wb_order_id
            ) fp ON fp.wb_order_id = f.wb_order_id
            LEFT JOIN wb_fbs_warehouse wh
                ON wh.warehouseId = f.warehouse_id AND wh.company_id = o.company_id
            LEFT JOIN wbcards c ON c.nmID = o.nm_id {card_comp}
            WHERE o.company_id = {(':company_id') if self.company_id is not None else 'o.company_id'}
              AND o.date BETWEEN :d1 AND :d2{self._extra(nm_id, brand, category)}
              AND f.wb_created_at > '1000-01-01 00:00:00'
              AND fh.first_handover_at > f.wb_created_at
              AND fp.first_pickup_at > fh.first_handover_at
            GROUP BY f.wb_order_id, f.warehouse_id, wh.name,
                     o.nm_id, o.date, f.wb_created_at,
                     fh.first_handover_at, fp.first_pickup_at"""),
            params)).mappings().all()
        items = [{"wid": r["wid"], "wname": r["wname"],
                  "direction": r["direction"], "nm_id": r["nm_id"],
                  "title": r["title"], "photos": r["photos"],
                  "vendor_code": r["vendor_code"], "card_brand": r["card_brand"],
                  "subject_name": r["subject_name"],
                  "h1": float(r["h1"]), "h2": float(r["h2"]),
                  "total": float(r["h1"]) + float(r["h2"])}
                 for r in rows]
        n = len(items)
        kpi = {
            "measured_cnt": n,
            "avg_total_h": round(mean([x["total"] for x in items]), 1) if n else None,
            "avg_leg1_h": round(mean([x["h1"] for x in items]), 1) if n else None,
            "avg_leg2_h": round(mean([x["h2"] for x in items]), 1) if n else None,
        }
        # направления топ-N + остальные
        by_dir: dict = {}
        for x in items:
            by_dir[x["direction"]] = by_dir.get(x["direction"], 0) + 1
        # Топ-N отбираем по объёму, а колонки сортируем по алфавиту — так искать легче.
        top = sorted(sorted(by_dir, key=lambda d: -by_dir[d])[:top_dirs])
        matrix = []
        whs: dict = {}
        for x in items:
            whs.setdefault((x["wid"], x["wname"]), []).append(x)
        for (wid, wname), lst in sorted(whs.items(),
                                        key=lambda kv: (-len(kv[1]), str(kv[0][1]))):
            cells = {"all": self._avg([x["total"] for x in lst])}
            rest = []
            for d in top:
                sub = [x["total"] for x in lst if x["direction"] == d]
                cells[d] = self._avg(sub)
            rest = [x["total"] for x in lst if x["direction"] not in top]
            cells["rest"] = self._avg(rest)
            matrix.append({"warehouse_id": wid, "warehouse_name": wname,
                           "cnt": len(lst), "cells": cells})
        # по товарам топ-100
        by_nm: dict = {}
        for x in items:
            by_nm.setdefault(x["nm_id"], []).append(x)
        products = [{
            "nm_id": k, "title": v[0]["title"], "photos": v[0]["photos"],
            "vendor_code": v[0]["vendor_code"], "card_brand": v[0]["card_brand"],
            "subject_name": v[0]["subject_name"], "cnt": len(v),
            "avg_total_h": self._avg([x["total"] for x in v]),
            "avg_leg1_h": self._avg([x["h1"] for x in v]),
            "avg_leg2_h": self._avg([x["h2"] for x in v]),
        } for k, v in sorted(by_nm.items(), key=lambda kv: -len(kv[1]))[:100]]
        return {"kpi": kpi, "directions": ["all"] + top + ["rest"],
                "dir_counts": {d: by_dir[d] for d in top},
                "matrix": matrix, "products": products}

    @staticmethod
    def _avg(vals: list):
        return round(mean(vals), 1) if vals else None
