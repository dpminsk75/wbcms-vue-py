"""Себестоимость wbcards_costs — порт CostImportController. Без company: nmID глобально уникален."""
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


class CostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_costs(self, date_from: str, date_to: str, nm_id: int | None = None, sku: str | None = None) -> list[dict]:
        """Карточка выбрана → ВСЯ её история (load_date DESC, chrtID), опц. фильтр по sku.
        Иначе → последние по каждой связке (nmID, chrtID, sku). Даты игнорируются (см. md 2026-09-17)."""
        base = """SELECT c.id, c.load_date, c.nmID, c.chrtID, c.sku, c.price,
                w.title AS product_name, w.vendorCode
            FROM wbcards_costs c LEFT JOIN wbcards w ON w.nmID = c.nmID"""
        if nm_id:
            sql = base + " WHERE c.nmID = :nm"
            params: dict = {"nm": nm_id}
            if sku:
                sql += " AND c.sku = :sku"
                params["sku"] = sku
            sql += " ORDER BY c.load_date DESC, c.chrtID ASC"
        else:
            sql = base + """ INNER JOIN (
                    SELECT nmID, chrtID, sku, MAX(load_date) AS md FROM wbcards_costs
                    GROUP BY nmID, chrtID, sku
                ) m ON m.nmID <=> c.nmID AND m.chrtID <=> c.chrtID AND m.sku <=> c.sku AND m.md = c.load_date
                ORDER BY c.nmID ASC, c.chrtID ASC"""
            params = {}
        rows = (await self.db.execute(text(sql), params)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["load_date"] = str(d["load_date"])
            d["price"] = float(d["price"])
            out.append(d)
        return out

    @staticmethod
    def parse_sizes(raw) -> list[dict]:
        """sizes двойного кодирования → [{chrtID, sku}]. Пары 1:1."""
        import json
        v = raw
        for _ in range(2):
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except (TypeError, ValueError):
                    return []
        if not isinstance(v, list):
            return []
        out = []
        for s in v:
            if isinstance(s, dict) and s.get("chrtID"):
                skus = s.get("skus") or []
                out.append({"chrtID": str(s["chrtID"]), "sku": str(skus[0]) if skus else ""})
        return out

    async def search_cards(self, q: str, limit: int = 50) -> list[dict]:
        """Все карточки (а не только с костами): nmID/vendorCode/title/sku из sizes-текста. Косты глобальные, скоупа нет."""
        like = f"%{q}%"
        rows = (await self.db.execute(text("""
            SELECT w.nmID, w.vendorCode, w.title, w.sizes
            FROM wbcards w
            WHERE CAST(w.nmID AS CHAR) LIKE :q OR w.vendorCode LIKE :q
               OR w.title LIKE :q OR w.sizes LIKE :q
            ORDER BY w.nmID DESC LIMIT :lim
        """), {"q": like, "lim": limit})).mappings().all()
        return [{"nmID": r["nmID"], "vendorCode": r["vendorCode"], "title": r["title"],
                 "sizes": self.parse_sizes(r["sizes"])} for r in rows]

    @staticmethod
    def check_price(raw: str) -> tuple[bool, float | str]:
        """Порт валидации update-price: запятая→точка, число ≥0, round 2."""
        s = (raw or "").strip().replace(",", ".")
        try:
            v = float(s)
        except (TypeError, ValueError):
            return False, "Некорректная цена"
        if s == "" or v < 0:
            return False, "Некорректная цена"
        return True, round(v, 2)

    async def save_many(self, date: str, items: list[dict]) -> int:
        """Upsert по UNIQUE(load_date, nmID, chrtID, sku). Мусор пропускаем как в Yii2."""
        import re
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
            raise ValueError("Некорректная дата загрузки")
        clean = []
        for it in items or []:
            nm = str(it.get("nmID", "")).strip()
            if not nm or not nm.isdigit():
                continue
            ok, price = self.check_price(str(it.get("price", "")))
            if not ok:
                continue
            chrt = str(it.get("chrtID", "") or "").strip()
            sku = str(it.get("sku", "") or "").strip()
            clean.append({"d": date, "nm": int(nm),
                          "ch": int(chrt) if chrt.isdigit() else None,
                          "s": sku or None, "p": price})
        if not clean:
            return 0
        await self.db.execute(
            text("""INSERT INTO wbcards_costs(load_date, nmID, chrtID, sku, price)
                    VALUES(:d, :nm, :ch, :s, :p)
                    ON DUPLICATE KEY UPDATE price = VALUES(price)"""),
            clean,
        )
        await self.db.commit()
        return len(clean)

    async def update_row(self, row_id: int, price_raw: str | None = None, load_date: str | None = None) -> dict:
        import re
        from sqlalchemy.exc import IntegrityError
        sets: dict = {}
        if price_raw is not None:
            ok, price = self.check_price(price_raw)
            if not ok:
                raise ValueError(price)
            sets["price"] = price
        if load_date is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", load_date):
                raise ValueError("Некорректная дата")
            sets["load_date"] = load_date
        if not sets:
            raise ValueError("Нечего сохранять")
        try:
            res = await self.db.execute(
                text(f"UPDATE wbcards_costs SET {', '.join(f'{k}=:{k}' for k in sets)} WHERE id=:id"),
                {**sets, "id": row_id},
            )
        except IntegrityError:
            raise ValueError("Такая запись уже есть (дубль даты/размера)")
        if res.rowcount == 0:
            raise LookupError("Запись не найдена")
        await self.db.commit()
        row = (await self.db.execute(
            text("SELECT load_date, price FROM wbcards_costs WHERE id=:id"), {"id": row_id}
        )).mappings().first()
        return {"load_date": str(row["load_date"]), "price": float(row["price"])}

    async def delete_cost(self, row_id: int) -> None:
        res = await self.db.execute(text("DELETE FROM wbcards_costs WHERE id=:id"), {"id": row_id})
        if res.rowcount == 0:
            raise LookupError("Запись не найдена")
        await self.db.commit()

    async def missing_costs(self, date_from: str, date_to: str, company_id: int | None = None,
                            page: int = 1, page_size: int = 100) -> dict:
        """Зерно (nmID, chrtID, barcode) с заказами за период, без единой строки в костах. Пагинация — зерен тысячи."""
        scope = "" if company_id is None else " AND o.company_id = :company_id"
        params: dict = {"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"}
        if company_id is not None:
            params["company_id"] = company_id
        # зерно = (nmID, sku): chrtID не группируем и не матчим (пары 1:1, chrt только для показа)
        # баркод: NULL в заказе + единственный размер в товаре → берем его; иначе как есть
        sku_expr = ("COALESCE(NULLIF(TRIM(o.barcode), ''), "
                    "CASE WHEN w2.n = 1 THEN w2.sku1 END)")
        base = f"""
            FROM wb_order o
            LEFT JOIN (
                SELECT nmID,
                    JSON_UNQUOTE(JSON_EXTRACT(JSON_UNQUOTE(sizes), '$[0].skus[0]')) AS sku1,
                    JSON_LENGTH(JSON_UNQUOTE(sizes)) AS n
                FROM wbcards
            ) w2 ON w2.nmID = TRIM(o.nm_id)
            LEFT JOIN wbcards w ON w.nmID = TRIM(o.nm_id)
            LEFT JOIN wbcards_costs c ON c.nmID = TRIM(o.nm_id)
                AND (c.sku IS NULL OR {sku_expr} IS NULL OR c.sku = {sku_expr})
            WHERE o.date BETWEEN :d1 AND :d2{scope}
            GROUP BY TRIM(o.nm_id), {sku_expr}
            HAVING MAX(c.id) IS NULL
        """
        rows = (await self.db.execute(text(f"""
            SELECT TRIM(o.nm_id) AS nmID, MAX(o.chrt_id) AS chrtID, {sku_expr} AS sku,
                MIN(o.date) AS first_order, COUNT(*) AS orders_cnt,
                MAX(w.vendorCode) AS vendorCode, MAX(w.title) AS title
            {base}
            ORDER BY first_order DESC LIMIT :lim OFFSET :off
        """), {**params, "lim": page_size, "off": (page - 1) * page_size})).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["first_order"] = str(d["first_order"])[:10]
            d["orders_cnt"] = int(d["orders_cnt"] or 0)
            out.append(d)
        total = (await self.db.execute(text(f"SELECT COUNT(*) AS cnt FROM (SELECT 1 {base}) t"), params)).scalar()
        return {"models": out, "total": int(total or 0), "page": page, "page_size": page_size}

    # --- импорт: резолв сырых строк (шаг 7, md 2026-09-17) ---
    VENDOR_H = {"арт продавца", "артикул продавца", "vendorcode"}
    NM_H = {"nmid", "nm_id", "артикул wb"}
    ART_H = {"артикул"}  # буквы→vendor, цифры→nmID
    SKU_H = {"sku", "баркод", "штрихкод", "шк", "barcode"}
    PRICE_H = {"себестоимость", "цена"}

    @staticmethod
    def _norm(h) -> str:
        return str(h or "").strip().lower()

    async def _card_by_nm(self, nm_id: int) -> dict | None:
        row = (await self.db.execute(
            text("SELECT nmID, vendorCode, title, sizes FROM wbcards WHERE nmID=:nm LIMIT 1"), {"nm": nm_id}
        )).mappings().first()
        return dict(row) if row else None

    async def _card_by_vendor(self, vendor: str) -> dict | None:
        row = (await self.db.execute(
            text("SELECT nmID, vendorCode, title, sizes FROM wbcards WHERE vendorCode=:v LIMIT 1"), {"v": vendor}
        )).mappings().first()
        return dict(row) if row else None

    async def _card_by_sku(self, sku: str) -> dict | None:
        """Карточка по баркоду: ищем sku в sizes-тексте, точное совпадение проверяем в Python."""
        rows = (await self.db.execute(text(
            "SELECT nmID, vendorCode, title, sizes FROM wbcards WHERE sizes LIKE :p LIMIT 5"
        ), {"p": f"%{sku}%"})).mappings().all()
        for r in rows:
            d = dict(r)
            if any(s["sku"] == sku for s in self.parse_sizes(d.get("sizes"))):
                return d
        return None

    async def preview_rows(self, date: str, raw: list[list]) -> dict:
        """Dry-run: резолв без записи. Возвращает items (+action новая/перезапись) и errors."""
        import re
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
            return {"success": False, "message": "Некорректная дата загрузки", "items": [], "errors": []}
        if not raw:
            return {"success": False, "message": "Файл пуст", "items": [], "errors": []}
        header = [self._norm(h) for h in (raw[0] or [])]
        cols: dict[str, int] = {}
        for i, h in enumerate(header):
            if h in self.VENDOR_H and "vendor" not in cols:
                cols["vendor"] = i
            elif h in self.NM_H and "nm" not in cols:
                cols["nm"] = i
            elif h in self.ART_H and "art" not in cols:
                cols["art"] = i
            elif h in self.SKU_H and "sku" not in cols:
                cols["sku"] = i
            elif h in self.PRICE_H and "price" not in cols:
                cols["price"] = i
        positional = "price" not in cols
        items: list[dict] = []
        errors: list[dict] = []
        seen: set[tuple] = set()
        for r in range(1, len(raw)):
            line = raw[r] or []
            get = lambda i: str(line[i] if i < len(line) else "" or "").strip()
            if positional:
                # Ф2: [vendor, sku(13 цифр), chrt(игнор), price] — шапок нет
                cells = [get(i) for i in range(min(4, len(line)))]
                if not any(cells):
                    continue
                vendor_raw = cells[0] if len(cells) > 0 else ""
                sku_raw = next((c for c in cells[1:3] if re.fullmatch(r"\d{13}", c)), "")
                price_raw = cells[-1] if len(cells) > 1 and re.fullmatch(r"\d+([.,]\d+)?", cells[-1]) and cells[-1] != sku_raw else ""
                art_raw, nm_raw = "", ""
            else:
                if not any(get(i) for i in cols.values()):
                    continue
                vendor_raw = get(cols["vendor"]) if "vendor" in cols else ""
                nm_raw = get(cols["nm"]) if "nm" in cols else ""
                art_raw = get(cols["art"]) if "art" in cols else ""
                sku_raw = get(cols["sku"]) if "sku" in cols else ""
                price_raw = get(cols["price"])
            ok, price = self.check_price(price_raw)
            if not ok:
                errors.append({"row": r + 1, "reason": "Некорректная или отсутствующая цена", "raw": price_raw})
                continue
            # шаг 1: карточка
            nm_id: int | None = None
            vendor_code = vendor_raw or None
            if vendor_raw:
                pass
            elif art_raw:
                if art_raw.isdigit():
                    nm_id = int(art_raw)
                else:
                    vendor_code = art_raw
            elif nm_raw and nm_raw.isdigit():
                nm_id = int(nm_raw)
            if nm_id is None and not vendor_code and not sku_raw:
                errors.append({"row": r + 1, "reason": "Нет артикула (vendor/артикул/nmid)", "raw": ""})
                continue
            card = None
            if nm_id is not None:
                card = await self._card_by_nm(nm_id)
            if card is None and vendor_code:
                card = await self._card_by_vendor(vendor_code)
                if card:
                    nm_id = int(card["nmID"])
            # шаг 2: размер через баркод (sku главнее кривого артикула)
            targets: list[tuple] = []
            if sku_raw:
                if not re.fullmatch(r"\d+", sku_raw):
                    errors.append({"row": r + 1, "reason": "Некорректный баркод", "raw": sku_raw})
                    continue
                if card is None:
                    # артикул в файле кривой, но sku верный — находим карточку по sku
                    card = await self._card_by_sku(sku_raw)
                    if card:
                        nm_id = int(card["nmID"])
                if card is None:
                    errors.append({"row": r + 1, "reason": "Карточка не найдена ни по артикулу, ни по баркоду", "raw": sku_raw})
                    continue
                sizes = self.parse_sizes(card.get("sizes"))
                hit = next((s for s in sizes if s["sku"] == sku_raw), None)
                if not hit:
                    errors.append({"row": r + 1, "reason": "Баркод не найден в размерах карточки", "raw": sku_raw})
                    continue
                targets = [(nm_id, hit["chrtID"], sku_raw)]
            else:
                if card is None:
                    errors.append({"row": r + 1, "reason": "Карточка не найдена", "raw": vendor_code or nm_raw or art_raw})
                    continue
                sizes = self.parse_sizes(card.get("sizes"))
                if not sizes:
                    errors.append({"row": r + 1, "reason": "У карточки нет размеров", "raw": ""})
                    continue
                targets = [(nm_id, s["chrtID"], s["sku"]) for s in sizes]
            for t_nm, t_ch, t_sku in targets:
                key = (t_nm, t_ch, t_sku)
                if key in seen:
                    errors.append({"row": r + 1, "reason": f"Дубликат {t_nm}/{t_sku} в файле (взято последнее значение)", "raw": ""})
                seen.add(key)
                exists = (await self.db.execute(text(
                    "SELECT id FROM wbcards_costs WHERE load_date=:d AND nmID=:nm AND chrtID<=>:ch AND sku<=>:s LIMIT 1"
                ), {"d": date, "nm": t_nm, "ch": int(t_ch) if str(t_ch).isdigit() else None, "s": t_sku or None})).scalar()
                items.append({"row": r + 1, "nmID": t_nm, "vendorCode": card.get("vendorCode"),
                              "title": card.get("title"), "chrtID": t_ch, "sku": t_sku,
                              "price": price, "action": "update" if exists else "insert"})
        # дубликаты: последнее вхождение побеждает
        uniq: dict[tuple, dict] = {}
        for it in items:
            uniq[(it["nmID"], it["chrtID"], it["sku"])] = it
        return {"success": True, "items": list(uniq.values()), "errors": errors}
