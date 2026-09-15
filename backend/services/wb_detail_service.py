from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class WbDetailService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self, alias: str = "") -> str:
        prefix = f"{alias}." if alias else ""
        return "" if self.company_id is None else f" AND {prefix}company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def get_warehouse_stocks(self, nm_id: int):
        # как WbStocks::getWarehouseStocks
        last_date_sql = text("SELECT MAX(date) as d FROM wb_stocks WHERE company_id = :cid") if self.company_id is not None else text("SELECT date FROM wb_stocks ORDER BY date DESC LIMIT 1")
        params = {"cid": self.company_id} if self.company_id is not None else {}
        row = (await self.db.execute(last_date_sql, params)).first()
        last_date = row[0] if row else None
        if not last_date:
            return []
        sql = text(f"""SELECT warehouse_name, quantity FROM wb_stocks
                      WHERE nm_id=:nm_id AND date=:d{self._company_where()} AND quantity>0 ORDER BY quantity DESC""")
        rows = (await self.db.execute(sql, {"nm_id": nm_id, "d": last_date, **self._company_params()})).mappings().all()
        return [dict(r) for r in rows]

    async def get_in_way_stocks(self, nm_id: int):
        last_date_sql = text("SELECT MAX(date) as d FROM wb_stocks WHERE company_id = :cid") if self.company_id is not None else text("SELECT date FROM wb_stocks ORDER BY date DESC LIMIT 1")
        params = {"cid": self.company_id} if self.company_id is not None else {}
        row = (await self.db.execute(last_date_sql, params)).first()
        last_date = row[0] if row else None
        if not last_date:
            return []
        sql = text(f"""SELECT warehouse_name, in_way_to_client, in_way_from_client FROM wb_stocks
                      WHERE nm_id=:nm_id AND date=:d{self._company_where()} AND (in_way_to_client>0 OR in_way_from_client>0)
                      ORDER BY warehouse_name ASC""")
        rows = (await self.db.execute(sql, {"nm_id": nm_id, "d": last_date, **self._company_params()})).mappings().all()
        return [dict(r) for r in rows]

    async def get_paid_storage(self, nm_id: int, date_from: str, date_to: str):
        # из WbController detail.php wb_paid_storage group calcType
        sql = text(f"""SELECT calcType,
                             COUNT(DISTINCT date) as days_cnt,
                             SUM(barcodesCount) as total_units,
                             AVG(volume) as avg_volume,
                             SUM(warehousePrice) as total_price,
                             SUM(warehousePrice)/NULLIF(SUM(barcodesCount),0) as price_per_unit
                      FROM wb_paid_storage
                      WHERE nmId=:nm_id AND date BETWEEN :d1 AND :d2{self._company_where()}
                      GROUP BY calcType ORDER BY total_price DESC""")
        rows = (await self.db.execute(sql, {"nm_id": nm_id, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()
        return [dict(r) for r in rows]

    async def get_adv(self, nm_id: int, date_from: str, date_to: str):
        # как WbController.php:383 — LEFT JOIN item (adv=1 реклама / 0 органика), без INNER по wbcards
        sql = text(f"""
            SELECT c.campaign_id, c.name, c.status,
                   CASE WHEN i.id IS NULL THEN 0 ELSE 1 END as adv,
                   SUM(n.orders) as orders, SUM(n.sum) as sum, SUM(n.sum_price) as sum_price
            FROM wb_campaign_stats_nms n
            INNER JOIN wb_campaign_stats s ON n.parent_id=s.id
            INNER JOIN wb_campaign c ON c.campaign_id=s.campaign_id{self._company_where('c')}
            LEFT JOIN wb_campaign_item i ON i.campaign_id=s.campaign_id AND n.nm_id=i.nm_id{self._company_where('i')}
            WHERE n.nm_id=:nm_id AND s.date BETWEEN :d1 AND :d2 AND n.orders>0
            GROUP BY c.campaign_id, c.name, adv, c.status
            ORDER BY adv DESC, SUM(n.orders) DESC
        """)
        rows = (await self.db.execute(sql, {"nm_id": nm_id, "d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59", **self._company_params()})).mappings().all()
        return [dict(r) for r in rows]

    async def get_order_stats(self, nm_id: int, date_from: str, date_to: str):
        # как WbController.php:467 — период date_from..(date_to-14д), связка заказов и продаж по srid
        from datetime import date as dt_date, timedelta
        try:
            d_to = dt_date.fromisoformat(date_to) - timedelta(days=14)
        except Exception:
            d_to = dt_date.today() - timedelta(days=14)
        sql = text(f"""
            SELECT SUM(o.is_realization) as alls, SUM(o.finished_price) as sLO,
                   SUM(o.is_cancel) as cancel,
                   SUM(CASE WHEN s.saleID IS NULL THEN 1 ELSE 0 END) as notb,
                   SUM(CASE WHEN s.saleID IS NULL THEN 0 ELSE 1 END) as bought,
                   SUM(s.finishedPrice) as `sum`, SUM(s.forPay) as sFP
            FROM wb_order o LEFT JOIN wb_sales s ON o.srid=s.srid
            WHERE o.nm_id=:nm_id AND o.date BETWEEN :d1 AND :d2{self._company_where('o')}
            GROUP BY o.nm_id
        """)
        row = (await self.db.execute(sql, {"nm_id": nm_id, "d1": f"{date_from} 00:00:00", "d2": f"{d_to.isoformat()} 23:59:59", **self._company_params()})).mappings().first()
        if not row:
            return {"alls": 0, "sLO": 0, "cancel": 0, "notb": 0, "bought": 0, "sum": 0, "sFP": 0, "date_to14": d_to.isoformat()}
        d = dict(row)
        return {"alls": int(d.get("alls") or 0), "sLO": float(d.get("sLO") or 0), "cancel": int(d.get("cancel") or 0),
                "notb": int(d.get("notb") or 0), "bought": int(d.get("bought") or 0),
                "sum": float(d.get("sum") or 0), "sFP": float(d.get("sFP") or 0), "date_to14": d_to.isoformat()}

    async def get_funnel(self, nm_id: int, date_from: str, date_to: str):
        # как WbController.php:499-550 — суммы + доли от кол-ва, buyout = bought/(bought+cancel)
        sql = text(f"""
            SELECT COUNT(*) as total_qty, COALESCE(SUM(o.finished_price),0) as total_sum,
                   SUM(CASE WHEN s.saleID IS NOT NULL AND s.saleID NOT LIKE 'R%' THEN 1 ELSE 0 END) as bought_qty,
                   COALESCE(SUM(CASE WHEN s.saleID IS NOT NULL AND s.saleID NOT LIKE 'R%' THEN s.finishedPrice ELSE 0 END),0) as bought_sum,
                   SUM(CASE WHEN o.is_cancel=1 THEN 1 ELSE 0 END) as cancel_qty,
                   COALESCE(SUM(CASE WHEN o.is_cancel=1 THEN o.finished_price ELSE 0 END),0) as cancel_sum,
                   SUM(CASE WHEN o.is_cancel=0 AND s.saleID IS NULL THEN 1 ELSE 0 END) as delivery_qty,
                   COALESCE(SUM(CASE WHEN o.is_cancel=0 AND s.saleID IS NULL THEN o.finished_price ELSE 0 END),0) as delivery_sum,
                   SUM(CASE WHEN s.saleID LIKE 'R%' THEN 1 ELSE 0 END) as returns_qty,
                   COALESCE(SUM(CASE WHEN s.saleID LIKE 'R%' THEN s.finishedPrice ELSE 0 END),0) as returns_sum
            FROM wb_order o LEFT JOIN wb_sales s ON s.srid=o.srid
            WHERE o.nm_id=:nm_id AND o.date BETWEEN :d1 AND :d2{self._company_where('o')}
        """)
        r = (await self.db.execute(sql, {"nm_id": nm_id, "d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59", **self._company_params()})).mappings().first()
        d = dict(r) if r else {}
        tot = int(d.get("total_qty") or 0)
        bq = int(d.get("bought_qty") or 0)
        cq = int(d.get("cancel_qty") or 0)
        dq = int(d.get("delivery_qty") or 0)
        rq = int(d.get("returns_qty") or 0)
        pct = lambda q: round(q/tot*100, 2) if tot else 0
        return {"total_qty": tot, "total_sum": float(d.get("total_sum") or 0),
                "bought_qty": bq, "bought_sum": float(d.get("bought_sum") or 0), "bought_percent": pct(bq),
                "delivery_qty": dq, "delivery_sum": float(d.get("delivery_sum") or 0), "delivery_percent": pct(dq),
                "cancel_qty": cq, "cancel_sum": float(d.get("cancel_sum") or 0), "cancel_percent": pct(cq),
                "returns_qty": rq, "returns_sum": float(d.get("returns_sum") or 0), "returns_percent": pct(rq),
                "buyout_percent": round(bq/(bq+cq)*100, 2) if (bq+cq) else 0}

    async def get_daily_orders(self, nm_id: int, date_from: str, date_to: str):
        sql = text(f"""SELECT DATE(date) as odate, nm_id,
                             SUM(is_realization) as cnt,
                             SUM(is_cancel) as cns,
                             SUM(CASE WHEN is_cancel=0 THEN finished_price ELSE 0 END) as sum,
                             AVG(total_price) as tp,
                             AVG(discount_percent) as dsc,
                             AVG(price_with_disc) as apwd,
                             AVG(spp) as spp,
                             AVG(finished_price) as finished_price
                      FROM wb_order WHERE nm_id=:nm_id AND date BETWEEN :d1 AND :d2{self._company_where()} GROUP BY DATE(date), nm_id ORDER BY odate DESC""")
        rows = (await self.db.execute(sql, {"nm_id": nm_id, "d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59", **self._company_params()})).mappings().all()
        return [dict(r) for r in rows]

    async def get_daily_sales(self, nm_id: int, date_from: str, date_to: str):
        sql = text(f"""SELECT DATE(date) as odate, nmId as nm_id,
                             SUM(isRealization) as cnt,
                             SUM(finishedPrice) as sum,
                             SUM(forPay) as sFP,
                             AVG(totalPrice) as tp,
                             AVG(discountPercent) as dsc,
                             AVG(priceWithDisc) as apwd,
                             AVG(spp) as spp,
                             AVG(finishedPrice) as finished_price,
                             AVG(forPay) as forPay
                      FROM wb_sales WHERE nmId=:nm_id AND date BETWEEN :d1 AND :d2{self._company_where()} GROUP BY DATE(date), nmId ORDER BY odate DESC""")
        rows = (await self.db.execute(sql, {"nm_id": nm_id, "d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59", **self._company_params()})).mappings().all()
        return [dict(r) for r in rows]

    async def get_weekly_finance(self, nm_id: int, date_from: str, date_to: str):
        # как WbController.php:555 — реклама/отзывы из ff_adv/ff_otziv, net_profit с поправкой
        sql = text(f"""SELECT DATE_SUB(sdate, INTERVAL WEEKDAY(sdate) DAY) as sdate,
                             SUM(qnt) as qnt, SUM(amount) as amount, SUM(commission) as commission,
                             SUM(f_acquiring_fee) as f_acquiring_fee, SUM(f_delivery) as f_delivery,
                             SUM(f_penalty) as f_penalty,
                             COALESCE(SUM(ff_otziv),0) as f_otziv, COALESCE(SUM(ff_adv),0) as f_adv, SUM(f_cashback) as f_cashback,
                             SUM(net_profit)-COALESCE(SUM(ff_otziv),0)-COALESCE(SUM(ff_adv),0) as net_profit,
                             COALESCE(SUM(f_nds),0) as total_nds, COALESCE(SUM(f_cost_price),0) as total_cost,
                             SUM(net_profit)-COALESCE(SUM(f_nds),0)-COALESCE(SUM(f_cost_price),0)-COALESCE(SUM(ff_otziv),0)-COALESCE(SUM(ff_adv),0) as profit_before_tax,
                             GREATEST(0, SUM(net_profit)-COALESCE(SUM(f_nds),0)-COALESCE(SUM(f_cost_price),0)-COALESCE(SUM(ff_otziv),0)-COALESCE(SUM(ff_adv),0))*0.07 as tax_amount,
                             (SUM(net_profit)-COALESCE(SUM(f_nds),0)-COALESCE(SUM(f_cost_price),0)-COALESCE(SUM(ff_otziv),0)-COALESCE(SUM(ff_adv),0))
                              - (GREATEST(0, SUM(net_profit)-COALESCE(SUM(f_nds),0)-COALESCE(SUM(f_cost_price),0)-COALESCE(SUM(ff_otziv),0)-COALESCE(SUM(ff_adv),0))*0.07) as clean_margin,
                             COALESCE(SUM(amount)/NULLIF(SUM(qnt),0),0) as amount_per_item,
                             COALESCE(SUM(net_profit)/NULLIF(SUM(qnt),0),0) as profit_per_item,
                             COALESCE(((SUM(net_profit)-COALESCE(SUM(f_nds),0)-COALESCE(SUM(f_cost_price),0)-COALESCE(SUM(ff_otziv),0)-COALESCE(SUM(ff_adv),0))
                              - (GREATEST(0, SUM(net_profit)-COALESCE(SUM(f_nds),0)-COALESCE(SUM(f_cost_price),0)-COALESCE(SUM(ff_otziv),0)-COALESCE(SUM(ff_adv),0))*0.07))/NULLIF(SUM(qnt),0),0) as clear_per_item
                      FROM agg_daily_summary WHERE nm_id=:nm_id AND sdate BETWEEN :d1 AND :d2{self._company_where()}
                      GROUP BY DATE_SUB(sdate, INTERVAL WEEKDAY(sdate) DAY) ORDER BY sdate DESC""")
        rows = (await self.db.execute(sql, {"nm_id": nm_id, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()
        return [dict(r) for r in rows]

    async def get_phrases(self, nm_id: int, date_from: str, date_to: str):
        # как WbSearchService.php:18 — оконные SUM/AVG по фразе, сортировка по частотности
        # wb_sr_report_item_phrases не имеет company_id — данные глобальные по артикулу
        sql = text("""SELECT `phrase`, `date`, avg_position, clicks, orders, week_frequency,
                             SUM(clicks) OVER (PARTITION BY `phrase`) as total_clicks,
                             SUM(orders) OVER (PARTITION BY `phrase`) as total_orders,
                             AVG(week_frequency) OVER (PARTITION BY `phrase`) as avg_week_freq
                       FROM wb_sr_report_item_phrases
                       WHERE nmID=:nm_id AND `date` BETWEEN :d1 AND :d2
                       ORDER BY avg_week_freq DESC, `date` ASC""")
        rows = (await self.db.execute(sql, {"nm_id": nm_id, "d1": date_from, "d2": date_to})).mappings().all()
        matrix: dict = {}
        stats: dict = {}
        dates: dict = {}
        order: list = []
        for r in rows:
            ph = r["phrase"]
            dt = str(r["date"])[:10]
            if ph not in matrix:
                matrix[ph] = {}
                order.append(ph)
            matrix[ph][dt] = {"pos": int(r["avg_position"] or 0), "orders": int(r["orders"] or 0)}
            stats[ph] = {"clicks": int(r["total_clicks"] or 0), "orders": int(r["total_orders"] or 0), "freq": int(r["avg_week_freq"] or 0)}
            dates[dt] = True
        unique = sorted(dates.keys())
        models = []
        for ph in order:
#            m: dict = {"phrase": ph, "avg_freq": stats[ph]["freq"], "total_clicks": stats[ph]["total_clicks"], "total_orders": stats[ph]["total_orders"]}
            m: dict = {"phrase": ph, "avg_freq": stats[ph]["freq"], "total_clicks": stats[ph]["clicks"], "total_orders": stats[ph]["orders"]}
            for dt in unique:
                m[dt] = matrix[ph].get(dt)
            models.append(m)
        return {"models": models, "dates": unique}
