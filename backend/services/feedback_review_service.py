"""Разбор отзыва через ИИ: эмоциональность / конструктивность / тональность.

Разбор идёт ПО КАЖДОМУ отзыву (не по карточке) — в фоне, по мере появления
отзывов, и по кнопке вручную на странице «Отзывы и ответы».

Очередь: отзыва нет в wb_feedback_ai_review (или status='pending').
Ошибка разбора пишется status='error' и больше автоматически не обрабатывается —
вернуть в очередь может админ (status='pending').

Если у провайдера кончились токены (insufficient_balance / 402) — компания
встаёт на паузу на 3 часа (llm_balance), отзыв остаётся в очереди и разбирается
после паузы. Такие ошибки НЕ пишутся в status='error'.

Промпт — настройка компании (companies.feedback_review_prompt); в коде его нет.
Модель — «Модель (сводка)» (kind=summary).

MySQL 8 + алиас строки `AS new`: unqualified-ссылка на колонку, КОТОРАЯ входит
в список INSERT, неоднозначна → 1052 "Column 'x' in field list is ambiguous".
Старое значение берём только с префиксом таблицы (wb_feedback_ai_review.col).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import llm_balance
from backend.services import llm_quota
from backend.services import openrouter_service as llm

log = logging.getLogger("feedback_review")

SCENARIO = "feedback_review"

# Промпт разбора отзыва — ТОЛЬКО из настроек компании.
PROMPT_FIELD = "feedback_review_prompt"

# Пауза между тиками цикла (секунды) и хвост журнала, который не подчищаем.
IDLE_SLEEP = 60
LOG_KEEP = 200

_MAX_TEXT = 1200       # символов текста отзыва в промпт
_MAX_PROS = 300
_MAX_CONS = 400
_MAX_TITLE = 300

# Допустимые значения меток — вне их ответ модели считаем ошибкой.
EMOTIONS = ("low", "mid", "high")
CONSTRUCTIVENESS = ("low", "mid", "high")
TONES = ("neg", "pos", "neutral")

# Отзыв с текстом + карточка (для промпта).
SQL_FEEDBACK = """
SELECT f.id AS id, f.nmID AS nm_id, f.company_id AS company_id,
       f.productValuation AS rating, f.text AS text,
       f.pros AS pros, f.cons AS cons, f.createdDate AS created_at,
       c.title AS title, c.brand AS brand, c.subjectName AS subject_name
FROM wb_feedbacks f
LEFT JOIN wbcards c ON c.nmID = f.nmID
WHERE f.id = :fid
LIMIT 1
"""

# Очередь: отзывы с текстом, для которых нет записи разбора (или status='pending').
SQL_PENDING = """
SELECT f.id AS id, f.nmID AS nm_id, f.productValuation AS rating,
       f.text AS text, f.createdDate AS created_at
FROM wb_feedbacks f
LEFT JOIN wb_feedback_ai_review r
       ON r.company_id = f.company_id AND r.feedback_id = f.id
WHERE f.text IS NOT NULL AND f.text <> ''
  {cid}
  {date_where}
  AND (r.id IS NULL OR r.status = 'pending')
ORDER BY f.createdDate DESC
LIMIT :lim
"""

# Отзывы с ошибкой разбора — список для админа.
SQL_ERRORS = """
SELECT r.id AS id, r.feedback_id AS feedback_id, r.nm_id AS nm_id, r.rating AS rating,
       r.error AS error, r.attempts AS attempts, r.updated_at AS updated_at,
       f.text AS text, f.createdDate AS created_at, c.title AS product_title
FROM wb_feedback_ai_review r
LEFT JOIN wb_feedbacks f ON f.id = r.feedback_id
LEFT JOIN wbcards c ON c.nmID = r.nm_id
WHERE r.status = 'error'
  {cid}
ORDER BY r.updated_at DESC
LIMIT :lim
"""


def _clip(v, n: int) -> str:
    s = str(v or "").strip()
    return s[:n]


def _i(v) -> int:
    """Мягкое приведение к int (None/мусор → 0)."""
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


# --- фоновый цикл (как phrase_miner: task внутри процесса веба, без таймера) ---

_started = False
_task: asyncio.Task | None = None
_paused = False
_log_tail = 0
_manual_task: asyncio.Task | None = None
_manual_company: int | None = None


def manual_running() -> bool:
    """Идёт ли ручной запуск разбора (кнопка «Разобрать порцию»)."""
    return _manual_task is not None and not _manual_task.done()


def status_flags(company_id: int | None = None) -> dict:
    """Состояние цикла для экрана: работает ли, на паузе ли (ручной/по токенам)."""
    bal = llm_balance.scope_state(company_id)
    return {
        "running": bool(_started and _task is not None and not _task.done()),
        "paused": _paused,
        "interval_sec": IDLE_SLEEP,
        "balance_paused": bal["paused"],
        "balance_pause_until": bal["until"],
        "balance_pause_left_sec": bal["left_sec"],
        "balance_pause_reason": bal["reason"],
        "balance_companies": bal["companies"],
        "manual_running": manual_running(),
    }


def set_paused(v: bool, company_id: int | None = None) -> None:
    """Пауза/снятие паузы фонового разбора (глобально, в памяти процесса).

    Снятие ручной паузы (v=False) снимает и паузу «нет токенов» у компании:
    админ нажал «Возобновить» — значит токены есть.
    """
    global _paused
    _paused = bool(v)
    if not _paused:
        llm_balance.clear(company_id)


def start() -> None:
    """Запуск фонового цикла (вызывается из main.py startup). Повтор — no-op."""
    global _started, _task
    if _started:
        return
    _started = True
    _task = asyncio.create_task(_loop())
    log.info("feedback_review: started")


def stop() -> None:
    """Остановить фоновые задачи (shutdown процесса) — иначе uvicorn ждёт их."""
    for t in (_task, _manual_task):
        if t is not None and not t.done():
            t.cancel()


async def _log(db: AsyncSession, level: str, message: str, *,
               action: str = "", company_id: int | None = None) -> None:
    """Строка журнала (хвост подчищаем, чтобы таблица не росла).

    ROLLBACK здесь делать нельзя: вызывается в той же сессии, что и разбор, —
    откат снёс бы уже сохранённые результаты.
    """
    global _log_tail
    try:
        await db.execute(text("""
            INSERT INTO wb_feedback_review_log (company_id, level, action, message, created_at)
            VALUES (:cid, :level, :action, :msg, NOW())
        """), {"cid": company_id, "level": level, "action": action or "",
               "msg": str(message)[:1000]})
        _log_tail += 1
        if _log_tail >= LOG_KEEP:
            _log_tail = 0
            await db.execute(text("""
                DELETE FROM wb_feedback_review_log
                WHERE id < (SELECT id FROM wb_feedback_review_log
                            ORDER BY id DESC LIMIT 1 OFFSET :keep)
            """), {"keep": LOG_KEEP})
    except Exception as exc:  # журнал не должен ронять разбор
        log.warning("feedback_review: журнал недоступен (%s: %s)", type(exc).__name__, exc)


async def _tick(db: AsyncSession) -> tuple[float, int]:
    """Один тик: разобрать порцию отзывов по компаниям с авторазбором.

    Возвращает (пауза до следующего тика, сколько разобрано).
    """
    companies = (await db.execute(text("""
        SELECT id, name, feedback_review_batch FROM companies
        WHERE is_active = 1 AND api_key IS NOT NULL AND api_key <> ''
          AND feedback_auto_review = 1
        ORDER BY id
    """))).mappings().all()
    done = 0
    for comp in companies:
        cid = int(comp["id"])
        if llm_balance.is_paused(cid):
            # у компании кончились токены — ждём (пауза снимется сама или вручную)
            continue
        if _manual_company is not None and _manual_company == cid:
            # эту компанию сейчас разбирает ручной запуск — не дублируем
            continue
        # Остаток лимита у провайдера: мало (или окно не активно) → пауза до сброса.
        # Ловим ДО батча, иначе получим сотни 402-ошибок.
        q = await llm_quota.check(db, cid)
        if llm_quota.is_low(q) and q.get("pause_until"):
            reason = (f"лимит ИИ {q.get('percent')}% · сброс {str(q.get('reset_at') or '')[:16]}")
            llm_balance.pause_until(cid, q["pause_until"], reason=reason)
            await _log(db, "warn",
                       f"лимит ИИ почти исчерпан ({q.get('percent')}%) — пауза до "
                       f"{q.get('reset_at')} ({q.get('reset_left') or ''})",
                       action="quota-pause", company_id=cid)
            continue
        try:
            batch = max(1, min(int(comp["feedback_review_batch"] or 100), 500))
        except (TypeError, ValueError):
            batch = 100
        svc = FeedbackReviewService(db, company_id=cid)
        st = await svc.review_pending(limit=batch)
        done += st["ok"]
        if st.get("balance_error"):
            # паузу уже поставил review_one (журнал пишет он) — идём к следующей компании
            continue
        if st["ok"] or st["errors"]:
            await _log(db, "info",
                       f"разобрано {st['ok']}, ошибок {st['errors']} (взято {st['taken']})",
                       action="tick", company_id=cid)
        if st.get("fatal"):
            await _log(db, "error", f"цикл остановлен: {st['fatal']}",
                       action="fatal", company_id=cid)
            # глобальная проблема (нет промпта/моделей) — не долбимся
            return IDLE_SLEEP, done
    return IDLE_SLEEP, done


async def _loop() -> None:
    """Основной цикл: сбой не убивает задачу — пишем в журнал и продолжаем."""
    while True:
        wait = IDLE_SLEEP
        try:
            from backend.database import SessionLocal
            async with SessionLocal() as db:
                if _paused:
                    wait = 30.0
                else:
                    wait, _done = await _tick(db)
                await db.commit()
        except Exception as exc:
            log.warning("feedback_review: тик упал (%s: %s)", type(exc).__name__, exc)
            try:
                from backend.database import SessionLocal
                async with SessionLocal() as db2:
                    await _log(db2, "error", f"цикл: {type(exc).__name__}: {exc}",
                               action="error")
                    await db2.commit()
            except Exception:
                pass
            wait = 30.0
        await asyncio.sleep(wait or IDLE_SLEEP)


class FeedbackReviewService:
    """Разбор отзывов через ИИ (по одному отзыву за вызов)."""

    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # --- промпт -------------------------------------------------------------

    async def get_prompt(self, company_id: int | None = None) -> str:
        """Промпт разбора отзыва из настроек компании. Пусто = не задан.

        Читаем отдельным запросом, а не через llm_provider.company_row: там список
        колонок фиксирован — новая колонка (миграция 20261041) не должна ломать
        остальные вызовы до её применения.
        """
        cid = company_id if company_id is not None else self.company_id
        if cid is None:
            return ""
        row = (await self.db.execute(text(
            f"SELECT {PROMPT_FIELD} FROM companies WHERE id=:cid LIMIT 1"),
            {"cid": cid})).mappings().first()
        return str((row or {}).get(PROMPT_FIELD) or "").strip()

    async def set_prompt(self, prompt: str, company_id: int | None = None) -> dict:
        """Сохранить промпт разбора отзыва в настройках компании."""
        cid = company_id if company_id is not None else self.company_id
        if cid is None:
            raise ValueError("компания не выбрана")
        await self.db.execute(text(
            f"UPDATE companies SET {PROMPT_FIELD}=:p, updated_at=NOW() WHERE id=:cid"),
            {"p": str(prompt or ""), "cid": cid})
        await self.db.commit()
        return {"ok": True, "prompt": str(prompt or "")}

    async def get_settings(self, company_id: int | None = None) -> dict:
        """Настройки авторазбора: включён ли, размер порции + промпт."""
        cid = company_id if company_id is not None else self.company_id
        if cid is None:
            return {"auto": False, "batch": 100, "prompt": ""}
        row = (await self.db.execute(text(
            "SELECT feedback_auto_review AS auto, feedback_review_batch AS batch, "
            f"{PROMPT_FIELD} AS prompt FROM companies WHERE id=:cid LIMIT 1"),
            {"cid": cid})).mappings().first()
        d = dict(row or {})
        try:
            auto = int(d.get("auto") or 0)
        except (TypeError, ValueError):
            auto = 0
        try:
            batch = max(1, min(int(d.get("batch") or 100), 500))
        except (TypeError, ValueError):
            batch = 100
        return {"auto": bool(auto), "batch": batch, "prompt": str(d.get("prompt") or "")}

    async def set_settings(self, auto: bool | None = None, batch: int | None = None,
                           company_id: int | None = None) -> dict:
        """Сохранить настройки авторазбора."""
        cid = company_id if company_id is not None else self.company_id
        if cid is None:
            raise ValueError("компания не выбрана")
        sets: dict = {}
        if auto is not None:
            sets["feedback_auto_review"] = 1 if auto else 0
        if batch is not None:
            sets["feedback_review_batch"] = max(1, min(int(batch or 100), 500))
        if not sets:
            return await self.get_settings()
        cols = ", ".join(f"{k}=:{k}" for k in sets)
        await self.db.execute(text(
            f"UPDATE companies SET {cols}, updated_at=NOW() WHERE id=:cid"),
            {**sets, "cid": cid})
        await self.db.commit()
        return await self.get_settings()

    async def _build_messages(self, fb: dict) -> list[dict]:
        """Промпт компании + данные отзыва."""
        prompt = await self.get_prompt()
        if not prompt:
            raise ValueError(
                "Промпт разбора отзыва не задан — впишите его в карточке компании "
                f"(companies.{PROMPT_FIELD})")
        payload = {
            "id": fb.get("id"),
            "rating": fb.get("rating"),
            "text": _clip(fb.get("text"), _MAX_TEXT),
            "pros": _clip(fb.get("pros"), _MAX_PROS),
            "cons": _clip(fb.get("cons"), _MAX_CONS),
            "date": str(fb.get("created_at") or "")[:10],
            "card": {
                "nm_id": fb.get("nm_id"),
                "title": _clip(fb.get("title"), _MAX_TITLE),
                "brand": _clip(fb.get("brand"), 120),
                "subject": _clip(fb.get("subject_name"), 120),
            },
        }
        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    # --- разбор -------------------------------------------------------------

    @staticmethod
    def _parse(raw: str) -> dict:
        """JSON из ответа модели → 3 метки. Бросает ValueError при мусоре."""
        content = (raw or "").strip()
        m = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.S)
        if m:
            content = m.group(1).strip()
        parsed = llm.safe_json_decode(content)
        if not isinstance(parsed, dict):
            raise ValueError("не удалось разобрать JSON из ответа модели")
        out = {}
        for key, allowed in (("emotion", EMOTIONS),
                             ("constructiveness", CONSTRUCTIVENESS),
                             ("tone", TONES)):
            val = str(parsed.get(key) or "").strip().lower()
            if val not in allowed:
                raise ValueError(f"поле {key}: недопустимое значение «{val}»")
            out[key] = val
        out["summary"] = _clip(parsed.get("summary"), 500)
        topics = parsed.get("topics")
        out["topics"] = [str(t)[:80] for t in topics][:10] if isinstance(topics, list) else []
        return out

    async def review_one(self, feedback_id: str, company_id: int | None = None,
                         source: str = "manual") -> dict:
        """Разобрать один отзыв. Возвращает {ok, ...} — без исключений на ошибке модели.

        source: manual (кнопка в отзывах) | batch (фоновый цикл/воркер).
        Успех в журнал пишем только для ручного запуска — иначе фон даст
        строку на каждый отзыв (сводка по прогону пишется отдельно).
        """
        cid = company_id if company_id is not None else self.company_id
        row = (await self.db.execute(text(SQL_FEEDBACK), {"fid": str(feedback_id)})).mappings().first()
        if not row:
            return {"ok": False, "error": "отзыв не найден"}
        fb = dict(row)
        fb_company = fb.get("company_id") or cid
        if fb_company is None:
            return {"ok": False, "error": "не определена компания отзыва"}
        if cid is not None and int(fb_company) != int(cid):
            return {"ok": False, "error": "отзыв другой компании"}

        try:
            messages = await self._build_messages(fb)
        except ValueError as e:
            # Глобальная проблема (промпт не задан) — отзыв не трогаем, батч стоп.
            return {"ok": False, "error": str(e), "fatal": True}

        cands = await llm.model_candidates(self.db, fb_company, kind="summary")
        if not cands:
            return {"ok": False, "error": "нет доступных моделей", "fatal": True}

        # Все данные уже материализованы (fb, messages, модели): закрываем
        # открытую чтениями транзакцию — иначе её read view держится через ВСЕ
        # попытки LLM (60 с × моделей) и тормозит InnoDB purge всего сервера.
        # В batch-режиме от этого страдает и очередь review_pending (SELECT :581).
        await self.db.rollback()

        last_err = "все модели не ответили"
        balance_reason = ""
        for try_model in cands:
            res = await llm.chat(
                self.db, messages, fb_company,
                temperature=0.2, max_tokens=600, model=try_model,
                note=f"feedback_review, id {feedback_id}",
                scenario=SCENARIO, nm_id=fb.get("nm_id"), timeout=60,
                # разбор = JSON-метки, глубокое thinking не нужно: без low
                # reasoning-модель думает по максимуму и отзыв уходит в таймаут
                reasoning_effort="low")
            if res.get("error"):
                err = str(res["error"])
                reason = llm_balance.reason_of(res)
                if reason:
                    # У провайдера кончились токены: модель тут ни при чём, следующие
                    # не пробуем — встаём на паузу (3 ч) и ждём.
                    balance_reason = reason
                    last_err = f"model {try_model}: {err}"
                    break
                await llm.mark_model(self.db, try_model, False, err)
                last_err = f"model {try_model}: {err}"
                continue
            content = (res.get("content") or "").strip()
            if not content:
                await llm.mark_model(self.db, try_model, False, "empty response")
                last_err = f"model {try_model}: empty response"
                continue
            try:
                parsed = self._parse(content)
            except ValueError as e:
                await llm.mark_model(self.db, try_model, False, f"bad JSON: {e}")
                last_err = f"model {try_model}: {e}"
                continue
            await llm.mark_model(self.db, try_model, True)
            await self._save(fb, fb_company, parsed, try_model, res)
            if source == "manual":
                await _log(self.db, "info",
                           f"отзыв {feedback_id} разобран: {parsed.get('emotion')}/"
                           f"{parsed.get('constructiveness')}/{parsed.get('tone')}",
                           action="manual", company_id=fb_company)
            # Коммитим в обоих режимах: конец транзакции после каждого отзыва.
            # Раньше в batch-режиме _save висел pending до случайного чужого
            # commit (record_usage внутри llm.chat) — ненадёжно и держит txn.
            await self.db.commit()
            return {"ok": True, **parsed, "model": try_model}

        if balance_reason:
            # Отзыв НЕ помечаем ошибкой — он остаётся в очереди и разберётся
            # после паузы. Модель не трогаем: она не сломана, кончились токены.
            llm_balance.pause(fb_company, balance_reason)
            await _log(self.db, "warn",
                       f"отзыв {feedback_id}: {balance_reason} — нет токенов, "
                       f"пауза {int(llm_balance.pause_seconds() // 60)} мин",
                       action="balance-pause", company_id=fb_company)
            await self.db.commit()
            return {"ok": False, "error": last_err, "balance_error": True,
                    "balance_reason": balance_reason}

        await self._save_error(fb, fb_company, last_err)
        await _log(self.db, "error", f"отзыв {feedback_id}: {last_err}",
                   action="error", company_id=fb_company)
        await self.db.commit()
        return {"ok": False, "error": last_err}

    # --- сохранение ---------------------------------------------------------

    async def _save(self, fb: dict, company_id, parsed: dict, model: str, res: dict) -> None:
        await self.db.execute(text("""
            INSERT INTO wb_feedback_ai_review (
                company_id, feedback_id, nm_id, rating,
                emotion, constructiveness, tone, topics, summary,
                model, prompt_tokens, completion_tokens, cost,
                status, error, attempts, created_at, updated_at
            ) VALUES (
                :company_id, :feedback_id, :nm_id, :rating,
                :emotion, :constructiveness, :tone, :topics, :summary,
                :model, :pt, :ct, :cost,
                'ok', NULL, 1, NOW(), NOW()
            ) AS new
            ON DUPLICATE KEY UPDATE
                nm_id = new.nm_id, rating = new.rating,
                emotion = new.emotion, constructiveness = new.constructiveness,
                tone = new.tone, topics = new.topics, summary = new.summary,
                model = new.model, prompt_tokens = new.prompt_tokens,
                completion_tokens = new.completion_tokens, cost = new.cost,
                status = 'ok', error = NULL,
                attempts = wb_feedback_ai_review.attempts + 1, updated_at = NOW()
        """), {
            "company_id": company_id,
            "feedback_id": str(fb.get("id")),
            "nm_id": fb.get("nm_id"),
            "rating": fb.get("rating"),
            "emotion": parsed.get("emotion"),
            "constructiveness": parsed.get("constructiveness"),
            "tone": parsed.get("tone"),
            "topics": json.dumps(parsed.get("topics") or [], ensure_ascii=False),
            "summary": parsed.get("summary") or None,
            "model": model,
            "pt": res.get("prompt_tokens"),
            "ct": res.get("completion_tokens"),
            "cost": res.get("cost"),
        })
        await self.db.commit()

    async def _save_error(self, fb: dict, company_id, error: str) -> None:
        """Ошибка разбора: пишем status='error' — воркер такие больше не трогает."""
        await self.db.execute(text("""
            INSERT INTO wb_feedback_ai_review (
                company_id, feedback_id, nm_id, rating, status, error, attempts,
                created_at, updated_at
            ) VALUES (
                :company_id, :feedback_id, :nm_id, :rating, 'error', :error, 1,
                NOW(), NOW()
            ) AS new
            ON DUPLICATE KEY UPDATE
                status = 'error', error = new.error,
                attempts = wb_feedback_ai_review.attempts + 1, updated_at = NOW()
        """), {
            "company_id": company_id,
            "feedback_id": str(fb.get("id")),
            "nm_id": fb.get("nm_id"),
            "rating": fb.get("rating"),
            "error": str(error)[:500],
        })
        await self.db.commit()

    # --- очередь ------------------------------------------------------------

    def _cid_where(self, alias: str | None = "f") -> tuple[str, dict]:
        """Условие по компании. alias=None — колонка без префикса (UPDATE без алиаса)."""
        if self.company_id is None:
            return "", {}
        col = f"{alias}.company_id" if alias else "company_id"
        return f" AND {col} = :cid", {"cid": self.company_id}

    async def review_pending(self, limit: int = 100,
                             date_from: str | None = None,
                             date_to: str | None = None) -> dict:
        """Разобрать порцию неразобранных отзывов (очередь = нет записи или pending).

        date_from/date_to — ограничить очередь по дате отзыва (backfill за период).

        Глобальная ошибка (не задан промпт / нет моделей) — останавливаем батч:
        иначе отзывы будут браться по кругу (запись не создаётся → очередь не убывает).
        """
        limit = max(1, min(int(limit or 100), 500))
        cid_where, params = self._cid_where()
        date_where = ""
        if date_from or date_to:
            date_where = " AND f.createdDate BETWEEN :d1 AND :d2"
            params["d1"] = f"{date_from} 00:00:00" if date_from else "1970-01-01 00:00:00"
            params["d2"] = f"{date_to} 23:59:59" if date_to else "2099-12-31 23:59:59"
        rows = (await self.db.execute(
            text(SQL_PENDING.format(cid=cid_where, date_where=date_where)),
            {**params, "lim": limit})).mappings().all()
        done = 0
        errors = 0
        fatal = ""
        balance = ""
        for r in rows:
            res = await self.review_one(str(r["id"]), source="batch")
            if res.get("ok"):
                done += 1
            elif res.get("fatal"):
                fatal = str(res.get("error") or "")
                break
            elif res.get("balance_error"):
                # нет токенов: батч прерываем, остальные отзывы остаются в очереди
                balance = str(res.get("balance_reason") or "insufficient_balance")
                break
            else:
                errors += 1
            # прогресс в журнал — батч идёт минуты, без строк видно «зависло»
            if (done + errors) % 10 == 0:
                await _log(self.db, "info",
                           f"прогресс: разобрано {done}, ошибок {errors} (взято {len(rows)})",
                           action="progress", company_id=self.company_id)
        return {"taken": len(rows), "ok": done, "errors": errors, "fatal": fatal,
                "balance_error": bool(balance), "balance_reason": balance,
                "paused": False}

    async def queue_preview(self, limit: int = 50,
                            date_from: str | None = None,
                            date_to: str | None = None) -> dict:
        """Очередь неразобранных отзывов (без разбора) — dry-run и экран очереди.

        Точного COUNT «сколько в очереди» не делаем: это скан по отзывам с
        LEFT JOIN без индекса по тексту — тяжело и лишне. Вместо этого берём
        limit+1 строк и по наличию лишней определяем «ещё есть».
        """
        limit = max(1, min(int(limit or 50), 500))
        cid_where, params = self._cid_where()
        date_where = ""
        if date_from or date_to:
            date_where = " AND f.createdDate BETWEEN :d1 AND :d2"
            params["d1"] = f"{date_from} 00:00:00" if date_from else "1970-01-01 00:00:00"
            params["d2"] = f"{date_to} 23:59:59" if date_to else "2099-12-31 23:59:59"
        rows = (await self.db.execute(
            text(SQL_PENDING.format(cid=cid_where, date_where=date_where)),
            {**params, "lim": limit + 1})).mappings().all()
        has_more = len(rows) > limit
        items = []
        for r in rows[:limit]:
            d = dict(r)
            items.append({
                "id": str(d.get("id")),
                "nm_id": d.get("nm_id"),
                "rating": d.get("rating"),
                "text": _clip(d.get("text"), 300),
                "created_at": str(d.get("created_at") or "")[:16],
            })
        return {"items": items, "has_more": has_more}

    async def retry(self, feedback_id: str) -> dict:
        """Вернуть отзыв в очередь (после ошибки разбора)."""
        # UPDATE без алиаса: в MySQL в SET нельзя указывать алиас таблицы,
        # поэтому и в WHERE колонка без префикса (иначе 1054 Unknown column).
        cid_where, params = self._cid_where(None)
        res = await self.db.execute(text(f"""
            UPDATE wb_feedback_ai_review
            SET status = 'pending', error = NULL, updated_at = NOW()
            WHERE feedback_id = :fid AND status = 'error' {cid_where}
        """), {"fid": str(feedback_id), **params})
        await self.db.commit()
        return {"ok": bool(res.rowcount)}

    async def errors(self, limit: int = 100) -> dict:
        """Список отзывов с ошибкой разбора — для модалки в UI."""
        limit = max(1, min(int(limit or 100), 500))
        cid_where, params = self._cid_where("r")
        rows = (await self.db.execute(
            text(SQL_ERRORS.format(cid=cid_where)),
            {**params, "lim": limit})).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            items.append({
                "feedback_id": d.get("feedback_id"),
                "nm_id": d.get("nm_id"),
                "rating": d.get("rating"),
                "error": d.get("error"),
                "attempts": d.get("attempts"),
                "text": _clip(d.get("text"), 300),
                "created_at": str(d.get("created_at") or "")[:16],
                "product_title": d.get("product_title"),
            })
        return {"items": items, "total": len(items)}

    # --- экран разбора (фон) ------------------------------------------------

    async def get_status(self, company_id: int | None = None) -> dict:
        """Статус фонового разбора: флаги цикла, счётчики, очередь, настройки."""
        cid = company_id if company_id is not None else self.company_id
        where, params = (" WHERE company_id = :cid", {"cid": cid}) if cid is not None else ("", {})
        try:
            counts = (await self.db.execute(text(
                "SELECT status, COUNT(*) AS n FROM wb_feedback_ai_review"
                f"{where} GROUP BY status"), params)).mappings().all()
        except Exception:
            counts = []
        by_status = {str(r["status"]): int(r["n"]) for r in counts}
        done = by_status.get("ok", 0)
        err = by_status.get("error", 0)
        pending = by_status.get("pending", 0)

        # Очередь (неразобранные) — считаем за 30 дней: полный COUNT по всей
        # истории отзывов без индекса по тексту — слишком тяжёлый.
        queue_count = 0
        try:
            from datetime import date, timedelta
            d30 = (date.today() - timedelta(days=30)).isoformat()
            row = (await self.db.execute(text("""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN r.id IS NOT NULL AND r.status = 'ok' THEN 1 ELSE 0 END) AS done
                FROM wb_feedbacks f
                LEFT JOIN wb_feedback_ai_review r
                       ON r.company_id = f.company_id AND r.feedback_id = f.id
                WHERE f.text IS NOT NULL AND f.text <> ''
                  AND f.createdDate >= :d1
                  {cid}
            """), {**params, "d1": f"{d30} 00:00:00"})).mappings().first()
            d = dict(row or {})
            queue_count = max(0, _i(d.get("total")) - _i(d.get("done")))
        except Exception:
            queue_count = 0

        settings = await self.get_settings()
        q = await self.queue_preview(limit=1)
        quota = await llm_quota.check_fast(self.db, cid)
        return {
            "flags": status_flags(cid),
            "counts": {"done": done, "error": err, "pending": pending,
                       "queue_count": queue_count,
                       "queue_has_more": bool(q.get("has_more"))},
            "settings": {"auto": settings["auto"], "batch": settings["batch"]},
            "prompt_set": bool(settings["prompt"]),
            "scenario": SCENARIO,
            "quota": quota,
        }

    async def get_log(self, limit: int = 50, offset: int = 0,
                      level: str | None = None,
                      company_id: int | None = None) -> dict:
        """Журнал фонового разбора (пагинация, фильтр по уровню)."""
        limit = max(1, min(int(limit or 50), 500))
        offset = max(0, int(offset or 0))
        where = ""
        params: dict = {"lim": limit, "off": offset}
        if level:
            where = " WHERE level = :level"
            params["level"] = level
        if company_id is not None:
            where += (" AND " if where else " WHERE ") + "company_id = :cid"
            params["cid"] = company_id
        try:
            rows = (await self.db.execute(text(
                "SELECT id, company_id, level, action, message, created_at "
                f"FROM wb_feedback_review_log{where} "
                "ORDER BY id DESC LIMIT :lim OFFSET :off"), params)).mappings().all()
            total = int((await self.db.execute(text(
                f"SELECT COUNT(*) FROM wb_feedback_review_log{where}"), params)).scalar() or 0)
        except Exception:
            return {"items": [], "total": 0,
                    "error": "нет таблицы журнала — примените миграцию 20261043"}
        items = []
        for r in rows:
            d = dict(r)
            d["created_at"] = str(d.get("created_at") or "")[:16]
            d["message"] = str(d.get("message") or "")[:500]
            items.append(d)
        return {"items": items, "total": total}

    async def run_now(self, limit: int = 20,
                      company_id: int | None = None) -> dict:
        """Разобрать порцию прямо сейчас — СИНХРОННО (воркер).

        Кнопка «Разобрать порцию» в UI идёт через start_run(): батч из 100
        отзывов по 30-60 с каждый нельзя держать в HTTP-запросе (nginx отрежет).
        """
        cid = company_id if company_id is not None else self.company_id
        if llm_balance.is_paused(cid):
            # токены кончились — не жжём очередь, а говорим когда ждать
            st = llm_balance.state(cid)
            return {"taken": 0, "ok": 0, "errors": 0, "fatal": "",
                    "paused": True, "pause_until": st["until"],
                    "pause_reason": st["reason"]}
        svc = FeedbackReviewService(self.db, company_id=cid)
        st = await svc.review_pending(limit=limit)
        if st["ok"] or st["errors"]:
            await _log(self.db, "info",
                       f"ручной запуск: разобрано {st['ok']}, ошибок {st['errors']}",
                       action="manual", company_id=cid)
            await self.db.commit()
        return st

    async def start_run(self, limit: int = 20, company_id: int | None = None) -> dict:
        """Запустить разбор порции В ФОНЕ — HTTP-запрос не блокируется.

        Прогресс — в журнале разбора (строка каждые 10 отзывов), итог — в конце.
        """
        global _manual_task, _manual_company
        cid = company_id if company_id is not None else self.company_id
        if manual_running():
            return {"started": False, "reason": "разбор уже идёт"}
        if llm_balance.is_paused(cid):
            st = llm_balance.state(cid)
            return {"started": False, "paused": True, "pause_until": st["until"],
                    "pause_reason": st["reason"]}
        # остаток лимита у провайдера — мало → пауза до сброса окна
        q = await llm_quota.check(self.db, cid)
        if llm_quota.is_low(q) and q.get("pause_until"):
            reason = f"лимит ИИ {q.get('percent')}% · сброс {str(q.get('reset_at') or '')[:16]}"
            llm_balance.pause_until(cid, q["pause_until"], reason=reason)
            return {"started": False, "paused": True, "pause_until": q["pause_until"],
                    "pause_reason": reason}
        limit = max(1, min(int(limit or 20), 500))

        async def _work() -> None:
            global _manual_company
            _manual_company = cid
            try:
                from backend.database import SessionLocal
                async with SessionLocal() as db:
                    svc = FeedbackReviewService(db, company_id=cid)
                    st = await svc.review_pending(limit=limit)
                    await _log(db, "info",
                               f"ручной запуск: разобрано {st['ok']}, ошибок {st['errors']} "
                               f"(взято {st['taken']})", action="manual", company_id=cid)
                    await db.commit()
            except Exception as exc:
                log.warning("feedback_review: ручной запуск упал (%s: %s)",
                            type(exc).__name__, exc)
            finally:
                _manual_company = None

        _manual_task = asyncio.create_task(_work())
        return {"started": True, "limit": limit}

    async def retry_all(self, company_id: int | None = None) -> dict:
        """Вернуть ВСЕ отзывы с ошибкой в очередь разбора."""
        cid = company_id if company_id is not None else self.company_id
        where = " AND company_id = :cid" if cid is not None else ""
        params = {"cid": cid} if cid is not None else {}
        res = await self.db.execute(text(
            "UPDATE wb_feedback_ai_review SET status = 'pending', error = NULL, "
            f"updated_at = NOW() WHERE status = 'error'{where}"), params)
        await self.db.commit()
        return {"ok": True, "count": int(res.rowcount or 0)}

    # --- статистика (дашборд) -----------------------------------------------

    async def stats(self, date_from: str, date_to: str) -> dict:
        """Доли меток по разобранным отзывам за период + «разобрано X из Y»."""
        cid_where, params = self._cid_where()
        params = {**params, "d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        row = (await self.db.execute(text(f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN r.id IS NOT NULL AND r.status='ok' THEN 1 ELSE 0 END) AS parsed_ok,
                   SUM(CASE WHEN r.status='error' THEN 1 ELSE 0 END) AS parsed_err,
                   SUM(CASE WHEN r.emotion='low' THEN 1 ELSE 0 END) AS e_low,
                   SUM(CASE WHEN r.emotion='mid' THEN 1 ELSE 0 END) AS e_mid,
                   SUM(CASE WHEN r.emotion='high' THEN 1 ELSE 0 END) AS e_high,
                   SUM(CASE WHEN r.constructiveness='low' THEN 1 ELSE 0 END) AS c_low,
                   SUM(CASE WHEN r.constructiveness='mid' THEN 1 ELSE 0 END) AS c_mid,
                   SUM(CASE WHEN r.constructiveness='high' THEN 1 ELSE 0 END) AS c_high,
                   SUM(CASE WHEN r.tone='neg' THEN 1 ELSE 0 END) AS t_neg,
                   SUM(CASE WHEN r.tone='pos' THEN 1 ELSE 0 END) AS t_pos,
                   SUM(CASE WHEN r.tone='neutral' THEN 1 ELSE 0 END) AS t_neutral
            FROM wb_feedbacks f
            LEFT JOIN wb_feedback_ai_review r
                   ON r.company_id = f.company_id AND r.feedback_id = f.id
            WHERE f.text IS NOT NULL AND f.text <> ''
              AND f.createdDate BETWEEN :d1 AND :d2
              {cid_where}
        """), params)).mappings().first()
        d = dict(row or {})

        def _pct(v, base):
            return round(v * 100 / base) if base else 0

        parsed = _i(d.get("parsed_ok"))
        err = _i(d.get("parsed_err"))
        total = _i(d.get("total"))
        emotion = {"low": _i(d.get("e_low")), "mid": _i(d.get("e_mid")), "high": _i(d.get("e_high"))}
        construct = {"low": _i(d.get("c_low")), "mid": _i(d.get("c_mid")), "high": _i(d.get("c_high"))}
        tone = {"neg": _i(d.get("t_neg")), "pos": _i(d.get("t_pos")), "neutral": _i(d.get("t_neutral"))}
        return {
            "total": total,
            "parsed": parsed,
            "errors": err,
            "emotion": [{"name": k, "cnt": v, "pct": _pct(v, parsed)} for k, v in emotion.items()],
            "constructiveness": [{"name": k, "cnt": v, "pct": _pct(v, parsed)} for k, v in construct.items()],
            "tone": [{"name": k, "cnt": v, "pct": _pct(v, parsed)} for k, v in tone.items()],
        }
