"""Фоновый разбор фраз: статус воркера, очередь, журнал, пауза (план 2026-10-28).

Видимость работы — по образцу домену «Затраты ИИ» (/seo/ai-usage): блок затрат в
status собирается из ai_usage.summary по сценарию newcard_phrases_miner;
«$» (cost) отдаётся только глобальному админу (can_see_cost) — как на /ai-usage.

Скоуп компании: админ компании видит только свою компанию (селектор топ-бара),
глобальный админ — фильтр по компании (None = все компании).
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, require_seo
from backend.services import ai_usage_service
from backend.services import auth_service
from backend.services import phrase_miner_service as miner

router = APIRouter(prefix="/api/phrases/miner", tags=["phrases-miner"])


async def _scope(db: AsyncSession, user: dict, selector_cid: int | None,
                  param_cid: int | None) -> tuple[int | None, bool]:
    """Скоуп компании для очереди/журнала/затрат.

    Возвращает (company_id | None = все компании, is_global).
    Не-глобальный админ: принудительно своя компания (селектор) — чужую не видит.
    Глобальный: company_id из параметра, None = все компании.
    """
    is_global = await auth_service.is_global_admin(db, user["id"])
    if is_global:
        return param_cid, True
    return selector_cid, False


def _strip(tot: dict, can_see: bool) -> dict:
    """Колонка «$» — только глобальному админу (can_see_cost), остальным скрыта."""
    d = {}
    for k, v in tot.items():
        d[k] = round(v, 2) if isinstance(v, float) else v
    if not can_see:
        d.pop("cost", None)
    return d


def _cost_block(day_rows: list[dict], day_totals: dict, model_rows: list[dict],
                can_see: bool) -> dict:
    """Блок «Затраты ИИ»: сегодня / 7 дней / 30 дней + разрез по моделям."""

    def sum_days(rows: list[dict], max_age: int) -> dict:
        tot = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
               "total_tokens": 0, "cost": 0.0, "failed": 0}
        for r in rows:
            try:
                d = date.fromisoformat(str(r.get("grp") or "")[:10])
            except Exception:
                continue
            if (date.today() - d).days >= max_age:
                continue
            for k in ("calls", "prompt_tokens", "completion_tokens", "total_tokens", "failed"):
                tot[k] += int(r.get(k) or 0)
            tot["cost"] += float(r.get("cost") or 0.0)
        return tot

    return {
        "today": _strip(sum_days(day_rows, 1), can_see),
        "week": _strip(sum_days(day_rows, 7), can_see),
        "month": _strip(day_totals or {}, can_see),
        "by_model": [_strip(dict(r), can_see) for r in (model_rows or [])],
    }


@router.get("/status")
async def miner_status(
    company_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id_from_selector: int | None = Depends(get_current_company),
):
    """Живой статус воркера + счётчики очереди + блок «Затраты ИИ»."""
    scope, is_global = await _scope(db, user, company_id_from_selector, company_id)
    base = await miner.get_status(db, company_id=scope)
    scen = miner.SCENARIO
    d30 = (date.today() - timedelta(days=29)).isoformat()
    day = await ai_usage_service.summary(db, group_by="day", scenario=scen,
                                         company_id=scope, date_from=d30, limit=60)
    model_cut = await ai_usage_service.summary(db, group_by="model", scenario=scen,
                                               company_id=scope, date_from=d30, limit=50)
    base["scenario"] = scen
    base["can_see_cost"] = is_global
    base["is_global"] = is_global
    base["company_scope"] = scope
    base["ai_usage"] = _cost_block(day.get("rows") or [], day.get("totals") or {},
                                   model_cut.get("rows") or [], is_global)
    return base


@router.get("/queue")
async def miner_queue(
    status: str | None = Query(default=None),
    company_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id_from_selector: int | None = Depends(get_current_company),
):
    """Очередь работ (пагинация, фильтр по статусу)."""
    scope, _ = await _scope(db, user, company_id_from_selector, company_id)
    return await miner.get_queue(db, status=status, company_id=scope,
                                 limit=limit, offset=offset)


@router.get("/log")
async def miner_log(
    level: str | None = Query(default=None),
    action: str | None = Query(default=None),
    company_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id_from_selector: int | None = Depends(get_current_company),
):
    """Журнал работы воркера (пагинация, фильтры по уровню/событию/компании)."""
    scope, _ = await _scope(db, user, company_id_from_selector, company_id)
    return await miner.get_log(db, level=level, action=action, company_id=scope,
                               limit=limit, offset=offset)


@router.post("/pause")
async def miner_pause(
    payload: dict | None = None,
    _user: dict = Depends(require_seo),
):
    """Пауза/запуск фонового обхода (флаг in-memory — рестарта нет)."""
    want = bool((payload or {}).get("paused"))
    miner.set_paused(want)
    return {"ok": True, "paused": want}
