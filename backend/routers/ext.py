"""Расширение-коллектор (§10 md): порт wb_extension/server.py (Flask :8765) на FastAPI.

Логика перенесена 1в1, включая правило 24ч в result и «не затирать recs пустыми».
Отличия от Flask (все со скоупом — без него токен бессмысленен):
- гейт — Bearer ext-токена (require_ext_token), компанию берём из токена, JWT не принимаем;
- wb_enrich_queue фильтруем по company_id (миграция 20260925); старые строки с NULL
  забираются через next (claim проставляет компанию) и видны в status;
- wb_seo_target без миграции — скоуп через nmID IN (SELECT nmID FROM wbcards WHERE company_id=...);
- wb_competitor_cards без колонки — скоуп через source-карточку (как в CompetitorService);
- position_bulk: чужой source отбрасываем со счётчиком skipped (403 не шлём — поллер);
- search_next с чужим nm_id отдаёт {nm_id: None} (поллер, не человек);
- source=compquery — очередь wb_competitor_query; результаты пишутся в wb_competitor_cards
  с source='search' (default), query_phrase и position;
- result UPDATE писан явными параметрами: Flask-форма `SET x=VALUES(x)` вне INSERT
  в MySQL не работает — семантика та же;
- position collected_at NULL → CURDATE() (колонка DATE NOT NULL, Flask падал бы 500);
- diagnose хранится в backend/runtime/diag/{company_id}/ (как ai.log), а не в /tmp;
- троттлинга 429 на поллинге НЕТ (next/status дергаются каждые 0.5-2с) — last_used_at
  трогаем не чаще раза в минуту (см. deps.require_ext_token).
"""

import asyncio
import json
import pathlib
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_ext_token, require_seo
from backend.services import ext_service, capture_service, shelves_service, search_raw_service

router = APIRouter(prefix="/api/ext", tags=["ext"])
admin_router = APIRouter(prefix="/api/companies/{company_id}/ext-tokens", tags=["ext-tokens"])
diag_admin_router = APIRouter(prefix="/api/companies/{company_id}/ext-diag", tags=["ext-diag"])
dl_router = APIRouter(prefix="/api/companies/{company_id}/ext-download", tags=["ext-tokens"])
cat_router = APIRouter(prefix="/api/companies/{company_id}/ext-filters", tags=["ext-tokens"])

OWNED_CARDS = "SELECT nmID FROM wbcards WHERE company_id=:cid"


async def _owns_card(db: AsyncSession, cid: int, nm_id: int) -> bool:
    r = (await db.execute(text(f"SELECT 1 FROM wbcards WHERE nmID=:n AND company_id=:c LIMIT 1"),
                          {"n": nm_id, "c": cid})).first()
    return r is not None


# MySQL: 1213 — deadlock, 1205 — превышено ожидание блокировки.
# Расширение шлёт 4 канала почти одновременно, а «позиции» (DOM) и «сырой
# каталог» (JSON) пишут одни и те же строки wb_competitor_position в разном
# порядке — два запроса могут упереться в deadlock. Тогда повторяем попытку.
_DEADLOCK_CODES = (1213, 1205)


async def _with_db_retry(db: AsyncSession, fn, tries: int = 3):
    """Выполнить fn, при deadlock/lock-timeout MySQL — повторить (до tries раз)."""
    for attempt in range(tries):
        try:
            return await fn()
        except OperationalError as e:
            code = (getattr(e, "orig", None).args or [None])[0]
            if code not in _DEADLOCK_CODES or attempt + 1 >= tries:
                raise
            try:
                await db.rollback()
            except Exception:
                pass
            await asyncio.sleep(0.4 * (attempt + 1))


def _diag_dir(cid: int) -> pathlib.Path:
    d = pathlib.Path(__file__).resolve().parents[1] / "runtime" / "diag" / str(cid)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------- выдача/отзыв (JWT: viewSeo + членство в компании из пути) ----------

@admin_router.get("")
async def ext_tokens_list(
    company_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    """Список токенов (сырого тут нет — он показывается один раз при создании)."""
    return await ext_service.list_tokens(db, company_id)


@admin_router.post("")
async def ext_tokens_create(
    company_id: int = Path(..., ge=1),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    """Выдать токен. Ответ содержит `token` — показать и больше нигде не хранить."""
    return await ext_service.create_token(db, company_id, (payload or {}).get("name") or "", user["id"])


@admin_router.delete("/{token_id}")
async def ext_tokens_revoke(
    company_id: int = Path(..., ge=1),
    token_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    if not await ext_service.revoke_token(db, company_id, token_id):
        raise HTTPException(status_code=404, detail="token not found")
    return {"ok": True}


# ---------- enrich: статус/очередь/результат (порт server.py) ----------

@router.get("/whoami")
async def ext_whoami(
    ext: dict = Depends(require_ext_token),
):
    """Кто мы: имя токена и компания — попап показывает, каким токеном работаем."""
    return {
        "id": ext.get("id"),
        "name": ext.get("name") or "",
        "company_id": ext.get("company_id"),
    }


@router.get("/status")
async def ext_status(
    nm_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    cid = int(ext["company_id"])
    if nm_id:
        if not await _owns_card(db, cid, nm_id):
            raise HTTPException(status_code=403, detail="foreign source_nm_id")
        rows = (await db.execute(text(f"""
            SELECT q.status, COUNT(DISTINCT q.id) as cnt FROM wb_enrich_queue q
            JOIN wb_competitor_cards c ON c.nm_id=q.nm_id AND c.source_nm_id=:nm
            WHERE (q.company_id=:cid OR q.company_id IS NULL OR q.status='need_update')
              AND c.source_nm_id IN ({OWNED_CARDS.replace(':cid', ':cid2')})
            GROUP BY q.status
        """), {"nm": nm_id, "cid": cid, "cid2": cid})).mappings().all()
    else:
        rows = (await db.execute(text("""
            SELECT status, COUNT(*) as cnt FROM wb_enrich_queue
            WHERE company_id=:cid OR company_id IS NULL OR status='need_update'
            GROUP BY status
        """), {"cid": cid})).mappings().all()
    counts = {r["status"]: r["cnt"] for r in rows}
    return {"total": sum(counts.values()), **counts}


@router.post("/seed")
async def ext_seed(
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """POST {"source_nm_id": N} — заполнить очередь из wb_competitor_cards (24ч-правило как во Flask)."""
    cid = int(ext["company_id"])
    source = (payload or {}).get("source_nm_id")
    try:
        source = int(source) if source else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad source_nm_id")
    if source:
        if not await _owns_card(db, cid, source):
            raise HTTPException(status_code=403, detail="foreign source_nm_id")
        # Только карточки, которых ещё нет в очереди (то есть новые). Собранные
        # раньше не возвращаем в pending автоматически: обновление назначается
        # руками (режим «Обновление» / need_update), а ожившее — кнопкой
        # «Сброс ошибок / зависших». Раньше тут стоял TTL 24 ч и перевод
        # done->pending — из-за этого «Обработано» таяло, а очередь пухла.
        r = await db.execute(text(f"""
            INSERT INTO wb_enrich_queue (nm_id, company_id)
            SELECT DISTINCT nm_id, :cid FROM wb_competitor_cards
            WHERE source_nm_id=:s
              AND nm_id > 0
              AND nm_id NOT IN (SELECT nm_id FROM wb_enrich_queue)
            ON DUPLICATE KEY UPDATE
              company_id=IF(company_id IS NULL, :cid, company_id)
        """), {"s": source, "cid": cid})
    else:
        # То же для всех наших карточек-источников (без TTL и без перевода статусов)
        r = await db.execute(text(f"""
            INSERT INTO wb_enrich_queue (nm_id, company_id)
            SELECT DISTINCT nm_id, :cid FROM wb_competitor_cards
            WHERE source_nm_id IN ({OWNED_CARDS.replace(':cid', ':cid2')})
              AND nm_id > 0
              AND nm_id NOT IN (SELECT nm_id FROM wb_enrich_queue)
            ON DUPLICATE KEY UPDATE
              company_id=IF(company_id IS NULL, :cid, company_id)
        """), {"cid": cid, "cid2": cid})
    await db.commit()
    return {"added": r.rowcount}


@router.get("/next")
async def ext_next(
    nm_id: int | None = Query(default=None, ge=1, alias="nm_id"),
    mode: str = Query(default="new"),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Расширение забирает следующий nmID; claim проставляет компанию (старые NULL-строки).

    `mode`:
    - `new` (по умолчанию) — только pending, как раньше;
    - `refresh` — только need_update;
    - `all` — pending, затем need_update.
    """
    cid = int(ext["company_id"])
    mode = (mode or "new").strip().lower()
    if mode not in ("new", "refresh", "all"):
        mode = "new"
    # зависший processing: расширение могли закрыть посреди сбора — снимаем в
    # pending (тот же 30-минутный reset, что у wb_competitor_query и wb_seo_target).
    # claimed_at=NULL = claim до миграции/старым кодом — тоже считается зависшим.
    # Скоуп — только свой company_id: чужие строки поднимает тот, кто их клал.
    # need_update не трогаем — это флаг «контент устарел», его отдаём как есть.
    await db.execute(text("""
        UPDATE wb_enrich_queue SET status='pending', claimed_at=NULL
        WHERE status='processing'
          AND company_id=:cid
          AND (claimed_at IS NULL OR claimed_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE))
    """), {"cid": cid})
    await db.commit()
    if mode == "new":
        cond = "q.status='pending' AND (q.company_id=:cid OR q.company_id IS NULL)"
        order = "q.id"
    elif mode == "refresh":
        cond = "q.status='need_update'"
        order = "q.id"
    else:
        cond = ("((q.status='pending' AND (q.company_id=:cid OR q.company_id IS NULL))"
                " OR q.status='need_update')")
        order = "CASE WHEN q.status='pending' THEN 0 ELSE 1 END, q.id"
    if nm_id:
        if not await _owns_card(db, cid, nm_id):
            return {"nm_id": None}
        row = (await db.execute(text(f"""
            SELECT q.id, q.nm_id FROM wb_enrich_queue q
            JOIN wb_competitor_cards c ON c.nm_id=q.nm_id AND c.source_nm_id=:nm
            WHERE {cond}
              AND c.source_nm_id IN ({OWNED_CARDS.replace(':cid', ':cid2')})
            GROUP BY q.id, q.nm_id, q.status ORDER BY {order} LIMIT 1
        """), {"nm": nm_id, "cid": cid, "cid2": cid})).mappings().first()
    else:
        row = (await db.execute(text(f"""
            SELECT q.id, q.nm_id FROM wb_enrich_queue q
            WHERE {cond}
            ORDER BY {order} LIMIT 1
        """), {"cid": cid})).mappings().first()
    if not row:
        return {"nm_id": None}
    await db.execute(text("""
        UPDATE wb_enrich_queue
        SET status='processing', company_id=:cid, claimed_at=NOW()
        WHERE id=:i
          AND (status='need_update'
               OR (status='pending' AND (company_id=:cid OR company_id IS NULL)))
    """), {"cid": cid, "i": row["id"]})
    await db.commit()
    return {"queue_id": row["id"], "nm_id": row["nm_id"]}


@router.post("/result")
async def ext_result(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Результат обогащения: правило 24ч + «не затирать recs пустыми» (порт 1в1)."""
    cid = int(ext["company_id"])
    uid = ext.get("created_by")
    nm_id = (payload or {}).get("nm_id")
    try:
        nm_id = int(nm_id) if nm_id else 0
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad nm_id")
    if not nm_id:
        raise HTTPException(status_code=400, detail="nm_id required")
    owned = (await db.execute(text("""
        SELECT 1 FROM wb_enrich_queue WHERE nm_id=:n AND (company_id=:c OR company_id IS NULL) LIMIT 1
    """), {"n": nm_id, "c": cid})).first()
    if not owned:
        chk = (await db.execute(text(f"""
            SELECT 1 FROM wb_competitor_cards
            WHERE nm_id=:n AND source_nm_id IN ({OWNED_CARDS.replace(':cid', ':c2')}) LIMIT 1
        """), {"n": nm_id, "c2": cid})).first()
        if not chk:
            raise HTTPException(status_code=403, detail="foreign nm_id")
    existing = (await db.execute(text("""
        SELECT id, recommendations, collected_at, full_collected_at
        FROM wb_competitor_details WHERE nm_id=:n
    """), {"n": nm_id})).mappings().first()
    new_recs = json.dumps(payload.get("recommendations") or [], ensure_ascii=False)
    new_chars = json.dumps(payload.get("characteristics") or [], ensure_ascii=False)
    new_badges = json.dumps(payload.get("badges") or [], ensure_ascii=False)
    is_full = 1 if (str(payload.get("description") or "").strip() and payload.get("characteristics")) else 0
    params = {
        "n": nm_id, "t": payload.get("title", ""), "d": payload.get("description", ""),
        "u": payload.get("url", ""), "b": payload.get("brand", ""), "s": payload.get("seller", ""),
        "p": capture_service._to_int(payload.get("price")),
        "o": capture_service._to_int(payload.get("old_price")),
        "img": json.dumps(payload.get("images") or [], ensure_ascii=False),
        "chars": new_chars, "subj": str(payload.get("subject_name") or "")[:255],
        "rate": capture_service._to_float(payload.get("rating")),
        "fb": capture_service._to_int(payload.get("feedbacks")),
        "q": capture_service._to_int(payload.get("questions")),
        "bg": new_badges, "full": is_full,
        "so": 1 if (payload or {}).get("sold_out") else 0,
        "cid": cid, "uid": uid,
    }
    if existing:
        age_h = 25.0
        # Свежесть полного сбора — по full_collected_at (пассивное наблюдение его не двигает).
        ref = existing["full_collected_at"] or existing["collected_at"]
        try:
            age_h = (datetime.now() - ref).total_seconds() / 3600
        except TypeError:
            pass
        if age_h < 24:
            final_recs = existing["recommendations"] if (not payload.get("recommendations") and existing["recommendations"]) else new_recs
            await db.execute(text("""
                UPDATE wb_competitor_details SET
                  title=:t, description=:d, recommendations=:r, url=:u,
                  brand=:b, seller=:s, price=:p, old_price=:o,
                  images=IF(:img='[]', images, :img), collected_at=NOW(),
                  characteristics=IF(:chars='[]', characteristics, :chars),
                  subject_name=IF(:subj='', subject_name, :subj),
                  rating=IF(:rate IS NULL, rating, :rate),
                  feedbacks=IF(:fb IS NULL, feedbacks, :fb),
                  questions=IF(:q IS NULL, questions, :q),
                  badges=IF(:bg='[]', badges, :bg),
                  sold_out=:so,
                  full_collected_at=IF(:full=1, NOW(), full_collected_at),
                  captured_company_id=COALESCE(captured_company_id, :cid),
                  captured_by=COALESCE(captured_by, :uid)
                WHERE nm_id=:n
            """), {**params, "r": final_recs})
        else:
            # было REPLACE INTO: терялись first_collected_at/captured_* — теперь UPDATE
            await db.execute(text("""
                UPDATE wb_competitor_details SET
                  title=:t, description=:d, recommendations=:r, url=:u,
                  brand=:b, seller=:s, price=:p, old_price=:o,
                  images=IF(:img='[]', images, :img), collected_at=NOW(),
                  characteristics=IF(:chars='[]', characteristics, :chars),
                  subject_name=IF(:subj='', subject_name, :subj),
                  rating=IF(:rate IS NULL, rating, :rate),
                  feedbacks=IF(:fb IS NULL, feedbacks, :fb),
                  questions=IF(:q IS NULL, questions, :q),
                  badges=IF(:bg='[]', badges, :bg),
                  sold_out=:so,
                  full_collected_at=IF(:full=1, NOW(), full_collected_at),
                  captured_company_id=COALESCE(captured_company_id, :cid),
                  captured_by=COALESCE(captured_by, :uid)
                WHERE nm_id=:n
            """), {**params, "r": new_recs})
    else:
        await db.execute(text("""
            INSERT INTO wb_competitor_details
              (nm_id, title, description, recommendations, url, brand, seller, price, old_price, images,
               characteristics, subject_name, rating, feedbacks, questions, badges, sold_out,
               first_collected_at, full_collected_at, captured_company_id, captured_by)
            VALUES (:n, :t, :d, :nr, :u, :b, :s, :p, :o, :img, :chars, :subj, :rate, :fb, :q, :bg, :so,
                    NOW(), IF(:full=1, NOW(), NULL), :cid, :uid)
        """), {**params, "nr": new_recs})
    # История: снимок при смене content_hash (source='enrich', как в capture_service).
    cur = (await db.execute(text("""
        SELECT title, description, characteristics, brand, seller, price, old_price, images
        FROM wb_competitor_details WHERE nm_id=:n LIMIT 1
    """), {"n": nm_id})).mappings().first()
    if cur:
        chars_raw = cur["characteristics"]
        if not isinstance(chars_raw, str):
            chars_raw = json.dumps(chars_raw or [], ensure_ascii=False)
        h = capture_service.content_hash(
            cur["title"] or "", cur["description"] or "", chars_raw,
            cur["price"] or "", cur["old_price"] or "")
        last = (await db.execute(text("""
            SELECT content_hash FROM wb_competitor_details_history
            WHERE nm_id=:n ORDER BY id DESC LIMIT 1
        """), {"n": nm_id})).first()
        if not last or last[0] != h:
            await db.execute(text("""
                INSERT INTO wb_competitor_details_history
                  (nm_id, title, description, characteristics, brand, seller, price, old_price,
                   images, content_hash, captured_company_id, captured_by, source)
                VALUES (:n, :t, :d, :ch, :b, :s, :p, :o, :img, :h, :cid, :uid, 'enrich')
            """), {"n": nm_id, "t": cur["title"], "d": cur["description"], "ch": chars_raw,
                   "b": cur["brand"] or "", "s": cur["seller"] or "", "p": cur["price"] or "",
                   "o": cur["old_price"] or "", "img": cur["images"] or "", "h": h,
                   "cid": cid, "uid": uid})
    # Очередь: контент общий кэш — статус закрываем, но владельца (company_id) НЕ перебиваем:
    # строка одна на nm_id (uq_nm_id), иначе компания-владелец теряла бы свою очередь.
    await db.execute(text("""
        UPDATE wb_enrich_queue SET status='done', processed_at=NOW(),
          company_id=COALESCE(company_id, :c)
        WHERE nm_id=:n
    """), {"n": nm_id, "c": cid})
    await db.commit()
    return {"ok": True}


@router.post("/capture")
async def ext_capture(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Коллектор «текущей страницы» (§8 md): контент конкурента без привязок.

    В отличие от /result пишет, даже если nm не в очереди и не в наших конкурентах:
    details + capture-видимость + снимок истории. Своя карточка → skip own_card,
    свежее 24 ч → skip fresh (force обходит оба ограничения, allow_own — только своё).
    """
    try:
        return await capture_service.capture(
            db, int(ext["company_id"]), ext.get("created_by"), payload or {}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/error")
async def ext_error(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    cid = int(ext["company_id"])
    try:
        nm_id = int((payload or {}).get("nm_id") or 0)
    except (TypeError, ValueError):
        nm_id = 0
    # «Карточки нет на WB»: WB отдаёт error404 / content404, обогащение такой сбор
    # не пройдёт никогда. Ставим 'gone' вместо 'error': /next не выдаёт gone в
    # обновление, reset_enrich не поднимает — пока человек не проверит кнопку
    # «Появилась снова» (reset_enrich include_gone=1).
    if str((payload or {}).get("reason") or "") == "not_found":
        await db.execute(text("""
            UPDATE wb_enrich_queue SET status='gone', not_found_at=NOW(),
              error_msg=:m, company_id=COALESCE(company_id, :c)
            WHERE nm_id=:n AND (company_id=:c OR company_id IS NULL)
        """), {"m": str((payload or {}).get("error", "карточка не найдена на WB"))[:500],
               "n": nm_id, "c": cid})
        await db.commit()
        return {"ok": True}
    await db.execute(text("""
        UPDATE wb_enrich_queue SET status='error', error_msg=:m,
          company_id=COALESCE(company_id, :c)
        WHERE nm_id=:n AND (company_id=:c OR company_id IS NULL)
    """), {"m": str((payload or {}).get("error", "unknown"))[:500], "n": nm_id, "c": cid})
    await db.commit()
    return {"ok": True}


@router.post("/observe_search")
async def ext_observe_search(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Наблюдение выдачи: человек сам что-то искал — сохраняем фразу, позиции, цены, бейджи.

    - все позиции → `wb_competitor_position` (дневные срезы, `source_nm_id` = наша карточка
      из выдачи, 0 — если наших в выдаче не было);
    - топ-12 → `wb_competitor_cards` (конкуренты нашей карточки);
    - топ-12 → `wb_competitor_details` (цена/рейтинг/бейджи — «кто в акции»).

    Ничего не привязывает к анализу: только карточка+позиции+контент.
    """
    return await _with_db_retry(db, lambda: _observe_search_impl(payload, db, ext))


async def _observe_search_impl(payload: dict, db: AsyncSession, ext: dict):
    cid = int(ext["company_id"])
    data = payload or {}
    # Фразу нормализуем (WB даёт её и с дефисами, и с пробелами) — иначе один
    # запрос = две фразы в БД и в отчёте.
    phrase = capture_service._norm_phrase(data.get("phrase"))[:500]
    products = data.get("products") or []
    # Метка захода в поиск: расширение присылает search_stamp (один на все каналы
    # одного поиска). Если её нет — берём последний срез по этой фразе (заход был
    # минуту назад, JSON-каталог уже записался).
    slice_stamp = str(data.get("search_stamp") or "")[:20]
    if not slice_stamp:
        try:
            row = (await db.execute(text(
                "SELECT slice_stamp FROM wb_competitor_position "
                "WHERE company_id=:cid AND query_phrase=:ph AND slice_stamp<>'' "
                "ORDER BY id DESC LIMIT 1"
            ), {"cid": cid, "ph": phrase})).mappings().first()
            if row:
                slice_stamp = str(row["slice_stamp"] or "")[:20]
        except Exception:
            slice_stamp = ""
    # Не плодим срезы: заход в течение часа перезаписывает последний срез по фразе
    slice_stamp = await capture_service.resolve_slice_stamp(db, cid, phrase, slice_stamp)
    if not phrase or not products:
        # 400 — чтобы в журнале сервера было видно, что расширение прислало пустую выдачу
        raise HTTPException(
            status_code=400,
            detail=f"empty observation: phrase={phrase!r} products={len(products)}",
        )

    # наши карточки среди выдачи (определяем на сервере — расширение о компании не знает)
    ids = [int(p.get("id")) for p in products[:200] if p.get("id")]
    our: set[int] = set()
    if ids:
        ph = ",".join(f":i{i}" for i in range(len(ids)))
        rows = (await db.execute(
            text(f"SELECT nmID FROM wbcards WHERE company_id=:cid AND nmID IN ({ph})"),
            {**{"cid": cid}, **{f"i{i}": v for i, v in enumerate(ids)}},
        )).scalars().all()
        our = {int(x) for x in rows}
    # если наших в выдаче нет — привязываем к «нашей карточке» нельзя, пишем наблюдение без привязки
    sources = sorted(our) if our else [0]

    saved = 0
    for idx, p in enumerate(products[:200], 1):
        pid = p.get("id")
        if not pid:
            continue
        pos = int(p.get("position") or idx)
        img = p.get("imageUrl") or p.get("photourl") or ""
        if img.startswith("//"):
            img = "https:" + img
        price = capture_service._to_int(p.get("price", p.get("salePriceU", p.get("priceU", 0))))
        old_price = capture_service._to_int(p.get("old_price"))
        rating = capture_service._to_float(p.get("rating", p.get("reviewRating", 0)))
        fb = capture_service._to_int(p.get("feedbacks", 0))
        reviews = capture_service._to_int(p.get("reviews", 0))       # отзывы (WB API)
        badges = p.get("badges") or []
        seller = str(p.get("seller") or "")[:255]
        promo_id = capture_service._to_int(p.get("promo_id", 0))
        # «Нет в наличии» в выдаче: карточка без цены
        sold_out = 1 if p.get("sold_out") else 0
        uid = ext.get("created_by")
        tok = ext.get("id")

        for src in sources:
            await db.execute(text("""
                INSERT INTO wb_competitor_position
                  (company_id, source_nm_id, query_phrase, position, nm_id, title, brand, seller,
                   price, old_price, rating, feedbacks, reviews, badges, promo_id, image_url,
                   sold_out, created_by, ext_token_id, collected_at, slice_stamp)
                VALUES (:cid, :s, :ph, :pos, :pid, :t, :b, :seller, :price, :old_price, :rating,
                    :fb, :rev, :bg, :promo, :img, :so, :uid, :tok, CURDATE(), :slice_stamp)
                ON DUPLICATE KEY UPDATE
                  position=VALUES(position), title=VALUES(title), brand=VALUES(brand),
                  seller=IF(VALUES(seller)='', seller, VALUES(seller)),
                  price=IF(VALUES(price)>0, VALUES(price), price),
                  old_price=IF(VALUES(old_price)>0, VALUES(old_price), old_price),
                  rating=IF(VALUES(rating)>0, VALUES(rating), rating),
                  feedbacks=IF(VALUES(feedbacks)>0, VALUES(feedbacks), feedbacks),
                  reviews=IF(VALUES(reviews)>0, VALUES(reviews), reviews),
                  badges=IF(VALUES(badges)='[]', badges, VALUES(badges)),
                  promo_id=VALUES(promo_id), image_url=VALUES(image_url),
                  sold_out=VALUES(sold_out),
                  created_by=COALESCE(created_by, VALUES(created_by)),
                  ext_token_id=COALESCE(ext_token_id, VALUES(ext_token_id))
            """), {"cid": cid, "s": src, "ph": phrase, "pos": pos, "pid": pid,
                   "t": p.get("name", ""), "b": p.get("brand", ""), "seller": seller,
                   "price": price, "old_price": old_price, "rating": rating,
                   "fb": fb, "rev": reviews,
                   "bg": json.dumps(badges, ensure_ascii=False),
                   "promo": promo_id, "img": img, "so": sold_out,
                   "uid": uid, "tok": tok,
                   "slice_stamp": slice_stamp})

        # конкуренты нашей карточки — только топ-12
        if pos > 12:
            continue
        if our:
            for src in sorted(our):
                await db.execute(text("""
                    INSERT INTO wb_competitor_cards
                      (source_nm_id, query_phrase, position, nm_id, title, brand, seller,
                       price, old_price, rating, feedbacks, badges, image_url, source, added_by,
                       ext_token_id, sold_out)
                    VALUES (:s, :ph, :pos, :pid, :t, :b, :seller, :price, :old_price, :rating,
                            :fb, :bg, :img, 'search', :uid, :tok, :so)
                    ON DUPLICATE KEY UPDATE
                      position=VALUES(position), title=VALUES(title), brand=VALUES(brand),
                      seller=IF(VALUES(seller)='', seller, VALUES(seller)),
                      price=VALUES(price), old_price=VALUES(old_price), rating=VALUES(rating),
                      feedbacks=VALUES(feedbacks),
                      badges=IF(VALUES(badges)='[]', badges, VALUES(badges)),
                      image_url=VALUES(image_url),
                      sold_out=VALUES(sold_out),
                      added_by=COALESCE(added_by, VALUES(added_by)),
                      ext_token_id=COALESCE(ext_token_id, VALUES(ext_token_id))
                """), {"s": src, "ph": phrase, "pos": pos, "pid": pid,
                       "t": p.get("name", ""), "b": p.get("brand", ""), "seller": seller,
                       "price": price, "old_price": old_price, "rating": rating,
                       "fb": fb, "bg": json.dumps(badges, ensure_ascii=False),
                       "img": img, "uid": uid, "tok": tok, "so": sold_out})
        # Контент карточки из выдачи: цена/рейтинг/бейджи + превью.
        # Галерею (`images`) пишет только сбор с карточки (/result, /capture) —
        # наблюдение выдачи её не трогает, иначе одно превью затирает весь массив.
        await db.execute(text("""
            INSERT INTO wb_competitor_details
              (nm_id, title, brand, seller, price, old_price, rating, feedbacks, badges,
               images, preview_image, url, sold_out,
               collected_at, first_collected_at, captured_company_id, captured_by)
            VALUES (:n, :t, :b, :seller, :p, :o, :r, :fb, :bg,
                    JSON_ARRAY(), NULLIF(:prev, ''), :u, :so,
                    NOW(), NOW(), :cid, :uid)
            ON DUPLICATE KEY UPDATE
              title=IF(:t='', title, :t),
              brand=IF(:b='', brand, :b),
              seller=IF(:seller='', seller, :seller),
              price=IF(:p IS NULL, price, :p),
              old_price=IF(:o IS NULL, old_price, :o),
              rating=IF(:r IS NULL, rating, :r),
              feedbacks=IF(:fb IS NULL, feedbacks, :fb),
              badges=IF(:bg='[]', badges, :bg),
              preview_image=IF(:prev='', preview_image, :prev),
              sold_out=:so,
              collected_at=NOW()
        """), {"n": pid, "t": p.get("name", ""), "b": p.get("brand", ""), "seller": seller,
               "p": price, "o": old_price, "r": rating, "fb": fb, "so": sold_out,
               "bg": json.dumps(badges, ensure_ascii=False),
               "prev": str(img or "")[:1000],
               "u": f"https://www.wildberries.ru/catalog/{pid}/detail.aspx",
               "cid": cid, "uid": ext.get("created_by")})
        # видимость: конкурента мы «собрали» (позиция, цена, акции) — он попадает
        # в «Собранные карточки» и в попап; описание доберёт очередь.
        await db.execute(text("""
            INSERT INTO wb_competitor_capture
              (nm_id, company_id, is_own, is_hidden, first_seen_by, last_seen_by)
            VALUES (:n, :cid, 0, 0, :uid, :uid)
            ON DUPLICATE KEY UPDATE
              last_seen_at=NOW(), last_seen_by=:uid
        """), {"n": pid, "cid": cid, "uid": ext.get("created_by")})
        saved += 1

    await db.commit()
    return {"ok": True, "saved": saved, "positions": len(products),
            "our_cards": sorted(our), "phrase": phrase}


@router.post("/search_raw")
async def ext_search_raw(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Сырые ответы поисковой выдачи WB (план «2026-10-22_wb_search_json.md», Ш4).

    Расширение присылает то, что страница WB уже получила: каталог выдачи, фильтры
    ниши, баннеры/полки поиска и подсказки (related-запросы). Мы:
      1) сохраняем тело ответа файлом (как пришло) + компактные метаданные рядом;
      2) каталог → дополняем `wb_competitor_position` полями JSON
         (position_api, price_api, продавец, match_id и т.д.);
      3) фильтры → `wb_seo_search_filters`; баннеры/полки → `wb_seo_search_shelfs`;
      4) подсказки → только файл.

    Доменные поля выдачи (position, price, badges, картинка) пишет /observe_search —
    здесь их не трогаем.
    """
    return await _with_db_retry(db, lambda: search_raw_service.save_search_raw(db, ext, payload))


# ---------- search-режим: фразы/выдача/срезы (порт server.py) ----------

@router.get("/search_status")
async def ext_search_status(
    source: str = Query(default="seo"),
    nm_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    cid = int(ext["company_id"])
    if nm_id and not await _owns_card(db, cid, nm_id):
        raise HTTPException(status_code=403, detail="foreign nm_id")

    async def _seo_counts() -> dict:
        if nm_id:
            rows = (await db.execute(text(f"""
                SELECT status, COUNT(*) as cnt FROM wb_seo_target
                WHERE nmID=:n AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')}) GROUP BY status
            """), {"n": nm_id, "c2": cid})).mappings().all()
        else:
            rows = (await db.execute(text(f"""
                SELECT status, COUNT(*) as cnt FROM wb_seo_target
                WHERE nmID IN ({OWNED_CARDS.replace(':cid', ':c2')}) GROUP BY status
            """), {"c2": cid})).mappings().all()
        return {r["status"]: r["cnt"] for r in rows}

    async def _report_counts() -> dict:
        if not nm_id:
            return {"total": 0, "pending": 0, "done": 0}
        phrases = (await db.execute(text("""
            SELECT phrase FROM wb_sr_report_item_phrases WHERE nmID=:n AND orders>0 GROUP BY phrase
        """), {"n": nm_id})).mappings().all()
        pending, done = 0, 0
        for r in [x["phrase"] for x in phrases[:20]]:
            # фраза в отчёте может быть с дефисами/подчёркиваниями — маркер «(empty)»
            # пишется нормализованной (:np), проверяем оба варианта
            hit = (await db.execute(text("""
                SELECT 1 FROM wb_competitor_cards
                WHERE source_nm_id=:n AND (query_phrase=:p OR query_phrase=:np) LIMIT 1
            """), {"n": nm_id, "p": r, "np": capture_service._norm_phrase(r)})).first()
            if hit:
                done += 1
            else:
                pending += 1
        return {"pending": pending, "done": done}

    async def _compquery_counts() -> dict:
        where = "company_id=:c AND is_active=1"
        params = {"c": cid}
        if nm_id:
            where += " AND source_nm_id=:n"
            params["n"] = nm_id
        rows = (await db.execute(text(f"""
            SELECT status, COUNT(*) AS cnt FROM wb_competitor_query
            WHERE {where} GROUP BY status
        """), params)).mappings().all()
        return {r["status"]: r["cnt"] for r in rows}

    if source == "seo":
        rows = await _seo_counts()
    elif source == "report":
        rep = await _report_counts()
        return rep if "total" in rep else {"total": sum(rep.values()), **rep}
    elif source == "compquery":
        rows = await _compquery_counts()
    elif source == "phrases":
        rows = (await db.execute(text("""
            SELECT status, COUNT(*) AS cnt FROM wb_search_phrase_queue
            WHERE company_id=:c GROUP BY status
        """), {"c": cid})).mappings().all()
        rows = {r["status"]: r["cnt"] for r in rows}
    else:  # both
        rows = await _seo_counts()
        if nm_id:
            rep_pending = (await _report_counts()).get("pending", 0)
            rows["pending"] = rows.get("pending", 0) + rep_pending
    return {"total": sum(rows.values()), **rows}


async def _next_report_phrase(db: AsyncSession, nm_id: int) -> dict | None:
    """Следующая фраза из отчёта, которой ещё нет в cards. LIMIT 20 как в main.py парсера."""
    phrases = (await db.execute(text("""
        SELECT phrase, MAX(orders) as orders
        FROM wb_sr_report_item_phrases
        WHERE nmID=:n AND orders>0
        GROUP BY phrase
        ORDER BY SUM(orders) DESC
        LIMIT 20
    """), {"n": nm_id})).mappings().all()
    for r in phrases:
        # маркер «(empty)» пишется нормализованной фразой — проверяем оба варианта
        hit = (await db.execute(text("""
            SELECT 1 FROM wb_competitor_cards
            WHERE source_nm_id=:n AND (query_phrase=:p OR query_phrase=:np) LIMIT 1
        """), {"n": nm_id, "p": r["phrase"], "np": capture_service._norm_phrase(r["phrase"])})).first()
        if not hit:
            return {"queue_id": None, "nm_id": int(nm_id), "phrase": r["phrase"]}
    return None


@router.get("/search_next")
async def ext_search_next(
    nm_id: int | None = Query(default=None, ge=1),
    source: str = Query(default="seo"),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    cid = int(ext["company_id"])
    if nm_id and not await _owns_card(db, cid, nm_id):
        return {"nm_id": None}
    if source == "compquery":
        where = "company_id=:c AND is_active=1"
        params = {"c": cid}
        if nm_id:
            where += " AND source_nm_id=:n"
            params["n"] = nm_id
        # расширение могли закрыть в середине поиска — снимаем зависший processing
        await db.execute(text(f"""
            UPDATE wb_competitor_query SET status='pending'
            WHERE {where} AND status='processing'
              AND updated_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE)
        """), params)
        await db.commit()
        row = (await db.execute(text(f"""
            SELECT id, source_nm_id, phrase FROM wb_competitor_query
            WHERE {where} AND status='pending'
            ORDER BY priority, id LIMIT 1
        """), params)).mappings().first()
        if row:
            upd = await db.execute(text("""
                UPDATE wb_competitor_query SET status='processing', updated_at=NOW()
                WHERE id=:i AND status='pending'
            """), {"i": row["id"]})
            await db.commit()
            if upd.rowcount:
                return {"queue_id": row["id"], "nm_id": row["source_nm_id"], "phrase": row["phrase"]}
        return {"nm_id": None}
    if source == "phrases":
        # Очередь фраз на пересборку выдачи (из отчёта «Выдача WB»).
        await db.execute(text("""
            UPDATE wb_search_phrase_queue SET status='pending', updated_at=NOW()
            WHERE company_id=:c AND status='processing'
              AND updated_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE)
        """), {"c": cid})
        await db.commit()
        row = (await db.execute(text("""
            SELECT id, source_nm_id, query_phrase FROM wb_search_phrase_queue
            WHERE company_id=:c AND status='pending'
            ORDER BY priority, id LIMIT 1
        """), {"c": cid})).mappings().first()
        if row:
            upd = await db.execute(text("""
                UPDATE wb_search_phrase_queue SET status='processing', updated_at=NOW()
                WHERE id=:i AND status='pending'
            """), {"i": row["id"]})
            await db.commit()
            if upd.rowcount:
                return {"queue_id": int(row["id"]),
                        "nm_id": int(row["source_nm_id"] or 0),
                        "phrase": row["query_phrase"]}
        return {"nm_id": None}
    if source in ("seo", "both"):
        # зависший processing: расширение могло закрыться посреди поиска —
        # снимаем в pending (тот же 30-минутный reset, что у compquery).
        # updated_at при claim проставляется явно (см. ниже) — по нему и сверяем.
        if nm_id:
            await db.execute(text(f"""
                UPDATE wb_seo_target SET status='pending', updated_at=NOW()
                WHERE status='processing' AND nmID=:n
                  AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')})
                  AND updated_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE)
            """), {"n": nm_id, "c2": cid})
        else:
            await db.execute(text(f"""
                UPDATE wb_seo_target SET status='pending', updated_at=NOW()
                WHERE status='processing'
                  AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')})
                  AND updated_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE)
            """), {"c2": cid})
        await db.commit()
        if nm_id:
            row = (await db.execute(text(f"""
                SELECT id, nmID, phrase FROM wb_seo_target
                WHERE status='pending' AND nmID=:n AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')})
                ORDER BY priority DESC, id LIMIT 1
            """), {"n": nm_id, "c2": cid})).mappings().first()
        else:
            row = (await db.execute(text(f"""
                SELECT id, nmID, phrase FROM wb_seo_target
                WHERE status='pending' AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')})
                ORDER BY priority DESC, id LIMIT 1
            """), {"c2": cid})).mappings().first()
        if row:
            # updated_at=NOW() явно — точка старта 30-минутного таймаута processing
            await db.execute(text("UPDATE wb_seo_target SET status='processing', updated_at=NOW() WHERE id=:i"), {"i": row["id"]})
            await db.commit()
            return {"queue_id": row["id"], "nm_id": row["nmID"], "phrase": row["phrase"]}
    if source in ("report", "both") and nm_id:
        rep = await _next_report_phrase(db, nm_id)
        if rep:
            return rep
    return {"nm_id": None}


@router.post("/search_result")
async def ext_search_result(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    return await _with_db_retry(db, lambda: _search_result_impl(payload, db, ext))


async def _search_result_impl(payload: dict, db: AsyncSession, ext: dict):
    cid = int(ext["company_id"])
    data = payload or {}
    queue_id = data.get("queue_id")
    nm_id = data.get("nm_id")
    phrase = capture_service._norm_phrase(data.get("phrase", ""))[:500]
    products = data.get("products") or []
    source = str(data.get("source") or "seo")
    try:
        nm_id = int(nm_id) if nm_id else 0
        queue_id = int(queue_id) if queue_id else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad queue_id/nm_id")
    # Для очереди «Поисковые фразы» карточка может быть не привязана (nm_id=0):
    # тогда соберём сырьё по нише, а позиций «нас» не будет.
    if not nm_id and source != "phrases":
        raise HTTPException(status_code=400, detail="nm_id required")
    if nm_id and not await _owns_card(db, cid, nm_id):
        raise HTTPException(status_code=403, detail="foreign nm_id")
    # Метка захода в поиск — как в /observe_search (с окном в час)
    slice_stamp = str(data.get("search_stamp") or "")[:20]
    slice_stamp = await capture_service.resolve_slice_stamp(db, cid, phrase, slice_stamp)
    if not slice_stamp:
        try:
            row = (await db.execute(text(
                "SELECT slice_stamp FROM wb_competitor_position "
                "WHERE company_id=:cid AND query_phrase=:ph AND source_nm_id=:s AND slice_stamp<>'' "
                "ORDER BY id DESC LIMIT 1"
            ), {"cid": cid, "ph": phrase, "s": nm_id})).mappings().first()
            if row:
                slice_stamp = str(row["slice_stamp"] or "")[:20]
        except Exception:
            slice_stamp = ""
    uid = ext.get("created_by")
    tok = ext.get("id")
    for idx, p in enumerate(products, 1):
        pid = p.get("id")
        if not pid:
            continue
        pos = int(p.get("position") or idx)
        img = p.get("imageUrl", p.get("photourl", ""))
        if img and img.startswith("//"):
            img = "https:" + img
        price = capture_service._to_int(p.get("price", p.get("salePriceU", p.get("priceU", 0))))
        old_price = capture_service._to_int(p.get("old_price"))
        rating = capture_service._to_float(p.get("rating", p.get("reviewRating", 0)))
        fb = capture_service._to_int(p.get("feedbacks", 0))
        reviews = capture_service._to_int(p.get("reviews", 0))
        badges = p.get("badges") or []
        seller = str(p.get("seller") or "")[:255]
        promo_id = capture_service._to_int(p.get("promo_id", 0))
        # «Нет в наличии» в выдаче: карточка без цены — флаг на строку
        sold_out = 1 if p.get("sold_out") else 0
        # Позиции выдачи — дневные срезы (все позиции, хвост не теряем)
        await db.execute(text("""
            INSERT INTO wb_competitor_position
              (company_id, source_nm_id, query_phrase, position, nm_id, title, brand, seller,
               price, old_price, rating, feedbacks, reviews, badges, promo_id, image_url,
               sold_out, created_by, ext_token_id, collected_at, slice_stamp)
            VALUES (:cid, :s, :ph, :pos, :pid, :t, :b, :seller, :price, :old_price, :rating,
                    :fb, :rev, :bg, :promo, :img, :so, :uid, :tok, CURDATE(), :slice_stamp)
            ON DUPLICATE KEY UPDATE
              position=VALUES(position), title=VALUES(title), brand=VALUES(brand),
              seller=IF(VALUES(seller)='', seller, VALUES(seller)),
              price=IF(VALUES(price)>0, VALUES(price), price),
              old_price=IF(VALUES(old_price)>0, VALUES(old_price), old_price),
              rating=IF(VALUES(rating)>0, VALUES(rating), rating),
              feedbacks=IF(VALUES(feedbacks)>0, VALUES(feedbacks), feedbacks),
              reviews=IF(VALUES(reviews)>0, VALUES(reviews), reviews),
              badges=IF(VALUES(badges)='[]', badges, VALUES(badges)),
              promo_id=VALUES(promo_id), image_url=VALUES(image_url),
              sold_out=VALUES(sold_out),
              created_by=COALESCE(created_by, VALUES(created_by)),
              ext_token_id=COALESCE(ext_token_id, VALUES(ext_token_id))
        """), {"cid": cid, "s": nm_id, "ph": phrase, "pos": pos, "pid": pid,
               "t": p.get("name", ""), "b": p.get("brand", ""), "seller": seller,
               "price": price, "old_price": old_price, "rating": rating, "fb": fb, "rev": reviews,
               "bg": json.dumps(badges, ensure_ascii=False),
               "promo": promo_id, "img": img, "so": sold_out,
               "uid": uid, "tok": tok, "slice_stamp": slice_stamp})
        # Конкуренты нашей карточки — только топ-12 (схема: «позиция в выдаче, 1-12»)
        if pos > 12:
            continue
        if not nm_id:
            # фраза без привязки к нашей карточке: позиции пишем, конкурентов — некуда
            continue
        await db.execute(text("""
            INSERT INTO wb_competitor_cards
              (source_nm_id, query_phrase, position, nm_id, title, brand, seller,
               price, old_price, rating, feedbacks, badges, image_url, source, added_by,
               ext_token_id, sold_out)
            VALUES (:s, :ph, :pos, :pid, :t, :b, :seller, :price, :old_price, :rating,
                    :fb, :bg, :img, 'search', :uid, :tok, :so)
            ON DUPLICATE KEY UPDATE
              position=VALUES(position), title=VALUES(title), brand=VALUES(brand),
              seller=IF(VALUES(seller)='', seller, VALUES(seller)),
              price=VALUES(price), old_price=VALUES(old_price), rating=VALUES(rating),
              feedbacks=VALUES(feedbacks),
              badges=IF(VALUES(badges)='[]', badges, VALUES(badges)),
              image_url=VALUES(image_url),
              sold_out=VALUES(sold_out),
              added_by=COALESCE(added_by, VALUES(added_by)),
              ext_token_id=COALESCE(ext_token_id, VALUES(ext_token_id))
        """), {"s": nm_id, "ph": phrase, "pos": pos, "pid": pid,
               "t": p.get("name", ""), "b": p.get("brand", ""), "seller": seller,
               "price": price, "old_price": old_price, "rating": rating, "fb": fb,
               "bg": json.dumps(badges, ensure_ascii=False),
               "img": img, "uid": uid, "tok": tok, "so": sold_out})
    if queue_id:
        if source == "phrases":
            await db.execute(text("""
                UPDATE wb_search_phrase_queue SET status='done', updated_at=NOW()
                WHERE id=:i AND company_id=:c
            """), {"i": queue_id, "c": cid})
        elif source == "compquery":
            q = (await db.execute(text("""
                SELECT source_nm_id FROM wb_competitor_query
                WHERE id=:i AND company_id=:c LIMIT 1
            """), {"i": queue_id, "c": cid})).mappings().first()
            if not q or int(q["source_nm_id"]) != nm_id:
                await db.rollback()
                raise HTTPException(status_code=403, detail="foreign queue_id")
            await db.execute(text("""
                UPDATE wb_competitor_query SET status='done', updated_at=NOW() WHERE id=:i
            """), {"i": queue_id})
        else:
            tgt = (await db.execute(text("SELECT nmID FROM wb_seo_target WHERE id=:i LIMIT 1"),
                                    {"i": queue_id})).mappings().first()
            if tgt and not await _owns_card(db, cid, int(tgt["nmID"])):
                await db.rollback()
                raise HTTPException(status_code=403, detail="foreign queue_id")
            await db.execute(text("UPDATE wb_seo_target SET status='done' WHERE id=:i"), {"i": queue_id})
    elif not products and source != "compquery" and nm_id:
        # report-источник с пустым результатом («Не нашлось») — маркируем чтобы не зацикливаться
        await db.execute(text("""
            INSERT IGNORE INTO wb_competitor_cards
              (source_nm_id, query_phrase, position, nm_id, title)
            VALUES (:s, :ph, 0, 0, '(empty)')
        """), {"s": nm_id, "ph": phrase})
    if source == "compquery":
        # найденные поиском карточки сразу ставим в очередь на сбор описаний
        await db.execute(text("""
            INSERT INTO wb_enrich_queue (nm_id, company_id)
            SELECT DISTINCT c.nm_id, :c
            FROM wb_competitor_cards c
            WHERE c.source_nm_id=:s AND c.query_phrase=:ph AND c.nm_id>0
              AND c.nm_id NOT IN (
                  SELECT d.nm_id FROM wb_competitor_details d
                  WHERE d.collected_at > NOW() - INTERVAL 24 HOUR
              )
            ON DUPLICATE KEY UPDATE
              company_id=IF(company_id IS NULL, :c, company_id),
              status=IF((company_id IS NULL OR company_id=:c) AND status IN ('done', 'error'), 'pending', status)
        """), {"c": cid, "s": nm_id, "ph": phrase})
    await db.commit()
    return {"ok": True, "saved": len(products)}


@router.post("/search_error")
async def ext_search_error(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    cid = int(ext["company_id"])
    data = payload or {}
    source = str(data.get("source") or "seo")
    try:
        queue_id = int(data.get("queue_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad queue_id")
    if queue_id:
        if source == "compquery":
            q = (await db.execute(text("""
                SELECT id FROM wb_competitor_query WHERE id=:i AND company_id=:c LIMIT 1
            """), {"i": queue_id, "c": cid})).mappings().first()
            if q:
                await db.execute(text("""
                    UPDATE wb_competitor_query SET status='error', updated_at=NOW() WHERE id=:i
                """), {"i": queue_id})
                await db.commit()
            return {"ok": True}
        tgt = (await db.execute(text("SELECT nmID FROM wb_seo_target WHERE id=:i LIMIT 1"),
                                {"i": queue_id})).mappings().first()
        if tgt and not await _owns_card(db, cid, int(tgt["nmID"])):
            raise HTTPException(status_code=403, detail="foreign queue_id")
        await db.execute(text("UPDATE wb_seo_target SET status='error' WHERE id=:i"), {"i": queue_id})
        await db.commit()
    elif source == "report":
        # report-фразы отдаются без queue_id (поиск по отчёту): ошибку по фразе
        # помечаем тем же маркером «(empty)», что и пустую выдачу (search_result),
        # иначе search_next возвращает эту фразу бесконечно. Расширение шлёт
        # nm_id + phrase в payload (background.js reportSearchError).
        try:
            nm_id = int(data.get("nm_id") or 0)
        except (TypeError, ValueError):
            nm_id = 0
        phrase = capture_service._norm_phrase(data.get("phrase") or "")[:500]
        if nm_id and phrase and await _owns_card(db, cid, nm_id):
            await db.execute(text("""
                INSERT IGNORE INTO wb_competitor_cards
                  (source_nm_id, query_phrase, position, nm_id, title)
                VALUES (:s, :ph, 0, 0, '(empty)')
            """), {"s": nm_id, "ph": phrase})
            await db.commit()
    return {"ok": True}


@router.post("/reset_enrich")
async def ext_reset_enrich(
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Сброс зависших/ошибочных в pending.

    'gone' (карточки нет на WB) по умолчанию НЕ сбрасывается: пока человек
    не проверил, что карточка появилась, в обновление её не даём. Явным
    include_gone=1 (кнопка «Появилась снова») строку gone поднимаем."""
    cid = int(ext["company_id"])
    data = payload or {}
    nm_id = data.get("nm_id")
    include_gone = bool(data.get("include_gone"))
    try:
        nm_id = int(nm_id) if nm_id else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad nm_id")
    if include_gone:
        # «Появилась снова»: удаляем маркер gone вручную (человек проверил).
        if nm_id:
            if not await _owns_card(db, cid, nm_id):
                raise HTTPException(status_code=403, detail="foreign nm_id")
            r = await db.execute(text(f"""
                UPDATE wb_enrich_queue
                SET status='done', processed_at=NOW()
                WHERE status='gone' AND nm_id=:n
                  AND (company_id=:c OR company_id IS NULL)
                  AND nm_id IN (
                      SELECT nm_id FROM wb_competitor_cards
                      WHERE source_nm_id=:n
                  )
            """), {"n": nm_id, "c": cid})
        else:
            r = await db.execute(text(f"""
                UPDATE wb_enrich_queue
                SET status='done', processed_at=NOW()
                WHERE status='gone'
                  AND (company_id=:c OR company_id IS NULL)
                  AND nm_id IN (
                      SELECT nm_id FROM wb_competitor_cards
                      WHERE source_nm_id IN ({OWNED_CARDS.replace(':cid', ':c2')})
                  )
            """), {"c": cid, "c2": cid})
        await db.commit()
        return {"reset": r.rowcount}
    statuses = "error, processing"
    if nm_id:
        if not await _owns_card(db, cid, nm_id):
            raise HTTPException(status_code=403, detail="foreign nm_id")
        r = await db.execute(text(f"""
            UPDATE wb_enrich_queue q
            JOIN wb_competitor_cards c ON c.nm_id=q.nm_id
            SET q.status='pending'
            WHERE q.status IN ({statuses}) AND c.source_nm_id=:n AND (q.company_id=:c OR q.company_id IS NULL)
        """), {"n": nm_id, "c": cid})
        if r.rowcount == 0:
            # fallback если join не нашёл (прямой фильтр по queue без join — как во Flask)
            r = await db.execute(text("""
                UPDATE wb_enrich_queue SET status='pending'
                WHERE status IN ('error', 'processing') AND (company_id=:c OR company_id IS NULL)
                  AND nm_id IN (SELECT nm_id FROM wb_competitor_cards WHERE source_nm_id=:n)
            """), {"n": nm_id, "c": cid})
    else:
        r = await db.execute(text("""
            UPDATE wb_enrich_queue SET status='pending'
            WHERE status IN ('error', 'processing') AND (company_id=:c OR company_id IS NULL)
        """), {"c": cid})
    await db.commit()
    return {"reset": r.rowcount}


@router.post("/reset_search")
async def ext_reset_search(
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    cid = int(ext["company_id"])
    data = payload or {}
    nm_id = data.get("nm_id")
    source = data.get("source", "seo")
    try:
        nm_id = int(nm_id) if nm_id else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad nm_id")
    changed = 0
    if source in ("seo", "both"):
        if nm_id:
            if not await _owns_card(db, cid, nm_id):
                raise HTTPException(status_code=403, detail="foreign nm_id")
            r = await db.execute(text(f"""
                UPDATE wb_seo_target SET status='pending', updated_at=NOW()
                WHERE status IN ('error','processing') AND nmID=:n AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')})
            """), {"n": nm_id, "c2": cid})
        else:
            r = await db.execute(text(f"""
                UPDATE wb_seo_target SET status='pending', updated_at=NOW()
                WHERE status IN ('error','processing') AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')})
            """), {"c2": cid})
        changed = r.rowcount
    elif source == "compquery":
        where = "company_id=:c AND is_active=1"
        params = {"c": cid}
        if nm_id:
            if not await _owns_card(db, cid, nm_id):
                raise HTTPException(status_code=403, detail="foreign nm_id")
            where += " AND source_nm_id=:n"
            params["n"] = nm_id
        r = await db.execute(text(f"""
            UPDATE wb_competitor_query SET status='pending', updated_at=NOW()
            WHERE {where} AND status IN ('error', 'processing')
        """), params)
        changed = r.rowcount
    elif source == "phrases":
        r = await db.execute(text("""
            UPDATE wb_search_phrase_queue SET status='pending', updated_at=NOW()
            WHERE company_id=:c AND status IN ('error', 'processing')
        """), {"c": cid})
        changed = r.rowcount
    await db.commit()
    return {"reset": changed}


@router.get("/report_phrases")
async def ext_report_phrases(
    nm_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    cid = int(ext["company_id"])
    if not nm_id:
        return {"phrases": []}
    if not await _owns_card(db, cid, nm_id):
        raise HTTPException(status_code=403, detail="foreign nm_id")
    rows = (await db.execute(text("""
        SELECT phrase FROM wb_sr_report_item_phrases
        WHERE nmID=:n AND orders>0 AND phrase NOT REGEXP '^[0-9]+$' AND CHAR_LENGTH(phrase)>3
        GROUP BY phrase ORDER BY SUM(orders) DESC LIMIT 20
    """), {"n": nm_id})).scalars().all()
    return {"phrases": [str(x) for x in rows]}


# ---------- diagnose: «чёрный ящик» на смену вёрстки WB ----------

@router.post("/diagnose")
async def ext_diagnose_save(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    _ = db
    cid = int(ext["company_id"])
    data = payload or {}
    try:
        nm_id = int(data.get("nm_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad nm_id")
    if not nm_id:
        raise HTTPException(status_code=400, detail="nm_id required")
    d = _diag_dir(cid)
    (d / f"diag_{nm_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # ротация: не больше 100 слепков на компанию
    files = sorted(d.glob("diag_*.json"), key=lambda p: p.stat().st_mtime)
    for old in files[:-100]:
        try:
            old.unlink()
        except OSError:
            pass
    return {"ok": True, "saved": f"diag/{cid}/diag_{nm_id}.json"}


def _diag_summary(d: dict) -> dict:
    return {"nm_id": d.get("nm_id"), "h2_count": len(d.get("h2", []) or []),
            "sections_count": len(d.get("sections", []) or []),
            "catalog_links": len(d.get("catalogLinks", []) or []),
            "popup_cards": len(d.get("popupCards", []) or [])}


@router.get("/diagnose")
@router.get("/diagnose_list")
async def ext_diagnose_list(
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Последние 10 слепков своей компании (порт diagnose_list, но скоуп по папке компании)."""
    _ = db
    return _diag_list_for(int(ext["company_id"]))


@router.get("/diagnose/{nm_id}")
async def ext_diagnose_view(
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    _ = db
    return _diag_view_for(int(ext["company_id"]), nm_id)


def _diag_list_for(cid: int) -> list[dict]:
    d = _diag_dir(cid)
    files = sorted(d.glob("diag_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
    out = []
    for f in files:
        try:
            out.append(_diag_summary(json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def _diag_view_for(cid: int, nm_id: int) -> dict:
    p = _diag_dir(cid) / f"diag_{nm_id}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="not found")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        raise HTTPException(status_code=500, detail="bad diag json")


# ---------- diag для людей (JWT, та же папка компании) ----------

@diag_admin_router.get("")
async def ext_diag_admin_list(
    company_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    """Слепки своей компании для страницы просмотра (читает то же, что пишет расширение)."""
    _ = db
    return _diag_list_for(company_id)


@diag_admin_router.get("/{nm_id}")
async def ext_diag_admin_view(
    company_id: int = Path(..., ge=1),
    nm_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    _ = db
    return _diag_view_for(company_id, nm_id)


# ---------- пресеты фильтра категорий (JWT + расширение) ----------

# Фолбэк, пока компания не завела свои (тот же набор, что был захардкожен в popup).
DEFAULT_CATEGORY_FILTERS = [
    {"id": 0, "name": "Книги и журналы", "subjects": "381;397;1132;662;661"},
]


def _norm_subjects(raw: str) -> str:
    """id subject цифрами через «;»: допускаем запятые/пробелы на входе."""
    import re as _re
    ids = [p for p in _re.split(r"[;,\s]+", str(raw or "")) if p.isdigit()]
    if not ids:
        raise ValueError("subjects: нужен хотя бы один числовой id (разделитель ; , пробел)")
    return ";".join(ids)[:500]


@cat_router.get("")
async def ext_filters_list(
    company_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    rows = (await db.execute(text("""
        SELECT id, company_id, name, subjects, is_active FROM ext_category_filters
        WHERE company_id=:c ORDER BY id
    """), {"c": company_id})).mappings().all()
    return [{**dict(r), "is_active": bool(r["is_active"])} for r in rows]


@cat_router.post("")
async def ext_filters_create(
    company_id: int = Path(..., ge=1),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    data = payload or {}
    name = str(data.get("name") or "").strip()[:100]
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    try:
        subjects = _norm_subjects(data.get("subjects"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.rollback()
    try:
        async with db.begin():
            await db.execute(text("""
                INSERT INTO ext_category_filters (company_id, name, subjects, is_active, created_by)
                VALUES (:c, :n, :s, :a, :u)
            """), {"c": company_id, "n": name, "s": subjects,
                   "a": 0 if data.get("is_active") is False else 1, "u": user["id"]})
            row = (await db.execute(text("""
                SELECT id, company_id, name, subjects, is_active FROM ext_category_filters
                WHERE company_id=:c AND name=:n LIMIT 1
            """), {"c": company_id, "n": name})).mappings().first()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="preset with this name exists")
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    return d


@cat_router.patch("/{fid}")
async def ext_filters_update(
    company_id: int = Path(..., ge=1),
    fid: int = Path(..., ge=1),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    data = payload or {}
    sets: dict = {}
    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()[:100]
        if not name:
            raise HTTPException(status_code=400, detail="bad name")
        sets["name"] = name
    if "subjects" in data and data["subjects"] is not None:
        try:
            sets["subjects"] = _norm_subjects(data["subjects"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if "is_active" in data and data["is_active"] is not None:
        sets["is_active"] = 1 if data["is_active"] else 0
    if not sets:
        raise HTTPException(status_code=400, detail="nothing to update")
    await db.rollback()
    try:
        async with db.begin():
            r = await db.execute(text(f"""
                UPDATE ext_category_filters SET {", ".join(f"{k}=:{k}" for k in sets)}
                WHERE id=:i AND company_id=:c
            """), {**sets, "i": fid, "c": company_id})
            if not r.rowcount:
                raise HTTPException(status_code=404, detail="preset not found")
            row = (await db.execute(text("""
                SELECT id, company_id, name, subjects, is_active FROM ext_category_filters
                WHERE id=:i LIMIT 1
            """), {"i": fid})).mappings().first()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="preset with this name exists")
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    return d


@cat_router.delete("/{fid}")
async def ext_filters_delete(
    company_id: int = Path(..., ge=1),
    fid: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    await db.rollback()
    async with db.begin():
        r = await db.execute(text("""
            DELETE FROM ext_category_filters WHERE id=:i AND company_id=:c
        """), {"i": fid, "c": company_id})
        if not r.rowcount:
            raise HTTPException(status_code=404, detail="preset not found")
    return {"ok": True}


@router.get("/filters")
async def ext_filters_for_extension(
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Активные пресеты компании токена для дропдауна в popup. Пусто — фолбэк по умолчанию."""
    cid = int(ext["company_id"])
    try:
        rows = (await db.execute(text("""
            SELECT id, name, subjects FROM ext_category_filters
            WHERE company_id=:c AND is_active=1 ORDER BY id
        """), {"c": cid})).mappings().all()
    except Exception:
        await db.rollback()
        return []  # миграции ещё нет — расширение оставит локальный дефолт
    out = [dict(r) for r in rows]
    return out or DEFAULT_CATEGORY_FILTERS


# ---------- скачивание расширения (JWT, side-load, §10 п.4) ----------

# Что НЕ тащим в архив (служебное/мусор)
EXT_ZIP_SKIP_SUFFIX = {".md", ".txt", ".log", ".map", ".bak", ".tmp", ".zip"}
EXT_ZIP_SKIP_NAMES = {".DS_Store", "Thumbs.db", "package.json", "package-lock.json"}


def _ext_zip_files(src: pathlib.Path) -> list[str]:
    """Все файлы расширения из папки — относительные пути через '/'.

    Раньше был жёсткий список: новый файл (иконка, новый content-script) молча
    не попадал в архив, а отсутствующий в папке — ронял скачивание на 500.
    """
    out: list[str] = []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        if p.name in EXT_ZIP_SKIP_NAMES or p.name.startswith("."):
            continue
        if p.suffix.lower() in EXT_ZIP_SKIP_SUFFIX:
            continue
        out.append(p.relative_to(src).as_posix())
    return out


def _ext_manifest_cleanup(manifest: dict, files: list[str]) -> dict:
    """Убрать из манифеста ссылки на файлы, которых нет в архиве.

    Иначе Chrome при установке ругается «Could not load icon ...».
    """
    have = set(files)

    def _exists(path: str) -> bool:
        return str(path or "").replace("\\", "/") in have

    icons = manifest.get("icons")
    if isinstance(icons, dict):
        manifest["icons"] = {k: v for k, v in icons.items() if _exists(k)}
        if not manifest["icons"]:
            manifest.pop("icons", None)
    action = manifest.get("action")
    if isinstance(action, dict) and "default_icon" in action:
        if not _exists(action["default_icon"]):
            manifest["action"] = {k: v for k, v in action.items() if k != "default_icon"}
    for cs in manifest.get("content_scripts") or []:
        if not isinstance(cs, dict):
            continue
        for key in ("js", "css"):
            if key in cs:
                cs[key] = [x for x in (cs[key] or []) if _exists(x)]
    return manifest


@dl_router.get("")
async def ext_download(
    company_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _member: int | None = Depends(get_current_company),
    _seo: dict = Depends(require_seo),
):
    """Zip расширения с уже вшитым SERVER (EXT_PUBLIC_BASE) и host_permissions.
    Токен не вшиваем — его человек вставляет в popup руками (выдаётся один раз)."""
    import io
    import os
    import re
    import zipfile

    _ = db
    _ = company_id
    src = os.getenv("EXTENSION_DIR", "").rstrip("/\\")
    base = os.getenv("EXT_PUBLIC_BASE", "http://31.130.204.146:3000").rstrip("/")
    if not src:
        raise HTTPException(status_code=500, detail="EXTENSION_DIR is not set (см. backend/.env.example)")
    root = pathlib.Path(src)
    manifest_p = root / "manifest.json"
    if not manifest_p.exists():
        raise HTTPException(status_code=500, detail=f"extension not found in EXTENSION_DIR={src}")
    try:
        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    except ValueError:
        raise HTTPException(status_code=500, detail="bad manifest.json in EXTENSION_DIR")
    files = _ext_zip_files(root)
    if "manifest.json" not in files:
        raise HTTPException(status_code=500, detail="extension folder has no manifest.json")
    version = str(manifest.get("version") or "1.0")
    hp = list(manifest.get("host_permissions") or [])
    if f"{base}/*" not in hp:
        hp.append(f"{base}/*")
    manifest["host_permissions"] = hp
    manifest = _ext_manifest_cleanup(manifest, files)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in files:
            p = root / name
            try:
                data = p.read_bytes()
            except OSError:
                continue
            if name.endswith(".js"):
                # вшиваем адрес сервера во ВСЕ js-файлы (раньше — только в два)
                try:
                    text_js = data.decode("utf-8")
                except UnicodeDecodeError:
                    text_js = None
                if text_js is not None:
                    text_js = re.sub(r'const DEFAULT_SERVER = "[^"]*";',
                                     f'const DEFAULT_SERVER = "{base}";', text_js, count=1)
                    data = text_js.encode("utf-8")
            if name == "manifest.json":
                data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            zf.writestr(name, data)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="wb-competitor-parser-{version}.zip"',
            # что реально внутри архива — видно в devtools/curl
            "X-Ext-Files": ",".join(files),
        })


# ---------- полки / дубликаты / клипы (пассивный перехват) ----------

@router.post("/shelves")
async def ext_shelves(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Полки «Смотрите также», кластеры дубликатов и UGC-клипы с карточки WB.

    Расширение присылает только то, что страница уже получила сама (без
    дополнительных запросов к WB). Повторный снимок за день обновляет строки,
    между днями остаётся история (`snapshot_date`).
    """
    try:
        res = await shelves_service.save_shelves(
            db, int(ext["company_id"]), ext.get("created_by"), payload or {}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {"ok": True, **res}