import { api } from './client'

export interface FbsSummaryParams {
  date_from: string
  date_to: string
  nm_id?: string
  brand?: string
  category?: string
}

export const fbsApi = {
  async summary(params: FbsSummaryParams): Promise<any> {
    const { data } = await api.get('/api/fbs/summary', { params })
    return data
  },
  async options(date_from: string, date_to: string): Promise<{ brands: string[]; categories: string[] }> {
    const { data } = await api.get('/api/fbs/options', { params: { date_from, date_to } })
    return data
  },
  async breakdown(params: FbsSummaryParams & { mode: string }): Promise<{ mode: string; items: any[] }> {
    const { data } = await api.get('/api/fbs/breakdown', { params })
    return data
  },
}
