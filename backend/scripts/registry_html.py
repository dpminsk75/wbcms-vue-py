#!/usr/bin/env python3
"""Веб-витрина реестра: один самодостаточный HTML-файл.

Читает docs/registry/data.json (данные реестра) и docs/registry/known.json
(известные проблемы) и собирает docs/registry/index.html — статику без сети,
без зависимостей. Открывается двойным щелчком.

Запуск:
    python3 backend/scripts/registry_html.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry_gen import REG, read  # noqa: E402

DATA = REG / "data.json"
KNOWN = REG / "known.json"
OUT = REG / "index.html"


def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Реестр проекта — wbcms-site-proto</title>
<style>
:root{
  --bg:#F3F4F5; --surface:#FFFFFF; --surface-2:#F8F9FA; --surface-3:#EDEFF1;
  --ink:#111315; --ink-soft:#4C5257; --ink-muted:#969CA1;
  --line:#E1E3E6; --line-strong:#CBD0D4;
  --brand:#283445; --brand-hover:#1B2532; --brand-tint:#EDF0F4; --brand-deep:#1B2532; --brand-ink:#fff;
  --good:#0F8A5F; --good-tint:#E7F5EF; --good-deep:#0B5F49;
  --bad:#C62828; --bad-tint:#FBECEC; --bad-deep:#8E1E1E;
  --warn:#C2830B; --warn-tint:#FDF3E0; --warn-deep:#7A4A08;
  --info:#2563EB; --info-tint:#E9F0FE; --info-deep:#1A4C9E;
  --radius-sm:6px; --radius-md:10px; --radius-lg:14px;
  --shadow-1:0 1px 2px rgba(15,23,42,.06),0 1px 3px rgba(15,23,42,.04);
  --font:'Segoe UI',system-ui,-apple-system,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 var(--font)}
a{color:var(--info-deep);text-decoration:none}
a:hover{text-decoration:underline}
code,kbd{font-family:ui-monospace,'Cascadia Code',Consolas,monospace;font-size:.92em;
  background:var(--surface-3);padding:1px 5px;border-radius:4px}
header.top{background:var(--brand);color:#fff;padding:20px 28px}
header.top h1{margin:0 0 4px;font-size:21px;font-weight:700;letter-spacing:-.2px}
header.top .sub{opacity:.75;font-size:13px}
header.top .sub b{opacity:1;font-weight:600}
nav.tabs{display:flex;gap:2px;padding:0 28px;background:var(--surface);
  border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
nav.tabs button{border:0;background:none;padding:12px 16px;font:inherit;font-weight:600;
  color:var(--ink-soft);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
nav.tabs button:hover{color:var(--ink);background:var(--surface-2)}
nav.tabs button.on{color:var(--brand);border-bottom-color:var(--brand)}
nav.tabs button .n{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:99px;
  background:var(--surface-3);color:var(--ink-soft);font-size:11px;font-weight:600}
nav.tabs button.on .n{background:var(--brand-tint);color:var(--brand)}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:14px 28px;
  background:var(--surface);border-bottom:1px solid var(--line)}
.toolbar input[type=search]{flex:1;min-width:220px;padding:9px 12px;font:inherit;
  border:1px solid var(--line-strong);border-radius:var(--radius-sm);background:var(--surface-2)}
.toolbar input[type=search]:focus{outline:2px solid var(--brand);outline-offset:-1px;background:var(--surface)}
.chip{border:1px solid var(--line-strong);background:var(--surface);color:var(--ink-soft);
  padding:7px 13px;border-radius:99px;font:inherit;font-size:13px;cursor:pointer}
.chip:hover{background:var(--surface-2)}
.chip.on{background:var(--brand);border-color:var(--brand);color:#fff}
.count{color:var(--ink-muted);font-size:13px;margin-left:auto}
main{padding:22px 28px 60px;max-width:1500px}
.panel{display:none}
.panel.on{display:block}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-md);
  box-shadow:var(--shadow-1);margin-bottom:20px;overflow:hidden}
.card>h2{margin:0;padding:13px 18px;font-size:14px;font-weight:700;
  background:var(--brand-tint);color:var(--brand-deep);border-bottom:1px solid var(--line)}
.card .body{padding:16px 18px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:9px 12px;background:var(--surface-2);color:var(--ink-soft);
  font-weight:600;font-size:12px;border-bottom:1px solid var(--line-strong);
  position:sticky;top:0;cursor:pointer;user-select:none;white-space:nowrap}
th:hover{background:var(--surface-3)}
td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--surface-2)}
tbody tr.clickable{cursor:pointer}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.mono{font-family:ui-monospace,'Cascadia Code',Consolas,monospace;font-size:12px}
.muted{color:var(--ink-muted)}
.badge{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;
  font-weight:600;white-space:nowrap}
.b-ok{background:var(--good-tint);color:var(--good-deep)}
.b-bad{background:var(--bad-tint);color:var(--bad-deep)}
.b-warn{background:var(--warn-tint);color:var(--warn-deep)}
.b-info{background:var(--info-tint);color:var(--info-deep)}
.b-neutral{background:var(--surface-3);color:var(--ink-soft)}
.tag{display:inline-block;padding:1px 6px;border-radius:4px;background:var(--surface-3);
  color:var(--ink-soft);font-size:11px;margin:1px 3px 1px 0;
  font-family:ui-monospace,'Cascadia Code',Consolas,monospace}
.tag.dup{background:var(--bad-tint);color:var(--bad-deep)}
.detail{background:var(--surface-2);border-left:3px solid var(--brand)}
.detail td{font-size:13px}
.kv{display:grid;grid-template-columns:150px 1fr;gap:6px 14px;font-size:13px}
.kv dt{color:var(--ink-muted);font-size:12px;font-weight:600}
.kv dd{margin:0}
.empty{padding:34px;text-align:center;color:var(--ink-muted)}
.note{background:var(--warn-tint);border-left:3px solid var(--warn);padding:12px 16px;
  border-radius:0 var(--radius-sm) var(--radius-sm) 0;margin-bottom:18px;font-size:13px;color:var(--warn-deep)}
.note b{color:var(--warn-deep)}
.scroll{max-height:calc(100vh - 250px);overflow:auto}
.hint{font-size:12px;color:var(--ink-muted);margin:-6px 0 14px}
.kbd{background:var(--surface-3);border:1px solid var(--line-strong);border-bottom-width:2px;
  border-radius:4px;padding:1px 5px;font-size:11px}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px;font-size:13px;color:var(--ink-soft)}
.legend span{display:flex;align-items:center;gap:6px}
@media(max-width:760px){
  header.top,nav.tabs,.toolbar,main{padding-left:14px;padding-right:14px}
  .kv{grid-template-columns:1fr}
}
</style>
</head>
<body>
<header class="top">
  <h1>Реестр проекта — wbcms-site-proto</h1>
  <div class="sub">
    Что уже есть в проекте: компоненты, таблицы, стили.
    Сгенерировано <b id="gen"></b> · <b id="srcfiles"></b>
  </div>
</header>

<nav class="tabs" id="tabs">
  <button data-tab="comp" class="on">Компоненты <span class="n" id="n-comp"></span></button>
  <button data-tab="tbl">Таблицы БД <span class="n" id="n-tbl"></span></button>
  <button data-tab="sty">Стили <span class="n" id="n-sty"></span></button>
  <button data-tab="iss">Проблемы <span class="n" id="n-iss"></span></button>
  <button data-tab="how">Как пользоваться</button>
</nav>

<div class="toolbar">
  <input type="search" id="q" placeholder="Поиск по имени файла, пропсам, таблицам, классам…">
  <span class="count" id="cnt"></span>
</div>

<main>
  <section class="panel on" id="p-comp">
    <div class="legend">
      <span><span class="badge b-bad">дубль</span> совпадает с другим компонентом</span>
      <span><span class="badge b-warn">не используется</span> ни разу не импортирован</span>
      <span><span class="badge b-neutral">нет описания</span> нет doc-комментария</span>
    </div>
    <div class="toolbar" style="border:0;padding:0 0 12px;background:none">
      <button class="chip" data-f="dup">Только дубли</button>
      <button class="chip" data-f="unused">Только неиспользуемые</button>
      <button class="chip" data-f="nodoc">Только без описания</button>
    </div>
    <div class="card">
      <div class="scroll"><table id="t-comp">
        <thead><tr>
          <th data-s="path">Компонент</th>
          <th data-s="props">props</th>
          <th data-s="models">models</th>
          <th data-s="emits">emits</th>
          <th data-s="slots">slots</th>
          <th data-s="used" class="num">Используют</th>
          <th data-s="flags">Флаги</th>
          <th data-s="purpose">Назначение</th>
        </tr></thead><tbody></tbody>
      </table></div>
    </div>
  </section>

  <section class="panel" id="p-tbl">
    <div class="card">
      <div class="scroll"><table id="t-tbl">
        <thead><tr>
          <th data-s="name">Таблица</th>
          <th data-s="writes" class="num">Пишет</th>
          <th data-s="reads" class="num">Читает</th>
          <th data-s="idx" class="num">Индексов</th>
          <th data-s="flags">Флаги</th>
          <th data-s="indexes">Индексы</th>
        </tr></thead><tbody></tbody>
      </table></div>
    </div>
  </section>

  <section class="panel" id="p-sty">
    <div id="sty-body"></div>
  </section>

  <section class="panel" id="p-iss">
    <div class="note">
      Это накопленный долг — всё, что нашлось в коде на момент последней генерации.
      Новые находки появляются в отчёте <code>registry_check.py</code> как «новые».
    </div>
    <div id="iss-body"></div>
  </section>

  <section class="panel" id="p-how">
    <div class="card"><div class="body" id="how-body"></div></div>
  </section>
</main>

<script id="payload" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
const $ = (s,r=document)=>r.querySelector(s);
const $$ = (s,r=document)=>[...r.querySelectorAll(s)];
const esc = s => String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

document.getElementById('gen').textContent = DATA.generated;
document.getElementById('srcfiles').textContent = DATA.counts.components + ' .vue, ' + DATA.counts.tables + ' таблиц';

let tab='comp', query='', sortKey='path', sortDir=1;
const filters = new Set();

/* ---------- helpers ---------- */
function tags(list, cls=''){
  if(!list || !list.length) return '<span class="muted">—</span>';
  return list.map(x=>`<span class="tag ${cls}">${esc(x)}</span>`).join('');
}
function matches(hay){
  if(!query) return true;
  return String(hay).toLowerCase().includes(query);
}

/* ---------- components ---------- */
function compRow(c){
  const flags=[];
  if(c.dup_sig && c.dup_sig.length>1) flags.push('<span class="badge b-bad">дубль</span>');
  if(c.dup_markup && c.dup_markup.length) flags.push('<span class="badge b-warn">каркас</span>');
  if(!c.used_by.length) flags.push('<span class="badge b-warn">не используется</span>');
  if(!c.purpose) flags.push('<span class="badge b-neutral">нет описания</span>');
  return `<tr class="clickable" data-i="${c._i}">
    <td class="mono">${esc(c.path)}</td>
    <td>${tags(c.props)}</td>
    <td>${tags(c.models)}</td>
    <td>${tags(c.emits)}</td>
    <td>${tags(c.slots)}</td>
    <td class="num">${c.used_by.length}</td>
    <td>${flags.join(' ')||'<span class="muted">—</span>'}</td>
    <td>${esc(c.purpose||'—')}</td>
  </tr>`;
}
function compDetail(c){
  const rows=[];
  if(c.purpose) rows.push(['Назначение', esc(c.purpose)]);
  if(c.props.length) rows.push(['props', tags(c.props)]);
  if(c.models.length) rows.push(['models (v-model)', tags(c.models)]);
  if(c.emits.length) rows.push(['emits', tags(c.emits)]);
  if(c.slots.length) rows.push(['slots', tags(c.slots)]);
  rows.push(['Используют ('+c.used_by.length+')',
    c.used_by.length ? tags(c.used_by.map(x=>x.replace(/^frontend\\/src\\//,''))) : '<span class="muted">никто не импортирует</span>']);
  if(c.dup_sig && c.dup_sig.length>1)
    rows.push(['Дубль по сигнатуре', tags(c.dup_sig.filter(x=>x!==c.path.split('/').pop()&&x!==c.path))]);
  if(c.dup_markup && c.dup_markup.length)
    rows.push(['Похожий каркас (≥80%)', tags(c.dup_markup)]);
  return `<tr class="detail"><td colspan="8"><dl class="kv">${rows.map(r=>`<dt>${r[0]}</dt><dd>${r[1]}</dd>`).join('')}</dl></td></tr>`;
}

/* ---------- tables ---------- */
function tblRow(t){
  const flags=[];
  if(t.read_only) flags.push('<span class="badge b-warn">только чтение</span>');
  if(t.dup_index) flags.push('<span class="badge b-bad">дубль индекса</span>');
  return `<tr><td class="mono">${esc(t.name)}</td>
    <td class="num">${t.writes||'—'}</td><td class="num">${t.reads||'—'}</td>
    <td class="num">${t.idx_count}</td><td>${flags.join(' ')||'<span class="muted">—</span>'}</td>
    <td class="mono muted">${esc(t.indexes.join(', ')||'—')}</td></tr>`;
}

/* ---------- styles ---------- */
function stylesHtml(){
  const s=DATA.styles;
  let h='';
  h+=`<div class="card"><h2>Наши общие классы — не Bootstrap, не тема (${s.ours.length})</h2>
      <div class="body"><p class="hint">Используются в ≥8 компонентах. Кандидаты на переезд в <code>assets/css/theme/</code>.</p>
      <table><thead><tr><th>Класс</th><th class="num">Компонентов</th></tr></thead><tbody>`;
  s.ours.forEach(([k,n])=>{h+=`<tr><td class="mono">.${esc(k)}</td><td class="num">${n}</td></tr>`});
  h+=`</tbody></table></div>`;

  h+=`<div class="card"><h2>Повторяющиеся инлайны (${s.inline.length})</h2>
      <div class="body"><p class="hint"><code>AGENTS.md</code>: свой CSS — только по явному указанию. Эти значения — готовые повторы.</p>
      <table><thead><tr><th class="num">Раз</th><th>Значение</th></tr></thead><tbody>`;
  s.inline.forEach(([v,n])=>{h+=`<tr><td class="num">${n}</td><td class="mono">${esc(v)}</td></tr>`});
  h+=`</tbody></table></div>`;

  h+=`<div class="card"><h2>Пересечения с глобальным CSS (${s.collisions.length})</h2>
      <div class="body"><p class="hint">Класс определён в <code>scoped</code>-стиле компонента, но уже есть в глобальном CSS.
      <code>AGENTS.md</code>: «глобальные классы из страничного CSS не переопределять».</p>
      <table><thead><tr><th>Класс</th><th>Компоненты</th><th>Уже в</th></tr></thead><tbody>`;
  s.collisions.forEach(c=>{h+=`<tr><td class="mono">.${esc(c[0])}</td><td class="mono muted">${esc(c[1].join(', '))}</td><td class="mono muted">${esc(c[2])}</td></tr>`});
  h+=`</tbody></table></div>`;

  h+=`<div class="card"><h2>Локальные классы — используются в ≤2 компонентах (${s.local.length})</h2>
      <div class="body"><p class="hint">Кандидаты на обобщение: повторяющийся смысл, но разные имена.</p>
      <table><thead><tr><th>Класс</th><th class="num">Компонентов</th></tr></thead><tbody>`;
  s.local.forEach(([k,n])=>{h+=`<tr><td class="mono">.${esc(k)}</td><td class="num">${n}</td></tr>`});
  h+=`</tbody></table></div>`;
  return h;
}

/* ---------- issues ---------- */
function issuesHtml(){
  const g=DATA.issues;
  let h='';
  h+=`<div class="legend">`;
  Object.entries(g).forEach(([k,v])=>{
    h+=`<span><span class="badge ${v.severity}">${esc(k)}</span> ${v.items.length}</span>`;
  });
  h+=`</div>`;
  Object.entries(g).forEach(([k,v])=>{
    h+=`<div class="card"><h2>${esc(k)} — ${v.items.length}</h2><div class="body"><table><tbody>`;
    v.items.forEach(it=>{h+=`<tr><td class="mono">${esc(it)}</td></tr>`});
    h+=`</tbody></table></div></div>`;
  });
  return h;
}

/* ---------- render ---------- */
function render(){
  const q=query.toLowerCase();
  // счётчики на вкладках — всегда видны
  document.getElementById('n-comp').textContent = DATA.counts.components;
  document.getElementById('n-tbl').textContent = DATA.counts.tables;
  document.getElementById('n-sty').textContent = DATA.counts.classes;
  const totalIssues=Object.values(DATA.issues).reduce((a,v)=>a+v.items.length,0);
  document.getElementById('n-iss').textContent = totalIssues;

  if(tab==='comp'){
    let rows=DATA.components.filter(c=>{
      const hay=[c.path,c.purpose,...c.props,...c.models,...c.emits,...c.slots,...c.used_by].join(' ').toLowerCase();
      if(q && !hay.includes(q)) return false;
      if(filters.has('dup') && !(c.dup_sig&&c.dup_sig.length>1) && !(c.dup_markup&&c.dup_markup.length)) return false;
      if(filters.has('unused') && c.used_by.length) return false;
      if(filters.has('nodoc') && c.purpose) return false;
      return true;
    });
    rows.sort((a,b)=>{
      let x=a[sortKey], y=b[sortKey];
      if(Array.isArray(x)) x=x.length; if(Array.isArray(y)) y=y.length;
      if(typeof x==='string') return x.localeCompare(y,'ru')*sortDir;
      return ((x||0)-(y||0))*sortDir;
    });
    $('#t-comp tbody').innerHTML = rows.map(compRow).join('') ||
      '<tr><td colspan="8" class="empty">Ничего не найдено</td></tr>';
    document.getElementById('cnt').textContent = rows.length + ' из ' + DATA.counts.components;
  }
  if(tab==='tbl'){
    let rows=DATA.tables.filter(t=>!q || [t.name,t.indexes.join(' ')].join(' ').toLowerCase().includes(q));
    $('#t-tbl tbody').innerHTML = rows.map(tblRow).join('') ||
      '<tr><td colspan="6" class="empty">Ничего не найдено</td></tr>';
    document.getElementById('cnt').textContent = rows.length + ' из ' + DATA.counts.tables;
  }
  if(tab==='sty'){
    document.getElementById('cnt').textContent = DATA.counts.classes + ' классов, ' + DATA.counts.inline + ' инлайнов';
  }
  if(tab==='iss'){
    document.getElementById('cnt').textContent = totalIssues + ' находок';
  }
}

/* ---------- events ---------- */
$$('#tabs button').forEach(b=>b.onclick=()=>{
  tab=b.dataset.tab;
  $$('#tabs button').forEach(x=>x.classList.toggle('on',x===b));
  $$('.panel').forEach(p=>p.classList.toggle('on',p.id==='p-'+tab));
  if(tab==='sty' && !$('#sty-body').innerHTML) $('#sty-body').innerHTML = stylesHtml();
  if(tab==='iss' && !$('#iss-body').innerHTML) $('#iss-body').innerHTML = issuesHtml();
  if(tab==='how' && !$('#how-body').innerHTML) $('#how-body').innerHTML = DATA.how_html;
  render();
});
$('#q').addEventListener('input', e=>{ query=e.target.value; render(); });
document.addEventListener('keydown', e=>{
  if(e.key==='/' && document.activeElement!==$('#q')){ e.preventDefault(); $('#q').focus(); }
  if(e.key==='Escape'){ $('#q').value=''; query=''; render(); }
});
$$('.chip[data-f]').forEach(c=>c.onclick=()=>{
  const f=c.dataset.f;
  if(filters.has(f)) filters.delete(f); else filters.add(f);
  c.classList.toggle('on');
  render();
});
$$('#t-comp thead th').forEach(th=>th.onclick=()=>{
  const k=th.dataset.s;
  if(sortKey===k) sortDir*=-1; else { sortKey=k; sortDir=1; }
  render();
});
$('#t-comp tbody').addEventListener('click', e=>{
  const tr=e.target.closest('tr.clickable'); if(!tr) return;
  const next=tr.nextElementSibling;
  if(next && next.classList.contains('detail')){ next.remove(); return; }
  $$('#t-comp tbody tr.detail').forEach(x=>x.remove());
  const c=DATA.components[+tr.dataset.i];
  tr.insertAdjacentHTML('afterend', compDetail(c));
});

$('#sty-body').innerHTML = stylesHtml();
$('#iss-body').innerHTML = issuesHtml();
$('#how-body').innerHTML = DATA.how_html;
render();
</script>
</body>
</html>
"""


def build() -> None:
    if not DATA.exists():
        print("Нет docs/registry/data.json — сначала запусти registry_gen.py")
        return
    data = json.loads(read(DATA))

    known = {"known": []}
    if KNOWN.exists():
        try:
            known = json.loads(read(KNOWN))
        except Exception:
            known = {"known": []}

    issues: dict[str, dict] = {}
    for entry in known.get("known", []):
        kind, _, detail = entry.partition("|")
        sev = "b-bad"
        if kind in ("ИНЛАЙН-ПОВТОР", "БИТАЯ-ССЫЛКА", "КЛАСС-ПЕРЕСЕЧЕНИЕ"):
            sev = "b-warn"
        elif kind in ("ФИЛЬТР-ЛЕГАСИ", "ФИЛЬТР-ЛОКАЛЬНЫЙ"):
            sev = "b-info"
        issues.setdefault(kind, {"severity": sev, "items": []})["items"].append(detail)
    data["issues"] = issues

    how = data.pop("how_md", "")
    data["how_html"] = md_to_html(how)

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    OUT.write_text(HTML.replace("__DATA__", payload), encoding="utf-8")
    print(f"записан: docs/registry/index.html ({OUT.stat().st_size // 1024} КБ)")


def md_to_html(md: str) -> str:
    """Минимальный markdown → HTML: заголовки, списки, таблицы, код, жирный, ссылки."""
    import re

    out: list[str] = []
    in_table = False
    in_list = False
    in_code = False
    code: list[str] = []
    for raw in md.splitlines():
        line = raw.rstrip()

        # блок кода в тройных кавычках
        if line.strip().startswith("```"):
            if in_code:
                out.append("<pre><code>" + esc("\n".join(code)) + "</code></pre>")
                code = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code.append(raw)
            continue

        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                out.append("<table>")
                in_table = True
            out.append("<tr>" + "".join(f"<{tag}>{inline_md(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False

        if re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline_md(re.sub(r'^\s*[-*]\s+', '', line))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = m.group(1).count("#")
            out.append(f"<h{lvl}>{inline_md(m.group(2))}</h{lvl}>")
            continue
        if line.strip() == "---":
            out.append("<hr>")
            continue
        if line.startswith(">"):
            out.append(f"<blockquote>{inline_md(line.lstrip('> '))}</blockquote>")
            continue
        if not line.strip():
            continue
        out.append(f"<p>{inline_md(line)}</p>")
    if in_code:
        out.append("<pre><code>" + esc("\n".join(code)) + "</code></pre>")
    if in_table:
        out.append("</table>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def inline_md(text: str) -> str:
    import re

    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


if __name__ == "__main__":
    build()
