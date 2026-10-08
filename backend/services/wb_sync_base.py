"""Общая база sync-воркеров WB: гейт по company_wb_tokens + POST с ретраями.

Гейт компании (до первого запроса в WB):
- нет api_key / нет активной строки проверки → unknown-тип, базовые паузы + WARNING;
- is_test / days_left<0 → SKIP; нет нужной категории → SKIP (401/403 не ждём);
- unknown-тип = базовый (консервативно).
Правило 2 часов (2026-10-07): базовый токен с оценкой > 2ч → SKIP
(«нужен персональный/сервисный»), ≤ 2ч → едем. Только stdlib.
"""

import json
import time
import urllib.error
import urllib.request

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_BASIC_S = 7200  # 2 часа — потолок работы на базовом токене
REQ_OVERHEAD_S = 5  # оценка времени одного запроса сверх паузы


async def company_sync_plan(
    db: AsyncSession,
    company_id: int,
    need_category: str,
    chunks: int,
    pause_fast_s: int = 20,
    pause_slow_s: int = 1800,
) -> dict:
    """План прогона компании: токен, пауза, оценка времени или причина скипа."""
    row = (await db.execute(
        text("SELECT api_key FROM companies WHERE id = :cid"), {"cid": company_id}
    )).first()
    token = ((row[0] if row else "") or "").strip()
    if not token:
        return {"skip": "companies.api_key пуст", "token": ""}
    trow = (await db.execute(text("""
        SELECT token_type, categories, is_test, days_left
        FROM company_wb_tokens WHERE company_id = :c AND is_active = 1 LIMIT 1"""),
        {"c": company_id})).mappings().first()
    if trow is None:
        pause, ttype, warn = pause_slow_s, "unknown", "нет строки проверки токена"
    else:
        if trow["is_test"]:
            return {"skip": "тестовый токен (is_test=1)", "token": token}
        if trow["days_left"] is not None and int(trow["days_left"]) < 0:
            return {"skip": "токен протух (days_left<0)", "token": token}
        cats = trow["categories"] or []
        if isinstance(cats, str):
            try:
                cats = json.loads(cats)
            except ValueError:
                cats = []
        if need_category not in (cats or []):
            return {"skip": f"нет категории {need_category} в токене", "token": token}
        ttype = (trow["token_type"] or "unknown").strip() or "unknown"
        pause = pause_fast_s if ttype in ("personal", "service") else pause_slow_s
        warn = "" if ttype in ("personal", "service") else f"токен {ttype}"
    est = max(0, chunks - 1) * (pause + REQ_OVERHEAD_S)
    if pause != pause_fast_s and est > MAX_BASIC_S:
        return {"skip": f"basic: ~{est // 3600}ч > 2ч, нужен персональный/сервисный",
                "token": token, "token_type": ttype, "est_s": est}
    out = {"token": token, "token_type": ttype, "pause_s": pause,
           "chunks": chunks, "est_s": est}
    if warn:
        out["warning"] = warn
    return out


def post_json(url: str, payload: dict, auth: str, timeout: int = 15,
               retries: int = 3, log=None) -> dict | list:
    """POST JSON с ретраями: 429 — по Retry-After/X-RateLimit-Retry, 5xx/сеть — экспонента.
    log(msg) — колбэк для видимости (send/retry), чтобы не выглядело «висением»."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last: Exception | None = None
    if log:
        log("send")
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": auth, "Content-Type": "application/json",
            "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                try:
                    _b = e.read(300).decode("utf-8", "replace")
                except Exception:
                    _b = ""
                wait = _retry_after_raw(e, _b) or 60
                if log:
                    log(f"429 → жду {wait}с (попытка {attempt + 2}/{retries + 1})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"WB http={e.code}") from e
        except Exception as e:
            last = e
            reason = str(getattr(e, "reason", e))[:80]
            if attempt < retries:
                wait = 2 ** attempt
                if log:
                    log(f"{type(e).__name__}({reason}) → жду {wait}с "
                        f"(попытка {attempt + 2}/{retries + 1})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"WB network: {type(e).__name__}({reason})") from e
    raise RuntimeError(f"WB failed: {last}")


def get_json(url: str, params=None, token: str = "", timeout: int = 15,
               retries: int = 3, log=None) -> dict | list:
    """GET с ретраями (те же правила, что в post_json).
    params: dict или список кортежей (повтор ключей: [("id",1),("id",2)])."""
    import urllib.parse
    q = ""
    if params:
        q = ("?" + urllib.parse.urlencode(params, doseq=True)) if not isinstance(params, str) else params
    last: Exception | None = None
    if log:
        log("send")
    for attempt in range(retries + 1):
        req = urllib.request.Request(url + q, headers={
            "Authorization": token, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                if not raw.strip():
                    if int(resp.status) == 204:
                        return []  # дока WB: 204 на download = «нет данных», не ошибка
                    raise RuntimeError("WB: пустой ответ")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read(300).decode("utf-8", "replace")
            except Exception:
                pass
            if e.code == 429 and attempt < retries:
                wait = _retry_after_raw(e, body) or 60
                if log:
                    log(f"429 → жду {wait}с (попытка {attempt + 2}/{retries + 1})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"WB http={e.code} {body[:120]}") from e
        except RuntimeError:
            raise  # наши собственные (пустой ответ) — не ретраить как сеть
        except Exception as e:
            last = e
            reason = str(getattr(e, "reason", e))[:80]
            if attempt < retries:
                wait = 2 ** attempt
                if log:
                    log(f"{type(e).__name__}({reason}) → жду {wait}с "
                        f"(попытка {attempt + 2}/{retries + 1})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"WB network: {type(e).__name__}({reason})") from e
    raise RuntimeError(f"WB failed: {last}")


def _retry_after_raw(e: urllib.error.HTTPError, body: str) -> int | None:
    for h in ("X-RateLimit-Retry", "Retry-After"):
        v = e.headers.get(h)
        if v and str(v).isdigit():
            return max(1, int(v))
    try:
        detail = (json.loads(e.read(500).decode("utf-8", "replace")).get("detail") or "")
    except Exception:
        return None
    import re
    m = re.search(r"retry.*?(\d+)\s*s", detail, re.I)
    return max(1, int(m.group(1))) if m else None


TERMINAL_TASK = {"purged", "canceled", "cancelled", "error", "failed"}


def run_async_report(base: str, kind: str, token: str, df: str, dt: str,
                     log=None, timeout: int = 15) -> list:
    """Async-отчёт WB: create task (429×5) → poll status 10с×60 → download.
    kind: 'paid_storage' | 'acceptance_report'. Возвращает список строк."""
    task = None
    for attempt in range(1, 6):
        try:
            data = get_json(f"{base}/api/v1/{kind}",
                            [("dateFrom", df), ("dateTo", dt)],
                            token, timeout=timeout, log=log)
        except RuntimeError as e:
            if "http=429" in str(e) and attempt < 5:
                time.sleep(60)
                continue
            raise
        d = data if isinstance(data, dict) else {}
        task = ((d.get("data") or {}).get("id") if isinstance(d.get("data"), dict)
                else None) or (d.get("data") or {}).get("taskId") \
            or d.get("id") or d.get("taskId")
        if isinstance(task, dict):
            task = task.get("id")
        if task:
            break
        raise RuntimeError(f"WB {kind}: нет taskId в ответе {str(data)[:200]}")
    if log:
        log(f"task {task}")
    # Опрос по докам WB: backoff 5→30с (лимит статуса 1/5с), дедлайн 10 мин
    # (магазины маленькие; будет большой клиент — поднять до 1800).
    # purged = отчёт удалён (окно 2ч) — пересоздавать тут не пытаемся, упадёт в ERROR
    # и доберётся следующим прогоном; canceled — параметры кривые.
    delay, deadline, t0 = 5, time.monotonic() + 600, time.monotonic()
    while time.monotonic() < deadline:
        try:
            data = get_json(f"{base}/api/v1/{kind}/tasks/{task}/status",
                            None, token, timeout=timeout, log=log)
        except RuntimeError as e:
            msg = str(e)
            if "http=4" in msg and "http=429" not in msg:
                raise  # задача протухла/нет прав — дальше ждать бессмысленно
            if log:
                log(f"пустой ответ/сеть ({msg[:60]}), жду")
            time.sleep(delay)
            delay = min(delay * 2, 30)
            continue
        d = data if isinstance(data, dict) else {}
        st = ((d.get("data") or {}).get("status") if isinstance(d.get("data"), dict)
              else d.get("status"))
        st = str(st or "").lower()
        if st == "done":
            break
        if st in TERMINAL_TASK:
            raise RuntimeError(f"WB {kind}: задача {st}")
        if log:
            el = int(time.monotonic() - t0)
            log(f"статус {st or '?'} [{el // 60}м{el % 60:02d}]")
        time.sleep(delay)
        delay = min(delay * 2, 30)
    else:
        raise RuntimeError(f"WB {kind}: задача не done за 10 мин")
    try:
        if log:
            log("скачиваю отчёт...")
        data = get_json(f"{base}/api/v1/{kind}/tasks/{task}/download",
                        None, token, timeout=120, log=log)
    except RuntimeError as e:
        if "JSONDecode" in str(e) or "Expecting value" in str(e):
            # HTTP 204/пустое тело на download = «нет данных», не ошибка
            if log:
                log("download пуст — нет данных")
            return []
        raise
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        rows = data["data"]
    elif isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = [data]
    else:
        rows = []
    if log:
        log(f"скачано строк {len(rows)}")
    return rows
