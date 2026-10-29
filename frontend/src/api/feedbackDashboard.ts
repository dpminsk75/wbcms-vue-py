import { api } from './client'

export type DashPeriod = 'day' | 'week' | 'month'

/** Что считаем «отзывом»: все / с текстом или тегами / только с оценкой. */
export type DashRevMode = 'all' | 'content' | 'rated'

export interface DashKpi {
  reviews_cnt: number
  with_text_cnt: number
  with_text_pct: number
  with_tags_cnt: number
  rated_cnt: number
  avg_rating: number | null
  nps: number | null
  pos_cnt: number
  neg_cnt: number
  no_rating_cnt: number
  c5: number
}

export interface DashDelta {
  reviews_cnt_pct: number | null
  avg_rating_pp: number | null
  nps_pp: number | null
}

export interface DashRating {
  rating: number
  cnt: number
  pct: number
}

export interface DashDaily {
  d: string
  cnt: number
  pos: number
  neg: number
  avg_rating: number | null
}

export interface DashAiLevel {
  name: string
  cnt: number
  pct: number
}

/** Метки ИИ-разбора отзывов за период (донаты на дашборде). */
export interface DashAiSentiment {
  total: number
  parsed: number
  errors: number
  emotion: DashAiLevel[]
  constructiveness: DashAiLevel[]
  tone: DashAiLevel[]
}

export interface DashSummary {
  period: { from: string; to: string; days: number; prev_from: string; prev_to: string }
  period_kind: DashPeriod
  kpi: DashKpi
  prev: DashKpi
  delta: DashDelta
  ratings: DashRating[]
  sentiment: { positive: number; negative: number; no_rating: number }
  ai_sentiment?: DashAiSentiment
  daily: DashDaily[]
}

export interface DashCard {
  nm_id: number
  title: string | null
  vendor_code: string | null
  brand: string | null
  subject_name: string | null
  photos: string | null
  orders_cnt: number
  reviews_cnt: number
  with_text_cnt: number
  with_tags_cnt: number
  pos_cnt: number
  neg_cnt: number
  avg_rating: number | null
  nps: number | null
}

export interface DashCardsResponse {
  items: DashCard[]
  total: number
  limit: number
  /** Карточек в кубе заказов за период. */
  cards_total?: number
  /** Карточек с отзывами за период. */
  cards_with_reviews?: number
  /** Заказов в кубе нет — сортировка по количеству отзывов. */
  orders_missing?: boolean
}

export const feedbackDashboardApi = {
  summary: (params: {
    date_from: string; date_to: string; q?: string
    brand?: string; category?: string; period?: DashPeriod
    rev_mode?: DashRevMode
  }) => api.get('/api/feedback/dashboard/summary', { params })
    .then((r) => r.data as DashSummary),

  cards: (params: {
    date_from: string; date_to: string; q?: string
    brand?: string; category?: string; limit?: number
    rev_mode?: DashRevMode
  }) => api.get('/api/feedback/dashboard/cards', { params })
    .then((r) => r.data as DashCardsResponse),

  options: () => api.get('/api/feedback/dashboard/options')
    .then((r) => r.data as { brands: string[]; categories: string[] }),
}
