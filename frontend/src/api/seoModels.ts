import { api } from '../api/client'

export interface SeoModelRow {
  id: number; model_id: string; title?: string | null; is_active: boolean;
  priority?: number | null; ctx?: number | null;
  success_count?: number | null; error_count?: number | null; consecutive_errors?: number | null;
  cooldown_until?: string | null; last_error?: string | null;
  last_success_at?: string | null; last_429_at?: string | null;
}

export interface SeoModelsApplyOut {
  model_id: string; replaced: number; dry_run: boolean;
  companies: Array<number | { company_id: number; old: string; new: string }>;
}

export const seoModelsApi = {
  list: () => api.get('/api/admin/seo-models').then((r) => r.data as SeoModelRow[]),
  patch: (modelId: string, payload: { is_active?: boolean; priority?: number }) =>
    api.patch(`/api/admin/seo-models/${encodeURIComponent(modelId)}`, payload).then((r) => r.data as SeoModelRow),
  resetCooldown: (modelId: string) =>
    api.post(`/api/admin/seo-models/${encodeURIComponent(modelId)}/reset-cooldown`).then((r) => r.data as { ok: boolean }),
  apply: (modelId: string, dryRun = false) =>
    api.post('/api/admin/seo-models/apply', { model_id: modelId, dry_run: dryRun }).then((r) => r.data as SeoModelsApplyOut),
}
