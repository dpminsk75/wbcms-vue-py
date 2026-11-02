"""Состояние контента карточки-конкурента — один источник правды.

«Контент есть» = описание не короче `DESC_MIN_LEN` (50) символов. Лёгкие строки,
которые создаёт наблюдение выдачи (цена/рейтинг/превью), описания не содержат —
значит контента по карточке ещё нет.

Порог и выражение длины описания живут здесь, а не в каждом сервисе: от него
зависят счётчики «А|У|Н» и кнопки сбора в SEO-мониторинге, фильтр «есть
контент» в «Собранных карточках» и отбор фраз в фраз-минере. Расхождение
критериев между ними и было причиной расхождения счётчиков.

Производительность: запросов не добавляем — та же выборка по
`wb_competitor_details` (GROUP BY nm_id), те же чанки по 400 id (сервер 1 ГБ,
больших IN не делаем).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, NamedTuple, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Порог «контент есть»: длина описания в символах.
DESC_MIN_LEN = 50

# Сколько nm_id за один запрос (IN большого размера на 1 ГБ сервере — нельзя).
CHUNK_SIZE = 400


class ContentState(NamedTuple):
    """Состояние контента карточки — для кнопок сбора и правила «12 ч»."""

    has: bool                   # описание есть (не короче DESC_MIN_LEN)
    full_at: str                # дата полного сбора 'YYYY-MM-DD'
    first_at: str               # дата первого сбора (легаси-строки)
    full_dt: datetime | None    # момент полного сбора (часы нужны для RECOLLECT_MIN_HOURS)


# Контента нет — заглушка вместо кортежа-заплатки.
EMPTY_STATE = ContentState(False, "", "", None)


def desc_len_sql(alias: str = "d") -> str:
    """SQL-выражение длины описания (алиас таблицы `wb_competitor_details`)."""
    return "CHAR_LENGTH(COALESCE(%s.description, ''))" % alias


def has_content_sql(alias: str = "d") -> str:
    """Признак «контент есть» в SQL: 1 — описание не короче общего порога.

    Готовый кусок для SELECT: `MAX(<это>)` в агрегате или `<это>` в обычной
    выборке. Внутрь MAX() CASE вставлять нельзя (MySQL: 1241 «Operand should
    contain 1 column(s)») — поэтому здесь он уже собран.
    """
    return "CASE WHEN %s >= %d THEN 1 ELSE 0 END" % (desc_len_sql(alias), DESC_MIN_LEN)


def chunk_ids(ids: Iterable[int], size: int = CHUNK_SIZE) -> list[list[int]]:
    """Разбить nm_id на чанки — больших IN не делаем (сервер 1 ГБ)."""
    uniq = sorted({int(n) for n in ids if n})
    return [uniq[i:i + size] for i in range(0, len(uniq), size)]


def build_content_states(rows: Sequence[Any]) -> dict[int, ContentState]:
    """Строки выборки → {nm_id: ContentState}; «есть контент» — по общему порогу."""
    out: dict[int, ContentState] = {}
    for r in rows:
        full_dt = r["full_at"] if isinstance(r["full_at"], datetime) else None
        out[int(r["nm_id"] or 0)] = ContentState(
            has=int(r["dlen"] or 0) >= DESC_MIN_LEN,
            full_at=full_dt.strftime("%Y-%m-%d") if full_dt else "",
            first_at=str(r["first_at"] or "")[:10],
            full_dt=full_dt,
        )
    return out


async def load_content_states(db: AsyncSession, nm_ids: Iterable[int],
                               chunk: int = CHUNK_SIZE) -> dict[int, ContentState]:
    """Состояние контента по карточкам: есть ли описание, даты сборов.

    Одна выборка на 400 nm_id из `wb_competitor_details` (GROUP BY nm_id).
    Дата контента — `full_collected_at` (полный сбор: описание + характеристики),
    иначе `first_collected_at` (строки, собранные до миграции 20261021).

    НЕ `collected_at`: его двигает пассивное наблюдение выдачи — карточка, у
    которой описание никто не собирал, выглядела бы «свежей», и кнопки сбора
    не видели бы кандидатов.
    """
    out: dict[int, ContentState] = {}
    for chunk_ids_list in chunk_ids(nm_ids, chunk):
        cph, cp = _inlist("c", chunk_ids_list)
        rows = (await db.execute(text(f"""
            SELECT nm_id,
                   MAX(full_collected_at) AS full_at,
                   MAX(first_collected_at) AS first_at,
                   MAX(CHAR_LENGTH(COALESCE(d.description, ''))) AS dlen
            FROM wb_competitor_details d WHERE d.nm_id IN ({cph}) GROUP BY d.nm_id
        """), cp)).mappings().all()
        out.update(build_content_states(rows))
    return out


def _inlist(prefix: str, values: Sequence[int]) -> tuple[str, dict]:
    """Список параметров в IN(...): ':c0, :c1, …' + словарь значений.

    Без скобок: в шаблоне запроса уже стоит `IN ({cph})` — с лишними
    скобками получается `IN ((...))`, и MySQL отвечает 1241 «Operand should
    contain 1 column(s)».
    """
    if not values:
        return "", {}
    names = [f":{prefix}{i}" for i in range(len(values))]
    params = {f"{prefix}{i}": v for i, v in enumerate(values)}
    return ", ".join(names), params
