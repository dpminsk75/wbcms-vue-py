import { api } from './client'

export interface YearCompareRow {
  nm_id: number
  title: string
  brand: string
  subject: string
  vendor_code: string
  photos: any
  qty: Record<string, number>
  amount: Record<string, number>
  avg_price: Record<string, number>
}

export interface YearCompareResponse {
  tab: 'orders' | 'sales'
  available_years: number[]
  years: number[]
  meta: {
    prev_month?: { num: number; name: string; years: number[] }
    curr_month?: { num: number; name: string; day: number }
    today?: string
    nm_id?: number | null
  }
  summary_prev: Array<{ year: number; qty: number; amount: number; change: number | null }>
  summary_curr: Array<{ year: number; qty: number; amount: number; change: number | null }>
  summary_year: Array<{ year: number; qty: number; amount: number; change: number | null }>
  months: Array<Record<string, any>>
  top_prev: YearCompareRow[]
  top_curr: YearCompareRow[]
}

export const reportsApi = {
  /** Сравнение заказов/продаж по годам (порты Yii2 AggOrders/AggSalesReportController). */
  async yearCompare(
    tab: 'orders' | 'sales' = 'orders',
    years: number[] = [],
    nmId?: number | null,
  ): Promise<YearCompareResponse> {
    const { data } = await api.get('/api/reports/year-compare', {
      params: {
        tab,
        years: years.length ? years.join(',') : undefined,
        nm_id: nmId || undefined,
      },
    })
    return data
  },
}
