"""Складской учёт: баланс + ledger одной транзакцией (порт StockService::apply).

apply(company, warehouseId, doc_type, doc_id, [(sku, delta)]):
баланс -1/+N (строка создаётся с 0 при отсутствии), ledger — строка на sku
с before/after. nmID/chrtID подтягиваем из wbcards_sizes. Только stdlib/SQL.

Добавлено (порт StockService::transfer / getBalance):
  * transfer() — перемещение: две проводки (from −qty, to +qty) в ОДНОЙ транзакции;
  * get_balance() — текущий остаток по (company, склад, sku).
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_balance(db: AsyncSession, company_id: int, warehouse_id: int, sku: str) -> int:
    """Текущий остаток по SKU на складе (0, если строки нет)."""
    row = (await db.execute(text("""
        SELECT quantity FROM wb_stock_balance
        WHERE company_id = :c AND warehouseId = :w AND sku = :s LIMIT 1"""),
        {"c": company_id, "w": warehouse_id, "s": sku})).first()
    return int(row[0]) if row else 0


async def _apply_items(db: AsyncSession, company_id: int, warehouse_id: int,
                       doc_type: str, doc_id: int | None,
                       items: list[tuple[str, int]],
                       user_id: int | None = None,
                       allow_negative: bool = False) -> None:
    """Проводки внутри УЖЕ открытой транзакции. Бросает исключение при нехватке.

    allow_negative=False (умолчание, как в PHP StockService): списание в минус
    запрещено. Сторно (RECEIPT_CANCEL и т.п.) вызывает через apply_batch,
    где минус разрешен - после проведения часть товара могла уже уйти.
    """
    for sku, delta in items:
        delta = int(delta)
        if delta == 0:
            continue
        row = (await db.execute(text("""
                    SELECT quantity FROM wb_stock_balance
                    WHERE company_id = :c AND warehouseId = :w AND sku = :s
                    FOR UPDATE"""),
                {"c": company_id, "w": warehouse_id, "s": sku})).first()
        before = int(row[0]) if row else 0
        after = before + delta
        if after < 0 and not allow_negative:
            raise ValueError(
                f"Недостаточно на складе {warehouse_id} sku {sku}: {before} + ({delta}) <0")
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
             "w": warehouse_id, "s": sku, "d": delta,
             "b": before, "a": after, "u": user_id})


async def apply(db: AsyncSession, company_id: int, warehouse_id: int,
                doc_type: str, doc_id: int | None,
                items: list[tuple[str, int]],
                user_id: int | None = None,
                allow_negative: bool = False) -> dict:
    """Возвращает {ok, error}. Пишет и коммитит (транзакция на вызов)."""
    try:
        await db.rollback()  # сброс autobegin от предыдущих SELECT (B6), иначе begin упадёт
        async with db.begin():
            await _apply_items(db, company_id, warehouse_id, doc_type, doc_id, items,
                               user_id, allow_negative)
        return {"ok": True, "error": ""}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def apply_batch(db: AsyncSession, company_id: int, doc_type: str, doc_id: int | None,
                      items_by_warehouse: list[tuple[int, list[tuple[str, int]]]],
                      user_id: int | None = None) -> dict:
    """Проводки по нескольким складам ОДНОЙ транзакцией.

    items_by_warehouse: [(warehouse_id, [(sku, delta), ...]), ...].
    Если ошибка на любом складе - откатываются все (как transfer в PHP).

    В отличие от apply/transfer минус разрешен: используется для сторно,
    где после проведения часть остатков могла уже уйти.
    """
    try:
        await db.rollback()
        async with db.begin():
            for wh_id, items in items_by_warehouse:
                await _apply_items(db, company_id, wh_id, doc_type, doc_id, items, user_id)
        return {"ok": True, "error": ""}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def transfer(db: AsyncSession, company_id: int, from_wh: int, to_wh: int,
                   doc_type: str, doc_id: int | None,
                   items: list[tuple[str, int]],
                   user_id: int | None = None,
                   allow_negative: bool = False) -> dict:
    """Перемещение между складами одной транзакцией (порт StockService::transfer).

    items — список (sku, qty) с ПОЛОЖИТЕЛЬНЫМ qty: из from_wh списывается qty,
    в to_wh зачисляется qty. При нехватке на from_wh откатываются обе ноги.
    """
    try:
        await db.rollback()
        async with db.begin():
            minus = [(sku, -abs(int(qty))) for sku, qty in items if int(qty) != 0]
            plus = [(sku, abs(int(qty))) for sku, qty in items if int(qty) != 0]
            if minus:
                await _apply_items(db, company_id, from_wh, doc_type, doc_id, minus,
                                   user_id, allow_negative)
            if plus:
                await _apply_items(db, company_id, to_wh, doc_type, doc_id, plus,
                                   user_id, allow_negative)
        return {"ok": True, "error": ""}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
