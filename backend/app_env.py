"""Режим окружения и управление фоновыми задачами.

Два независимых механизма (читаются из .env бэка):

1. ``APP_ENV`` — режим окружения: ``prod`` | ``dev`` | ``staging``.
   Влияет на безопасные умолчания: в ``dev`` фоновые задачи выключены.

2. ``DISABLE_BACKGROUND_TASKS`` — явный переключатель фоновых задач:
   ``1``/``true`` — выключить, ``0``/``false`` — включить.
   Если переменная не задана, решение принимается по ``APP_ENV``.

Зачем это нужно. Фоновые циклы (phrase_miner, feedback_review, images_sync)
живут ВНУТРИ процесса бэка и стартуют в ``@app.on_event("startup")``.
Их нельзя «остановить» снаружи: любой рестарт systemd-юнита поднимает их
заново. Поэтому режим должен задаваться ДО старта процесса — через .env.

На dev-сервере бэк подключается к реплике БД в режиме super_read_only:
фоновые задачи всё равно не смогли бы писать, но они бы штурмовали реплику
запросами и мешали отладке. С ``DISABLE_BACKGROUND_TASKS=1`` они не стартуют
вовсе.

Значения по умолчанию рассчитаны на прод: ``APP_ENV=prod`` (фоновые задачи
включены) — поведение не меняется, пока переменная не выставлена явно.
"""

import os

#: Допустимые режимы окружения.
APP_ENVS = ("prod", "dev", "staging")

#: Текущий режим окружения. Неизвестное значение -> "prod" (безопасный дефолт).
APP_ENV = (os.getenv("APP_ENV") or "prod").strip().lower()
if APP_ENV not in APP_ENVS:
    APP_ENV = "prod"


def _env_flag(name: str):
    """Читает булеву переменную окружения. None — если не задана."""
    raw = (os.getenv(name) or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def _resolve_background_tasks() -> bool:
    """Включены ли фоновые задачи.

    Приоритет у явного ``DISABLE_BACKGROUND_TASKS``. Если его нет —
    по умолчанию в ``dev`` выключаем, в ``prod``/``staging`` включаем.
    """
    explicit = _env_flag("DISABLE_BACKGROUND_TASKS")
    if explicit is not None:
        return not explicit
    return APP_ENV != "dev"


#: Запускать ли фоновые циклы бэка (phrase_miner / feedback_review / images_sync).
BACKGROUND_TASKS_ENABLED = _resolve_background_tasks()


def is_dev() -> bool:
    """Режим разработки (dev-сервер, тесты, локальный запуск)."""
    return APP_ENV == "dev"


def is_staging() -> bool:
    """Режим staging."""
    return APP_ENV == "staging"


def env_info() -> dict:
    """Сведения о режиме — показываются в /health, чтобы режим был виден сразу."""
    return {
        "app_env": APP_ENV,
        "background_tasks": BACKGROUND_TASKS_ENABLED,
    }
