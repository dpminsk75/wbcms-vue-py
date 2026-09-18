"""Вариант B: фоновые AI-задачи (job + items) с опросом статуса.

Фронт: POST запускает job → {job_id}, поллит GET /api/ai-jobs/{id} (раз в 2с),
у pending/processing записей крутит лоадер. Воркер — FastAPI BackgroundTasks
поверх async OpenRouter-вызовов (to_thread, loop свободен).
Рестарт между делом: running/queued при старте помечаются interrupted (main.startup).
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

KINDS = ("competitor_analyze_all", "seo_process")


async def create_job(db: AsyncSession, *, company_id: int | None, kind: str,
                     nm_id: int | None, items: list[dict], created_by: int | None) -> int:
    if kind not in KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    await db.rollback()  # сбрасываем autobegin от deps перед begin (как в companies.py)
    async with db.begin():
        await db.execute(text("""
            INSERT INTO ai_job (company_id, kind, nm_id, status, total, done, created_by)
            VALUES (:c, :k, :n, 'queued', :t, 0, :u)
        """), {"c": company_id, "k": kind, "n": nm_id, "t": len(items), "u": created_by})
        job_id = (await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()
        for it in items:
            await db.execute(text("""
                INSERT INTO ai_job_item (job_id, label, ref_id, status)
                VALUES (:j, :label, :ref, 'pending')
            """), {"j": int(job_id), "label": it.get("label"), "ref": it.get("ref_id")})
    return int(job_id)


async def get_job(db: AsyncSession, job_id: int) -> dict | None:
    job = (await db.execute(
        text("SELECT * FROM ai_job WHERE id=:j LIMIT 1"), {"j": job_id}
    )).mappings().first()
    if not job:
        return None
    try:
        items = (await db.execute(
            text("SELECT id, label, ref_id, status, result, error, note FROM ai_job_item WHERE job_id=:j ORDER BY id"),
            {"j": job_id},
        )).mappings().all()
    except Exception:
        await db.rollback()  # колонки note ещё нет (миграция не применена)
        items = (await db.execute(
            text("SELECT id, label, ref_id, status, result, error FROM ai_job_item WHERE job_id=:j ORDER BY id"),
            {"j": job_id},
        )).mappings().all()
    out = dict(job)
    for k in ("created_at", "updated_at"):
        if hasattr(out.get(k), "isoformat"):
            out[k] = out[k].isoformat()
    out["items"] = [dict(i) for i in items]
    return out


async def _set(db: AsyncSession, sql: str, params: dict) -> None:
    await db.execute(text(sql), params)
    await db.commit()


async def run_job(job_id: int) -> None:
    """BackgroundTasks-цель: прогоняет items через handler вида, финализирует job."""
    from backend.database import SessionLocal
    async with SessionLocal() as db:
        job = await get_job(db, job_id)
        if not job or job["status"] not in ("queued", "running"):
            return
        await _set(db, "UPDATE ai_job SET status='running' WHERE id=:j", {"j": job_id})
        handler_name = {"competitor_analyze_all": ("backend.services.competitor_service",
                                                  "execute_analyze_job"),
                          "seo_process": ("backend.services.seo_service",
                                          "execute_process_job")}.get(job["kind"])
        if not handler_name:
            await _set(db, "UPDATE ai_job SET status='error', error='no handler' WHERE id=:j", {"j": job_id})
            return
        mod_name, fn_name = handler_name
        import importlib
        handler = getattr(importlib.import_module(mod_name), fn_name)
        try:
            await handler(job_id, db)
        except Exception as exc:
            await db.rollback()
            await _set(db, "UPDATE ai_job SET status='error', error=:e WHERE id=:j",
                       {"e": f"{type(exc).__name__}: {exc}"[:500], "j": job_id})
            return
        job = await get_job(db, job_id)
        failed = sum(1 for i in job["items"] if i["status"] == "error")
        if failed >= len(job["items"]) and job["items"]:
            await _set(db, "UPDATE ai_job SET status='error', error='all items failed' WHERE id=:j", {"j": job_id})
        else:
            await _set(db, "UPDATE ai_job SET status='done', error=:e WHERE id=:j",
                       {"e": f"{failed} failed" if failed else None, "j": job_id})


async def recover_interrupted() -> int:
    """При старте: зависшие queued/running → interrupted (таблицы может не быть — молча 0)."""
    try:
        from backend.database import SessionLocal
        async with SessionLocal() as db:
            r = await db.execute(text(
                "UPDATE ai_job SET status='interrupted' WHERE status IN ('queued','running')"))
            await db.commit()
            return int(r.rowcount or 0)
    except Exception:
        return 0
