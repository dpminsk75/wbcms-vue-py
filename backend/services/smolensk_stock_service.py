"""Смоленск (ступень 2 производственного контура) — порт StockSnapshot/StockMovement.

Таблицы уже в БД (DDL по моделям PHP, миграции в PHP-репо нет):
  stock_snapshot: id, nm_id(int), period_date(DATE), qty_start(int), created_at(int)
  stock_movement: id, nm_id(int), type(production_in|adjustment|loss), qty(int),
                  movement_date(DATE), comment(varchar255), source(manual|excel_import),
                  created_by(int|null), created_at(int), updated_at(int)
company_id в таблицах НЕТ (как у production_plan_item) — скоп через JOIN wbcards.

Логика баланса — порт StockBalanceService.php:
  баланс = qty_start последнего снапшота (period_date <= дата)
         + SUM(движений всех типов) от даты снапшота до даты включительно.
Сверка (adjustment) — факт сравнивается с qty_start снапшота периода (StockMovementController::actionReconcile).
Импорт движений — nmID/vendorCode + Количество, 2 режима (production_in / adjustment),
карточка резолвится как StockMovement::findCardByImportRow (nmID цифрами -> иначе vendorCode).
"""
from __future__ import annotations

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.like_mask import escape_like

TYPES = ("production_in", "adjustment", "loss")
SOURCES = ("manual", "excel_import")
EPOCH = "1970-01-01"


def _ts(dt_val) -> int:
    import time as _t
    return int(_t.mktime(dt_val.timetuple())) if hasattr(dt_val, "timetuple") else int(dt_val)


class SmolenskStockService:
    def __init__(self, db: AsyncSession, company_id: int | None = None,
                 user_id: int | None = None):
        self.db = db
        self.company_id = company_id
        self.user_id = user_id

    # --- общий скоп ------------------------------------------------------
    def _cid_cond(self, alias: str = "c") -> str:
        return "" if self.company_id is None else f" AND {alias}.company_id = :cid"

    def _cid_params(self) -> dict:
        return {} if self.company_id is None else {"cid": self.company_id}

    async def _card_belongs(self, nm_id: int) -> bool:
        """Порт validateNmIdCompanyScope: карточка принадлежит компании."""
        sql = ("SELECT 1 FROM wbcards WHERE nmID = :nm"
               + ("" if self.company_id is None else " AND company_id = :cid") + " LIMIT 1")
        params = {"nm": nm_id, **self._cid_params()}
        return (await self.db.execute(text(sql), params)).first() is not None

    async def _resolve_card_by_import_row(self, nm_raw: str | None,
                                          vendor: str | None) -> dict | None:
        """Порт StockMovement::findCardByImportRow: цифры -> nmID, иначе vendorCode."""
        nm_raw = (nm_raw or "").strip()
        vendor = (vendor or "").strip()
        base = ("SELECT nmID, vendorCode, title FROM wbcards WHERE {cond}"
                + self._cid_cond() + " LIMIT 1")
        params: dict = {**self._cid_params()}
        if nm_raw.isdigit():
            row = (await self.db.execute(
                text(base.format(cond="nmID = :nm")), {**params, "nm": int(nm_raw)})
            ).mappings().first()
            if row:
                return dict(row)
        if vendor:
            row = (await self.db.execute(
                text(base.format(cond="vendorCode = :vc")), {**params, "vc": vendor})
            ).mappings().first()
            if row:
                return dict(row)
        return None

    # --- снапшоты ---------------------------------------------------------
    async def snapshots(self, period: str | None, q: str | None,
                        page: int = 1, page_size: int = 20) -> dict:
        conds: list[str] = []
        params: dict = {**self._cid_params(), "lim": max(1, min(page_size, 200)),
                        "off": max(0, (max(1, page) - 1)) * max(1, min(page_size, 200))}
        if period and len(period) == 7 and period[4] == "-":
            conds.append("s.period_date BETWEEN :d1 AND :d2")
            y, m = int(period[:4]), int(period[5:7])
            eoy = y + 1 if m == 12 else y
            eom = 1 if m == 12 else m + 1
            params["d1"] = f"{y}-{m:02d}-01"
            params["d2"] = f"{eoy}-{eom:02d}-01"
        q = (q or "").strip()
        if q:
            conds.append("(c.vendorCode LIKE :q OR c.title LIKE :q OR CAST(s.nm_id AS CHAR) LIKE :q)")
            params["q"] = f"%{escape_like(q)}%"
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        where_total = where.replace(":d1", ":d1").replace(":d2", ":d2")
        total = (await self.db.execute(text(f"""
            SELECT COUNT(*) FROM stock_snapshot s
            LEFT JOIN wbcards c ON c.nmID = s.nm_id {where_total}"""), params)).scalar() or 0
        rows = (await self.db.execute(text(f"""
            SELECT s.id, s.nm_id, s.period_date, s.qty_start, s.created_at,
                   c.vendorCode, c.title
            FROM stock_snapshot s
            LEFT JOIN wbcards c ON c.nmID = s.nm_id {where}
            ORDER BY s.period_date DESC, s.nm_id ASC
            LIMIT :lim OFFSET :off"""), params)).mappings().all()
        return {"rows": [dict(r) for r in rows], "total": int(total),
                "page": page, "page_size": page_size}

    async def snapshot_create(self, data: dict) -> dict:
        nm_id = self._int_or_none(data.get("nm_id"))
        period_date = (data.get("period_date") or "").strip()
        qty_start = self._int_or_none(data.get("qty_start"))
        if not nm_id or nm_id <= 0 or not period_date or len(period_date) != 10:
            raise ValueError("Нужны nm_id, period_date (YYYY-MM-DD) и qty_start")
        if nm_id and not await self._card_belongs(nm_id):
            raise ValueError(f"Карточка {nm_id} не принадлежит компании")
        dup = (await self.db.execute(text(
            "SELECT id FROM stock_snapshot WHERE nm_id = :nm AND period_date = :pd LIMIT 1"),
            {"nm": nm_id, "pd": period_date})).first()
        if dup:
            raise ValueError(f"Снапшот для {nm_id} на {period_date} уже есть")
        import datetime as _dt
        await self.db.execute(text("""
            INSERT INTO stock_snapshot(nm_id, period_date, qty_start, created_at)
            VALUES(:nm, :pd, :q, :now)"""),
            {"nm": nm_id, "pd": period_date, "q": qty_start or 0,
             "now": _ts(_dt.datetime.now())})
        await self.db.commit()
        return {"ok": True}

    async def snapshot_update(self, snap_id: int, data: dict) -> dict:
        row = (await self.db.execute(text(
            "SELECT s.* FROM stock_snapshot s WHERE s.id = :id LIMIT 1"), {"id": snap_id}
        )).mappings().first()
        if not row:
            raise ValueError("Снапшот не найден")
        nm_id = self._int_or_none(data.get("nm_id")) or int(row["nm_id"])
        period_date = (data.get("period_date") or str(row["period_date"])).strip()[:10]
        qty_start = self._int_or_none(data.get("qty_start"))
        qty_start = int(row["qty_start"]) if qty_start is None else qty_start
        if nm_id != int(row["nm_id"]) and not await self._card_belongs(nm_id):
            raise ValueError(f"Карточка {nm_id} не принадлежит компании")
        if (nm_id, period_date) != (int(row["nm_id"]), str(row["period_date"])[:10]):
            dup = (await self.db.execute(text(
                "SELECT id FROM stock_snapshot WHERE nm_id = :nm AND period_date = :pd AND id <> :id LIMIT 1"),
                {"nm": nm_id, "pd": period_date, "id": snap_id})).first()
            if dup:
                raise ValueError(f"Снапшот для {nm_id} на {period_date} уже есть")
        await self.db.execute(text("""
            UPDATE stock_snapshot SET nm_id = :nm, period_date = :pd, qty_start = :q
            WHERE id = :id"""), {"nm": nm_id, "pd": period_date, "q": qty_start, "id": snap_id})
        await self.db.commit()
        return {"ok": True}

    async def snapshot_delete(self, snap_id: int) -> dict:
        await self.db.execute(text("DELETE FROM stock_snapshot WHERE id = :id"), {"id": snap_id})
        await self.db.commit()
        return {"ok": True}

    async def save_availability(self, rows: list[dict]) -> dict:
        """Пакт «Сохранить все наличия»: upsert снапшотов (nm_id, period_date) -> qty_start."""
        import datetime as _dt
        saved = 0
        skipped: list[str] = []
        for r in rows or []:
            nm_id = self._int_or_none(r.get("nm_id"))
            period_date = (r.get("period_date") or "").strip()[:10]
            qty_start = self._int_or_none(r.get("qty_start")) or 0
            if not nm_id or len(period_date) != 10:
                skipped.append(f"Строка пропущена: некорректные данные ({r})")
                continue
            if not await self._card_belongs(nm_id):
                skipped.append(f"nmID {nm_id}: карточка не принадлежит компании")
                continue
            ex = (await self.db.execute(text(
                "SELECT id FROM stock_snapshot WHERE nm_id = :nm AND period_date = :pd LIMIT 1"),
                {"nm": nm_id, "pd": period_date})).first()
            if ex:
                await self.db.execute(text(
                    "UPDATE stock_snapshot SET qty_start = :q WHERE id = :id"),
                    {"q": qty_start, "id": ex[0]})
            else:
                await self.db.execute(text("""
                    INSERT INTO stock_snapshot(nm_id, period_date, qty_start, created_at)
                    VALUES(:nm, :pd, :q, :now)"""),
                    {"nm": nm_id, "pd": period_date, "q": qty_start,
                     "now": _ts(_dt.datetime.now())})
            saved += 1
        await self.db.commit()
        return {"saved": saved, "skipped": skipped}

    # --- движения ----------------------------------------------------------
    async def movements(self, mv_type: str | None, date_from: str | None,
                        date_to: str | None, nm_id: int | None, q: str | None,
                        page: int = 1, page_size: int = 20) -> dict:
        conds: list[str] = []
        params: dict = {**self._cid_params(), "lim": max(1, min(page_size, 200)),
                        "off": max(0, (max(1, page) - 1)) * max(1, min(page_size, 200))}
        if mv_type in TYPES:
            conds.append("m.type = :t")
            params["t"] = mv_type
        if date_from and len(date_from) == 10:
            conds.append("m.movement_date >= :df")
            params["df"] = date_from
        if date_to and len(date_to) == 10:
            conds.append("m.movement_date <= :dt")
            params["dt"] = date_to
        if nm_id:
            conds.append("m.nm_id = :nm")
            params["nm"] = int(nm_id)
        q = (q or "").strip()
        if q:
            conds.append("(c.vendorCode LIKE :q OR c.title LIKE :q OR CAST(m.nm_id AS CHAR) LIKE :q OR m.comment LIKE :q)")
            params["q"] = f"%{escape_like(q)}%"
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        total = (await self.db.execute(text(f"""
            SELECT COUNT(*) FROM stock_movement m
            LEFT JOIN wbcards c ON c.nmID = m.nm_id {where}"""), params)).scalar() or 0
        rows = (await self.db.execute(text(f"""
            SELECT m.id, m.nm_id, m.type, m.qty, m.movement_date, m.comment, m.source,
                   m.created_at, c.vendorCode, c.title
            FROM stock_movement m
            LEFT JOIN wbcards c ON c.nmID = m.nm_id {where}
            ORDER BY m.movement_date DESC, m.id DESC
            LIMIT :lim OFFSET :off"""), params)).mappings().all()
        return {"rows": [dict(r) for r in rows], "total": int(total),
                "page": page, "page_size": page_size}

    def _movement_params(self, nm_id: int, mv_type, qty: int,
                         movement_date: str, comment: str, source: str) -> dict:
        import datetime as _dt
        return {
            "nm": nm_id, "t": mv_type, "q": qty, "md": movement_date,
            "cm": (comment or "")[:255], "src": source, "uid": self.user_id,
            "now": _ts(_dt.datetime.now()),
        }

    async def movement_create(self, data: dict) -> dict:
        mv_type = data.get("type")
        nm_id = self._int_or_none(data.get("nm_id"))
        qty = self._int_or_none(data.get("qty"))
        movement_date = (data.get("movement_date") or "").strip()[:10]
        comment = data.get("comment") or None
        if not nm_id or mv_type not in TYPES or qty is None or len(movement_date) != 10:
            raise ValueError("Нужны nm_id, type (production_in/adjustment/loss), qty, movement_date")
        if not await self._card_belongs(nm_id):
            raise ValueError(f"Карточка {nm_id} не принадлежит компании")
        await self.db.execute(text("""
            INSERT INTO stock_movement(nm_id, type, qty, movement_date, comment,
                                       source, created_by, created_at, updated_at)
            VALUES(:nm, :t, :q, :md, :cm, :src, :uid, :now, :now)"""),
            self._movement_params(nm_id, mv_type, qty, movement_date, comment,
                                  data.get("source") if data.get("source") in SOURCES else "manual"))
        await self.db.commit()
        return {"ok": True}

    async def movement_update(self, mov_id: int, data: dict) -> dict:
        row = (await self.db.execute(text(
            "SELECT m.* FROM stock_movement m WHERE m.id = :id LIMIT 1"), {"id": mov_id}
        )).mappings().first()
        if not row:
            raise ValueError("Движение не найдено")
        mv_type = data.get("type") or row["type"]
        nm_id = self._int_or_none(data.get("nm_id")) or int(row["nm_id"])
        qty = self._int_or_none(data.get("qty"))
        qty = int(row["qty"]) if qty is None else qty
        movement_date = ((data.get("movement_date") or str(row["movement_date"]))).strip()[:10]
        comment = data.get("comment", row["comment"])
        if mv_type not in TYPES:
            raise ValueError("Некорректный тип движения")
        if nm_id != int(row["nm_id"]) and not await self._card_belongs(nm_id):
            raise ValueError(f"Карточка {nm_id} не принадлежит компании")
        await self.db.execute(text("""
            UPDATE stock_movement SET nm_id = :nm, type = :t, qty = :q,
                   movement_date = :md, comment = :cm, updated_at = :now
            WHERE id = :id"""),
            {**self._movement_params(nm_id, mv_type, qty, movement_date, comment, "manual"),
             "id": mov_id})
        await self.db.commit()
        return {"ok": True}

    async def movement_delete(self, mov_id: int) -> dict:
        await self.db.execute(text("DELETE FROM stock_movement WHERE id = :id"), {"id": mov_id})
        await self.db.commit()
        return {"ok": True}

    # --- баланс ------------------------------------------------------------
    async def balance(self, nm_id: int, on_date: str | None = None) -> dict:
        import datetime as _dt
        d = (on_date or _dt.date.today().isoformat()).strip()[:10]
        snap = (await self.db.execute(text(f"""
            SELECT s.period_date, s.qty_start
            FROM stock_snapshot s
            INNER JOIN wbcards c ON c.nmID = s.nm_id
            WHERE s.nm_id = :nm AND s.period_date <= :d{self._cid_cond()}
            ORDER BY s.period_date DESC
            LIMIT 1"""), {"nm": nm_id, "d": d, **self._cid_params()})).mappings().first()
        if not snap:
            return {"nm_id": nm_id, "on_date": d, "balance": 0,
                    "snapshot_date": None, "qty_start": 0,
                    "breakdown": {}, "detail": []}
        since = str(snap["period_date"])[:10]
        mv_rows = (await self.db.execute(text(f"""
            SELECT m.type, m.qty, m.movement_date
            FROM stock_movement m
            INNER JOIN wbcards c ON c.nmID = m.nm_id
            WHERE m.nm_id = :nm AND m.movement_date >= :since AND m.movement_date <= :d
              {self._cid_cond()}"""), {"nm": nm_id, "since": since, "d": d,
                                       **self._cid_params()})).mappings().all()
        breakdown: dict[str, int] = {}
        total = int(snap["qty_start"] or 0)
        for r in mv_rows:
            breakdown[r["type"]] = breakdown.get(r["type"], 0) + int(r["qty"] or 0)
            total += int(r["qty"] or 0)
        return {"nm_id": nm_id, "on_date": d, "balance": total,
                "snapshot_date": since, "qty_start": int(snap["qty_start"] or 0),
                "breakdown": breakdown}

    async def _batch_base_balances(self, nm_ids: list[int], movement_date: str) -> dict[int, int]:
        """Расчётный баланс на movement_date для списка nm_id (2 прохода, таблицы малые)."""
        if not nm_ids:
            return {}
        # 1) последний снапшот <= даты по каждому nm_id (ORDER BY_nm+date, берём последний в Python)
        s_rows = (await self.db.execute(text(f"""
            SELECT s.nm_id, s.qty_start, s.period_date AS pd
            FROM stock_snapshot s
            INNER JOIN wbcards c ON c.nmID = s.nm_id{self._cid_cond()}
            WHERE s.period_date <= :d AND s.nm_id IN :ids
            ORDER BY s.nm_id ASC, s.period_date ASC"""
        ).bindparams(bindparam("ids", expanding=True)),
            {"d": movement_date, "ids": nm_ids, **self._cid_params()})).mappings().all()
        latest: dict[int, dict] = {}
        for r in s_rows:
            latest[int(r["nm_id"])] = {"start": int(r["qty_start"] or 0),
                                       "since": str(r["pd"])[:10]}
        # 2) все движения этих nm_id включительно до даты; в Python отрезаем до даты снапшота
        mv_rows = (await self.db.execute(text(f"""
            SELECT m.nm_id, m.qty, m.movement_date
            FROM stock_movement m
            INNER JOIN wbcards c ON c.nmID = m.nm_id{self._cid_cond()}
            WHERE m.movement_date <= :d AND m.nm_id IN :ids"""
        ).bindparams(bindparam("ids", expanding=True)),
            {"d": movement_date, "ids": nm_ids, **self._cid_params()})).mappings().all()
        base: dict[int, int] = {n: latest.get(n, {}).get("start", 0) for n in nm_ids}
        since_by: dict[int, str] = {n: latest.get(n, {}).get("since", EPOCH) for n in nm_ids}
        for r in mv_rows:
            nm = int(r["nm_id"])
            md = str(r["movement_date"])[:10]
            if md < since_by.get(nm, EPOCH):
                continue
            base[nm] = base.get(nm, 0) + int(r["qty"] or 0)
        return base

    # --- сверка ------------------------------------------------------------
    async def reconcile(self, nm_id: int, period_date: str, actual_qty: float) -> dict:
        period_date = (period_date or "").strip()[:10]
        if not nm_id or len(period_date) != 10:
            raise ValueError("Укажите nmID и период (YYYY-MM-DD)")
        expected = (await self.db.execute(text(
            "SELECT qty_start FROM stock_snapshot WHERE nm_id = :nm AND period_date = :pd LIMIT 1"),
            {"nm": nm_id, "pd": period_date})).scalar()
        if expected is None:
            raise ValueError(f"Снапшот для товара {nm_id} на {period_date} не найден.")
        diff = int(round(float(actual_qty))) - int(expected)
        if diff == 0:
            return {"diff": 0, "message": "Расхождений нет, движение не создавалось."}
        import datetime as _dt
        comment = f"Сверка на {period_date}: остаток на начало периода {int(expected)}, факт {int(round(float(actual_qty)))}"
        await self.db.execute(text("""
            INSERT INTO stock_movement(nm_id, type, qty, movement_date, comment,
                                       source, created_by, created_at, updated_at)
            VALUES(:nm, 'adjustment', :q, :md, :cm, 'manual', :uid, :now, :now)"""),
            self._movement_params(nm_id, "adjustment", diff, period_date, comment, "manual"))
        await self.db.commit()
        return {"diff": diff,
                "message": f"Излишек +{diff} зафиксирован." if diff > 0 else f"Недостача {diff} зафиксирована."}

    async def reconcile_bulk(self, changes: list[dict]) -> dict:
        processed = no_diff = skipped = 0
        errors: list[str] = []
        for ch in changes or []:
            try:
                res = await self.reconcile(
                    int(ch.get("nm_id") or 0), ch.get("period_date") or "",
                    ch.get("actual_qty") if ch.get("actual_qty") not in (None, "") else float("nan"))
                if res.get("diff") == 0:
                    no_diff += 1
                else:
                    processed += 1
            except (ValueError, TypeError) as e:
                skipped += 1
                errors.append(str(e))
        return {"processed": processed, "no_diff": no_diff, "skipped": skipped, "errors": errors}

    # --- импорт движений -----------------------------------------------------
    async def import_movements(self, rows: list[dict], mv_type: str,
                               movement_date: str) -> dict:
        """Порт StockMovementController::actionImport (rows: nmId/vendorCode/qty из xlsx).

        Приход: movement type=production_in с qty из файла.
        Сверка: qty из файла = факт; движение adjustment только если разница <> 0.
        """
        import datetime as _dt
        if mv_type not in ("production_in", "adjustment"):
            raise ValueError("type должен быть production_in или adjustment")
        movement_date = (movement_date or _dt.date.today().isoformat()).strip()[:10]
        if len(movement_date) != 10:
            raise ValueError("Некорректная дата движения")

        parsed: list[tuple[int, int]] = []       # (nm_id, qty)
        skipped: list[str] = []
        for i, r in enumerate(rows or []):
            nm_raw = str(r.get("nm_id_raw") or "").strip()
            vendor = str(r.get("vendor") or "").strip()
            qty_raw = r.get("qty")
            if qty_raw in (None, ""):
                continue
            try:
                qty = int(round(float(qty_raw)))
            except (TypeError, ValueError):
                continue
            card = await self._resolve_card_by_import_row(nm_raw, vendor)
            if not card:
                skipped.append(f"Строка {i + 2}: карточка не найдена (nmId={nm_raw}, vendorCode={vendor})")
                continue
            parsed.append((int(card["nmID"]), qty))

        if not parsed:
            return {"processed": 0, "created": 0, "skipped": skipped}

        if mv_type == "production_in":
            base = {}
        else:
            base = await self._batch_base_balances([n for n, _ in parsed], movement_date)

        inserted: dict[int, int] = {}
        created = processed = 0
        for nm_id, qty in parsed:
            if mv_type == "production_in":
                final_qty, comment = qty, "Импорт прихода из Excel"
            else:
                bal = base.get(nm_id, 0) + inserted.get(nm_id, 0)
                diff = qty - bal
                if diff == 0:
                    processed += 1
                    continue
                final_qty = diff
                comment = f"Сверка: расчётный {bal}, факт {qty}"
            await self.db.execute(text("""
                INSERT INTO stock_movement(nm_id, type, qty, movement_date, comment,
                                           source, created_by, created_at, updated_at)
                VALUES(:nm, :t, :q, :md, :cm, 'excel_import', :uid, :now, :now)"""),
                self._movement_params(nm_id, mv_type, final_qty, movement_date, comment, "excel_import"))
            inserted[nm_id] = inserted.get(nm_id, 0) + final_qty
            created += 1
            processed += 1
        await self.db.commit()
        return {"processed": processed, "created": created, "skipped": skipped}

    # --- разбор xlsx-грида (фронт присылает any[][], как cost-import) ---------
    COL_NM = ["nmid", "nm_id", "nm id", "id"]
    COL_VENDOR = ["vendorcode", "vendor_code", "артикул", "vendor code"]
    COL_QTY = ["количество", "qty", "quantity", "кол-во", "остаток", "наличие"]

    @classmethod
    def parse_grid(cls, grid: list[list]) -> tuple[list[dict], str | None]:
        """Первая строка — заголовок. Возвращает [{nm_id_raw, vendor, qty}] или ошибку."""
        if not grid or not grid[0]:
            return [], "Файл пустой."
        header = [str(h or "").strip().lower() for h in grid[0]]

        def col(variants: list[str]) -> int | None:
            want = set(variants)
            for i, h in enumerate(header):
                if h in want:
                    return i
            return None

        i_nm, i_vendor, i_qty = col(cls.COL_NM), col(cls.COL_VENDOR), col(cls.COL_QTY)
        if i_qty is None or (i_nm is None and i_vendor is None):
            return [], ("Не найдены нужные колонки. Ожидаются заголовки: "
                        "nmId и/или vendorCode, Количество.")
        rows: list[dict] = []
        for r in grid[1:]:
            r = list(r) + [None] * max(0, len(header) - len(r))
            rows.append({
                "nm_id_raw": str(r[i_nm] or "").strip() if i_nm is not None else "",
                "vendor": str(r[i_vendor] or "").strip() if i_vendor is not None else "",
                "qty": r[i_qty] if i_qty is not None else None,
            })
        return rows, None

    # --- разбор наличий (снапшоты) --------------------------------------------
    async def parse_availability(self, rows: list[dict]) -> dict:
        """Порт actionParseAvailability: nmId/vendorCode + Количество -> соответствия (без записи)."""
        matched: list[dict] = []
        skipped: list[str] = []
        for i, r in enumerate(rows or []):
            nm_raw = str(r.get("nm_id_raw") or "").strip()
            vendor = str(r.get("vendor") or "").strip()
            qty_raw = r.get("qty")
            if qty_raw in (None, ""):
                continue
            try:
                qty = int(round(float(qty_raw)))
            except (TypeError, ValueError):
                continue
            card = await self._resolve_card_by_import_row(nm_raw, vendor)
            if not card:
                skipped.append(f"Строка {i + 2}: товар не найден (nmId={nm_raw}, vendorCode={vendor})")
                continue
            matched.append({"nm_id": int(card["nmID"]), "qty": qty,
                            "vendor_code": card["vendorCode"], "title": card["title"]})
        return {"matched": matched, "skipped": skipped}

    @staticmethod
    def _int_or_none(v) -> int | None:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
