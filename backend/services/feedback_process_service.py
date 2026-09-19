"""Запуск по расписанию для process-feedback: select_pending → send → verify → mark.

Чистая выборка кандидатов (БЕЗ отправки) — порт processPeriod:119-132.
Отправка — в feedback_wb_sender.send_answer (там HTTP + verify + mark):
воркер process вызывает этот модуль для списка, затем sender для каждого.
Деление dry-run/send по модулям — требование под будущий cron.
"""


class FeedbackProcessService:
    def __init__(self, db, company_id=None):
        self.db = db
        self.company_id = company_id

    async def select_pending(self, date_from: str, date_to: str) -> list:
        """Отзывы без ответа под автоответ: is_auto_replied=0, valuation>0,
        text/pros/cons пустые, answer пустой, createdDate в окне, своя company."""
        from sqlalchemy import text
        where = [
            "f.company_id = :cid" if self.company_id is not None else "1=1",
            "f.createdDate BETWEEN :d1 AND :d2",
            "f.is_auto_replied = 0",
            "f.productValuation > 0",
            "(f.text IS NULL OR f.text = '')",
            "(f.pros IS NULL OR f.pros = '')",
            "(f.cons IS NULL OR f.cons = '')",
            "(f.answer IS NULL OR f.answer = '' OR f.answer = 'null')",
        ]
        params: dict = {
            "d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59",
        }
        if self.company_id is not None:
            params["cid"] = self.company_id
        rows = (await self.db.execute(text(
            f"""SELECT f.*, c.title AS card_title, c.brand AS card_brand
                FROM wb_feedbacks f
                LEFT JOIN wbcards c ON c.nmID = f.nmID
                WHERE {' AND '.join(where)}
                ORDER BY f.createdDate ASC"""),
            params)).mappings().all()
        return [dict(r) for r in rows]
