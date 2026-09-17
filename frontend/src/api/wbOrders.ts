import { api } from './client'

export interface WbOrderRow {
  id: number
  date: string
  nm_id: string | null
  supplier_article: string | null
  card_title: string | null
  subject: string | null
  brand: string | null
  warehouse_name: string | null
  warehouse_type: string | null
  total_price: number | null
  discount_percent: number | null
  price_with_disc: number | null
  spp: number | null
  finished_price: number | null
  country_name: string | null
  oblast_okrug_name: string | null
  region_name: string | null
  is_cancel: number | null
  g_number: string | null
  [k: string]: unknown
}

export interface WbOrderListParams {
  date_from?: string
  date_to?: string
  nm_id?: string
  supplier_article?: string
  brand?: string
  category?: string
  card_title?: string
  g_number?: string
  is_cancel?: number | string
  sort?: string
  page?: number
  page_size?: number
}

export const wbOrdersApi = {
  async list(params: WbOrderListParams): Promise<{ items: WbOrderRow[]; total: number; page: number; page_size: number }> {
    const { data } = await api.get('/api/wb-orders', { params })
    return data
  },
  async get(id: number): Promise<WbOrderRow> {
    const { data } = await api.get(`/api/wb-orders/${id}`)
    return data
  },
}
