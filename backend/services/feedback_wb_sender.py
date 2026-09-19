"""HTTP-слой отправки ответов в WB (порт sendAnswerToWb + checkPublishedAnswer + mark).

Отдельный модуль под cron: process вызывает match+build (feedback_reply_service),
затем sender.send_answer (POST → sleep 3 → verify → mark answer/is_auto_replied=1/rule_id).
Без httpx-зависимостей: stdlib urllib (requirements не трогаем).

НЕ вызывать из превью/test-generation — только воркер process / ручной reply.
"""


def encode_answer(answer_text: str) -> str:
    import json
    return json.dumps({"text": answer_text, "state": "published"}, ensure_ascii=False)


class FeedbackWbSender:
    URL_ANSWER = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
    URL_GET = "https://feedbacks-api.wildberries.ru/api/v1/feedback?id="

    def __init__(self, db, api_key: str):
        self.db = db
        self.api_key = api_key

    def _headers(self) -> dict:
        return {"Authorization": self.api_key, "Content-Type": "application/json"}

    def post_answer(self, feedback_id: str, text_out: str) -> dict:
        """POST answer → {success, http_code, body} (порт sendAnswerToWb:421-438)."""
        import json
        import urllib.request
        payload = json.dumps({"id": feedback_id, "text": text_out}, ensure_ascii=False).encode()
        req = urllib.request.Request(self.URL_ANSWER, data=payload,
                                     headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return {"success": resp.status in (200, 204),
                        "http_code": resp.status, "body": resp.read().decode() or ""}
        except Exception as e:
            code = getattr(getattr(e, "headers", None), "status", None) or getattr(e, "code", 0)
            try:
                body = e.read().decode()  # type: ignore[attr-defined]
            except Exception:
                body = str(e)
            return {"success": False, "http_code": int(code or 0), "body": body}

    def verify_published(self, feedback_id: str):
        """GET feedback → текст ответа или False (порт checkPublishedAnswer:443-465)."""
        import json
        import urllib.request
        req = urllib.request.Request(self.URL_GET + str(feedback_id), headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode() or "{}")
        except Exception:
            return False
        try:
            t = data["data"]["answer"]["text"]
            return t if str(t or "").strip() else False
        except (KeyError, TypeError):
            return False

    async def mark_replied(self, feedback_id: str, rule_id: int | None, published: str) -> None:
        """answer/is_auto_replied=1/rule_id — порт :186-191 / :301-306."""
        from sqlalchemy import text
        import time
        await self.db.execute(text(
            "UPDATE wb_feedbacks SET answer=:a, is_auto_replied=1,"
            " rule_id=:r, updated_at=:u WHERE id=:id"),
            {"a": encode_answer(published), "r": rule_id,
             "u": int(time.time()), "id": feedback_id})
        await self.db.commit()

    async def send_answer(self, fb: dict, text_out: str, rule_id: int | None) -> dict:
        """Полный цикл одного отзыва: POST → sleep 3 → verify → mark.
        Повторяемость: cron увидит is_auto_replied=1 и пропустит (идемпотентность)."""
        import time
        post = self.post_answer(str(fb["id"]), text_out)
        if not post["success"]:
            return {"ok": False, "stage": "post", **post}
        time.sleep(3)
        published = self.verify_published(str(fb["id"]))
        if not published:
            return {"ok": False, "stage": "verify", **post}
        await self.mark_replied(str(fb["id"]), rule_id, published)
        return {"ok": True, "stage": "done", **post}
