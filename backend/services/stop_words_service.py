"""Стоп-слова автоответов wb_reply_stop_words (company_id строгий, md §7.1).

Логика (новая, в Yii2 её не было — таблица мёртвая):
- слова хранятся в нижнем регистре (комментарий structure.sql:2161),
- проверка — подстрока по склейке text+pros+cons (lower),
- только is_active=1 своей company,
- сработало → match_rule возвращает None + reason='stop_word'.
Используют: preview (показывает причину) и воркер (пропуск, не отправка).
"""


class StopWordsService:
    def __init__(self, db, company_id=None):
        self.db = db
        self.company_id = company_id

    async def list(self) -> list:
        from sqlalchemy import text
        where = "1=1" if self.company_id is None else "company_id = :company_id"
        params = {} if self.company_id is None else {"company_id": self.company_id}
        rows = (await self.db.execute(text(
            f"SELECT id, word, is_active FROM wb_reply_stop_words"
            f" WHERE {where} ORDER BY word"),
            params)).mappings().all()
        return [dict(r) for r in rows]

    async def create(self, word: str) -> dict:
        from sqlalchemy import text
        w = str(word or "").strip().lower()
        if not w:
            raise ValueError("Слово пустое")
        exists = (await self.db.execute(text(
            "SELECT id FROM wb_reply_stop_words WHERE word=:w"),
            {"w": w})).scalar()
        if exists:
            raise ValueError("Такое слово уже есть")
        await self.db.execute(text(
            "INSERT INTO wb_reply_stop_words(word, is_active, company_id)"
            " VALUES(:w, 1, :cid)"),
            {"w": w, "cid": self.company_id})
        row_id = int((await self.db.execute(text("SELECT LAST_INSERT_ID()"))).scalar() or 0)
        await self.db.commit()
        return {"ok": True, "id": row_id}

    async def toggle(self, word_id: int) -> int | None:
        from sqlalchemy import text
        scope = "" if self.company_id is None else " AND company_id = :company_id"
        cur = (await self.db.execute(text(
            f"SELECT is_active FROM wb_reply_stop_words WHERE id=:id{scope}"),
            {"id": word_id, **({} if self.company_id is None else {"company_id": self.company_id})})
        ).scalar()
        if cur is None:
            return None
        new = 0 if int(cur) else 1
        await self.db.execute(text(
            "UPDATE wb_reply_stop_words SET is_active=:a WHERE id=:id"),
            {"a": new, "id": word_id})
        await self.db.commit()
        return new

    async def remove(self, word_id: int) -> bool:
        from sqlalchemy import text
        scope = "" if self.company_id is None else " AND company_id = :company_id"
        res = await self.db.execute(text(
            f"DELETE FROM wb_reply_stop_words WHERE id=:id{scope}"),
            {"id": word_id, **({} if self.company_id is None else {"company_id": self.company_id})})
        await self.db.commit()
        return (res.rowcount or 0) > 0

    async def active_words(self) -> list:
        """Активные слова своей company для проверки отзывов."""
        from sqlalchemy import text
        where = "is_active = 1" if self.company_id is None \
            else "is_active = 1 AND company_id = :company_id"
        params = {} if self.company_id is None else {"company_id": self.company_id}
        rows = (await self.db.execute(text(
            f"SELECT word FROM wb_reply_stop_words WHERE {where}"),
            params)).scalars().all()
        return [str(w) for w in rows if str(w or "").strip()]

    @staticmethod
    def find_hit(words: list, fb: dict) -> str | None:
        """Первое стоп-слово, встретившееся в text+pros+cons (lower, подстрока)."""
        hay = " ".join(str(fb.get(k) or "") for k in ("text", "pros", "cons")).lower()
        for w in words:
            if w and w in hay:
                return w
        return None
