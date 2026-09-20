import { api } from '../api/client'

export interface CmsBlock {
  key: string; title: string; body_md: string; updated_at?: string;
}

export const cmsApi = {
  get: (key: string) =>
    api.get(`/api/cms/blocks/${encodeURIComponent(key)}`).then((r) => r.data as CmsBlock),
  put: (key: string, payload: { title?: string; body_md: string }) =>
    api.put(`/api/cms/blocks/${encodeURIComponent(key)}`, payload).then((r) => r.data as CmsBlock),
}
