"""Фоновый робот кэша фото WB: обход источников, скачивание, история, уборка.

План: `plans/2026-10-31_PLAN_local-images-cache.md`.

Живёт внутри процесса FastAPI (как `feedback_review_service` / `phrase_miner_service`):
тик раз в 10 минут, пауза/старт и ручной прогон — из интерфейса.

Две фазы:
  1. **Сбор** — обходим источники и качаем всё, чего ещё нет. Источники
     мутабельные (карточка обновляется на месте) и append-only (снимок выдачи).
  2. **Наблюдение** — когда все источники пройдены до конца, включается
     еженедельный обход собранного: HEAD-запрос по каждому файлу, и если
     размер/ETag изменился — перекачиваем и пишем событие «фото сменилось».

Курсоры обхода лежат в `wb_images_state` (переживают рестарт).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import images_service as svc

log = logging.getLogger("wbcms.images")

# --- источники: приоритет решает, кто «главнее» при расхождении фото ------
SOURCES: dict[str, dict] = {
    "wbcards": {"priority": 100, "kind": "cursor_ts"},
    "details": {"priority": 90, "kind": "full"},
    "cards": {"priority": 50, "kind": "full"},
    "position": {"priority": 10, "kind": "cursor_id"},
}

POSITION_BATCH = 1000      # строк снимка выдачи за тик
MUTABLE_BATCH = 1000       # строк мутабельного источника за проход
FULL_SCAN_LIMIT = 20000
SWEEP_INTERVAL_DAYS = 7    # недельный обход собранного
GC_EVERY_HOURS = 24        # уборка — раз в сутки
MAX_ATTEMPTS = 3           # попыток на строку в БД (строка уходит в ошибку после этого)
BATCH_TIME_BUDGET = 300    # секунд на один батч скачивания: не тратим тик на сеть

_started = False
_task: asyncio.Task | None = None
_manual_task: asyncio.Task | None = None
_paused = False
_tick_count = 0
_last_mutable_scan: datetime | None = None
_last_tick: str | None = None
_last_error: str | None = None
_last_result: dict = {}
_schema_checked = False
# тик и ручной прогон не должны идти одновременно: они пишут в одни и те же
# строки wb_images → deadlock (1213) при пересечении по ключу
_run_lock = asyncio.Lock()

NEED_COLUMNS = ("src_length", "src_etag", "content_hash", "checked_at", "state")


# ---------------------------------------------------------------------------
# Состояние / управление
# ---------------------------------------------------------------------------

def started() -> bool:
    return bool(_started and _task is not None and not _task.done())


def manual_running() -> bool:
    return _manual_task is not None and not _manual_task.done()


def set_paused(v: bool) -> None:
    """Пауза/старт фонового цикла (флаг в памяти процесса)."""
    global _paused
    _paused = bool(v)


def status() -> dict:
    """Состояние цикла для интерфейса."""
    return {
        "running": started(),
        "paused": _paused,
        "manual_running": manual_running(),
        "last_tick": _last_tick,
        "last_error": _last_error,
        "last_result": dict(_last_result),
    }


def start() -> None:
    """Запуск фонового цикла (вызывается из main.py startup). Повтор — no-op."""
    global _started, _task
    if _started:
        return
    _started = True
    _check_versions()
    _task = asyncio.create_task(_loop())
    log.info("images: робот кэша фото запущен (версия %s)", svc.CODE_VERSION)


def _check_versions() -> None:
    """Проверить, что сервис и робот из одной выкатки.

    Если файлы разных версий, сигнатуры не совпадут (log_event) — и тик будет
    падать на каждом шаге. Ловим это сразу и говорим в журнал сервера.
    """
    import inspect
    try:
        params = list(inspect.signature(svc.log_event).parameters)
    except (TypeError, ValueError) as exc:
        log.error("images: не смог проверить сигнатуру log_event: %s", exc)
        return
    if params[:2] != ["level", "message"]:
        log.error("images: ВЕРСИИ НЕ СОВПАДАЮТ — images_service.py и "
                  "images_sync_service.py из разных выкаток (сигнатура log_event: %s). "
                  "Перекопируй ОБА файла.", params)
    else:
        log.info("images: версия %s, сигнатуры совпадают", svc.CODE_VERSION)


def stop() -> None:
    """Остановить фоновые задачи (shutdown процесса) — иначе uvicorn ждёт их."""
    for task in (_task, _manual_task):
        if task is not None and not task.done():
            task.cancel()


async def run_manual(limit: int = 50) -> dict:
    """Ручной прогон: скачать порцию прямо сейчас (без ожидания расписания)."""
    global _manual_task
    if manual_running():
        return {"ok": False, "error": "ручной прогон уже идёт"}
    _manual_task = asyncio.create_task(_manual(limit))
    return {"ok": True}


async def _manual(limit: int) -> None:
    from backend.database import SessionLocal
    try:
        async with _run_lock:
            async with SessionLocal() as db:
                res = await _download_batch(db, limit)
                await db.commit()
        log.info("images: ручной прогон: %s", res)
    except Exception as exc:
        log.warning("images: ручной прогон упал (%s: %s)", type(exc).__name__, exc)
    finally:
        _manual_task = None


# ---------------------------------------------------------------------------
# Цикл
# ---------------------------------------------------------------------------

async def _loop() -> None:
    """Основной цикл: сбой не убивает задачу — пишем в журнал и продолжаем."""
    global _last_tick, _last_error, _last_result
    while True:
        wait = 600.0
        try:
            from backend.database import SessionLocal
            async with SessionLocal() as db:
                settings = await svc.get_settings(db)
                wait = float(settings.get("interval_sec") or 600)
                if _paused:
                    wait = 30.0
                else:
                    async with _run_lock:
                        result = await _tick(db, settings)
                        _last_tick = datetime.now().isoformat(timespec="seconds")
                        _last_result = result
                await db.commit()
        except Exception as exc:
            _last_error = f"{type(exc).__name__}: {exc}"
            log.warning("images: тик упал (%s: %s)", type(exc).__name__, exc)
            # нет таблиц (миграция не применена) — не долбимся, ждём дольше
            wait = 300.0 if "1146" in str(exc) or "doesn't exist" in str(exc) else 30.0
        await asyncio.sleep(wait)


async def _check_schema(db: AsyncSession) -> None:
    """Один раз за процесс проверяем, что в wb_images есть все нужные колонки.

    Таблица создаётся через CREATE TABLE IF NOT EXISTS, поэтому если миграция
    применена была раньше (и колонок в ней не было) — повторное применение
    их не добавит. Ловим это тут и говорим в журнал сервера.
    """
    global _schema_checked
    if _schema_checked:
        return
    _schema_checked = True
    try:
        rows = (await db.execute(text("""
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wb_images'
              AND COLUMN_NAME IN ('src_length', 'src_etag', 'content_hash',
                                  'checked_at', 'state')
        """))).mappings().all()
        have = {str(r["COLUMN_NAME"]) for r in rows}
        missing = [c for c in NEED_COLUMNS if c not in have]
        if missing:
            log.error("images: в wb_images нет колонок %s — примените миграцию "
                      "20261047_wb_images_src_len.sql", missing)
    except Exception as exc:
        log.debug("images: проверка схемы не удалась: %s", exc)


async def _tick(db: AsyncSession, settings: dict) -> dict:
    """Один тик: собрать → скачать → (в фазе наблюдения) обойти за неделю."""
    global _tick_count, _last_error
    _tick_count += 1
    _last_error = None

    await _check_schema(db)

    current = await _load_current(db)
    discovered = await _discover(db)
    events, current_rows = _compare(current, discovered)
    if current_rows:
        await svc.upsert_current(db, current_rows)
    if events:
        await svc.add_history(db, events)
    await svc.enqueue_images(db, [{"url": v["url"], "nm_id": nm}
                                  for nm, v in discovered.items()])
    await db.commit()

    downloaded = await _download_batch(db, int(settings.get("batch_limit") or 150))
    await db.commit()

    cur_phase = await phase(db)
    swept = 0
    if cur_phase == "watch":
        # обход и уборка — отдельные шаги: их сбой не должен ронять тик
        try:
            swept = await _sweep(db, int(settings.get("sweep_limit") or 200), current)
            await db.commit()
        except Exception as exc:
            log.warning("images: недельный обход упал (%s: %s)", type(exc).__name__, exc)

    removed = 0
    if await _gc_due(db):
        try:
            removed = await _gc(db, int(settings.get("ttl_days") or 180))
            await db.commit()
        except Exception as exc:
            log.warning("images: уборка упала (%s: %s)", type(exc).__name__, exc)

    result = {
        "phase": cur_phase,
        "discovered": len(discovered),
        "events": len(events),
        "downloaded": downloaded,
        "swept": swept,
        "removed": removed,
    }
    log.info("images: тик: %s", result)
    return result


# ---------------------------------------------------------------------------
# Текущее состояние фото
# ---------------------------------------------------------------------------

async def _load_current(db: AsyncSession) -> dict:
    """Карта «текущее фото карточки»: nm_id -> (src_key, priority, url).

    Один запрос на тик — разбор в Python, без N+1 (правила AGENTS.md).
    """
    rows = (await db.execute(text(
        "SELECT nm_id, src_key, priority, src_url FROM wb_images_current"
    ))).mappings().all()
    return {int(r["nm_id"]): (str(r["src_key"]), int(r["priority"] or 0), str(r["src_url"] or ""))
            for r in rows}


# ---------------------------------------------------------------------------
# Обход источников
# ---------------------------------------------------------------------------

async def _state_row(db: AsyncSession, source: str) -> dict:
    row = (await db.execute(text(
        "SELECT source, cursor_id, cursor_ts, done_at FROM wb_images_state WHERE source = :s"),
        {"s": source})).mappings().first()
    if not row:
        await db.execute(text(
            "INSERT INTO wb_images_state (source) VALUES (:s)"), {"s": source})
        row = {"source": source, "cursor_id": 0, "cursor_ts": None, "done_at": None}
    return dict(row)


async def _save_state(db: AsyncSession, source: str, **fields) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    params = {k: v for k, v in fields.items()}
    params["s"] = source
    await db.execute(text(
        f"UPDATE wb_images_state SET {sets} WHERE source = :s"), params)


async def _discover(db: AsyncSession) -> dict:
    """Собрать фото из источников: nm_id -> {url, source, priority, key}.

    Внутри источника берём ПОСЛЕДНЕЕ наблюдение (строки идут по id/времени).
    """
    found: dict[int, dict] = {}

    async def put(nm_id, url, source):
        url = svc.normalize_url(url)
        if not nm_id or not url:
            return
        priority = SOURCES[source]["priority"]
        cur = found.get(nm_id)
        if cur and cur["priority"] > priority:
            return
        found[nm_id] = {"url": url, "source": source, "priority": priority,
                        "key": svc.src_key(url)}

    # Мутабельные источники (карточка обновляется на месте) — раз в час.
    global _last_mutable_scan
    now = datetime.now()
    hourly = (_last_mutable_scan is None
              or (now - _last_mutable_scan) >= timedelta(hours=1))

    # 1. Снимок поисковой выдачи — append-only, курсор по id.
    st = await _state_row(db, "position")
    cur_id = int(st.get("cursor_id") or 0)
    rows = (await db.execute(text(
        "SELECT id, nm_id, image_url FROM wb_competitor_position "
        "WHERE id > :cur ORDER BY id LIMIT :lim"),
        {"cur": cur_id, "lim": POSITION_BATCH})).mappings().all()
    max_id = cur_id
    for r in rows:
        max_id = max(max_id, int(r["id"]))
        await put(int(r["nm_id"]), r["image_url"] or "", "position")
    if max_id != cur_id:
        await _save_state(db, "position", cursor_id=max_id)
    if not rows and not st.get("done_at"):
        await _save_state(db, "position", done_at=datetime.now())

    # 2. Карточки конкурентов из выдачи — мутабельные, полный скан раз в час.
    if hourly:
        rows = (await db.execute(text(
            "SELECT nm_id, image_url FROM wb_competitor_cards "
            "WHERE COALESCE(image_url, '') <> '' LIMIT :lim"),
            {"lim": FULL_SCAN_LIMIT})).mappings().all()
        for r in rows:
            await put(int(r["nm_id"]), r["image_url"] or "", "cards")
        st = await _state_row(db, "cards")
        if not st.get("done_at"):
            await _save_state(db, "cards", done_at=datetime.now())

        # 3. Собранные карточки конкурентов — галерея, полный скан раз в час.
        rows = (await db.execute(text(
            "SELECT nm_id, images, preview_image FROM wb_competitor_details LIMIT :lim"),
            {"lim": FULL_SCAN_LIMIT})).mappings().all()
        for r in rows:
            url = svc.first_image(r.get("images")) or (r.get("preview_image") or "")
            await put(int(r["nm_id"]), url, "details")
        st = await _state_row(db, "details")
        if not st.get("done_at"):
            await _save_state(db, "details", done_at=datetime.now())

        # 4. Наши карточки — курсор по updated_at.
        st = await _state_row(db, "wbcards")
        cur_ts = st.get("cursor_ts") or "2000-01-01 00:00:00"
        rows = (await db.execute(text(
            "SELECT nmID, photos, updated_at FROM wbcards "
            "WHERE updated_at >= :ts ORDER BY updated_at LIMIT :lim"),
            {"ts": cur_ts, "lim": MUTABLE_BATCH})).mappings().all()
        max_ts = cur_ts
        for r in rows:
            ts = r.get("updated_at")
            if ts is not None:
                max_ts = max(str(max_ts), str(ts))
            await put(int(r["nmID"]), svc.first_image(r.get("photos")), "wbcards")
        if rows:
            await _save_state(db, "wbcards", cursor_ts=max_ts)
        elif not st.get("done_at"):
            await _save_state(db, "wbcards", done_at=datetime.now())

    if hourly:
        _last_mutable_scan = now
    return found


def _compare(current: dict, discovered: dict) -> tuple[list[dict], list[dict]]:
    """Разобрать расхождения: события истории + строки текущего фото."""
    events: list[dict] = []
    current_rows: list[dict] = []
    for nm_id, item in discovered.items():
        prev = current.get(nm_id)
        if not prev:
            events.append({"nm": nm_id, "event": "new", "key": item["key"],
                           "url": item["url"], "prev_key": None, "prev_url": None,
                           "hash": None, "prev_hash": None, "msg": None})
            current_rows.append({"nm": nm_id, "url": item["url"], "key": item["key"],
                                 "src": item["source"], "prio": item["priority"]})
            continue
        prev_key, prev_prio, prev_url = prev
        if prev_key == item["key"]:
            continue
        if item["priority"] < prev_prio:
            # фото из выдачи не перебивает фото из собранной карточки
            continue
        events.append({"nm": nm_id, "event": "replaced", "key": item["key"],
                       "url": item["url"], "prev_key": prev_key, "prev_url": prev_url,
                       "hash": None, "prev_hash": None, "msg": "фото сменилось"})
        current_rows.append({"nm": nm_id, "url": item["url"], "key": item["key"],
                             "src": item["source"], "prio": item["priority"]})
    return events, current_rows


# ---------------------------------------------------------------------------
# Скачивание
# ---------------------------------------------------------------------------

async def _download_batch(db: AsyncSession, limit: int) -> int:
    """Скачать и пережать порцию фото.

    Файл пишем на диск сразу, а состояние в БД — **отдельной сессией**:
    сбой записи не должен откатывать уже скачанное и ронять весь батч.
    Каждый UPDATE — под SAVEPOINT: одна плохая строка не роняет остальные.
    """
    rows = (await db.execute(text(
        "SELECT src_url, src_key FROM wb_images "
        "WHERE state IN ('pending', 'error') AND attempts < :max "
        "ORDER BY id LIMIT :lim"),
        {"max": MAX_ATTEMPTS, "lim": max(1, limit)})).mappings().all()
    if not rows:
        return 0
    # Скачивание держит сеть до BATCH_TIME_BUDGET (300 с): read view от SELECT
    # не должна жить в это время — всё материализовано в rows, txn закрываем.
    # Записи тут дальше нет: результаты пишет отдельная сессия (_write_results).
    await db.rollback()
    ok_rows: list[dict] = []
    err_rows: list[dict] = []
    deadline = time.monotonic() + BATCH_TIME_BUDGET
    for r in rows:
        # бюджет времени: не тратим тик на сеть — остальное уйдёт в следующий
        if time.monotonic() > deadline:
            log.info("images: бюджет батча исчерпан (%s с) — остальное в следующий тик",
                     BATCH_TIME_BUDGET)
            break
        url = str(r["src_url"])
        key = str(r["src_key"])
        try:
            # сеть и Pillow — в потоке: иначе event loop веба встанет на всё время
            raw, data, width, height = await asyncio.to_thread(svc.fetch_webp, url)
            svc.store(key, data)
            ok_rows.append({"k": key, "w": width, "h": height, "b": len(data),
                            "ch": svc.content_hash(data), "sl": len(raw)})
        except Exception as exc:
            err_rows.append({"k": key, "e": str(exc)[:500]})
    await _write_results(ok_rows, err_rows)
    await svc.log_event("info",
                        f"скачано {len(ok_rows)} из {len(rows)} (ошибок: {len(err_rows)})",
                        action="download")
    return len(ok_rows)


async def _write_results(ok_rows: list[dict], err_rows: list[dict]) -> None:
    """Записать результаты скачивания в БД — отдельной сессией и под SAVEPOINT."""
    if not ok_rows and not err_rows:
        return
    from backend.database import SessionLocal
    try:
        # сортируем по ключу: единый порядок блокировок строк → меньше шанс deadlock
        ok_rows.sort(key=lambda r: r["k"])
        err_rows.sort(key=lambda r: r["k"])
        async with SessionLocal() as db:
            for row in ok_rows:
                try:
                    async with db.begin_nested():
                        await db.execute(text("""
                            UPDATE wb_images
                            SET state = 'ok', width = :w, height = :h, bytes = :b,
                                content_hash = :ch, src_length = :sl, downloaded_at = NOW(),
                                checked_at = NOW(), last_error = NULL, attempts = attempts + 1
                            WHERE src_key = :k
                        """), {"w": row["w"], "h": row["h"], "b": row["b"],
                              "ch": row["ch"], "sl": row["sl"], "k": row["k"]})
                except Exception as exc:
                    # строка не обновилась (например нет колонки) — помечаем ошибкой
                    log.error("images: %s: не записал состояние: %s", row["k"], exc)
                    await _mark_error(db, row["k"], f"не записал состояние: {exc}")
            for row in err_rows:
                await _mark_error(db, row["k"], row["e"])
            await db.commit()
    except Exception as exc:
        log.error("images: не записал результаты (%s: %s)", type(exc).__name__, exc)


async def _mark_error(db: AsyncSession, key: str, err: str) -> None:
    """Пометить фото как неудачное (под SAVEPOINT — ошибка не роняет батч)."""
    try:
        async with db.begin_nested():
            await db.execute(text("""
                UPDATE wb_images
                SET state = 'error', attempts = attempts + 1, last_error = :err
                WHERE src_key = :k
            """), {"err": str(err)[:500], "k": key})
    except Exception as exc:
        log.error("images: %s: не пометил ошибку: %s", key, exc)


# ---------------------------------------------------------------------------
# Недельный обход (фаза «наблюдение»)
# ---------------------------------------------------------------------------

async def phase(db: AsyncSession) -> str:
    """Фаза робота: сбор, пока не пройдены все источники; дальше — наблюдение."""
    rows = (await db.execute(text(
        "SELECT source, done_at FROM wb_images_state WHERE source IN ('wbcards','details','cards','position')"
    ))).mappings().all()
    done = {str(r["source"]): r["done_at"] for r in rows}
    if len(done) >= 4 and all(done.get(s) for s in ("wbcards", "details", "cards", "position")):
        return "watch"
    return "collect"


async def _sweep(db: AsyncSession, limit: int, current: dict) -> int:
    """Еженедельный обход: HEAD по каждому файлу, при отличии — перекачать.

    Тот же URL, но другое содержимое — редкий случай; ловим по размеру/ETag.
    """
    days = int(SWEEP_INTERVAL_DAYS)
    rows = (await db.execute(text(
        f"SELECT src_url, src_key, content_hash, src_length, src_etag FROM wb_images "
        f"WHERE state = 'ok' AND checked_at < NOW() - INTERVAL {days} DAY "
        f"ORDER BY checked_at LIMIT :lim"),
        {"lim": max(1, limit)})).mappings().all()
    if not rows:
        return 0
    # Read view от SELECT не должна жить через HEAD/скачивание всех строк:
    # материализовано в rows — txn закрываем, запись коммитим после каждого
    # UPDATE (см. ниже).
    await db.rollback()
    nm_by_key = {key: nm for nm, (key, _p, _u) in current.items()}
    changed = 0
    for r in rows:
        url = str(r["src_url"])
        key = str(r["src_key"])
        info = await asyncio.to_thread(svc.head_info, url)
        differs = False
        if info:
            old_len = r.get("src_length")
            old_etag = r.get("src_etag")
            if old_len is not None and info.get("length") and int(old_len) != int(info["length"]):
                differs = True
            elif old_etag and info.get("etag") and str(old_etag) != str(info["etag"]):
                differs = True
        else:
            # HEAD недоступен — фолбэк на полное скачивание
            differs = True
        if not differs:
            await db.execute(text(
                "UPDATE wb_images SET checked_at = NOW() WHERE src_key = :k"), {"k": key})
            await db.commit()
            continue
        try:
            raw, data, width, height = await asyncio.to_thread(svc.fetch_webp, url)
            new_hash = svc.content_hash(data)
            old_hash = r.get("content_hash")
            svc.store(key, data)
            await db.execute(text("""
                UPDATE wb_images
                SET width = :w, height = :h, bytes = :b, content_hash = :ch,
                    src_length = :sl, downloaded_at = NOW(), checked_at = NOW(),
                    state = 'ok', last_error = NULL
                WHERE src_key = :k
            """), {"w": width, "h": height, "b": len(data), "ch": new_hash,
                  "sl": len(raw), "k": key})
            if old_hash and new_hash != old_hash:
                changed += 1
                await svc.add_history(db, [{
                    "nm": nm_by_key.get(key), "event": "replaced", "key": key,
                    "url": url, "prev_key": key, "prev_url": url,
                    "hash": new_hash, "prev_hash": old_hash,
                    "msg": "фото изменилось (тот же URL)",
                }])
            await db.commit()
        except Exception as exc:
            await db.execute(text(
                "UPDATE wb_images SET checked_at = NOW(), last_error = :err WHERE src_key = :k"),
                {"err": str(exc)[:500], "k": key})
            await db.commit()
            log.debug("images: sweep не удался %s: %s", url, exc)
    if changed:
        await svc.log_event("info", f"обновлено фото: {changed}", action="sweep")
    return changed


# ---------------------------------------------------------------------------
# Уборка
# ---------------------------------------------------------------------------

async def _gc_due(db: AsyncSession) -> bool:
    """Пора ли убирать (раз в сутки). Отметка — в строке source='gc'."""
    st = await _state_row(db, "gc")
    last = st.get("cursor_ts")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(str(last))
    except ValueError:
        return True
    return (datetime.now() - last_dt) >= timedelta(hours=GC_EVERY_HOURS)


async def _gc(db: AsyncSession, ttl_days: int) -> int:
    """Убрать фото, которые дольше TTL не встречаются в источниках.

    Критерий — last_seen_at: фото, которое мы всё ещё видим, при каждом обходе
    обновляет его и не удаляется, даже если файл старый.
    """
    ttl = max(1, int(ttl_days))
    rows = (await db.execute(text(
        f"SELECT id, src_key FROM wb_images WHERE last_seen_at < NOW() - INTERVAL {ttl} DAY "
        f"LIMIT 5000"))).mappings().all()
    removed = 0
    keys: list[str] = []
    for r in rows:
        key = str(r["src_key"])
        keys.append(key)
        try:
            svc.file_path(key).unlink(missing_ok=True)
        except OSError:
            pass
        removed += 1
    if keys:
        for chunk in svc.chunks(keys):
            marks = ", ".join(f":k{i}" for i in range(len(chunk)))
            params = {f"k{i}": v for i, v in enumerate(chunk)}
            await db.execute(text(f"DELETE FROM wb_images WHERE src_key IN ({marks})"), params)
            await db.execute(text(f"DELETE FROM wb_images_current WHERE src_key IN ({marks})"), params)
    # события истории — тоже под нож (по времени)
    await db.execute(text(
        f"DELETE FROM wb_images_history WHERE changed_at < NOW() - INTERVAL {ttl} DAY"))

    # осиротевшие файлы: на диске есть, в базе нет
    orphans = await _orphan_files(db)
    for key in orphans:
        try:
            svc.file_path(key).unlink(missing_ok=True)
        except OSError:
            pass
    removed += len(orphans)
    if removed:
        await svc.log_event("info",
                            f"уборка: удалено {removed} (ttl {ttl_days} дн., осиротевших {len(orphans)})",
                            action="gc")
    await _save_state(db, "gc", cursor_ts=datetime.now())
    return removed


async def _orphan_files(db: AsyncSession) -> list[str]:
    """Файлы в папке кэша, для которых нет строки в wb_images."""
    known = {str(r["src_key"]) for r in
             (await db.execute(text("SELECT src_key FROM wb_images"))).mappings().all()}
    out: list[str] = []
    try:
        for entry in svc.img_root().iterdir():
            if not entry.is_file() or not entry.name.endswith(".webp"):
                continue
            key = entry.stem
            if key not in known:
                out.append(key)
    except OSError:
        pass
    return out
