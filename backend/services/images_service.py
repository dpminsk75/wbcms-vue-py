"""Локальный кэш фото WB: пути, скачивание, пережатие в WebP, учёт в БД.

План: `plans/2026-10-31_PLAN_local-images-cache.md`.

Ключевые решения:
  * **Один размер на фото** — 516×688 (3:4, родной кадр WB), WebP q82.
    Меньше — мыло в галерее модалки (260 px ширины), больше — трафик и диск.
  * **Файлы глобальные** — один URL = один файл на всех компаний, company_id
    в таблицах нет: nm_id — глобальный ключ карточки WB.
  * **Ключ файла = md5 нормализованного URL**: все размеры одного кадра
    (`c246x328`, `big`, …) нормализуются в `c516x688` → попадают в один файл.
  * Нет httpx/aiohttp в проекте — скачивание через stdlib `urllib`
    (как в `wb_token_service`, `feedback_wb_sender`).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import pathlib
import re
import socket
import time
import urllib.request
from contextlib import contextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("wbcms.images")

# Метка версии: сервис и робот обязаны быть из одной выкатки. При старте
# робот проверяет согласованность (см. images_sync_service._check_versions) —
# иначе вызовы не совпадут по сигнатуре и тик будет падать.
CODE_VERSION = "2026-10-31.2"

# --- размеры и качество -------------------------------------------------
TARGET_W = 516
TARGET_H = 688
WEBP_QUALITY = 82
WEBP_METHOD = 4

# --- сеть ---------------------------------------------------------------
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")
HTTP_TIMEOUT = 10        # секунд на одну попытку (короткий: нормальный ответ 0,2–1 с)
DOWNLOAD_TRIES = 3       # попыток на одно фото
RETRY_PAUSE = 1.0        # пауза между попытками, сек
MAX_BYTES = 5 * 1024 * 1024

# --- журнал --------------------------------------------------------------
LOG_KEEP = 500

# --- дефолты настроек (перекрываются строкой source='settings') -----------
DEFAULT_SETTINGS: dict[str, int] = {
    "ttl_days": 180,      # сколько дней хранить фото, которое больше не встречается
    "interval_sec": 600,  # интервал тика робота, сек (10 минут)
    "batch_limit": 150,   # сколько фото скачивать за тик
    "sweep_limit": 200,   # сколько проверять за тик в недельном обходе
}

# WB отдаёт кадр в разных размерах: /images/big/, /images/c516x688/, …
# Переписываем на c516x688 — тот кадр, который мы и так берём сегодня
# (WbSearchCard.vue:98). Переписываем ТОЛЬКО известные размеры: в новом
# формате WB после /images/ идёт номер тома, и подмена сломала бы URL.
_SIZE_SEGMENT = re.compile(r"/images/([^/]+)/")
_KNOWN_SIZES = {"big", "small", "mini", "tm1", "tm2", "c516x688", "c246x328", "c1032x1376"}
_SIZE_LIKE = re.compile(r"^c\d+x\d+$")

_root: pathlib.Path | None = None


# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------

def img_root() -> pathlib.Path:
    """Папка кэша. Env `WB_IMAGES_DIR` важнее дефолта <корень проекта>/wb_images."""
    global _root
    if _root is None:
        env = (os.getenv("WB_IMAGES_DIR") or "").strip()
        root = pathlib.Path(env) if env else pathlib.Path(__file__).resolve().parents[2] / "wb_images"
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.warning("images: не удалось создать папку %s: %s", root, exc)
        _root = root
    return _root


def file_path(src_key: str) -> pathlib.Path:
    """Путь к файлу по ключу."""
    return img_root() / f"{src_key}.webp"


def dir_stats() -> dict:
    """Сколько файлов в кэше и сколько они занимают."""
    count = 0
    total = 0
    try:
        with os.scandir(img_root()) as it:
            for entry in it:
                if entry.is_file() and entry.name.endswith(".webp"):
                    count += 1
                    total += entry.stat().st_size
    except OSError as exc:
        log.debug("images: не удалось прочитать папку кэша: %s", exc)
    return {"files": count, "bytes": total}


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------

def _is_size_segment(seg: str) -> bool:
    return seg in _KNOWN_SIZES or bool(_SIZE_LIKE.match(seg))


def normalize_url(url: str) -> str:
    """Привести URL фото к канону: https, без query, кадр c516x688.

    Идемпотентна: normalize(normalize(u)) == normalize(u).
    """
    s = (url or "").strip()
    if not s:
        return ""
    if s.startswith("//"):
        s = "https:" + s
    s = s.split("?", 1)[0].split("#", 1)[0]
    m = _SIZE_SEGMENT.search(s)
    if m and _is_size_segment(m.group(1)):
        s = _SIZE_SEGMENT.sub("/images/c516x688/", s, count=1)
    return s


def src_key(url: str) -> str:
    """Ключ файла: md5 нормализованного URL."""
    return hashlib.md5(normalize_url(url).encode("utf-8")).hexdigest()


def first_image(raw: Any) -> str:
    """Первое фото из значения WB: JSON-массив (иногда дважды закодированный),
    список объектов, объект или просто URL."""
    val = raw
    for _ in range(2):
        if isinstance(val, (list, dict)):
            break
        if not isinstance(val, str):
            return ""
        s = val.strip()
        if not s:
            return ""
        try:
            val = json.loads(s)
        except ValueError:
            return s if s.startswith("http") else ""
    if isinstance(val, dict):
        nested = val.get("images") or val.get("urls") or val.get("photo")
        val = nested if nested is not None else [val]
    if isinstance(val, str):
        val = [val]
    if not isinstance(val, list):
        return ""
    for item in val:
        if isinstance(item, dict):
            item = (item.get("big") or item.get("c516x688") or item.get("url")
                    or item.get("photo") or item.get("square"))
        s = str(item or "").strip()
        if s.startswith("//"):
            s = "https:" + s
        if s.startswith("http"):
            return s
    return ""


# ---------------------------------------------------------------------------
# Скачивание и пережатие
# ---------------------------------------------------------------------------

_real_getaddrinfo = socket.getaddrinfo


@contextmanager
def _force_ipv4():
    """Резолвим только IPv4.

    У части хостов CDN WB есть AAAA-записи, но маршрут по IPv6 с сервера не
    работает: TCP-соединение устанавливается, а дальше виснет TLS-рукопожатие.
    Ответ получается только по IPv4.
    """
    def getaddrinfo(host, port, family=0, *args, **kwargs):
        return _real_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
    socket.getaddrinfo = getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = _real_getaddrinfo


def download(url: str) -> bytes:
    """Скачать фото с CDN WB. Бросает исключение при ошибке."""
    with _force_ipv4():
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = resp.read(MAX_BYTES + 1)
    if not data:
        raise ValueError("пустой ответ")
    if len(data) > MAX_BYTES:
        raise ValueError(f"файл больше {MAX_BYTES} байт")
    return data


def head_info(url: str) -> dict | None:
    """HEAD-запрос: размер и ETag без скачивания тела.

    Нужен недельному обходу: «фото изменилось?» — обычно хватает смены
    Content-Length/ETag. Если CDN не отдаёт HEAD — None, тогда фолбэк на GET.
    """
    try:
        with _force_ipv4():
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                length = resp.headers.get("Content-Length")
                return {
                    "length": int(length) if length and length.isdigit() else None,
                    "etag": (resp.headers.get("ETag") or "").strip() or None,
                    "status": int(getattr(resp, "status", 0) or 0),
                }
    except Exception as exc:  # HEAD может быть запрещён — это не ошибка
        log.debug("images: HEAD %s не удался: %s", url, exc)
        return None


def make_webp(data: bytes) -> tuple[bytes, int, int]:
    """Пережать в WebP 516×688. Пропорции сохраняются, лишнее обрезается по центру.

    Возвращает (байты webp, ширина, высота).
    """
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        fitted = ImageOps.fit(im, (TARGET_W, TARGET_H),
                              method=Image.LANCZOS, centering=(0.5, 0.5))
        out = io.BytesIO()
        fitted.save(out, format="WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
        return out.getvalue(), fitted.width, fitted.height


def store(src_key_: str, data: bytes) -> pathlib.Path:
    """Записать файл кэша (через временный — чтобы читатель не увидел половину)."""
    path = file_path(src_key_)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


def content_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def fetch_webp(url: str) -> tuple[bytes, bytes, int, int]:
    """Скачать фото и пережать в WebP. До DOWNLOAD_TRIES попыток, между ними пауза.

    Синхронно — вызывать через to_thread. Возвращает (исходные байты, байты
    webp, ширина, высота).
    """
    last: Exception | None = None
    for attempt in range(1, DOWNLOAD_TRIES + 1):
        try:
            raw = download(url)
            data, width, height = make_webp(raw)
            return raw, data, width, height
        except Exception as exc:
            last = exc
            if attempt < DOWNLOAD_TRIES:
                time.sleep(RETRY_PAUSE)
    raise RuntimeError(f"попыток {DOWNLOAD_TRIES}: {type(last).__name__}: {last}") from last


# ---------------------------------------------------------------------------
# Многострочные вставки (чанки по 300 — MySQL не любит тысячи параметров)
# ---------------------------------------------------------------------------

CHUNK = 300


def _multi_values(rows: list[dict], cols: list[tuple[str, str | None]]) -> tuple[str, dict]:
    """Собрать список VALUES из rows. Возвращает (кусок SQL, параметры).

    cols: [(имя_колонки, sql-литерал|None)]. Литерал (например 'NOW()')
    подставляется как есть, иначе значение берётся из словаря строки.
    """
    parts: list[str] = []
    params: dict[str, Any] = {}
    for i, row in enumerate(rows):
        vals = []
        for c, lit in cols:
            if lit is not None:
                vals.append(lit)
                continue
            name = f"v{i}_{c}"
            params[name] = row.get(c)
            vals.append(f":{name}")
        parts.append("(" + ", ".join(vals) + ")")
    return ", ".join(parts), params


def _chunks(values: list, size: int = CHUNK):
    for i in range(0, len(values), size):
        yield values[i:i + size]


def chunks(values: list, size: int = CHUNK):
    """Порции по size элементов (MySQL не любит тысячи параметров)."""
    return _chunks(values, size)


# ---------------------------------------------------------------------------
# Журнал
# ---------------------------------------------------------------------------

_log_tail = 0


async def log_event(level: str, message: str, *,
                    action: str = "", nm_id: int | None = None) -> None:
    """Строка в wb_images_log.

    Отдельная сессия намеренно: журнал — диагностика, он не должен ломать
    робота. Если писать в ту же транзакцию, что и основную работу, то любой
    сбой в журнале откатил бы и сами изменения (файлы-то уже на диске).
    """
    global _log_tail
    try:
        from backend.database import SessionLocal
        async with SessionLocal() as db:
            await db.execute(text("""
                INSERT INTO wb_images_log (`level`, `action`, `message`, `nm_id`)
                VALUES (:level, :action, :msg, :nm)
            """), {"level": level, "action": action or "", "msg": str(message)[:1000],
                  "nm": nm_id})
            _log_tail += 1
            if _log_tail >= 200:
                _log_tail = 0
                await db.execute(text("""
                    DELETE FROM wb_images_log
                    WHERE id < (SELECT id FROM wb_images_log
                                ORDER BY id DESC LIMIT 1 OFFSET :keep)
                """), {"keep": LOG_KEEP})
            await db.commit()
    except Exception as exc:  # журнал не должен ронять робота
        log.warning("images: журнал недоступен (%s: %s)", type(exc).__name__, exc)


# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------

def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if raw.isdigit():
        return int(raw)
    return default


async def get_settings(db: AsyncSession) -> dict:
    """Настройки робота из строки source='settings' (создаётся при первом обращении)."""
    row = (await db.execute(text("""
        SELECT ttl_days, interval_sec, batch_limit, sweep_limit
        FROM wb_images_state WHERE source = 'settings'
    """))).mappings().first()
    if not row:
        values = {
            "ttl": _env_int("WB_IMAGES_TTL_DAYS", DEFAULT_SETTINGS["ttl_days"]),
            "ival": DEFAULT_SETTINGS["interval_sec"],
            "batch": DEFAULT_SETTINGS["batch_limit"],
            "sweep": DEFAULT_SETTINGS["sweep_limit"],
        }
        await db.execute(text("""
            INSERT INTO wb_images_state (source, ttl_days, interval_sec, batch_limit, sweep_limit)
            VALUES ('settings', :ttl, :ival, :batch, :sweep)
        """), values)
        await db.commit()
        return {
            "ttl_days": values["ttl"],
            "interval_sec": values["ival"],
            "batch_limit": values["batch"],
            "sweep_limit": values["sweep"],
        }
    out = dict(DEFAULT_SETTINGS)
    for key in DEFAULT_SETTINGS:
        val = row.get(key)
        if val is not None:
            out[key] = int(val)
    return out


async def save_settings(db: AsyncSession, **kwargs) -> dict:
    """Сохранить настройки. Принимает только известные ключи."""
    await get_settings(db)
    allowed = {k: int(v) for k, v in kwargs.items()
               if k in DEFAULT_SETTINGS and v is not None and str(v).strip() != ""}
    if not allowed:
        return await get_settings(db)
    sets = ", ".join(f"{k} = :{k}" for k in allowed)
    params = dict(allowed)
    params.update({"ttl": allowed.get("ttl_days", DEFAULT_SETTINGS["ttl_days"]),
                   "ival": allowed.get("interval_sec", DEFAULT_SETTINGS["interval_sec"]),
                   "batch": allowed.get("batch_limit", DEFAULT_SETTINGS["batch_limit"]),
                   "sweep": allowed.get("sweep_limit", DEFAULT_SETTINGS["sweep_limit"])})
    await db.execute(text(f"UPDATE wb_images_state SET {sets} WHERE source = 'settings'"),
                     params)
    await db.commit()
    return await get_settings(db)


# ---------------------------------------------------------------------------
# Очередь и учёт
# ---------------------------------------------------------------------------

async def enqueue_images(db: AsyncSession, items: list[dict]) -> int:
    """Поставить URL в очередь на скачивание и обновить last_seen_at.

    items: [{'url': …, 'nm_id': …}]. Возвращает, сколько записей затронуто.
    Одна многострочная вставка на чанк: новые URL попадают в state='pending',
    уже известные — обновляют last_seen_at (по нему считается уборка).
    """
    if not items:
        return 0
    rows: list[dict] = []
    seen: set[str] = set()
    for it in items:
        url = normalize_url(it.get("url") or "")
        if not url:
            continue
        key = src_key(url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"url": url, "key": key, "nm": it.get("nm_id")})
    if not rows:
        return 0
    total = 0
    for chunk in _chunks(rows):
        values, params = _multi_values(chunk, [
            ("url", None), ("key", None), ("nm", None),
            ("state", "'pending'"), ("last_seen_at", "NOW()"),
        ])
        await db.execute(text(f"""
            INSERT INTO wb_images (src_url, src_key, nm_id, state, last_seen_at)
            VALUES {values}
            AS new
            ON DUPLICATE KEY UPDATE
                last_seen_at = new.last_seen_at,
                nm_id = COALESCE(new.nm_id, wb_images.nm_id)
        """), params)
        total += len(chunk)
    return total


async def upsert_current(db: AsyncSession, rows: list[dict]) -> int:
    """Записать текущее фото карточек.

    rows: [{'nm_id': …, 'url': …, 'key': …, 'source': …, 'priority': …}].
    changed_at двигается только если сменился сам src_key (фото).
    """
    if not rows:
        return 0
    total = 0
    for chunk in _chunks(rows):
        values, params = _multi_values(chunk, [
            ("nm", None), ("url", None), ("key", None), ("src", None), ("prio", None),
            ("changed_at", "NOW()"),
        ])
        await db.execute(text(f"""
            INSERT INTO wb_images_current (nm_id, src_url, src_key, source, priority, changed_at)
            VALUES {values}
            AS new
            ON DUPLICATE KEY UPDATE
                src_url = new.src_url,
                src_key = new.src_key,
                source = new.source,
                priority = new.priority,
                changed_at = IF(wb_images_current.src_key = new.src_key,
                                wb_images_current.changed_at, new.changed_at)
        """), params)
        total += len(chunk)
    return total


async def add_history(db: AsyncSession, rows: list[dict]) -> int:
    """События смены фото.

    rows: [{'nm_id':…, 'event':…, 'key':…, 'url':…, 'prev_key':…, 'prev_url':…,
            'hash':…, 'prev_hash':…, 'message':…}]
    """
    if not rows:
        return 0
    total = 0
    for chunk in _chunks(rows):
        values, params = _multi_values(chunk, [
            ("nm", None), ("event", None), ("key", None), ("url", None),
            ("prev_key", None), ("prev_url", None),
            ("hash", None), ("prev_hash", None), ("msg", None),
        ])
        await db.execute(text(f"""
            INSERT INTO wb_images_history
                (nm_id, event, src_key, src_url, prev_src_key, prev_src_url,
                 content_hash, prev_content_hash, message)
            VALUES {values}
        """), params)
        total += len(chunk)
    return total


async def find_card_photo(db: AsyncSession, nm_id: int) -> tuple[str, str]:
    """Найти главное фото карточки: (url, source).

    Порядок источников — тот же, что у приоритетов: наша карточка, потом
    собранная карточка конкурента, потом фото из выдачи.
    """
    row = (await db.execute(text(
        "SELECT photos FROM wbcards WHERE nmID = :nm LIMIT 1"), {"nm": nm_id})).mappings().first()
    if row:
        url = first_image(row.get("photos"))
        if url:
            return normalize_url(url), "wbcards"

    row = (await db.execute(text(
        "SELECT images, preview_image FROM wb_competitor_details WHERE nm_id = :nm LIMIT 1"),
        {"nm": nm_id})).mappings().first()
    if row:
        url = first_image(row.get("images")) or normalize_url(row.get("preview_image") or "")
        if url:
            return url, "details"

    row = (await db.execute(text(
        "SELECT image_url FROM wb_competitor_cards WHERE nm_id = :nm AND image_url <> '' "
        "ORDER BY id DESC LIMIT 1"), {"nm": nm_id})).mappings().first()
    if row:
        url = normalize_url(row.get("image_url") or "")
        if url:
            return url, "cards"
    return "", ""
