"""Отчеты склада (порт StockReportService, Yii2): наличие / оборотка / карточка / неликвиды.

Отличия от PHP (осознанные):
  * серверная пагинация LIMIT/OFFSET (в PHP вся таблица тянулась в память);
  * оборотка - ОДИН проход агрегации по ledger вместо трех подзапросов;
  * поиск q - LIMIT + разбор в Python (в PHP LIKE '%q%' по wbcards.title без индекса);
  * история «Наличия» по складу - рабочая (в PHP был опечатан JOIN, запрос падал).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.like_mask import escape_like


class StockReportService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _cid(self) -> str:
        return "" if self.company_id is None else " AND company_id = :cid"

    def _params(self) -> dict:
        return {} if self.company_id is None else {"cid": self.company_id}

    async def warehouses(self) -> list[dict]:
        rows = (await self.db.execute(text("""
            SELECT id, name, code, is_central, is_fbs, is_active
            FROM our_warehouse
            WHERE (:cid IS NULL OR company_id = :cid) AND is_active = 1
            ORDER BY name ASC"""), {"cid": self.company_id})).mappings().all()
        return [dict(r) for r in rows]

    async def _cards_page(self, q: str | None, page: int = 1,
                          page_size: int = 100) -> dict:
        """Пагинированный список SKU компании (LIMIT/OFFSET в SQL, память не собираем).

        Возвращает {rows, total}: total = число SKU компании (без фильтра
        по остаткам) - pages по SKU, фильтры остатков крутятся уже по странице.
        """
        where = " AND c.company_id = :cid"
        params: dict = {"cid": self.company_id}
        q = (q or "").strip()
        if q:
            where += (" AND (s.sku LIKE :like OR c.vendorCode LIKE :like"
                      " OR c.title LIKE :like OR CAST(c.nmID AS CHAR) LIKE :like)")
            params["like"] = f"%{escape_like(q)}%"
        total = (await self.db.execute(text(f"""
            SELECT COUNT(*)
            FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            WHERE 1=1{where}"""), params)).scalar() or 0
        rows = (await self.db.execute(text(f"""
            SELECT s.sku, s.nmID, s.chrtID, c.vendorCode, c.title
            FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            WHERE 1=1{where}
            ORDER BY c.vendorCode ASC, s.sku ASC
            LIMIT :lim OFFSET :off"""),
            {**params, "lim": page_size, "off": max(0, (page - 1) * page_size)}
        )).mappings().all()
        return {"rows": [dict(r) for r in rows], "total": int(total)}

    # --- 1. Наличие ------------------------------------------------------
    async def balance(self, warehouse_id: str | None = "all", on_date: str | None = None,
                      q: str | None = None, only_available: bool = False,
                      page: int = 1, page_size: int = 100) -> dict:
        """Остатки на складе (или на дату в прошлом - по ledger).

        Страница SKU берется из SQL (LIMIT/OFFSET), остатки - одним запросом
        `sku IN (страница)`. total = число SKU компании; фильтр only_available
        применяется к уже выбранной странице (страница может быть пустой).
        """
        is_history = False
        if on_date:
            try:
                d = datetime.fromisoformat(on_date.replace("T", " "))
            except ValueError:
                d = None
            if d is not None and d.date() < date.today():
                is_history = True
        wh = None if (not warehouse_id or warehouse_id == "all") else int(warehouse_id)

        page_cards = await self._cards_page(q, page, page_size)
        total = page_cards["total"]
        skus = [c["sku"] for c in page_cards["rows"]]
        rows: list[dict] = []
        if skus:
            skus_bind = bindparam("skus", expanding=True)
            if is_history:
                dt = on_date.replace("T", " ")
                if len(dt) == 10:
                    dt += " 00:00:00"
                wh_sql = " AND warehouseId = :wid" if wh else ""
                agg = (await self.db.execute(text(f"""
                    SELECT sku, SUM(qty_delta) AS qty
                    FROM wb_stock_ledger
                    WHERE company_id = :cid AND sku IN :skus
                      AND created_at <= :dt{wh_sql}
                    GROUP BY sku""").bindparams(skus_bind),
                    {"cid": self.company_id, "skus": skus, "dt": dt,
                     **({"wid": wh} if wh else {})}
                )).mappings().all()
                qty_by_sku = {r["sku"]: int(r["qty"] or 0) for r in agg}
                for c in page_cards["rows"]:
                    qty = qty_by_sku.get(c["sku"], 0)
                    if only_available and qty <= 0:
                        continue
                    rows.append({**c, "warehouse_id": wh, "warehouse_name": None,
                                 "quantity": qty})
            else:
                wh_sql = " AND warehouseId = :wid" if wh else ""
                bal = (await self.db.execute(text(f"""
                    SELECT sku, warehouseId, quantity
                    FROM wb_stock_balance
                    WHERE company_id = :cid AND sku IN :skus{wh_sql}""").bindparams(skus_bind),
                    {"cid": self.company_id, "skus": skus,
                     **({"wid": wh} if wh else {})}
                )).mappings().all()
                if wh:
                    by_sku = {r["sku"]: int(r["quantity"] or 0) for r in bal}
                    for c in page_cards["rows"]:
                        qty = by_sku.get(c["sku"], 0)
                        if only_available and qty <= 0:
                            continue
                        rows.append({**c, "warehouse_id": wh,
                                     "warehouse_name": None, "quantity": qty})
                else:
                    by_sku: dict[str, list] = {}
                    for r in bal:
                        by_sku.setdefault(r["sku"], []).append(r)
                    wh_names = {int(r["id"]): r["name"] for r in (
                        await self.db.execute(text(
                            "SELECT id, name FROM our_warehouse WHERE is_active = 1")
                        )).mappings().all()}
                    for c in page_cards["rows"]:
                        items = by_sku.get(c["sku"]) or []
                        if not items:
                            if only_available:
                                continue
                            rows.append({**c, "warehouse_id": None,
                                         "warehouse_name": None, "quantity": 0})
                            continue
                        for r in items:
                            qty = int(r["quantity"] or 0)
                            if only_available and qty <= 0:
                                continue
                            rows.append({**c, "warehouse_id": r["warehouseId"],
                                         "warehouse_name": wh_names.get(
                                             int(r["warehouseId"] or 0)),
                                         "quantity": qty})

        return {"rows": rows, "total": total, "page": page,
                "page_size": page_size, "is_history": is_history}

    # --- 2. Оборотная ведомость ------------------------------------------
    async def turnover(self, warehouse_id: str | None = "all",
                       date_from: str | None = None, date_to: str | None = None,
                       q: str | None = None, page: int = 1, page_size: int = 100) -> dict:
        """Оборотная ведомость.

        Страница SKU - из SQL; агрегация ledger - ОДИН проход по странице
        (`sku IN (страница)`), а не по всему ledger компании.
        total = число SKU компании.
        """
        wh = None if (not warehouse_id or warehouse_id == "all") else int(warehouse_id)
        today = date.today()
        d1 = date_from or today.replace(day=1).isoformat()
        d2 = date_to or today.isoformat()
        d1_dt = f"{d1} 00:00:00"
        d2_dt = f"{d2} 23:59:59"

        page_cards = await self._cards_page(q, page, page_size)
        total = page_cards["total"]
        skus = [c["sku"] for c in page_cards["rows"]]

        rows: list[dict] = []
        if skus:
            wh_sql = " AND warehouseId = :wid" if wh else ""
            params = {"cid": self.company_id, "d1": d1_dt, "d2": d2_dt, "skus": skus}
            if wh:
                params["wid"] = wh
            # ОДИН проход агрегации по ledger для SKU страницы
            agg = (await self.db.execute(text(f"""
                SELECT sku,
                       SUM(CASE WHEN created_at < :d1 THEN qty_delta ELSE 0 END) AS start_qty,
                       SUM(CASE WHEN created_at <= :d2 THEN qty_delta ELSE 0 END) AS end_qty,
                       SUM(CASE WHEN created_at BETWEEN :d1 AND :d2 AND doc_type = 'RECEIPT'
                                THEN qty_delta ELSE 0 END) AS receipt,
                       SUM(CASE WHEN created_at BETWEEN :d1 AND :d2 AND doc_type = 'EXPENSE'
                                THEN -qty_delta ELSE 0 END) AS expense,
                       SUM(CASE WHEN created_at BETWEEN :d1 AND :d2 AND doc_type = 'TRANSFER'
                                         AND qty_delta > 0 THEN qty_delta ELSE 0 END) AS t_in,
                       SUM(CASE WHEN created_at BETWEEN :d1 AND :d2 AND doc_type = 'TRANSFER'
                                         AND qty_delta < 0 THEN -qty_delta ELSE 0 END) AS t_out,
                       SUM(CASE WHEN created_at BETWEEN :d1 AND :d2 AND doc_type = 'INVENTORY'
                                THEN qty_delta ELSE 0 END) AS inv,
                       SUM(CASE WHEN created_at BETWEEN :d1 AND :d2 AND doc_type = 'ADJUSTMENT'
                                THEN qty_delta ELSE 0 END) AS adj
                FROM wb_stock_ledger
                WHERE company_id = :cid AND sku IN :skus AND created_at <= :d2{wh_sql}
                GROUP BY sku""").bindparams(bindparam("skus", expanding=True)),
                params)).mappings().all()
            by_sku = {r["sku"]: dict(r) for r in agg}

            for c in page_cards["rows"]:
                a = by_sku.get(c["sku"])
                if not a:
                    continue
                start_qty = int(a["start_qty"] or 0)
                end_qty = int(a["end_qty"] or 0)
                receipt = int(a["receipt"] or 0)
                expense = int(a["expense"] or 0)
                t_in = int(a["t_in"] or 0)
                t_out = int(a["t_out"] or 0)
                inv = int(a["inv"] or 0)
                adj = int(a["adj"] or 0)
                turnover = receipt + expense + t_in + t_out + abs(inv) + abs(adj)
                if not (start_qty or end_qty or turnover):
                    continue
                rows.append({**c, "start_qty": start_qty, "end_qty": end_qty,
                             "receipt": receipt, "expense": expense, "t_in": t_in,
                             "t_out": t_out, "inv": inv, "adj": adj, "turnover": turnover})

        return {"rows": rows, "total": total, "page": page, "page_size": page_size,
                "date_from": d1, "date_to": d2}

    # --- 3. Карточка товара ----------------------------------------------
    async def card(self, term: str, warehouse_id: str | None = "all",
                   date_from: str | None = None, date_to: str | None = None,
                   limit: int = 500) -> dict:
        term = (term or "").strip()
        if not term:
            return {"rows": [], "skus": [], "total": 0}
        like = f"%{escape_like(term)}%"
        sku_rows = (await self.db.execute(text("""
            SELECT s.sku FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            WHERE c.company_id = :cid
              AND (s.sku LIKE :like OR c.vendorCode LIKE :like OR c.title LIKE :like
                   OR CAST(c.nmID AS CHAR) LIKE :like)
            ORDER BY c.vendorCode ASC
            LIMIT 50"""),
            {"cid": self.company_id, "like": like})).mappings().all()
        skus = [r["sku"] for r in sku_rows] or [term]
        wh = None if (not warehouse_id or warehouse_id == "all") else int(warehouse_id)

        where = " AND l.company_id = :cid AND l.sku IN :skus"
        params: dict = {"cid": self.company_id, "skus": skus, "lim": limit}
        if wh:
            where += " AND l.warehouseId = :wid"
            params["wid"] = wh
        if date_from:
            where += " AND l.created_at >= :df"
            params["df"] = f"{date_from} 00:00:00"
        if date_to:
            where += " AND l.created_at <= :dt"
            params["dt"] = f"{date_to} 23:59:59"
        stmt = text(f"""
            SELECT l.id, l.created_at, l.doc_type, l.doc_id, l.warehouseId,
                   w.name AS warehouse_name, l.sku, c.vendorCode, c.title,
                   l.qty_delta, l.qty_before, l.qty_after, u.username
            FROM wb_stock_ledger l
            LEFT JOIN our_warehouse w ON w.id = l.warehouseId
            LEFT JOIN `user` u ON u.id = l.user_id
            LEFT JOIN wbcards_sizes s ON s.sku = l.sku
            LEFT JOIN wbcards c ON c.nmID = s.nmID
            WHERE 1=1{where}
            ORDER BY l.created_at ASC, l.id ASC
            LIMIT :lim""").bindparams(bindparam("skus", expanding=True))
        rows = (await self.db.execute(stmt, params)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["created_at"] = str(d["created_at"] or "")
            out.append(d)
        return {"rows": out, "skus": skus, "total": len(out)}

    # --- 4. Неликвиды -----------------------------------------------------
    async def nonliquid(self, warehouse_id: str | None = "all", days: int = 30,
                         q: str | None = None, page: int = 1, page_size: int = 100) -> dict:
        """Неликвиды: остаток есть, движений нет дольше N дней.

        ОДИН проход агрегации по ledger (последнее движение по sku), далее
        фильтр по остаткам в Python и пагинация. Селект по странице не делаем,
        потому что total нужен по всем неликвидам сразу.
        """
        days = max(1, min(int(days or 30), 365))
        threshold = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        wh = None if (not warehouse_id or warehouse_id == "all") else int(warehouse_id)
        wh_led = " AND warehouseId = :wid" if wh else ""
        params: dict = {"cid": self.company_id, "thr": threshold}
        if wh:
            params["wid"] = wh

        # 1) последнее движение по sku - один проход по ledger
        last_m = (await self.db.execute(text(f"""
            SELECT sku, MAX(created_at) AS last_move
            FROM wb_stock_ledger
            WHERE company_id = :cid{wh_led}
            GROUP BY sku"""), params)).mappings().all()
        last_move = {r["sku"]: str(r["last_move"] or "") for r in last_m}

        # 2) остатки с карточкой (без ledger-подзапроса)
        wh_bal = " AND b.warehouseId = :wid" if wh else ""
        bal = (await self.db.execute(text(f"""
            SELECT s.sku, s.nmID, s.chrtID, c.vendorCode, c.title,
                   b.warehouseId AS wid, b.quantity
            FROM wb_stock_balance b
            INNER JOIN wbcards_sizes s ON s.sku = b.sku
            INNER JOIN wbcards c ON c.nmID = s.nmID
            WHERE b.company_id = :cid{wh_bal} AND b.quantity > 0"""), params)).mappings().all()

        rows = []
        q_low = (q or "").strip().lower()
        for r in bal:
            lm = last_move.get(r["sku"])
            if lm is not None and lm >= threshold:
                continue  # движение было недавно - ликвид
            d = dict(r)
            if q_low and not (
                    q_low in (r["sku"] or "").lower()
                    or q_low in (r["vendorCode"] or "").lower()
                    or q_low in (r["title"] or "").lower()):
                continue
            d["last_move"] = lm or ""
            rows.append(d)
        # NULL last_move раньше всех (как ORDER BY ... ASC в MySQL)
        rows.sort(key=lambda r: (r["last_move"] or "",
                                 r["vendorCode"] or "", r["sku"] or ""))
        total = len(rows)
        start = max(0, (page - 1) * page_size)
        rows = rows[start:start + page_size]
        # имя склада одним запросом
        wh_ids = {int(r["wid"]) for r in rows if r["wid"] is not None}
        wh_names: dict[int, str] = {}
        if wh_ids:
            wh_rows = (await self.db.execute(text(
                "SELECT id, name FROM our_warehouse WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
                {"ids": sorted(wh_ids)})).mappings().all()
            wh_names = {int(r["id"]): r["name"] for r in wh_rows}
        out = []
        for r in rows:
            d = dict(r)
            d["warehouse_name"] = wh_names.get(int(r["wid"] or 0))
            out.append(d)
        return {"rows": out, "total": total, "page": page, "page_size": page_size,
                "days": days}
