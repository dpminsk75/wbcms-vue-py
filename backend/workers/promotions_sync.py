"""Акции WB — синк календаря акций (dp-calendar-api → wb_promotions).

Запуск (на сервере, только venv):
  .venv/bin/python backend/workers/promotions_sync.py
  .venv/bin/python backend/workers/promotions_sync.py --company-id 1
  .venv/bin/python backend/workers/promotions_sync.py --without-products
  .venv/bin/python backend/workers/promotions_sync.py --probe-auto
  DRY_RUN=1 .venv/bin/python backend/workers/promotions_sync.py
  Таймер: wbcms-promotions (hourly в :10)

GET dp-calendar-api.../calendar/promotions (+ /details, + /nomenclatures),
Authorization = raw companies.api_key, категория токена «Цены и скидки».
Таблицы: wb_promotions (календарь+детали), wb_promotion_products (номенклатура).

Каждый прогон пробует номенклатуру ПЕРВОЙ автоакции: спека WB говорит
«Not applicable for auto promotions», но если метод заработал — приложение
перейдёт на данные API. Ответ 422 означает «и остальные не дадут» — дальше
запросы не тратим. --probe-auto проверяет все автоакции окна.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _make_progress(label: str):
    def cb(stage: str, n: int, status: str, text: str):
        print(f"  [{label}] {stage}: {text}", flush=True)
    return cb


async def run(args) -> int:
    from sqlalchemy import text
    from backend.database import get_session
    from backend.services.promotions_sync_service import PromotionsSyncService

    ok, skipped, errors = 0, 0, 0
    try:
        async with get_session() as db:
            companies = (await db.execute(text(
                "SELECT id, name FROM companies WHERE is_active = 1"
                " AND api_key IS NOT NULL AND api_key <> ''"
                + (" AND id = :cid" if args.company_id else "")
                + " ORDER BY id"),
                ({"cid": args.company_id} if args.company_id else {}))).mappings().all()
            for comp in companies:
                cid = int(comp["id"])
                name = comp["name"] or str(cid)
                print(f"[{name}] старт...", flush=True)
                try:
                    st = await PromotionsSyncService(db, company_id=cid).sync_all(
                        days_back=args.days_back, days_forward=args.days_forward,
                        with_products=not args.without_products,
                        probe_auto=args.probe_auto,
                        dry_run=args.dry_run,
                        progress=_make_progress(name))
                    if st.get("skipped"):
                        print(f"[{name}] SKIP: {st['skipped']}")
                        skipped += 1
                        continue
                    warn = f" WARNING: {st['warning']}" if st.get("warning") else ""
                    print(f"[{name}] акций={st.get('fetched')} деталей={st.get('details')} "
                          f"товаров={st.get('products')} {st.get('token_type')}{warn}", flush=True)
                    for probe in (st.get("probed_auto") or []):
                        if probe.get("ok"):
                            print(f"[{name}] АВТОАКЦИЯ {probe['promo_id']}: "
                                  f"номенклатура ДОСТУПНА ({probe['products']} шт.)")
                        else:
                            print(f"[{name}] АВТОАКЦИЯ {probe['promo_id']}: "
                                  f"номенклатура недоступна — {probe.get('error')}")
                    probed = st.get("probed_auto") or []
                    if probed:
                        ok = sum(1 for p in probed if p.get("ok"))
                        print(f"[{name}] автоакций проверено: {len(probed)}, "
                              f"номенклатура доступна у {ok}"
                              + ("" if ok else " → берём ассортимент из метода цен WB"))
                    ok += 1
                except Exception as e:
                    print(f"[{name}] ERROR: {e}", flush=True)
                    errors += 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    print(f"TOTAL: ok={ok} skipped={skipped} errors={errors} dry_run={args.dry_run}")
    return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Акции WB (dp-calendar-api → wb_promotions)")
    ap.add_argument("--company-id", type=int, default=None)
    ap.add_argument("--days-back", type=int, default=30,
                    help="сколько дней назад брать календарь (дефолт 30)")
    ap.add_argument("--days-forward", type=int, default=90,
                    help="сколько дней вперёд (дефолт 90 — анонсы акций)")
    ap.add_argument("--without-products", action="store_true",
                    help="только календарь, без номенклатуры активных акций")
    ap.add_argument("--probe-auto", action="store_true",
                    help="расширенная проверка: номенклатура для ВСЕХ автоакций окна "
                         "(обычно хватает одной — первой)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("DRY_RUN")))
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
