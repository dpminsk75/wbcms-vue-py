import { api } from '../api/client'

export interface ExtToken {
  id: number; company_id: number; name: string; token_prefix: string;
  is_active: boolean; last_used_at: string | null; created_by: number | null;
  created_at?: string;
  /** Сырой токен — только в ответе create, показать один раз. */
  token?: string;
}

export interface ExtDiagSummary {
  nm_id: number | null; h2_count: number; sections_count: number;
  catalog_links: number; popup_cards: number;
}

export interface ExtCategoryFilter {
  id: number; company_id?: number; name: string; subjects: string; is_active?: boolean;
}

export const extTokensApi = {
  list: (companyId: number) =>
    api.get(`/api/companies/${companyId}/ext-tokens`).then((r) => r.data as ExtToken[]),
  create: (companyId: number, name: string) =>
    api.post(`/api/companies/${companyId}/ext-tokens`, { name }).then((r) => r.data as ExtToken),
  revoke: (companyId: number, tokenId: number) =>
    api.delete(`/api/companies/${companyId}/ext-tokens/${tokenId}`).then((r) => r.data as { ok: boolean }),
  diagList: (companyId: number) =>
    api.get(`/api/companies/${companyId}/ext-diag`).then((r) => r.data as ExtDiagSummary[]),
  diagView: (companyId: number, nmId: number) =>
    api.get(`/api/companies/${companyId}/ext-diag/${nmId}`).then((r) => r.data as any),
  /** Скачивание zip расширения (SERVER уже вшит бэком). Качает через blob — с JWT из interceptor. */
  download: async (companyId: number) => {
    const r = await api.get(`/api/companies/${companyId}/ext-download`, { responseType: 'blob' })
    const cd = String(r.headers?.['content-disposition'] || '')
    const m = cd.match(/filename="([^"]+)"/)
    const name = m ? m[1] : 'wb-competitor-parser.zip'
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  },
}

export const extCategoryApi = {
  list: (companyId: number) =>
    api.get(`/api/companies/${companyId}/ext-filters`).then((r) => r.data as ExtCategoryFilter[]),
  create: (companyId: number, payload: { name: string; subjects: string }) =>
    api.post(`/api/companies/${companyId}/ext-filters`, payload).then((r) => r.data as ExtCategoryFilter),
  update: (companyId: number, fid: number, payload: { name?: string; subjects?: string; is_active?: boolean }) =>
    api.patch(`/api/companies/${companyId}/ext-filters/${fid}`, payload).then((r) => r.data as ExtCategoryFilter),
  remove: (companyId: number, fid: number) =>
    api.delete(`/api/companies/${companyId}/ext-filters/${fid}`).then((r) => r.data as { ok: boolean }),
}
