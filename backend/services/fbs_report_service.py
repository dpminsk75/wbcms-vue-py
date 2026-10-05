"""FBS-дашборд «Продажа со своего склада», вкладка Сводка.

ТЗ: 2026-10-05_fbs-report-tz.md, решения: 2026-10-05_fbs-report-analysis.md (§3a маппинг,
§3b supply_id не признак, до СПП = price_with_disc, prev-период той же длины).

Только FBS: o.warehouse_type = 'Склад продавца'. Последний статус — MAX(id) как в
WbOrderFeedSearch.php:206-217, но с фильтром company_id внутри обоих уровней подзапроса.
"""
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Бакет статуса — порядок важен, первое совпадение побеждает (анализ §3a).
BUCKET_CASE = """CASE
  WHEN ls.supplier_status = 'cancel' OR ls.wb_status = 'canceled' THEN 'seller_cancel'
  WHEN ls.wb_status = 'canceled_by_client' THEN 'buyer_cancel'
  WHEN ls.wb_status IN ('declined_by_client', 'defect') THEN 'declined'
  WHEN ls.wb_status = 'sold' THEN 'sold'
  WHEN ls.wb_status = 'ready_for_pickup' THEN 'pickup'
  WHEN ls.wb_status IN ('sorted', 'accepted_by_carrier', 'sent_to_carrier') THEN 'transit'
  WHEN ls.supplier_status = 'complete' AND ls.wb_status = 'waiting' THEN 'handed'
  WHEN ls.supplier_status = 'confirm' THEN 'assembling'
  WHEN ls.supplier_status = 'new' AND ls.wb_status = 'waiting' THEN 'new'
  ELSE 'unknown'
END"""

BUCKETS = ("new", "assembling", "handed", "transit", "pickup", "sold",
           "declined", "buyer_cancel", "seller_cancel", "unknown")

# Границы «Времени обработки» 1в1 со скрина 10X: [0,13)/[13,42)/[42,48)/[48,54)/[54,60)/[60,+).
HANDLING_BOUNDS = [0, 13, 42, 48, 54, 60]


class FbsReportService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _period_params(self, date_from: str, date_to: str,
                       nm_id: int | None, brand: str | None,
                       category: str | None) -> dict:
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

    def _extra_where(self, nm_id: int | None, brand: str | None,
                     category: str | None) -> str:
        extra = ""
        if nm_id:
            extra += " AND o.nm_id = :nm_id"
        if brand:
            extra += " AND o.brand = :brand"
        if category:
            extra += " AND o.category = :category"
        return extra

    def _latest_status_join(self) -> str:
        comp = "WHERE company_id = :company_id" if self.company_id is not None else ""
        return f"""LEFT JOIN (
            SELECT s1.wb_order_id, s1.supplier_status, s1.wb_status
            FROM wb_orders_fbs_statuses s1
            JOIN (SELECT wb_order_id, MAX(id) AS max_id
                  FROM wb_orders_fbs_statuses {comp} GROUP BY wb_order_id) m
              ON m.wb_order_id = s1.wb_order_id AND m.max_id = s1.id
            {('WHERE s1.company_id = :company_id') if self.company_id is not None else ''}
        ) ls ON ls.wb_order_id = f.wb_order_id"""

    def _base_where(self) -> str:
        where = ("o.date BETWEEN :d1 AND :d2"
                 " AND o.warehouse_type = 'Склад продавца'")
        if self.company_id is not None:
            where += " AND o.company_id = :company_id"
        return where

    def _from_sql(self) -> str:
        return f"""FROM wb_order o
            LEFT JOIN wb_orders_fbs f ON f.rid = o.srid AND f.company_id = o.company_id
            {self._latest_status_join()}"""

    async def _kpi_pipeline(self, date_from: str, date_to: str,
                            nm_id: int | None, brand: str | None,
                            category: str | None) -> dict:
        bucket_sums = ",\n".join(
            f"SUM(CASE WHEN {BUCKET_CASE} = '{b}' THEN 1 ELSE 0 END) AS {b}"
            for b in BUCKETS
        )
        sql = text(f"""SELECT COUNT(*) AS cnt,
                COALESCE(SUM(o.price_with_disc), 0) AS orders_sum,
                {bucket_sums}
            {self._from_sql()}
            WHERE {self._base_where()}{self._extra_where(nm_id, brand, category)}""")
        row = (await self.db.execute(
            sql, self._period_params(date_from, date_to, nm_id, brand, category)
        )).mappings().first()
        return {k: row[k] for k in ("cnt", "orders_sum", *BUCKETS)} if row else {}

    async def _daily(self, date_from: str, date_to: str,
                     nm_id: int | None, brand: str | None,
                     category: str | None) -> list:
        bucket_sums = ",\n".join(
            f"SUM(CASE WHEN {BUCKET_CASE} = '{b}' THEN 1 ELSE 0 END) AS {b}"
            for b in BUCKETS
        )
        sql = text(f"""SELECT DATE(o.date) AS d, COUNT(*) AS cnt,
                {bucket_sums}
            {self._from_sql()}
            WHERE {self._base_where()}{self._extra_where(nm_id, brand, category)}
            GROUP BY d ORDER BY d ASC""")
        rows = (await self.db.execute(
            sql, self._period_params(date_from, date_to, nm_id, brand, category)
        )).mappings().all()
        return [dict(r, d=str(r["d"])) for r in rows]

    async def _handling(self, date_from: str, date_to: str,
                        nm_id: int | None, brand: str | None,
                        category: str | None) -> dict:
        # v4 (2026-10-05): время СБОРКИ = wb_created_at → первый
        # confirm/complete ТОЛЬКО по статусам. scanDt не учитываем: WB не
        # всегда отдаёт номер поставки при смене статуса, скана может не быть
        # в принципе (таблица поставок — в резерве). last_change_date не
        # используем: там финал заказа, всё падало в 60+ч.
        comp = "WHERE company_id = :company_id" if self.company_id is not None else ""
        # Нулевые даты '0000-00-00' режем через валидный порог: сам литерал
        # '0000-00-00' MySQL отвергает (1525, journalctl 2026-10-05).
        eff = "fh.first_handover_at"
        h = ("TIMESTAMPDIFF(HOUR, "
             "CASE WHEN f.wb_created_at > '1000-01-01 00:00:00' THEN f.wb_created_at END, "
             f"({eff}))")
        ok = (f"({eff}) > '1000-01-01 00:00:00' "
              "AND f.wb_created_at > '1000-01-01 00:00:00' "
              f"AND ({eff}) > f.wb_created_at")
        conds = []
        lo = HANDLING_BOUNDS
        for i in range(len(lo)):
            if i < len(lo) - 1:
                conds.append(
                    f"SUM(CASE WHEN {ok} "
                    f"AND {h} >= {lo[i]} AND {h} < {lo[i + 1]} "
                    f"THEN 1 ELSE 0 END) AS b{i}")
            else:
                conds.append(
                    f"SUM(CASE WHEN {ok} "
                    f"AND {h} >= {lo[i]} THEN 1 ELSE 0 END) AS b{i}")
        sql = text(f"""SELECT COUNT(*) AS total,
                SUM(CASE WHEN {ok} THEN 1 ELSE 0 END) AS measured,
                {', '.join(conds)}
            FROM wb_orders_fbs f
            JOIN wb_order o ON o.srid = f.rid AND o.company_id = f.company_id
            LEFT JOIN (
                SELECT wb_order_id,
                    MIN(CASE WHEN supplier_status IN ('confirm', 'complete')
                              AND created_at > '1000-01-01 00:00:00'
                        THEN created_at END) AS first_handover_at
                FROM wb_orders_fbs_statuses {comp} GROUP BY wb_order_id
            ) fh ON fh.wb_order_id = f.wb_order_id
            WHERE {self._base_where()}{self._extra_where(nm_id, brand, category)}""")
        row = (await self.db.execute(
            sql, self._period_params(date_from, date_to, nm_id, brand, category)
        )).mappings().first()
        return dict(row) if row else {}

    @staticmethod
    def _derive(kpi: dict) -> dict:
        g = lambda k: int(kpi.get(k) or 0)
        sold, declined = g("sold"), g("declined")
        buyer, seller = g("buyer_cancel"), g("seller_cancel")
        closed = sold + declined + buyer + seller
        transit = (g("new") + g("assembling") + g("handed")
                   + g("transit") + g("pickup"))
        return {
            "orders_cnt": g("cnt"),
            "orders_sum": float(kpi.get("orders_sum") or 0),
            "buyout_pct": round(sold / closed * 100, 2) if closed else 0,
            "in_transit_cnt": transit,
            "canceled_cnt": declined + buyer + seller,
            "canceled_seller": seller,
            "canceled_buyer": declined + buyer,
        }

    @staticmethod
    def _pct(cur: float, prev: float):
        if not prev:
            return None
        return round((cur - prev) / abs(prev) * 100, 2)

    async def summary(self, date_from: str, date_to: str,
                      nm_id: int | None = None, brand: str | None = None,
                      category: str | None = None) -> dict:
        d1 = date.fromisoformat(date_from)
        d2 = date.fromisoformat(date_to)
        days = (d2 - d1).days + 1
        prev_to = (d1 - timedelta(days=1)).isoformat()
        prev_from = (d1 - timedelta(days=days)).isoformat()

        cur = await self._kpi_pipeline(date_from, date_to, nm_id, brand, category)
        prev = await self._kpi_pipeline(prev_from, prev_to, nm_id, brand, category)
        daily_rows = await self._daily(date_from, date_to, nm_id, brand, category)
        handling_row = await self._handling(date_from, date_to, nm_id, brand, category)

        kpi = self._derive(cur)
        pkpi = self._derive(prev)
        delta = {
            "orders_sum_pct": self._pct(kpi["orders_sum"], pkpi["orders_sum"]),
            "orders_cnt_pct": self._pct(kpi["orders_cnt"], pkpi["orders_cnt"]),
            "buyout_pp": round(kpi["buyout_pct"] - pkpi["buyout_pct"], 2),
            "in_transit_pct": self._pct(kpi["in_transit_cnt"], pkpi["in_transit_cnt"]),
            "canceled_pct": self._pct(kpi["canceled_cnt"], pkpi["canceled_cnt"]),
        }
        pipeline = {b: int(cur.get(b) or 0) for b in BUCKETS}
        daily = [{
            "d": r["d"],
            "sold": int(r["sold"] or 0),
            "new": int(r["new"] or 0),
            "assembling": int(r["assembling"] or 0),
            "handed": int(r["handed"] or 0),
            "transit": int(r["transit"] or 0),
            "pickup": int(r["pickup"] or 0),
            "declined": int(r["declined"] or 0),
            "buyer_cancel": int(r["buyer_cancel"] or 0),
            "seller_cancel": int(r["seller_cancel"] or 0),
            "unknown": int(r["unknown"] or 0),
        } for r in daily_rows]

        measured = int(handling_row.get("measured") or 0)
        labels = ["0–13 ч", "13–42 ч", "42–48 ч", "48–54 ч", "54–60 ч", "от 60 ч"]
        buckets = []
        for i, label in enumerate(labels):
            cnt = int(handling_row.get(f"b{i}") or 0)
            buckets.append({"id": label, "cnt": cnt,
                            "pct": round(cnt / measured * 100, 2) if measured else 0})
        handling = {"measured": measured,
                    "total": int(handling_row.get("total") or 0),
                    "buckets": buckets}
        return {
            "period": {"from": date_from, "to": date_to, "days": days,
                       "prev_from": prev_from, "prev_to": prev_to},
            "kpi": kpi, "prev": pkpi, "delta": delta,
            "pipeline": pipeline, "daily": daily, "handling": handling,
        }

    async def breakdown(self, mode: str, date_from: str, date_to: str,
                        nm_id: int | None = None, brand: str | None = None,
                        category: str | None = None,
                        limit: int = 100) -> dict:
        """Разрез периода: mode=products (GROUP BY nm_id + карточка) или
        mode=warehouses (GROUP BY склад FBS). Без размеров — построчный вариант."""
        bucket_sums = ",\n".join(
            f"SUM(CASE WHEN {BUCKET_CASE} = '{b}' THEN 1 ELSE 0 END) AS {b}"
            for b in BUCKETS
        )
        params = self._period_params(date_from, date_to, nm_id, brand, category)
        params["lim"] = max(1, min(limit, 500))
        where = (f"{self._base_where()}"
                 f"{self._extra_where(nm_id, brand, category)}")
        if mode == "warehouses":
            sql = text(f"""SELECT f.warehouse_id AS wid,
                    COALESCE(wh.name,
                        CASE WHEN f.warehouse_id IS NULL THEN '—'
                             ELSE CONCAT('Склад ', f.warehouse_id) END) AS wname,
                    COUNT(*) AS cnt,
                    COALESCE(SUM(o.price_with_disc), 0) AS orders_sum,
                    {bucket_sums}
                {self._from_sql()}
                LEFT JOIN wb_fbs_warehouse wh
                    ON wh.warehouseId = f.warehouse_id AND wh.company_id = o.company_id
                WHERE {where}
                GROUP BY f.warehouse_id, wh.name
                ORDER BY cnt DESC LIMIT :lim""")
        else:
            card_comp = "AND c.company_id = o.company_id" if self.company_id is not None else ""
            sql = text(f"""SELECT o.nm_id AS nm_id,
                    MAX(c.title) AS title, MAX(c.vendorCode) AS vendor_code,
                    MAX(c.photos) AS photos, MAX(c.brand) AS card_brand,
                    COUNT(*) AS cnt,
                    COALESCE(SUM(o.price_with_disc), 0) AS orders_sum,
                    {bucket_sums}
                {self._from_sql()}
                LEFT JOIN wbcards c ON c.nmID = o.nm_id {card_comp}
                WHERE {where}
                GROUP BY o.nm_id
                ORDER BY cnt DESC LIMIT :lim""")
        rows = (await self.db.execute(sql, params)).mappings().all()
        items = []
        for r in rows:
            d = self._derive({k: r[k] for k in ("cnt", "orders_sum", *BUCKETS)})
            item = {"cnt": d["orders_cnt"], "orders_sum": d["orders_sum"],
                    "buyout_pct": d["buyout_pct"],
                    "in_transit_cnt": d["in_transit_cnt"],
                    "canceled_cnt": d["canceled_cnt"],
                    "canceled_seller": d["canceled_seller"],
                    "canceled_buyer": d["canceled_buyer"],
                    "sold": int(r["sold"] or 0)}
            if mode == "warehouses":
                item["warehouse_id"] = r["wid"]
                item["warehouse_name"] = r["wname"]
            else:
                item["nm_id"] = r["nm_id"]
                item["title"] = r["title"]
                item["vendor_code"] = r["vendor_code"]
                item["photos"] = r["photos"]
                item["card_brand"] = r["card_brand"]
            items.append(item)
        return {"mode": mode, "items": items}

    async def options(self, date_from: str, date_to: str) -> dict:
        params = self._period_params(date_from, date_to, None, None, None)
        base = f"{self._base_where()}"
        br = (await self.db.execute(
            text(f"SELECT DISTINCT o.brand FROM wb_order o "
                 f"WHERE {base} AND o.brand IS NOT NULL AND o.brand <> '' "
                 f"ORDER BY o.brand LIMIT 500"), params)).all()
        ct = (await self.db.execute(
            text(f"SELECT DISTINCT o.category FROM wb_order o "
                 f"WHERE {base} AND o.category IS NOT NULL AND o.category <> '' "
                 f"ORDER BY o.category LIMIT 500"), params)).all()
        return {"brands": [r[0] for r in br], "categories": [r[0] for r in ct]}
