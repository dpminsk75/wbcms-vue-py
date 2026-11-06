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
  days: number
  min_margin_pct: number
  min_margin_rub: number
  max_drop_pp: number | null
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
  price: number | null
  discount: number
  price_now: number | null
  plan_price: number | null
  plan_discount: number
  price_new: number | null
  price_mismatch: boolean
  /** Минимальная цена, при которой маржа держится порога (шаблон WB). */
  min_price: number | null
  /** Экономика на единицу при цене акции. */
  unit: PromoUnit
  /** Экономика на единицу при текущей цене. */
  unit_now: PromoUnit
  margin_now_pct: number | null
  margin_now_rub: number | null
  margin_new_pct: number | null
  margin_new_rub: number | null
  margin_drop_pp: number | null
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
  min_margin_pct: 10,
  min_margin_rub: 0,
  max_drop_pp: 5,
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
    'Цена тек., ₽': money(r.price_now),
    'Скидка тек., %': r.discount,
    'Цена план., ₽': money(r.price_new),
    'Скидка план., %': r.plan_discount,
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
    'Маржа/шт, ₽': money(r.unit.margin_rub),
    'Маржа, %': r.unit.margin_pct ?? '',
    'Δ маржи, п.п.': r.margin_drop_pp ?? '',
    'Мин. цена, ₽': r.min_price ?? '',
    'Рекомендация': r.recommend ? 'в акцию' : 'не в акцию',
    'Причина': r.reason || '',
  }))
  await exportXlsx({
    rows: data,
    filename,
    sheetName: 'Подбор товаров',
    cols: [{ wch: 34 }, { wch: 12 }, { wch: 16 }, { wch: 18 }, { wch: 12 }, { wch: 12 },
      { wch: 16 }, { wch: 18 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 16 },
      { wch: 15 }, { wch: 18 }, { wch: 16 }, { wch: 16 }, { wch: 16 }, { wch: 14 }, { wch: 13 },
      { wch: 14 }, { wch: 13 }, { wch: 13 }, { wch: 18 }, { wch: 14 }, { wch: 14 }, { wch: 12 },
      { wch: 14 }, { wch: 14 }, { wch: 16 },
    ],
  })
}

