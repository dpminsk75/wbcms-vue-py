"""Настройки налогов компании (company_tax_settings) + покрытие НДС по карточкам.

Ключевые решения (зафиксированы владельцем 2026-11-06):
  * НДС НЕ хранится как одна ставка компании. Он заложен в товаре и лежит
    в wbcards_nds (nmID + load_date -> nds). Берём ставку карточки на дату
    операции: последняя запись с load_date <= sdate.
  * company_tax_settings хранит только режим и ставку ОСНОВНОГО налога
    (УСН/АУСН/ОСНО), версии по датам (valid_from/valid_to) и аудит.
  * Если по карточке ставки нет — это NDS_MISSING, а не «0 по умолчанию».
  * Готовый отчёт (Dashboard, /wb-profit, /wb/detail) НЕ трогаем: модуль
    только сохраняет правила и считает «живой пример» отдельно.

Источники: wbcards (карточки компании), wbcards_nds (ставки НДС по карточкам),
agg_daily_summary (дневные деньги по nm), marketing_expense_lines (ручной маркетинг).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.marketing_service import allocate_days

log = logging.getLogger("wbcms.tax_settings")

MODES = ("none", "income", "profit", "osno")
VAT_SOURCES = ("cards", "none")

MODE_LABELS = {
    "none": "Не считать налог",
    "income": "УСН «Доходы» / АУСН",
    "profit": "УСН «Доходы − расходы»",
    "osno": "ОСНО",
}

# Пределы предпросмотра (защита от случайного тяжёлого запроса).
PREVIEW_MAX_DAYS = 62
PREVIEW_MAX_ROWS = 60_000
# Сессионные лимиты MySQL для предпросмотра (глобальные настройки НЕ трогаем).
PREVIEW_SESSION_LIMITS = [
    "SET SESSION max_execution_time = 20000",
    "SET SESSION temptable_max_ram = 67108864",
    "SET SESSION tmp_table_size = 33554432",
    "SET SESSION max_heap_table_size = 33554432",
    "SET SESSION sort_buffer_size = 1048576",
]


class TaxSettingsError(Exception):
    """Ошибка валидации настроек налога."""


class TaxSettingsService:
    def __init__(self, db: AsyncSession, company_id: int | None = None,
                 user_id: int | None = None):
        self.db = db
        self.company_id = company_id
        self.user_id = user_id

    # ---------------------------------------------------------------- utils
    def _need_company(self) -> int:
        if self.company_id is None:
            raise TaxSettingsError("company_id is required")
        return self.company_id

    @staticmethod
    def _d(value, field: str) -> str:
        s = str(value or "").strip()
        if not s:
            raise TaxSettingsError(f"{field}: не заполнено")
        try:
            return date.fromisoformat(s[:10]).isoformat()
        except ValueError:
            raise TaxSettingsError(f"{field}: ожидается дата в формате YYYY-MM-DD")

    @staticmethod
    def _rate(value, field: str) -> float:
        if value is None or value == "":
            return 0.0
        try:
            r = float(str(value).replace(",", ".").replace("%", "").strip())
        except (TypeError, ValueError):
            raise TaxSettingsError(f"{field}: ставка должна быть числом")
        if r < 0 or r > 100:
            raise TaxSettingsError(f"{field}: ставка вне диапазона 0..100")
        return round(r, 4)

    # -------------------------------------------------------------- версии
    async def list_versions(self) -> list[dict]:
        cid = self._need_company()
        rows = (await self.db.execute(text("""
            SELECT s.id, s.company_id, s.valid_from, s.valid_to, s.mode, s.main_rate,
                   s.vat_source, s.profit_rate, s.reason,
                   s.created_by, s.updated_by, s.created_at, s.updated_at,
                   u.username AS created_by_name
            FROM company_tax_settings s
            LEFT JOIN `user` u ON u.id = s.created_by
            WHERE s.company_id = :cid
            ORDER BY s.valid_from DESC, s.id DESC"""),
            {"cid": cid})).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["mode_label"] = MODE_LABELS.get(d.get("mode") or "", d.get("mode"))
            d["valid_from"] = str(d.get("valid_from") or "")[:10]
            d["valid_to"] = str(d.get("valid_to") or "")[:10] or None
            d["main_rate"] = float(d.get("main_rate") or 0)
            d["profit_rate"] = float(d["profit_rate"]) if d.get("profit_rate") is not None else None
            d["is_current"] = (d["valid_from"] <= date.today().isoformat()
                               and (not d["valid_to"] or d["valid_to"] >= date.today().isoformat()))
            out.append(d)
        return out

    async def current(self, on_date: str | None = None) -> dict | None:
        cid = self._need_company()
        d = self._d(on_date or date.today().isoformat(), "дата")
        row = (await self.db.execute(text("""
            SELECT s.id, s.valid_from, s.valid_to, s.mode, s.main_rate, s.vat_source,
                   s.profit_rate, s.reason, s.created_at
            FROM company_tax_settings s
            WHERE s.company_id = :cid AND s.valid_from <= :d
              AND (s.valid_to IS NULL OR s.valid_to >= :d)
            ORDER BY s.valid_from DESC LIMIT 1"""),
            {"cid": cid, "d": d})).mappings().first()
        if not row:
            return None
        out = dict(row)
        out["mode_label"] = MODE_LABELS.get(out.get("mode") or "", out.get("mode"))
        out["main_rate"] = float(out.get("main_rate") or 0)
        out["profit_rate"] = float(out["profit_rate"]) if out.get("profit_rate") is not None else None
        out["valid_from"] = str(out.get("valid_from") or "")[:10]
        out["valid_to"] = str(out.get("valid_to") or "")[:10] or None
        return out

    async def create_version(self, data: dict) -> dict:
        """Новая версия настроек. Старая закрывается, история не переписывается."""
        cid = self._need_company()
        mode = str(data.get("mode") or "").strip().lower()
        if mode not in MODES:
            raise TaxSettingsError(f"mode: допустимо {', '.join(MODES)}")
        vat_source = str(data.get("vat_source") or "cards").strip().lower()
        if vat_source not in VAT_SOURCES:
            raise TaxSettingsError(f"vat_source: допустимо {', '.join(VAT_SOURCES)}")
        valid_from = self._d(data.get("valid_from"), "valid_from")
        main_rate = self._rate(data.get("main_rate"), "main_rate")
        profit_rate = None
        if mode == "osno":
            # Ставка налога одна: для ОСНО это ставка налога на прибыль.
            profit_rate = main_rate
            if profit_rate <= 0:
                raise TaxSettingsError("main_rate: для ОСНО нужна ставка налога на прибыль")
        elif mode == "none":
            main_rate = 0.0
        reason = str(data.get("reason") or "").strip()
        if not reason:
            raise TaxSettingsError("reason: укажите причину изменения (попадёт в историю)")

        # такой же valid_from уже есть — конфликт версий
        dup = (await self.db.execute(text(
            "SELECT id FROM company_tax_settings WHERE company_id=:cid AND valid_from=:d LIMIT 1"),
            {"cid": cid, "d": valid_from})).scalar()
        if dup:
            raise TaxSettingsError("на эту дату версия уже создана — выберите другую дату")

        prev_day = (date.fromisoformat(valid_from) - timedelta(days=1)).isoformat()
        await self.db.execute(text("""
            UPDATE company_tax_settings
            SET valid_to = :prev, updated_at = NOW()
            WHERE company_id = :cid AND valid_to IS NULL AND valid_from < :d"""),
            {"cid": cid, "prev": prev_day, "d": valid_from})
        await self.db.execute(text("""
            INSERT INTO company_tax_settings
              (company_id, valid_from, valid_to, mode, main_rate, vat_source,
               profit_rate, reason, created_by, updated_by)
            VALUES (:cid, :d, NULL, :mode, :rate, :vat, :profit, :reason, :uid, :uid)"""),
            {"cid": cid, "d": valid_from, "mode": mode, "rate": main_rate,
             "vat": vat_source, "profit": profit_rate, "reason": reason,
             "uid": self.user_id})
        await self.db.commit()
        return {"ok": True, "valid_from": valid_from, "closed_previous_to": prev_day}

    # -------------------------------------------------------- покрытие НДС
    async def nds_coverage(self) -> dict:
        """Сколько карточек компании имеют ставку НДС, а сколько — нет.

        Форма запросов — ровно как в nds_missing_cards (та отработала на проде):
        полу-джойн через NOT EXISTS по индексу nmID. Без GROUP BY по всей
        истории wbcards_nds (тяжёлый GROUP BY запрещён AGENTS.md §3) и без
        коррелированного ORDER BY на каждую карточку — на проде это уходило
        в таймаут и давало 500.

        Распределение ставок не считаем: полная история wbcards_nds — тяжёлый
        GROUP BY, а справочной ценности у него нет. Если понадобится — отдельной
        отложенной задачей по последнему срезу.
        """
        cid = self._need_company()
        try:
            total = int((await self.db.execute(text(
                "SELECT COUNT(*) FROM wbcards WHERE company_id = :cid AND is_active = 1"),
                {"cid": cid})).scalar() or 0)
            missing = int((await self.db.execute(text("""
                SELECT COUNT(*) FROM wbcards c
                WHERE c.company_id = :cid AND c.is_active = 1
                  AND NOT EXISTS (SELECT 1 FROM wbcards_nds n WHERE n.nmID = c.nmID)"""),
                {"cid": cid})).scalar() or 0)
        except Exception as e:
            log.exception("nds_coverage: счётчики покрытия НДС не прочитаны")
            raise TaxSettingsError(f"не удалось посчитать покрытие НДС ({e})")
        # Дата последнего среза — справочно: при ошибке не роняем весь ответ.
        last = None
        try:
            last = (await self.db.execute(text(
                "SELECT MAX(load_date) FROM wbcards_nds"))).scalar()
        except Exception as e:
            log.warning("nds_coverage: дата последнего среза НДС не прочитана: %s", e)
        return {
            "total": total,
            "with_rate": max(0, total - missing),
            "missing": missing,
            "last_load_date": str(last)[:10] if last else None,
        }

    async def nds_missing_cards(self, q: str = "", limit: int = 200) -> list[dict]:
        """Карточки компании без ставки НДС (для выгрузки в Excel)."""
        cid = self._need_company()
        limit = max(1, min(int(limit or 200), 1000))
        params: dict = {"cid": cid, "lim": limit}
        where = ""
        if q:
            where = " AND (c.vendorCode LIKE :q OR c.title LIKE :q OR CAST(c.nmID AS CHAR) LIKE :q)"
            params["q"] = f"%{q.strip()}%"
        rows = (await self.db.execute(text(f"""
            SELECT c.nmID, c.vendorCode, c.title
            FROM wbcards c
            WHERE c.company_id = :cid AND c.is_active = 1
              AND NOT EXISTS (SELECT 1 FROM wbcards_nds n WHERE n.nmID = c.nmID){where}
            ORDER BY c.nmID LIMIT :lim"""), params)).mappings().all()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------- пример
    async def preview(self, date_from: str, date_to: str,
                      mode: str | None = None,
                      main_rate: float | None = None,
                      vat_source: str | None = None) -> dict:
        """Живой пример расчёта: продажи → НДС по карточкам → налог.

        Ничего не пишет в отчёты. Считает по agg_daily_summary (готовая витрина)
        и wbcards_nds (ставка карточки на дату).
        """
        cid = self._need_company()
        d1 = self._d(date_from, "date_from")
        d2 = self._d(date_to, "date_to")
        if d1 > d2:
            raise TaxSettingsError("date_from позже date_to")
        days = (date.fromisoformat(d2) - date.fromisoformat(d1)).days + 1
        if days > PREVIEW_MAX_DAYS:
            raise TaxSettingsError(f"период длиннее {PREVIEW_MAX_DAYS} дней — считайте по частям")

        cur = await self.current(d1)
        if cur is None:
            raise TaxSettingsError("для выбранной даты нет настроек налога — создайте версию")
        use_mode = (mode or cur["mode"] or "none").strip().lower()
        if use_mode not in MODES:
            raise TaxSettingsError("mode: неизвестный режим")
        if main_rate is None:
            use_rate = float(cur.get("main_rate") or 0)
        else:
            use_rate = self._rate(main_rate, "main_rate")
        if use_mode == "osno" and main_rate is None:
            # ОСНО: ставка на прибыль хранится в profit_rate (заполняется из main_rate).
            use_rate = float(cur.get("profit_rate") or 0)
        use_vat = (vat_source or cur.get("vat_source") or "cards").strip().lower()
        if use_vat not in VAT_SOURCES:
            raise TaxSettingsError("vat_source: неизвестный источник")

        for stmt in PREVIEW_SESSION_LIMITS:
            try:
                await self.db.execute(text(stmt))
            except Exception as e:  # pragma: no cover - лимиты не должны ронять расчёт
                log.debug("preview session limit failed: %s (%s)", stmt, e)

        rows = (await self.db.execute(text("""
            SELECT s.sdate, s.nm_id,
                   SUM(s.amount) AS sales,
                   SUM(s.`return`) AS ret_sum,
                   SUM(s.f_cost_price) AS cost,
                   SUM(s.commission) AS commission,
                   SUM(s.f_acquiring_fee) AS acquiring,
                   SUM(s.f_acceptance) AS acceptance,
                   SUM(s.f_delivery) AS delivery,
                   SUM(s.f_storage_fee) AS storage,
                   SUM(s.f_penalty) AS penalty,
                   SUM(s.f_deduction) AS deduction,
                   SUM(s.f_otziv) AS otziv,
                   SUM(s.f_adv) AS adv,
                   SUM(s.f_cashback) AS cashback
            FROM agg_daily_summary s
            WHERE s.company_id = :cid AND s.sdate BETWEEN :d1 AND :d2
            GROUP BY s.sdate, s.nm_id
            LIMIT :lim"""),
            {"cid": cid, "d1": d1, "d2": d2, "lim": PREVIEW_MAX_ROWS})).mappings().all()

        # Ставки НДС по карточкам: тянем историю wbcards_nds пачками и выбираем
        # в Python последний срез с load_date <= sdate (без correlated subquery на каждую строку).
        nds_hist: dict[int, list] = {}
        nm_ids = sorted({int(r["nm_id"]) for r in rows})
        for i in range(0, len(nm_ids), 500):
            chunk = nm_ids[i:i + 500]
            stmt = text("""
                SELECT nmID, load_date, nds FROM wbcards_nds
                WHERE nmID IN :ids AND load_date <= :d2
                ORDER BY nmID, load_date""").bindparams(bindparam("ids", expanding=True))
            for nr in (await self.db.execute(stmt, {"ids": chunk, "d2": d2})).mappings().all():
                nds_hist.setdefault(int(nr["nmID"]), []).append(
                    (str(nr["load_date"])[:10], float(nr["nds"] or 0)))

        def rate_for(nm_id: int, day: str) -> float | None:
            hist = nds_hist.get(int(nm_id))
            if not hist:
                return None
            found = None
            for ld, val in hist:
                if ld <= day:
                    found = val
                else:
                    break
            return found

        # Ручной маркетинг — по периоду размещения: сумма позиции растягивается
        # на дни периода, в расчёт попадает только часть, попавшая в окно.
        manual_rows = (await self.db.execute(text("""
            SELECT d.document_date AS d, d.period_start AS ps, d.period_end AS pe,
                   SUM(l.amount) AS amount
            FROM marketing_expense_lines l
            INNER JOIN marketing_expense_documents d ON d.id = l.document_id
            WHERE l.company_id = :cid AND d.document_date BETWEEN :d1 AND :d2
            GROUP BY d.id, d.document_date, d.period_start, d.period_end"""),
            {"cid": cid, "d1": d1, "d2": d2})).all()
        manual: dict[str, float] = {}
        for r in manual_rows:
            p_start = date.fromisoformat(str(r["ps"] or r["d"])[:10])
            p_end = date.fromisoformat(str(r["pe"] or r["ps"] or r["d"])[:10])
            for day, kop in allocate_days(float(r["amount"] or 0), p_start, p_end):
                key = day.isoformat()
                manual[key] = manual.get(key, 0.0) + kop / 100.0

        days_map: dict[str, dict] = {}

        def day_bucket(key: str) -> dict:
            b = days_map.get(key)
            if b is None:
                b = {
                    "date": key, "sales": 0.0, "returns": 0.0, "net": 0.0,
                    "vat": 0.0, "vat_missing_rows": 0, "vat_missing_amount": 0.0,
                    "cost": 0.0, "commission": 0.0, "acquiring": 0.0, "acceptance": 0.0,
                    "delivery": 0.0, "storage": 0.0, "penalty": 0.0, "deduction": 0.0,
                    "otziv": 0.0, "adv": 0.0, "cashback": 0.0, "manual": manual.get(key, 0.0),
                }
                days_map[key] = b
            return b

        for r in rows:
            key = str(r["sdate"])[:10]
            b = day_bucket(key)
            sales = float(r["sales"] or 0)
            ret = float(r["ret_sum"] or 0)
            net = sales - ret
            b["sales"] += sales
            b["returns"] += ret
            b["net"] += net
            for key2, col in (("cost", "cost"), ("commission", "commission"),
                              ("acquiring", "acquiring"), ("acceptance", "acceptance"),
                              ("delivery", "delivery"), ("storage", "storage"),
                              ("penalty", "penalty"), ("deduction", "deduction"),
                              ("otziv", "otziv"), ("adv", "adv"), ("cashback", "cashback")):
                b[key2] += float(r[col] or 0)
            nds = rate_for(int(r["nm_id"]), key)
            if nds is None:
                b["vat_missing_rows"] += 1
                b["vat_missing_amount"] += net
            else:
                b["vat"] += net * nds / (100.0 + nds) if use_vat == "cards" else 0.0

        # Дни, в которые были только ручные расходы (продаж нет) — тоже в расчёт:
        # иначе «растянутый» расход потерялся бы.
        for key in manual:
            if key not in days_map:
                days_map[key] = {
                    "date": key, "sales": 0.0, "returns": 0.0, "net": 0.0,
                    "vat": 0.0, "vat_missing_rows": 0, "vat_missing_amount": 0.0,
                    "cost": 0.0, "commission": 0.0, "acquiring": 0.0, "acceptance": 0.0,
                    "delivery": 0.0, "storage": 0.0, "penalty": 0.0, "deduction": 0.0,
                    "otziv": 0.0, "adv": 0.0, "cashback": 0.0, "manual": manual[key],
                }

        out_days = []
        totals = {"sales": 0.0, "returns": 0.0, "net": 0.0, "vat": 0.0,
                  "vat_missing_rows": 0, "vat_missing_amount": 0.0, "manual": 0.0}
        for key in sorted(days_map):
            b = days_map[key]
            income_base = b["net"] - b["vat"]
            # f_deduction уже содержит f_otziv и f_adv (это подмножества удержаний),
            # поэтому отдельно их НЕ вычитаем — иначе двойной счёт.
            profit_base = (income_base
                           - b["cost"] - b["commission"] - b["acquiring"] - b["acceptance"]
                           - b["delivery"] - b["storage"] - b["penalty"] - b["deduction"]
                           - b["cashback"] - b["manual"])
            if use_mode == "none":
                tax = 0.0
            elif use_mode == "income":
                tax = max(0.0, income_base) * use_rate / 100.0
            elif use_mode == "profit":
                tax = max(0.0, profit_base) * use_rate / 100.0
            else:  # osno
                tax = max(0.0, profit_base) * use_rate / 100.0
            b["income_base"] = income_base
            b["profit_base"] = profit_base
            b["tax"] = tax
            b["total_tax"] = b["vat"] + tax
            out_days.append(b)
            for k in totals:
                totals[k] += b.get(k, 0) or 0

        total_income_base = totals["net"] - totals["vat"]
        total_profit_base = (total_income_base
                             - sum(d["cost"] for d in out_days)
                             - sum(d["commission"] for d in out_days)
                             - sum(d["acquiring"] for d in out_days)
                             - sum(d["acceptance"] for d in out_days)
                             - sum(d["delivery"] for d in out_days)
                             - sum(d["storage"] for d in out_days)
                             - sum(d["penalty"] for d in out_days)
                             - sum(d["deduction"] for d in out_days)
                             - sum(d["cashback"] for d in out_days)
                             - totals["manual"])
        if use_mode == "none":
            total_tax = 0.0
        elif use_mode == "income":
            total_tax = max(0.0, total_income_base) * use_rate / 100.0
        elif use_mode == "profit":
            total_tax = max(0.0, total_profit_base) * use_rate / 100.0
        else:
            total_tax = max(0.0, total_profit_base) * use_rate / 100.0

        notes = [
            "Расчёт — управленческая оценка, не налоговая декларация.",
            "Ставка НДС берётся из wbcards_nds по карточке на дату продажи (без НДС / 10% / 22%).",
            "База НДС — оборот по цене продавца со скидкой за вычетом возвратов. Фактическая база "
            "НДС WB — цена покупателя с учётом СПП, поэтому сумма НДС здесь оценочная; точную базу "
            "нужно сверить с актами реализации.",
            "Расходы взяты по уровню компании (f_*): это итоги акта реализации, как в месячных "
            "отчётах. В разбивке по конкретному товару проект считает по ff_* (позиционные суммы) — "
            "между уровнями есть расхождения, их нужно сверять при подключении к отчётам.",
        ]
        if use_vat == "cards" and totals["vat_missing_rows"]:
            notes.append(
                f"НДС не посчитан по {int(totals['vat_missing_rows'])} строкам без ставки "
                f"(на {round(totals['vat_missing_amount'], 2)} ₽) — они попадут в NDS_MISSING.")
        if len(rows) >= PREVIEW_MAX_ROWS:
            notes.append(f"Выборка усечена на {PREVIEW_MAX_ROWS} строк — сократите период.")
        if use_mode == "osno":
            notes.append("Входящий НДС к вычету не применяется: нет подтверждённого источника.")
        if use_mode in ("profit", "osno"):
            notes.append("В базе налога Д−Р/ОСНО: доход без НДС минус расходы (себес, комиссия, "
                         "эквайринг, приёмка, доставка, хранение, штрафы, удержания, cashback "
                         "и ручной маркетинг).")
        notes.append("Реклама и отзывы (f_adv, f_otziv) — часть удержаний f_deduction, поэтому "
                     "отдельно не вычитаются: иначе получился бы двойной счёт. В колонке "
                     "«расходы» они показаны справочно.")

        return {
            "mode": use_mode,
            "mode_label": MODE_LABELS.get(use_mode, use_mode),
            "main_rate": use_rate,
            "vat_source": use_vat,
            "date_from": d1,
            "date_to": d2,
            "days": out_days,
            "totals": {
                **totals,
                "income_base": total_income_base,
                "profit_base": total_profit_base,
                "tax": total_tax,
                "total_tax": totals["vat"] + total_tax,
            },
            "partial": bool(totals["vat_missing_rows"]),
            "notes": notes,
        }
