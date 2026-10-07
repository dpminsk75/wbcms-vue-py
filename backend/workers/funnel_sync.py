"""Воронка продаж WB (sales-funnel history) — порт wb-funnel/sync + sync-missing.

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/funnel_sync.py
  .venv/bin/python backend/workers/funnel_sync.py --missing-only   # догрузка без истории
  .venv/bin/python backend/workers/funnel_sync.py --date-from 2026-04-01 --date-to 2026-04-22  # разовый бэкфилл
  DRY_RUN=1 .venv/bin/python backend/workers/funnel_sync.py  # опрос без записи
  Таймеры: wbcms-funnel-sync (03:00), wbcms-funnel-missing (03:20)

Цикл по активным компаниям с api_key. Гейт токена (analytics, протухание,
тест, правило 2ч для базовых) — backend/services/wb_sync_base.py.
Таблица: wb_sales_funnel_history (upsert).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    """Одна строка на чанк, дописывается по фазам (без \\r — терминал их
    разворачивает в строки). Формат:
    `чанк i/n: отправляю... [429 → жду 30с...] api 0.2с → запись 0.1с → пауза 25с`."""
    def cb(i, n, stage, k, api, db, wait, msg=""):
        if stage == "send":
            print(f"  [{label}] чанк {i}/{n}: отправляю...", end=" ", flush=True)
        elif stage == "retry":
            print(f"[{msg}]", end=" ", flush=True)
        elif stage == "pause":
            left = (n - i) * (wait + api + db) / 60
            print(f"api {api:.1f}с → запись {db:.1f}с → пауза {wait:.0f}с, "
                  f"строк {k} (осталось ~{left:.0f} мин)", flush=True)
        # api/db молчим — всё влезет в итоговую строку
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.funnel_sync_service import FunnelSyncService
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
                st = await FunnelSyncService(db, company_id=cid).sync(
                    date_from=args.date_from, date_to=args.date_to,
                    dry_run=args.dry_run, missing_only=args.missing_only,
                    include_inactive=args.include_inactive,
                    progress=_make_progress(comp["name"] or str(cid)))
                if st.get("skipped"):
                    print(f"[{comp['name'] or cid}] SKIP: {st['skipped']}")
                    skipped += 1
                else:
                    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                    print(f"[{comp['name'] or cid}] nm={st['nm_ids']}/{st.get('total_nm_ids')} "
                          f"upserted={st['upserted']} {st.get('token_type')}{warn}")
                    ok += 1
            except Exception as e:
                print(f"[{comp['name'] or cid}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Воронка продаж WB (sales-funnel history)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--missing-only", action="store_true",
                    help="только nmId без истории за период (sync-missing)")
    ap.add_argument("--include-inactive", action="store_true",
                    help="без фильтра активности: все nmId (по дефолту — заказы за 30д или новинки)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
