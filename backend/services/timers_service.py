"""Оперативное управление systemd-таймерами воркеров из админки.

Только stdlib. Все мутации — через `sudo -n` (без пароля, fail-fast):
sudoers-вайтлист — deploy/wbcms-timers.sudoers. Имена юнитов строго
из ALLOWED (regex + явный список), OnCalendar валидируется
`systemd-analyze calendar` до записи.
"""

import asyncio
import re

ALLOWED: dict[str, dict] = {
    "wbcms-commission-tariffs": {
        "title": "Комиссии WB (тарифы + предметы)",
        "default": "04:00",
        "group": "night",
    },
    "wbcms-finance-balance": {
        "title": "Баланс ЛК WB",
        "default": "00,03,06,09,12,15,18,21:05",
        "group": "day",
    },
    "wbcms-funnel-sync": {
        "title": "Воронка продаж WB (sync)",
        "default": "03:00",
        "group": "night",
    },
    "wbcms-funnel-missing": {
        "title": "Воронка продаж WB (догрузка)",
        "default": "03:20",
        "group": "night",
    },
    "wbcms-adv-queries": {
        "title": "Поисковые запросы рекламы",
        "default": "03:45",
        "group": "night",
    },
    "wbcms-adv-index": {
        "title": "Реклама WB (index: count/details/stats)",
        "default": "00,04,08,12,16,20:10",
        "group": "day",
    },
    "wbcms-news": {
        "title": "Новости WB (hourly :05)",
        "default": "*:05",
    },
    "wbcms-fbs-all": {
        "title": "FBS-связка (заказы+статусы+вычет+поставки)",
        "default": "*:02/5",
        "group": "day",
    },
    "wbcms-orders-sync": {
        "title": "Заказы WB (fetch+feed)",
        "default": "*:00/5",
        "group": "day",
    },
    "wbcms-sales-fetch": {
        "title": "Продажи WB (supplier/sales)",
        "default": "*:15",
        "group": "day",
    },
    "wbcms-cards-sync": {
        "title": "Карточки WB (связка list+nds+sizes+subjects)",
        "default": "04:10",
        "group": "night",
    },
    "wbcms-paid-storage": {
        "title": "Платное хранение (async)",
        "default": "05:00",
        "group": "night",
    },
    "wbcms-acceptance": {
        "title": "Приёмка WB (async)",
        "default": "05:15",
        "group": "night",
    },
    "wbcms-stocks-all": {
        "title": "Остатки WB (блок: stocks+offices+products)",
        "default": "04:30",
        "group": "night",
    },
    "wbcms-wb-tokens": {
        "title": "WB-токены health-check (daily)",
        "default": "daily",
        "group": "night",
    },
    "wbcms-py-healthcheck": {
        "title": "Liveness бэка (каждые 5 мин)",
        "default": "OnBootSec=1min OnUnitActiveSec=5min",
        "group": "day",
    },
}

_NAME_RE = re.compile(r"^wbcms-[a-z0-9-]+$")
_TIMEOUT = 20


class TimersError(RuntimeError):
    pass


def check_name(name: str) -> str:
    if not _NAME_RE.match(name or "") or name not in ALLOWED:
        raise TimersError(f"unknown timer: {name}")
    return name


async def _run(*args: str, timeout: int = _TIMEOUT, stdin: bytes | None = None) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise TimersError(f"systemd недоступен на этой машине: {e.filename}") from e
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin), timeout)
    except asyncio.TimeoutError as e:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise TimersError(f"timeout: {' '.join(args)}") from e
    return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


async def _show(unit: str) -> dict:
    rc, out, _ = await _run(
        "systemctl", "show", unit,
        "-p", "LoadState,ActiveState,SubState,UnitFileState,"
              "NextElapseUSecRealtime,NextElapseUSecMonotonic,"
              "LastTriggerUSecRealtime,LastTriggerUSecMonotonic,"
              "Result,ExecMainStatus,ExecMainStartTimestamp",
        "--no-pager",
    )
    props: dict = {}
    if rc == 0:
        for line in out.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                props[k] = v or None
    return props


async def _on_calendars(timer: str) -> list[str]:
    rc, out, _ = await _run("systemctl", "cat", timer, "--no-pager")
    found: list[str] = []
    if rc == 0:
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("OnCalendar=") and s != "OnCalendar=":
                found.append(s[len("OnCalendar="):])
            elif s.startswith("OnUnitActiveSec=") or s.startswith("OnBootSec="):
                found.append(s)
    return found


def _ts(*vals: str | None) -> str | None:
    """Первый непустой systemd-таймстамп (0/n/a = не было)."""
    for v in vals:
        if v and v not in ("0", "n/a", "[not set]"):
            return v
    return None


async def status_one(name: str) -> dict:
    check_name(name)
    timer, service = f"{name}.timer", f"{name}.service"
    tp = await _show(timer)
    sp = await _show(service)
    cals = await _on_calendars(timer)
    rc, out, _ = await _run("systemctl", "is-enabled", timer)
    enabled = out.strip() == "enabled"
    return {
        "id": name,
        "timer": timer,
        "service": service,
        "title": ALLOWED[name]["title"],
        "default": ALLOWED[name]["default"],
        "group": ALLOWED[name].get("group", "day"),
        "enabled": enabled,
        "load_state": tp.get("LoadState"),
        "unit_file_state": tp.get("UnitFileState"),
        "active_state": tp.get("ActiveState"),
        "sub_state": tp.get("SubState"),
        "next": _ts(tp.get("NextElapseUSecRealtime"), tp.get("NextElapseUSecMonotonic")),
        "last_trigger": _ts(tp.get("LastTriggerUSecRealtime"), tp.get("LastTriggerUSecMonotonic")),
        "on_calendar": cals,
        "svc_state": sp.get("ActiveState"),
        "svc_sub": sp.get("SubState"),
        "svc_result": sp.get("Result"),
        "svc_exec_status": sp.get("ExecMainStatus"),
        "svc_last_start": sp.get("ExecMainStartTimestamp"),
    }


async def status_all() -> list[dict]:
    return [await status_one(n) for n in ALLOWED]


async def _sudo(*args: str) -> str:
    rc, _, err = await _run("sudo", "-n", *args)
    if rc != 0:
        raise TimersError(
            "sudo отказал (нет NOPASSWD-правил?): "
            + (err.strip().splitlines()[-1] if err.strip() else f"rc={rc}")
            + " — поставь deploy/wbcms-timers.sudoers в /etc/sudoers.d/"
        )
    return "ok"


async def enable(name: str) -> dict:
    check_name(name)
    await _sudo("systemctl", "enable", "--now", f"{name}.timer")
    return {"ok": True}


async def disable(name: str) -> dict:
    check_name(name)
    await _sudo("systemctl", "disable", "--now", f"{name}.timer")
    return {"ok": True}


async def run_now(name: str) -> dict:
    check_name(name)
    await _sudo("systemctl", "start", f"{name}.service")
    return {"ok": True}


async def validate_calendar(value: str) -> None:
    v = (value or "").strip()
    if not v:
        raise TimersError("on_calendar пуст")
    if len(v) > 120 or "\n" in v:
        raise TimersError("on_calendar: слишком длинное/перенос строки запрещён")
    rc, _, err = await _run("systemd-analyze", "calendar", v)
    if rc != 0:
        raise TimersError("плохой OnCalendar: " + (err.strip().splitlines()[-1] if err.strip() else v))


async def set_schedule(name: str, value: str) -> dict:
    check_name(name)
    v = (value or "").strip()
    await validate_calendar(v)
    timer = f"{name}.timer"
    override = f"[Timer]\nOnCalendar=\nOnCalendar={v}\n"
    rc, _, err = await _run(
        "sudo", "-n", "tee", f"/etc/systemd/system/{timer}.d/override.conf",
        stdin=override.encode("utf-8"),
    )
    if rc != 0:
        raise TimersError("не пишу override.conf: " + (err.strip() or f"rc={rc}"))
    await _sudo("systemctl", "daemon-reload")
    await _sudo("systemctl", "restart", timer)
    return {"ok": True, "on_calendar": v}


async def tail_log(name: str, lines: int = 100) -> dict:
    check_name(name)
    n = max(20, min(int(lines or 100), 500))
    rc, out, err = await _run(
        "journalctl", "-q", "-u", f"{name}.service", "-n", str(n), "--no-pager"
    )
    if rc != 0:
        raise TimersError("journalctl: " + (err.strip() or f"rc={rc}"))
    return {"lines": out.splitlines()[-n:]}
