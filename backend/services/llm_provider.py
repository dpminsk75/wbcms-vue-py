"""Провайдеры LLM: транспорт к «другому сервису» (не OpenRouter).

Фасад для всех вызовов — `openrouter_service.chat()`: он смотрит на
`companies.seo_llm_provider` и, если провайдер = custom, уходит сюда.
Формат (диалект API) — `companies.seo_llm_format`:
openai | anthropic | gemini | ollama | yandex.

Настройки (URL/ключ/заголовки/таймаут) — `companies.seo_llm_*`.
Модели — существующие `companies.seo_model` / `seo_summary_model` / `seo_newcard_model`
(строки через запятую, пробуются по очереди).
"""

import asyncio
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

FORMATS = ("openai", "anthropic", "gemini", "ollama", "yandex")

# (заголовок авторизации, префикс значения) по умолчанию для формата
DEFAULT_AUTH = {
    "openai": ("Authorization", "Bearer "),
    "anthropic": ("x-api-key", ""),
    "gemini": ("x-goog-api-key", ""),
    "ollama": ("Authorization", "Bearer "),
    "yandex": ("Authorization", "Api-Key "),
}

# URL по умолчанию (если пользователь не задал свой)
DEFAULT_URL = {
    "openai": "",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "ollama": "http://127.0.0.1:11434",
    "yandex": "https://ai.api.cloud.yandex.net/v1/chat/completions",
}

DEFAULT_TIMEOUT = 90
RETRY_429_WAIT = 20

COMPANY_SQL_FULL = """
    SELECT id, seo_openrouter_key, seo_openrouter_referer, seo_openrouter_title,
           seo_model, seo_summary_model, seo_summary_max_tokens,
           seo_desc_min, seo_desc_max, seo_prompt, seo_competitor_prompt, seo_summary_prompt,
           seo_anti_spam_days, seo_daily_limit, seo_newcard_prompt, seo_newcard_model,
           seo_phrases_prompt,
           seo_llm_provider, seo_llm_format, seo_llm_url, seo_llm_api_key,
           seo_llm_folder_id, seo_llm_auth_header, seo_llm_auth_prefix,
           seo_llm_extra_headers, seo_llm_extra_body, seo_llm_timeout,
           seo_llm_model, seo_llm_summary_model
    FROM companies WHERE id=:c LIMIT 1
"""

# fallback — если миграция 20261023 ещё не применена (нет только колонок seo_llm_*)
COMPANY_SQL_LEGACY = """
    SELECT id, seo_openrouter_key, seo_openrouter_referer, seo_openrouter_title,
           seo_model, seo_summary_model, seo_summary_max_tokens,
           seo_desc_min, seo_desc_max, seo_prompt, seo_competitor_prompt, seo_summary_prompt,
           seo_anti_spam_days, seo_daily_limit, seo_newcard_prompt, seo_newcard_model
    FROM companies WHERE id=:c LIMIT 1
"""


@dataclass
class LlmConfig:
    provider: str = "openrouter"
    fmt: str = "openai"
    url: str = ""
    api_key: str = ""
    folder_id: str = ""
    auth_header: str = ""
    auth_prefix: str | None = None
    extra_headers: dict = field(default_factory=dict)
    extra_body: dict = field(default_factory=dict)
    timeout: int = DEFAULT_TIMEOUT


def _json_obj(raw) -> dict:
    """JSON-строка → dict; битый JSON → пустой dict (ошибку покажет «Проверить»)."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        out = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return dict(out) if isinstance(out, dict) else {}


def _norm_provider(v) -> str:
    p = str(v or "openrouter").strip().lower()
    return p if p in ("openrouter", "custom") else "openrouter"


def _norm_format(v) -> str:
    f = str(v or "openai").strip().lower()
    return f if f in FORMATS else "openai"


def provider_of(row: dict | None) -> str:
    """'openrouter' | 'custom' — провайдер компании."""
    return _norm_provider((row or {}).get("seo_llm_provider"))


def model_list(row: dict | None, kind: str = "main") -> list[str]:
    """Модели компании ДЛЯ ТЕКУЩЕГО провайдера (список через запятую, по порядку).

    kind: main | summary | newcard.
    У «другого сервиса» — свои модели (seo_llm_model / seo_llm_summary_model):
    openrouter-slug'и (dots-llama/..., z-ai/...) в его запрос уходить не должны.
    Для openrouter «newcard» = модель сводки (companies.seo_summary_model) —
    отдельного «модель новой карточки» больше нет.
    """
    row = row or {}
    if provider_of(row) != "openrouter":
        if kind == "summary":
            raw = row.get("seo_llm_summary_model") or row.get("seo_llm_model") or ""
        else:
            raw = row.get("seo_llm_model") or ""
    else:
        if kind in ("summary", "newcard"):
            raw = row.get("seo_summary_model") or row.get("seo_model") or ""
        else:
            raw = row.get("seo_model") or ""
    return [m.strip() for m in str(raw or "").split(",") if m.strip()]


def _to_int(v, default: int = 0) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


async def company_row(db: AsyncSession, company_id: int | None) -> dict | None:
    """Строка companies с SEO-настройками. None — компании нет (или company_id=None).

    Если основной SELECT падает (нет какой-то колонки — миграция не применена) —
    откатываемся на старый SELECT без seo_llm_*: провайдер = openrouter, поведение
    прежнее. ВАЖНО: fallback пишет предупреждение в лог, иначе «тихо» уезжает
    на OpenRouter (витрина: модель из openrouter вместо кастомной).
    """
    if company_id is None:
        return None
    try:
        row = (await db.execute(text(COMPANY_SQL_FULL), {"c": company_id})).mappings().first()
        return dict(row) if row else None
    except Exception as exc:
        await db.rollback()
        try:
            print(json.dumps({"llm_provider_fallback": "legacy",
                              "company_id": company_id,
                              "error": f"{type(exc).__name__}: {exc}"[:400]},
                             ensure_ascii=False), flush=True)
        except Exception:
            pass
    try:
        row = (await db.execute(text(COMPANY_SQL_LEGACY), {"c": company_id})).mappings().first()
        return dict(row) if row else None
    except Exception:
        await db.rollback()
        return None


def config_from_row(row: dict | None) -> LlmConfig:
    """Настройки провайдера из строки companies."""
    row = row or {}
    return LlmConfig(
        provider=_norm_provider(row.get("seo_llm_provider")),
        fmt=_norm_format(row.get("seo_llm_format")),
        url=str(row.get("seo_llm_url") or "").strip(),
        api_key=str(row.get("seo_llm_api_key") or "").strip(),
        folder_id=str(row.get("seo_llm_folder_id") or "").strip(),
        auth_header=str(row.get("seo_llm_auth_header") or "").strip(),
        auth_prefix=(row.get("seo_llm_auth_prefix")
                     if row.get("seo_llm_auth_prefix") is not None else None),
        extra_headers=_json_obj(row.get("seo_llm_extra_headers")),
        extra_body=_json_obj(row.get("seo_llm_extra_body")),
        timeout=_to_int(row.get("seo_llm_timeout"), DEFAULT_TIMEOUT),
    )


def config_from_draft(draft: dict | None, saved: dict | None = None) -> LlmConfig:
    """Настройки из черновика формы (кнопка «Проверить» до сохранения).

    Пустые поля черновика добираются из сохранённых настроек компании.
    """
    d = draft or {}
    s = saved or {}
    prefix = d.get("auth_prefix", s.get("seo_llm_auth_prefix"))
    return LlmConfig(
        provider=_norm_provider(d.get("provider") or s.get("seo_llm_provider")),
        fmt=_norm_format(d.get("format") or s.get("seo_llm_format")),
        url=str(d.get("url") or s.get("seo_llm_url") or "").strip(),
        api_key=str(d.get("api_key") or s.get("seo_llm_api_key") or "").strip(),
        folder_id=str(d.get("folder_id") or s.get("seo_llm_folder_id") or "").strip(),
        auth_header=str(d.get("auth_header") or s.get("seo_llm_auth_header") or "").strip(),
        auth_prefix=(prefix if prefix is not None else None),
        extra_headers=_json_obj(d.get("extra_headers")) or _json_obj(s.get("seo_llm_extra_headers")),
        extra_body=_json_obj(d.get("extra_body")) or _json_obj(s.get("seo_llm_extra_body")),
        timeout=_to_int(d.get("timeout"), _to_int(s.get("seo_llm_timeout"), DEFAULT_TIMEOUT)),
    )


def build_headers(cfg: LlmConfig) -> dict:
    """Заголовки запроса под формат. extra_headers мержится последним."""
    head: dict = {"Content-Type": "application/json", "Accept": "application/json"}
    def_header, def_prefix = DEFAULT_AUTH.get(cfg.fmt, DEFAULT_AUTH["openai"])
    header = cfg.auth_header or def_header
    prefix = cfg.auth_prefix if cfg.auth_prefix is not None else def_prefix
    if cfg.api_key:
        key = cfg.api_key
        # префикс без хвостового пробела ("Bearer") → "Bearer ": иначе Authorization: Bearer<ключ>
        if prefix and not prefix.endswith(" ") and not key.startswith(" "):
            prefix = prefix + " "
        head[header] = f"{prefix}{key}"
    if cfg.fmt == "anthropic":
        head.setdefault("anthropic-version", "2023-06-01")
    if cfg.fmt == "gemini":
        head.pop("Authorization", None)
    if cfg.fmt == "yandex" and cfg.folder_id:
        head["OpenAI-Project"] = cfg.folder_id
    for k, v in (cfg.extra_headers or {}).items():
        head[str(k)] = str(v)
    return head


def build_url(cfg: LlmConfig, model: str) -> str:
    """URL эндпоинта: {model} подставляется, иначе путь достраивается по формату."""
    url = (cfg.url or DEFAULT_URL.get(cfg.fmt, "")).strip()
    if "{model}" in url:
        return url.replace("{model}", model or "")
    fmt = cfg.fmt
    if fmt == "openai":
        low = url.lower()
        if "completion" in low:
            # уже полный эндпоинт: /v1/chat/completions, /v1/text/chatcompletion_v2 и т.п.
            pass
        elif low.endswith("/chat"):
            url = url.rstrip("/") + "/completions"
        elif (low.endswith("/v1") or low.endswith("/v2") or low.endswith("/openai")
              or not low.split("://")[-1].strip("/")):
            url = url.rstrip("/") + "/chat/completions"
        # иначе считаем полным эндпоинтом и не трогаем (нативный MiniMax и др.)
    elif fmt == "anthropic":
        if not url.endswith("/messages"):
            url = url.rstrip("/") + "/v1/messages"
    elif fmt == "gemini":
        if "/models/" not in url:
            url = url.rstrip("/") + f"/v1beta/models/{model}:generateContent"
    elif fmt == "ollama":
        if not url.endswith("/chat"):
            url = url.rstrip("/") + "/api/chat"
    return url


def build_payload(cfg: LlmConfig, messages: list[dict], model: str,
                  temperature: float | None, max_tokens: int,
                  reasoning_effort: str | None = None,
                  send_max_tokens: bool = False) -> dict:
    """Тело запроса под формат. extra_body мержится последним (может переопределить поля).

    send_max_tokens — оставлен для совместимости: лимит max_tokens и так шлём всегда.
    """
    sys_text = "\n\n".join(str(m.get("content") or "") for m in messages
                           if m.get("role") == "system")
    chat_msgs = [{"role": m.get("role"), "content": str(m.get("content") or "")}
                 for m in messages if m.get("role") != "system"]
    fmt = cfg.fmt
    # Лимит длины ответа шлём ВСЕГДА (и openrouter, и «другой сервис»): без потолка
    # модель уходит в длинную генерацию и запрос упирается в таймаут (через OpenRouter
    # потолок был — поэтому там отвечало за секунды).
    # Для reasoning-моделей счётчик общий с thinking → свой лимит задаётся в
    # «Доп. параметры (JSON)»: {"max_tokens": 8000} (extra_body мержится последним).
    # У anthropic max_tokens обязателен (требование API) — там оставляем.
    limit = max_tokens or 0
    if fmt == "anthropic":
        payload: dict = {"model": model, "messages": chat_msgs, "max_tokens": limit}
        if sys_text:
            payload["system"] = sys_text
        if temperature is not None:
            payload["temperature"] = temperature
    elif fmt == "gemini":
        contents = []
        for m in chat_msgs:
            contents.append({"role": "model" if m.get("role") == "assistant" else "user",
                             "parts": [{"text": m.get("content") or ""}]})
        payload = {"contents": contents}
        if sys_text:
            payload["systemInstruction"] = {"parts": [{"text": sys_text}]}
        gen: dict = {}
        if limit:
            gen["maxOutputTokens"] = limit
        if temperature is not None:
            gen["temperature"] = temperature
        if gen:
            payload["generationConfig"] = gen
    elif fmt == "ollama":
        payload = {"model": model, "messages": messages, "stream": False}
        opts: dict = {}
        if limit:
            opts["num_predict"] = limit
        if temperature is not None:
            opts["temperature"] = temperature
        if opts:
            payload["options"] = opts
    else:  # openai, yandex
        payload = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if limit:
            payload["max_tokens"] = limit
    if fmt == "yandex" and cfg.folder_id and model and "://" not in model:
        payload["model"] = f"gpt://{cfg.folder_id}/{model}"
    for k, v in (cfg.extra_body or {}).items():
        payload[str(k)] = v
    # Явный reasoning_effort важнее компании extra_body: для извлечения фраз
    # нам нужен low, даже если в настройках сервиса стоит max.
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    return payload


def parse_response(cfg: LlmConfig, body) -> dict:
    """Ответ провайдера → {content, prompt_tokens, completion_tokens, model}."""
    if not isinstance(body, dict):
        return {"error": f"bad response: {str(body)[:200]}"}
    fmt = cfg.fmt
    if fmt == "anthropic":
        blocks = body.get("content") or []
        content = ""
        if isinstance(blocks, list):
            content = "".join(str(b.get("text") or "") for b in blocks if isinstance(b, dict))
        usage = body.get("usage") or {}
        return {"content": content,
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
                "finish_reason": body.get("stop_reason"),
                "model": body.get("model")}
    if fmt == "gemini":
        cands = body.get("candidates") or []
        content = ""
        if cands and isinstance(cands[0], dict):
            parts = (cands[0].get("content") or {}).get("parts") or []
            content = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
        usage = body.get("usageMetadata") or {}
        return {"content": content,
                "prompt_tokens": usage.get("promptTokenCount"),
                "completion_tokens": usage.get("candidatesTokenCount"),
                "finish_reason": cands[0].get("finishReason") if cands and isinstance(cands[0], dict) else None,
                "model": body.get("modelVersion")}
    if fmt == "ollama":
        return {"content": str((body.get("message") or {}).get("content") or ""),
                "prompt_tokens": body.get("prompt_eval_count"),
                "completion_tokens": body.get("eval_count"),
                "cost": float(body.get("prompt_eval_cost") or 0.0) + float(body.get("eval_cost") or 0.0),
                "finish_reason": body.get("done_reason"),
                "model": body.get("model")}
    try:
        choice = body["choices"][0]
        msg = choice["message"]
    except (KeyError, IndexError, TypeError):
        return {"error": f"bad response: {str(body)[:200]}"}
    if not isinstance(choice, dict) or not isinstance(msg, dict):
        return {"error": f"bad response: {str(body)[:200]}"}
    raw_content = msg.get("content")
    if isinstance(raw_content, list):
        # Некоторые OpenAI-совместимые API отдают content массивом частей.
        content = "".join(
            str(p.get("text") or "") if isinstance(p, dict) else str(p)
            for p in raw_content
        )
    else:
        content = str(raw_content or "")
    if "<think>" in content:
        # MiniMax (native API) может прислать рассуждения тегами <think> внутри content —
        # выкидываем их, чтобы остался чистый JSON.
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    usage = body.get("usage") or {}
    cost = usage.get("cost")
    try:
        cost = float(cost) if cost is not None else 0.0
    except (TypeError, ValueError):
        cost = 0.0
    # Часть API (MiniMax) отдаёт бизнес-ошибку ВНУТРИ HTTP 200: content пустой,
    # а код — в base_resp.status_code (1002 rate-limit, 1004 auth, 1008 нет баланса).
    base = body.get("base_resp") or {}
    bcode = base.get("status_code")
    if bcode not in (None, 0, "0"):
        bmsg = str(base.get("status_msg") or "").strip()
        return {"error": (f"provider error {bcode}" + (f": {bmsg}" if bmsg else "")),
                "provider_status": bcode, "provider_message": bmsg,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "cost": cost, "model": body.get("model")}
    return {"content": content,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost": cost,
            "finish_reason": choice.get("finish_reason"),
            # reasoning/refusal не ответ, но помогают понять пустой content
            "reasoning": (msg.get("reasoning_content") or msg.get("reasoning")
                          or msg.get("refusal")),
            "model": body.get("model")}


def headers_dict(headers) -> dict:
    try:
        return {k.lower(): v for k, v in dict(headers.items()).items()}
    except Exception:
        return {}


def post_json(url: str, payload: dict, headers: dict, timeout: int):
    """POST JSON. Возвращает (http_status, http_reason, response_headers, body, info)."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2_000_000).decode("utf-8", "replace")
            ms = int((time.monotonic() - t0) * 1000)
            status, reason, resp_headers = int(resp.status), str(getattr(resp, "reason", "")), headers_dict(resp.headers)
            try:
                return status, reason, resp_headers, json.loads(raw), f"{ms}ms"
            except ValueError:
                # 200 с битым телом — не сетевая ошибка: помечаем отдельно, chat разберёт как bad-response
                return status, reason, resp_headers, {"_invalid_json": raw[:2000]}, f"{ms}ms"
    except urllib.error.HTTPError as exc:
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
        return (int(exc.code), str(getattr(exc, "reason", "")), headers_dict(exc.headers), err_data,
                f"http {exc.code} ({ms}ms, retry-after: {wait or '-'})")
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return 0, "timeout", {}, None, f"таймаут {timeout} с (сервис не ответил)"
        return 0, type(exc).__name__, {}, None, f"{type(exc).__name__} ({ms}ms)"


def err_text(body, info: str) -> str:
    """Тело HTTP-ошибки в читаемом виде для лога/item.error: JSON → компактно, текст → как есть."""
    if isinstance(body, dict):
        try:
            return json.dumps(body, ensure_ascii=False)[:500]
        except Exception:
            pass
    if isinstance(body, str) and body.strip():
        return body[:500]
    return info


def ms_from_info(info: str) -> int:
    m = re.search(r"(\d+)ms", info or "")
    return int(m.group(1)) if m else 0


_SECRET_HINTS = ("authorization", "api-key", "apikey", "x-api-key", "cookie", "token")


def mask_headers(headers: dict | None) -> dict:
    """Замаскировать значения заголовков с секретами (в лог уходят заголовки ответа)."""
    out: dict = {}
    for k, v in (headers or {}).items():
        out[k] = "***" if any(h in str(k).lower() for h in _SECRET_HINTS) else v
    return out


def ai_log(kind: str, model: str | None, messages: list[dict], content: str,
           http: str = "", headers: dict | None = None, note: str = "",
           provider: str = "") -> None:
    """Аналог yii ai.log: полный обмен — в backend/runtime/ai.log (папка создаётся
    сама, ротация при >10МБ), краткая строка — в stdout (journalctl -u wbcms-py).
    Полный обмен последнего вызова задачи — также в ai_job_item.result."""
    if not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False)
        except Exception:
            content = str(content)
    line = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "ai_log": kind, "model": model,
            "http": http, "try": note, "provider": provider or "openrouter",
            "headers": mask_headers(headers),
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
                          "provider": line["provider"],
                          "req_chars": req_chars,
                          "resp_chars": len(content or ""),
                          "resp_head": (content or "")[:300],
                          "ts": line["ts"]},
                         ensure_ascii=False), flush=True)
    except Exception:
        pass


async def chat(cfg: LlmConfig, messages: list[dict], temperature: float | None = 0.4,
               max_tokens: int = 1500, model: str | None = None, note: str = "",
               timeout: int | None = None, retry_429: bool = True,
               probe: bool = False, reasoning_effort: str | None = None,
               send_max_tokens: bool = False) -> dict:
    """Запрос к «другому сервису». Контракт как у openrouter_service.chat():
    {content, prompt_tokens, completion_tokens, model, http} либо {error}.

    timeout — переопределение таймаута (сек); retry_429 — ретрай после 429
    (для ручной пробы «Проверить» ретрай не нужен — ждать 20 с незачем);
    reasoning_effort — глубина thinking для reasoning-моделей (low/medium/...);
    send_max_tokens — явно отправить max_tokens даже «другому сервису» (фразы);
    probe — ручная проба: если reasoning_effort не задан, просим low.
    Если провайдер параметр не знает — убираем и повторяем без него."""
    model = (model or "").strip() or "default"
    url = build_url(cfg, model)
    headers = build_headers(cfg)
    if not reasoning_effort and probe:
        reasoning_effort = "low"
    payload = build_payload(cfg, messages, model, temperature, max_tokens, reasoning_effort,
                            send_max_tokens)
    timeout = int(timeout or cfg.timeout or DEFAULT_TIMEOUT)
    last_http, last_headers, last_info = "", {}, ""
    for attempt in (1, 2, 3):
        status, reason, resp_headers, body, info = await asyncio.to_thread(
            post_json, url, payload, headers, timeout)
        http = f"{status} {reason}".strip()
        last_http, last_headers, last_info = http, resp_headers, info
        if status == 200 and isinstance(body, dict):
            parsed = parse_response(cfg, body)
            if parsed.get("error"):
                ai_log("bad-response", model, messages, str(body)[:500], http, resp_headers, note,
                       provider=cfg.provider)
                return {"error": parsed["error"], "http": http}
            content = (parsed.get("content") or "").strip()
            from_reasoning = False
            if not content:
                why = parsed.get("reasoning")
                if cfg.fmt in ("openai", "yandex"):
                    chs = body.get("choices") or []
                    if chs and isinstance(chs[0], dict):
                        msg0 = chs[0].get("message") or {}
                        why = (msg0.get("refusal") or msg0.get("reasoning_content")
                               or msg0.get("reasoning"))
                why = why or parsed.get("reasoning") or str(body)[:2000]
                # Некоторые reasoning-провайдеры кладут финальный JSON в
                # reasoning_content, оставляя content пустым.
                if isinstance(why, str) and why.strip().startswith(("{", "[")):
                    content = why.strip()
                    from_reasoning = True
                else:
                    ai_log("empty", model, messages, str(why), http, resp_headers, note,
                           provider=cfg.provider)
                    return {"content": "", "prompt_tokens": parsed.get("prompt_tokens"),
                            "completion_tokens": parsed.get("completion_tokens"),
                            "cost": float(parsed.get("cost") or 0.0),
                            "provider": cfg.provider,
                            "error": f"empty response: {str(why)[:300]}",
                            "empty_reason": str(why or "")[:8000],
                            "finish_reason": parsed.get("finish_reason"),
                            "model": parsed.get("model") or model, "http": http}
            out = {"content": content,
                   "prompt_tokens": parsed.get("prompt_tokens"),
                   "completion_tokens": parsed.get("completion_tokens"),
                   "cost": float(parsed.get("cost") or 0.0),
                   "model": parsed.get("model") or model,
                   "provider": cfg.provider,
                   "finish_reason": parsed.get("finish_reason"),
                   "reasoning": parsed.get("reasoning"),
                   "from_reasoning": from_reasoning,
                   "http": http, "ms": ms_from_info(info)}
            ai_log("ok", model, messages, out["content"], http, resp_headers, note, provider=cfg.provider)
            return out
        if status == 400 and "reasoning_effort" in payload \
                and "reasoning_effort" in err_text(body, info):
            # провайдер не знает параметр — убираем и повторяем сразу
            payload.pop("reasoning_effort", None)
            continue
        if status == 429 and attempt == 1 and retry_429:
            ai_log("429-retry", model, messages, err_text(body, info), http, resp_headers, note,
                   provider=cfg.provider)
            await asyncio.sleep(RETRY_429_WAIT)
            continue
        ai_log("error", model, messages, err_text(body, info), http, resp_headers, note,
               provider=cfg.provider)
        return {"error": err_text(body, info), "http": http, "ms": ms_from_info(info),
                "provider": cfg.provider, "model": model}
    ai_log("error", model, messages, f"retry exhausted ({last_info})", last_http, last_headers, note,
           provider=cfg.provider)
    return {"error": f"retry exhausted ({last_info})", "http": last_http,
            "provider": cfg.provider, "model": model}


def openrouter_key_from_row(row: dict | None) -> str:
    """Ключ OpenRouter: companies.seo_openrouter_key → env OPENROUTER_API_KEY."""
    key = os.getenv("OPENROUTER_API_KEY", "")
    if row and row.get("seo_openrouter_key"):
        key = row["seo_openrouter_key"]
    return key
