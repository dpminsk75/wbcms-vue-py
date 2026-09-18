#!/usr/bin/env python3
"""Бенч бесплатных моделей OpenRouter (порт php yii bench/free).

Тестирует коротким JSON-промптом без ретраев, обновляет wb_seo_model
(404→deactivate, 429→cooldown, ok→add/success/priority) и печатает топ-3
для companies.seo_model.

Запуск из корня проекта:
  .venv/bin/python backend/scripts/bench_models.py --limit 6 --timeout 30
  .venv/bin/python backend/scripts/bench_models.py --model google/gemma-4-31b-it:free
Ключ: env OPENROUTER_API_KEY (или первая компания с seo_openrouter_key — нет, только env).
"""

import argparse
import asyncio
import json
import os
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _load_dotenv(path: pathlib.Path) -> None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    except FileNotFoundError:
        pass


def is_seo_suitable(mid: str) -> bool:
    low = mid.lower()
    bad = ["code", "lyria", "clip", "audio", "whisper", "tts", "vision",
           "image", "embedding", "rerank", "transcribe", "reasoning"]
    return not any(b in low for b in bad)


def quality_priority(mid: str, secs: float, ctx=None) -> int:
    low = mid.lower()
    bonus = 0
    if ctx:
        ctx = int(ctx)
        bonus = -3 if ctx >= 500000 else (0 if ctx >= 200000 else 5)
    if "pro" in low:
        return 10 + bonus
    if "dots" in low:
        return 12 + bonus
    if "gemma-4-31b" in low:
        return 13 + bonus
    if "gemma-4-26b" in low:
        return 14 + bonus
    if "nemotron-3.5-lightning" in low:
        return 15 + bonus
    if "nemotron-3-super" in low:
        return 16 + bonus
    if "qwen" in low:
        return 17 + bonus
    if "llama" in low:
        return 18 + bonus
    if "sante" in low or "fin" in low:
        return 25
    if "mini" in low and "pro" not in low:
        return 28
    if "lfm" in low:
        return 40 + bonus
    return 20 + bonus


def get_models(api_key: str, timeout: int) -> dict | None:
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read(5_000_000).decode("utf-8", "replace"))
    except Exception as exc:
        print(f"getModels failed: {type(exc).__name__}: {exc}")
        return None
    items = data.get("data") or []
    all_models = [{"id": m.get("id"), "context_length": m.get("context_length")} for m in items]
    free = []
    for m in all_models:
        mid = m["id"] or ""
        if mid.endswith(":free"):
            free.append(m)
            continue
        pricing = next((x for x in items if x.get("id") == mid), {}).get("pricing") or {}
        try:
            if float(pricing.get("prompt") or 1) == 0 and float(pricing.get("completion") or 1) == 0:
                free.append(m)
        except (TypeError, ValueError):
            pass
    free = [m for m in free if m["id"] not in ("google/lyria-3-clip-preview", "openrouter/free")]
    return {"all": all_models, "free": free}


def chat_once(api_key: str, model: str, timeout: int) -> tuple[float, int, dict | None, str]:
    payload = {"model": model, "temperature": 0.3, "max_tokens": 150,
               "messages": [
                   {"role": "system", "content": 'Верни ТОЛЬКО валидный JSON без markdown: {"ok":true,"text":"привет"}'},
                   {"role": "user", "content": 'Верни JSON {"ok":true,"text":"тест скорости"}'},
               ]}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=data, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read(200_000).decode("utf-8", "replace"))
            return time.monotonic() - t0, int(resp.status), body, ""
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(500).decode("utf-8", "replace")
        except Exception:
            detail = ""
        return time.monotonic() - t0, int(exc.code), None, f"http {exc.code}: {detail[:150]}"
    except Exception as exc:
        return time.monotonic() - t0, 0, None, type(exc).__name__


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    _load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        print("OPENROUTER_API_KEY is empty (.env)")
        return 1

    from sqlalchemy import text  # noqa: E402
    from backend.database import SessionLocal  # noqa: E402

    res = await asyncio.to_thread(get_models, api_key, args.timeout)
    if not res:
        return 1
    free = res["free"]
    print(f"Всего: {len(res['all'])}, free: {len(free)}")
    if args.model:
        found = [m for m in res["all"] if m["id"] == args.model]
        free = found or [{"id": args.model, "context_length": "?"}]
        print(f"Тест одной модели: {args.model}")
    elif args.limit:
        free = free[: max(1, args.limit)]
    free = [m for m in free if is_seo_suitable(m["id"])]
    print(f"Тестирую {len(free)} моделей (без ретраев, timeout={args.timeout}с)...\n")

    results = []
    for i, m in enumerate(free):
        mid, ctx = m["id"], m.get("context_length")
        print(f"[{i + 1}/{len(free)}] {mid} ctx={ctx} ... ", flush=True, end="")
        dt, status, body, err = await asyncio.to_thread(chat_once, api_key, mid, args.timeout)
        ok, content = False, ""
        if body:
            try:
                content = (body["choices"][0]["message"].get("content") or "").strip()
            except (KeyError, IndexError, TypeError):
                content = ""
            try:
                j = json.loads(content)
                ok = isinstance(j, dict) and ("ok" in j)
            except ValueError:
                ok = False
        results.append({"id": mid, "ctx": ctx, "ok": ok, "time": dt,
                        "status": status, "error": err, "content": content[:80]})
        print(f"{'OK' if ok else 'FAIL'} {dt:.2f}с HTTP={status} {content[:60] if ok else err}")
        if i < len(free) - 1:
            await asyncio.sleep(2)

    results.sort(key=lambda r: (not r["ok"], r["time"] if r["ok"] else (r["status"] or 999)))
    print("\n" + "=" * 80 + "\nИТОГИ (успешные → быстрее):")
    print(f"{'N':<4} {'model_id':<45} {'ctx':<8} {'OK':<6} {'time':<7} {'HTTP':<6} error/content")
    for i, r in enumerate(results):
        print(f"{i + 1:<4} {r['id']:<45} {str(r['ctx']):<8} "
              f"{'YES' if r['ok'] else 'NO':<6} {r['time']:<7.2f} {r['status']:<6} "
              f"{r['content'] if r['ok'] else r['error']}")

    # --- wb_seo_model ---
    updated = 0
    async with SessionLocal() as db:
        for r in results:
            row = (await db.execute(text("""
                SELECT id, consecutive_errors FROM wb_seo_model WHERE model_id=:m LIMIT 1
            """), {"m": r["id"]})).mappings().first()
            err = r["error"] or ""
            is404 = ("404" in err) or r["status"] == 404 or ("unavailable for free" in err)
            is429 = ("429" in err) or ("rate limited" in err.lower())
            if is404:
                if row:
                    await db.execute(text("""
                        UPDATE wb_seo_model SET is_active=0, last_error=:e, updated_at=NOW() WHERE id=:i
                    """), {"e": f"bench: 404 not free {time.strftime('%Y-%m-%d %H:%M')}", "i": row["id"]})
                    print(f"  {r['id']} -> deactivated (404)")
                    updated += 1
            elif is429:
                if row:
                    ce = (row["consecutive_errors"] or 0) + 1
                    minutes = [5, 15, 60, 180][ce - 1] if ce <= 4 else 180
                    await db.execute(text("""
                        UPDATE wb_seo_model SET error_count=error_count+1, consecutive_errors=:ce,
                          last_error=:e, last_429_at=NOW(),
                          cooldown_until=DATE_ADD(NOW(), INTERVAL :mm MINUTE), updated_at=NOW()
                        WHERE id=:i
                    """), {"ce": ce, "e": err[:480], "mm": minutes, "i": row["id"]})
                    print(f"  {r['id']} -> cooldown 429")
                    updated += 1
            elif r["ok"]:
                if not row:
                    await db.execute(text("""
                        INSERT INTO wb_seo_model (model_id, title, is_active, priority, created_at, updated_at)
                        VALUES (:m, :m, 1, 20, NOW(), NOW())
                    """), {"m": r["id"]})
                    print(f"  {r['id']} -> added (was not in table)")
                    row = (await db.execute(text("""
                        SELECT id, consecutive_errors FROM wb_seo_model WHERE model_id=:m LIMIT 1
                    """), {"m": r["id"]})).mappings().first()
                await db.execute(text("""
                    UPDATE wb_seo_model SET success_count=success_count+1, consecutive_errors=0,
                      last_success_at=NOW(), last_error=NULL, cooldown_until=NULL, updated_at=NOW()
                    WHERE id=:i
                """), {"i": row["id"]})
                if r["time"] < 5:
                    prio = min(100, max(10, quality_priority(r["id"], r["time"], r["ctx"])))
                elif r["time"] < 15:
                    prio = min(100, max(20, int(r["time"] * 5)))
                else:
                    prio = 100
                await db.execute(text("UPDATE wb_seo_model SET priority=:p WHERE id=:i"),
                                 {"p": prio, "i": row["id"]})
                updated += 1
            else:
                if row:
                    ce = (row["consecutive_errors"] or 0) + 1
                    await db.execute(text("""
                        UPDATE wb_seo_model SET error_count=error_count+1, consecutive_errors=:ce,
                          last_error=:e, updated_at=NOW(),
                          is_active=CASE WHEN :ce >= 10 THEN 0 ELSE is_active END
                        WHERE id=:i
                    """), {"ce": ce, "e": (err or "no content")[:480], "i": row["id"]})
                    updated += 1
        await db.commit()
    if updated:
        print(f"Обновлено в базе: {updated}")

    best = sorted([r for r in results if r["ok"]],
                  key=lambda r: quality_priority(r["id"], r["time"], r["ctx"]))
    print("\n" + "-" * 80)
    if best:
        print("РЕКОМЕНДАЦИЯ — ставь в companies.seo_model (приоритет 1..3):")
        for k, r in enumerate(best[:3]):
            print(f" {k + 1}. {r['id']} ({r['time']:.2f}с)")
        print(f"\nДля замены:\n  UPDATE companies SET seo_model='{best[0]['id']}' WHERE id=1;")
    else:
        print("РЕКОМЕНДАЦИЯ: ни одна модель не ответила валидным JSON. "
              "Попробуй --limit=3 или --model=<id> и проверь ключ OpenRouter.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
