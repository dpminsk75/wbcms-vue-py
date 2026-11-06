"""Акции WB — чтение кэша (календарь, номенклатура, пометки пользователя).

Синк с WB живёт в `promotions_sync_service.py` (по конвенции WB_API_SYNC.md),
здесь только чтение данных из БД — страница никогда не ходит в WB сама.

Таблицы:
  wb_promotions           — календарь акций + детали (advantages, ranging, счётчики)
  wb_promotion_products   — номенклатура регулярных акций (цена, скидки, план. цена)
  wb_promotion_decisions  — пометки пользователя (снял рекомендацию / добавил товар)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.sql_bulk import exec_bulk_insert

log = logging.getLogger("wbcms.promotions")


def _i(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") if dt else None


def _loads(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


PROMO_SELECT = """
    SELECT promo_id, name, promo_type, start_dt, end_dt, description,
           advantages, in_promo_leftovers, in_promo_total,
           not_in_promo_leftovers, not_in_promo_total,
           participation_percentage, exception_products_count,
           ranging, fetched_at
    FROM wb_promotions
"""


def _promo_row(row) -> dict:
    d = dict(row)
    d["start_dt"] = _iso(d.get("start_dt"))
    d["end_dt"] = _iso(d.get("end_dt"))
    d["advantages"] = _loads(d.get("advantages"))
    d["ranging"] = _loads(d.get("ranging"))
    d["fetched_at"] = _iso(d.get("fetched_at"))
    d["start_date"] = (d.get("start_dt") or "")[:10]
    d["end_date"] = (d.get("end_dt") or "")[:10]
    return d


class PromotionsService:
    """Чтение кэша акций WB + пометки пользователя."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    # -------------------------------------------------------------- чтение

    async def calendar(self, date_from: str, date_to: str) -> list[dict]:
        """Акции из кэша за период (пересечение с [date_from, date_to])."""
        rows = (await self.db.execute(text(
            PROMO_SELECT + """
            WHERE company_id = :cid
              AND (start_dt IS NULL OR start_dt <= :d2)
              AND (end_dt IS NULL OR end_dt >= :d1)
            ORDER BY start_dt IS NULL, start_dt, promo_id"""),
            {"cid": self.company_id, "d1": date_from, "d2": date_to})).mappings().all()
        return [_promo_row(r) for r in rows]

    async def promo(self, promo_id: int) -> dict | None:
        rows = (await self.db.execute(text(
            PROMO_SELECT + "WHERE company_id = :cid AND promo_id = :pid"),
            {"cid": self.company_id, "pid": int(promo_id)})).mappings().all()
        return _promo_row(rows[0]) if rows else None

    async def fetched_at(self) -> str | None:
        """Когда последний раз обновлялся кэш календаря (для плашки «обновлено»)."""
        row = (await self.db.execute(text(
            "SELECT MAX(fetched_at) FROM wb_promotions WHERE company_id = :cid"),
            {"cid": self.company_id})).first()
        return _iso(row[0]) if row and row[0] else None

    async def products(self, promo_id: int) -> list[dict]:
        """Номенклатура регулярной акции (из кэша)."""
        rows = (await self.db.execute(text("""
            SELECT nm_id, in_action, price, plan_price, currency_code,
                   discount, plan_discount
            FROM wb_promotion_products
            WHERE company_id = :cid AND promo_id = :pid
            ORDER BY in_action DESC, nm_id"""),
            {"cid": self.company_id, "pid": int(promo_id)})).mappings().all()
        return [dict(r) for r in rows]

    async def products_from_prices(self, promo_id: int,
                                   discount_level: int = 30) -> list[dict]:
        """Товары для АВТОАКЦИИ: весь наш ассортимент с текущими ценами и скидками.

        Источник — метод цен WB (GET /api/v2/list/goods/filter); он уже синкается
        в wb_price_history (таймер wbcms-price-sync, каждые 6 ч). Для автоакций
        календарь WB товаров не отдаёт (nomenclatures → 422), поэтому берём
        массив из кэша цен.

        Уровень скидки акции через API недоступен — задаётся вручную (параметр
        расчёта). Он же задаёт плановую цену акции.

        in_action НЕ проставляем: по кэшу цен нельзя понять, участвует товар
        в этой автоакции или нет (эвристика «скидка ≥ уровня акции» считала
        всех наших товаров с большой скидкой и давала одинаковое число для всех
        автоакций). Источник правды по участию — загруженный отчёт WB
        («Товар уже участвует в акции»), см. report_products.
        """
        level = max(0, min(99, int(discount_level or 0)))
        rows = (await self.db.execute(text("""
            SELECT nm_id, MAX(price) AS price, MAX(discounted_price) AS discounted_price,
                   MAX(discount) AS discount
            FROM wb_price_history
            WHERE company_id = :cid AND is_latest = 1
            GROUP BY nm_id"""),
            {"cid": self.company_id})).mappings().all()
        out = []
        for r in rows:
            price = _f(r.get("price"))
            discount = _i(r.get("discount"))
            if price is None:
                continue
            out.append({
                "nm_id": int(r["nm_id"]),
                "in_action": 0,
                "price": price,
                # плановая цена автоакции = цена со скидкой уровня акции
                "plan_price": round(price * (1 - level / 100.0), 2),
                "currency_code": "RUB",
                "discount": discount or 0,
                "plan_discount": level,
            })
        out.sort(key=lambda x: x["nm_id"])
        return out

    # ------------------------------------------------- отчёт WB (ЛК)

    async def report_products(self, promo_id: int) -> list[dict]:
        """Номенклатура автоакции из загруженного отчёта WB.

        Отчёт — выгрузка ЛК WB «Товары для исключения из акции» (лист
        «Отчёт по скидкам»). В нём WB отдаёт по каждому товару плановую цену
        акции, минимальную цену для применения скидки, блокировку, статус
        участия и скидку, которую надо загрузить. Для автоакций это единственный
        источник правды: метод номенклатуры WB их не отдаёт (422).

        Если миграция не применена (нет таблицы/колонок) — не падаем: отдаём
        пусто, страница работает на кэше цен.
        """
        try:
            rows = (await self.db.execute(text("""
                SELECT nm_id, in_action, price, plan_price, currency_code,
                       discount, plan_discount, min_price, blocked, status,
                       turnover_days, stock_wb, stock_fbs, barcode, vendor_code,
                       brand, subject, title, source
                FROM wb_promotion_products
                WHERE company_id = :cid AND promo_id = :pid AND source = 'report'
                ORDER BY in_action DESC, nm_id"""),
                {"cid": self.company_id, "pid": int(promo_id)})).mappings().all()
        except (OperationalError, ProgrammingError) as e:
            await self.db.rollback()
            log.warning("отчёт WB недоступен — проверь миграцию %s: %s",
                        "20261105_wb_promotions.sql", e)
            return []
        out = []
        for r in rows:
            d = dict(r)
            d["in_action"] = int(d.get("in_action") or 0)
            out.append(d)
        return out

    async def report_meta(self, promo_id: int) -> dict:
        """Загружен ли отчёт WB по акции и когда."""
        try:
            row = (await self.db.execute(text(
                "SELECT COUNT(*) AS n, MAX(fetched_at) AS at FROM wb_promotion_products "
                "WHERE company_id = :cid AND promo_id = :pid AND source = 'report'"),
                {"cid": self.company_id, "pid": int(promo_id)})).first()
        except (OperationalError, ProgrammingError) as e:
            await self.db.rollback()
            log.warning("отчёт WB недоступен — проверь миграцию %s: %s",
                        "20261105_wb_promotions.sql", e)
            return {"count": 0, "loaded_at": None}
        return {
            "count": int(row[0] or 0) if row else 0,
            "loaded_at": _iso(row[1]) if row and row[1] else None,
        }

    async def save_report(self, promo_id: int, items: list[dict]) -> int:
        """Сохранить отчёт WB по акции (разобранный на фронте).

        Кладём в ту же таблицу, что и номенклатуру из API: source='report'
        отличает отчёт от данных WB API.
        """
        now = datetime.now().replace(microsecond=0)
        rows = []
        for it in items or []:
            nm = _i(it.get("nm_id"))
            if nm is None:
                continue
            rows.append({
                "company_id": self.company_id,
                "promo_id": int(promo_id),
                "nm_id": nm,
                "in_action": 1 if it.get("in_action") else 0,
                "price": _f(it.get("price")),
                "plan_price": _f(it.get("plan_price")),
                "currency_code": (it.get("currency_code") or "RUB")[:8],
                "discount": _i(it.get("discount")),
                "plan_discount": _i(it.get("plan_discount")),
                "min_price": _f(it.get("min_price")),
                "blocked": 1 if it.get("blocked") else 0,
                "status": (it.get("status") or "")[:255] or None,
                "turnover_days": _f(it.get("turnover_days")),
                "stock_wb": _i(it.get("stock_wb")),
                "stock_fbs": _i(it.get("stock_fbs")),
                "barcode": (it.get("barcode") or "")[:64] or None,
                "vendor_code": (it.get("vendor_code") or "")[:128] or None,
                "brand": (it.get("brand") or "")[:255] or None,
                "subject": (it.get("subject") or "")[:255] or None,
                "title": (it.get("title") or "")[:1024] or None,
                "source": "report",
                "fetched_at": now,
            })
        if not rows:
            return 0
        cols = ["company_id", "promo_id", "nm_id", "in_action", "price",
                "plan_price", "currency_code", "discount", "plan_discount",
                "min_price", "blocked", "status", "turnover_days", "stock_wb",
                "stock_fbs", "barcode", "brand", "subject", "title", "source",
                "fetched_at"]
        upd = ", ".join(f"{c} = new.{c}" for c in
                        ("in_action", "price", "plan_price", "currency_code",
                         "discount", "plan_discount", "min_price", "blocked",
                         "status", "turnover_days", "stock_wb", "stock_fbs",
                         "barcode", "brand", "subject", "title", "source",
                         "fetched_at"))
        suffix = f"AS new ON DUPLICATE KEY UPDATE {upd}"
        try:
            await exec_bulk_insert(self.db, "wb_promotion_products", cols, rows,
                                   suffix=suffix)
            await self.db.commit()
        except (OperationalError, ProgrammingError) as e:
            await self.db.rollback()
            raise RuntimeError(
                "Нет таблицы wb_promotion_products — примените миграцию "
                "backend/migrations/20261105_wb_promotions.sql") from e
        return len(rows)

    async def auto_products(self, promo_id: int, discount_level: int = 30) -> list[dict]:
        """Товары автоакции: отчёт WB, если загружен, иначе весь ассортимент.

        Отчёт — источник правды (WB сам пишет цены, минимальную цену и статус).
        Если его нет — откат на кэш цен WB.
        """
        rows = await self.report_products(promo_id)
        if rows:
            return rows
        return await self.products_from_prices(promo_id, discount_level)

    async def _known_nm_ids(self, nm_ids: list[int]) -> set[int]:
        """Какие из nm_id есть в нашем ассортименте (wbcards)."""
        out: set[int] = set()
        for i in range(0, len(nm_ids), 500):
            chunk = nm_ids[i:i + 500]
            ids = ", ".join(f":n{j}" for j in range(len(chunk)))
            params: dict = {"cid": self.company_id}
            params.update({f"n{j}": v for j, v in enumerate(chunk)})
            rows = (await self.db.execute(text(
                f"SELECT DISTINCT nmID FROM wbcards WHERE nmID IN ({ids}) "
                "AND (company_id = :cid OR company_id IS NULL)"),
                params)).all()
            for r in rows:
                if r and r[0] is not None:
                    out.add(int(r[0]))
        return out

    async def preview_report(self, promo_id: int, items: list[dict]) -> dict:
        """Превью загрузки отчёта WB — dry-run, без записи.

        Показывает: сколько товаров в файле, сколько из них есть в нашем
        ассортименте, какие артикулы неизвестны, что изменится по сравнению с
        текущим отчётом (по ценам, скидкам, минимальной цене и блокировке).
        """
        nm_ids: list[int] = []
        for it in items or []:
            nm = _i(it.get("nm_id"))
            if nm is not None and nm not in nm_ids:
                nm_ids.append(nm)
        known = await self._known_nm_ids(nm_ids)
        cur = {int(r["nm_id"]): r for r in await self.report_products(promo_id)}

        unknown = [nm for nm in nm_ids if nm not in known]
        new_ids = [nm for nm in nm_ids if nm not in cur]
        changed: list[dict] = []
        fields = (("price", "цена"), ("plan_price", "план. цена"),
                  ("discount", "скидка"), ("plan_discount", "загружаемая скидка"),
                  ("min_price", "мин. цена"), ("blocked", "блокировка"))
        for it in items or []:
            nm = _i(it.get("nm_id"))
            if nm is None or nm not in cur:
                continue
            c = cur[nm]
            diff = []
            for key, label in fields:
                new_v = it.get(key)
                if new_v is None:
                    continue
                old_v = c.get(key)
                if key == "blocked":
                    new_v = 1 if new_v else 0
                    old_v = int(old_v or 0)
                try:
                    if abs(float(new_v) - float(old_v or 0)) > 0.001:
                        diff.append(label)
                except (TypeError, ValueError):
                    if str(new_v) != str(old_v):
                        diff.append(label)
            if diff:
                changed.append({"nm_id": nm, "fields": diff})
        return {
            "promo_id": int(promo_id),
            "total": len(nm_ids),
            "known": len(nm_ids) - len(unknown),
            "unknown": unknown[:50],
            "unknown_count": len(unknown),
            "new_count": len(new_ids),
            "changed_count": len(changed),
            "changed": changed[:50],
            "in_action": len([nm for nm in nm_ids if int((cur.get(nm) or {}).get("in_action") or 0)]),
        }

    # -------------------------------------------------------------- пометки

    async def decisions(self, promo_id: int) -> dict[int, dict]:
        rows = (await self.db.execute(text("""
            SELECT nm_id, selected, manual FROM wb_promotion_decisions
            WHERE company_id = :cid AND promo_id = :pid"""),
            {"cid": self.company_id, "pid": int(promo_id)})).mappings().all()
        return {int(r["nm_id"]): {"selected": int(r["selected"] or 0),
                                  "manual": int(r["manual"] or 0)} for r in rows}

    async def save_decisions(self, promo_id: int, items: list[dict],
                             user_id: int | None = None) -> int:
        """Сохранить пометки пользователя (upsert пачкой)."""
        now = datetime.now().replace(microsecond=0)
        rows = []
        for it in items:
            nm = _i(it.get("nm_id"))
            if nm is None:
                continue
            rows.append({
                "company_id": self.company_id, "promo_id": int(promo_id),
                "nm_id": nm, "selected": 1 if it.get("selected") else 0,
                "manual": 1 if it.get("manual", True) else 0,
                "user_id": user_id, "created_at": now, "updated_at": now,
            })
        if not rows:
            return 0
        cols = ["company_id", "promo_id", "nm_id", "selected", "manual",
                "user_id", "created_at", "updated_at"]
        suffix = ("AS new ON DUPLICATE KEY UPDATE "
                  "selected = new.selected, manual = new.manual, "
                  "user_id = new.user_id, updated_at = new.updated_at")
        await exec_bulk_insert(self.db, "wb_promotion_decisions", cols, rows,
                               suffix=suffix)
        await self.db.commit()
        return len(rows)
