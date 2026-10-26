"""Цены и скидки WB — чтение wb_price_history.

Таблицу наполняет `backend/services/price_sync_service.py`
(порт commands/WbPriceController.php).

Схема хранения (история, а не «последнее значение»):
  при смене цены старая запись закрывается (is_latest=0), появляется новая
  (is_latest=1). Поэтому «текущая цена» = строки с is_latest=1,
  а «история изменений» = закрытые записи (is_latest=0) в заданном периоде.

Индексы wb_price_history: PK(id), idx_wb_price_company_nm (company_id, nm_id),
idx_wb_price_lookup (company_id, nm_id, size_id, is_latest).
Все запросы идут по company_id + nm_id (индекс), остальное — остаточное
 условие по небольшой выборке строк карточки.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PriceService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _company_where(self, alias: str = "") -> str:
        prefix = f"{alias}." if alias else ""
        return "" if self.company_id is None else f" AND {prefix}company_id = :company_id"

    def _company_params(self) -> dict:
        return {} if self.company_id is None else {"company_id": self.company_id}

    async def current(self, nm_id: int) -> list:
        """Актуальные цены по размерам карточки (is_latest = 1)."""
        sql = text(f"""SELECT id, size_id, tech_size_name, price, discounted_price,
                              club_discounted_price, currency_code, discount,
                              club_discount, is_bad_turnover, created_at, updated_at
                       FROM wb_price_history
                       WHERE nm_id = :nm_id AND is_latest = 1{self._company_where()}
                       ORDER BY size_id""")
        rows = (await self.db.execute(
            sql, {"nm_id": nm_id, **self._company_params()})).mappings().all()
        return [dict(r) for r in rows]

    async def history(self, nm_id: int, date_from: str, date_to: str,
                      limit: int = 200) -> list:
        """История изменения цены/скидки.

        Берём закрытые записи (is_latest=0), созданные в периоде, + текущие
        записи (is_latest=1), чтобы в попапе была видна точка «сейчас».
        """
        sql = text(f"""SELECT id, size_id, tech_size_name, price, discounted_price,
                              club_discounted_price, discount, club_discount,
                              is_latest, created_at, updated_at
                       FROM wb_price_history
                       WHERE nm_id = :nm_id{self._company_where()}
                         AND (is_latest = 1
                              OR (is_latest = 0 AND created_at BETWEEN :d1 AND :d2))
                       ORDER BY created_at DESC, id DESC
                       LIMIT :lim""")
        params = {"nm_id": nm_id, "d1": f"{date_from} 00:00:00",
                  "d2": f"{date_to} 23:59:59", "lim": max(1, min(limit, 500)),
                  **self._company_params()}
        rows = (await self.db.execute(sql, params)).mappings().all()
        return [dict(r) for r in rows]
