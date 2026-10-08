"""Вычет FBS-заказов из виртуальных остатков — порт deductVirtualStocks (D5, без API
кроме выгрузки). Гейты: companies.fbs_deduct_enabled=1, склад our_warehouse.is_fbs=1,
consider_orders=1, fbs_deduct_test=1 = dry-run без PUT (дефолт из компании, флаг --test
переопределяет). Dedup по ledger (fbs_order/orderId). PUT stocks чанки 1000
по складам is_virtual=1 + зеркало wb_fbs_stock. Лог — в консоль (journal), без файла.
"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import stock_service
from backend.services.wb_sync_base import post_json


def _put(url: str, payload: dict, token: str, log=None) -> int:
    import urllib.request, urllib.error, json
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = 0
    if log:
        log("send")
    for attempt in range(4):
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": token, "Content-Type": "application/json",
            "Accept": "application/json"}, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return int(resp.status)
        except urllib.error.HTTPError as e:
            last = int(e.code)
            if last == 429 and attempt < 3:
                time.sleep(60)
                continue
            return last
        except Exception as e:
            if log:
                log(f"{type(e).__name__} → жду {[1, 2, 4][min(attempt, 2)]}с")
            time.sleep([1, 2, 4][min(attempt, 2)])
    return last


class DeductService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, test: bool | None = None, dry_run: bool = False,
                   progress=None) -> dict:
        comp = (await self.db.execute(
            text("SELECT * FROM companies WHERE id = :c"), {"c": self.company_id}
        )).mappings().first()
        if not comp or not comp.get("fbs_deduct_enabled"):
            return {"company_id": self.company_id, "skipped": "fbs_deduct_enabled=0",
                    "dry_run": dry_run}
        is_test = test if test is not None else bool(comp.get("fbs_deduct_test"))
        fbs_row = (await self.db.execute(text("""
            SELECT id, name, consider_orders FROM our_warehouse
            WHERE company_id = :c AND is_fbs = 1 LIMIT 1"""),
            {"c": self.company_id})).mappings().first()
        if not fbs_row:
            return {"company_id": self.company_id,
                    "skipped": "нет склада our_warehouse is_fbs=1", "dry_run": dry_run}
        fbs_id = int(fbs_row["id"])
        wh_ids = [int(r[0]) for r in (await self.db.execute(text("""
            SELECT warehouseId FROM wb_fbs_warehouse
            WHERE company_id = :c AND consider_orders = 1 AND is_deleting = 0"""),
            {"c": self.company_id})).all() if r[0] is not None]
        if not int(fbs_row.get("consider_orders") or 0) and not wh_ids:
            return {"company_id": self.company_id,
                    "skipped": "нет складов consider_orders=1", "dry_run": dry_run}
        q = """SELECT wb_order_id, chrt_id, warehouse_id FROM wb_orders_fbs
               WHERE company_id = :c AND is_deducted = 0"""
        params: dict = {"c": self.company_id}
        if wh_ids:
            ph = ",".join(f":w{j}" for j in range(len(wh_ids)))
            q += f" AND warehouse_id IN ({ph})"
            params.update({f"w{j}": v for j, v in enumerate(wh_ids)})
        orders = (await self.db.execute(text(q), params)).mappings().all()
        if not orders:
            return {"company_id": self.company_id, "orders": 0, "ok": 0,
                    "dry_run": dry_run}
        ok, skip, fail, skus = 0, 0, 0, set()
        fail_sample = ""
        for o in orders:
            oid = int(o["wb_order_id"] or 0)
            if not oid:
                fail += 1
                continue
            dup = (await self.db.execute(text("""
                SELECT 1 FROM wb_stock_ledger
                WHERE company_id = :c AND doc_type = 'fbs_order' AND doc_id = :d LIMIT 1"""),
                {"c": self.company_id, "d": oid})).first()
            if dup:
                await self.db.execute(text("""
                    UPDATE wb_orders_fbs SET is_deducted = 1, deducted_at = NOW()
                    WHERE wb_order_id = :o"""), {"o": oid})
                await self.db.commit()
                skip += 1
                continue
            ch = o.get("chrt_id")
            if not ch:
                continue
            size = (await self.db.execute(text("""
                SELECT sku, nmID FROM wbcards_sizes WHERE chrtID = :ch LIMIT 1"""),
                {"ch": int(ch)})).first()
            if not size:
                continue
            res = await stock_service.apply(
                self.db, self.company_id, fbs_id, "fbs_order", oid, [(size[0], -1)])
            if not res["ok"]:
                if not fail_sample:
                    fail_sample = res["error"][:200]
                fail += 1
                continue
            await self.db.execute(text("""
                UPDATE wb_orders_fbs SET is_deducted = 1, deducted_at = NOW()
                WHERE wb_order_id = :o"""), {"o": oid})
            await self.db.commit()
            skus.add(size[0])
            ok += 1
        uploaded = 0
        if (ok or skip) and skus and not dry_run:
            uploaded = await self._upload(
                str(comp.get("api_key") or ""), fbs_id, sorted(skus), is_test, progress)
        return {"company_id": self.company_id, "orders": len(orders), "ok": ok,
                "skip_ledger": skip, "fail": fail, "fail_sample": fail_sample,
                "uploaded_skus": uploaded,
                "test_mode": is_test, "dry_run": dry_run}

    async def _upload(self, token: str, fbs_id: int, skus: list,
                      is_test: bool, progress) -> int:
        vwh = [int(r[0]) for r in (await self.db.execute(text("""
            SELECT warehouseId FROM wb_fbs_warehouse
            WHERE company_id = :c AND is_virtual = 1"""),
            {"c": self.company_id})).all() if r[0] is not None]
        if not vwh or not token:
            return 0
        bal = {(r[0], r[1]) for r in (await self.db.execute(text("""
            SELECT sku, quantity FROM wb_stock_balance
            WHERE company_id = :c AND warehouseId = :w"""),
            {"c": self.company_id, "w": fbs_id})).all()}
        bal = dict(bal)
        payload = []
        for sku in skus:
            ch = (await self.db.execute(
                text("SELECT chrtID FROM wbcards_sizes WHERE sku = :s LIMIT 1"),
                {"s": sku})).scalar()
            if ch is None:
                continue
            payload.append({"chrtId": int(ch), "amount": int(bal.get(sku, 0))})
        n = 0
        for wid in vwh:
            for i in range(0, len(payload), 1000):
                ch = payload[i:i + 1000]
                if is_test:
                    if progress:
                        progress(0, 0, "retry", 0, 0.0, 0.0, 0,
                                 f"[DRY] PUT stocks/{wid} {len(ch)} sku")
                    continue
                code = _put(
                    f"https://marketplace-api.wildberries.ru/api/v3/stocks/{wid}",
                    {"stocks": ch}, token,
                    log=(lambda m: progress(0, 0, "retry", 0, 0.0, 0.0, 0, m))
                    if progress else None)
                if code in (200, 204):
                    for p in ch:
                        size = (await self.db.execute(text("""
                            SELECT sku, nmID FROM wbcards_sizes
                            WHERE chrtID = :ch LIMIT 1"""),
                            {"ch": p["chrtId"]})).first()
                        if not size:
                            continue
                        await self.db.execute(text("""
                            INSERT INTO wb_fbs_stock(company_id, warehouseId, sku,
                                amount, nmID, chrtID)
                            VALUES(:c, :w, :s, :a, :nm, :ch) AS new
                            ON DUPLICATE KEY UPDATE amount = new.amount"""),
                            {"c": self.company_id, "w": wid, "s": size[0],
                             "a": p["amount"], "nm": size[1], "ch": p["chrtId"]})
                    await self.db.commit()
                    n += len(ch)
                time.sleep(0.3)
        return n
