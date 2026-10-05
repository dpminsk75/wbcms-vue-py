"""Базовые комиссии WB: синк tariffs/commission + справочник предметов.

Источники:
- GET https://common-api.wildberries.ru/api/v1/tariffs/commission
  -> {"report": [{kgvpBooking, kgvpMarketplace, kgvpPickup, kgvpSupplier,
                  kgvpSupplierExpress, paidStorageKgvp,
                  parentID, parentName, subjectID, subjectName}]}
- GET https://content-api.wildberries.ru/content/v2/object/parent/all
  -> {"data": [{id, name, isVisible}]} — апсерт в wb_subject_catalog (PK subject_id).

Срезы бессрочно, пишем только изменения (diff с последним срезом по subject_id).
Токен — companies.api_key компании id=1 (тарифы глобальные). Только stdlib.
"""
import json
import urllib.request
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TARIFFS_URL = "https://common-api.wildberries.ru/api/v1/tariffs/commission"
SUBJECTS_URL = "https://content-api.wildberries.ru/content/v2/object/parent/all"
TIMEOUT_S = 15

# api-поле -> колонка wb_commission_tariffs
KGVP_MAP = (
    ("kgvpBooking", "kgvp_booking"),
    ("kgvpMarketplace", "kgvp_marketplace"),
    ("kgvpPickup", "kgvp_pickup"),
    ("kgvpSupplier", "kgvp_supplier"),
    ("kgvpSupplierExpress", "kgvp_supplier_express"),
    ("paidStorageKgvp", "paid_storage_kgvp"),
)


def _num(v):
    try:
        return round(float(v), 2) if v is not None else None
    except (TypeError, ValueError):
        return None


class CommissionTariffsService:
    def __init__(self, db: AsyncSession, company_id: int = 1):
        self.db = db
        self.company_id = company_id

    async def _token(self) -> str:
        row = (await self.db.execute(
            text("SELECT api_key FROM companies WHERE id = :cid"),
            {"cid": self.company_id})).first()
        key = (row[0] if row else "") or ""
        if not key.strip():
            raise RuntimeError(f"companies.api_key пуст (id={self.company_id})")
        return key.strip()

    @staticmethod
    def _get(url: str, token: str) -> dict:
        req = urllib.request.Request(url, headers={"Authorization": token})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))

    async def sync_subjects(self, dry_run: bool = False) -> dict:
        """Справочник предметов parent/all -> wb_subject_catalog (upsert по PK)."""
        data = self._get(SUBJECTS_URL, await self._token()).get("data") or []
        rows = [{"sid": int(x["id"]), "nm": x.get("name") or ""}
                for x in data if str(x.get("id", "")).isdigit()]
        if not dry_run and rows:
            await self.db.execute(text("""
                INSERT INTO wb_subject_catalog(subject_id, subject_name, parent_id, parent_name)
                VALUES(:sid, :nm, 0, '') AS new
                ON DUPLICATE KEY UPDATE subject_name = new.subject_name"""), rows)
            await self.db.commit()
        return {"fetched": len(data), "upserted": 0 if dry_run else len(rows),
                "dry_run": dry_run}

    def _latest(self, rows) -> dict:
        """Последний срез по subject_id -> {sid: {col: num}}."""
        out: dict = {}
        for r in rows:
            out[int(r["subject_id"])] = {c: _num(r[c]) for _, c in KGVP_MAP}
        return out

    async def sync_tariffs(self, dry_run: bool = False) -> dict:
        """Срез tariffs/commission: INSERT только изменившихся относительно
        последнего среза (tariff_date = сегодня)."""
        report = self._get(TARIFFS_URL, await self._token()).get("report") or []
        latest_rows = (await self.db.execute(text("""
            SELECT t.* FROM wb_commission_tariffs t
            JOIN (SELECT subject_id, MAX(tariff_date) AS md
                  FROM wb_commission_tariffs GROUP BY subject_id) m
              ON m.subject_id = t.subject_id AND m.md = t.tariff_date"""))).mappings().all()
        latest = self._latest(latest_rows)
        today = date.today().isoformat()
        changed = []
        for x in report:
            try:
                sid = int(x.get("subjectID"))
            except (TypeError, ValueError):
                continue
            cur = {c: _num(x.get(f)) for f, c in KGVP_MAP}
            if latest.get(sid) == cur:
                continue
            changed.append({
                "td": today, "sid": sid,
                "snm": x.get("subjectName"), "pid": x.get("parentID"),
                "pnm": x.get("parentName"),
                **cur,
            })
        if not dry_run and changed:
            await self.db.execute(text("""
                INSERT INTO wb_commission_tariffs(
                    tariff_date, subject_id, subject_name, parent_id, parent_name,
                    kgvp_booking, kgvp_marketplace, kgvp_pickup,
                    kgvp_supplier, kgvp_supplier_express, paid_storage_kgvp)
                VALUES(:td, :sid, :snm, :pid, :pnm,
                    :kgvp_booking, :kgvp_marketplace, :kgvp_pickup,
                    :kgvp_supplier, :kgvp_supplier_express, :paid_storage_kgvp) AS new
                ON DUPLICATE KEY UPDATE
                    subject_name = new.subject_name,
                    parent_id = new.parent_id,
                    parent_name = new.parent_name,
                    kgvp_booking = new.kgvp_booking,
                    kgvp_marketplace = new.kgvp_marketplace,
                    kgvp_pickup = new.kgvp_pickup,
                    kgvp_supplier = new.kgvp_supplier,
                    kgvp_supplier_express = new.kgvp_supplier_express,
                    paid_storage_kgvp = new.paid_storage_kgvp"""), changed)
            await self.db.commit()
        return {"fetched": len(report), "changed": len(changed),
                "inserted": 0 if dry_run else len(changed),
                "dry_run": dry_run, "tariff_date": today}
