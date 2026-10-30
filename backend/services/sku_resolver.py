"""Общий резолвер SKU для Excel-импорта остатков/документов.

Порядок разрешения — как в PHP:
  1) баркод (sku)   — точное совпадение wbcards_sizes.sku;
  2) nmID           — только если строка состоит из цифр; карточка + её первый размер;
  3) артикул продавца (vendorCode) — карточка + размер, но ТОЛЬКО если у карточки
     ровно один размер (иначе неоднозначно → строка в skipped).

Заголовки колонок ищутся точным совпадением (lower + trim) по набору вариантов —
как findColumn() в WbDocController / WbFbsVirtualController.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# --- варианты заголовков (как в PHP) -------------------------------------
COL_SKU = ["баркод", "barcode", "sku", "штрихкод"]
COL_VENDOR = ["артикул продавца", "vendorcode", "vendor_code", "артикул"]
COL_NMID = ["nmid", "nm_id", "nm id", "артикул wb", "nm"]
COL_QTY = ["количество", "qty", "quantity", "кол-во", "остаток"]

NO_COLUMNS_ERROR = "Не найдены колонки. Нужны: Баркод и/или Артикул + Количество"


@dataclass
class ParsedRow:
    """Строка Excel, разобранная в SKU + количество."""
    sku: str
    nm_id: int | None
    chrt_id: int | None
    qty: int
    row: int                      # номер строки в Excel (1 = заголовок)
    raw: dict[str, Any]           # исходная строка


def find_column(header: Sequence[Any], variants: Iterable[str]) -> int | None:
    """Индекс колонки по точному совпадению (lower + trim)."""
    want = {v.lower() for v in variants}
    for idx, h in enumerate(header):
        if str(h or "").strip().lower() in want:
            return idx
    return None


def detect_columns(header: Sequence[Any]) -> dict[str, int | None]:
    """Определяет индексы колонок Barcode/Vendor/nmID/Qty по заголовку."""
    return {
        "sku": find_column(header, COL_SKU),
        "vendor": find_column(header, COL_VENDOR),
        "nm_id": find_column(header, COL_NMID),
        "qty": find_column(header, COL_QTY),
    }


def columns_ok(cols: dict[str, int | None]) -> bool:
    """Есть ли количество и хотя бы один идентификатор карточки."""
    has_id = cols["sku"] is not None or cols["vendor"] is not None or cols["nm_id"] is not None
    return cols["qty"] is not None and has_id


class SkuResolver:
    """Резолвит строки Excel в SKU компании."""

    def __init__(self, db: AsyncSession, company_id: int | None):
        self.db = db
        self.company_id = company_id

    async def _by_sku(self, sku: str) -> dict | None:
        rows = (await self.db.execute(text("""
            SELECT s.sku, s.nmID, s.chrtID
            FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            WHERE s.sku = :sku AND (:cid IS NULL OR c.company_id = :cid)
            LIMIT 1
        """), {"sku": sku, "cid": self.company_id})).mappings().all()
        return dict(rows[0]) if rows else None

    async def _by_nm_id(self, nm_id: int) -> dict | None:
        rows = (await self.db.execute(text("""
            SELECT s.sku, s.nmID, s.chrtID
            FROM wbcards_sizes s
            INNER JOIN wbcards c ON c.nmID = s.nmID
            WHERE s.nmID = :nm AND (:cid IS NULL OR c.company_id = :cid)
            ORDER BY s.id ASC
            LIMIT 1
        """), {"nm": nm_id, "cid": self.company_id})).mappings().all()
        return dict(rows[0]) if rows else None

    async def _by_vendor(self, vendor_code: str) -> dict | None:
        """Только если у карточки ровно один размер — иначе строка неоднозначна."""
        rows = (await self.db.execute(text("""
            SELECT c.nmID,
                   (SELECT COUNT(*) FROM wbcards_sizes s2 WHERE s2.nmID = c.nmID) AS sizes_cnt
            FROM wbcards c
            WHERE c.vendorCode = :vc AND (:cid IS NULL OR c.company_id = :cid)
            LIMIT 1
        """), {"vc": vendor_code, "cid": self.company_id})).mappings().all()
        if not rows:
            return None
        nm = int(rows[0]["nmID"])
        if int(rows[0]["sizes_cnt"] or 0) != 1:
            return None
        return await self._by_nm_id(nm)

    async def resolve(self, sku: str | None, vendor_code: str | None, nm_id_raw: str | None) -> dict | None:
        """Возвращает {sku, nmID, chrtID} или None."""
        if sku:
            r = await self._by_sku(sku.strip())
            if r:
                return r
        if nm_id_raw and str(nm_id_raw).strip().isdigit():
            r = await self._by_nm_id(int(str(nm_id_raw).strip()))
            if r:
                return r
        if vendor_code:
            r = await self._by_vendor(vendor_code.strip())
            if r:
                return r
        return None

    async def parse_rows(self, sheet: list[list[Any]]) -> tuple[list[ParsedRow], list[str]]:
        """Разбирает лист Excel (первая строка — заголовок).

        Возвращает (matched, skipped). Строки без числового количества
        пропускаются молча (как в PHP).
        """
        matched: list[ParsedRow] = []
        skipped: list[str] = []
        if not sheet:
            return matched, [NO_COLUMNS_ERROR]
        header = list(sheet[0])
        cols = detect_columns(header)
        if not columns_ok(cols):
            return matched, [NO_COLUMNS_ERROR]

        for i in range(1, len(sheet)):
            row = list(sheet[i]) + [None] * max(0, len(header) - len(sheet[i]))
            raw_sku = str(row[cols["sku"]] or "").strip() if cols["sku"] is not None else ""
            raw_vendor = str(row[cols["vendor"]] or "").strip() if cols["vendor"] is not None else ""
            raw_nm = str(row[cols["nm_id"]] or "").strip() if cols["nm_id"] is not None else ""
            qty_raw = row[cols["qty"]] if cols["qty"] is not None else None
            if qty_raw is None or qty_raw == "":
                continue
            try:
                qty = int(round(float(qty_raw)))
            except (TypeError, ValueError):
                continue
            resolved = await self.resolve(raw_sku or None, raw_vendor or None, raw_nm or None)
            if not resolved:
                skipped.append(
                    f"Строка {i + 1}: не найден (sku={raw_sku} vendor={raw_vendor} nmID={raw_nm})"
                )
                continue
            matched.append(ParsedRow(
                sku=str(resolved["sku"]),
                nm_id=int(resolved["nmID"]) if resolved.get("nmID") is not None else None,
                chrt_id=int(resolved["chrtID"]) if resolved.get("chrtID") is not None else None,
                qty=qty,
                row=i + 1,
                raw={k: row[k] for k in range(len(row)) if row[k] is not None},
            ))
        return matched, skipped
