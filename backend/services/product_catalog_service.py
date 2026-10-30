"""Справочник линеек (В8) — порт Product/ProductWbCard/ProductType/Brand.

Таблицы уже в БД:
  product(id, name, product_type_id, brand_id, cost, weight, vat_rate, created_at, updated_at)
  product_wb_card(id, product_id, wb_nm_id, type 0..9, q, p)
  product_type(id, name, description), brand(id, name) — глобальные справочники.
product/product_wb_card без company_id — принадлежность через карточки wbcards.company_id.

При сохранении состава нормируем p до 100 по карточке: если сумма p по ВСЕМ
линейкам карточки != 100 и > 0 — все её строки масштабируются (иначе отчёт
«Маржа по линейкам» считает долю неверно). UNIQUE (product_id, wb_nm_id).
View/админ-мутации решает роутер (view = authenticated, мутации = admin).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _now() -> str:
    return date.today().isoformat()


class ProductCatalogService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    # --- product ----------------------------------------------------------
    async def list_products(self, q: str | None = None) -> dict:
        params: dict = {}
        where = ""
        q = (q or "").strip()
        if q:
            where = (" WHERE (pr.name LIKE :q OR b.name LIKE :q OR pt.name LIKE :q"
                     " OR CAST(pr.id AS CHAR) = :qid)")
            params["q"] = f"%{q}%"
            params["qid"] = q
        rows = (await self.db.execute(text(f"""
            SELECT pr.id, pr.name, pr.product_type_id, pr.brand_id, pr.cost,
                   pr.weight, pr.vat_rate, pr.created_at, pr.updated_at,
                   pt.name AS product_type, b.name AS brand,
                   (SELECT COUNT(*) FROM product_wb_card pwc WHERE pwc.product_id = pr.id) AS links_cnt
            FROM product pr
            LEFT JOIN product_type pt ON pt.id = pr.product_type_id
            LEFT JOIN brand b ON b.id = pr.brand_id{where}
            ORDER BY pr.id DESC"""), params)).mappings().all()
        return {"rows": [dict(r) for r in rows]}

    async def product_create(self, data: dict) -> dict:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("Название обязательно")
        pid = (await self.db.execute(text("""
            INSERT INTO product(name, product_type_id, brand_id, cost, weight, vat_rate,
                                created_at, updated_at)
            VALUES(:name, :pt, :br, :cost, :wt, :vat, :now, :now)"""),
            {"name": name, "pt": self._int(data.get("product_type_id")),
             "br": self._int(data.get("brand_id")),
             "cost": self._float(data.get("cost")),
             "wt": self._float(data.get("weight")),
             "vat": data.get("vat_rate") or None, "now": _now()})).lastrowid
        await self.db.commit()
        return {"ok": True, "id": int(pid)}

    async def product_update(self, product_id: int, data: dict) -> dict:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("Название обязательно")
        await self.db.execute(text("""
            UPDATE product SET name = :name, product_type_id = :pt, brand_id = :br,
                   cost = :cost, weight = :wt, vat_rate = :vat, updated_at = :now
            WHERE id = :id"""),
            {"name": name, "pt": self._int(data.get("product_type_id")),
             "br": self._int(data.get("brand_id")),
             "cost": self._float(data.get("cost")),
             "wt": self._float(data.get("weight")),
             "vat": data.get("vat_rate") or None, "now": _now(), "id": product_id})
        await self.db.commit()
        return {"ok": True}

    async def product_delete(self, product_id: int) -> dict:
        await self.db.execute(text(
            "DELETE FROM product_wb_card WHERE product_id = :id"), {"id": product_id})
        await self.db.execute(text("DELETE FROM product WHERE id = :id"), {"id": product_id})
        await self.db.commit()
        return {"ok": True}

    # --- состав линейки ----------------------------------------------------
    async def product_links(self, product_id: int) -> dict:
        """Связки линейки + карточки компании + сумма p по каждой карточке."""
        cid = "" if self.company_id is None else " AND c.company_id = :cid"
        params: dict = {"id": product_id,
                        **({} if self.company_id is None else {"cid": self.company_id})}
        rows = (await self.db.execute(text(f"""
            SELECT pwc.id, pwc.wb_nm_id, pwc.q, pwc.p, pwc.type,
                   c.vendorCode, c.title
            FROM product_wb_card pwc
            INNER JOIN wbcards c ON c.nmID = pwc.wb_nm_id{cid}
            WHERE pwc.product_id = :id
            ORDER BY pwc.wb_nm_id ASC"""), params)).mappings().all()
        sums = (await self.db.execute(text(f"""
            SELECT pwc2.wb_nm_id, SUM(pwc2.p) AS p_sum
            FROM product_wb_card pwc2
            WHERE pwc2.wb_nm_id IN (SELECT wb_nm_id FROM product_wb_card WHERE product_id = :id)
            GROUP BY pwc2.wb_nm_id"""), {"id": product_id})).mappings().all()
        p_sum = {int(r["wb_nm_id"]): float(r["p_sum"] or 0) for r in sums}
        return {"rows": [dict(r) for r in rows],
                "p_sum": {str(k): round(v, 2) for k, v in p_sum.items()}}

    async def product_links_save(self, product_id: int, items: list[dict]) -> dict:
        """Замена состава линейки (порт ProductController actionCreate/Update: full replace).

        Карточки валидируются по компании; после замены нормируем p до 100
        по каждой затронутой карточке (по всем её линейкам).
        """
        row = (await self.db.execute(text(
            "SELECT id FROM product WHERE id = :id LIMIT 1"), {"id": product_id})).first()
        if not row:
            raise ValueError("Линейка не найдена")

        clean: list[dict] = []
        seen: set[int] = set()
        for it in items or []:
            nm = self._int(it.get("wb_nm_id"))
            if not nm or nm in seen:
                continue
            q = self._int(it.get("q"))
            p = self._float(it.get("p"))
            t = self._int(it.get("type"))
            if q is not None and q < 0:
                q = None
            clean.append({
                "nm": nm, "q": q if q is not None else 1,
                "p": round(max(0.0, p if p is not None else 0.0), 2),
                "type": t if t is not None and 0 <= t <= 9 else 1,
            })
            seen.add(nm)
        # валидация карточек по компании
        ids = [c["nm"] for c in clean]
        if ids:
            markers, binds = self._in_list(ids, "nm")
            cid = "" if self.company_id is None else " AND company_id = :cid"
            params = {**binds, **({"cid": self.company_id} if self.company_id is not None else {})}
            found = {int(r[0]) for r in (await self.db.execute(text(
                f"SELECT nmID FROM wbcards WHERE nmID IN {markers}{cid}"), params)).all()}
            clean = [c for c in clean if c["nm"] in found]

        await self.db.execute(text(
            "DELETE FROM product_wb_card WHERE product_id = :id"), {"id": product_id})
        for c in clean:
            await self.db.execute(text("""
                INSERT INTO product_wb_card(product_id, wb_nm_id, q, p, type)
                VALUES(:pid, :nm, :q, :p, :t)"""),
                {"pid": product_id, "nm": c["nm"], "q": c["q"], "p": c["p"], "t": c["type"]})
        await self.db.commit()

        adjusted = await self.normalize_p([c["nm"] for c in clean])
        return {"ok": True, "saved": len(clean), "normalized": adjusted}

    async def normalize_p(self, nm_ids: list[int]) -> list[dict]:
        """Нормировка p до 100 по карточке (по всем её строкам во всех линейках)."""
        out: list[dict] = []
        if not nm_ids:
            return out
        markers, binds = self._in_list(nm_ids, "nm")
        rows = (await self.db.execute(text(f"""
            SELECT wb_nm_id, SUM(p) AS p_sum FROM product_wb_card
            WHERE wb_nm_id IN {markers} GROUP BY wb_nm_id"""), binds)).mappings().all()
        for r in rows:
            nm, s = int(r["wb_nm_id"]), float(r["p_sum"] or 0)
            if s <= 0 or abs(s - 100.0) < 0.01:
                continue
            k = 100.0 / s
            upd = []
            rr = (await self.db.execute(text(
                "SELECT id, p FROM product_wb_card WHERE wb_nm_id = :nm"),
                {"nm": nm})).mappings().all()
            for link in rr:
                new_p = round(float(link["p"] or 0) * k, 2)
                upd.append((new_p, int(link["id"])))
            for new_p, lid in upd:
                await self.db.execute(text(
                    "UPDATE product_wb_card SET p = :p WHERE id = :id"),
                    {"p": new_p, "id": lid})
            out.append({"wb_nm_id": nm, "was": round(s, 2), "now": 100.0})
        if out:
            await self.db.commit()
        return out

    # --- справочники ---------------------------------------------------------
    async def product_types(self) -> dict:
        rows = (await self.db.execute(text(
            "SELECT id, name, description FROM product_type ORDER BY name ASC"))).mappings().all()
        return {"rows": [dict(r) for r in rows]}

    async def product_type_save(self, data: dict, item_id: int | None = None) -> dict:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("Название обязательно")
        if item_id is None:
            pid = (await self.db.execute(text(
                "INSERT INTO product_type(name, description, created_at, updated_at)"
                " VALUES(:n, :d, :now, :now)"),
                {"n": name, "d": data.get("description") or None, "now": _now()})).lastrowid
            await self.db.commit()
            return {"ok": True, "id": int(pid)}
        await self.db.execute(text(
            "UPDATE product_type SET name = :n, description = :d, updated_at = :now WHERE id = :id"),
            {"n": name, "d": data.get("description") or None, "now": _now(), "id": item_id})
        await self.db.commit()
        return {"ok": True}

    async def product_type_delete(self, item_id: int) -> dict:
        used = (await self.db.execute(text(
            "SELECT COUNT(*) FROM product WHERE product_type_id = :id"), {"id": item_id}
        )).scalar() or 0
        if used:
            raise ValueError(f"Тип используется в {used} линейках — сначала уберите связи")
        await self.db.execute(text("DELETE FROM product_type WHERE id = :id"), {"id": item_id})
        await self.db.commit()
        return {"ok": True}

    async def brands(self) -> dict:
        rows = (await self.db.execute(text(
            "SELECT id, name FROM brand ORDER BY name ASC"))).mappings().all()
        return {"rows": [dict(r) for r in rows]}

    async def brand_save(self, data: dict, item_id: int | None = None) -> dict:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("Название обязательно")
        if item_id is None:
            bid = (await self.db.execute(text(
                "INSERT INTO brand(name, created_at, updated_at) VALUES(:n, :now, :now)"),
                {"n": name, "now": _now()})).lastrowid
            await self.db.commit()
            return {"ok": True, "id": int(bid)}
        await self.db.execute(text(
            "UPDATE brand SET name = :n, updated_at = :now WHERE id = :id"),
            {"n": name, "now": _now(), "id": item_id})
        await self.db.commit()
        return {"ok": True}

    async def brand_delete(self, item_id: int) -> dict:
        used = (await self.db.execute(text(
            "SELECT COUNT(*) FROM product WHERE brand_id = :id"), {"id": item_id}
        )).scalar() or 0
        if used:
            raise ValueError(f"Бренд используется в {used} линейках — сначала уберите связи")
        await self.db.execute(text("DELETE FROM brand WHERE id = :id"), {"id": item_id})
        await self.db.commit()
        return {"ok": True}

    # --- утилиты --------------------------------------------------------------
    @staticmethod
    def _int(v) -> int | None:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float(v) -> float | None:
        try:
            if v in (None, ""):
                return None
            return round(float(v), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _in_list(ids: list[int], prefix: str) -> tuple[str, dict]:
        return ("(" + ", ".join(f":{prefix}{i}" for i in range(len(ids))) + ")",
                {f"{prefix}{i}": int(v) for i, v in enumerate(ids)})
