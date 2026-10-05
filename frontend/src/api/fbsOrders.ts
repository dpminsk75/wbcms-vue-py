import { api } from './client'

export interface FbsOrdersParams {
  date_from: string
  date_to: string
  warehouse_id?: number | string
  brand?: string
  category?: string
}

export const fbsOrdersApi = {
  async warehouses(): Promise<{ warehouse_id: number | null; name: string }[]> {
    const { data } = await api.get('/api/fbs/orders/warehouses')
    return data
  },
  async economy(params: FbsOrdersParams): Promise<any> {
    const { data } = await api.get('/api/fbs/orders/economy', { params })
    return data
  },
  async dynamics(params: FbsOrdersParams): Promise<{ days: any[] }> {
    const { data } = await api.get('/api/fbs/orders/dynamics', { params })
    return data
  },
  async assembly(params: FbsOrdersParams): Promise<any> {
    const { data } = await api.get('/api/fbs/orders/assembly', { params })
    return data
  },
}
