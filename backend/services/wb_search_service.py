"""Порт WbSearchController (card/phrase/trend) + ajax-search."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class WbSearchService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self, alias: str = "p") -> str:
        return "" if self.company_id is None else f" AND {alias}.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def trend(self, phrase_text: str | None, date_from: str, date_to: str,
                    page: int = 1, page_size: int = 50) -> dict:
        """Порт actionTrend:552 — понедельные частоты + ТОП-9 для графика."""
        where = "p.date BETWEEN :d1 AND :d2"
        params: dict = {"d1": date_from, "d2": date_to, **self._company_params()}
        if phrase_text and phrase_text.strip():
            if phrase_text.strip().isdigit():
                where += " AND pd.id = :pid"
                params["pid"] = int(phrase_text.strip())
            else:
                where += " AND p.phrase LIKE :like"
                params["like"] = f"%{phrase_text.strip()}%"
        stmt = text(f"""
            SELECT pd.id as phrase_id, p.phrase, DATE_FORMAT(p.date, '%x-%v') as week_key,
                MAX(p.week_frequency) as freq, SUM(p.clicks) as clicks, SUM(p.orders) as orders
            FROM wb_sr_report_item_phrases p
            LEFT JOIN wb_phrases_directory pd ON pd.phrase = p.phrase
            WHERE {where}{self._company_where()}
            GROUP BY pd.id, p.phrase, week_key
            HAVING MAX(p.week_frequency) >= 5
        """)
        rows = (await self.db.execute(stmt, params)).mappings().all()
        stats: dict[str, dict] = {}
        weeks: set[str] = set()
        for r in rows:
            ph, wk = r["phrase"], f"w_{r['week_key']}"
            weeks.add(wk)
            freq = int(r["freq"] or 0)
            cell = stats.setdefault(ph, {"phrase": ph, "phrase_id": r["phrase_id"],
                                         "total_clicks": 0, "total_orders": 0, "sum_freq": 0, "cnt_weeks": 0})
            cell[wk] = freq
            cell["total_clicks"] += int(r["clicks"] or 0)
            cell["total_orders"] += int(r["orders"] or 0)
            if freq > 0:
                cell["sum_freq"] += freq
                cell["cnt_weeks"] += 1
        models = []
        for ph, c in stats.items():
            cnt = c["cnt_weeks"] or 1
            avg = round(c["sum_freq"] / cnt)
            conv = round(c["total_orders"] / c["total_clicks"] * 100, 2) if c["total_clicks"] else 0
            row = {"phrase": ph, "phrase_id": c["phrase_id"], "avg_freq": avg,
                   "total_clicks": c["total_clicks"], "total_orders": c["total_orders"], "conversion": conv}
            for wk in weeks:
                row[wk] = c.get(wk, 0)
            models.append(row)
        models.sort(key=lambda m: m["avg_freq"], reverse=True)
        top9 = models[:9]
        sorted_weeks = sorted(weeks)
        chart = [{"week": wk[2:], **{f"val_{i}": tp.get(wk, 0) for i, tp in enumerate(top9)}} for wk in sorted_weeks]
        total = len(models)
        start = (page - 1) * page_size
        return {"models": models[start:start + page_size], "total": total, "page": page,
                "page_size": page_size, "weeks": sorted_weeks,
                "chartData": chart, "topPhrases": [{"phrase": tp["phrase"]} for tp in top9]}

    async def card_info(self, nm_id: int) -> dict | None:
        row = (await self.db.execute(
            text("SELECT nmID, title FROM wbcards WHERE nmID=:id"
                 + ("" if self.company_id is None else " AND (company_id = :cid OR company_id IS NULL)")),
            {"id": nm_id} | ({} if self.company_id is None else {"cid": self.company_id}),
        )).mappings().first()
        return dict(row) if row else None

    async def card_matrix(self, nm_id: int, date_from: str, date_to: str) -> tuple[list[dict], list[str]]:
        """Порт actionCard:29 — строки=фразы, ячейки {pos, orders}. Без window-функций (старый MySQL), агрегаты в Python."""
        stmt = text(f"""
            SELECT phrase, date, avg_position, clicks, orders, week_frequency
            FROM wb_sr_report_item_phrases p
            WHERE nmID=:nm AND date BETWEEN :d1 AND :d2{self._company_where()}
            ORDER BY date ASC
        """)
        rows = (await self.db.execute(stmt, {"nm": nm_id, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()
        matrix: dict[str, dict] = {}
        clicks: dict[str, int] = {}
        orders: dict[str, int] = {}
        freq_sum: dict[str, int] = {}
        freq_cnt: dict[str, int] = {}
        dates: set[str] = set()
        for r in rows:
            ph, d = r["phrase"], str(r["date"])
            matrix.setdefault(ph, {})[d] = {"pos": int(r["avg_position"] or 0), "orders": int(r["orders"] or 0)}
            clicks[ph] = clicks.get(ph, 0) + int(r["clicks"] or 0)
            orders[ph] = orders.get(ph, 0) + int(r["orders"] or 0)
            if r["week_frequency"] is not None:
                freq_sum[ph] = freq_sum.get(ph, 0) + int(r["week_frequency"])
                freq_cnt[ph] = freq_cnt.get(ph, 0) + 1
            dates.add(d)
        unique_dates = sorted(dates)
        models = [
            {"phrase": ph, "avg_freq": round(freq_sum.get(ph, 0) / (freq_cnt.get(ph) or 1)),
             "total_clicks": clicks[ph], "total_orders": orders[ph],
             **{d: matrix[ph].get(d) for d in unique_dates}}
            for ph in matrix
        ]
        models.sort(key=lambda m: m["total_clicks"], reverse=True)
        return models, unique_dates

    async def analytics(self, date_from: str, date_to: str,
                      q: str | None = None, sort: str = "freq",
                      page: int = 1, page_size: int = 50) -> dict:
        """Частотность фраз за период vs предыдущий равный период.

        Метрика недельная (frequency_current == week_frequency всегда,
        проверено 2026-10-15: 241k строк, diff=0) — это СРЕДНЕСУТОЧНАЯ
        частота (совпадает с колонкой WB «в среднем за день» 1в1).
        «Количество запросов» WB = AVG дневных MAX × N дней периода.
        Дедуп nmID обязателен: одна фраза приходит по нескольким артикулам.
        Порог MAX > 1. Позиции: AVG/MIN по ненулевым avg_position."""
        from datetime import date as _date, timedelta
        d1 = _date.fromisoformat(date_from)
        d2 = _date.fromisoformat(date_to)
        n = (d2 - d1).days + 1
        p2 = d1 - timedelta(days=1)
        p1 = p2 - timedelta(days=n - 1)
        params: dict = {"p1": p1.isoformat(), "c2": d2.isoformat(),
                        **self._company_params()}
        like = ""
        if q and q.strip():
            like = " AND p.phrase LIKE :q"
            params["q"] = f"%{q.strip()}%"
        rows = (await self.db.execute(text(f"""
            SELECT p.phrase, p.date,
                MAX(p.week_frequency) AS freq,
                AVG(NULLIF(p.avg_position, 0)) AS avg_pos,
                MIN(NULLIF(p.avg_position, 0)) AS best_pos,
                SUM(p.clicks) AS clicks, SUM(p.orders) AS orders
            FROM wb_sr_report_item_phrases p
            WHERE p.date BETWEEN :p1 AND :c2{self._company_where()}{like}
            GROUP BY p.phrase, p.date
        """), params)).mappings().all()
        cur: dict[str, dict] = {}
        prev: dict[str, dict] = {}
        for r in rows:
            cell = {"freq": int(r["freq"] or 0),
                    "pos": float(r["avg_pos"]) if r["avg_pos"] is not None else None,
                    "best": int(r["best_pos"]) if r["best_pos"] is not None else None,
                    "clicks": int(r["clicks"] or 0),
                    "orders": int(r["orders"] or 0)}
            tgt = cur if str(r["date"]) >= date_from else prev
            tgt.setdefault(r["phrase"], []).append(cell)
        goods_rows = (await self.db.execute(text(f"""
            SELECT p.phrase, COUNT(DISTINCT p.nmID) AS goods
            FROM wb_sr_report_item_phrases p
            WHERE p.date BETWEEN :d1 AND :d2{self._company_where()}{like}
            GROUP BY p.phrase
        """), {"d1": date_from, "d2": date_to,
               **self._company_params(),
               **({"q": params["q"]} if "q" in params else {})})).mappings().all()
        goods = {r["phrase"]: int(r["goods"] or 0) for r in goods_rows}
        models = []
        for ph, days in cur.items():
            max_f = max(d["freq"] for d in days)
            if max_f <= 1:
                continue
            avg_c = round(sum(d["freq"] for d in days) / len(days))
            pd = prev.get(ph, [])
            avg_p = round(sum(d["freq"] for d in pd) / len(pd)) if pd else 0
            poses = [d["pos"] for d in days if d["pos"] is not None]
            bests = [d["best"] for d in days if d["best"] is not None]
            models.append({
                "phrase": ph,
                "freq": avg_c, "freq_max": max_f,
                "freq_prev": avg_p, "delta": avg_c - avg_p,
                "total": avg_c * n, "total_prev": avg_p * n,
                "delta_total": (avg_c - avg_p) * n,
                "is_new": not pd,
                "goods": goods.get(ph, 0),
                "avg_pos": round(sum(poses) / len(poses), 1) if poses else None,
                "best_pos": min(bests) if bests else None,
                "clicks": sum(d["clicks"] for d in days),
                "orders": sum(d["orders"] for d in days),
            })
        if sort == "delta":
            models.sort(key=lambda m: m["delta"], reverse=True)
        elif sort == "goods":
            models.sort(key=lambda m: (m["goods"], m["freq"]), reverse=True)
        elif sort == "orders":
            models.sort(key=lambda m: (m["orders"], m["freq"]), reverse=True)
        elif sort == "best":
            models.sort(key=lambda m: (m["best_pos"] is None, m["best_pos"] or 0))
        elif sort == "pos":
            models.sort(key=lambda m: (m["avg_pos"] is None, m["avg_pos"] or 0))
        else:  # freq/day: порядок одинаковый (total = freq x N дней)
            models.sort(key=lambda m: (m["freq"], m["freq_max"]), reverse=True)
        total = len(models)
        start = (page - 1) * page_size
        return {"models": models[start:start + page_size], "total": total,
                "page": page, "page_size": page_size,
                "date_from": date_from, "date_to": date_to,
                "prev_from": p1.isoformat(), "prev_to": p2.isoformat()}

    async def phrases_directory(self, q: str | None = None, limit: int = 1000) -> list[dict]:
        """Порт phrasesMap: живые фразы для селекта."""
        sql = """
            SELECT id, phrase, max_frequency FROM wb_phrases_directory
            WHERE max_frequency > 5
        """
        params: dict = {}
        if q:
            sql += " AND phrase LIKE :q"
            params["q"] = f"%{q}%"
        sql += " ORDER BY max_frequency DESC LIMIT :lim"
        params["lim"] = limit
        rows = (await self.db.execute(text(sql), params)).mappings().all()
        out = [dict(r) for r in rows]
        if self.company_id is not None:
            out = [r for r in out]  # directory общий; фильтр по данным ниже
        return out

    async def resolve_phrase(self, phrase_id: int | None, phrase: str | None) -> tuple[int | None, str | None]:
        """phrase_id → текст через справочник; иначе текст как есть."""
        if phrase_id:
            row = (await self.db.execute(
                text("SELECT id, phrase FROM wb_phrases_directory WHERE id=:id"), {"id": phrase_id}
            )).mappings().first()
            if row:
                return int(row["id"]), row["phrase"]
        if phrase:
            return None, phrase
        return None, None

    async def phrase_matrix(self, phrase_text: str, date_from: str, date_to: str) -> tuple[list[dict], list[str]]:
        """Порт actionPhrase:369 — строки=карточки. Без window-функций, агрегаты в Python."""
        stmt = text(f"""
            SELECT p.nmID, c.title, p.date, p.avg_position, p.clicks, p.orders, p.week_frequency
            FROM wb_sr_report_item_phrases p
            LEFT JOIN wbcards c ON c.nmID = p.nmID
            WHERE p.phrase=:ph AND p.date BETWEEN :d1 AND :d2{self._company_where()}
        """)
        rows = (await self.db.execute(stmt, {"ph": phrase_text, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()
        matrix: dict[int, dict] = {}
        titles: dict[int, str] = {}
        clicks: dict[int, int] = {}
        orders: dict[int, int] = {}
        freq_sum: dict[int, int] = {}
        freq_cnt: dict[int, int] = {}
        dates: set[str] = set()
        for r in rows:
            nm, d = int(r["nmID"]), str(r["date"])
            matrix.setdefault(nm, {})[d] = {"pos": int(r["avg_position"] or 0), "orders": int(r["orders"] or 0)}
            titles[nm] = r["title"] or str(nm)
            clicks[nm] = clicks.get(nm, 0) + int(r["clicks"] or 0)
            orders[nm] = orders.get(nm, 0) + int(r["orders"] or 0)
            if r["week_frequency"] is not None:
                freq_sum[nm] = freq_sum.get(nm, 0) + int(r["week_frequency"])
                freq_cnt[nm] = freq_cnt.get(nm, 0) + 1
            dates.add(d)
        unique_dates = sorted(dates)
        models = [
            {"nmID": nm, "title": titles[nm], "avg_freq": round(freq_sum.get(nm, 0) / (freq_cnt.get(nm) or 1)),
             "total_clicks": clicks[nm], "total_orders": orders[nm],
             **{d: matrix[nm].get(d) for d in unique_dates}}
            for nm in matrix
        ]
        models.sort(key=lambda m: m["total_clicks"], reverse=True)
        return models, unique_dates

    async def phrase_chart(self, phrase_text: str, date_from: str, date_to: str) -> tuple[list[dict], dict[int, str]]:
        """Порт actionPhrase:432 — ТОП-5 по кликам + частотность с forward-fill (простой ≥7д → 0)."""
        from datetime import date as _date, timedelta
        stmt = text(f"""
            SELECT p.nmID, c.title, p.date, p.clicks, p.week_frequency
            FROM wb_sr_report_item_phrases p
            LEFT JOIN wbcards c ON c.nmID = p.nmID
            WHERE p.phrase=:ph AND p.date BETWEEN :d1 AND :d2{self._company_where()}
        """)
        rows = (await self.db.execute(stmt, {"ph": phrase_text, "d1": date_from, "d2": date_to, **self._company_params()})).mappings().all()
        clicks: dict[int, dict[str, int]] = {}
        names: dict[int, str] = {}
        totals: dict[int, int] = {}
        freq_raw: dict[str, int] = {}
        for r in rows:
            nm, d = int(r["nmID"]), str(r["date"])
            clicks.setdefault(nm, {})[d] = int(r["clicks"] or 0)
            names[nm] = r["title"] or str(nm)
            totals[nm] = totals.get(nm, 0) + int(r["clicks"] or 0)
            f = int(r["week_frequency"] or 0)
            if d not in freq_raw or f > freq_raw[d]:
                freq_raw[d] = f
        top5 = sorted(totals, key=lambda k: totals[k], reverse=True)[:5]
        cur = _date.fromisoformat(date_from)
        end = _date.fromisoformat(date_to)
        chart: list[dict] = []
        last_freq, idle = 0, 0
        while cur <= end:
            d = cur.isoformat()
            if freq_raw.get(d, 0) > 0:
                last_freq, idle = freq_raw[d], 0
            else:
                idle += 1
                if idle >= 7:
                    last_freq = 0
            point: dict = {"date": d, "frequency": last_freq}
            for nm in top5:
                point[f"card_{nm}"] = clicks.get(nm, {}).get(d, 0)
            chart.append(point)
            cur += timedelta(days=1)
        return chart, {nm: names[nm] for nm in top5}

    # ------------------------------------------------------------------ каннибализация

    async def cannibalization(self, date_from: str, date_to: str, q: str | None = None,
                              nm_id: int | None = None, brand: str | None = None,
                              category: str | None = None, page: int = 1,
                              page_size: int = 50) -> dict:
        """Порт actionCannibalization (WbSearchController.php:192) — фразы, по которым
        в выдаче WB ранжируются ≥2 наших карточек.

        Отличия от PHP:
          * **нет N+1** — карточки и позиции берутся ОДНИМ запросом по отобранным фразам
            (в PHP на каждую строку был отдельный SELECT в wbcards);
          * **есть LIMIT/OFFSET и счётчик** — в PHP пагинации не было, весь результат
            попадал в память, а GROUP_CONCAT резался на 1024 байтах;
          * добавлены **средняя и лучшая позиция** карточки (в PHP позиций не было);
          * фильтры по бренду и категории — через wbcards (в отчёте WB их нет).

        Фильтр по карточке (nm_id) НЕ меняет условие «≥2 карточек» — он лишь отбирает
        фразы, в которых эта карточка участвует (EXISTS по тому же отчёту WB).
        """
        where = "p.date BETWEEN :d1 AND :d2"
        params: dict = {"d1": date_from, "d2": date_to, **self._company_params()}
        if self.company_id is not None:
            where = "p.company_id = :company_id AND " + where
        if q and q.strip():
            where += " AND p.phrase LIKE :q"
            params["q"] = f"%{q.strip()}%"
        if nm_id:
            where += (" AND EXISTS (SELECT 1 FROM wb_sr_report_item_phrases p2"
                      " WHERE p2.phrase = p.phrase AND p2.nmID = :nm"
                      " AND p2.date BETWEEN :d1 AND :d2)")
            params["nm"] = int(nm_id)
        if brand and str(brand).strip():
            where += (" AND EXISTS (SELECT 1 FROM wbcards c2"
                      " WHERE c2.nmID = p.nmID AND c2.brand = :brand)")
            params["brand"] = str(brand).strip()
        if category and str(category).strip():
            where += (" AND EXISTS (SELECT 1 FROM wbcards c3"
                      " WHERE c3.nmID = p.nmID AND c3.subjectName = :category)")
            params["category"] = str(category).strip()

        # Только фразы с ≥2 карточками — общий кусок для выборки и счётчика.
        base = f"""
            FROM wb_sr_report_item_phrases p
            WHERE {where}
            GROUP BY p.phrase
            HAVING COUNT(DISTINCT p.nmID) > 1
        """

        lim = max(1, min(int(page_size or 50), 200))
        off = max(0, (int(page or 1) - 1) * lim)

        rows_sql = text(f"""
            SELECT p.phrase,
                   COUNT(DISTINCT p.nmID) AS cards_count,
                   SUM(p.clicks) AS total_clicks,
                   SUM(p.orders) AS total_orders,
                   AVG(p.week_frequency) AS avg_freq
            {base}
            ORDER BY total_orders DESC, p.phrase ASC
            LIMIT :lim OFFSET :off
        """)
        rows = (await self.db.execute(
            rows_sql, {**params, "lim": lim, "off": off})).mappings().all()

        total = 0
        cnt_sql = text(f"SELECT COUNT(*) FROM (SELECT p.phrase {base}) x")
        total = int((await self.db.execute(cnt_sql, params)).scalar() or 0)

        # Карточки и позиции по отобранным фразам — один запрос (вместо N+1).
        cards_by_phrase: dict[str, list[dict]] = {}
        phrases = [str(r["phrase"]) for r in rows]
        if phrases:
            ph = ",".join(f":p{i}" for i in range(len(phrases)))
            ph_params = {f"p{i}": v for i, v in enumerate(phrases)}
            detail_sql = text(f"""
                SELECT p.phrase, p.nmID, c.title, c.vendorCode, c.brand, c.subjectName AS subject,
                       AVG(NULLIF(p.avg_position, 0)) AS avg_pos,
                       MIN(NULLIF(p.avg_position, 0)) AS best_pos,
                       MAX(p.week_frequency) AS max_freq,
                       SUM(p.clicks) AS clicks, SUM(p.orders) AS orders
                FROM wb_sr_report_item_phrases p
                LEFT JOIN wbcards c ON c.nmID = p.nmID
                WHERE p.date BETWEEN :d1 AND :d2{self._company_where()}
                  AND p.phrase IN ({ph})
                GROUP BY p.phrase, p.nmID, c.title, c.vendorCode, c.brand, c.subjectName
            """)
            detail = (await self.db.execute(
                detail_sql, {"d1": date_from, "d2": date_to, **ph_params, **self._company_params()}
            )).mappings().all()
            for r in detail:
                cards_by_phrase.setdefault(str(r["phrase"]), []).append({
                    "nm_id": int(r["nmID"] or 0),
                    "title": r["title"] or "",
                    "vendor_code": r["vendorCode"] or "",
                    "brand": r["brand"] or "",
                    "subject": r["subject"] or "",
                    "avg_pos": round(float(r["avg_pos"]), 1) if r["avg_pos"] is not None else None,
                    "best_pos": int(r["best_pos"]) if r["best_pos"] is not None else None,
                    "max_freq": int(r["max_freq"] or 0),
                    "clicks": int(r["clicks"] or 0),
                    "orders": int(r["orders"] or 0),
                })
            for lst in cards_by_phrase.values():
                lst.sort(key=lambda c: (c["avg_pos"] is None, c["avg_pos"] or 0))

        models = []
        for r in rows:
            ph = str(r["phrase"])
            models.append({
                "phrase": ph,
                "cards_count": int(r["cards_count"] or 0),
                "total_clicks": int(r["total_clicks"] or 0),
                "total_orders": int(r["total_orders"] or 0),
                "avg_freq": round(float(r["avg_freq"] or 0), 1),
                "cards": cards_by_phrase.get(ph, []),
            })
        return {
            "models": models,
            "total": total,
            "page": int(page or 1),
            "page_size": lim,
            "date_from": date_from,
            "date_to": date_to,
        }
