import { api } from './client'

/** Отчёты по собранной выдаче WB — /api/competitors/positions */

export interface PositionsSavedBy {
  id: number
  username: string
  /** Имя ext-токена (машина/автор парсинга). */
  token_name?: string
  token_ids?: number[]
  tokens?: string[]
}

export interface PositionsSourceCard {
  nm_id: number
  title: string
}

/** Статус пересборки выдачи по фразе (очередь для расширения). */
export type RequeueStatus = '' | 'pending' | 'processing' | 'done' | 'error'

export interface PositionsPhraseRow {
  phrase: string
  /** Статус пересборки: пусто = не отправляли. */
  requeue_status?: RequeueStatus
  /** Когда последний раз ставили на пересборку. */
  requeue_at?: string
  requeue_error?: string
  /** Сколько раз заходили в поиск по этой фразе (число заходов, не дней). */
  collections?: number
  /** Как фраза приходила в WB (может быть с дефисами и с пробелами) — объединено в отчёте. */
  phrase_variants?: string[]
  rows: number
  days: number
  products: number
  first_at: string
  last_at: string
  user_ids: number[]
  source_ids: number[]
  sources: PositionsSourceCard[]
  saved_by: PositionsSavedBy[]
}

export interface PositionsItem {
  position: number
  position_api?: number | null
  nm_id: number
  title: string
  brand: string
  seller: string
  seller_id?: number | null
  seller_rating?: number | null
  price: number | null
  old_price: number | null
  price_api?: number | null
  old_price_api?: number | null
  rating: number | null
  review_rating?: number | null
  feedbacks: number | null
  reviews: number | null
  badges: string[]
  promo_id: number | null
  is_adv: number
  match_id?: number | null
  /** Фото товара (из DOM-выдачи). */
  image_url?: string
  /** Наш товар — тот, кто сам был в выдаче (а не просто конкурент). */
  is_ours?: boolean
  source_nm_id: number
  /** Наши карточки, к которым привязан этот товар в выдаче (одна строка на товар). */
  source_nm_ids?: number[]
  source_title: string
  source_vendor: string
  created_by: number | null
  ext_token_id?: number | null
  token_name?: string
  username: string
  at: string
}

export interface PositionsPhraseDetail {
  phrase: string
  date: string
  days: string[]
  items: PositionsItem[]
  /** Срезы по заходам в поиск: строка отчёта = один заход (дата + время), в ней карточки выдачи. */
  slices?: Array<{ date: string; time: string; stamp: string; items: PositionsItem[] }>
  sources: PositionsSourceCard[]
  saved_by: PositionsSavedBy[]
}

export interface PositionsCardRow {
  nm_id: number
  title: string
  vendor: string
  brand: string
  phrases: number
  days: number
  first_at: string
  last_at: string
  best_position: number | null
}

export interface PositionsCompetitor {
  position: number
  position_api?: number | null
  nm_id: number
  title: string
  brand: string
  seller: string
  seller_id?: number | null
  seller_rating?: number | null
  price: number | null
  old_price: number | null
  price_api?: number | null
  old_price_api?: number | null
  rating: number | null
  review_rating?: number | null
  feedbacks: number | null
  reviews: number | null
  badges: string[]
  promo_id: number | null
  match_id?: number | null
  username: string
}

/** Профиль ниши по фразе (разбор filters выдачи). */
export interface NicheRow {
  phrase: string
  /** Другие варианты написания той же фразы (дефисы/пробелы) — схлопнуты в одну. */
  phrase_variants?: string[]
  phrase_norm: string
  date: string
  collected_at: string
  file_name: string
  total: number | null
  price_min: number | null
  price_max: number | null
  delivery_min: number | null
  delivery_max: number | null
  brands: Array<{ id: number | null; name: string }>
  sellers: Array<{ id: number | null; name: string }>
  subjects: Array<{ id: number | null; name: string; parentId: number | null; parentName: string }>
  sale_factions: Array<{ id: number | null; name: string }>
  countries: Array<{ id: number | null; name: string }>
  ages: Array<{ id: number | null; name: string }>
  delivery_types: Array<{ id: number | null }>
  flags: Array<{ key: string; name?: string | null; type?: string | null; maxselect?: number | null; items?: number }>
  /** Все фасеты ниши как пришли: {key: {name, items[]}} */
  facets?: Record<string, { name?: string | null; items?: Array<{ id?: number | null; name?: string | null }> }>
  created_by: number | null
}

/** Баннеры (реклама) и брендовые полки в поиске. */
export interface SearchAdsRow {
  phrase: string
  /** Другие варианты написания той же фразы (дефисы/пробелы) — схлопнуты в одну. */
  phrase_variants?: string[]
  date: string
  collected_at: string
  file_name: string
  banner_cnt: number
  shelf_cnt: number
  shelf_products_cnt: number
  banners: Array<{
    uid?: string | null; cpm?: string | null; type?: string | null; mark?: string | null
    erid?: string | null; url?: string | null; is_commercial?: boolean | null; ts?: number | null
  }>
  shelfs: Array<{
    title: string; url: string; mark: string; cpm: string
    products: Array<{ id?: number | null; name?: string; seller?: string; price?: number | null }>
  }>
  sellers: Array<{ name: string; mark?: string | null }>
  created_by: number | null
}

export interface PositionsPhraseBlock {
  phrase: string
  days: string[]
  last_day: string
  our_positions: Array<{ date: string; position: number | null; position_api?: number | null; price: number | null }>
  last_position: number | null
  best_position: number | null
  /** Позиция по данным WB (JSON-каталог) — порядок среди всех товаров выдачи. */
  last_position_api?: number | null
  best_position_api?: number | null
  competitors: PositionsCompetitor[]
  products: number
}

export interface PositionsCardDetail {
  card: { nm_id: number; title: string; vendor: string; brand: string }
  phrases: PositionsPhraseBlock[]
  our_history: Array<{ phrase: string; date: string; position: number | null; price: number | null }>
}

/** Сводка нашей карточки: описание, характеристики и наши позиции в выдаче. */
export interface OurCardSummary {
  card: {
    nm_id: number
    title: string
    brand: string
    vendor: string
    subject: string
    description: string
    characteristics: Array<{ name?: string | null; value?: string[] }>
    photos: string[]
  }
  phrases: Array<{
    phrase: string
    days: string[]
    last_day: string
    position: number | null
    position_api?: number | null
    price: number | null
    price_api?: number | null
    old_price_api?: number | null
    rating?: number | null
    reviews?: number | null
    badges: string[]
    image_url?: string
    history: Array<{
      date: string
      position: number
      position_api?: number | null
      price: number | null
      price_api?: number | null
    }>
  }>
}

export const competitorsPositionsApi = {
  phrases: (params: { date_from?: string; date_to?: string; q?: string; limit?: number }) =>
    api.get('/api/competitors/positions/phrases', { params })
      .then((r) => r.data as { items: PositionsPhraseRow[]; total: number }),

  phrase: (params: { phrase: string; date_from?: string; date_to?: string; day?: string }) =>
    api.get('/api/competitors/positions/phrase', { params })
      .then((r) => r.data as PositionsPhraseDetail),

  cards: (params: { date_from?: string; date_to?: string; limit?: number }) =>
    api.get('/api/competitors/positions/cards', { params })
      .then((r) => r.data as { items: PositionsCardRow[]; total: number }),

  card: (params: { nm_id: number; date_from?: string; date_to?: string; top?: number }) =>
    api.get('/api/competitors/positions/card', { params })
      .then((r) => r.data as PositionsCardDetail),

  niches: (params: { date_from?: string; date_to?: string; limit?: number }) =>
    api.get('/api/competitors/positions/niches', { params })
      .then((r) => r.data as { items: NicheRow[]; total: number }),

  ads: (params: { date_from?: string; date_to?: string; limit?: number }) =>
    api.get('/api/competitors/positions/ads', { params })
      .then((r) => r.data as { items: SearchAdsRow[]; total: number }),

  /** Отправить фразы на пересборку выдачи (расширение их обойдёт). */
  requeue: (payload: { phrases: string[]; source_nm_id?: number; source?: string }) =>
    api.post('/api/competitors/positions/requeue', payload)
      .then((r) => r.data as {
        queued: number; phrases: string[]; skipped: string[]; limit: number
      }),

  ourCard: (params: { nm_id: number; date_from?: string; date_to?: string }) =>
    api.get('/api/competitors/positions/our_card', { params, timeout: 30000 })
      .then((r) => r.data as OurCardSummary),
}
