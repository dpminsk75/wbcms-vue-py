import { api } from './client'

export interface TagItem {
  id: number
  name: string
  tag_group: string | null
  color: string
  priority: number
  cards_count: number
}

export interface WbCardOption {
  nmID: number
  vendorCode: string
  title: string
}

export interface TagDetail extends TagItem {
  wbCardIds: number[]
  cards: WbCardOption[]
}

export interface TagAnalytics {
  tag: TagDetail
  allTags: TagItem[]
  chartData: Array<Record<string, any>>
  byProduct: Array<Record<string, any>>
  byDate: Array<Record<string, any>>
  /** Карточки тега — с фото и реквизитами (для общей карточки товара). */
  relatedCards: Array<{
    nmId: number
    card_name: string
    vendorCode: string
    photos?: any
    brand?: string | null
    subjectName?: string | null
  }>
  date_from: string
  date_to: string
}

export const tagsApi = {
  async list(): Promise<TagItem[]> {
    const { data } = await api.get('/api/tags')
    return Array.isArray(data) ? data : (data.items ?? [])
  },
  async get(id: number | string): Promise<TagDetail> {
    const { data } = await api.get(`/api/tags/${id}`)
    return data
  },
  async create(payload: { name: string; tag_group?: string | null; color: string; priority: number; wbCardIds: number[] }) {
    const { data } = await api.post('/api/tags', payload)
    return data
  },
  async update(id: number | string, payload: { name: string; tag_group?: string | null; color: string; priority: number; wbCardIds: number[] }) {
    const { data } = await api.put(`/api/tags/${id}`, payload)
    return data
  },
  async remove(id: number | string) {
    const { data } = await api.delete(`/api/tags/${id}`)
    return data
  },
  async searchCards(q: { nmID?: string; vendorCode?: string; title?: string }): Promise<WbCardOption[]> {
    const query = [q.nmID, q.vendorCode, q.title].filter(Boolean).join(' ')
    const { data } = await api.get('/api/wb/cards', { params: { q: query || undefined, limit: 50 } })
    const rows = Array.isArray(data) ? data : (data.items ?? [])
    return rows.map((r: any) => ({ nmID: Number(r.nmID ?? r.nm_id), vendorCode: String(r.vendorCode ?? ''), title: String(r.title ?? '') }))
  },
  async analytics(id: number | string, dateFrom: string, dateTo: string): Promise<TagAnalytics> {
    const { data } = await api.get(`/api/tags/${id}/analytics`, { params: { date_from: dateFrom, date_to: dateTo } })
    return data
  },
  async margin(id: number | string, dateFrom: string, dateTo: string, sortBy = 'qnt', withStock = false): Promise<any[]> {
    const { data } = await api.get(`/api/tags/${id}/margin`, { params: { date_from: dateFrom, date_to: dateTo, sort_by: sortBy, with_stock: withStock ? 1 : 0 } })
    return Array.isArray(data) ? data : []
  },
}
