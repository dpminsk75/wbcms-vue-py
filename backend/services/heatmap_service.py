"""Порт WbOrderController.php:134 actionHeatmap — 7×24 WEEKDAY/HOUR"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class HeatmapService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_heatmap(self, nm_id: int | None, date_from: str, date_to: str) -> dict:
        where = ["o.date BETWEEN :d1 AND :d2"]
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if nm_id:
            where.append("o.nm_id = :nm_id")
            params["nm_id"] = nm_id
        where_sql = " AND ".join(where)

        sql = text(f"""
            SELECT WEEKDAY(o.date) as wd, HOUR(o.date) as hr,
                   COUNT(*) as cnt,
                   SUM(COALESCE(o.finished_price, o.price_with_disc, 0)) as sum_price,
                   SUM(CASE WHEN o.is_cancel=1 THEN 1 ELSE 0 END) as cancel_cnt
            FROM wb_order o WHERE {where_sql}
            GROUP BY wd, hr
        """)
        rows = (await self.db.execute(sql, params)).mappings().all()

        matrix = [[[0,0,0] for _ in range(24)] for _ in range(7)]  # wd 0=Пн..6=Вс, each [cnt,sum,cancel]
        # use dict for easier response: 7x24 objects
        matrix_obj = [[{"cnt":0,"sum":0.0,"cancel_cnt":0} for _ in range(24)] for _ in range(7)]
        max_cnt = 0
        total_cnt = 0
        total_sum = 0.0
        for r in rows:
            wd = int(r["wd"])
            hr = int(r["hr"])
            cnt = int(r["cnt"] or 0)
            s = float(r["sum_price"] or 0)
            canc = int(r["cancel_cnt"] or 0)
            matrix_obj[wd][hr] = {"cnt": cnt, "sum": s, "cancel_cnt": canc}
            max_cnt = max(max_cnt, cnt)
            total_cnt += cnt
            total_sum += s

        # windows 2-чаc скользящее как в php:181
        windows = []
        for h0 in range(24):
            h1 = (h0 + 1) % 24
            cnt = 0; s = 0.0; canc = 0
            for wd in range(7):
                cnt += matrix_obj[wd][h0]["cnt"] + matrix_obj[wd][h1]["cnt"]
                s += matrix_obj[wd][h0]["sum"] + matrix_obj[wd][h1]["sum"]
                canc += matrix_obj[wd][h0]["cancel_cnt"] + matrix_obj[wd][h1]["cancel_cnt"]
            avg = s / cnt if cnt else 0
            cancel_rate = canc / cnt * 100 if cnt else 0
            share = cnt / total_cnt * 100 if total_cnt else 0
            label = f"{h0:02d}:00–{(h1+1)%24:02d}:00"
            windows.append({"h0":h0,"h1":h1,"label":label,"label_short":label,"cnt":cnt,"sum":s,"avg":avg,"cancel_cnt":canc,"cancel_rate":cancel_rate,"share":share})

        by_volume = sorted(windows, key=lambda x: x["cnt"], reverse=True)
        by_avg_src = [w for w in windows if w["cnt"] >= 5] or windows
        by_avg = sorted(by_avg_src, key=lambda x: x["avg"], reverse=True)
        by_reli_src = [w for w in windows if w["cnt"] >= 5] or windows
        by_reli = sorted(by_reli_src, key=lambda x: x["cancel_rate"])

        recommend = {
            "byVolume": {"best": by_volume[0] if by_volume else None, "top3": by_volume[:3]},
            "byAvg": {"best": by_avg[0] if by_avg else None, "top3": by_avg[:3]},
            "byReli": {"best": by_reli[0] if by_reli else None, "top3": by_reli[:3]},
        }

        card = None
        if nm_id:
            try:
                card_sql = text("SELECT nmID, vendorCode, title, brand, photos FROM wbcards WHERE nmID=:nm_id LIMIT 1")
                card_row = (await self.db.execute(card_sql, {"nm_id": nm_id})).mappings().first()
                if card_row:
                    card = dict(card_row)
            except Exception:
                card = None

        return {
            "matrix": matrix_obj,
            "maxCnt": max_cnt,
            "totalCnt": total_cnt,
            "totalSum": total_sum,
            "dateFrom": date_from,
            "dateTo": date_to,
            "params": {"nm_id": nm_id, "date_from": date_from, "date_to": date_to},
            "recommend": recommend,
            "card": card,
        }
