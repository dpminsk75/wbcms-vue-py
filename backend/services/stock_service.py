"""Складской учёт: баланс + ledger одной транзакцией (порт StockService::apply).

apply(company, warehouseId, doc_type, doc_id, [(sku, delta)]):
баланс -1/+N (строка создаётся с 0 при отсутствии), ledger — строка на sku
с before/after. nmID/chrtID подтягиваем из wbcards_sizes. Только stdlib/SQL.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def apply(db: AsyncSession, company_id: int, warehouse_id: int,
                doc_type: str, doc_id: int | None,
                items: list[tuple[str, int]],
                user_id: int | None = None) -> dict:
    """Возвращает {ok, error}. Пишет и коммитит (транзакция на вызов)."""
    try:
        await db.rollback()  # сброс autobegin от предыдущих SELECT (B6), иначе begin упадёт
        async with db.begin():
            for sku, delta in items:
                row = (await db.execute(text("""
                    SELECT quantity FROM wb_stock_balance
                    WHERE company_id = :c AND warehouseId = :w AND sku = :s
                    FOR UPDATE"""),
                    {"c": company_id, "w": warehouse_id, "s": sku})).first()
                before = int(row[0]) if row else 0
                after = before + int(delta)
                if row is None:
                    card = (await db.execute(text("""
                        SELECT nmID, chrtID FROM wbcards_sizes WHERE sku = :s LIMIT 1"""),
                        {"s": sku})).first()
                    await db.execute(text("""
                        INSERT INTO wb_stock_balance(company_id, warehouseId, sku,
                            nmID, chrtID, quantity)
                        VALUES(:c, :w, :s, :nm, :ch, :q)"""),
                        {"c": company_id, "w": warehouse_id, "s": sku,
                         "nm": card[0] if card else None,
                         "ch": card[1] if card else None, "q": after})
                else:
                    await db.execute(text("""
                        UPDATE wb_stock_balance SET quantity = :q
                        WHERE company_id = :c AND warehouseId = :w AND sku = :s"""),
                        {"q": after, "c": company_id, "w": warehouse_id, "s": sku})
                await db.execute(text("""
                    INSERT INTO wb_stock_ledger(company_id, doc_type, doc_id,
                        warehouseId, sku, qty_delta, qty_before, qty_after, user_id)
                    VALUES(:c, :dt, :did, :w, :s, :d, :b, :a, :u)"""),
                    {"c": company_id, "dt": doc_type, "did": doc_id,
                     "w": warehouse_id, "s": sku, "d": int(delta),
                     "b": before, "a": after, "u": user_id})
        return {"ok": True, "error": ""}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
