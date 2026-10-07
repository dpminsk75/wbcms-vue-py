"""Баланс ЛК WB: GET finance-api /api/v1/account/balance -> wb_finance_balance.

Ответ WB: {"currency":"RUB","current":N,"for_withdraw":N}.
Лимит WB — 1 запр/мин на продавца (у каждой компании свой токен/лимит).
Токен — companies.api_key (нужна категория Finance, иначе 401/403).
Только stdlib (как commission_tariffs_service).
"""
import json
import urllib.error
import urllib.request
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BALANCE_URL = "https://finance-api.wildberries.ru/api/v1/account/balance"
TIMEOUT_S = 15


def _num(v):
    try:
        return round(float(v), 2) if v is not None else None
    except (TypeError, ValueError):
        return None


class FinanceBalanceService:
    def __init__(self, db: AsyncSession, company_id: int):
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
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"WB balance http={e.code}") from e

    async def fetch(self) -> dict:
        """Живой опрос WB без записи (для dry-run/диагностики)."""
        return self._get(BALANCE_URL, await self._token())

    async def latest(self) -> dict:
        """Последний срез из wb_finance_balance (для дашборда, без сети)."""
        row = (await self.db.execute(text("""
            SELECT currency, current_balance, for_withdraw, fetched_at
            FROM wb_finance_balance WHERE company_id = :cid
            ORDER BY fetched_at DESC LIMIT 1"""),
            {"cid": self.company_id})).mappings().first()
        if not row:
            return {"has_data": False, "currency": "RUB",
                    "current": None, "for_withdraw": None, "fetched_at": None}
        return {"has_data": True, "currency": row["currency"],
                "current": float(row["current_balance"]) if row["current_balance"] is not None else None,
                "for_withdraw": float(row["for_withdraw"]) if row["for_withdraw"] is not None else None,
                "fetched_at": row["fetched_at"].isoformat() if row["fetched_at"] else None}

    async def sync(self, dry_run: bool = False) -> dict:
        """Опрос WB + запись среза в wb_finance_balance (upsert)."""
        data = await self.fetch()
        row = {
            "cid": self.company_id,
            "ts": datetime.now().replace(microsecond=0),
            "cur": str(data.get("currency") or "RUB")[:8],
            "bal": _num(data.get("current")),
            "wd": _num(data.get("for_withdraw")),
            "raw": json.dumps(data, ensure_ascii=False),
        }
        if not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_finance_balance(
                    company_id, fetched_at, currency,
                    current_balance, for_withdraw, raw)
                VALUES(:cid, :ts, :cur, :bal, :wd, :raw) AS new
                ON DUPLICATE KEY UPDATE
                    currency = new.currency,
                    current_balance = new.current_balance,
                    for_withdraw = new.for_withdraw,
                    raw = new.raw"""), row)
            await self.db.commit()
        return {"company_id": self.company_id, "fetched_at": row["ts"].isoformat(),
                "currency": row["cur"], "current": row["bal"],
                "for_withdraw": row["wd"], "dry_run": dry_run}
