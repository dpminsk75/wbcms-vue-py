"""Журнал вызовов ИИ: учёт токенов/стоимости по компаниям.

Одна строка = одна попытка к одной модели. Пишется из openrouter_service.chat()
(единая точка для обоих провайдеров). Отчёт — GROUP BY по журналу (агрегатов нет:
объём мал, цифры всегда актуальны).
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Группировки отчёта. Значения — SQL-выражения (в SELECT и GROUP BY — одинаково,
# иначе ONLY_FULL_GROUP_BY ругается).
GROUP_EXPR: dict[str, str] = {
    "day": "DATE(u.created_at)",
    "month": "DATE_FORMAT(u.created_at, '%Y-%m')",
    "model": "u.model",
    "provider": "u.provider",
    "scenario": "u.scenario",
    "company": "u.company_id",
    "user": "u.user_id",
}
GROUP_LABELS: dict[str, str] = {
    "day": "День",
    "month": "Месяц",
    "model": "Модель",
    "provider": "Провайдер",
    "scenario": "Сценарий",
    "company": "Компания",
    "user": "Сотрудник",
    "detail": "Детально (по вызовам)",
}
SCENARIO_LABELS: dict[str, str] = {
    "seo": "SEO-рекомендации",
    "competitor": "Анализ конкурента",
    "summary": "Сводка по конкурентам",
    "newcard_phrases": "Фразы (новый товар)",
    "newcard_generate": "Title+Description (новый товар)",
    "test": "Проба подключения",
    "other": "Прочее",
}
PREVIEW_CHARS = 800

# Если таблицы ещё нет (миграция не применена) — не мучаем БД на каждом вызове ИИ
_table_ok: bool | None = None


def _table_missing(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "1146" in msg or "doesn't exist" in msg or "не существует" in msg


def _empty_report(group_by: str) -> dict:
    return {
        "rows": [],
        "totals": {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                   "total_tokens": 0, "cost": 0.0, "failed": 0},
        "group_by": group_by,
        "group_labels": GROUP_LABELS,
        "scenario_labels": SCENARIO_LABELS,
        "models": [],
        "table_missing": True,
    }


def _http_status(http: str | None) -> int | None:
    try:
        return int(str(http or "").split(" ")[0])
    except (TypeError, ValueError):
        return None


async def record_usage(
    db: AsyncSession,
    *,
    company_id: int | None = None,
    user_id: int | None = None,
    provider: str = "openrouter",
    model: str | None = None,
    scenario: str = "other",
    nm_id: int | None = None,
    job_id: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost: float | None = None,
    preview: str | None = None,
    http: str | None = None,
    ok: bool = True,
    error: str | None = None,
) -> None:
    """Одна строка журнала. Ошибка записи не должна ломать основной поток."""
    global _table_ok
    if _table_ok is False:
        return
    try:
        p_tok = int(prompt_tokens or 0)
        c_tok = int(completion_tokens or 0)
        await db.execute(text("""
            INSERT INTO ai_usage (
              company_id, user_id, provider, model, scenario, nm_id, job_id,
              prompt_tokens, completion_tokens, total_tokens, cost, preview,
              http_status, ok, error
            ) VALUES (
              :c, :u, :p, :m, :s, :n, :j,
              :pt, :ct, :tt, :cost, :pv,
              :hs, :ok, :err
            )
        """), {
            "c": company_id, "u": user_id, "p": provider or "openrouter",
            "m": (model or "unknown")[:120], "s": scenario or "other",
            "n": nm_id, "j": job_id,
            "pt": p_tok, "ct": c_tok, "tt": p_tok + c_tok,
            "cost": float(cost or 0.0),
            "pv": (preview or "")[:PREVIEW_CHARS] or None,
            "hs": _http_status(http),
            "ok": 1 if ok else 0,
            "err": (error or "")[:500] or None,
        })
        await db.commit()
        _table_ok = True
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        if _table_missing(exc):
            _table_ok = False


def _where(date_from: str | None, date_to: str | None, company_id: int | None,
           scenario: str | None, provider: str | None, model: str | None,
           nm_id: int | None, user_id: int | None) -> tuple[str, dict]:
    """WHERE-собиралка: только безопасные параметры (значения — в :плейсхолдеры)."""
    cond: list[str] = []
    p: dict[str, Any] = {}
    if date_from:
        cond.append("u.created_at >= :df")
        p["df"] = f"{date_from} 00:00:00"
    if date_to:
        cond.append("u.created_at < :dt")
        p["dt"] = f"{date_to} 23:59:59"
    if company_id is not None:
        cond.append("u.company_id = :cid")
        p["cid"] = int(company_id)
    if scenario:
        cond.append("u.scenario = :sc")
        p["sc"] = scenario
    if provider:
        cond.append("u.provider = :pv")
        p["pv"] = provider
    if model:
        cond.append("u.model = :md")
        p["md"] = model
    if nm_id:
        cond.append("u.nm_id = :nm")
        p["nm"] = int(nm_id)
    if user_id:
        cond.append("u.user_id = :us")
        p["us"] = int(user_id)
    return (" AND ".join(cond) if cond else "1=1"), p


_TOTALS_SQL = """
    SELECT COUNT(*) AS calls,
           SUM(u.prompt_tokens) AS prompt_tokens,
           SUM(u.completion_tokens) AS completion_tokens,
           SUM(u.total_tokens) AS total_tokens,
           SUM(u.cost) AS cost,
           SUM(CASE WHEN u.ok = 0 THEN 1 ELSE 0 END) AS failed
    FROM ai_usage u WHERE {where}
"""


async def totals(db: AsyncSession, where: str, p: dict) -> dict:
    row = (await db.execute(text(_TOTALS_SQL.format(where=where)), p)).mappings().first()
    d = dict(row) if row else {}
    return {
        "calls": int(d.get("calls") or 0),
        "prompt_tokens": int(d.get("prompt_tokens") or 0),
        "completion_tokens": int(d.get("completion_tokens") or 0),
        "total_tokens": int(d.get("total_tokens") or 0),
        "cost": float(d.get("cost") or 0.0),
        "failed": int(d.get("failed") or 0),
    }


async def summary(
    db: AsyncSession,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    company_id: int | None = None,
    group_by: str = "model",
    scenario: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    nm_id: int | None = None,
    user_id: int | None = None,
    sort: str = "tokens",
    direction: str = "desc",
    limit: int = 500,
    offset: int = 0,
) -> dict:
    """Срез по журналу: строки + итоги. group_by='detail' — по вызовам."""
    where, p = _where(date_from, date_to, company_id, scenario, provider, model, nm_id, user_id)
    try:
        tot = await totals(db, where, p)
        if group_by == "detail":
            rows = (await db.execute(text(f"""
                SELECT u.id, DATE(u.created_at) AS day, u.created_at, u.company_id, u.user_id,
                       u.provider, u.model, u.scenario, u.nm_id, u.job_id,
                       u.prompt_tokens, u.completion_tokens, u.total_tokens, u.cost,
                       u.preview, u.http_status, u.ok, u.error,
                       us.username AS user_name, c.name AS company_name
                FROM ai_usage u
                LEFT JOIN `user` us ON us.id = u.user_id
                LEFT JOIN companies c ON c.id = u.company_id
                WHERE {where}
                ORDER BY u.created_at DESC
                LIMIT :lim OFFSET :off
            """), {**p, "lim": max(1, min(int(limit), 2000)), "off": max(0, int(offset))})).mappings().all()
            out_rows = [_row_out(r, detail=True) for r in rows]
        else:
            expr = GROUP_EXPR.get(group_by, GROUP_EXPR["model"])
            # выражение группировки в SELECT и GROUP BY — дословно одно и то же
            extra = ""
            join = ""
            if group_by == "company":
                join = " LEFT JOIN companies c ON c.id = u.company_id"
                extra = ", MAX(c.name) AS company_name"
            elif group_by == "user":
                join = " LEFT JOIN `user` us ON us.id = u.user_id"
                extra = ", MAX(us.username) AS user_name"
            rows = (await db.execute(text(f"""
                SELECT {expr} AS grp{extra},
                       COUNT(*) AS calls,
                       SUM(u.prompt_tokens) AS prompt_tokens,
                       SUM(u.completion_tokens) AS completion_tokens,
                       SUM(u.total_tokens) AS total_tokens,
                       SUM(u.cost) AS cost,
                       SUM(CASE WHEN u.ok = 0 THEN 1 ELSE 0 END) AS failed
                FROM ai_usage u{join}
                WHERE {where}
                GROUP BY {expr}
                ORDER BY {_order_expr(group_by, sort, direction)}
                LIMIT :lim OFFSET :off
            """), {**p, "lim": max(1, min(int(limit), 2000)), "off": max(0, int(offset))})).mappings().all()
            out_rows = [_row_out(r) for r in rows]
        models = (await db.execute(text(f"""
            SELECT DISTINCT u.model FROM ai_usage u WHERE {where} ORDER BY u.model LIMIT 200
        """), p)).scalars().all()
    except Exception as exc:
        await db.rollback()
        if _table_missing(exc):
            return _empty_report(group_by)
        raise
    return {
        "rows": out_rows,
        "totals": tot,
        "group_by": group_by,
        "group_labels": GROUP_LABELS,
        "scenario_labels": SCENARIO_LABELS,
        "models": list(models or []),
    }


def _order_expr(group_by: str, sort: str, direction: str) -> str:
    """ORDER BY по whitelist'у (значения — не из пользовательского ввода)."""
    d = "ASC" if str(direction).lower() == "asc" else "DESC"
    if sort == "tokens":
        return f"total_tokens {d}"
    if sort == "cost":
        return f"cost {d}"
    if sort == "calls":
        return f"calls {d}"
    if sort == "date" and group_by in ("day", "month"):
        return f"grp {d}"
    if group_by == "day":
        return f"grp {d}"
    return f"total_tokens {d}"


def _row_out(r, detail: bool = False) -> dict:
    d = dict(r)
    out = {
        "calls": int(d.get("calls") or 0),
        "prompt_tokens": int(d.get("prompt_tokens") or 0),
        "completion_tokens": int(d.get("completion_tokens") or 0),
        "total_tokens": int(d.get("total_tokens") or 0),
        "cost": float(d.get("cost") or 0.0),
        "failed": int(d.get("failed") or 0),
        "grp": d.get("grp"),
    }
    if d.get("company_name"):
        out["company_name"] = d["company_name"]
    if d.get("user_name"):
        out["user_name"] = d["user_name"]
    if detail:
        out.update({
            "id": d.get("id"),
            "created_at": d.get("created_at").isoformat() if hasattr(d.get("created_at"), "isoformat") else d.get("created_at"),
            "company_id": d.get("company_id"),
            "user_id": d.get("user_id"),
            "provider": d.get("provider"),
            "model": d.get("model"),
            "scenario": d.get("scenario"),
            "nm_id": d.get("nm_id"),
            "job_id": d.get("job_id"),
            "user_name": d.get("user_name") or "",
            "company_name": d.get("company_name") or "",
            "preview": d.get("preview") or "",
            "http_status": d.get("http_status"),
            "ok": bool(d.get("ok")),
            "error": d.get("error") or "",
        })
    return out


async def artifacts(db: AsyncSession, scenario: str, nm_id: int,
                    company_id: int | None = None) -> list[dict]:
    """«Что сгенерировали» — артефакт из таблицы сценария (полный текст).

    company_id — если задан, смотрим только артефакты своей компании.
    """
    cid = int(company_id) if company_id else None
    cid_sql = " AND company_id = :cid" if cid is not None else ""
    p: dict[str, Any] = {"n": int(nm_id)}
    if cid is not None:
        p["cid"] = cid
    try:
        if scenario == "seo":
            rows = (await db.execute(text(f"""
                SELECT id, nmID AS nm_id, model, old_title, new_title, new_description,
                       rationale, created_at
                FROM wb_seo_recommendation WHERE nmID=:n{cid_sql}
                ORDER BY id DESC LIMIT 5
            """), p)).mappings().all()
            return [{"type": "seo", "id": dict(r)["id"], "title": dict(r).get("new_title"),
                     "text": dict(r).get("new_description"),
                     "extra": {"old_title": dict(r).get("old_title"), "model": dict(r).get("model"),
                               "rationale": dict(r).get("rationale")},
                     "created_at": dict(r).get("created_at")} for r in rows]
        if scenario == "competitor":
            rows = (await db.execute(text(f"""
                SELECT id, competitor_nm_id, model, ai_result, created_at
                FROM wb_competitor_analysis WHERE source_nm_id=:n{cid_sql}
                ORDER BY id DESC LIMIT 5
            """), p)).mappings().all()
            return [{"type": "competitor", "id": dict(r)["id"],
                     "title": f"конкурент nm {dict(r).get('competitor_nm_id')}",
                     "text": dict(r).get("ai_result"),
                     "extra": {"model": dict(r).get("model")},
                     "created_at": dict(r).get("created_at")} for r in rows]
        if scenario == "summary":
            rows = (await db.execute(text(f"""
                SELECT id, model, suggested_title, suggested_description, created_at
                FROM wb_competitor_summary WHERE source_nm_id=:n{cid_sql}
                ORDER BY id DESC LIMIT 5
            """), p)).mappings().all()
            return [{"type": "summary", "id": dict(r)["id"],
                     "title": dict(r).get("suggested_title"),
                     "text": dict(r).get("suggested_description"),
                     "extra": {"model": dict(r).get("model")},
                     "created_at": dict(r).get("created_at")} for r in rows]
    except Exception:
        await db.rollback()
    return []
