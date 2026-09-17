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
  [k: string]: unknown
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
}
