"""Финдетализация WB: sales-reports/detailed -> detail_by_period.

Порт WbDetailFinanceController::actionSync (F1, без адресов!):
POST finance-api.../sales-reports/detailed {dateFrom,dateTo,limit:100000,
period:daily,rrdid}, rrdid-пагинация, 429→65с, темп 61с/запрос, 204/пусто=конец.
Upsert ~70 полей 1в1, чанки 2000, ошибки поштучно, курсор двигаем всегда.
После: forecast по затронутым датам + факты wb_order по затронутым srid
(строками! — PHP-ловушка с int-ключами). Плейсхолдеры с нулями (:s00) —
иначе :s1 наезжает на :s10. Токен raw. Только stdlib.
"""
import json
import time
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

DETAIL_URL = "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed"
TIMEOUT_S = 15
PAGE_LIMIT = 100000
PACE_S = 61

INTS = ("nm_id", "quantity", "sale_percent", "is_kgvp_v2", "srv_dbs",
        "report_type", "payment_schedule", "ppvz_office_id")
DECIMALS = ["retail_price", "retail_amount", "commission_percent",
            "retail_price_withdisc_rub", "delivery_amount", "return_amount",
            "delivery_rub", "ppvz_spp_prc", "ppvz_kvw_prc_base", "ppvz_kvw_prc",
            "ppvz_sales_commission", "ppvz_for_pay", "ppvz_reward", "ppvz_vw",
            "ppvz_vw_nds", "penalty", "additional_payment", "rebill_logistic_cost",
            "storage_fee", "deduction", "acceptance", "product_discount_for_report",
            "supplier_promo", "sup_rating_prc_up", "acquiring_fee", "acquiring_percent",
            "wibes_wb_discount_percent", "cashback_amount", "cashback_discount",
            "cashback_commission_change", "seller_promo_discount", "loyalty_discount",
            "sale_price_promocode_discount_prc", "dlv_prc",
            "sale_price_affiliated_discount_prc", "sale_price_wholesale_discount_prc"]


def _dt(v):
    if not v:
        return None
    s = str(v).strip()
    if len(s) == 10:
        s += " 00:00:00"  # date-only от WB
    if len(s) < 19:
        return None
    try:
        return s[:19].replace("T", " ")
    except (TypeError, ValueError):
        return None


def _num(v, t):
    if v is None or v == "":
        return None
    try:
        out = t(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return round(out, 2) if t is float else out


class FinanceDetailService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, progress=None) -> dict:
        df = date_from or (date.today() - timedelta(days=7)).isoformat()
        dt = date_to or date.today().isoformat()
        plan = await company_sync_plan(
            self.db, self.company_id, "finance", 1,
            pause_fast_s=PACE_S, pause_slow_s=PACE_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth = plan["token"]
        id_before = (await self.db.execute(
            text("SELECT COALESCE(MAX(id), 0) FROM detail_by_period"))).scalar() or 0
        rrdid, total, pages = 0, 0, 0
        err_total, err_sample = 0, ""
        affected_dates: set[str] = set()
        affected_srids: list[str] = []
        while True:
            def _log(m, _p=pages + 1):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(0, 0, st, 0, 0.0, 0.0, 0, f"запрос {_p}: {m}")

            t0 = time.monotonic()
            try:
                data = post_json(DETAIL_URL, {
                    "dateFrom": df, "dateTo": dt, "limit": PAGE_LIMIT,
                    "period": "daily", "rrdid": int(rrdid),
                }, auth, timeout=TIMEOUT_S, log=_log if progress else None)
            except RuntimeError as e:
                if "http=204" in str(e) or "пустой ответ" in str(e):
                    break
                raise
            el = time.monotonic() - t0
            rows = data if isinstance(data, list) else []
            if not rows:
                break
            saved = 0
            for i in range(0, len(rows), 2000):
                n, e, s = await self._save(rows[i:i + 2000], dry_run,
                                           affected_dates, affected_srids)
                saved += n
                err_total += e
                if s and not err_sample:
                    err_sample = s
            total += saved
            pages += 1
            rrdid = rows[-1].get("rrdId", rrdid)
            if progress:
                progress(pages, len(rows), "pause", saved, el, 0.0, PACE_S)
            if len(rows) < PAGE_LIMIT:
                break  # неполная страница — дальше пусто, лишний запрос не нужен
            wait = max(0.0, PACE_S - el)
            if wait:
                time.sleep(wait)
        forecast_n, facts_n = 0, 0
        if not dry_run:
            forecast_n = await self.update_forecast(sorted(affected_dates))
            facts_n = await self.update_facts(sorted(set(affected_srids)))
        id_after = 0
        if not dry_run:
            id_after = (await self.db.execute(
                text("SELECT COALESCE(MAX(id), 0) FROM detail_by_period"))).scalar() or 0
        out = {"company_id": self.company_id, "rows": total,
               "db_inserted": max(0, id_after - id_before) if not dry_run else 0,
               "errors": err_total, "error_sample": err_sample,
               "forecast_dates": forecast_n, "facts": facts_n,
               "token_type": plan["token_type"], "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    def _map(self, x: dict) -> dict:
        r = {
            "company_id": self.company_id,
            "realizationreport_id": x.get("reportId"), "rrd_id": x.get("rrdId", 0),
            "gi_id": x.get("giId"), "shk_id": x.get("shkId"),
            "product_id": x.get("productId"), "rid": x.get("rid"),
            "seller_promo_id": x.get("sellerPromoId"), "loyalty_id": x.get("loyaltyId"),
            "date_from": _dt(x.get("dateFrom")), "date_to": _dt(x.get("dateTo")),
            "create_dt": _dt(x.get("createDate")), "order_dt": _dt(x.get("orderDt")),
            "sale_dt": _dt(x.get("saleDt")), "rr_dt": _dt(x.get("rrDate")),
            "nm_id": x.get("nmId"), "quantity": x.get("quantity"),
            "sale_percent": x.get("salePercent"), "is_kgvp_v2": x.get("isKgvpV2"),
            "srv_dbs": x.get("srvDbs"), "report_type": x.get("reportType"),
            "payment_schedule": x.get("paymentSchedule"),
            "ppvz_office_id": x.get("ppvzOfficeId"),
        }
        for api, col in (
                ("retailPrice", "retail_price"), ("retailAmount", "retail_amount"),
                ("commissionPercent", "commission_percent"),
                ("retailPriceWithDisc", "retail_price_withdisc_rub"),
                ("deliveryAmount", "delivery_amount"), ("returnAmount", "return_amount"),
                ("deliveryService", "delivery_rub"), ("spp", "ppvz_spp_prc"),
                ("kvwBase", "ppvz_kvw_prc_base"), ("kvw", "ppvz_kvw_prc"),
                ("ppvzSalesCommission", "ppvz_sales_commission"),
                ("forPay", "ppvz_for_pay"), ("ppvzReward", "ppvz_reward"),
                ("vw", "ppvz_vw"), ("vwNds", "ppvz_vw_nds"),
                ("penalty", "penalty"), ("additionalPayment", "additional_payment"),
                ("rebillLogisticCost", "rebill_logistic_cost"),
                ("paidStorage", "storage_fee"), ("deduction", "deduction"),
                ("paidAcceptance", "acceptance"),
                ("productDiscountForReport", "product_discount_for_report"),
                ("supplierPromo", "supplier_promo"), ("supRatingUp", "sup_rating_prc_up"),
                ("acquiringFee", "acquiring_fee"),
                ("acquiringPercent", "acquiring_percent"),
                ("wibesDiscountPercent", "wibes_wb_discount_percent"),
                ("cashbackAmount", "cashback_amount"),
                ("cashbackDiscount", "cashback_discount"),
                ("cashbackCommissionChange", "cashback_commission_change"),
                ("sellerPromoDiscount", "seller_promo_discount"),
                ("loyaltyDiscount", "loyalty_discount"),
                ("salePricePromocodeDiscountPrc", "sale_price_promocode_discount_prc"),
                ("dlvPrc", "dlv_prc"),
                ("salePriceAffiliatedDiscountPrc", "sale_price_affiliated_discount_prc"),
                ("salePriceWholesaleDiscountPrc", "sale_price_wholesale_discount_prc")):
            r[col] = _num(x.get(api), float)
        for api, col in (
                ("subjectName", "subject_name"), ("brandName", "brand_name"),
                ("vendorCode", "sa_name"), ("techSize", "ts_name"),
                ("sku", "barcode"), ("docTypeName", "doc_type_name"),
                ("officeName", "office_name"), ("sellerOperName", "supplier_oper_name"),
                ("giBoxTypeName", "gi_box_type_name"),
                ("ppvzOfficeName", "ppvz_office_name"),
                ("ppvzSupplierInn", "ppvz_inn"),
                ("declarationNumber", "declaration_number"),
                ("stickerId", "sticker_id"), ("srid", "srid"),
                ("paymentProcessing", "payment_processing"),
                ("acquiringBank", "acquiring_bank"),
                ("deliveryMethod", "delivery_method"), ("orderUid", "order_uid"),
                ("uuidPromocode", "uuid_promocode"),
                ("ppvzSupplierName", "ppvz_supplier_name"),
                ("rebillLogisticOrg", "rebill_logistic_org"), ("kiz", "kiz"),
                ("bonusTypeName", "bonus_type_name"), ("country", "site_country"),
                ("currency", "currency"), ("title", "title"),
                ("trbxId", "trbx_id"),
                ("articleSubstitution", "article_substitution")):
            r[col] = x.get(api)
        r["is_b2b"] = 1 if x.get("isB2b") in (True, 1, "1") else 0
        r["installment_cofinancing_amount"] = _num(x.get("installmentCofinancingAmount"), float)
        # NOT NULL-колонки без дефолта в запросе — None роняет весь INSERT
        for _c in ("installment_cofinancing_amount",
                   "sale_price_affiliated_discount_prc",
                   "sale_price_wholesale_discount_prc"):
            if r[_c] is None:
                r[_c] = 0.0
        r["suppliercontract_code"] = None
        r["ppvz_supplier_id"] = None
        r["address_id"] = None
        return r

    async def _save(self, rows: list, dry_run: bool,
                    affected_dates: set, affected_srids: list) -> tuple[int, int, str]:
        cols = ["company_id", "realizationreport_id", "rrd_id", "gi_id", "shk_id",
                "product_id", "rid", "seller_promo_id", "loyalty_id", "date_from",
                "date_to", "create_dt", "order_dt", "sale_dt", "rr_dt", "nm_id",
                "quantity", "sale_percent", "is_kgvp_v2", "srv_dbs", "report_type",
                "payment_schedule", "ppvz_office_id"] + DECIMALS + [
                "subject_name", "brand_name", "sa_name", "ts_name", "barcode",
                "doc_type_name", "office_name", "supplier_oper_name",
                "gi_box_type_name", "ppvz_office_name", "ppvz_inn",
                "declaration_number", "sticker_id", "srid", "payment_processing",
                "acquiring_bank", "delivery_method", "order_uid", "uuid_promocode",
                "ppvz_supplier_name", "rebill_logistic_org", "kiz", "bonus_type_name",
                "site_country", "is_b2b", "installment_cofinancing_amount",
                "currency", "title", "trbx_id",
                "article_substitution", "suppliercontract_code", "ppvz_supplier_id",
                "address_id"]
        assert len(cols) == len(set(cols)), f"дубль колонок: {sorted(cols)}"
        n, errs = 0, 0
        err_sample = ""
        for x in rows:
            r = self._map(x)
            if r["rr_dt"]:
                affected_dates.add(str(r["rr_dt"])[:10])
            if r["srid"]:
                affected_srids.append(str(r["srid"]))
            if dry_run:
                n += 1
                continue
            try:
                await self.db.execute(text(f"""
                    INSERT INTO detail_by_period({", ".join(cols)})
                    VALUES({", ".join(":" + c for c in cols)}) AS new
                    ON DUPLICATE KEY UPDATE
                    {", ".join(f"{c} = new.{c}" for c in cols if c != "company_id")}"""),
                    r)
                n += 1
            except Exception as e:
                errs += 1
                if not err_sample:
                    err_sample = f"{type(e).__name__}: {e}"[:300]
        if not dry_run:
            await self.db.commit()
        return n, errs, err_sample

    async def update_forecast(self, dates: list) -> int:
        for i in range(0, len(dates), 30):
            ch = dates[i:i + 30]
            w = len(str(len(ch) - 1))
            ph = ",".join(f":d{j:0{w}d}" for j in range(len(ch)))
            try:
                await self.db.execute(text(f"""
                    INSERT INTO detail_by_period_forecast
                      (company_id, stat_date, warehouse_type, warehouse_name, region_name,
                       category, subject, orders_count, sum_retail_amount, sum_ppvz_for_pay,
                       sum_sales_commission, sum_delivery_rub, sum_acquiring_fee,
                       sum_storage_fee, sum_penalty, sum_deduction)
                    SELECT o.company_id, DATE(d.rr_dt), o.warehouse_type, o.warehouse_name,
                      o.region_name, o.category, o.subject,
                      COUNT(CASE WHEN d.supplier_oper_name = 'Продажа' THEN 1 END),
                      SUM(d.retail_price_withdisc_rub), SUM(d.ppvz_for_pay),
                      SUM(ROUND(d.retail_price_withdisc_rub * d.commission_percent / 100, 2)),
                      SUM(d.delivery_rub), SUM(d.acquiring_fee), SUM(d.storage_fee),
                      SUM(d.penalty), SUM(d.deduction)
                    FROM detail_by_period d
                    JOIN wb_order o ON o.srid = d.srid
                    WHERE d.company_id = :cid AND o.company_id = :cid
                      AND d.rr_dt IS NOT NULL AND DATE(d.rr_dt) IN ({ph})
                      AND d.supplier_oper_name IN ('Продажа', 'Логистика')
                    GROUP BY o.company_id, DATE(d.rr_dt), o.warehouse_type,
                      o.warehouse_name, o.region_name, o.category, o.subject
                    AS new
                    ON DUPLICATE KEY UPDATE
                      orders_count = new.orders_count,
                      sum_retail_amount = new.sum_retail_amount,
                      sum_ppvz_for_pay = new.sum_ppvz_for_pay,
                      sum_sales_commission = new.sum_sales_commission,
                      sum_delivery_rub = new.sum_delivery_rub,
                      sum_acquiring_fee = new.sum_acquiring_fee,
                      sum_storage_fee = new.sum_storage_fee,
                      sum_penalty = new.sum_penalty,
                      sum_deduction = new.sum_deduction"""),
                    {"cid": self.company_id,
                     **{f"d{j:0{w}d}": v for j, v in enumerate(ch)}})
                await self.db.commit()
            except Exception:
                pass
        return len(dates)

    async def update_facts(self, srids: list) -> int:
        srids = sorted({str(s) for s in srids})
        total = 0
        for bi in range(0, len(srids), 500):
            ch = srids[bi:bi + 500]
            w = len(str(len(ch) - 1))
            ph = ",".join(f":s{j:0{w}d}" for j in range(len(ch)))
            p = {"company_id": self.company_id,
                 **{f"s{j:0{w}d}": v for j, v in enumerate(ch)}}
            for sql in (
                """UPDATE wb_order o JOIN (
                     SELECT t.srid, t.delivery_rub, t.delivery_method FROM (
                       SELECT d.srid, d.delivery_rub, d.delivery_method,
                              ROW_NUMBER() OVER (PARTITION BY d.srid ORDER BY d.rrd_id DESC) AS rn
                       FROM detail_by_period d
                       WHERE d.company_id = :company_id AND d.supplier_oper_name = 'Логистика'
                         AND d.delivery_amount > 0 AND d.srid IN ({ph})) t WHERE t.rn = 1
                   ) t ON t.srid = o.srid
                   SET o.delivery_rub = t.delivery_rub, o.delivery_method = t.delivery_method,
                       o.facts_updated_at = NOW()
                   WHERE o.company_id = :company_id""".replace("{ph}", ph),
                """UPDATE wb_order o JOIN (
                     SELECT t.srid, t.delivery_rub AS return_rub FROM (
                       SELECT d.srid, d.delivery_rub,
                              ROW_NUMBER() OVER (PARTITION BY d.srid ORDER BY d.rrd_id DESC) AS rn
                       FROM detail_by_period d
                       WHERE d.company_id = :company_id AND d.supplier_oper_name = 'Логистика'
                         AND d.return_amount > 0 AND d.srid IN ({ph})) t WHERE t.rn = 1
                   ) t ON t.srid = o.srid
                   SET o.return_rub = t.return_rub, o.facts_updated_at = NOW()
                   WHERE o.company_id = :company_id""".replace("{ph}", ph),
                """UPDATE wb_order o JOIN (
                     SELECT t.srid, t.commission_percent, t.retail_price_withdisc_rub,
                            t.acquiring_percent, t.acquiring_fee FROM (
                       SELECT d.srid, d.commission_percent, d.retail_price_withdisc_rub,
                              d.acquiring_percent, d.acquiring_fee,
                              ROW_NUMBER() OVER (PARTITION BY d.srid ORDER BY d.rrd_id DESC) AS rn
                       FROM detail_by_period d
                       WHERE d.company_id = :company_id AND d.supplier_oper_name = 'Продажа'
                         AND d.srid IN ({ph})) t WHERE t.rn = 1
                   ) t ON t.srid = o.srid
                   SET o.commission_percent = t.commission_percent,
                       o.commission_fee = ROUND(t.retail_price_withdisc_rub * t.commission_percent / 100, 2),
                       o.acquiring_percent = t.acquiring_percent,
                       o.acquiring_fee = t.acquiring_fee, o.facts_updated_at = NOW()
                   WHERE o.company_id = :company_id""".replace("{ph}", ph),
                """UPDATE wb_order o JOIN (
                     SELECT t.srid, t.cashback_amount FROM (
                       SELECT d.srid, d.cashback_amount,
                              ROW_NUMBER() OVER (PARTITION BY d.srid ORDER BY d.rrd_id DESC) AS rn
                       FROM detail_by_period d
                       WHERE d.company_id = :company_id
                         AND d.supplier_oper_name = 'Сумма баллов, удержанных за покупку товаров'
                         AND d.srid IN ({ph})) t WHERE t.rn = 1
                   ) t ON t.srid = o.srid
                   SET o.cashback_amount = t.cashback_amount, o.facts_updated_at = NOW()
                   WHERE o.company_id = :company_id""".replace("{ph}", ph),
            ):
                try:
                    r = await self.db.execute(text(sql), p)
                    total += r.rowcount or 0
                except Exception:
                    pass
            await self.db.commit()
        return total
