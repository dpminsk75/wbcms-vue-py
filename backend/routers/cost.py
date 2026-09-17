"""Импорт себестоимости — порт CostImportController."""
from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_current_company
from backend.services.cost_service import CostService

router = APIRouter(prefix="/api/cost-import", tags=["cost-import"])


class CostItem(BaseModel):
    nmID: str | int
    price: str | float
    chrtID: str | int | None = None
    sku: str | None = None


class CostSaveIn(BaseModel):
    date: str
    items: list[CostItem]


class CostPreviewIn(BaseModel):
    date: str
    rows: list[list]


@router.get("/list")
async def cost_list(
    date_from: str = Query(...),
    date_to: str = Query(...),
    nm_id: int | None = Query(default=None, alias="nm_id"),
    sku: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = CostService(db)
    return await svc.list_costs(date_from, date_to, nm_id, sku)


@router.post("/save")
async def cost_save(payload: CostSaveIn, db: AsyncSession = Depends(get_db)):
    svc = CostService(db)
    try:
        processed = await svc.save_many(payload.date, [i.model_dump() for i in payload.items])
    except ValueError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "processed": processed, "message": f"Сохранено позиций: {processed}"}


@router.post("/preview")
async def cost_preview(payload: CostPreviewIn, db: AsyncSession = Depends(get_db)):
    """Тестовый режим: резолв сырых строк Excel без записи (dry-run, видно новая/перезапись)."""
    svc = CostService(db)
    return await svc.preview_rows(payload.date, payload.rows)


@router.post("/update-price")
async def cost_update_price(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    svc = CostService(db)
    try:
        data = await svc.update_row(
            int(payload.get("id") or 0),
            payload.get("price"),
            payload.get("load_date"),
        )
    except ValueError as e:
        return {"success": False, "message": str(e)}
    except LookupError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, **data}


@router.get("/missing")
async def cost_missing(
    date_from: str = Query(...),
    date_to: str = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    """Зерно (nmID/chrtID/sku) с заказами за период без единой строки в костах."""
    svc = CostService(db)
    return await svc.missing_costs(date_from, date_to, company_id, page, page_size)


@router.get("/cards")
async def cost_cards(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = CostService(db)
    return await svc.search_cards(q.strip(), limit)


@router.delete("/{row_id}")
async def cost_delete(row_id: int, db: AsyncSession = Depends(get_db)):
    svc = CostService(db)
    try:
        await svc.delete_cost(row_id)
    except LookupError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}
