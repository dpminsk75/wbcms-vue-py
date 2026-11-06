"""Справочник рекламы: предметы и доступные карточки товаров.

Два метода WB (оба read-only, x-readonly-method: true):
  GET  /adv/v1/supplier/subjects?payment_type=cpm|cpc
       -> предметы, которые можно добавить в рекламную кампанию.
          Лимит: 1 запрос / 12 сек — поэтому ходим раз в сутки.
          Ответ: [{"id":…, "name":"3D очки", "count":1899}]
  POST /adv/v2/supplier/nms   (тело — МАССИВ ID предметов: [123, 456, …])
       -> карточки товаров, которые можно добавить в кампанию.
          Лимит: 5 запросов / мин, интервал 12 сек.
          Ответ: [{"title":"Плед", "nm":146168367, "subjectId":765}]

Таблицы: wb_adv_subject, wb_adv_supplier_nm.
"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.wb_sync_base import company_sync_plan, get_json, post_json

ADVERT = "https://advert-api.wildberries.ru"
SUBJECTS_URL = f"{ADVERT}/adv/v1/supplier/subjects"
NMS_URL = f"{ADVERT}/adv/v2/supplier/nms"

PAUSE_SUBJECTS_S = 12.0   # WB: 1 запрос / 12 с
PAUSE_NMS_S = 12.0        # WB: 5 запросов / мин, интервал 12 с
TIMEOUT_S = 30
MAX_SUBJECTS = 500        # больше не берём — предметов у продавца не бывает


def _pick(d, *names, default=None):
    """Взять поле по любому из вариантов написания (camelCase и snake_case)."""
    if not isinstance(d, dict):
        return default
    for n in names:
        v = d.get(n)
        if v is not None:
            return v
    return default


class AdvCatalogService:
    """Снимает предметы и список карточек, доступных для добавления в кампании."""

    def __init__(self, db: AsyncSession, company_id: int):
        self.db = db
        self.company_id = company_id

    async def sync(self, payment_type: str = "cpm", dry_run: bool = False,
                   progress=None) -> dict:
        """Предметы → доступные карточки. Один запрос на каждый метод."""
        plan = await company_sync_plan(
            self.db, self.company_id, "promotion", 2,
            pause_fast_s=PAUSE_SUBJECTS_S, pause_slow_s=1800)
        if plan.get("skip"):
            return {"company_id": self.company_id, "skipped": plan["skip"],
                    "token_type": plan.get("token_type"), "dry_run": dry_run}
        token = plan["token"]
        out = {"company_id": self.company_id, "payment_type": payment_type,
               "token_type": plan.get("token_type"), "dry_run": dry_run}

        subjects = await self._sync_subjects(token, payment_type, dry_run, progress)
        out["subjects"] = len(subjects)
        if subjects:
            out["cards"] = await self._sync_nms(token, subjects, dry_run, progress)
        else:
            out["cards"] = 0
        return out

    async def _sync_subjects(self, token: str, payment_type: str,
                              dry_run: bool, progress=None) -> list[dict]:
        """GET /adv/v1/supplier/subjects — предметы для добавления в кампанию."""
        data = get_json(SUBJECTS_URL, [("payment_type", payment_type)],
                        token, timeout=TIMEOUT_S)
        rows = []
        for s in (data if isinstance(data, list) else []):
            try:
                sid = int(_pick(s, "id", "subject_id"))
            except (TypeError, ValueError):
                continue
            rows.append({
                "cid": self.company_id, "sid": sid,
                "name": str(_pick(s, "name", default="") or "")[:255],
                "cnt": int(_pick(s, "count", default=0) or 0),
                "pt": payment_type,
            })
        rows = rows[:MAX_SUBJECTS]
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_subject(company_id, subject_id, name, nm_count, payment_type)
                VALUES(:cid, :sid, :name, :cnt, :pt) AS new
                ON DUPLICATE KEY UPDATE
                    name = new.name, nm_count = new.nm_count"""), rows)
            await self.db.commit()
        if progress:
            progress("phase", 1, 1, f"subjects: {len(rows)} предметов")
        return rows

    async def _sync_nms(self, token: str, subjects: list[dict],
                        dry_run: bool, progress=None) -> int:
        """POST /adv/v2/supplier/nms — карточки, доступные для добавления.

        Тело — МАССИВ ID предметов (не объект!), поэтому хватает одного запроса.
        """
        sids = [s["sid"] for s in subjects]
        if not sids:
            return 0
        data = post_json(NMS_URL, sids, token, timeout=TIMEOUT_S)
        rows = []
        for it in (data if isinstance(data, list) else []):
            try:
                nm = int(_pick(it, "nm", "nmId", "nm_id"))
            except (TypeError, ValueError):
                continue
            rows.append({
                "cid": self.company_id, "nm": nm,
                "sid": int(_pick(it, "subjectId", "subject_id", default=0) or 0),
                "title": str(_pick(it, "title", default="") or "")[:255],
            })
        if rows and not dry_run:
            await self.db.execute(text("""
                INSERT INTO wb_adv_supplier_nm(company_id, nm_id, subject_id, title)
                VALUES(:cid, :nm, :sid, :title) AS new
                ON DUPLICATE KEY UPDATE
                    subject_id = new.subject_id, title = new.title"""), rows)
            await self.db.commit()
        if progress:
            progress("phase", 1, 1, f"supplier/nms: {len(rows)} карточек")
        time.sleep(PAUSE_NMS_S)
        return len(rows)
