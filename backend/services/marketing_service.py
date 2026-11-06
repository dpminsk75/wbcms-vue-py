"""Ручной маркетинг: площадки (marketing_channels) + документы/строки расходов.

Модель (зафиксирована владельцем 2026-11-06):
  marketing_channels            — справочник «кто/где продвигали»: блогер, сайт,
                                  Telegram, YouTube и т.п. + минимальные реквизиты.
  marketing_expense_documents   — один акт/интеграция/договор = один документ.
  marketing_expense_lines       — позиции документа: SKU + сумма (всегда привязаны к nmID).

Расход ВСЕГДА привязан к SKU: строки без nmID не принимаются. Итог документа
считается из строк (total_amount), а не вводится отдельно.

Период размещения (period_start/period_end): расход «растягивается» по дням
периода. В окно отчёта попадает только часть суммы позиции, приходящаяся на
дни пересечения периода размещения с окном отчёта (allocate_days).

Excel: один лист, строки документа и строки SKU связаны document_key.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

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

DOC_TYPES = (
    "blogger_post", "giveaway", "self_buyout", "review_cashback", "other",
    "media", "article", "promo",
)
DOC_TYPE_LABELS = {
    "blogger_post": "Пост у блогера",
    "giveaway": "Раздача",
    "self_buyout": "Самовыкуп",
    "review_cashback": "Кешбек за отзыв",
    "other": "Прочее",
    "media": "Медийная реклама",
    "article": "Статья",
    "promo": "Промокод",
}

# Колонки Excel-шаблона (один лист). period_start/period_end необязательны:
# если их нет в файле, период = document_date (старые файлы не падают).
XLSX_COLUMNS = [
    "document_key", "document_date", "channel", "doc_type", "title",
    "vendor_code", "nm_id", "amount", "comment",
    "period_start", "period_end",
]

# Максимальная длина периода размещения, дней (решение владельца 2026-11-06).
MAX_PERIOD_DAYS = 366


class MarketingError(Exception):
    """Ошибка валидации маркетинговых данных."""


def allocate_days(amount: float, p_start: date, p_end: date) -> list[tuple[date, int]]:
    """Разложить сумму позиции по дням периода — целочисленно, в копейках.

    Сумма частей ТОЧНО равна исходной сумме: остаток от деления на дни
    раздаётся по одной копейке на первые дни периода. Порядок дней
    фиксирован, поэтому результат детерминирован.
    """
    days = (p_end - p_start).days + 1
    if days < 1:
        raise MarketingError("период размещения: конец раньше начала")
    total_kop = int(round(amount * 100))
    base, rem = divmod(total_kop, days)
    return [(p_start + timedelta(days=i), base + (1 if i < rem else 0))
            for i in range(days)]


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


def _period(data: dict, doc_date: str) -> tuple[str, str]:
    """Период размещения из payload. Пустые даты = разовое размещение в дату документа."""
    p_start = str(data.get("period_start") or "").strip() or doc_date
    p_end = str(data.get("period_end") or "").strip() or p_start
    p_start = _date(p_start, "period_start")
    p_end = _date(p_end, "period_end")
    d1 = date.fromisoformat(p_start)
    d2 = date.fromisoformat(p_end)
    if d2 < d1:
        raise MarketingError("period_end: окончание размещения раньше начала")
    if (d2 - d1).days + 1 > MAX_PERIOD_DAYS:
        raise MarketingError(f"период размещения длиннее {MAX_PERIOD_DAYS} дней")
    return p_start, p_end


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
            SELECT d.id, d.document_key, d.document_date, d.period_start, d.period_end,
                   d.channel_id, d.doc_type, d.title,
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
            d["period_start"] = str(d.get("period_start") or d["document_date"])[:10]
            d["period_end"] = str(d.get("period_end") or d["period_start"])[:10]
            d["period_days"] = (date.fromisoformat(d["period_end"])
                                - date.fromisoformat(d["period_start"])).days + 1
            out.append(d)
        return out

    async def get_document(self, document_id: int) -> dict:
        cid = self._need_company()
        row = (await self.db.execute(text("""
            SELECT d.id, d.document_key, d.document_date, d.period_start, d.period_end,
                   d.channel_id, d.doc_type, d.title,
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
        doc["period_start"] = str(doc.get("period_start") or doc["document_date"])[:10]
        doc["period_end"] = str(doc.get("period_end") or doc["period_start"])[:10]
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

    async def create_document(self, data: dict) -> dict:
        """Создать документ с позициями. Позиции всегда привязаны к SKU."""
        cid = self._need_company()
        dkey = str(data.get("document_key") or "").strip()
        ddate = _date(data.get("document_date"), "document_date")
        p_start, p_end = _period(data, ddate)
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
            base_key = f"D-{ddate}-{date.today().strftime('%y%m%d%H%M%S')}"
            dkey = base_key
            for i in range(2, 50):
                dup = (await self.db.execute(text(
                    "SELECT id FROM marketing_expense_documents WHERE company_id=:cid AND document_key=:k LIMIT 1"),
                    {"cid": cid, "k": dkey})).scalar()
                if not dup:
                    break
                dkey = f"{base_key}-{i}"
            else:
                raise MarketingError("не удалось сгенерировать document_key — укажите его вручную")
        else:
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
              (company_id, document_key, document_date, period_start, period_end,
               channel_id, doc_type, title, comment, total_amount, created_by, updated_by)
            VALUES (:cid, :k, :d, :ps, :pe, :ch, :t, :title, :cmt, :total, :uid, :uid)"""),
            {"cid": cid, "k": dkey, "d": ddate, "ps": p_start, "pe": p_end,
             "ch": channel_id, "t": dtype,
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
        p_start, p_end = _period(data, ddate)
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
            SET document_date=:d, period_start=:ps, period_end=:pe,
                channel_id=:ch, doc_type=:t, title=:title,
                comment=:cmt, total_amount=:total, updated_by=:uid
            WHERE id=:id AND company_id=:cid"""),
            {"id": document_id, "cid": cid, "d": ddate, "ps": p_start, "pe": p_end,
             "ch": channel_id, "t": dtype,
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
                # Период размещения: необязательные колонки; без них — разовое
                # размещение в дату документа (старые файлы не падают).
                p_start, p_end = _period({"period_start": cell("period_start"),
                                          "period_end": cell("period_end")}, ddate)
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
                           "p_start": p_start, "p_end": p_end,
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
                "period_start": p["p_start"],
                "period_end": p["p_end"],
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
            SELECT d.document_key, d.document_date, d.period_start, d.period_end,
                   c.name AS channel, d.doc_type, d.title,
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
            d["period_start"] = str(d.get("period_start") or d["document_date"])[:10]
            d["period_end"] = str(d.get("period_end") or d["period_start"])[:10]
            d["amount"] = float(d.get("amount") or 0)
            out.append(d)
        return out

    # ------------------------------------------------- копия и сводка
    async def copy_document(self, document_id: int) -> dict:
        """Копия документа («по образцу»): шапка и позиции, но новая запись.

        Дата документа и период — сегодня (разовое размещение), document_key —
        новый. Исходный документ не меняется.
        """
        cid = self._need_company()
        src = await self.get_document(document_id)
        today = date.today().isoformat()
        payload = {
            "document_key": "",
            "document_date": today,
            "period_start": today,
            "period_end": today,
            "channel_id": src.get("channel_id"),
            "doc_type": src.get("doc_type"),
            "title": src.get("title"),
            "comment": src.get("comment"),
            "lines": [{"nm_id": l["nm_id"], "vendor_code": l.get("vendor_code"),
                       "amount": float(l.get("amount") or 0), "comment": l.get("comment")}
                      for l in (src.get("lines") or [])],
        }
        return await self.create_document(payload)

    async def summary(self, date_from: str | None = None, date_to: str | None = None,
                      channel_id: int | None = None, q: str = "") -> dict:
        """Сводка по окну фильтра: документы, площадки, суммы и «в отчёт».

        «В отчёт» — часть суммы позиций, растянутая по дням периода размещения
        и попавшая в окно отчёта (allocate_days). Период в будущем сюда не
        попадает: пересечения с окном нет.
        """
        cid = self._need_company()
        docs = await self.list_documents(date_from, date_to, channel_id, q, limit=1000)
        if not docs:
            return {"documents": 0, "channels": 0, "total": 0.0, "in_report": 0.0,
                    "by_type": [], "by_channel": []}

        d1 = date.fromisoformat(str(date_from)[:10]) if date_from else None
        d2 = date.fromisoformat(str(date_to)[:10]) if date_to else None
        ids = [d["id"] for d in docs]
        stmt = text("""
            SELECT l.document_id, l.amount
            FROM marketing_expense_lines l
            WHERE l.company_id = :cid AND l.document_id IN :ids""").bindparams(
            bindparam("ids", expanding=True))
        lines = (await self.db.execute(stmt, {"cid": cid, "ids": ids})).mappings().all()
        by_doc: dict[int, float] = {}
        for r in lines:
            by_doc[int(r["document_id"])] = by_doc.get(int(r["document_id"]), 0.0) + float(r["amount"] or 0)

        total = 0.0
        in_report = 0.0
        by_type: dict[str, dict] = {}
        by_channel: dict[str, dict] = {}
        for d in docs:
            amount = by_doc.get(d["id"], 0.0)
            total += amount
            p_start = date.fromisoformat(d["period_start"])
            p_end = date.fromisoformat(d["period_end"])
            doc_in_report = 0
            for day, kop in allocate_days(amount, p_start, p_end):
                if d1 and day < d1:
                    continue
                if d2 and day > d2:
                    continue
                doc_in_report += kop
            in_report += doc_in_report / 100.0
            t_key = d.get("doc_type") or "other"
            t = by_type.setdefault(t_key, {"doc_type": t_key,
                                          "label": DOC_TYPE_LABELS.get(t_key, t_key),
                                          "documents": 0, "total": 0.0, "in_report": 0.0})
            t["documents"] += 1
            t["total"] = round(t["total"] + amount, 2)
            t["in_report"] = round(t["in_report"] + doc_in_report / 100.0, 2)
            c_key = d.get("channel_name") or "—"
            c = by_channel.setdefault(c_key, {"channel": c_key, "documents": 0,
                                               "total": 0.0, "in_report": 0.0})
            c["documents"] += 1
            c["total"] = round(c["total"] + amount, 2)
            c["in_report"] = round(c["in_report"] + doc_in_report / 100.0, 2)

        return {
            "documents": len(docs),
            "channels": len({d.get("channel_id") for d in docs if d.get("channel_id")}),
            "total": round(total, 2),
            "in_report": round(in_report, 2),
            "by_type": sorted(by_type.values(), key=lambda x: -x["total"]),
            "by_channel": sorted(by_channel.values(), key=lambda x: -x["total"]),
        }
