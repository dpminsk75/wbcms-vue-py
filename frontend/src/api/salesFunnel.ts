import { api } from './client'

export interface SalesFunnelRow {
  date: string
  nm_id: number
  card_name: string
  vendor_code: string
  brand: string
  subject: string
  open_count: number
  cart_count: number
  open_to_cart: number | null
  order_count: number
  cart_to_order: number | null
  order_sum: number
  avg_order: number
  buyout_count: number
  order_to_buyout: number | null
  buyout_sum: number
}

export interface SalesFunnelChartRow {
  date: string
  open_count: number
  cart_count: number
  order_count: number
  order_sum: number
  buyout_count: number
  buyout_sum: number
}

export interface SalesFunnelTotals {
  open_count: number
  cart_count: number
  order_count: number
  order_sum: number
  buyout_count: number
  buyout_sum: number
  open_to_cart: number | null
  cart_to_order: number | null
  order_to_buyout: number | null
}

export interface SalesFunnelData {
  card: any
  rows: SalesFunnelRow[]
  chartData: SalesFunnelChartRow[]
  totals: SalesFunnelTotals
  params: {
    nm_id: number
    date_from: string
    date_to: string
  }
}

export const salesFunnelApi = {
  get: (params: { nm_id: number; date_from: string; date_to: string }) =>
    api.get<SalesFunnelData>('/api/wb-sales-funnel/wbcard', { params }).then(response => response.data),
  exportExcel: (params: { nm_id: number; date_from: string; date_to: string }) =>
    api.get(`/api/wb-sales-funnel/wbcard/export`, { params, responseType: 'blob' }).then(response => response.data),
}
