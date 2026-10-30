"""Справочник своих складов (our_warehouse) - порт OurWarehouseController (Yii2).

Таблица our_warehouse: id, company_id, name, code, is_central, is_fbs,
consider_orders, is_active, address.

Важно: our_warehouse.id - это наш склад, он же warehouseId в
wb_stock_balance / wb_stock_ledger (id из WB API лежит в wb_fbs_warehouse).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

FIELDS = ("name", "code", "is_central", "is_fbs", "consider_orders", "is_active", "address")
BOOL_FIELDS = ("is_central", "is_fbs", "consider_orders", "is_active")


def _b(v) -> int:
    if v is None:
        return 0
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return 1 if v else 0
    s = str(v).strip().lower()
    return 1 if s in ("1", "true", "yes", "on", "да") else 0


class WarehouseService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _cid(self) -> str:
        return "" if self.company_id is None else " AND company_id = :cid"

    def _params(self) -> dict:
        return {} if self.company_id is None else {"cid": self.company_id}

    async def list(self, active_only: bool = False) -> list[dict]:
        extra = " AND is_active = 1" if active_only else ""
        sql = f"""
            SELECT id, company_id, name, code, is_central, is_fbs,
                   consider_orders, is_active, address
            FROM our_warehouse
            WHERE 1=1{self._cid()}{extra}
            ORDER BY is_active DESC, name ASC
        """
        rows = (await self.db.execute(text(sql), self._params())).mappings().all()
        return [dict(r) for r in rows]

    async def get(self, wh_id: int) -> dict | None:
        row = (await self.db.execute(text("""
            SELECT id, company_id, name, code, is_central, is_fbs,
                   consider_orders, is_active, address
            FROM our_warehouse WHERE id = :id LIMIT 1"""),
            {"id": wh_id})).mappings().first()
        return dict(row) if row else None

    async def balances_count(self, wh_id: int) -> dict:
        """Сколько строк остатков/движений завязано на склад (для защиты от удаления)."""
        cid_sql = " AND company_id = :cid" if self.company_id is not None else ""
        params: dict = {"w": wh_id}
        if self.company_id is not None:
            params["cid"] = self.company_id
        bal = (await self.db.execute(text(fr"""
            SELECT COUNT(*) FROM wb_stock_balance
            WHERE warehouseId = :w{cid_sql}"""), params)).scalar() or 0
        led = (await self.db.execute(text(fr"""
            SELECT COUNT(*) FROM wb_stock_ledger
            WHERE warehouseId = :w{cid_sql}"""), params)).scalar() or 0
        docs = (await self.db.execute(text(fr"""
            SELECT COUNT(*) FROM wb_doc
            WHERE (warehouseId = :w OR to_warehouseId = :w){cid_sql}"""), params)).scalar() or 0
        return {"balances": int(bal), "ledger": int(led), "docs": int(docs)}

    async def create(self, name: str, code: str | None = None, is_central: int = 0,
                     is_fbs: int = 0, consider_orders: int = 0, is_active: int = 1,
                     address: str | None = None) -> dict:
        cid = self.company_id
        if cid is None:
            raise ValueError("company_id is required")
        row_id = (await self.db.execute(text("""
            INSERT INTO our_warehouse(company_id, name, code, is_central, is_fbs,
                consider_orders, is_active, address)
            VALUES(:cid, :name, :code, :central, :fbs, :consider, :active, :addr)"""),
            {"cid": cid, "name": name.strip(), "code": (code or None),
             "central": _b(is_central), "fbs": _b(is_fbs),
             "consider": _b(consider_orders), "active": _b(is_active) or 1,
             "addr": (address or None)})).lastrowid
        await self.db.commit()
        return (await self.get(int(row_id))) or {}

    async def update(self, wh_id: int, data: dict) -> dict | None:
        sets = []
        params: dict = {"id": wh_id}
        for f in FIELDS:
            if f not in data:
                continue
            val = data[f]
            if f in BOOL_FIELDS:
                val = _b(val)
            elif f in ("name", "code", "address"):
                val = (str(val).strip() or None) if f != "name" else str(val).strip()
            sets.append(f"{f} = :{f}")
            params[f] = val
        if not sets:
            return await self.get(wh_id)
        await self.db.execute(text(
            f"UPDATE our_warehouse SET {', '.join(sets)} WHERE id = :id"), params)
        await self.db.commit()
        return await self.get(wh_id)

    async def toggle(self, wh_id: int, field: str) -> dict | None:
        if field not in BOOL_FIELDS:
            raise ValueError(f"bad toggle field: {field}")
        await self.db.execute(text(f"""
            UPDATE our_warehouse SET {field} = 1 - IFNULL({field}, 0)
            WHERE id = :id"""), {"id": wh_id})
        await self.db.commit()
        return await self.get(wh_id)

    async def delete(self, wh_id: int) -> None:
        await self.db.execute(text("DELETE FROM our_warehouse WHERE id = :id"),
                              {"id": wh_id})
        await self.db.commit()

    async def central_id(self) -> int | None:
        if self.company_id is None:
            return None
        row = (await self.db.execute(text("""
            SELECT id FROM our_warehouse
            WHERE company_id = :cid AND is_central = 1 LIMIT 1"""),
            {"cid": self.company_id})).first()
        return int(row[0]) if row else None

    async def fbs_id(self) -> int | None:
        if self.company_id is None:
            return None
        row = (await self.db.execute(text("""
            SELECT id FROM our_warehouse
            WHERE company_id = :cid AND is_fbs = 1 LIMIT 1"""),
            {"cid": self.company_id})).first()
        return int(row[0]) if row else None
