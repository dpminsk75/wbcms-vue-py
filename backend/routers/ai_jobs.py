"""Вариант B: опрос фоновых AI-задач. Гейт — require_seo, чужую компанию не отдаём."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_user, require_seo
from backend.services import ai_job_service as jobs
from backend.services import auth_service

router = APIRouter(prefix="/api/ai-jobs", tags=["ai-jobs"])


@router.get("/{job_id}")
async def ai_job_status(
    job_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_seo),
):
    job = await jobs.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if not await auth_service.is_global_admin(db, user["id"]):
        mine = {c["id"] for c in await auth_service.get_user_companies(db, user["id"])}
        if (job.get("company_id") is not None) and (job["company_id"] not in mine):
            raise HTTPException(status_code=403, detail="job access denied")
    return job
