"""Общие колонки маржи (порт WbProfitController::actionTopProducts).

Правило: формулы правятся ТОЛЬКО здесь. Используют TopProductsService и TagMarginService.
"""
from datetime import date, timedelta

SORTABLE = ("qnt", "amount", "net_profit", "clean_margin")

MARGIN_DIMENSIONS = [
    "p.nm_id",
    "c.title",
    "c.brand",
    "c.vendorCode as vendor_code",
]

MARGIN_SELECT = [
    "SUM(p.qnt) as qnt",
    "SUM(p.amount) as amount",
    "SUM(p.`return`) as return_sum",
    "SUM(p.commission) as commission",
    "SUM(p.f_acquiring_fee) as f_acquiring_fee",
    "SUM(p.f_acceptance) as f_acceptance",
    "SUM(p.f_delivery) as f_delivery",
    "SUM(p.f_storage_fee) as f_storage_fee",
    "SUM(p.f_penalty) as f_penalty",
    "SUM(p.f_deduction) as f_deduction",
    "SUM(p.ff_otziv) as f_otziv",
    "SUM(IFNULL(p.ff_adv, 0)) as f_adv",
    "SUM(p.f_cashback) as f_cashback",
    "SUM(p.net_profit) - SUM(IFNULL(p.ff_otziv, 0)) - SUM(IFNULL(p.ff_adv, 0)) as net_profit",
    "SUM(IFNULL(p.f_nds, 0)) as total_nds",
    "SUM(IFNULL(p.f_cost_price, 0)) as total_cost",
    "SUM(p.net_profit) - SUM(IFNULL(p.f_nds, 0)) - SUM(IFNULL(p.f_cost_price, 0)) - SUM(IFNULL(p.ff_otziv, 0)) - SUM(IFNULL(p.ff_adv, 0)) as profit_before_tax",
    "GREATEST(0, SUM(p.net_profit) - SUM(IFNULL(p.f_nds, 0)) - SUM(IFNULL(p.f_cost_price, 0)) - SUM(IFNULL(p.ff_otziv, 0)) - SUM(IFNULL(p.ff_adv, 0))) * 0.07 as tax_amount",
    "(SUM(p.net_profit) - SUM(IFNULL(p.f_nds, 0)) - SUM(IFNULL(p.f_cost_price, 0)) - SUM(IFNULL(p.ff_otziv, 0)) - SUM(IFNULL(p.ff_adv, 0))) - (GREATEST(0, SUM(p.net_profit) - SUM(IFNULL(p.f_nds, 0)) - SUM(IFNULL(p.f_cost_price, 0)) - SUM(IFNULL(p.ff_otziv, 0)) - SUM(IFNULL(p.ff_adv, 0))) * 0.07) as clean_margin",
    "SUM(p.amount) / NULLIF(SUM(p.qnt), 0) as amount_per_item",
    "SUM(p.net_profit) / NULLIF(SUM(p.qnt), 0) as profit_per_item",
    "((SUM(p.net_profit) - SUM(IFNULL(p.f_nds, 0)) - SUM(IFNULL(p.f_cost_price, 0)) - SUM(IFNULL(p.ff_otziv, 0)) - SUM(IFNULL(p.ff_adv, 0))) - (GREATEST(0, SUM(p.net_profit) - SUM(IFNULL(p.f_nds, 0)) - SUM(IFNULL(p.f_cost_price, 0)) - SUM(IFNULL(p.ff_otziv, 0)) - SUM(IFNULL(p.ff_adv, 0))) * 0.07)) / NULLIF(SUM(p.qnt), 0) as clear_per_item",
    "SUM(IFNULL(p.f_cost_price, 0)) / NULLIF(SUM(p.qnt), 0) as cost_per_item",
]


def validate_sort(sort_by: str) -> str:
    return sort_by if sort_by in SORTABLE else "qnt"


def default_period(date_from: str | None, date_to: str | None, days: int = 30) -> tuple[str, str]:
    if not date_from:
        date_from = (date.today() - timedelta(days=days)).isoformat()
    if not date_to:
        date_to = date.today().isoformat()
    return date_from, date_to
