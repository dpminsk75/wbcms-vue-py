"""Вопросы покупателей WB — синхронизация feedbacks-api.

Методы WB (категория «Вопросы и отзывы», бит 7 токена):
  1) GET /api/v1/questions?isAnswered=true|false&take=&skip=&order=&dateFrom=&dateTo=&nmId=
     — список вопросов. isAnswered обязателен (два прохода: неотвеченные/отвеченные).
     Ограничение WB: take + skip ≤ 10000 → окно дат режется пополам, если в нём
     больше 10000 вопросов.
  2) GET /api/v1/question?id=<id> — один вопрос с ответом (дозагрузка ответа).
  3) GET /api/v1/questions/count?dateFrom=&dateTo=&isAnswered — счётчик (контроль).

Лимиты запросов категории «Вопросы и отзывы» (одного продавца):
  персональный/сервисный/базовый-с-секретом — 3 запроса/с (интервал 333 мс);
  базовый — 5 запросов/час (интервал 12 мин). Пауза подстраивается под тип токена.

Запись в wb_questions (PK (company_id, id)): multi-row INSERT ... AS new
ON DUPLICATE KEY UPDATE (VALUES() запрещён MySQL 8.0.20+).
Не трогаем при UPDATE: id, company_id, created_date, created_at.
"""
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.feedback_sync_service import parse_dt
from backend.services.wb_sync_base import company_sync_plan, get_json

QUESTIONS_URL = "https://feedbacks-api.wildberries.ru/api/v1/questions"
QUESTION_URL = "https://feedbacks-api.wildberries.ru/api/v1/question"
COUNT_URL = "https://feedbacks-api.wildberries.ru/api/v1/questions/count"

TIMEOUT_S = 20
TAKE = 500            # размер страницы
MAX_WINDOW = 10000    # WB: take + skip ≤ 10000
PAUSE_FAST_S = 0.5    # personal/service: 3 запроса/с — берём 2/с, чтобы не делить лимит с синком отзывов
PAUSE_SLOW_S = 720    # basic: 5 запросов/час → интервал 12 мин
BATCH = 200           # строк в одном multi-row INSERT
WINDOW_DAYS = 90      # окно «полного» режима: чем больше окно, тем меньше запросов к WB
MSK = timezone(timedelta(hours=3))
EPOCH_TS = 1546300800  # 2019-01-01 00:00:00 UTC — WB не старше

# Колонки wb_questions для INSERT.
INSERT_COLS = [
    "company_id", "id", "nm_id", "imt_id", "product_name", "supplier_article",
    "supplier_name", "brand_name", "q_text", "answer_text", "answer_editable",
    "answer_date", "state", "was_viewed", "is_warned", "created_date",
    "raw_json", "created_at", "updated_at",
]
# Широкий UPDATE: содержимое вопроса и ответа обновляем всегда (ответ мог
# прийти позже даты вопроса — поэтому «свежий» режим берёт окно шире 2 дней).
UPDATE_COLS = [c for c in INSERT_COLS
                if c not in ("company_id", "id", "created_date", "created_at")]


def _int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def day_bounds(date_from: str | None, date_to: str | None) -> tuple[int, int]:
    """Границы периода (YYYY-MM-DD) в МСК → unix-таймстампы для WB."""
    today = datetime.now(MSK).date()
    df = date_from or (today - timedelta(days=10)).isoformat()
    dt = date_to or today.isoformat()
    start = datetime.fromisoformat(df + "T00:00:00").replace(tzinfo=MSK)
    end = datetime.fromisoformat(dt + "T23:59:59").replace(tzinfo=MSK)
    return int(start.timestamp()), int(end.timestamp())


def fmt_ts(ts: int | None) -> str:
    """Unix-таймстамп → 'ДД.ММ.ГГГГ ЧЧ:ММ' (МСК) — для логов воркера."""
    if not ts:
        return "—"
    return datetime.fromtimestamp(int(ts), MSK).strftime("%d.%m.%Y %H:%M")


def _txt(v, limit: int) -> str | None:
    """Строка из WB, обрезанная под VARCHAR-колонку (WB не ограничивает длину)."""
    if v is None:
        return None
    s = str(v)
    return s[:limit] if len(s) > limit else s


def map_row(item: dict, company_id: int, now: int) -> dict | None:
    """Вопрос WB → строка wb_questions (1в1 с полями ответа WB)."""
    qid = item.get("id")
    if not qid:
        return None
    pd = item.get("productDetails")
    if not isinstance(pd, dict):
        pd = {}
    ans = item.get("answer")
    if not isinstance(ans, dict):
        ans = {}
    nm = _int(pd.get("nmId"))
    imt = _int(pd.get("imtId"))
    return {
        "company_id": company_id,
        "id": _txt(qid, 64),
        "nm_id": nm or None,
        "imt_id": imt or None,
        "product_name": _txt(pd.get("productName"), 512),
        "supplier_article": _txt(pd.get("supplierArticle"), 255),
        "supplier_name": _txt(pd.get("supplierName"), 255),
        "brand_name": _txt(pd.get("brandName"), 255),
        "q_text": item.get("text"),
        "answer_text": ans.get("text"),
        "answer_editable": 1 if ans.get("editable") else 0,
        "answer_date": parse_dt(ans.get("createDate")),
        "state": _txt(item.get("state"), 32),
        "was_viewed": 1 if item.get("wasViewed") else 0,
        "is_warned": 1 if item.get("isWarned") else 0,
        "created_date": parse_dt(item.get("createdDate")),
        # сырой объект WB целиком: новые поля WB не теряем
        "raw_json": json.dumps(item, ensure_ascii=False),
        "created_at": now,
        "updated_at": now,
    }


class QuestionsSyncService:
    """Наполнение wb_questions вопросами WB."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id
        self._pause = PAUSE_FAST_S   # пауза между запросами к WB (растёт при 429)
        self._progress = None        # колбэк лога

    # --- запись -----------------------------------------------------------

    async def _session_guards(self) -> None:
        """Ограничители сессии (правило проекта для прод-DML):
        lock_wait_timeout в MySQL 8 по умолчанию = год — без него запрос
        может висеть на блокировке строки практически вечно."""
        await self.db.execute(text("SET SESSION lock_wait_timeout = 5"))
        await self.db.execute(text("SET SESSION innodb_lock_wait_timeout = 5"))
        await self.db.commit()

    async def _acquire_lock(self) -> bool:
        """Адvisory-лок MySQL: один синк вопросов на компанию.
        Без него два прогона (таймер + ручной + кнопка на странице) дерутся
        за одни и те же строки и висят на row lock."""
        res = (await self.db.execute(text(
            "SELECT GET_LOCK(:name, 0)"), {"name": self._lock_name()})).scalar()
        await self.db.commit()
        return int(res or 0) == 1

    async def _release_lock(self) -> None:
        try:
            await self.db.execute(
                text("SELECT RELEASE_LOCK(:name)"), {"name": self._lock_name()})
            await self.db.commit()
        except Exception:
            pass

    def _lock_name(self) -> str:
        return f"wbcms_questions_sync_{self.company_id}"

    async def _upsert(self, rows: list, dry_run: bool = False) -> int:
        """Multi-row INSERT ... AS new ON DUPLICATE KEY UPDATE, батчами по BATCH."""
        if not rows:
            return 0
        if dry_run:
            return len(rows)
        total = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            w = len(str(len(chunk)))
            params: dict = {}
            vals = []
            for n, r in enumerate(chunk, start=1):
                vals.append("(" + ",".join(f":{c}_{n:0{w}d}" for c in INSERT_COLS) + ")")
                for c in INSERT_COLS:
                    params[f"{c}_{n:0{w}d}"] = r.get(c)
            sql = (
                f"INSERT INTO wb_questions ({', '.join(INSERT_COLS)}) "
                f"VALUES {', '.join(vals)} AS new "
                f"ON DUPLICATE KEY UPDATE "
                + ", ".join(f"{c} = new.{c}" for c in UPDATE_COLS)
            )
            await self.db.execute(text(sql), params)
            total += len(chunk)
        await self.db.commit()
        return total

    # --- чтение WB ---------------------------------------------------------

    async def _get(self, url: str, params: list, token: str) -> dict | list:
        """GET к WB в отдельном потоке: urllib блокирующий, а мы живём в event loop.

        429 (лимит категории «Вопросы и отзывы» — 3 запроса/с на продавца, а токен
        общий с синком отзывов) — растим паузу и повторяем: иначе каждый запрос
        в очереди ждёт Retry-After по минуте и прогон «подвисает».
        """
        for attempt in range(6):
            t0 = time.monotonic()
            try:
                data = await asyncio.to_thread(get_json, url, params, token,
                                               TIMEOUT_S, 0)
            except RuntimeError as e:
                msg = str(e)
                if "http=429" in msg:
                    if attempt >= 5:
                        raise
                    wait = self._bump_pause()
                    if self._progress:
                        self._progress("лимит WB (429)", f"пауза {wait}с", 0)
                    await asyncio.sleep(wait)
                    continue
                # сеть / 5xx — короткий повтор
                if attempt >= 2:
                    raise
                await asyncio.sleep(2 ** attempt)
                continue
            el = time.monotonic() - t0
            if el >= 8 and self._progress:
                self._progress("медленный WB", f"{el:.0f}с", 0)
            return data
        raise RuntimeError("WB: 429 не прошёл за 6 попыток")

    def _bump_pause(self) -> int:
        """Пауза между запросами растёт при 429 и не сбрасывается до конца прогона."""
        self._pause = min(int(self._pause * 2) + 5, 120)
        return self._pause

    async def _fetch_page_window(self, token: str, ts_from: int, ts_to: int,
                                 is_answered: bool, nm_id: int | None) -> tuple[list, bool]:
        """Все вопросы окна по одному isAnswered. Возвращает (вопросы, окно переполнено)."""
        items: list = []
        skip = 0
        while True:
            params = [("isAnswered", "true" if is_answered else "false"),
                      ("take", TAKE), ("skip", skip), ("order", "dateAsc")]
            if nm_id:
                params.append(("nmId", nm_id))
            params.append(("dateFrom", ts_from))
            params.append(("dateTo", ts_to))
            data = await self._get(QUESTIONS_URL, params, token)
            body = (data.get("data") or {}) if isinstance(data, dict) else {}
            batch = body.get("questions") or []
            items.extend(batch)
            if len(batch) < TAKE:
                return items, False
            skip += TAKE
            if skip + TAKE > MAX_WINDOW:
                # WB: take + skip ≤ 10000 — дальше нельзя, окно режем пополам
                return items, True
            await asyncio.sleep(self._pause)

    async def _window(self, token: str, ts_from: int, ts_to: int,
                      nm_id: int | None, dry_run: bool, progress=None) -> dict:
        """Все вопросы окна (оба isAnswered). Окно >10000 вопросов → режем пополам."""
        fetched: list = []
        truncated = False
        for is_answered in (False, True):
            items, tr = await self._fetch_page_window(token, ts_from, ts_to,
                                                      is_answered, nm_id)
            fetched.extend(items)
            if tr:
                truncated = True
                break
            if progress:
                progress("isAnswered=" + ("true" if is_answered else "false"),
                         f"{fmt_ts(ts_from)} … {fmt_ts(ts_to)}", len(items))
        if truncated and (ts_to - ts_from) > 1:
            mid = ts_from + (ts_to - ts_from) // 2
            if progress:
                progress("окно переполнено", "режу пополам", 0)
            a = await self._window(token, ts_from, mid, nm_id, dry_run, progress)
            b = await self._window(token, mid + 1, ts_to, nm_id, dry_run, progress)
            return {"fetched": a["fetched"] + b["fetched"],
                    "saved": a["saved"] + b["saved"],
                    "pages": a["pages"] + b["pages"],
                    "split": True}
        now = int(time.time())
        rows = [r for r in (map_row(it, self.company_id, now) for it in fetched) if r]
        saved = await self._upsert(rows, dry_run)
        return {"fetched": len(fetched), "saved": saved, "pages": 1, "split": False}

    async def _fetch_one(self, token: str, qid: str) -> dict | None:
        """GET /api/v1/question?id= — один вопрос с ответом."""
        data = await self._get(QUESTION_URL, [("id", qid)], token)
        body = (data.get("data") if isinstance(data, dict) else None)
        return body if isinstance(body, dict) and body.get("id") else None

    async def _count(self, token: str, ts_from: int | None = None,
                     ts_to: int | None = None, is_answered: bool = True) -> int:
        """GET /api/v1/questions/count — сколько вопросов за период (контроль полноты)."""
        params: list = [("isAnswered", "true" if is_answered else "false")]
        if ts_from:
            params.append(("dateFrom", ts_from))
        if ts_to:
            params.append(("dateTo", ts_to))
        data = await self._get(COUNT_URL, params, token)
        if isinstance(data, dict):
            try:
                return int(data.get("data") or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    # --- режимы -------------------------------------------------------------

    async def sync_fresh(self, token: str, ts_from: int, ts_to: int,
                         nm_id: int | None = None, dry_run: bool = False,
                         progress=None) -> dict:
        """Одно окно дат, оба isAnswered — «свежие» вопросы."""
        res = await self._window(token, ts_from, ts_to, nm_id, dry_run, progress)
        res["from"] = ts_from
        res["to"] = ts_to
        res["period"] = f"{fmt_ts(ts_from)} … {fmt_ts(ts_to)}"
        return res

    async def sync_full(self, token: str, ts_from: int | None = None,
                        ts_to: int | None = None, window_days: int = WINDOW_DAYS,
                        nm_id: int | None = None, dry_run: bool = False,
                        max_windows: int = 200, progress=None) -> dict:
        """Вся история: окна от сегодня назад по window_days.

        Стоп — не «3 пустых окна» (в истории бывают перерывы длиннее 90 дней,
        и вопросы за ними потерялись бы), а точный ответ WB: если счётчик
        вопросов раньше окна пуст — истории больше нет.
        """
        end = int(ts_to) if ts_to else int(datetime.now(MSK).replace(
            hour=23, minute=59, second=59).timestamp())
        start_limit = int(ts_from) if ts_from else EPOCH_TS
        out = {"fetched": 0, "saved": 0, "pages": 0, "windows": 0,
               "empty_windows": 0, "stopped": "",
               "period": f"{fmt_ts(start_limit)} … {fmt_ts(end)}"}
        for _ in range(max(1, int(max_windows or 1))):
            w_start = max(start_limit, end - int(window_days) * 86400)
            if w_start > end:
                out["stopped"] = "дошли до начала периода"
                break
            res = await self._window(token, w_start, end, nm_id, dry_run, progress)
            out["fetched"] += res["fetched"]
            out["saved"] += res["saved"]
            out["pages"] += res["pages"]
            out["windows"] += 1
            if progress:
                progress(f"окно {out['windows']}",
                         f"{fmt_ts(w_start)} … {fmt_ts(end)}", res["fetched"])
            # окно закрыли — транзакцию сбрасываем (пустое окно не пишет ничего)
            await self.db.commit()
            if not res["fetched"]:
                out["empty_windows"] += 1
                # точно ли раньше есть вопросы? (перерыв в истории — идём дальше)
                older = (await self._count(token, start_limit, w_start - 1, is_answered=False)
                         + await self._count(token, start_limit, w_start - 1, is_answered=True))
                if progress:
                    progress("проверка", f"раньше {fmt_ts(w_start)}", older)
                if older == 0:
                    out["stopped"] = f"в WB вопросов раньше {fmt_ts(w_start)} нет — конец истории"
                    break
            end = w_start - 1
        else:
            out["stopped"] = f"достигнут лимит окон ({max_windows})"
        return out

    async def sync_one(self, token: str, qid: str, dry_run: bool = False) -> dict:
        """Дозагрузить один вопрос (GET /api/v1/question?id=) и обновить строку."""
        await self._session_guards()
        self._pause = PAUSE_FAST_S
        item = await self._fetch_one(token, qid)
        if not item:
            return {"ok": False, "error": "вопрос не найден в WB"}
        row = map_row(item, self.company_id, int(time.time()))
        if not row:
            return {"ok": False, "error": "пустой ответ WB"}
        saved = await self._upsert([row], dry_run)
        return {"ok": True, "saved": saved, "dry_run": dry_run}

    # --- основной -----------------------------------------------------------

    async def sync(self, mode: str = "fresh", date_from: str | None = None,
                   date_to: str | None = None, nm_id: int | None = None,
                   window_days: int = WINDOW_DAYS, max_windows: int = 200,
                   dry_run: bool = False, progress=None) -> dict:
        """Прогон одной компании: гейт токена → fresh (окно) или full (история)."""
        await self._session_guards()
        if not await self._acquire_lock():
            return {"company_id": self.company_id,
                    "skipped": "синк этой компании уже идёт в другом процессе",
                    "dry_run": dry_run}
        try:
            return await self._sync_locked(mode, date_from, date_to, nm_id,
                                           window_days, max_windows, dry_run,
                                           progress)
        finally:
            await self._release_lock()

    async def _sync_locked(self, mode: str, date_from, date_to, nm_id,
                            window_days: int, max_windows: int, dry_run: bool,
                            progress) -> dict:
        plan = await company_sync_plan(self.db, self.company_id, "feedbacks", 1)
        # план — только чтение: закрываем транзакцию, дальше идём в сеть,
        # держать открытую транзакцию минуты нельзя (blocks ALTER, держит снапшот)
        await self.db.commit()
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token = plan["token"]
        token_type = plan.get("token_type") or "unknown"
        fast = token_type in ("personal", "service")
        # пауза между запросами к WB: 0.5 с на быстром токене (лимит 3/с на
        # продавца, токен общий с синком отзывов), 12 мин на базовом (5/час).
        # При 429 пауза растёт сама — см. _bump_pause.
        self._pause = PAUSE_FAST_S if fast else PAUSE_SLOW_S
        self._progress = progress
        if not fast and mode == "full":
            return {"company_id": self.company_id, "skipped":
                    "токен basic/unknown (5 запросов/час) — полный срез невозможен, "
                    "нужен персональный/сервисный",
                    "token_type": token_type, "dry_run": dry_run}
        ts_from, ts_to = day_bounds(date_from, date_to)
        out = {"company_id": self.company_id, "mode": mode, "dry_run": dry_run,
               "token_type": token_type, "pause_s": self._pause,
               "from": date_from, "to": date_to}
        if mode == "full":
            # вся история: начало — 2019-01-01, если период не задан
            out["full"] = await self.sync_full(
                token, ts_from=ts_from if date_from else None,
                ts_to=ts_to if date_to else None,
                window_days=window_days or WINDOW_DAYS, nm_id=nm_id, dry_run=dry_run,
                max_windows=max_windows, progress=progress)
            # контроль полноты: сколько вопросов видит WB всего
            out["wb_count"] = {
                "unanswered": await self._count(token, is_answered=False),
                "answered": await self._count(token, is_answered=True),
            }
        else:
            out["fresh"] = await self.sync_fresh(
                token, ts_from, ts_to, nm_id=nm_id, dry_run=dry_run, progress=progress)
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out


# --- фоновый запуск синка из UI ---------------------------------------------
# Синк (особенно full) идёт минуты — HTTP-запрос столько не ждёт, поэтому
# запуск идёт отдельной задачей, состояние смотрим через /api/questions/sync/status.
_SYNC_STATE: dict = {"running": False, "started_at": None, "finished_at": None,
                     "log": [], "result": None, "company_id": None, "mode": None}
_SYNC_TASK: asyncio.Task | None = None


def sync_state() -> dict:
    """Текущее состояние фонового синка (без внутренних объектов)."""
    return {k: v for k, v in _SYNC_STATE.items() if k != "result"} | \
        {"result": _SYNC_STATE.get("result")}


async def _run_sync_task(company_id: int, mode: str, date_from, date_to,
                         nm_id, window_days: int, dry_run: bool):
    from backend.database import get_session
    lines: list = []
    _SYNC_STATE["log"] = lines   # список мутируется на месте — видно прогресс

    def progress(stage: str, sub: str, count: int):
        lines.append(f"{stage} {sub}: {count}")
        del lines[:-50]

    try:
        async with get_session() as db:
            svc = QuestionsSyncService(db, company_id=company_id)
            res = await svc.sync(mode=mode, date_from=date_from, date_to=date_to,
                                 nm_id=nm_id, window_days=window_days,
                                 dry_run=dry_run, progress=progress)
        _SYNC_STATE["result"] = res
    except Exception as exc:
        _SYNC_STATE["result"] = {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        _SYNC_STATE["log"] = lines
        _SYNC_STATE["running"] = False
        _SYNC_STATE["finished_at"] = int(time.time())


def start_sync(company_id: int, mode: str = "fresh", date_from=None,
               date_to=None, nm_id=None, window_days: int = 30,
               dry_run: bool = False) -> dict:
    """Запустить синк в фоне. Возвращает статус запуска."""
    global _SYNC_TASK
    if _SYNC_STATE.get("running"):
        return {"started": False, "error": "синк уже выполняется"}
    _SYNC_STATE.update({"running": True, "started_at": int(time.time()),
                        "finished_at": None, "log": [], "result": None,
                        "company_id": company_id, "mode": mode})
    _SYNC_TASK = asyncio.create_task(_run_sync_task(
        company_id, mode, date_from, date_to, nm_id, window_days, dry_run))
    return {"started": True, "company_id": company_id, "mode": mode,
            "dry_run": dry_run}
