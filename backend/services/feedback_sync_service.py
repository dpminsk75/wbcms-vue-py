"""Синхронизация отзывов WB — порт commands/WbFeedbacksController::actionSync
(широкий upsert) + узкий upsert из WbAutoReplyController::syncTodayFeedbacks
для подготовки автоответчика (narrow_update=True).

Два API feedbacks-api.wildberries.ru:
  1) GET /api/v1/feedbacks?isAnswered=false|true&take=500&skip=N&dateFrom=<unix>&dateTo=<unix>
     — два прохода (неотвеченные, затем отвеченные), skip += take, стоп при count < take
  2) GET /api/v1/feedbacks/archive?take=500&skip=N&order=dateDesc
     — БЕЗ фильтра по датам: дата режется локально по createdDate
       (новее dateTo → пропуск, в диапазоне → берём, старше dateFrom → стоп-флаг:
        архив отсортирован от новых к старым).

Токен — raw companies.api_key (PHP WbHttpClient шлёт Authorization без Bearer).
Границы суток — МСК (UTC+3), в PHP было strtotime() → зависело от TZ сервера.
Запись в wb_feedbacks (PK id varchar(64)): multi-row INSERT ... AS new
ON DUPLICATE KEY UPDATE (VALUES() запрещён MySQL 8.0.20+).
Не трогаем при UPDATE: id, company_id, imtId, nmID, createdDate, created_at,
is_auto_replied, rule_id, f_action.
"""
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json

FEEDBACKS_URL = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
ARCHIVE_URL = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/archive"
TIMEOUT_S = 20
TAKE = 500
PAUSE_S = 0.5      # feedbacks-api: ~300 запросов/мин на токен
BATCH = 300        # строк в одном multi-row INSERT
MSK = timezone(timedelta(hours=3))

# Колонки wb_feedbacks для INSERT (1в1 с PHP-upsert из WbFeedbacksController).
INSERT_COLS = [
    "id", "company_id", "imtId", "nmID", "subjectId", "subjectName", "userName",
    "matchingSize", "color", "text", "pros", "cons", "productValuation", "isNew",
    "state", "status", "orderStatus", "is_pay", "f_cost", "is_archive",
    "createdDate", "updatedDate", "productDetails", "photoLinks", "video",
    "answer", "bables", "created_at", "updated_at",
]
# Широкий UPDATE при уже существующей записи (WbFeedbacksController, :338-362).
FULL_UPDATE_COLS = [
    "subjectId", "subjectName", "userName", "matchingSize", "color", "text", "pros",
    "cons", "productValuation", "isNew", "state", "status", "orderStatus",
    "is_pay", "f_cost", "is_archive", "updatedDate", "productDetails",
    "photoLinks", "video", "answer", "bables", "updated_at",
]
# Узкий UPDATE из WbAutoReplyController::syncTodayFeedbacks (:558-568):
# is_archive/state/status НЕ трогаем, answer обновляем ВСЕГДА — так узнаём,
# что на отзыв ответили вручную (иначе рискуем ответить повторно).
NARROW_UPDATE_COLS = ["text", "pros", "cons", "productValuation", "answer", "updated_at"]


def _dt(v):
    """Дата WB ('...' или Z/ISO) → datetime naive в МСК или None."""
    if not v:
        return None
    s = str(v).strip()
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s[:-1] + "+00:00")
        elif "T" in s:
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.fromisoformat(s.replace(" ", "T"))
    except ValueError:
        try:
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(MSK).replace(tzinfo=None)
    return dt


def parse_dt(v):
    dt = _dt(v)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def parse_ts(v):
    """Дата WB → unix-таймстамп (сравнение с границами МСК)."""
    dt = _dt(v)
    return int(dt.replace(tzinfo=MSK).timestamp()) if dt else None


def day_bounds(date_from, date_to):
    """Границы периода (даты 'YYYY-MM-DD') в МСК → unix-таймстампы для API.
    По умолчанию — последние 10 дней (как в PHP actionSync)."""
    today = datetime.now(MSK).date()
    df = date_from or (today - timedelta(days=10)).isoformat()
    dt = date_to or today.isoformat()
    start = datetime.fromisoformat(df + "T00:00:00").replace(tzinfo=MSK)
    end = datetime.fromisoformat(dt + "T23:59:59").replace(tzinfo=MSK)
    return int(start.timestamp()), int(end.timestamp())


def _json_or_none(v):
    """JSON-колонка: значение как есть (аналог PHP Json::encode) либо NULL."""
    if v is None:
        return None
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def map_row(item, company_id, is_archive, now: int):
    """Отзыв WB → строка wb_feedbacks (поля 1в1 с PHP-вставкой)."""
    fid = item.get("id")
    if not fid:
        return None
    pd = item.get("productDetails")
    if not isinstance(pd, dict):
        pd = {}
    f_cost = item.get("fCost")
    if f_cost in (None, ""):
        f_cost = item.get("bableCost")
    if isinstance(f_cost, str):
        try:
            f_cost = int(f_cost)
        except ValueError:
            f_cost = None
    def _int(key, default=0):
        try:
            return int(item.get(key) or default)
        except (TypeError, ValueError):
            return default
    try:
        nm = int(pd.get("nmId") or 0)
    except (TypeError, ValueError):
        nm = 0
    now_fmt = datetime.now(MSK).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "id": str(fid),
        "company_id": company_id,
        "imtId": _int("imtId"),
        "nmID": nm,
        "subjectId": item.get("subjectId"),
        "subjectName": item.get("subjectName"),
        "userName": item.get("userName"),
        "matchingSize": item.get("matchingSize"),
        "color": item.get("color"),
        "text": item.get("text"),
        "pros": item.get("pros"),
        "cons": item.get("cons"),
        "productValuation": _int("productValuation"),
        # PHP WbFeedbacksController:318 — нет isNew в ответе → 1
        "isNew": 1 if item.get("isNew") else (1 if "isNew" not in item else 0),
        "state": item.get("state"),
        "status": item.get("status"),
        "orderStatus": item.get("orderStatus"),
        "is_pay": 1 if item.get("isPay") else 0,
        "f_cost": f_cost,
        "is_archive": 1 if is_archive else 0,
        "createdDate": parse_dt(item.get("createdDate")) or now_fmt,
        "updatedDate": parse_dt(item.get("updatedDate")),
        "productDetails": json.dumps(pd, ensure_ascii=False) if pd else "{}",
        "photoLinks": _json_or_none(item.get("photoLinks")),
        "video": _json_or_none(item.get("video")),
        "answer": _json_or_none(item.get("answer")),
        "bables": _json_or_none(item.get("bables")),
        "created_at": now,
        "updated_at": now,
    }


class FeedbackSyncService:
    """Наполнение wb_feedbacks отзывами WB (актуальные + архив)."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    # --- запись -----------------------------------------------------------

    async def _upsert(self, rows: list, update_cols: list, dry_run: bool = False) -> int:
        """Multi-row INSERT ... AS new ON DUPLICATE KEY UPDATE, батчами по BATCH."""
        if not rows:
            return 0
        if dry_run:
            return len(rows)
        total = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            w = len(str(len(chunk)))
            params = {}
            vals = []
            for n, r in enumerate(chunk, start=1):
                vals.append("(" + ",".join(f":{c}_{n:0{w}d}" for c in INSERT_COLS) + ")")
                for c in INSERT_COLS:
                    params[f"{c}_{n:0{w}d}"] = r.get(c)
            sql = (
                f"INSERT INTO wb_feedbacks ({', '.join(INSERT_COLS)}) "
                f"VALUES {', '.join(vals)} AS new "
                f"ON DUPLICATE KEY UPDATE "
                + ", ".join(f"{c} = new.{c}" for c in update_cols)
            )
            await self.db.execute(text(sql), params)
            total += len(chunk)
        await self.db.commit()
        return total

    # --- актуальные ---------------------------------------------------------

    async def sync_current(self, token: str, ts_from: int, ts_to: int,
                           narrow_update: bool = False, dry_run: bool = False,
                           progress=None) -> dict:
        """GET /api/v1/feedbacks — два прохода: неотвеченные, затем отвеченные."""
        out = {"fetched": 0, "saved": 0, "pages": 0}
        for is_answered in ("false", "true"):
            skip = 0
            while True:
                params = [("isAnswered", is_answered), ("take", TAKE), ("skip", skip),
                          ("dateFrom", ts_from), ("dateTo", ts_to)]
                data = get_json(FEEDBACKS_URL, params, token, timeout=TIMEOUT_S)
                body = (data if isinstance(data, dict) else {}).get("data") or {}
                items = body.get("feedbacks") or []
                if progress:
                    progress(f"isAnswered={is_answered}", f"skip={skip}", len(items))
                if not items:
                    break
                if not out["pages"] and items:
                    out["first_created"] = parse_dt(items[0].get("createdDate"))
                now = int(time.time())
                rows = [r for r in
                        (map_row(it, self.company_id, False, now) for it in items) if r]
                out["saved"] += await self._upsert(
                    rows, NARROW_UPDATE_COLS if narrow_update else FULL_UPDATE_COLS,
                    dry_run)
                out["fetched"] += len(items)
                out["pages"] += 1
                if len(items) < TAKE:
                    break
                skip += TAKE
                time.sleep(PAUSE_S)
        return out

    # --- архив --------------------------------------------------------------

    async def sync_archive(self, token: str, ts_from: int, ts_to: int,
                           max_pages: int = 200, dry_run: bool = False,
                           progress=None) -> dict:
        """GET /api/v1/feedbacks/archive — фильтр по дате локально, стоп по dateFrom."""
        out = {"fetched": 0, "saved": 0, "pages": 0, "stopped_by_date": False}
        skip = 0
        while out["pages"] < max(1, int(max_pages or 1)):
            params = [("take", TAKE), ("skip", skip), ("order", "dateDesc")]
            data = get_json(ARCHIVE_URL, params, token, timeout=TIMEOUT_S)
            body = (data if isinstance(data, dict) else {}).get("data") or {}
            items = body.get("feedbacks") or []
            if progress:
                progress("archive", f"skip={skip}", len(items))
            if not items:
                break
            out["pages"] += 1
            now = int(time.time())
            rows, stop = [], False
            for it in items:
                ts = parse_ts(it.get("createdDate"))
                if ts is None:
                    continue
                if ts > ts_to:
                    continue
                if ts < ts_from:
                    stop = True
                    continue
                r = map_row(it, self.company_id, True, now)
                if r:
                    rows.append(r)
            out["saved"] += await self._upsert(rows, FULL_UPDATE_COLS, dry_run)
            out["fetched"] += len(items)
            if stop or len(items) < TAKE:
                out["stopped_by_date"] = stop
                break
            skip += TAKE
            time.sleep(PAUSE_S)
        return out

    # --- основной -----------------------------------------------------------

    async def sync(self, date_from=None, date_to=None, include_current: bool = True,
                   include_archive: bool = True, narrow_update: bool = False,
                   max_archive_pages: int = 200, dry_run: bool = False,
                   progress=None) -> dict:
        """Полный прогон одной компании: гейт токена → current (+ archive)."""
        # chunks=1 → оценка времени для basic-токена нулевая (гейт только по категории).
        plan = await company_sync_plan(self.db, self.company_id, "feedbacks", 1)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token = plan["token"]
        ts_from, ts_to = day_bounds(date_from, date_to)
        out = {"company_id": self.company_id, "from": date_from, "to": date_to,
               "dry_run": dry_run, "token_type": plan["token_type"]}
        if include_current:
            out["current"] = await self.sync_current(
                token, ts_from, ts_to, narrow_update, dry_run, progress)
        if include_archive:
            out["archive"] = await self.sync_archive(
                token, ts_from, ts_to, max_archive_pages, dry_run, progress)
        if plan.get("warning"):
            out["warning"] = plan["warning"]
        return out
