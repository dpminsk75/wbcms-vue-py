import { api } from './client'

/** Рабочее место «SEO-мониторинг» — /api/seo-watch (план 2026-10-23) */

/** Пороги мониторинга (companies.watch_*). */
export interface WatchSettings {
  top_cards_n: number
  top_phrases_n: number
  stale_days: number
  price_delta_pct: number
  /** Сколько фраз набора анализируем за раз. */
  phrases_limit?: number
  /** Старше стольких дней карточка считается «устаревшей» для сбора контента. */
  card_stale_days?: number
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
  /** Насколько наша цена дороже медианы конкурентов ТОП-40, %. */
  price_delta_pct?: number | null
  /** Сколько конкурентов в ТОП-40 дешевле нас. */
  cheaper_cnt?: number | null
}

export interface WatchNewItem {
  nm_id: number
  title: string
  position: number
  price: number | null
  /**
   * Контент карточки уже собран не раньше старого захода — событие в неё уже
   * «вошло», повторный сбор не нужен (в очереди такая карточка пропускается).
   */
  fresh?: boolean
}

export interface WatchPriceMove {
  nm_id: number
  title: string
  from: number
  to: number
  pct: number
  /** См. WatchNewItem.fresh — то же правило для сдвига цены. */
  fresh?: boolean
}

export interface WatchMatrixRow {
  phrase: string
  /** Максимальные заказы по фразе у наших карточек ТОП (из Search Reports). */
  orders_max: number
  /**
   * «Запросов» за период — метрика /wb-search/analytics: MAX(week_frequency)
   * по nmID за день → AVG по дням × дней периода. Ранг 'freq' идёт по ней.
   */
  freq?: number
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
  /**
   * Актуальных карточек ТОП-40: описание есть и полный сбор не старше порога
   * компании (watch_card_stale_days).
   */
  cards_fresh?: number
  /** Устаревших карточек ТОП-40: описание есть, но старше порога. */
  cards_stale?: number
  /** Карточек ТОП-40 без описания — контент не собирали ни разу. */
  cards_missing?: number
  /**
   * Корзины по глубине захода (ключ «10»/«20»/«40») — счётчик кнопки сбора
   * должен совпадать с тем, что реально соберётся при выбранной глубине.
   */
  cards_by_depth?: Record<string, { fresh: number; stale: number; missing: number }>
  /**
   * Карточки окна последнего захода (ТОП-40) для точных счётчиков кнопок:
   * [nmId, позиция, статус контента] — статус 0 актуальный / 1 устаревший /
   * 2 без описания. Фронт дедупит по nmId: суммы по фразам завышали кнопки
   * (числили карточку в нескольких фразах, а в очередь она встаёт один раз).
   */
  pool?: Array<[number, number, number]>
  ours_cnt: number
  /** Позиций в окне анализа (ТОП-40). */
  top_cnt?: number
  /** Наших карточек внутри окна анализа */
  top_ours_cnt?: number
  /** Цены против медианы конкурентов в ТОП-40 (наши исключены). */
  price_median?: number | null
  price_min?: number | null
  /** Сколько конкурентских цен учтено в медиане. */
  price_cnt?: number
  our_positions: WatchOurPosition[]
  best_position: number | null
  new_cnt: number
  new_items: WatchNewItem[]
  price_moves: WatchPriceMove[]
  price_moves_cnt: number
  requeue_status: string
  requeue_at: string
}

/** Активные фильтры панели (рассчитаны бекендом; попадают в ключ кэша матрицы). */
export interface WatchFilter {
  card_nm: number
  rank: 'orders' | 'freq'
  queries: number
}

export interface WatchMatrix {
  settings: WatchSettings
  filter?: WatchFilter
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
  filter?: WatchFilter
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
  /** Фраз, взятых в работу (целевых). */
  phrases_cnt?: number
  /** Пропущено карточек, собранных сегодня. */
  skipped_today?: number
  stale_days: number
}

/** Результат сбора карточек в очередь enrich (source='watch'). */
export interface WatchCollectResult {
  mode: 'changed' | 'stale' | 'missing'
  requested: number
  assigned: number
  skipped: number
  candidates: number
  top: number
  phrases_cnt: number
  stale_days: number
}

export interface WatchFilterParams {
  date_from?: string
  date_to?: string
  /** Фильтр «наша карточка»: nmID (0/пусто = все наши). */
  card_nm?: number
  /** Ранг фраз: 'orders' — по заказам (по умолчанию), 'freq' — по частотности. */
  rank?: string
  /** ТОП-N запросов карточки (0 = порог компании top_phrases_n). */
  queries?: number
}

export const seoWatchApi = {
  /** Тяжёлый расчёт матрицы может думать десятки секунд — не ждём вечно («Загрузка…»). */
  TIMEOUT: 120000,

  summary: (params: WatchFilterParams) =>
    api.get('/api/seo-watch/summary', { params, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchSummary),

  matrix: (params: WatchFilterParams) =>
    api.get('/api/seo-watch/matrix', { params, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchMatrix),

  phrase: (params: { phrase: string; date_from?: string; date_to?: string }) =>
    api.get('/api/seo-watch/phrase', { params, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchPhraseDetail),

  events: (params: WatchFilterParams & { type?: string; limit?: number }) =>
    api.get('/api/seo-watch/events', { params, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as { new?: any[]; price?: any[] }),

  requeue: (phrases: string[], dateFrom?: string, f?: Partial<WatchFilterParams>) =>
    api.post('/api/seo-watch/requeue', { phrases, ...f },
      { params: { date_from: dateFrom || undefined }, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchRequeueResult),

  refresh: (phrases: string[], top = 10, dateFrom?: string, dateTo?: string, f?: Partial<WatchFilterParams>) =>
    api.post('/api/seo-watch/refresh', { phrases, top, ...f },
      { params: { date_from: dateFrom || undefined, date_to: dateTo || undefined }, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchRefreshResult),

  /** Сбор карточек SEO-мониторинга: 'changed' — новые/изменённые, 'stale' — устаревшие. */
  collect: (mode: 'changed' | 'stale' | 'missing', phrases: string[] = [], top = 40, dateFrom?: string, dateTo?: string, f?: Partial<WatchFilterParams>) =>
    api.post('/api/seo-watch/collect', { mode, phrases, top, ...f },
      { params: { date_from: dateFrom || undefined, date_to: dateTo || undefined }, timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as WatchCollectResult),

  /** Собрать перечисленные карточки сейчас («Собрать» на собранных карточках).
   * Исключённые из сбора (is_hidden) расширение не трогает — сервер их пропускает. */
  collectNms: (nmIds: number[]) =>
    api.post('/api/seo-watch/collect-nms', { nm_ids: nmIds }, { timeout: seoWatchApi.TIMEOUT })
      .then((r) => r.data as { requested: number; assigned: number; skipped: number; excluded: number }),
}