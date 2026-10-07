"""Единый источник интервалов сборки: backend/config/fbs_assembly_tariffs.json.

Версионность (новость WB 06.10.2026: с 07.10 штраф другой): файл хранит
versions[] с valid_from; деньги считаются по версии на дату заказа, отображение
(границы/легенды) — по последней версии. Виды бакетов: discount_pp (значение
со знаком, напр. −5), base, penalty_pct_per_h (%/ч сверх overdue_from_h),
penalty_flat_pct (фикс % при попадании в зону).
"""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "config",
                     "fbs_assembly_tariffs.json")

with open(_PATH, encoding="utf-8") as _fh:
    TARIFFS = json.load(_fh)


def _grid_for(date_str: str | None = None) -> dict:
    versions = TARIFFS.get("versions") or []
    if not versions:
        raise ValueError("versions пусто")
    if not date_str:
        return versions[-1]
    best = versions[0]
    for v in versions:
        if str(v.get("valid_from", "")) <= str(date_str):
            best = v
        else:
            break
    return best


def thresholds() -> dict:
    return TARIFFS.get("thresholds", {})


def versions() -> list:
    return TARIFFS.get("versions", [])


def bounds(date_str: str | None = None) -> list:
    """Нижние границы бакетов версии: [0, 13, 42, 48, ...]."""
    lo = [0]
    for b in _grid_for(date_str)["buckets"]:
        upto = b["upto_h"]
        if upto is not None and (not lo or upto > lo[-1]):
            lo.append(upto)
    return lo


def labels(date_str: str | None = None) -> list:
    lo = bounds(date_str)
    out = []
    for i in range(len(lo)):
        if i < len(lo) - 1:
            out.append(f"{lo[i]}–{lo[i + 1]} ч")
        else:
            out.append(f"от {lo[i]} ч")
    return out


def bucket_index(h: float, date_str: str | None = None) -> int:
    lo = bounds(date_str)
    for i in range(len(lo)):
        if i == len(lo) - 1 or h < lo[i + 1]:
            return i
    return len(lo) - 1


def discount_pp(h: float, date_str: str | None = None) -> float:
    """Модуль скидки по версии на дату (формула денег: discount/100*price)."""
    for b in _grid_for(date_str)["buckets"]:
        upto = b["upto_h"]
        if b["kind"] == "discount_pp" and (upto is None or h < upto):
            return abs(float(b["value"]))
    return 0.0


def penalty_pct(h: float, date_str: str | None = None) -> float:
    """Итоговый % штрафа по версии на дату: ставка тира x часы сверх
    overdue_from_h, либо фикс (penalty_flat_pct)."""
    overdue = float(thresholds().get("overdue_from_h", 48))
    if h < overdue:
        return 0.0
    tier = None
    for b in _grid_for(date_str)["buckets"]:
        upto = b["upto_h"]
        tier = b
        if upto is None or h < upto:
            break
    if tier is None:
        return 0.0
    if tier["kind"] == "penalty_pct_per_h":
        return abs(float(tier["value"])) * (h - overdue)
    if tier["kind"] == "penalty_flat_pct":
        return abs(float(tier["value"]))
    return 0.0


def reload() -> dict:
    """Перечитать JSON с диска (после правки из админки). In-place."""
    with open(_PATH, encoding="utf-8") as fh:
        fresh = json.load(fh)
    TARIFFS.clear()
    TARIFFS.update(fresh)
    return TARIFFS


_BUCKET_KINDS = ("discount_pp", "base", "penalty_pct_per_h", "penalty_flat_pct")


def validate(payload: dict) -> str | None:
    """None = ок, иначе текст ошибки."""
    if not isinstance(payload, dict):
        return "корень — объект"
    th = payload.get("thresholds")
    if not isinstance(th, dict):
        return "thresholds: объект"
    for key in ("base_sla_h", "warn_h", "pre_cancel_h", "auto_cancel_h",
                "overdue_from_h", "quota_overdue_h"):
        v = th.get(key)
        if not isinstance(v, (int, float)) or v < 0:
            return f"thresholds.{key}: неотрицательное число"
    if payload.get("base_field") != "kgvp_marketplace":
        return "base_field: пока только kgvp_marketplace"
    versions = payload.get("versions")
    if not isinstance(versions, list) or not versions:
        return "versions: непустой список"
    prev_from = ""
    for vi, ver in enumerate(versions):
        if not isinstance(ver, dict):
            return f"versions[{vi}]: объект"
        vf = ver.get("valid_from", "")
        if not isinstance(vf, str) or not vf or vf <= prev_from and vi > 0:
            if vi > 0 and vf <= prev_from:
                return f"versions[{vi}].valid_from: должен расти"
            if not vf:
                return f"versions[{vi}].valid_from: дата YYYY-MM-DD"
        prev_from = vf
        buckets = ver.get("buckets")
        if not isinstance(buckets, list) or not buckets:
            return f"versions[{vi}].buckets: непустой список"
        prev = None
        for i, b in enumerate(buckets):
            if not isinstance(b, dict):
                return f"buckets[{i}]: объект"
            if b.get("kind") not in _BUCKET_KINDS:
                return f"buckets[{i}].kind: {'|'.join(_BUCKET_KINDS)}"
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
    """Валидация + атомарная запись + hot-reload."""
    import os as _os
    err = validate(payload)
    if err:
        raise ValueError(err)
    data = {"_comment": payload.get("_comment", TARIFFS.get("_comment", "")),
            "base_field": payload["base_field"],
            "thresholds": dict(payload["thresholds"]),
            "versions": [
                {"valid_from": v.get("valid_from", ""),
                 "comment": v.get("comment", ""),
                 "buckets": [{"upto_h": b["upto_h"], "kind": b["kind"],
                              "value": b["value"]} for b in v["buckets"]]}
                for v in payload["versions"]]}
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    _os.replace(tmp, _PATH)
    return reload()
