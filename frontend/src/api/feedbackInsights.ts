import { api } from './client'

export interface FeedbackCard {
  nm_id: number
  cnt: number
  pos_cnt: number
  neg_cnt: number
  pos_pct: number
  neg_pct: number
  avg_rating: number | null
  days_cnt: number
  last_at: string | null
  title: string | null
  vendor_code: string | null
  brand: string | null
  subject_name: string | null
  last_insight_at: string | null
}

export interface FeedbackItem {
  id: string
  rating: number | null
  text: string | null
  pros: string | null
  cons: string | null
  size: string | null
  color: string | null
  created_at: string | null
}

export interface PanelGroup {
  title: string
  items: string[]
}

export interface FeedbackPanel {
  plus: PanelGroup[]
  minus: PanelGroup[]
}

export interface FeedbackRec {
  issue: string
  fix?: string
  action?: string
  highlight?: string | null
  evidence: string[]
  priority: number
  desc_add?: string[]
  desc_change?: Array<{ was: string; now: string }>
  desc_remove?: string[]
  desc_old?: string
  desc_new?: string | null
}

export interface FeedbackInsight {
  id: number
  nm_id: number
  job_id: number | null
  period_from: string | null
  period_to: string | null
  reviews_cnt: number
  neg_cnt: number
  avg_rating: number | null
  card_rec: FeedbackRec | null
  product_rec: FeedbackRec | null
  panel: FeedbackPanel
  summary: string | null
  confidence: number | null
  model: string | null
  status: string
  error: string | null
  created_at: string | null
  card_title: string | null
  vendor_code: string | null
  brand: string | null
  subject_name: string | null
}

export const feedbackInsightsApi = {
  filters: () => api.get('/api/feedback-insights/filters').then((r) => r.data as {
    brands: string[]; categories: string[]
  }),

  reviews: (params: {
    date_from: string; date_to: string; nm_id?: number; q?: string
    brand?: string; category?: string; page?: number; page_size?: number
  }) => api.get('/api/feedback-insights/reviews', { params }).then((r) => r.data as {
    items: FeedbackCard[]; total: number; page: number; page_size: number
  }),

  cardReviews: (nmId: number, params: {
    date_from: string; date_to: string; limit?: number
  }) => api.get(`/api/feedback-insights/reviews/${nmId}`, { params })
    .then((r) => r.data as { items: FeedbackItem[] }),

  run: (payload: {
    nm_ids: number[]; date_from?: string; date_to?: string
  }) => api.post('/api/feedback-insights/run', payload).then((r) => r.data as { job_id: number }),

  insights: (params: {
    date_from?: string; date_to?: string; nm_id?: number; job_id?: number
    q?: string; brand?: string; category?: string; page?: number; page_size?: number
  }) => api.get('/api/feedback-insights', { params }).then((r) => r.data as {
    items: FeedbackInsight[]; total: number; page: number; page_size: number
  }),

  insight: (id: number) => api.get(`/api/feedback-insights/${id}`).then((r) => r.data as FeedbackInsight),

  prompt: () => api.get('/api/feedback-insights/prompt').then((r) => r.data as {
    prompt: string; is_custom: boolean
  }),

  savePrompt: (prompt: string) => api.put('/api/feedback-insights/prompt', { prompt })
    .then((r) => r.data as { ok: boolean; is_custom: boolean }),
}
