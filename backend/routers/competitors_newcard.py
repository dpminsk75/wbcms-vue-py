"""Конкуренты (новый товар): /api/competitors/new-cards (§9, §15 Ш2/Ш4/Ш5 плана 2026-10-20).

Гейт — require_seo (viewSeo|admin), company-scope через get_current_company.
Префикс вложен в /api/competitors, но роут статический: GET /api/competitors/{nm}
не существует, все {nm}-роуты competitor.py двухсегментные — конфликта нет.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

import json

from backend.database import get_db
from backend.deps import get_current_company, require_seo
from backend.services.competitors_newcard_service import CompetitorsNewcardService

router = APIRouter(prefix="/api/competitors/new-cards", tags=["competitors-new-cards"])
# «Собранные карточки» — отдельный префикс, чтобы не ловить `/{nm_id}` (см. §9 плана).
captured_router = APIRouter(prefix="/api/competitors/captured", tags=["competitors-captured"])
# §16: подбор конкурентов и массовая привязка.
pick_router = APIRouter(prefix="/api/competitors/pick", tags=["competitors-pick"])
# §17.2: повторный обход устаревших карточек конкурентов.
refresh_router = APIRouter(prefix="/api/competitors/refresh", tags=["competitors-refresh"])


async def _svc(db: AsyncSession, company_id: int | None, nm_id: int) -> CompetitorsNewcardService:
    svc = CompetitorsNewcardService(db, company_id)
    if not await svc.owns_card(nm_id):
        raise HTTPException(status_code=404, detail="card not found")
    return svc


@router.get("")
async def competitors_new_cards(
    q: str = Query(default=""),
    include_all: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Карточки «в работе» (есть запросы или конкуренты) + счётчики.

    `include_all=1` — все активные карточки компании; `q` — маска nmID/vendorCode/title.
    """
    return await CompetitorsNewcardService(db, company_id).list_cards(q, limit, include_all)


@router.get("/{nm_id}")
async def competitors_new_card(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = await _svc(db, company_id, nm_id)
    data = await svc.card_detail(nm_id)
    if not data:
        raise HTTPException(status_code=404, detail="card not found")
    return data


# ---------- поисковые запросы (широкие, для сбора конкурентов) ----------

@router.get("/{nm_id}/queries")
async def competitors_queries(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = await _svc(db, company_id, nm_id)
    return await svc.list_queries(nm_id)


@router.get("/{nm_id}/queries/suggest")
async def competitors_queries_suggest(
    nm_id: int = Path(..., ge=1),
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Подсказки из wb_sr_report_item_phrases по всей базе (фильтр по subject_name карточки)."""
    svc = await _svc(db, company_id, nm_id)
    return await svc.suggest_queries(nm_id, q)


@router.post("/{nm_id}/queries")
async def competitors_queries_add(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = await _svc(db, company_id, nm_id)
    try:
        return await svc.add_query(nm_id, str((payload or {}).get("phrase") or ""), user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{nm_id}/queries/reset")
async def competitors_queries_reset(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Сбросить очередь запросов карточки — расширение пересоберёт их заново."""
    svc = await _svc(db, company_id, nm_id)
    return {"reset": await svc.reset_queries(nm_id)}


@router.delete("/{nm_id}/queries/{qid}")
async def competitors_queries_remove(
    nm_id: int = Path(..., ge=1),
    qid: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = await _svc(db, company_id, nm_id)
    if not await svc.remove_query(nm_id, qid):
        raise HTTPException(status_code=404, detail="query not found")
    return {"ok": True}


# ---------- конкуренты ----------

@router.get("/{nm_id}/competitors")
async def competitors_list(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = await _svc(db, company_id, nm_id)
    return await svc.list_competitors(nm_id)


@router.get("/{nm_id}/competitors/{cid}/details")
async def competitors_details(
    nm_id: int = Path(..., ge=1),
    cid: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Полная карточка привязанного конкурента: фото, описание, характеристики, история цен."""
    svc = await _svc(db, company_id, nm_id)
    if not await svc.has_competitor(nm_id, cid):
        raise HTTPException(status_code=404, detail="competitor not found")
    data = await svc.details(cid, our_nm=nm_id)
    if not data:
        raise HTTPException(status_code=404, detail="details not collected")
    return data


@router.post("/{nm_id}/competitors")
async def competitors_add(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Ручное добавление: {"nm_ids": [123, 456]} → wb_competitor_cards(source='manual') + очередь."""
    svc = await _svc(db, company_id, nm_id)
    try:
        return await svc.add_competitors(nm_id, (payload or {}).get("nm_ids") or [], user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{nm_id}/competitors/from-card")
async def competitors_from_card(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Скопировать конкурентов с другой нашей карточки: {"source_nm_id": N} → source='sibling'."""
    svc = await _svc(db, company_id, nm_id)
    try:
        return await svc.copy_from_card(nm_id, int((payload or {}).get("source_nm_id") or 0), user["id"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{nm_id}/competitors/{cid}")
async def competitors_detach(
    nm_id: int = Path(..., ge=1),
    cid: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Отвязать конкурента от нашей карточки (контент и история остаются)."""
    svc = await _svc(db, company_id, nm_id)
    try:
        ok = await svc.detach_competitor(nm_id, cid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=404, detail="competitor not found")
    return {"ok": True, "nm_id": nm_id, "competitor_nm_id": cid}


# ---------- Ш11: фразы из описаний конкурентов + генерация ----------

@router.get("/{nm_id}/phrases")
async def competitors_phrases(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = await _svc(db, company_id, nm_id)
    return await svc.list_phrases(nm_id)


@router.post("/{nm_id}/phrases/analyze")
async def competitors_phrases_analyze(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """LLM: вытащить фразы из описаний привязанных конкурентов + статистика нашей базы.

    Синхронно (один вызов модели, до ~60 с): фронт показывает спиннер.
    `run_id` (uuid клиента) — для прогресса: какая модель и попытка.
    """
    svc = await _svc(db, company_id, nm_id)
    run_id = str((payload or {}).get("run_id") or "").strip()[:64] or None
    try:
        return await svc.analyze_phrases(nm_id, run_id, user_id=user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{nm_id}/phrases/merge")
async def competitors_phrases_merge(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Только слияние формулировок в группы — без повторного разбора описаний.

    Сырьё берётся из wb_competitor_phrase_comp (уже разобранные конкуренты),
    поэтому 1–3 вызова модели вместо 14. Рабочий список перезаписывается.
    """
    svc = await _svc(db, company_id, nm_id)
    run_id = str((payload or {}).get("run_id") or "").strip()[:64] or None
    try:
        return await svc.merge_phrases(nm_id, run_id, user_id=user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{nm_id}/phrases")
async def competitors_phrases_add(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = await _svc(db, company_id, nm_id)
    try:
        return await svc.add_phrase(nm_id, str((payload or {}).get("phrase") or ""), user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{nm_id}/phrases/select")
async def competitors_phrases_select(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """{"phrases": ["..."], "selected": true|false} — отметить набор для генерации."""
    svc = await _svc(db, company_id, nm_id)
    try:
        return await svc.select_phrases(nm_id, (payload or {}).get("phrases") or [],
                                        bool((payload or {}).get("selected", True)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{nm_id}/phrases/{pid}")
async def competitors_phrases_remove(
    nm_id: int = Path(..., ge=1),
    pid: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = await _svc(db, company_id, nm_id)
    if not await svc.delete_phrase(nm_id, pid):
        raise HTTPException(status_code=404, detail="phrase not found")
    return {"ok": True}


@router.post("/{nm_id}/generate")
async def competitors_generate(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Title + description по выбранным фразам. Результат — в wb_competitor_summary."""
    svc = await _svc(db, company_id, nm_id)
    run_id = str((payload or {}).get("run_id") or "").strip()[:64] or None
    try:
        return await svc.generate_description(nm_id, (payload or {}).get("phrases"), run_id,
                                              user_id=user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{nm_id}/runs/{run_id}")
async def competitors_run_status(
    nm_id: int = Path(..., ge=1),
    run_id: str = Path(..., min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Прогресс AI-вызова: статус, модель, попытка (для модалок)."""
    svc = await _svc(db, company_id, nm_id)
    row = await svc.get_run_safe(nm_id, run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return row


# ---------- §16: подбор конкурентов и массовая привязка ----------

@pick_router.get("/cards")
async def pick_cards(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Наши карточки для выбора источника/цели: nmID, vendorCode, title + счётчики."""
    return await CompetitorsNewcardService(db, company_id).pick_cards(q, limit)


@pick_router.get("/candidates")
async def pick_candidates(
    source_nm_ids: str = Query(default=""),
    mode: str = Query(default="recommend"),
    q: str = Query(default=""),
    only_content: bool = Query(default=False),
    only_recommended: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="relevance"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Пул кандидатов: recommend=A∪B (B — рекомендации конкурентов A), competitors=A, captured=вся база компании."""
    svc = CompetitorsNewcardService(db, company_id)
    try:
        return await svc.pick_candidates(
            source_nm_ids, mode, q, only_content, only_recommended, limit, offset, sort,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@pick_router.get("/candidates/{nm_id}/details")
async def pick_candidate_details(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Попап конкурента из пула: capture, привязка или рекомендация (B)."""
    data = await CompetitorsNewcardService(db, company_id).pick_details(nm_id)
    if not data:
        raise HTTPException(status_code=404, detail="details not collected")
    return data


@pick_router.post("/attach")
async def pick_attach(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Массовая привязка captured-кандидатов к нашим карточкам (идемпотентно)."""
    body = payload or {}
    svc = CompetitorsNewcardService(db, company_id)
    try:
        return await svc.bulk_attach(
            body.get("nm_ids"), body.get("target_nm_ids"),
            user["id"], str(body.get("mode") or "recommend"),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------- §8.5/§11.3: «Собранные карточки» (capture) ----------

@captured_router.get("")
async def captured_list(
    q: str = Query(default=""),
    include_hidden: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="collected_at"),
    direction: str = Query(default="desc"),
    scope: str = Query(default="captured"),
    collected_from: str = Query(default=""),
    collected_to: str = Query(default=""),
    first_seen_from: str = Query(default=""),
    first_seen_to: str = Query(default=""),
    content: str = Query(default=""),
    phrase: str = Query(default=""),
    attached: str = Query(default=""),
    source: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Что расширение собрало в общую базу. Ничего не привязано — только видимость компании.

    Фильтры/сортировка/пагинация — §19.6:
    - `scope=captured` (по умолчанию) — реестр нашей компании; `scope=all_details` —
      общий кэш контента (видно и собранное другими компаниями);
    - `include_hidden=1` — показать карточки, исключённые из сбора;
    - `sort`/`direction` — серверная сортировка (whitelist);
    - `collected_from/to`, `first_seen_from/to` — даты (YYYY-MM-DD);
    - `content` — has_desc|no_desc|has_chars|no_chars; `attached` — yes|no;
    - `phrase` — по позициям выдачи и формулировкам конкурентов; `source` — cards.source.
    """
    return await CompetitorsNewcardService(db, company_id).list_captured(
        q, include_hidden, limit, offset,
        sort=sort, direction=direction, scope=scope,
        collected_from=collected_from, collected_to=collected_to,
        first_seen_from=first_seen_from, first_seen_to=first_seen_to,
        content=content, phrase=phrase, attached=attached, source=source,
    )


@captured_router.get("/{nm_id}/history")
async def captured_history(
    nm_id: int = Path(..., ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Снимки контента по content_hash (append-only, дедуп)."""
    return await CompetitorsNewcardService(db, company_id).history(nm_id, limit)


@captured_router.get("/{nm_id}/details")
async def captured_details(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Полная карточка собранного конкурента для попапа.

    Лестница источников (все company-scoped): контент (wb_competitor_details,
    видимый через wb_competitor_capture) → запись выдачи (wb_competitor_cards) →
    строка выдачи (wb_competitor_position). Нет полного сбора — отдаём частичные
    данные с флагом found != "details": фронт показывает кнопку «Собрать в
    расширении» вместо 404.
    """
    svc = CompetitorsNewcardService(db, company_id)
    data = await svc.details(nm_id) if await svc.capture_visible(nm_id) else None
    if data:
        data["found"] = "details"
        return data
    for found, row, extra in (
        ("cards", await svc.cards_fallback(nm_id), ("phrase",)),
        ("position", await svc.positions_fallback(nm_id), ("phrase", "position", "position_api")),
    ):
        if not row:
            continue
        bad = row.get("badges")
        if isinstance(bad, str):
            try:
                bad = json.loads(bad)
            except Exception:
                bad = []
        img = row.get("image_url") or None
        out = {
            "found": found,
            "nm_id": nm_id,
            "title": row.get("title") or "",
            "description": "",
            "brand": row.get("brand") or "",
            "seller": row.get("seller") or "",
            "subject_name": None,
            "photo": img,
            "preview_image": img,
            "images": [img] if img else [],
            "characteristics": [],
            "badges": bad if isinstance(bad, list) else [],
            "price": row.get("price"),
            "old_price": row.get("old_price"),
            "rating": row.get("rating"),
            "feedbacks": row.get("feedbacks"),
            "questions": None,
            "sold_out": 1 if row.get("sold_out") else 0,
            "url": f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
            "collected_at": row.get("collected_at"),
            "first_collected_at": None,
            "full_collected_at": None,
            "source_nm_id": row.get("source_nm_id"),
            "slice_stamp": row.get("slice_stamp") or "",
        }
        for k in extra:
            out[k] = row.get(k)
        return out
    raise HTTPException(status_code=404, detail="card not found")


@captured_router.post("/{nm_id}/attach")
async def captured_attach(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Привязать собранную карточку к нашей: `wb_competitor_cards(source='capture')`."""
    svc = CompetitorsNewcardService(db, company_id)
    try:
        return await svc.attach(nm_id, int((payload or {}).get("source_nm_id") or 0), user["id"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@captured_router.post("/{nm_id}/detach")
async def captured_detach(
    nm_id: int = Path(..., ge=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Отвязать пару (только `source='capture'`), контент и история остаются."""
    svc = CompetitorsNewcardService(db, company_id)
    try:
        return await svc.detach(nm_id, int((payload or {}).get("source_nm_id") or 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@captured_router.post("/{nm_id}/hide")
async def captured_hide(
    nm_id: int = Path(..., ge=1),
    hidden: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """Исключить карточку из сбора / вернуть (`?hidden=0` — вернуть).

    Исключение per-company: карточка перестаёт собираться (расширение её не
    открывает и не скроллит, сервер не обновляет контент). Вернуть — только здесь.
    """
    svc = CompetitorsNewcardService(db, company_id)
    try:
        return await svc.hide(nm_id, hidden)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------- §17.2: повторный обход устаревших конкурентов ----------

@refresh_router.get("")
async def refresh_list(
    days: int = Query(default=30, ge=1, le=3650),
    q: str = Query(default=""),
    only_captured: bool = Query(default=False),
    include_hidden: bool = Query(default=False),
    source_nm_id: int | None = Query(default=None, ge=1),
    status: str = Query(default=""),
    limit: int = Query(default=300, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    svc = CompetitorsNewcardService(db, company_id)
    try:
        return await svc.list_refresh(
            days=days, q=q, only_captured=only_captured, include_hidden=include_hidden,
            source_nm_id=source_nm_id, status=status, limit=limit, offset=offset,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@refresh_router.post("/assign")
async def refresh_assign(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    raw = (payload or {}).get("nm_ids") or []
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="nm_ids должен быть массивом")
    try:
        days = int((payload or {}).get("days") or 30)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad days")
    svc = CompetitorsNewcardService(db, company_id)
    try:
        return await svc.assign_refresh(raw, days=days, user_id=user["id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@refresh_router.post("/restore")
async def refresh_restore(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
    company_id: int | None = Depends(get_current_company),
):
    """«Появилась снова»: ручная разблокировка карточек со статусом gone"""
    raw = (payload or {}).get("nm_ids") or []
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="nm_ids должен быть массивом")
    svc = CompetitorsNewcardService(db, company_id)
    try:
        return await svc.restore_gone(raw, user_id=user["id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
