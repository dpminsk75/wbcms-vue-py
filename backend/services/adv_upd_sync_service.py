"""История списаний по рекламе WB (GET /adv/v1/upd).

Метод отдаёт фактические списания по кампаниям за период (1…31 день).
Поля: updNum, updTime, updSum, advertId, campName, advertType,
paymentType (Баланс | Бонусы | Счёт | Кэшбэк), advertStatus.

Ловушки (подтверждено обсуждением на форуме WB):
  * updTime бывает NULL — это «текущее, ещё не проведённое» списание; WB такие
    строки переписывает. Поэтому перед вставкой удаляем наши строки за период
    с upd_time IS NULL, иначе задвоятся;
  * updNum у WB часто 0 — уникальный ключ строим сами: хэш от
    updTime|advertId|updSum|paymentType.

Таблица: wb_adv_upd.
"""
import hashlib
import time
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json

UPD_URL = "https://advert-api.wildberries.ru/adv/v1/upd"
PAYMENTS_URL = "https://advert-api.wildberries.ru/adv/v1/payments"
PAUSE_S = 1.0
TIMEOUT_S = 30
MAX_DAYS = 31


def _i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _f(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _dt(v) -> str | None:
    """ISO-строка WB ('2023-07-31T12:12:54.060536+03:00') → 'YYYY-MM-DD HH:MM:SS'.
    None остаётся None — значит списание «текущее», ещё не проведённое."""
    if not v:
        return None
    try:
        from datetime import datetime
        s = str(v).replace("Z", "+00:00")
        return datetime.fromisoformat(s).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _key(upd_time, advert_id: int, upd_sum: float, payment_type: str) -> str:
    raw = f"{upd_time or ''}|{advert_id}|{upd_sum}|{payment_type}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]


class AdvUpdSyncService:
    """Тянет историю списаний по рекламе."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, date_from: str | None = None, date_to: str | None = None,
                   dry_run: bool = False, progress=None) -> dict:
        """Снимает списания за период (по умолчанию — вчера и позавчера)."""
        dt = date_to or (date.today() - timedelta(days=1)).isoformat()
        df = date_from or (date.fromisoformat(dt) - timedelta(days=1)).isoformat()
        days = (date.fromisoformat(dt) - date.fromisoformat(df)).days + 1
        if days > MAX_DAYS:
            df = (date.fromisoformat(dt) - timedelta(days=MAX_DAYS - 1)).isoformat()
            days = MAX_DAYS
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion", days,
            pause_fast_s=PAUSE_S, pause_slow_s=3600)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token = plan["token"]
        data = get_json(UPD_URL, [("from", df), ("to", dt)], token, timeout=TIMEOUT_S)
        rows = []
        for u in (data if isinstance(data, list) else []):
            try:
                advert = int(u.get("advertId"))
            except (TypeError, ValueError):
                continue
            upd_time = u.get("updTime")
            upd_sum = _f(u.get("updSum"))
            ptype = str(u.get("paymentType") or "")[:32]
            rows.append({
                "cid": self.company_id, "adv": advert,
                "key": _key(upd_time, advert, upd_sum, ptype),
                "t": _dt(upd_time), "sum": upd_sum,
                "name": str(u.get("campName") or "")[:255],
                "atype": _i(u.get("advertType")),
                "ptype": ptype,
                "astatus": _i(u.get("advertStatus")),
            })
            if len(rows) % 200 == 0:
                time.sleep(PAUSE_S)
        if not dry_run:
            # «текущие» списания (upd_time IS NULL) WB переписывает — чистим свои
            await self.db.execute(text(
                "DELETE FROM wb_adv_upd WHERE company_id = :cid AND upd_time IS NULL"),
                {"cid": self.company_id})
            await self.db.commit()
            if rows:
                await self.db.execute(text("""
                    INSERT INTO wb_adv_upd(company_id, advert_id, upd_key, upd_time,
                        upd_sum, camp_name, advert_type, payment_type, advert_status)
                    VALUES(:cid, :adv, :key, :t, :sum, :name, :atype, :ptype, :astatus)
                    AS new
                    ON DUPLICATE KEY UPDATE
                        upd_time = new.upd_time, upd_sum = new.upd_sum,
                        camp_name = new.camp_name, advert_type = new.advert_type,
                        payment_type = new.payment_type,
                        advert_status = new.advert_status"""), rows)
                await self.db.commit()
        cashback = round(sum(r["sum"] for r in rows if r["ptype"] == "Кэшбэк"), 2)
        total = round(sum(r["sum"] for r in rows), 2)
        if progress:
            progress("phase", 1, 1,
                     f"upd {df}..{dt}: {len(rows)} списаний на {total:.2f} (кэшбэк {cashback:.2f})")
        out = {"date_from": df, "date_to": dt, "rows": len(rows),
               "total": total, "cashback": cashback, "dry_run": dry_run}
        # пополнения рекламного счёта за тот же период
        try:
            out["payments"] = await self._sync_payments(df, dt, dry_run)
        except RuntimeError as e:
            out["payments"] = {"skipped": str(e)[:160]}
        return out

    async def _sync_payments(self, df: str, dt: str, dry_run: bool) -> dict:
        """GET /adv/v1/payments — история пополнений счёта WB Продвижение.

        Ответ: [{"id":…, "date":"ISO", "sum":…, "type":0|1|3,
                 "statusId":0|1, "cardStatus":"success", "currency":"RUB"}].
        """
        rows = []
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion", 1,
            pause_fast_s=PAUSE_S, pause_slow_s=3600)
        if plan.get("skip"):
            return {"skipped": plan["skip"]}
        data = get_json(PAYMENTS_URL, [("from", df), ("to", dt)],
                        plan["token"], timeout=TIMEOUT_S)
        for p in (data if isinstance(data, list) else []):
            try:
                pid = int(p.get("id"))
            except (TypeError, ValueError):
                continue
            rows.append({
                "cid": self.company_id, "pid": pid,
                "t": _dt(p.get("date")),
                "sum": _f(p.get("sum")),
                "pt": _i(p.get("type")),
                "st": _i(p.get("statusId")),
                "cs": str(p.get("cardStatus") or "")[:32],
                "cur": str(p.get("currency") or "RUB")[:8],
            })
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_payment(company_id, pay_id, pay_date, `sum`,
                    pay_type, status_id, card_status, currency)
                VALUES(:cid, :pid, :t, :sum, :pt, :st, :cs, :cur) AS new
                ON DUPLICATE KEY UPDATE
                    pay_date = new.pay_date, `sum` = new.`sum`,
                    pay_type = new.pay_type, status_id = new.status_id,
                    card_status = new.card_status, currency = new.currency"""), rows)
            await self.db.commit()
        return {"rows": len(rows),
                "total": round(sum(r["sum"] for r in rows), 2)}
