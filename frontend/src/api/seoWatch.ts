import { api } from './client'

/** Рабочее место «SEO-мониторинг» — /api/seo-watch (план 2026-10-23) */

/** Пороги мониторинга (companies.watch_*). */
export interface WatchSettings {
  top_cards_n: number
  top_phrases_n: number
  stale_days: number
  price_delta_pct: number
}

export interface WatchCard {
  nm_id: number
  orders: number
  subject_name: string
  brand_name: string
}

/** Наши позиции в последнем срезе выдачи по фразе. */
export interface WatchOurPosition {
  nm_id: number
  position: number | null
  price: number | null
  /** Артикул нашей карточки (wbcards.vendorCode) — для тултипа. */
  vendor_code?: string
}

export interface WatchNewItem {
  nm_id: number
  title: string
  position: number
  price: number | null
}

export interface WatchPriceMove {
  nm_id: number
  title: string
  from: number
  to: number
  pct: number
}

export interface WatchMatrixRow {
  phrase: string
  /** Максимальные заказы по фразе среди наших карточек ТОП (из Search Reports). */
  orders_max: number
  cards: Array<{ nm_id: number; orders: number; clicks: number }>
  /** Дата последнего захода в поиск по фразе. */
  last_at: string
  prev_at: string
  /** Метка последнего захода (20261022_131023). */
  last_stamp: string
  /** Сколько заходов было за период. */
  slices_cnt: number
  days_old: number | null
  /** Сбор свежее порога компании (`watch_stale_days`). */
  fresh: boolean
  stale_days: number
  /** Уникальных карточек в последнем заходе (COUNT DISTINCT по срезу). */
  cards_cnt: number
  ours_cnt: number
  /** Позиций в окне анализа (ТОП-40). */
  top_cnt?: number
  /** Наших карточек внутри окна анализа */
  top_ours_cnt?: number
  our_positions: WatchOurPosition[]
  best_position: number | null
  new_cnt: number
  new_items: WatchNewItem[]
  price_moves: WatchPriceMove[]
  price_moves_cnt: number
  requeue_status: string
  requeue_at: string
}

export interface WatchMatrix {
  settings: WatchSettings
  date_from: string
  date_to: string
  cards: WatchCard[]
  cards_cnt: number
  items: WatchMatrixRow[]
  total: number
  phrases_cnt: number
  /** Всего фраз в наборе мониторинга (лимит фраз режет только анализ). */
  phrases_total?: number
  /** Тайминги фаз последнего расчёта матрицы, секунды (settings/stamps/slices/...). */
  timings?: Record<string, number>
}

export interface WatchSummary {
  settings: WatchSettings
  date_from: string
  date_to: string
  cards_cnt: number
  /** Сколько фраз анализируется. */
  phrases_cnt: number
  /** Всего фраз в наборе мониторинга. */
  phrases_total?: number
  fresh_cnt: number
  stale_cnt: number
  with_position_cnt: number
  top3_cnt: number
  top10_cnt: number
  top3_pct: number
  top10_pct: number
  avg_position: number | null
  new_cnt: number
  price_moves_cnt: number
}

/** Срез выдачи по фразе (раскрытие строки матрицы). */
export interface WatchPhraseItem {
  nm_id: number
  title: string
  brand: string
  seller: string
  position: number
  position_api?: number | null
  price: number | null
  price_api?: number | null
  old_price?: number | null
  rating: number | null
  review_rating?: number | null
  reviews?: number | null
  feedbacks?: number | null
  badges: string[]
  image_url?: string
  /** Наш товар — тот, кто сам был в выдаче. */
  is_ours?: number
  /** Впервые появился в выдаче (светло-голубой фон). */
  is_new?: number
  /** Цена изменилась против прошлого захода (оранжевая подпись). */
  price_changed?: number
  /** Прежняя цена и процент изменения. */
  price_prev?: number | null
  price_pct?: number | null
  source_nm_id: number
}

export interface WatchPhraseDay {
  date: string
  /** Время захода в поиск (13:10). */
  time?: string
  cards_cnt: number
  items: WatchPhraseItem[]
}

export interface WatchPhraseDetail {
  phrase: string
  days: WatchPhraseDay[]
  days_cnt: number
}

export interface WatchRequeueResult {
  queued: number
  phrases: string[]
  skipped: string[]
}

export interface WatchRefreshResult {
  requested: number
  assigned: number
  skipped: number
  candidates: number
  top: number
  /** Фраз сверх лимита за раз (не взяты в очередь). */
  overflow?: number
  stale_days: number
}

export const seoWatchApi = {
  /** Тяжёлый расчёт матрицы может думать десятки секунд — не ждём вечно («Загрузка…»). */
  TIMEOUT: 120000,

  summary: (params: { date_from?: string; date_to?: string }) =>
    api.get('/api/seo-watch/summary', { params, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchSummary),

  matrix: (params: { date_from?: string; date_to?: string }) =>
    api.get('/api/seo-watch/matrix', { params, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchMatrix),

  phrase: (params: { phrase: string; date_from?: string; date_to?: string }) =>
    api.get('/api/seo-watch/phrase', { params, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchPhraseDetail),

  events: (params: { date_from?: string; date_to?: string; type?: string; limit?: number }) =>
    api.get('/api/seo-watch/events', { params, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as { new?: any[]; price?: any[] }),

  requeue: (phrases: string[], dateFrom?: string) =>
    api.post('/api/seo-watch/requeue', { phrases }, { params: { date_from: dateFrom || undefined }, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchRequeueResult),

  refresh: (phrases: string[], top = 10) =>
    api.post('/api/seo-watch/refresh', { phrases, top }, { timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchRefreshResult),
}