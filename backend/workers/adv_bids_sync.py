"""Снимок состояния рекламы WB: ставки кластеров, кластеры, минус-фразы,
конфиг аккаунта, баланс, дневные лимиты, остаток бюджета кампаний.

Только чтение из advert-api — в кабинет продавца ничего не пишем.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/adv_bids_sync.py
  .venv/bin/python backend/workers/adv_bids_sync.py --company-id 1
  DRY_RUN=1 .venv/bin/python backend/workers/adv_bids_sync.py   # опрос без записи
  Таймер: wbcms-adv-bids (каждые 30 мин)

Таблицы: wb_adv_bid(+history), wb_adv_cluster, wb_adv_minus_phrase,
wb_adv_account, wb_adv_daily_limit, wb_campaign.budget_total.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(kind, i, n, text):
        if kind == "retry":
            print(f"  [{label}] [{text}]", flush=True)
        else:
            print(f"  [{label}] {text}", flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.adv_bids_sync_service import AdvBidsSyncService
    print("WB API: normquery/get-bids + normquery/list + normquery/get-minus"
          " + config + balance + daily-limits + budget → снимок рекламы", flush=True)
    async with get_session() as db:
        companies = (await db.execute(text(
            "SELECT id, name FROM companies WHERE is_active = 1"
            " AND api_key IS NOT NULL AND api_key <> ''"
            + (" AND id = :cid" if args.company_id else "")
            + " ORDER BY id"),
            ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
        ok, skipped, errors = 0, 0, 0
        for comp in companies:
            cid = int(comp["id"])
            name = comp["name"] or str(cid)
            print(f"[{name}] старт...", flush=True)
            try:
                st = await AdvBidsSyncService(db, company_id=cid).sync(
                    dry_run=args.dry_run, progress=_make_progress(name))
                if st.get("skipped"):
                    print(f"[{name}] SKIP: {st['skipped']}")
                    skipped += 1
                    continue
                warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                types = st.get("types") or {}
                print(f"[{name}] пар={st.get('pairs')} кампаний={st.get('campaigns')} "
                      f"ставок={st.get('bids', {}).get('bids', 0)} "
                      f"изменилось={st.get('bids', {}).get('changed', 0)} "
                      f"кластеров={st.get('clusters', {}).get('clusters', 0)} "
                      f"минус={st.get('minus', {}).get('minus', 0)} "
                      f"лимитов={st.get('limits', {}).get('campaigns', 0)} "
                      f"мин.ставок={st.get('min_bids', {}).get('cards', 0)} "
                      f"{st.get('token_type')}{warn}")
                if types:
                    print(f"  [{name}] тип ставки: {types.get('bid_type')}"
                          f" · тип оплаты: {types.get('payment_type')}")
                if not (st.get("bids", {}).get("bids") or 0) and not (
                        st.get("bids", {}).get("manual_pairs") or 0):
                    print("  [note] кампаний с ручной ставкой нет — ставок кластеров"
                          " у WB не существует (единая ставка)")
                for part in ("config", "balance", "budget", "min_bids",
                             "limits", "clusters", "bids", "minus"):
                    sub = st.get(part) or {}
                    if sub.get("error"):
                        print(f"  [{name}] {part}: ОШИБКА — {sub['error']}")
                    elif sub.get("skipped"):
                        print(f"  [{name}] {part}: SKIP — {sub['skipped']}")
                ok += 1
            except Exception as e:
                print(f"[{name}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Снимок состояния рекламы WB")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
