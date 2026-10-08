"""Финдетализация WB — порт wb-detail-finance/sync (F1, без адресов!).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/finance_detail_sync.py
  .venv/bin/python backend/workers/finance_detail_sync.py --date-from 2026-09-01 --date-to 2026-09-30
  DRY_RUN=1 .venv/bin/python backend/workers/finance_detail_sync.py
  Дефолт -7д..сегодня.

API→upsert detail_by_period → forecast по датам → факты wb_order.
Отдельные update-order-facts/update-forecast покрываются флагами
--facts-only/--forecast-only (период + --company-id).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(i, n, stage, k, api, db, wait, msg=""):
        if stage in ("send", "retry"):
            print(f"  [{label}] [{msg}]", flush=True)
        elif stage == "pause":
            print(f"  [{label}] запрос {i}: получено {n}, записано {k} (api {api:.0f}с)",
                  flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.finance_detail_sync_service import FinanceDetailService
    print("WB API: POST finance.../sales-reports/detailed → detail_by_period",
          flush=True)
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
            print(f"[{comp['name'] or cid}] старт...", flush=True)
            try:
                svc = FinanceDetailService(db, company_id=cid)
                if args.facts_only or args.forecast_only:
                    if args.forecast_only:
                        from datetime import date, timedelta
                        df = args.date_from or (date.today() - timedelta(days=7)).isoformat()
                        dt = args.date_to or date.today().isoformat()
                        from datetime import date as _d
                        days, cur = [], _d.fromisoformat(df)
                        end = _d.fromisoformat(dt)
                        while cur <= end:
                            days.append(cur.isoformat())
                            cur += timedelta(days=1)
                        n = await svc.update_forecast(days)
                        print(f"[{comp['name'] or cid}] forecast дат={n}")
                    else:
                        rows = (await db.execute(text("""
                            SELECT DISTINCT srid FROM detail_by_period
                            WHERE company_id = :c AND srid IS NOT NULL AND srid <> ''"""),
                            {"c": cid})).all()
                        n = await svc.update_facts([str(r[0]) for r in rows])
                        print(f"[{comp['name'] or cid}] facts={n}")
                else:
                    st = await svc.sync(
                        date_from=args.date_from, date_to=args.date_to,
                        dry_run=args.dry_run,
                        progress=_make_progress(comp["name"] or str(cid)))
                    if st.get("skipped"):
                        print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                        skipped += 1
                    else:
                        warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                        print(f"[{comp['name'] or cid}] rows={st['rows']} "
                              f"(вставлено {st.get('db_inserted')}, ошибок {st.get('errors')}) "
                              f"forecast={st['forecast_dates']} facts={st['facts']} "
                              f"{st.get('token_type')}{warn}")
                        if st.get("error_sample"):
                            print(f"  пример ошибки: {st['error_sample']}")
                        if st.get("errors"):
                            errors += 1
                ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Финдетализация WB (detail_by_period)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--facts-only", action="store_true")
    ap.add_argument("--forecast-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
