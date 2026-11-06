"""Рекомендуемые ставки WB (GET /api/advert/v0/bids/recommendations).

Метод отдаёт рекомендации для ОДНОЙ пары (кампания, карточка) за запрос,
интервал между запросами — 12 с (личный/сервисный токен, 5 запросов в минуту).
Допустим только персональный/сервисный токен.

Ответ (CPM):
  {advertId, nmId,
   base: {competitiveBid:{bidKopecks}, leadersBid:{bidKopecks}, top2:{bidKopecks}},
   normQueries: [{normQuery,
                  reachMin:{bidKopecks, bidKopecksMin},
                  reachMedium:{...}, reachMax:{...}}]}

Ответ (CPC, с 2026-09) отличается: вместо normQueries приходит `levels`
(рекомендации по диапазонам позиций). Его мы сохраняем целиком в raw_json —
разбор отложим до появления экрана.

Таблица: wb_adv_bid_recommendation.
"""
import json
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json

REC_URL = "https://advert-api.wildberries.ru/api/advert/v0/bids/recommendations"
PAUSE_S = 12.0
TIMEOUT_S = 20
PAIRS_DAYS = 30         # окно, за которое берём карточки из статистики
MAX_REQS = 60           # запросов за прогон (12 с каждый -> 12 мин); остальное — в следующих
PERSONAL_TYPES = ("personal", "service")


def _kop(obj) -> int | None:
    """Достать bidKopecks из объекта вида {bidKopecks: N}."""
    if not isinstance(obj, dict):
        return None
    v = obj.get("bidKopecks")
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _kop_min(obj) -> int | None:
    """Достать bidKopecksMin (минимальная ставка WB) из объекта reach*."""
    if not isinstance(obj, dict):
        return None
    v = obj.get("bidKopecksMin")
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _pick(d, *names, default=None):
    """Взять поле по любому из вариантов написания (camelCase и snake_case)."""
    if not isinstance(d, dict):
        return default
    for n in names:
        v = d.get(n)
        if v is not None:
            return v
    return default


class AdvBidRecService:
    """Снимает рекомендации WB по кампаниям и карточкам."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def _pairs(self) -> list[tuple[int, int]]:
        """Пары (кампания, карточка), реально участвующие в рекламе.

        Источник — wb_campaign_stats_nms, а не wb_campaign_item: в item по
        одной карточке на кампанию, а в рекламе крутятся десятки (на
        staging разница была 21 пара против 1409 за 30 дней).

        Порядок — «кругом»: сначала пары, по которым рекомендаций ещё нет,
        потом самые старые (по updated_at рекомендации). Так за несколько
        прогонов обходим все карточки.
        """
        rows = (await self.db.execute(text(f"""
            SELECT s.campaign_id, n.nm_id
            FROM wb_campaign_stats s
            JOIN wb_campaign_stats_nms n
              ON n.parent_id = s.id AND n.company_id = s.company_id
            JOIN wb_campaign c ON c.campaign_id = s.campaign_id
              AND c.company_id = :cid
            LEFT JOIN wb_adv_bid_recommendation r
              ON r.company_id = n.company_id
             AND r.campaign_id = s.campaign_id
             AND r.nm_id = n.nm_id
             AND r.scope = 'base'
            WHERE s.company_id = :cid AND n.nm_id > 0 AND c.status IN (9, 11)
              AND s.date >= DATE_SUB(CURDATE(), INTERVAL {PAIRS_DAYS} DAY)
            GROUP BY s.campaign_id, n.nm_id
            ORDER BY (MAX(r.updated_at) IS NULL) DESC, MAX(r.updated_at) ASC,
                     s.campaign_id, n.nm_id"""),
            {"cid": self.company_id})).all()
        return [(int(r[0]), int(r[1])) for r in rows if r[0] and r[1]]

    async def _token(self) -> str | None:
        row = (await self.db.execute(text(
            "SELECT token_type FROM company_wb_tokens"
            " WHERE company_id = :c AND is_active = 1 LIMIT 1"),
            {"c": self.company_id})).first()
        ttype = (row[0] or "") if row else ""
        return ttype if ttype in PERSONAL_TYPES else None

    async def sync(self, dry_run: bool = False, max_pairs: int | None = None,
                   progress=None) -> dict:
        """Снимает рекомендации. max_pairs ограничивает число пар за прогон."""
        if not await self._token():
            return {"company_id": self.company_id,
                    "skipped": "bids/recommendations доступен только на personal/service токене",
                    "dry_run": dry_run}
        pairs = await self._pairs()
        limit = max_pairs or MAX_REQS
        pairs = pairs[:limit]
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion", len(pairs),
            pause_fast_s=PAUSE_S, pause_slow_s=3600)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token = plan["token"]
        rows: list[dict] = []
        raw_rows: list[dict] = []
        errors = 0
        if progress and pairs:
            progress("phase", 0, len(pairs),
                     f"рекомендации: {len(pairs)} пар, между запросами пауза "
                     f"{PAUSE_S:.0f} с — ориентировочно {len(pairs) * PAUSE_S / 60:.1f} мин")
        for i, (cid, nm) in enumerate(pairs, 1):
            try:
                data = get_json(REC_URL, [("advertId", cid), ("nmId", nm)],
                                token, timeout=TIMEOUT_S)
            except RuntimeError as e:
                errors += 1
                if progress:
                    progress("retry", i, len(pairs), f"{cid}/{nm}: {e}")
                continue
            if not isinstance(data, dict):
                continue
            base = _pick(data, "base", default={}) or {}
            rows.append({
                "cid": self.company_id, "c": cid, "nm": nm, "sc": "base", "q": "",
                "min": None, "med": None, "max": None, "minlim": None,
                "comp": _kop(_pick(base, "competitiveBid", "competitive_bid")),
                "lead": _kop(_pick(base, "leadersBid", "leaders_bid")),
                "top2": _kop(_pick(base, "top2")),
                "raw": None,
            })
            for nq in (_pick(data, "normQueries", "norm_queries", default=[]) or []):
                q = str(_pick(nq, "normQuery", "norm_query", default="") or "").strip()
                if not q:
                    continue
                rmin = _pick(nq, "reachMin", "reach_min", default={}) or {}
                rmed = _pick(nq, "reachMedium", "reach_medium", default={}) or {}
                rmax = _pick(nq, "reachMax", "reach_max", default={}) or {}
                rows.append({
                    "cid": self.company_id, "c": cid, "nm": nm, "sc": "cluster",
                    "q": q[:255],
                    "min": _kop(rmin), "med": _kop(rmed), "max": _kop(rmax),
                    "minlim": _kop_min(rmin),
                    "comp": None, "lead": None, "top2": None, "raw": None,
                })
            if _pick(data, "levels") is not None:
                raw_rows.append({
                    "cid": self.company_id, "c": cid, "nm": nm,
                    "raw": json.dumps(data, ensure_ascii=False)[:60000],
                })
            if progress:
                progress("phase", i, len(pairs), f"рекомендации {i}/{len(pairs)}")
            if i < len(pairs):
                time.sleep(PAUSE_S)
        if not dry_run and (rows or raw_rows):
            if rows:
                await self.db.execute(text("""
                    INSERT INTO wb_adv_bid_recommendation(company_id, campaign_id, nm_id,
                        scope, norm_query, min_kopecks, medium_kopecks, max_kopecks,
                        min_limit_kopecks, competitive_kopecks, leaders_kopecks, top2_kopecks)
                    VALUES(:cid, :c, :nm, :sc, :q, :min, :med, :max, :minlim,
                           :comp, :lead, :top2) AS new
                    ON DUPLICATE KEY UPDATE
                        min_kopecks = new.min_kopecks, medium_kopecks = new.medium_kopecks,
                        max_kopecks = new.max_kopecks,
                        min_limit_kopecks = new.min_limit_kopecks,
                        competitive_kopecks = new.competitive_kopecks,
                        leaders_kopecks = new.leaders_kopecks,
                        top2_kopecks = new.top2_kopecks"""), rows)
            if raw_rows:
                await self.db.execute(text("""
                    INSERT INTO wb_adv_bid_recommendation(company_id, campaign_id, nm_id,
                        scope, norm_query, raw_json)
                    VALUES(:cid, :c, :nm, 'cpc', '', :raw) AS new
                    ON DUPLICATE KEY UPDATE raw_json = new.raw_json"""), raw_rows)
            await self.db.commit()
        if progress:
            progress("phase", len(pairs), len(pairs),
                     f"рекомендации: {len(rows)} строк, ошибок {errors}")
        return {"pairs": len(pairs), "rows": len(rows), "raw": len(raw_rows),
                "errors": errors, "dry_run": dry_run}
