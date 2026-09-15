from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import json

class WbCardService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    async def list_cards(self, q: str | None = None, limit: int = 50):
        # как в WbCard::getListForSelect + фильтр по q; скоуп по wbcards.company_id
        # (синк карточек идёт по компаниям — чужие строки не отдаём).
        sql = "SELECT nmID, vendorCode, title, brand, photos FROM wbcards"
        params: dict = {}
        conds: list[str] = []
        if q:
            conds.append("(CAST(nmID AS CHAR) LIKE :q OR vendorCode LIKE :q OR title LIKE :q)")
            params["q"] = f"%{q}%"
        if self.company_id is not None:
            conds.append("company_id = :company_id")
            params["company_id"] = self.company_id
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY nmID DESC LIMIT :lim"
        params["lim"] = limit
        rows = (await self.db.execute(text(sql), params)).mappings().all()
        return [dict(r) for r in rows]

    async def get_card(self, nm_id: int):
        sql = text("""SELECT nmID, vendorCode, title, brand, description, photos, video, dimensions, characteristics, sizes, tags,
                             subjectName, subjectID, created_at, updated_at
                      FROM wbcards WHERE nmID=:nm_id""" + ("" if self.company_id is None else " AND company_id = :company_id") + """ LIMIT 1""")
        params: dict = {"nm_id": nm_id}
        if self.company_id is not None:
            params["company_id"] = self.company_id
        row = (await self.db.execute(sql, params)).mappings().first()
        if not row:
            return None
        d = dict(row)
        # JSON поля как в WbCard::afterFind
        for k in ("photos","dimensions","characteristics","sizes","tags"):
            v = d.get(k)
            if isinstance(v, str):
                try:
                    # двойной decode защита как в feed.php
                    first = json.loads(v)
                    if isinstance(first, str):
                        first = json.loads(first)
                    d[k] = first
                except Exception:
                    pass
        return d
