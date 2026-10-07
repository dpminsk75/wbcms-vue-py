"""Админка systemd-таймеров воркеров: только require_admin.

GET  /api/admin/timers              — статус всех (whitelist timers_service.ALLOWED)
POST /api/admin/timers/{id}/enable  — enable --now
POST /api/admin/timers/{id}/disable — disable --now
POST /api/admin/timers/{id}/run     — разовый старт .service
PUT  /api/admin/timers/{id}/schedule {on_calendar} — drop-in override + reload
GET  /api/admin/timers/{id}/log?lines=100 — хвост journalctl .service
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from backend.deps import require_admin
from backend.services import timers_service
from backend.services.timers_service import TimersError

router = APIRouter(prefix="/api/admin/timers", tags=["admin-timers"])


def _err(e: TimersError, code: int = 500) -> HTTPException:
    msg = str(e)
    if msg.startswith(("unknown timer", "плохой OnCalendar", "on_calendar")):
        code = 400
    elif "sudo отказал" in msg:
        code = 409
    return HTTPException(status_code=code, detail=msg)


@router.get("")
async def timers_list(_admin: dict = Depends(require_admin)) -> list[dict]:
    try:
        return await timers_service.status_all()
    except TimersError as e:
        raise _err(e)


@router.post("/{timer_id}/enable")
async def timer_enable(timer_id: str, _admin: dict = Depends(require_admin)) -> dict:
    try:
        return await timers_service.enable(timer_id)
    except TimersError as e:
        raise _err(e)


@router.post("/{timer_id}/disable")
async def timer_disable(timer_id: str, _admin: dict = Depends(require_admin)) -> dict:
    try:
        return await timers_service.disable(timer_id)
    except TimersError as e:
        raise _err(e)


@router.post("/{timer_id}/run")
async def timer_run(timer_id: str, _admin: dict = Depends(require_admin)) -> dict:
    try:
        return await timers_service.run_now(timer_id)
    except TimersError as e:
        raise _err(e)


@router.put("/{timer_id}/schedule")
async def timer_schedule(
    timer_id: str,
    payload: dict = Body(...),
    _admin: dict = Depends(require_admin),
) -> dict:
    try:
        return await timers_service.set_schedule(timer_id, (payload or {}).get("on_calendar", ""))
    except TimersError as e:
        raise _err(e)


@router.get("/{timer_id}/log")
async def timer_log(
    timer_id: str,
    lines: int = Query(default=100, ge=20, le=500),
    _admin: dict = Depends(require_admin),
) -> dict:
    try:
        return await timers_service.tail_log(timer_id, lines)
    except TimersError as e:
        raise _err(e)
