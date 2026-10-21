import { api } from './client'

/** Конкуренты (новый товар) — /api/competitors/new-cards (§9 плана 2026-10-20). */

export interface NewCardRow {
  nmID: number
  title?: string | null
  brand?: string | null
  vendor_code?: string | null
  subject_name?: string | null
  photo?: string | null
  desc_len: number
  seen_at?: string | null
  targets_cnt: number
  queries_cnt: number
  competitors_cnt: number
  content_cnt: number
  analyzed_cnt: number
  phrases_cnt: number
  selected_cnt: number
  summary_cnt: number
}

export interface NewCardPhrase {
  id: number
  phrase: string
  source: 'ai' | 'db' | 'manual' | string
  hit_cnt: number
  orders: number
  freq: number
  cards_cnt: number
  in_db: boolean
  is_selected: boolean
  in_targets: boolean
  model?: string | null
  created_at?: string | null
}

export interface NewCardGenerateResult {
  title: string
  description: string
  title_len: number
  desc_len: number
  phrases: string[]
  phrases_used?: string[]
  phrases_missing?: string[]
  model?: string | null
  competitor_count: number
  desc_min: number
  desc_max: number
  prompt_source?: string
  prompt_version?: string
  desc_warning?: boolean
}

export interface NewCardRunStatus {
  run_id: string
  kind: 'phrases' | 'generate' | string
  status: 'running' | 'done' | 'error'
  attempt: number
  total: number
  model?: string | null
  error?: string | null
  is_free: boolean
  created_at?: string
  updated_at?: string
}

export interface NewCardDetail {
  card: {
    nmID: number; company_id?: number | null; title?: string | null; brand?: string | null
    vendor_code?: string | null; subject_name?: string | null; photo?: string | null
    description?: string | null; desc_len: number
    characteristics?: Array<{ name?: string; value?: string[] | string }>
  }
  counts: {
    targets_cnt: number; queries_cnt: number; competitors_cnt: number
    content_cnt: number; analyzed_cnt: number; phrases_cnt: number; selected_cnt: number
  }
  summary: { suggested_title?: string | null; suggested_description?: string | null; competitor_count?: number; model?: string | null; created_at?: string } | null
  targets: Array<{ id: number; nmID: number; phrase: string; priority: number; is_active: number }>
  queries: CompetitorQuery[]
  competitors: CompetitorRow[]
  phrases: NewCardPhrase[]
}

export interface CompetitorQuery {
  id: number; phrase: string; priority: number; is_active: number
  source: string; status: 'pending' | 'processing' | 'done' | 'error'
  added_by?: number | null; created_at?: string
}

export interface CompetitorQuerySuggest {
  phrase: string; orders: number; freq: number; cards: number; added: boolean
}

export interface CompetitorRow {
  nm_id: number
  title?: string | null
  brand?: string | null
  seller?: string | null
  price?: string | number | null
  old_price?: string | null
  photo?: string | null
  desc_len: number
  chars_cnt: number
  collected_at?: string | null
  analysis_status?: string | null
  sources: string[]
  phrases?: string | null
  manual: boolean
}

export interface CapturedAttachedCard {
  nm_id: number
  title?: string | null
}

export interface CapturedRow {
  nm_id: number
  title?: string | null
  brand?: string | null
  seller?: string | null
  price?: string | null
  old_price?: string | null
  url?: string | null
  photo?: string | null
  desc_len: number
  chars_cnt: number
  collected_at?: string | null
  first_seen_at?: string | null
  last_seen_at?: string | null
  companies_cnt: number
  is_own: boolean
  is_hidden: boolean
  attached: CapturedAttachedCard[]
  attached_cnt: number
  history_cnt: number
}

export interface CapturedHistoryItem {
  id: number
  nm_id: number
  title?: string | null
  brand?: string | null
  seller?: string | null
  price?: string | null
  old_price?: string | null
  content_hash: string
  source: string
  captured_company_id?: number | null
  captured_by?: number | null
  created_at?: string | null
  characteristics: Array<{ name?: string; value?: string[] | string }>
  desc_len: number
  chars_cnt: number
  description_preview: string
}

export const competitorsNewcardApi = {
  list: (q = '', limit = 200, includeAll = false) =>
    api.get('/api/competitors/new-cards', { params: { q, limit, include_all: includeAll } })
      .then((r) => r.data as { items: NewCardRow[]; total: number; desc_min_len: number }),

  detail: (nm: number) =>
    api.get(`/api/competitors/new-cards/${nm}`).then((r) => r.data as NewCardDetail),

  queries: (nm: number) =>
    api.get(`/api/competitors/new-cards/${nm}/queries`)
      .then((r) => r.data as { nm_id: number; items: CompetitorQuery[] }),

  suggest: (nm: number, q: string) =>
    api.get(`/api/competitors/new-cards/${nm}/queries/suggest`, { params: { q } })
      .then((r) => r.data as { items: CompetitorQuerySuggest[]; added: string[]; subject_name: string }),

  addQuery: (nm: number, phrase: string) =>
    api.post(`/api/competitors/new-cards/${nm}/queries`, { phrase }).then((r) => r.data as { id: number }),

  removeQuery: (nm: number, qid: number) =>
    api.delete(`/api/competitors/new-cards/${nm}/queries/${qid}`).then((r) => r.data),

  competitors: (nm: number) =>
    api.get(`/api/competitors/new-cards/${nm}/competitors`)
      .then((r) => r.data as { nm_id: number; items: CompetitorRow[] }),

  addCompetitors: (nm: number, nm_ids: number[]) =>
    api.post(`/api/competitors/new-cards/${nm}/competitors`, { nm_ids })
      .then((r) => r.data as { added: number; requested: number; nm_ids: number[] }),

  fromCard: (nm: number, source_nm_id: number) =>
    api.post(`/api/competitors/new-cards/${nm}/competitors/from-card`, { source_nm_id })
      .then((r) => r.data as { added: number; source_nm_id: number }),

  detachCompetitor: (nm: number, competitorNm: number) =>
    api.delete(`/api/competitors/new-cards/${nm}/competitors/${competitorNm}`).then((r) => r.data),

  // ---------- Ш11: фразы + генерация ----------

  phrases: (nm: number) =>
    api.get(`/api/competitors/new-cards/${nm}/phrases`)
      .then((r) => r.data as { nm_id: number; items: NewCardPhrase[]; selected_cnt: number }),

  analyzePhrases: (nm: number, runId?: string) =>
    api.post(`/api/competitors/new-cards/${nm}/phrases/analyze`, { run_id: runId || '' }, { timeout: 600000 })
      .then((r) => r.data as {
        items: NewCardPhrase[]; selected_cnt: number; model?: string
        competitors_cnt?: number; prompt_version?: string
      }),

  selectPhrases: (nm: number, phrases: string[], selected = true) =>
    api.post(`/api/competitors/new-cards/${nm}/phrases/select`, { phrases, selected })
      .then((r) => r.data as { updated: number; selected: boolean }),

  addPhrase: (nm: number, phrase: string) =>
    api.post(`/api/competitors/new-cards/${nm}/phrases`, { phrase })
      .then((r) => r.data as { phrase: string; in_db: boolean }),

  removePhrase: (nm: number, pid: number) =>
    api.delete(`/api/competitors/new-cards/${nm}/phrases/${pid}`).then((r) => r.data),

  generate: (nm: number, phrases?: string[], runId?: string) =>
    api.post(`/api/competitors/new-cards/${nm}/generate`,
      { phrases: phrases || [], run_id: runId || '' }, { timeout: 600000 })
      .then((r) => r.data as NewCardGenerateResult & { success: boolean }),

  runStatus: (nm: number, runId: string) =>
    api.get(`/api/competitors/new-cards/${nm}/runs/${runId}`)
      .then((r) => r.data as NewCardRunStatus),

  // ---------- «Собранные карточки» (capture, §8.5) ----------

  captured: (q = '', includeHidden = false, limit = 300) =>
    api.get('/api/competitors/captured', { params: { q, include_hidden: includeHidden, limit } })
      .then((r) => r.data as { items: CapturedRow[]; total: number }),

  capturedHistory: (nm: number, limit = 50) =>
    api.get(`/api/competitors/captured/${nm}/history`, { params: { limit } })
      .then((r) => r.data as { nm_id: number; items: CapturedHistoryItem[] }),

  attachCaptured: (nm: number, source_nm_id: number) =>
    api.post(`/api/competitors/captured/${nm}/attach`, { source_nm_id })
      .then((r) => r.data as { attached: number; source_nm_id: number; exists: boolean }),

  detachCaptured: (nm: number, source_nm_id: number) =>
    api.post(`/api/competitors/captured/${nm}/detach`, { source_nm_id })
      .then((r) => r.data as { detached: number; source_nm_id: number }),

  hideCaptured: (nm: number, hidden = true) =>
    api.post(`/api/competitors/captured/${nm}/hide`, null, { params: { hidden } })
      .then((r) => r.data as { nm_id: number; is_hidden: boolean }),
}
