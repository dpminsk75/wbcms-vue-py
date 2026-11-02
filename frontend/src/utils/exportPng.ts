/**
 * Выгрузка таблицы в PNG — механика (без UI).
 *
 * Два варианта картинки:
 *   • «Снимок» — захват DOM-узла таблицы через SVG foreignObject.
 *     Выглядит ровно как на экране: тема, зебра, фото товаров.
 *   • «Карточка» — своя отрисовка на canvas из данных (spec).
 *     Читается в мессенджере: крупные цифры, мало колонок.
 *
 * Общее у обоих: шапка отчёта (название, фильтры, компания, дата) и
 * финальный Blob, который можно скачать или положить в буфер обмена.
 *
 * ЗАМЕНА БЛОКА ТАБЛИЦЫ. Перед захватом:
 *   1) `.tbl-wrap` раскрывается до scrollWidth — иначе горизонтальный
 *      скролл обрежет колонки (theme/table.css:139);
 *   2) кнопка «Увидеть ещё N» и кнопки в шапке блока не попадают
 *      в картинку: они ИСКЛЮЧАЮТСЯ ИЗ КЛОНА html-to-image (`filter`),
 *      живой DOM не трогается — кнопка остаётся на экране и показывает
 *      спиннер, пока идёт захват.
 * Ширина после захвата возвращается как была.
 */

/** Метаданные для шапки картинки. */
export type PngHeader = {
  /** Название отчёта, напр. «Сравнение по годам». */
  title: string
  /** Подзаголовок: какая вкладка/срез, напр. «Отчёт „ТОП товаров“ · вкладка „Продажи“». */
  subtitle?: string
  /** Компания — из выбранной компании в шапке приложения. */
  company?: string
  /** Дата формирования. По умолчанию — сегодня. */
  date?: string
  /** Фильтры: только значимые. Пустой массив — полосу фильтров не рисуем. */
  filters?: { label: string; value: string }[]
  /** Номер страницы пагинации — «стр. N из M». */
  page?: { current: number; total: number }
}

/** Описание колонки для карточки (вариант «Карточка»). */
export type PngCardColumn = {
  key: string
  label: string
  /** Выравнивание: текст слева, числа справа. */
  align?: 'left' | 'right' | 'center'
  /** Ширина колонки в условных единицах (доля от суммы). */
  weight?: number
}

/** Данные для карточки (вариант «Карточка»). */
export type PngCardSpec = {
  header: PngHeader
  columns: PngCardColumn[]
  /** Строки: значения по ключам колонок. */
  rows: Record<string, any>[]
  /** Итоговая строка (рисуется отдельной полосой). */
  totals?: Record<string, any>
  /** Плитки KPI над таблицей: подпись, значение, комментарий. */
  kpis?: { label: string; value: string; note?: string }[]
  /** Фото по ключу строки: { ключ строки → URL }. */
  photos?: Record<string, string>
  /** Подвал карточки (источник данных, топ-N). */
  footer?: string
}

const FONT_STACK = "'Source Sans 3', system-ui, sans-serif"

/* ------------------------------------------------------------------ утилиты */

/** Токен темы: значение CSS-переменной с корня документа. */
export function themeVar(name: string, fallback = ''): string {
  if (typeof document === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

/** Дата в формате «02.11.2026». */
export function pngDate(d = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}`
}

/**
 * Имя файла без расширения — из заголовка и «следа» таблицы.
 * «ТОП за прошлый месяц (Октябрь)» → «top-za-proshlyy-mesyats-oktyabr».
 */
export function pngFileBase(title: string): string {
  const map: Record<string, string> = {
    а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z',
    и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r',
    с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'c', ч: 'ch', ш: 'sh', щ: 'sch',
    ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
  }
  const base = title
    .toLowerCase()
    .replace(/[«»"'()]/g, ' ')
    .replace(/[^а-яёa-z0-9]+/gi, ' ')
    .trim()
    .split(/\s+/)
    .map((w) => w.split('').map((ch) => (map[ch] !== undefined ? map[ch] : ch)).join(''))
    .filter(Boolean)
    .join('-')
  return base || 'table'
}

/* ------------------------------------------------------- захват DOM (снимок) */

/**
 * Что НЕ попадает в картинку (исключается из клона html-to-image).
 *
 * Прятать эти узлы в живом DOM (`display:none` на время захвата) нельзя:
 * захват долгий (фото с CDN), и пользователь всё это время видит пропавшие
 * кнопки — «тишина». Фильтр применяется к КОПИИ узла (clone-node.js:277),
 * живой DOM остаётся видимым.
 */
const HIDE_IN_PNG: string[] = [
  '.hd-grp',             // наш блок PNG
  '.hd-btn',             // кнопка Excel и прочие .hd-btn в шапке
  '.expand-btn-wrapper', // «Увидеть ещё N»
  // тост и модалка живут в DOM внутри .card__hd — в клон не должны
  // попасть: position:fixed внутри SVG отрисовался бы поверх картинки
  '.png-toast',
  '.png-copy__backdrop',
]

/**
 * Захват DOM-узла в PNG + шапка отчёта сверху.
 *
 * @param el      узел для съёмки (обычно `.tbl-card`)
 * @param header  шапка отчёта — рисуется НАД снимком
 * @param scale   множитель резкости (2 = HiDPI)
 */
export async function captureElementPng(
  el: HTMLElement,
  header: PngHeader,
  scale = 2,
): Promise<Blob> {
  const { toCanvas } = await import('html-to-image')

  // --- временные правки блока; всё возвращается в finally ---
  const restore: (() => void)[] = []

  // 1) ширина. Горизонтальный скролл (.tbl-wrap { overflow-x: auto }) обрезает
  //    колонки, поэтому прокрутку раскрываем.
  //
  //    Ширину меряем ДО раскрытия: `width: max-content` на .tbl-wrap ищет
  //    максимальную ширину содержимого, а не текущую — таблица в 984 px
  //    растягивается до 1145 px и в PNG появляется пустое поле справа.
  //    Поэтому меряем натуральную ширину таблицы заранее и задаём её явно.
  const table = el.querySelector<HTMLElement>('table')
  const tableW = table ? Math.ceil(table.scrollWidth) : 0

  const cardPrev = { overflow: el.style.overflow }
  el.style.overflow = 'visible'
  restore.push(() => { el.style.overflow = cardPrev.overflow })

  const wrap = el.querySelector<HTMLElement>('.tbl-wrap')
  if (wrap) {
    const wrapPrev = { overflow: wrap.style.overflow, width: wrap.style.width }
    wrap.style.overflow = 'visible'
    wrap.style.width = `${tableW}px`
    restore.push(() => {
      wrap.style.overflow = wrapPrev.overflow
      wrap.style.width = wrapPrev.width
    })
  }

  if (table) {
    const prevWidth = table.style.width
    table.style.width = `${tableW}px`
    restore.push(() => { table.style.width = prevWidth })
  }

  // 2) кнопки в картинке не нужны — исключаются из КЛОНА через `filter`
  //    (см. HIDE_IN_PNG), живой DOM не трогается. Фильтр вызывается и для
  //    текстовых узлов — matches() есть только у Element.
  const hideClone = (node: Element): boolean =>
    !HIDE_IN_PNG.some((s) => node.matches(s))

  try {
    // ширина картинки: карточка по контейнеру, но если таблица шире
    // (горизонтальный скролл) — берём натуральную ширину таблицы
    const cardW = Math.ceil(el.getBoundingClientRect().width)
    const width = Math.max(cardW, tableW + 2)
    const fontCss = await embedFontsCss()

    // фото встраиваем сами (data-URL): html-to-image грузит их сам через fetch
    // и падает целиком, если хоть одна не загрузилась — одно битое фото
    // не должно убивать выгрузку
    const restoreImages = await embedImagesSafe(el)

    let tableCanvas: HTMLCanvasElement
    try {
      tableCanvas = await toCanvas(el, {
        pixelRatio: scale,
        backgroundColor: '#FFFFFF',
        fontEmbedCSS: fontCss,
        width,
        filter: (node) =>
          node instanceof Element ? hideClone(node) : true,
        style: { width: `${width}px`, margin: '0' },
      })
    } finally {
      restoreImages()
    }

    const headerNode = buildHeaderNode(header)
    headerNode.style.width = `${width}px`
    headerNode.style.minWidth = '0'
    // Шапку надо временно вставить в документ: у отсоединённого узла
    // clientHeight = 0, и html-to-image нарисует пустой холст.
    // В сторону уводим ОБЁРТКУ, а не сам узел: клон html-to-image копирует
    // только узел (без предков), и унаследовал бы смещение — картинка вышла
    // бы пустой.
    const holder = document.createElement('div')
    holder.style.cssText = 'position:fixed;left:-99999px;top:0;z-index:-1;'
    holder.appendChild(headerNode)
    document.body.appendChild(holder)
    let headerCanvas: HTMLCanvasElement
    try {
      headerCanvas = await toCanvas(headerNode, {
        pixelRatio: scale,
        backgroundColor: '#FFFFFF',
        fontEmbedCSS: fontCss,
        width,
        height: headerNode.offsetHeight,
        style: { width: `${width}px`, margin: '0' },
      })
    } finally {
      holder.remove()
    }

    return await stackCanvases(headerCanvas, tableCanvas)
  } finally {
    // --- возврат как было ---
    restore.reverse().forEach((fn) => fn())
  }
}

/**
 * Встроить фото блока как data-URL.
 *
 * Зачем своя обёртка: `html-to-image` подтягивает картинки сам через `fetch`
 * и при ошибке на любой из них отклоняет весь промис. У нас фото — с CDN WB
 * (у товара может быть битая ссылка), поэтому ронять выгрузку из-за одного
 * фото нельзя.
 *
 * @returns функция возврата исходных src.
 */
async function embedImagesSafe(el: HTMLElement): Promise<() => void> {
  const imgs = Array.from(el.querySelectorAll('img'))
  const saved: { img: HTMLImageElement; src: string }[] = []

  await Promise.all(imgs.map(async (img) => {
    const src = img.getAttribute('src') || ''
    if (!src || src.startsWith('data:')) return
    saved.push({ img, src })
    try {
      const res = await fetch(src, { mode: 'cors', credentials: 'omit' })
      if (!res.ok) throw new Error('HTTP ' + res.status)
      const blob = await res.blob()
      img.setAttribute('src', await blobToDataUrl(blob))
    } catch {
      // фото не пришло — ставим прозрачную заглушку, выгрузка продолжается
      img.setAttribute('src', BLANK_PNG)
    }
  }))

  return () => {
    saved.forEach(({ img, src }) => img.setAttribute('src', src))
  }
}

/** Прозрачная картинка 1×1 — заглушка, если фото не встроились. */
const BLANK_PNG =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='

/** Склейка двух canvas (шапка сверху, снимок снизу) в один Blob. */
async function stackCanvases(top: HTMLCanvasElement, bottom: HTMLCanvasElement): Promise<Blob> {
  const w = Math.max(top.width, bottom.width)
  const h = top.height + bottom.height
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas 2d недоступен')
  ctx.fillStyle = '#FFFFFF'
  ctx.fillRect(0, 0, w, h)
  ctx.drawImage(top, 0, 0)
  ctx.drawImage(bottom, 0, top.height)
  return await canvasToBlob(canvas)
}

/** Blob → HTMLImageElement. */
export function blobToImage(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob)
    const img = new Image()
    img.onload = () => { URL.revokeObjectURL(url); resolve(img) }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('не удалось прочитать картинку')) }
    img.src = url
  })
}

/** Canvas → Blob (PNG). */
export function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((b) => {
      if (b) resolve(b)
      else reject(new Error('не удалось сохранить canvas в PNG'))
    }, 'image/png')
  })
}

/* ------------------------------------------------------------ шапка отчёта */

/**
 * Шапка отчёта — DOM-узел (её потом рисует canvas-вариант отдельно).
 * Стили — инлайн, потому что узел живёт вне приложения.
 */
export function buildHeaderNode(header: PngHeader): HTMLElement {
  const brand = themeVar('--brand', '#283445')
  const brandDeep = themeVar('--brand-deep', '#1B2532')
  const ink = themeVar('--ink', '#111315')
  const line = themeVar('--line-strong', '#CBD0D4')
  const brandTint = themeVar('--brand-tint', '#EDF0F4')

  const root = document.createElement('div')
  root.style.cssText = `width:max-content;min-width:100%;font-family:${FONT_STACK};background:#fff;color:${ink};`

  // --- верхняя полоса: логотип, название, компания/дата ---
  const top = document.createElement('div')
  top.style.cssText = `display:flex;align-items:center;gap:14px;padding:16px 20px;background:${brand};color:#fff;`
  const logo = document.createElement('div')
  logo.textContent = 'S'
  logo.style.cssText = 'width:42px;height:42px;border-radius:10px;background:rgba(255,255,255,.16);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;flex:none;'
  const titles = document.createElement('div')
  const t = document.createElement('div')
  t.textContent = header.title
  t.style.cssText = 'font-size:18px;font-weight:700;line-height:1.2;'
  titles.appendChild(t)
  if (header.subtitle) {
    const s = document.createElement('div')
    s.textContent = header.subtitle
    s.style.cssText = 'font-size:12.5px;opacity:.85;margin-top:2px;'
    titles.appendChild(s)
  }
  const right = document.createElement('div')
  right.style.cssText = 'margin-left:auto;text-align:right;font-size:12px;opacity:.85;line-height:1.5;'
  if (header.company) {
    const c = document.createElement('div')
    c.textContent = header.company
    right.appendChild(c)
  }
  const d = document.createElement('div')
  d.textContent = header.date || pngDate()
  right.appendChild(d)
  top.appendChild(logo)
  top.appendChild(titles)
  top.appendChild(right)
  root.appendChild(top)

  // --- полоса фильтров ---
  const filters = [...(header.filters || [])]
  if (header.page) {
    filters.push({ label: 'Страница', value: `${header.page.current} из ${header.page.total}` })
  }
  if (filters.length) {
    const bar = document.createElement('div')
    bar.style.cssText = `display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:10px 20px;background:${brandTint};color:${brandDeep};border-bottom:1px solid ${line};font-size:12px;`
    filters.forEach((f, i) => {
      if (i > 0) {
        const sep = document.createElement('span')
        sep.style.cssText = 'width:1px;height:14px;background:currentColor;opacity:.25;margin:0 4px;'
        bar.appendChild(sep)
      }
      const lbl = document.createElement('b')
      lbl.textContent = `${f.label}:`
      lbl.style.fontWeight = '700'
      bar.appendChild(lbl)
      const chip = document.createElement('span')
      chip.textContent = f.value
      chip.style.cssText = `background:color-mix(in srgb, ${brand} 12%, transparent);border-radius:99px;padding:2px 9px;font-weight:600;`
      bar.appendChild(chip)
    })
    root.appendChild(bar)
  }

  return root
}

/**
 * @font-face темы — в data-URI, чтобы SVG-рендер показал наш шрифт,
 * а не системный. Берём только используемую гарнитуру (--font-ui) и её
 * сабсеты latin/cyrillic (theme/base.css).
 *
 * Вызывается дважды за выгрузку (таблица + шапка) — кэшируем промис:
 * иначе каждый раз уходят 2 запроса шрифтов + base64.
 */
let fontCssCache: Promise<string> | null = null

function embedFontsCss(): Promise<string> {
  if (!fontCssCache) fontCssCache = embedFontsCssOnce()
  return fontCssCache
}

async function embedFontsCssOnce(): Promise<string> {
  const family = themeVar('--font-ui', "'Source Sans 3'")
  const name = family.split(',')[0].trim().replace(/^['"]|['"]$/g, '')
  const files: string[] = []
  // латиница и кириллица текущей гарнитуры
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '')
  const map: Record<string, [string, string]> = {
    sourcesans3: ['source-latin.woff2', 'source-cyrillic.woff2'],
    wixmadefortext: ['wix-latin.woff2', 'wix-cyrillic.woff2'],
    manrope: ['manrope-latin.woff2', 'manrope-cyrillic.woff2'],
    onest: ['onest-latin.woff2', 'onest-cyrillic.woff2'],
    golostext: ['golos-latin.woff2', 'golos-cyrillic.woff2'],
  }
  const pair = map[slug]
  if (pair) files.push(...pair)
  if (!files.length) return ''

  const parts: string[] = []
  for (const file of files) {
    try {
      const res = await fetch(`/fonts/${file}`)
      if (!res.ok) continue
      const blob = await res.blob()
      const dataUrl = await blobToDataUrl(blob)
      // unicode-range нужен, иначе кириллица и латиница смешаются
      const range = file.includes('cyrillic')
        ? 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116'
        : 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C5,U+02C7,U+02CC-02CE,U+02D4-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD'
      parts.push(
        `@font-face{font-family:'${name}';font-style:normal;font-weight:100 900;` +
        `src:url(${dataUrl}) format('woff2');unicode-range:${range};}`,
      )
    } catch {
      /* шрифт не загрузился — подставится системный */
    }
  }
  return parts.join('\n')
}

/** Blob → data:URL. */
export function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader()
    fr.onload = () => resolve(String(fr.result))
    fr.onerror = () => reject(new Error('не удалось прочитать blob'))
    fr.readAsDataURL(blob)
  })
}

/* -------------------------------------------------- карточка (canvas) */

/**
 * Подпись изменения суммы к предыдущему году — для плиток KPI.
 *
 * Знак — как в бэкенде (`year_compare_service.py:125`):
 *   change = (cur - prev) / abs(prev) * 100
 * то есть РОСТ = плюс, падение = минус.
 *
 * @param amount     сумма за текущий год
 * @param prevAmount сумма за предыдущий год
 * @param prevLabel  подпись предыдущего года (напр. «2024»)
 */
export function kpiChangeNote(
  amount: number,
  prevAmount: number,
  prevLabel: string,
): string {
  if (!prevAmount) return 'базовый год'
  const d = Math.round(((amount - prevAmount) / Math.abs(prevAmount)) * 100)
  return `${d >= 0 ? '+' : ''}${d} % к ${prevLabel}`
}

/**
 * Карточка — своя отрисовка на canvas.
 * Крупный шрифт, минимум колонок, итоги отдельной полосой — читается в чате.
 *
 * Сейчас вариант скрыт в интерфейсе (решение 2026-11-02): движок оставлен,
 * чтобы вернуть карточку можно было без новой отрисовки с нуля.
 */
export async function renderCardPng(spec: PngCardSpec, scale = 2): Promise<Blob> {
  const h = spec.header
  const brand = themeVar('--brand', '#283445')
  const brandDeep = themeVar('--brand-deep', '#1B2532')
  const brandTint = themeVar('--brand-tint', '#EDF0F4')
  const ink = themeVar('--ink', '#111315')
  const inkMuted = themeVar('--ink-muted', '#969CA1')
  const line = themeVar('--line-strong', '#CBD0D4')

  const hasPhoto = !!spec.photos && Object.keys(spec.photos).length > 0
  const cols = spec.columns
  const weights = cols.map((c) => c.weight ?? 1)
  const totalWeight = weights.reduce((a, b) => a + b, 0)

  // ширины: фото-колонка фиксированная, остальные — по весам
  const PAD = 20
  const ROW_H = hasPhoto ? 62 : 34
  const HEAD_H = 34
  const KPI_H = spec.kpis?.length ? 74 : 0
  const PHOTO_H = 40
  const PHOTO_W = Math.round((PHOTO_H * 516) / 688)
  const photoColW = hasPhoto ? PHOTO_W + 10 : 0

  // считаем ширину по содержимому
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas 2d недоступен')

  const font = (size: number, weight = 400) => `${weight} ${size}px ${FONT_STACK}`
  const measure = (text: string, size: number, weight = 400) => {
    ctx.font = font(size, weight)
    return ctx.measureText(text).width
  }

  // Ширины колонок — в пикселях. Сначала по весам (доля от полезной ширины),
  // потом расширяем те, где текст не влезает: иначе колонки наезжают.
  const MIN_COL = 96
  const TITLE_MAX = 460
  const PAD_R = 10   // отступ справа у колонки
  const PAD_L = 8    // отступ слева у колонки

  // Ширина текстовой колонки — по самому длинному значению (и заголовку).
  // Ширину «по весу» НЕ оставляем: текстовая колонка иначе получает
  // свободное место и в картинке появляется пустая полоса.
  // В колонке 0 может быть фото — тогда она занимает фото + текст.
  let titleTextW = 0
  spec.rows.forEach((r) => {
    const t = String(r[cols[0]?.key] ?? '')
    const w = measure(t, 13, 600)
    if (w > titleTextW) titleTextW = w
  })
  if (cols.length) {
    const headW = measure(cols[0].label, 11.5, 700)
    titleTextW = Math.max(titleTextW, headW)
  }
  const titleW = Math.min(TITLE_MAX, Math.ceil(titleTextW) + PAD_L + PAD_R)

  const colWidths = cols.map((c, i) => {
    if (i === 0) return hasPhoto ? photoColW + titleW : titleW
    return Math.max(MIN_COL, Math.round((weights[i] / totalWeight) * 900))
  })

  // числовые колонки — по самому широкому значению
  cols.forEach((c, i) => {
    if (i === 0) return
    let longest = measure(c.label, 11.5, 700)
    spec.rows.forEach((r) => {
      const t = String(r[c.key] ?? '—')
      const w = measure(t, 13)
      if (w > longest) longest = w
    })
    colWidths[i] = Math.max(colWidths[i], Math.ceil(longest) + PAD_R + 12)
  })

  const contentW = colWidths.reduce((a, b) => a + b, 0)
  const W = Math.max(720, Math.ceil(contentW + PAD * 2))
  const rowsH = spec.rows.length * ROW_H
  const totalsH = spec.totals ? 38 : 0
  const headerH = 74
  const filters = [...(h.filters || [])]
  if (h.page) filters.push({ label: 'Страница', value: `${h.page.current} из ${h.page.total}` })
  const filtersH = filters.length ? 40 : 0
  const footerH = spec.footer ? 34 : 0
  const H = headerH + filtersH + KPI_H + HEAD_H + rowsH + totalsH + footerH

  canvas.width = W * scale
  canvas.height = H * scale
  ctx.scale(scale, scale)
  ctx.fillStyle = '#FFFFFF'
  ctx.fillRect(0, 0, W, H)
  ctx.textBaseline = 'middle'

  let y = 0

  // --- шапка ---
  ctx.fillStyle = brand
  ctx.fillRect(0, 0, W, headerH)
  ctx.fillStyle = 'rgba(255,255,255,.16)'
  roundRect(ctx, PAD, y + 16, 42, 42, 10)
  ctx.fill()
  ctx.fillStyle = '#FFFFFF'
  ctx.font = font(16, 700)
  ctx.textAlign = 'center'
  ctx.fillText('S', PAD + 21, y + 37)
  ctx.textAlign = 'left'
  ctx.font = font(18, 700)
  ctx.fillText(h.title, PAD + 58, y + 30)
  if (h.subtitle) {
    ctx.font = font(12.5)
    ctx.globalAlpha = .85
    ctx.fillText(h.subtitle, PAD + 58, y + 50)
    ctx.globalAlpha = 1
  }
  // компания и дата — справа
  ctx.textAlign = 'right'
  ctx.font = font(12)
  ctx.globalAlpha = .85
  const rightX = W - PAD
  if (h.company) ctx.fillText(h.company, rightX, y + 30)
  ctx.fillText(h.date || pngDate(), rightX, y + 48)
  ctx.globalAlpha = 1
  ctx.textAlign = 'left'
  y += headerH

  // --- фильтры ---
  if (filters.length) {
    ctx.fillStyle = brandTint
    ctx.fillRect(0, y, W, filtersH)
    let fx = PAD
    filters.forEach((f, i) => {
      if (i > 0) {
        ctx.fillStyle = brandDeep
        ctx.globalAlpha = .25
        ctx.fillRect(fx + 4, y + 13, 1, 14)
        ctx.globalAlpha = 1
        fx += 13
      }
      ctx.fillStyle = brandDeep
      ctx.font = font(12, 700)
      ctx.fillText(`${f.label}:`, fx, y + filtersH / 2)
      fx += ctx.measureText(`${f.label}: `).width
      const vw = measure(f.value, 12, 600)
      ctx.fillStyle = brandTint
      roundRect(ctx, fx, y + 10, vw + 18, 20, 10)
      ctx.fill()
      ctx.fillStyle = brandDeep
      ctx.font = font(12, 600)
      ctx.fillText(f.value, fx + 9, y + filtersH / 2)
      fx += vw + 18 + 6
    })
    ctx.fillStyle = line
    ctx.fillRect(0, y + filtersH - 1, W, 1)
    y += filtersH
  }

  // --- KPI ---
  if (spec.kpis?.length) {
    const kw = (W - PAD * 2 - (spec.kpis.length - 1) * 10) / spec.kpis.length
    spec.kpis.forEach((k, i) => {
      const kx = PAD + i * (kw + 10)
      ctx.fillStyle = brandTint
      roundRect(ctx, kx, y + 10, kw, KPI_H - 22, 10)
      ctx.fill()
      ctx.fillStyle = inkMuted
      ctx.font = font(11.5)
      ctx.fillText(k.label, kx + 12, y + 28)
      ctx.fillStyle = brandDeep
      ctx.font = font(19, 700)
      ctx.fillText(k.value, kx + 12, y + 50)
      if (k.note) {
        ctx.fillStyle = inkMuted
        ctx.font = font(11.5)
        ctx.fillText(k.note, kx + 12, y + 66)
      }
    })
    y += KPI_H
  }

  // --- заголовок колонок ---
  let x = PAD
  cols.forEach((c, i) => {
    const cw = colWidths[i]
    const align = c.align ?? 'right'
    const hasPh = i === 0 && hasPhoto
    ctx.fillStyle = ink
    ctx.font = font(11.5, 700)
    ctx.textAlign = align === 'left' ? 'left' : align === 'center' ? 'center' : 'right'
    const tx = hasPh
      ? x + photoColW
      : align === 'left' ? x + PAD_L : align === 'center' ? x + cw / 2 : x + cw - PAD_R
    const maxW = cw - (hasPh ? photoColW : 0) - PAD_L - PAD_R
    ctx.fillText(fitText(ctx, c.label, maxW, font(11.5, 700)), tx, y + HEAD_H / 2)
    x += cw
  })
  ctx.textAlign = 'left'
  ctx.fillStyle = line
  ctx.fillRect(PAD, y + HEAD_H - 1, contentW, 1)
  y += HEAD_H

  // --- строки ---
  // photos: ключ строки → URL; photosMap: ключ строки → загруженная картинка
  const photoUrls = spec.photos || {}
  const photosMap = await loadPhotos(photoUrls)
  spec.rows.forEach((row, ri) => {
    const ry = y + ri * ROW_H
    if (ri % 2 === 1) {
      ctx.fillStyle = 'rgba(17,19,21,.04)'
      ctx.fillRect(PAD - 8, ry, contentW + 16, ROW_H)
    }
    let cx = PAD
    cols.forEach((c, ci) => {
      const cw = colWidths[ci]
      const raw = row[c.key]
      const text = raw === null || raw === undefined ? '—' : String(raw)
      const align = c.align ?? 'right'
      if (ci === 0 && hasPhoto) {
        // колонка 0: фото слева, текст справа от него
        const rowKey = row.__key ?? String(ri)
        const img = photosMap[rowKey]
        if (img) {
          drawImageCover(ctx, img, cx, ry + (ROW_H - PHOTO_H) / 2, PHOTO_W, PHOTO_H)
        }
        ctx.fillStyle = ink
        ctx.font = font(13, 600)
        ctx.textAlign = 'left'
        ctx.fillText(
          fitText(ctx, text, cw - photoColW - PAD_L - PAD_R, font(13, 600)),
          cx + photoColW, ry + ROW_H / 2,
        )
      } else {
        ctx.fillStyle = ink
        ctx.font = font(13)
        // позиция по выравниванию: left — от левого края колонки,
        // right — от правого (иначе текст уезжает в пустую полосу)
        ctx.textAlign = align === 'left' ? 'left' : align === 'center' ? 'center' : 'right'
        const px = align === 'left'
          ? cx + PAD_L
          : align === 'center' ? cx + cw / 2 : cx + cw - PAD_R
        ctx.fillText(fitText(ctx, text, cw - PAD_L - PAD_R, font(13)), px, ry + ROW_H / 2)
        ctx.textAlign = 'left'
      }
      cx += cw
    })
  })
  y += rowsH

  // --- итоги ---
  if (spec.totals) {
    ctx.fillStyle = brandTint
    ctx.fillRect(PAD - 8, y, contentW + 16, totalsH)
    ctx.fillStyle = brandDeep
    ctx.font = font(13, 700)
    let tx = PAD
    cols.forEach((c, ci) => {
      const cw = colWidths[ci]
      const raw = spec.totals?.[c.key]
      const text = raw === null || raw === undefined ? '—' : String(raw)
      const align = c.align ?? 'right'
      ctx.textAlign = align === 'left' ? 'left' : align === 'center' ? 'center' : 'right'
      const hasPh = ci === 0 && hasPhoto
      const maxW = cw - (hasPh ? photoColW : 0) - PAD_L - PAD_R
      const px = hasPh
        ? tx + photoColW
        : align === 'left' ? tx + PAD_L : align === 'center' ? tx + cw / 2 : tx + cw - PAD_R
      ctx.fillText(fitText(ctx, text, maxW, font(13, 700)), px, y + totalsH / 2)
      tx += cw
    })
    ctx.textAlign = 'left'
    y += totalsH
  }

  // --- подвал ---
  if (spec.footer) {
    ctx.fillStyle = inkMuted
    ctx.font = font(11.5)
    ctx.fillText(spec.footer, PAD, y + footerH / 2)
  }

  return await canvasToBlob(canvas)
}

/** Загрузить фото (с CORS — CDN WB отдаёт `access-control-allow-origin: *`). */
async function loadPhotos(map: Record<string, string>): Promise<Record<string, HTMLImageElement>> {
  const out: Record<string, HTMLImageElement> = {}
  await Promise.all(Object.entries(map).map(async ([key, url]) => {
    if (!url) return
    await new Promise<void>((resolve) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => { out[key] = img; resolve() }
      img.onerror = () => resolve()
      img.src = url
    })
  }))
  return out
}

/** Нарисовать фото с обрезкой по центру (как object-fit: cover). */
function drawImageCover(ctx: CanvasRenderingContext2D, img: HTMLImageElement, x: number, y: number, w: number, h: number) {
  const sr = img.width / img.height
  const dr = w / h
  let sw = img.width
  let sh = img.height
  let sx = 0
  let sy = 0
  if (sr > dr) { sw = img.height * dr; sx = (img.width - sw) / 2 }
  else { sh = img.width / dr; sy = (img.height - sh) / 2 }
  ctx.save()
  ctx.beginPath()
  roundRect(ctx, x, y, w, h, 4)
  ctx.clip()
  ctx.drawImage(img, sx, sy, sw, sh, x, y, w, h)
  ctx.restore()
}

/**
 * Обрезать текст по ширине с многоточием.
 * `ctx.font` должен быть уже установлен на нужный.
 */
function fitText(ctx: CanvasRenderingContext2D, text: string, maxW: number, fontStr: string): string {
  if (maxW <= 10) return ''
  if (ctx.measureText(text).width <= maxW) return text
  const prev = ctx.font
  ctx.font = fontStr
  let lo = 0
  let hi = text.length
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2)
    const s = text.slice(0, mid) + '…'
    if (ctx.measureText(s).width <= maxW) lo = mid
    else hi = mid - 1
  }
  ctx.font = prev
  return lo > 0 ? text.slice(0, lo) + '…' : ''
}

/** Прямоугольник со скруглением. */
function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {  const rr = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + rr, y)
  ctx.lineTo(x + w - rr, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr)
  ctx.lineTo(x + w, y + h - rr)
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h)
  ctx.lineTo(x + rr, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr)
  ctx.lineTo(x, y + rr)
  ctx.quadraticCurveTo(x, y, x + rr, y)
  ctx.closePath()
}

/* ------------------------------------------------- сохранение и копирование */

/** Скачать blob как файл. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/**
 * Положить картинку в буфер обмена.
 * @returns true — скопировано; false — браузер не умеет (нужна модалка).
 */
export async function copyBlobToClipboard(blob: Blob): Promise<boolean> {
  if (!canCopyImages()) return false
  try {
    const item = new ClipboardItem({ 'image/png': blob })
    await navigator.clipboard.write([item])
    return true
  } catch {
    return false
  }
}

/**
 * Может ли браузер писать картинку в буфер.
 * Нужен secure context (https/localhost) + Clipboard API + ClipboardItem.
 * Firefox и Safari картинку не пишут — там всегда модалка.
 */
export function canCopyImages(): boolean {
  if (typeof window === 'undefined') return false
  if (!window.isSecureContext) return false
  if (!navigator.clipboard?.write) return false
  if (typeof ClipboardItem === 'undefined') return false
  return true
}
