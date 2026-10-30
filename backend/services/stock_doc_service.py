"""Документы склада (wb_doc / wb_doc_item) - порт WbDocController (Yii2).

Типы: RECEIPT / EXPENSE / TRANSFER / INVENTORY / ADJUSTMENT.
Статусы: draft -> posted -> canceled.

Проводка идёт через backend/services/stock_service (apply/transfer):
  RECEIPT/EXPENSE  - +/- qty на складе документа;
  TRANSFER         - две проводки (откуда -qty, куда +qty) в одной транзакции;
  INVENTORY        - дельта (факт - по учету), строки с нулевой дельтой не пишутся;
  ADJUSTMENT       - знаковая дельта из qty.

Отмена = сторно: берём проведенные строки ledger по документу и пишем обратные
проводки с doc_type = <TYPE>_CANCEL. Это точнее, чем пересчёт дельт в PHP
(там fallback qty_before при отмене инвентаризации = 0, из-за чего сторно
иногда не равно проведению).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import stock_service
from backend.services.like_mask import escape_like

TYPES = ("RECEIPT", "EXPENSE", "TRANSFER", "INVENTORY", "ADJUSTMENT")
TYPE_LABELS = {
    "RECEIPT": "Приход",
    "EXPENSE": "Расход",
    "TRANSFER": "Перемещение",
    "INVENTORY": "Инвентаризация",
    "ADJUSTMENT": "Корректировка",
}
STATUS_LABELS = {"draft": "Черновик", "posted": "Проведен", "canceled": "Отменен"}


def _norm_date(value: Any) -> str:
    """'2026-09-09T14:30' | '2026-09-09 14:30' -> 'YYYY-MM-DD HH:MM:SS'."""
    if not value:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s = str(value).strip().replace("T", " ")
    if len(s) == 16:
        s += ":00"
    if len(s) == 10:
        s += " 00:00:00"
    return s


class DocError(Exception):
    """Ошибка бизнес-логики документа (показываем пользователю)."""


class StockDocService:
    def __init__(self, db: AsyncSession, company_id: int | None = None,
                 user_id: int | None = None):
        self.db = db
        self.company_id = company_id
        self.user_id = user_id

    # --- чтение -------------------------------------------------------
    async def list(self, doc_type: str | None = None, page: int = 1,
                   page_size: int = 20) -> dict:
        where = " AND d.company_id = :cid" if self.company_id is not None else ""
        params: dict = {"cid": self.company_id} if self.company_id is not None else {}
        if doc_type:
            where += " AND d.type = :type"
            params["type"] = doc_type
        total = (await self.db.execute(text(
            f"SELECT COUNT(*) FROM wb_doc d WHERE 1=1{where}"), params)).scalar() or 0
        rows = (await self.db.execute(text(f"""
            SELECT d.id, d.type, d.status, d.warehouseId, d.to_warehouseId, d.date,
                   d.comment, d.user_id,
                   w.name AS warehouse_name, tw.name AS to_warehouse_name,
                   (SELECT COUNT(*) FROM wb_doc_item i WHERE i.doc_id = d.id) AS items_count
            FROM wb_doc d
            LEFT JOIN our_warehouse w ON w.id = d.warehouseId
            LEFT JOIN our_warehouse tw ON tw.id = d.to_warehouseId
            WHERE 1=1{where}
            ORDER BY d.date DESC, d.id DESC
            LIMIT :lim OFFSET :off"""),
            {**params, "lim": page_size, "off": max(0, (page - 1) * page_size)}
        )).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["type_label"] = TYPE_LABELS.get(d["type"], d["type"])
            d["status_label"] = STATUS_LABELS.get(d["status"], d["status"])
            d["date"] = str(d["date"] or "")
            out.append(d)
        return {"rows": out, "total": int(total), "page": page, "page_size": page_size}

    async def get(self, doc_id: int) -> dict | None:
        row = (await self.db.execute(text("""
            SELECT d.id, d.company_id, d.type, d.status, d.warehouseId, d.to_warehouseId,
                   d.date, d.comment, d.user_id,
                   w.name AS warehouse_name, tw.name AS to_warehouse_name
            FROM wb_doc d
            LEFT JOIN our_warehouse w ON w.id = d.warehouseId
            LEFT JOIN our_warehouse tw ON tw.id = d.to_warehouseId
            WHERE d.id = :id AND (:cid IS NULL OR d.company_id = :cid)
            LIMIT 1"""),
            {"id": doc_id, "cid": self.company_id})).mappings().first()
        if not row:
            return None
        doc = dict(row)
        items = (await self.db.execute(text("""
            SELECT i.id, i.sku, i.nmID, i.chrtID, i.qty, i.qty_before, i.qty_fact, i.price,
                   c.vendorCode, c.title, s.nmID AS s_nmID
            FROM wb_doc_item i
            LEFT JOIN wbcards_sizes s ON s.sku = i.sku
            LEFT JOIN wbcards c ON c.nmID = s.nmID
                 AND (:cid IS NULL OR c.company_id = :cid)
            WHERE i.doc_id = :id
            ORDER BY i.id ASC"""), {"id": doc_id, "cid": self.company_id})).mappings().all()
        doc["items"] = [dict(i) for i in items]
        doc["type_label"] = TYPE_LABELS.get(doc["type"], doc["type"])
        doc["status_label"] = STATUS_LABELS.get(doc["status"], doc["status"])
        doc["date"] = str(doc["date"] or "")
        return doc

    async def warehouses(self) -> list[dict]:
        rows = (await self.db.execute(text("""
            SELECT id, name, code, is_central, is_fbs, is_active
            FROM our_warehouse
            WHERE (:cid IS NULL OR company_id = :cid) AND is_active = 1
            ORDER BY name ASC"""), {"cid": self.company_id})).mappings().all()
        return [dict(r) for r in rows]

    # --- позиции -------------------------------------------------------
    async def _save_items(self, doc_id: int, items: list[dict]) -> None:
        await self.db.execute(text("DELETE FROM wb_doc_item WHERE doc_id = :d"),
                              {"d": doc_id})
        for it in items or []:
            sku = str(it.get("sku") or "").strip()
            if not sku:
                continue
            qty = it.get("qty")
            qty_before = it.get("qty_before")
            qty_fact = it.get("qty_fact")
            price = it.get("price")
            await self.db.execute(text("""
                INSERT INTO wb_doc_item(doc_id, sku, nmID, chrtID, qty, qty_before, qty_fact, price)
                VALUES(:d, :sku, :nm, :ch, :qty, :before, :fact, :price)"""),
                {"d": doc_id, "sku": sku, "nm": it.get("nm_id"), "ch": it.get("chrt_id"),
                 "qty": int(qty or 0),
                 "before": int(qty_before) if qty_before is not None else None,
                 "fact": int(qty_fact) if qty_fact is not None else None,
                 "price": price})

    async def _resolve_size(self, sku: str) -> tuple[int | None, int | None]:
        row = (await self.db.execute(text(
            "SELECT nmID, chrtID FROM wbcards_sizes WHERE sku = :s LIMIT 1"),
            {"s": sku})).first()
        return (int(row[0]) if row and row[0] is not None else None,
                int(row[1]) if row and row[1] is not None else None)

    async def _prepare_items(self, doc_type: int | str, warehouse_id: int,
                             raw_items: list[dict]) -> list[dict]:
        """Готовит строки документа по типу (как в PHP create/update)."""
        out: list[dict] = []
        for it in raw_items or []:
            sku = str(it.get("sku") or "").strip()
            if not sku:
                continue
            nm, chrt = await self._resolve_size(sku)
            base = {"sku": sku, "nm_id": nm, "chrt_id": chrt, "price": it.get("price")}
            if doc_type == "INVENTORY":
                qty_fact = it.get("qty_fact")
                if qty_fact is None or qty_fact == "":
                    qty_fact = it.get("qty")
                if qty_fact is None or qty_fact == "":
                    continue
                qty_before = it.get("qty_before")
                if qty_before is None or qty_before == "":
                    qty_before = await stock_service.get_balance(
                        self.db, self.company_id, warehouse_id, sku)
                out.append({**base, "qty": int(qty_fact or 0),
                            "qty_before": int(qty_before or 0),
                            "qty_fact": int(qty_fact or 0)})
            elif doc_type == "ADJUSTMENT":
                qty = it.get("qty")
                if qty is None or qty == "":
                    continue
                delta = int(qty)
                if delta == 0:
                    continue
                out.append({**base, "qty": delta})
            else:  # RECEIPT / EXPENSE / TRANSFER
                qty = it.get("qty")
                if qty is None or qty == "":
                    continue
                out.append({**base, "qty": int(qty)})
        return out

    # --- create / update ------------------------------------------------
    async def create(self, payload: dict) -> dict:
        doc_type = str(payload.get("type") or "RECEIPT").upper()
        if doc_type not in TYPES:
            raise DocError("Неизвестный тип документа")
        if self.company_id is None:
            raise DocError("Не выбрана компания")
        wh_id = int(payload.get("warehouse_id") or 0)
        if not wh_id:
            raise DocError("Не указан склад")
        to_wh = payload.get("to_warehouse_id")
        to_wh = int(to_wh) if to_wh else None
        comment = (payload.get("comment") or "").strip() or None
        if doc_type == "TRANSFER":
            if not to_wh:
                raise DocError('Укажите склад "куда"')
            if to_wh == wh_id:
                raise DocError('Склады "откуда" и "куда" должны отличаться')
        if doc_type == "ADJUSTMENT" and not comment:
            raise DocError("Укажите причину корректировки")

        items = await self._prepare_items(doc_type, wh_id, payload.get("items") or [])
        doc_id = (await self.db.execute(text("""
            INSERT INTO wb_doc(company_id, type, status, warehouseId, to_warehouseId,
                               date, comment, user_id)
            VALUES(:cid, :type, 'draft', :wh, :towh, :date, :comment, :uid)"""),
            {"cid": self.company_id, "type": doc_type, "wh": wh_id, "towh": to_wh,
             "date": _norm_date(payload.get("date")), "comment": comment,
             "uid": self.user_id})).lastrowid
        await self._save_items(int(doc_id), items)
        await self.db.commit()
        return await self.get(int(doc_id)) or {}

    async def update(self, doc_id: int, payload: dict) -> dict:
        doc = await self.get(doc_id)
        if not doc:
            raise DocError("Документ не найден")
        if doc["status"] not in ("draft", "canceled"):
            raise DocError("Редактировать можно только черновик или отмененный")
        doc_type = str(payload.get("type") or doc["type"]).upper()
        if doc_type not in TYPES:
            raise DocError("Неизвестный тип документа")
        wh_id = int(payload.get("warehouse_id") or doc["warehouseId"] or 0)
        to_wh = payload.get("to_warehouse_id")
        to_wh = int(to_wh) if to_wh else None
        comment = (payload.get("comment") or "").strip() or None
        if doc_type == "TRANSFER":
            if not to_wh:
                raise DocError('Укажите склад "куда"')
            if to_wh == wh_id:
                raise DocError('Склады "откуда" и "куда" должны отличаться')
        if doc_type == "ADJUSTMENT" and not comment:
            raise DocError("Укажите причину корректировки")

        items = await self._prepare_items(doc_type, wh_id, payload.get("items") or [])
        await self.db.execute(text("""
            UPDATE wb_doc SET type = :type, warehouseId = :wh, to_warehouseId = :towh,
                   date = :date, comment = :comment, status = 'draft'
            WHERE id = :id"""),
            {"id": doc_id, "type": doc_type, "wh": wh_id, "towh": to_wh,
             "date": _norm_date(payload.get("date") or doc["date"]),
             "comment": comment})
        await self._save_items(doc_id, items)
        await self.db.commit()
        return await self.get(doc_id) or {}

    async def delete(self, doc_id: int) -> None:
        doc = await self.get(doc_id)
        if not doc:
            raise DocError("Документ не найден")
        if doc["status"] not in ("draft", "canceled"):
            raise DocError("Удалить можно только черновик/отмененный")
        await self.db.execute(text("DELETE FROM wb_doc_item WHERE doc_id = :d"),
                              {"d": doc_id})
        await self.db.execute(text("DELETE FROM wb_doc WHERE id = :d"), {"d": doc_id})
        await self.db.commit()

    # --- проведение / отмена -------------------------------------------
    async def post(self, doc_id: int) -> dict:
        doc = await self.get(doc_id)
        if not doc:
            raise DocError("Документ не найден")
        if doc["status"] != "draft":
            raise DocError("Только черновик можно провести")
        doc_type = doc["type"]
        cid = int(doc["company_id"]) if doc["company_id"] is not None else self.company_id
        if cid is None:
            raise DocError("Не выбрана компания")
        wh_id = int(doc["warehouseId"])
        items = doc["items"] or []

        if doc_type == "TRANSFER":
            to_wh = int(doc["to_warehouseId"] or 0)
            res = await stock_service.transfer(
                self.db, cid, wh_id, to_wh, "TRANSFER", doc_id,
                [(i["sku"], int(i["qty"] or 0)) for i in items],
                self.user_id, allow_negative=False)
        elif doc_type == "INVENTORY":
            deltas = []
            for i in items:
                fact = i.get("qty_fact")
                fact = int(fact) if fact is not None else int(i.get("qty") or 0)
                before = i.get("qty_before")
                if before is None:
                    before = await stock_service.get_balance(
                        self.db, cid, wh_id, i["sku"])
                d = fact - int(before)
                if d != 0:
                    deltas.append((i["sku"], d))
            if not deltas:
                await self.db.execute(text(
                    "UPDATE wb_doc SET status = 'posted' WHERE id = :id"), {"id": doc_id})
                await self.db.commit()
                return {"ok": True, "message": "Инвентаризация проведена — расхождений нет"}
            res = await stock_service.apply(
                self.db, cid, wh_id, "INVENTORY", doc_id, deltas, self.user_id,
                allow_negative=False)
        elif doc_type == "ADJUSTMENT":
            if not items:
                raise DocError("Нет строк для корректировки")
            res = await stock_service.apply(
                self.db, cid, wh_id, "ADJUSTMENT", doc_id,
                [(i["sku"], int(i["qty"] or 0)) for i in items],
                self.user_id, allow_negative=False)
        else:  # RECEIPT / EXPENSE
            sign = 1 if doc_type == "RECEIPT" else -1
            res = await stock_service.apply(
                self.db, cid, wh_id, doc_type, doc_id,
                [(i["sku"], sign * int(i["qty"] or 0)) for i in items],
                self.user_id, allow_negative=False)

        if not res.get("ok"):
            raise DocError(res.get("error") or "Ошибка проведения")
        await self.db.execute(text("UPDATE wb_doc SET status = 'posted' WHERE id = :id"),
                              {"id": doc_id})
        await self.db.commit()
        return {"ok": True, "message": "Документ проведен"}

    async def cancel(self, doc_id: int) -> dict:
        """Сторно: обратные проводки по проведенным строкам ledger."""
        doc = await self.get(doc_id)
        if not doc:
            raise DocError("Документ не найден")
        if doc["status"] != "posted":
            raise DocError("Только проведенный можно отменить")
        doc_type = doc["type"]
        cid = int(doc["company_id"]) if doc["company_id"] is not None else self.company_id
        if cid is None:
            raise DocError("Не выбрана компания")
        rows = (await self.db.execute(text("""
            SELECT warehouseId, sku, qty_delta FROM wb_stock_ledger
            WHERE company_id = :cid AND doc_id = :did AND doc_type = :dt
            ORDER BY id ASC"""),
            {"cid": cid, "did": doc_id, "dt": doc_type})).mappings().all()
        if not rows:
            await self.db.execute(text(
                "UPDATE wb_doc SET status = 'canceled' WHERE id = :id"), {"id": doc_id})
            await self.db.commit()
            return {"ok": True, "message": "Документ отменен (сторно не требуется)"}

        by_wh: dict[int, list[tuple[str, int]]] = {}
        for r in rows:
            by_wh.setdefault(int(r["warehouseId"]), []).append(
                (r["sku"], -int(r["qty_delta"] or 0)))
        res = await stock_service.apply_batch(
            self.db, cid, f"{doc_type}_CANCEL", doc_id,
            [(wh_id, items) for wh_id, items in by_wh.items()], self.user_id)
        if not res.get("ok"):
            raise DocError(res.get("error") or "Ошибка отмены")
        await self.db.execute(text(
            "UPDATE wb_doc SET status = 'canceled' WHERE id = :id"), {"id": doc_id})
        await self.db.commit()
        return {"ok": True, "message": "Документ отменен (сторно)"}

    # --- справочные выборки ---------------------------------------------
    async def balance(self, sku: str, warehouse_id: int) -> dict:
        qty = await stock_service.get_balance(self.db, self.company_id, warehouse_id, sku)
        return {"sku": sku, "warehouse_id": warehouse_id, "qty": qty}

    async def inventory_data(self, warehouse_id: int) -> list[dict]:
        rows = (await self.db.execute(text("""
            SELECT s.sku, s.nmID, s.chrtID, c.vendorCode, c.title,
                   COALESCE(b.quantity, 0) AS qty_before
            FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            LEFT JOIN wb_stock_balance b ON b.sku = s.sku
                 AND b.company_id = :cid AND b.warehouseId = :wid
            WHERE c.company_id = :cid
            ORDER BY c.vendorCode ASC, s.sku ASC
            LIMIT 5000"""),
            {"cid": self.company_id, "wid": warehouse_id})).mappings().all()
        return [dict(r) for r in rows]

    async def search_product(self, term: str, limit: int = 20) -> list[dict]:
        term = (term or "").strip()
        if len(term) < 2:
            return []
        like = f"%{escape_like(term)}%"
        rows = (await self.db.execute(text("""
            SELECT s.sku, s.nmID, s.chrtID, c.vendorCode, c.title, c.brand
            FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            WHERE c.company_id = :cid
              AND (s.sku LIKE :like OR c.vendorCode LIKE :like OR c.title LIKE :like)
            ORDER BY c.vendorCode ASC
            LIMIT :lim"""),
            {"cid": self.company_id, "like": like, "lim": limit})).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["label"] = f"{d.get('vendorCode') or ''} — {d.get('title') or ''} ({d.get('sku')})"
            out.append(d)
        return out
