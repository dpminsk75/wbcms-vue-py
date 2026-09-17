import { api } from './client'

export interface ReplyRuleItem {
  id: number
  title: string
  is_active: number
  rule_type: string
  rating_min: number
  rating_max: number
  text_condition: string
  part_separator: string
  updated_at?: number
  brands: string[]
  products: Array<{ nmID: number; title: string | null }>
}

export interface ReplyRuleDetail extends ReplyRuleItem {
  greetings: string[]
  bodies: string[]
  signoffs: string[]
}

export interface ReplyRulePayload {
  title: string
  is_active: number
  rule_type: string
  rating_min: number
  rating_max: number
  text_condition: string
  part_separator: string
  greetings: string[]
  bodies: string[]
  signoffs: string[]
  brands: string[]
  product_ids: number[]
}

export const replyRulesApi = {
  async list(page = 1): Promise<{ items: ReplyRuleItem[]; total: number; page: number; page_size: number }> {
    const { data } = await api.get('/api/reply-rules', { params: { page } })
    return data
  },
  async get(id: number | string): Promise<ReplyRuleDetail> {
    const { data } = await api.get(`/api/reply-rules/${id}`)
    return data
  },
  async create(payload: ReplyRulePayload) {
    const { data } = await api.post('/api/reply-rules', payload)
    return data
  },
  async update(id: number | string, payload: ReplyRulePayload) {
    const { data } = await api.put(`/api/reply-rules/${id}`, payload)
    return data
  },
  async remove(id: number | string) {
    const { data } = await api.delete(`/api/reply-rules/${id}`)
    return data
  },
  async toggle(id: number | string): Promise<{ ok: boolean; is_active: number }> {
    const { data } = await api.patch(`/api/reply-rules/${id}/active`)
    return data
  },
  async productList(q: string): Promise<Array<{ id: string; text: string }>> {
    const { data } = await api.get('/api/reply-rules/product-list', { params: { q } })
    return data.results || []
  },
  async brandList(q: string): Promise<Array<{ id: string; text: string }>> {
    const { data } = await api.get('/api/reply-rules/brand-list', { params: { q } })
    return data.results || []
  },
}
