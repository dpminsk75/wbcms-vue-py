"""Управление виртуальными складами FBS (порты WbFbsVirtualController, Yii2).

В py уже есть автоматика (deduct_sync_service): списание FBS-заказов из остатков
оперативного склада + выгрузка остатков в виртуальные склады WB. Здесь - UI-часть:

  * F1. Таблица остатков: все SKU компании, центральный остаток (is_central=1)
        и виртуальный (is_fbs=1), фильтры поиска/количества, серверная пагинация;
  * F2. Склады WB (wb_fbs_warehouse): тумблеры is_virtual / consider_orders;
  * F3. Импорт остатков из Excel (общий sku_resolver) -> превью -> запись в баланс;
  * F4. Ручная выгрузка остатков в WB + лог списаний (из wb_stock_ledger).

Особенности переноса ( consciously ):
  * PHP тянет всю таблицу wbcards_sizes без LIMIT и режет в PHP - здесь LIMIT/OFFSET;
  * правка виртуальных остатков идет через TRANSFER (центральный <-> оперативный),
    doc_type='fbs_virtual_adjust' (как в PHP), а не прямым UPDATE;
  * лог списаний берется из БД (ledger/orders), а не из файлов runtime/logs.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import stock_service
from backend.services.like_mask import escape_like
from backend.services.sku_resolver import SkuResolver

QTY_FILTERS = ("all", "not_found", "zero", "1_9")
WB_STOCKS_URL = "https://marketplace-api.wildberries.ru/api/v3/stocks/{wid}"
CHUNK = 1000


class FbsVirtualError(Exception):
    pass


class FbsVirtualService:
    def __init__(self, db: AsyncSession, company_id: int | None = None,
                 user_id: int | None = None):
        self.db = db
        self.company_id = company_id
        self.user_id = user_id

    def _cid(self) -> str:
        return "" if self.company_id is None else " AND company_id = :cid"

    def _params(self) -> dict:
        return {} if self.company_id is None else {"cid": self.company_id}

    # --- склады наши ----------------------------------------------------
    async def _our_warehouses(self) -> tuple[int | None, int | None]:
        if self.company_id is None:
            return None, None
        central = (await self.db.execute(text("""
            SELECT id FROM our_warehouse
            WHERE company_id = :cid AND is_central = 1 LIMIT 1"""),
            {"cid": self.company_id})).first()
        fbs = (await self.db.execute(text("""
            SELECT id FROM our_warehouse
            WHERE company_id = :cid AND is_fbs = 1 LIMIT 1"""),
            {"cid": self.company_id})).first()
        central_id = int(central[0]) if central else None
        fbs_id = int(fbs[0]) if fbs else None
        if central_id is None:
            row = (await self.db.execute(text("""
                SELECT id FROM our_warehouse
                WHERE company_id = :cid AND is_active = 1 ORDER BY id LIMIT 1"""),
                {"cid": self.company_id})).first()
            central_id = int(row[0]) if row else None
        if fbs_id is None:
            fbs_id = central_id
        return central_id, fbs_id

    # --- F1: таблица остатков -------------------------------------------
    async def stocks(self, q: str | None = None, qty: str = "all",
                     page: int = 1, page_size: int = 100) -> dict:
        if self.company_id is None:
            raise FbsVirtualError("Не выбрана компания")
        central_id, fbs_id = await self._our_warehouses()
        where = ["c.company_id = :cid"]
        params: dict = {"cid": self.company_id, "central": central_id, "fbs": fbs_id}
        q = (q or "").strip()
        if q:
            like = f"%{escape_like(q)}%"
            where.append("(s.sku LIKE :like OR c.vendorCode LIKE :like OR c.title LIKE :like"
                         " OR CAST(s.nmID AS CHAR) LIKE :like)")
            params["like"] = like
        if qty == "not_found":
            where.append("fb.quantity IS NULL")
        elif qty == "zero":
            where.append("fb.quantity = 0")
        elif qty == "1_9":
            where.append("fb.quantity BETWEEN 1 AND 9")
        where_sql = " AND ".join(where)

        total = (await self.db.execute(text(f"""
            SELECT COUNT(*)
            FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            LEFT JOIN wb_stock_balance fb ON fb.sku = s.sku
                 AND fb.company_id = :cid AND fb.warehouseId = :fbs
            WHERE {where_sql}"""), params)).scalar() or 0

        rows = (await self.db.execute(text(f"""
            SELECT s.sku, s.nmID, s.chrtID, c.vendorCode, c.title, c.brand,
                   cb.quantity AS central_qty, fb.quantity AS virtual_qty
            FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            LEFT JOIN wb_stock_balance cb ON cb.sku = s.sku
                 AND cb.company_id = :cid AND cb.warehouseId = :central
            LEFT JOIN wb_stock_balance fb ON fb.sku = s.sku
                 AND fb.company_id = :cid AND fb.warehouseId = :fbs
            WHERE {where_sql}
            ORDER BY c.vendorCode ASC, s.sku ASC
            LIMIT :lim OFFSET :off"""),
            {**params, "lim": page_size, "off": max(0, (page - 1) * page_size)}
        )).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["central_qty"] = int(d["central_qty"] or 0) if d["central_qty"] is not None else None
            d["virtual_qty"] = int(d["virtual_qty"] or 0) if d["virtual_qty"] is not None else None
            out.append(d)
        return {
            "rows": out,
            "total": int(total),
            "page": page,
            "page_size": page_size,
            "central_id": central_id,
            "fbs_id": fbs_id,
        }

    # --- F2: склады WB ---------------------------------------------------
    async def warehouses(self) -> list[dict]:
        rows = (await self.db.execute(text("""
            SELECT id, company_id, warehouseId, name, address, isActive, is_virtual,
                   is_deleting, is_processing, consider_orders, type
            FROM wb_fbs_warehouse
            WHERE is_deleting = 0 AND (:cid IS NULL OR company_id = :cid)
            ORDER BY name ASC"""), {"cid": self.company_id})).mappings().all()
        return [dict(r) for r in rows]

    async def toggle(self, wh_id: int, field: str) -> dict:
        if field not in ("is_virtual", "consider_orders"):
            raise FbsVirtualError(f"bad field: {field}")
        row = (await self.db.execute(text("""
            SELECT id, name FROM wb_fbs_warehouse
            WHERE id = :id AND (:cid IS NULL OR company_id = :cid) LIMIT 1"""),
            {"id": wh_id, "cid": self.company_id})).first()
        if not row:
            raise FbsVirtualError("Склад не найден")
        await self.db.execute(text(f"""
            UPDATE wb_fbs_warehouse SET {field} = 1 - IFNULL({field}, 0)
            WHERE id = :id AND (:cid IS NULL OR company_id = :cid)"""),
            {"id": wh_id, "cid": self.company_id})
        await self.db.commit()
        res = (await self.db.execute(text("""
            SELECT id, name, is_virtual, consider_orders FROM wb_fbs_warehouse
            WHERE id = :id LIMIT 1"""), {"id": wh_id})).mappings().first()
        return dict(res) if res else {}

    # --- F3: импорт остатков --------------------------------------------
    async def parse(self, rows: list[list]) -> dict:
        resolver = SkuResolver(self.db, self.company_id)
        matched, skipped = await resolver.parse_rows(rows)
        return {
            "success": True,
            "matched": [{"sku": m.sku, "nm_id": m.nm_id, "chrt_id": m.chrt_id, "qty": m.qty}
                        for m in matched],
            "skipped": skipped,
        }

    async def save_central(self, changes: list[dict]) -> dict:
        """Прямая проводка на центральный склад (doc_type=fbs_central_adjust)."""
        if self.company_id is None:
            raise FbsVirtualError("Не выбрана компания")
        central_id, _ = await self._our_warehouses()
        if not central_id:
            raise FbsVirtualError("Нет центрального склада (is_central=1)")
        items = []
        for c in changes or []:
            sku = str(c.get("sku") or "").strip()
            if not sku or c.get("qty") is None:
                continue
            new_qty = int(round(float(c["qty"])))
            old = await stock_service.get_balance(self.db, self.company_id, central_id, sku)
            delta = new_qty - old
            if delta != 0:
                items.append((sku, delta))
        if not items:
            return {"success": True, "processed": 0, "errors": []}
        res = await stock_service.apply(self.db, self.company_id, central_id,
                                        "fbs_central_adjust", None, items, self.user_id)
        if not res.get("ok"):
            raise FbsVirtualError(res.get("error") or "Ошибка сохранения")
        return {"success": True, "processed": len(items), "errors": []}

    async def save_virtual(self, changes: list[dict]) -> dict:
        """Правка виртуальных остатков - TRANSFER центральный <-> оперативный."""
        if self.company_id is None:
            raise FbsVirtualError("Не выбрана компания")
        central_id, fbs_id = await self._our_warehouses()
        if not central_id or not fbs_id:
            raise FbsVirtualError("Нет центрального/оперативного склада")
        plus: list[tuple[str, int]] = []
        minus: list[tuple[str, int]] = []
        for c in changes or []:
            sku = str(c.get("sku") or "").strip()
            if not sku or c.get("qty") is None:
                continue
            new_qty = int(round(float(c["qty"])))
            old = await stock_service.get_balance(self.db, self.company_id, fbs_id, sku)
            delta = new_qty - old
            if delta == 0:
                continue
            if delta > 0:
                plus.append((sku, delta))
            else:
                minus.append((sku, -delta))
        processed = 0
        if plus:
            res = await stock_service.transfer(self.db, self.company_id, central_id, fbs_id,
                                               "fbs_virtual_adjust", None, plus, self.user_id)
            if not res.get("ok"):
                raise FbsVirtualError(res.get("error") or "Ошибка сохранения")
            processed += len(plus)
        if minus:
            res = await stock_service.transfer(self.db, self.company_id, fbs_id, central_id,
                                               "fbs_virtual_adjust", None, minus, self.user_id)
            if not res.get("ok"):
                raise FbsVirtualError(res.get("error") or "Ошибка сохранения")
            processed += len(minus)
        return {"success": True, "processed": processed, "errors": []}

    async def delete_virtual(self, sku: str) -> dict:
        """Очистить позицию: остаток возвращается на центральный склад."""
        sku = (sku or "").strip()
        if not sku:
            raise FbsVirtualError("sku не передан")
        central_id, fbs_id = await self._our_warehouses()
        if not fbs_id:
            raise FbsVirtualError("Нет оперативного склада is_fbs")
        old = await stock_service.get_balance(self.db, self.company_id, fbs_id, sku)
        if old == 0:
            return {"success": True}
        res = await stock_service.transfer(self.db, self.company_id, fbs_id, central_id,
                                           "fbs_virtual_delete", None, [(sku, old)], self.user_id)
        if not res.get("ok"):
            raise FbsVirtualError(res.get("error") or "Ошибка удаления")
        return {"success": True}

    # --- F4: выгрузка в WB + лог -----------------------------------------
    async def _company_token(self) -> str:
        row = (await self.db.execute(text(
            "SELECT api_key FROM companies WHERE id = :cid LIMIT 1"),
            {"cid": self.company_id})).first()
        return str(row[0] or "") if row else ""

    async def _virtual_warehouses(self, wh_filter: str | None = None) -> list[dict]:
        rows = (await self.db.execute(text("""
            SELECT id, warehouseId, name FROM wb_fbs_warehouse
            WHERE company_id = :cid AND is_virtual = 1 AND is_deleting = 0
            ORDER BY name ASC"""), {"cid": self.company_id})).mappings().all()
        out = [dict(r) for r in rows]
        if wh_filter and wh_filter != "all":
            out = [w for w in out if str(w["warehouseId"]) == str(wh_filter)]
            if not out:
                raise FbsVirtualError(f"Склад {wh_filter} не найден среди виртуальных")
        return out

    async def upload_all(self, test: bool = True, wh_filter: str | None = None) -> dict:
        """Выгрузка всех остатков оперативного склада в виртуальные склады WB."""
        if self.company_id is None:
            raise FbsVirtualError("Не выбрана компания")
        _, fbs_id = await self._our_warehouses()
        if not fbs_id:
            raise FbsVirtualError("Нет оперативного склада is_fbs")
        rows = (await self.db.execute(text("""
            SELECT sku, nmID, chrtID, quantity FROM wb_stock_balance
            WHERE company_id = :cid AND warehouseId = :wid
            ORDER BY sku ASC"""),
            {"cid": self.company_id, "wid": fbs_id})).mappings().all()
        if not rows:
            raise FbsVirtualError("Нет виртуальных остатков для выгрузки")
        warehouses = await self._virtual_warehouses(wh_filter)
        if not warehouses:
            raise FbsVirtualError("Нет виртуальных складов (отметьте is_virtual)")
        token = await self._company_token()
        if not test and not token:
            raise FbsVirtualError("Нет токена компании")

        payload_stocks = [{"chrtId": int(r["chrtID"] or 0), "amount": int(r["quantity"] or 0)}
                          for r in rows]
        results = []
        for w in warehouses:
            for idx, chunk in enumerate(_chunks(payload_stocks, CHUNK)):
                payload = {"stocks": chunk}
                url = WB_STOCKS_URL.format(wid=w["warehouseId"])
                if test:
                    results.append({"warehouseId": w["warehouseId"], "chunk": idx + 1,
                                    "ok": True, "dry": True, "count": len(chunk)})
                    continue
                code, body = _put(url, payload, token)
                ok = code in (200, 204)
                results.append({"warehouseId": w["warehouseId"], "chunk": idx + 1,
                                "ok": ok, "status": code, "body": body[:500]})
                time.sleep(0.3)
            if not test:
                await self._mirror(w["warehouseId"], rows)
        if not test:
            await self.db.commit()
        return {"success": True, "dry": test, "results": results}

    async def upload_one(self, sku: str, amount: float | None = None,
                         test: bool = True, wh_filter: str | None = None) -> dict:
        """Выгрузка одного SKU (qty = текущий остаток оперативного склада)."""
        sku = (sku or "").strip()
        if not sku:
            raise FbsVirtualError("sku не передан")
        central_id, fbs_id = await self._our_warehouses()
        if not fbs_id:
            raise FbsVirtualError("Нет оперативного склада is_fbs")
        row = (await self.db.execute(text("""
            SELECT sku, chrtID, quantity FROM wb_stock_balance
            WHERE company_id = :cid AND warehouseId = :wid AND sku = :sku LIMIT 1"""),
            {"cid": self.company_id, "wid": fbs_id, "sku": sku})).mappings().first()
        if row is None:
            if amount is None:
                raise FbsVirtualError("Остаток не найден — сначала Сохранить или введите количество")
            new_qty = int(round(float(amount)))
            old = 0
        else:
            old = int(row["quantity"] or 0)
            new_qty = int(round(float(amount))) if amount is not None else old
        chrt = int(row["chrtID"]) if row and row["chrtID"] is not None else None
        nm_id = int(row["nmID"]) if row and row["nmID"] is not None else None
        size = None
        if chrt is None:
            size = (await self.db.execute(text(
                "SELECT nmID, chrtID FROM wbcards_sizes WHERE sku = :sku LIMIT 1"),
                {"sku": sku})).first()
            if not size:
                raise FbsVirtualError(f"SKU {sku} не найден в wbcards_sizes")
            chrt = int(size[1] or 0)
            nm_id = int(size[0]) if size[0] is not None else None
        delta = new_qty - old
        if delta != 0:
            # проводка через ledger (не прямой UPDATE баланса): строка отсутствует ->
            # старый остаток = 0, дельта = new_qty, doc_type fbs_virtual_upload
            if row is None:
                res = await stock_service.apply(
                    self.db, self.company_id, fbs_id, "fbs_virtual_upload",
                    None, [(sku, new_qty)], self.user_id, allow_negative=False)
            elif delta > 0 and central_id:
                res = await stock_service.transfer(
                    self.db, self.company_id, central_id, fbs_id,
                    "fbs_virtual_upload", None, [(sku, delta)],
                    self.user_id, allow_negative=False)
            elif delta < 0:
                res = await stock_service.transfer(
                    self.db, self.company_id, fbs_id, central_id,
                    "fbs_virtual_upload", None, [(sku, -delta)],
                    self.user_id, allow_negative=False)
            else:
                res = {"ok": False, "error": "Нет центрального склада для проводки дельты"}
            if not res.get("ok"):
                raise FbsVirtualError(res.get("error") or "Ошибка проводки остатка")

        warehouses = await self._virtual_warehouses(wh_filter)
        if not warehouses:
            raise FbsVirtualError("Нет виртуальных складов (отметьте is_virtual)")
        token = await self._company_token()
        if not test and not token:
            raise FbsVirtualError("Нет токена компании")
        payload = {"stocks": [{"chrtId": chrt, "amount": new_qty}]}
        results = []
        for w in warehouses:
            url = WB_STOCKS_URL.format(wid=w["warehouseId"])
            if test:
                results.append({"warehouseId": w["warehouseId"], "ok": True, "dry": True,
                                "payload": payload})
                continue
            code, body = _put(url, payload, token)
            ok = code in (200, 204)
            results.append({"warehouseId": w["warehouseId"], "ok": ok, "status": code,
                            "body": body[:500]})
            time.sleep(0.3)
            await self.db.execute(text("""
                INSERT INTO wb_fbs_stock(company_id, warehouseId, sku, amount, nmID, chrtID)
                VALUES(:cid, :wid, :sku, :a, :nm, :ch)
                ON DUPLICATE KEY UPDATE amount = :a, nmID = :nm, chrtID = :ch"""),
                {"cid": self.company_id, "wid": w["warehouseId"], "sku": sku,
                 "a": new_qty, "nm": nm_id, "ch": chrt})
        if not test:
            await self.db.commit()
        return {"success": True, "dry": test, "results": results}

    async def _mirror(self, wid: int, rows) -> None:
        for r in rows:
            await self.db.execute(text("""
                INSERT INTO wb_fbs_stock(company_id, warehouseId, sku, amount, nmID, chrtID)
                VALUES(:cid, :wid, :sku, :a, :nm, :ch)
                ON DUPLICATE KEY UPDATE amount = :a, nmID = :nm, chrtID = :ch"""),
                {"cid": self.company_id, "wid": wid, "sku": r["sku"],
                 "a": int(r["quantity"] or 0),
                 "nm": int(r["nmID"]) if r["nmID"] is not None else None,
                 "ch": int(r["chrtID"]) if r["chrtID"] is not None else None})

    async def deduct_log(self, limit: int = 200) -> dict:
        """Последние списания FBS-заказов (doc_type='fbs_order') + счётчик ожидающих."""
        rows = (await self.db.execute(text("""
            SELECT l.id, l.created_at, l.doc_id, l.warehouseId, l.sku,
                   l.qty_delta, l.qty_before, l.qty_after, w.name AS warehouse_name
            FROM wb_stock_ledger l
            LEFT JOIN our_warehouse w ON w.id = l.warehouseId
            WHERE l.company_id = :cid AND l.doc_type = 'fbs_order'
            ORDER BY l.id DESC
            LIMIT :lim"""),
            {"cid": self.company_id, "lim": limit})).mappings().all()
        pending = (await self.db.execute(text("""
            SELECT COUNT(*) FROM wb_orders_fbs
            WHERE company_id = :cid AND is_deducted = 0"""),
            {"cid": self.company_id})).scalar() or 0
        out = []
        for r in rows:
            d = dict(r)
            d["created_at"] = str(d["created_at"] or "")
            out.append(d)
        return {"rows": out, "pending_orders": int(pending), "limit": limit}


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _put(url: str, payload: dict, token: str) -> tuple[int, str]:
    """PUT в WB API. Токен идёт БЕЗ префикса Bearer (как в PHP)."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Authorization": token,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        return e.code, body
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"
