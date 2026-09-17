"""Отзывы wb_feedbacks — порт WbFeedbackAnswersController::actionIndex."""


def decode_json_field(raw):
    """Порт $decodeJsonField (views/wb-feedback-answers/index.php:20-32)."""
    import json
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s == "null":
        return None
    try:
        v = json.loads(s)
    except (TypeError, ValueError):
        return None
    for _ in range(3):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except (TypeError, ValueError):
                return None
        else:
            break
    return v


class FeedbackService:
    def __init__(self, db, company_id=None):
        self.db = db
        self.company_id = company_id

    def _company_where(self) -> str:
        return "" if self.company_id is None else " AND f.company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    def _filters(self, date_from, date_to, nm_id, rating,
                 status, has_media, paid_only) -> tuple:
        where = ["1=1" + self._company_where()]
        params: dict = {**self._company_params()}
        if date_from:
            where.append("f.createdDate >= :d1")
            params["d1"] = f"{date_from} 00:00:00"
        if date_to:
            where.append("f.createdDate <= :d2")
            params["d2"] = f"{date_to} 23:59:59"
        if nm_id not in (None, ""):
            where.append("f.nmID = :nm_id")
            params["nm_id"] = int(nm_id)
        if rating not in (None, ""):
            where.append("f.productValuation = :rating")
            params["rating"] = int(rating)
        if status == "answered":
            where.append("(f.answer IS NOT NULL AND f.answer != '' AND f.answer != 'null')")
        elif status == "not_answered":
            where.append("(f.answer IS NULL OR f.answer = '' OR f.answer = 'null')")
        if has_media:
            where.append("((f.photoLinks IS NOT NULL AND f.photoLinks NOT IN ('', 'null', '[]'))"
                         " OR (f.video IS NOT NULL AND f.video NOT IN ('', 'null', '{}')))")
        if paid_only:
            where.append("f.f_cost > 0")
        return " AND ".join(where), params

    @staticmethod
    def _serialize(row: dict) -> dict:
        d = dict(row)
        for k in ("createdDate", "updatedDate"):
            if d.get(k) is not None:
                d[k] = str(d[k])
        photos = decode_json_field(d.get("photoLinks"))
        d["photoLinks"] = photos if isinstance(photos, list) else []
        video = decode_json_field(d.get("video"))
        d["video"] = video if isinstance(video, dict) else None
        bables = decode_json_field(d.get("bables"))
        d["bables"] = [str(t).strip() for t in bables if str(t).strip()] \
            if isinstance(bables, list) else []
        ans = decode_json_field(d.get("answer"))
        if isinstance(ans, dict) and ans.get("text") is not None:
            d["answer_text"] = str(ans.get("text"))
        elif isinstance(ans, str):
            d["answer_text"] = ans
        elif ans is None:
            d["answer_text"] = None
        else:
            d["answer_text"] = str(d.get("answer"))
        for k in ("f_cost", "productValuation", "nmID", "is_auto_replied", "rule_id"):
            if d.get(k) is not None:
                try:
                    d[k] = int(d[k])
                except (TypeError, ValueError):
                    pass
        return d

    async def list(self, date_from=None, date_to=None, nm_id=None, rating=None,
                   status=None, has_media=False, paid_only=False,
                   sort="createdDate", order="desc", page=1, page_size=30) -> dict:
        from sqlalchemy import text
        where_sql, params = self._filters(
            date_from, date_to, nm_id, rating, status, has_media, paid_only)
        col = {"createdDate": "f.createdDate",
               "productValuation": "f.productValuation"}.get(sort or "", "f.createdDate")
        direction = "ASC" if str(order).lower() == "asc" else "DESC"
        total = (await self.db.execute(text(
            f"SELECT COUNT(*) AS cnt FROM wb_feedbacks f WHERE {where_sql}"),
            params)).scalar() or 0
        rows = (await self.db.execute(text(
            f"""SELECT f.id, f.nmID, f.userName, f.productValuation, f.text, f.pros, f.cons,
                f.answer, f.is_auto_replied, f.rule_id, f.createdDate, f.updatedDate,
                f.photoLinks, f.video, f.f_cost, f.bables,
                c.title AS product_title, rr.title AS rule_title
                FROM wb_feedbacks f
                LEFT JOIN wbcards c ON c.nmID = f.nmID
                LEFT JOIN wb_reply_rules rr ON rr.id = f.rule_id
                WHERE {where_sql}
                ORDER BY {col} {direction} LIMIT :lim OFFSET :off"""),
            {**params, "lim": page_size, "off": (page - 1) * page_size})).mappings().all()
        return {"items": [self._serialize(r) for r in rows],
                "total": int(total), "page": page, "page_size": page_size}

    async def tags_sentiment(self) -> dict:
        from sqlalchemy import text
        rows = (await self.db.execute(
            text("SELECT tag_text, sentiment FROM wb_feedback_tags"))).mappings().all()
        return {str(r["tag_text"]): r["sentiment"] for r in rows}

    async def rules_options(self) -> list:
        from sqlalchemy import text
        where = "1=1" if self.company_id is None else "company_id = :company_id"
        params = {} if self.company_id is None else {"company_id": self.company_id}
        rows = (await self.db.execute(
            text(f"SELECT id, title FROM wb_reply_rules WHERE {where} ORDER BY id"),
            params)).mappings().all()
        return [dict(r) for r in rows]


    async def list_tags(self, filt: str = "unclassified") -> list:
        from sqlalchemy import text
        sql = "SELECT id, tag_text, sentiment, usage_count FROM wb_feedback_tags"
        params: dict = {}
        if filt == "unclassified":
            sql += " WHERE sentiment = 'neutral'"
        sql += " ORDER BY usage_count DESC"
        rows = (await self.db.execute(text(sql), params)).mappings().all()
        return [dict(r) for r in rows]

    async def set_sentiment(self, tag_id: int, sentiment: str) -> bool:
        from sqlalchemy import text
        import time
        if sentiment not in ("positive", "negative", "neutral"):
            return False
        res = await self.db.execute(text(
            "UPDATE wb_feedback_tags SET sentiment=:s, updated_at=:u WHERE id=:id"),
            {"s": sentiment, "u": int(time.time()), "id": tag_id})
        await self.db.commit()
        return (res.rowcount or 0) > 0

    async def sync_tags(self) -> dict:
        """Порт commands/WbFeedbackTagsController::actionSync: скан bables → upsert."""
        from sqlalchemy import text
        import time
        counts: dict = {}
        total_rows = 0
        offset = 0
        batch = 1000
        while True:
            rows = (await self.db.execute(text(
                "SELECT bables FROM wb_feedbacks"
                " WHERE bables IS NOT NULL AND bables NOT IN ('', 'null', '[]')"
                " LIMIT :lim OFFSET :off"),
                {"lim": batch, "off": offset})).mappings().all()
            if not rows:
                break
            for r in rows:
                total_rows += 1
                tags = decode_json_field(r.get("bables"))
                if not isinstance(tags, list):
                    continue
                for t in tags:
                    t = str(t).strip()
                    if t:
                        counts[t] = counts.get(t, 0) + 1
            offset += batch
        now = int(time.time())
        new_tags = 0
        updated_tags = 0
        for tag_text, usage in counts.items():
            exists = (await self.db.execute(text(
                "SELECT id FROM wb_feedback_tags WHERE tag_text=:t"),
                {"t": tag_text})).scalar()
            if exists:
                await self.db.execute(text(
                    "UPDATE wb_feedback_tags SET usage_count=:u, updated_at=:n WHERE id=:id"),
                    {"u": usage, "n": now, "id": exists})
                updated_tags += 1
            else:
                await self.db.execute(text(
                    "INSERT INTO wb_feedback_tags(tag_text, sentiment, usage_count, created_at, updated_at)"
                    " VALUES(:t, 'neutral', :u, :n, :n)"),
                    {"t": tag_text, "u": usage, "n": now})
                new_tags += 1
        await self.db.commit()
        return {"ok": True, "rows_scanned": total_rows,
                "unique_tags": len(counts), "new_tags": new_tags, "updated_tags": updated_tags}
