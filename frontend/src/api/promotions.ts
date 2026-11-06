import { api } from './client'
import { exportXlsx } from '@/utils/exportXlsx'

/** Акция в календаре WB (из кэша /api/promotions). */
export interface PromoRow {
  promo_id: number
  name: string
  promo_type: string
  start_dt: string | null
  end_dt: string | null
  start_date: string
  end_date: string
  description: string | null
  advantages: string[] | null
  in_promo_leftovers: number | null
  in_promo_total: number | null
  not_in_promo_leftovers: number | null
  not_in_promo_total: number | null
  participation_percentage: number | null
  ranging: any[] | null
  fetched_at: string | null
}

/**
 * Состояние акции по датам: «Анонс» (ещё не началась) / «Идёт» / «Завершилась».
 * Общий расчёт для календаря и таблицы — раньше он был продублирован в двух
 * компонентах, и «Тип»/«Статус» в таблице показывали одно и то же.
 */
export type PromoStatus = 'announce' | 'active' | 'finished'

/** Разбор даты «YYYY-MM-DD» в локальную дату (без сдвига по UTC). */
export function promoDate(v: string | null | undefined): Date | null {
  const a = String(v || '').slice(0, 10).split('-').map(Number)
  if (a.length !== 3 || !a[0]) return null
  return new Date(a[0], (a[1] || 1) - 1, a[2] || 1)
}

function promoToday(): Date {
  const n = new Date()
  return new Date(n.getFullYear(), n.getMonth(), n.getDate())
}

export function promoStatus(p: { start_date?: string | null; end_date?: string | null }): PromoStatus {
  const today = promoToday().getTime()
  const s = promoDate(p.start_date)
  const e = promoDate(p.end_date)
  if (s && s.getTime() > today) return 'announce'
  if (e && e.getTime() < today) return 'finished'
  return 'active'
}

export function promoStatusLabel(p: { start_date?: string | null; end_date?: string | null }): string {
  const s = promoStatus(p)
  if (s === 'announce') return 'Анонс'
  if (s === 'finished') return 'Завершилась'
  return 'Идёт'
}

/** Вид акции: регулярная или автоакция WB. */
export function promoTypeLabel(p: { promo_type?: string | null }): string {
  return (p.promo_type || '') === 'auto' ? 'Автоакция' : 'Акция'
}

/** Товар акции (номенклатура). */
export interface PromoProductRow {  nm_id: number
  in_action: number | boolean
  price: number | null
  plan_price: number | null
  currency_code: string | null
  discount: number | null
  plan_discount: number | null
}

/** Параметры расчёта маржи. */
export interface PromoCalcParams {
  /** Окно истории: даты (если заданы) либо последние N дней. */
  date_from: string
  date_to: string
  /** Длина окна в днях: по датам или фолбэк 30 — в панели не задаётся. */
  days: number
  /** «Мин. маржа, ₽»: маржа на цене акции должна быть строго больше порога.
   *  Может быть отрицательной (например −10 ₽). */
  min_margin_rub: number
  /** «Падение маржи, %»: маржа на цене акции может стать хуже текущей не более чем на столько %. */
  max_drop_pct: number
  /** «Падение маржи, ₽»: на сколько ₽/шт маржа может стать хуже текущей. */
  max_drop_rub: number
  /** «Учитывать: только Мин маржа» — в вердикте проверяется только порог
   *  «Мин. маржа, ₽», остальные не применяются. */
  only_min_margin: boolean
  min_stock_wb: number
  include_reviews: boolean
  include_adv: boolean
  include_cashback: boolean
  include_penalties: boolean
  tax_rate: number
  /** Уровень скидки автоакции, % (через API не отдаётся — задаётся вручную). */
  auto_discount: number
  /** Фильтр по товару: nmID или маска. */
  nm_id: string
}

/** Структура экономики на единицу товара (все суммы — ₽ на штуку). */
export interface PromoUnit {
  revenue: number | null
  commission: number | null
  acquiring: number | null
  acceptance: number | null
  delivery: number | null
  storage: number | null
  penalty: number | null
  deduction: number | null
  cashback: number | null
  nds: number | null
  cost: number | null
  reviews: number | null
  adv: number | null
  storage_paid: number | null
  net_profit: number | null
  profit_before_tax: number | null
  tax: number | null
  margin_rub: number | null
  margin_pct: number | null
}

/** Строка результата подбора. */
export interface PromoAnalysisRow {
  nm_id: number
  in_action: boolean
  title: string | null
  vendor_code: string | null
  brand: string | null
  subject: string | null
  photos: string | null
  barcodes: string
  stock_wb: number
  stock_fbs: number
  sold_qty: number
  speed: number
  turnover_days: number | null
  /** Розничная цена (карточка WB). */
  price: number | null
  discount: number
  price_now: number | null
  /** Розничная цена из кэша цен WB (wb_price_history.price). */
  wb_price: number | null
  /** Цена со скидкой из кэша цен WB (wb_price_history.discounted_price). */
  wb_price_discounted: number | null
  /** Текущая скидка WB из кэша цен. */
  wb_discount: number | null
  /** Цена продажи из куба (amount / количество продаж) — на ней «Маржа тек.». */
  price_cube: number | null
  plan_price: number | null
  plan_discount: number
  price_new: number | null
  price_mismatch: boolean
  /** Юнит-экономика собрана по аналогам (товар без продаж в окне). */
  est_analog: boolean
  /** Минимальная цена, при которой маржа держится порога (шаблон WB). */
  min_price: number | null
  /** Экономика на единицу при цене акции. */
  unit: PromoUnit
  /** Экономика на единицу при текущей цене. */
  unit_now: PromoUnit
  margin_now_rub: number | null
  margin_now_pct: number | null
  margin_new_pct: number | null
  margin_new_rub: number | null
  /** Изменение маржи: % (по формуле (новое − старое) ÷ старое) и ₽. */
  margin_change_pct: number | null
  margin_change_rub: number | null
  recommend: boolean
  reason: string
  selected: boolean
  manual: boolean
}

export interface PromoDecision {
  nm_id: number
  selected: boolean
  manual: boolean
}

export const DEFAULT_CALC_PARAMS: PromoCalcParams = {
  date_from: '',
  date_to: '',
  days: 30,
  min_margin_rub: 0,
  max_drop_pct: 10,
  max_drop_rub: 5,
  only_min_margin: false,
  min_stock_wb: 0,
  include_reviews: false,
  include_adv: false,
  include_cashback: false,
  include_penalties: false,
  tax_rate: 0.07,
  auto_discount: 30,
  nm_id: '',
}

// ---------------------------------------------------------------- отчёт WB

/** Разбор отчёта WB — в отдельном модуле (без импортов, его можно проверять скриптом). */
import { WB_REPORT_HEADERS } from './promotionsReport'

export type { PromoReportItem } from './promotionsReport'
export { parseWbPromoReport, WB_REPORT_HEADERS } from './promotionsReport'

/**
 * Шаблон WB «Товары для исключения из акции» — пустой файл: только названия
 * колонок. Пользователь заполняет список товаров и загружает обратно через
 * «Загрузить из шаблона».
 */
export async function exportPromoTemplate(filename: string) {
  const XLSX = await import('xlsx')
  // одна строка — названия колонок; данных нет
  const ws = XLSX.utils.aoa_to_sheet([WB_REPORT_HEADERS])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Отчёт по скидкам')
  XLSX.writeFile(wb, filename)
}

/**
 * Выгрузка в формате WB «Отчет - цены и скидки на товары» —
 * файл для передачи товаров в WB (загрузка цен и скидок).
 *
 * Новая цена — цена в акции (или минимум WB, если он выше текущей),
 * новая скидка — скидка, нужная для участия, «Цена со скидкой» — итог.
 */
export async function exportPromoWbPrices(rows: PromoAnalysisRow[], filename: string) {
  if (!rows.length) return
  const data = rows.map(r => {
    const price = r.price ?? 0
    const minPrice = r.min_price ?? 0
    const newPrice = minPrice > price ? minPrice : price
    const discount = r.plan_discount ?? r.discount ?? 0
    const withDiscount = Math.round(newPrice * (1 - discount / 100) * 100) / 100
    return {
      'Бренд': r.brand || '',
      'Категория': r.subject || '',
      'Артикул WB': r.nm_id,
      'Артикул продавца': r.vendor_code || '',
      'Последний баркод': (r.barcodes || '').split(',')[0].trim(),
      'Остатки WB': r.stock_wb ?? '',
      'Остатки продавца': r.stock_fbs ?? '',
      'Оборачиваемость': r.turnover_days ?? '',
      'Текущая цена': price || '',
      'Новая цена, RUB': newPrice || '',
      'Текущая скидка': r.discount ?? '',
      'Новая скидка': discount,
      'Цена со скидкой': withDiscount,
      'Наличие ошибки': '',
    }
  })
  await exportXlsx({
    rows: data,
    filename,
    sheetName: 'Отчет - цены и скидки на товары',
    cols: [{ wch: 18 }, { wch: 16 }, { wch: 12 }, { wch: 24 }, { wch: 16 },
      { wch: 10 }, { wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 12 },
      { wch: 10 }, { wch: 10 }, { wch: 14 }, { wch: 14 }],
  })
}

/** Список для исключения — файл в форме отчёта WB («Отчёт по скидкам»):
 * загружается в ЛК, чтобы исключить товары из автоакции. */
export async function exportPromoExclude(rows: PromoAnalysisRow[], filename: string) {
  if (!rows.length) return
  const XLSX = await import('xlsx')
  const data = rows.map(r => [
    r.in_action ? 'Да' : 'Нет',
    r.brand || '',
    r.subject || '',
    r.title || '',
    r.vendor_code || '',
    r.nm_id,
    (r.barcodes || '').split(',')[0].trim(),
    '',
    r.turnover_days ?? '',
    r.stock_wb ?? '',
    r.stock_fbs ?? '',
    r.price_new ?? '',
    r.price ?? '',
    'RUB',
    r.min_price ?? '',
    '',
    '',
    '',
    r.discount ?? '',
    r.plan_discount ?? '',
    r.reason || '',
  ])
  const ws = XLSX.utils.aoa_to_sheet([WB_REPORT_HEADERS, ...data])
  ws['!cols'] = [
    { wch: 12 }, { wch: 16 }, { wch: 16 }, { wch: 34 }, { wch: 20 }, { wch: 12 },
    { wch: 16 }, { wch: 10 }, { wch: 10 }, { wch: 10 }, { wch: 10 }, { wch: 12 },
    { wch: 12 }, { wch: 8 }, { wch: 16 }, { wch: 10 }, { wch: 12 }, { wch: 12 },
    { wch: 10 }, { wch: 12 }, { wch: 24 },
  ]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Отчёт по скидкам')
  XLSX.writeFile(wb, filename)
}

export const promotionsApi = {
  /** Календарь акций из кэша; refresh=1 — перезабрать из WB. */
  calendar(params: { date_from?: string; date_to?: string; refresh?: number }) {
    return api.get('/api/promotions/calendar', { params }).then(r => r.data as {
      date_from: string
      date_to: string
      rows: PromoRow[]
      count: number
      sync: Record<string, any>
    })
  },

  /** Детали одной акции. */
  promo(promoId: number, refresh?: number) {
    return api.get(`/api/promotions/${promoId}`, { params: { refresh } }).then(r => r.data as PromoRow)
  },

  /** Номенклатура акции (из кэша; refresh=1 — из WB). */
  products(promoId: number, params?: { in_action?: number; refresh?: number }) {
    return api.get(`/api/promotions/${promoId}/products`, { params }).then(r => r.data as {
      promo_id: number
      promo: PromoRow | null
      rows: PromoProductRow[]
      count: number
      is_auto: boolean
    })
  },

  /** Загрузить отчёт WB (выгрузка ЛК «Товары для исключения из акции»). */
  saveReport(promoId: number, items: PromoReportItem[]) {
    return api.post(`/api/promotions/${promoId}/report`, { items }).then(r => r.data as {
      promo_id: number
      saved: number
      count: number
      loaded_at: string | null
    })
  },

  /** Превью загрузки отчёта — dry-run, без записи. */
  previewReport(promoId: number, items: PromoReportItem[]) {
    return api.post(`/api/promotions/${promoId}/report/preview`, { items }).then(r => r.data as {
      promo_id: number
      total: number
      known: number
      unknown: number[]
      unknown_count: number
      new_count: number
      changed_count: number
      changed: { nm_id: number; fields: string[] }[]
      in_action: number
    })
  },

  /** Расчёт маржи на новой цене + вердикт. */
  analyze(promoId: number, params: PromoCalcParams, rows?: PromoProductRow[]) {
    return api.post(`/api/promotions/${promoId}/analyze`, { params, rows }).then(r => r.data as {
      rows: PromoAnalysisRow[]
      params: PromoCalcParams
      window: { date_from: string; date_to: string; days: number }
      summary: { total: number; recommend: number; reject: number; selected: number }
    })
  },

  /** Пометки пользователя по акции. */
  decisions(promoId: number) {
    return api.get(`/api/promotions/${promoId}/decisions`).then(r => r.data as {
      promo_id: number
      rows: PromoDecision[]
    })
  },

  /** Сохранить пометки. */
  saveDecisions(promoId: number, items: { nm_id: number; selected: boolean }[]) {
    return api.post(`/api/promotions/${promoId}/decisions`, { items }).then(r => r.data as {
      promo_id: number
      saved: number
    })
  },

  /** Добавить номенклатуру в акцию (только регулярные акции). */
  upload(promoId: number, nmIds: number[]) {
    return api.post(`/api/promotions/${promoId}/upload`, { nm_ids: nmIds }).then(r => r.data as {
      promo_id: number
      uploaded: number
      wb: Record<string, any>
    })
  },

  /** Подготовка загрузки цен и скидок (автоакции): позиции + риски карантина. */
  preparePrices(promoId: number, rows: PromoAnalysisRow[]) {
    return api.post(`/api/promotions/${promoId}/prices/prepare`, { rows }).then(r => r.data as {
      items: { nm_id: number; title: string; vendor_code: string; price: number; discount: number; new_discounted: number; old_discounted: number | null; risky: boolean; blocked?: boolean }[]
      risky: { nm_id: number; title: string; new_discounted: number; old_discounted: number | null; risky: boolean; blocked?: boolean }[]
      prices_source: string
    })
  },

  /** Загрузить цены и скидки в WB (автоакции; загрузка асинхронная). */
  uploadPrices(promoId: number, rows: PromoAnalysisRow[], withRisky: boolean) {
    return api.post(`/api/promotions/${promoId}/prices/upload`, {
      rows, with_risky: withRisky,
    }).then(r => r.data as {
      promo_id: number
      sent: number
      tasks: { id: number | null; count: number; already_exists: boolean }[]
      skipped_risky: number
    })
  },

  /** Товары в карантине цен WB. */
  quarantine() {
    return api.get('/api/promotions/quarantine').then(r => r.data as {
      rows: { nm_id: number; old_price: number; new_price: number; old_discount: number; new_discount: number; price_diff: number }[]
      count: number
    })
  },
}

const money = (v: number | null | undefined) =>
  v == null ? '' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(v)

/** Выгрузка нашей таблицы подбора (те же колонки, что на экране). */
export async function exportPromoRows(rows: PromoAnalysisRow[], filename: string) {
  if (!rows.length) return
  const data = rows.map(r => ({
    'Товар': r.title || '',
    'Арт. WB': r.nm_id,
    'Арт. поставщика': r.vendor_code || '',
    'Баркод': r.barcodes || '',
    'Продано, шт': r.sold_qty,
    'Остаток WB': r.stock_wb,
    'Остаток продавца': r.stock_fbs,
    'Оборачиваемость, дн': r.turnover_days ?? '',
    'Цена тек. (розничная WB), ₽': money(r.wb_price ?? r.price),
    'Цена тек. со скидкой, ₽': money(r.wb_price_discounted),
    'Цена продажи из куба, ₽': money(r.price_cube),
    'Скидка тек., %': r.discount,
    'Маржа тек., ₽': money(r.margin_now_rub),
    'Цена план., ₽': money(r.price_new),
    'Скидка план., %': r.plan_discount,
    'Мин. цена, ₽': r.min_price ?? '',
    'Выручка/шт, ₽': money(r.unit.revenue),
    'Комиссия WB/шт, ₽': money(r.unit.commission),
    'Эквайринг/шт, ₽': money(r.unit.acquiring),
    'Приёмка/шт, ₽': money(r.unit.acceptance),
    'Логистика/шт, ₽': money(r.unit.delivery),
    'Хранение/шт, ₽': money(r.unit.storage),
    'Штрафы/шт, ₽': money(r.unit.penalty),
    'Отзывы/шт, ₽': money(r.unit.reviews),
    'Реклама/шт, ₽': money(r.unit.adv),
    'Кэшбек/шт, ₽': money(r.unit.cashback),
    'Итого/шт, ₽': money(r.unit.net_profit),
    'НДС/шт, ₽': money(r.unit.nds),
    'Себестоимость/шт, ₽': money(r.unit.cost),
    'Прибыль/шт, ₽': money(r.unit.profit_before_tax),
    'Налог 7%/шт, ₽': money(r.unit.tax),
    'Маржа, %': r.unit.margin_pct ?? '',
    'Маржа на цене акции, ₽': money(r.unit.margin_rub),
    'Изменение маржи, %': r.margin_change_pct ?? '',
    'Изменение маржи, ₽': money(r.margin_change_rub),
    'Оценка по аналогам': r.est_analog ? 'да' : '',
    'Рекомендация': r.recommend ? 'в акцию' : 'не в акцию',
    'Причина': r.reason || '',
  }))
  await exportXlsx({
    rows: data,
    filename,
    sheetName: 'Подбор товаров',
    cols: [{ wch: 34 }, { wch: 12 }, { wch: 16 }, { wch: 18 }, { wch: 12 }, { wch: 12 },
      { wch: 16 }, { wch: 18 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 14 },
      { wch: 14 }, { wch: 14 }, { wch: 12 },
      { wch: 15 }, { wch: 18 }, { wch: 16 }, { wch: 16 }, { wch: 16 }, { wch: 14 }, { wch: 13 },
      { wch: 14 }, { wch: 13 }, { wch: 13 }, { wch: 18 }, { wch: 14 }, { wch: 14 }, { wch: 12 },
      { wch: 14 }, { wch: 12 }, { wch: 16 }, { wch: 16 },
      { wch: 16 }, { wch: 12 }, { wch: 40 },
    ],
  })
}

