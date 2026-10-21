"""Конкуренты (новый товар) — сервис страницы /competitor/new-cards.

План: 2026-10-20_new-cards_description.md (§5, §11.2, §15 Ш2/Ш4/Ш5).
Гейт — require_seo + company-scope (как competitor_service): не-global видит только
свои nmID через wbcards.company_id.

Термины:
- «новые карточки» — строки wbcards с пустым/коротким описанием (новая карточка WB);
- целевые фразы (wb_seo_target) — узкие, идут в промпт;
- поисковые запросы (wb_competitor_query) — широкие, нужны только для сбора конкурентов;
- конкуренты (wb_competitor_cards) — nm_id, привязанные к нашему source_nm_id.
"""

import json
import re
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import openrouter_service as llm
from backend.services import llm_provider

# Порог «описания нет»: короче 50 символов считаем пустым (как в §11.2 плана).
DESC_MIN_LEN = 50
MAX_COMPETITORS_PER_REQUEST = 50
MAX_COMPETITORS_FOR_AI = 20
MAX_PHRASES = 80
# Сколько моделей пробуем за один вызов: каждая может висеть до ~90 с,
# поэтому без лимита модалка «висит» 10+ минут.
MAX_AI_ATTEMPTS = 4
# Запас на thinking + сам JSON. Для «другого сервиса» шлём явно (send_max_tokens),
# иначе дефолт провайдера может закончиться на рассуждениях. Плюс reasoning_effort=low.
PHRASES_MAX_TOKENS = 8000
# Версии промптов — пишем в результат и ai_log, чтобы понимать, чем сделан текст.
PHRASES_PROMPT_VERSION = "newcard-phrases-v3"
DESC_PROMPT_VERSION = "newcard-desc-v3"


# Промпт извлечения фраз из описаний конкурентов (Ш11).
DEFAULT_PHRASES_PROMPT = """Ты — SEO-специалист Wildberries. Тебе дают описания карточек конкурентов по одному товару.
Задача: собрать поисковые фразы, по которым покупатели находят этот товар.
Верни ТОЛЬКО JSON без markdown: {"phrases": ["фраза 1", "фраза 2"]}
Поле должно называться именно `phrases` (не `keywords`).
Не пиши рассуждений, пояснений и markdown. Первый символ ответа — `{`, последний — `}`.

ПРАВИЛА:
- 15–40 фраз, 2–4 слова, в нижнем регистре, без знаков препинания и эмодзи.
- Каждая фраза — законченный поисковый запрос на ЭТОТ товар: содержит название товара/предмета или его общеупотребительный синоним (например «органайзер для белья», «коробка для хранения»).
- Можно: материал, размер, назначение, для кого, комплектация, сезон, стиль.
- Нельзя: общие маркетинговые обороты («идеальный подарок», «быстрая доставка», «высокое качество», «лучший выбор», «не оставит равнодушным»), призывы, бренды, названия конкурентов, слова «товар», «купить», «wildberries», «оптом».
- Не дублируй фразы в разных формах и не добавляй ту же фразу с другим порядком слов.
- Сначала фразы, которые встречаются у большинства конкурентов, потом редкие.
- Отвечай на русском."""


# Промпт генерации title + description по выбранным фразам (Ш11 v3).
# ВАЖНО: это отдельный промпт «новой карточки». companies.seo_summary_prompt
# здесь НЕ используется — он написан под старую «Сводку» (title_recommendations,
# priority_actions и анализы конкурентов) и на этом входе даёт мусор.
DEFAULT_DESC_PROMPT = """Ты — SEO-специалист Wildberries. У товара НОВАЯ карточка: описания ещё нет, его нужно написать с нуля по фактам, которые даны ниже.
Верни ТОЛЬКО JSON без markdown: {"title":"...","description":"..."}

### ЧТО У ТЕБЯ ЕСТЬ
1) НАША КАРТОЧКА: название, бренд, предмет (subject), характеристики. Это факты — используй их.
2) ПОИСКОВЫЕ ФРАЗЫ: 8–12 фраз с приоритетом P0/P1/P2 — по ним товар ищут.
3) ОПИСАНИЯ КОНКУРЕНТОВ: источник фактов и формулировок. Перефразируй, не копируй дословно.

### ПРИОРИТЕТ ФРАЗ
P0 — целевые (если есть): КАЖДАЯ обязана попасть в заголовок или описание в естественной форме.
P1 — фразы с заказами: покрой ВСЕ, это деньги.
P2 — остальные: покрой максимум; если фраза ломает русский язык — пропусти.
Если фраз 12 — используй минимум 8; если меньше — все P0 и P1, остальные по возможности.
Точные словоформы не обязательны (WB понимает леммы), но не коверкай фразы и не меняй порядок слов без нужды.

### ЗАГОЛОВОК — СТРОГО ≤60 символов
- Формула: [тип товара] + [главная фраза P0, иначе P1] + 1–2 атрибута.
- Без дублирования слов внутри заголовка; читаемо; без «купить», «дёшево», «оптом», эмодзи и КАПС.
- Бренд — в конец, только если влезает и не вытесняет тип товара и главную фразу.
- Посчитай символы. Если больше 60 — сокращай по смыслу, не обрывай на полуслове.

### ОПИСАНИЕ — {DESC_MIN}–{DESC_MAX} символов, 3–4 абзаца сплошного текста
1) Что это и для кого: 1–2 предложения, понятные без картинки.
2) Из чего и как работает: материал, размеры, состав, комплектация — только факты.
3) Зачем покупателю: сценарии использования, польза, уход и эксплуатация.
4) Короткое завершение — без призыва «покупайте» и без пафоса.
Вплетай фразы в живые предложения: «летнее женское платье» вместо «платье женский летний» — лемма зачтётся.

### ОДНО СЛОВО — ОДИН РАЗ
Покрытие важнее повторов. Если слово уже есть в заголовке или в предмете (subject), в описании используй синоним.
Повтор не растит позиции, а рискует пессимизацией за спам. Не перечисляй фразы через запятую и не ставь их подряд.

### ХАРАКТЕРИСТИКИ
Они уже заполнены в карточке — не предлагай их менять и не выдумывай новые. Используй только как источник фактов.

### ЗАПРЕТЫ (нарушение = брак)
- Слово «Характеристики:», подзаголовки отдельной строкой.
- Списки, маркеры «-», «—», «•», нумерация, markdown, эмодзи, КАПС, восклицательные знаки.
- Выдуманные факты: бренды, ГОСТы, награды, «100% натуральный», которых нет в данных.
- Вода: «идеальный выбор», «лучший друг», «источник вдохновения», «не оставит равнодушным».
- Ключи вне списка фраз и целевых.

### САМОПРОВЕРКА ПЕРЕД ОТВЕТОМ
1. title ≤60 символов, description в диапазоне {DESC_MIN}–{DESC_MAX}.
2. Все P0 и P1 есть в title + description (хотя бы леммой).
3. В описании нет ни одного маркера списка, markdown и слова «Характеристики».
4. Ни одна фраза не повторяется больше 2 раз.
В ответе только два поля: title и description."""




def _norm_phrase(raw) -> str:
    """Нормализация фразы: нижний регистр, один пробел, без обрамляющих знаков."""
    s = " ".join(str(raw or "").split()).strip().lower()
    s = s.strip(" .,;:!?\"'()[]{}«»—–-")
    return s[:500]


def _parse_json(content: str):
    """Достаём JSON из ответа модели (markdown-обёртки, текст вокруг)."""
    s = (content or "").strip()
    if not s:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", s, re.S | re.I)
    if m:
        s = m.group(1).strip()
    data = llm.safe_json_decode(s)
    if isinstance(data, (dict, list)):
        return data
    # Модель могла добавить цитату/пояснение после JSON — берём первый
    # самостоятельный объект/массив, а не жадный кусок до последней скобки.
    dec = json.JSONDecoder()
    for pat in (r"\{", r"\["):
        for m2 in re.finditer(pat, s):
            try:
                obj, _ = dec.raw_decode(s[m2.start():])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    return None


def _phrases_from_parsed(parsed, depth: int = 0):
    """Список фраз из разных форм ответа: list, {"phrases": [...]},
    {"phrases": "a, b"}, вложенные data/result/response/output."""
    if depth > 4:
        return None
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return None
    for key in ("phrases", "phrases_list", "keywords", "search_phrases", "queries", "items"):
        val = parsed.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, str) and val.strip():
            if val.lstrip().startswith(("{", "[")):
                found = _phrases_from_parsed(_parse_json(val), depth + 1)
                if found is not None:
                    return found
            parts = re.split(r"[\n,;]+", val)
            out = [p.strip(" \t-—–•*") for p in parts if p.strip(" \t-—–•*")]
            if out:
                return out
        if isinstance(val, dict):
            out = [v for v in val.values() if isinstance(v, (str, dict))]
            if out:
                return out
    for key in ("data", "result", "response", "output"):
        if key in parsed:
            found = _phrases_from_parsed(parsed[key], depth + 1)
            if found is not None:
                return found
    return None


def _unwrap_dict(raw, depth: int = 5) -> dict:
    """Порт unwrapResult: {"raw": "{...}"} → вложенный объект."""
    data = raw if isinstance(raw, dict) else _parse_json(str(raw or ""))
    for _ in range(depth):
        if not isinstance(data, dict) or set(data.keys()) != {"raw"}:
            break
        data = _parse_json(str(data.get("raw") or ""))
    return data if isinstance(data, dict) else {}


def _resp_title(data: dict) -> str:
    """title из ответа модели; поддерживаем старую схему new_title."""
    return str(data.get("title") or data.get("new_title") or "").strip()


def _resp_desc(data: dict) -> str:
    """description из ответа модели; поддерживаем старую схему new_description."""
    return str(data.get("description") or data.get("new_description") or "").strip()


_BULLET_PREFIXES = ("-", "—", "–", "•", "*", "·")


def _desc_problem(title: str, description: str, desc_min: int) -> str:
    """Грубая валидация ответа модели: отсекаем списки, markdown и пустоту.

    Возвращает текст ошибки или "" — если ответ пригоден.
    """
    if not title:
        return "пустой title"
    if len(title) < 15:
        return "слишком короткий title"
    if not description:
        return "пустой description"
    low = description.lower()
    if "характеристики:" in low:
        return "в описании «Характеристики:»"
    if "**" in description or "###" in description or "```" in description:
        return "markdown-разметка в описании"
    for line in description.splitlines():
        s = line.strip()
        if s and s.startswith(_BULLET_PREFIXES):
            return "список в описании"
    floor = max(400, int(desc_min * 0.35))
    if len(description) < floor:
        return f"слишком короткое описание ({len(description)} < {floor})"
    return ""


def _j(raw):
    if raw is None:
        return None
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _photo(photos_raw) -> str | None:
    """Первое фото: photos может быть JSON-строкой или двойным кодированием (как в competitor_service)."""
    val = _j(photos_raw)
    if isinstance(val, str) and val.strip().startswith(("[", "{")):
        val = _j(val)
    if isinstance(val, list):
        for u in val:
            if u:
                return str(u)
        return None
    if isinstance(val, str) and val:
        return val
    return None


def _images(raw) -> list[str]:
    """Нормализуем images: JSON-строка, двойное кодирование или список объектов."""
    val = _j(raw)
    if isinstance(val, str) and val.strip().startswith(("[", "{")):
        val = _j(val)
    if isinstance(val, dict):
        val = val.get("images") or val.get("urls") or []
    if not isinstance(val, list):
        return []
    out: list[str] = []
    for item in val:
        if isinstance(item, dict):
            item = item.get("url") or item.get("big") or item.get("c516x688") or item.get("square")
        s = str(item or "").strip()
        if s.startswith("//"):
            s = "https:" + s
        if s and s not in out:
            out.append(s)
    return out


def _like(q: str) -> str:
    """Экранируем % и _ в пользовательском вводе (иначе LIKE-инъекция по спецсимволам)."""
    return "%" + re.sub(r"[%_]", lambda m: "\\" + m.group(0), q.strip()) + "%"


def _ints(raw, limit: int = MAX_COMPETITORS_PER_REQUEST) -> list[int]:
    out: list[int] = []
    for v in raw or []:
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n > 0 and n not in out:
            out.append(n)
        if len(out) >= limit:
            break
    return out


def _chunks(values: list[int], size: int = 400):
    """Режем IN (...) на порции: MySQL не любит тысячи параметров в одном запросе."""
    for i in range(0, len(values), size):
        yield values[i:i + size]


def _ts(v) -> float:
    """Сортировка по дате: MySQL может вернуть str или datetime."""
    if not v:
        return 0.0
    if isinstance(v, datetime):
        try:
            return v.timestamp()
        except Exception:
            return 0.0
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


class CompetitorsNewcardService:
    def __init__(self, db: AsyncSession, company_id: int | None):
        self.db = db
        self.company_id = company_id

    # ---------- helpers ----------

    def _scope(self, alias: str = "w") -> tuple[str, dict]:
        if self.company_id is None:
            return "", {}
        pre = f"{alias}." if alias else ""
        return f"AND {pre}company_id=:cid", {"cid": self.company_id}

    async def owns_card(self, nm_id: int) -> bool:
        if self.company_id is None:
            return True
        r = (await self.db.execute(text("""
            SELECT 1 FROM wbcards WHERE nmID=:n AND company_id=:c LIMIT 1
        """), {"n": nm_id, "c": self.company_id})).first()
        return r is not None

    async def _company_for(self, nm_id: int) -> int | None:
        """company_id для записи: выбранная компания, иначе — владелец карточки (global admin)."""
        if self.company_id is not None:
            return self.company_id
        r = (await self.db.execute(text("""
            SELECT company_id FROM wbcards WHERE nmID=:n LIMIT 1
        """), {"n": nm_id})).first()
        return int(r[0]) if r and r[0] else None

    async def _card(self, nm_id: int) -> dict | None:
        scope, p = self._scope()
        r = (await self.db.execute(text(f"""
            SELECT w.nmID, w.company_id, w.title, w.brand, w.vendorCode, w.subjectName,
                   w.description, w.characteristics, w.photos,
                   CHAR_LENGTH(COALESCE(w.description,'')) AS desc_len
            FROM wbcards w
            WHERE w.nmID=:n {scope} LIMIT 1
        """), {"n": nm_id, **p})).mappings().first()
        if not r:
            return None
        d = dict(r)
        d["photo"] = _photo(d.pop("photos", None))
        d["vendor_code"] = d.pop("vendorCode", None)
        d["subject_name"] = d.pop("subjectName", None)
        d["characteristics"] = _j(d.get("characteristics")) or []
        return d

    # ---------- §11.2: список карточек «в работе» ----------

    async def list_cards(self, q: str = "", limit: int = 200, include_all: bool = False) -> dict:
        """Карточки в работе: есть поисковые запросы или привязанные конкуренты.

        `include_all=1` — все активные карточки (кнопка «показать все»);
        `q` — маска по nmID / vendorCode / title / бренду.
        """
        scope, p = self._scope("w")
        params: dict = {"lim": limit, **p}
        conds = ["w.is_active=1"]
        if q.strip():
            conds.append("(w.title LIKE :like OR w.vendorCode LIKE :like"
                         " OR w.brand LIKE :like OR CAST(w.nmID AS CHAR) LIKE :like)")
            params["like"] = _like(q)
        if not include_all:
            conds.append("""(EXISTS (SELECT 1 FROM wb_competitor_query cq WHERE cq.source_nm_id=w.nmID)
                          OR EXISTS (SELECT 1 FROM wb_competitor_cards cc
                                     WHERE cc.source_nm_id=w.nmID
                                       AND cc.source IN ('manual','capture')))""")
        where = " AND ".join(conds)
        rows = (await self.db.execute(text(f"""
            SELECT w.nmID, w.title, w.brand, w.vendorCode, w.subjectName, w.photos,
                   CHAR_LENGTH(COALESCE(w.description,'')) AS desc_len,
                   COALESCE(w.last_seen_at, w.created_at) AS seen_at,
                   (SELECT COUNT(*) FROM wb_seo_target t WHERE t.nmID=w.nmID) AS targets_cnt,
                   (SELECT COUNT(*) FROM wb_competitor_query cq WHERE cq.source_nm_id=w.nmID) AS queries_cnt,
                   (SELECT COUNT(DISTINCT cc.nm_id) FROM wb_competitor_cards cc
                     WHERE cc.source_nm_id=w.nmID) AS competitors_cnt,
                   (SELECT COUNT(*) FROM wb_competitor_details d
                     WHERE d.nm_id IN (SELECT nm_id FROM wb_competitor_cards cc3 WHERE cc3.source_nm_id=w.nmID)
                       AND CHAR_LENGTH(COALESCE(d.description,'')) >= :minlen) AS content_cnt,
                   (SELECT COUNT(*) FROM wb_competitor_analysis a
                     WHERE a.source_nm_id=w.nmID AND a.status='analyzed') AS analyzed_cnt,
                   (SELECT COUNT(*) FROM wb_competitor_phrase ph
                     WHERE ph.source_nm_id=w.nmID) AS phrases_cnt,
                   (SELECT COUNT(*) FROM wb_competitor_phrase ph
                     WHERE ph.source_nm_id=w.nmID AND ph.is_selected=1) AS selected_cnt,
                   (SELECT COUNT(*) FROM wb_competitor_summary s
                     WHERE s.source_nm_id=w.nmID) AS summary_cnt
            FROM wbcards w
            WHERE {where}
            ORDER BY COALESCE(w.last_seen_at, w.created_at) DESC
            LIMIT :lim
        """), {**params, "minlen": DESC_MIN_LEN})).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            d["photo"] = _photo(d.pop("photos", None))
            d["vendor_code"] = d.pop("vendorCode", None)
            d["subject_name"] = d.pop("subjectName", None)
            items.append(d)
        return {"items": items, "total": len(items), "desc_min_len": DESC_MIN_LEN}

    async def card_detail(self, nm_id: int) -> dict | None:
        card = await self._card(nm_id)
        if not card:
            return None
        summary = (await self.db.execute(text("""
            SELECT suggested_title, suggested_description, competitor_count, model, created_at
            FROM wb_competitor_summary WHERE source_nm_id=:n LIMIT 1
        """), {"n": nm_id})).mappings().first()
        targets = (await self.db.execute(text("""
            SELECT id, nmID, phrase, priority, is_active FROM wb_seo_target
            WHERE nmID=:n ORDER BY priority, id
        """), {"n": nm_id})).mappings().all()
        queries = await self.list_queries(nm_id)
        competitors = await self.list_competitors(nm_id)
        phrases = await self.list_phrases(nm_id)
        counts = {
            "targets_cnt": len(targets),
            "queries_cnt": len(queries["items"]),
            "competitors_cnt": len(competitors["items"]),
            "content_cnt": sum(1 for c in competitors["items"] if int(c.get("desc_len") or 0) >= DESC_MIN_LEN),
            "analyzed_cnt": sum(1 for c in competitors["items"] if c.get("analysis_status") == "analyzed"),
            "phrases_cnt": len(phrases["items"]),
            "selected_cnt": phrases["selected_cnt"],
        }
        return {
            "card": card,
            "counts": counts,
            "summary": dict(summary) if summary else None,
            "targets": [dict(t) for t in targets],
            "queries": queries["items"],
            "competitors": competitors["items"],
            "phrases": phrases["items"],
        }

    # ---------- §5: поисковые запросы (широкие, для сбора конкурентов) ----------

    async def list_queries(self, nm_id: int) -> dict:
        rows = (await self.db.execute(text("""
            SELECT q.id, q.phrase, q.priority, q.is_active, q.source, q.status,
                   q.added_by, q.created_at,
                   (SELECT COUNT(DISTINCT c.nm_id) FROM wb_competitor_cards c
                    WHERE c.source_nm_id=q.source_nm_id AND c.query_phrase=q.phrase
                      AND c.nm_id>0) AS found_cnt,
                   (SELECT MIN(c.position) FROM wb_competitor_cards c
                    WHERE c.source_nm_id=q.source_nm_id AND c.query_phrase=q.phrase
                      AND c.nm_id>0 AND c.position>0) AS best_position
            FROM wb_competitor_query q
            WHERE q.source_nm_id=:n
            ORDER BY q.priority, q.id
        """), {"n": nm_id})).mappings().all()
        return {"nm_id": nm_id, "items": [dict(r) for r in rows]}

    async def add_query(self, nm_id: int, phrase: str, user_id: int | None) -> dict:
        phrase = (phrase or "").strip()[:500]
        if not phrase:
            raise ValueError("Пустой запрос")
        exists = (await self.db.execute(text("""
            SELECT id FROM wb_competitor_query WHERE source_nm_id=:n AND phrase=:p LIMIT 1
        """), {"n": nm_id, "p": phrase})).first()
        if exists:
            raise ValueError("Уже добавлен")
        await self.db.rollback()
        company = await self._company_for(nm_id)
        if not company:
            raise ValueError("Не удалось определить компанию карточки")
        async with self.db.begin():
            await self.db.execute(text("""
                INSERT INTO wb_competitor_query
                  (company_id, source_nm_id, phrase, priority, is_active, source, added_by, created_at, updated_at)
                VALUES (:c, :n, :p, 10, 1, 'manual', :u, NOW(), NOW())
            """), {"c": company, "n": nm_id, "p": phrase, "u": user_id})
            qid = (await self.db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()
        return {"id": int(qid)}

    async def remove_query(self, nm_id: int, qid: int) -> bool:
        await self.db.rollback()
        async with self.db.begin():
            r = await self.db.execute(text("""
                DELETE FROM wb_competitor_query WHERE id=:i AND source_nm_id=:n
            """), {"i": qid, "n": nm_id})
        return bool(r.rowcount)

    async def suggest_queries(self, nm_id: int, q: str, limit: int = 12) -> dict:
        """Подсказки из базы: wb_sr_report_item_phrases по ВСЕЙ базе, фильтр по subject_name

        нашей карточки, сортировка по заказам/частоте (§9 плана). Добавление — по одному.
        """
        q = (q or "").strip()
        if len(q) < 2:
            return {"items": [], "added": []}
        card = await self._card(nm_id)
        subject = (card or {}).get("subject_name") or ""
        rows = (await self.db.execute(text("""
            SELECT p.phrase,
                   SUM(p.orders) AS orders,
                   MAX(COALESCE(p.frequency_current, p.week_frequency, 0)) AS freq,
                   COUNT(DISTINCT p.nmID) AS cards
            FROM wb_sr_report_item_phrases p
            JOIN wb_sr_report_items i ON i.id = p.item_id
            WHERE p.phrase LIKE :like
              AND (:subj = '' OR i.subject_name = :subj)
            GROUP BY p.phrase
            ORDER BY orders DESC, freq DESC
            LIMIT :lim
        """), {"like": _like(q), "subj": subject, "lim": limit})).mappings().all()
        added = (await self.db.execute(text("""
            SELECT phrase FROM wb_competitor_query WHERE source_nm_id=:n
        """), {"n": nm_id})).scalars().all()
        added_set = {str(x) for x in added}
        items = []
        for r in rows:
            d = dict(r)
            d["orders"] = int(d.get("orders") or 0)
            d["freq"] = int(d.get("freq") or 0)
            d["cards"] = int(d.get("cards") or 0)
            d["added"] = d["phrase"] in added_set
            items.append(d)
        return {"items": items, "added": sorted(added_set), "subject_name": subject}

    # ---------- §11.1: конкуренты ----------

    async def list_competitors(self, nm_id: int) -> dict:
        rows = (await self.db.execute(text("""
            SELECT c.nm_id,
                   MAX(c.title) AS title,
                   MAX(c.brand) AS brand,
                   MAX(c.price) AS price,
                   MAX(c.image_url) AS image_url,
                   MAX(c.collected_at) AS collected_at,
                   MAX(q.status) AS queue_status,
                   MAX(q.error_msg) AS queue_error,
                   MAX(q.processed_at) AS queue_processed_at,
                   GROUP_CONCAT(DISTINCT c.source ORDER BY c.source) AS sources,
                   GROUP_CONCAT(DISTINCT NULLIF(c.query_phrase,'') SEPARATOR ' | ') AS phrases
            FROM wb_competitor_cards c
            LEFT JOIN wb_enrich_queue q ON q.nm_id=c.nm_id
              AND (:qc IS NULL OR q.company_id=:qc OR q.company_id IS NULL)
            WHERE c.source_nm_id=:n
            GROUP BY c.nm_id
            ORDER BY c.nm_id
        """), {"n": nm_id, "qc": self.company_id})).mappings().all()
        ids = [r["nm_id"] for r in rows]
        details: dict[int, dict] = {}
        analysis: dict[int, str] = {}
        if ids:
            ph = ",".join(f":d{i}" for i in range(len(ids)))
            for r in (await self.db.execute(text(f"""
                SELECT nm_id, title, brand, seller, price, old_price, images,
                       CHAR_LENGTH(COALESCE(description,'')) AS desc_len,
                       JSON_LENGTH(COALESCE(characteristics, JSON_ARRAY())) AS chars_cnt,
                       collected_at
                FROM wb_competitor_details WHERE nm_id IN ({ph})
            """), {f"d{i}": v for i, v in enumerate(ids)})).mappings().all():
                details[r["nm_id"]] = dict(r)
            for r in (await self.db.execute(text(f"""
                SELECT competitor_nm_id, status FROM wb_competitor_analysis
                WHERE source_nm_id=:n AND competitor_nm_id IN ({ph})
                ORDER BY (status='analyzed') DESC, id DESC
            """), {"n": nm_id, **{f"d{i}": v for i, v in enumerate(ids)}})).mappings().all():
                analysis.setdefault(r["competitor_nm_id"], r["status"])
        items = []
        for r in rows:
            d = dict(r)
            det = details.get(d["nm_id"]) or {}
            d["title"] = det.get("title") or d.get("title")
            d["brand"] = det.get("brand") or d.get("brand")
            d["seller"] = det.get("seller") or ""
            d["price"] = det.get("price") or d.get("price")
            d["old_price"] = det.get("old_price") or ""
            d["photo"] = _photo(det.get("images")) or (d.get("image_url") or None)
            d["desc_len"] = int(det.get("desc_len") or 0)
            d["chars_cnt"] = int(det.get("chars_cnt") or 0)
            d["collected_at"] = det.get("collected_at") or d.get("collected_at")
            d["analysis_status"] = analysis.get(d["nm_id"])
            d["sources"] = (d.get("sources") or "").split(",") if d.get("sources") else []
            d["manual"] = "manual" in d["sources"] or "capture" in d["sources"]
            items.append(d)
        return {"nm_id": nm_id, "items": items}

    async def add_competitors(self, nm_id: int, raw_nm_ids, user_id: int | None) -> dict:
        """Ручное добавление конкурентов: wb_competitor_cards(source='manual') + очередь обогащения."""
        nm_ids = [n for n in _ints(raw_nm_ids) if n != nm_id]
        if not nm_ids:
            raise ValueError("Укажите хотя бы один nmID (кроме текущего)")
        await self.db.rollback()
        async with self.db.begin():
            added = 0
            for cn in nm_ids:
                r = await self.db.execute(text("""
                    INSERT IGNORE INTO wb_competitor_cards
                      (source_nm_id, query_phrase, position, nm_id, title, brand, price, image_url, source, added_by)
                    VALUES (:s, '', 0, :n, '', '', 0, '', 'manual', :u)
                """), {"s": nm_id, "n": cn, "u": user_id})
                added += int(r.rowcount or 0)
            await self._queue(nm_id, nm_ids)
        return {"added": added, "requested": len(nm_ids), "nm_ids": nm_ids}

    async def copy_from_card(self, nm_id: int, src_nm_id: int, user_id: int | None) -> dict:
        """Скопировать конкурентов (и их фразы) с другой нашей карточки: source='sibling'."""
        if not src_nm_id or src_nm_id == nm_id:
            raise ValueError("Укажите другую нашу карточку")
        if not await self.owns_card(src_nm_id):
            raise ValueError("Карточка-источник не найдена в вашей компании")
        await self.db.rollback()
        async with self.db.begin():
            r = await self.db.execute(text("""
                INSERT IGNORE INTO wb_competitor_cards
                  (source_nm_id, query_phrase, position, nm_id, title, brand, price, image_url, source, added_by)
                SELECT :n, query_phrase, position, nm_id, title, brand, price, image_url, 'sibling', :u
                FROM wb_competitor_cards WHERE source_nm_id=:s
            """), {"n": nm_id, "s": src_nm_id, "u": user_id})
            added = int(r.rowcount or 0)
            ids = (await self.db.execute(text("""
                SELECT DISTINCT nm_id FROM wb_competitor_cards WHERE source_nm_id=:n
            """), {"n": nm_id})).scalars().all()
            await self._queue(nm_id, [int(x) for x in ids])
        return {"added": added, "source_nm_id": src_nm_id}

    # ---------- §8.5/§11.3: «Собранные карточки» (capture) ----------

    async def list_captured(self, q: str = "", include_hidden: bool = False,
                            limit: int = 300) -> dict:
        """Список `wb_competitor_capture` компании + контент из общих `wb_competitor_details`.

        global admin (company_id None) видит все компании; is_hidden — своё значение для
        компании, у админа MIN (видна, если хотя бы у одной компании не скрыта).
        """
        where = []
        params: dict = {"lim": limit}
        if self.company_id is not None:
            where.append("c.company_id = :cid")
            params["cid"] = self.company_id
        if not include_hidden:
            where.append("c.is_hidden = 0")
        having = ""
        if q.strip():
            params["like"] = _like(q)
            having = ("HAVING (title LIKE :like OR brand LIKE :like OR seller LIKE :like"
                      " OR CAST(c.nm_id AS CHAR) LIKE :like)")
        rows = (await self.db.execute(text(f"""
            SELECT c.nm_id,
                   MAX(c.is_own) AS is_own,
                   MIN(c.is_hidden) AS is_hidden,
                   MIN(c.first_seen_at) AS first_seen_at,
                   MAX(c.last_seen_at) AS last_seen_at,
                   COUNT(DISTINCT c.company_id) AS companies_cnt,
                   MAX(d.title) AS title,
                   MAX(d.brand) AS brand,
                   MAX(d.seller) AS seller,
                   MAX(d.price) AS price,
                   MAX(d.old_price) AS old_price,
                   MAX(d.url) AS url,
                   MAX(d.images) AS images,
                   MAX(CHAR_LENGTH(COALESCE(d.description,''))) AS desc_len,
                   MAX(JSON_LENGTH(COALESCE(d.characteristics, JSON_ARRAY()))) AS chars_cnt,
                   MAX(d.collected_at) AS collected_at
            FROM wb_competitor_capture c
            LEFT JOIN wb_competitor_details d ON d.nm_id = c.nm_id
            WHERE {' AND '.join(where) if where else '1=1'}
            GROUP BY c.nm_id
            {having}
            ORDER BY MAX(c.last_seen_at) DESC
            LIMIT :lim
        """), params)).mappings().all()

        ids = [r["nm_id"] for r in rows]
        attached: dict[int, list[dict]] = {}
        history_cnt: dict[int, int] = {}
        if ids:
            ph = ",".join(f":d{i}" for i in range(len(ids)))
            iparams: dict = {f"d{i}": v for i, v in enumerate(ids)}
            scope = ""
            if self.company_id is not None:
                scope = "AND cc.source_nm_id IN (SELECT nmID FROM wbcards WHERE company_id=:cid2)"
                iparams["cid2"] = self.company_id
            for r in (await self.db.execute(text(f"""
                SELECT cc.nm_id, cc.source_nm_id, w.title AS source_title
                FROM wb_competitor_cards cc
                LEFT JOIN wbcards w ON w.nmID = cc.source_nm_id
                WHERE cc.source='capture' AND cc.nm_id IN ({ph}) {scope}
                ORDER BY cc.source_nm_id
            """), iparams)).mappings().all():
                attached.setdefault(int(r["nm_id"]), []).append({
                    "nm_id": int(r["source_nm_id"]),
                    "title": r["source_title"],
                })
            for r in (await self.db.execute(text(f"""
                SELECT nm_id, COUNT(*) AS cnt FROM wb_competitor_details_history
                WHERE nm_id IN ({ph}) GROUP BY nm_id
            """), iparams)).mappings().all():
                history_cnt[int(r["nm_id"])] = int(r["cnt"] or 0)

        items = []
        for r in rows:
            d = dict(r)
            n = int(d["nm_id"])
            d["photo"] = _photo(d.pop("images", None))
            d["desc_len"] = int(d.get("desc_len") or 0)
            d["chars_cnt"] = int(d.get("chars_cnt") or 0)
            d["is_own"] = bool(d.get("is_own"))
            d["is_hidden"] = bool(d.get("is_hidden"))
            d["companies_cnt"] = int(d.get("companies_cnt") or 0)
            d["attached"] = attached.get(n, [])
            d["attached_cnt"] = len(d["attached"])
            d["history_cnt"] = history_cnt.get(n, 0)
            d["url"] = d.get("url") or f"https://www.wildberries.ru/catalog/{n}/detail.aspx"
            items.append(d)
        return {"items": items, "total": len(items)}

    # ---------- §16: подбор конкурентов и массовая привязка ----------

    async def pick_cards(self, q: str = "", limit: int = 50) -> dict:
        """Наши карточки для выбора источника/цели (nmID, vendorCode, title, счётчики)."""
        limit = max(1, min(int(limit or 50), 200))
        scope, p = self._scope("w")
        params: dict = {"lim": limit, "minlen": DESC_MIN_LEN, **p}
        conds = ["w.is_active=1"]
        if q.strip():
            conds.append("(w.title LIKE :like OR w.vendorCode LIKE :like"
                         " OR w.brand LIKE :like OR CAST(w.nmID AS CHAR) LIKE :like)")
            params["like"] = _like(q)
        rows = (await self.db.execute(text(f"""
            SELECT w.nmID, w.company_id, w.title, w.brand, w.vendorCode,
                   w.subjectName, w.photos,
                   (SELECT COUNT(DISTINCT cc.nm_id) FROM wb_competitor_cards cc
                    WHERE cc.source_nm_id=w.nmID) AS competitors_cnt,
                   (SELECT COUNT(DISTINCT cc.nm_id)
                    FROM wb_competitor_cards cc
                    JOIN wb_competitor_details d ON d.nm_id=cc.nm_id
                    WHERE cc.source_nm_id=w.nmID
                      AND CHAR_LENGTH(COALESCE(d.description,'')) >= :minlen) AS content_cnt
            FROM wbcards w
            WHERE {' AND '.join(conds)}
            ORDER BY COALESCE(w.last_seen_at, w.created_at) DESC
            LIMIT :lim
        """), params)).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            d["photo"] = _photo(d.pop("photos", None))
            d["vendor_code"] = d.pop("vendorCode", None)
            d["subject_name"] = d.pop("subjectName", None)
            d["competitors_cnt"] = int(d.get("competitors_cnt") or 0)
            d["content_cnt"] = int(d.get("content_cnt") or 0)
            items.append(d)
        return {"items": items, "total": len(items), "desc_min_len": DESC_MIN_LEN}

    async def _pick_sources(self, ids: list[int]) -> list[int]:
        ids = list(dict.fromkeys(int(x) for x in ids if int(x) > 0))
        if not ids:
            return []
        found: set[int] = set()
        for chunk in _chunks(ids):
            ph = ",".join(f":s{i}" for i in range(len(chunk)))
            params: dict = {f"s{i}": v for i, v in enumerate(chunk)}
            scope = ""
            if self.company_id is not None:
                scope = " AND company_id=:cid"
                params["cid"] = self.company_id
            rows = (await self.db.execute(text(f"""
                SELECT nmID FROM wbcards WHERE nmID IN ({ph}) {scope}
            """), params)).scalars().all()
            found.update(int(x) for x in rows)
        missing = [n for n in ids if n not in found]
        if missing:
            if self.company_id is not None:
                foreign: set[int] = set()
                for chunk in _chunks(missing):
                    ph = ",".join(f":f{i}" for i in range(len(chunk)))
                    rows = (await self.db.execute(text(f"""
                        SELECT nmID FROM wbcards
                        WHERE nmID IN ({ph}) AND company_id<>:cid
                    """), {**{f"f{i}": v for i, v in enumerate(chunk)}, "cid": self.company_id})).scalars().all()
                    foreign.update(int(x) for x in rows)
                if foreign:
                    raise PermissionError("Карточка принадлежит другой компании: "
                                          + ", ".join(str(n) for n in sorted(foreign)[:10]))
            raise ValueError("Карточки не найдены: " + ", ".join(str(n) for n in missing[:10]))
        return ids

    async def _own_card_ids(self) -> set[int]:
        if self.company_id is None:
            rows = (await self.db.execute(text("SELECT nmID FROM wbcards"))).scalars().all()
        else:
            rows = (await self.db.execute(text(
                "SELECT nmID FROM wbcards WHERE company_id=:cid"
            ), {"cid": self.company_id})).scalars().all()
        return {int(x) for x in rows}

    async def _details_map(self, ids: list[int]) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for chunk in _chunks(ids):
            ph = ",".join(f":d{i}" for i in range(len(chunk)))
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, title, brand, seller, price, old_price, images,
                       recommendations,
                       CHAR_LENGTH(COALESCE(description,'')) AS desc_len,
                       JSON_LENGTH(COALESCE(characteristics, JSON_ARRAY())) AS chars_cnt,
                       collected_at
                FROM wb_competitor_details
                WHERE nm_id IN ({ph})
                ORDER BY collected_at DESC
            """), {f"d{i}": v for i, v in enumerate(chunk)})).mappings().all()
            for r in rows:
                out.setdefault(int(r["nm_id"]), dict(r))
        return out

    async def _cards_meta_map(self, ids: list[int]) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for chunk in _chunks(ids):
            ph = ",".join(f":m{i}" for i in range(len(chunk)))
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, MAX(title) AS title, MAX(brand) AS brand,
                       MAX(price) AS price, MAX(image_url) AS image_url,
                       MAX(collected_at) AS collected_at,
                       GROUP_CONCAT(DISTINCT source) AS sources
                FROM wb_competitor_cards
                WHERE nm_id IN ({ph})
                GROUP BY nm_id
            """), {f"m{i}": v for i, v in enumerate(chunk)})).mappings().all()
            for r in rows:
                out[int(r["nm_id"])] = dict(r)
        return out

    async def _capture_map(self, ids: list[int]) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for chunk in _chunks(ids):
            ph = ",".join(f":c{i}" for i in range(len(chunk)))
            params: dict = {f"c{i}": v for i, v in enumerate(chunk)}
            if self.company_id is None:
                rows = (await self.db.execute(text(f"""
                    SELECT nm_id, MAX(is_own) AS is_own, MIN(is_hidden) AS is_hidden
                    FROM wb_competitor_capture
                    WHERE nm_id IN ({ph})
                    GROUP BY nm_id
                """), params)).mappings().all()
            else:
                params["cid"] = self.company_id
                rows = (await self.db.execute(text(f"""
                    SELECT nm_id, is_own, is_hidden
                    FROM wb_competitor_capture
                    WHERE nm_id IN ({ph}) AND company_id=:cid
                """), params)).mappings().all()
            for r in rows:
                out[int(r["nm_id"])] = dict(r)
        return out

    async def _attached_map(self, ids: list[int]) -> dict[int, list[dict]]:
        out: dict[int, list[dict]] = {}
        for chunk in _chunks(ids):
            ph = ",".join(f":a{i}" for i in range(len(chunk)))
            params: dict = {f"a{i}": v for i, v in enumerate(chunk)}
            scope = ""
            if self.company_id is not None:
                scope = (" AND cc.source_nm_id IN "
                         "(SELECT nmID FROM wbcards WHERE company_id=:cid)")
                params["cid"] = self.company_id
            rows = (await self.db.execute(text(f"""
                SELECT cc.nm_id, cc.source_nm_id, cc.source,
                       w.title AS source_title
                FROM wb_competitor_cards cc
                LEFT JOIN wbcards w ON w.nmID=cc.source_nm_id
                WHERE cc.nm_id IN ({ph}) {scope}
                ORDER BY cc.source_nm_id
            """), params)).mappings().all()
            for r in rows:
                n = int(r["nm_id"])
                src = int(r["source_nm_id"])
                bucket = out.setdefault(n, [])
                if any(x["nm_id"] == src for x in bucket):
                    continue
                bucket.append({
                    "nm_id": src,
                    "title": r["source_title"],
                    "source": r["source"],
                })
        return out

    async def _queue_map(self, ids: list[int]) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for chunk in _chunks(ids):
            ph = ",".join(f":q{i}" for i in range(len(chunk)))
            params: dict = {f"q{i}": v for i, v in enumerate(chunk)}
            params["cid"] = self.company_id
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, status, error_msg, processed_at
                FROM wb_enrich_queue
                WHERE nm_id IN ({ph})
                  AND (:cid IS NULL OR company_id=:cid OR company_id IS NULL)
                ORDER BY id DESC
            """), params)).mappings().all()
            for r in rows:
                out.setdefault(int(r["nm_id"]), dict(r))
        return out

    async def pick_candidates(self, raw_source_nm_ids, mode: str = "recommend",
                              q: str = "", only_content: bool = False,
                              only_recommended: bool = False,
                              limit: int = 200, offset: int = 0) -> dict:
        """Пул кандидатов §16: A ∪ B / только A / вся captured-база компании."""
        mode = (mode or "recommend").strip().lower()
        if mode not in ("recommend", "competitors", "captured"):
            raise ValueError("mode: recommend | competitors | captured")
        if isinstance(raw_source_nm_ids, str):
            raw_source_nm_ids = [x for x in re.split(r"[,;\s]+", raw_source_nm_ids) if x]
        limit = max(1, min(int(limit or 200), 500))
        offset = max(0, int(offset or 0))

        source_ids: list[int] = []
        base: dict[int, dict] = {}

        def blank(nm: int) -> dict:
            return {
                "nm_id": nm, "in_a": False, "rec_cnt": 0, "recommended_by": [],
                "title": "", "brand": "", "price": "", "image_url": "",
                "collected_at": None, "sources": [],
            }

        if mode in ("recommend", "competitors"):
            source_ids = await self._pick_sources(_ints(raw_source_nm_ids, 200))
            if not source_ids:
                raise ValueError("Выберите хотя бы одну нашу карточку")
            for chunk in _chunks(source_ids):
                ph = ",".join(f":s{i}" for i in range(len(chunk)))
                rows = (await self.db.execute(text(f"""
                    SELECT nm_id, MAX(title) AS title, MAX(brand) AS brand,
                           MAX(price) AS price, MAX(image_url) AS image_url,
                           MAX(collected_at) AS collected_at,
                           GROUP_CONCAT(DISTINCT source) AS sources
                    FROM wb_competitor_cards
                    WHERE source_nm_id IN ({ph}) AND nm_id > 0
                    GROUP BY nm_id
                """), {f"s{i}": v for i, v in enumerate(chunk)})).mappings().all()
                for r in rows:
                    n = int(r["nm_id"])
                    item = blank(n)
                    item.update({
                        "in_a": True,
                        "title": r["title"] or "",
                        "brand": r["brand"] or "",
                        "price": r["price"] or "",
                        "image_url": r["image_url"] or "",
                        "collected_at": r["collected_at"],
                        "sources": (r["sources"] or "").split(",") if r["sources"] else [],
                    })
                    base[n] = item

            if mode == "recommend" and base:
                a_ids = list(base.keys())
                for chunk in _chunks(a_ids):
                    ph = ",".join(f":r{i}" for i in range(len(chunk)))
                    rows = (await self.db.execute(text(f"""
                        SELECT nm_id, recommendations
                        FROM wb_competitor_details
                        WHERE nm_id IN ({ph})
                        ORDER BY collected_at DESC
                    """), {f"r{i}": v for i, v in enumerate(chunk)})).mappings().all()
                    seen: set[int] = set()
                    for r in rows:
                        src = int(r["nm_id"])
                        if src in seen:
                            continue
                        seen.add(src)
                        recs = _j(r["recommendations"])
                        if isinstance(recs, dict):
                            recs = recs.get("items") or recs.get("recommendations") or []
                        if not isinstance(recs, list):
                            continue
                        for rec in recs:
                            if isinstance(rec, dict):
                                rn = rec.get("nm_id") or rec.get("nmId") or rec.get("id")
                                rtitle = rec.get("title") or ""
                            else:
                                rn, rtitle = rec, ""
                            try:
                                rn = int(rn or 0)
                            except (TypeError, ValueError):
                                continue
                            if rn <= 0 or rn == src:
                                continue
                            item = base.get(rn)
                            if item is None:
                                item = blank(rn)
                                item["title"] = str(rtitle or "")
                                base[rn] = item
                            if src not in item["recommended_by"]:
                                item["recommended_by"].append(src)
                                item["rec_cnt"] = len(item["recommended_by"])
        else:
            # captured: вся видимая база компании; source_nm_ids не нужны
            if self.company_id is None:
                rows = (await self.db.execute(text(
                    "SELECT nm_id FROM wb_competitor_capture GROUP BY nm_id"
                ))).scalars().all()
            else:
                rows = (await self.db.execute(text("""
                    SELECT nm_id FROM wb_competitor_capture
                    WHERE company_id=:cid GROUP BY nm_id
                """), {"cid": self.company_id})).scalars().all()
            for nm in rows:
                n = int(nm)
                base[n] = blank(n)

        own = await self._own_card_ids()
        base = {n: v for n, v in base.items() if n not in own}
        if not base:
            return {"items": [], "total": 0, "mode": mode, "source_nm_ids": source_ids,
                    "offset": offset, "limit": limit, "desc_min_len": DESC_MIN_LEN,
                    "counts": {"a_cnt": 0, "rec_cnt": 0, "captured_cnt": 0}}

        ids = list(base.keys())
        details = await self._details_map(ids)
        meta = await self._cards_meta_map(ids)
        capture = await self._capture_map(ids)
        attached = await self._attached_map(ids)
        queue = await self._queue_map(ids)

        ql = q.strip().lower()
        items: list[dict] = []
        for n in ids:
            b = base[n]
            det = details.get(n) or {}
            m = meta.get(n) or {}
            cap = capture.get(n)
            sources = b.get("sources") or ((m.get("sources") or "").split(",") if m.get("sources") else [])
            item = {
                "nm_id": n,
                "title": det.get("title") or b.get("title") or m.get("title") or "",
                "brand": det.get("brand") or b.get("brand") or m.get("brand") or "",
                "seller": det.get("seller") or "",
                "price": det.get("price") or b.get("price") or m.get("price") or "",
                "old_price": det.get("old_price") or "",
                "photo": _photo(det.get("images")) or b.get("image_url") or m.get("image_url"),
                "desc_len": int(det.get("desc_len") or 0),
                "chars_cnt": int(det.get("chars_cnt") or 0),
                "collected_at": det.get("collected_at") or b.get("collected_at") or m.get("collected_at"),
                "in_a": bool(b.get("in_a")),
                "rec_cnt": int(b.get("rec_cnt") or 0),
                "recommended_by": list(b.get("recommended_by") or [])[:5],
                "captured": bool(cap),
                "is_own": bool(cap.get("is_own")) if cap else False,
                "is_hidden": bool(cap.get("is_hidden")) if cap else False,
                "attached_to": attached.get(n, []),
                "queue_status": (queue.get(n) or {}).get("status"),
                "queue_error": (queue.get(n) or {}).get("error_msg"),
                "queue_processed_at": (queue.get(n) or {}).get("processed_at"),
                "sources": sources,
            }
            item["has_content"] = item["desc_len"] >= DESC_MIN_LEN
            item["visible"] = bool(item["captured"] or item["in_a"] or item["attached_to"])
            item["can_attach"] = bool(item["visible"] and not item["is_hidden"] and not item["is_own"])
            if ql:
                hay = " ".join(str(item.get(k) or "") for k in
                               ("title", "brand", "seller", "nm_id")).lower()
                hay += " " + " ".join(str(a.get("title") or "") for a in item["attached_to"]).lower()
                if ql not in hay:
                    continue
            if only_content and not item["has_content"]:
                continue
            if only_recommended and not item["rec_cnt"]:
                continue
            items.append(item)

        items.sort(key=lambda x: (
            0 if x["in_a"] else 1,
            -int(x["rec_cnt"] or 0),
            -int(x["desc_len"] or 0),
            -int(x["chars_cnt"] or 0),
            -_ts(x.get("collected_at")),
        ))
        total = len(items)
        counts = {
            "a_cnt": sum(1 for x in items if x["in_a"]),
            "rec_cnt": sum(1 for x in items if x["rec_cnt"]),
            "captured_cnt": sum(1 for x in items if x["captured"]),
        }
        return {
            "items": items[offset:offset + limit],
            "total": total,
            "mode": mode,
            "source_nm_ids": source_ids,
            "offset": offset,
            "limit": limit,
            "desc_min_len": DESC_MIN_LEN,
            "counts": counts,
        }

    async def bulk_attach(self, raw_nm_ids, raw_target_nm_ids,
                          user_id: int | None = None, mode: str = "recommend") -> dict:
        """Массовая привязка captured-кандидатов к нашим карточкам (§16.5).

        Не трогает `search/manual/sibling`, не ставит в очередь, идемпотентна по паре.
        """
        nm_ids = _ints(raw_nm_ids, limit=200)
        target_ids = _ints(raw_target_nm_ids, limit=20)
        if not nm_ids:
            raise ValueError("Выберите хотя бы одного конкурента")
        if not target_ids:
            raise ValueError("Выберите хотя бы одну нашу карточку")
        target_ids = await self._pick_sources(target_ids)

        own = await self._own_card_ids()
        nm_ids = [n for n in nm_ids if n not in own and n not in target_ids]
        if not nm_ids:
            raise ValueError("Нечего привязывать: кандидаты совпадают с нашими карточками")

        capture = await self._capture_map(nm_ids)
        attached = await self._attached_map(nm_ids)
        eligible: list[int] = []
        skipped_candidates: list[dict] = []
        for n in nm_ids:
            cap = capture.get(n)
            if cap and bool(cap.get("is_own")):
                skipped_candidates.append({"nm_id": n, "reason": "own"})
            elif cap and bool(cap.get("is_hidden")):
                skipped_candidates.append({"nm_id": n, "reason": "hidden"})
            elif not cap and not attached.get(n):
                # Нет capture и нет привязки к нашей карточке — кандидат не виден компании.
                skipped_candidates.append({"nm_id": n, "reason": "not_captured"})
            else:
                eligible.append(n)

        requested = len(nm_ids) * len(target_ids)
        if not eligible:
            return {
                "added": 0, "exists": 0,
                "skipped": len(skipped_candidates) * len(target_ids),
                "requested": requested, "mode": mode,
                "target_nm_ids": target_ids,
                "skipped_candidates": skipped_candidates[:50],
                "errors": [],
            }

        details = await self._details_map(eligible)
        meta = await self._cards_meta_map(eligible)

        # Какие пары уже есть: один запрос вместо SELECT на каждую пару.
        existing: set[tuple[int, int]] = set()
        tph = ",".join(f":t{i}" for i in range(len(target_ids)))
        tparams = {f"t{i}": v for i, v in enumerate(target_ids)}
        for chunk in _chunks(eligible):
            ph = ",".join(f":n{i}" for i in range(len(chunk)))
            rows = (await self.db.execute(text(f"""
                SELECT source_nm_id, nm_id FROM wb_competitor_cards
                WHERE source_nm_id IN ({tph}) AND nm_id IN ({ph})
            """), {**tparams, **{f"n{i}": v for i, v in enumerate(chunk)}})).mappings().all()
            for r in rows:
                existing.add((int(r["source_nm_id"]), int(r["nm_id"])))

        added = 0
        exists = 0
        await self.db.rollback()
        async with self.db.begin():
            for n in eligible:
                det = details.get(n) or {}
                m = meta.get(n) or {}
                title = str(det.get("title") or m.get("title") or "")[:500]
                brand = str(det.get("brand") or m.get("brand") or "")[:255]
                price = str(det.get("price") or m.get("price") or "")[:50]
                img = str(_photo(det.get("images")) or m.get("image_url") or "")[:1000]
                for t in target_ids:
                    if (t, n) in existing:
                        exists += 1
                        continue
                    r = await self.db.execute(text("""
                        INSERT IGNORE INTO wb_competitor_cards
                          (source_nm_id, query_phrase, position, nm_id, title, brand,
                           price, image_url, source, added_by)
                        VALUES (:s, '', 0, :n, :t, :b, :p, :img, 'capture', :u)
                    """), {"s": t, "n": n, "t": title, "b": brand,
                           "p": price, "img": img, "u": user_id})
                    if int(r.rowcount or 0) > 0:
                        added += 1
                        existing.add((t, n))
                    else:
                        exists += 1

        return {
            "added": added,
            "exists": exists,
            "skipped": len(skipped_candidates) * len(target_ids),
            "requested": requested,
            "mode": mode,
            "target_nm_ids": target_ids,
            "skipped_candidates": skipped_candidates[:50],
            "errors": [],
        }

    async def history(self, nm_id: int, limit: int = 50) -> dict:
        """Снимки контента (append-only, дедуп по content_hash при capture)."""
        rows = (await self.db.execute(text("""
            SELECT id, nm_id, title, description, characteristics, brand, seller, price, old_price,
                   content_hash, source, captured_company_id, captured_by, created_at
            FROM wb_competitor_details_history
            WHERE nm_id=:n ORDER BY id DESC LIMIT :lim
        """), {"n": nm_id, "lim": limit})).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            chars = _j(d.get("characteristics")) or []
            d["characteristics"] = chars if isinstance(chars, list) else []
            d["desc_len"] = len(str(d.get("description") or ""))
            d["chars_cnt"] = len(d["characteristics"])
            d["description_preview"] = str(d.get("description") or "")[:300]
            d.pop("description", None)
            items.append(d)
        return {"nm_id": nm_id, "items": items}

    async def details(self, nm_id: int) -> dict | None:
        """Полная карточка конкурента для попапа: контент, фото, характеристики, цены."""
        row = (await self.db.execute(text("""
            SELECT nm_id, title, description, brand, seller, subject_name, url,
                   price, old_price, images, characteristics,
                   COALESCE(collected_at, first_collected_at) AS collected_at,
                   first_collected_at
            FROM wb_competitor_details
            WHERE nm_id=:n ORDER BY COALESCE(collected_at, first_collected_at) DESC, id DESC LIMIT 1
        """), {"n": nm_id})).mappings().first()
        if not row:
            return None
        d = dict(row)
        images = _images(d.get("images"))
        d["images"] = images
        d["photo"] = images[0] if images else None
        chars = _j(d.get("characteristics")) or []
        d["characteristics"] = chars if isinstance(chars, list) else []
        d["url"] = d.get("url") or f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
        d["price_history"] = await self._price_history(
            nm_id, d.get("price"), d.get("old_price"), d.get("collected_at")
        )
        return d

    async def _price_history(self, nm_id: int, price, old_price, collected_at) -> list[dict]:
        """Точки изменения цены из снимков истории (только когда цена реально менялась)."""
        rows = (await self.db.execute(text("""
            SELECT price, old_price, created_at
            FROM wb_competitor_details_history
            WHERE nm_id=:n ORDER BY id
        """), {"n": nm_id})).mappings().all()
        points: list[dict] = []
        prev: tuple[str, str] | None = None
        for r in rows:
            pair = (str(r.get("price") or ""), str(r.get("old_price") or ""))
            if pair == prev:
                continue
            points.append({
                "price": pair[0],
                "old_price": pair[1],
                "at": r.get("created_at"),
            })
            prev = pair
        cur = (str(price or ""), str(old_price or ""))
        if cur[0] and cur != prev:
            points.append({
                "price": cur[0],
                "old_price": cur[1],
                "at": collected_at,
            })
        return points

    async def capture_visible(self, nm_id: int) -> bool:
        """Есть ли карточка в собранных у этой компании (для доступа к попапу)."""
        return bool(await self._capture_row(nm_id))

    async def has_competitor(self, source_nm_id: int, nm_id: int) -> bool:
        """Привязан ли конкурент к нашей карточке (для доступа к попапу)."""
        r = (await self.db.execute(text("""
            SELECT 1 FROM wb_competitor_cards
            WHERE source_nm_id=:s AND nm_id=:n LIMIT 1
        """), {"s": source_nm_id, "n": nm_id})).first()
        return r is not None

    async def _capture_row(self, nm_id: int) -> dict | None:
        scope = ""
        params: dict = {"n": nm_id}
        if self.company_id is not None:
            scope = "AND company_id=:cid"
            params["cid"] = self.company_id
        r = (await self.db.execute(text(f"""
            SELECT nm_id, company_id, is_own, is_hidden FROM wb_competitor_capture
            WHERE nm_id=:n {scope} ORDER BY last_seen_at DESC LIMIT 1
        """), params)).mappings().first()
        return dict(r) if r else None

    async def attach(self, nm_id: int, source_nm_id: int, user_id: int | None) -> dict:
        """Привязать собранную карточку к нашей: `wb_competitor_cards(source='capture')`.

        Идемпотентно (uq_source_phrase_nm в wb_competitor_cards). Ни анализ, ни очередь
        не трогаем — контент уже собран.
        """
        try:
            source_nm_id = int(source_nm_id or 0)
        except (TypeError, ValueError):
            raise ValueError("Укажите нашу карточку")
        if not source_nm_id or source_nm_id == nm_id:
            raise ValueError("Укажите другую нашу карточку")
        if not await self.owns_card(source_nm_id):
            raise ValueError("Карточка не найдена в вашей компании")
        if not await self._capture_row(nm_id):
            raise ValueError("Карточка не собрана — нет в wb_competitor_capture")
        det = (await self.db.execute(text("""
            SELECT title, brand, price, images FROM wb_competitor_details WHERE nm_id=:n LIMIT 1
        """), {"n": nm_id})).mappings().first()
        det = dict(det) if det else {}
        await self.db.rollback()
        async with self.db.begin():
            # Идемпотентность без опоры на уникальный индекс: пара уже есть — не дублируем.
            exists = (await self.db.execute(text("""
                SELECT 1 FROM wb_competitor_cards
                WHERE source_nm_id=:s AND nm_id=:n LIMIT 1
            """), {"s": source_nm_id, "n": nm_id})).first()
            if exists:
                return {"attached": 0, "source_nm_id": source_nm_id, "exists": True}
            r = await self.db.execute(text("""
                INSERT IGNORE INTO wb_competitor_cards
                  (source_nm_id, query_phrase, position, nm_id, title, brand, price, image_url, source, added_by)
                VALUES (:s, '', 0, :n, :t, :b, :p, :img, 'capture', :u)
            """), {
                "s": source_nm_id, "n": nm_id,
                "t": str(det.get("title") or "")[:500],
                "b": str(det.get("brand") or "")[:255],
                "p": str(det.get("price") or "")[:50],
                "img": str(_photo(det.get("images")) or "")[:1000],
                "u": user_id,
            })
            added = int(r.rowcount or 0)
        return {"attached": added, "source_nm_id": source_nm_id, "exists": added == 0}

    async def detach(self, nm_id: int, source_nm_id: int) -> dict:
        """Отвязать только пару (nm × наша карточка), только строку `source='capture'`."""
        try:
            source_nm_id = int(source_nm_id or 0)
        except (TypeError, ValueError):
            raise ValueError("Укажите нашу карточку")
        if not source_nm_id:
            raise ValueError("Укажите нашу карточку")
        if not await self.owns_card(source_nm_id):
            raise ValueError("Карточка не найдена в вашей компании")
        await self.db.rollback()
        async with self.db.begin():
            r = await self.db.execute(text("""
                DELETE FROM wb_competitor_cards
                WHERE source='capture' AND nm_id=:n AND source_nm_id=:s
            """), {"n": nm_id, "s": source_nm_id})
        return {"detached": int(r.rowcount or 0), "source_nm_id": source_nm_id}

    async def hide(self, nm_id: int, hidden: bool = True) -> dict:
        """Скрыть/вернуть в своём списке: `wb_competitor_capture.is_hidden`."""
        if self.company_id is None:
            raise ValueError("Выберите компанию в шапке — скрытие своё у каждой компании")
        await self.db.rollback()
        async with self.db.begin():
            r = await self.db.execute(text("""
                UPDATE wb_competitor_capture SET is_hidden=:h
                WHERE nm_id=:n AND company_id=:c
            """), {"h": 1 if hidden else 0, "n": nm_id, "c": self.company_id})
            changed = int(r.rowcount or 0)
        if not changed:
            raise ValueError("Карточка не найдена в собранных")
        return {"nm_id": nm_id, "is_hidden": bool(hidden)}

    # ---------- §11.2/Ш11: фразы из описаний конкурентов ----------

    # ---------- прогресс AI-вызовов (для модалок) ----------

    async def _run_start(self, run_id: str | None, nm_id: int, kind: str,
                         total: int, company_id: int | None) -> None:
        if not run_id:
            return
        await self.db.execute(text("""
            DELETE FROM wb_competitor_run WHERE created_at < DATE_SUB(NOW(), INTERVAL 2 DAY)
        """))
        await self.db.execute(text("""
            INSERT INTO wb_competitor_run
              (run_id, company_id, source_nm_id, kind, status, attempt, total)
            VALUES (:r, :c, :n, :k, 'running', 0, :t)
            ON DUPLICATE KEY UPDATE status='running', attempt=0, total=VALUES(total),
              model=NULL, error=NULL
        """), {"r": run_id[:64], "c": company_id, "n": nm_id, "k": kind, "t": total})
        await self.db.commit()

    async def _run_step(self, run_id: str | None, attempt: int, model: str) -> None:
        if not run_id:
            return
        await self.db.execute(text("""
            UPDATE wb_competitor_run SET attempt=:a, model=:m, status='running'
            WHERE run_id=:r
        """), {"a": attempt, "m": model[:190], "r": run_id[:64]})
        await self.db.commit()

    async def _run_finish(self, run_id: str | None, status: str, error: str | None = None) -> None:
        if not run_id:
            return
        await self.db.execute(text("""
            UPDATE wb_competitor_run SET status=:s, error=:e WHERE run_id=:r
        """), {"s": status, "e": (error or "")[:500] or None, "r": run_id[:64]})
        await self.db.commit()

    async def get_run(self, nm_id: int, run_id: str) -> dict | None:
        row = (await self.db.execute(text("""
            SELECT run_id, source_nm_id, kind, status, attempt, total, model, error,
                   created_at, updated_at
            FROM wb_competitor_run
            WHERE run_id=:r AND source_nm_id=:n LIMIT 1
        """), {"r": run_id[:64], "n": nm_id})).mappings().first()
        if not row:
            return None
        d = dict(row)
        d["is_free"] = ":free" in (d.get("model") or "").lower()
        return d

    async def _company_settings(self, nm_id: int) -> dict:
        company_id = self.company_id or await self._company_for(nm_id)
        if not company_id:
            return {}
        # единый загрузчик настроек (в т.ч. seo_llm_* — модели «другого сервиса»)
        row = await llm_provider.company_row(self.db, company_id)
        d = dict(row) if row else {}
        d["company_id"] = company_id
        return d

    async def _competitors_with_content(self, nm_id: int,
                                        limit: int = MAX_COMPETITORS_FOR_AI) -> list[dict]:
        """Привязанные конкуренты, у которых уже собрано описание."""
        rows = (await self.db.execute(text("""
            SELECT d.nm_id, d.title, d.brand, d.description
            FROM wb_competitor_details d
            JOIN (SELECT DISTINCT nm_id FROM wb_competitor_cards WHERE source_nm_id=:n) c
              ON c.nm_id = d.nm_id
            WHERE CHAR_LENGTH(COALESCE(d.description,'')) >= :minlen
            ORDER BY CHAR_LENGTH(d.description) DESC
            LIMIT :lim
        """), {"n": nm_id, "minlen": DESC_MIN_LEN, "lim": limit})).mappings().all()
        return [dict(r) for r in rows]

    async def _phrase_stats(self, phrases: list[str], subject: str = "") -> dict[str, dict]:
        """Статистика фраз по всей базе wb_sr_report_item_phrases (фильтр по предмету)."""
        cleaned = [_norm_phrase(x) for x in (phrases or [])]
        cleaned = [x for x in dict.fromkeys(cleaned) if x]
        if not cleaned:
            return {}
        ph = ",".join(f":p{i}" for i in range(len(cleaned)))
        rows = (await self.db.execute(text(f"""
            SELECT LOWER(p.phrase) AS phrase,
                   SUM(p.orders) AS orders,
                   MAX(COALESCE(p.frequency_current, p.week_frequency, 0)) AS freq,
                   COUNT(DISTINCT p.nmID) AS cards
            FROM wb_sr_report_item_phrases p
            JOIN wb_sr_report_items i ON i.id = p.item_id
            WHERE LOWER(p.phrase) IN ({ph})
              AND (:subj = '' OR i.subject_name = :subj)
            GROUP BY LOWER(p.phrase)
        """), {**{f"p{i}": v for i, v in enumerate(cleaned)}, "subj": subject or ""})).mappings().all()
        return {str(r["phrase"]): {"orders": int(r["orders"] or 0),
                                   "freq": int(r["freq"] or 0),
                                   "cards": int(r["cards"] or 0)} for r in rows}

    async def list_phrases(self, nm_id: int) -> dict:
        rows = (await self.db.execute(text("""
            SELECT p.id, p.phrase, p.source, p.hit_cnt, p.orders, p.freq, p.cards_cnt,
                   p.in_db, p.is_selected, p.model, p.created_at,
                   EXISTS(SELECT 1 FROM wb_seo_target t
                          WHERE t.nmID=p.source_nm_id AND LOWER(t.phrase)=LOWER(p.phrase)) AS in_targets
            FROM wb_competitor_phrase p
            WHERE p.source_nm_id=:n
            ORDER BY p.is_selected DESC, p.in_db DESC, p.orders DESC, p.hit_cnt DESC, p.id
        """), {"n": nm_id})).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            d["in_db"] = bool(d.get("in_db"))
            d["is_selected"] = bool(d.get("is_selected"))
            d["in_targets"] = bool(d.get("in_targets"))
            for k in ("hit_cnt", "orders", "freq", "cards_cnt"):
                d[k] = int(d.get(k) or 0)
            items.append(d)
        return {"nm_id": nm_id, "items": items,
                "selected_cnt": sum(1 for x in items if x["is_selected"])}

    async def analyze_phrases(self, nm_id: int, run_id: str | None = None,
                              user_id: int | None = None) -> dict:
        """LLM: вытащить поисковые фразы из описаний конкурентов + статистика нашей базы."""
        card = await self._card(nm_id) or {}
        comps = await self._competitors_with_content(nm_id)
        if not comps:
            raise ValueError("Нет собранных описаний конкурентов: привяжите конкурентов и соберите контент расширением")
        st = await self._company_settings(nm_id)
        company_id = st.get("company_id") or self.company_id or card.get("company_id")
        if not company_id:
            raise ValueError("Не удалось определить компанию карточки")
        parts = []
        for c in comps:
            parts.append(f"--- Конкурент nmID {c['nm_id']} ---\n"
                         f"Заголовок: {(c.get('title') or '')[:200]}\n"
                         f"Описание: {(c.get('description') or '')[:1000]}\n")
        up = (f"=== НАШ ТОВАР ===\nНазвание: {card.get('title') or ''}\n"
              f"Предмет: {card.get('subject_name') or ''}\nБренд: {card.get('brand') or ''}\n\n"
              f"=== ОПИСАНИЯ КОНКУРЕНТОВ ({len(comps)} шт) ===\n"
              + "\n".join(parts)
              + '\nИзвлеки поисковые фразы и верни JSON {"phrases": [...]}. '
                'Не рассуждай, не пиши пояснений — только JSON.')
        custom_prompt = (st.get("seo_phrases_prompt") or "").strip()
        prompt = custom_prompt or DEFAULT_PHRASES_PROMPT
        prompt_source = "company" if custom_prompt else "default"
        messages = [{"role": "system", "content": prompt},
                    {"role": "user", "content": up}]
        cands = (await llm.model_candidates(
            self.db, company_id, kind="newcard",
        ))[:MAX_AI_ATTEMPTS]
        await self._run_start(run_id, nm_id, "phrases", len(cands), company_id)
        last_err, data, used_model = "All models failed", None, None
        for i, try_model in enumerate(cands):
            await self._run_step(run_id, i + 1, try_model)
            res = await llm.chat(self.db, messages, company_id, temperature=0.1,
                                 max_tokens=PHRASES_MAX_TOKENS, model=try_model,
                                 reasoning_effort="low", send_max_tokens=True,
                                 note=f"phrases nm {nm_id}, кандидат {i + 1}/{len(cands)}",
                                 scenario="newcard_phrases", user_id=user_id, nm_id=nm_id)
            if res.get("error"):
                detail = str(res["error"])
                if res.get("finish_reason") and "finish_reason" not in detail:
                    detail += f", finish_reason={res['finish_reason']}"
                if res.get("completion_tokens"):
                    detail += f", tokens={res['completion_tokens']}"
                await llm.mark_model(self.db, try_model, False, detail)
                last_err = f"model {try_model}: {detail}"
                continue
            raw = res.get("content") or ""
            parsed = _parse_json(raw)
            phrases = _phrases_from_parsed(parsed)
            if not isinstance(phrases, list) or not phrases:
                head = " ".join(raw.split())[:180]
                finish = str(res.get("finish_reason") or "")
                if not raw.strip():
                    reason = "пустой ответ"
                    if res.get("empty_reason"):
                        reason += f" ({str(res['empty_reason'])[:180]})"
                elif not isinstance(parsed, (dict, list)):
                    reason = f"ответ не JSON: {head!r}"
                elif isinstance(parsed, dict) and "phrases" in parsed:
                    reason = f"phrases не список фраз: {head!r}"
                else:
                    reason = f"в JSON нет списка phrases: {head!r}"
                if finish:
                    reason += f", finish_reason={finish}"
                    if finish == "length":
                        reason += " (ответ обрезан по лимиту токенов)"
                err = f"model {try_model}: {reason}"
                await llm.ai_log("parse-error", try_model, messages, raw,
                                 http=res.get("http") or "",
                                 note=f"phrases nm {nm_id}", provider=res.get("provider") or "")
                await llm.mark_model(self.db, try_model, False, err)
                last_err = err
                continue
            await llm.mark_model(self.db, try_model, True)
            data, used_model = phrases, (res.get("model") or try_model)
            break
        if not data:
            await self._run_finish(run_id, "error", last_err)
            raise ValueError(last_err)

        norm: list[str] = []
        for raw in data:
            if isinstance(raw, dict):
                raw = raw.get("phrase") or raw.get("text") or ""
            p = _norm_phrase(raw)
            if 3 <= len(p) <= 200 and p not in norm:
                norm.append(p)
        norm = norm[:MAX_PHRASES]
        if not norm:
            await self._run_finish(run_id, "error", "Модель не вернула пригодных фраз")
            raise ValueError("Модель не вернула пригодных фраз")

        descs = [(c.get("description") or "").lower() for c in comps]
        stats = await self._phrase_stats(norm, card.get("subject_name") or "")
        await self.db.rollback()
        async with self.db.begin():
            for p in norm:
                s = stats.get(p) or {}
                hits = sum(1 for d in descs if p in d)
                await self.db.execute(text("""
                    INSERT INTO wb_competitor_phrase
                      (company_id, source_nm_id, phrase, source, hit_cnt, orders, freq,
                       cards_cnt, in_db, model)
                    VALUES (:c, :n, :p, 'ai', :h, :o, :f, :cc, :indb, :m)
                    ON DUPLICATE KEY UPDATE
                      hit_cnt=VALUES(hit_cnt), orders=VALUES(orders), freq=VALUES(freq),
                      cards_cnt=VALUES(cards_cnt), in_db=VALUES(in_db), model=VALUES(model)
                """), {"c": company_id, "n": nm_id, "p": p, "h": hits,
                       "o": int(s.get("orders") or 0), "f": int(s.get("freq") or 0),
                       "cc": int(s.get("cards") or 0), "indb": 1 if s else 0, "m": used_model})
        out = await self.list_phrases(nm_id)
        out["model"] = used_model
        out["competitors_cnt"] = len(comps)
        out["prompt_version"] = PHRASES_PROMPT_VERSION
        out["prompt_source"] = prompt_source
        await self._run_finish(run_id, "done")
        return out

    async def select_phrases(self, nm_id: int, phrases: list[str], selected: bool = True) -> dict:
        norm = [_norm_phrase(x) for x in (phrases or [])]
        norm = [x for x in dict.fromkeys(norm) if x]
        if not norm:
            raise ValueError("Не переданы фразы")
        ph = ",".join(f":p{i}" for i in range(len(norm)))
        await self.db.rollback()
        async with self.db.begin():
            r = await self.db.execute(text(f"""
                UPDATE wb_competitor_phrase SET is_selected=:s
                WHERE source_nm_id=:n AND phrase IN ({ph})
                  AND (:cid IS NULL OR company_id=:cid)
            """), {"s": 1 if selected else 0, "n": nm_id, "cid": self.company_id,
                   **{f"p{i}": v for i, v in enumerate(norm)}})
        return {"updated": int(r.rowcount or 0), "selected": bool(selected)}

    async def add_phrase(self, nm_id: int, phrase: str, user_id: int | None = None) -> dict:
        p = _norm_phrase(phrase)
        if len(p) < 2:
            raise ValueError("Пустая фраза")
        card = await self._card(nm_id) or {}
        company_id = self.company_id or await self._company_for(nm_id)
        if not company_id:
            raise ValueError("Не удалось определить компанию карточки")
        stats = await self._phrase_stats([p], card.get("subject_name") or "")
        s = stats.get(p) or {}
        await self.db.rollback()
        async with self.db.begin():
            await self.db.execute(text("""
                INSERT INTO wb_competitor_phrase
                  (company_id, source_nm_id, phrase, source, hit_cnt, orders, freq,
                   cards_cnt, in_db, is_selected)
                VALUES (:c, :n, :p, 'manual', 0, :o, :f, :cc, :indb, 1)
                ON DUPLICATE KEY UPDATE
                  is_selected=1, orders=VALUES(orders), freq=VALUES(freq),
                  cards_cnt=VALUES(cards_cnt), in_db=VALUES(in_db)
            """), {"c": company_id, "n": nm_id, "p": p,
                   "o": int(s.get("orders") or 0), "f": int(s.get("freq") or 0),
                   "cc": int(s.get("cards") or 0), "indb": 1 if s else 0})
        return {"phrase": p, "in_db": bool(stats)}

    async def delete_phrase(self, nm_id: int, phrase_id: int) -> bool:
        await self.db.rollback()
        async with self.db.begin():
            r = await self.db.execute(text("""
                DELETE FROM wb_competitor_phrase
                WHERE id=:i AND source_nm_id=:n AND (:cid IS NULL OR company_id=:cid)
            """), {"i": phrase_id, "n": nm_id, "cid": self.company_id})
        return bool(r.rowcount)

    async def generate_description(self, nm_id: int, phrases: list[str] | None = None,
                                   run_id: str | None = None,
                                   user_id: int | None = None) -> dict:
        """Ш3: title + description по выбранным фразам, характеристикам и описаниям конкурентов."""
        card = await self._card(nm_id)
        if not card:
            raise ValueError("Наша карточка не найдена")
        sel = [_norm_phrase(x) for x in (phrases or []) if _norm_phrase(x)]
        if not sel:
            sel = [str(x) for x in (await self.db.execute(text("""
                SELECT phrase FROM wb_competitor_phrase
                WHERE source_nm_id=:n AND is_selected=1
                ORDER BY in_db DESC, orders DESC, hit_cnt DESC, id
            """), {"n": nm_id})).scalars().all()]
        sel = list(dict.fromkeys(sel))[:12]
        if not sel:
            raise ValueError("Выберите фразы для генерации")
        comps = await self._competitors_with_content(nm_id, 10)
        if not comps:
            raise ValueError("Нет описаний конкурентов — генерация не по чему")
        st = await self._company_settings(nm_id)
        company_id = st.get("company_id") or self.company_id or card.get("company_id")
        if not company_id:
            raise ValueError("Не удалось определить компанию карточки")
        desc_min = int(st.get("seo_desc_min") or 1500)
        desc_max = int(st.get("seo_desc_max") or 4000)
        custom = (st.get("seo_newcard_prompt") or "").strip()
        base = custom or DEFAULT_DESC_PROMPT
        system = (base.replace("{DESC_MIN}", str(desc_min)).replace("{DESC_MAX}", str(desc_max))
                  .replace("{$descMin}", str(desc_min)).replace("{$descMax}", str(desc_max)))
        prompt_source = "company" if custom else "default"

        char_lines = []
        for c in (card.get("characteristics") or [])[:60]:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name") or "").strip()
            val = c.get("value")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val if str(v).strip())
            val = str(val or "").strip()
            if name:
                char_lines.append(f"- {name}: {val}")
        up = (f"=== НАША КАРТОЧКА ===\nЗаголовок: {card.get('title') or ''}\n"
              f"Бренд: {card.get('brand') or ''}\nПредмет: {card.get('subject_name') or ''}\n"
              f"Текущее описание: {(card.get('description') or '')[:600]}\n")
        if char_lines:
            up += "Характеристики:\n" + "\n".join(char_lines) + "\n"

        # Метрики выбранных фраз: раскладываем на P0 (целевые) / P1 (с заказами) / P2.
        ph_meta: dict[str, dict] = {}
        if sel:
            ph = ",".join(f":p{i}" for i in range(len(sel)))
            rows = (await self.db.execute(text(f"""
                SELECT p.phrase, p.orders, p.freq, p.cards_cnt,
                       EXISTS(SELECT 1 FROM wb_seo_target t
                              WHERE t.nmID=p.source_nm_id AND LOWER(t.phrase)=LOWER(p.phrase)) AS in_targets
                FROM wb_competitor_phrase p
                WHERE p.source_nm_id=:n AND p.phrase IN ({ph})
            """), {"n": nm_id, **{f"p{i}": v for i, v in enumerate(sel)}})).mappings().all()
            ph_meta = {r["phrase"]: dict(r) for r in rows}

        def phrase_line(p: str) -> str:
            m = ph_meta.get(p) or {}
            bits = []
            if int(m.get("orders") or 0):
                bits.append(f"заказов {int(m['orders'])}")
            if int(m.get("freq") or 0):
                bits.append(f"частота {int(m['freq'])}")
            if int(m.get("cards_cnt") or 0):
                bits.append(f"у конкурентов {int(m['cards_cnt'])}")
            return f"- {p}" + (f" · {' · '.join(bits)}" if bits else "")

        tiers: list[list[str]] = [[], [], []]
        for p in sel:
            m = ph_meta.get(p) or {}
            if m.get("in_targets"):
                tiers[0].append(p)
            elif int(m.get("orders") or 0) > 0:
                tiers[1].append(p)
            else:
                tiers[2].append(p)

        up += "\n=== ПОИСКОВЫЕ ФРАЗЫ (по убыванию важности) ===\n"
        tier_titles = (
            "P0 — целевые, обязательно все",
            "P1 — с заказами, обязательно все",
            "P2 — остальные, покрой максимум",
        )
        for i, tier in enumerate(tiers):
            if tier:
                up += tier_titles[i] + ":\n" + "\n".join(phrase_line(p) for p in tier) + "\n"
        up += f"\n\n=== ОПИСАНИЯ КОНКУРЕНТОВ ({len(comps)} шт, перефразируй, не копируй) ===\n"
        for c in comps:
            up += (f"\n--- nmID {c['nm_id']} ---\nЗаголовок: {(c.get('title') or '')[:200]}\n"
                   f"Описание: {(c.get('description') or '')[:1200]}\n")
        up += (f"\nСформируй title (≤60 символов) и description ({desc_min}–{desc_max} символов) "
               "по правилам системного промпта. Верни только JSON.")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": up}]

        cands = (await llm.model_candidates(
            self.db, company_id, kind="newcard",
        ))[:MAX_AI_ATTEMPTS]
        await self._run_start(run_id, nm_id, "generate", len(cands), company_id)
        max_tokens = int(st.get("seo_summary_max_tokens") or 4000)
        last_err, data, used_model, raw = "All models failed", None, None, ""
        for i, try_model in enumerate(cands):
            await self._run_step(run_id, i + 1, try_model)
            res = await llm.chat(self.db, messages, company_id, temperature=0.7,
                                 max_tokens=max_tokens, model=try_model,
                                 note=f"generate nm {nm_id}, кандидат {i + 1}/{len(cands)}",
                                 scenario="newcard_generate", user_id=user_id, nm_id=nm_id)
            if res.get("error"):
                await llm.mark_model(self.db, try_model, False, res["error"])
                last_err = f"model {try_model}: {res['error']}"
                continue
            parsed = _unwrap_dict(res.get("content") or "")
            title = _resp_title(parsed)
            description = _resp_desc(parsed)
            problem = _desc_problem(title, description, desc_min)
            if problem and description:
                # Не выбрасываем ответ сразу: просим ту же модель исправить
                # конкретную проблему (список, markdown, длина).
                fix_messages = messages + [
                    {"role": "assistant",
                     "content": json.dumps({"title": title, "description": description},
                                           ensure_ascii=False)},
                    {"role": "user",
                     "content": (f"Твой ответ отклонён: {problem}. Перепиши по правилам "
                                 'системного промпта. Верни только JSON {"title":"...",'
                                 '"description":"..."}.')},
                ]
                fix = await llm.chat(self.db, fix_messages, company_id, temperature=0.3,
                                     max_tokens=max_tokens, model=try_model,
                                     note=f"generate nm {nm_id}, repair {try_model}",
                                     scenario="newcard_generate", user_id=user_id, nm_id=nm_id)
                if not fix.get("error"):
                    p2 = _unwrap_dict(fix.get("content") or "")
                    t2 = _resp_title(p2)
                    d2 = _resp_desc(p2)
                    if not _desc_problem(t2, d2, desc_min):
                        title, description, problem = t2, d2, ""
                        raw_fix = fix.get("content") or ""
                        parsed = {"title": title, "description": description}
                        res = fix
                        res["content"] = raw_fix
            if problem:
                err = f"model {try_model}: {problem}"
                await llm.mark_model(self.db, try_model, False, err)
                last_err = err
                continue
            await llm.mark_model(self.db, try_model, True)
            data, used_model, raw = parsed, (res.get("model") or try_model), (res.get("content") or "")
            break
        if not data:
            await self._run_finish(run_id, "error", last_err)
            raise ValueError(last_err)

        title = _resp_title(data)
        description = _resp_desc(data)
        if len(title) > 60:
            cut = title[:60]
            sp = cut.rfind(" ")
            title = (cut[:sp] if sp > 30 else cut).strip().rstrip(",.")
        low_desc = description.lower()
        phrases_used = [p for p in sel if p.lower() in low_desc]
        phrases_missing = [p for p in sel if p.lower() not in low_desc]
        to_save = {"title": title, "description": description,
                   "phrases": sel, "phrases_used": phrases_used,
                   "phrases_missing": phrases_missing, "model": used_model,
                   "prompt_version": DESC_PROMPT_VERSION, "prompt_source": prompt_source}
        await self.db.rollback()
        async with self.db.begin():
            await self.db.execute(text("""
                INSERT INTO wb_competitor_summary
                  (company_id, source_nm_id, result, raw_ai_response, suggested_title,
                   suggested_description, competitor_count, model)
                VALUES (:c, :n, :r, :raw, :t, :d, :cnt, :m)
                ON DUPLICATE KEY UPDATE company_id=VALUES(company_id), result=VALUES(result),
                  raw_ai_response=VALUES(raw_ai_response), suggested_title=VALUES(suggested_title),
                  suggested_description=VALUES(suggested_description),
                  competitor_count=VALUES(competitor_count), model=VALUES(model)
            """), {"c": company_id, "n": nm_id, "r": json.dumps(to_save, ensure_ascii=False),
                   "raw": raw, "t": title[:500], "d": description,
                   "cnt": len(comps), "m": used_model})
        await self._run_finish(run_id, "done")
        return {"success": True, "title": title, "description": description,
                "title_len": len(title), "desc_len": len(description),
                "phrases": sel, "phrases_used": phrases_used,
                "phrases_missing": phrases_missing,
                "model": used_model, "competitor_count": len(comps),
                "desc_min": desc_min, "desc_max": desc_max,
                "prompt_source": prompt_source, "prompt_version": DESC_PROMPT_VERSION,
                "desc_warning": (len(description) < desc_min or len(description) > desc_max)}

    async def detach_competitor(self, nm_id: int, competitor_nm_id: int) -> bool:
        """Отвязать конкурента от нашей карточки (все строки пары).

        Контент и история в `wb_competitor_details` остаются: карточка может быть
        привязана к другим нашим товарам и снова пригодится из «Собранных карточек».
        """
        if competitor_nm_id == nm_id:
            raise ValueError("Нельзя отвязать нашу же карточку")
        await self.db.rollback()
        async with self.db.begin():
            r = await self.db.execute(text("""
                DELETE FROM wb_competitor_cards
                WHERE source_nm_id=:n AND nm_id=:c
            """), {"n": nm_id, "c": competitor_nm_id})
        return bool(r.rowcount)

    async def _queue(self, source_nm_id: int, nm_ids: list[int]) -> None:
        """Поставить конкурентов в wb_enrich_queue (24ч-правило: свежие не трогаем).

        company_id — компания карточки-источника: строка без него (NULL) была бы
        «ничейной» и её забрал бы любой, кто первый позвонит в /api/ext/next.
        Уже существующую строку не перебиваем: владельцем остаётся тот, кто засеял.
        """
        if not nm_ids:
            return
        cid = self.company_id or await self._company_for(source_nm_id)
        if not cid:
            raise ValueError("Не удалось определить компанию карточки")
        ph = ",".join(f":q{i}" for i in range(len(nm_ids)))
        await self.db.execute(text(f"""
            INSERT INTO wb_enrich_queue (nm_id, company_id)
            SELECT t.nm_id, :cid FROM (
                SELECT DISTINCT nm_id FROM wb_competitor_cards
                WHERE nm_id IN ({ph})
            ) t
            WHERE t.nm_id NOT IN (
                SELECT nm_id FROM wb_competitor_details
                WHERE collected_at > NOW() - INTERVAL 24 HOUR
            )
            ON DUPLICATE KEY UPDATE
              company_id=IF(company_id IS NULL, :cid, company_id),
              status=IF((company_id IS NULL OR company_id=:cid) AND status IN ('done','error'), 'pending', status)
        """), {"cid": cid, **{f"q{i}": v for i, v in enumerate(nm_ids)}})
