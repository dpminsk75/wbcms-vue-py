"""SEO рекомендации (порт SeoController): лента, unprocessed, view, viewed/requeue,
targets, AI-process через jobs (вариант B).

Гейт — require_seo. Company-scope: не-global → свой company_id (счётчики тоже
со скоупом — в yii без, тут фиксим). q-поиск как в yii: цифры — nmID=точное
ИЛИ vendorCode/title LIKE; текст — title/vendorCode/subjectName LIKE.
"""

import json
import re
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import openrouter_service as llm

PAGE_SIZE = 20
FALLBACK_MODELS = ["z-ai/glm-5.2:free", "minimax/minimax-m3:free",
                   "nvidia/nemotron-3.5-lightning:free", "inclusionai/ling-3.0-flash-fin:free",
                   "google/gemma-4-26b-a4b-it:free"]


def _j(raw):
    """JSON-колонка asyncmy: str/dict/None (photos — двойное кодирование, парсим дважды)."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            out = json.loads(raw)
        except ValueError:
            return None
        if isinstance(out, str):
            try:
                out = json.loads(out)
            except ValueError:
                pass
        return out
    return None


def _first_photo(photos_raw) -> str | None:
    ph = _j(photos_raw)
    if isinstance(ph, list) and ph and isinstance(ph[0], str):
        return ph[0]
    return None


class SeoService:
    def __init__(self, db: AsyncSession, company_id: int | None):
        self.db = db
        self.company_id = company_id

    def _scope(self, alias: str = "r") -> tuple[str, dict]:
        if self.company_id is None:
            return "", {}
        return f"AND {alias}.company_id=:cid", {"cid": self.company_id}

    async def _company_seo(self, company_id: int | None) -> dict:
        if company_id is None:
            return {}
        row = (await self.db.execute(text("""
            SELECT seo_model, seo_desc_min, seo_desc_max, seo_prompt, seo_anti_spam_days
            FROM companies WHERE id=:c LIMIT 1
        """), {"c": company_id})).mappings().first()
        return dict(row) if row else {}

    async def counts(self) -> dict:
        scope, p = self._scope("wb_seo_recommendation")
        rows = (await self.db.execute(text(f"""
            SELECT status, COUNT(*) AS c FROM wb_seo_recommendation
            WHERE status IN ('new','viewed') {scope} GROUP BY status
        """), p)).mappings().all()
        out = {"new": 0, "viewed": 0}
        for r in rows:
            out[r["status"]] = r["c"]
        return out

    async def search(self, status: str, q: str, page: int) -> dict:
        status = status if status in ("new", "viewed") else "new"
        scope, p = self._scope("r")
        join = ""
        cond = ""
        if q:
            join = "JOIN wbcards w ON w.nmID=r.nmID"
            if q.isdigit():
                cond = "AND (r.nmID=:qn OR w.vendorCode LIKE :ql OR w.title LIKE :ql)"
                p.update({"qn": int(q), "ql": f"%{q}%"})
            else:
                cond = "AND (w.title LIKE :ql OR w.vendorCode LIKE :ql OR w.subjectName LIKE :ql)"
                p["ql"] = f"%{q}%"
        total = (await self.db.execute(text(f"""
            SELECT COUNT(*) FROM wb_seo_recommendation r {join}
            WHERE r.status=:s {scope} {cond}
        """), {**p, "s": status})).scalar()
        offset = (max(page, 1) - 1) * PAGE_SIZE
        rows = (await self.db.execute(text(f"""
            SELECT r.* FROM wb_seo_recommendation r {join}
            WHERE r.status=:s {scope} {cond}
            ORDER BY r.created_at DESC LIMIT :lim OFFSET :off
        """), {**p, "s": status, "lim": PAGE_SIZE, "off": offset})).mappings().all()
        items = [await self._enrich(dict(r)) for r in rows]
        return {"items": items, "total": total, "page": max(page, 1), "page_size": PAGE_SIZE}

    async def _enrich(self, r: dict) -> dict:
        card = None
        if r.get("nmID"):
            c = (await self.db.execute(text("""
                SELECT nmID, title, subjectName, brand, vendorCode, photos
                FROM wbcards WHERE nmID=:n LIMIT 1
            """), {"n": r["nmID"]})).mappings().first()
            if c:
                card = dict(c)
                card["photo"] = _first_photo(card.get("photos"))
                card.pop("photos", None)
        raw = _j(r.get("raw_json")) or {}
        prompt = raw.get("prompt") or {}
        cnt = len(prompt.get("top_phrases_by_clicks") or []) or len(prompt.get("phrases_with_orders") or [])
        for k in ("created_at", "updated_at", "viewed_at", "requeued_at"):
            if hasattr(r.get(k), "isoformat"):
                r[k] = r[k].isoformat()
        r["keywords_added"] = _j(r.get("keywords_added")) or []
        r["keywords_removed"] = _j(r.get("keywords_removed")) or []
        r["card"] = card
        r["phrases_count"] = cnt
        r.pop("raw_json", None)
        return r

    async def unprocessed(self, q: str) -> list[dict]:
        company = await self._company_seo(self.company_id)
        spam_days = int(company.get("seo_anti_spam_days") or 14)
        date_to = (date.today() - timedelta(days=1)).isoformat()
        date_from = (date.today() - timedelta(days=30)).isoformat()
        cond = ""
        p: dict = {"from": date_from, "to": date_to, "spam": spam_days}
        if q:
            if q.isdigit():
                cond = "AND (w.nmID=:qn OR w.vendorCode LIKE :ql OR LOWER(w.title) LIKE LOWER(:ql))"
                p.update({"qn": int(q), "ql": f"%{q}%"})
            else:
                cond = "AND (LOWER(w.title) LIKE LOWER(:ql) OR LOWER(w.vendorCode) LIKE LOWER(:ql) OR LOWER(w.subjectName) LIKE LOWER(:ql))"
                p["ql"] = f"%{q}%"
        scope = ""
        if self.company_id is not None:
            scope = "AND w.company_id=:cid"
            p["cid"] = self.company_id
        rows = (await self.db.execute(text(f"""
            SELECT w.nmID, w.title, w.subjectName, w.brand, w.vendorCode, w.photos,
                   COALESCE(s.total_qnt,0) AS total_qnt
            FROM wbcards w
            LEFT JOIN (SELECT nm_id, SUM(qnt) AS total_qnt FROM agg_daily_summary
                       WHERE sdate BETWEEN :from AND :to GROUP BY nm_id) s ON s.nm_id=w.nmID
            WHERE 1=1 {cond} {scope} AND w.nmID NOT IN (
                SELECT nmID FROM wb_seo_recommendation
                WHERE is_requeued=0 AND created_at >= DATE_SUB(NOW(), INTERVAL :spam DAY)
            )
            ORDER BY total_qnt DESC, w.nmID DESC LIMIT 20
        """), p)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["photo"] = _first_photo(d.pop("photos", None))
            d["total_qnt"] = int(d.get("total_qnt") or 0)
            out.append(d)
        return out

    async def cards_search(self, q: str) -> dict:
        company = await self._company_seo(self.company_id)
        spam_days = int(company.get("seo_anti_spam_days") or 14)
        cond = ""
        p: dict = {"spam": spam_days}
        if q.isdigit():
            cond = "(w.nmID=:qn OR w.vendorCode LIKE :ql OR w.title LIKE :ql)"
            p.update({"qn": int(q), "ql": f"%{q}%"})
        else:
            cond = "(w.title LIKE :ql OR w.vendorCode LIKE :ql OR w.subjectName LIKE :ql)"
            p["ql"] = f"%{q}%"
        # Как в yii: глобально без company/is_active (иначе "заготов" не находится)
        base = f"""FROM wbcards w WHERE {cond} AND w.nmID NOT IN (
            SELECT nmID FROM wb_seo_recommendation
            WHERE is_requeued=0 AND created_at >= DATE_SUB(NOW(), INTERVAL :spam DAY))"""
        total = (await self.db.execute(text(f"SELECT COUNT(*) {base}"), p)).scalar()
        rows = (await self.db.execute(text(f"""
            SELECT nmID, title, subjectName, brand, vendorCode, photos {base}
            ORDER BY nmID DESC LIMIT :lim
        """), {**p, "lim": PAGE_SIZE})).mappings().all()
        ids = (await self.db.execute(text(f"SELECT nmID {base} ORDER BY nmID DESC LIMIT 100"), p)).scalars().all()
        items = []
        for r in rows:
            d = dict(r)
            d["photo"] = _first_photo(d.pop("photos", None))
            items.append(d)
        return {"items": items, "total": total, "all_ids": [int(i) for i in ids]}

    async def get_view(self, rec_id: int) -> dict | None:
        r = (await self.db.execute(text("""
            SELECT * FROM wb_seo_recommendation WHERE id=:i LIMIT 1
        """), {"i": rec_id})).mappings().first()
        if not r:
            return None
        d = dict(r)
        if self.company_id is not None and d.get("company_id") != self.company_id:
            return None
        out = await self._enrich(d)
        out["raw_json"] = _j(r.get("raw_json"))
        tg = (await self.db.execute(text("""
            SELECT * FROM wb_seo_target WHERE nmID=:n ORDER BY priority, id
        """), {"n": d["nmID"]})).mappings().all()
        out["targets"] = [dict(t) for t in tg]
        return out

    async def _touch(self, rec_id: int, sets: dict) -> bool:
        if self.company_id is not None:
            own = (await self.db.execute(text("""
                SELECT id FROM wb_seo_recommendation WHERE id=:i AND company_id=:c LIMIT 1
            """), {"i": rec_id, "c": self.company_id})).first()
            if not own:
                return False
        cols = ", ".join(f"{k}=:{k}" for k in sets)
        await db_rollback_begin(self.db)
        async with self.db.begin():
            r = await self.db.execute(
                text(f"UPDATE wb_seo_recommendation SET {cols}, updated_at=NOW() WHERE id=:i"),
                {**sets, "i": rec_id})
        return bool(r.rowcount)

    async def set_viewed(self, rec_id: int, user_id: int) -> bool:
        return await self._touch(rec_id, {"status": "viewed", "viewed_by": user_id,
                                          "viewed_at": datetime.now(), "is_requeued": 0, "requeued_at": None})

    async def set_requeue(self, rec_id: int) -> bool:
        return await self._touch(rec_id, {"status": "new", "is_requeued": 1,
                                          "requeued_at": datetime.now(),
                                          "viewed_by": None, "viewed_at": None})

    async def add_target(self, nm_id: int, phrase: str, user_id: int) -> dict:
        phrase = phrase.strip()[:500]
        if not nm_id or not phrase:
            raise ValueError("phrase required")
        exists = (await self.db.execute(text("""
            SELECT id FROM wb_seo_target WHERE nmID=:n AND phrase=:p LIMIT 1
        """), {"n": nm_id, "p": phrase})).first()
        if exists:
            raise ValueError("Уже добавлена")
        await db_rollback_begin(self.db)
        async with self.db.begin():
            await self.db.execute(text("""
                INSERT INTO wb_seo_target (nmID, phrase, priority, is_active, added_by, created_at, updated_at)
                VALUES (:n, :p, 10, 1, :u, NOW(), NOW())
            """), {"n": nm_id, "p": phrase, "u": user_id})
            tid = (await self.db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()
        return {"id": int(tid)}

    async def remove_target(self, tid: int) -> bool:
        await db_rollback_begin(self.db)
        async with self.db.begin():
            r = await self.db.execute(text("DELETE FROM wb_seo_target WHERE id=:i"), {"i": tid})
        return bool(r.rowcount)

    # ---------- AI: build_prompt + process-воркер (порт SeoAnalyzerService) ----------

    async def build_prompt(self, nm_id: int, company_id: int) -> dict | None:
        card = (await self.db.execute(text("""
            SELECT nmID, company_id, subjectName, brand, title, description, characteristics
            FROM wbcards WHERE nmID=:n LIMIT 1
        """), {"n": nm_id})).mappings().first()
        if not card:
            return None
        card = dict(card)
        chars_raw = _j(card.get("characteristics")) or []
        chars = [{"name": c.get("name", ""), "value": (", ".join(c["value"]) if isinstance(c.get("value"), list) else c.get("value", ""))}
                 for c in chars_raw[:7]] if isinstance(chars_raw, list) else []
        date_to = (date.today() - timedelta(days=1)).isoformat()
        date_from = (date.today() - timedelta(days=30)).isoformat()
        prows = (await self.db.execute(text("""
            SELECT phrase, AVG(week_frequency) AS avg_freq, AVG(avg_position) AS avg_pos,
                   SUM(clicks) AS total_clicks, SUM(orders) AS total_orders, AVG(ctr) AS avg_ctr
            FROM wb_sr_report_item_phrases
            WHERE nmID=:n AND `date` BETWEEN :f AND :t
            GROUP BY phrase ORDER BY total_clicks DESC LIMIT 30
        """), {"n": nm_id, "f": date_from, "t": date_to})).mappings().all()
        prows = [dict(r) for r in prows]
        top_clicks = prows[:10]
        with_orders = sorted([r for r in prows if (r["total_orders"] or 0) > 0],
                             key=lambda r: -(r["total_orders"] or 0))[:5]
        opportunity = sorted([r for r in prows
                              if 11 <= (r["avg_pos"] or 0) <= 50 and (r["avg_freq"] or 0) > 500],
                             key=lambda r: -(r["avg_freq"] or 0))[:5]
        tg = (await self.db.execute(text("""
            SELECT phrase, priority FROM wb_seo_target
            WHERE nmID=:n AND is_active=1 ORDER BY priority, id LIMIT 10
        """), {"n": nm_id})).mappings().all()
        targets = [dict(t) for t in tg]
        company = await self._company_seo(company_id)
        desc_min = int(company.get("seo_desc_min") or 800)
        desc_max = int(company.get("seo_desc_max") or 1200)
        desc_min = max(desc_min, 300)
        desc_max = max(desc_max, desc_min + 400)
        default_system = (
            "Ты — SEO-специалист Wildberries. На основе title/description карточки, характеристик и кластеров поисковых фраз предложи улучшения по правилам WB.\n"
            "Заголовок (до 60 симв): формула [Тип товара] + [Главный кластер/ключевой атрибут]. Без дублирования слов внутри заголовка. Читаемо, бренд сохрани.\n"
            "Характеристики: заполни максимум полей.\n"
            f"Описание {desc_min}-{desc_max} симв: вприлетай ключи из оставшихся кластеров в естественные предлоги. WB понимает леммы и синонимы — точные вхождения не нужны.\n"
            "Принцип «Одно слово — один раз»: если слово уже в Заголовке/Категории (subjectName) — не повторяй 10 раз в описании. Используй синонимы.\n"
            f"Морфология: не коверкай фразы. Требования: заголовок до 60 симв, описание {desc_min}-{desc_max}. Не выдумывай характеристики, не добавляй ключей вне списка кластеров и целевых.\n"
            'Ответ СТРОГО JSON без markdown: {"new_title":"...","new_description":"...","keywords_added":["..."],"keywords_removed":["..."],"rationale":"кратко почему","confidence":0.0-1.0,"risks":"..."}'
        )
        custom = (company.get("seo_prompt") or "").strip()
        system = custom.replace("{DESC_MIN}", str(desc_min)).replace("{DESC_MAX}", str(desc_max)) if custom else default_system
        if targets and "целев" not in system:
            tlist = ", ".join(f'"{t["phrase"]}"' for t in targets)
            system += f" Обязательно включи целевые фразы: [{tlist}] — приоритет выше статистики, вставь естественно."
        fmt = lambda r: {"phrase": r["phrase"], "freq": int(r["avg_freq"] or 0),
                         "avg_pos": round(float(r["avg_pos"] or 0), 1),
                         "clicks": int(r["total_clicks"] or 0), "orders": int(r["total_orders"] or 0)}
        user_data = {
            "nmID": nm_id, "company_id": company_id,
            "subject": card.get("subjectName"), "brand": card.get("brand"),
            "current_title": card.get("title"), "current_description": card.get("description"),
            "characteristics": chars,
            "top_phrases_by_clicks": [fmt(r) for r in top_clicks],
            "phrases_with_orders": [fmt(r) for r in with_orders],
            "opportunity_phrases_pos_11_50": [{k: v for k, v in fmt(r).items() if k != "orders"} for r in opportunity],
            "target_phrases": [t["phrase"] for t in targets],
            "period": f"{date_from} — {date_to}",
        }
        return {"card": card, "user_data": user_data,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": json.dumps(user_data, ensure_ascii=False)}]}

    async def _model_candidates(self, company_id: int | None, override: str | None) -> list[str]:
        cands: list[str] = []
        if override:
            cands = [m.strip() for m in override.split(",") if m.strip()]
        else:
            company = await self._company_seo(company_id) if company_id else {}
            raw = (company.get("seo_model") or "").strip()
            if raw:
                cands = [m.strip() for m in raw.split(",") if m.strip()]
        rows = (await self.db.execute(text("""
            SELECT model_id FROM wb_seo_model
            WHERE is_active=1 AND (cooldown_until IS NULL OR cooldown_until <= NOW())
            ORDER BY priority, id
        """))).mappings().all()
        for r in rows:
            if r["model_id"] not in cands:
                cands.append(r["model_id"])
        for fb in FALLBACK_MODELS:
            if fb not in cands:
                cands.append(fb)
        return cands

    async def _mark_model(self, model_id: str, ok: bool, error: str = "") -> None:
        try:
            if ok:
                await self.db.execute(text("""
                    UPDATE wb_seo_model SET success_count=success_count+1, consecutive_errors=0,
                      last_success_at=NOW(), last_error=NULL, cooldown_until=NULL, updated_at=NOW()
                    WHERE model_id=:m
                """), {"m": model_id})
            else:
                is429 = ("429" in error) or ("rate-limited" in error)
                row = (await self.db.execute(text("""
                    SELECT consecutive_errors FROM wb_seo_model WHERE model_id=:m LIMIT 1
                """), {"m": model_id})).mappings().first()
                ce = (dict(row)["consecutive_errors"] + 1) if row else 1
                minutes = [5, 15, 60, 180][ce - 1] if ce <= 4 else 180
                await self.db.execute(text("""
                    UPDATE wb_seo_model SET error_count=error_count+1, consecutive_errors=:ce,
                      last_error=:e, updated_at=NOW(),
                      last_429_at=CASE WHEN :r THEN NOW() ELSE last_429_at END,
                      cooldown_until=CASE WHEN :r THEN DATE_ADD(NOW(), INTERVAL :mm MINUTE) ELSE cooldown_until END,
                      is_active=CASE WHEN :ce >= 10 THEN 0 ELSE is_active END
                    WHERE model_id=:m
                """), {"ce": ce, "e": error[:480], "r": 1 if is429 else 0, "mm": minutes, "m": model_id})
            await self.db.commit()
        except Exception:
            await self.db.rollback()

    async def start_process(self, nm_ids: list[int], created_by: int | None, background) -> int:
        from backend.services import ai_job_service as jobs
        nm_ids = [int(n) for n in nm_ids if int(n) > 0][:100]
        if not nm_ids:
            raise ValueError("empty nm_ids")
        job_id = await jobs.create_job(
            self.db, company_id=self.company_id, kind="seo_process",
            nm_id=nm_ids[0] if len(nm_ids) == 1 else None,
            items=[{"ref_id": n, "label": f"nm {n}"} for n in nm_ids],
            created_by=created_by)
        background.add_task(jobs.run_job, job_id)
        return job_id


async def db_rollback_begin(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:
        pass


async def execute_process_job(job_id: int, db: AsyncSession) -> None:
    """Воркер kind=seo_process: item(ref=nmID) → build_prompt → кандидаты моделей → запись status=new."""
    svc = SeoService(db, None)
    job = (await db.execute(
        text("SELECT * FROM ai_job WHERE id=:j LIMIT 1"), {"j": job_id})).mappings().first()
    if not job:
        return
    job = dict(job)
    items = (await db.execute(
        text("SELECT * FROM ai_job_item WHERE job_id=:j AND status='pending' ORDER BY id"),
        {"j": job_id})).mappings().all()

    async def mark(item_id: int, status: str, result: dict | None = None, error: str | None = None):
        await db.execute(text("""
            UPDATE ai_job_item SET status=:s, result=:r, error=:e, note=NULL WHERE id=:i
        """), {"s": status, "r": json.dumps(result, ensure_ascii=False) if result else None,
               "e": (error or "")[:500] if error else None, "i": item_id})
        await db.execute(text("UPDATE ai_job SET done=done+1 WHERE id=:j"), {"j": job_id})
        await db.commit()

    async def progress(item_id: int, note: str) -> None:
        try:
            await db.execute(text("UPDATE ai_job_item SET note=:n WHERE id=:i"), {"n": note[:500], "i": item_id})
            await db.commit()
        except Exception:
            await db.rollback()

    for item in items:
        item = dict(item)
        await db.execute(text("UPDATE ai_job_item SET status='processing' WHERE id=:i"), {"i": item["id"]})
        await db.commit()
        try:
            nm_id = int(item["ref_id"])
            card = (await db.execute(text("""
                SELECT company_id, title, description FROM wbcards WHERE nmID=:n LIMIT 1
            """), {"n": nm_id})).mappings().first()
            if not card:
                await mark(item["id"], "error", error=f"Карточка nmID {nm_id} не найдена")
                continue
            company_id = dict(card)["company_id"] or job["company_id"] or 1
            built = await svc.build_prompt(nm_id, company_id)
            if not built:
                await mark(item["id"], "error", error="buildPrompt failed")
                continue
            last_err = "All models failed"
            rec_id = None
            cands = await svc._model_candidates(company_id, None)
            for i, try_model in enumerate(cands):
                await progress(item["id"], f"кандидат {i + 1}/{len(cands)}: {try_model}")
                res = await llm.chat(db, built["messages"], company_id,
                                     temperature=0.4, max_tokens=1500, model=try_model,
                                     note=f"кандидат {i + 1}/{len(cands)}, nm {nm_id}")
                if res.get("error"):
                    await svc._mark_model(try_model, False, res["error"])
                    last_err = f"model {try_model}: {res['error']}"
                    continue
                content = (res.get("content") or "").strip()
                if not content:
                    err = f"model {try_model}: empty response"
                    await svc._mark_model(try_model, False, err)
                    last_err = err
                    continue
                import re as _re
                m = _re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.S)
                if m:
                    content = m.group(1).strip()
                parsed = llm.safe_json_decode(content)
                if not isinstance(parsed, dict) or not parsed.get("new_title") or not parsed.get("new_description"):
                    err = f"JSON parse failed model={try_model}"
                    await svc._mark_model(try_model, False, err)
                    last_err = err
                    continue
                await svc._mark_model(try_model, True)
                now = datetime.now()
                kw_a = parsed.get("keywords_added")
                kw_r = parsed.get("keywords_removed")
                await db_rollback_begin(db)
                async with db.begin():
                    await db.execute(text("""
                        INSERT INTO wb_seo_recommendation (
                          company_id, nmID, old_title, old_description, new_title, new_description,
                          rationale, keywords_added, keywords_removed, confidence, model,
                          prompt_tokens, completion_tokens, raw_json, status, is_requeued,
                          created_at, updated_at
                        ) VALUES (
                          :c, :n, :ot, :od, :nt, :nd, :ra, :ka, :kr, :cf, :mo,
                          :pt, :ct, :raw, 'new', 0, :now, :now)
                    """), {
                        "c": company_id, "n": nm_id,
                        "ot": dict(card)["title"], "od": dict(card)["description"],
                        "nt": str(parsed["new_title"]).strip()[:500],
                        "nd": str(parsed["new_description"]).strip(),
                        "ra": str(parsed.get("rationale") or "")[:5000] or None,
                        "ka": json.dumps(kw_a, ensure_ascii=False) if isinstance(kw_a, list) else None,
                        "kr": json.dumps(kw_r, ensure_ascii=False) if isinstance(kw_r, list) else None,
                        "cf": float(parsed["confidence"]) if isinstance(parsed.get("confidence"), (int, float)) else None,
                        "mo": res.get("model"),
                        "pt": res.get("prompt_tokens"), "ct": res.get("completion_tokens"),
                        "raw": json.dumps({"prompt": built["user_data"], "response": parsed,
                                           "raw_content": res.get("content")}, ensure_ascii=False),
                        "now": now,
                    })
                    rec_id = (await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()
                break
            if rec_id:
                await mark(item["id"], "done", result={"rec_id": int(rec_id)})
            else:
                await mark(item["id"], "error", error=last_err)
        except Exception as exc:
            await db.rollback()
            await mark(item["id"], "error", error=f"{type(exc).__name__}: {exc}")
