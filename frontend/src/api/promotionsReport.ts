/**
 * Разбор отчёта WB «Товары для исключения из акции» (выгрузка ЛК WB).
 *
 * Файл приходит из личного кабинета WB: лист «Отчёт по скидкам», 21 колонка.
 * По каждому товару WB отдаёт плановую цену акции, минимальную цену для
 * применения скидки, блокировку, статус участия и скидку, которую надо
 * загрузить. Для автоакций это источник правды: метод номенклатуры WB их не
 * отдаёт (422).
 *
 * Модуль без других импортов — его можно проверять скриптом на живых файлах.
 */

/**
 * Названия колонок файла WB «Товары для исключения из акции» (лист «Отчёт по
 * скидкам»), в порядке исходного файла. Это и есть форма шаблона: пустой
 * Excel с этими заголовками — «Скачать шаблон».
 */
export const WB_REPORT_HEADERS = [
  'Товар уже участвует в акции',
  'Бренд',
  'Предмет',
  'Наименование',
  'Артикул поставщика',
  'Артикул WB',
  'Последний баркод',
  'Количество дней на сайте',
  'Оборачиваемость',
  'Остаток товара на складах Wb (шт.)',
  'Остаток товара на складе продавца Wb (шт.)',
  'Плановая цена для акции',
  'Текущая розничная цена',
  'Валюта',
  'Минимальная цена для применения скидки по автоакции',
  'Минимальная цена: осталось дней',
  'Блокировка применения скидки по автоакции',
  'Блокировка изменения скидки для участия в автоакции: осталось дней',
  'Текущая скидка на сайте, %',
  'Загружаемая скидка для участия в акции',
  'Статус',
]

/** Строка отчёта WB, приведённая к полям расчёта маржи. */
export interface PromoReportItem {
  nm_id: number
  in_action: boolean
  vendor_code: string
  barcode: string
  title: string
  brand: string
  subject: string
  /** Текущая розничная цена, ₽. */
  price: number | null
  /** Плановая цена для акции, ₽. */
  plan_price: number | null
  /** Текущая скидка на сайте, %. */
  discount: number | null
  /** Загружаемая скидка для участия в акции, %. */
  plan_discount: number | null
  /** Минимальная цена для применения скидки по автоакции, ₽. */
  min_price: number | null
  /** Стоит блокировка применения скидки по автоакции. */
  blocked: boolean
  /** Статус участия из отчёта WB. */
  status: string
  turnover_days: number | null
  stock_wb: number | null
  stock_fbs: number | null
  currency_code: string
}

/** Нормализация заголовка: без пробелов, регистра и знаков. */
function normHead(v: unknown): string {
  return String(v ?? '')
    .toLowerCase()
    .replace(/[^a-zа-я0-9]+/gi, '')
    .trim()
}

/** Число из ячейки: «1 234,56», «1234.56», 1234.56. */
function num(v: unknown): number | null {
  if (v == null || v === '') return null
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  const s = String(v).replace(/\s/g, '').replace(',', '.').replace('%', '').trim()
  if (!s) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

/** «Да»/«Нет»/истина → boolean. */
function bool(v: unknown): boolean {
  const s = String(v ?? '').trim().toLowerCase()
  return s === 'да' || s === 'true' || s === '1' || s === 'yes'
}

/**
 * Разобрать xlsx-отчёт WB.
 * Бросает Error с понятным текстом, если файл не тот.
 */
export async function parseWbPromoReport(file: File | ArrayBuffer): Promise<PromoReportItem[]> {
  const XLSX = await import('xlsx')
  const buf = file instanceof ArrayBuffer ? file : await file.arrayBuffer()
  const wb = XLSX.read(buf, { type: 'array' })
  const sheetName = wb.SheetNames[0]
  if (!sheetName) throw new Error('В файле нет листов')
  const ws = wb.Sheets[sheetName]
  const matrix = XLSX.utils.sheet_to_json<any[]>(ws, { header: 1, raw: true, defval: '' })
  if (!matrix.length) throw new Error('Файл пустой')

  const head = (matrix[0] || []).map(normHead)
  const idx = (names: string[]): number => {
    for (const n of names) {
      const key = normHead(n)
      const i = head.findIndex(h => h === key || (key.length > 6 && h.startsWith(key)))
      if (i >= 0) return i
    }
    return -1
  }
  const cNm = idx(['Артикул WB'])
  if (cNm < 0) throw new Error('В отчёте нет колонки «Артикул WB»')

  const c = {
    inAction: idx(['Товар уже участвует в акции']),
    brand: idx(['Бренд']),
    subject: idx(['Предмет', 'Категория']),
    title: idx(['Наименование', 'Название']),
    vendor: idx(['Артикул поставщика']),
    barcode: idx(['Последний баркод', 'Баркод']),
    turnover: idx(['Оборачиваемость']),
    stockWb: idx(['Остаток товара на складах Wb', 'Остатки WB']),
    stockFbs: idx(['Остаток товара на складе продавца Wb', 'Остатки продавца']),
    planPrice: idx(['Плановая цена для акции']),
    price: idx(['Текущая розничная цена']),
    currency: idx(['Валюта']),
    minPrice: idx(['Минимальная цена для применения скидки по автоакции']),
    blocked: idx(['Блокировка применения скидки по автоакции']),
    discount: idx(['Текущая скидка на сайте']),
    planDiscount: idx(['Загружаемая скидка для участия в акции']),
    status: idx(['Статус']),
  }
  const cell = (row: any[], i: number): any => (i >= 0 ? row[i] : '')

  const out: PromoReportItem[] = []
  for (let r = 1; r < matrix.length; r++) {
    const row = matrix[r] || []
    const nm = num(cell(row, cNm))
    if (!nm) continue
    out.push({
      nm_id: nm,
      in_action: bool(cell(row, c.inAction)),
      vendor_code: String(cell(row, c.vendor) ?? ''),
      barcode: String(cell(row, c.barcode) ?? ''),
      title: String(cell(row, c.title) ?? ''),
      brand: String(cell(row, c.brand) ?? ''),
      subject: String(cell(row, c.subject) ?? ''),
      price: num(cell(row, c.price)),
      plan_price: num(cell(row, c.planPrice)),
      discount: num(cell(row, c.discount)),
      plan_discount: num(cell(row, c.planDiscount)),
      min_price: num(cell(row, c.minPrice)),
      blocked: bool(cell(row, c.blocked)),
      status: String(cell(row, c.status) ?? '').trim(),
      turnover_days: num(cell(row, c.turnover)),
      stock_wb: num(cell(row, c.stockWb)),
      stock_fbs: num(cell(row, c.stockFbs)),
      currency_code: String(cell(row, c.currency) ?? '') || 'RUB',
    })
  }
  if (!out.length) throw new Error('В отчёте не нашлось товаров')
  return out
}
