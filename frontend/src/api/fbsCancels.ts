import { api } from './client'

export interface FbsCancelsParams {
  date_from: string
  date_to: string
  nm_id?: string
  brand?: string
  category?: string
}

export const fbsCancelsApi = {
  async summary(params: FbsCancelsParams): Promise<any> {
    const { data } = await api.get('/api/fbs/cancels/summary', { params })
    return data
  },
  async byWarehouse(params: FbsCancelsParams): Promise<{ items: any[] }> {
    const { data } = await api.get('/api/fbs/cancels/by-warehouse', { params })
    return data
  },
  async orders(params: FbsCancelsParams & { bucket: string; warehouse_id?: number | string }): Promise<{ bucket: string; items: any[] }> {
    const { data } = await api.get('/api/fbs/cancels/orders', { params })
    return data
  },
}
