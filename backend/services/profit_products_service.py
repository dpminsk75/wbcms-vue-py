"""Отчёт «Маржа по продуктам» - порт логики product/product_wb_card на FastAPI.

Правила (зафиксированы владельцем):
  * product = линейка; product_wb_card = состав: q (штук), p (процент карточки).
  * p/q влияют ТОЛЬКО на себестоимость. Выручка/статьи/итог/НДС/маржа = суммы по
    карточкам линейки БЕЗ весов (как отчёт по карточкам).
  * p нормируется по карточке: p_norm = p / SUM(p по карточке во всех линейках).
  * Себестоимость: product.cost задан (>0) -> как есть ("ручная"); иначе производная
    SUM( cost_карточки * q * p_norm ), где cost_карточки = SUM(f_cost_price) куба.
  * Двойной счёт выручки (карточка в 2 линейках) оставляем, показываем предупреждение.

Источники:
  product / product_wb_card / product_type / brand - справочники линеек;
  agg_daily_summary (company_id, sdate, nm_id)    - куб продаж/себестоимости.
"""
from datetime import date, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_DAYS = 400
SORTABLE = ("qnt", "amount", "net_profit", "clean_margin", "total_cost")
ALLOWED_LIMITS = (20, 50, 100, 200, 500)

# --- метрики карточки за период (те же формулы, что в profit_columns.MARGIN_SELECT) ---
CARD_METRICS_SQL = """
SELECT p.nm_id AS nm_id,
       SUM(p.qnt) AS qnt,
       SUM(p.amount) AS amount,
       SUM(p.`return`) AS return_sum,
       SUM(p.commission) AS commission,
       SUM(p.f_acquiring_fee) AS f_acquiring_fee,
       SUM(p.f_acceptance) AS f_acceptance,
       SUM(p.f_delivery) AS f_delivery,
       SUM(IFNULL(p.ff_storage_fee, 0)) AS f_storage_fee,
       SUM(p.f_penalty) AS f_penalty,
       SUM(p.f_deduction) AS f_deduction,
       SUM(IFNULL(p.ff_otziv, 0)) AS f_otziv,
       SUM(IFNULL(p.ff_adv, 0)) AS f_adv,
       SUM(p.f_cashback) AS f_cashback,
       SUM(p.net_profit) - SUM(IFNULL(p.ff_otziv, 0)) - SUM(IFNULL(p.ff_adv, 0))
         - SUM(IFNULL(p.ff_storage_fee, 0)) AS net_profit,
       SUM(IFNULL(p.f_nds, 0)) AS total_nds,
       SUM(IFNULL(p.f_cost_price, 0)) AS total_cost
FROM agg_daily_summary p
WHERE p.sdate BETWEEN :d1 AND :d2{cid_filter}
  AND p.nm_id IN :ids
GROUP BY p.nm_id
"""

# --- состав линейки: product -> product_wb_card -> карточка компании ---
COMPOSITION_SQL = """
SELECT pr.id AS product_id,
       pr.name AS product_name,
       pr.cost AS product_cost,
       pt.name AS product_type,
       b.name AS brand,
       pwc.wb_nm_id AS wb_nm_id,
       pwc.q AS q,
       pwc.p AS p,
       pwc.type AS link_type,
       c.title AS title,
       c.vendorCode AS vendor_code,
       c.brand AS card_brand,
       pn.p_sum AS p_sum
FROM product pr
INNER JOIN product_wb_card pwc ON pwc.product_id = pr.id
INNER JOIN wbcards c ON c.nmID = pwc.wb_nm_id{cid_filter}
LEFT JOIN product_type pt ON pt.id = pr.product_type_id
LEFT JOIN brand b ON b.id = pr.brand_id
LEFT JOIN (
    SELECT pwc2.wb_nm_id, SUM(pwc2.p) AS p_sum
    FROM product_wb_card pwc2
    INNER JOIN wbcards c2 ON c2.nmID = pwc2.wb_nm_id{cid_filter2}
    GROUP BY pwc2.wb_nm_id
) pn ON pn.wb_nm_id = pwc.wb_nm_id
"""

ZERO_METRICS = {
    "qnt": 0.0, "amount": 0.0, "return_sum": 0.0, "commission": 0.0,
    "f_acquiring_fee": 0.0, "f_acceptance": 0.0, "f_delivery": 0.0,
    "f_storage_fee": 0.0, "f_penalty": 0.0, "f_deduction": 0.0, "f_otziv": 0.0,
    "f_adv": 0.0, "f_cashback": 0.0, "net_profit": 0.0, "total_nds": 0.0,
    "total_cost": 0.0,
}
METRIC_KEYS = tuple(ZERO_METRICS.keys())


def default_period(date_from: str | None, date_to: str | None, days: int = 30) -> tuple[str, str]:
    if not date_to:
        date_to = date.today().isoformat()
    if not date_from:
        date_from = (date.fromisoformat(date_to) - timedelta(days=days - 1)).isoformat()
    return date_from, date_to


def validate_sort(sort_by: str | None) -> str:
    return sort_by if sort_by in SORTABLE else "amount"


def _f(v: float, digits: int = 2) -> float:
    return round(float(v) + 0.0, digits)


class ProfitProductsService:
    """Маржа по линейкам (product) за период."""

    def __init__(self, db: AsyncSession, company_id: int | None = None):
        self.db = db
        self.company_id = company_id

    def _cid_filter(self) -> str:
        return " AND p.company_id = :cid" if self.company_id is not None else ""

    def _cid_filter_cards(self) -> str:
        return " AND c.company_id = :cid" if self.company_id is not None else ""

    def _cid_params(self) -> dict:
        return {} if self.company_id is None else {"cid": self.company_id}

    # --- выборки -------------------------------------------------------
    async def _composition(self) -> list[dict]:
        """Связки product -> product_wb_card -> карточка (без метрик)."""
        cid = self._cid_params()
        sql = COMPOSITION_SQL.format(
            cid_filter=self._cid_filter_cards(),
            cid_filter2=self._cid_filter_cards().replace("c.", "c2."))
        rows = (await self.db.execute(text(sql), cid)).mappings().all()
        return [dict(r) for r in rows]

    async def _card_metrics(self, nm_ids: list[int], d1: str, d2: str) -> dict[int, dict]:
        """Метрики куба по карточкам за период."""
        if not nm_ids:
            return {}
        sql = CARD_METRICS_SQL.format(cid_filter=self._cid_filter())
        stmt = text(sql).bindparams(bindparam("ids", expanding=True))
        params = {"d1": d1, "d2": d2, "ids": list(nm_ids), **self._cid_params()}
        rows = (await self.db.execute(stmt, params)).mappings().all()
        out: dict[int, dict] = {}
        for r in rows:
            d = dict(r)
            out[int(d["nm_id"])] = d
        return out

    # --- сборка --------------------------------------------------------
    def _aggregate(self, links: list[dict], metrics: dict[int, dict]) -> dict:
        """Суммы по линейке: статьи без весов, себестоимость - с весами q/p_norm."""
        agg = {k: 0.0 for k in METRIC_KEYS}
        derived_cost = 0.0
        p_incomplete = False
        cards_seen: set[int] = set()
        for lk in links:
            nm = int(lk["wb_nm_id"])
            cards_seen.add(nm)
            m = metrics.get(nm)
            if m:
                for k in METRIC_KEYS:
                    agg[k] += float(m.get(k) or 0)
            # себестоимость: стоимость карточки * q * p_norm
            card_cost = float((m or {}).get("total_cost") or 0)
            p_sum = float(lk.get("p_sum") or 0)
            p_raw = float(lk.get("p") or 0)
            q = float(lk.get("q") or 0)
            if abs(p_sum - 100.0) > 0.01:
                p_incomplete = True
            p_norm = (p_raw / p_sum) if p_sum > 0 else 0.0
            derived_cost += card_cost * q * p_norm

        manual_cost = float(links[0].get("product_cost") or 0) if links else 0.0
        if manual_cost > 0:
            total_cost = manual_cost
            cost_source = "manual"
        elif derived_cost > 0:
            total_cost = derived_cost
            cost_source = "derived"
        else:
            total_cost = 0.0
            cost_source = "none"

        net_profit = agg["net_profit"]
        total_nds = agg["total_nds"]
        profit_before_tax = net_profit - total_nds - total_cost
        tax_amount = max(0.0, profit_before_tax) * 0.07
        clean_margin = profit_before_tax - tax_amount
        qnt = agg["qnt"]
        return {
            "product_id": int(links[0]["product_id"]),
            "product_name": links[0].get("product_name") or "",
            "product_type": links[0].get("product_type") or "",
            "brand": links[0].get("brand") or "",
            "cards_count": len(cards_seen),
            "qnt": _f(qnt),
            "amount": _f(agg["amount"]),
            "return_sum": _f(agg["return_sum"]),
            "commission": _f(agg["commission"]),
            "f_acquiring_fee": _f(agg["f_acquiring_fee"]),
            "f_acceptance": _f(agg["f_acceptance"]),
            "f_delivery": _f(agg["f_delivery"]),
            "f_storage_fee": _f(agg["f_storage_fee"]),
            "f_penalty": _f(agg["f_penalty"]),
            "f_deduction": _f(agg["f_deduction"]),
            "f_otziv": _f(agg["f_otziv"]),
            "f_adv": _f(agg["f_adv"]),
            "f_cashback": _f(agg["f_cashback"]),
            "net_profit": _f(net_profit),
            "total_nds": _f(total_nds),
            "total_cost": _f(total_cost),
            "cost_source": cost_source,
            "profit_before_tax": _f(profit_before_tax),
            "tax_amount": _f(tax_amount),
            "clean_margin": _f(clean_margin),
            "amount_per_item": _f(agg["amount"] / qnt if qnt else 0),
            "profit_per_item": _f(net_profit / qnt if qnt else 0),
            "clear_per_item": _f(clean_margin / qnt if qnt else 0),
            "cost_per_item": _f(total_cost / qnt if qnt else 0),
            "p_incomplete": p_incomplete,
            "no_cost": cost_source == "none",
        }

    def _warnings(self, rows: list[dict], links: list[dict], metrics: dict[int, dict]) -> dict:
        # карточки, входящие в несколько линеек (выручка задвоена)
        by_card: dict[int, int] = {}
        for lk in links:
            nm = int(lk["wb_nm_id"])
            by_card[nm] = by_card.get(nm, 0) + 1
        dup_cards = [nm for nm, cnt in by_card.items() if cnt > 1]
        dup_amount = 0.0
        for nm in dup_cards:
            m = metrics.get(nm)
            if m:
                dup_amount += float(m.get("amount") or 0) * (by_card[nm] - 1)
        p_bad = {int(lk["wb_nm_id"]) for lk in links
                 if abs(float(lk.get("p_sum") or 0) - 100.0) > 0.01}
        return {
            "duplicated_cards": len(dup_cards),
            "duplicated_amount": _f(dup_amount),
            "p_incomplete_cards": len(p_bad),
            "products_without_cost": sum(1 for r in rows if r.get("no_cost")),
            "products_manual_cost": sum(1 for r in rows if r.get("cost_source") == "manual"),
        }

    # --- публичные методы ----------------------------------------------
    async def report(self, date_from: str | None = None, date_to: str | None = None,
                     sort_by: str | None = "amount", limit: int = 100,
                     product_id: int | None = None) -> dict:
        """Свод по линейкам за период."""
        d1, d2 = default_period(date_from, date_to)
        sort_by = validate_sort(sort_by)
        lim = limit if limit in ALLOWED_LIMITS else 100

        links = await self._composition()
        if product_id is not None:
            links = [l for l in links if int(l["product_id"]) == product_id]
        nm_ids = sorted({int(l["wb_nm_id"]) for l in links})
        metrics = await self._card_metrics(nm_ids, d1, d2)

        by_product: dict[int, list[dict]] = {}
        for lk in links:
            by_product.setdefault(int(lk["product_id"]), []).append(lk)

        rows_all = [self._aggregate(ls, metrics) for ls in by_product.values()]
        rows_all.sort(key=lambda r: r.get(sort_by) or 0, reverse=True)
        total_rows = len(rows_all)
        # предупреждения считаются по ВСЕМ линейкам, до усечения limit
        warnings = self._warnings(rows_all, links, metrics)
        rows = rows_all[:lim]

        totals = {k: 0.0 for k in METRIC_KEYS}
        for r in rows:
            for k in METRIC_KEYS:
                totals[k] += float(r.get(k) or 0)
        net_profit = totals["net_profit"]
        total_nds = totals["total_nds"]
        total_cost = totals["total_cost"]
        pbt = net_profit - total_nds - total_cost
        tax = max(0.0, pbt) * 0.07
        qnt = totals["qnt"]
        totals_row = {
            "product_id": 0,
            "product_name": "ИТОГО",
            "product_type": "",
            "brand": "",
            "cards_count": len(nm_ids),
            **{k: _f(totals[k]) for k in METRIC_KEYS},
            "cost_source": "derived",
            "profit_before_tax": _f(pbt),
            "tax_amount": _f(tax),
            "clean_margin": _f(pbt - tax),
            "amount_per_item": _f(totals["amount"] / qnt if qnt else 0),
            "profit_per_item": _f(net_profit / qnt if qnt else 0),
            "clear_per_item": _f((pbt - tax) / qnt if qnt else 0),
            "cost_per_item": _f(total_cost / qnt if qnt else 0),
            "p_incomplete": False,
            "no_cost": False,
        }

        return {
            "rows": rows,
            "totals": totals_row,
            "date_from": d1,
            "date_to": d2,
            "sort_by": sort_by,
            "total_rows": total_rows,
            "warnings": warnings,
        }

    async def product_cards(self, product_id: int, date_from: str | None = None,
                             date_to: str | None = None) -> dict:
        """Состав линейки: карточки + их вклад в себестоимость."""
        d1, d2 = default_period(date_from, date_to)
        links = await self._composition()
        links = [l for l in links if int(l["product_id"]) == product_id]
        nm_ids = sorted({int(l["wb_nm_id"]) for l in links})
        metrics = await self._card_metrics(nm_ids, d1, d2)

        agg = self._aggregate(links, metrics) if links else {}
        rows = []
        for lk in links:
            nm = int(lk["wb_nm_id"])
            m = metrics.get(nm) or {}
            p_sum = float(lk.get("p_sum") or 0)
            p_raw = float(lk.get("p") or 0)
            q = float(lk.get("q") or 0)
            p_norm = (p_raw / p_sum) if p_sum > 0 else 0.0
            card_cost = float(m.get("total_cost") or 0)
            net_profit = float(m.get("net_profit") or 0)
            total_nds = float(m.get("total_nds") or 0)
            cost_contrib = card_cost * q * p_norm
            pbt = net_profit - total_nds - cost_contrib
            tax = max(0.0, pbt) * 0.07
            rows.append({
                "nm_id": nm,
                "title": lk.get("title") or "",
                "brand": lk.get("card_brand") or "",
                "vendor_code": lk.get("vendor_code") or "",
                "q": int(lk.get("q") or 0),
                "p": _f(p_raw),
                "p_norm": _f(p_norm),
                "p_sum": _f(p_sum),
                "link_type": lk.get("link_type"),
                "cost_price": _f(card_cost / (float(m.get("qnt") or 0)) if m.get("qnt") else 0),
                "cost_contribution": _f(cost_contrib),
                "qnt": _f(m.get("qnt") or 0),
                "amount": _f(m.get("amount") or 0),
                "net_profit": _f(net_profit),
                "total_nds": _f(total_nds),
                "total_cost": _f(card_cost),
                "profit_before_tax": _f(pbt),
                "tax_amount": _f(tax),
                "clean_margin": _f(pbt - tax),
                "has_sales": bool(m),
            })

        return {
            "product_id": product_id,
            "product_name": agg.get("product_name") or "",
            "rows": rows,
            "total_cost": agg.get("total_cost", 0.0),
            "cost_source": agg.get("cost_source", "none"),
            "date_from": d1,
            "date_to": d2,
        }

