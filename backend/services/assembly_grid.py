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
