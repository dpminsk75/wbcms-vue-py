import logging
import os
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+asyncmy://", 1)
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,  # сброс коннектов раньше MySQL wait_timeout (ночной простой)
    pool_timeout=30,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with SessionLocal() as session:
        yield session


def get_session():
    """Контекстный менеджер сессии для воркеров (cron): `async with get_session() as db`."""
    return SessionLocal()


# --- медленные SQL-стейтменты -------------------------------------------------
# Задача: после очередного «повесило сервер» сразу видеть, КАКОЙ запрос был
# долгим, не гадая (в journald: `journalctl -u wbcms-py | grep slow_sql`).
# Порог 2 с: обычные запросы бэкенда укладываются в десятки мс; дольше 2 с —
# уже подозреваемый на перебор строк/нет индекса. Пишем в stderr → journald.
SLOW_SQL_SECONDS = 2.0

_slow_sql_log = logging.getLogger("wbcms.slow_sql")
if not _slow_sql_log.handlers:      # uvicorn корневой logger не настраивает
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    _slow_sql_log.addHandler(_h)
_slow_sql_log.setLevel(logging.INFO)


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _slow_sql_start(conn, cursor, statement, parameters, context, executemany):
    # присваиваем (не setdefault!) — каждый стейтмент меряется заново,
    # чтобы не таскать стартовое время от предыдущего
    conn.info["_slow_sql_started"] = time.monotonic()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _slow_sql_done(conn, cursor, statement, parameters, context, executemany):
    started = conn.info.pop("_slow_sql_started", None)
    if started is None:
        return
    took = time.monotonic() - started
    if took < SLOW_SQL_SECONDS:
        return
    try:
        rows = cursor.rowcount
    except Exception:
        rows = -1
    _slow_sql_log.info(
        "slow_sql %.2fs rows=%s many=%s :: %s",
        took, rows, bool(executemany),
        " ".join(str(statement or "").split())[:400],
    )
