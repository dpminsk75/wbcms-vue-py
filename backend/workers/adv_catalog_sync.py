"""Справочник рекламы WB: предметы и карточки, доступные для добавления в кампанию.

Два read-only метода WB:
  GET  /adv/v1/supplier/subjects  — предметы (лимит 1 запрос / 12 с)
  POST /adv/v2/supplier/nms      — карточки по предметам (5 запросов / мин)

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/adv_catalog_sync.py
  .venv/bin/python backend/workers/adv_catalog_sync.py --company-id 1 --payment-type cpc
  DRY_RUN=1 .venv/bin/python backend/workers/adv_catalog_sync.py
  Таймер: wbcms-adv-catalog (ежедневно)

Таблицы: wb_adv_subject, wb_adv_supplier_nm.
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
    from backend.services.adv_catalog_service import AdvCatalogService
    print("WB API: GET advert.../supplier/subjects + POST .../supplier/nms"
          " → wb_adv_subject, wb_adv_supplier_nm", flush=True)
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
                st = await AdvCatalogService(db, company_id=cid).sync(
                    payment_type=args.payment_type, dry_run=args.dry_run,
                    progress=_make_progress(name))
                if st.get("skipped"):
                    print(f"[{name}] SKIP: {st['skipped']}")
                    skipped += 1
                    continue
                print(f"[{name}] предметов={st.get('subjects')} "
                      f"карточек={st.get('cards')} "
                      f"тип оплаты={args.payment_type} {st.get('token_type')}")
                ok += 1
            except Exception as e:
                print(f"[{name}] ERROR: {e}")
                errors += 1
        print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
        return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Справочник рекламы WB (предметы и карточки)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--payment-type", choices=("cpm", "cpc"), default="cpm")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
