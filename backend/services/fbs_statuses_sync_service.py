"""Статусы FBS-заказов: orders/status -> wb_orders_fbs_statuses.

Порт WbOrdersFbsController::actionSyncStatuses (D4): кандидаты — заказы 30д
с «живым» последним статусом (new/confirm/complete + waiting/sorted) либо
непроверенные. Батчи 1000, пауза 200мс. Строка пишется ТОЛЬКО при смене
статуса (created_at = момент смены). Токен raw. Только stdlib.
"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

STATUS_URL = "https://marketplace-api.wildberries.ru/api/v3/orders/status"
TIMEOUT_S = 15
BATCH = 1000
SUPPLIER_LIVE = ("new", "confirm", "complete")
WB_LIVE = ("waiting", "sorted")


class FbsStatusesService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def _candidates(self) -> list[int]:
        ss = ",".join(f"'{s}'" for s in SUPPLIER_LIVE)
        ws = ",".join(f"'{s}'" for s in WB_LIVE)
        rows = (await self.db.execute(text(f"""
            SELECT f.wb_order_id FROM wb_orders_fbs f
            LEFT JOIN (
                SELECT s1.wb_order_id, s1.supplier_status, s1.wb_status
                FROM wb_orders_fbs_statuses s1
                JOIN (SELECT wb_order_id, MAX(id) AS max_id
                      FROM wb_orders_fbs_statuses WHERE company_id = :cid
                      GROUP BY wb_order_id) m
                  ON m.wb_order_id = s1.wb_order_id AND m.max_id = s1.id
            ) ls ON ls.wb_order_id = f.wb_order_id
            WHERE f.company_id = :cid
              AND (ls.wb_order_id IS NULL
                   OR (ls.supplier_status IN ({ss}) AND ls.wb_status IN ({ws})))"""),
            {"cid": self.company_id})).all()
        return [int(r[0]) for r in rows if r[0] is not None]

    async def sync(self, dry_run: bool = False, progress=None) -> dict:
        plan = await company_sync_plan(
            self.db, self.company_id, "marketplace", 1,
            pause_fast_s=0, pause_slow_s=0)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        ids = await self._candidates()
        if not ids:
            return {"company_id": self.company_id, "candidates": 0, "changed": 0,
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        checked, changed, pages = 0, 0, 0
        for bi in range(0, len(ids), BATCH):
            chunk = ids[bi:bi + BATCH]
            ph = ",".join(f":o{j}" for j in range(len(chunk)))
            last = {(r[0], r[1], r[2]) for r in (await self.db.execute(text(f"""
                SELECT s.wb_order_id, s.supplier_status, s.wb_status
                FROM wb_orders_fbs_statuses s
                JOIN (SELECT wb_order_id, MAX(id) AS m FROM wb_orders_fbs_statuses
                      WHERE company_id = :cid AND wb_order_id IN ({ph})
                      GROUP BY wb_order_id) x
                  ON x.wb_order_id = s.wb_order_id AND x.m = s.id"""),
                {"cid": self.company_id,
                 **{f"o{j}": v for j, v in enumerate(chunk)}})).all()}
            last = {(int(a), b, c) for a, b, c in last}

            def _log(m, _p=pages + 1):
                if progress:
                    st = "send" if m == "send" else "retry"
                    progress(0, 0, st, 0, 0.0, 0.0, 0, f"пачка {_p}: {m}")

            t0 = time.monotonic()
            data = post_json(STATUS_URL, {"orders": [int(x) for x in chunk]},
                             plan["token"], timeout=TIMEOUT_S,
                             log=_log if progress else None)
            el = time.monotonic() - t0
            new_rows = []
            for st in ((data or {}).get("orders") or []):
                oid = st.get("id")
                if oid is None:
                    continue
                checked += 1
                key = (int(oid), st.get("supplierStatus"), st.get("wbStatus"))
                if key not in last:
                    new_rows.append({
                        "cid": self.company_id, "oid": int(oid),
                        "ss": st.get("supplierStatus"), "ws": st.get("wbStatus"),
                        "cc": 1 if st.get("isCancellable") else 0})
                    changed += 1
            if new_rows and not dry_run:
                await self.db.execute(text("""
                    INSERT INTO wb_orders_fbs_statuses(company_id, wb_order_id,
                        supplier_status, wb_status, is_cancellable)
                    VALUES(:cid, :oid, :ss, :ws, :cc)"""), new_rows)
                await self.db.commit()
            pages += 1
            if progress:
                progress(pages, 0, "pause", len(new_rows), el, 0.0, 0)
            time.sleep(0.2)
        return {"company_id": self.company_id, "candidates": len(ids),
                "checked": checked, "changed": 0 if dry_run else changed,
                "token_type": plan.get("token_type"), "dry_run": dry_run}
