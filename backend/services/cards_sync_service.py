"""Карточки WB: content cards/list -> wbcards (+history/nds/sizes/subjects).

Порт WbController::actionSyncCards + actionSyncNds + backfillCardSizes + syncSubjects
(A1+A2+A3+A4 одной связкой): cursor-пагинация limit=100 -> upsert карточки ->
история изменений tracked-полей -> деактивация пропавших (last_seen_at + нет
заказов 30д) -> НДС из characteristics (только изменения) -> развёртка sizes ->
предметы (CommissionTariffsService, глобальные).
Токен — companies.api_key (категория content), гейт — wb_sync_base.
Пауз между страницами в PHP нет (только 429→65с) — так же. Только stdlib.
"""
import json
import time
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, post_json

CARDS_URL = "https://content-api.wildberries.ru/content/v2/get/cards/list"
TIMEOUT_S = 15
PAGE_LIMIT = 100

TRACKED = ("title", "description", "photos", "video", "dimensions",
           "characteristics", "sizes", "tags", "subjectName", "brand", "vendorCode")


def _js(v):
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def _de2(raw):
    """JSON двойного кодирования (как sizes/characteristics) -> list/dict."""
    if raw is None:
        return []
    v = raw
    for _ in range(3):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                try:
                    v = json.loads(v.replace("\\\"", "\""))
                except ValueError:
                    return []
        else:
            break
    return v if isinstance(v, (list, dict)) else []


class CardsSyncService:
    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync_list(self, dry_run: bool = False, progress=None) -> dict:
        plan = await company_sync_plan(
            self.db, self.company_id, "content", 1,
            pause_fast_s=0, pause_slow_s=0)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        auth = f"Bearer {plan['token']}"
        started = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        cur_at, cur_nm, fetched, failed = None, None, 0, False
        pages = 0
        while True:
            cursor = {"limit": PAGE_LIMIT}
            if cur_at is not None and cur_nm is not None:
                cursor["updatedAt"], cursor["nmID"] = cur_at, cur_nm
            try:
                data = post_json(CARDS_URL, {
                    "settings": {"sort": {"ascending": True},
                                 "filter": {"withPhoto": -1}, "cursor": cursor},
                }, auth, timeout=TIMEOUT_S)
            except Exception as e:
                if progress:
                    progress("retry", 0, 0, str(e))
                failed = True
                break
            cards = (data or {}).get("cards") or []
            cur = (data or {}).get("cursor") or {}
            if not cards:
                break
            fetched += len(cards)
            pages += 1
            if not dry_run:
                for c in cards:
                    await self._save_card(c, started)
            if progress:
                progress("phase", pages, 0, f"cards: {fetched}")
            total = int(cur.get("total") or 0)
            if total < PAGE_LIMIT or len(cards) < PAGE_LIMIT:
                break
            cur_at, cur_nm = cur.get("updatedAt"), cur.get("nmID")
            if cur_at is None or cur_nm is None:
                break
        deact = 0 if (dry_run or failed) else await self._deactivate(started)
        return {"company_id": self.company_id, "fetched": fetched,
                "deactivated": deact, "failed": failed,
                "token_type": plan["token_type"], "dry_run": dry_run}

    async def _save_card(self, card: dict, now: str) -> None:
        nm = card.get("nmID")
        if not nm:
            return
        try:
            nm = int(nm)
        except (TypeError, ValueError):
            return
        photos = []
        for p in (card.get("photos") or []):
            if isinstance(p, dict):
                u = p.get("big") or p.get("c246x328") or p.get("url")
                if u:
                    photos.append(u)
        cols = {
            "cid": self.company_id, "nm": nm,
            "imt": card.get("imtID"), "uuid": str(card.get("nmUUID") or "")[:64],
            "sid": card.get("subjectID"), "snm": card.get("subjectName"),
            "vc": card.get("vendorCode"), "br": card.get("brand"),
            "ti": card.get("title"), "de": card.get("description"),
            "ph": _js(photos), "vi": card.get("video"),
            "di": _js(card.get("dimensions")) if card.get("dimensions") is not None else None,
            "ch": _js(card.get("characteristics")) if card.get("characteristics") is not None else None,
            "sz": _js(card.get("sizes")) if card.get("sizes") is not None else None,
            "tg": _js(card.get("tags")) if card.get("tags") is not None else None,
            "now": now,
        }
        old = (await self.db.execute(text(
            "SELECT is_active, " + ", ".join(TRACKED) +
            " FROM wbcards WHERE company_id = :cid AND nmID = :nm"),
            {"cid": self.company_id, "nm": nm})).mappings().first()
        hist = []
        if old is None:
            hist.append({"cid": self.company_id, "nm": nm, "f": "_created",
                         "o": None, "n": None, "now": now})
        else:
            new_vals = {"title": cols["ti"], "description": cols["de"], "photos": cols["ph"],
                        "video": cols["vi"], "dimensions": cols["di"],
                        "characteristics": cols["ch"], "sizes": cols["sz"],
                        "tags": cols["tg"], "subjectName": cols["snm"],
                        "brand": cols["br"], "vendorCode": cols["vc"]}
            for f in TRACKED:
                if str(old.get(f) or "") != str(new_vals.get(f) or ""):
                    hist.append({"cid": self.company_id, "nm": nm, "f": f,
                                 "o": str(old.get(f))[:65535] if old.get(f) is not None else None,
                                 "n": str(new_vals.get(f))[:65535] if new_vals.get(f) is not None else None,
                                 "now": now})
            if int(old.get("is_active") or 1) == 0:
                hist.append({"cid": self.company_id, "nm": nm, "f": "is_active",
                             "o": "0", "n": "1", "now": now})
        if hist:
            await self.db.execute(text("""
                INSERT INTO wbcards_history(company_id, nmID, field, old_value, new_value, changed_at)
                VALUES(:cid, :nm, :f, :o, :n, :now)"""), hist)
        await self.db.execute(text("""
            INSERT INTO wbcards(company_id, nmID, imtID, nmUUID, subjectID, subjectName,
                vendorCode, brand, title, description, photos, video, dimensions,
                characteristics, sizes, tags, last_seen_at, is_active)
            VALUES(:cid, :nm, :imt, :uuid, :sid, :snm, :vc, :br, :ti, :de,
                :ph, :vi, :di, :ch, :sz, :tg, :now, 1) AS new
            ON DUPLICATE KEY UPDATE
                imtID = new.imtID, nmUUID = new.nmUUID, subjectID = new.subjectID,
                subjectName = new.subjectName, vendorCode = new.vendorCode,
                brand = new.brand, title = new.title, description = new.description,
                photos = new.photos, video = new.video, dimensions = new.dimensions,
                characteristics = new.characteristics, sizes = new.sizes,
                tags = new.tags, last_seen_at = new.last_seen_at, is_active = new.is_active"""), cols)
        await self._sync_sizes(nm, card.get("sizes"))
        await self.db.commit()

    async def _sync_sizes(self, nm: int, raw) -> int:
        await self.db.execute(
            text("DELETE FROM wbcards_sizes WHERE nmID = :nm"), {"nm": nm})
        rows = []
        for s in (_de2(raw) or []):
            if not isinstance(s, dict) or s.get("chrtID") is None:
                continue
            try:
                ch = int(s["chrtID"])
            except (TypeError, ValueError):
                continue
            for sku in (s.get("skus") or []):
                sku = str(sku).strip()
                if sku:
                    rows.append({"nm": nm, "ch": ch,
                                 "ts": str(s.get("techSize") or ""),
                                 "ws": str(s.get("wbSize") or ""), "sku": sku})
        if rows:
            await self.db.execute(text("""
                INSERT IGNORE INTO wbcards_sizes(nmID, chrtID, techSize, wbSize, sku)
                VALUES(:nm, :ch, :ts, :ws, :sku)"""), rows)
        return len(rows)

    async def _deactivate(self, started: str) -> int:
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        await self.db.execute(text("""
            INSERT INTO wbcards_history (company_id, nmID, field, old_value, new_value, changed_at)
            SELECT company_id, nmID, 'is_active', '1', '0', :now
            FROM wbcards w
            WHERE w.company_id = :cid AND w.is_active = 1 AND w.last_seen_at < :st
              AND NOT EXISTS (SELECT 1 FROM wb_order o
                              WHERE o.nm_id = w.nmID AND o.date >= :cut)"""),
            {"now": started, "cid": self.company_id, "st": started, "cut": cutoff})
        r = await self.db.execute(text("""
            UPDATE wbcards w SET w.is_active = 0
            WHERE w.company_id = :cid AND w.is_active = 1 AND w.last_seen_at < :st
              AND NOT EXISTS (SELECT 1 FROM wb_order o
                              WHERE o.nm_id = w.nmID AND o.date >= :cut)"""),
            {"cid": self.company_id, "st": started, "cut": cutoff})
        await self.db.commit()
        return r.rowcount or 0

    async def sync_nds(self, dry_run: bool = False) -> dict:
        """НДС из characteristics (только изменения). Без API."""
        today = datetime.now().strftime("%Y-%m-%d")
        last, proc, upd = 0, 0, 0
        while True:
            cards = (await self.db.execute(text("""
                SELECT nmID, characteristics FROM wbcards
                WHERE company_id = :cid AND nmID > :last
                ORDER BY nmID LIMIT 500"""),
                {"cid": self.company_id, "last": last})).all()
            if not cards:
                break
            for nm, raw in cards:
                last = int(nm)
                proc += 1
                val = None
                for ch in (_de2(raw) or []):
                    if isinstance(ch, dict) and str(ch.get("name") or "").strip() == "Ставка НДС":
                        v = ch.get("value")
                        val = v[0] if isinstance(v, list) and v else v
                        break
                if val is None or str(val) == "":
                    continue
                try:
                    cur = float(val)
                except (TypeError, ValueError):
                    continue
                prev = (await self.db.execute(text("""
                    SELECT nds FROM wbcards_nds WHERE nmID = :nm
                    ORDER BY id DESC LIMIT 1"""), {"nm": last})).scalar()
                if prev is None or float(prev) != cur:
                    if not dry_run:
                        await self.db.execute(text("""
                            INSERT INTO wbcards_nds(load_date, nmID, nds)
                            VALUES(:d, :nm, :nds)"""),
                            {"d": today, "nm": last, "nds": cur})
                    upd += 1
            if not dry_run:
                await self.db.commit()
        return {"company_id": self.company_id, "processed": proc,
                "updated": 0 if dry_run else upd, "dry_run": dry_run}

    async def sync_sizes_backfill(self) -> dict:
        """Развёртка sizes всех карточек (бэкфилл). Без API."""
        last, done, ins = 0, 0, 0
        while True:
            rows = (await self.db.execute(text("""
                SELECT nmID, sizes FROM wbcards
                WHERE company_id = :cid AND nmID > :last
                ORDER BY nmID LIMIT 500"""),
                {"cid": self.company_id, "last": last})).all()
            if not rows:
                break
            for nm, raw in rows:
                last = int(nm)
                done += 1
                try:
                    ins += await self._sync_sizes(last, raw)
                except Exception:
                    pass
            await self.db.commit()
        return {"company_id": self.company_id, "cards": done, "skus": ins}
