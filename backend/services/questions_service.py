"""Вопросы покупателей WB (таблица wb_questions) — чтение для страницы «Вопросы»."""
from sqlalchemy import text

# Статусы WB: none — отклонён продавцом, wbRu — ответ есть,
# suppliersPortalSynch — новый вопрос без ответа.
STATE_LABELS = {
    "none": "Отклонён",
    "wbRu": "Есть ответ",
    "suppliersPortalSynch": "Без ответа",
}


class QuestionsService:
    def __init__(self, db, company_id=None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND q.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    def _filters(self, date_from, date_to, nm_id, status, q) -> tuple:
        where = ["1=1" + self._company_where()]
        params: dict = {**self._company_params()}
        if date_from:
            where.append("q.created_date >= :d1")
            params["d1"] = f"{date_from} 00:00:00"
        if date_to:
            where.append("q.created_date <= :d2")
            params["d2"] = f"{date_to} 23:59:59"
        if nm_id not in (None, ""):
            where.append("q.nm_id = :nm_id")
            params["nm_id"] = int(nm_id)
        if status == "unanswered":
            where.append("(q.answer_text IS NULL OR q.answer_text = '')")
        elif status == "answered":
            where.append("(q.answer_text IS NOT NULL AND q.answer_text <> '')")
        elif status == "rejected":
            where.append("q.state = 'none'")
        elif status == "warned":
            where.append("q.is_warned = 1")
        if q not in (None, ""):
            # поиск по своей (маленькой) таблице вопросов
            where.append("(q.q_text LIKE :search OR q.answer_text LIKE :search "
                         "OR q.product_name LIKE :search OR q.supplier_article LIKE :search)")
            params["search"] = f"%{str(q).strip()}%"
        return " AND ".join(where), params

    @staticmethod
    def _serialize(row: dict) -> dict:
        d = dict(row)
        d["created_date"] = str(d.get("created_date") or "")
        d["answer_date"] = str(d.get("answer_date") or "") or None
        state = d.get("state") or ""
        has_answer = 1 if str(d.get("answer_text") or "").strip() else 0
        d["has_answer"] = has_answer
        # подпись — по факту ответа, а не только по state WB: ответ мог прийти,
        # а state ещё не обновился (и наоборот)
        if state == "none":
            d["state_label"] = STATE_LABELS["none"]
        elif has_answer:
            d["state_label"] = STATE_LABELS["wbRu"]
        elif state:
            d["state_label"] = STATE_LABELS.get(state, state)
        else:
            d["state_label"] = "—"
        for k in ("nm_id", "imt_id", "was_viewed", "is_warned", "answer_editable"):
            if d.get(k) is not None:
                try:
                    d[k] = int(d[k])
                except (TypeError, ValueError):
                    pass
        return d

    async def list(self, date_from=None, date_to=None, nm_id=None, status=None,
                   q=None, sort="created_date", order="desc", page=1,
                   page_size=30) -> dict:
        where_sql, params = self._filters(date_from, date_to, nm_id, status, q)
        col = {"created_date": "q.created_date",
               "answer_date": "q.answer_date",
               "state": "q.state"}.get(sort or "", "q.created_date")
        direction = "ASC" if str(order).lower() == "asc" else "DESC"
        total = (await self.db.execute(text(
            f"SELECT COUNT(*) AS cnt FROM wb_questions q WHERE {where_sql}"),
            params)).scalar() or 0
        rows = (await self.db.execute(text(
            f"""SELECT q.id, q.nm_id, q.imt_id, q.product_name, q.supplier_article,
                       q.supplier_name, q.brand_name, q.q_text, q.answer_text,
                       q.answer_editable, q.answer_date, q.state, q.was_viewed,
                       q.is_warned, q.created_date, q.updated_at,
                       c.title AS card_title, c.vendorCode AS card_vendor,
                       c.subjectName AS card_subject, c.brand AS card_brand,
                       c.photos AS card_photos
                FROM wb_questions q
                LEFT JOIN wbcards c ON c.nmID = q.nm_id
                WHERE {where_sql}
                ORDER BY {col} {direction}, q.id DESC
                LIMIT :lim OFFSET :off"""),
            {**params, "lim": int(page_size), "off": (int(page) - 1) * int(page_size)}
        )).mappings().all()
        return {"items": [self._serialize(r) for r in rows],
                "total": int(total), "page": int(page), "page_size": int(page_size)}

    async def stats(self, date_from=None, date_to=None) -> dict:
        """Счётчики для KPI-плиток: по тому же периоду, что и таблица."""
        where_sql, params = self._filters(date_from, date_to, None, None, None)
        row = (await self.db.execute(text(
            f"""SELECT COUNT(*) AS total,
                       SUM(CASE WHEN q.answer_text IS NULL OR q.answer_text = '' THEN 1 ELSE 0 END) AS unanswered,
                       SUM(CASE WHEN q.answer_text IS NOT NULL AND q.answer_text <> '' THEN 1 ELSE 0 END) AS answered,
                       SUM(CASE WHEN q.state = 'none' THEN 1 ELSE 0 END) AS rejected,
                       SUM(CASE WHEN q.is_warned = 1 THEN 1 ELSE 0 END) AS warned,
                       MAX(q.updated_at) AS last_sync
                FROM wb_questions q WHERE {where_sql}"""),
            params)).mappings().first()
        s = dict(row) if row else {}
        last = s.get("last_sync")
        return {
            "total": int(s.get("total") or 0),
            "unanswered": int(s.get("unanswered") or 0),
            "answered": int(s.get("answered") or 0),
            "rejected": int(s.get("rejected") or 0),
            "warned": int(s.get("warned") or 0),
            "last_sync": int(last) if last else None,
        }

    async def get(self, qid: str) -> dict | None:
        row = (await self.db.execute(text(
            """SELECT q.id, q.nm_id, q.imt_id, q.product_name, q.supplier_article,
                      q.supplier_name, q.brand_name, q.q_text, q.answer_text,
                      q.answer_editable, q.answer_date, q.state, q.was_viewed,
                      q.is_warned, q.created_date, q.updated_at,
                      c.title AS card_title, c.vendorCode AS card_vendor,
                      c.subjectName AS card_subject, c.brand AS card_brand,
                      c.photos AS card_photos
               FROM wb_questions q
               LEFT JOIN wbcards c ON c.nmID = q.nm_id
               WHERE q.id = :qid""" + self._company_where(),
            {"qid": qid, **self._company_params()}))).mappings().first()
        return self._serialize(dict(row)) if row else None
