import { api } from './client'

export interface FbsCommissionParams {
  date_from: string
  date_to: string
  nm_id?: string
  brand?: string
  category?: string
}

export const fbsCommissionApi = {
  async summary(params: FbsCommissionParams): Promise<any> {
    const { data } = await api.get('/api/fbs/commission/summary', { params })
    return data
  },
}
