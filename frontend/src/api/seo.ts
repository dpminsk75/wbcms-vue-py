import { api } from './client'

export interface SeoCard {
  nmID: number; title?: string | null; subjectName?: string | null;
  brand?: string | null; vendorCode?: string | null; photo?: string | null;
}

export interface SeoRec {
  id: number; company_id: number; nmID: number;
  old_title?: string | null; old_description?: string | null;
  new_title?: string | null; new_description?: string | null;
  rationale?: string | null; keywords_added?: string[]; keywords_removed?: string[];
  confidence?: number | null; model?: string | null;
  prompt_tokens?: number | null; completion_tokens?: number | null;
  status: 'new' | 'viewed'; created_at?: string; updated_at?: string;
  card?: SeoCard | null; phrases_count?: number;
}

export interface SeoTarget { id: number; nmID: number; phrase: string; priority: number; is_active: number }

export const seoApi = {
  list: (status = 'new', q = '', page = 1) =>
    api.get('/api/seo/recommendations', { params: { status, q, page } }).then((r) => r.data as {
      items: SeoRec[]; total: number; page: number; page_size: number;
      counts: { new: number; viewed: number }; status: string; q: string;
    }),
  unprocessed: (q = '') =>
    api.get('/api/seo/unprocessed', { params: { q } }).then((r) => r.data as {
      items: Array<{ nmID: number; title?: string; subjectName?: string; brand?: string; vendorCode?: string; photo?: string | null; total_qnt: number }>;
    }),
  cards: (q: string) =>
    api.get('/api/seo/cards', { params: { q } }).then((r) => r.data as {
      items: SeoCard[]; total: number; all_ids: number[];
    }),
  view: (id: number) =>
    api.get(`/api/seo/recommendations/${id}`).then((r) => r.data as SeoRec & { targets: SeoTarget[]; raw_json?: any }),
  markViewed: (id: number) =>
    api.post(`/api/seo/recommendations/${id}/viewed`).then((r) => r.data),
  requeue: (id: number) =>
    api.post(`/api/seo/recommendations/${id}/requeue`).then((r) => r.data),
  addTarget: (nmID: number, phrase: string) =>
    api.post('/api/seo/targets', { nmID, phrase }).then((r) => r.data as { id: number }),
  removeTarget: (id: number) =>
    api.delete(`/api/seo/targets/${id}`).then((r) => r.data),
  process: (nm_ids: number[]) =>
    api.post('/api/seo/process', { nm_ids }).then((r) => r.data as { job_id: number }),
}
