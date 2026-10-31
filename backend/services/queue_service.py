"""Управление очередями сбора — страница «Очередь» (26.10).

Скоуп согласован с пользователем:
- закладка «Сбор карточек» — `wb_enrich_queue` (режимы расширения /api/ext/next:
  new / refresh / all / watch);
- закладка «Сбор поисковой выдачи» — `/api/ext/search_next`: source=seo
  (`wb_seo_target`), compquery (`wb_competitor_query`), phrases
  (`wb_search_phrase_queue`); report — не очередь (неуправляемо), не показываем.

Действия: удалить из очереди (DELETE строки), добавить в очередь, вернуть в
очередь (pending), блокировать будущее добавление (`capture.is_hidden`, §19.4).
Скоуп — компания из шапки (`company_id`); глобальный админ видит всё.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import capture_service

LIMIT_MAX = 300

ENRICH_HID_COND = ("NOT EXISTS (SELECT 1 FROM wb_competitor_capture cap"
                   " WHERE cap.nm_id=q.nm_id AND cap.company_id=:cid"
                   " AND cap.is_hidden=1)")

# Статусы, которые реально видит/использует расширение
ENRICH_STATUSES = ("pending", "need_update", "processing", "done", "error", "gone")
SEARCH_STATUSES = ("pending", "processing", "done", "error")


def _inlist(pref: str, ids: list[int]) -> tuple[str, dict]:
    ph = ",".join(f":{pref}{i}" for i in range(len(ids)))
    return ph, {f"{pref}{i}": v for i, v in enumerate(ids)}


def _like(q: str) -> str:
    """Маска LIKE: % и _ в данных — литеральные, как на остальных страницах."""
    s = (q or "").strip()
    s = s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{s}%"


def enrich_owner_union(cols: str, extra_where: str = "", join: str = "") -> str:
    """Владелец строки очереди — 3 непересекающиеся ветки (UNION ALL).

    Было одним условием: (q.company_id=:cid OR q.company_id IS NULL OR
    q.status='need_update'). OR из трёх условий MySQL не сводит в один диапазон
    по индексу → фулл-скан wb_enrich_queue на КАЖДЫЙ опрос расширения
    (/api/ext/status поллится каждые 0.5–2 с — 72 с на запрос, БД встаёт).

    Ветки дают ровно тот же набор строк (строки разных компаний не пересекаются):
      1) свои строки компании;
      2) «ничьи» строки (company_id IS NULL);
      3) need_update чужих компаний — глобальный флаг «контент устарел».
    Каждая ветка берётся по индексу (company_id,status) или (source,status).
    """
    def br(cond: str) -> str:
        w = f"WHERE {cond}"
        if extra_where:
            w += f" AND {extra_where}"
        return f"SELECT {cols} FROM wb_enrich_queue q {join} {w}"
    return ("("
            + br("q.company_id = :cid")
            + " UNION ALL "
            + br("q.company_id IS NULL")
            + " UNION ALL "
            + br("q.status = 'need_update' AND q.company_id IS NOT NULL"
                 " AND q.company_id <> :cid")
            + ")")


def _src_cond(source: str) -> str:
    """Фильтр источника очереди: отражает режимы попапа (тексты про /status)."""
    s = (source or "").strip().lower()
    if s == "watch":
        return "q.source='watch'"
    if s == "all":
        return "1=1"
    # source — NOT NULL DEFAULT '' (миграция 20261035): «общая куча» это ровно
    # source='', а «='' OR IS NULL» ломало бы индекс по source.
    return "q.source=''"


async def enrich_counts(db: AsyncSession, cid: int | None, source: str = "") -> dict:
    """Счётчики «Сбора карточек» — той же логикой, что отдаёт /api/ext/status.

    cid IS NULL (глобальный админ) считаем все строки.
    source: '' (по умолчанию) — общая куча, 'watch' — SEO-мониторинг, 'all' — обе.
    """
    src_cond = _src_cond(source)
    params: dict = {}
    if cid is not None:
        params["cid"] = cid
    # владелец — 3 ветки UNION ALL (индексы вместо фулл-скана очереди)
    if cid is not None:
        cnt_sql = f"""
            SELECT t.status, COUNT(DISTINCT t.id) AS cnt
            FROM {enrich_owner_union('q.status AS status, q.id AS id',
                                     extra_where=f'q.nm_id > 0 AND {src_cond}')} t
            GROUP BY t.status
        """
    else:
        cnt_sql = f"""
            SELECT q.status, COUNT(*) AS cnt FROM wb_enrich_queue q
            WHERE q.nm_id > 0 AND {src_cond}
            GROUP BY q.status
        """
    rows = (await db.execute(text(cnt_sql), params)).mappings().all()
    counts = {r["status"]: int(r["cnt"]) for r in rows}
    hidden = 0
    if cid is not None:
        hidden = int((await db.execute(text(f"""
            SELECT COUNT(*) FROM wb_enrich_queue q
            JOIN wb_competitor_capture cap ON cap.nm_id=q.nm_id
                AND cap.company_id=:cid AND cap.is_hidden=1
            WHERE q.nm_id > 0 AND {src_cond}
        """), params)).scalar() or 0)
    counts["hidden"] = hidden
    counts["total"] = sum(v for k, v in counts.items() if k != "hidden")
    return counts


async def enrich_list(db: AsyncSession, cid: int | None, *, status: str = "",
                      q: str = "", hidden: bool = False, source: str = "",
                      limit: int = 50, offset: int = 0) -> dict:
    """Строки очереди сбора карточек + признаки для UI.

    source: '' — общая куча, 'watch' — очередь SEO-мониторинга, 'all' — обе
    (маппинг на фильтр «Очередь»; условия те же, что у /api/ext/next).
    hidden=True — показать только исключённые из сбора (блокировка, §19.4);
    иначе исключённые не показываем (их /next не отдаёт, счётчик — enrich_counts).
    """
    limit = int(limit or 0)
    # limit=0 — «Все» на странице (без LIMIT/OFFSET); иначе 1..LIMIT_MAX
    limit = max(1, min(limit, LIMIT_MAX)) if limit else 0
    offset = max(0, int(offset or 0))
    params: dict = {}
    if limit:
        params["lim"] = limit
        params["off"] = offset
    if cid is not None:
        params["cid"] = cid
    src_cond = _src_cond(source)
    where = ["q.nm_id > 0", src_cond]
    # владелец строки вынесен из WHERE в ветки UNION ALL (индексы вместо
    # фулл-скана очереди) — набор строк тот же
    owner_in_union = cid is not None
    if hidden:
        if cid is None:
            raise ValueError("Свои исключения есть только у компании — выберите её в шапке")
        # правило per-company: у админа своего «исключения» нет
        where.append("""EXISTS (SELECT 1 FROM wb_competitor_capture hcap
                              WHERE hcap.nm_id=q.nm_id AND hcap.company_id=:cid
                                AND hcap.is_hidden=1)""")
    elif cid is not None:
        where.append(ENRICH_HID_COND)
    else:
        params["cid"] = None  # для колонки is_hidden в SELECT (ниже)
        where.append("1=1")
    if status:
        where.append("q.status=:st")
        params["st"] = status
    if q.strip():
        params["like"] = _like(q)
        where.append("(CAST(q.nm_id AS CHAR) LIKE :like OR d.title LIKE :like"
                     " OR d.brand LIKE :like OR d.seller LIKE :like"
                     " OR pp.title LIKE :like OR pc.title LIKE :like)")
    base_where = " AND ".join(where)
    hidden_col = ("EXISTS (SELECT 1 FROM wb_competitor_capture hcap"
                  " WHERE hcap.nm_id=q.nm_id AND hcap.company_id=:cid"
                  " AND hcap.is_hidden=1) AS is_hidden") if cid is not None else "0 AS is_hidden"
    # Fallback title/brand/цены: details → последняя строка выдачи
    # (wb_competitor_position, индекс idx_position_company_nm) → wb_competitor_cards.
    pos_scope = "AND p2.company_id=:cid" if cid is not None else ""
    fb_joins = f"""
        LEFT JOIN wb_competitor_position pp ON pp.id = (
            SELECT p2.id FROM wb_competitor_position p2
            WHERE p2.nm_id=q.nm_id {pos_scope}
            ORDER BY p2.id DESC LIMIT 1)
        LEFT JOIN wb_competitor_cards pc ON pc.id = (
            SELECT c2.id FROM wb_competitor_cards c2
            WHERE c2.nm_id=q.nm_id
            ORDER BY c2.id DESC LIMIT 1)
    """
    page_sql = "LIMIT :lim OFFSET :off" if limit else ""
    item_cols = """q.id, q.nm_id, q.status, q.source, q.company_id AS owner_company_id,
               q.requested_at, q.claimed_at, q.processed_at,
               COALESCE(NULLIF(d.title,''),  NULLIF(pp.title,''),  NULLIF(pc.title,'')) AS title,
               COALESCE(NULLIF(d.brand,''),  NULLIF(pp.brand,''),  NULLIF(pc.brand,'')) AS brand,
               COALESCE(NULLIF(d.seller,''), NULLIF(pp.seller,'')) AS seller,
               COALESCE(NULLIF(d.price,0), NULLIF(pp.price,0), NULLIF(pc.price,0)) AS price,
               {hidden_col}"""
    joins = (f"LEFT JOIN wb_competitor_details d ON d.nm_id=q.nm_id {fb_joins}")
    if owner_in_union:
        union = enrich_owner_union(item_cols, extra_where=base_where, join=joins)
        lean_union = enrich_owner_union("q.id AS id", extra_where=base_where, join=joins)
        items_sql = f"""
            SELECT * FROM ({union}) t
            ORDER BY t.status='pending' DESC, t.status='need_update' DESC, t.id
            {page_sql}
        """
        total_sql = f"SELECT COUNT(*) FROM ({lean_union}) t"
    else:
        items_sql = f"""
            SELECT {item_cols}
            FROM wb_enrich_queue q
            {joins}
            WHERE {base_where}
            ORDER BY q.status='pending' DESC, q.status='need_update' DESC, q.id
            {page_sql}
        """
        total_sql = f"""
            SELECT COUNT(*) FROM wb_enrich_queue q
            {joins}
            WHERE {base_where}
        """
    items = (await db.execute(text(items_sql), params)).mappings().all()
    total = int((await db.execute(text(total_sql),
                                  {k: v for k, v in params.items()
                                   if k not in ("lim", "off")})).scalar() or 0)
    return {"items": [dict(r) for r in items], "total": total,
            "limit": limit, "offset": offset}


async def enrich_delete(db: AsyncSession, cid: int | None, queue_id: int) -> int:
    """Удалить строку очереди. Скоуп: владелец или NULL-строка (ничей).

    Сам seeded вернёт карточку при следующем засеве — честно отражаем в UI.
    """
    cond = "AND (company_id=:cid OR company_id IS NULL)" if cid is not None else ""
    params: dict = {"i": queue_id}
    if cid is not None:
        params["cid"] = cid
    r = await db.execute(text(f"""
        DELETE FROM wb_enrich_queue WHERE id=:i {cond}
    """), params)
    await db.commit()
    return int(r.rowcount or 0)


async def enrich_requeue(db: AsyncSession, cid: int | None, queue_id: int) -> dict:
    """Вернуть строку в ожидание: done/error/gone → pending."""
    cond_owner = "AND (company_id=:cid OR company_id IS NULL)" if cid is not None else ""
    params: dict = {"i": queue_id}
    if cid is not None:
        params["cid"] = cid
    r = await db.execute(text(f"""
        UPDATE wb_enrich_queue
        SET status='pending', claimed_at=NULL
        WHERE id=:i {cond_owner}
          AND status IN ('done', 'error', 'gone', 'need_update')
    """), params)
    await db.commit()
    if not r.rowcount:
        raise ValueError("Строка не найдена или в работе")
    return {"ok": True}


async def enrich_add(db: AsyncSession, cid: int, nm_id: int) -> dict:
    """Добавить конкурента в очередь сбора.

    Права: только свои карточки-конкуренты (source_nm_id в OUR карточках).
    Заблокированные (is_hidden) не добавляем — «блокировать будущее добавление».
    """
    if cid is None:
        raise ValueError("Выберите компанию в шапке")
    if nm_id <= 0:
        raise ValueError("bad nm_id")
    ok = (await db.execute(text("""
        SELECT 1 FROM wb_competitor_cards c
        WHERE c.nm_id=:n
          AND c.source_nm_id IN (SELECT nmID FROM wbcards WHERE company_id=:cid)
        LIMIT 1
    """), {"n": nm_id, "cid": cid})).first()
    if not ok:
        raise ValueError("Карточка не является конкурентом ваших карточек")
    if await capture_service.is_excluded(db, cid, nm_id):
        raise ValueError("Карточка исключена из сбора — сначала разблокируйте")
    await db.execute(text("""
        INSERT INTO wb_enrich_queue (nm_id, company_id, status)
        VALUES (:n, :cid, 'pending')
        ON DUPLICATE KEY UPDATE
          status=IF(status IN ('done','error','gone'), 'pending', status)
    """), {"n": nm_id, "cid": cid})
    await db.commit()
    return {"ok": True}


async def enrich_block(db: AsyncSession, cid: int, nm_id: int, hidden: bool,
                       user_id: int | None = None) -> dict:
    """Блокировать/разблокировать будущее добавление (§19.4: capture.is_hidden).

    Разблокировка per-company; блокировка тоже per-company. Содержимое карточки
    (кэш, история) не трогаем.
    """
    if cid is None:
        raise ValueError("Выберите компанию в шапке")
    res = await capture_service.set_hidden(db, cid, nm_id, hidden, user_id)
    await db.commit()
    return res


async def _owns_our_card(db: AsyncSession, cid: int, source_nm_id: int) -> None:
    ok = (await db.execute(text(
        "SELECT 1 FROM wbcards WHERE nmID=:n AND company_id=:cid LIMIT 1"
    ), {"n": int(source_nm_id or 0), "cid": cid})).first()
    if not ok:
        raise ValueError("Карточка не ваша")


async def enrich_competitors_count(db: AsyncSession, cid: int,
                                   source_nm_id: int) -> dict:
    """Сколько конкурентов у нашей карточки — для кнопки «Добавить (N)»."""
    if cid is None:
        raise ValueError("Выберите компанию в шапке")
    await _owns_our_card(db, cid, source_nm_id)
    row = (await db.execute(text("""
        SELECT COUNT(DISTINCT c.nm_id) AS cnt,
               COUNT(DISTINCT CASE WHEN cap.is_hidden=1 THEN c.nm_id END) AS hidden
        FROM wb_competitor_cards c
        LEFT JOIN wb_competitor_capture cap
          ON cap.nm_id=c.nm_id AND cap.company_id=:cid
        WHERE c.source_nm_id=:n AND c.nm_id > 0
    """), {"n": int(source_nm_id), "cid": cid})).mappings().first()
    return {"count": int(row["cnt"] or 0), "hidden": int(row["hidden"] or 0)}


async def enrich_seed(db: AsyncSession, cid: int, source_nm_id: int) -> dict:
    """Конкуренты нашей карточки → очередь, как seed расширения (/queue/seed).

    Без дублей и без 24ч-правила: сеем тех, кого нет в очереди; собранные
    раньше в pending автоматически не возвращаем (как в ext-сидировании —
    обновление назначается руками). Скрытые (is_hidden) не сеются.
    """
    if cid is None:
        raise ValueError("Выберите компанию в шапке")
    n = int(source_nm_id or 0)
    await _owns_our_card(db, cid, n)
    cnt = (await db.execute(text("""
        SELECT COUNT(DISTINCT c.nm_id) AS cnt,
               COUNT(DISTINCT CASE WHEN cap.is_hidden=1 THEN c.nm_id END) AS hidden
        FROM wb_competitor_cards c
        LEFT JOIN wb_competitor_capture cap
          ON cap.nm_id=c.nm_id AND cap.company_id=:cid
        WHERE c.source_nm_id=:n AND c.nm_id > 0
    """), {"n": n, "cid": cid})).mappings().first()
    checked = int(cnt["cnt"] or 0)
    hidden_cnt = int(cnt["hidden"] or 0)
    # Нулевые артикулы не сеем и скрытых не трогаем — тот же SQL, что в ext.py
    r = await db.execute(text("""
        INSERT INTO wb_enrich_queue (nm_id, company_id)
        SELECT DISTINCT wc.nm_id, :cid FROM wb_competitor_cards wc
        WHERE wc.source_nm_id=:s
          AND wc.nm_id > 0
          AND wc.nm_id NOT IN (SELECT nm_id FROM wb_enrich_queue)
          AND NOT EXISTS (SELECT 1 FROM wb_competitor_capture cap
                          WHERE cap.nm_id=wc.nm_id
                            AND cap.company_id=:cid AND cap.is_hidden=1)
        ON DUPLICATE KEY UPDATE
          company_id=IF(company_id IS NULL, :cid, company_id)
    """), {"s": n, "cid": cid})
    added = int(r.rowcount or 0)
    await db.commit()
    return {"checked": checked, "added": added,
            "skipped_hidden": hidden_cnt,
            "already": max(checked - hidden_cnt - added, 0)}


# ---------- Сбор поисковой выдачи ----------

async def search_counts(db: AsyncSession, cid: int | None) -> dict:
    """Статусы по каждому источнику (как видел бы /api/ext/search_next)."""
    out: dict[str, dict] = {}
    seo_cond = ("""AND s.nmID IN (SELECT nmID FROM wbcards WHERE company_id=:cid)"""
                if cid is not None else "")
    params_seo = {"cid": cid} if cid is not None else {}
    rows = (await db.execute(text(f"""
        SELECT s.status, COUNT(*) AS cnt FROM wb_seo_target s WHERE 1=1 {seo_cond}
        GROUP BY s.status
    """), params_seo)).mappings().all()
    out["seo"] = {r["status"]: int(r["cnt"]) for r in rows}
    for src, table in (("compquery", "wb_competitor_query"),
                       ("phrases", "wb_search_phrase_queue")):
        cond = "WHERE company_id=:cid" if cid is not None else ""
        params = {"cid": cid} if cid is not None else {}
        rows = (await db.execute(text(f"""
            SELECT status, COUNT(*) AS cnt FROM {table} {cond} GROUP BY status
        """), params)).mappings().all()
        out[src] = {r["status"]: int(r["cnt"]) for r in rows}
    return out


async def search_list(db: AsyncSession, cid: int | None, source: str, *,
                      status: str = "", q: str = "",
                      limit: int = 50, offset: int = 0) -> dict:
    """Строки очереди поисковой выдачи по источнику seo/compquery/phrases/all.

    'all' — режим «Все» на странице: единый список трёх управляемых очередей
    (UNION ALL, в каждой строке src — её очередь для кнопок вернуться/удалить).
    report («ТОП-20») в списке не участвует — собирается на лету, очереди нет.
    """
    src = (source or "").strip().lower()
    if src not in ("seo", "compquery", "phrases", "all"):
        raise ValueError("source must be seo|compquery|phrases|all")
    limit = int(limit or 0)
    # limit=0 — «Все» на странице (без LIMIT/OFFSET); иначе 1..LIMIT_MAX
    limit = max(1, min(limit, LIMIT_MAX)) if limit else 0
    offset = max(0, int(offset or 0))
    page_sql = "LIMIT :lim OFFSET :off" if limit else ""
    params: dict = {"like": _like(q)}
    if limit:
        params["lim"] = limit
        params["off"] = offset
    if cid is not None:
        params["cid"] = cid
    if status:
        params["st"] = status

    def _cond(key: str) -> str:
        """Условия одной таблицы: компания-скоуп + статус + поиск по фразе."""
        c: list[str] = []
        if cid is not None:
            if key == "seo":
                c.append("t.nmID IN (SELECT nmID FROM wbcards WHERE company_id=:cid)")
            else:
                c.append("t.company_id=:cid")
        if status:
            c.append("t.status=:st")
        c.append("t.query_phrase LIKE :like" if key == "phrases" else "t.phrase LIKE :like")
        return " AND ".join(c)

    if src == "all":
        sel_seo = f"""
            SELECT 'seo' AS src, t.id, t.nmID AS nm_id, t.phrase AS phrase,
                   t.is_active, t.priority, t.status, t.updated_at
            FROM wb_seo_target t WHERE {_cond('seo')}
        """
        sel_cq = f"""
            SELECT 'compquery' AS src, t.id, t.source_nm_id AS nm_id,
                   t.phrase AS phrase, t.is_active, t.priority, t.status,
                   t.updated_at
            FROM wb_competitor_query t WHERE {_cond('compquery')}
        """
        sel_ph = f"""
            SELECT 'phrases' AS src, t.id, t.source_nm_id AS nm_id,
                   t.query_phrase AS phrase, NULL AS is_active, t.priority,
                   t.status, t.updated_at
            FROM wb_search_phrase_queue t WHERE {_cond('phrases')}
        """
        sql = f"""
            SELECT * FROM ({sel_seo} UNION ALL {sel_cq} UNION ALL {sel_ph}) u
            ORDER BY u.status='pending' DESC, u.updated_at DESC, u.id DESC
            {page_sql}
        """
        cond_params = {k: v for k, v in params.items() if k not in ("lim", "off")}
        total = 0
        for key, table in (("seo", "wb_seo_target"),
                           ("compquery", "wb_competitor_query"),
                           ("phrases", "wb_search_phrase_queue")):
            total += int((await db.execute(
                text(f"SELECT COUNT(*) FROM {table} t WHERE {_cond(key)}"),
                cond_params)).scalar() or 0)
        items = (await db.execute(text(sql), params)).mappings().all()
        return {"source": "all", "items": [dict(r) for r in items],
                "total": total, "limit": limit, "offset": offset}

    # алиас: у seo строки собираются во вложенном подзапросе с алиасом t0
    ali = "t0" if src == "seo" else "t"
    where: list[str] = []
    if cid is not None:
        params["cid"] = cid
        if src == "seo":
            where.append(f"{ali}.nmID IN (SELECT nmID FROM wbcards WHERE company_id=:cid)")
        else:
            where.append(f"{ali}.company_id=:cid")
    if status:
        where.append(f"{ali}.status=:st")
        params["st"] = status
    if src == "phrases":
        where.append(f"{ali}.query_phrase LIKE :like")
    else:
        where.append(f"{ali}.phrase LIKE :like")
    cond = " AND ".join(where) if where else "1=1"
    if src == "seo":
        sql = f"""
            SELECT t.id, t.nmID AS nm_id, t.phrase, t.is_active, t.priority,
                   t.status, t.updated_at, SUM(t.active_cnt) AS active_cnt
            FROM (
                SELECT t0.id, t0.nmID, t0.phrase, t0.is_active, t0.priority,
                       t0.status, t0.updated_at,
                       (SELECT COUNT(*) FROM wb_seo_target t2
                        WHERE t2.nmID=t0.nmID AND t2.is_active=1) AS active_cnt
                FROM wb_seo_target t0 WHERE {cond}
            ) t
            GROUP BY t.id ORDER BY t.status='pending' DESC, t.id
            {page_sql}
        """
        total_sql = f"SELECT COUNT(*) FROM wb_seo_target t0 WHERE {cond}"
    elif src == "compquery":
        sql = f"""
            SELECT t.id, t.source_nm_id AS nm_id, t.phrase, t.status,
                   t.is_active, t.priority, t.updated_at
            FROM wb_competitor_query t
            WHERE {cond}
            ORDER BY t.status='pending' DESC, t.id
            {page_sql}
        """
        total_sql = f"SELECT COUNT(*) FROM wb_competitor_query t WHERE {cond}"
    else:
        sql = f"""
            SELECT t.id, t.source_nm_id AS nm_id, t.query_phrase AS phrase,
                   t.status, t.priority, t.updated_at
            FROM wb_search_phrase_queue t
            WHERE {cond}
            ORDER BY t.status='pending' DESC, t.id
            {page_sql}
        """
        total_sql = f"SELECT COUNT(*) FROM wb_search_phrase_queue t WHERE {cond}"
    items = (await db.execute(text(sql), params)).mappings().all()
    total = int((await db.execute(text(total_sql),
                                  {k: v for k, v in params.items()
                                   if k not in ("lim", "off")})).scalar() or 0)
    return {"source": src, "items": [dict(r) for r in items], "total": total,
            "limit": limit, "offset": offset}


async def search_delete(db: AsyncSession, cid: int | None, source: str,
                        queue_id: int) -> int:
    src = (source or "").strip().lower()
    if src not in ("seo", "compquery", "phrases"):
        raise ValueError("source must be seo|compquery|phrases")
    params: dict = {"i": queue_id}
    if src == "seo":
        cond = (""" AND t.nmID IN (SELECT nmID FROM wbcards WHERE company_id=:cid)"""
                if cid is not None else "")
        if cid is not None:
            params["cid"] = cid
        sql = f"DELETE t FROM wb_seo_target t WHERE t.id=:i {cond}"
    else:
        table = "wb_competitor_query" if src == "compquery" else "wb_search_phrase_queue"
        cond = " AND t.company_id=:cid" if cid is not None else ""
        if cid is not None:
            params["cid"] = cid
        sql = f"DELETE t FROM {table} t WHERE t.id=:i {cond}"
    r = await db.execute(text(sql), params)
    await db.commit()
    return int(r.rowcount or 0)


async def search_requeue(db: AsyncSession, cid: int | None, source: str,
                         queue_id: int) -> dict:
    src = (source or "").strip().lower()
    if src not in ("seo", "compquery", "phrases"):
        raise ValueError("source must be seo|compquery|phrases")
    params: dict = {"i": queue_id}
    now = "NOW()"
    if src == "seo":
        cond = (""" AND t.nmID IN (SELECT nmID FROM wbcards WHERE company_id=:cid)"""
                if cid is not None else "")
        if cid is not None:
            params["cid"] = cid
        sql = (f"UPDATE wb_seo_target t SET t.status='pending', t.updated_at={now} "
               f"WHERE t.id=:i AND t.status IN ('done','error') {cond}")
    else:
        if cid is not None:
            params["cid"] = cid
            cond = "AND t.company_id=:cid"
        else:
            cond = ""
        table = "wb_competitor_query" if src == "compquery" else "wb_search_phrase_queue"
        sql = (f"UPDATE {table} t SET t.status='pending', t.updated_at={now} "
               f"WHERE t.id=:i AND t.status IN ('done','error') {cond}")
    r = await db.execute(text(sql), params)
    await db.commit()
    if not r.rowcount:
        raise ValueError("Строка не найдена или уже в сборе")
    return {"ok": True}


async def search_add(db: AsyncSession, cid: int, source: str, *,
                     nm_id: int, phrase: str, priority: int = 0,
                     user_id: int | None = None) -> dict:
    """Добавить в очередь выдачи: seo — целевая фраза; compquery — запрос
    конкурентов (source_nm_id = наша карточка); phrases — фраза на пересборку
    выдачи (source_nm_id = наша карточка)."""
    src = (source or "").strip().lower()
    if src not in ("seo", "compquery", "phrases"):
        raise ValueError("source must be seo|compquery|phrases")
    if cid is None:
        raise ValueError("Выберите компанию в шапке")
    ph = (phrase or "").strip()[:190]
    if not ph:
        raise ValueError("Фраза обязательна")
    n = int(nm_id or 0)
    if src == "seo":
        if n <= 0:
            raise ValueError("nmID нашей карточки обязателен")
        ok = (await db.execute(text(
            "SELECT 1 FROM wbcards WHERE nmID=:n AND company_id=:cid LIMIT 1"
        ), {"n": n, "cid": cid})).first()
        if not ok:
            raise ValueError("Карточка не ваша")
        # wb_seo_target — таблица без гарантированного UNIQUE(nmID, phrase):
        # ищем существующую строку и обновляем, как это делает seo-service.
        cur = (await db.execute(text(
            "SELECT id, is_active, status FROM wb_seo_target "
            "WHERE nmID=:n AND phrase=:p ORDER BY id LIMIT 1"
        ), {"n": n, "p": ph})).mappings().first()
        if cur:
            await db.execute(text("""
                UPDATE wb_seo_target SET is_active=1, priority=:pr,
                    updated_at=NOW(),
                    status=IF(status IN ('done','error'), 'pending', status)
                WHERE id=:i
            """), {"i": cur["id"], "pr": int(priority or 0)})
        else:
            await db.execute(text("""
                INSERT INTO wb_seo_target (nmID, phrase, priority, is_active, added_by, created_at, updated_at, status)
                VALUES (:n, :p, :pr, 1, :uid, NOW(), NOW(), 'pending')
            """), {"n": n, "p": ph, "pr": int(priority or 0), "uid": user_id})
    elif src == "compquery":
        if n <= 0:
            raise ValueError("nmID нашей карточки обязателен")
        ok = (await db.execute(text(
            "SELECT 1 FROM wbcards WHERE nmID=:n AND company_id=:cid LIMIT 1"
        ), {"n": n, "cid": cid})).first()
        if not ok:
            raise ValueError("Карточка не ваша")
        await db.execute(text("""
            INSERT INTO wb_competitor_query
              (source_nm_id, phrase, priority, is_active, company_id, status)
            VALUES (:n, :p, :pr, 1, :cid, 'pending') AS new
            ON DUPLICATE KEY UPDATE is_active=1, priority=new.priority,
              status=IF(status IN ('done','error'), 'pending', status), updated_at=NOW()
        """), {"n": n, "p": ph, "pr": int(priority or 0), "cid": cid})
    else:
        # phrases: наша карточка может быть не указана (фраза без привязки) —
        # расширение такие обрабатывает (source_nm_id хранится как есть)
        await db.execute(text("""
            INSERT INTO wb_search_phrase_queue
              (company_id, query_phrase, source_nm_id, priority, status, source, created_by)
            VALUES (:cid, :p, :n, :pr, 'pending', 'manual', :uid)
            ON DUPLICATE KEY UPDATE
              status=IF(status IN ('done','error'), 'pending', status),
              updated_at=NOW(), source_nm_id=COALESCE(NULLIF(:n,0), source_nm_id)
        """), {"cid": cid, "p": ph, "n": n, "pr": int(priority or 0), "uid": user_id})
    await db.commit()
    return {"ok": True}
