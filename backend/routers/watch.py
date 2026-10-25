"""SEO-мониторинг `/api/seo-watch` — рабочее место менеджера (план 2026-10-23).

Watch set: ТОП-N карточек по заказам × ТОП-M приносящих заказы фраз (пороги —
компания). По этим фразам — матрица из выдачи `wb_competitor_position`: наши
позиции, новые карточки, сдвиги цен, свежесть сбора. Ручные действия менеджера:
`/requeue` (пересборка выдачи) и `/refresh` (контент ТОП-N в очередь enrich).

Гейт — require_seo (viewSeo|admin), скоуп по компании.
"""

from __future__ import annotations

import json
import traceback
from datetime import date, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, require_seo
from backend.services.watch_service import WatchService

router = APIRouter(prefix="/api/seo-watch", tags=["seo-watch"])


def _d1(default_days: int = 30) -> str:
    return (date.today() - timedelta(days=default_days)).isoformat()


def _d0() -> str:
    return date.today().isoformat()


def _fail(what: str, exc: Exception) -> HTTPException:
    """Лог трейсбека в stdout (journalctl) + короткая причина в ответе.

    Без этого 500 уходит в пустоту: uvicorn пишет трейсбек, но в шуме журнала
    его легко пропустить, а на странице — просто «500».
    """
    try:
        print(json.dumps({"seo_watch_error": what,
                          "error": f"{type(exc).__name__}: {exc}"[:600],
                          "trace": traceback.format_exc()[-2000:]},
                         ensure_ascii=False), flush=True)
    except Exception:
        pass
    return HTTPException(status_code=500,
                         detail=f"{what}: {type(exc).__name__}: {exc}"[:300])


@router.get("/summary")
async def watch_summary(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    card_nm: int = Query(default=0, ge=0),
    rank: str = Query(default="orders"),
    queries: int = Query(default=0, ge=0, le=50),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """KPI мониторинга: карточки/фразы, свежесть, наши ТОП-3/10, события."""
    svc = WatchService(db, company_id)
    try:
        return await svc.summary(date_from or _d1(), date_to or _d0(),
                                 card_nm=card_nm, rank_by=rank, queries_n=queries)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _fail("summary", exc)


@router.get("/matrix")
async def watch_matrix(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    card_nm: int = Query(default=0, ge=0),
    rank: str = Query(default="orders"),
    queries: int = Query(default=0, ge=0, le=50),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Матрица по фразам: позиции, новые карточки, сдвиги цен, свежесть.

    Фильтры панели: `card_nm` — наша карточка (0 = все наши), `rank` — ранг
    фраз (`orders`/`freq`), `queries` — ТОП-N запросов карточки (0 = порог).
    """
    svc = WatchService(db, company_id)
    try:
        return await svc.matrix(date_from or _d1(), date_to or _d0(),
                                card_nm=card_nm, rank_by=rank, queries_n=queries)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _fail("matrix", exc)


@router.get("/events")
async def watch_events(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    type: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
    card_nm: int = Query(default=0, ge=0),
    rank: str = Query(default="orders"),
    queries: int = Query(default=0, ge=0, le=50),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Лента событий: новые карточки (`type=new`) и сдвиги цен (`type=price`)."""
    svc = WatchService(db, company_id)
    try:
        return await svc.events(date_from or _d1(), date_to or _d0(), type, limit,
                                card_nm=card_nm, rank_by=rank, queries_n=queries)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _fail("events", exc)


@router.get("/phrase")
async def watch_phrase(
    phrase: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Срезы выдачи по одной фразе мониторинга (последние N дней) — раскрытие строки."""
    svc = WatchService(db, company_id)
    try:
        return await svc.phrase_detail(phrase, date_from or _d1(), date_to or _d0())
    except Exception as exc:
        raise _fail("phrase", exc)


@router.post("/requeue")
async def watch_requeue(
    payload: dict = Body(...),
    date_from: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Пометить фразы на пересборку выдачи (очередь `wb_search_phrase_queue`).

    Это та самая очередь, которую читает расширение («Поисковые фразы» в попапе).
    """
    phrases = payload.get("phrases") or []
    svc = WatchService(db, company_id)
    try:
        return await svc.requeue(phrases, user_id=_user.get("id"),
                                 date_from=date_from or _d1(),
                                 card_nm=int(payload.get("card_nm") or 0),
                                 rank_by=str(payload.get("rank") or "orders"),
                                 queries_n=int(payload.get("queries") or 0))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _fail("requeue", exc)


@router.post("/refresh")
async def watch_refresh(
    payload: dict = Body(...),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """«Обновить ТОП-N»: карточки ТОП-N последнего среза фраз → очередь enrich.

    Пропускаем только то, что полным сбором взяли сегодня; свои карточки не
    пропускаем (менеджеру нужны их бэджи/цены). Очередь — `source='watch'`,
    её забирает расширение в режиме «SEO-мониторинг».

    `phrases` — отмеченные в матрице фразы; пусто → весь watch set.
    """
    phrases = payload.get("phrases") or []
    top = int(payload.get("top") or 10)
    svc = WatchService(db, company_id)
    try:
        return await svc.refresh_top(phrases, top, date_from=date_from or _d1(),
                                     date_to=date_to or _d0(),
                                     card_nm=int(payload.get("card_nm") or 0),
                                     rank_by=str(payload.get("rank") or "orders"),
                                     queries_n=int(payload.get("queries") or 0))
    except Exception as exc:
        raise _fail("refresh", exc)


@router.post("/collect")
async def watch_collect(
    payload: dict = Body(...),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Собрать карточки SEO-мониторинга → очередь enrich (`source='watch'`).

    mode:
    - `changed` — новые в выдаче и сдвиги цены (события матрицы);
    - `stale`   — карточки, чей контент старше `watch_card_stale_days`;
    - `missing` — только карточки без записи в `wb_competitor_details` вовсе.

    `phrases` — отмеченные в матрице фразы: для `stale`/`missing` пул собирается
    только по ним. `top` — глубина захода (10/20/40).
    """
    mode = str(payload.get("mode") or "")
    phrases = payload.get("phrases") or []
    top = int(payload.get("top") or 40)
    svc = WatchService(db, company_id)
    try:
        return await svc.collect_cards(date_from or _d1(), date_to or _d0(),
                                       mode, phrases=phrases, top=top,
                                       card_nm=int(payload.get("card_nm") or 0),
                                       rank_by=str(payload.get("rank") or "orders"),
                                       queries_n=int(payload.get("queries") or 0))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _fail("collect", exc)