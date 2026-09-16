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
  relatedCards: Array<{ nmId: number; card_name: string; vendorCode: string }>
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
  async margin(id: number | string, dateFrom: string, dateTo: string, sortBy = 'qnt'): Promise<any[]> {
    const { data } = await api.get(`/api/tags/${id}/margin`, { params: { date_from: dateFrom, date_to: dateTo, sort_by: sortBy } })
    return Array.isArray(data) ? data : []
  },
  async exportByProduct(id: number | string, dateFrom: string, dateTo: string) {
    const a = await this.analytics(id, dateFrom, dateTo)
    const { default: XLSX } = await import('xlsx')
    const ws = XLSX.utils.json_to_sheet(a.byProduct.map((r: any) => ({
      'Арт WB': r.nm_id, 'Товар': r.card_title, 'Артикул': r.card_vendor_code,
      'Количество': r.cnt, 'Отменено': r.cns, 'Выкуплено': r.byt,
      'Цена': r.tp, 'Скидка %': r.dsc, 'Цена со ск': r.apwd, 'СПП %': r.spp,
      'Цена прод': r.finished_price, 'Сумма заказов': r.sum_ord, 'Сумма выкупа': r.sum_byt,
    })))
    ws['!cols'] = [{ wch: 12 }, { wch: 32 }, { wch: 18 }, { wch: 10 }, { wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 10 }, { wch: 12 }, { wch: 10 }, { wch: 12 }, { wch: 15 }, { wch: 14 }]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'tag-products')
    XLSX.writeFile(wb, `tag-${id}-products.xlsx`)
  },
  async exportByDate(id: number | string, dateFrom: string, dateTo: string) {
    const a = await this.analytics(id, dateFrom, dateTo)
    const { default: XLSX } = await import('xlsx')
    const ws = XLSX.utils.json_to_sheet(a.byDate.map((r: any) => ({
      'Дата': r.odate, 'Кол-во': r.cnt, 'Отмена': r.cns, 'Сумма': r.sum_ord,
      'Цена Рзн': r.tp, 'Скидка %': r.dsc, 'Цена со ск': r.apwd, 'СПП %': r.spp, 'Цена зкз': r.finished_price,
    })))
    ws['!cols'] = [{ wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 14 }, { wch: 12 }, { wch: 10 }, { wch: 12 }, { wch: 10 }, { wch: 12 }]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'tag-dates')
    XLSX.writeFile(wb, `tag-${id}-dates.xlsx`)
  },
}
