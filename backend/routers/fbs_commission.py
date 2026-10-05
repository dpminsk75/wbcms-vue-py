"""«FBS Комиссия» (/fbs-commission): скорость сборки в деньгах."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.fbs_commission_service import FbsCommissionService

router = APIRouter(prefix="/api/fbs/commission", tags=["fbs-commission"])


@router.get("/summary")
async def fbs_commission_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = FbsCommissionService(db, company_id=company_id)
    return await svc.summary(date_from, date_to, nm_id, brand, category)
