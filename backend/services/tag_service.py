"""Порт TagController::actionView + WbOrderRepository::getOrdersStats + prepareAmChartsData."""
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession


class TagService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND o.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def get_stats(self, nm_ids: list[int], date_from: str, date_to: str,
                        group_by_date: bool = True, group_by_nm: bool = True) -> list[dict]:
        """Порт WbOrderRepository::getOrdersStats. Даты включительно, как BETWEEN в Yii2."""
        if not nm_ids:
            return []
        select = [
            "AVG(o.total_price) AS tp",
            "AVG(o.discount_percent) AS dsc",
            "AVG(o.price_with_disc) AS apwd",
            "AVG(o.spp) AS spp",
            "AVG(o.finished_price) AS finished_price",
            "COUNT(*) AS cnt",
            "SUM(CASE WHEN o.is_cancel = 1 THEN 1 ELSE 0 END) AS cns",
            "SUM(CASE WHEN o.sale_date IS NOT NULL THEN 1 ELSE 0 END) AS byt",
            "SUM(CASE WHEN o.is_cancel = 0 THEN o.price_with_disc ELSE 0 END) AS sum_ord",
            "SUM(CASE WHEN o.sale_date IS NOT NULL THEN o.price_with_disc ELSE 0 END) AS sum_byt",
        ]
        group: list[str] = []
        if group_by_nm:
            select = [
                "o.nm_id AS nm_id",
                "MAX(w.photos) AS card_photos",
                "MAX(w.title) AS card_title",
                "MAX(w.subjectName) AS card_subject_name",
                "MAX(w.brand) AS card_brand",
                "MAX(w.vendorCode) AS card_vendor_code",
                *select,
            ]
            group.append("o.nm_id")
        if group_by_date:
            select.append("DATE(o.date) AS odate")
            group.append("DATE(o.date)")
        group_sql = f"GROUP BY {', '.join(group)}" if group else ""
        # Yii2: orderBy cnt DESC при группировке по nm, иначе odate DESC
        order_sql = "ORDER BY cnt DESC" if group_by_nm else ("ORDER BY odate DESC" if group_by_date else "")
        join_sql = "LEFT JOIN wbcards w ON w.nmID = o.nm_id" if group_by_nm else ""
        stmt = text(f"""
            SELECT {', '.join(select)} FROM wb_order o {join_sql}
            WHERE o.nm_id IN :ids AND o.date BETWEEN :d1 AND :d2{self._company_where()}
            {group_sql} {order_sql}
        """).bindparams(bindparam("ids", expanding=True))
        params: dict = {
            "ids": [int(x) for x in nm_ids],
            "d1": f"{date_from} 00:00:00",
            "d2": f"{date_to} 23:59:59",
            **self._company_params(),
        }
        rows = (await self.db.execute(stmt, params)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("odate") is not None:
                d["odate"] = str(d["odate"])
            out.append(d)
        return out

    @staticmethod
    def build_chart(detail: list[dict]) -> list[dict]:
        """Порт TagController::prepareAmChartsData. date — ISO-строка для echarts time-axis."""
        nm_ids = sorted({int(r["nm_id"]) for r in detail if r.get("nm_id") is not None})
        by_date: dict[str, dict] = {}
        for row in detail:
            day = str(row["odate"])
            cell = by_date.get(day)
            if cell is None:
                cell = {"date": day, "total_cnt": 0}
                for nid in nm_ids:
                    cell[f"value_{nid}"] = 0
                    cell[f"sum_{nid}"] = 0.0
                by_date[day] = cell
            cell[f"value_{row['nm_id']}"] = int(row["cnt"] or 0)
            cell[f"sum_{row['nm_id']}"] = float(row["sum_ord"] or 0)
            cell["total_cnt"] += int(row["cnt"] or 0)
        return [by_date[k] for k in sorted(by_date)]

    async def analytics(self, tag: dict, date_from: str, date_to: str) -> dict:
        nm_ids = [int(x) for x in (tag.get("wbCardIds") or [])]
        if not nm_ids:
            return {"byProduct": [], "byDate": [], "chartData": [], "relatedCards": []}
        links_stmt = text("""
            SELECT w.nmID AS nmId, w.title AS card_name, w.vendorCode AS vendorCode
            FROM tag_card_links t INNER JOIN wbcards w ON t.nmID = w.nmID
            WHERE t.tag_id = :id
        """)
        related = [dict(r) for r in (await self.db.execute(links_stmt, {"id": tag["id"]})).mappings().all()]
        by_date = await self.get_stats(nm_ids, date_from, date_to, True, False)
        detail = await self.get_stats(nm_ids, date_from, date_to, True, True)
        by_product = await self.get_stats(nm_ids, date_from, date_to, False, True)
        return {
            "byProduct": by_product,
            "byDate": by_date,
            "chartData": self.build_chart(detail),
            "relatedCards": related,
        }
