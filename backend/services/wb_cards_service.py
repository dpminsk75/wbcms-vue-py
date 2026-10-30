"""Витрина карточек WB (/wb/cards) — порт WbController::actionCards + WbCardSearch.

Фильтры как в PHP: nmID, imtID, subjectID, vendorCode, brand, subjectName,
title, description, только не занятые в линейках (onlyUnused).
Отличие от PHP: скоуп по wbcards.company_id (в PHP-отчёте список был глобальный).
Пагинация LIMIT/OFFSET; ORDER BY nmID DESC.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.like_mask import escape_like


class WbCardsService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _conds(self, **f) -> tuple[list[str], dict]:
        conds: list[str] = []
        params: dict = {}
        if self.company_id is not None:
            conds.append("c.company_id = :company_id")
            params["company_id"] = self.company_id
        if f.get("nm_id"):
            conds.append("c.nmID = :nm_id")
            params["nm_id"] = int(f["nm_id"])
        if f.get("imt_id"):
            conds.append("c.imtID = :imt_id")
            params["imt_id"] = int(f["imt_id"])
        if f.get("subject_id"):
            conds.append("c.subjectID = :subject_id")
            params["subject_id"] = int(f["subject_id"])
        for key, col in (("vendor", "c.vendorCode"), ("brand", "c.brand"),
                         ("subject_name", "c.subjectName"), ("title", "c.title")):
            val = (f.get(key) or "").strip()
            if val:
                conds.append(f"{col} LIKE :{key}_like")
                params[f"{key}_like"] = f"%{escape_like(val)}%"
        desc = (f.get("description") or "").strip()
        if desc:
            conds.append("c.description LIKE :desc_like")
            params["desc_like"] = f"%{escape_like(desc)}%"
        if f.get("only_unused"):
            conds.append("NOT EXISTS (SELECT 1 FROM product_wb_card l WHERE l.wb_nm_id = c.nmID)")
        return conds, params

    async def search(self, nm_id=None, imt_id=None, subject_id=None, vendor: str | None = None,
                     brand: str | None = None, subject_name: str | None = None,
                     title: str | None = None, description: str | None = None,
                     only_unused: int = 0, page: int = 1,
                     page_size: int = 20) -> dict:
        conds, params = self._conds(
            nm_id=nm_id, imt_id=imt_id, subject_id=subject_id, vendor=vendor, brand=brand,
            subject_name=subject_name, title=title, description=description,
            only_unused=only_unused)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        lim = max(1, min(page_size, 200))
        off = max(0, (max(1, page) - 1)) * lim
        total = (await self.db.execute(text(
            f"SELECT COUNT(*) FROM wbcards c {where}"), params)).scalar() or 0
        rows = (await self.db.execute(text(f"""
            SELECT c.nmID, c.imtID, c.vendorCode, c.brand, c.subjectName, c.subjectID,
                   c.title, c.created_at,
                   (SELECT COUNT(*) FROM product_wb_card l WHERE l.wb_nm_id = c.nmID) AS links_cnt
            FROM wbcards c {where}
            ORDER BY c.nmID DESC
            LIMIT {lim} OFFSET {off}"""), params)).mappings().all()
        return {"rows": [dict(r) for r in rows], "total": int(total),
                "page": page, "page_size": page_size}

    async def filters(self) -> dict:
        """Уникальные бренды/предметы для Select2 (порт actionCards)."""
        cid = "" if self.company_id is None else " AND company_id = :company_id"
        params = {} if self.company_id is None else {"company_id": self.company_id}
        brands = [r[0] for r in (await self.db.execute(text(
            "SELECT DISTINCT brand FROM wbcards WHERE brand IS NOT NULL AND brand <> ''"
            f"{cid} ORDER BY brand"), params)).all()]
        subjects = [r[0] for r in (await self.db.execute(text(
            "SELECT DISTINCT subjectName FROM wbcards WHERE subjectName IS NOT NULL "
            f"AND subjectName <> ''{cid} ORDER BY subjectName"), params)).all()]
        return {"brands": brands, "subjectNames": subjects}
