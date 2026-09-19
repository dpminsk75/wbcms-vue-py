"""Админка wb_seo_model + apply-model (§9.1/§9.2, решения §11): только require_admin.

Ротацию пишут воркеры через mark_model (приоритет/кулдауны/счётчики/авто-off),
bench_models.py — зондирование. Тут — чтение и ручные правки: вкл/выкл, приоритет,
сброс кулдауна, замена дохлых моделей во всех companies одной кнопкой.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import require_admin

router = APIRouter(prefix="/api/admin/seo-models", tags=["admin-seo-models"])


def _row_to_out(r) -> dict:
    d = dict(r)
    for k in ("cooldown_until", "last_success_at", "last_429_at", "created_at", "updated_at"):
        if hasattr(d.get(k), "isoformat"):
            d[k] = d[k].isoformat()
    if "is_active" in d:
        d["is_active"] = bool(d["is_active"])
    return d


@router.get("")
async def seo_models_list(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> list[dict]:
    try:
        rows = (await db.execute(text("""
            SELECT * FROM wb_seo_model ORDER BY priority, id
        """))).mappings().all()
    except Exception:
        await db.rollback()
        return []  # таблицы ещё нет — пусто, не 500
    return [_row_to_out(r) for r in rows]


@router.patch("/{model_id:path}")
async def seo_model_patch(
    model_id: str = Path(...),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> dict:
    """Ручные правки поверх авто-приоритетов bench: is_active и/или priority (1..200)."""
    data = payload or {}
    sets: dict = {}
    if "is_active" in data and data["is_active"] is not None:
        sets["is_active"] = 1 if data["is_active"] else 0
    if "priority" in data and data["priority"] is not None:
        try:
            p = int(data["priority"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="bad priority")
        if not 1 <= p <= 200:
            raise HTTPException(status_code=400, detail="priority must be 1..200")
        sets["priority"] = p
    if not sets:
        raise HTTPException(status_code=400, detail="nothing to update")
    sets["m"] = model_id
    await db.rollback()
    async with db.begin():
        r = await db.execute(text(f"""
            UPDATE wb_seo_model SET {", ".join(f"{k}=:{k}" for k in sets if k != "m")},
              updated_at=NOW() WHERE model_id=:m
        """), sets)
        if not r.rowcount:
            raise HTTPException(status_code=404, detail="model not found")
        row = (await db.execute(text("""
            SELECT * FROM wb_seo_model WHERE model_id=:m LIMIT 1
        """), {"m": model_id})).mappings().first()
    return _row_to_out(row)


@router.post("/{model_id:path}/reset-cooldown")
async def seo_model_reset_cooldown(
    model_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> dict:
    await db.rollback()
    async with db.begin():
        r = await db.execute(text("""
            UPDATE wb_seo_model SET consecutive_errors=0, cooldown_until=NULL, updated_at=NOW()
            WHERE model_id=:m
        """), {"m": model_id})
        if not r.rowcount:
            raise HTTPException(status_code=404, detail="model not found")
    return {"ok": True, "model_id": model_id}


@router.post("/apply")
async def seo_models_apply(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> dict:
    """Порт actionApplyModel (без telegram-части): заменить дохлые части companies.seo_model
    на новую рабочую модель. Чиним только компании с дохлыми частями списка; части,
    неизвестные таблице, не трогаем (консервативно). dry_run — предпросмотр без записи.

    NB: выведено из описания md (:346-365); при доступе сверить с SeoController дословно.
    """
    model_id = str((payload or {}).get("model_id") or "").strip()
    dry_run = bool((payload or {}).get("dry_run"))
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id required")
    rows = (await db.execute(text("""
        SELECT model_id, is_active FROM wb_seo_model
    """))).mappings().all()
    active = {r["model_id"]: bool(r["is_active"]) for r in rows}
    if model_id not in active:
        raise HTTPException(status_code=404, detail="model unknown: run bench first")
    companies = (await db.execute(text("""
        SELECT id, seo_model FROM companies
        WHERE seo_model IS NOT NULL AND seo_model != ''
    """))).mappings().all()
    changed: list[dict] = []
    for c in companies:
        parts = [p.strip() for p in str(c["seo_model"]).split(",") if p.strip()]
        dead = {p for p in parts if active.get(p) is False}
        if not dead:
            continue
        out: list[str] = []
        for p in parts:
            if p in dead:
                if model_id not in out:
                    out.append(model_id)
            elif p not in out:
                out.append(p)
        new_s = ", ".join(out)
        if new_s == str(c["seo_model"]):
            continue
        changed.append({"company_id": c["id"], "old": str(c["seo_model"]), "new": new_s})
    if not dry_run and changed:
        await db.rollback()
        async with db.begin():
            for ch in changed:
                await db.execute(text("""
                    UPDATE companies SET seo_model=:s WHERE id=:c
                """), {"s": ch["new"], "c": ch["company_id"]})
    return {"model_id": model_id, "replaced": 0 if dry_run else len(changed),
            "dry_run": dry_run, "companies": changed if dry_run else [c["company_id"] for c in changed]}
