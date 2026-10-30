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

import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import SessionLocal
from backend.services import openrouter_service as llm
from backend.services import llm_provider
from backend.services.like_mask import escape_like

# Порог «описания нет»: короче 50 символов считаем пустым (как в §11.2 плана).
DESC_MIN_LEN = 50
# §17.2: через сколько дней контент конкурента считаем устаревшим.
REFRESH_AFTER_DAYS = 30
# §13: окно для поведения в таблице конкурентов (полки/поиск/дубликаты).
BEHAVIOR_DAYS = 30
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
PHRASES_PROMPT_VERSION = "newcard-phrases-v4"
MERGE_PROMPT_VERSION = "newcard-merge-v1"
DESC_PROMPT_VERSION = "newcard-desc-v3"

# Фраз на ОДНОГО конкурента (промпт) и жёсткий кап на ответ модели.
PHRASES_PER_COMPETITOR_MIN = 10
PHRASES_PER_COMPETITOR_MAX = 15
# Сколько уникальных формулировок отдаём модели за один вызов группировки.
# 40 — ответ модели короткий (только группы из 2+ фраз), при 60+ резался по токенам.
MERGE_BATCH = 40
MERGE_MAX_TOKENS = 6000
# Сколько LLM-вызовов идёт одновременно. Пул БД: pool_size=5 + max_overflow=5,
# сервер 1 ГБ, один воркер uvicorn — больше 4 одновременно рискованно.
LLM_PARALLEL = 4
# Сколько моделей пробуем на ОДНОГО конкурента (иначе 20 конкурентов × 4 = 80 вызовов).
PER_CALL_ATTEMPTS = 2


# Промпт извлечения фраз из описания ОДНОГО конкурента (Ш11, v4).
# С 21.10 анализ идёт по одному конкуренту: так модель не «сплавляет» описания
# 20 разных товаров и выдаёт конкретные формулировки каждого, а не общие слова
# категории. Слияние формулировок — отдельным вызовом (DEFAULT_MERGE_PROMPT).
DEFAULT_PHRASES_PROMPT = """Ты — SEO-специалист Wildberries. Тебе дано описание карточки ОДНОГО конкурента.
Задача: собрать 10–15 поисковых фраз, по которым покупатели находят ЭТОТ товар.
Верни ТОЛЬКО JSON без markdown: {"phrases": ["фраза 1", "фраза 2"]}
Поле должно называться именно `phrases` (не `keywords`).
Не пиши рассуждений, пояснений и markdown. Первый символ ответа — `{`, последний — `}`.

ПРАВИЛА:
- 10–15 фраз, 2–5 слов, в нижнем регистре, без знаков препинания и эмодзи.
- Каждая фраза — законченный поисковый запрос на ЭТОТ товар: содержит название товара/предмета или его общеупотребительный синоним (например «органайзер для белья», «коробка для хранения», «книга по вязанию крючком»).
- Фраза должна читаться как запрос в поиске WB: обычно сначала тип товара или его материал/назначение («книга по вязанию», «пряжа шерсть»).
- Можно: материал, назначение, для кого, комплектация, сезон, стиль, способ использования.
- Нельзя: общие маркетинговые обороты («идеальный подарок», «быстрая доставка», «высокое качество», «лучший выбор», «не оставит равнодушным»), призывы, бренды, названия конкурентов, слова «товар», «купить», «wildberries», «оптом».
- Нельзя: конкретные параметры чужой упаковки (масса, объём, количество предметов, цвет, модель) — у нас своя упаковка.
- Не дублируй фразы в разных формулировках: одна мысль — одна фраза.
- Сначала самые типичные формулировки для этого товара, потом более редкие.
- Отвечай на русском."""

# Хвост к своему промпту компании: он написан под общий анализ («15–40 фраз» по
# ВСЕМ описаниям сразу). Суффикс идёт ПОСЛЕ него — позднее правило побеждает.
PHRASES_TASK_SUFFIX = """

ВАЖНО (текущий режим): в запросе ОДНО описание карточки — одного конкурента.
Нужно 10–15 фраз на этот товар (не 15–40: описывать нечего, описаний одно)."""


# Промпт слияния формулировок: «книга по вязанию крючком» и «вязание игрушек крючком книга» —
# одна фраза. Канон берём из ответа модели, но выбор канона потом уточняем по данным
# (сколько разных конкурентов использует формулировку).
#
# ВАЖНО: выводим ТОЛЬКО группы из 2+ фраз. Одиночные фразы сервер добавляет сам —
# требование «каждая фраза входит в группу» раздувало ответ и модель резала его
# по лимиту токенов (слияние молча не срабатывало).
DEFAULT_MERGE_PROMPT = """Ты — SEO-специалист Wildberries. Ниже — поисковые фразы конкурентов; в скобках — сколько разных конкурентов её используют.
Задача: найти группы ОДИНАКОВЫХ ПО СМЫСЛУ формулировок.
Верни ТОЛЬКО JSON без markdown: {"groups":[{"canonical":"...","members":["..."]}]}
Поле должно называться именно `groups` (не `clusters`).
Не пиши рассуждений, пояснений и markdown. Первый символ ответа — `{`, последний — `}`.

ЧТО ОБЪЕДИНЯТЬ (это один и тот же поисковый запрос, записанный по-разному):
- перестановка слов: «книга по вязанию крючком» = «вязание крючком книга»;
- словоформа: «вязанию» = «вязание» = «вязать»;
- синоним вместо слова: «чай для похудения» = «чай для снижения веса»;
- лишнее слово-уточнение, не меняющее сути: «книга по вязанию крючком» = «книга по вязанию крючком игрушек» = «вязание игрушек крючком книга».

ЧТО НЕ ОБЪЕДИНЯТЬ (разные запросы):
- разный смысл: «чай для похудения» и «чай для детей»;
- разный товар: «органайзер для белья» и «органайзер для кухни».

ПРАВИЛА:
- Выводи ТОЛЬКО группы, где минимум 2 фразы. Фразы, которые ни с чем не объединил, НЕ упоминай.
- canonical — самая употребительная формулировка из members (при равенстве — первая). Только формулировка из members, ничего не переписывай.
- members — исходные фразы без изменений, без сокращений и добавлений.
- Каждая исходная фраза — максимум в одной группе.
- Не выдумывай фраз, которых нет во входном списке.
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


def _groups_from_parsed(parsed, depth: int = 0):
    """Группы формулировок из разных форм ответа модели слияния."""
    if depth > 4:
        return None
    if isinstance(parsed, dict):
        for key in ("groups", "clusters", "items", "data", "result", "response", "output"):
            if key in parsed:
                found = _groups_from_parsed(parsed[key], depth + 1)
                if found is not None:
                    return found
        return None
    if isinstance(parsed, list):
        out: list[dict] = []
        for g in parsed:
            if isinstance(g, dict):
                members = g.get("members") or g.get("phrases") or g.get("items") or g.get("variants")
                canon = g.get("canonical") or g.get("phrase") or g.get("title") or ""
                if isinstance(members, str):
                    members = [members]
                if isinstance(members, list) and members:
                    out.append({"canonical": str(canon or ""),
                                "members": [str(x) for x in members]})
            elif isinstance(g, str) and g.strip():
                out.append({"canonical": g, "members": [g]})
        return out or None
    return None


def _validate_groups(groups: list[dict], batch: list[str],
                     counts: dict[str, int]) -> list[list[str]]:
    """Строгая валидация ответа модели слияния.

    - члены группы — только реальные фразы из входа;
    - каждая фраза — максимум в одной группе;
    - канон берём из members, а окончательный выбор — по данным (counts): у какой
      формулировки больше разных конкурентов, та и канон;
    - фразы, не попавшие ни в одну группу, — одиночные группы (ничего не теряем).
    """
    known = {_norm_phrase(p) for p in batch}
    used: set[str] = set()
    out: list[list[str]] = []
    for g in groups:
        members: list[str] = []
        for m in g.get("members") or []:
            n = _norm_phrase(m)
            if n in known and n not in used:
                used.add(n)
                members.append(n)
        if not members:
            continue
        canon = _norm_phrase(g.get("canonical") or "")
        if canon not in members:
            canon = members[0]
        # порядок: по числу конкурентов (данные), при равенстве — канон модели
        members.sort(key=lambda p: (-counts.get(p, 0), 0 if p == canon else 1))
        out.append(members)
    for p in batch:
        n = _norm_phrase(p)
        if n and n not in used:
            used.add(n)
            out.append([n])
    return out


def _comp_content_hash(comp: dict) -> str:
    """md5 описания конкурента — чтобы не звать модель, если описание не менялось."""
    payload = "\n".join([
        str(comp.get("nm_id") or ""),
        str(comp.get("title") or ""),
        str(comp.get("description") or ""),
    ])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


# Предлоги/союзы — не несут смысла, для ключа перестановок их отбрасываем.
_MERGE_STOPWORDS = {
    "по", "для", "от", "с", "в", "на", "и", "к", "о", "об", "из", "у", "за", "до",
    "при", "без", "под", "над", "то", "же", "ли", "бы", "а", "но", "или", "не",
}


def _perm_key(phrase: str) -> tuple:
    """Ключ для чистых перестановок слов: значимые слова фразы, отсортированные.

    «книга по вязанию крючком» и «крючком по вязанию книга» дают один ключ —
    такие группы собираем без модели.
    """
    norm = _norm_phrase(phrase)
    words = [w for w in norm.split() if w not in _MERGE_STOPWORDS]
    if not words:
        words = norm.split()
    return tuple(sorted(words))


# Есть ли новая схема фраз (миграция 20261026). True — кэшируем, False — переспрашиваем
# (после применения миграции подхватится без перезапуска).
_PHRASE_SCHEMA_OK: bool | None = None
# Есть ли прогресс-разбора (миграция 20261027): phase/done_ids в wb_competitor_run.
_RUN_PROGRESS_OK: bool | None = None


async def _phrase_schema_ready(db: AsyncSession) -> bool:
    """Проверка наличия wb_competitor_phrase_comp и колонки variants_cnt."""
    global _PHRASE_SCHEMA_OK
    if _PHRASE_SCHEMA_OK:
        return True
    try:
        await db.execute(text("SELECT variants_cnt FROM wb_competitor_phrase LIMIT 1"))
        await db.execute(text("SELECT id FROM wb_competitor_phrase_comp LIMIT 1"))
        _PHRASE_SCHEMA_OK = True
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass
        _PHRASE_SCHEMA_OK = False
    return _PHRASE_SCHEMA_OK


async def _run_progress_ready(db: AsyncSession) -> bool:
    """Есть ли phase/done_ids в wb_competitor_run (миграция 20261027)."""
    global _RUN_PROGRESS_OK
    if _RUN_PROGRESS_OK:
        return True
    try:
        await db.execute(text("SELECT phase, done_ids FROM wb_competitor_run LIMIT 1"))
        _RUN_PROGRESS_OK = True
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass
        _RUN_PROGRESS_OK = False
    return _RUN_PROGRESS_OK


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
    """Первое фото: JSON-строка, двойное кодирование, список объектов или простой URL."""
    images = _images(photos_raw)
    return images[0] if images else None


def _images(raw) -> list[str]:
    """Нормализуем images: JSON-строка, двойное кодирование, список объектов или простой URL."""
    if raw is None:
        return []
    if isinstance(raw, (list, dict)):
        val = raw
    else:
        s = str(raw).strip()
        if not s:
            return []
        val = _j(s)
        if isinstance(val, str):
            val = _j(val) if val.strip().startswith(("[", "{")) else [val]
        elif val is None:
            val = [s]
    if isinstance(val, dict):
        nested = val.get("images") or val.get("urls")
        val = nested if nested is not None else [val]
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
    """Экранируем спецсимволы LIKE (% _ \\) в пользовательском вводе.

    Общий хелпер — как в остальных сервисах (иначе '_' в артикуле/фразе
    превращается в wildcard и поиск находит лишнее).
    """
    return f"%{escape_like(q.strip())}%"


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


def _int_price(v) -> int | None:
    """Цена из БД: INT или строка вида «1 021 ₽» / «1021.0»."""
    if v is None or v == "":
        return None
    s = re.sub(r"[^\d]", "", str(v))
    return int(s) if s else None


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
            SELECT 1 FROM wbcards WHERE nmID=:n AND (company_id=:c OR company_id IS NULL) LIMIT 1
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
                   q.added_by, q.created_at, q.updated_at,
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

    async def reset_queries(self, nm_id: int) -> int:
        """Вернуть запросы карточки в очередь — расширение пересоберёт их заново.

        Фразы и настройки не трогаем: статус снова становится 'pending', и poller
        расширения (/api/ext/search_next?source=compquery) заберёт их по одной.
        """
        await self.db.rollback()
        company = await self._company_for(nm_id)
        if not company:
            return 0
        async with self.db.begin():
            r = await self.db.execute(text("""
                UPDATE wb_competitor_query
                SET status='pending', updated_at=NOW()
                WHERE source_nm_id=:n AND company_id=:c AND is_active=1
            """), {"n": nm_id, "c": company})
        return int(r.rowcount or 0)

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

    async def _behavior_map(self, ids: list[int]) -> dict[int, dict]:
        """Поведение конкурента для таблицы: полки, клипы, поиск, дубликаты, Δ цены.

        Один батч по nm_id (без N+1), окно BEHAVIOR_DAYS, скоуп — компания.
        Таблицы полок/дубликатов могут отсутствовать на старом стенде — тогда
        блок просто пустой, остальные метрики считаются.
        """
        out: dict[int, dict] = {int(n): {} for n in ids}
        if not ids:
            return out
        cid = self.company_id
        days = BEHAVIOR_DAYS
        for chunk in _chunks(ids):
            ph = ",".join(f":b{i}" for i in range(len(chunk)))
            params: dict = {f"b{i}": v for i, v in enumerate(chunk)}
            if cid is not None:
                params["cid"] = cid

            # 1. Полки: последний срез по каждой полке, где встречался конкурент.
            try:
                scope = "" if cid is None else "AND s.company_id=:cid"
                rows = (await self.db.execute(text(f"""
                    SELECT i.nm_id,
                           COUNT(DISTINCT i.shelf_id) AS shelves_cnt,
                           COUNT(DISTINCT s.nm_id) AS anchors_cnt,
                           AVG(i.position) AS avg_pos,
                           MIN(i.position) AS best_pos,
                           MAX(i.snapshot_date) AS last_at
                    FROM wb_competitor_cards_shelf_item i
                    JOIN wb_competitor_cards_shelf s ON s.id = i.shelf_id
                    JOIN (
                        SELECT i2.shelf_id, MAX(i2.snapshot_date) AS d
                        FROM wb_competitor_cards_shelf_item i2
                        WHERE i2.shelf_id IN (
                            SELECT DISTINCT i3.shelf_id
                            FROM wb_competitor_cards_shelf_item i3
                            WHERE i3.nm_id IN ({ph})
                              AND i3.snapshot_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                        )
                          AND i2.snapshot_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                        GROUP BY i2.shelf_id
                    ) ld ON ld.shelf_id = i.shelf_id AND ld.d = i.snapshot_date
                    WHERE i.nm_id IN ({ph})
                      AND i.snapshot_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                      {scope}
                    GROUP BY i.nm_id
                """), params)).mappings().all()
                for r in rows:
                    out.setdefault(int(r["nm_id"]), {}).update({
                        "shelves_cnt": int(r["shelves_cnt"] or 0),
                        "shelf_anchors_cnt": int(r["anchors_cnt"] or 0),
                        "shelf_avg_pos": round(float(r["avg_pos"]), 1) if r["avg_pos"] is not None else None,
                        "shelf_best_pos": int(r["best_pos"]) if r["best_pos"] is not None else None,
                        "shelf_last_at": r["last_at"],
                    })
            except Exception:
                await self.db.rollback()

            # 2. Клипы (глобальные, без скоупа компании).
            try:
                rows = (await self.db.execute(text(f"""
                    SELECT cn.nm_id,
                           COUNT(DISTINCT cn.clip_id) AS clips_cnt,
                           COUNT(DISTINCT c.author_id) AS authors_cnt,
                           MAX(c.publication_date) AS last_at
                    FROM wb_competitor_cards_clip_nm cn
                    JOIN wb_competitor_cards_clip c ON c.clip_id = cn.clip_id
                    WHERE cn.nm_id IN ({ph})
                    GROUP BY cn.nm_id
                """), params)).mappings().all()
                for r in rows:
                    out.setdefault(int(r["nm_id"]), {}).update({
                        "clips_cnt": int(r["clips_cnt"] or 0),
                        "clips_authors_cnt": int(r["authors_cnt"] or 0),
                        "clips_last_at": r["last_at"],
                    })
            except Exception:
                await self.db.rollback()

            # 3. Поиск: топ-10 по нашим фразам за окно.
            try:
                scope = "" if cid is None else "AND p.company_id=:cid"
                rows = (await self.db.execute(text(f"""
                    SELECT p.nm_id,
                           COUNT(DISTINCT CASE WHEN p.position BETWEEN 1 AND 10
                                               THEN p.query_phrase END) AS top10_cnt,
                           COUNT(DISTINCT p.query_phrase) AS phrases_cnt,
                           MIN(NULLIF(p.position, 0)) AS best_pos,
                           MAX(p.collected_at) AS last_at
                    FROM wb_competitor_position p
                    WHERE p.nm_id IN ({ph})
                      AND p.collected_at >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                      {scope}
                    GROUP BY p.nm_id
                """), params)).mappings().all()
                for r in rows:
                    out.setdefault(int(r["nm_id"]), {}).update({
                        "top10_cnt": int(r["top10_cnt"] or 0),
                        "phrases_cnt": int(r["phrases_cnt"] or 0),
                        "best_pos": int(r["best_pos"]) if r["best_pos"] is not None else None,
                        "positions_last_at": r["last_at"],
                    })
            except Exception:
                await self.db.rollback()

            # 4. Дубликаты: минимальная цена кластера и разрыв с ней.
            try:
                scope = "" if cid is None else "AND r.company_id=:cid"
                rows = (await self.db.execute(text(f"""
                    SELECT o.nm_id,
                           MIN(o.price_gap_pct) AS gap,
                           MIN(r.min_price) AS min_price,
                           MAX(r.offers_total) AS offers_total,
                           MAX(r.snapshot_date) AS last_at
                    FROM wb_competitor_cards_offer o
                    JOIN wb_competitor_cards_offer_run r ON r.id = o.run_id
                    WHERE o.nm_id IN ({ph})
                      AND r.snapshot_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                      {scope}
                    GROUP BY o.nm_id
                """), params)).mappings().all()
                for r in rows:
                    out.setdefault(int(r["nm_id"]), {}).update({
                        "dup_gap_pct": int(r["gap"]) if r["gap"] is not None else None,
                        "dup_min_price": int(r["min_price"]) if r["min_price"] is not None else None,
                        "dup_offers_total": int(r["offers_total"]) if r["offers_total"] is not None else None,
                        "dup_last_at": r["last_at"],
                    })
            except Exception:
                await self.db.rollback()

            # 5. База для Δ цены: последний снимок старше 7 дней.
            try:
                rows = (await self.db.execute(text(f"""
                    SELECT t.nm_id, t.price
                    FROM (
                        SELECT nm_id, price,
                               ROW_NUMBER() OVER (PARTITION BY nm_id
                                                  ORDER BY created_at DESC, id DESC) AS rn
                        FROM wb_competitor_details_history
                        WHERE nm_id IN ({ph})
                          AND created_at <= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    ) t
                    WHERE t.rn = 1
                """), params)).mappings().all()
                for r in rows:
                    out.setdefault(int(r["nm_id"]), {})["price_base"] = r["price"]
            except Exception:
                await self.db.rollback()

            # 6. Когда последний раз менялась цена/контент.
            try:
                rows = (await self.db.execute(text(f"""
                    SELECT nm_id, MAX(created_at) AS last_at
                    FROM wb_competitor_details_history
                    WHERE nm_id IN ({ph})
                    GROUP BY nm_id
                """), params)).mappings().all()
                for r in rows:
                    out.setdefault(int(r["nm_id"]), {})["price_last_at"] = r["last_at"]
            except Exception:
                await self.db.rollback()

        return out

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
                SELECT nm_id, title, brand, seller, price, old_price, images, preview_image, badges,
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
        beh = await self._behavior_map([int(i) for i in ids])
        items = []
        for r in rows:
            d = dict(r)
            det = details.get(d["nm_id"]) or {}
            d["title"] = det.get("title") or d.get("title")
            d["brand"] = det.get("brand") or d.get("brand")
            d["seller"] = det.get("seller") or ""
            d["price"] = det.get("price") or d.get("price")
            d["old_price"] = det.get("old_price") or ""
            d["photo"] = (_photo(det.get("images")) or det.get("preview_image")
                          or d.get("image_url") or None)
            d["desc_len"] = int(det.get("desc_len") or 0)
            d["chars_cnt"] = int(det.get("chars_cnt") or 0)
            d["collected_at"] = det.get("collected_at") or d.get("collected_at")
            d["analysis_status"] = analysis.get(d["nm_id"])
            d["sources"] = (d.get("sources") or "").split(",") if d.get("sources") else []
            d["manual"] = "manual" in d["sources"] or "capture" in d["sources"]

            # §13.1: поведение для таблицы (полки/клипы/поиск/дубликаты/Δ цены).
            b = beh.get(d["nm_id"]) or {}
            cur_price = _int_price(d.get("price"))
            base_price = _int_price(b.get("price_base"))
            d["price_delta_7d"] = (
                round((cur_price - base_price) / base_price * 100, 1)
                if cur_price and base_price else None
            )
            d["shelves_cnt"] = int(b.get("shelves_cnt") or 0)
            d["shelf_anchors_cnt"] = int(b.get("shelf_anchors_cnt") or 0)
            d["shelf_avg_pos"] = b.get("shelf_avg_pos")
            d["shelf_best_pos"] = b.get("shelf_best_pos")
            d["clips_cnt"] = int(b.get("clips_cnt") or 0)
            d["clips_last_at"] = b.get("clips_last_at")
            d["clips_authors_cnt"] = int(b.get("clips_authors_cnt") or 0)
            d["top10_cnt"] = int(b.get("top10_cnt") or 0)
            d["phrases_cnt"] = int(b.get("phrases_cnt") or 0)
            d["best_pos"] = b.get("best_pos")
            d["dup_min_price"] = b.get("dup_min_price")
            d["dup_gap_pct"] = b.get("dup_gap_pct")
            d["dup_offers_total"] = int(b.get("dup_offers_total") or 0)
            bg = _j(det.get("badges"))
            d["badges"] = bg if isinstance(bg, list) else []
            stamps = [d.get("collected_at"), b.get("shelf_last_at"), b.get("clips_last_at"),
                      b.get("positions_last_at"), b.get("price_last_at"), b.get("dup_last_at")]
            last = max(stamps, key=_ts) if stamps else None
            d["last_activity_at"] = last if _ts(last) else None
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

    # Сортировка списка — whitelist (SQL не собирается из пользователя).
    # Значения — готовые выражения MySQL (агрегаты по группе nm_id).
    CAPTURED_SORTS = {
        "collected_at": "COALESCE(MAX(d.full_collected_at), MAX(d.collected_at))",
        "first_collected_at": "MAX(d.first_collected_at)",
        "first_seen_at": "MIN(c.first_seen_at)",
        "title": "MAX(d.title)",
        "desc_len": "MAX(CHAR_LENGTH(COALESCE(d.description,'')))",
        "chars_cnt": "MAX(JSON_LENGTH(COALESCE(d.characteristics, JSON_ARRAY())))",
        "price": "CAST(MAX(d.price) AS DECIMAL(12,2))",
        "attached_cnt": "COALESCE(MAX(att.attached_cnt), 0)",
        "companies_cnt": "COUNT(DISTINCT c.company_id)",
        "nm_id": "base.nm_id",
    }

    async def list_captured(self, q: str = "", include_hidden: bool = False,
                            limit: int = 50, offset: int = 0, *,
                            sort: str = "collected_at", direction: str = "desc",
                            scope: str = "captured",
                            collected_from: str = "", collected_to: str = "",
                            first_seen_from: str = "", first_seen_to: str = "",
                            content: str = "", phrase: str = "",
                            attached: str = "", source: str = "") -> dict:
        """Собранные карточки: фильтры + сортировка + пагинация (§19.6).

        `scope`:
        - `captured` (по умолчанию) — реестр `wb_competitor_capture` нашей компании
          (что собрали мы); глобальный админ видит все компании;
        - `all_details` — общий кэш контента `wb_competitor_details`: видно и то,
          что собрали другие компании, плюс наши отметки (исключено/наша/привязана).

        Наши карточки (`wbcards`) не показываются никогда: сбор их пропускает
        (`own_card`), а в списке конкурентов они пользы не дают.
        """
        cid = self.company_id
        limit = max(1, min(int(limit or 50), 300))
        offset = max(0, int(offset or 0))
        sort_key = str(sort or "").strip() or "collected_at"
        sort_expr = self.CAPTURED_SORTS.get(sort_key, self.CAPTURED_SORTS["collected_at"])
        dir_sql = "ASC" if str(direction or "desc").strip().lower() == "asc" else "DESC"
        all_details = str(scope or "").strip() == "all_details"

        params: dict = {}
        where: list[str] = []
        having: list[str] = []

        # --- откуда строки ---
        if all_details:
            base_sql = "SELECT nm_id FROM wb_competitor_details"
        elif cid is not None:
            base_sql = "SELECT nm_id FROM wb_competitor_capture WHERE company_id=:cid"
            params["cid"] = cid
        else:
            base_sql = "SELECT nm_id FROM wb_competitor_capture"

        # --- наши отметки по компании ---
        cap_join = "LEFT JOIN wb_competitor_capture c ON c.nm_id=base.nm_id"
        own_join = "LEFT JOIN wbcards w ON w.nmID=base.nm_id"
        if cid is not None:
            cap_join += " AND c.company_id=:cid"
            own_join += " AND w.company_id=:cid"
            params["cid"] = cid

        # --- привязки (cards.source='capture') — счётчик для сортировки/фильтра ---
        att_sql = ("LEFT JOIN (SELECT cc.nm_id, COUNT(DISTINCT cc.source_nm_id) AS attached_cnt"
                   " FROM wb_competitor_cards cc WHERE cc.source='capture'")
        if cid is not None:
            att_sql += " AND cc.source_nm_id IN (SELECT nmID FROM wbcards WHERE company_id=:cid2)"
            params["cid2"] = cid
        att_sql += " GROUP BY cc.nm_id) att ON att.nm_id=base.nm_id"

        # --- поиск ---
        if q.strip():
            params["like"] = _like(q)
            having.append("(title LIKE :like OR brand LIKE :like OR seller LIKE :like"
                          " OR CAST(nm_id AS CHAR) LIKE :like)")

        # --- даты ---
        if collected_from:
            params["cf"] = collected_from
            where.append("d.collected_at >= :cf")
        if collected_to:
            params["ct"] = collected_to
            where.append("d.collected_at < DATE_ADD(:ct, INTERVAL 1 DAY)")
        if first_seen_from:
            params["ff"] = first_seen_from
            having.append("MIN(c.first_seen_at) >= :ff")
        if first_seen_to:
            params["ft"] = first_seen_to
            having.append("MIN(c.first_seen_at) < DATE_ADD(:ft, INTERVAL 1 DAY)")

        # --- контент ---
        if content == "has_desc":
            having.append("desc_len > 0")
        elif content == "no_desc":
            having.append("desc_len = 0")
        elif content == "has_chars":
            having.append("chars_cnt > 0")
        elif content == "no_chars":
            having.append("chars_cnt = 0")

        # --- фраза: позиции выдачи + формулировки конкурентов ---
        if phrase.strip():
            params["ph"] = _like(phrase)
            subs = ["(SELECT p.nm_id FROM wb_competitor_position p"
                    " WHERE p.query_phrase LIKE :ph"]
            if cid is not None:
                subs[0] += " AND p.company_id=:cid3"
                params["cid3"] = cid
            subs[0] += ")"
            if await _phrase_schema_ready(self.db):
                subs.append("(SELECT pc.competitor_nm_id FROM wb_competitor_phrase_comp pc"
                            " WHERE pc.phrase LIKE :ph")
                if cid is not None:
                    subs[-1] += " AND pc.company_id=:cid3"
                subs[-1] += ")"
            where.append(f"base.nm_id IN ({' UNION '.join(subs)})")

        # --- привязка ---
        if attached == "yes":
            having.append("attached_cnt > 0")
        elif attached == "no":
            having.append("attached_cnt = 0")

        # --- источник (cards.source) ---
        if source.strip():
            params["src"] = source.strip()
            sub = "(SELECT cc.nm_id FROM wb_competitor_cards cc WHERE cc.source=:src"
            if cid is not None:
                sub += " AND cc.source_nm_id IN (SELECT nmID FROM wbcards WHERE company_id=:cid4)"
                params["cid4"] = cid
            sub += ")"
            where.append(f"base.nm_id IN {sub}")

        # --- свои карточки: никогда не показываем (сбор их пропускает — own_card) ---
        having.append("is_own = 0")

        # --- исключённые из сбора (is_hidden) ---
        if not include_hidden:
            having.append("(is_hidden IS NULL OR is_hidden = 0)")

        select_sql = f"""
            SELECT base.nm_id AS nm_id,
                   MAX(w.nmID IS NOT NULL) AS is_own,
                   MIN(c.is_hidden) AS is_hidden,
                   MIN(c.first_seen_at) AS first_seen_at,
                   MAX(c.last_seen_at) AS last_seen_at,
                   COUNT(DISTINCT c.company_id) AS companies_cnt,
                   MAX(c.company_id IS NOT NULL) AS captured_by_us,
                   MAX(d.title) AS title,
                   MAX(d.brand) AS brand,
                   MAX(d.seller) AS seller,
                   MAX(d.price) AS price,
                   MAX(d.old_price) AS old_price,
                   MAX(d.url) AS url,
                   MAX(d.images) AS images,
                   MAX(d.preview_image) AS preview_image,
                   MAX(CHAR_LENGTH(COALESCE(d.description,''))) AS desc_len,
                   MAX(JSON_LENGTH(COALESCE(d.characteristics, JSON_ARRAY()))) AS chars_cnt,
                   MAX(d.collected_at) AS collected_at,
                   MAX(d.full_collected_at) AS full_collected_at,
                   MAX(d.first_collected_at) AS first_collected_at,
                   COALESCE(MAX(att.attached_cnt), 0) AS attached_cnt
            FROM ({base_sql}) base
            {cap_join}
            {own_join}
            {att_sql}
            LEFT JOIN wb_competitor_details d ON d.nm_id=base.nm_id
            WHERE {' AND '.join(where) if where else '1=1'}
            GROUP BY base.nm_id
        """
        having_sql = (" HAVING " + " AND ".join(having)) if having else ""

        rows = (await self.db.execute(text(
            select_sql + having_sql
            + f" ORDER BY {sort_expr} {dir_sql}, base.nm_id {dir_sql}"
            + " LIMIT :lim OFFSET :off"
        ), {**params, "lim": limit, "off": offset})).mappings().all()
        total = int((await self.db.execute(text(
            f"SELECT COUNT(*) FROM ({select_sql}{having_sql}) t"
        ), params)).scalar() or 0)

        ids = [r["nm_id"] for r in rows]
        attached: dict[int, list[dict]] = {}
        history_cnt: dict[int, int] = {}
        positions_cnt: dict[int, int] = {}
        phrases_cnt: dict[int, int] = {}
        if ids:
            ph = ",".join(f":d{i}" for i in range(len(ids)))
            iparams = {f"d{i}": v for i, v in enumerate(ids)}
            scope = ""
            if self.company_id is not None:
                scope = "AND cc.source_nm_id IN (SELECT nmID FROM wbcards WHERE company_id=:cid2)"
                iparams["cid2"] = self.company_id
            for r in (await self.db.execute(text(f"""
                SELECT cc.nm_id, cc.source_nm_id, w2.title AS source_title
                FROM wb_competitor_cards cc
                LEFT JOIN wbcards w2 ON w2.nmID = cc.source_nm_id
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

            # --- фразы: выдача (positions) + формулировки после разбора (phrase_comp) ---
            pscope, pscope_p = "", {}
            if self.company_id is not None:
                pscope = "AND company_id=:pcid"
                pscope_p["pcid"] = self.company_id
            for r in (await self.db.execute(text(f"""
                SELECT nm_id, COUNT(DISTINCT query_phrase) AS cnt
                FROM wb_competitor_position
                WHERE nm_id IN ({ph}) {pscope} GROUP BY nm_id
            """), {**iparams, **pscope_p})).mappings().all():
                positions_cnt[int(r["nm_id"])] = int(r["cnt"] or 0)
            if await _phrase_schema_ready(self.db):
                for r in (await self.db.execute(text(f"""
                    SELECT competitor_nm_id AS nm_id, COUNT(DISTINCT phrase) AS cnt
                    FROM wb_competitor_phrase_comp
                    WHERE competitor_nm_id IN ({ph}) {pscope} GROUP BY competitor_nm_id
                """), {**iparams, **pscope_p})).mappings().all():
                    phrases_cnt[int(r["nm_id"])] = int(r["cnt"] or 0)

        items = []
        for r in rows:
            d = dict(r)
            n = int(d["nm_id"])
            d["photo"] = _photo(d.pop("images", None)) or (d.get("preview_image") or None)
            d["desc_len"] = int(d.get("desc_len") or 0)
            d["chars_cnt"] = int(d.get("chars_cnt") or 0)
            d["is_own"] = bool(d.get("is_own"))
            d["is_hidden"] = bool(d.get("is_hidden"))
            d["captured_by_us"] = bool(d.get("captured_by_us"))
            d["companies_cnt"] = int(d.get("companies_cnt") or 0)
            d["attached"] = attached.get(n, [])
            d["attached_cnt"] = int(d.get("attached_cnt") or 0)
            d["history_cnt"] = history_cnt.get(n, 0)
            d["positions_cnt"] = positions_cnt.get(n, 0)
            d["phrases_cnt"] = phrases_cnt.get(n, 0)
            d["url"] = d.get("url") or f"https://www.wildberries.ru/catalog/{n}/detail.aspx"
            items.append(d)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "sort": sort_key,
            "direction": dir_sql.lower(),
            "scope": "all_details" if all_details else "captured",
        }

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
                "SELECT nmID FROM wbcards WHERE company_id=:cid OR company_id IS NULL"
            ), {"cid": self.company_id})).scalars().all()
        return {int(x) for x in rows}

    async def _details_map(self, ids: list[int]) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for chunk in _chunks(ids):
            ph = ",".join(f":d{i}" for i in range(len(chunk)))
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, title, brand, seller, price, old_price, images, preview_image,
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
                              limit: int = 200, offset: int = 0,
                              sort: str = "relevance") -> dict:
        """Пул кандидатов §16: A ∪ B (B — рекомендации конкурентов A) / только A / вся captured-база компании."""
        mode = (mode or "recommend").strip().lower()
        if mode not in ("recommend", "competitors", "captured"):
            raise ValueError("mode: recommend | competitors | captured")
        if isinstance(raw_source_nm_ids, str):
            raw_source_nm_ids = [x for x in re.split(r"[,;\s]+", raw_source_nm_ids) if x]
        limit = max(1, min(int(limit or 200), 500))
        offset = max(0, int(offset or 0))
        sort = (sort or "relevance").strip().lower()
        if sort not in ("relevance", "title_asc", "title_desc"):
            sort = "relevance"

        source_ids: list[int] = []
        base: dict[int, dict] = {}

        def blank(nm: int) -> dict:
            return {
                "nm_id": nm, "in_a": False, "rec_cnt": 0, "recommended_by": [],
                "title": "", "brand": "", "price": "", "image_url": "",
                "collected_at": None, "sources": [], "source_nm_ids": [],
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
                           GROUP_CONCAT(DISTINCT source) AS sources,
                           GROUP_CONCAT(DISTINCT source_nm_id) AS source_nm_ids
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
                        "source_nm_ids": _ints(str(r["source_nm_ids"] or "").split(","), 200),
                    })
                    base[n] = item

            if mode == "recommend" and base:
                # B: рекомендации из карточек конкурентов A.
                # A — это wb_competitor_cards выбранных источников; новые nm_id
                # добавляем в пул, у существующих A только отмечаем рекомендовавших.
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
                        # На всякий случай поддерживаем двойной JSON-анкодинг.
                        if isinstance(recs, str):
                            recs = _j(recs)
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
                    "offset": offset, "limit": limit, "sort": sort, "desc_min_len": DESC_MIN_LEN,
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
            sources = b.get("sources") or []
            if not sources and mode == "captured":
                sources = (m.get("sources") or "").split(",") if m.get("sources") else []
            rec_by = list(b.get("recommended_by") or [])[:50]
            item = {
                "nm_id": n,
                "title": det.get("title") or b.get("title") or m.get("title") or "",
                "brand": det.get("brand") or b.get("brand") or m.get("brand") or "",
                "seller": det.get("seller") or "",
                "price": det.get("price") or b.get("price") or m.get("price") or "",
                "old_price": det.get("old_price") or "",
                "photo": (_photo(det.get("images")) or det.get("preview_image")
                          or b.get("image_url") or m.get("image_url")),
                "desc_len": int(det.get("desc_len") or 0),
                "chars_cnt": int(det.get("chars_cnt") or 0),
                "collected_at": det.get("collected_at") or b.get("collected_at") or m.get("collected_at"),
                "in_a": bool(b.get("in_a")),
                "rec_cnt": int(b.get("rec_cnt") or 0),
                "recommended_by": rec_by,
                "recommended_by_cards": [
                    {
                        "nm_id": src,
                        "title": (details.get(src) or {}).get("title") or (base.get(src) or {}).get("title") or "",
                        "source_nm_ids": list((base.get(src) or {}).get("source_nm_ids") or []),
                    }
                    for src in rec_by
                ],
                "source_nm_ids": list(b.get("source_nm_ids") or []),
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
            item["visible"] = bool(item["captured"] or item["in_a"] or item["rec_cnt"] or item["attached_to"])
            # Рекомендации (B) можно привязывать без capture — это основной сценарий §16.
            item["can_attach"] = bool(not item["is_hidden"] and not item["is_own"])
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
        if sort == "title_asc":
            items.sort(key=lambda x: ((x.get("title") or "").strip().lower(), int(x["nm_id"])))
        elif sort == "title_desc":
            items.sort(key=lambda x: ((x.get("title") or "").strip().lower(), int(x["nm_id"])), reverse=True)
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
            "sort": sort,
            "desc_min_len": DESC_MIN_LEN,
            "counts": counts,
        }

    async def bulk_attach(self, raw_nm_ids, raw_target_nm_ids,
                          user_id: int | None = None, mode: str = "recommend") -> dict:
        """Массовая привязка кандидатов к нашим карточкам (§16.5).

        Привязывает конкурентов выбранных карточек, рекомендации (B) и captured-строки.
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
        eligible: list[int] = []
        skipped_candidates: list[dict] = []
        for n in nm_ids:
            cap = capture.get(n)
            if cap and bool(cap.get("is_own")):
                skipped_candidates.append({"nm_id": n, "reason": "own"})
            elif cap and bool(cap.get("is_hidden")):
                skipped_candidates.append({"nm_id": n, "reason": "hidden"})
            else:
                # Кандидат может быть рекомендацией (B) без capture — привязка разрешена.
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
                img = str(_photo(det.get("images")) or det.get("preview_image")
                          or m.get("image_url") or "")[:1000]
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

    async def pick_details(self, nm_id: int) -> dict | None:
        """Карточка кандидата для попапа: capture, привязка или рекомендация (B)."""
        return await self.details(nm_id)

    async def list_refresh(self, days: int = REFRESH_AFTER_DAYS, q: str = "",
                           only_captured: bool = False, include_hidden: bool = False,
                           source_nm_id: int | None = None, status: str = "",
                           limit: int = 300, offset: int = 0) -> dict:
        """§17.2: конкуренты, контент которых собирали давно.

        База — объединение привязанных к нашим карточкам и явно собранных
        компанией. Берём только последнюю запись details; own-карточки и
        (по умолчанию) скрытые исключаем.
        """
        days = max(1, min(int(days or REFRESH_AFTER_DAYS), 3650))
        limit = max(1, min(int(limit or 300), 500))
        offset = max(0, int(offset or 0))
        status = (status or "").strip().lower()
        if status not in ("", "all", "stale", "assigned", "queued", "processing", "error", "gone"):
            status = ""

        src = None
        if source_nm_id:
            src = int(source_nm_id)
            await self._pick_sources([src])

        params: dict = {
            "cid": self.company_id,
            "only_captured": 1 if only_captured else 0,
            "include_hidden": 1 if include_hidden else 0,
        }
        where = [
            "r.rn=1",
            "r.last_at IS NOT NULL",
            f"r.last_at < DATE_SUB(NOW(), INTERVAL {days} DAY)",
            "(:include_hidden=1 OR COALESCE(cap.is_hidden,0)=0)",
            "(:only_captured=0 OR COALESCE(cap.capture_cnt,0)>0)",
            "r.nm_id NOT IN (SELECT nmID FROM wbcards WHERE (:cid IS NULL OR company_id=:cid))",
        ]
        if src is not None:
            where.append("""EXISTS (
                SELECT 1 FROM wb_competitor_cards csrc
                WHERE csrc.nm_id=r.nm_id AND csrc.source_nm_id=:src
            )""")
            params["src"] = src
        if q.strip():
            where.append("""(r.title LIKE :like OR r.brand LIKE :like OR r.seller LIKE :like
                             OR CAST(r.nm_id AS CHAR) LIKE :like)""")
            params["like"] = _like(q)

        rows = (await self.db.execute(text(f"""
            WITH visible AS (
                SELECT cc.nm_id
                FROM wb_competitor_cards cc
                JOIN wbcards w ON w.nmID=cc.source_nm_id
                WHERE (:cid IS NULL OR w.company_id=:cid)
                UNION
                SELECT cap.nm_id
                FROM wb_competitor_capture cap
                WHERE (:cid IS NULL OR cap.company_id=:cid)
            ),
            ranked AS (
                SELECT d.nm_id, d.title, d.brand, d.seller, d.images, d.preview_image,
                       COALESCE(d.collected_at, d.first_collected_at) AS last_at,
                       ROW_NUMBER() OVER (
                         PARTITION BY d.nm_id
                         ORDER BY COALESCE(d.collected_at, d.first_collected_at) DESC, d.id DESC
                       ) AS rn
                FROM wb_competitor_details d
                JOIN visible v ON v.nm_id=d.nm_id
            )
            SELECT r.nm_id, r.title, r.brand, r.seller, r.images, r.preview_image, r.last_at,
                   DATEDIFF(NOW(), r.last_at) AS days_old,
                   q.status AS queue_status, q.error_msg AS queue_error,
                   q.processed_at AS queue_processed_at, q.requested_at, q.not_found_at,
                   COALESCE(cap.is_hidden,0) AS is_hidden,
                   COALESCE(cap.capture_cnt,0) AS capture_cnt
            FROM ranked r
            LEFT JOIN (
                SELECT nm_id, MAX(is_hidden) AS is_hidden, COUNT(*) AS capture_cnt
                FROM wb_competitor_capture
                WHERE (:cid IS NULL OR company_id=:cid)
                GROUP BY nm_id
            ) cap ON cap.nm_id=r.nm_id
            LEFT JOIN wb_enrich_queue q ON q.nm_id=r.nm_id
            WHERE {' AND '.join(where)}
            ORDER BY r.last_at ASC, r.nm_id
        """), params)).mappings().all()

        counts = {"stale": 0, "assigned": 0, "queued": 0, "processing": 0, "error": 0, "gone": 0}
        matched: list[tuple[dict, str]] = []
        for r in rows:
            qs = str(r["queue_status"] or "")
            if qs == "need_update":
                key = "assigned"
            elif qs == "pending":
                key = "queued"
            elif qs == "processing":
                key = "processing"
            elif qs == "error":
                key = "error"
            elif qs == "gone":
                # карточки нет на WB (error404): в обновление не отдаём,
                # пока человек не проверит, что она появилась
                key = "gone"
            else:
                key = "stale"
            counts[key] += 1
            if status not in ("", "all") and key != status:
                continue
            matched.append((dict(r), key))

        total = len(matched)
        page = matched[offset:offset + limit]
        ids = [int(r["nm_id"]) for r, _ in page]
        attached = await self._attached_map(ids) if ids else {}
        items = []
        for r, key in page:
            n = int(r["nm_id"])
            att = attached.get(n, [])
            items.append({
                "nm_id": n,
                "title": r.get("title") or "",
                "brand": r.get("brand") or "",
                "seller": r.get("seller") or "",
                "photo": _photo(r.get("images")) or (r.get("preview_image") or None),
                "collected_at": r.get("last_at"),
                "days_old": int(r.get("days_old") or 0),
                "attached_to": att,
                "attached_cnt": len(att),
                "captured": bool(int(r.get("capture_cnt") or 0)),
                "is_hidden": bool(r.get("is_hidden")),
                "queue_status": r.get("queue_status"),
                "queue_error": r.get("queue_error"),
                "queue_processed_at": r.get("queue_processed_at"),
                "queue_not_found_at": r.get("not_found_at"),
                "requested_at": r.get("requested_at"),
                "ui_status": key,
            })
        return {
            "items": items,
            "total": total,
            "days": days,
            "counts": counts,
            "offset": offset,
            "limit": limit,
        }

    async def assign_refresh(self, raw_nm_ids, days: int = REFRESH_AFTER_DAYS,
                             user_id: int | None = None) -> dict:
        """§17.2: вручную поставить выбранным конкурентам `need_update`.

        Проверяем видимость компании, свежесть и текущий статус очереди.
        `pending`/`processing` не перебиваем; `done`/`error` переводим в
        `need_update` (error_msg и processed_at очищаем).
        """
        nm_ids = _ints(raw_nm_ids, limit=200)
        if not nm_ids:
            raise ValueError("Выберите хотя бы одного конкурента")
        days = max(1, min(int(days or REFRESH_AFTER_DAYS), 3650))
        cutoff = datetime.now() - timedelta(days=days)

        own = await self._own_card_ids()
        attached = await self._attached_map(nm_ids)
        capture = await self._capture_map(nm_ids)
        visible = set(attached) | set(capture)

        last_map: dict[int, object] = {}
        for chunk in _chunks(nm_ids):
            ph = ",".join(f":d{i}" for i in range(len(chunk)))
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, MAX(COALESCE(collected_at, first_collected_at)) AS last_at
                FROM wb_competitor_details
                WHERE nm_id IN ({ph})
                GROUP BY nm_id
            """), {f"d{i}": v for i, v in enumerate(chunk)})).mappings().all()
            for r in rows:
                last_map[int(r["nm_id"])] = r["last_at"]

        queue: dict[int, str] = {}
        for chunk in _chunks(nm_ids):
            ph = ",".join(f":q{i}" for i in range(len(chunk)))
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, status FROM wb_enrich_queue WHERE nm_id IN ({ph})
            """), {f"q{i}": v for i, v in enumerate(chunk)})).mappings().all()
            for r in rows:
                queue[int(r["nm_id"])] = str(r["status"] or "")

        skipped_candidates: list[dict] = []
        assignable: list[int] = []
        already = in_progress = 0
        cutoff_ts = _ts(cutoff)
        for n in nm_ids:
            if n in own:
                skipped_candidates.append({"nm_id": n, "reason": "own"})
                continue
            if n not in visible:
                skipped_candidates.append({"nm_id": n, "reason": "not_visible"})
                continue
            cap = capture.get(n) or {}
            if bool(cap.get("is_hidden")):
                skipped_candidates.append({"nm_id": n, "reason": "hidden"})
                continue
            last = last_map.get(n)
            if not last:
                skipped_candidates.append({"nm_id": n, "reason": "no_content"})
                continue
            if _ts(last) >= cutoff_ts:
                skipped_candidates.append({"nm_id": n, "reason": "fresh"})
                continue
            qs = queue.get(n, "")
            if qs == "processing":
                in_progress += 1
                continue
            if qs == "gone":
                # «карточки нет на WB»: назначаем только после «Появилась снова»
                skipped_candidates.append({"nm_id": n, "reason": "gone"})
                continue
            if qs in ("pending", "need_update"):
                already += 1
                continue
            assignable.append(n)

        assigned = 0
        if assignable:
            await self.db.rollback()
            async with self.db.begin():
                for n in assignable:
                    if n in queue:
                        r = await self.db.execute(text("""
                            UPDATE wb_enrich_queue
                            SET status='need_update', requested_at=NOW(), error_msg=NULL,
                                processed_at=NULL, company_id=COALESCE(company_id, :cid)
                            WHERE nm_id=:n AND status IN ('done', 'error')
                        """), {"n": n, "cid": self.company_id})
                    else:
                        r = await self.db.execute(text("""
                            INSERT IGNORE INTO wb_enrich_queue
                              (nm_id, company_id, status, requested_at)
                            VALUES (:n, :cid, 'need_update', NOW())
                        """), {"n": n, "cid": self.company_id})
                    if int(r.rowcount or 0) > 0:
                        assigned += 1
                    else:
                        already += 1

        return {
            "assigned": assigned,
            "already": already,
            "in_progress": in_progress,
            "skipped": len(skipped_candidates),
            "requested": len(nm_ids),
            "days": days,
            "skipped_candidates": skipped_candidates[:50],
            "errors": [],
        }

    async def restore_gone(self, raw_nm_ids, user_id: int | None = None) -> dict:
        """«Появилась снова»: человек проверил карточку на WB — снимаем «gone».

        Было: WB отдавал error404 («По Вашему запросу ничего не найдено»), сбор
        не удалён, статус очереди 'gone'. Человек открывал карточку и убедился,
        что она вернулась → статус 'done' (обновление назначается отдельно).
        Видимость проверяем как в assign_refresh: свою/чужую карточку не путаем.
        """
        nm_ids = _ints(raw_nm_ids, limit=200)
        if not nm_ids:
            raise ValueError("Выберите хотя бы одного конкурента")

        own = await self._own_card_ids()
        attached = await self._attached_map(nm_ids)
        capture = await self._capture_map(nm_ids)
        visible = set(attached) | set(capture)

        skipped_candidates: list[dict] = []
        restorable: list[int] = []
        not_gone = 0
        for n in nm_ids:
            if n in own:
                skipped_candidates.append({"nm_id": n, "reason": "own"})
                continue
            if n not in visible:
                skipped_candidates.append({"nm_id": n, "reason": "not_visible"})
                continue
            restorable.append(n)

        rows_seen: dict[int, str] = {}
        for chunk in _chunks(restorable):
            ph = ",".join(f":g{i}" for i in range(len(chunk)))
            rows = (await self.db.execute(text(f"""
                SELECT nm_id, status FROM wb_enrich_queue
                WHERE nm_id IN ({ph}) AND status='gone'
            """), {f"g{i}": v for i, v in enumerate(chunk)})).mappings().all()
            for r in rows:
                rows_seen[int(r["nm_id"])] = str(r["status"] or "")

        restored = 0
        if rows_seen:
            await self.db.rollback()
            async with self.db.begin():
                for n in rows_seen:
                    r = await self.db.execute(text("""
                        UPDATE wb_enrich_queue
                        SET status='done', processed_at=NOW(), error_msg=NULL,
                            not_found_at=NULL
                        WHERE nm_id=:n AND status='gone'
                    """), {"n": n})
                    restored += int(r.rowcount or 0)
        not_gone = len(restorable) - len(rows_seen)

        return {
            "restored": restored,
            "not_gone": not_gone,
            "skipped": len(skipped_candidates),
            "requested": len(nm_ids),
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

    async def _competitor_phrases(self, nm_id: int) -> list[dict]:
        """§17.3: фразы, которые разбор новой карточки привязал к конкуренту.

        `wb_competitor_phrase_comp` — сырьё (конкурент + его формулировка),
        `wb_competitor_phrase` — канон-группа. Показываем только завершённый
        разбор (`phrase_id IS NOT NULL`), иначе в модалке будет мусор
        прерванного прогона.
        """
        if not await _phrase_schema_ready(self.db):
            return []
        try:
            rows = (await self.db.execute(text("""
                SELECT pc.phrase_id, pc.phrase, pc.source_nm_id, pc.model,
                       pc.created_at,
                       p.phrase AS canon, p.is_selected, p.hit_cnt, p.variants_cnt,
                       w.title AS source_title, w.vendorCode AS source_vendor_code
                FROM wb_competitor_phrase_comp pc
                LEFT JOIN wb_competitor_phrase p ON p.id=pc.phrase_id
                LEFT JOIN wbcards w ON w.nmID=pc.source_nm_id
                WHERE pc.competitor_nm_id=:n
                  AND pc.phrase_id IS NOT NULL
                  AND (:cid IS NULL OR pc.company_id=:cid)
                ORDER BY pc.source_nm_id, p.is_selected DESC, p.hit_cnt DESC, pc.phrase
                LIMIT 200
            """), {"n": nm_id, "cid": self.company_id})).mappings().all()
        except Exception:
            await self.db.rollback()
            return []
        # «отдаёт ли WB эту фразу» — смотрим по ИСХОДНОЙ формулировке конкурента,
        # а не по канону группы (они могут отличаться)
        stats = await self._raw_phrase_stats([r.get("phrase") or "" for r in rows])
        out: list[dict] = []
        for r in rows:
            raw = (r.get("phrase") or "").strip()
            st = stats.get(raw.lower()) or {}
            out.append({
                "phrase_id": int(r["phrase_id"]) if r.get("phrase_id") else None,
                "phrase": raw,
                "canon": r.get("canon") or None,
                "source_nm_id": int(r["source_nm_id"]),
                "source_title": r.get("source_title") or "",
                "source_vendor_code": r.get("source_vendor_code") or "",
                "is_selected": bool(r.get("is_selected")),
                "hit_cnt": int(r.get("hit_cnt") or 0),
                "variants_cnt": int(r.get("variants_cnt") or 0),
                "in_db": bool(st),
                "orders": int(st.get("orders") or 0),
                "freq": int(st.get("freq") or 0),
                "cards_cnt": int(st.get("cards") or 0),
                "model": r.get("model"),
                "created_at": r.get("created_at"),
            })
        return out

    async def _raw_phrase_stats(self, phrases: list[str]) -> dict[str, dict]:
        """Есть ли фраза в нашей базе поисковых запросов (WB её отдаёт) + заказы/частота."""
        cleaned = [p.strip().lower() for p in phrases if p and p.strip()]
        cleaned = list(dict.fromkeys(cleaned))[:200]
        if not cleaned:
            return {}
        ph = ",".join(f":p{i}" for i in range(len(cleaned)))
        try:
            rows = (await self.db.execute(text(f"""
                SELECT LOWER(p.phrase) AS phrase,
                       SUM(p.orders) AS orders,
                       MAX(COALESCE(p.frequency_current, p.week_frequency, 0)) AS freq,
                       COUNT(DISTINCT p.nmID) AS cards
                FROM wb_sr_report_item_phrases p
                WHERE LOWER(p.phrase) IN ({ph})
                GROUP BY LOWER(p.phrase)
            """), {f"p{i}": v for i, v in enumerate(cleaned)})).mappings().all()
        except Exception:
            await self.db.rollback()
            return {}
        return {str(r["phrase"]): {"orders": int(r.get("orders") or 0),
                                   "freq": int(r.get("freq") or 0),
                                   "cards": int(r.get("cards") or 0)} for r in rows}

    async def details(self, nm_id: int, our_nm: int | None = None) -> dict | None:
        """Полная карточка конкурента для попапа: контент, поведение, клипы, дубликаты.

        `our_nm` — наша карточка, из которой открыли досье: для неё считается сравнение.
        Если контент ещё не собран, отдаём заглушку из `wb_competitor_cards` —
        поведение (полки/клипы/поиск) всё равно полезно.
        """
        row = (await self.db.execute(text("""
            SELECT nm_id, title, description, brand, seller, subject_name, url,
                   price, old_price, images, preview_image, characteristics,
                   rating, feedbacks, questions, badges, sold_out, is_resale,
                   COALESCE(collected_at, first_collected_at) AS collected_at,
                   first_collected_at, full_collected_at
            FROM wb_competitor_details
            WHERE nm_id=:n ORDER BY COALESCE(collected_at, first_collected_at) DESC, id DESC LIMIT 1
        """), {"n": nm_id})).mappings().first()
        if row:
            d = dict(row)
            d["sold_out"] = 1 if row.get("sold_out") else 0
            images = _images(row.get("images"))
            d["images"] = images
            # Галерея — только с карточки; если её ещё нет, показываем превью из выдачи.
            d["photo"] = images[0] if images else (d.get("preview_image") or None)
            chars = _j(d.get("characteristics")) or []
            d["characteristics"] = chars if isinstance(chars, list) else []
            badges = _j(d.get("badges")) or []
            badges = badges if isinstance(badges, list) else []
            # Ресейл (товар от частного лица): метка в бейджи — досье открывают
            # чаще всего по карточке из выдачи, там бейдж уже есть; здесь
            # добавляем по признаку в карточке (исторические строки бейдж не
            # получили — их ставил бэкфилл только в выдаче).
            if d.get("is_resale") and "ресейл" not in badges:
                badges = badges + ["ресейл"]
            d["badges"] = badges
            d["is_resale"] = 1 if d.get("is_resale") else 0
        else:
            fb = (await self.db.execute(text("""
                SELECT nm_id, MAX(title) AS title, MAX(brand) AS brand,
                       MAX(price) AS price, MAX(image_url) AS image_url,
                       MAX(collected_at) AS collected_at
                FROM wb_competitor_cards WHERE nm_id=:n
            """), {"n": nm_id})).mappings().first()
            if not fb:
                return None
            d = {
                "nm_id": nm_id,
                "title": fb.get("title") or "",
                "description": "",
                "brand": fb.get("brand") or "",
                "seller": "",
                "subject_name": None,
                "url": None,
                "price": fb.get("price"),
                "old_price": None,
                "images": [],
                "preview_image": fb.get("image_url") or None,
                "photo": fb.get("image_url") or None,
                "characteristics": [],
                "rating": None,
                "feedbacks": None,
                "questions": None,
                "badges": [],
                "sold_out": 0,
                "collected_at": fb.get("collected_at"),
                "first_collected_at": None,
                "full_collected_at": None,
            }
        d["url"] = d.get("url") or f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
        d["attached_to"] = (await self._attached_map([nm_id])).get(nm_id, [])
        d["attached_cnt"] = len(d["attached_to"])
        d["price_history"] = await self._price_history(
            nm_id, d.get("price"), d.get("old_price"), d.get("collected_at")
        )
        d["positions"] = await self._positions(nm_id)
        d["phrases"] = await self._competitor_phrases(nm_id)
        d["shelves"] = await self._shelves(nm_id)
        clips = await self._clips(nm_id)
        d["clips"] = clips["items"]
        d["clips_cnt"] = clips["total"]
        d["clips_authors_cnt"] = clips["authors"]
        d["clips_last_at"] = clips["last_at"]
        d["duplicates"] = await self._duplicates(nm_id)
        d["compare"] = await self._compare(our_nm) if our_nm and int(our_nm) != int(nm_id) else None
        return d

    async def _titles_map(self, ids: list[int]) -> dict[int, str]:
        """nm → название: сначала контент конкурента, потом наши карточки."""
        out: dict[int, str] = {}
        uniq = sorted({int(i) for i in ids if i})
        if not uniq:
            return out
        for chunk in _chunks(uniq):
            ph = ",".join(f":t{i}" for i in range(len(chunk)))
            params = {f"t{i}": v for i, v in enumerate(chunk)}
            try:
                rows = (await self.db.execute(text(f"""
                    SELECT nm_id, MAX(title) AS title
                    FROM wb_competitor_details
                    WHERE nm_id IN ({ph}) AND title <> ''
                    GROUP BY nm_id
                """), params)).mappings().all()
                for r in rows:
                    out[int(r["nm_id"])] = r["title"]
            except Exception:
                await self.db.rollback()
            try:
                rows = (await self.db.execute(text(f"""
                    SELECT nmID AS nm_id, title
                    FROM wbcards
                    WHERE nmID IN ({ph})
                """), params)).mappings().all()
                for r in rows:
                    out.setdefault(int(r["nm_id"]), r.get("title") or "")
            except Exception:
                await self.db.rollback()
        return out

    async def _shelves(self, nm_id: int) -> dict:
        """Полки конкурента: где он стоит (item) и какие полки у него на карточке (anchor)."""
        cid = self.company_id
        params: dict = {"n": nm_id}
        scope = ""
        if cid is not None:
            scope = "AND s.company_id=:cid"
            params["cid"] = cid

        as_item: list[dict] = []
        try:
            rows = (await self.db.execute(text(f"""
                SELECT s.nm_id AS anchor_nm, s.preset_id, s.preset_type, s.dest,
                       i.snapshot_date, i.position, i.price, i.seller,
                       COALESCE(NULLIF(s.title, ''), NULLIF(p.title, ''),
                                CONCAT('#', s.preset_id)) AS shelf_title
                FROM wb_competitor_cards_shelf_item i
                JOIN wb_competitor_cards_shelf s ON s.id = i.shelf_id
                LEFT JOIN wb_competitor_cards_shelf_preset p ON p.preset_id = s.preset_id
                JOIN (
                    SELECT i2.shelf_id, MAX(i2.snapshot_date) AS d
                    FROM wb_competitor_cards_shelf_item i2
                    WHERE i2.shelf_id IN (
                        SELECT DISTINCT i3.shelf_id
                        FROM wb_competitor_cards_shelf_item i3
                        WHERE i3.nm_id = :n
                    )
                    GROUP BY i2.shelf_id
                ) ld ON ld.shelf_id = i.shelf_id AND ld.d = i.snapshot_date
                WHERE i.nm_id = :n {scope}
                ORDER BY i.snapshot_date DESC, i.position
                LIMIT 100
            """), params)).mappings().all()
            as_item = [dict(r) for r in rows]
        except Exception:
            await self.db.rollback()

        titles = await self._titles_map([int(r["anchor_nm"]) for r in as_item])
        for r in as_item:
            r["anchor_title"] = titles.get(int(r["anchor_nm"]), "")

        as_anchor: list[dict] = []
        try:
            rows = (await self.db.execute(text(f"""
                SELECT s.preset_id, s.preset_type, s.dest,
                       COALESCE(NULLIF(s.title, ''), NULLIF(p.title, ''),
                                CONCAT('#', s.preset_id)) AS shelf_title,
                       s.total_candidates, s.pages_loaded, s.is_partial, s.last_seen_at,
                       (SELECT COUNT(*) FROM wb_competitor_cards_shelf_item i
                         WHERE i.shelf_id = s.id
                           AND i.snapshot_date = (SELECT MAX(i2.snapshot_date)
                                                    FROM wb_competitor_cards_shelf_item i2
                                                   WHERE i2.shelf_id = s.id)) AS items_cnt,
                       (SELECT ROUND(AVG(i.price)) FROM wb_competitor_cards_shelf_item i
                         WHERE i.shelf_id = s.id
                           AND i.snapshot_date = (SELECT MAX(i2.snapshot_date)
                                                    FROM wb_competitor_cards_shelf_item i2
                                                   WHERE i2.shelf_id = s.id)) AS avg_price
                FROM wb_competitor_cards_shelf s
                LEFT JOIN wb_competitor_cards_shelf_preset p ON p.preset_id = s.preset_id
                WHERE s.nm_id = :n {scope}
                ORDER BY s.preset_id
            """), params)).mappings().all()
            as_anchor = [dict(r) for r in rows]
        except Exception:
            await self.db.rollback()

        for r in as_anchor:
            r["avg_price"] = int(r["avg_price"]) if r.get("avg_price") is not None else None
            r["items_cnt"] = int(r.get("items_cnt") or 0)

        positions = [int(r["position"]) for r in as_item if r.get("position") is not None]
        return {
            "as_item": as_item,
            "as_anchor": as_anchor,
            "counts": {
                "shelves_cnt": len(as_item),
                "anchors_cnt": len({int(r["anchor_nm"]) for r in as_item}),
                "avg_pos": round(sum(positions) / len(positions), 1) if positions else None,
                "best_pos": min(positions) if positions else None,
            },
        }

    async def card_shelves(self, nm_id: int) -> dict:
        """Полки любой карточки — в том числе НАШЕЙ (модалка «Полки и баджи»).

        Тот же company-scoped срез, что у досье конкурента, но без привязки к
        «конкуренту»: полка лежит по nmID карточки, на которой её увидели.
        """
        return await self._shelves(nm_id)


    async def _clips(self, nm_id: int) -> dict:
        """Клипы, привязанные к карточке (`clip_nm.nm_id = nm`)."""
        empty = {"items": [], "total": 0, "authors": 0, "last_at": None}
        try:
            totals = (await self.db.execute(text("""
                SELECT COUNT(*) AS total, COUNT(DISTINCT c.author_id) AS authors,
                       MAX(c.publication_date) AS last_at
                FROM wb_competitor_cards_clip_nm cn
                JOIN wb_competitor_cards_clip c ON c.clip_id = cn.clip_id
                WHERE cn.nm_id = :n
            """), {"n": nm_id})).mappings().first()
            if not totals or not int(totals["total"] or 0):
                return empty
            rows = (await self.db.execute(text("""
                SELECT c.clip_id, c.type, c.name, c.description, c.duration_s,
                       c.publication_date, c.author_id, c.author_name, c.author_verified,
                       c.preview_url, c.public_url, c.nm_count,
                       JSON_UNQUOTE(JSON_EXTRACT(c.extra, '$.author.link')) AS author_url
                FROM wb_competitor_cards_clip_nm cn
                JOIN wb_competitor_cards_clip c ON c.clip_id = cn.clip_id
                WHERE cn.nm_id = :n
                ORDER BY c.publication_date DESC, c.clip_id DESC
                LIMIT 30
            """), {"n": nm_id})).mappings().all()
            items = []
            for r in rows:
                item = dict(r)
                if not item.get("public_url"):
                    item["public_url"] = f"https://wibes.ru/clips/{item['clip_id']}"
                items.append(item)
            return {
                "items": items,
                "total": int(totals["total"] or 0),
                "authors": int(totals["authors"] or 0),
                "last_at": totals["last_at"],
            }
        except Exception:
            await self.db.rollback()
            return empty

    async def _duplicates(self, nm_id: int) -> dict | None:
        """Кластер дубликатов с участием конкурента (последний срез)."""
        cid = self.company_id
        params: dict = {"n": nm_id}
        scope = ""
        if cid is not None:
            scope = "AND r.company_id=:cid"
            params["cid"] = cid
        try:
            row = (await self.db.execute(text(f"""
                SELECT r.id AS run_id, r.match_id, r.anchor_nm_id, r.anchor_price,
                       r.min_price, r.min_price_nm_id, r.offers_total,
                       r.snapshot_date, r.dest, o.price AS my_price,
                       o.price_gap_pct, o.seller
                FROM wb_competitor_cards_offer o
                JOIN wb_competitor_cards_offer_run r ON r.id = o.run_id
                WHERE o.nm_id = :n {scope}
                ORDER BY r.snapshot_date DESC, r.id DESC
                LIMIT 1
            """), params)).mappings().first()
            if not row:
                return None
            offers = (await self.db.execute(text("""
                SELECT nm_id, name, price, seller, is_anchor, is_min_price, price_gap_pct
                FROM wb_competitor_cards_offer
                WHERE run_id = :r
                ORDER BY price, position
                LIMIT 20
            """), {"r": row["run_id"]})).mappings().all()
            titles = await self._titles_map([
                int(row["anchor_nm_id"] or 0),
                int(row["min_price_nm_id"] or 0),
            ])
            return {
                "match_id": row["match_id"],
                "anchor_nm": row["anchor_nm_id"],
                "anchor_title": titles.get(int(row["anchor_nm_id"] or 0), ""),
                "anchor_price": row["anchor_price"],
                "my_price": row["my_price"],
                "min_price": row["min_price"],
                "min_price_nm": row["min_price_nm_id"],
                "min_price_title": titles.get(int(row["min_price_nm_id"] or 0), ""),
                "price_gap_pct": row["price_gap_pct"],
                "offers_total": row["offers_total"],
                "snapshot_date": row["snapshot_date"],
                "offers": [dict(o) for o in offers],
            }
        except Exception:
            await self.db.rollback()
            return None

    async def _compare(self, our_nm: int) -> dict:
        """Наша карточка для сравнения: контент + клипы (полки сравниваются отдельно)."""
        row = (await self.db.execute(text("""
            SELECT nm_id, title, price, old_price, rating, feedbacks, badges,
                   CHAR_LENGTH(COALESCE(description, '')) AS desc_len,
                   JSON_LENGTH(COALESCE(characteristics, JSON_ARRAY())) AS chars_cnt,
                   COALESCE(collected_at, first_collected_at) AS collected_at
            FROM wb_competitor_details
            WHERE nm_id = :n
            ORDER BY COALESCE(collected_at, first_collected_at) DESC, id DESC
            LIMIT 1
        """), {"n": our_nm})).mappings().first()
        out: dict = {"nm_id": our_nm}
        if row:
            out.update(dict(row))
        else:
            w = (await self.db.execute(text("""
                SELECT nmID AS nm_id, title, description, characteristics
                FROM wbcards WHERE nmID = :n LIMIT 1
            """), {"n": our_nm})).mappings().first()
            if not w:
                return out
            chars = _j(w.get("characteristics")) or []
            out.update({
                "nm_id": our_nm,
                "title": w.get("title") or "",
                "price": None,
                "old_price": None,
                "rating": None,
                "feedbacks": None,
                "badges": [],
                "desc_len": len(w.get("description") or ""),
                "chars_cnt": len(chars) if isinstance(chars, list) else 0,
                "collected_at": None,
            })
        badges = _j(out.get("badges")) or []
        out["badges"] = badges if isinstance(badges, list) else []
        try:
            cnt = (await self.db.execute(text(
                "SELECT COUNT(*) FROM wb_competitor_cards_clip_nm WHERE nm_id = :n"
            ), {"n": our_nm})).scalar()
            out["clips_cnt"] = int(cnt or 0)
        except Exception:
            await self.db.rollback()
            out["clips_cnt"] = 0
        return out

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

    async def _positions(self, nm_id: int) -> list[dict]:
        """Где конкурент был в выдаче: фраза → позиция/цена по дням (wb_competitor_position)."""
        scope = ""
        params = {"n": nm_id}
        if self.company_id is not None:
            scope = "AND p.company_id=:cid"
            params["cid"] = self.company_id
        rows = (await self.db.execute(text(f"""
            SELECT p.query_phrase, p.source_nm_id, p.position, p.price, p.collected_at, p.sold_out,
                   w.title AS source_title
            FROM wb_competitor_position p
            LEFT JOIN wbcards w ON w.nmID = p.source_nm_id
            WHERE p.nm_id=:n {scope}
            ORDER BY p.query_phrase, p.collected_at, p.id
        """), params)).mappings().all()
        grouped: dict[tuple, list] = {}
        for r in rows:
            grouped.setdefault((r["query_phrase"], r["source_nm_id"]), []).append(r)
        out: list[dict] = []
        for (phrase, src), items in grouped.items():
            hist: list[dict] = []
            prev = None
            for it in items:
                if it["position"] != prev:
                    hist.append({
                        "position": it["position"],
                        "price": it["price"],
                        "sold_out": 1 if it.get("sold_out") else 0,
                        "at": it["collected_at"],
                    })
                    prev = it["position"]
            last = hist[-1] if hist else {}
            out.append({
                "phrase": phrase,
                "source_nm_id": src,
                "source_title": items[0].get("source_title") or "",
                "last_position": last.get("position"),
                "last_price": last.get("price"),
                "last_sold_out": last.get("sold_out") or 0,
                "at": items[-1]["collected_at"],
                "days": len(items),
                "positions": hist,
            })
        out.sort(key=lambda x: (str(x.get("at") or ""), str(x.get("phrase") or "")), reverse=True)
        return out

    async def capture_visible(self, nm_id: int) -> bool:
        """Есть ли карточка в собранных у этой компании (для доступа к попапу)."""
        return bool(await self._capture_row(nm_id))

    async def cards_fallback(self, nm_id: int) -> dict | None:
        """Последняя строка конкурента в wb_competitor_cards (наши карточки компании)."""
        scope, params = "", {"n": nm_id}
        if self.company_id is not None:
            scope = "AND w.company_id=:cid"
            params["cid"] = self.company_id
        r = (await self.db.execute(text(f"""
            SELECT c.source_nm_id, c.query_phrase, c.position, c.title, c.brand, c.seller,
                   c.price, c.old_price, c.rating, c.feedbacks, c.badges, c.image_url,
                   c.sold_out, c.collected_at
            FROM wb_competitor_cards c
            JOIN wbcards w ON w.nmID=c.source_nm_id
            WHERE c.nm_id=:n {scope}
            ORDER BY c.id DESC LIMIT 1
        """), params)).mappings().first()
        return dict(r) if r else None

    async def positions_fallback(self, nm_id: int) -> dict | None:
        """Последняя строка конкурента в выдаче (wb_competitor_position)."""
        scope, params = "", {"n": nm_id}
        if self.company_id is not None:
            scope = "AND company_id=:cid"
            params["cid"] = self.company_id
        r = (await self.db.execute(text(f"""
            SELECT source_nm_id, query_phrase, position, position_api, title, brand, seller,
                   price, old_price, rating, feedbacks, badges, image_url, sold_out,
                   collected_at, slice_stamp
            FROM wb_competitor_position
            WHERE nm_id=:n {scope}
            ORDER BY id DESC LIMIT 1
        """), params)).mappings().first()
        return dict(r) if r else None

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
            SELECT title, brand, price, images, preview_image
            FROM wb_competitor_details WHERE nm_id=:n LIMIT 1
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
                "img": str(_photo(det.get("images")) or det.get("preview_image") or "")[:1000],
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
        """Исключить карточку из сбора / вернуть: `wb_competitor_capture.is_hidden`.

        Исключение per-company: другая компания ту же карточку собирать может.
        Исключённая карточка не обновляется (сервер) и не собирается (расширение).
        """
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
                         total: int, company_id: int | None,
                         phase: str = "extract") -> None:
        if not run_id:
            return
        await self.db.execute(text("""
            DELETE FROM wb_competitor_run WHERE created_at < DATE_SUB(NOW(), INTERVAL 2 DAY)
        """))
        try:
            await self.db.execute(text("""
                INSERT INTO wb_competitor_run
                  (run_id, company_id, source_nm_id, kind, status, attempt, total, phase)
                VALUES (:r, :c, :n, :k, 'running', 0, :t, :ph) AS new
                ON DUPLICATE KEY UPDATE status='running', attempt=0, total=new.total,
                  model=NULL, error=NULL, phase=new.phase, done_ids=NULL
            """), {"r": run_id[:64], "c": company_id, "n": nm_id, "k": kind, "t": total,
                   "ph": phase})
        except Exception:
            # миграция 20261027 не применена — пишем без фазы
            await self.db.rollback()
            await self.db.execute(text("""
                INSERT INTO wb_competitor_run
                  (run_id, company_id, source_nm_id, kind, status, attempt, total)
                VALUES (:r, :c, :n, :k, 'running', 0, :t) AS new
                ON DUPLICATE KEY UPDATE status='running', attempt=0, total=new.total,
                  model=NULL, error=NULL
            """), {"r": run_id[:64], "c": company_id, "n": nm_id, "k": kind, "t": total})
        await self.db.commit()

    async def _run_step(self, run_id: str | None, attempt: int, model: str,
                        phase: str | None = None, done_ids: str | None = None) -> None:
        """Прогресс прогона: шаг, модель, фаза (extract|merge), готовые конкуренты."""
        if not run_id:
            return
        extra = ""
        params: dict = {"a": attempt, "m": model[:190], "r": run_id[:64]}
        if phase:
            extra += ", phase=:ph"
            params["ph"] = phase
        if done_ids is not None:
            extra += ", done_ids=:di"
            params["di"] = done_ids[:4000]
        try:
            await self.db.execute(text(f"""
                UPDATE wb_competitor_run SET attempt=:a, model=:m, status='running' {extra}
                WHERE run_id=:r
            """), params)
        except Exception:
            await self.db.rollback()
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
                   phase, done_ids, created_at, updated_at
            FROM wb_competitor_run
            WHERE run_id=:r AND source_nm_id=:n LIMIT 1
        """), {"r": run_id[:64], "n": nm_id})).mappings().first()
        if not row:
            return None
        d = dict(row)
        d["is_free"] = ":free" in (d.get("model") or "").lower()
        return d

    async def get_run_safe(self, nm_id: int, run_id: str) -> dict | None:
        """Как get_run, но без падения, если миграция 20261027 ещё не применена."""
        try:
            return await self.get_run(nm_id, run_id)
        except Exception:
            await self.db.rollback()
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
            d["phase"] = None
            d["done_ids"] = None
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

    async def _phrases_for_competitor(self, comp: dict, model: str, company_id: int,
                                       user_id: int | None, nm_id: int,
                                       prompt: str) -> tuple[list[str], str | None]:
        """Фразы ОДНОГО конкурента.

        Отдельная сессия: вызовы идут параллельно, а AsyncSession не потокобезопасен.
        """
        cid = comp.get("nm_id")
        up = (f"=== КОНКУРЕНТ nmID {cid} ===\n"
              f"Название: {(comp.get('title') or '')[:200]}\n"
              f"Описание: {(comp.get('description') or '')[:1500]}\n\n"
              'Извлеки поисковые фразы и верни JSON {"phrases": [...]}.')
        messages = [{"role": "system", "content": prompt},
                    {"role": "user", "content": up}]
        try:
            async with SessionLocal() as sdb:
                res = await llm.chat(sdb, messages, company_id, temperature=0.1,
                                     max_tokens=PHRASES_MAX_TOKENS, model=model,
                                     reasoning_effort="low", send_max_tokens=True,
                                     note=f"phrases nm {nm_id}, конкурент {cid}",
                                     scenario="newcard_phrases", user_id=user_id, nm_id=nm_id)
        except Exception as exc:
            return [], f"{type(exc).__name__}: {exc}"
        if res.get("error"):
            detail = str(res.get("error"))
            if res.get("finish_reason") and "finish_reason" not in detail:
                detail += f", finish_reason={res['finish_reason']}"
            return [], detail
        raw = res.get("content") or ""
        phrases = _phrases_from_parsed(_parse_json(raw))
        if not isinstance(phrases, list) or not phrases:
            return [], f"не удалось разобрать список фраз ({' '.join(raw.split())[:120]!r})"
        out: list[str] = []
        for item in phrases:
            if isinstance(item, dict):
                item = item.get("phrase") or item.get("text") or ""
            p = _norm_phrase(item)
            if 3 <= len(p) <= 200 and p not in out:
                out.append(p)
        if not out:
            return [], "нет пригодных фраз"
        return out[:PHRASES_PER_COMPETITOR_MAX], None

    async def _merge_batch(self, batch: list[str], counts: dict[str, int], model: str,
                           company_id: int, user_id: int | None, nm_id: int,
                           errors: list[str]) -> list[list[str]]:
        """Один вызов группировки: батч формулировок → группы.

        Пустой результат = слияние не удалось (модель не ответила / ответ обрезан /
        JSON не разобрали). Ошибку пишем в errors, чтобы это было видно в UI, и
        полный обмен — в ai.log.
        """
        listed = "\n".join(f"- {p} ({counts.get(p, 0)})" for p in batch)
        up = (f"=== СПИСОК ФРАЗ (в скобках — сколько разных конкурентов) ===\n{listed}\n\n"
              "Объедини одинаковые по смыслу формулировки в группы (только группы из 2+ фраз). "
              'Верни JSON {"groups":[{"canonical":"...","members":["..."]}]}.')
        messages = [{"role": "system", "content": DEFAULT_MERGE_PROMPT},
                    {"role": "user", "content": up}]
        try:
            async with SessionLocal() as sdb:
                res = await llm.chat(sdb, messages, company_id, temperature=0.0,
                                     max_tokens=MERGE_MAX_TOKENS, model=model,
                                     reasoning_effort="low", send_max_tokens=True,
                                     note=f"merge nm {nm_id}", scenario="newcard_merge",
                                     user_id=user_id, nm_id=nm_id)
        except Exception as exc:
            errors.append(f"слияние: {type(exc).__name__}: {exc}")
            return []
        if res.get("error"):
            errors.append(f"слияние: {res['error']}")
            return []
        raw = res.get("content") or ""
        groups = _groups_from_parsed(_parse_json(raw))
        if not groups:
            head = " ".join(raw.split())[:200]
            finish = str(res.get("finish_reason") or "")
            err = f"слияние: не разобрали ответ модели{f' (finish_reason={finish})' if finish else ''}: {head!r}"
            errors.append(err)
            try:
                llm.ai_log("merge-parse-error", model, messages, raw,
                           http=res.get("http") or "", note=f"merge nm {nm_id}",
                           provider=res.get("provider") or "")
            except Exception:
                pass
            return []
        return _validate_groups(groups, batch, counts)

    async def _merge_groups(self, phrase_comp: dict[str, set[int]], cands: list[str],
                            company_id: int, user_id: int | None, nm_id: int,
                            errors: list[str], run_id: str | None = None,
                            base_attempt: int = 0) -> list[list[str]]:
        """Слияние формулировок.

        Шаг 1 (без модели): одинаковые фразы и чистые перестановки слов.
        Шаг 2 (модель, батчами, до 4 параллельно): синонимы, словоформы, лишние слова.

        Возвращает список групп; в каждой первой идёт канон (по данным: у какой
        формулировки больше разных конкурентов).
        """
        # шаг 1: кластеры (точные дубли + перестановки слов)
        clusters: list[list[str]] = []
        by_key: dict[tuple, int] = {}
        for p in dict.fromkeys(phrase_comp.keys()):
            if not p:
                continue
            k = _perm_key(p)
            idx = by_key.get(k)
            if idx is None:
                by_key[k] = len(clusters)
                clusters.append([p])
            else:
                clusters[idx].append(p)
        if len(clusters) <= 1:
            return clusters
        cluster_of = {c[0]: c for c in clusters}
        reps = list(cluster_of.keys())
        counts: dict[str, int] = {}
        for rep in reps:
            comps: set[int] = set()
            for m in cluster_of[rep]:
                comps |= phrase_comp.get(m, set())
            counts[rep] = len(comps)
        # шаг 2: модель по представителям кластеров
        batches = [reps[i:i + MERGE_BATCH] for i in range(0, len(reps), MERGE_BATCH)]
        sem = asyncio.Semaphore(LLM_PARALLEL)
        last_model = {"m": ""}

        async def one(batch: list[str]) -> list[list[str]]:
            async with sem:
                for model in cands[:PER_CALL_ATTEMPTS]:
                    groups = await self._merge_batch(batch, counts, model, company_id,
                                                     user_id, nm_id, errors)
                    last_model["m"] = model
                    if groups:
                        return groups
                return []

        merged: list[list[str]] = []
        done = 0
        tasks = [asyncio.create_task(one(b)) for b in batches]
        for fut in asyncio.as_completed(tasks):
            merged.extend(await fut)
            done += 1
            if run_id:
                try:
                    await self._run_step(run_id, base_attempt + done, last_model["m"], "merge")
                except Exception:
                    await self.db.rollback()
        # раскрываем группы до полных формулировок
        out: list[list[str]] = []
        used: set[str] = set()
        for grp in merged:
            members: list[str] = []
            for rep in grp:
                if rep in used:
                    continue
                used.add(rep)
                members.extend(cluster_of.get(rep, [rep]))
            if not members:
                continue
            members.sort(key=lambda p: (-len(phrase_comp.get(p, set())), 0))
            out.append(members)
        for c in clusters:
            if c[0] not in used:
                out.append(c)
        return out

    async def _comp_phrases_cached(self, nm_id: int) -> dict[int, dict]:
        """Уже собранные фразы по конкурентам: хэш описания + список фраз.

        Только строки с заполненным phrase_id — это завершённый разбор (после слияния).
        Сырьё без группы (прерванный прогон) не считаем кэшем.
        """
        out: dict[int, dict] = {}
        try:
            rows = (await self.db.execute(text("""
                SELECT competitor_nm_id, phrase, content_hash, model
                FROM wb_competitor_phrase_comp
                WHERE source_nm_id=:n AND phrase_id IS NOT NULL
            """), {"n": nm_id})).mappings().all()
        except Exception:
            await self.db.rollback()
            return out
        for r in rows:
            d = out.setdefault(int(r["competitor_nm_id"]),
                               {"hash": r["content_hash"] or "", "phrases": [], "model": r["model"]})
            if r["phrase"]:
                d["phrases"].append(r["phrase"])
        return out

    async def _save_comp_rows(self, nm_id: int, company_id: int, cid: int,
                               phrases: list[str], model: str | None,
                               content_hash: str) -> None:
        """Сырьё по конкуренту — сразу в БД (phrase_id заполнится после слияния)."""
        rows = [{"c": company_id, "n": nm_id, "cn": cid, "p": p, "m": model, "h": content_hash}
                for p in phrases]
        if not rows:
            return
        await self.db.execute(text("""
            INSERT INTO wb_competitor_phrase_comp
              (company_id, source_nm_id, competitor_nm_id, phrase_id, phrase, model, content_hash)
            VALUES (:c, :n, :cn, NULL, :p, :m, :h) AS new
            ON DUPLICATE KEY UPDATE
              phrase=new.phrase, model=new.model, content_hash=new.content_hash
        """), rows)
        await self.db.commit()

    async def list_phrases(self, nm_id: int) -> dict:
        """Рабочий список фраз (групп) + у кого встречается + варианты формулировок."""
        has = await _phrase_schema_ready(self.db)
        cols = "p.variants_cnt, " if has else ""
        rows = (await self.db.execute(text(f"""
            SELECT p.id, p.phrase, p.source, p.hit_cnt, {cols}p.orders, p.freq, p.cards_cnt,
                   p.in_db, p.is_selected, p.model, p.created_at,
                   EXISTS(SELECT 1 FROM wb_seo_target t
                          WHERE t.nmID=p.source_nm_id AND LOWER(t.phrase)=LOWER(p.phrase)) AS in_targets
            FROM wb_competitor_phrase p
            WHERE p.source_nm_id=:n
            ORDER BY p.is_selected DESC, p.orders DESC, p.hit_cnt DESC, p.in_db DESC, p.id
        """), {"n": nm_id})).mappings().all()
        cmap: dict[int, list[dict]] = {}
        vmap: dict[int, list[str]] = {}
        if rows and has:
            ids = [int(r["id"]) for r in rows]
            ph = ",".join(f":p{i}" for i in range(len(ids)))
            params = {"n": nm_id, **{f"p{i}": v for i, v in enumerate(ids)}}
            for r in (await self.db.execute(text(f"""
                SELECT pc.phrase_id, pc.competitor_nm_id, pc.phrase,
                       COALESCE(d.title, c.title) AS title
                FROM wb_competitor_phrase_comp pc
                LEFT JOIN wb_competitor_details d ON d.nm_id = pc.competitor_nm_id
                LEFT JOIN (SELECT nm_id, MAX(title) AS title FROM wb_competitor_cards
                           WHERE source_nm_id=:n GROUP BY nm_id) c
                       ON c.nm_id = pc.competitor_nm_id
                WHERE pc.source_nm_id=:n AND pc.phrase_id IN ({ph})
            """), params)).mappings().all():
                pid = int(r["phrase_id"])
                lst = cmap.setdefault(pid, [])
                cn = int(r["competitor_nm_id"])
                if not any(x["nm_id"] == cn for x in lst):
                    lst.append({"nm_id": cn, "title": r["title"] or ""})
                vs = vmap.setdefault(pid, [])
                if r["phrase"] and r["phrase"] not in vs:
                    vs.append(r["phrase"])
        items = []
        for r in rows:
            d = dict(r)
            pid = int(d["id"])
            d["in_db"] = bool(d.get("in_db"))
            d["is_selected"] = bool(d.get("is_selected"))
            d["in_targets"] = bool(d.get("in_targets"))
            for k in ("hit_cnt", "orders", "freq", "cards_cnt", "variants_cnt"):
                d[k] = int(d.get(k) or 0)
            d["competitors"] = sorted(cmap.get(pid, []), key=lambda x: x["nm_id"])
            variants = [d["phrase"]] + [v for v in vmap.get(pid, []) if v != d["phrase"]]
            d["variants"] = variants
            d["variants_cnt"] = max(d["variants_cnt"], len(variants))
            items.append(d)
        # сколько сырых формулировок есть (до слияния) — для кнопки «Слить формулировки»
        raw_cnt = 0
        if has:
            try:
                raw_cnt = int((await self.db.execute(text("""
                    SELECT COUNT(DISTINCT phrase) FROM wb_competitor_phrase_comp
                    WHERE source_nm_id=:n AND phrase IS NOT NULL AND phrase <> ''
                """), {"n": nm_id})).scalar() or 0)
            except Exception:
                await self.db.rollback()
        return {"nm_id": nm_id, "items": items, "raw_cnt": raw_cnt,
                "selected_cnt": sum(1 for x in items if x["is_selected"])}

    async def _write_groups(self, nm_id: int, company_id: int, groups: list[list[str]],
                            phrase_comp: dict[str, set[int]], stats: dict[str, dict],
                            main_model: str | None) -> None:
        """Группы → wb_competitor_phrase (рабочий список) + phrase_id в сырье.

        «Протухшие» ai-фразы карточки удаляются (ручные — нет), is_selected у
        переживших фраз сохраняется.
        """
        await self.db.rollback()
        async with self.db.begin():
            keep: list[str] = []
            for grp in groups:
                canon = grp[0]
                comps_n: set[int] = set()
                for m in grp:
                    comps_n |= phrase_comp.get(m, set())
                s = stats.get(canon) or {}
                await self.db.execute(text("""
                    INSERT INTO wb_competitor_phrase
                      (company_id, source_nm_id, phrase, source, hit_cnt, variants_cnt,
                       orders, freq, cards_cnt, in_db, model)
                    VALUES (:c, :n, :p, 'ai', :h, :v, :o, :f, :cc, :indb, :m) AS new
                    ON DUPLICATE KEY UPDATE
                      hit_cnt=new.hit_cnt, variants_cnt=new.variants_cnt,
                      orders=new.orders, freq=new.freq, cards_cnt=new.cards_cnt,
                      in_db=new.in_db,
                      model=IF(:m IS NULL, wb_competitor_phrase.model, new.model)
                """), {"c": company_id, "n": nm_id, "p": canon, "h": len(comps_n),
                       "v": len(grp), "o": int(s.get("orders") or 0),
                       "f": int(s.get("freq") or 0), "cc": int(s.get("cards") or 0),
                       "indb": 1 if s else 0, "m": main_model or None})
                keep.append(canon)
            ids_map: dict[str, int] = {}
            if keep:
                ph = ",".join(f":k{i}" for i in range(len(keep)))
                params = {"n": nm_id, **{f"k{i}": v for i, v in enumerate(keep)}}
                for r in (await self.db.execute(text(f"""
                    SELECT id, phrase FROM wb_competitor_phrase
                    WHERE source_nm_id=:n AND phrase IN ({ph})
                """), params)).mappings().all():
                    ids_map[str(r["phrase"])] = int(r["id"])
            old_ai = [int(r[0]) for r in (await self.db.execute(text("""
                SELECT id FROM wb_competitor_phrase WHERE source_nm_id=:n AND source='ai'
            """), {"n": nm_id})).all()]
            new_ids = set(ids_map.values())
            stale = [i for i in old_ai if i not in new_ids]
            if stale:
                ph = ",".join(f":s{i}" for i in range(len(stale)))
                await self.db.execute(
                    text(f"DELETE FROM wb_competitor_phrase WHERE id IN ({ph})"),
                    {f"s{i}": v for i, v in enumerate(stale)})
            # сырьё уже записано по ходу разбора — проставляем группу
            for grp in groups:
                gid = ids_map.get(grp[0])
                if not gid:
                    continue
                members = [m for m in grp if m]
                ph = ",".join(f":m{i}" for i in range(len(members)))
                await self.db.execute(text(f"""
                    UPDATE wb_competitor_phrase_comp SET phrase_id=:pid
                    WHERE source_nm_id=:n AND phrase IN ({ph})
                """), {"pid": gid, "n": nm_id,
                       **{f"m{i}": v for i, v in enumerate(members)}})

    async def merge_phrases(self, nm_id: int, run_id: str | None = None,
                            user_id: int | None = None) -> dict:
        """ТОЛЬКО слияние формулировок — без повторного разбора описаний.

        Сырьё берём из wb_competitor_phrase_comp (уже разобранные конкуренты),
        группы собираем заново и перезаписываем рабочий список. Дёшево: 1–3 вызова
        модели вместо 14 (разбор описаний).
        """
        if not await _phrase_schema_ready(self.db):
            raise ValueError("Нужна миграция 20261026_competitor_phrase_comp.sql")
        # 20261027 нужна только для прогресса по фазам; без неё слияние всё равно работает
        progress = await _run_progress_ready(self.db)
        card = await self._card(nm_id) or {}
        st = await self._company_settings(nm_id)
        company_id = st.get("company_id") or self.company_id or card.get("company_id")
        if not company_id:
            raise ValueError("Не удалось определить компанию карточки")
        rows = (await self.db.execute(text("""
            SELECT phrase, competitor_nm_id FROM wb_competitor_phrase_comp
            WHERE source_nm_id=:n AND phrase IS NOT NULL AND phrase <> ''
        """), {"n": nm_id})).mappings().all()
        phrase_comp: dict[str, set[int]] = {}
        for r in rows:
            p = _norm_phrase(r["phrase"])
            if p:
                phrase_comp.setdefault(p, set()).add(int(r["competitor_nm_id"]))
        if not phrase_comp:
            raise ValueError("Нет разобранных фраз — сначала запустите анализ описаний конкурентов")
        cands = (await llm.model_candidates(self.db, company_id, kind="newcard"))[:MAX_AI_ATTEMPTS]
        if not cands:
            raise ValueError("Нет доступных моделей для слияния")
        errors: list[str] = []
        merge_batches = max(1, -(-len(set(_perm_key(p) for p in phrase_comp)) // MERGE_BATCH))
        await self._run_start(run_id, nm_id, "merge", merge_batches, company_id, phase="merge")
        groups = await self._merge_groups(phrase_comp, cands, company_id, user_id,
                                          nm_id, errors, run_id=run_id)
        groups = [g for g in (groups or []) if g]
        if not groups:
            await self._run_finish(run_id, "error", "После слияния не осталось фраз")
            raise ValueError("После слияния не осталось фраз")
        stats = await self._phrase_stats([p for g in groups for p in g],
                                         card.get("subject_name") or "")
        await self._write_groups(nm_id, company_id, groups, phrase_comp, stats, None)
        out = await self.list_phrases(nm_id)
        out["groups_cnt"] = len(groups)
        out["raw_cnt"] = len(phrase_comp)
        out["merged_cnt"] = max(0, len(phrase_comp) - len(groups))
        out["errors"] = errors[:5]
        out["merge_prompt_version"] = MERGE_PROMPT_VERSION
        await self._run_finish(run_id, "done")
        return out

    async def analyze_phrases(self, nm_id: int, run_id: str | None = None,
                              user_id: int | None = None) -> dict:
        """Фразы по каждому конкуренту ОТДЕЛЬНО → слияние → рабочий список.

        Шаг 1: по одному LLM-вызову на конкурента (до 4 параллельно). Модель не
               «сплавляет» описания 20 разных товаров и выдаёт конкретные
               формулировки каждого, а не общие слова категории.
        Шаг 2: слияние формулировок (LLM, батчами) — «книга по вязанию крючком»
               и «вязание крючком книга» становятся одной фразой.
        Шаг 3: запись — wb_competitor_phrase (канон-группы) +
               wb_competitor_phrase_comp (сырьё с привязкой «фраза → конкурент»).
        """
        if not await _phrase_schema_ready(self.db):
            raise ValueError("Нужна миграция 20261026_competitor_phrase_comp.sql")
        if not await _run_progress_ready(self.db):
            raise ValueError("Нужна миграция 20261027_competitor_phrase_progress.sql")
        card = await self._card(nm_id) or {}
        comps = await self._competitors_with_content(nm_id)
        if not comps:
            raise ValueError("Нет собранных описаний конкурентов: привяжите конкурентов и соберите контент расширением")
        st = await self._company_settings(nm_id)
        company_id = st.get("company_id") or self.company_id or card.get("company_id")
        if not company_id:
            raise ValueError("Не удалось определить компанию карточки")
        custom_prompt = (st.get("seo_phrases_prompt") or "").strip()
        prompt = (custom_prompt + PHRASES_TASK_SUFFIX) if custom_prompt else DEFAULT_PHRASES_PROMPT
        prompt_source = "company" if custom_prompt else "default"
        cands = (await llm.model_candidates(
            self.db, company_id, kind="newcard",
        ))[:MAX_AI_ATTEMPTS]
        if not cands:
            raise ValueError("Нет доступных моделей для анализа фраз")

        # инкрементальность: описание конкурента не менялось — модель не зовём
        cached = await self._comp_phrases_cached(nm_id)
        plan: list[tuple[dict, list[str] | None]] = []
        for c in comps:
            old = cached.get(int(c["nm_id"]))
            if old and old["hash"] and old["hash"] == _comp_content_hash(c) and old["phrases"]:
                plan.append((c, list(old["phrases"])))
            else:
                plan.append((c, None))
        todo = [c for c, ph in plan if ph is None]
        cached_n = len(plan) - len(todo)
        hash_by_id = {int(c["nm_id"]): _comp_content_hash(c) for c in comps}
        model_by_id = {int(c["nm_id"]): (cached.get(int(c["nm_id"])) or {}).get("model")
                       for c in comps}
        merge_batches = 1
        # total в пределах фазы: extract — сколько конкурентов разобрать,
        # merge — сколько батчей слить (счётчик перезапускается на фазе)
        await self._run_start(run_id, nm_id, "phrases", len(todo), company_id)

        # чистим старое сырьё и сразу кладём кэшированных конкурентов (их не пересчитываем)
        await self.db.rollback()
        await self.db.execute(text("""
            DELETE FROM wb_competitor_phrase_comp WHERE source_nm_id=:n
        """), {"n": nm_id})
        await self.db.commit()
        for c, ph in plan:
            if ph is not None:
                await self._save_comp_rows(nm_id, company_id, int(c["nm_id"]), ph,
                                           model_by_id.get(int(c["nm_id"])),
                                           hash_by_id.get(int(c["nm_id"]), ""))

        # --- шаг 1: извлечение по конкурентам (параллельно, до LLM_PARALLEL) ---
        sem = asyncio.Semaphore(LLM_PARALLEL)
        extracted: dict[int, list[str]] = {}
        used_model: dict[int, str] = {}
        errors: list[str] = []

        async def one(comp: dict) -> tuple[int, list[str], str | None, str | None]:
            async with sem:
                last = None
                for model in cands[:PER_CALL_ATTEMPTS]:
                    phrases, err = await self._phrases_for_competitor(
                        comp, model, company_id, user_id, nm_id, prompt)
                    if phrases:
                        return int(comp["nm_id"]), phrases, None, model
                    last = err
                return int(comp["nm_id"]), [], last, cands[0]

        done = 0
        # кэшированные конкуренты уже готовы — отмечаем сразу
        done_ids: list[str] = [str(int(c["nm_id"])) for c, ph in plan if ph is not None]
        if todo:
            tasks = [asyncio.create_task(one(c)) for c in todo]
            for fut in asyncio.as_completed(tasks):
                cid, phrases, err, model = await fut
                done += 1
                if model:
                    try:
                        await llm.mark_model(self.db, model, bool(phrases), err or "")
                    except Exception:
                        await self.db.rollback()
                if phrases:
                    extracted[cid] = phrases
                    if model:
                        used_model[cid] = model
                    # сырьё сразу в БД — прогресс виден и не теряется при падении
                    try:
                        await self._save_comp_rows(nm_id, company_id, cid, phrases, model,
                                                   hash_by_id.get(cid, ""))
                    except Exception:
                        await self.db.rollback()
                else:
                    errors.append(f"nm {cid}: {err or 'нет фраз'}")
                done_ids.append(str(cid))
                try:
                    await self._run_step(run_id, done, model or "", "extract", ",".join(done_ids))
                except Exception:
                    await self.db.rollback()
        for c, ph in plan:
            if ph is not None:
                extracted[int(c["nm_id"])] = list(ph)
        if not extracted:
            await self._run_finish(run_id, "error", errors[0] if errors else "нет фраз")
            raise ValueError(errors[0] if errors else "Модель не вернула пригодных фраз")

        # --- шаг 2: слияние формулировок ---
        phrase_comp: dict[str, set[int]] = {}
        for cid, phrases in extracted.items():
            for p in phrases:
                phrase_comp.setdefault(p, set()).add(cid)
        # фаза слияния: свой счётчик (батчи), total перезаписываем
        merge_batches = max(1, -(-len(set(_perm_key(p) for p in phrase_comp)) // MERGE_BATCH))
        if run_id:
            await self.db.execute(text(
                "UPDATE wb_competitor_run SET total=:t, phase='merge', attempt=0 WHERE run_id=:r"),
                {"t": merge_batches, "r": run_id[:64]})
            await self.db.commit()
        main_model = used_model.get(next(iter(extracted)), "") or ""
        groups = await self._merge_groups(phrase_comp, cands, company_id, user_id,
                                          nm_id, errors, run_id=run_id)
        groups = [g for g in (groups or []) if g]
        if not groups:
            await self._run_finish(run_id, "error", "После слияния не осталось фраз")
            raise ValueError("После слияния не осталось фраз")
        # --- шаг 3: запись ---
        stats = await self._phrase_stats([p for g in groups for p in g],
                                         card.get("subject_name") or "")
        await self._write_groups(nm_id, company_id, groups, phrase_comp, stats, main_model)
        out = await self.list_phrases(nm_id)
        out["model"] = main_model
        out["competitors_cnt"] = len(comps)
        out["analyzed_cnt"] = len(todo)
        out["cached_cnt"] = cached_n
        out["groups_cnt"] = len(groups)
        out["raw_cnt"] = len(phrase_comp)
        out["merged_cnt"] = max(0, len(phrase_comp) - len(groups))
        out["errors"] = errors[:5]
        out["prompt_version"] = PHRASES_PROMPT_VERSION
        out["merge_prompt_version"] = MERGE_PROMPT_VERSION
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
                VALUES (:c, :n, :p, 'manual', 0, :o, :f, :cc, :indb, 1) AS new
                ON DUPLICATE KEY UPDATE
                  is_selected=1, orders=new.orders, freq=new.freq,
                  cards_cnt=new.cards_cnt, in_db=new.in_db
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
                VALUES (:c, :n, :r, :raw, :t, :d, :cnt, :m) AS new
                ON DUPLICATE KEY UPDATE company_id=new.company_id, result=new.result,
                  raw_ai_response=new.raw_ai_response, suggested_title=new.suggested_title,
                  suggested_description=new.suggested_description,
                  competitor_count=new.competitor_count, model=new.model
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
                WHERE nm_id IN ({ph}) AND nm_id > 0
            ) t
            WHERE t.nm_id NOT IN (
                SELECT nm_id FROM wb_competitor_details
                WHERE full_collected_at > NOW() - INTERVAL 24 HOUR
            )
              AND NOT EXISTS (SELECT 1 FROM wb_competitor_capture cap
                              WHERE cap.nm_id=t.nm_id AND cap.company_id=:cid
                                AND cap.is_hidden=1)
            ON DUPLICATE KEY UPDATE
              company_id=IF(company_id IS NULL, :cid, company_id),
              status=IF((company_id IS NULL OR company_id=:cid) AND status IN ('done','error'), 'pending', status)
        """), {"cid": cid, **{f"q{i}": v for i, v in enumerate(nm_ids)}})
