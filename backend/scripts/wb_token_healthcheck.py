#!/usr/bin/env python3
"""Daily health-check WB-токенов всех активных компаний.

Декодирует companies.api_key, живым ping опрашивает категории из маски s,
пишет результат в company_wb_tokens (active=1), в stdout — ALERT-строки:
  ALERT <company> token expired / dead 401 /членит по категориям 403.
Запуск: systemd timer wbcms-wb-tokens (ежедневно) или руками из корня проекта:
  .venv/bin/python backend/scripts/wb_token_healthcheck.py
Сырые токены не печатаем — только id компании, имя и sha256-префикс.
"""

import asyncio
import hashlib
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _load_dotenv(path: pathlib.Path) -> None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass


async def main() -> int:
    _load_dotenv(ROOT / ".env")
    from backend.database import SessionLocal  # noqa: E402
    from backend.services import wb_token_service as svc  # noqa: E402
    from sqlalchemy import text  # noqa: E402

    alerts = 0
    checked = 0
    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT id, name, api_key FROM companies
            WHERE is_active=1 AND api_key IS NOT NULL AND api_key <> ''
            ORDER BY id
        """))).mappings().all()
        for row in rows:
            cid, name, raw = row["id"], row["name"], (row["api_key"] or "").strip()
            tag = f"[company {cid} {name} sha={hashlib.sha256(raw.encode()).hexdigest()[:8]}]"
            dec = svc.decode_token(raw)
            if not dec.get("valid"):
                print(f"ALERT {tag} token undecodable: {dec.get('error')}", flush=True)
                alerts += 1
                continue
            if dec.get("expired"):
                print(f"ALERT {tag} token EXPIRED at {dec.get('exp_at')}", flush=True)
                alerts += 1
            elif (dec.get("days_left") or 999) <= 14:
                print(f"WARN {tag} token expires in {dec.get('days_left')}d ({dec.get('exp_at')})", flush=True)
            out = await svc.ping_token(raw, only_in_token=True)
            dead = [k for k, p in (out.get("ping") or {}).items() if p.get("http") == 401]
            denied = [k for k, p in (out.get("ping") or {}).items() if p.get("http") == 403]
            if dead:
                print(f"ALERT {tag} ping 401 (token dead/revoked) on: {','.join(sorted(dead))}", flush=True)
                alerts += 1
            if denied:
                print(f"WARN {tag} ping 403 (no access/subscription) on: {','.join(sorted(denied))}", flush=True)
            ok = await svc.save_check(db, cid, raw, out, active=True)
            print(f"OK {tag} type={out.get('token_type')} days_left={out.get('days_left')} saved={ok}", flush=True)
            # Профиль продавца: добиваем, если нет, старше 7 дней или с ошибкой.
            try:
                prow = (await db.execute(text("""
                    SELECT fetched_at, last_error FROM company_wb_profile WHERE company_id=:c LIMIT 1
                """), {"c": cid})).mappings().first()
            except Exception:
                await db.rollback()
                prow = {"fetched_at": None, "last_error": "no table"}
            from datetime import datetime as _dt  # noqa: E402
            stale = True
            if prow and prow["fetched_at"] and not prow["last_error"]:
                try:
                    stale = (_dt.now() - prow["fetched_at"]).days >= 7
                except TypeError:
                    stale = True
            if stale and not dec.get("expired"):
                prof = await svc.fetch_seller_profile(raw)
                pok = await svc.save_profile(db, cid, out.get("sid"), prof)
                print(f"OK {tag} profile saved={pok} err={prof.get('last_error')}", flush=True)
            checked += 1
            await asyncio.sleep(2)  # щадим лимиты WB между компаниями
    print(f"DONE checked={checked} alerts={alerts}", flush=True)
    return 2 if alerts else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
