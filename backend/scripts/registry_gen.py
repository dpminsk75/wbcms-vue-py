#!/usr/bin/env python3
"""Реестр проекта: что уже есть (компоненты, таблицы, стили).

Генерирует docs/registry/*.md из исходников. Только стандартная библиотека.

Запуск:
    python3 backend/scripts/registry_gen.py            # перегенерировать
    python3 backend/scripts/registry_gen.py --check    # только проверить, что актуально

Файлы результата помечены "АВТОГЕНЕРИРОВАНО" — править их руками нельзя,
иначе они разойдутся с кодом. Ручные решения — в docs/decisions/.
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"
BE = ROOT / "backend"
DOCS = ROOT / "docs"
REG = DOCS / "registry"

# Структура БД лежит в legacy-репозитории wbcms; путь можно переопределить.
STRUCTURE_SQL = Path(
    __import__("os").environ.get(
        "WBCMS_STRUCTURE_SQL", r"D:\OpenCode\wbcms\structure.sql"
    )
)

BANNER = (
    "<!-- АВТОГЕНЕРИРОВАНО: backend/scripts/registry_gen.py — не править руками.\n"
    "     Перегенерировать: python3 backend/scripts/registry_gen.py -->\n"
)


# --------------------------------------------------------------------------
# утилиты разбора
# --------------------------------------------------------------------------
def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def split_top(s: str) -> list[str]:
    """Разбить по запятым верхнего уровня (игнорируя вложенные <>()[]{})."""
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in s:
        if ch in "<([{":
            depth += 1
        elif ch in ">)]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [x.strip() for x in out if x.strip()]


def gblock(text: str, marker: str) -> str:
    """Содержимое generic-блока {…} после `marker<` — с учётом вложенности."""
    m = re.search(re.escape(marker) + r"<", text)
    if not m:
        return ""
    start = text.find("{", m.end())
    if start < 0:
        return ""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return ""


def props_of(text: str) -> list[str]:
    """Имена props из defineProps<{…}> — по запятым, а не по строкам."""
    out: list[str] = []
    for part in split_top(gblock(text, "defineProps")):
        m = re.match(r"([a-zA-Z_]\w*)\??\s*[:?]", part)
        if m:
            out.append(m.group(1))
    return out


def emits_of(text: str) -> list[str]:
    """Имена событий из defineEmits<{…}> — по запятым верхнего уровня."""
    out: list[str] = []
    for part in split_top(gblock(text, "defineEmits")):
        out += re.findall(r"['\"]([^'\"]+)['\"]", part)
    return sorted(set(out))


def models_of(text: str) -> list[str]:
    """Имена v-model из defineModel('name') / defineModel<T>('name')."""
    out: list[str] = []
    for m in re.finditer(r"defineModel(?:<[^>]*>)?\(\s*['\"]([^'\"]+)['\"]", text):
        out.append(m.group(1))
    if re.search(r"defineModel(?:<[^>]*>)?\(\s*\)", text):
        out.append("(modelValue)")
    return out


def slots_of(text: str) -> list[str]:
    return sorted(set(re.findall(r"<slot[^>]*name=\"([^\"]+)\"", text)))


def purpose_of(text: str) -> str:
    """Первая строка doc-комментария в <script setup> — назначение компонента."""
    m = re.search(r"<script setup[^>]*>(.*?)</script>", text, re.S)
    if not m:
        return ""
    d = re.search(r"/\*\*\s*\n?\s*(.{0,400}?)\*/", m.group(1), re.S)
    if not d:
        return ""
    lines = [x.strip(" *") for x in d.group(1).splitlines() if x.strip(" *")]
    return " ".join(lines)[:200]


def skeleton(text: str) -> str:
    """Скелет разметки без текста/интерполяций/биндингов — для сравнения похожих."""
    m = re.search(r"<template>(.*?)</template>", text, re.S)
    if not m:
        return ""
    s = m.group(1)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\{\{.*?\}\}", "", s)
    s = re.sub(r":[a-zA-Z-]+=\"[^\"]*\"", "", s)
    s = re.sub(r"@[a-zA-Z:.-]+=\"[^\"]*\"", "", s)
    s = re.sub(r"[0-9a-zA-Z_]+", "", s)
    return re.sub(r"\s+", "", s)


def consumers_of() -> dict[str, set[str]]:
    """Файл -> какие .vue он импортирует (по имени файла).

    Учитываются оба вида импорта:
      - статический: `import X from './X.vue'`
      - динамический: `import('../pages/X.vue')` — так подключаются все страницы в роутере.
    """
    out: dict[str, set[str]] = collections.defaultdict(set)
    for f in list(SRC.rglob("*.vue")) + list(SRC.rglob("*.ts")):
        text = read(f)
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        specs = [m.group(1) for m in re.finditer(r"from\s+'([^']*\.vue)'", text)]
        specs += [m.group(1) for m in re.finditer(r"import\(\s*['\"]([^'\"]*\.vue)['\"]\s*\)", text)]
        for spec in specs:
            if spec.startswith("@/"):
                resolved = "frontend/src/" + spec[2:]
            elif spec.startswith("."):
                try:
                    resolved = str((f.parent / spec).resolve().relative_to(ROOT)).replace("\\", "/")
                except ValueError:
                    continue
            else:
                continue
            out[Path(resolved).name].add(rel)
    return out


# --------------------------------------------------------------------------
# 1. Компоненты
# --------------------------------------------------------------------------
def collect_components() -> list[dict]:
    comps: list[dict] = []
    for f in sorted(SRC.rglob("*.vue")):
        text = read(f)
        rel = str(f.relative_to(SRC)).replace("\\", "/")
        comps.append(
            {
                "path": rel,
                "dir": str(f.relative_to(SRC).parent).replace("\\", "/"),
                "props": props_of(text),
                "emits": emits_of(text),
                "models": models_of(text),
                "slots": slots_of(text),
                "purpose": purpose_of(text),
                "skeleton": skeleton(text),
                "text": text,
                "name": f.name,
            }
        )
    return comps


def mark_duplicates(comps: list[dict], consumers: dict[str, set[str]]) -> None:
    """Пометить группы дублей: по сигнатуре (props+emits+slots) и по скелету."""
    by_sig: dict[tuple, list[dict]] = collections.defaultdict(list)
    for c in comps:
        key = (tuple(sorted(c["props"])), tuple(c["emits"]), tuple(c["slots"]))
        if any(key):
            by_sig[key].append(c)

    for group in by_sig.values():
        if len(group) > 1:
            names = [c["name"] for c in group]
            for c in group:
                c["dup_sig"] = names

    modals = [c for c in comps if "wb-modal-backdrop" in c["text"]]
    for i in range(len(modals)):
        for j in range(i + 1, len(modals)):
            a, b = modals[i], modals[j]
            if not a["skeleton"] or not b["skeleton"]:
                continue
            ratio = difflib.SequenceMatcher(None, a["skeleton"], b["skeleton"]).quick_ratio()
            if ratio >= 0.80:
                a.setdefault("dup_markup", []).append(b["path"])
                b.setdefault("dup_markup", []).append(a["path"])

    for c in comps:
        c["used_by"] = sorted(consumers.get(c["name"], set()))
        c["dup_markup"] = sorted(set(c.get("dup_markup", [])))


def write_components(comps: list[dict]) -> str:
    groups: dict[tuple, list[str]] = collections.defaultdict(list)
    for c in comps:
        if c.get("dup_sig"):
            groups[tuple(c["dup_sig"])] = c["dup_sig"]

    L: list[str] = []
    L.append("# Реестр компонентов")
    L.append("")
    L.append(BANNER.rstrip())
    L.append("")
    L.append(f"Всего `.vue` в `frontend/src`: **{len(comps)}**, из них в `components/`: "
             f"**{sum(1 for c in comps if c['path'].startswith('components/'))}**.")
    L.append("")
    L.append("Колонка **Дубль** — компоненты с одинаковой сигнатурой (props+emits+slots).")
    L.append("Это не ошибка само по себе, но перед созданием нового — проверь, нет ли готового.")
    L.append("")

    # ключ сортировки включает имена — иначе группы одного размера
    # выводились в порядке хеширования и файл менялся от запуска к запуску
    dup_rows = sorted(
        ((len(g), g) for g in {tuple(v) for v in groups.values()}),
        key=lambda x: (-x[0], x[1]),
    )
    L.append(f"## Групп с одинаковой сигнатурой: {len(dup_rows)}")
    L.append("")
    if dup_rows:
        L.append("| В группе | Компоненты |")
        L.append("|---:|---|")
        for n, g in dup_rows:
            L.append(f"| {n} | " + ", ".join(f"`{x}`" for x in g) + " |")
        L.append("")

    L.append("## Модалки: одинаковый каркас, скопированный N раз")
    L.append("")
    L.append("`theme.md` §5.8: «не плодить свои модалки, взять существующий каркас")
    L.append("`.wb-modal-backdrop` / `.wb-modal-box`».")
    L.append("")
    markup = [c for c in comps if c.get("dup_markup")]
    if markup:
        L.append("Компоненты с ≥80% одинаковым скелетом разметки (текст и биндинги вырезаны):")
        L.append("")
        for c in sorted(markup, key=lambda x: -len(x["dup_markup"])):
            L.append(f"- `{c['name']}` — совпадает с: " + ", ".join(f"`{x}`" for x in c["dup_markup"]))
        L.append("")

    L.append("## Полный список")
    L.append("")
    L.append("| Компонент | props | models | emits | slots | Используют | Дубль | Назначение |")
    L.append("|---|---:|---|---|---|---:|---|---|")
    for c in sorted(comps, key=lambda x: x["path"]):
        props = ", ".join(c["props"]) or "—"
        models = ", ".join(c["models"]) or "—"
        emits = ", ".join(c["emits"]) or "—"
        slots = ", ".join(c["slots"]) or "—"
        used = str(len(c["used_by"])) if c["used_by"] else "**0**"
        dup = "⚠ " + ", ".join(f"`{x}`" for x in c["dup_sig"]) if c.get("dup_sig") else (
            "≈ " + ", ".join(f"`{x}`" for x in c["dup_markup"]) if c.get("dup_markup") else "—"
        )
        purpose = c["purpose"] or "—"
        L.append(
            f"| `{c['path']}` | {props} | {models} | {emits} | {slots} | {used} | {dup} | {purpose} |"
        )
    L.append("")

    orphans = [c for c in comps if not c["used_by"] and c["path"].startswith("components/")]
    L.append("## Ни разу не импортированные")
    L.append("")
    if orphans:
        for c in orphans:
            L.append(f"- `{c['path']}`")
    else:
        L.append("— нет.")
    L.append("")

    nodoc = [c for c in comps if not c["purpose"] and c["path"].startswith("components/")]
    L.append(f"## Без doc-комментария: {len(nodoc)}")
    L.append("")
    L.append("Назначение этих компонентов не видно из кода — реестр их не описывает.")
    L.append("")
    if nodoc:
        L.append(", ".join(f"`{c['path']}`" for c in nodoc))
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# 2. Таблицы и индексы
# --------------------------------------------------------------------------
def collect_tables() -> tuple[dict, dict]:
    writes: dict[str, set[str]] = collections.defaultdict(set)
    reads: dict[str, set[str]] = collections.defaultdict(set)
    files = list((BE / "services").glob("*.py")) + list((BE / "routers").glob("*.py")) + list(BE.glob("*.py"))
    pat = re.compile(r"(?:INTO|UPDATE)\s+`?(wb_[a-z_]+|wbcards|agg_[a-z_]+|pvz_[a-z_]+|dadata_[a-z_]+)", re.I)
    pat2 = re.compile(r"(?:FROM|JOIN)\s+`?(wb_[a-z_]+|wbcards|agg_[a-z_]+|pvz_[a-z_]+|dadata_[a-z_]+)", re.I)
    for f in files:
        text = read(f)
        rel = str(f.relative_to(BE)).replace("\\", "/")
        for m in pat.finditer(text):
            writes[m.group(1).lower()].add(rel)
        for m in pat2.finditer(text):
            reads[m.group(1).lower()].add(rel)
    return writes, reads


def collect_indexes() -> dict[str, list[tuple[str, str, str]]]:
    """таблица -> [(вид, имя, столбцы)] из structure.sql (или из миграций)."""
    per: dict[str, list[tuple[str, str, str]]] = collections.defaultdict(list)
    if STRUCTURE_SQL.exists():
        text = read(STRUCTURE_SQL)
        cur = None
        for line in text.splitlines():
            m = re.match(r"\s*CREATE TABLE\s+`?(\w+)`?", line, re.I)
            if m:
                cur = m.group(1)
                continue
            m = re.match(r"\s*(UNIQUE\s+)?KEY\s+`?(\w+)`?\s*\((.*)\),?\s*$", line, re.I)
            if m and cur:
                cols = ",".join(
                    c.strip() for c in split_top(re.sub(r"\(\d+\)", "", m.group(3)))
                )
                per[cur].append(("UNIQUE" if m.group(1) else "INDEX", m.group(2), cols))
        return per

    # запасной вариант — миграции
    mig = BE / "migrations"
    for f in list(mig.glob("*.sql")) + list((mig / "bak").glob("*.sql")):
        text = read(f)
        for m in re.finditer(
            r"ALTER TABLE\s+`?(\w+)`?[^;]*?ADD\s+(UNIQUE\s+)?(?:KEY|INDEX)\s+`?(\w+)`?\s*\(([^)]*)\)",
            text,
            re.I | re.S,
        ):
            cols = ",".join(c.strip() for c in split_top(re.sub(r"\(\d+\)", "", m.group(4))))
            per[m.group(1)].append(("UNIQUE" if m.group(2) else "INDEX", m.group(3), cols))
    return per


def write_tables() -> str:
    writes, reads = collect_tables()
    indexes = collect_indexes()
    tables = sorted(set(writes) | set(reads))

    L: list[str] = []
    L.append("# Реестр таблиц БД")
    L.append("")
    L.append(BANNER.rstrip())
    L.append("")
    L.append(f"Таблиц, к которым обращается код: **{len(tables)}**.")
    L.append(f"Индексов в схеме: **{sum(len(v) for v in indexes.values())}**.")
    L.append("")

    L.append("## Кто пишет, кто читает")
    L.append("")
    L.append("| Таблица | Пишет (файлов) | Читает (файлов) | Индексов |")
    L.append("|---|---:|---:|---:|")
    for t in tables:
        nw = len(writes.get(t, ()))
        nr = len(reads.get(t, ()))
        L.append(f"| `{t}` | {nw if nw else '—'} | {nr if nr else '—'} | {len(indexes.get(t, []))} |")
    L.append("")

    ro = [t for t in tables if t in reads and t not in writes]
    L.append("## Читается, но не пишется кодом")
    L.append("")
    L.append("Либо таблица заполняется вне этого репозитория (импорт, legacy), либо осталась в наследство.")
    L.append("")
    for t in ro:
        L.append(f"- `{t}`")
    if not ro:
        L.append("— нет.")
    L.append("")

    L.append("## Дубли индексов внутри одной таблицы")
    L.append("")
    L.append("Одинаковые имена индексов в *разных* таблицах — легально в MySQL")
    L.append("(имя уникально в пределах таблицы) и дефектом не является.")
    L.append("А вот два индекса на одном столбце в одной таблице — мусор.")
    L.append("")
    found = False
    for t, ks in sorted(indexes.items()):
        seen: dict[tuple, list[str]] = collections.defaultdict(list)
        for kind, name, cols in ks:
            seen[(kind, cols)].append(name)
        for (kind, cols), names in seen.items():
            if len(names) > 1:
                found = True
                L.append(f"- `{t}`: {kind} на ({cols}) → " + ", ".join(f"`{n}`" for n in names))
    if not found:
        L.append("— не найдено.")
    L.append("")

    L.append("## Таблицы с наибшим числом индексов")
    L.append("")
    L.append("| Таблица | Индексов | Имена |")
    L.append("|---|---:|---|")
    for t, ks in sorted(indexes.items(), key=lambda x: (-len(x[1]), x[0]))[:15]:
        names = ", ".join(f"`{n}`" for _, n, _ in ks)
        L.append(f"| `{t}` | {len(ks)} | {names} |")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# 3. Стили
# --------------------------------------------------------------------------
def collect_styles(comps: list[dict]) -> tuple[dict, collections.Counter]:
    classes: dict[str, set[str]] = collections.defaultdict(set)
    inline: collections.Counter = collections.Counter()
    for c in comps:
        text = c["text"]
        for m in re.finditer(r'class="([^"{}]+)"', text):
            for cls in m.group(1).split():
                if re.fullmatch(r"[a-z][a-z0-9_-]{2,}", cls):
                    classes[cls].add(c["path"])
        for m in re.finditer(r'style="([^"]*)"', text):
            s = m.group(1).strip()
            if s:
                inline[s] += 1
    return classes, inline


def bootstrap_classes() -> set[str]:
    """Классы Bootstrap — чтобы не считать их «нашими»."""
    p = ROOT / "frontend" / "node_modules" / "bootstrap" / "dist" / "css" / "bootstrap.css"
    if not p.exists():
        return set()
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", read(p)))


def theme_classes() -> set[str]:
    """Классы темы (theme/*.css) — эталон, свои под такими именами не создаём."""
    out: set[str] = set()
    for f in (ROOT / "frontend" / "src" / "assets" / "css" / "theme").glob("*.css"):
        out |= set(re.findall(r"\.([a-zA-Z][\w-]*)", read(f)))
    return out


def write_styles(comps: list[dict]) -> str:
    classes, inline = collect_styles(comps)
    bs = bootstrap_classes()
    theme = theme_classes()
    shared = sorted(((len(v), k) for k, v in classes.items() if len(v) >= 8), reverse=True)
    local = sorted(((len(v), k) for k, v in classes.items() if len(v) <= 2), reverse=True)
    repeated = sorted(((n, s) for s, n in inline.items() if n >= 4), reverse=True)

    L: list[str] = []
    L.append("# Реестр стилей")
    L.append("")
    L.append(BANNER.rstrip())
    L.append("")
    L.append(f"Классов в `class=\"…\"`: **{len(classes)}**. Значений `style=\"…\"`: **{len(inline)}**.")
    L.append("")

    L.append("## Наши общие классы (не Bootstrap, не тема)")
    L.append("")
    L.append("Используются в ≥8 компонентах, но не являются ни утилитой Bootstrap,")
    L.append("ни классом темы. Кандидаты на переезд в `assets/css/theme/`.")
    L.append("")
    ours = [(n, k) for n, k in shared if k not in bs and k not in theme]
    L.append(f"Всего: **{len(ours)}** (из {len(shared)} общих; остальные — Bootstrap и тема).")
    L.append("")
    if ours:
        L.append("| Класс | Компонентов |")
        L.append("|---|---:|")
        for n, k in ours:
            L.append(f"| `.{k}` | {n} |")
    L.append("")

    L.append("## Повторяющиеся инлайны (≥4 раза)")
    L.append("")
    L.append("`AGENTS.md`: свой CSS — только по явному указанию. Эти значения — готовые повторы.")
    L.append("")
    if repeated:
        L.append("| Раз | Значение |")
        L.append("|---:|---|")
        for n, s in repeated:
            L.append(f"| {n} | `{s}` |")
    else:
        L.append("— нет.")
    L.append("")

    L.append("## Пересечения с глобальным CSS")
    L.append("")
    L.append("Класс определён в `scoped`-стиле компонента, но уже есть в глобальном CSS.")
    L.append("`AGENTS.md`: «глобальные классы из страничного CSS не переопределять».")
    L.append("")
    global_classes: dict[str, list[str]] = collections.defaultdict(list)
    for f in (ROOT / "frontend" / "src" / "assets" / "css").rglob("*.css"):
        text = read(f)
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        for m in re.finditer(r"\.([a-zA-Z][\w-]*)", text):
            global_classes[m.group(1)].append(rel)
    collisions: dict[str, list[str]] = collections.defaultdict(list)
    for c in comps:
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", c["text"], re.S):
            for cls in sorted(set(re.findall(r"\.([a-zA-Z][\w-]*)", m.group(1)))):
                if cls in global_classes:
                    collisions[cls].append(c["path"])
    if collisions:
        L.append("| Класс | Компоненты | Уже в |")
        L.append("|---|---|---|")
        for cls in sorted(collisions):
            where = ", ".join(sorted(set(global_classes[cls]))[:2])
            L.append(f"| `.{cls}` | " + ", ".join(f"`{x}`" for x in collisions[cls]) + f" | {where} |")
    else:
        L.append("— нет.")
    L.append("")

    L.append("## Локальные классы (≤2 компонента)")
    L.append("")
    L.append("Кандидаты на обобщение: повторяющийся смысл, но разные имена.")
    L.append("")
    L.append(f"Всего: **{len(local)}** (полный список — в `styles.txt`).")
    L.append("")
    if local:
        L.append("| Класс | Компонентов |")
        L.append("|---|---:|")
        for n, k in local[:60]:
            L.append(f"| `.{k}` | {n} |")
        if len(local) > 60:
            L.append(f"| …ещё {len(local) - 60} | |")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build_data(comps: list[dict]) -> dict:
    """Данные реестра в JSON — для веб-витрины (registry_html.py)."""
    writes, reads = collect_tables()
    indexes = collect_indexes()
    classes, inline = collect_styles(comps)
    bs = bootstrap_classes()
    theme = theme_classes()

    tables = []
    for t in sorted(set(writes) | set(reads)):
        idx = indexes.get(t, [])
        names = [n for _, n, _ in idx]
        dup = False
        seen: dict[tuple, list[str]] = collections.defaultdict(list)
        for kind, name, cols in idx:
            seen[(kind, cols)].append(name)
        dup = any(len(v) > 1 for v in seen.values())
        tables.append(
            {
                "name": t,
                "writes": len(writes.get(t, ())),
                "reads": len(reads.get(t, ())),
                "idx_count": len(idx),
                "indexes": names,
                "read_only": t in reads and t not in writes,
                "dup_index": dup,
            }
        )

    global_classes: dict[str, list[str]] = collections.defaultdict(list)
    for f in (ROOT / "frontend" / "src" / "assets" / "css").rglob("*.css"):
        text = read(f)
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        for m in re.finditer(r"\.([a-zA-Z][\w-]*)", text):
            global_classes[m.group(1)].append(rel)
    collisions = []
    for c in comps:
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", c["text"], re.S):
            for cls in sorted(set(re.findall(r"\.([a-zA-Z][\w-]*)", m.group(1)))):
                if cls in global_classes:
                    collisions.append(
                        [cls, [c["path"]], ", ".join(sorted(set(global_classes[cls]))[:2])]
                    )

    def sort_by_count(pairs):
        return sorted(pairs, key=lambda x: (-x[1], x[0]))

    ours = sort_by_count(
        [(k, len(v)) for k, v in classes.items() if len(v) >= 8 and k not in bs and k not in theme]
    )
    local = sort_by_count([(k, len(v)) for k, v in classes.items() if len(v) <= 2])
    inline_rep = sorted(
        [(v, k) for k, v in inline.items() if v >= 4], key=lambda x: (-x[0], x[1])
    )

    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "counts": {
            "components": len(comps),
            "tables": len(tables),
            "classes": len(classes),
            "inline": len(inline),
            "indexes": sum(len(v) for v in indexes.values()),
        },
        "components": [
            {
                "_i": idx,
                "path": c["path"],
                "dir": c["dir"],
                "props": c["props"],
                "models": c["models"],
                "emits": c["emits"],
                "slots": c["slots"],
                "purpose": c["purpose"],
                "used_by": c["used_by"],
                "dup_sig": c.get("dup_sig", []),
                "dup_markup": c.get("dup_markup", []),
            }
            for idx, c in enumerate(comps)
        ],
        "tables": tables,
        "styles": {
            "ours": ours,
            "local": local,
            "inline": inline_rep,
            "collisions": collisions,
        },
    }


def build() -> dict[str, str]:
    comps = collect_components()
    consumers = consumers_of()
    mark_duplicates(comps, consumers)
    REG.mkdir(parents=True, exist_ok=True)
    out = {
        "components.md": write_components(comps),
        "tables.md": write_tables(),
        "styles.md": write_styles(comps),
    }
    data = build_data(comps)
    how = ""
    how_path = DOCS / "README.md"
    if how_path.exists():
        how = read(how_path)
    data["how_md"] = how
    (REG / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Генератор реестра проекта")
    ap.add_argument("--check", action="store_true", help="только проверить актуальность")
    args = ap.parse_args()

    files = build()
    if args.check:
        stale = []
        for name, content in files.items():
            p = REG / name
            if not p.exists() or read(p) != content:
                stale.append(name)
        if stale:
            print("Устарело (перегенерируй): " + ", ".join(stale))
            return 1
        print("Реестр актуален.")
        return 0

    for name, content in files.items():
        (REG / name).write_text(content, encoding="utf-8")
        print(f"записан: docs/registry/{name}")

    # веб-витрина — из тех же данных
    try:
        import registry_html

        registry_html.build()
    except Exception as exc:  # витрина не должна ломать генерацию
        print(f"витрина не собрана: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
