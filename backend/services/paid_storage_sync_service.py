"""Платное хранение: async paid_storage -> wb_paid_storage.

Порт WbPaidStorageController (C1): чанки 8д (лимит WB), дефолт вчера,
65с между чанками, 2с между компаниями. Запись 1в1: DELETE периода + INSERT
пачками (upsert невозможен — нет UNIQUE). DDL из синка выкинут.
Токен — companies.api_key (категория analytics). Только stdlib.
"""
import time
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, run_async_report

BASE = "https://seller-analytics-api.wildberries.ru"
CHUNK_DAYS = 8
PAUSE_CHUNK_S = 65
PAUSE_COMPANY_S = 2


def _dt(v):
    if not v:
        return None
    s = str(v)[:10]
    try:
        date.fromisoformat(s)
        return s
    except ValueError:
        return None


def _days(df: str, dt: str, n: int = CHUNK_DAYS):
    d0, out = date.fromisoformat(df), []
    d1 = date.fromisoformat(dt)
    while d0 <= d1:
        e = min(d0 + timedelta(days=n - 1), d1)
        out.append((d0.isoformat(), e.isoformat()))
        d0 = e + timedelta(days=1)
    return out


class PaidStorageService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, progress=None) -> dict:
        yd = (date.today() - timedelta(days=1)).isoformat()
        df, dt = date_from or yd, date_to or date_from or yd
        chunks = _days(df, dt)
        plan = await company_sync_plan(
            self.db, self.company_id, "analytics", len(chunks),
            pause_fast_s=PAUSE_CHUNK_S, pause_slow_s=PAUSE_CHUNK_S)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth = plan["token"]
        total = 0
        for i, (cf, ct) in enumerate(chunks):
            def _log(m, _i=i, _n=len(chunks)):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(0, 0, st, 0, 0.0, 0.0, 0, f"кусок {_i + 1}/{_n}: {m}")

            t0 = time.monotonic()
            rows = run_async_report(BASE, "paid_storage", auth, cf, ct,
                                    log=_log if progress else None)
            el = time.monotonic() - t0
            mapped = [r for r in (self._row(x) for x in rows) if r is not None]
            if mapped and not dry_run:
                await self._save(mapped)
            total += len(mapped)
            if progress:
                progress(i + 1, len(chunks), "pause", len(mapped), el, 0.0, PAUSE_CHUNK_S)
            if i + 1 < len(chunks):
                time.sleep(PAUSE_CHUNK_S)
        out = {"company_id": self.company_id, "chunks": len(chunks),
               "rows": 0 if dry_run else total, "fetched": total,
               "token_type": plan["token_type"], "dry_run": dry_run}
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out

    def _row(self, x: dict) -> dict | None:
        d, ch = _dt(x.get("date")), x.get("chrtId")
        if not d or ch is None:
            return None
        try:
            ch = int(ch)
        except (TypeError, ValueError):
            return None
        f = lambda k, t=float: (t(x[k]) if x.get(k) is not None else None)
        return {
            "cid": self.company_id, "d": d,
            "lwc": f("logWarehouseCoef"), "oid": x.get("officeId"),
            "wh": x.get("warehouse"), "wc": f("warehouseCoef"),
            "gi": x.get("giId"), "ch": ch, "sz": x.get("size"),
            "bc": x.get("barcode"), "sub": x.get("subject"), "br": x.get("brand"),
            "vc": x.get("vendorCode"), "nm": x.get("nmId"),
            "vol": f("volume"), "ct": x.get("calcType"), "wp": f("warehousePrice"),
            "bcn": x.get("barcodesCount"), "ppc": x.get("palletPlaceCode"),
            "pc": x.get("palletCount"), "od": _dt(x.get("originalDate")),
            "ld": x.get("loyaltyDiscount"), "tfd": _dt(x.get("tariffFixDate")),
            "tld": _dt(x.get("tariffLowerDate")),
        }

    async def _save(self, rows: list) -> None:
        ds = sorted({r["d"] for r in rows})
        await self.db.execute(text("""
            DELETE FROM wb_paid_storage
            WHERE company_id = :cid AND date BETWEEN :mn AND :mx"""),
            {"cid": self.company_id, "mn": ds[0], "mx": ds[-1]})
        for i in range(0, len(rows), 500):
            try:
                await self.db.execute(text("""
                    INSERT INTO wb_paid_storage(company_id, date, logWarehouseCoef,
                        officeId, warehouse, warehouseCoef, giId, chrtId, size, barcode,
                        subject, brand, vendorCode, nmId, volume, calcType, warehousePrice,
                        barcodesCount, palletPlaceCode, palletCount, originalDate,
                        loyaltyDiscount, tariffFixDate, tariffLowerDate)
                    VALUES(:cid, :d, :lwc, :oid, :wh, :wc, :gi, :ch, :sz, :bc,
                        :sub, :br, :vc, :nm, :vol, :ct, :wp, :bcn, :ppc, :pc,
                        :od, :ld, :tfd, :tld)"""), rows[i:i + 500])
            except Exception:
                for r in rows[i:i + 500]:
                    try:
                        await self.db.execute(text("""
                            INSERT INTO wb_paid_storage(company_id, date, logWarehouseCoef,
                                officeId, warehouse, warehouseCoef, giId, chrtId, size, barcode,
                                subject, brand, vendorCode, nmId, volume, calcType, warehousePrice,
                                barcodesCount, palletPlaceCode, palletCount, originalDate,
                                loyaltyDiscount, tariffFixDate, tariffLowerDate)
                            VALUES(:cid, :d, :lwc, :oid, :wh, :wc, :gi, :ch, :sz, :bc,
                                :sub, :br, :vc, :nm, :vol, :ct, :wp, :bcn, :ppc, :pc,
                                :od, :ld, :tfd, :tld)"""), r)
                    except Exception:
                        pass
        await self.db.commit()
