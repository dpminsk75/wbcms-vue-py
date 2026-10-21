"""Search-report WB (позиции + поисковые фразы) -> wb_sr_report_* + справочник фраз.

Порт commands/WbParserController (actionSearchReport/actionSearchReportRange/
actionUpdateDirectory). Токен — companies.api_key (категория analytics
в company_wb_tokens), гейт + паузы — wb_sync_base (personal/service 20с,
basic 30мин, правило 2ч). Только stdlib.

API seller-analytics-api:
  POST /api/v2/search-report/report                  -> summary/groups/items
  POST /api/v2/search-report/product/search-texts    -> item_phrases
Чанки как в PHP: 150 nmId на основной отчёт, фразы — подчанками по 50.
"""
import json
import time
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

BASE = "https://seller-analytics-api.wildberries.ru"
REPORT_URL = f"{BASE}/api/v2/search-report/report"
PHRASES_URL = f"{BASE}/api/v2/search-report/product/search-texts"
TIMEOUT_S = 120  # отчёты тяжёлые; в PHP клиент был с timeout 180
MAIN_CHUNK = 150
PHRASE_CHUNK = 50


def _j(v) -> str | None:
    return json.dumps(v, ensure_ascii=False) if v is not None else None


def _num(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class SearchReportService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def get_nm_ids(self, target_date: str) -> list[int]:
        """Артикулы компании по заказам за 5д, топ по выручке (1в1 PHP)."""
        d0 = (date.fromisoformat(target_date) - timedelta(days=5)).isoformat()
        rows = (await self.db.execute(text("""
            SELECT o.nm_id FROM wb_order o
            INNER JOIN wbcards c
              ON c.nmID = o.nm_id AND c.company_id = o.company_id
            WHERE o.date >= :d0 AND o.company_id = :cid AND c.company_id = :cid
            GROUP BY o.nm_id ORDER BY SUM(o.finished_price) DESC"""),
            {"d0": d0, "cid": self.company_id})).all()
        return [int(r[0]) for r in rows if r[0] is not None]

    async def sync_date(self, target_date: str, dry_run: bool = False,
                        progress=None) -> dict:
        """Прогон одной даты: main-отчёт чанками + фразы подчанками."""
        nm_ids = await self.get_nm_ids(target_date)
        if not nm_ids:
            return {"company_id": self.company_id, "date": target_date,
                    "nm_ids": 0, "items": 0, "phrases": 0, "dry_run": dry_run}
        chunks = [nm_ids[i:i + MAIN_CHUNK]
                  for i in range(0, len(nm_ids), MAIN_CHUNK)]
        total_reqs = len(chunks) + sum(
            (len(c) + PHRASE_CHUNK - 1) // PHRASE_CHUNK for c in chunks)
        plan = await company_sync_plan(
            self.db, self.company_id, "analytics", total_reqs,
            pause_fast_s=20, pause_slow_s=1800)
        if plan.get("skip"):
            return {"company_id": self.company_id, "date": target_date,
                    "nm_ids": len(nm_ids), "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth, pause = f"Bearer {plan['token']}", plan["pause_s"]
        prev = date.fromisoformat(target_date) - timedelta(days=1)
        prev = prev.isoformat()

        summary_id = None
        if not dry_run:
            await self.db.execute(text("""
                DELETE FROM wb_sr_report_summary
                WHERE period_start = :d AND company_id = :cid"""),
                {"d": target_date, "cid": self.company_id})
            res = await self.db.execute(text("""
                INSERT INTO wb_sr_report_summary
                    (company_id, period_start, period_end, currency)
                VALUES (:cid, :d, :d, 'RUB')"""),
                {"cid": self.company_id, "d": target_date})
            summary_id = res.lastrowid
            await self.db.commit()

        items_total, phrases_total, reqs = 0, 0, 0
        for ci, chunk in enumerate(chunks):
            t0 = time.monotonic()

            def _log(m, _ci=ci):
                if progress:
                    progress("main" if m == "send" else "retry",
                             _ci + 1, len(chunks), m)

            resp = post_json(REPORT_URL, {
                "currentPeriod": {"start": target_date, "end": target_date},
                "pastPeriod": {"start": prev, "end": prev},
                "nmIds": [int(x) for x in chunk],
                "positionCluster": "all",
                "orderBy": {"field": "avgPosition", "mode": "asc"},
                "limit": 1000, "offset": 0,
            }, auth, timeout=TIMEOUT_S, log=_log if progress else None)
            el = time.monotonic() - t0
            body = resp.get("data") if isinstance(resp, dict) else None
            reqs += 1
            if isinstance(body, dict):
                if dry_run:
                    for g in body.get("groups") or []:
                        items_total += len(g.get("items") or [])
                else:
                    items_total += await self._save_main(body, summary_id,
                                                         target_date)
            if progress:
                progress("main", ci + 1, len(chunks),
                         f"api {el:.1f}с, товаров {items_total}")
            wait = max(0.0, pause - el)
            if progress:
                progress("pause", ci + 1, len(chunks), f"пауза {wait:.0f}с")
            time.sleep(wait)  # rate-limit как в PHP (sleep 20)

            subs = [chunk[i:i + PHRASE_CHUNK]
                    for i in range(0, len(chunk), PHRASE_CHUNK)]
            for si, sub in enumerate(subs):
                t1 = time.monotonic()

                def _log2(m):
                    if progress:
                        progress("phrase" if m == "send" else "retry",
                                 si + 1, len(subs), m)

                presp = post_json(PHRASES_URL, {
                    "currentPeriod": {"start": target_date, "end": target_date},
                    "pastPeriod": {"start": prev, "end": prev},
                    "nmIds": [int(x) for x in sub],
                    "topOrderBy": "openToCart",
                    "includeSubstitutedSKUs": True,
                    "includeSearchTexts": True,
                    "orderBy": {"field": "avgPosition", "mode": "asc"},
                    "limit": 30,
                }, auth, timeout=TIMEOUT_S, log=_log2 if progress else None)
                el2 = time.monotonic() - t1
                pbody = presp.get("data") if isinstance(presp, dict) else None
                reqs += 1
                if isinstance(pbody, dict):
                    if dry_run:
                        phrases_total += sum(
                            1 for it in (pbody.get("items") or [])
                            if (it.get("nmId") and it.get("text")))
                    else:
                        phrases_total += await self._save_phrases(
                            pbody, sub, summary_id, target_date)
                if progress:
                    progress("phrase", si + 1, len(subs),
                             f"api {el2:.1f}с, фраз {phrases_total}")
                wait2 = max(0.0, pause - el2)
                if progress:
                    progress("pause", si + 1, len(subs),
                             f"пауза {wait2:.0f}с")
                time.sleep(wait2)
        out = {"company_id": self.company_id, "date": target_date,
               "nm_ids": len(nm_ids), "requests": reqs,
               "items": items_total, "phrases": phrases_total,
               "token_type": plan["token_type"], "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    async def _save_main(self, body: dict, summary_id: int,
                         target_date: str) -> int:
        """Summary-агрегаты + groups/items. Возвращает число товаров."""
        await self.db.execute(text("""
            UPDATE wb_sr_report_summary SET total_products = :tp,
                currency = :cur, supplier_rating_json = :sr,
                advertised_products_json = :ap, position_info_json = :pi,
                visibility_info_json = :vi, raw_json = :raw WHERE id = :sid"""),
            {"tp": _num((body.get("commonInfo") or {}).get("totalProducts")),
             "cur": body.get("currency") or "RUB",
             "sr": _j(body.get("supplierRating")),
             "ap": _j(body.get("advertisedProducts")),
             "pi": _j(body.get("positionInfo")),
             "vi": _j(body.get("visibilityInfo")),
             "raw": _j(body), "sid": summary_id})
        count = 0
        for g in body.get("groups") or []:
            gr = await self.db.execute(text("""
                INSERT INTO wb_sr_report_groups
                    (company_id, summary_id, date, subject_id, subject_name,
                     brand_name, tag_id, tag_name, metrics_json, raw_json)
                VALUES (:cid, :sid, :d, :subj_id, :subj, :brand,
                        :tag_id, :tag, :metrics, :raw)"""),
                {"cid": self.company_id, "sid": summary_id, "d": target_date,
                 "subj_id": g.get("subjectId"), "subj": str(g.get("subjectName") or ""),
                 "brand": str(g.get("brandName") or ""),
                 "tag_id": g.get("tagId"), "tag": str(g.get("tagName") or ""),
                 "metrics": _j(g.get("metrics")), "raw": _j(g)})
            gid = gr.lastrowid
            rows = [self._item_row(it, gid, target_date)
                    for it in g.get("items") or [] if it.get("nmId")]
            if rows:
                await self.db.execute(text("""
                    INSERT INTO wb_sr_report_items
                        (company_id, group_id, date, nmID, vendor_code, name,
                         brand_name, subject_name, is_advertised, is_card_rated,
                         rating, feedback_rating, avg_position, clicks, orders,
                         ctr, price_json, metrics_json)
                    VALUES (:cid, :gid, :d, :nm, :vc, :name, :brand, :subj,
                            :adv, :rated, :rating, :frating, :pos, :clicks,
                            :orders, :ctr, :price, :metrics)"""), rows)
                count += len(rows)
        await self.db.commit()
        return count

    def _item_row(self, it: dict, gid: int, target_date: str) -> dict:
        return {
            "cid": self.company_id, "gid": gid, "d": target_date,
            "nm": int(it.get("nmId")), "vc": it.get("vendorCode"),
            "name": it.get("name"), "brand": it.get("brandName"),
            "subj": it.get("subjectName"),
            "adv": int(it.get("isAdvertised") or 0),
            "rated": int(it.get("isCardRated") or 0),
            "rating": _fnum(it.get("rating")),
            "frating": _fnum(it.get("feedbackRating")),
            "pos": _num((it.get("avgPosition") or {}).get("current")),
            "clicks": _num((it.get("openCard") or {}).get("current")),
            "orders": _num((it.get("orders") or {}).get("current")),
            "ctr": _fnum((it.get("openToCart") or {}).get("current")),
            "price": _j(it.get("price")), "metrics": _j(it),
        }

    async def _save_phrases(self, body: dict, sub: list[int], summary_id: int,
                            target_date: str) -> int:
        """Фразы подчанка. Связка nmId->item через items этой summary."""
        ph = ",".join(f":n{j}" for j in range(len(sub)))
        have = (await self.db.execute(text(f"""
            SELECT i.id, i.nmID FROM wb_sr_report_items i
            INNER JOIN wb_sr_report_groups g ON g.id = i.group_id
            WHERE g.summary_id = :sid AND i.nmID IN ({ph})"""),
            {"sid": summary_id,
             **{f"n{j}": int(v) for j, v in enumerate(sub)}})).all()
        id_by_nm: dict[int, int] = {}
        for iid, nm in have:
            id_by_nm.setdefault(int(nm), int(iid))
        rows = []
        for it in body.get("items") or []:
            nm, txt = it.get("nmId"), it.get("text")
            if not nm or not txt or int(nm) not in id_by_nm:
                continue
            rows.append({
                "cid": self.company_id, "iid": id_by_nm[int(nm)],
                "d": target_date, "nm": int(nm), "ph": str(txt),
                "pos": _num((it.get("avgPosition") or {}).get("current")),
                "clicks": _num((it.get("openCard") or {}).get("current")),
                "orders": _num((it.get("orders") or {}).get("current")),
                "ctr": _fnum((it.get("openToCart") or {}).get("current")),
                "rated": int(it.get("isCardRated") or 0),
                "rating": _fnum(it.get("rating")),
                "frating": _fnum(it.get("feedbackRating")),
                "freq": _num((it.get("frequency") or {}).get("current")),
                "med": _num((it.get("medianPosition") or {}).get("current")),
                "wf": it.get("weekFrequency"),
                "oc": _j(it.get("openCard")), "atc": _j(it.get("addToCart")),
                "otc": _j(it.get("openToCart")), "ord": _j(it.get("orders")),
                "cto": _j(it.get("cartToOrder")), "raw": _j(it),
            })
        if rows:
            await self.db.execute(text("""
                INSERT INTO wb_sr_report_item_phrases
                    (company_id, item_id, date, nmID, phrase, avg_position,
                     clicks, orders, ctr, is_card_rated, rating,
                     feedback_rating, frequency_current,
                     median_position_current, week_frequency, open_card_json,
                     add_to_cart_json, open_to_cart_json, orders_json,
                     cart_to_order_json, raw_json)
                VALUES (:cid, :iid, :d, :nm, :ph, :pos, :clicks, :orders,
                        :ctr, :rated, :rating, :frating, :freq, :med, :wf,
                        :oc, :atc, :otc, :ord, :cto, :raw)"""), rows)
            await self.db.commit()
        return len(rows)


async def update_directory(db: AsyncSession) -> dict:
    """Справочник фраз (1в1 actionUpdateDirectory): INSERT IGNORE + агрегаты."""
    ins = await db.execute(text("""
        INSERT IGNORE INTO wb_phrases_directory (phrase)
        SELECT DISTINCT phrase FROM wb_sr_report_item_phrases
        WHERE phrase IS NOT NULL AND phrase != ''"""))
    await db.commit()
    upd = await db.execute(text("""
        UPDATE wb_phrases_directory d
        JOIN (
            SELECT phrase, MAX(week_frequency) as max_freq,
                COUNT(DISTINCT nmID) as items_cnt,
                SUM(orders) as orders_sum,
                COUNT(DISTINCT date) as unique_dates_cnt
            FROM wb_sr_report_item_phrases
            GROUP BY phrase
        ) s ON d.phrase = s.phrase
        SET d.max_frequency = s.max_freq, d.items_count = s.items_cnt,
            d.orders_count = s.orders_sum,
            d.entries_count = s.unique_dates_cnt"""))
    await db.commit()
    return {"inserted": ins.rowcount, "updated": upd.rowcount}
