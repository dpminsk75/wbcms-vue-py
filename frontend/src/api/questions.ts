import { api } from './client'

export interface QuestionItem {
  id: string
  nm_id: number | null
  imt_id: number | null
  product_name: string | null
  supplier_article: string | null
  supplier_name: string | null
  brand_name: string | null
  /** Текст вопроса покупателя. */
  q_text: string | null
  /** Текст ответа продавца (null — ответа нет). */
  answer_text: string | null
  answer_editable: number | null
  answer_date: string | null
  /** none | wbRu | suppliersPortalSynch — статус вопроса по данным WB. */
  state: string | null
  state_label: string
  was_viewed: number | null
  is_warned: number | null
  has_answer: number
  created_date: string
  card_title: string | null
  card_vendor: string | null
  card_subject: string | null
  card_brand: string | null
  card_photos: any
}

export interface QuestionsStats {
  total: number
  unanswered: number
  answered: number
  rejected: number
  warned: number
  /** unix времени последней загрузки. */
  last_sync: number | null
}

export interface QuestionsParams {
  date_from?: string
  date_to?: string
  nm_id?: number | string
  status?: string
  q?: string
  sort?: string
  order?: string
  page?: number
  page_size?: number
}

export interface SyncStatus {
  running: boolean
  started_at: number | null
  finished_at: number | null
  company_id: number | null
  mode: string | null
  log: string[]
  result: any
}

export const questionsApi = {
  async list(params: QuestionsParams): Promise<{
    items: QuestionItem[]
    total: number
    page: number
    page_size: number
    stats: QuestionsStats
  }> {
    const { data } = await api.get('/api/questions', { params })
    return data
  },
  async stats(params: { date_from?: string, date_to?: string }): Promise<QuestionsStats> {
    const { data } = await api.get('/api/questions/stats', { params })
    return data
  },
  async get(id: string): Promise<QuestionItem> {
    const { data } = await api.get(`/api/questions/${encodeURIComponent(id)}`)
    return data
  },
  /** Запустить синк в фоне (fresh — окно дат, full — вся история). */
  async sync(payload: { mode?: string, date_from?: string, date_to?: string, nm_id?: number }): Promise<{ started: boolean }> {
    const { data } = await api.post('/api/questions/sync', payload)
    return data
  },
  async syncStatus(): Promise<SyncStatus> {
    const { data } = await api.get('/api/questions/sync/status')
    return data
  },
}
