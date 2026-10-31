"""Минимальный OpenRouter chat (порт OpenRouterClient::chat для вариантов A/B).

urllib + asyncio.to_thread — event loop свободен, `--workers 1` не висит.
Пока без ротации wb_seo_model/cooldown (следующий шаг): модель — первая из
списка компании (companies.seo_model, запятая = fallback), ключ — per-company
или env OPENROUTER_API_KEY. Ретрай 429 — 1 раз после Retry-After (иначе 20с).

С 2026-10-21 — точка выбора провайдера: если companies.seo_llm_provider = 'custom',
запрос уходит в llm_provider (другой сервис: свой URL/ключ/формат API).
Ветка openrouter ниже не менялась.
"""

import asyncio
import json
import os
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.services import llm_balance
from backend.services import llm_provider

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_S = 90
DEFAULT_MODEL = "minimax/minimax-m3:free"
RETRY_429_WAIT = 20

# логирование/парсинг ошибок/JSON — живут в llm_provider (общие для всех провайдеров)
ai_log = llm_provider.ai_log
_err_text = llm_provider.err_text


async def resolve_company_llm(db: AsyncSession, company_id: int | None,
                              row: dict | None = None) -> tuple[str, str]:
    """(api_key, model) для openrouter. row — уже прочитанная строка companies (опционально)."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    if row is None and company_id is not None:
        row = await llm_provider.company_row(db, company_id)
    if row:
        if row.get("seo_openrouter_key"):
            api_key = row["seo_openrouter_key"]
        if row.get("seo_model"):
            model = row["seo_model"]
    # "m1,m2" — первая рабочая, остальные fallback вызывающей стороны
    model = (model or DEFAULT_MODEL).split(",")[0].strip() or DEFAULT_MODEL
    return api_key, model


def _post(url: str, payload: dict, api_key: str, timeout: int):
    """POST к openrouter (заголовки как раньше). Общий HTTP — в llm_provider.post_json."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return llm_provider.post_json(url, payload, headers, timeout)


async def chat(db: AsyncSession, messages: list[dict], company_id: int | None,
               temperature: float = 0.4, max_tokens: int = 1500,
               model: str | None = None, note: str = "",
               timeout: int | None = None, retry_429: bool = True,
               scenario: str = "other", user_id: int | None = None,
               nm_id: int | None = None, job_id: int | None = None,
               journal: bool = True, reasoning_effort: str | None = None,
               send_max_tokens: bool = False) -> dict:
    """Единая точка вызова ИИ: сам запрос + запись в журнал ai_usage.

    note — контекст вызывающей стороны для лога ('кандидат 2/5, nm 123'): кто и зачем стучится.
    scenario/user_id/nm_id/job_id — для журнала расхода (см. ai_usage_service).
    journal=False — не писать в журнал (журнал пишет вызывающая сторона).
    Возвращает {content, prompt_tokens, completion_tokens, cost, model, provider} или {error}."""
    res = await _chat_inner(db, messages, company_id, temperature, max_tokens, model, note,
                            timeout, retry_429, reasoning_effort, send_max_tokens)
    if journal:
        await _record_usage(db, res, company_id=company_id, user_id=user_id, scenario=scenario,
                            nm_id=nm_id, job_id=job_id, model=model)
    # У провайдера кончились токены → компания встаёт на паузу (3 ч): фоновые
    # разборы не должны долбить ключ, пока не откроется окно. Правило одно на
    # всех вызовов (фоновые и ручные) — см. backend/services/llm_balance.py.
    reason = llm_balance.reason_of(res)
    if reason:
        llm_balance.pause(company_id, reason)
    return res


async def _record_usage(db: AsyncSession, res: dict, *, company_id: int | None,
                        user_id: int | None, scenario: str, nm_id: int | None,
                        job_id: int | None, model: str | None) -> None:
    """Запись вызова в ai_usage. Ошибка записи не ломает основной поток."""
    try:
        from backend.services import ai_usage_service
        err = res.get("error") or ""
        content = (res.get("content") or "").strip()
        await ai_usage_service.record_usage(
            db,
            company_id=company_id,
            user_id=user_id,
            provider=res.get("provider") or "openrouter",
            model=res.get("model") or model,
            scenario=scenario,
            nm_id=nm_id,
            job_id=job_id,
            prompt_tokens=res.get("prompt_tokens"),
            completion_tokens=res.get("completion_tokens"),
            cost=res.get("cost"),
            # при ошибке/пустом ответе в preview кладём тело ответа провайдера
            preview=content or res.get("empty_reason") or err,
            http=res.get("http"),
            ok=bool(content) and not err,
            error=err,
        )
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


async def _chat_inner(db: AsyncSession, messages: list[dict], company_id: int | None,
                       temperature: float, max_tokens: int, model: str | None, note: str,
                       timeout: int | None, retry_429: bool,
                       reasoning_effort: str | None = None,
                       send_max_tokens: bool = False) -> dict:
    """Сам запрос (без журнала) — тело без изменений с 2026-10-21."""
    # Настройки компании читаем на КОРОТКОЙ сессии: если оставить SELECT на db
    # вызывающего, autobegin-транзакция откроется ПОД HTTP-ожидание (до 90 с × 2-3
    # попытки) — её read view будет держать InnoDB purge у всего сервера
    # (растёт history list) — тот самый «повесило сервер».
    async with get_session() as sdb:
        row = await llm_provider.company_row(sdb, company_id)
    cfg = llm_provider.config_from_row(row)
    if cfg.provider != "openrouter":
        # «другой сервис» — свой транспорт (URL/ключ/формат из companies.seo_llm_*).
        # Страховка: отправляем ТОЛЬКО модель этого сервиса — openrouter-slug'и
        # (dots-llama/..., z-ai/...) такому API не годятся.
        main_models = llm_provider.model_list(row, "main")
        sum_models = llm_provider.model_list(row, "summary")
        allowed = main_models + [m for m in sum_models if m not in main_models]
        m = (model or "").split(",")[0].strip()
        if not m:
            m = allowed[0] if allowed else ""
        elif allowed and m not in allowed:
            m = allowed[0]
        if not m:
            return {"error": "не задана модель для «другого сервиса» (companies.seo_llm_model)",
                    "provider": cfg.provider}
        return await llm_provider.chat(cfg, messages, temperature=temperature,
                                       max_tokens=max_tokens, model=m, note=note,
                                       timeout=timeout, retry_429=retry_429,
                                       reasoning_effort=reasoning_effort,
                                       send_max_tokens=send_max_tokens)
    async with get_session() as sdb:
        api_key, resolved = await resolve_company_llm(sdb, company_id, row=row)
    model = (model or resolved).split(",")[0].strip() or DEFAULT_MODEL
    if not api_key:
        return {"error": "openrouter key is empty (env OPENROUTER_API_KEY / companies.seo_openrouter_key)",
                "provider": "openrouter"}
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens,
               # reasoning-модели сливают thinking в content вместо ответа —
               # просим провайдера исключить reasoning из выдачи
               "reasoning": {"exclude": True}}
    url = f"{BASE_URL}/chat/completions"
    req_timeout = int(timeout or TIMEOUT_S)
    last_http, last_headers, last_info = "", {}, ""
    for attempt in (1, 2):
        status, reason, headers, body, info = await asyncio.to_thread(_post, url, payload, api_key, req_timeout)
        http = f"{status} {reason}".strip()
        last_http, last_headers, last_info = http, headers, info
        if status == 200 and isinstance(body, dict):
            try:
                choice = body["choices"][0]
                msg = choice["message"]
                if not isinstance(choice, dict) or not isinstance(msg, dict):
                    raise TypeError("message is not an object")
                usage = body.get("usage") or {}
                content = msg.get("content") or ""
                if isinstance(content, list):
                    content = "".join(
                        str(p.get("text") or "") if isinstance(p, dict) else str(p)
                        for p in content
                    )
                from_reasoning = False
                if not content.strip():
                    # Пусто при 200: в лог — ПОЧЕМУ (refusal/reasoning/сырое тело), а не пустую строку
                    why = (msg.get("refusal")
                           or msg.get("reasoning_content") or msg.get("reasoning")
                           or str(body)[:2000])
                    if isinstance(why, str) and why.strip().startswith(("{", "[")):
                        content = why.strip()
                        from_reasoning = True
                    else:
                        ai_log("empty", model, messages, str(why), http, headers, note,
                               provider="openrouter")
                        return {"content": "", "prompt_tokens": usage.get("prompt_tokens"),
                                "completion_tokens": usage.get("completion_tokens"),
                                "cost": float(usage.get("cost") or 0.0),
                                "provider": "openrouter",
                                "error": f"empty response: {str(why)[:300]}",
                                "empty_reason": str(why or "")[:8000],
                                "finish_reason": choice.get("finish_reason"),
                                "model": body.get("model") or model, "http": http}
                out = {"content": content,
                       "prompt_tokens": usage.get("prompt_tokens"),
                       "completion_tokens": usage.get("completion_tokens"),
                       "cost": float(usage.get("cost") or 0.0),
                       "provider": "openrouter",
                       "finish_reason": choice.get("finish_reason"),
                       "from_reasoning": from_reasoning,
                       "model": body.get("model") or model,
                       "http": http}
                ai_log("ok", model, messages, out["content"], http, headers, note, provider="openrouter")
                return out
            except (KeyError, IndexError, TypeError):
                ai_log("bad-response", model, messages, str(body)[:500], http, headers, note,
                       provider="openrouter")
                return {"error": f"bad openrouter response: {str(body)[:200]}", "http": http,
                        "provider": "openrouter", "model": model}
        if status == 429 and attempt == 1 and retry_429:
            # Первый 429 тоже логируем (раньше событие терялось до retry)
            ai_log("429-retry", model, messages, _err_text(body, info), http, headers, note,
                   provider="openrouter")
            await asyncio.sleep(RETRY_429_WAIT)
            continue
        ai_log("error", model, messages, _err_text(body, info), http, headers, note, provider="openrouter")
        return {"error": _err_text(body, info), "http": http, "provider": "openrouter", "model": model}
    ai_log("error", model, messages, f"retry exhausted ({last_info})", last_http, last_headers, note,
           provider="openrouter")
    return {"error": f"openrouter retry exhausted ({last_info})", "http": last_http}


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
                           kind: str = "main",
                           fallback: tuple[str, ...] = ()) -> list[str]:
    """Список моделей для сценария: main | summary | newcard.

    Для провайдера 'custom' возвращаем ТОЛЬКО его модели (companies.seo_llm_model /
    seo_llm_summary_model, список через запятую, по порядку проб): openrouter-slug'и
    в запрос другого сервиса не годятся, пул wb_seo_model и fallback — тоже.
    """
    row = await llm_provider.company_row(db, company_id)
    cfg = llm_provider.config_from_row(row)
    if cfg.provider != "openrouter":
        return llm_provider.model_list(row, kind)
    cands: list[str] = llm_provider.model_list(row, kind)
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
    """Порт WbSeoModel::markSuccess/markError: счётчики, кулдаун 5/15/60/180м, авто-off после 10.

    Модели другого провайдера в wb_seo_model не знаем — для них это no-op
    (статистика по custom-провайдерам — отдельная задача)."""
    try:
        known = (await db.execute(text("""
            SELECT id FROM wb_seo_model WHERE model_id=:m LIMIT 1
        """), {"m": model_id})).mappings().first()
        if not known:
            await db.rollback()
            return
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
