"""Кэш фото WB: отдача картинок и управление роботом — /api/img, /api/images/*.

`GET /api/img?u=<url>` — отдаёт локальную копию (WebP 516×688). Копии ещё нет →
302 на исходный URL WB, поэтому фронт работает как раньше, пока робот не
догрузил кэш.

Гейт управления — require_seo (viewSeo|admin). Файлы кэша **глобальные**
(для всех компаний), company_id в таблицах нет.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import require_seo
from backend.services import images_service as svc
from backend.services import images_sync_service as worker

router = APIRouter(prefix="/api", tags=["images"])

# CDN Wildberries — картинки отдаём только с него (иначе /api/img стал бы
# чужим редиректом на любой URL).
# Хосты WB множатся: basket-01.wb.ru, basket-28.wbbasket.ru,
# mns-basket-cdn-02.geobasket.net, ...wbtree.net — список расширяем по факту.
WB_HOST_SUFFIXES = (
    ".wb.ru",
    ".wbbasket.ru",
    ".geobasket.net",
    ".wbtree.net",
    ".wbstatic.net",
)


def _is_wb_url(url: str) -> bool:
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    if any(host.endswith(h) for h in WB_HOST_SUFFIXES):
        return True
    # новые CDN-хосты WB по шаблону basket-*: не блокируем, но и не пускаем
    # чужие домены (в них должен быть «basket» и домен WB)
    return "basket" in host and host.endswith((".net", ".ru", ".com"))


# ---------------------------------------------------------------------------
# Отдача картинки
# ---------------------------------------------------------------------------

@router.get("/img")
async def img(u: str = Query(..., min_length=1)):
    """Локальная копия фото; нет копии — 302 на WB.

    Без JWT: `<img>` не умеет слать токен, а фото WB публичные.
    """
    target = svc.normalize_url(u) or u
    if not _is_wb_url(target):
        raise HTTPException(status_code=404, detail="не WB-ссылка")
    key = svc.src_key(target)
    path = svc.file_path(key)
    try:
        stat = path.stat()
    except OSError:
        stat = None
    if stat is not None and stat.st_size:
        return FileResponse(
            path,
            media_type="image/webp",
            headers={
                "Cache-Control": "public, max-age=86400",
                "ETag": f'"{stat.st_size}-{int(stat.st_mtime)}"',
            },
        )
    # копии нет — отдаём исходник (короткий кеш, чтобы после догрузки
    # браузер переключился на локальный файл)
    return RedirectResponse(target, status_code=302,
                            headers={"Cache-Control": "public, max-age=300"})


# ---------------------------------------------------------------------------
# Статус и журнал
# ---------------------------------------------------------------------------

@router.get("/images/status")
async def images_status(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """Состояние робота: фаза, счётчики, размер кэша на диске, настройки."""
    settings = await svc.get_settings(db)
    counts = {"pending": 0, "ok": 0, "error": 0, "gone": 0}
    for r in (await db.execute(text(
            "SELECT state, COUNT(*) AS n FROM wb_images GROUP BY state"))).mappings().all():
        counts[str(r["state"])] = int(r["n"])
    total = sum(counts.values())
    # Счётчики для бейджей на вкладках — в этом же ответе, чтобы страница не
    # делала отдельные запросы ради цифр.
    history_total = int((await db.execute(text(
        "SELECT COUNT(*) AS n FROM wb_images_history"))).scalar() or 0)
    log_total = int((await db.execute(text(
        "SELECT COUNT(*) AS n FROM wb_images_log"))).scalar() or 0)
    files = svc.dir_stats()
    phase = await worker.phase(db)
    st = worker.status()
    return {
        **st,
        "phase": phase,
        "phase_label": "Наблюдение (недельный обход)" if phase == "watch" else "Сбор",
        "version": svc.CODE_VERSION,
        "counts": counts,
        "total": total,
        "history_total": history_total,
        "log_total": log_total,
        "files": files["files"],
        "bytes": files["bytes"],
        "settings": settings,
    }


@router.get("/images/log")
async def images_log(
    level: str = Query(default=""),
    action: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """Журнал робота (хвост)."""
    where = ""
    params: dict = {"lim": limit, "off": offset}
    if level:
        where += " AND level = :level"
        params["level"] = level
    if action:
        where += " AND action = :action"
        params["action"] = action
    rows = (await db.execute(text(
        f"SELECT id, `level`, `action`, `message`, nm_id, created_at FROM wb_images_log "
        f"WHERE 1=1{where} ORDER BY id DESC LIMIT :lim OFFSET :off"), params)).mappings().all()
    total = int((await db.execute(text(
        f"SELECT COUNT(*) AS n FROM wb_images_log WHERE 1=1{where}"), params)).scalar() or 0)
    return {"items": [dict(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


@router.get("/images/history")
async def images_history(
    nm_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """История смены фото: было → стало."""
    where = ""
    params: dict = {"lim": limit, "off": offset}
    if nm_id:
        where = " WHERE nm_id = :nm"
        params["nm"] = nm_id
    rows = (await db.execute(text(
        f"SELECT id, nm_id, event, src_url, prev_src_url, content_hash, "
        f"prev_content_hash, message, changed_at FROM wb_images_history{where} "
        f"ORDER BY id DESC LIMIT :lim OFFSET :off"), params)).mappings().all()
    total = int((await db.execute(text(
        f"SELECT COUNT(*) AS n FROM wb_images_history{where}"), params)).scalar() or 0)
    return {"items": [dict(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


@router.get("/images/queue")
async def images_queue(
    state: str = Query(default=""),
    nm_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """Очередь фото: что скачано, что ждёт, что сломалось."""
    where = ""
    params: dict = {"lim": limit, "off": offset}
    if state:
        where += " AND state = :state"
        params["state"] = state
    if nm_id:
        where += " AND nm_id = :nm"
        params["nm"] = nm_id
    rows = (await db.execute(text(
        f"SELECT id, nm_id, state, src_url, width, height, bytes, attempts, "
        f"last_error, first_seen_at, last_seen_at, downloaded_at, checked_at "
        f"FROM wb_images WHERE 1=1{where} ORDER BY id DESC LIMIT :lim OFFSET :off"),
        params)).mappings().all()
    total = int((await db.execute(text(
        f"SELECT COUNT(*) AS n FROM wb_images WHERE 1=1{where}"), params)).scalar() or 0)
    return {"items": [dict(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Управление
# ---------------------------------------------------------------------------

@router.get("/images/settings")
async def images_settings_get(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """Настройки робота."""
    return {"settings": await svc.get_settings(db)}


@router.put("/images/settings")
async def images_settings_put(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """Сохранить настройки: ttl_days, interval_sec, batch_limit, sweep_limit."""
    payload = payload or {}
    saved = await svc.save_settings(
        db,
        ttl_days=payload.get("ttl_days"),
        interval_sec=payload.get("interval_sec"),
        batch_limit=payload.get("batch_limit"),
        sweep_limit=payload.get("sweep_limit"),
    )
    await svc.log_event("info", "настройки обновлены", action="settings")
    await db.commit()
    return {"ok": True, "settings": saved}


@router.post("/images/queue")
async def images_queue_add(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """Поставить фото карточки в очередь на скачивание: {nm_id}."""
    try:
        nm = int((payload or {}).get("nm_id") or 0)
    except (TypeError, ValueError):
        nm = 0
    if nm <= 0:
        raise HTTPException(status_code=400, detail="bad nm_id")
    url, source = await svc.find_card_photo(db, nm)
    if not url:
        raise HTTPException(status_code=404, detail="фото карточки не найдено в базе")
    await svc.enqueue_images(db, [{"url": url, "nm_id": nm}])
    await db.commit()
    await svc.log_event("info", f"в очередь добавлено фото карточки {nm} ({source})",
                        action="manual", nm_id=nm)
    return {"ok": True, "nm_id": nm, "url": url, "source": source}


@router.post("/images/queue/{img_id}/requeue")
async def images_queue_requeue(
    img_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """Вернуть фото в очередь (перекачать)."""
    res = await db.execute(text("""
        UPDATE wb_images SET state = 'pending', attempts = 0, last_error = NULL
        WHERE id = :id
    """), {"id": img_id})
    if not res.rowcount:
        raise HTTPException(status_code=404, detail="запись не найдена")
    await db.commit()
    return {"ok": True}


@router.post("/images/run")
async def images_run(
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
):
    """Прогнать порцию скачивания прямо сейчас."""
    try:
        limit = int((payload or {}).get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50
    res = await worker.run_manual(max(1, min(limit, 300)))
    return res


@router.post("/images/pause")
async def images_pause(
    payload: dict | None = Body(default=None),
    _user: dict = Depends(require_seo),
):
    """Пауза/старт фонового цикла (флаг в памяти процесса)."""
    want = bool((payload or {}).get("paused"))
    worker.set_paused(want)
    return {"ok": True, "paused": want}
