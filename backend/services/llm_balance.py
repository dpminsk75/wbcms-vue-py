"""Пауза фоновых ИИ-задач, когда у провайдера кончились токены/баланс.

Правило одно на все фоновые разборы (отзывы — feedback_review_service,
фразы — phrase_miner_service): провайдер ответил «нет токенов»
(insufficient_balance / HTTP 402 / MiniMax base_resp.status_code=1008)
→ компания встаёт на паузу на 3 часа, её дела не трогаем.

Почему пауза на компанию, а не на весь цикл: у каждой компании свой
провайдер/ключ (companies.seo_llm_*), чужой исчерпанный ключ не должен
останавливать разбор остальных.

Пауза живёт в памяти процесса (uvicorn --workers 1): после рестарта
wbcms-py теряется, но цикл поставит её заново на первом же таком ответе.

Детектор и реестр — здесь, чтобы оба разбора смотрели на один список
маркеров и в один реестр пауз.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

# Маркеры в тексте ошибки провайдера (тело ответа — JSON или строка).
MARKERS = (
    "insufficient_balance",
    "insufficient balance",
    "insufficient credits",
    "insufficient quota",
)

# Коды провайдера: 1008 — MiniMax «нет баланса» (base_resp.status_code,
# приходит внутри HTTP 200), 402 — HTTP «Payment Required».
PROVIDER_CODES = (1008, 402)

DEFAULT_PAUSE_H = 3.0
ENV_HOURS = "LLM_BALANCE_PAUSE_H"

# company_id → {until: unix, reason: str, since: unix}
_pause: dict[int, dict] = {}


def pause_seconds() -> float:
    """Длительность паузы в секундах (env LLM_BALANCE_PAUSE_H, по умолчанию 3 ч)."""
    try:
        h = float(os.getenv(ENV_HOURS, "") or DEFAULT_PAUSE_H)
    except (TypeError, ValueError):
        h = DEFAULT_PAUSE_H
    return max(0.0, h) * 3600.0


def reason_of(res: dict | None) -> str | None:
    """Метка «нет токенов» по ответу провайдера. None — обычная ошибка.

    res — как возвращает openrouter_service.chat(): {error, http,
    provider_status, provider_message, ...}.
    """
    if not isinstance(res, dict):
        return None
    code = res.get("provider_status")
    try:
        code = int(code) if code not in (None, "") else 0
    except (TypeError, ValueError):
        code = 0
    if code in PROVIDER_CODES:
        return f"provider {code}"
    low = str(res.get("error") or "").lower()
    for m in MARKERS:
        if m in low:
            return m
    http = str(res.get("http") or "").strip()
    if http.startswith("402"):
        return "http 402"
    return None


def pause(company_id: int | None, reason: str = "") -> dict:
    """Поставить паузу компании (продлить, если уже стоит). Возвращает состояние."""
    if company_id is None:
        return {}
    cid = int(company_id)
    now = time.time()
    until = now + pause_seconds()
    _pause[cid] = {"until": until, "reason": str(reason or "")[:100], "since": now}
    return state(cid)


def pause_until(company_id: int | None, until: float | str, reason: str = "") -> dict:
    """Пауза до конкретного момента (unix ts или ISO-строка со смещением).

    Для окна лимита провайдера: ждём не «3 часа с момента», а до сброса окна.
    """
    if company_id is None:
        return {}
    ts = _to_ts(until)
    if ts <= 0:
        return {}
    cid = int(company_id)
    now = time.time()
    _pause[cid] = {"until": ts, "reason": str(reason or "")[:100], "since": now}
    return state(cid)


def _to_ts(v) -> float:
    """Момент времени → unix ts. Принимает ts и ISO со смещением."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v or "").strip()
    if not s:
        return 0.0
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return 0.0


def is_paused(company_id: int | None) -> bool:
    """Стоит ли пауза у компании (протухшая — снимается)."""
    if company_id is None:
        return False
    cid = int(company_id)
    item = _pause.get(cid)
    if not item:
        return False
    if item["until"] <= time.time():
        _pause.pop(cid, None)
        return False
    return True


def paused_companies() -> list[int]:
    """Компании в паузе (протухшие убираем)."""
    now = time.time()
    for cid in [c for c, v in _pause.items() if v["until"] <= now]:
        _pause.pop(cid, None)
    return sorted(_pause)


def clear(company_id: int | None = None) -> None:
    """Снять паузу: у компании — или у всех (company_id=None)."""
    if company_id is None:
        _pause.clear()
        return
    _pause.pop(int(company_id), None)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def state(company_id: int | None) -> dict:
    """Состояние паузы компании: {paused, until, left_sec, reason}."""
    empty = {"paused": False, "until": None, "left_sec": 0, "reason": ""}
    if company_id is None:
        return empty
    cid = int(company_id)
    item = _pause.get(cid)
    if not item:
        return empty
    left = int(max(0, item["until"] - time.time()))
    if left <= 0:
        _pause.pop(cid, None)
        return empty
    return {"paused": True, "until": _iso(item["until"]),
            "left_sec": left, "reason": item["reason"]}


def scope_state(company_id: int | None) -> dict:
    """Состояние для экрана: по компании или по всем (company_id=None → список).

    {paused, until, left_sec, reason, companies:[{company_id, until, left_sec, reason}]}
    """
    if company_id is not None:
        s = state(company_id)
        companies = ([{"company_id": int(company_id), **s}] if s["paused"] else [])
        return {**s, "companies": companies}
    now = time.time()
    companies = []
    for cid in paused_companies():
        item = _pause[cid]
        companies.append({"company_id": cid, "until": _iso(item["until"]),
                          "left_sec": int(max(0, item["until"] - now)),
                          "reason": item["reason"]})
    return {
        "paused": bool(companies),
        "until": companies[0]["until"] if companies else None,
        "left_sec": companies[0]["left_sec"] if companies else 0,
        "reason": companies[0]["reason"] if companies else "",
        "companies": companies,
    }
