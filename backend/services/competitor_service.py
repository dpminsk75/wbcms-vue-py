"""Конкуренты: витрина товаров (порт CompetitorController::actionIndex).

Скоуп компании — через wbcards.company_id (в wb_competitor_cards company_id нет):
global_admin без выбора → все (company_id=None), остальные → только свои source.
В yii скоупа не было — расхождение зафиксировано в md миграции.
"""

from datetime import datetime
import json
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import openrouter_service as llm

# Порт CompetitorController::defaultCompetitorPrompt (сокращён без потери формата/правил)
DEFAULT_COMPETITOR_PROMPT = """Ты — SEO-специалист Wildberries. Сравни две карточки (title + description) и верни ТОЛЬКО JSON без markdown.

ФОРМАТ:
{"competitor_better": ["факт 1", "факт 2"], "we_better": ["факт 1"], "recommendations": ["что конкретно изменить 1"]}

ПРАВИЛА:
- До 5 пунктов в каждом массиве. Каждый пункт — 1 конкретный факт с цифрами/примерами, а не "лучше описание".
- Сравнивай ТОЛЬКО title и description. Игнорируй цену/отзывы.
- Учитывай поисковые фразы конкурента — они показывают, за счёт чего он в топе.
- Рекомендации — actionable: "Добавить в title 'лунный календарь 2027'", а не "улучшить заголовок".
- Если отличий нет — пиши ["отличий нет"], не выдумывай.
- Отвечай на русском."""

# Порт системного промпта сводки (CompetitorController::actionSummary), {DESC_MIN}/{DESC_MAX} подставляются
DEFAULT_SUMMARY_PROMPT = """Ты — копирайтер Wildberries. Верни ТОЛЬКО валидный JSON без markdown-обёрток и без пояснений.

### FORMAT (строго такой, без доп. полей):
{"title":"...","description":"...","title_recommendations":["..."],"description_recommendations":["..."],"priority_actions":["..."]}

### ЗАГОЛОВОК — СТРОГО ≤60 символов:
- Посчитай символы. Если >60 — сократи. Это критично, иначе отклоню.
- Структура: 1-2 частотных поисковых запроса + 2-3 атрибута через запятую
- Без стоп-слов: "недатированный", "идеальный", "лучший друг", "источник вдохновения"

### ОПИСАНИЕ — {DESC_MIN}-{DESC_MAX} символов, ОДИН СПЛОШНОЙ ТЕКСТ:
- Оптимальная длина {DESC_MIN}-{DESC_MAX} символов. Перед ответом посчитай длину.
- Возьми лучшее из нашей карточки и конкурентов, перефразируй (не копируй дословно).
- Вплети поисковые фразы как ключевые слова (каждую 1-2 раза, естественно, без спама).

### CRITICAL RULES — нарушение = брак, ответ отклоню:
- ЗАПРЕЩЕНО слово "Характеристики:" в любом регистре и падеже.
- ЗАПРЕЩЕНЫ подзаголовки "Что внутри", "Для кого", "Состав", "Комплектация", "Описание" отдельной строкой.
- ЗАПРЕЩЕН список с "—" или "-" в начале строки. Только сплошной текст абзацами (2-3 абзаца, без маркеров).

Стиль: разговорный, конкретно, без воды. Пиши как для покупателя, а не для SEO-робота."""


def _unwrap_result(raw) -> dict:
    """Порт unwrapResult: распаковка {"raw": "{...}"} до 5 уровней."""
    import re as _re
    result = llm.safe_json_decode(raw) if isinstance(raw, str) else raw
    if not isinstance(result, dict):
        if isinstance(raw, str):
            m = re.search(r"\{.*\}", raw, re.S)
            tmp = llm.safe_json_decode(m.group(0)) if m else None
            if isinstance(tmp, dict):
                return tmp
        return {"raw": str(raw)}
    for _ in range(5):
        if set(result.keys()) != {"raw"}:
            break
        inner = result["raw"]
        inner = llm.safe_json_decode(inner) if isinstance(inner, str) else inner
        if not isinstance(inner, dict):
            if isinstance(result["raw"], str):
                m = re.search(r"\{.*\}", result["raw"], re.S)
                inner = llm.safe_json_decode(m.group(0)) if m else None
            if not isinstance(inner, dict):
                break
        result = inner
    return result


def _first_photo(raw) -> str | None:
    """Первое фото wbcards.photos (двойное кодирование — парсим дважды)."""
    import json as _json
    if raw is None:
        return None
    ph = raw
    if isinstance(ph, str):
        try:
            ph = json.loads(ph)
        except ValueError:
            return None
        if isinstance(ph, str):
            try:
                ph = json.loads(ph)
            except ValueError:
                return None
    if isinstance(ph, list) and ph and isinstance(ph[0], str):
        return ph[0]
    return None


def _summary_out(cached: dict, is_admin: bool) -> dict:
    result = _unwrap_result(cached.get("result"))
    age = None
    can_recalc = True
    if cached.get("created_at"):
        try:
            age = (datetime.now() - cached["created_at"]).days
            if age < 30 and not is_admin:
                can_recalc = False
        except TypeError:
            pass
    return {"result": result, "cached": True, "competitor_count": cached.get("competitor_count"),
            "cached_at": cached["created_at"].isoformat() if hasattr(cached.get("created_at"), "isoformat") else cached.get("created_at"),
            "cached_model": cached.get("model"), "can_recalc": can_recalc, "cache_age_days": age}


class CompetitorService:
    def __init__(self, db: AsyncSession, company_id: int | None):
        self.db = db
        self.company_id = company_id

    def _scope(self, alias: str = "") -> tuple[str, dict]:
        pre = f"{alias}." if alias else ""
        if self.company_id is None:
            return "", {}
        return f"AND {pre}company_id=:cid", {"cid": self.company_id}

    async def _card(self, nm_id: int) -> dict | None:
        r = (await self.db.execute(text("""
            SELECT nmID, company_id, title, brand, vendorCode, photos
            FROM wbcards WHERE nmID=:n LIMIT 1
        """), {"n": nm_id})).mappings().first()
        if not r:
            return None
        d = dict(r)
        d["photo"] = _first_photo(d.pop("photos", None))
        d["vendor_code"] = d.pop("vendorCode", None)
        return d

    async def list_sources(self) -> dict:
        params: dict = {}
        scope = ""
        ascope = ""
        if self.company_id is not None:
            scope = "AND c.source_nm_id IN (SELECT nmID FROM wbcards WHERE company_id=:cid)"
            ascope = "AND company_id=:cid"
            params["cid"] = self.company_id
        rows = (await self.db.execute(text(f"""
            SELECT c.source_nm_id,
                   COUNT(DISTINCT c.nm_id) AS cnt,
                   COUNT(DISTINCT c.query_phrase) AS phrases
            FROM wb_competitor_cards c
            WHERE 1=1 {scope}
            GROUP BY c.source_nm_id
            ORDER BY c.source_nm_id
        """), params)).mappings().all()
        rows = [dict(r) for r in rows]
        analyzed: dict[int, int] = {}
        if rows:
            for r in (await self.db.execute(text(f"""
                SELECT source_nm_id, COUNT(DISTINCT competitor_nm_id) AS n
                FROM wb_competitor_analysis
                WHERE status='analyzed' {ascope}
                GROUP BY source_nm_id
            """), params)).mappings().all():
                analyzed[r["source_nm_id"]] = r["n"]
        cards: dict = {}
        if rows:
            ids = [r["source_nm_id"] for r in rows]
            ph = ",".join(f":n{i}" for i in range(len(ids)))
            for r in (await self.db.execute(
                text(f"SELECT nmID, title, brand, vendorCode, photos FROM wbcards WHERE nmID IN ({ph})"),
                {f"n{i}": v for i, v in enumerate(ids)},
            )).mappings().all():
                cards[r["nmID"]] = {"title": r["title"], "brand": r["brand"],
                                    "vendor_code": r["vendorCode"], "photo": _first_photo(r["photos"])}
        return {"rows": [
            {"source_nm_id": r["source_nm_id"], "cnt": r["cnt"], "phrases": r["phrases"],
             "analyzed": analyzed.get(r["source_nm_id"], 0),
             "title": (cards.get(r["source_nm_id"]) or {}).get("title"),
             "brand": (cards.get(r["source_nm_id"]) or {}).get("brand"),
             "vendor_code": (cards.get(r["source_nm_id"]) or {}).get("vendor_code"),
             "photo": (cards.get(r["source_nm_id"]) or {}).get("photo")}
            for r in rows
        ]}

    async def get_phrases(self, nm_id: int) -> dict:
        """Порт actionSelect: все фразы + уже отобранные + карточка."""
        scope, p = self._scope("a")
        selected = (await self.db.execute(text(f"""
            SELECT DISTINCT query_phrase FROM wb_competitor_analysis a
            WHERE source_nm_id=:n {scope}
        """), {"n": nm_id, **p})).scalars().all()
        all_phrases = (await self.db.execute(text("""
            SELECT DISTINCT query_phrase FROM wb_competitor_cards
            WHERE source_nm_id=:n ORDER BY query_phrase
        """), {"n": nm_id})).scalars().all()
        return {"nm_id": nm_id, "phrases": [str(x) for x in all_phrases],
                "selected": [str(x) for x in selected], "card": await self._card(nm_id)}

    async def save_selection(self, nm_id: int, phrases: list[str], position_max: int) -> dict:
        """Порт saveCompetitors: транзакция, удалить свои selected, batchInsert новых."""
        phrases = [str(x).strip() for x in (phrases or []) if str(x).strip()]
        if not phrases:
            raise ValueError("Выберите хотя бы одну фразу")
        card = await self._card(nm_id)
        company_id = self.company_id or (card or {}).get("company_id")
        await self.db.rollback()
        async with self.db.begin():
            await self.db.execute(text("""
                DELETE FROM wb_competitor_analysis
                WHERE source_nm_id=:n AND status='selected'
            """), {"n": nm_id})
            in_ph = ",".join(f":p{i}" for i in range(len(phrases)))
            pos = "" if not position_max else "AND position <= :pm"
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, title, brand, query_phrase, position FROM wb_competitor_cards
                WHERE source_nm_id=:n AND query_phrase IN ({in_ph}) {pos}
                ORDER BY nm_id, position
            """), {"n": nm_id, **{f"p{i}": v for i, v in enumerate(phrases)},
                   **({"pm": position_max} if position_max else {})})).mappings().all()
            existing = (await self.db.execute(text("""
                SELECT id, competitor_nm_id, query_phrase FROM wb_competitor_analysis
                WHERE source_nm_id=:n
            """), {"n": nm_id})).mappings().all()
            emap = {(r["competitor_nm_id"], r["query_phrase"]): r["id"] for r in existing}
            saved = 0
            for r in rows:
                if r["nm_id"] == nm_id:
                    continue
                key = (r["nm_id"], r["query_phrase"])
                if key in emap:
                    await self.db.execute(text("""
                        UPDATE wb_competitor_analysis SET status='selected', position=:pos WHERE id=:i
                    """), {"pos": r["position"], "i": emap[key]})
                else:
                    await self.db.execute(text("""
                        INSERT INTO wb_competitor_analysis
                          (company_id, source_nm_id, competitor_nm_id, query_phrase, position, status)
                        VALUES (:c, :s, :cn, :q, :pos, 'selected')
                    """), {"c": company_id, "s": nm_id, "cn": r["nm_id"],
                            "q": r["query_phrase"], "pos": r["position"]})
                saved += 1
        return {"saved": saved}

    async def get_selected(self, nm_id: int) -> dict:
        """Порт actionSelected (GET): конкуренты с фразами + details + analysisMap."""
        scope, p = self._scope("a")
        rows = (await self.db.execute(text(f"""
            SELECT a.* FROM wb_competitor_analysis a
            WHERE a.source_nm_id=:n AND a.competitor_nm_id<>:n {scope}
            ORDER BY a.competitor_nm_id, a.id
        """), {"n": nm_id, **p})).mappings().all()
        rows = [dict(r) for r in rows]
        grouped: dict[int, dict] = {}
        amap: dict[int, dict] = {}
        for r in rows:
            cnid = r["competitor_nm_id"]
            grouped.setdefault(cnid, {"nm_id": cnid, "queries": []})
            grouped[cnid]["queries"].append({"phrase": r["query_phrase"], "position": r["position"],
                                             "status": r["status"], "id": r["id"]})
            if cnid not in amap or (r["status"] == "analyzed" and amap[cnid].get("status") != "analyzed"):
                amap[cnid] = {"id": r["id"], "status": r["status"], "ai_result": r["ai_result"]}
        details: dict = {}
        if grouped:
            ids = sorted(grouped)
            ph = ",".join(f":d{i}" for i in range(len(ids)))
            for d in (await self.db.execute(
                    text(f"SELECT * FROM wb_competitor_details WHERE nm_id IN ({ph})"),
                    {f"d{i}": v for i, v in enumerate(ids)})).mappings().all():
                details[d["nm_id"]] = dict(d)
        positions = [r["position"] for r in rows if r["position"] is not None]
        return {"nm_id": nm_id, "card": await self._card(nm_id),
                "competitors": [{**g, "detail": details.get(g["nm_id"]),
                                 "analysis": amap[g["nm_id"]]} for g in grouped.values()],
                "position_max": max(positions) if positions else 0}

    async def remove_selected(self, source_nm_id: int, nm_id: int) -> bool:
        await self.db.rollback()
        async with self.db.begin():
            r = await self.db.execute(text("""
                DELETE FROM wb_competitor_analysis
                WHERE source_nm_id=:s AND competitor_nm_id=:c AND status='selected'
            """), {"s": source_nm_id, "c": nm_id})
        return bool(r.rowcount)

    async def start_analyze_one(self, analysis_id: int, created_by: int | None, background) -> int:
        """Job из 1 item по analysis.id (порт actionAnalyze)."""
        from backend.services import ai_job_service as jobs
        scope, p = self._scope("")
        an = (await self.db.execute(text(f"""
            SELECT * FROM wb_competitor_analysis WHERE id=:i {scope} LIMIT 1
        """), {"i": analysis_id, **p})).mappings().first()
        if not an:
            raise ValueError("Не найдено")
        an = dict(an)
        job_id = await jobs.create_job(
            self.db, company_id=self.company_id or an["company_id"], kind="competitor_analyze_all",
            nm_id=an["source_nm_id"],
            items=[{"ref_id": analysis_id, "label": f'nm {an["competitor_nm_id"]}'}],
            created_by=created_by)
        background.add_task(jobs.run_job, job_id)
        return job_id

    async def start_analyze_direct(self, source_nm_id: int, competitor_nm_id: int,
                                   created_by: int | None, background) -> int:
        """Порт actionAnalyzeDirect: нет записей — создаём selected из cards, дальше job."""
        from backend.services import ai_job_service as jobs
        card = await self._card(source_nm_id)
        if not card:
            raise ValueError("Наша карточка не найдена")
        company_id = self.company_id or card.get("company_id")
        scope, p = self._scope("")
        existing = (await self.db.execute(text(f"""
            SELECT id FROM wb_competitor_analysis
            WHERE source_nm_id=:s AND competitor_nm_id=:c AND status<>'removed' {scope} LIMIT 1
        """), {"s": source_nm_id, "c": competitor_nm_id, **p})).first()
        if existing:
            aid = existing[0]
        else:
            best = (await self.db.execute(text("""
                SELECT query_phrase, position FROM wb_competitor_cards
                WHERE source_nm_id=:s AND nm_id=:c ORDER BY position LIMIT 1
            """), {"s": source_nm_id, "c": competitor_nm_id})).mappings().first()
            await self.db.rollback()
            async with self.db.begin():
                await self.db.execute(text("""
                    INSERT INTO wb_competitor_analysis
                      (company_id, source_nm_id, competitor_nm_id, query_phrase, position, status)
                    VALUES (:co, :s, :c, :q, :pos, 'selected')
                """), {"co": company_id, "s": source_nm_id, "c": competitor_nm_id,
                        "q": (dict(best)["query_phrase"] if best else "поиск"),
                        "pos": (dict(best)["position"] if best else 0)})
                aid = (await self.db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()
        job_id = await jobs.create_job(
            self.db, company_id=company_id, kind="competitor_analyze_all", nm_id=source_nm_id,
            items=[{"ref_id": int(aid), "label": f"nm {competitor_nm_id}"}], created_by=created_by)
        background.add_task(jobs.run_job, job_id)
        return job_id

    async def get_summary(self, nm_id: int, force: bool, is_admin: bool) -> dict:
        """Порт actionSummary: кэш 30д (force только admin), иначе генерация платной моделью."""
        import json as _json
        cached = (await self.db.execute(text("""
            SELECT * FROM wb_competitor_summary WHERE source_nm_id=:n LIMIT 1
        """), {"n": nm_id})).mappings().first()
        cached = dict(cached) if cached else None
        if cached and not force:
            return {"success": True, **_summary_out(cached, is_admin)}
        if cached and cached.get("created_at") and not is_admin:
            try:
                age = (datetime.now() - cached["created_at"]).days
            except TypeError:
                age = 999
            if age < 30:
                if force:
                    return {"success": False,
                            "error": "Пересчёт доступен только администратору (рекомендация моложе 30 дней)"}
                return {"success": True, **_summary_out(cached, is_admin)}
        return await self._generate_summary(nm_id)

    async def _generate_summary(self, nm_id: int) -> dict:
        import json as _json
        import re as _re
        card = await self._card(nm_id)
        if not card:
            return {"success": False, "error": "Наша карточка не найдена"}
        company_id = self.company_id or card.get("company_id")
        scope, p = self._scope("a")
        items = (await self.db.execute(text(f"""
            SELECT a.* FROM wb_competitor_analysis a
            WHERE a.source_nm_id=:n AND a.ai_result IS NOT NULL
              AND a.competitor_nm_id<>:n {scope}
        """), {"n": nm_id, **p})).mappings().all()
        items = [dict(r) for r in items]
        if not items:
            return {"success": False, "error": "Нет проанализированных конкурентов"}
        cnids = sorted({r["competitor_nm_id"] for r in items})
        ph = ",".join(f":c{i}" for i in range(len(cnids)))
        details = {d["nm_id"]: dict(d) for d in (await self.db.execute(
            text(f"SELECT * FROM wb_competitor_details WHERE nm_id IN ({ph})"),
            {f"c{i}": v for i, v in enumerate(cnids)})).mappings().all()}
        best: dict[int, dict] = {}
        for r in items:
            nid = r["competitor_nm_id"]
            if nid not in best or (r["position"] or 999) < (best[nid]["position"] or 999):
                best[nid] = r
        company = {}
        if company_id:
            crow = (await self.db.execute(text("""
                SELECT id, seo_summary_model, seo_model, seo_summary_max_tokens,
                       seo_desc_min, seo_desc_max, seo_summary_prompt
                FROM companies WHERE id=:c LIMIT 1
            """), {"c": company_id})).mappings().first()
            company = dict(crow) if crow else {}
        desc_min = int(company.get("seo_desc_min") or 1500)
        desc_max = int(company.get("seo_desc_max") or 4000)
        summaries = []
        for nid, r in best.items():
            res = llm.safe_json_decode(r["ai_result"]) if isinstance(r["ai_result"], str) else r["ai_result"]
            if not isinstance(res, dict):
                continue
            cd = details.get(nid) or {}
            summaries.append({
                "competitor_nm_id": nid, "query": r["query_phrase"], "position": r["position"],
                "comp_title": (cd.get("title") or "")[:200],
                "comp_desc": (cd.get("description") or "")[:1200],
                "competitor_better": res.get("competitor_better") or [],
                "we_better": res.get("we_better") or [],
                "recommendations": res.get("recommendations") or [],
            })
        if not summaries:
            return {"success": False, "error": "Нет данных для сводки"}
        custom = (company.get("seo_summary_prompt") or "").strip()
        if custom:
            system = custom.replace("{DESC_MIN}", str(desc_min)).replace("{DESC_MAX}", str(desc_max))
        else:
            system = (DEFAULT_SUMMARY_PROMPT
                      .replace("{$descMin}", str(desc_min)).replace("{$descMax}", str(desc_max))
                      .replace("{DESC_MIN}", str(desc_min)).replace("{DESC_MAX}", str(desc_max)))
        up = "=== ПОИСКОВЫЕ ФРАЗЫ КОНКУРЕНТОВ (ОБЯЗАТЕЛЬНО ИСПОЛЬЗУЙ В ЗАГОЛОВКЕ И ОПИСАНИИ) ===\n"
        seen = []
        for s in summaries:
            if s["query"] not in seen:
                seen.append(s["query"])
                up += f"- {s['query']}\n"
        up += f"\n=== НАША КАРТОЧКА ===\nЗаголовок: {card.get('title') or ''}\nОписание: {card.get('description') or ''}\n\n"
        up += f"=== АНАЛИЗЫ КОНКУРЕНТОВ ({len(summaries)} шт) ===\n"
        for i, s in enumerate(summaries):
            up += (f"\n--- Конкурент {i+1} (nmID {s['competitor_nm_id']}, позиция #{s['position']}, фраза: {s['query']}) ---\n"
                   f"Заголовок конкурента: {s['comp_title']}\nОписание конкурента: {s['comp_desc']}\n")
            if s["competitor_better"]:
                up += "Лучше у конкурента: " + "; ".join(s["competitor_better"]) + "\n"
            if s["we_better"]:
                up += "Лучше у нас: " + "; ".join(s["we_better"]) + "\n"
            if s["recommendations"]:
                up += "Рекомендации: " + "; ".join(s["recommendations"]) + "\n"
        up += f"\nВАЖНО: Сформируй заголовок (до 60 символов!) и описание ({desc_min}-{desc_max} символов), используя поисковые фразы как ключевые слова для индексации."
        model = (company.get("seo_summary_model") or company.get("seo_model") or "").split(",")[0].strip() or None
        max_tokens = int(company.get("seo_summary_max_tokens") or 4000)
        res = await llm.chat(self.db, [{"role": "system", "content": system}, {"role": "user", "content": up}],
                             company_id, temperature=0.7, max_tokens=max_tokens, model=model)
        if res.get("error"):
            return {"success": False, "error": res["error"]}
        content = (res.get("content") or "").strip()
        raw_response = content
        m = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.S)
        if m:
            content = m.group(1).strip()
        decoded = llm.safe_json_decode(content)
        if not isinstance(decoded, dict):
            m2 = re.search(r"\{.*\}", content, re.S)
            decoded = llm.safe_json_decode(m2.group(0)) if m2 else None
        if not isinstance(decoded, dict):
            decoded = {"raw": content}
        if not decoded.get("title") and decoded.get("title_recommendations"):
            decoded["title"] = " ".join(decoded["title_recommendations"][:1])
        if not decoded.get("description") and decoded.get("description_recommendations"):
            decoded["description"] = " ".join(decoded["description_recommendations"][:1])
        to_save = _unwrap_result(decoded)
        await self.db.rollback()
        async with self.db.begin():
            await self.db.execute(text("""
                INSERT INTO wb_competitor_summary
                  (company_id, source_nm_id, result, raw_ai_response, suggested_title,
                   suggested_description, competitor_count, model)
                VALUES (:c, :n, :r, :raw, :t, :d, :cnt, :m)
                ON DUPLICATE KEY UPDATE company_id=VALUES(company_id), result=VALUES(result),
                  raw_ai_response=VALUES(raw_ai_response), suggested_title=VALUES(suggested_title),
                  suggested_description=VALUES(suggested_description),
                  competitor_count=VALUES(competitor_count), model=VALUES(model)
            """), {"c": company_id, "n": nm_id, "r": json.dumps(to_save, ensure_ascii=False),
                   "raw": raw_response, "t": (to_save.get("title") or "")[:500] if isinstance(to_save, dict) else None,
                   "d": to_save.get("description") if isinstance(to_save, dict) else None,
                   "cnt": len(summaries), "m": res.get("model")})
        return {"success": True, "result": to_save, "cached": False, "competitor_count": len(summaries)}

    async def get_results(self, nm_id: int) -> dict:
        """Порт actionResults: записи анализа + все конкуренты + карточки + детали."""
        import json as _json
        scope, p = self._scope("a")
        items = (await self.db.execute(text(f"""
            SELECT a.* FROM wb_competitor_analysis a
            WHERE a.source_nm_id=:n AND a.status<>'removed' AND a.competitor_nm_id<>:n {scope}
            ORDER BY a.competitor_nm_id, a.query_phrase
        """), {"n": nm_id, **p})).mappings().all()
        items = [dict(r) for r in items]
        comp_ids: dict[int, None] = {}
        for cr in (await self.db.execute(text("""
            SELECT nm_id FROM wb_competitor_cards
            WHERE source_nm_id=:n AND nm_id<>:n GROUP BY nm_id ORDER BY nm_id
        """), {"n": nm_id})).mappings().all():
            comp_ids[cr["nm_id"]] = None
        for r in items:
            comp_ids[r["competitor_nm_id"]] = None
        comp_ids = sorted(comp_ids)
        comp_cards: dict = {}
        comp_details: dict = {}
        if comp_ids:
            ph = ",".join(f":c{i}" for i in range(len(comp_ids)))
            pp = {f"c{i}": v for i, v in enumerate(comp_ids)}
            for c in (await self.db.execute(text(f"""
                SELECT * FROM wb_competitor_cards
                WHERE source_nm_id=:n AND nm_id IN ({ph})
                ORDER BY nm_id, position
            """), {"n": nm_id, **pp})).mappings().all():
                comp_cards.setdefault(c["nm_id"], dict(c))
            for d in (await self.db.execute(
                    text(f"SELECT * FROM wb_competitor_details WHERE nm_id IN ({ph})"), pp)
                    ).mappings().all():
                comp_details[d["nm_id"]] = dict(d)
        by_comp: dict[int, list] = {}
        for r in items:
            by_comp.setdefault(r["competitor_nm_id"], []).append(r)
        competitors = []
        for cnid in comp_ids:
            rows = by_comp.get(cnid, [])
            first_analyzed = next((r for r in rows if r["ai_result"] not in (None, "")), None)
            # Старые прогоны клали двойные обёртки {"raw": "{...}"} — разворачиваем
            ai = _unwrap_result(first_analyzed["ai_result"]) if first_analyzed else None
            if ai == {"raw": ""} or ai == {"raw": None}:
                ai = None
            upd = (first_analyzed or {}).get("updated_at")
            card0 = comp_cards.get(cnid) or {}
            det = comp_details.get(cnid) or {}
            images = json.loads(det["images"]) if isinstance(det.get("images"), str) and det.get("images") else (det.get("images") or [])
            competitors.append({
                "nm_id": cnid,
                "title": det.get("title") or card0.get("title"),
                "brand": det.get("brand") or card0.get("brand"),
                "seller": det.get("seller"),
                "price": card0.get("price"),
                "rating": card0.get("rating"),
                "feedbacks": card0.get("feedbacks"),
                "image": (images[0] if images else None) or card0.get("image_url"),
                "url": det.get("url"),
                "description": det.get("description"),
                "phrases": [{"phrase": r["query_phrase"], "position": r["position"]} for r in rows],
                "analysis": ({"id": rows[0]["id"], "status": rows[0]["status"]} if rows else None),
                "has_analysis": ai is not None,
                "ai_result": ai,
                "model": (first_analyzed or {}).get("model"),
                "analyzed_at": upd.isoformat() if hasattr(upd, "isoformat") else upd,
            })
        return {"nm_id": nm_id, "card": await self._card(nm_id), "competitors": competitors}

    async def start_analyze_all(self, nm_id: int, created_by: int | None, background) -> int:
        """Job analyze-all по отмеченным (status=selected): item = 1 конкурент.
        Порт CompetitorController::actionAnalyzeAll (группировка + worker вместо цикла в запросе)."""
        from backend.services import ai_job_service as jobs
        params: dict = {"n": nm_id}
        scope = ""
        if self.company_id is not None:
            scope = "AND company_id=:c"
            params["c"] = self.company_id
        rows = (await self.db.execute(text(f"""
            SELECT id, competitor_nm_id FROM wb_competitor_analysis
            WHERE source_nm_id=:n AND status='selected' {scope}
            ORDER BY competitor_nm_id, id
        """), params)).mappings().all()
        if not rows:
            raise ValueError("Нет отмеченных конкурентов для анализа")
        seen: dict[int, int] = {}
        for r in rows:
            seen.setdefault(r["competitor_nm_id"], r["id"])
        items = [{"ref_id": aid, "label": f"nm {cnid}"} for cnid, aid in sorted(seen.items())]
        job_id = await jobs.create_job(
            self.db, company_id=self.company_id, kind="competitor_analyze_all",
            nm_id=nm_id, items=items, created_by=created_by)
        background.add_task(jobs.run_job, job_id)
        return job_id


async def execute_analyze_job(job_id: int, db: AsyncSession) -> None:
    """Воркер kind=competitor_analyze_all: item(ref=analysis.id) → AI → ai_result всем фразам конкурента."""
    job = (await db.execute(
        text("SELECT * FROM ai_job WHERE id=:j LIMIT 1"), {"j": job_id})).mappings().first()
    if not job:
        return
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
        """Живой прогресс для фронта/консоли (миграция 20260922); без колонки — молча пропускаем."""
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
            an = (await db.execute(text("""
                SELECT * FROM wb_competitor_analysis WHERE id=:i LIMIT 1
            """), {"i": item["ref_id"]})).mappings().first()
            if not an:
                await mark(item["id"], "error", error="analysis not found")
                continue
            an = dict(an)
            card = (await db.execute(text("""
                SELECT title, description, company_id FROM wbcards WHERE nmID=:n LIMIT 1
            """), {"n": an["source_nm_id"]})).mappings().first()
            if not card:
                await mark(item["id"], "error", error="Наша карточка не найдена")
                continue
            detail = (await db.execute(text("""
                SELECT title, description FROM wb_competitor_details WHERE nm_id=:n LIMIT 1
            """), {"n": an["competitor_nm_id"]})).mappings().first()
            if not detail:
                await mark(item["id"], "error", error="Детали конкурента не найдены (нужно обогащение)")
                continue
            phrases = (await db.execute(text("""
                SELECT query_phrase, position FROM wb_competitor_analysis
                WHERE source_nm_id=:s AND competitor_nm_id=:c AND status<>'removed'
            """), {"s": an["source_nm_id"], "c": an["competitor_nm_id"]})).mappings().all()
            company_id = an["company_id"] or job["company_id"] or dict(card)["company_id"]
            prompt_row = None
            if company_id:
                prompt_row = (await db.execute(text("""
                    SELECT seo_competitor_prompt FROM companies WHERE id=:c LIMIT 1
                """), {"c": company_id})).mappings().first()
            system = (dict(prompt_row)["seo_competitor_prompt"]
                      if prompt_row and (dict(prompt_row)["seo_competitor_prompt"] or "").strip()
                      else DEFAULT_COMPETITOR_PROMPT)
            up = "=== ПОИСКОВЫЕ ФРАЗЫ КОНКУРЕНТА ===\n"
            for p in phrases:
                up += f'- "{p["query_phrase"]}" (позиция #{p["position"]})\n'
            up += (f"\n=== НАША КАРТОЧКА ===\nЗаголовок: {dict(card)['title'] or ''}\n"
                   f"Описание: {dict(card)['description'] or ''}\n\n=== КОНКУРЕНТ ===\n"
                   f"Заголовок: {dict(detail)['title'] or ''}\nОписание: {dict(detail)['description'] or ''}\n"
                   "\nПроанализируй и дай рекомендации с учётом всех фраз.")
            messages = [{"role": "system", "content": system}, {"role": "user", "content": up}]
            last_err = "All models failed"
            decoded = None
            used_model = None
            raw_content = ""
            cands = await llm.model_candidates(db, company_id)
            for i, try_model in enumerate(cands):
                await progress(item["id"], f"кандидат {i + 1}/{len(cands)}: {try_model}")
                res = await llm.chat(db, messages, company_id,
                                     temperature=0.3, max_tokens=1500, model=try_model,
                                     note=f"кандидат {i + 1}/{len(cands)}, nm {an['competitor_nm_id']}")
                if res.get("error"):
                    await llm.mark_model(db, try_model, False, res["error"])
                    last_err = f"model {try_model}: {res['error']}"
                    continue
                content = (res.get("content") or "").strip()
                if not content:
                    err = f"model {try_model}: empty response"
                    await llm.mark_model(db, try_model, False, err)
                    last_err = err
                    continue
                m = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.S)
                if m:
                    content = m.group(1)
                parsed = llm.safe_json_decode(content)
                if not isinstance(parsed, (dict, list)):
                    err = f"model {try_model}: JSON parse failed"
                    await llm.mark_model(db, try_model, False, err)
                    last_err = err
                    continue
                await llm.mark_model(db, try_model, True)
                decoded = parsed
                used_model = res.get("model") or try_model
                raw_content = res.get("content")
                break
            if decoded is None:
                await mark(item["id"], "error", error=last_err)
                continue
            await db.execute(text("""
                UPDATE wb_competitor_analysis SET ai_result=:r, status='analyzed', model=:m
                WHERE source_nm_id=:s AND competitor_nm_id=:c AND status<>'removed'
            """), {"r": json.dumps(decoded, ensure_ascii=False), "m": used_model,
                   "s": an["source_nm_id"], "c": an["competitor_nm_id"]})
            await db.commit()
            await mark(item["id"], "done", result={
                "competitor_nm_id": an["competitor_nm_id"],
                "model": used_model,
                # Полный обмен для отладки (аналог yii ai.log): запрос и сырой ответ
                "request": [{"role": m["role"], "content": m["content"]} for m in messages],
                "response": raw_content,
            })
        except Exception as exc:
            await db.rollback()
            await mark(item["id"], "error", error=f"{type(exc).__name__}: {exc}")
