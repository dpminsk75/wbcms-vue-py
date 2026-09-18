"""Минимальный OpenRouter chat (порт OpenRouterClient::chat для вариантов A/B).

urllib + asyncio.to_thread — event loop свободен, `--workers 1` не висит.
Пока без ротации wb_seo_model/cooldown (следующий шаг): модель — первая из
списка компании (companies.seo_model, запятая = fallback), ключ — per-company
или env OPENROUTER_API_KEY. Ретрай 429 — 1 раз после Retry-After (иначе 20с).
"""

import asyncio
import json
import os
import time
import urllib.error
import urllib.request

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_S = 90
DEFAULT_MODEL = "minimax/minimax-m3:free"
RETRY_429_WAIT = 20


async def resolve_company_llm(db: AsyncSession, company_id: int | None) -> tuple[str, str]:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    if company_id is not None:
        row = (await db.execute(text("""
            SELECT seo_openrouter_key, seo_model, seo_openrouter_referer, seo_openrouter_title
            FROM companies WHERE id=:c LIMIT 1
        """), {"c": company_id})).mappings().first()
        if row:
            if row["seo_openrouter_key"]:
                api_key = row["seo_openrouter_key"]
            if row["seo_model"]:
                model = row["seo_model"]
    # "m1,m2" — первая рабочая, остальные fallback вызывающей стороны
    model = (model or DEFAULT_MODEL).split(",")[0].strip() or DEFAULT_MODEL
    return api_key, model


def _headers_dict(headers) -> dict:
    try:
        return {k.lower(): v for k, v in dict(headers.items()).items()}
    except Exception:
        return {}


def _post(url: str, payload: dict, api_key: str, timeout: int) -> tuple[int, str, dict, dict | None, str]:
    """Возвращает (http_status, http_reason, response_headers, body, info).
    Статус/reason/headers/ms — с провода: reason парсит http.client из статус-строки,
    ms меряем локально монотонными часами, headers — реальные заголовки ответа."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2_000_000).decode("utf-8", "replace")
            ms = int((time.monotonic() - t0) * 1000)
            status, reason, headers = int(resp.status), str(getattr(resp, "reason", "")), _headers_dict(resp.headers)
            try:
                return status, reason, headers, json.loads(raw), f"{ms}ms"
            except ValueError:
                # 200 с битым телом — не сетевая ошибка: помечаем отдельно, chat разберёт как bad-response
                return status, reason, headers, {"_invalid_json": raw[:2000]}, f"{ms}ms"
    except urllib.error.HTTPError as exc:
        # Тело ошибки НЕ теряем: пробуем JSON (problem+json), иначе сырой текст — уходит в лог и item.error
        try:
            raw_body = exc.read(2000).decode("utf-8", "replace")
        except Exception:
            raw_body = ""
        try:
            err_data = json.loads(raw_body) if raw_body.strip() else None
        except ValueError:
            err_data = raw_body or None
        wait = exc.headers.get("X-Ratelimit-Retry") or exc.headers.get("Retry-After") or ""
        ms = int((time.monotonic() - t0) * 1000)
        return int(exc.code), str(getattr(exc, "reason", "")), _headers_dict(exc.headers), err_data, f"http {exc.code} ({ms}ms, retry-after: {wait or '-'})"
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        return 0, type(exc).__name__, {}, None, f"{type(exc).__name__} ({ms}ms)"


async def chat(db: AsyncSession, messages: list[dict], company_id: int | None,
               temperature: float = 0.4, max_tokens: int = 1500,
               model: str | None = None, note: str = "") -> dict:
    """note — контекст вызывающей стороны для лога ('кандидат 2/5, nm 123'): кто и зачем стучится.
    Возвращает {content, prompt_tokens, completion_tokens, model} или {error}."""
    api_key, resolved = await resolve_company_llm(db, company_id)
    model = (model or resolved).split(",")[0].strip() or DEFAULT_MODEL
    if not api_key:
        return {"error": "openrouter key is empty (env OPENROUTER_API_KEY / companies.seo_openrouter_key)"}
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens,
               # reasoning-модели сливают thinking в content вместо ответа —
               # просим провайдера исключить reasoning из выдачи
               "reasoning": {"exclude": True}}
    url = f"{BASE_URL}/chat/completions"
    last_http, last_headers, last_info = "", {}, ""
    for attempt in (1, 2):
        status, reason, headers, body, info = await asyncio.to_thread(_post, url, payload, api_key, TIMEOUT_S)
        http = f"{status} {reason}".strip()
        last_http, last_headers, last_info = http, headers, info
        if status == 200 and isinstance(body, dict):
            try:
                msg = body["choices"][0]["message"]
                usage = body.get("usage") or {}
                content = msg.get("content") or ""
                if not content.strip():
                    # Пусто при 200: в лог — ПОЧЕМУ (refusal/reasoning/сырое тело), а не пустую строку
                    why = (msg.get("refusal")
                           or msg.get("reasoning_content") or msg.get("reasoning")
                           or str(body)[:2000])
                    ai_log("empty", model, messages, str(why), http, headers, note)
                    return {"content": "", "prompt_tokens": usage.get("prompt_tokens"),
                            "completion_tokens": usage.get("completion_tokens"),
                            "model": body.get("model") or model, "http": http}
                out = {"content": content,
                       "prompt_tokens": usage.get("prompt_tokens"),
                       "completion_tokens": usage.get("completion_tokens"),
                       "model": body.get("model") or model,
                       "http": http}
                ai_log("ok", model, messages, out["content"], http, headers, note)
                return out
            except (KeyError, IndexError, TypeError):
                ai_log("bad-response", model, messages, str(body)[:500], http, headers, note)
                return {"error": f"bad openrouter response: {str(body)[:200]}", "http": http}
        if status == 429 and attempt == 1:
            # Первый 429 тоже логируем (раньше событие терялось до retry)
            ai_log("429-retry", model, messages, _err_text(body, info), http, headers, note)
            await asyncio.sleep(RETRY_429_WAIT)
            continue
        ai_log("error", model, messages, _err_text(body, info), http, headers, note)
        return {"error": _err_text(body, info), "http": http}
    ai_log("error", model, messages, f"retry exhausted ({last_info})", last_http, last_headers, note)
    return {"error": f"openrouter retry exhausted ({last_info})", "http": last_http}


def _err_text(body, info: str) -> str:
    """Тело HTTP-ошибки в читаемом виде для лога/item.error: JSON → компактно, текст → как есть."""
    if isinstance(body, dict):
        try:
            return json.dumps(body, ensure_ascii=False)[:500]
        except Exception:
            pass
    if isinstance(body, str) and body.strip():
        return body[:500]
    return info


def ai_log(kind: str, model: str | None, messages: list[dict], content: str, http: str = "", headers: dict | None = None, note: str = "") -> None:
    """Аналог yii ai.log: полный обмен — в backend/runtime/ai.log (папка создаётся
    сама, ротация при >10МБ), краткая строка — в stdout (journalctl -u wbcms-py).
    Полный обмен последнего вызова задачи — также в ai_job_item.result."""
    if not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False)
        except Exception:
            content = str(content)
    line = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "ai_log": kind, "model": model,
            "http": http, "try": note,
            "headers": headers or {},
            "request": messages, "response": content}
    try:
        import pathlib as _pl
        logdir = _pl.Path(__file__).resolve().parents[1] / "runtime"
        logdir.mkdir(parents=True, exist_ok=True)
        logf = logdir / "ai.log"
        if logf.exists() and logf.stat().st_size > 10_000_000:
            old = logdir / "ai.log.1"
            if old.exists():
                old.unlink()
            logf.rename(old)
        with open(logf, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        req_chars = sum(len(str(m.get("content") or "")) for m in messages)
        print(json.dumps({"ai_log": kind, "model": model, "http": http,
                          "req_chars": req_chars,
                          "resp_chars": len(content or ""),
                          "resp_head": (content or "")[:300],
                          "ts": line["ts"]},
                         ensure_ascii=False), flush=True)
    except Exception:
        pass


def safe_json_decode(raw: str) -> dict | list | None:
    """Порт CompetitorController::safeJsonDecode: BOM, ctrl-chars, висячие запятые, {..} внутри."""
    import re
    if not isinstance(raw, str):
        return raw if isinstance(raw, (dict, list)) else None
    try:
        out = json.loads(raw)
        if isinstance(out, (dict, list)):
            return out
    except ValueError:
        pass
    clean = raw.lstrip("﻿ \t\n\r")
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", clean)
    clean = re.sub(r",\s*([}\]])", r"\1", clean)
    try:
        out = json.loads(clean)
        if isinstance(out, (dict, list)):
            return out
    except ValueError:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            out = json.loads(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", m.group(0)))
            if isinstance(out, (dict, list)):
                return out
        except ValueError:
            return None
    return None


async def model_candidates(db: AsyncSession, company_id: int | None,
                           override: str | None = None,
                           fallback: tuple[str, ...] = ()) -> list[str]:
    """Список моделей: override/компания → активные wb_seo_model (без кулдауна) → fallback."""
    cands: list[str] = []
    if override:
        cands = [m.strip() for m in override.split(",") if m.strip()]
    else:
        raw = ""
        if company_id is not None:
            try:
                row = (await db.execute(text("""
                    SELECT seo_model FROM companies WHERE id=:c LIMIT 1
                """), {"c": company_id})).mappings().first()
                raw = (dict(row)["seo_model"] or "") if row else ""
            except Exception:
                await db.rollback()
        if raw.strip():
            cands = [m.strip() for m in raw.split(",") if m.strip()]
    try:
        rows = (await db.execute(text("""
            SELECT model_id FROM wb_seo_model
            WHERE is_active=1 AND (cooldown_until IS NULL OR cooldown_until <= NOW())
            ORDER BY priority, id
        """))).mappings().all()
        for r in rows:
            if r["model_id"] not in cands:
                cands.append(r["model_id"])
    except Exception:
        await db.rollback()
    for fb in fallback:
        if fb not in cands:
            cands.append(fb)
    return cands or [DEFAULT_MODEL]


async def mark_model(db: AsyncSession, model_id: str, ok: bool, error: str = "") -> None:
    """Порт WbSeoModel::markSuccess/markError: счётчики, кулдаун 5/15/60/180м, авто-off после 10."""
    try:
        if ok:
            await db.execute(text("""
                UPDATE wb_seo_model SET success_count=success_count+1, consecutive_errors=0,
                  last_success_at=NOW(), last_error=NULL, cooldown_until=NULL, updated_at=NOW()
                WHERE model_id=:m
            """), {"m": model_id})
        else:
            row = (await db.execute(text("""
                SELECT consecutive_errors FROM wb_seo_model WHERE model_id=:m LIMIT 1
            """), {"m": model_id})).mappings().first()
            ce = (dict(row)["consecutive_errors"] + 1) if row else 1
            minutes = [5, 15, 60, 180][ce - 1] if ce <= 4 else 180
            is429 = ("429" in error) or ("rate-limited" in error)
            await db.execute(text("""
                UPDATE wb_seo_model SET error_count=error_count+1, consecutive_errors=:ce,
                  last_error=:e, updated_at=NOW(),
                  last_429_at=CASE WHEN :r THEN NOW() ELSE last_429_at END,
                  cooldown_until=CASE WHEN :r THEN DATE_ADD(NOW(), INTERVAL :mm MINUTE) ELSE cooldown_until END,
                  is_active=CASE WHEN :ce >= 10 THEN 0 ELSE is_active END
                WHERE model_id=:m
            """), {"ce": ce, "e": error[:480], "r": 1 if is429 else 0, "mm": minutes, "m": model_id})
        await db.commit()
    except Exception:
        await db.rollback()
