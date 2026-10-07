"""Новости портала продавцов WB: communications/news -> wb_news.

Порт новый (крона не было). Новости глобальные: синк одним токеном
(доки WB — токен любой категории), фильтр типов — на чтении per-company
(companies.news_types). Пагинация fromID (включительно — overlap гасит upsert).
Только stdlib.
"""
import json
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import get_json

NEWS_URL = "https://common-api.wildberries.ru/api/communications/v2/news"
TIMEOUT_S = 15
PAGE_GUARD = 50  # стоп-кран пагинации


def _dt(v) -> str | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


class NewsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _token(self) -> tuple[str, int]:
        """Первая активная компания с живым токеном (не тест, не протух)."""
        rows = (await self.db.execute(text("""
            SELECT c.id, c.api_key, t.is_test, t.days_left
            FROM companies c LEFT JOIN company_wb_tokens t
              ON t.company_id = c.id AND t.is_active = 1
            WHERE c.is_active = 1 AND c.api_key IS NOT NULL AND c.api_key <> ''
            ORDER BY c.id"""))).mappings().all()
        fallback = None
        for r in rows:
            key = (r["api_key"] or "").strip()
            if not key:
                continue
            if r["is_test"]:
                continue
            if r["days_left"] is not None and int(r["days_left"]) < 0:
                continue
            if r["days_left"] is None and fallback is None:
                fallback = (key, int(r["id"]))  # нет строки проверки — про запас
                continue
            return key, int(r["id"])
        if fallback:
            return fallback
        raise RuntimeError("нет компании с живым токеном WB")

    async def sync(self, dry_run: bool = False, since: str | None = None,
                   progress=None) -> dict:
        token, cid = await self._token()
        if since:
            start = date.fromisoformat(since).isoformat()
        else:
            mx = (await self.db.execute(text("SELECT MAX(date) FROM wb_news"))).scalar()
            if mx:
                start = (mx - timedelta(days=1)).date().isoformat()
            else:
                start = (date.today() - timedelta(days=30)).isoformat()
        auth = f"Bearer {token}"
        from_id, total, pages = None, 0, 0
        min_d, max_d = None, None
        while pages < PAGE_GUARD:
            params = [("from", start)]
            if from_id is not None:
                params.append(("fromID", from_id))
            data = get_json(NEWS_URL, params, auth, timeout=TIMEOUT_S,
                            log=(lambda m: progress("retry", 0, 0, m)) if progress else None)
            items = (data or {}).get("data") or []
            if not items:
                break
            rows = [{"i": int(x["id"]), "d": _dt(x.get("date")),
                     "h": str(x.get("header") or "")[:500],
                     "c": x.get("content") or "",
                     "t": json.dumps([{"id": int(t.get("id")), "name": str(t.get("name") or "")}
                                      for t in (x.get("types") or []) if t.get("id")],
                                     ensure_ascii=False)}
                    for x in items if x.get("id") is not None]
            if rows and not dry_run:
                await self.db.execute(text("""
                    INSERT INTO wb_news(id, date, header, content, types, fetched_at)
                    VALUES(:i, :d, :h, :c, :t, NOW()) AS new
                    ON DUPLICATE KEY UPDATE
                        date = new.date, header = new.header,
                        content = new.content, types = new.types,
                        fetched_at = NOW()"""), rows)
                await self.db.commit()
            total += len(rows)
            pages += 1
            ds = [r["d"] for r in rows if r["d"]]
            if ds:
                min_d = min([d for d in [min_d, min(ds)] if d])
                max_d = max([d for d in [max_d, max(ds)] if d])
            new_max = max(int(x["id"]) for x in items)
            if progress:
                progress("phase", pages, 0, f"страница: новостей {len(rows)}")
            if new_max <= (from_id or 0):
                break
            from_id = new_max
        return {"via_company": cid, "pages": pages,
                "upserted": 0 if dry_run else total, "fetched": total,
                "min_date": min_d, "max_date": max_d, "dry_run": dry_run}

    def _type_filter(self, types_json, wanted: set[int] | None) -> list[dict]:
        try:
            ts = json.loads(types_json) if isinstance(types_json, str) else (types_json or [])
        except ValueError:
            ts = []
        if wanted is None:
            return ts
        return [t for t in ts if int(t.get("id", -1)) in wanted]

    async def _company_types(self, company_id: int | None) -> set[int] | None:
        if company_id is None:
            return None
        row = (await self.db.execute(
            text("SELECT news_types FROM companies WHERE id = :c"), {"c": company_id})).first()
        raw = row[0] if row else None
        if raw is None:
            return None
        try:
            ids = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            return None
        ids = [int(x) for x in (ids or []) if str(x).isdigit()]
        return set(ids) if ids else None

    async def _rows(self, where: str, params: dict, user_id: int | None,
                    company_id: int | None, limit: int) -> list[dict]:
        wanted = await self._company_types(company_id)
        q = (await self.db.execute(text(f"""
            SELECT n.id, n.date, n.header, n.content, n.types,
                   {'1' if user_id is None else 'r.news_id IS NOT NULL'} AS is_read
            FROM wb_news n
            {'LEFT JOIN wb_news_reads r ON r.news_id = n.id AND r.user_id = :uid' if user_id is not None else ''}
            WHERE {where} ORDER BY n.date DESC LIMIT :lim"""),
            {**params, **({"uid": user_id} if user_id is not None else {}),
             "lim": limit})).mappings().all()
        out = []
        for r in q:
            ts = self._type_filter(r["types"], None)
            if wanted is not None and not any(
                    int(t.get("id", -1)) in wanted for t in ts):
                continue
            d = dict(r)
            d["date"] = d["date"].isoformat() if hasattr(d.get("date"), "isoformat") else d.get("date")
            d["types"] = ts
            d["is_read"] = bool(d.get("is_read"))
            out.append(d)
        return out

    async def feed(self, user_id: int | None, company_id: int | None,
                   days: int = 3, limit: int = 12) -> list[dict]:
        return await self._rows("n.date >= DATE_SUB(NOW(), INTERVAL :days DAY)",
                                {"days": days}, user_id, company_id, limit)

    async def search(self, user_id: int | None, company_id: int | None,
                     date_from: str | None = None, date_to: str | None = None,
                     type_ids: list[int] | None = None, limit: int = 50,
                     q: str | None = None) -> list[dict]:
        cond, p = ["1 = 1"], {}
        if date_from:
            cond.append("n.date >= :df")
            p["df"] = date_from
        if date_to:
            cond.append("n.date < DATE_ADD(:dt, INTERVAL 1 DAY)")
            p["dt"] = date_to
        if q and q.strip():
            cond.append("(n.header LIKE :q OR n.content LIKE :q)")
            p["q"] = f"%{q.strip()[:80]}%"
        rows = await self._rows(" AND ".join(cond), p, user_id, company_id, 500)
        if type_ids:
            want = set(type_ids)
            rows = [r for r in rows if any(int(t.get("id", -1)) in want for t in r["types"])]
        return rows[:limit]

    async def type_list(self) -> list[dict]:
        rows = (await self.db.execute(
            text("SELECT types FROM wb_news ORDER BY date DESC LIMIT 500"))).all()
        seen: dict[int, str] = {}
        for r in rows:
            for t in self._type_filter(r[0], None):
                try:
                    seen.setdefault(int(t["id"]), str(t.get("name") or ""))
                except (TypeError, ValueError):
                    continue
        return [{"id": k, "name": v} for k, v in sorted(seen.items())]

    async def mark_read(self, user_id: int, news_id: int) -> dict:
        await self.db.execute(text("""
            INSERT IGNORE INTO wb_news_reads(user_id, news_id) VALUES(:u, :n)"""),
            {"u": user_id, "n": news_id})
        await self.db.commit()
        return {"ok": True}
