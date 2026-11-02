#!/usr/bin/env python3
"""Проверка реестра: ловит дубли, которые появляются ПОСЛЕ генерации.

Ключевая идея — разделение «нового» и «накопленного»:
  - `known.json` хранит уже найденные проблемы (снимок на момент признания);
  - проверка сообщает только о НОВЫХ проблемах, а известные показывает отдельно
    как «долг» — иначе отчёт в 8000 строк никто не прочитает.

Запуск:
    python3 backend/scripts/registry_check.py              # новые проблемы + долг
    python3 backend/scripts/registry_check.py --all        # без разделения, весь список
    python3 backend/scripts/registry_check.py --accept     # принять текущие как известные
    python3 backend/scripts/registry_check.py --reset      # сбросить базу известного

Код возврата: 0 — новых нарушений нет; 1 — есть новые; 2 — реестр устарел.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry_gen import (  # noqa: E402
    ROOT,
    SRC,
    BE,
    DOCS,
    REG,
    collect_components,
    collect_indexes,
    collect_styles,
    consumers_of,
    mark_duplicates,
    read,
)

try:  # консоль Windows — cp1251, а кириллица в сообщениях нужна
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

KNOWN = DOCS / "registry" / "known.json"

# Канонические фильтры. WbFilterBar — легаси (4 страницы), мигрируем на WbUniversalFilter.
CANONICAL_FILTERS = {"WbUniversalFilter.vue", "WbDateRangeFilter.vue"}
LEGACY_FILTERS = {"WbFilterBar.vue"}

# Классы темы — свои не создаём (AGENTS.md:47, theme.md §3).
THEME_CLASS_PREFIXES = (
    "tile", "tbl", "card__", "wb-panel", "wsp", "mn", "stab", "btn--",
    "badge--", "wb-input", "wb-field", "opt", "prod", "hd-", "wb-modal",
)

problems: list[tuple[str, str, str]] = []


def key_of(kd: tuple[str, str, str]) -> str:
    """Стабильный ключ проблемы для базы известного."""
    return f"{kd[0]}|{kd[2]}"


def report(kind: str, detail: str, key: str | None = None) -> None:
    """Ключ по умолчанию = текст находки.

    Если в тексте есть изменчивая часть (счётчик, список файлов), передаётся
    отдельный `key` — иначе любое косметическое изменение в коде выглядело бы
    как новая проблема и ломало базу известного.
    """
    problems.append((kind, detail, key if key is not None else detail))


# --------------------------------------------------------------------------
def check_filters() -> None:
    for f in list(SRC.rglob("*.vue")) + list(SRC.rglob("*.ts")):
        text = read(f)
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        for m in re.finditer(r"from\s+'([^']*\.vue)'", text):
            name = Path(m.group(1)).name
            if "Filter" not in name and "filter" not in name:
                continue
            if name in CANONICAL_FILTERS:
                continue
            if name in LEGACY_FILTERS:
                report("ФИЛЬТР-ЛЕГАСИ", f"{rel} → {name} (канон: WbUniversalFilter.vue)")
                continue
            report(
                "ФИЛЬТР-ЛОКАЛЬНЫЙ",
                f"{rel} → {name} (канон: WbUniversalFilter.vue / WbDateRangeFilter.vue)",
            )


def check_component_dups(comps: list[dict]) -> None:
    """Дубль по сигнатуре.

    Сравниваем ПАРАМИ, а не группами: пара (A, B) — стабильный ключ.
    Появился новый компонент → появляются только пары с его участием,
    а не перегенерируется весь список.
    """
    by_sig: dict[tuple, list[dict]] = collections.defaultdict(list)
    for c in comps:
        key = (tuple(sorted(c["props"])), tuple(c["emits"]), tuple(c["slots"]))
        if any(key):
            by_sig[key].append(c)
    for group in by_sig.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = sorted([group[i]["path"], group[j]["path"]])
                report("ДУБЛЬ-СИГНАТУРА", f"{a} ~ {b}")


def check_modal_dups(comps: list[dict]) -> None:
    """Модалки с ≥80% одинаковым каркасом — парами, без повторов."""
    pairs: set[tuple[str, str]] = set()
    for c in comps:
        for other in c.get("dup_markup", []):
            pairs.add(tuple(sorted([c["path"], other])))
    for a, b in sorted(pairs):
        report("ДУБЛЬ-КАРКАС", f"{a} ~ {b}")


def check_class_collisions(comps: list[dict]) -> None:
    """Класс, определённый в scoped-стиле компонента, уже есть в глобальном CSS.

    Это не «много классов», а конкретная коллизия: правило `AGENTS.md:44`
    «глобальные классы из страничного CSS не переопределять».

    В тексте находки — только компонент и класс: список CSS-файлов не входит,
    иначе добавление любого нового файла ломало бы ключ в базе известного.
    """
    global_classes: dict[str, list[str]] = collections.defaultdict(list)
    for f in (ROOT / "frontend" / "src" / "assets" / "css").rglob("*.css"):
        text = read(f)
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        for m in re.finditer(r"\.([a-zA-Z][\w-]*)", text):
            global_classes[m.group(1)].append(rel)
    if not global_classes:
        return
    for c in comps:
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", c["text"], re.S):
            for cls in sorted(set(re.findall(r"\.([a-zA-Z][\w-]*)", m.group(1)))):
                if cls in global_classes:
                    report("КЛАСС-ПЕРЕСЕЧЕНИЕ", f"{c['path']} → .{cls}")


def check_inline_repeats(comps: list[dict]) -> None:
    _, inline = collect_styles(comps)
    for n, value in sorted(((k, v) for k, v in inline.items() if v >= 4), reverse=True):
        report("ИНЛАЙН-ПОВТОР", f"{n}× `{value}`", key=value)


def check_index_dups() -> None:
    for t, ks in sorted(collect_indexes().items()):
        seen: dict[tuple, list[str]] = collections.defaultdict(list)
        for kind, name, cols in ks:
            seen[(kind, cols)].append(name)
        for (kind, cols), names in seen.items():
            if len(names) > 1:
                report(
                    "ИНДЕКС-ДУБЛЬ",
                    f"{t}: {kind} ({cols}) → {', '.join(names)}",
                    key=f"{t}: {kind} ({cols})",
                )


def check_doc_links() -> None:
    """Ссылки на файлы в docs/ — должны существовать.

    Путь резолвится от корня репозитория и от каталога самого md-файла.
    """
    repo_files: set[str] = set()
    names: set[str] = set()
    # пути относительно разных корней, встречающихся в документации
    roots = [ROOT, SRC, BE, ROOT / "backend", ROOT / "frontend"]
    for base_dir in roots:
        for f in base_dir.rglob("*"):
            if not f.is_file():
                continue
            if any(x in f.parts for x in ("node_modules", ".git", "__pycache__", "dist", ".vite")):
                continue
            try:
                rel = f.relative_to(base_dir).as_posix()
            except ValueError:
                continue
            repo_files.add(rel)
            names.add(f.name)

    md_files = sorted(DOCS.rglob("*.md")) if DOCS.exists() else []
    md_files += [ROOT / "AGENTS.md", ROOT / "theme.md", ROOT / "README.md"]
    ref = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:vue|py|css|ts|js|md|sql|json|yaml|yml|sh)\b")
    seen: set[tuple[str, str]] = set()
    for f in md_files:
        if not f.exists():
            continue
        rel_md = str(f.relative_to(ROOT)).replace("\\", "/")
        base = f.parent
        for m in ref.finditer(read(f)):
            r = m.group(0).replace("\\", "/").strip("`'\"()[]")
            if r.startswith(("http", "/tmp/", "/var/", "C:", "~")):
                continue
            if re.search(r"(^|/)(xxx|Xxx|\.\.\.)", r):
                continue
            # путь от корня репозитория
            if r in repo_files:
                continue
            # путь от каталога md-файла
            try:
                cand = (base / r).resolve().relative_to(ROOT).as_posix()
            except (ValueError, OSError):
                cand = None
            if cand and cand in repo_files:
                continue
            # только имя файла, если оно однозначное
            if "/" not in r and r in names:
                continue
            seen.add((rel_md, r))
    for rel_md, r in sorted(seen):
        report("БИТАЯ-ССЫЛКА", f"{rel_md} → {r}")


# --------------------------------------------------------------------------
def load_known() -> set[str]:
    if not KNOWN.exists():
        return set()
    try:
        return set(json.loads(read(KNOWN)).get("known", []))
    except Exception:
        return set()


def save_known(items: set[str]) -> None:
    KNOWN.parent.mkdir(parents=True, exist_ok=True)
    KNOWN.write_text(
        json.dumps({"known": sorted(items)}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Проверка реестра проекта")
    ap.add_argument("--all", action="store_true", help="показать все, без разделения на новое/долг")
    ap.add_argument("--accept", action="store_true", help="принять текущие проблемы как известные")
    ap.add_argument("--reset", action="store_true", help="сбросить базу известного")
    args = ap.parse_args()

    if args.reset:
        if KNOWN.exists():
            KNOWN.unlink()
        print("База известного сброшена.")
        return 0

    comps = collect_components()
    consumers = consumers_of()
    mark_duplicates(comps, consumers)
    by_name: dict[str, str] = {c["name"]: c["path"] for c in comps}
    for c in comps:
        c["_by_name"] = by_name

    check_filters()
    check_component_dups(comps)
    check_modal_dups(comps)
    check_class_collisions(comps)
    check_inline_repeats(comps)
    check_index_dups()
    check_doc_links()

    key = lambda kd: key_of(kd)
    if args.accept:
        save_known({key(p) for p in problems})
        print(f"Принято как известное: {len(problems)}")
        return 0

    known = load_known()
    fresh = [p for p in problems if key(p) not in known]
    debt = [p for p in problems if key(p) in known]

    if args.all:
        groups: dict[str, list[str]] = collections.defaultdict(list)
        for kind, detail, _ in problems:
            groups[kind].append(detail)
        print(f"Всего проблем: {len(problems)}")
        for kind in sorted(groups):
            print(f"\n[{kind}] — {len(groups[kind])}")
            for d in groups[kind]:
                print(f"    {d}")
        return 1 if problems else 0

    print(f"Новых нарушений: {len(fresh)}   (накопленный долг: {len(debt)})")
    print()
    if fresh:
        groups = collections.defaultdict(list)
        for kind, detail, _ in fresh:
            groups[kind].append(detail)
        for kind in sorted(groups):
            print(f"[{kind}] — {len(groups[kind])}")
            for d in groups[kind][:30]:
                print(f"    {d}")
            if len(groups[kind]) > 30:
                print(f"    …ещё {len(groups[kind]) - 30}")
            print()
    else:
        print("Новых нарушений нет — новый код не плодит дубли.")

    if debt:
        by_kind = collections.Counter(k for k, _, _ in debt)
        print("Накопленный долг (известно, ждёт отдельных задач):")
        for kind, n in sorted(by_kind.items()):
            print(f"    {kind}: {n}")
    return 1 if fresh else 0


if __name__ == "__main__":
    sys.exit(main())
