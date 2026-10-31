"""Остаток лимита ИИ у провайдера (MiniMax Token Plan) — до батча, а не после 402.

Зачем: у MiniMax Token Plan есть 5-часовое и недельное окна. Когда окно исчерпано,
API отвечает 402 insufficient_balance — и фон успевает насыпать сотни ошибок.
Дешевле спросить заранее: GET /v1/token_plan/remains → сколько осталось и когда
сброс — и встать на паузу до сброса + 30 мин (llm_balance.pause_until).

Эндпоинт (документация MiniMax):
    GET https://api.minimax.io/v1/token_plan/remains
    Authorization: Bearer <API Key>
Ответ: {"base_resp":{"status_code":0,...}, "model_remains":[{...}]}
    current_interval_remaining_percent — остаток 5-часового окна, % (0..100)
    current_interval_status           — 1 = окно активно
    remains_time / end_time            — до сброса (МИЛЛИСЕКУНДЫ)
    current_weekly_remaining_percent   — остаток недельного окна, %
    weekly_end_time                    — конец недельного окна (МС)

ВАЖНО: время в ответе — миллисекунды (end_time = 1793390400000, а не ...400).

Правила:
- только MiniMax (хост companies.seo_llm_url содержит minimax); остальным
  провайдерам фича не касается (applicable=False);
- любая ошибка (404, 401, таймаут, битый JSON, не-MiniMax) — fail-open: разбор
  продолжается как раньше, в лог — одна запись;
- кэш в памяти процесса на CACHE_TTL (5 минут) — не дёргаем API каждый тик;
- остаток = current_interval_remaining_percent; count-поля в ответе нулевые
  (total=0), поэтому проценты — единственный надёжный источник.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from backend.database import get_session

# Порог: остаток 5-часового окна ниже — встаём на паузу до сброса.
MIN_PERCENT = 10.0
# Запас после сброса окна (окно «rolling»: первые минуты могут быть не полными).
GRACE_MIN = 30
# Кэш проверки (секунды) — не чаще раза в 5 минут на компанию.
CACHE_TTL = 300
# Таймаут запроса к провайдеру (секунды).
HTTP_TIMEOUT = 15

EMPTY = {"applicable": False, "ok": False, "error": ""}

# company_id → {"at": ts, "state": {...}}
_cache: dict[int, dict] = {}


def _num(v) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v) -> int:
    n = _num(v)
    return int(n) if n is not None else 0


def quota_url(base_url: str) -> str:
    """Из URL чата провайдера — URL квоты Token Plan. "" если это не MiniMax."""
    u = str(base_url or "").strip()
    if "minimax" not in u.lower():
        return ""
    root = re.split(r"/v1\b", u, maxsplit=1)[0].rstrip("/")
    if not root:
        return ""
    return root + "/v1/token_plan/remains"


def _pick_model(items: list, model: str) -> dict | None:
    """Запись нашей модели → иначе «general» (текстовый пул, где живёт M3)."""
    if not isinstance(items, list) or not items:
        return None
    name = str(model or "").strip().lower()
    if name:
        for it in items:
            if isinstance(it, dict) and str(it.get("model_name") or "").strip().lower() == name:
                return it
    for it in items:
        if isinstance(it, dict) and str(it.get("model_name") or "").strip().lower() == "general":
            return it
    return None


def _reset_iso(m: dict) -> str:
    """Момент сброса окна — ISO с локальным смещением (для JS Date())."""
    ms = _int(m.get("remains_time"))
    if ms > 0:
        dt = datetime.now() + timedelta(milliseconds=ms)
    else:
        end = _int(m.get("end_time"))
        if end <= 0:
            return ""
        dt = datetime.fromtimestamp(end / 1000)
    return dt.astimezone().isoformat(timespec="seconds")


def _weekly_iso(m: dict) -> str:
    end = _int(m.get("weekly_end_time"))
    if end <= 0:
        return ""
    return datetime.fromtimestamp(end / 1000).astimezone().isoformat(timespec="seconds")


def _left_text(ms: int) -> str:
    """«3 ч 54 мин» — как в виджете."""
    if ms <= 0:
        return ""
    hours = ms // 3_600_000
    minutes = (ms % 3_600_000) // 60_000
    return f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"


def parse_remains(payload: dict, model: str = "") -> dict:
    """Ответ /token_plan/remains → состояние окна (чистая функция)."""
    if not isinstance(payload, dict):
        return {"ok": False, "error": "ответ не JSON-объект"}
    base = payload.get("base_resp") or {}
    code = base.get("status_code")
    if code not in (None, 0, "0"):
        return {"ok": False, "error": f"status_code={code} {base.get('status_msg') or ''}".strip()}
    items = payload.get("model_remains")
    if not isinstance(items, list) or not items:
        return {"ok": False, "error": "нет model_remains"}
    m = _pick_model(items, model)
    if not m:
        return {"ok": False, "error": "нет записи для нашей модели"}
    ms = _int(m.get("remains_time"))
    percent = _num(m.get("current_interval_remaining_percent"))
    status = _int(m.get("current_interval_status"))
    reset_at = _reset_iso(m)
    out = {
        "ok": True,
        "error": "",
        "model": str(m.get("model_name") or ""),
        "percent": percent,
        "status": status,
        "active": (status == 1) if status else None,
        "reset_at": reset_at,
        "reset_left": _left_text(ms),
        "reset_left_sec": int(ms / 1000) if ms > 0 else 0,
        "weekly_percent": _num(m.get("current_weekly_remaining_percent")),
        "weekly_reset_at": _weekly_iso(m),
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    # Пауза — до сброса окна + запас
    if reset_at:
        try:
            ts = datetime.fromisoformat(reset_at).timestamp()
            out["pause_until"] = datetime.fromtimestamp(
                ts + GRACE_MIN * 60).astimezone().isoformat(timespec="seconds")
        except ValueError:
            out["pause_until"] = ""
    else:
        out["pause_until"] = ""
    return out


def is_low(state: dict) -> bool:
    """Мало ли лимита: остаток ниже порога ИЛИ окно не активно."""
    if not isinstance(state, dict) or not state.get("ok"):
        return False
    if state.get("active") is False:
        return True
    p = state.get("percent")
    return p is not None and p < MIN_PERCENT


def _http_get(url: str, api_key: str) -> tuple[int, str, object]:
    """GET → (status, body-текст, json|None). Исключения не роняют вызывающего."""
    req = urllib.request.Request(url, method="GET", headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read(500_000).decode("utf-8", "replace")
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read(2000).decode("utf-8", "replace")
        except Exception:
            raw = ""
        status = int(exc.code)
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}", None
    try:
        return status, raw, json.loads(raw) if raw.strip() else None
    except ValueError:
        return status, raw, None


def cached(company_id: int | None) -> dict:
    """Последнее известное состояние (без сетевого запроса)."""
    if company_id is None:
        return dict(EMPTY)
    item = _cache.get(int(company_id))
    return dict(item["state"]) if item else dict(EMPTY)


async def check_fast(db, company_id: int | None, timeout: float = 5.0) -> dict:
    """Проверка с потолком по времени — страница не должна висеть на сети провайдера.

    Не успел — отдаём последнее известное состояние из кэша.
    """
    try:
        return await asyncio.wait_for(check(db, company_id), timeout=timeout)
    except Exception:
        return cached(company_id)


def _log_once(msg: str) -> None:
    try:
        print(json.dumps({"llm_quota": msg}, ensure_ascii=False), flush=True)
    except Exception:
        pass


async def check(db, company_id: int | None, force: bool = False) -> dict:
    """Остаток лимита провайдера для компании (с кэшем на CACHE_TTL).

    Никогда не бросает: любая проблема → applicable/ok=False (fail-open).
    """
    if company_id is None:
        return dict(EMPTY)
    cid = int(company_id)
    now = time.time()
    item = _cache.get(cid)
    if item and not force and (now - item["at"]) < CACHE_TTL:
        return dict(item["state"])

    state = dict(EMPTY)
    try:
        from backend.services import llm_provider
        # Настройки читаем на отдельной короткой сессии: иначе SELECT company_row
        # открывает txn на сессии вызывающего, и она остаётся открытой через
        # сеть ниже (to_thread, до HTTP_TIMEOUT с) — read view держит InnoDB
        # purge у всего сервера.
        async with get_session() as sdb:
            row = await llm_provider.company_row(sdb, cid)
        cfg = llm_provider.config_from_row(row)
        if cfg.provider != "custom" or not cfg.api_key:
            state = dict(EMPTY)
        else:
            url = quota_url(cfg.url)
            if not url:
                state = dict(EMPTY)
            else:
                model = str((row or {}).get("seo_llm_summary_model")
                            or (row or {}).get("seo_llm_model") or "")
                status, raw, body = await asyncio.to_thread(
                    _http_get, url, cfg.api_key)
                if body is None:
                    state = {"applicable": True, "ok": False,
                             "error": f"HTTP {status}: {str(raw)[:200]}"}
                else:
                    state = parse_remains(body, model)
                    state["applicable"] = True
                    if not state.get("ok"):
                        _log_once(f"company {cid}: quota error: {state.get('error')}")
    except Exception as exc:
        state = {"applicable": True, "ok": False,
                 "error": f"{type(exc).__name__}: {exc}"[:200]}

    _cache[cid] = {"at": now, "state": dict(state)}
    return dict(state)
