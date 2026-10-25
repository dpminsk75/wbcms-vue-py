"""Фоновый разбор фраз карточек конкурентов («phrase miner», 2026-10-28).

Асинхронный воркер, стартует в main.py:startup. Живёт, пока жив процесс; пауза —
только in-memory (после рестарта снова работает, очередь остаётся в БД).

Одна итерация цикла:
  1. Пополнение очереди wb_phrase_miner_queue (раз в REFILL_INTERVAL или при пустой):
     - приоритет 1: конкуренты из свежесобранных карточек SEO-мониторинга
       (wb_enrich_queue source='watch', status='done', processed_at за 24 ч);
     - приоритет 2 (наполнение): пары (наша карточка, конкурент) по всем компаниям,
       у которых сырьё в wb_competitor_phrase_comp отсутствует/устарело (content_hash),
       свежие → старые (full_collected_at).
  2. Одно дело = ОДИН конкурент = ОДИН вызов LLM (шаг 1 ручного «Разобрать фразы»).
     Сырьё пишется во ВСЕ привязки конкурента к карточкам компании — за конкурента
     платим один раз, а не за каждую привязку (фразы конкурент-специфичные).
  3. Каждое событие — строка в wb_phrase_miner_log.

Слияние формулировок (merge) фоном НЕ гоняется — остаётся в ручном анализе:
тот подхватит готовое сырьё через кэш content_hash, останутся только батчи merge.

Защиты: пауза между вызовами, отдых после серии, пропуск тика при активном ручном
run (wb_competitor_run), backoff при ошибках. Учет затрат — ai_log через llm.chat
(scenario='newcard_phrases_miner'), виден на /seo/ai-usage как «Фразы (фон-разбор)».
"""

import asyncio
import hashlib
import logging
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import SessionLocal
from backend.services import openrouter_service as llm
from backend.services import llm_provider
from backend.services.competitors_newcard_service import (
    DEFAULT_PHRASES_PROMPT,
    PHRASES_TASK_SUFFIX,
    PHRASES_MAX_TOKENS,
    PER_CALL_ATTEMPTS,
    _norm_phrase,
    _parse_json,
    _phrases_from_parsed,
)

log = logging.getLogger("wbcms.phrase_miner")

# --- константы (согласовано в чате 2026-10-25) ---
SCENARIO = "newcard_phrases_miner"  # имя сценария в ai_log / «Затраты ИИ»
MIN_DESC_LEN = 50                   # как DESC_MIN_LEN в competitors_newcard_service
CALL_PAUSE = 8.0                    # пауза между вызовами LLM, с
REST_EVERY = 20                     # после стольких карточек подряд — отдых
REST_SECS = 120.0                   # длительность отдыха, с
WATCH_WINDOW_H = 24                 # приоритетное окно «из SEO-мониторинга», ч
REFILL_INTERVAL = 300.0             # как часто пополняем очередь, с
IDLE_SLEEP = 60.0                   # пауза при пустой очереди / пропуске, с
PAIR_FILL_LIMIT = 200               # максимум пар за одно пополнение
ERROR_FAILS = 2                     # неудач подряд → отложить дело
ERROR_HOURS = 1                     # …на этот срок, ч
STALE_PROCESSING_MIN = 30           # зависший processing → обратно в pending
TAIL_KEEP = 10000                   # ретенция журнала (строк)

_log_tail = 0  # вставок журнала с последней чистки


async def _log(db: AsyncSession, level: str, msg: str, *, competitor_nm_id: int | None = None,
               phrases_cnt: int | None = None, model: str | None = None,
               ms: int | None = None, company_id: int | None = None,
               source_nm_id: int | None = None, action: str | None = None,
               queue_id: int | None = None, priority: int | None = None) -> None:
    """Строка в журнал работы. Журнал не должен ломать работу — сбои глотаем.

    Карточный контекст (компания, наша карточка, конкурент, приоритет) — чтобы
    журнал читался так же, как очередь."""
    global _log_tail
    try:
        await db.execute(text("""
            INSERT INTO wb_phrase_miner_log
              (level, action, msg, company_id, source_nm_id, competitor_nm_id,
               queue_id, priority, phrases_cnt, model, ms)
            VALUES (:lv, :act, :msg, :co, :src, :c, :q, :pr, :p, :m, :ms)
        """), {"lv": level, "act": action, "msg": (msg or "")[:500], "co": company_id,
               "src": source_nm_id, "c": competitor_nm_id, "q": queue_id, "pr": priority,
               "p": phrases_cnt, "m": model, "ms": ms})
        _log_tail += 1
        if _log_tail >= 200:  # чистим журнал периодически, не под каждым событием
            _log_tail = 0
            await db.execute(text("""
                DELETE FROM wb_phrase_miner_log
                WHERE id < (SELECT id FROM (
                    SELECT id FROM wb_phrase_miner_log ORDER BY id DESC LIMIT 1 OFFSET :keep
                ) x)
            """), {"keep": TAIL_KEEP - 1})
        await db.commit()
    except Exception as exc:
        db.rollback()
        log.warning("phrase_miner log: %s: %s", type(exc).__name__, exc)


# --- in-memory состояние воркера ---

_started = False
_task: asyncio.Task | None = None
_paused = False
_current: dict | None = None  # {competitor_nm_id, company_id, source_nm_id, since}
_last_refill = 0.0
_last_error: dict | None = None  # {msg, ts}


def is_running() -> bool:
    return _started and _task is not None and not _task.done()


def status_flags() -> dict:
    """Плоский статус для роутера (без походов в БД)."""
    return {
        "running": is_running(),
        "paused": _paused,
        "current": dict(_current) if _current else None,
        "last_error": dict(_last_error) if _last_error else None,
    }


def set_paused(v: bool) -> None:
    global _paused
    _paused = bool(v)


def start() -> None:
    """Запуск фонового цикла (main.py:startup). Повторный вызов — no-op."""
    global _started, _task
    if _started:
        return
    _started = True
    _task = asyncio.create_task(_loop())
    log.info("phrase_miner: started")


# --- очередь: готовность, пополнение, claim ---

async def _tables_ready(db: AsyncSession) -> bool:
    """Есть ли таблицы очереди/журнала (миграция 20261028)."""
    try:
        await db.execute(text("SELECT id FROM wb_phrase_miner_queue LIMIT 1"))
        return True
    except Exception as exc:
        log.warning("phrase_miner: нет миграции 20261028 (%s: %s)", type(exc).__name__, exc)
        return False


async def _manual_run_active(db: AsyncSession) -> bool:
    """Прямо сейчас идёт ручной разбор (wb_competitor_run.phase='phrases' в работе) —
    не мешаем модалке, пропускаем тик."""
    try:
        row = (await db.execute(text("""
            SELECT 1 FROM wb_competitor_run
            WHERE phase='phrases' AND status IN ('queued','running')
            LIMIT 1
        """))).first()
        return bool(row)
    except Exception:  # таблицы нет — миграция 20261027 не применена
        return False


async def refill(db: AsyncSession) -> int:
    """Пополнение очереди: приоритет (watch-сборы) + наполнение (неразобранные пары).
    Возвращает число вставленных строк (INSERT IGNORE — дедуп по UNIQUE)."""
    added = 0
    # 1) Приоритет: конкуренты, только что собранные из SEO-мониторинга.
    #    У конкурента без описания дела не создаём вовсе.
    r = await db.execute(text(r"""
        INSERT IGNORE INTO wb_phrase_miner_queue
          (company_id, source_nm_id, competitor_nm_id, content_hash, priority, status)
        SELECT DISTINCT w.company_id, c.source_nm_id, c.nm_id,
               MD5(CONCAT_WS('\n', d.nm_id, COALESCE(d.title,''), COALESCE(d.description,''))),
               1, 'pending'
        FROM wb_enrich_queue q
        JOIN wb_competitor_cards c ON c.nm_id = q.nm_id
        JOIN wbcards w ON w.nmID = c.source_nm_id
        JOIN wb_competitor_details d ON d.nm_id = q.nm_id
        WHERE q.source='watch' AND q.status='done'
          AND q.processed_at >= DATE_SUB(NOW(), INTERVAL :win HOUR)
          AND CHAR_LENGTH(COALESCE(d.description,'')) >= :minlen
        LIMIT :lim
    """), {"win": WATCH_WINDOW_H, "minlen": MIN_DESC_LEN, "lim": PAIR_FILL_LIMIT})
    added += r.rowcount or 0

    # 2) Наполнение: пары (наша карточка, конкурент) со свежими описаниями, у которых
    #    сырьё ещё не разобрано (нет строк с ТЕКУЩИМ content_hash). Свежие → старые.
    r = await db.execute(text(r"""
        INSERT IGNORE INTO wb_phrase_miner_queue
          (company_id, source_nm_id, competitor_nm_id, content_hash, priority, status)
        SELECT x.company_id, x.source_nm_id, x.nm_id, x.h, 2, 'pending'
        FROM (
            SELECT w.company_id AS company_id, c.source_nm_id, c.nm_id,
                   MD5(CONCAT_WS('\n', d.nm_id, COALESCE(d.title,''),
                                 COALESCE(d.description,''))) AS h,
                   COALESCE(d.full_collected_at, d.collected_at) AS fc
            FROM wbcards w
            JOIN wb_competitor_cards c ON c.source_nm_id = w.nmID
            JOIN wb_competitor_details d ON d.nm_id = c.nm_id
            WHERE CHAR_LENGTH(COALESCE(d.description,'')) >= :minlen
              AND w.company_id IS NOT NULL
        ) x
        WHERE NOT EXISTS (
            SELECT 1 FROM wb_competitor_phrase_comp pc
            WHERE pc.source_nm_id = x.source_nm_id
              AND pc.competitor_nm_id = x.nm_id
              AND pc.content_hash = x.h
        )
        ORDER BY x.fc DESC
        LIMIT :lim
    """), {"minlen": MIN_DESC_LEN, "lim": PAIR_FILL_LIMIT})
    added += r.rowcount or 0
    await db.commit()
    return added


async def _claim_next(db: AsyncSession) -> dict | None:
    """Взять одно дело. Бытовой ремонт: зависший processing → pending; error с
    истёкшим отложением → pending. Кандидаты с активным backoff не выдаём."""
    await db.execute(text("""
        UPDATE wb_phrase_miner_queue
        SET status='pending', processed_at=NULL
        WHERE status='processing' AND processed_at < DATE_SUB(NOW(), INTERVAL :stale MINUTE)
    """), {"stale": STALE_PROCESSING_MIN})
    await db.execute(text("""
        UPDATE wb_phrase_miner_queue
        SET status='pending', error_until=NULL
        WHERE status='error' AND error_until IS NOT NULL AND error_until <= NOW()
    """))
    rows = (await db.execute(text("""
        SELECT id, company_id, source_nm_id, competitor_nm_id, content_hash, priority
        FROM wb_phrase_miner_queue
        WHERE status='pending'
          AND (error_until IS NULL OR error_until <= NOW())
        ORDER BY priority, id
        LIMIT 20
    """))).mappings().all()
    for row in rows:
        job = dict(row)
        upd = await db.execute(text("""
            UPDATE wb_phrase_miner_queue
            SET status='processing', processed_at=NOW()
            WHERE id=:id AND status='pending'
        """), {"id": job["id"]})
        if (upd.rowcount or 0) == 1:
            await db.commit()
            return job
    await db.commit()
    return None


def _comp_hash(title: str, description: str, cid: int) -> str:
    """Тот же хеш, что _comp_content_hash в competitors_newcard_service (nm\ntitle\ndesc)."""
    payload = "\n".join([str(cid or ""), str(title or ""), str(description or "")])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


async def _competitor_details(db: AsyncSession, nm_id: int) -> dict:
    row = (await db.execute(text("""
        SELECT nm_id, title, description FROM wb_competitor_details WHERE nm_id=:n
    """), {"n": nm_id})).mappings().first()
    return dict(row) if row else {}


async def _company_bindings(db: AsyncSession, company_id: int, nm_id: int) -> list[int]:
    """Наши карточки компании (wbcards компании), к которым привязан конкурент."""
    rows = (await db.execute(text("""
        SELECT c.source_nm_id FROM wb_competitor_cards c
        JOIN wbcards w ON w.nmID = c.source_nm_id
        WHERE w.company_id=:cid AND c.nm_id=:n
    """), {"cid": company_id, "n": nm_id})).all()
    return sorted({int(r[0]) for r in rows})


async def _save_comp_rows(db: AsyncSession, nm_id: int, company_id: int, cid: int,
                          phrases: list[str], model: str | None, content_hash: str) -> None:
    """Сырьё по одной паре (тот же INSERT…ON DUPLICATE, что в ручном анализе;
    phrase_id заполняется при слиянии в ручном «Разобрать фразы»)."""
    if not phrases:
        return
    rows = [{"c": company_id, "n": nm_id, "cn": cid, "p": p, "m": model, "h": content_hash}
            for p in phrases]
    await db.execute(text("""
        INSERT INTO wb_competitor_phrase_comp
          (company_id, source_nm_id, competitor_nm_id, phrase_id, phrase, model, content_hash)
        VALUES (:c, :n, :cn, NULL, :p, :m, :h)
        ON DUPLICATE KEY UPDATE
          phrase=VALUES(phrase), model=VALUES(model), content_hash=VALUES(content_hash)
    """), rows)


async def _phrases_for_competitor(comp: dict, model: str, company_id: int,
                                  prompt: str) -> tuple[list[str], str | None, int]:
    """Один LLM-вызов на конкурента (аналог _phrases_for_competitor ручного анализа,
    своя сессия — SessionLocal оборачивает вызов, как в ручном анализе).
    Возвращает (фразы|null, ошибка|null, длительность мс). Затраты пишет ai_log."""
    cid = comp.get("nm_id")
    up = (f"=== КОНКУРЕНТ nmID {cid} ===\n"
          f"Название: {(comp.get('title') or '')[:200]}\n"
          f"Описание: {(comp.get('description') or '')[:1500]}\n\n"
          'Извлеки поисковые фразы и верни JSON {"phrases": [...]}.')
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": up}]
    t0 = time.monotonic()
    try:
        async with SessionLocal() as sdb:
            res = await llm.chat(sdb, messages, company_id, temperature=0.1,
                                 max_tokens=PHRASES_MAX_TOKENS, model=model,
                                 reasoning_effort="low", send_max_tokens=True,
                                 note=f"miner конкурент {cid}",
                                 scenario=SCENARIO, user_id=None, nm_id=None)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}", int((time.monotonic() - t0) * 1000)
    ms = int((time.monotonic() - t0) * 1000)
    if res.get("error"):
        detail = str(res.get("error"))
        if res.get("finish_reason") and "finish_reason" not in detail:
            detail += f", finish_reason={res['finish_reason']}"
        return [], detail, ms
    raw = res.get("content") or ""
    phrases = _phrases_from_parsed(_parse_json(raw))
    if not isinstance(phrases, list) or not phrases:
        return [], f"не удалось разобрать список фраз ({' '.join(raw.split())[:120]!r})", ms
    out: list[str] = []
    for item in phrases:
        if isinstance(item, dict):
            item = item.get("phrase") or item.get("text") or ""
        p = _norm_phrase(item)
        if 3 <= len(p) <= 200 and p not in out:
            out.append(p)
    if not out:
        return [], "нет пригодных фраз", ms
    return out, None, ms


async def _delay_job(db: AsyncSession, cid: int, content_hash: str, err: str,
                     company_id: int, source_nm_id: int | None = None,
                     queue_id: int | None = None, priority: int | None = None,
                     action: str = "error") -> None:
    """Неудача: attempts+1; после ERROR_FAILS — error до error_until (backoff).
    Кладём активные строки ЭТОГО конкурента в ЭТОЙ компании (дело одно на конкурента)."""
    await db.execute(text("""
        UPDATE wb_phrase_miner_queue
        SET attempts=attempts+1, last_error=:e, processed_at=NOW(),
            status=IF(attempts+1 >= :fails, 'error', 'pending'),
            error_until=IF(attempts+1 >= :fails,
                           DATE_ADD(NOW(), INTERVAL :hrs HOUR), NULL)
        WHERE competitor_nm_id=:cn AND content_hash=:h AND company_id=:co
          AND status IN ('pending','processing')
    """), {"e": err[:500], "fails": ERROR_FAILS, "hrs": ERROR_HOURS,
           "cn": cid, "h": content_hash, "co": company_id})
    await db.commit()
    await _log(db, "error", f"конкурент {cid}: {err}", competitor_nm_id=cid,
               company_id=company_id, source_nm_id=source_nm_id, action=action,
               queue_id=queue_id, priority=priority)


async def _process(db: AsyncSession, job: dict) -> dict:
    """Одно дело: конкурент → LLM-вызов → сырьё во все привязки компании.
    Возвращает сводку для цикла (фразы, ошибка, done)."""
    global _current
    cid = int(job["competitor_nm_id"])
    company_id = int(job["company_id"])
    our_nm = int(job.get("source_nm_id") or 0) or None
    queue_id = int(job.get("id") or 0) or None
    priority = int(job.get("priority") or 2)
    _current = {"competitor_nm_id": cid, "company_id": company_id,
                "source_nm_id": our_nm or 0, "since": time.time()}

    comp = await _competitor_details(db, cid)
    title = comp.get("title") or ""
    desc = comp.get("description") or ""
    content_hash = str(job.get("content_hash") or "") or _comp_hash(title, desc, cid)

    await _log(db, "info", f"взяли в работу: конкурент {cid}", competitor_nm_id=cid,
               company_id=company_id, source_nm_id=our_nm, action="start",
               queue_id=queue_id, priority=priority)

    if len(desc.strip()) < MIN_DESC_LEN:
        err = "описание короткое/отсутствует — сбор не дотянулся"
        await _delay_job(db, cid, content_hash, err, company_id, our_nm, queue_id, priority,
                         action="skip")
        _current = None
        return {"done": False, "phrases": 0, "error": err}

    st = await llm_provider.company_row(db, company_id)
    st = dict(st) if st else {}
    custom_prompt = (st.get("seo_phrases_prompt") or "").strip()
    prompt = (custom_prompt + PHRASES_TASK_SUFFIX) if custom_prompt else DEFAULT_PHRASES_PROMPT
    try:
        cands = (await llm.model_candidates(db, company_id, kind="newcard"))[:PER_CALL_ATTEMPTS]
    except Exception as exc:
        await _delay_job(db, cid, content_hash, f"модели: {type(exc).__name__}: {exc}",
                         company_id, our_nm, queue_id, priority)
        _current = None
        return {"done": False, "phrases": 0, "error": "модели"}
    if not cands:
        await _delay_job(db, cid, content_hash,
                         f"нет доступных моделей (компания {company_id})",
                         company_id, our_nm, queue_id, priority)
        _current = None
        return {"done": False, "phrases": 0, "error": "нет моделей"}

    phrases: list[str] = []
    model_used: str | None = None
    err: str | None = None
    ms_total = 0
    for mc in cands:
        ph, e, ms = await _phrases_for_competitor(comp, mc, company_id, prompt)
        ms_total += ms
        try:
            await llm.mark_model(db, mc, bool(ph), e or "")
            await db.commit()
        except Exception:
            await db.rollback()
        if ph:
            phrases, model_used, err = ph, mc, None
            break
        err = e

    _current = None
    if not phrases:
        await _delay_job(db, cid, content_hash, err or "нет фраз",
                         company_id, our_nm, queue_id, priority)
        return {"done": False, "phrases": 0,
                "model": model_used or str(cands[0]), "ms": ms_total, "error": err}

    bind_err: str | None = None
    our_ids = await _company_bindings(db, company_id, cid)
    if not our_ids:
        our_ids = [int(job.get("source_nm_id") or 0)]
    saved = 0
    for onm in our_ids:
        if not onm:
            continue
        try:
            await _save_comp_rows(db, onm, company_id, cid, phrases, model_used, content_hash)
            saved += 1
        except Exception as exc:
            await db.rollback()
            bind_err = f"{type(exc).__name__}: {exc}"
            await _log(db, "warn", f"конкурент {cid}: запись сырья в {onm} — {bind_err}",
                       competitor_nm_id=cid, company_id=company_id, source_nm_id=onm,
                       action="error", queue_id=queue_id, priority=priority)
    if saved:
        await db.commit()

    # всё дело завершено: все строки очереди этого конкурента (тот же хеш/компания)
    await db.execute(text("""
        UPDATE wb_phrase_miner_queue
        SET status='done', model=:m, phrases_cnt=:p, last_error=NULL, processed_at=NOW()
        WHERE competitor_nm_id=:cn AND content_hash=:h AND company_id=:cid
          AND status IN ('pending','processing')
    """), {"m": model_used, "p": len(phrases), "cn": cid, "h": content_hash, "cid": company_id})
    await db.commit()
    await _log(db, "info",
               f"конкурент {cid}: {len(phrases)} фраз, компания {company_id}, привязок {saved}",
               competitor_nm_id=cid, phrases_cnt=len(phrases), model=model_used, ms=ms_total,
               company_id=company_id, source_nm_id=our_nm, action="done",
               queue_id=queue_id, priority=priority)
    return {"done": True, "phrases": len(phrases), "model": model_used,
            "ms": ms_total, "bindings": saved}


async def _tick(db: AsyncSession) -> tuple[float, bool]:
    """Один шаг цикла → (пауза до следующего шага, с, сделано ли дело)."""
    global _last_refill, _last_error
    if not await _tables_ready(db):
        return 300.0, False
    if await _manual_run_active(db):
        await _log(db, "info", "тик пропущен: идёт ручной разбор (wb_competitor_run)",
                   action="manual")
        return 30.0, False

    row = (await db.execute(text(
        "SELECT COUNT(*) FROM wb_phrase_miner_queue WHERE status='pending'"
    ))).first()
    pending = int(row[0]) if row else 0
    if pending == 0 or (time.monotonic() - _last_refill) >= REFILL_INTERVAL:
        try:
            added = await refill(db)
            if added:
                await _log(db, "info", f"пополнение очереди: +{added}", action="refill")
        except Exception as exc:
            await db.rollback()
            await _log(db, "error", f"пополнение очереди упало: {type(exc).__name__}: {exc}",
                       action="refill")
        _last_refill = time.monotonic()

    job = await _claim_next(db)
    if not job:
        _current = None
        return IDLE_SLEEP, False
    try:
        res = await _process(db, job)
        _last_error = None  # прошлый сбой отработали
        return CALL_PAUSE, bool(res.get("done"))
    except Exception as exc:
        await db.rollback()
        msg = f"{type(exc).__name__}: {exc}"
        _last_error = {"msg": msg, "ts": time.time()}
        await _log(db, "error", f"конкурент {job.get('competitor_nm_id')}: исключение {msg}",
                   competitor_nm_id=job.get("competitor_nm_id"),
                   company_id=job.get("company_id"),
                   source_nm_id=job.get("source_nm_id"),
                   queue_id=job.get("id"), priority=job.get("priority"), action="error")
        try:
            await db.execute(text("""
                UPDATE wb_phrase_miner_queue
                SET status='error', last_error=:e, processed_at=NOW(),
                    error_until=DATE_ADD(NOW(), INTERVAL :hrs HOUR)
                WHERE id=:id
            """), {"e": msg[:500], "hrs": ERROR_HOURS, "id": job["id"]})
            await db.commit()
        except Exception:
            await db.rollback()
        return 30.0, False


async def _loop() -> None:
    """Основной цикл воркера: сбой не убивает задачу — пишем и продолжаем."""
    done_since_rest = 0
    while True:
        wait = IDLE_SLEEP
        try:
            async with SessionLocal() as db:
                if _paused:
                    _current = None
                    wait = 30.0
                else:
                    wait, done = await _tick(db)
                    if done:
                        done_since_rest += 1
                        if done_since_rest >= REST_EVERY:
                            done_since_rest = 0
                            await _log(db, "info",
                                       f"отдых после {REST_EVERY} карточек — {REST_SECS:.0f} с",
                                       action="rest")
                            wait += REST_SECS
                await db.commit()
        except Exception as exc:  # цикл не умирает
            try:
                async with SessionLocal() as db2:
                    await _log(db2, "error", f"цикл: {type(exc).__name__}: {exc}", action="error")
            except Exception:
                pass
            wait = 30.0
        await asyncio.sleep(wait or IDLE_SLEEP)


# --- данные для страницы (роутер) ---

async def get_status(db: AsyncSession, *, company_id: int | None = None) -> dict:
    """Статус + счётчики очереди (по компании или по всем). Журнал — отдельным
    эндпоинтом /log (со своей пагинацией), здесь его нет."""
    flags = status_flags()
    counts: dict[str, int] = {}
    by_priority: dict[int, int] = {}
    log_counts: dict[str, int] = {}
    where, p = "", {}
    if company_id is not None:
        where, p = " WHERE company_id = :cid", {"cid": company_id}
    try:
        for r in (await db.execute(text(
            f"SELECT status, COUNT(*) AS n FROM wb_phrase_miner_queue{where} GROUP BY status"
        ), p)).mappings().all():
            counts[str(r["status"])] = int(r["n"])
        for r in (await db.execute(text(
            f"SELECT priority, COUNT(*) AS n FROM wb_phrase_miner_queue{where}"
            f"{' AND' if where else ' WHERE'} status='pending' GROUP BY priority"
        ), p)).mappings().all():
            by_priority[int(r["priority"])] = int(r["n"])
        lwhere = " WHERE company_id = :cid" if company_id is not None else ""
        for r in (await db.execute(text(f"""
            SELECT level, COUNT(*) AS n FROM wb_phrase_miner_log{lwhere} GROUP BY level
        """), p)).mappings().all():
            log_counts[str(r["level"])] = int(r["n"])
        log_counts["total"] = sum(log_counts.values())
    except Exception:
        pass
    return {**flags,
            "queue": {"counts": counts, "pending_by_priority": by_priority},
            "log_counts": log_counts}


async def get_queue(db: AsyncSession, *, status: str | None, company_id: int | None = None,
                     limit: int = 50, offset: int = 0) -> dict:
    """Таблица очереди для UI (пагинация, фильтр по статусу и компании)."""
    conds: list[str] = []
    p: dict = {"lim": max(1, min(int(limit), 200)), "off": max(0, int(offset))}
    if status in ("pending", "processing", "done", "error"):
        conds.append("q.status = :st")
        p["st"] = status
    if company_id is not None:
        conds.append("q.company_id = :cid")
        p["cid"] = company_id
    clause = (" WHERE " + " AND ".join(conds)) if conds else ""
    total = (await db.execute(text(f"""
        SELECT COUNT(*) FROM wb_phrase_miner_queue q{clause}
    """), p)).first()
    rows = (await db.execute(text(f"""
        SELECT q.id, q.company_id, q.source_nm_id, q.competitor_nm_id, q.priority,
               q.status, q.attempts, q.last_error, q.error_until, q.model,
               q.phrases_cnt, q.created_at, q.processed_at
        FROM wb_phrase_miner_queue q{clause}
        ORDER BY CASE q.status WHEN 'processing' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
                 q.priority, q.id DESC
        LIMIT :lim OFFSET :off
    """), p)).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("id", "company_id", "source_nm_id", "competitor_nm_id", "priority",
                  "attempts", "phrases_cnt"):
            d[k] = None if d[k] is None else int(d[k])
        for k in ("created_at", "processed_at", "error_until"):
            d[k] = str(d[k]) if d[k] else None
        out.append(d)
    return {"total": int(total[0] or 0) if total else 0, "rows": out,
            "limit": int(limit), "offset": int(offset)}


async def get_log(db: AsyncSession, *, level: str | None = None, action: str | None = None,
                  company_id: int | None = None, limit: int = 50, offset: int = 0) -> dict:
    """Журнал работы: страница с пагинацией + фильтры (уровень, событие, компания)."""
    conds: list[str] = []
    p: dict = {"lim": max(1, min(int(limit), 200)), "off": max(0, int(offset))}
    if level in ("info", "warn", "error"):
        conds.append("l.level = :lv")
        p["lv"] = level
    if action:
        conds.append("l.action = :act")
        p["act"] = action
    if company_id is not None:
        conds.append("l.company_id = :cid")
        p["cid"] = company_id
    clause = (" WHERE " + " AND ".join(conds)) if conds else ""
    try:
        total = (await db.execute(text(f"""
            SELECT COUNT(*) FROM wb_phrase_miner_log l{clause}
        """), p)).first()
        rows = (await db.execute(text(f"""
            SELECT l.id, l.ts, l.level, l.action, l.msg, l.company_id, l.source_nm_id,
                   l.competitor_nm_id, l.queue_id, l.priority, l.phrases_cnt, l.model, l.ms
            FROM wb_phrase_miner_log l{clause}
            ORDER BY l.id DESC
            LIMIT :lim OFFSET :off
        """), p)).mappings().all()
    except Exception as exc:
        # нет новых колонок журнала (миграция 20261029 не применена) — не роняем страницу
        await db.rollback()
        log.warning("phrase_miner log query: %s: %s", type(exc).__name__, exc)
        return {"total": 0, "rows": [], "limit": int(limit), "offset": int(offset),
                "error": "Нет колонок журнала — примените миграцию 20261029_phrase_miner_log_columns.sql"}
    out = []
    for r in rows:
        d = dict(r)
        for k in ("id", "company_id", "source_nm_id", "competitor_nm_id", "queue_id",
                  "priority", "phrases_cnt", "ms"):
            d[k] = None if d[k] is None else int(d[k])
        d["ts"] = str(d["ts"]) if d["ts"] else None
        out.append(d)
    return {"total": int(total[0] or 0) if total else 0, "rows": out,
            "limit": int(limit), "offset": int(offset)}
