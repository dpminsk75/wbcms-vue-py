"""Акции WB — HTTP-слой: календарь, номенклатура, расчёт маржи, отправка в WB.

Основной путь — чтение кэша (его наполняет воркер promotions_sync по таймеру).
`refresh=1` — разовый прогон синка (для отладки), в нём же берётся номенклатура.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user
from backend.services.prices_upload_service import PricesUploadService
from backend.services.promotions_margin_service import PromotionsMarginService
from backend.services.promotions_service import PromotionsService
from backend.services.promotions_sync_service import (
    PromotionsError,
    PromotionsSyncService,
)

router = APIRouter(prefix="/api/promotions", tags=["promotions"])

WB_DT_FMT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_DAYS_BACK = 30
DEFAULT_DAYS_FORWARD = 90


def _need_company(company_id: int | None) -> int:
    if company_id is None:
        raise HTTPException(status_code=400, detail="company_id is required")
    return company_id


def _d(value: str | None, fallback: date) -> str:
    if not value:
        return fallback.isoformat()
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return fallback.isoformat()


def _wb_range(date_from: str, date_to: str) -> tuple[str, str]:
    """Диапазон для WB API: ±1 день запаса, фильтр по МСК делаем в SQL."""
    try:
        d1 = date.fromisoformat(date_from) - timedelta(days=1)
        d2 = date.fromisoformat(date_to) + timedelta(days=1)
    except ValueError:
        today = date.today()
        d1, d2 = today - timedelta(days=1), today + timedelta(days=1)
    return d1.strftime(WB_DT_FMT), d2.strftime(WB_DT_FMT)


@router.get("/calendar")
async def promotions_calendar(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    refresh: int = Query(default=0),
    auto: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Календарь акций из кэша. refresh=1 — перезабрать из WB."""
    cid = _need_company(company_id)
    today = date.today()
    d_from = _d(date_from, today - timedelta(days=DEFAULT_DAYS_BACK))
    d_to = _d(date_to, today + timedelta(days=DEFAULT_DAYS_FORWARD))
    svc = PromotionsService(db, cid)
    sync = None
    if refresh:
        try:
            sync = await PromotionsSyncService(db, cid).sync_calendar(
                *_wb_range(d_from, d_to), all_promo=True)
        except PromotionsError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=f"WB: {e}")
    rows = await svc.calendar(d_from, d_to)
    return {
        "date_from": d_from, "date_to": d_to,
        "rows": rows,
        "count": len(rows),
        "fetched_at": await svc.fetched_at(),
        "sync": sync or {},
    }


@router.get("/quarantine")
async def promotions_quarantine(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Товары в карантине цен WB — проверка после загрузки скидок.

    Если новая цена со скидкой была меньше трети текущей, товар попал
    в карантин и продаётся по старой цене.
    """
    cid = _need_company(company_id)
    try:
        return await PricesUploadService(db, cid).quarantine()
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"WB: {e}")


@router.get("/{promo_id}")
async def promotions_one(
    promo_id: int,
    refresh: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Детали одной акции (из кэша; refresh=1 — перезабрать календарь)."""
    cid = _need_company(company_id)
    svc = PromotionsService(db, cid)
    promo = await svc.promo(promo_id)
    if not promo:
        raise HTTPException(status_code=404, detail="акция не найдена в кэше")
    if refresh:
        try:
            await PromotionsSyncService(db, cid).sync_calendar(
                *_wb_range(promo["start_date"], promo["end_date"]), all_promo=True)
        except PromotionsError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=f"WB: {e}")
        promo = await svc.promo(promo_id) or promo
    return promo


@router.get("/{promo_id}/products")
async def promotions_products(
    promo_id: int,
    in_action: int | None = Query(default=None),
    refresh: int = Query(default=0),
    auto_discount: int = Query(default=30),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Товары акции.

    Регулярная акция — номенклатура из WB (кэш; refresh=1 — перезабрать).
    Автоакция — весь наш ассортимент с текущими ценами и скидками из метода
    цен WB (wb_price_history): календарь WB товаров автоакций не отдаёт.
    """
    cid = _need_company(company_id)
    svc = PromotionsService(db, cid)
    promo = await svc.promo(promo_id)
    is_auto = bool(promo and (promo.get("promo_type") or "") == "auto")
    if is_auto:
        rows = await svc.auto_products(promo_id, auto_discount)
        return {
            "promo_id": promo_id, "promo": promo, "rows": rows,
            "count": len(rows), "is_auto": True,
            "auto_discount": auto_discount,
            "report": await svc.report_meta(promo_id),
        }
    if refresh:
        try:
            await PromotionsSyncService(db, cid).sync_products(
                promo_id, None if in_action is None else bool(in_action))
        except PromotionsError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            msg = str(e)
            if "http=422" in msg:
                raise HTTPException(
                    status_code=400,
                    detail="WB не отдаёт товары для автоакций "
                           "(nomenclatures применим только к регулярным акциям)")
            raise HTTPException(status_code=502, detail=f"WB: {msg}")
    rows = await svc.products(promo_id)
    return {
        "promo_id": promo_id,
        "promo": promo,
        "rows": rows,
        "count": len(rows),
        "is_auto": False,
    }


@router.get("/{promo_id}/report")
async def promotions_report(
    promo_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Что по отчёту WB по акции: загружен ли и когда."""
    cid = _need_company(company_id)
    meta = await PromotionsService(db, cid).report_meta(promo_id)
    return {"promo_id": promo_id, **meta}


@router.post("/{promo_id}/report/preview")
async def promotions_preview_report(
    promo_id: int,
    payload: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Превью загрузки отчёта WB — dry-run, ничего не пишем.

    Показывает: сколько товаров в файле, сколько распознано, какие артикулы
    неизвестны нашему ассортименту и что изменится по сравнению с текущим
    отчётом.
    """
    cid = _need_company(company_id)
    items = list(payload.get("items") or [])
    if not items:
        raise HTTPException(status_code=400, detail="items is required")
    return await PromotionsService(db, cid).preview_report(promo_id, items)


@router.post("/{promo_id}/report")
async def promotions_save_report(
    promo_id: int,
    payload: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Сохранить отчёт WB (выгрузка ЛК «Товары для исключения из акции»).

    Файл разбирает фронт (xlsx → json), сюда приходят готовые строки.
    """
    cid = _need_company(company_id)
    items = list(payload.get("items") or [])
    if not items:
        raise HTTPException(status_code=400, detail="items is required")
    svc = PromotionsService(db, cid)
    try:
        n = await svc.save_report(promo_id, items)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"promo_id": promo_id, "saved": n, **await svc.report_meta(promo_id)}


@router.post("/{promo_id}/analyze")
async def promotions_analyze(
    promo_id: int,
    payload: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Маржа товаров на новой цене + вердикт (рекомендуем / нет)."""
    cid = _need_company(company_id)
    svc = PromotionsService(db, cid)
    params = payload.get("params") or {}
    promo = await svc.promo(promo_id)
    is_auto = bool(promo and (promo.get("promo_type") or "") == "auto")
    rows = payload.get("rows")
    if not rows:
        # Загруженный шаблон/отчёт WB задаёт список товаров — считаем только по нему.
        rep = await svc.report_products(promo_id)
        if rep:
            rows = rep
        elif is_auto:
            # автоакция без отчёта: весь наш ассортимент из кэша цен WB
            rows = await svc.products_from_prices(
                promo_id, int(params.get("auto_discount") or 30))
        else:
            rows = await svc.products(promo_id)
    svc_margin = PromotionsMarginService(db, cid)
    result = await svc_margin.analyze(list(rows), params)
    decisions = await svc.decisions(promo_id)
    for r in result["rows"]:
        if r.get("in_action"):
            # Товар «уже в акции» — птичка стоит и не снимается.
            r["selected"] = True
            r["manual"] = False
            continue
        dec = decisions.get(int(r["nm_id"]))
        if dec:
            r["selected"] = bool(dec["selected"])
            r["manual"] = bool(dec["manual"])
        elif is_auto:
            # В автоакции помечаем только непроходящие пороги: прошедшие
            # попадают в акцию автоматически, помечать их не нужно.
            r["selected"] = not bool(r["recommend"])
            r["manual"] = False
        else:
            r["selected"] = bool(r["recommend"])
            r["manual"] = False
    result["summary"]["selected"] = sum(1 for r in result["rows"] if r["selected"])
    return result


@router.get("/{promo_id}/decisions")
async def promotions_decisions(
    promo_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    cid = _need_company(company_id)
    dec = await PromotionsService(db, cid).decisions(promo_id)
    return {"promo_id": promo_id, "rows": [
        {"nm_id": nm, "selected": v["selected"], "manual": v["manual"]}
        for nm, v in sorted(dec.items())
    ]}


@router.post("/{promo_id}/decisions")
async def promotions_save_decisions(
    promo_id: int,
    payload: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Сохранить пометки пользователя (снял рекомендацию / добавил товар)."""
    cid = _need_company(company_id)
    n = await PromotionsService(db, cid).save_decisions(
        promo_id, list(payload.get("items") or []), user_id=user.get("id"))
    return {"promo_id": promo_id, "saved": n}


@router.post("/{promo_id}/prices/prepare")
async def promotions_prices_prepare(
    promo_id: int,
    payload: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Подготовка загрузки цен и скидок (автоакции) — без отправки.

    Считает по отмеченным строкам таблицы: цена (не ниже мин. цены WB) +
    скидка, и сверяет с текущими ценами. Текущие цены из кэша wb_price_history;
    если записи старее 12 ч — догоняем живым запросом к WB (тратит токен).
    Возвращает позиции и список рисков карантина (новая цена со скидкой
    меньше трети текущей).
    """
    cid = _need_company(company_id)
    rows = list(payload.get("rows") or [])
    if not rows:
        raise HTTPException(status_code=400, detail="rows is required")
    try:
        return await PricesUploadService(db, cid).prepare(rows)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{promo_id}/prices/upload")
async def promotions_prices_upload(
    promo_id: int,
    payload: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Загрузить цены и скидки в WB (автоакции) — discounts-prices /upload/task.

    По умолчанию отмеченные с риском карантина НЕ отправляем; with_risky=1
    (подтверждение пользователя после диалога) — отправляем всё.
    Загрузка в WB асинхронная: возвращаем id задач, итог — отдельной
    проверкой GET /api/promotions/quarantine.
    """
    cid = _need_company(company_id)
    rows = list(payload.get("rows") or [])
    if not rows:
        raise HTTPException(status_code=400, detail="rows is required")
    with_risky = bool(payload.get("with_risky"))
    try:
        res = await PricesUploadService(db, cid).upload(rows, with_risky=with_risky)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"WB: {e}")
    if res.get("errors"):
        raise HTTPException(
            status_code=502,
            detail="WB не принял часть задач: " + "; ".join(res["errors"])[:300])
    return {"promo_id": promo_id, "sent": res.get("sent", 0),
            "tasks": res.get("tasks", []),
            "skipped_risky": res.get("skipped_risky", 0)}


@router.post("/{promo_id}/upload")
async def promotions_upload(
    promo_id: int,
    payload: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    company_id: int | None = Depends(get_current_company),
):
    """Добавить номенклатуру в акцию (POST WB /calendar/promotions/upload).

    Только регулярные акции: для автоакций метод WB неприменим.
    """
    cid = _need_company(company_id)
    nm_ids = [int(x) for x in (payload.get("nm_ids") or [])]
    if not nm_ids:
        raise HTTPException(status_code=400, detail="nm_ids is required")
    svc = PromotionsService(db, cid)
    promo = await svc.promo(promo_id)
    if promo and (promo.get("promo_type") or "") == "auto":
        raise HTTPException(
            status_code=400,
            detail="WB не принимает номенклатуру для автоакций (promotions/upload — "
                   "только регулярные акции). Для автоакции используйте шаблон "
                   "«Новая минимальная цена / Новая блокировка»")
    try:
        data = await PromotionsSyncService(db, cid).upload(promo_id, nm_ids)
    except PromotionsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        msg = str(e)
        if "http=422" in msg:
            raise HTTPException(
                status_code=400,
                detail="WB не принимает номенклатуру для автоакций (upload — "
                       "только регулярные акции)")
        raise HTTPException(status_code=502, detail=f"WB: {msg}")
    return {"promo_id": promo_id, "uploaded": len(nm_ids), "wb": data}
