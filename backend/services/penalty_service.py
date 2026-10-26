"""Отчёт «Штрафы и потери на доставке» — порт WbPenaltyController + DetailByPeriod.

Источник данных — `detail_by_period` (финетализация WB, sales-reports/detailed).
Собственных таблиц у отчёта нет: это срез операций доставки.

ВАЖНО (проверено на боевой БД, 2026-10-26):
  * WB переименовала операцию «Логистика» → «Доставка» (август 2026, ~8-е число);
    старые строки остались с прежним именем → фильтр всегда IN (см. services/wb_ops.py);
  * WB переименовывает и `bonus_type_name`
    («От клиента при отмене» → «От клиенту при отмене»)
    → разбивка по причинам строится на ШАБЛОНАХ (LIKE), а не на точных названиях;
  * штрафы WB за нарушения продавца — ОТДЕЛЬНАЯ операция «Штраф» (сумма в колонке
    `penalty`), в срез доставки они не попадают → отдельный блок отчёта.

Разбивка потерь на доставке:
  Отмены  — bonus_type_name LIKE '%отмен%'
  Возвраты — LIKE '%возврат%' AND NOT LIKE '%брак%'
  Брак    — LIKE '%брак%'
  Прочее  — всё остальное (кроме штатной «К клиенту при продаже»)

ДИСЦИПЛИНА SQL (AGENTS.md §4):
  * ВСЕ запросы идут по company_id + rr_dt BETWEEN + supplier_oper_name IN (...)
    → индексы idx_company_rr_dt (company_id, rr_dt) и
       idx_detail_by_period_perf_rr (rr_dt, supplier_oper_name, bonus_type_name);
  * ни одного запроса без фильтра по компании/периоду;
  * агрегация — ОДИН проход по срезу, счётчик строк берётся из
    COUNT(*) OVER () в том же запросе (второго прохода нет);
  * пагинация — LIMIT/OFFSET в SQL;
  * DISTINCT только по двум спискам фильтров и обрезан LIMIT.

ПРО `COUNT(DISTINCT d.srid)`: srid — это varchar(255), но по факту там id заказа
(«12345678/1», до ~20 символов), а не свободный текст; DISTINCT считается по
срезу из одних строк доставки (сентябрь 2026 — 6 012 строк на компанию),
поэтому риск раздувания памяти минимальный. Это тот же запрос, что years
работал в Yii2 (WbPenaltyController::getProductSummary). «Кол-во» = число
заказов (а не строк) — поэтому рядом есть `rows_count` = COUNT(*).
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_ops import (
    LOGISTICS_OPS, PENALTY_OP, REASON_DEFECT, REASON_DELIVERY_PLAIN,
    REASON_FROM_CLIENT_CANCEL, REASON_FROM_CLIENT_RETURN,
    REASON_TO_CLIENT_CANCEL, ops_sql,
)

OPS_SQL = ops_sql(LOGISTICS_OPS)
PENALTY_OP_SQL = ops_sql((PENALTY_OP,))

# Строки отчёта ограничиваем: защита от случайного «год за раз»
MAX_ROWS = 2000
MAX_PAGE = 200


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def reason_bucket(reason: str) -> str:
    """Разносит причину по корзине (те же 5 корзин, что и в SQL отчёта):
    to_client_cancel / from_client_cancel / from_client_return / defect / other.

    Порядок важен: «Возврат брака (К продавцу)» содержит и «возврат», и «брак» —
    брак проверяем первым.
    """
    r = (reason or "").lower()
    if "брак" in r:
        return "defect"
    if r.startswith("к клиенту при отмене"):
        return "to_client_cancel"
    if "при отмене" in r:
        return "from_client_cancel"
    if "при возврате" in r:
        return "from_client_return"
    return "other"


class PenaltyService:
    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _scope(self) -> tuple[str, dict]:
        """Строка скоупа компании + параметры.

        company_id=None (global admin) — фильтр НЕ ставится: админ видит всё,
        как и в Yii2 (CompanyActiveQuery: при currentId=null скоуп не добавляется).
        """
        if self.company_id is None:
            return "", {}
        return " AND d.company_id = :cid", {"cid": self.company_id}

    def _base(self, alias: str = "d", office_name: str | None = None,
              bonus_type_name: str | None = None,
              nm_id: int | None = None) -> tuple[str, dict]:
        """Базовый WHERE отчёта: операция доставки + период по rr_dt (+ фильтры).

        company_id обязателен: без него отчёт показал бы чужие компании.
        """
        where = (
            f" AND {alias}.supplier_oper_name IN {OPS_SQL}"
            f" AND {alias}.rr_dt BETWEEN :d1 AND :d2"
            f" AND ({alias}.bonus_type_name IS NULL"
            f"      OR {alias}.bonus_type_name <> :plain_delivery)"
        )
        params: dict = {"d1": None, "d2": None, "plain_delivery": REASON_DELIVERY_PLAIN}
        if self.company_id is not None:
            where += f" AND {alias}.company_id = :cid"
            params["cid"] = self.company_id
        if office_name:
            where += f" AND {alias}.office_name = :office_name"
            params["office_name"] = office_name
        if bonus_type_name:
            where += f" AND {alias}.bonus_type_name = :bonus_type_name"
            params["bonus_type_name"] = bonus_type_name
        if nm_id:
            where += f" AND {alias}.nm_id = :nm_id"
            params["nm_id"] = int(nm_id)
        return where, params

    async def _run(self, sql: str, params: dict) -> list[dict]:
        rows = (await self.db.execute(text(sql), params)).mappings().all()
        return [dict(r) for r in rows]

    # --- 1. Итого за период, по причинам ---------------------------------

    async def summary_by_period(self, date_from: str, date_to: str,
                                office_name: str | None = None,
                                bonus_type_name: str | None = None,
                                nm_id: int | None = None) -> list:
        where, params = self._base("d", office_name, bonus_type_name, nm_id)
        params.update({"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"})
        sql = f"""SELECT COALESCE(d.bonus_type_name, '—') AS bonus_type_name,
                         COUNT(DISTINCT d.srid) AS items_count,
                         COUNT(*) AS rows_count,
                         ROUND(SUM(d.delivery_rub), 2) AS total_sum
                  FROM detail_by_period d
                  WHERE 1=1{where}
                  GROUP BY COALESCE(d.bonus_type_name, '—')
                  ORDER BY total_sum DESC
                  LIMIT {MAX_ROWS}"""
        return await self._run(sql, params)

    # --- 2. Сводная по товарам -------------------------------------------

    async def product_summary(self, date_from: str, date_to: str,
                              page: int = 1, page_size: int = 50,
                              office_name: str | None = None,
                              bonus_type_name: str | None = None,
                              nm_id: int | None = None) -> dict:
        where, params = self._base("d", office_name, bonus_type_name, nm_id)
        params.update({"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"})
        lim = max(1, min(int(page_size or 50), MAX_PAGE))
        off = max(0, (max(1, int(page or 1)) - 1) * lim)
        sql = f"""SELECT t.*, COUNT(*) OVER () AS total_rows FROM (
                     SELECT d.nm_id AS nm_id,
                            MAX(c.title) AS card_name,
                            COUNT(DISTINCT d.srid) AS items_count,
                            ROUND(SUM(CASE WHEN d.bonus_type_name LIKE 'К клиенту при отмене%'
                                           THEN d.delivery_rub ELSE 0 END), 2) AS sum_to_client_cancel,
                            ROUND(SUM(CASE WHEN d.bonus_type_name LIKE 'От клиент% при отмене%'
                                           THEN d.delivery_rub ELSE 0 END), 2) AS sum_from_client_cancel,
                            ROUND(SUM(CASE WHEN d.bonus_type_name LIKE 'От клиент% при возврате%'
                                           THEN d.delivery_rub ELSE 0 END), 2) AS sum_from_client_return,
                            ROUND(SUM(CASE WHEN d.bonus_type_name LIKE '%брак%'
                                           THEN d.delivery_rub ELSE 0 END), 2) AS sum_defect,
                            ROUND(SUM(d.delivery_rub)
                                  - SUM(CASE WHEN d.bonus_type_name LIKE 'К клиенту при отмене%'
                                             THEN d.delivery_rub ELSE 0 END)
                                  - SUM(CASE WHEN d.bonus_type_name LIKE 'От клиент% при отмене%'
                                             THEN d.delivery_rub ELSE 0 END)
                                  - SUM(CASE WHEN d.bonus_type_name LIKE 'От клиент% при возврате%'
                                             THEN d.delivery_rub ELSE 0 END)
                                  - SUM(CASE WHEN d.bonus_type_name LIKE '%брак%'
                                             THEN d.delivery_rub ELSE 0 END), 2) AS sum_other,
                            ROUND(SUM(d.delivery_rub), 2) AS total_sum
                     FROM detail_by_period d
                     LEFT JOIN wbcards c ON c.nmID = d.nm_id
                     WHERE 1=1{where}
                     GROUP BY d.nm_id
                  ) t
                  ORDER BY total_sum DESC
                  LIMIT {lim} OFFSET {off}"""
        rows = await self._run(sql, params)
        total = int(rows[0]["total_rows"]) if rows else 0
        for r in rows:
            r.pop("total_rows", None)
        return {"rows": rows, "total": total, "page": max(1, int(page or 1)),
                "page_size": lim}

    # --- 3. Статистика по дням -------------------------------------------

    async def summary_by_days(self, date_from: str, date_to: str,
                              office_name: str | None = None,
                              bonus_type_name: str | None = None,
                              nm_id: int | None = None) -> list:
        where, params = self._base("d", office_name, bonus_type_name, nm_id)
        params.update({"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"})
        sql = f"""SELECT DATE(d.rr_dt) AS date_only,
                         COALESCE(d.bonus_type_name, '—') AS bonus_type_name,
                         COUNT(DISTINCT d.srid) AS items_count,
                         ROUND(SUM(d.delivery_rub), 2) AS total_sum
                  FROM detail_by_period d
                  WHERE 1=1{where}
                  GROUP BY DATE(d.rr_dt), COALESCE(d.bonus_type_name, '—')
                  ORDER BY date_only DESC, total_sum DESC
                  LIMIT {MAX_ROWS}"""
        return await self._run(sql, params)

    # --- 4. Детализация (строки) -----------------------------------------

    async def detail(self, date_from: str, date_to: str, nm_id: int | None = None,
                     office_name: str | None = None,
                     bonus_type_name: str | None = None,
                     page: int = 1, page_size: int = 50) -> dict:
        where, params = self._base("d", office_name, bonus_type_name)
        params.update({"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"})
        extra = ""
        if nm_id:
            extra += " AND d.nm_id = :nm_id"
            params["nm_id"] = int(nm_id)
        lim = max(1, min(int(page_size or 50), MAX_PAGE))
        off = max(0, (max(1, int(page or 1)) - 1) * lim)
        sql = f"""SELECT d.rr_dt AS rr_dt, d.nm_id AS nm_id,
                         c.title AS card_name,
                         d.office_name AS office_name,
                         COALESCE(d.bonus_type_name, '—') AS bonus_type_name,
                         d.delivery_rub AS delivery_rub,
                         d.srid AS srid,
                         COUNT(*) OVER () AS total_rows
                  FROM detail_by_period d
                  LEFT JOIN wbcards c ON c.nmID = d.nm_id
                  WHERE 1=1{where}{extra}
                  ORDER BY d.rr_dt DESC, d.rrd_id DESC
                  LIMIT {lim} OFFSET {off}"""
        rows = await self._run(sql, params)
        total = int(rows[0]["total_rows"]) if rows else 0
        for r in rows:
            r.pop("total_rows", None)
        return {"rows": rows, "total": total, "page": max(1, int(page or 1)),
                "page_size": lim}

    # --- 5. Списки для фильтров ------------------------------------------

    async def filter_lists(self, date_from: str, date_to: str) -> dict:
        where, params = self._base()
        params.update({"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"})
        offices = await self._run(f"""SELECT DISTINCT d.office_name AS office_name
                                     FROM detail_by_period d
                                     WHERE 1=1{where}
                                       AND d.office_name IS NOT NULL
                                       AND d.office_name <> ''
                                     ORDER BY d.office_name
                                     LIMIT {MAX_ROWS}""", params)
        reasons = await self._run(f"""SELECT DISTINCT COALESCE(d.bonus_type_name, '—') AS bonus_type_name
                                     FROM detail_by_period d
                                     WHERE 1=1{where}
                                     ORDER BY COALESCE(d.bonus_type_name, '—')
                                     LIMIT {MAX_ROWS}""", params)
        docs = await self._run(f"""SELECT DISTINCT COALESCE(d.doc_type_name, '—') AS doc_type_name
                                   FROM detail_by_period d
                                   WHERE 1=1{where}
                                   LIMIT 50""", params)
        return {
            "offices": [r["office_name"] for r in offices],
            "reasons": [r["bonus_type_name"] for r in reasons],
            "doc_types": [r["doc_type_name"] for r in docs],
        }

    # --- 6. Штрафы WB (отдельная операция «Штраф») -----------------------

    async def wb_penalties(self, date_from: str, date_to: str) -> dict:
        scope, params = self._scope()
        params.update({"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"})
        sql = f"""SELECT COALESCE(d.bonus_type_name, '—') AS bonus_type_name,
                         COUNT(*) AS items_count,
                         ROUND(SUM(d.penalty), 2) AS total_sum
                  FROM detail_by_period d
                  WHERE d.supplier_oper_name IN {PENALTY_OP_SQL}
                    AND d.rr_dt BETWEEN :d1 AND :d2{scope}
                  GROUP BY COALESCE(d.bonus_type_name, '—')
                  ORDER BY total_sum DESC
                  LIMIT {MAX_ROWS}"""
        rows = await self._run(sql, params)
        total = round(sum(float(r["total_sum"] or 0) for r in rows), 2)
        return {"rows": rows, "total_sum": total,
                "total_count": sum(int(r["items_count"] or 0) for r in rows)}

    # --- 7. Попап-расшифровка «Логистики» --------------------------------

    async def popup(self, date_from: str, date_to: str,
                    nm_id: int | None = None) -> dict:
        where, params = self._base()
        params.update({"d1": f"{date_from} 00:00:00", "d2": f"{date_to} 23:59:59"})
        if nm_id:
            where += " AND d.nm_id = :nm_id"
            params["nm_id"] = int(nm_id)
        by_reason = await self._run(f"""SELECT COALESCE(d.bonus_type_name, '—') AS reason,
                                            COUNT(DISTINCT d.srid) AS items_count,
                                            ROUND(SUM(d.delivery_rub), 2) AS amount
                                     FROM detail_by_period d
                                     WHERE 1=1{where}
                                     GROUP BY COALESCE(d.bonus_type_name, '—')
                                     ORDER BY amount DESC
                                     LIMIT {MAX_ROWS}""", params)
        items = await self._run(f"""SELECT d.rr_dt AS row_date, d.nm_id AS nmID,
                                           MAX(c.title) AS card_title,
                                           ROUND(SUM(d.delivery_rub), 2) AS amount,
                                           COALESCE(d.bonus_type_name, '—') AS reason
                                    FROM detail_by_period d
                                    LEFT JOIN wbcards c ON c.nmID = d.nm_id
                                    WHERE 1=1{where}
                                    GROUP BY d.rr_dt, d.nm_id, COALESCE(d.bonus_type_name, '—')
                                    ORDER BY amount DESC
                                    LIMIT {MAX_PAGE}""", params)
        total_sum = round(sum(float(r["amount"] or 0) for r in items), 2)
        total_count = sum(int(r["items_count"] or 0) for r in by_reason)
        return {"total_sum": total_sum, "total_count": total_count,
                "by_reason": by_reason, "items": items, "limit": MAX_PAGE}
