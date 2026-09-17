import { api } from './client'

export interface CostRow {
  id: number
  load_date: string
  nmID: number
  chrtID: number | null
  sku: string | null
  price: number
  product_name: string | null
  vendorCode: string | null
}

export const costApi = {
  async list(dateFrom: string, dateTo: string, nmId?: string, sku?: string): Promise<CostRow[]> {
    const { data } = await api.get('/api/cost-import/list', {
      params: { date_from: dateFrom, date_to: dateTo, nm_id: nmId || undefined, sku: sku || undefined },
    })
    return Array.isArray(data) ? data : []
  },
  async save(date: string, items: Array<{ nmID: string; price: number; chrtID?: string; sku?: string }>) {
    const { data } = await api.post('/api/cost-import/save', { date, items })
    return data as { success: boolean; message: string; processed?: number }
  },
  async preview(date: string, rows: any[][]) {
    const { data } = await api.post('/api/cost-import/preview', { date, rows })
    return data as { success: boolean; message?: string; items: any[]; errors: any[] }
  },
  async updateRow(id: number, payload: { price?: string; load_date?: string }) {
    const { data } = await api.post('/api/cost-import/update-price', { id, ...payload })
    return data as { success: boolean; message?: string; price?: number; load_date?: string }
  },
  async remove(id: number) {
    const { data } = await api.delete(`/api/cost-import/${id}`)
    return data
  },
  async missing(dateFrom: string, dateTo: string, page = 1): Promise<{ models: any[]; total: number; page: number; page_size: number }> {
    const { data } = await api.get('/api/cost-import/missing', { params: { date_from: dateFrom, date_to: dateTo, page } })
    return data
  },
}
