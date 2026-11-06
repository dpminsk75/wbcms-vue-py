"""Ручной маркетинг: площадки (marketing_channels) + документы/строки расходов.

Модель (зафиксирована владельцем 2026-11-06):
  marketing_channels            — справочник «кто/где продвигали»: блогер, сайт,
                                  Telegram, YouTube и т.п. + минимальные реквизиты.
  marketing_expense_documents   — один акт/интеграция/договор = один документ.
  marketing_expense_lines       — позиции документа: SKU + сумма (всегда привязаны к nmID).

Расход ВСЕГДА привязан к SKU: строки без nmID не принимаются. Итог документа
считается из строк (total_amount), а не вводится отдельно.

Excel: один лист, строки документа и строки SKU связаны document_key.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.like_mask import escape_like

log = logging.getLogger("wbcms.marketing")

CHANNEL_TYPES = ("blogger", "site", "telegram", "youtube", "instagram", "other")
CHANNEL_TYPE_LABELS = {
    "blogger": "Блогер",
    "site": "Сайт",
    "telegram": "Telegram",
    "youtube": "YouTube",
    "instagram": "Instagram",
    "other": "Другое",
}

DOC_TYPES = ("blogger_post", "giveaway", "self_buyout", "review_cashback", "other")
DOC_TYPE_LABELS = {
    "blogger_post": "Пост у блогера",
    "giveaway": "Раздача",
    "self_buyout": "Самовыкуп",
    "review_cashback": "Кешбек за отзыв",
    "other": "Прочее",
}

# Колонки Excel-шаблона (один лист).
XLSX_COLUMNS = [
    "document_key", "document_date", "channel", "doc_type", "title",
    "vendor_code", "nm_id", "amount", "comment",
]


class MarketingError(Exception):
    """Ошибка валидации маркетинговых данных."""


def _num(value, field: str) -> float:
    s = str(value if value is not None else "").strip().replace(" ", "").replace(",", ".")
    if not s:
        raise MarketingError(f"{field}: сумма не заполнена")
    try:
        v = float(s)
    except ValueError:
        raise MarketingError(f"{field}: '{value}' — не число")
    if v <= 0:
        raise MarketingError(f"{field}: сумма должна быть больше 0")
    return round(v, 2)


def _date(value, field: str) -> str:
    s = str(value or "").strip()
    if not s:
        raise MarketingError(f"{field}: дата не заполнена")
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date().isoformat()
        except ValueError:
            continue
    raise MarketingError(f"{field}: '{value}' — не дата (YYYY-MM-DD)")


class MarketingService:
    def __init__(self, db: AsyncSession, company_id: int | None = None,
                 user_id: int | None = None):
        self.db = db
        self.company_id = company_id
        self.user_id = user_id

    def _need_company(self) -> int:
        if self.company_id is None:
            raise MarketingError("company_id is required")
        return self.company_id

    # ------------------------------------------------------------ площадки
    async def list_channels(self, q: str = "", include_archived: bool = False) -> list[dict]:
        cid = self._need_company()
        params: dict = {"cid": cid}
        where = ""
        if not include_archived:
            where = " AND c.is_active = 1"
        if q:
            where += " AND (c.name LIKE :q OR c.website_or_contact LIKE :q OR c.inn LIKE :q)"
            params["q"] = f"%{escape_like(q.strip())}%"
        rows = (await self.db.execute(text(f"""
            SELECT c.id, c.name, c.channel_type, c.website_or_contact, c.contact_name,
                   c.contact_phone, c.inn, c.comment, c.is_active, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM marketing_expense_documents d
                     WHERE d.channel_id = c.id) AS documents_cnt,
                   (SELECT COALESCE(SUM(l.amount), 0) FROM marketing_expense_lines l
                     INNER JOIN marketing_expense_documents d2 ON d2.id = l.document_id
                     WHERE d2.channel_id = c.id) AS total_amount
            FROM marketing_channels c
            WHERE c.company_id = :cid{where}
            ORDER BY c.is_active DESC, c.name"""), params)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["channel_type_label"] = CHANNEL_TYPE_LABELS.get(d.get("channel_type") or "", d.get("channel_type"))
            d["documents_cnt"] = int(d.get("documents_cnt") or 0)
            d["total_amount"] = float(d.get("total_amount") or 0)
            out.append(d)
        return out

    async def create_channel(self, data: dict) -> dict:
        cid = self._need_company()
        name = str(data.get("name") or "").strip()
        if not name:
            raise MarketingError("name: укажите площадку")
        ctype = str(data.get("channel_type") or "other").strip().lower()
        if ctype not in CHANNEL_TYPES:
            raise MarketingError(f"channel_type: допустимо {', '.join(CHANNEL_TYPES)}")
        dup = (await self.db.execute(text(
            "SELECT id FROM marketing_channels WHERE company_id=:cid AND name=:n LIMIT 1"),
            {"cid": cid, "n": name})).scalar()
        if dup:
            raise MarketingError("площадка с таким названием уже есть")
        cid_row = (await self.db.execute(text("""
            INSERT INTO marketing_channels
              (company_id, name, channel_type, website_or_contact, contact_name,
               contact_phone, inn, comment, is_active, created_by, updated_by)
            VALUES (:cid, :name, :type, :web, :cname, :cphone, :inn, :cmt, 1, :uid, :uid)"""),
            {"cid": cid, "name": name, "type": ctype,
             "web": (data.get("website_or_contact") or "").strip() or None,
             "cname": (data.get("contact_name") or "").strip() or None,
             "cphone": (data.get("contact_phone") or "").strip() or None,
             "inn": (data.get("inn") or "").strip() or None,
             "cmt": (data.get("comment") or "").strip() or None,
             "uid": self.user_id})).lastrowid
        await self.db.commit()
        return {"ok": True, "id": int(cid_row)}

    async def update_channel(self, channel_id: int, data: dict) -> dict:
        cid = self._need_company()
        row = (await self.db.execute(text(
            "SELECT id FROM marketing_channels WHERE id=:id AND company_id=:cid"),
            {"id": channel_id, "cid": cid})).scalar()
        if not row:
            raise MarketingError("площадка не найдена")
        name = str(data.get("name") or "").strip()
        if not name:
            raise MarketingError("name: укажите площадку")
        ctype = str(data.get("channel_type") or "other").strip().lower()
        if ctype not in CHANNEL_TYPES:
            raise MarketingError(f"channel_type: допустимо {', '.join(CHANNEL_TYPES)}")
        await self.db.execute(text("""
            UPDATE marketing_channels
            SET name=:name, channel_type=:type, website_or_contact=:web, contact_name=:cname,
                contact_phone=:cphone, inn=:inn, comment=:cmt, is_active=:active, updated_by=:uid
            WHERE id=:id AND company_id=:cid"""),
            {"id": channel_id, "cid": cid, "name": name, "type": ctype,
             "web": (data.get("website_or_contact") or "").strip() or None,
             "cname": (data.get("contact_name") or "").strip() or None,
             "cphone": (data.get("contact_phone") or "").strip() or None,
             "inn": (data.get("inn") or "").strip() or None,
             "cmt": (data.get("comment") or "").strip() or None,
             "active": 1 if data.get("is_active", 1) else 0,
             "uid": self.user_id})
        await self.db.commit()
        return {"ok": True}

    async def delete_channel(self, channel_id: int) -> dict:
        """Архивируем: если есть документы — удаление нельзя (ссылки)."""
        cid = self._need_company()
        row = (await self.db.execute(text(
            "SELECT id FROM marketing_channels WHERE id=:id AND company_id=:cid"),
            {"id": channel_id, "cid": cid})).scalar()
        if not row:
            raise MarketingError("площадка не найдена")
        used = (await self.db.execute(text(
            "SELECT COUNT(*) FROM marketing_expense_documents WHERE channel_id=:id"),
            {"id": channel_id})).scalar()
        if int(used or 0) > 0:
            await self.db.execute(text(
                "UPDATE marketing_channels SET is_active=0, updated_by=:uid WHERE id=:id"),
                {"id": channel_id, "uid": self.user_id})
            await self.db.commit()
            return {"ok": True, "archived": True,
                    "message": "по площадке есть документы — она архивирована, не удалена"}
        await self.db.execute(text("DELETE FROM marketing_channels WHERE id=:id AND company_id=:cid"),
                              {"id": channel_id, "cid": cid})
        await self.db.commit()
        return {"ok": True, "archived": False}

    # ----------------------------------------------------------- документы
    async def list_documents(self, date_from: str | None = None, date_to: str | None = None,
                             channel_id: int | None = None, q: str = "",
                             limit: int = 200) -> list[dict]:
        cid = self._need_company()
        limit = max(1, min(int(limit or 200), 1000))
        params: dict = {"cid": cid, "lim": limit}
        where = " WHERE d.company_id = :cid"
        if date_from:
            where += " AND d.document_date >= :d1"
            params["d1"] = str(date_from)[:10]
        if date_to:
            where += " AND d.document_date <= :d2"
            params["d2"] = str(date_to)[:10]
        if channel_id:
            where += " AND d.channel_id = :ch"
            params["ch"] = channel_id
        if q:
            where += (" AND (d.title LIKE :q OR d.document_key LIKE :q OR c.name LIKE :q)")
            params["q"] = f"%{escape_like(q.strip())}%"
        rows = (await self.db.execute(text(f"""
            SELECT d.id, d.document_key, d.document_date, d.channel_id, d.doc_type, d.title,
                   d.comment, d.total_amount, d.created_at, d.updated_at,
                   c.name AS channel_name,
                   (SELECT COUNT(*) FROM marketing_expense_lines l
                     WHERE l.document_id = d.id) AS lines_cnt
            FROM marketing_expense_documents d
            LEFT JOIN marketing_channels c ON c.id = d.channel_id
            {where}
            ORDER BY d.document_date DESC, d.id DESC
            LIMIT :lim"""), params)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["doc_type_label"] = DOC_TYPE_LABELS.get(d.get("doc_type") or "", d.get("doc_type"))
            d["total_amount"] = float(d.get("total_amount") or 0)
            d["lines_cnt"] = int(d.get("lines_cnt") or 0)
            d["document_date"] = str(d.get("document_date") or "")[:10]
            out.append(d)
        return out

    async def get_document(self, document_id: int) -> dict:
        cid = self._need_company()
        row = (await self.db.execute(text("""
            SELECT d.id, d.document_key, d.document_date, d.channel_id, d.doc_type, d.title,
                   d.comment, d.total_amount, d.created_at,
                   c.name AS channel_name
            FROM marketing_expense_documents d
            LEFT JOIN marketing_channels c ON c.id = d.channel_id
            WHERE d.id = :id AND d.company_id = :cid"""),
            {"id": document_id, "cid": cid})).mappings().first()
        if not row:
            raise MarketingError("документ не найден")
        doc = dict(row)
        doc["doc_type_label"] = DOC_TYPE_LABELS.get(doc.get("doc_type") or "", doc.get("doc_type"))
        doc["document_date"] = str(doc.get("document_date") or "")[:10]
        lines = (await self.db.execute(text("""
            SELECT l.id, l.nm_id, l.vendor_code, l.product_title, l.amount, l.comment
            FROM marketing_expense_lines l
            WHERE l.document_id = :id AND l.company_id = :cid
            ORDER BY l.id"""),
            {"id": document_id, "cid": cid})).mappings().all()
        doc["lines"] = [dict(r) for r in lines]
        doc["total_amount"] = float(doc.get("total_amount") or 0)
        return doc

    async def _cards_for(self, vendor_codes: list[str], nm_ids: list[int]) -> tuple[dict, dict]:
        """Карточки по списку: nmID→карточка и vendorCode→карточка (1–2 запроса)."""
        cid = self._need_company()
        by_nm: dict = {}
        by_vc: dict = {}
        if nm_ids:
            stmt = text("""
                SELECT nmID, vendorCode, title FROM wbcards
                WHERE company_id = :cid AND is_active = 1 AND nmID IN :ids""").bindparams(
                bindparam("ids", expanding=True))
            for r in (await self.db.execute(stmt, {"cid": cid, "ids": list(nm_ids)})).mappings().all():
                d = dict(r)
                by_nm[int(r["nmID"])] = d
        if vendor_codes:
            stmt = text("""
                SELECT nmID, vendorCode, title FROM wbcards
                WHERE company_id = :cid AND is_active = 1 AND vendorCode IN :vcs""").bindparams(
                bindparam("vcs", expanding=True))
            for r in (await self.db.execute(stmt, {"cid": cid, "vcs": list(vendor_codes)})).mappings().all():
                d = dict(r)
                by_vc[str(d["vendorCode"])] = d
        return by_nm, by_vc

    async def _cards_map(self) -> tuple[dict, dict]:
        """Все карточки компании (для небольших кабинетов)."""
        cid = self._need_company()
        rows = (await self.db.execute(text("""
            SELECT nmID, vendorCode, title FROM wbcards
            WHERE company_id = :cid AND is_active = 1"""), {"cid": cid})).mappings().all()
        by_nm: dict = {}
        by_vc: dict = {}
        for r in rows:
            d = dict(r)
            by_nm[int(r["nmID"])] = d
            if d.get("vendorCode"):
                by_vc[str(d["vendorCode"])] = d
        return by_nm, by_vc

    async def create_document(self, data: dict) -> dict:
        """Создать документ с позициями. Позиции всегда привязаны к SKU."""
        cid = self._need_company()
        dkey = str(data.get("document_key") or "").strip()
        ddate = _date(data.get("document_date"), "document_date")
        dtype = str(data.get("doc_type") or "other").strip().lower()
        if dtype not in DOC_TYPES:
            raise MarketingError(f"doc_type: допустимо {', '.join(DOC_TYPES)}")
        title = str(data.get("title") or "").strip()
        if not title:
            raise MarketingError("title: укажите название документа")
        raw_lines = data.get("lines") or []
        if not isinstance(raw_lines, list) or not raw_lines:
            raise MarketingError("lines: добавьте хотя бы одну позицию")
        if len(raw_lines) > 500:
            raise MarketingError("lines: максимум 500 позиций в документе")

        channel_id = data.get("channel_id")
        if channel_id in ("", None, 0):
            channel_id = None
        else:
            channel_id = int(channel_id)
            ch = (await self.db.execute(text(
                "SELECT id FROM marketing_channels WHERE id=:id AND company_id=:cid"),
                {"id": channel_id, "cid": cid})).scalar()
            if not ch:
                raise MarketingError("площадка не найдена")

        if not dkey:
            dkey = f"D-{ddate}-{date.today().strftime('%y%m%d%H%M%S')}"
        dup = (await self.db.execute(text(
            "SELECT id FROM marketing_expense_documents WHERE company_id=:cid AND document_key=:k LIMIT 1"),
            {"cid": cid, "k": dkey})).scalar()
        if dup:
            raise MarketingError(f"document_key '{dkey}' уже занят")

        prepared = []
        seen = set()
        total = 0.0
        want_nm = [int(ln["nm_id"]) for ln in raw_lines
                   if isinstance(ln, dict) and str(ln.get("nm_id") or "") not in ("", "0", "None")]
        want_vc = [str(ln.get("vendor_code") or "").strip() for ln in raw_lines
                   if isinstance(ln, dict) and str(ln.get("nm_id") or "") in ("", "0", "None")
                   and str(ln.get("vendor_code") or "").strip()]
        cards_by_nm, cards_by_vc = await self._cards_for(sorted(set(want_vc)), sorted(set(want_nm)))
        for i, ln in enumerate(raw_lines, start=1):
            if not isinstance(ln, dict):
                raise MarketingError(f"строка {i}: ожидается объект")
            raw_nm = ln.get("nm_id")
            raw_vc = str(ln.get("vendor_code") or "").strip()
            card = None
            if raw_nm not in (None, "", "0"):
                try:
                    card = cards_by_nm.get(int(raw_nm))
                except (TypeError, ValueError):
                    raise MarketingError(f"строка {i}: nm_id должен быть числом")
                if not card:
                    raise MarketingError(f"строка {i}: nm_id {raw_nm} — карточка не найдена")
            else:
                if not raw_vc:
                    raise MarketingError(f"строка {i}: укажите артикул (vendor_code) или nm_id")
                card = cards_by_vc.get(raw_vc)
                if not card:
                    raise MarketingError(f"строка {i}: артикул '{raw_vc}' — карточка не найдена")
            if card["nmID"] in seen:
                raise MarketingError(f"строка {i}: SKU {card['nmID']} уже есть в документе — "
                                    "суммируйте в одну строку")
            seen.add(card["nmID"])
            amount = _num(ln.get("amount"), f"строка {i}: сумма")
            total += amount
            prepared.append((card, amount, str(ln.get("comment") or "").strip() or None))

        doc_id = (await self.db.execute(text("""
            INSERT INTO marketing_expense_documents
              (company_id, document_key, document_date, channel_id, doc_type, title,
               comment, total_amount, created_by, updated_by)
            VALUES (:cid, :k, :d, :ch, :t, :title, :cmt, :total, :uid, :uid)"""),
            {"cid": cid, "k": dkey, "d": ddate, "ch": channel_id, "t": dtype,
             "title": title, "cmt": (data.get("comment") or "").strip() or None,
             "total": round(total, 2), "uid": self.user_id})).lastrowid
        for card, amount, comment in prepared:
            await self.db.execute(text("""
                INSERT INTO marketing_expense_lines
                  (company_id, document_id, nm_id, vendor_code, product_title, amount, comment)
                VALUES (:cid, :doc, :nm, :vc, :title, :amt, :cmt)"""),
                {"cid": cid, "doc": int(doc_id), "nm": card["nmID"],
                 "vc": card["vendorCode"], "title": card["title"],
                 "amt": amount, "cmt": comment})
        await self.db.commit()
        return {"ok": True, "id": int(doc_id), "document_key": dkey, "total_amount": round(total, 2)}

    async def update_document(self, document_id: int, data: dict) -> dict:
        cid = self._need_company()
        row = (await self.db.execute(text(
            "SELECT id FROM marketing_expense_documents WHERE id=:id AND company_id=:cid"),
            {"id": document_id, "cid": cid})).mappings().first()
        if not row:
            raise MarketingError("документ не найден")
        doc = dict(row)
        title = str(data.get("title") or doc.get("title") or "").strip()
        if not title:
            raise MarketingError("title: укажите название документа")
        dtype = str(data.get("doc_type") or doc.get("doc_type") or "other").strip().lower()
        if dtype not in DOC_TYPES:
            raise MarketingError(f"doc_type: допустимо {', '.join(DOC_TYPES)}")
        ddate = _date(data.get("document_date") or doc.get("document_date"), "document_date")
        channel_id = data.get("channel_id", doc.get("channel_id"))
        channel_id = int(channel_id) if channel_id not in (None, "", 0) else None

        raw_lines = data.get("lines")
        total = float(doc.get("total_amount") or 0)
        prepared = []
        if isinstance(raw_lines, list):
            if not raw_lines:
                raise MarketingError("lines: добавьте хотя бы одну позицию")
            seen = set()
            total = 0.0
            want_nm = [int(ln["nm_id"]) for ln in raw_lines
                       if isinstance(ln, dict) and str(ln.get("nm_id") or "") not in ("", "0", "None")]
            want_vc = [str(ln.get("vendor_code") or "").strip() for ln in raw_lines
                       if isinstance(ln, dict) and str(ln.get("nm_id") or "") in ("", "0", "None")
                       and str(ln.get("vendor_code") or "").strip()]
            cards_by_nm, cards_by_vc = await self._cards_for(sorted(set(want_vc)), sorted(set(want_nm)))
            for i, ln in enumerate(raw_lines, start=1):
                if not isinstance(ln, dict):
                    raise MarketingError(f"строка {i}: ожидается объект")
                raw_nm = ln.get("nm_id")
                raw_vc = str(ln.get("vendor_code") or "").strip()
                card = None
                if raw_nm not in (None, "", "0"):
                    try:
                        card = cards_by_nm.get(int(raw_nm))
                    except (TypeError, ValueError):
                        raise MarketingError(f"строка {i}: nm_id должен быть числом")
                    if not card:
                        raise MarketingError(f"строка {i}: nm_id {raw_nm} — карточка не найдена")
                else:
                    if not raw_vc:
                        raise MarketingError(f"строка {i}: укажите артикул (vendor_code) или nm_id")
                    card = cards_by_vc.get(raw_vc)
                    if not card:
                        raise MarketingError(f"строка {i}: артикул '{raw_vc}' — карточка не найдена")
                if card["nmID"] in seen:
                    raise MarketingError(f"строка {i}: SKU {card['nmID']} уже есть в документе")
                seen.add(card["nmID"])
                amount = _num(ln.get("amount"), f"строка {i}: сумма")
                total += amount
                prepared.append((card, amount, str(ln.get("comment") or "").strip() or None))

        await self.db.execute(text("""
            UPDATE marketing_expense_documents
            SET document_date=:d, channel_id=:ch, doc_type=:t, title=:title,
                comment=:cmt, total_amount=:total, updated_by=:uid
            WHERE id=:id AND company_id=:cid"""),
            {"id": document_id, "cid": cid, "d": ddate, "ch": channel_id, "t": dtype,
             "title": title, "cmt": (data.get("comment") or "").strip() or None,
             "total": round(total, 2), "uid": self.user_id})
        if isinstance(raw_lines, list):
            await self.db.execute(text(
                "DELETE FROM marketing_expense_lines WHERE document_id=:id"),
                {"id": document_id})
            for card, amount, comment in prepared:
                await self.db.execute(text("""
                    INSERT INTO marketing_expense_lines
                      (company_id, document_id, nm_id, vendor_code, product_title, amount, comment)
                    VALUES (:cid, :doc, :nm, :vc, :title, :amt, :cmt)"""),
                    {"cid": cid, "doc": document_id, "nm": card["nmID"],
                     "vc": card["vendorCode"], "title": card["title"],
                     "amt": amount, "cmt": comment})
        await self.db.commit()
        return {"ok": True, "total_amount": round(total, 2)}

    async def delete_document(self, document_id: int) -> dict:
        cid = self._need_company()
        row = (await self.db.execute(text(
            "SELECT id FROM marketing_expense_documents WHERE id=:id AND company_id=:cid"),
            {"id": document_id, "cid": cid})).scalar()
        if not row:
            raise MarketingError("документ не найдена")
        await self.db.execute(text(
            "DELETE FROM marketing_expense_lines WHERE document_id=:id"), {"id": document_id})
        await self.db.execute(text(
            "DELETE FROM marketing_expense_documents WHERE id=:id AND company_id=:cid"),
            {"id": document_id, "cid": cid})
        await self.db.commit()
        return {"ok": True}

    # ------------------------------------------------------------ карточки
    async def search_cards(self, q: str = "", limit: int = 20) -> list[dict]:
        """Поиск карточек компании — для выбора SKU в позиции расхода."""
        cid = self._need_company()
        limit = max(1, min(int(limit or 20), 50))
        q = str(q or "").strip()
        if not q:
            return []
        like = f"%{escape_like(q)}%"
        rows = (await self.db.execute(text("""
            SELECT nmID, vendorCode, title FROM wbcards
            WHERE company_id = :cid AND is_active = 1
              AND (CAST(nmID AS CHAR) LIKE :q OR vendorCode LIKE :q OR title LIKE :q)
            ORDER BY nmID DESC LIMIT :lim"""),
            {"cid": cid, "q": like, "lim": limit})).mappings().all()
        return [{"nm_id": r["nmID"], "vendor_code": r["vendorCode"], "title": r["title"]}
                for r in rows]

    # -------------------------------------------------------------- Excel
    async def import_preview(self, rows: list[list]) -> dict:
        """Разбор листа Excel: документы группируются по document_key."""
        cid = self._need_company()
        if not rows:
            raise MarketingError("файл пуст")
        header = [str(h or "").strip().lower() for h in rows[0]]
        idx = {name: i for i, name in enumerate(header)}
        missing_cols = [c for c in XLSX_COLUMNS[:5] + XLSX_COLUMNS[5:7] if c not in idx]
        if missing_cols:
            raise MarketingError("в файле нет колонок: " + ", ".join(missing_cols))

        channels = {str(c["name"]).strip().lower(): c for c in await self.list_channels(include_archived=True)}
        docs: dict[str, dict] = {}
        errors: list[dict] = []
        ok_rows = 0

        # 1) разбор ячеек без обращения к БД
        parsed: list[dict] = []
        need_vc: set[str] = set()
        need_nm: set[int] = set()
        for n, row in enumerate(rows[1:], start=2):
            if not any(str(v or "").strip() for v in row):
                continue

            def cell(name: str) -> str:
                i = idx.get(name, -1)
                return str(row[i] or "").strip() if 0 <= i < len(row) else ""

            raw = " | ".join(str(v or "") for v in row)
            dkey = cell("document_key")
            try:
                ddate = _date(cell("document_date"), "document_date")
                ch_name = cell("channel")
                dtype = cell("doc_type").lower() or "other"
                if dtype not in DOC_TYPES:
                    raise MarketingError(f"doc_type '{dtype}' — не из справочника")
                title = cell("title") or dkey or ch_name
                amount = _num(cell("amount"), "amount")
                raw_nm = cell("nm_id")
                raw_vc = cell("vendor_code")
                if raw_nm:
                    try:
                        nid = int(raw_nm)
                    except ValueError:
                        raise MarketingError("nm_id: должен быть числом")
                    need_nm.add(nid)
                else:
                    if not raw_vc:
                        raise MarketingError("укажите артикул (vendor_code) или nm_id")
                    need_vc.add(raw_vc)
            except MarketingError as e:
                errors.append({"row": n, "reason": str(e), "raw": raw})
                continue
            parsed.append({"row": n, "raw": raw, "dkey": dkey, "ddate": ddate,
                           "ch_name": ch_name, "dtype": dtype, "title": title,
                           "amount": amount, "raw_nm": raw_nm, "raw_vc": raw_vc,
                           "comment": cell("comment")})

        # 2) карточки — одним запросом по нужным артикулам/nmID
        cards_by_nm, cards_by_vc = await self._cards_for(sorted(need_vc), sorted(need_nm))

        # 3) сборка документов
        for p in parsed:
            n, row_raw = p["row"], p["raw"]
            card = None
            try:
                if p["raw_nm"]:
                    card = cards_by_nm.get(int(p["raw_nm"]))
                    if not card:
                        raise MarketingError(f"nm_id {p['raw_nm']}: карточка не найдена")
                else:
                    card = cards_by_vc.get(p["raw_vc"])
                    if not card:
                        raise MarketingError(f"артикул '{p['raw_vc']}': карточка не найдена")
            except MarketingError as e:
                errors.append({"row": n, "reason": str(e), "raw": row_raw})
                continue

            dkey = p["dkey"]
            ddate = p["ddate"]
            ch_name = p["ch_name"]
            dtype = p["dtype"]
            title = p["title"]
            amount = p["amount"]

            doc = docs.setdefault(dkey or f"{ddate}-{ch_name}-{n}", {
                "document_key": dkey or f"{ddate}-{ch_name}-{n}",
                "document_date": ddate,
                "channel": ch_name,
                "doc_type": dtype,
                "title": title,
                "lines": [],
                "comment": p["comment"],
            })
            if any(l["nm_id"] == card["nmID"] for l in doc["lines"]):
                errors.append({"row": n, "reason": f"SKU {card['nmID']} уже есть в документе "
                                                   f"{doc['document_key']}", "raw": row_raw})
                continue
            doc["lines"].append({"nm_id": card["nmID"], "vendor_code": card["vendorCode"],
                                 "product_title": card["title"], "amount": amount})
            ok_rows += 1

        for doc in docs.values():
            doc["total_amount"] = round(sum(l["amount"] for l in doc["lines"]), 2)
            doc["channel_found"] = str(doc.get("channel") or "").strip().lower() in channels
            doc["channel_id"] = (channels[str(doc["channel"]).strip().lower()]["id"]
                                 if doc["channel_found"] else None)

        return {"documents": list(docs.values()), "errors": errors, "ok_rows": ok_rows}

    async def import_save(self, documents: list[dict]) -> dict:
        """Сохранение разобранного файла. Ошибки в документах не пишем."""
        cid = self._need_company()
        if not documents:
            raise MarketingError("нет строк для сохранения")
        saved = 0
        skipped = 0
        errors: list[dict] = []
        for doc in documents:
            try:
                if not doc.get("channel_id"):
                    raise MarketingError(f"площадка '{doc.get('channel') or ''}' не найдена — "
                                        "заведите её заранее")
                await self.create_document(doc)
                saved += 1
            except MarketingError as e:
                skipped += 1
                errors.append({"document_key": doc.get("document_key"), "reason": str(e)})
        return {"ok": True, "saved": saved, "skipped": skipped, "errors": errors}

    async def export_rows(self, date_from: str | None = None, date_to: str | None = None,
                          channel_id: int | None = None) -> list[dict]:
        """Плоские строки для выгрузки (тот же формат, что и шаблон)."""
        cid = self._need_company()
        params: dict = {"cid": cid}
        where = " WHERE d.company_id = :cid"
        if date_from:
            where += " AND d.document_date >= :d1"
            params["d1"] = str(date_from)[:10]
        if date_to:
            where += " AND d.document_date <= :d2"
            params["d2"] = str(date_to)[:10]
        if channel_id:
            where += " AND d.channel_id = :ch"
            params["ch"] = channel_id
        rows = (await self.db.execute(text(f"""
            SELECT d.document_key, d.document_date, c.name AS channel, d.doc_type, d.title,
                   l.vendor_code, l.nm_id, l.amount, l.comment
            FROM marketing_expense_lines l
            INNER JOIN marketing_expense_documents d ON d.id = l.document_id
            LEFT JOIN marketing_channels c ON c.id = d.channel_id
            {where}
            ORDER BY d.document_date DESC, d.document_key, l.id
            LIMIT 20000"""), params)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["document_date"] = str(d.get("document_date") or "")[:10]
            d["amount"] = float(d.get("amount") or 0)
            out.append(d)
        return out
