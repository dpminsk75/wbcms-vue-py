"""Правила автоответов wb_reply_rules — порт WbReplyRulesController.

Скоуп company_id строгий (md 2026-09-17 §7.1): фильтр по прямому полю,
записи с company_id из get_current_company(), без OR NULL.
Матчинг/генерация — в feedback_reply_service (shared с test-generation и кроном).
"""


class ReplyRulesService:
    def __init__(self, db, company_id=None):
        self.db = db
        self.company_id = company_id

    def _cw(self, alias="") -> str:
        p = (alias + ".") if alias else ""
        return "" if self.company_id is None else f" AND {p}company_id = :company_id"

    def _cp(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def list(self, page=1, page_size=20) -> dict:
        from sqlalchemy import text
        total = (await self.db.execute(text(
            f"SELECT COUNT(*) AS cnt FROM wb_reply_rules WHERE 1=1{self._cw()}"),
            self._cp())).scalar() or 0
        rows = (await self.db.execute(text(
            f"""SELECT id, title, is_active, rule_type, rating_min, rating_max,
                text_condition, part_separator, created_at, updated_at
                FROM wb_reply_rules WHERE 1=1{self._cw()}
                ORDER BY updated_at DESC LIMIT :lim OFFSET :off"""),
            {**self._cp(), "lim": page_size, "off": (page - 1) * page_size})).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            d["brands"] = await self._brands(d["id"])
            d["products"] = await self._products(d["id"])
            items.append(d)
        return {"items": items, "total": int(total), "page": page, "page_size": page_size}

    async def _brands(self, rule_id: int) -> list:
        from sqlalchemy import text
        rows = (await self.db.execute(text(
            f"SELECT brand_name FROM wb_reply_rule_brands"
            f" WHERE rule_id=:id{self._cw()} ORDER BY brand_name"),
            {"id": rule_id, **self._cp()})).scalars().all()
        return [str(x) for x in rows]

    async def _products(self, rule_id: int) -> list:
        from sqlalchemy import text
        rows = (await self.db.execute(text(
            f"""SELECT p.nmID AS nmID, c.title AS title
                FROM wb_reply_rule_products p
                LEFT JOIN wbcards c ON c.nmID = p.nmID
                WHERE p.rule_id=:id{self._cw('p')}"""),
            {"id": rule_id, **self._cp()})).mappings().all()
        return [dict(r) for r in rows]

    async def get(self, rule_id: int) -> dict | None:
        from sqlalchemy import text
        row = (await self.db.execute(text(
            f"""SELECT id, title, is_active, rule_type, rating_min, rating_max,
                text_condition, part_separator, created_at, updated_at
                FROM wb_reply_rules WHERE id=:id{self._cw()} LIMIT 1"""),
            {"id": rule_id, **self._cp()})).mappings().first()
        if not row:
            return None
        d = dict(row)
        parts = (await self.db.execute(text(
            f"SELECT id, part_type, text FROM wb_reply_template_parts"
            f" WHERE rule_id=:id{self._cw()} ORDER BY id"),
            {"id": rule_id, **self._cp()})).mappings().all()
        d["greetings"] = [p["text"] for p in parts if p["part_type"] == "greeting"]
        d["bodies"] = [p["text"] for p in parts if p["part_type"] == "body"]
        d["signoffs"] = [p["text"] for p in parts if p["part_type"] == "signoff"]
        d["brands"] = await self._brands(rule_id)
        d["products"] = await self._products(rule_id)
        return d

    @staticmethod
    def validate(payload: dict) -> str | None:
        if not str(payload.get("title") or "").strip():
            return "Название правила обязательно"
        if payload.get("rule_type") not in ("general", "brand", "product"):
            return "Некорректный rule_type"
        for k in ("rating_min", "rating_max"):
            try:
                v = int(payload.get(k))
            except (TypeError, ValueError):
                return f"Некорректный {k}"
            if v < 1 or v > 5:
                return f"{k} должен быть 1-5"
        if payload.get("text_condition") not in ("any", "with_text", "no_text"):
            return "Некорректный text_condition"
        if payload.get("part_separator") not in ("space", "newline", "paragraph"):
            return "Некорректный part_separator"
        return None

    async def save(self, rule_id: int | None, p: dict) -> int:
        from sqlalchemy import text
        import time
        now = int(time.time())
        err = self.validate(p)
        if err:
            raise ValueError(err)
        title = str(p["title"]).strip()
        rmin, rmax = int(p["rating_min"]), int(p["rating_max"])
        if rule_id is None:
            await self.db.execute(text(
                """INSERT INTO wb_reply_rules(title, is_active, rule_type, rating_min, rating_max,
                    text_condition, part_separator, created_at, updated_at, company_id)
                    VALUES(:t, :a, :rt, :rmin, :rmax, :tc, :ps, :now, :now, :cid)"""),
                {"t": title, "a": int(p.get("is_active", 1)),
                 "rt": p["rule_type"], "rmin": rmin, "rmax": rmax,
                 "tc": p["text_condition"], "ps": p["part_separator"],
                 "now": now, "cid": self.company_id})
            rule_id = int((await self.db.execute(text("SELECT LAST_INSERT_ID()"))).scalar() or 0)
        else:
            res = await self.db.execute(text(
                f"""UPDATE wb_reply_rules SET title=:t, is_active=:a, rule_type=:rt,
                    rating_min=:rmin, rating_max=:rmax, text_condition=:tc,
                    part_separator=:ps, updated_at=:now WHERE id=:id{self._cw()}"""),
                {"t": title, "a": int(p.get("is_active", 1)),
                 "rt": p["rule_type"], "rmin": rmin, "rmax": rmax,
                 "tc": p["text_condition"], "ps": p["part_separator"],
                 "now": now, "id": rule_id, **self._cp()})
            if (res.rowcount or 0) == 0:
                raise LookupError("rule not found")
        await self.db.execute(
            text("DELETE FROM wb_reply_template_parts WHERE rule_id=:id"), {"id": rule_id})
        for ptype, key in (("greeting", "greetings"), ("body", "bodies"), ("signoff", "signoffs")):
            for t in (p.get(key) or []):
                t = str(t or "").strip()
                if not t:
                    continue
                await self.db.execute(text(
                    "INSERT INTO wb_reply_template_parts(rule_id, part_type, text, company_id)"
                    " VALUES(:r, :pt, :t, :cid)"),
                    {"r": rule_id, "pt": ptype, "t": t, "cid": self.company_id})
        await self.db.execute(
            text("DELETE FROM wb_reply_rule_brands WHERE rule_id=:id"), {"id": rule_id})
        if p["rule_type"] == "brand":
            for b in (p.get("brands") or []):
                b = str(b or "").strip()
                if b:
                    await self.db.execute(text(
                        "INSERT INTO wb_reply_rule_brands(rule_id, brand_name, company_id)"
                        " VALUES(:r, :b, :cid)"),
                        {"r": rule_id, "b": b, "cid": self.company_id})
        await self.db.execute(
            text("DELETE FROM wb_reply_rule_products WHERE rule_id=:id"), {"id": rule_id})
        if p["rule_type"] == "product":
            for nm in (p.get("product_ids") or []):
                try:
                    nm = int(nm)
                except (TypeError, ValueError):
                    continue
                if nm > 0:
                    await self.db.execute(text(
                        "INSERT INTO wb_reply_rule_products(rule_id, nmID, company_id)"
                        " VALUES(:r, :n, :cid)"),
                        {"r": rule_id, "n": nm, "cid": self.company_id})
        await self.db.commit()
        return rule_id

    async def delete(self, rule_id: int) -> bool:
        from sqlalchemy import text
        await self.db.execute(
            text("DELETE FROM wb_reply_template_parts WHERE rule_id=:id"), {"id": rule_id})
        await self.db.execute(
            text("DELETE FROM wb_reply_rule_brands WHERE rule_id=:id"), {"id": rule_id})
        await self.db.execute(
            text("DELETE FROM wb_reply_rule_products WHERE rule_id=:id"), {"id": rule_id})
        res = await self.db.execute(text(
            f"DELETE FROM wb_reply_rules WHERE id=:id{self._cw()}"),
            {"id": rule_id, **self._cp()})
        await self.db.commit()
        return (res.rowcount or 0) > 0

    async def toggle(self, rule_id: int) -> int | None:
        from sqlalchemy import text
        import time
        cur = (await self.db.execute(text(
            f"SELECT is_active FROM wb_reply_rules WHERE id=:id{self._cw()}"),
            {"id": rule_id, **self._cp()})).scalar()
        if cur is None:
            return None
        new = 0 if int(cur) else 1
        await self.db.execute(text(
            "UPDATE wb_reply_rules SET is_active=:a, updated_at=:u WHERE id=:id"),
            {"a": new, "u": int(time.time()), "id": rule_id})
        await self.db.commit()
        return new

    async def product_list(self, q: str) -> list:
        from sqlalchemy import text
        if not (q or "").strip():
            return []
        rows = (await self.db.execute(text(
            """SELECT CAST(nmID AS CHAR) AS id, CONCAT('[', nmID, '] ', title) AS text
                FROM wbcards
                WHERE title LIKE :q OR CAST(nmID AS CHAR) LIKE :q
                ORDER BY nmID DESC LIMIT 20"""),
            {"q": f"%{q.strip()}%"})).mappings().all()
        return [dict(r) for r in rows]

    async def brand_list(self, q: str) -> list:
        from sqlalchemy import text
        if not (q or "").strip():
            return []
        rows = (await self.db.execute(text(
            """SELECT DISTINCT brand AS id, brand AS text FROM wbcards
                WHERE brand LIKE :q AND brand IS NOT NULL AND brand != ''
                ORDER BY brand LIMIT 20"""),
            {"q": f"%{q.strip()}%"})).mappings().all()
        return [dict(r) for r in rows]