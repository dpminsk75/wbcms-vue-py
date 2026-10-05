import { api } from './client'

export interface FbsPvzParams {
  date_from: string
  date_to: string
  nm_id?: string
  brand?: string
  category?: string
  top_dirs?: number
}

export const fbsPvzApi = {
  async summary(params: FbsPvzParams): Promise<any> {
    const { data } = await api.get('/api/fbs/pvz/summary', { params })
    return data
  },
}
