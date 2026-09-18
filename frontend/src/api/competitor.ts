import { api } from './client'

export interface CompetitorSourceRow {
  source_nm_id: number; cnt: number; phrases: number; analyzed: number;
  title: string | null; brand: string | null; vendor_code: string | null; photo: string | null;
}

export interface CompetitorQuery { phrase: string; position: number | null; status?: string; id?: number }
export interface CompetitorDetail {
  nm_id: number; queries: CompetitorQuery[];
  detail?: { title?: string; description?: string; brand?: string; seller?: string; price?: string; old_price?: string; url?: string } | null;
  analysis?: { id: number; status: string; ai_result?: any } | null;
}

export const competitorApi = {
  sources: () =>
    api.get('/api/competitors').then((r) => r.data as { rows: CompetitorSourceRow[] }),
  phrases: (nmId: number) =>
    api.get(`/api/competitors/${nmId}/phrases`).then((r) => r.data as {
      nm_id: number; phrases: string[]; selected: string[]; card: { title?: string; brand?: string } | null;
    }),
  select: (nmId: number, phrases: string[], positionMax: number) =>
    api.post(`/api/competitors/${nmId}/select`, { phrases, position_max: positionMax }).then((r) => r.data as { saved: number }),
  selected: (nmId: number) =>
    api.get(`/api/competitors/${nmId}/selected`).then((r) => r.data as {
      nm_id: number; card: { title?: string; brand?: string } | null;
      competitors: CompetitorDetail[]; position_max: number;
    }),
  results: (nmId: number) =>
    api.get(`/api/competitors/${nmId}/results`).then((r) => r.data as {
      nm_id: number;
      card: { nmID?: number; title?: string; brand?: string; vendor_code?: string | null; photo?: string | null } | null;
      competitors: Array<{
        nm_id: number; title?: string | null; brand?: string | null; seller?: string | null;
        price?: number | null; rating?: number | null; feedbacks?: number | null;
        image?: string | null; url?: string | null; description?: string | null;
        phrases: CompetitorQuery[]; analysis?: { id: number; status: string } | null;
        has_analysis: boolean; ai_result?: any; model?: string | null; analyzed_at?: string | null;
      }>;
    }),
  remove: (sourceNmId: number, nmId: number) =>
    api.post('/api/competitors/remove', { source_nm_id: sourceNmId, nm_id: nmId }).then((r) => r.data),
  analyze: (id: number) =>
    api.post('/api/competitors/analyze', { id }).then((r) => r.data as { job_id: number }),
  analyzeDirect: (sourceNmId: number, competitorNmId: number) =>
    api.post('/api/competitors/analyze-direct', { source_nm_id: sourceNmId, competitor_nm_id: competitorNmId }).then((r) => r.data as { job_id: number }),
  analyzeAll: (nmId: number) =>
    api.post(`/api/competitors/${nmId}/analyze-all`).then((r) => r.data as { job_id: number }),
  summary: (nmId: number, force = false) =>
    api.post(`/api/competitors/${nmId}/summary`, { force }).then((r) => r.data as {
      success: boolean; error?: string; result?: any; cached?: boolean;
      competitor_count?: number; cached_at?: string; cached_model?: string;
      can_recalc?: boolean; cache_age_days?: number | null;
    }),
}
