"""Гео-продажи: detail_by_period x pvz_all (карта + таблица одним GROUP BY).

Порт GeoMapReportController::actionIndex (продажи по регионам), но джойн новый:
php: detail_by_period.address_id = dadata_address_cache.id,
здесь: detail_by_period.ppvz_office_id = pvz_all.wb_id (есть lat/lon для карты).
Фильтры как в php: supplier_oper_name='Продажа', sale_dt BETWEEN, nm_id обязателен.
Таблица = то же что карта: один запрос, level из зума, bbox из вьюпорта.

Уровни: country | okrug | region | city | pvz.
okrug (федеральный округ) — свёртка регионов в Python по статическому маппингу
REGION_OKRUG (не зависит от dadata_status: pending-строки без region/city всё равно
ложатся в округ, если регион известен; совсем без региона — «Без округа»).
Чужие страны на уровне okrug — по одному пузырю на страну (ключ 'C:XX').
Ключи okrug РФ — 'O:<название>'.

ONLY_FULL_GROUP_BY: в GROUP BY дословно те же выражения, что в SELECT
(см. AGENTS.md) — свёртка okrug поэтому в Python, а не вторым SQL.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.geo_names import (
    COUNTRY_NAMES, STEM2OKRUG, _stem, okrug_of,
)

LEVELS = ("country", "okrug", "region", "city", "pvz")


# Статичные якоря: центроид из AVG координат WB ненадёжен (кривые точки +
# малые n утаскивают пузырь в чужую страну), поэтому страны и округа
# стоят на фиксированных точках, а размер пузыря — из данных.
# Регионы/города/ПВЗ остаются на вычисляемых координатах.
COUNTRY_ANCHOR = {
    "RU": (55.75, 37.61),   # Москва
    "BY": (53.90, 27.56),   # Минск
    "KZ": (51.16, 71.43),   # Астана
    "UZ": (41.30, 69.24),   # Ташкент
    "AM": (40.18, 44.51),   # Ереван
    "KG": (42.87, 74.59),   # Бишкек
    "GE": (41.72, 44.79),   # Тбилиси
    "TJ": (38.56, 68.78),   # Душанбе
}

OKRUG_ANCHOR = {
    "Центральный ФО": (55.75, 37.61),        # Москва
    "Северо-Западный ФО": (59.93, 30.33),    # Санкт-Петербург
    "Южный ФО": (47.23, 39.70),              # Ростов-на-Дону
    "Северо-Кавказский ФО": (44.05, 43.06),  # Пятигорск
    "Приволжский ФО": (56.32, 44.00),        # Нижний Новгород
    "Уральский ФО": (56.83, 60.60),          # Екатеринбург
    "Сибирский ФО": (55.03, 82.92),          # Новосибирск
    "Дальневосточный ФО": (48.48, 135.07),   # Хабаровск
}




# Нормализация — в колонках pvz_all.region_norm / city_norm
# (считает scripts/pvz_norm.py через services/geo_names.py).
# Здесь только plain-колонки: никакой строковой хирургии в SQL (см. AGENTS.md).


def _parse_bbox(bbox: str | None):
    # формат "s,w,n,e" (юг,запад,север,восток); мусор -> None (без фильтра)
    if not bbox:
        return None
    try:
        s, w, n, ee = [float(x) for x in str(bbox).split(",")]
    except (TypeError, ValueError):
        return None
    if not (-90 <= s <= 90 and -90 <= n <= 90 and -180 <= w <= 180 and -180 <= ee <= 180):
        return None
    if s > n:
        s, n = n, s
    if w > ee:
        w, ee = ee, w
    # вырожденный bbox (точка) — не фильтруем
    if abs(n - s) < 1e-9 and abs(ee - w) < 1e-9:
        return None
    return s, w, n, ee


class GeoSalesService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    async def _regions_of_okrug(self, okrug: str) -> list[str]:
        """Нормы region_norm из pvz_all, ложащиеся в округ (для фильтра parent_okrug)."""
        rows = (await self.db.execute(text(
            "SELECT DISTINCT region_norm FROM pvz_all "
            "WHERE country = 'ru' AND region_norm IS NOT NULL"
        ))).scalars().all()
        return [str(r) for r in rows if STEM2OKRUG.get(_stem(str(r))) == okrug]

    # Порог office-first пути: больше офисов — дешевле идти обычным сканом периода.
    OFFICE_IN_LIMIT = 2000

    async def _offices_for_parent(self, parent_country: str | None,
                                  parent_okrug: str | None,
                                  parent_region: str | None,
                                  parent_city: str | None) -> list[int] | None:
        """wb_id офисов под parent-фильтром. None = фильтра нет (обычный путь)."""
        if not (parent_country or parent_okrug or parent_region or parent_city):
            return None
        conds: list[str] = []
        params: dict = {}
        if parent_country:
            conds.append("country = :pc")
            params["pc"] = str(parent_country).lower()[:2]
        if parent_okrug and not parent_region and not parent_city:
            regs = await self._regions_of_okrug(parent_okrug)
            if not regs:
                return []
            conds.append("region_norm IN ("
                         + ",".join("'" + r.replace("'", "''") + "'" for r in regs) + ")")
        if parent_region:
            if parent_region == "__none__":
                conds.append("region_norm IS NULL")
            else:
                conds.append("region_norm = :pr")
                params["pr"] = parent_region
        if parent_city:
            if parent_city == "__none__":
                conds.append("city_norm IS NULL")
            else:
                conds.append("city_norm = :pct")
                params["pct"] = parent_city
        rows = (await self.db.execute(text(
            "SELECT wb_id FROM pvz_all WHERE " + " AND ".join(conds)
            + f" LIMIT {self.OFFICE_IN_LIMIT + 1}"), params)).scalars().all()
        return [int(x) for x in rows if x]

    async def _grain(self, select: str, group: str, where_sql: str,
                     params: dict, order: str, limit: int) -> list[dict]:
        rows = (await self.db.execute(text(f"""
            SELECT {select},
                   COUNT(*) AS qty,
                   SUM(COALESCE(d.retail_price, 0)) AS sum_retail,
                   SUM(COALESCE(d.retail_amount, 0)) AS sum_amount,
                   SUM(COALESCE(d.ppvz_for_pay, 0)) AS sum_for_pay,
                   AVG(COALESCE(d.ppvz_spp_prc, 0)) AS spp,
                   COUNT(DISTINCT p.wb_id) AS pvz_count
            FROM detail_by_period d
            JOIN pvz_all p ON p.wb_id = d.ppvz_office_id
            WHERE {where_sql}
            GROUP BY {group}
            ORDER BY {order}
            LIMIT {limit}"""), params)).mappings().all()
        return [dict(r) for r in rows]

    @staticmethod
    def _nums(r: dict) -> dict:
        return {
            "lat": float(r["lat"]) if r.get("lat") is not None else None,
            "lon": float(r["lon"]) if r.get("lon") is not None else None,
            "qty": int(r.get("qty") or 0),
            "sum_retail": float(r.get("sum_retail") or 0),
            "sum_amount": float(r.get("sum_amount") or 0),
            "sum_for_pay": float(r.get("sum_for_pay") or 0),
            "spp": round(float(r.get("spp") or 0), 2),
            "pvz_count": int(r.get("pvz_count") or 0),
        }

    @staticmethod
    def _shape(r: dict) -> dict:
        return {
            "key": str(r.get("k")), "name": r.get("name"), "sub": r.get("sub") or "",
            "addr": r.get("addr") or "",
            **GeoSalesService._nums(r),
        }

    @staticmethod
    def _shape_region(r: dict) -> dict:
        code = str(r.get("cc") or "").upper()
        name = r.get("rn") or "Без региона"
        return {
            "key": f"{code}|{name}", "name": name,
            "sub": COUNTRY_NAMES.get(code, code or ""), "addr": "",
            **GeoSalesService._nums(r),
        }

    @staticmethod
    def _shape_city(r: dict) -> dict:
        code = str(r.get("cc") or "").upper()
        sub = r.get("rrn") or "Без региона"
        name = r.get("cn") or "Без города"
        return {
            "key": f"{code}|{sub}|{name}", "name": name, "sub": sub, "addr": "",
            **GeoSalesService._nums(r),
        }

    @staticmethod
    def _fold_okrug(rows: list[dict], metric: str) -> list[dict]:
        """Свёртка регион-зерна в округа + страны."""
        acc: dict[str, dict] = {}
        for r in rows:
            code = str(r.get("sub") or "").upper()
            q = int(r.get("qty") or 0)
            if code == "RU":
                ok = okrug_of(str(r.get("name") or ""))
                key = "O:" + ok
                name, sub = ok, COUNTRY_NAMES["RU"]
            else:
                key = "C:" + code
                name, sub = COUNTRY_NAMES.get(code, code or "—"), ""
            a = acc.setdefault(key, {"key": key, "name": name, "sub": sub,
                                     "qty": 0, "sum_retail": 0.0, "sum_amount": 0.0,
                                     "sum_for_pay": 0.0, "spp_w": 0.0, "pvz_count": 0})
            a["qty"] += q
            a["sum_retail"] += float(r.get("sum_retail") or 0)
            a["sum_amount"] += float(r.get("sum_amount") or 0)
            a["sum_for_pay"] += float(r.get("sum_for_pay") or 0)
            a["spp_w"] += float(r.get("spp") or 0) * q
            a["pvz_count"] += int(r.get("pvz_count") or 0)
        items = []
        for a in acc.values():
            q = a["qty"]
            anchor = None
            if a["key"].startswith("O:"):
                anchor = OKRUG_ANCHOR.get(a["name"])
            elif a["key"].startswith("C:"):
                anchor = COUNTRY_ANCHOR.get(a["key"][2:])
            if anchor is not None:
                lat, lon = anchor
            else:
                # «Без округа» и неизвестные коды: координат нет — фронт их не рисует
                lat = lon = None
            items.append({
                "key": a["key"], "name": a["name"], "sub": a["sub"], "addr": "",
                "lat": lat, "lon": lon,
                "qty": q, "sum_retail": a["sum_retail"], "sum_amount": a["sum_amount"],
                "sum_for_pay": a["sum_for_pay"],
                "spp": round(a["spp_w"] / q, 2) if q else 0.0,
                "pvz_count": a["pvz_count"],
            })
        items.sort(key=lambda x: x["qty"] if metric == "qty" else x["sum_amount"],
                   reverse=True)
        return items

    def _region_select_group(self) -> tuple[str, str]:
        select = ("p.country AS cc, p.region_norm AS rn, "
                  "AVG(p.lat) AS lat, AVG(p.lon) AS lon")
        group = "p.country, p.region_norm"
        return select, group

    def _city_select_group(self) -> tuple[str, str]:
        select = ("p.country AS cc, p.region_norm AS rrn, p.city_norm AS cn, "
                  "AVG(p.lat) AS lat, AVG(p.lon) AS lon")
        group = "p.country, p.region_norm, p.city_norm"
        return select, group

    async def _resolve_product_ids(self, nm_id: int | None, q: str | None,
                                     brand: str | None, category: str | None,
                                     ) -> list[int] | None:
        """Маска/бренд/категория -> список nmID через wbcards.
        None = товарный фильтр не задан (все продажи).
        [] = фильтр задан, но ничего не найдено (быстрый пустой ответ)."""
        if nm_id:
            return [int(nm_id)]
        conds: list[str] = []
        params: dict = {}
        if q and str(q).strip():
            # как WbCardService.list_cards: число = подстрока nmID, иначе vendorCode/title.
            # маска — буквальная подстрока: экранируем спецсимволы LIKE (% _ \).
            # ESCAPE-клаузу не пишем: бэкслэш внутри '...' сам экранирует кавычку (1064),
            # а по умолчанию LIKE уже понимает \-экранирование.
            mask = str(q).strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conds.append("(CAST(nmID AS CHAR) LIKE :q OR vendorCode LIKE :q OR title LIKE :q)")
            params["q"] = f"%{mask}%"
        if brand:
            conds.append("brand = :b")
            params["b"] = brand
        if category:
            conds.append("subjectName = :c")
            params["c"] = category
        if not conds:
            return None
        if self.company_id is not None:
            conds.append("company_id = :cid")
            params["cid"] = self.company_id
        rows = (await self.db.execute(text(
            "SELECT nmID FROM wbcards WHERE " + " AND ".join(conds) + " LIMIT 500"),
            params)).scalars().all()
        return sorted({int(x) for x in rows if x})

    async def options(self) -> dict:
        """Бренды + предметы для селектов универсального фильтра (из wbcards)."""
        comp = "" if self.company_id is None else " AND company_id = :cid"
        p = {} if self.company_id is None else {"cid": self.company_id}
        br = (await self.db.execute(text(
            f"SELECT DISTINCT brand FROM wbcards WHERE brand IS NOT NULL AND brand <> ''{comp} "
            f"ORDER BY brand LIMIT 500"), p)).scalars().all()
        ct = (await self.db.execute(text(
            f"SELECT DISTINCT subjectName FROM wbcards WHERE subjectName IS NOT NULL AND subjectName <> ''{comp} "
            f"ORDER BY subjectName LIMIT 500"), p)).scalars().all()
        return {"brands": [str(x) for x in br if x], "categories": [str(x) for x in ct if x]}

    async def sales_map(
        self,
        nm_id: int | None,
        date_from: str,
        date_to: str,
        q: str | None = None,
        brand: str | None = None,
        category: str | None = None,
        metric: str = "qty",
        level: str = "region",
        bbox: str | None = None,
        world: bool = False,
        parent_country: str | None = None,
        parent_okrug: str | None = None,
        parent_region: str | None = None,
        parent_city: str | None = None,
        limit: int = 2000,
    ) -> dict:
        metric = metric if metric in ("qty", "sum") else "qty"
        level = level if level in LEVELS else "region"
        limit = max(1, min(int(limit or 2000), 5000))
        ids = await self._resolve_product_ids(nm_id, q, brand, category)
        empty_params = {"nm_id": int(nm_id) if nm_id else None, "q": q, "brand": brand,
                        "category": category, "date_from": date_from, "date_to": date_to,
                        "metric": metric, "level": level, "resolved_ids": 0}
        if ids is not None and not ids:
            return {"level": level, "metric": metric, "items": [],
                    "total": {"qty": 0, "sum_for_pay": 0.0},
                    "hint": "по маске/бренду/категории ничего не найдено",
                    "params": empty_params}

        where = ["d.supplier_oper_name = 'Продажа'",
                 "d.sale_dt BETWEEN :df AND :dt",
                 "d.ppvz_office_id IS NOT NULL",
                 "p.lat IS NOT NULL", "p.lon IS NOT NULL"]
        params: dict = {
            "df": f"{date_from} 00:00:00", "dt": f"{date_to} 23:59:59",
        }
        if ids is not None:
            where.append(f"d.nm_id IN ({','.join(str(int(x)) for x in ids)})")
        if self.company_id is not None:
            where.append("d.company_id = :cid")
            params["cid"] = self.company_id
        box = None if world else _parse_bbox(bbox)
        if box:
            s, w, n, ee = box
            where.append("p.lat BETWEEN :s AND :n AND p.lon BETWEEN :w AND :e")
            params.update({"s": s, "n": n, "w": w, "e": ee})
        if parent_country:
            # коды в нижнем регистре (чистит pvz_norm.py) — прямое равенство по индексу
            where.append("p.country = :pc")
            params["pc"] = str(parent_country).lower()[:2]
        if parent_okrug and not parent_region and not parent_city:
            regs = await self._regions_of_okrug(parent_okrug)
            if regs:
                in_list = ",".join("'" + r.replace("'", "''") + "'" for r in regs)
                where.append(f"p.region_norm IN ({in_list})")
            else:
                where.append("1 = 0")
        if parent_region:
            if parent_region == "__none__":
                where.append("p.region_norm IS NULL")
            else:
                # крошка — имя из выдачи (= норма), сравнение plain-колонки
                where.append("p.region_norm = :pr")
                params["pr"] = parent_region
        if parent_city:
            if parent_city == "__none__":
                where.append("p.city_norm IS NULL")
            else:
                where.append("p.city_norm = :pct")
                params["pct"] = parent_city
        # office-first: при узком parent-фильтре идем точечными пробами
        # (company, supplier, ppvz, sale_dt) вместо скана всего периода
        offices = await self._offices_for_parent(
            parent_country, parent_okrug, parent_region, parent_city)
        if offices is not None:
            if not offices:
                return {"level": level, "metric": metric, "items": [],
                        "total": {"qty": 0, "sum_for_pay": 0.0, "sum_amount": 0.0},
                        "hint": "в parent-области нет офисов",
                        "params": {**empty_params, "offices": 0}}
            if len(offices) <= self.OFFICE_IN_LIMIT:
                where.append(f"d.ppvz_office_id IN ({','.join(str(x) for x in offices)})")
                empty_params["offices"] = len(offices)
        where_sql = " AND ".join(where)
        order = "qty DESC" if metric == "qty" else "sum_amount DESC"

        if level == "country":
            select = ("UPPER(p.country) AS k, UPPER(p.country) AS name, '' AS sub, "
                      "NULL AS addr, AVG(p.lat) AS lat, AVG(p.lon) AS lon")
            group = "UPPER(p.country)"
            items = [self._shape(r) for r in
                     await self._grain(select, group, where_sql, params, order, limit)]
            for d in items:
                code = str(d["name"] or "").upper()
                d["name"] = COUNTRY_NAMES.get(code, code or "—")
                d["sub"] = ""
                anchor = COUNTRY_ANCHOR.get(code)
                if anchor is not None:
                    d["lat"], d["lon"] = anchor
        elif level == "okrug":
            select, group = self._region_select_group()
            rows = await self._grain(select, group, where_sql, params, order, limit)
            mapped = []
            for r in rows:
                code = str(r.get("cc") or "").upper()
                mapped.append({**r, "sub": code,
                               "name": r.get("rn") or "Без региона"})
            items = self._fold_okrug(mapped, metric)
        elif level == "region":
            select, group = self._region_select_group()
            items = [self._shape_region(r) for r in
                     await self._grain(select, group, where_sql, params, order, limit)]
        elif level == "city":
            select, group = self._city_select_group()
            items = [self._shape_city(r) for r in
                     await self._grain(select, group, where_sql, params, order, limit)]
        else:
            select = ("CAST(p.wb_id AS CHAR) AS k, "
                      "CONCAT('ПВЗ ', CAST(p.wb_id AS CHAR)) AS name, "
                      "COALESCE(NULLIF(p.address, ''), '') AS sub, "
                      "COALESCE(NULLIF(p.address, ''), '') AS addr, "
                      "p.lat AS lat, p.lon AS lon")
            group = ("CAST(p.wb_id AS CHAR), CONCAT('ПВЗ ', CAST(p.wb_id AS CHAR)), "
                     "COALESCE(NULLIF(p.address, ''), ''), p.lat, p.lon")
            items = [self._shape(r) for r in
                     await self._grain(select, group, where_sql, params, order, limit)]

        tot = (await self.db.execute(text(f"""
            SELECT COUNT(*) AS qty, SUM(COALESCE(d.ppvz_for_pay, 0)) AS s,
                   SUM(COALESCE(d.retail_amount, 0)) AS a
            FROM detail_by_period d
            JOIN pvz_all p ON p.wb_id = d.ppvz_office_id
            WHERE {where_sql}"""), params)).mappings().first() or {}

        return {
            "level": level, "metric": metric,
            "items": items,
            "total": {"qty": int((tot or {}).get("qty") or 0),
                      "sum_for_pay": float((tot or {}).get("s") or 0),
                      "sum_amount": float((tot or {}).get("a") or 0),
                      "points": len(items)},
            "bbox_applied": bool(box),
            "params": {"nm_id": int(nm_id) if nm_id else None, "q": q, "brand": brand,
                       "category": category, "date_from": date_from, "date_to": date_to,
                       "metric": metric, "level": level,
                       "resolved_ids": len(ids) if ids is not None else None},
        }
