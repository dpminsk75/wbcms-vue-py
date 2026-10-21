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

import json
import pathlib
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company, get_current_user, require_ext_token, require_seo
from backend.services import ext_service, capture_service

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
        r = await db.execute(text(f"""
            INSERT INTO wb_enrich_queue (nm_id, company_id)
            SELECT DISTINCT nm_id, :cid FROM wb_competitor_cards
            WHERE source_nm_id=:s
              AND nm_id NOT IN (SELECT nm_id FROM wb_competitor_details WHERE collected_at > NOW() - INTERVAL 24 HOUR)
            ON DUPLICATE KEY UPDATE
              company_id=IF(company_id IS NULL, :cid, company_id),
              status=IF((company_id IS NULL OR company_id=:cid) AND status IN ('done', 'error'), 'pending', status)
        """), {"s": source, "cid": cid})
    else:
        r = await db.execute(text(f"""
            INSERT INTO wb_enrich_queue (nm_id, company_id)
            SELECT DISTINCT nm_id, :cid FROM wb_competitor_cards
            WHERE source_nm_id IN ({OWNED_CARDS.replace(':cid', ':cid2')})
              AND nm_id NOT IN (SELECT nm_id FROM wb_competitor_details WHERE collected_at > NOW() - INTERVAL 24 HOUR)
            ON DUPLICATE KEY UPDATE
              company_id=IF(company_id IS NULL, :cid, company_id),
              status=IF((company_id IS NULL OR company_id=:cid) AND status IN ('done', 'error'), 'pending', status)
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
        UPDATE wb_enrich_queue SET status='processing', company_id=:cid
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
        SELECT id, recommendations, collected_at FROM wb_competitor_details WHERE nm_id=:n
    """), {"n": nm_id})).mappings().first()
    new_recs = json.dumps(payload.get("recommendations") or [], ensure_ascii=False)
    new_chars = json.dumps(payload.get("characteristics") or [], ensure_ascii=False)
    params = {
        "n": nm_id, "t": payload.get("title", ""), "d": payload.get("description", ""),
        "u": payload.get("url", ""), "b": payload.get("brand", ""), "s": payload.get("seller", ""),
        "p": payload.get("price", ""), "o": payload.get("old_price", ""),
        "img": json.dumps(payload.get("images") or [], ensure_ascii=False),
        "chars": new_chars, "subj": str(payload.get("subject_name") or "")[:255],
        "cid": cid, "uid": uid,
    }
    if existing:
        age_h = 25.0
        try:
            age_h = (datetime.now() - existing["collected_at"]).total_seconds() / 3600
        except TypeError:
            pass
        if age_h < 24:
            final_recs = existing["recommendations"] if (not payload.get("recommendations") and existing["recommendations"]) else new_recs
            await db.execute(text("""
                UPDATE wb_competitor_details SET
                  title=:t, description=:d, recommendations=:r, url=:u,
                  brand=:b, seller=:s, price=:p, old_price=:o,
                  images=:img, collected_at=NOW(),
                  characteristics=IF(:chars='[]', characteristics, :chars),
                  subject_name=IF(:subj='', subject_name, :subj),
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
                  images=:img, collected_at=NOW(),
                  characteristics=IF(:chars='[]', characteristics, :chars),
                  subject_name=IF(:subj='', subject_name, :subj),
                  captured_company_id=COALESCE(captured_company_id, :cid),
                  captured_by=COALESCE(captured_by, :uid)
                WHERE nm_id=:n
            """), {**params, "r": new_recs})
    else:
        await db.execute(text("""
            INSERT INTO wb_competitor_details
              (nm_id, title, description, recommendations, url, brand, seller, price, old_price, images,
               characteristics, subject_name, first_collected_at, captured_company_id, captured_by)
            VALUES (:n, :t, :d, :nr, :u, :b, :s, :p, :o, :img, :chars, :subj, NOW(), :cid, :uid)
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
    await db.execute(text("""
        UPDATE wb_enrich_queue SET status='error', error_msg=:m,
          company_id=COALESCE(company_id, :c)
        WHERE nm_id=:n AND (company_id=:c OR company_id IS NULL)
    """), {"m": str((payload or {}).get("error", "unknown"))[:500], "n": nm_id, "c": cid})
    await db.commit()
    return {"ok": True}


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
            hit = (await db.execute(text("""
                SELECT 1 FROM wb_competitor_cards WHERE source_nm_id=:n AND query_phrase=:p LIMIT 1
            """), {"n": nm_id, "p": r})).first()
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
        hit = (await db.execute(text("""
            SELECT 1 FROM wb_competitor_cards WHERE source_nm_id=:n AND query_phrase=:p LIMIT 1
        """), {"n": nm_id, "p": r["phrase"]})).first()
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
    if source in ("seo", "both"):
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
            await db.execute(text("UPDATE wb_seo_target SET status='processing' WHERE id=:i"), {"i": row["id"]})
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
    cid = int(ext["company_id"])
    data = payload or {}
    queue_id = data.get("queue_id")
    nm_id = data.get("nm_id")
    phrase = data.get("phrase", "")
    products = data.get("products") or []
    source = str(data.get("source") or "seo")
    try:
        nm_id = int(nm_id) if nm_id else 0
        queue_id = int(queue_id) if queue_id else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad queue_id/nm_id")
    if not nm_id:
        raise HTTPException(status_code=400, detail="nm_id required")
    if not await _owns_card(db, cid, nm_id):
        raise HTTPException(status_code=403, detail="foreign nm_id")
    for pos, p in enumerate(products, 1):
        pid = p.get("id")
        if not pid:
            continue
        img = p.get("imageUrl", p.get("photourl", ""))
        if img and img.startswith("//"):
            img = "https:" + img
        await db.execute(text("""
            INSERT INTO wb_competitor_cards
              (source_nm_id, query_phrase, position, nm_id, title, brand, price, rating, feedbacks, image_url, source)
            VALUES (:s, :ph, :pos, :pid, :t, :b, :price, :rating, :fb, :img, 'search')
            ON DUPLICATE KEY UPDATE
              position=VALUES(position), title=VALUES(title), brand=VALUES(brand),
              price=VALUES(price), rating=VALUES(rating), feedbacks=VALUES(feedbacks),
              image_url=VALUES(image_url)
        """), {"s": nm_id, "ph": phrase, "pos": pos, "pid": pid,
               "t": p.get("name", ""), "b": p.get("brand", ""),
               "price": p.get("salePriceU", p.get("priceU", 0)),
               "rating": p.get("reviewRating", 0), "fb": p.get("feedbacks", 0), "img": img})
    if queue_id:
        if source == "compquery":
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
    elif not products and source != "compquery":
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
    return {"ok": True}


@router.post("/reset_enrich")
async def ext_reset_enrich(
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    cid = int(ext["company_id"])
    nm_id = (payload or {}).get("nm_id")
    try:
        nm_id = int(nm_id) if nm_id else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad nm_id")
    if nm_id:
        if not await _owns_card(db, cid, nm_id):
            raise HTTPException(status_code=403, detail="foreign nm_id")
        r = await db.execute(text("""
            UPDATE wb_enrich_queue q
            JOIN wb_competitor_cards c ON c.nm_id=q.nm_id
            SET q.status='pending'
            WHERE q.status IN ('error', 'processing') AND c.source_nm_id=:n AND (q.company_id=:c OR q.company_id IS NULL)
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
                UPDATE wb_seo_target SET status='pending'
                WHERE status='error' AND nmID=:n AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')})
            """), {"n": nm_id, "c2": cid})
        else:
            r = await db.execute(text(f"""
                UPDATE wb_seo_target SET status='pending'
                WHERE status='error' AND nmID IN ({OWNED_CARDS.replace(':cid', ':c2')})
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


@router.post("/position_bulk")
async def ext_position_bulk(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    ext: dict = Depends(require_ext_token),
):
    """Срезы позиций (только через расширение — WBAAS режет серверный cron, §10).
    Чужой source отбрасываем со счётчиком skipped."""
    cid = int(ext["company_id"])
    positions = (payload or {}).get("positions") or []
    owned_sources = {r for r in (await db.execute(
        text("SELECT nmID FROM wbcards WHERE company_id=:c"), {"c": cid})).scalars().all()}
    saved, skipped = 0, 0
    for r in positions:
        try:
            src = int(r.get("source_nm_id") or 0)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if src not in owned_sources:
            skipped += 1
            continue
        await db.execute(text("""
            INSERT INTO wb_competitor_position
              (source_nm_id, query_phrase, position, nm_id, title, brand, price, rating, feedbacks, image_url, collected_at)
            VALUES (:s, :ph, :pos, :n, :t, :b, :price, :rating, :fb, :img, COALESCE(:col, CURDATE()))
            ON DUPLICATE KEY UPDATE
              title=VALUES(title), brand=VALUES(brand), price=VALUES(price),
              rating=VALUES(rating), feedbacks=VALUES(feedbacks), image_url=VALUES(image_url)
        """), {"s": src, "ph": r.get("query_phrase"), "pos": r.get("position"), "n": r.get("nm_id"),
               "t": r.get("title", ""), "b": r.get("brand", ""), "price": r.get("price", 0),
               "rating": r.get("rating", 0), "fb": r.get("feedbacks", 0),
               "img": r.get("image_url", ""), "col": r.get("collected_at")})
        saved += 1
    await db.commit()
    return {"ok": True, "saved": saved, "skipped": skipped}


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
