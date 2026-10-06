"""Единый источник интервалов сборки: backend/config/fbs_assembly_tariffs.json.

Границы бакетов, подписи, скидки/штрафы — только отсюда. Все сервисы
(handling, dynamics, commission, assembly-economy) обязаны использовать
эти хелперы, хардкод [0, 13, 42, 48, 54, 60] в коде запрещён.
"""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "config",
                     "fbs_assembly_tariffs.json")

with open(_PATH, encoding="utf-8") as _fh:
    TARIFFS = json.load(_fh)


def reload() -> dict:
    """Перечитать JSON с диска (после правки из админки). In-place, чтобы
    подхватилось без рестарта: все сервисы держат ссылку на этот dict."""
    with open(_PATH, encoding="utf-8") as fh:
        fresh = json.load(fh)
    TARIFFS.clear()
    TARIFFS.update(fresh)
    return TARIFFS


def validate(payload: dict) -> str | None:
    """Проверка структуры перед записью. None = ок, иначе текст ошибки."""
    if not isinstance(payload, dict):
        return "корень — объект"
    for key in ("base_sla_h", "warn_h", "pre_cancel_h", "auto_cancel_h",
                "overdue_from_h", "quota_overdue_h"):
        v = payload.get(key)
        if not isinstance(v, (int, float)) or v < 0:
            return f"{key}: неотрицательное число"
    if payload.get("base_field") != "kgvp_marketplace":
        return "base_field: пока только kgvp_marketplace"
    buckets = payload.get("buckets")
    if not isinstance(buckets, list) or not buckets:
        return "buckets: непустой список"
    prev = None
    for i, b in enumerate(buckets):
        if not isinstance(b, dict):
            return f"buckets[{i}]: объект"
        if b.get("kind") not in ("discount_pp", "base", "penalty_pct_per_h"):
            return f"buckets[{i}].kind: discount_pp|base|penalty_pct_per_h"
        if not isinstance(b.get("value"), (int, float)):
            return f"buckets[{i}].value: число"
        upto = b.get("upto_h")
        last = i == len(buckets) - 1
        if last:
            if upto is not None:
                return "последний бакет: upto_h = null"
        else:
            if not isinstance(upto, (int, float)) or upto <= 0:
                return f"buckets[{i}].upto_h: положительное число"
            if prev is not None and upto <= prev:
                return "upto_h должны расти"
            prev = upto
    return None


def save(payload: dict) -> dict:
    """Валидация + атомарная запись + hot-reload. Возвращает актуальный dict."""
    import os as _os
    err = validate(payload)
    if err:
        raise ValueError(err)
    data = {"_comment": TARIFFS.get("_comment", ""),
            "base_sla_h": payload["base_sla_h"],
            "warn_h": payload["warn_h"],
            "pre_cancel_h": payload["pre_cancel_h"],
            "auto_cancel_h": payload["auto_cancel_h"],
            "quota_overdue_h": payload["quota_overdue_h"],
            "overdue_from_h": payload["overdue_from_h"],
            "base_field": payload["base_field"],
            "buckets": [{"upto_h": b["upto_h"], "kind": b["kind"],
                         "value": b["value"]} for b in payload["buckets"]]}
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    _os.replace(tmp, _PATH)
    return reload()


def bounds() -> list:
    """Нижние границы бакетов + сверхмаксимум: [0, 13, 42, 48, 54, 60]."""
    lo = []
    for b in TARIFFS["buckets"]:
        upto = b["upto_h"]
        if not lo:
            lo.append(0)
        if upto is not None:
            lo.append(upto)
    return lo


def labels() -> list:
    """Подписи бакетов 1в1 как в UI: ['0–13 ч', ..., 'от 60 ч']."""
    lo = bounds()
    out = []
    for i in range(len(lo)):
        if i < len(lo) - 1:
            out.append(f"{lo[i]}–{lo[i + 1]} ч")
        else:
            out.append(f"от {lo[i]} ч")
    return out


def bucket_index(h: float) -> int:
    lo = bounds()
    for i in range(len(lo)):
        if i == len(lo) - 1 or h < lo[i + 1]:
            return i
    return len(lo) - 1


def discount_pp(h: float) -> float:
    """Скидка с комиссии за быструю сдачу по сетке (kind=discount_pp).

    В JSON значения со знаком (−5), возвращаем МОДУЛЬ: формула денег везде
    `discount_pp(h) / 100 * price` со знаком плюс (баг 2026-10-05: уходило в минус).
    """
    for b in TARIFFS["buckets"]:
        upto = b["upto_h"]
        if b["kind"] == "discount_pp" and (upto is None or h < upto):
            return abs(float(b["value"]))
    return 0.0


def penalty_rate(h: float) -> float:
    """Ставка штрафа (%/ч сверх overdue_from_h) по сетке."""
    rate = 0.0
    for b in TARIFFS["buckets"]:
        if b["kind"] == "penalty_pct_per_h":
            rate = float(b["value"])
            upto = b["upto_h"]
            if upto is None or h < upto:
                break
    return rate if h >= TARIFFS["overdue_from_h"] else 0.0
