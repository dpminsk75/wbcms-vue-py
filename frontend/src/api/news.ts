import { api } from '../api/client'

export interface NewsType {
  id: number; name: string;
}

export interface NewsRow {
  id: number; date: string | null; header: string; content: string;
  types: NewsType[]; is_read: boolean;
}

export const newsApi = {
  feed: (days = 3, limit = 12) =>
    api.get('/api/news', { params: { days, limit } }).then((r) => r.data as NewsRow[]),
  all: (params: { date_from?: string; date_to?: string; types?: string; limit?: number; q?: string }) =>
    api.get('/api/news/all', { params }).then((r) => r.data as NewsRow[]),
  types: () => api.get('/api/news/types').then((r) => r.data as NewsType[]),
  markRead: (id: number) => api.post(`/api/news/${id}/read`).then((r) => r.data),
  companyTypes: (cid: number) =>
    api.get(`/api/companies/${cid}/news-types`).then((r) => r.data as { type_ids: number[]; available: NewsType[] }),
  saveCompanyTypes: (cid: number, typeIds: number[]) =>
    api.put(`/api/companies/${cid}/news-types`, { type_ids: typeIds }).then((r) => r.data),
}
