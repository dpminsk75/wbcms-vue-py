"""Пакетные INSERT ... ON DUPLICATE KEY UPDATE для ext-коллектора.

Зачем: расширение присылает выдачу на 200 товаров, а писателей на каждую строку
три (позиции выдачи, карточки конкурентов, контент). По одному INSERT на строку
это сотни round-trip'ов в одной транзакции → длинные удержания блокировок и
deadlock'и 1213/1205 (см. `_with_db_retry` в routers/ext.py), а ретрай повторяет
всю транзакцию целиком.

Семантика та же, что у одиночного запроса: MySQL 8.0.19+ умеет алиас строки
(`AS new`) и для multi-row INSERT — `new.<col>` это значение КОНКРЕТНОЙ
вставляемой строки, старое значение берём с префиксом имени таблицы
(иначе MySQL даёт 1052 «ambiguous» — см. AGENTS.md).

Чанки по 40 строк: ~40 × 45 колонок = 1800 плейсхолдеров на запрос (лимит
MySQL — 65535 плейсхолдеров и 65 535 параметров на prepared statement).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_CHUNK = 40


class Raw:
    """Значение-выражение SQL (CURDATE(), NOW(), JSON_ARRAY()) — вставляется как есть."""

    __slots__ = ("sql",)

    def __init__(self, sql: str):
        self.sql = sql


def _chunks(rows: list, size: int):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def build_bulk_sql(table: str, columns: list[str], rows: list[dict],
                   suffix: str = "", extra_params: dict | None = None,
                   chunk: int = DEFAULT_CHUNK) -> list[tuple[str, dict]]:
    """Собрать (sql, params) для каждого чанка строк.

    `suffix` — хвост запроса целиком (например `AS new ON DUPLICATE KEY UPDATE ...`).
    `extra_params` — параметры, общие для всех строк чанка.
    """
    out: list[tuple[str, dict]] = []
    base = dict(extra_params or {})
    for part in _chunks(rows, chunk):
        params = dict(base)
        values: list[str] = []
        for i, row in enumerate(part):
            cols: list[str] = []
            for j, col in enumerate(columns):
                val = row.get(col)
                if isinstance(val, Raw):
                    cols.append(val.sql)
                    continue
                key = f"b{i}_{j}"
                cols.append(f":{key}")
                params[key] = val
            values.append("(" + ", ".join(cols) + ")")
        sql = (f"INSERT INTO {table} ({', '.join(columns)}) VALUES "
               + ", ".join(values) + (f" {suffix}" if suffix else ""))
        out.append((sql, params))
    return out


async def exec_bulk_insert(db: AsyncSession, table: str, columns: list[str],
                           rows: list[dict], suffix: str = "",
                           extra_params: dict | None = None,
                           chunk: int = DEFAULT_CHUNK) -> int:
    """Выполнить пакетный INSERT (чанками). Возвращает число строк."""
    if not rows:
        return 0
    for sql, params in build_bulk_sql(table, columns, rows, suffix, extra_params, chunk):
        await db.execute(text(sql), params)
    return len(rows)
