import { api } from './client'

export interface FeedbackAnswer {
  id: string
  nmID: number | null
  userName: string | null
  productValuation: number | null
  text: string | null
  pros: string | null
  cons: string | null
  answer_text: string | null
  is_auto_replied: number | null
  rule_id: number | null
  createdDate: string | null
  updatedDate: string | null
  photoLinks: any[]
  video: Record<string, any> | null
  f_cost: number | null
  bables: string[]
  product_title: string | null
  rule_title: string | null
  /** Метки ИИ-разбора отзыва: low|mid|high / neg|pos|neutral; null — не разобран. */
  ai_emotion: string | null
  ai_constructiveness: string | null
  ai_tone: string | null
  ai_status: string | null
  ai_error: string | null
  [k: string]: unknown
}

/** Отзыв с ошибкой разбора — для модалки «Вернуть в очередь». */
export interface FeedbackReviewError {
  feedback_id: string
  nm_id: number | null
  rating: number | null
  error: string | null
  attempts: number | null
  text: string | null
  created_at: string | null
  product_title: string | null
}

export interface FeedbackAnswersParams {
  date_from?: string
  date_to?: string
  nm_id?: number | string
  rating?: number | string
  status?: string
  has_media?: boolean
  paid_only?: boolean
  sort?: string
  order?: string
  page?: number
  page_size?: number
}

export interface FeedbackTag {
  id: number
  tag_text: string
  sentiment: string
  usage_count: number
}

export const feedbackApi = {
  async answers(params: FeedbackAnswersParams): Promise<{
    items: FeedbackAnswer[]
    total: number
    page: number
    page_size: number
    tags_sentiment: Record<string, string>
    rules: Array<{ id: number; title: string }>
  }> {
    const { data } = await api.get('/api/feedback/answers', { params })
    return data
  },
  async tags(filt = 'unclassified'): Promise<FeedbackTag[]> {
    const { data } = await api.get('/api/feedback/tags', { params: { filter: filt } })
    return Array.isArray(data) ? data : []
  },
  async setSentiment(id: number, sentiment: string) {
    const { data } = await api.post(`/api/feedback/tags/${id}/sentiment`, { sentiment })
    return data
  },
  async syncTags(): Promise<{ rows_scanned: number; unique_tags: number; new_tags: number; updated_tags: number }> {
    const { data } = await api.post('/api/feedback/tags/sync')
    return data
  },
  /** Разобрать один отзыв через ИИ (синхронно). */
  async reviewOne(feedbackId: string): Promise<{
    ok: boolean; emotion: string; constructiveness: string; tone: string
    summary?: string; topics?: string[]; model?: string
  }> {
    const { data } = await api.post(`/api/feedback/review/${encodeURIComponent(feedbackId)}`)
    return data
  },
  /** Отзывы с ошибкой разбора. */
  async reviewErrors(limit = 100): Promise<{ items: FeedbackReviewError[]; total: number }> {
    const { data } = await api.get('/api/feedback/review/errors', { params: { limit } })
    return data
  },
  /** Вернуть отзыв в очередь разбора. */
  async reviewRetry(feedbackId: string): Promise<{ ok: boolean }> {
    const { data } = await api.post(`/api/feedback/review/${encodeURIComponent(feedbackId)}/retry`)
    return data
  },
  /** Промпт разбора отзыва (настройка компании). */
  async reviewPrompt(): Promise<{ prompt: string }> {
    const { data } = await api.get('/api/feedback/review/prompt')
    return data
  },
  async saveReviewPrompt(prompt: string): Promise<{ ok: boolean; prompt: string }> {
    const { data } = await api.put('/api/feedback/review/prompt', { prompt })
    return data
  },
  /** Настройки авторазбора: включён ли, порция за прогон, промпт. */
  async reviewSettings(): Promise<{ auto: boolean; batch: number; prompt: string }> {
    const { data } = await api.get('/api/feedback/review/settings')
    return data
  },
  async saveReviewSettings(settings: { auto?: boolean; batch?: number }):
    Promise<{ auto: boolean; batch: number; prompt: string }> {
    const { data } = await api.put('/api/feedback/review/settings', settings)
    return data
  },
}
