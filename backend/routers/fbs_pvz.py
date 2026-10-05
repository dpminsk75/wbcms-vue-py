"""«FBS Путь до ПВЗ» (/fbs-pvz): отрезки пути заказа до пункта выдачи."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.fbs_pvz_service import FbsPvzService

router = APIRouter(prefix="/api/fbs/pvz", tags=["fbs-pvz"])


@router.get("/summary")
async def fbs_pvz_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    top_dirs: int = Query(default=7, ge=0, le=100),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = FbsPvzService(db, company_id=company_id)
    return await svc.summary(date_from, date_to, nm_id, brand, category, top_dirs)
