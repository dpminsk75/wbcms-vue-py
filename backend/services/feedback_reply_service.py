"""Матчинг правил и сборка текста автоответа.

Порт: WbReplyRulesController::actionTestGeneration (матчинг+сборка) ==
commands/WbAutoReplyController::generateReplyText (дословно, включая
{{без_имени}} и приоритеты product>brand>general).

Чистая математика (БЕЗ HTTP, БЕЗ отправки) — используется везде:
- GET /api/reply-rules/test-generation (предпросмотр, ничего не отправляет),
- будущий фоновый воркер process (cron): sync → select_pending → match+build → send → verify → mark.
Отправка в WB и запись is_auto_replied живут ТОЛЬКО в send-слое (wb_sender),
а не здесь: этот модуль dry-run-безопасен по построению.
"""
import random
import re


class FeedbackReplyService:
    def __init__(self, db, company_id=None):
        self.db = db
        self.company_id = company_id

    def _cp(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def match_rule(self, fb: dict, _stop_words: list | None = None):
        """Порт generateReplyText:318-354: рейтинг + text_condition,
        приоритет product(1) > brand(2) > general(3), внутри — первое.
        Стоп-слова (НОВОЕ, в Yii2 проверки не было): если слово из активных
        стоп-слов своей company встретилось в text+pros+cons → None.
        Возвращает dict правила или None. company_id строгий (md §7.1 п.6)."""
        from sqlalchemy import text
        if _stop_words is None:
            from backend.services.stop_words_service import StopWordsService
            _stop_words = await StopWordsService(self.db, self.company_id).active_words()
        if _stop_words:
            from backend.services.stop_words_service import StopWordsService
            if StopWordsService.find_hit(_stop_words, fb):
                return None
        rating = int(fb.get("productValuation") or 5)
        has_text = bool(str(fb.get("text") or "").strip())
        scope = "" if self.company_id is None else " AND company_id = :company_id"
        rules = (await self.db.execute(text(
            f"SELECT * FROM wb_reply_rules WHERE is_active = 1{scope}"),
            self._cp())).mappings().all()
        best: dict = {}
        for r in rules:
            if rating < int(r["rating_min"]) or rating > int(r["rating_max"]):
                continue
            if r["text_condition"] == "with_text" and not has_text:
                continue
            if r["text_condition"] == "no_text" and has_text:
                continue
            if r["rule_type"] == "product":
                rows = await self._link("wb_reply_rule_products", r["id"], fb.get("nmID"), "nmID")
                if rows:
                    best.setdefault(1, []).append(r)
            elif r["rule_type"] == "brand":
                if fb.get("card_brand"):
                    rows = await self._link(
                        "wb_reply_rule_brands", r["id"], fb["card_brand"], "brand_name")
                    if rows:
                        best.setdefault(2, []).append(r)
            else:
                best.setdefault(3, []).append(r)
        return best.get(1, [None])[0] or best.get(2, [None])[0] or best.get(3, [None])[0]

    async def _link(self, table: str, rule_id: int, val, col: str) -> bool:
        from sqlalchemy import text
        scope = "" if self.company_id is None else " AND company_id = :company_id"
        row = (await self.db.execute(text(
            f"SELECT 1 FROM {table} WHERE rule_id=:r AND {col}=:v{scope} LIMIT 1"),
            {"r": rule_id, "v": val, **self._cp()})).scalar()
        return row is not None


    async def generate_text(self, fb: dict, seed=None) -> dict:
        """Порт generateReplyText:360-413 + test-generation:349-406.
        Возвращает {text, rule, part_ids, stop_hit} или {text: None, rule: None}.
        seed — для детерминированного предпросмотра (test-generation),
        None — случайный выбор как в кроне."""
        from sqlalchemy import text
        rule = await self.match_rule(fb)
        if not rule:
            from backend.services.stop_words_service import StopWordsService
            words = await StopWordsService(self.db, self.company_id).active_words()
            hit = StopWordsService.find_hit(words, fb)
            return {"text": None, "rule": None, "part_ids": {},
                    "stop_hit": hit}
        rnd = random.Random(seed) if seed is not None else random
        scope = "" if self.company_id is None else " AND company_id = :company_id"
        parts = (await self.db.execute(text(
            f"SELECT id, part_type, text FROM wb_reply_template_parts"
            f" WHERE rule_id=:r{scope} ORDER BY id"),
            {"r": rule["id"], **self._cp()})).mappings().all()
        by_type: dict = {}
        for p in parts:
            by_type.setdefault(p["part_type"], {})[p["id"]] = p["text"]
        user_name = str(fb.get("userName") or "").strip()
        has_name = bool(user_name)
        out: list = []
        debug = {"rule_id": rule["id"], "greeting_id": None,
                 "body_id": None, "signoff_id": None}
        greetings = by_type.get("greeting", {})
        if greetings:
            special = {i: re.sub(r"\{\{без_имени\}\}", "", t, flags=re.I)
                       for i, t in greetings.items() if "{{без_имени}}" in t.lower()}
            fallback = {i: t for i, t in greetings.items() if "{{без_имени}}" not in t.lower()}
            if not has_name and special:
                pid = rnd.choice(list(special))
                out.append(special[pid])
                debug["greeting_id"] = pid
            elif fallback:
                pid = rnd.choice(list(fallback))
                out.append(fallback[pid])
                debug["greeting_id"] = pid
        bodies = by_type.get("body", {})
        if bodies:
            pid = rnd.choice(list(bodies))
            out.append(bodies[pid])
            debug["body_id"] = pid
        signoffs = by_type.get("signoff", {})
        if signoffs:
            pid = rnd.choice(list(signoffs))
            out.append(signoffs[pid])
            debug["signoff_id"] = pid
        sep = {"space": " ", "newline": "\n", "paragraph": "\n\n"}.get(
            rule.get("part_separator") or "newline", "\n")
        text_out = sep.join([p for p in out if p])
        if has_name:
            text_out = re.sub(r"\{\{имя\}\}", user_name, text_out, flags=re.I)
        else:
            text_out = re.sub(r"\{\{имя\}\}", "", text_out, flags=re.I)
            text_out = text_out.replace("  ", " ")
        return {"text": text_out.strip(), "rule": dict(rule), "part_ids": debug,
                "stop_hit": None}

    async def preview(self, date_from=None, date_to=None, limit=100, seed=42) -> list:
        """100 последних отзывов компании → [{feedback, matched_rule, generated_text}].
        Детерминирован (seed) — один предпросмотр при перезагрузке.
        Ничего не отправляет и не пишет в БД."""
        from sqlalchemy import text
        where = ["1=1" + ("" if self.company_id is None else " AND f.company_id = :company_id")]
        params: dict = {**self._cp()}
        if date_from:
            where.append("f.createdDate >= :d1")
            params["d1"] = f"{date_from} 00:00:00"
        if date_to:
            where.append("f.createdDate <= :d2")
            params["d2"] = f"{date_to} 23:59:59"
        rows = (await self.db.execute(text(
            f"""SELECT f.*, c.title AS card_title, c.brand AS card_brand
                FROM wb_feedbacks f
                LEFT JOIN wbcards c ON c.nmID = f.nmID
                WHERE {' AND '.join(where)}
                ORDER BY f.created_at DESC LIMIT :lim"""),
            {**params, "lim": limit})).mappings().all()
        out = []
        for i, r in enumerate(rows):
            fb = dict(r)
            gen = await self.generate_text(fb, seed=(seed + i if seed is not None else None))
            for k in ("createdDate", "updatedDate"):
                if fb.get(k) is not None:
                    fb[k] = str(fb[k])
            out.append({
                "feedback": fb,
                "matched_rule": gen["rule"],
                "generated_text": gen["text"],
                "part_ids": gen["part_ids"],
                "stop_hit": gen.get("stop_hit"),
            })
        return out
