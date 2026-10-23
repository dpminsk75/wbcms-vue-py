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

export interface PhraseCompetitor {
  nm_id: number
  title?: string | null
}

export interface NewCardPhrase {
  id: number
  phrase: string
  source: 'ai' | 'db' | 'manual' | string
  hit_cnt: number
  variants_cnt: number
  variants: string[]
  competitors: PhraseCompetitor[]
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
  phase?: 'extract' | 'merge' | string | null
  done_ids?: string | null
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
  added_by?: number | null; created_at?: string; updated_at?: string
  found_cnt?: number
  best_position?: number | null
}

export interface CompetitorQuerySuggest {
  phrase: string; orders: number; freq: number; cards: number; added: boolean
}

export type QueueStatus = 'pending' | 'processing' | 'done' | 'error' | 'need_update'

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
  queue_status?: QueueStatus | null
  queue_error?: string | null
  queue_processed_at?: string | null
  sources: string[]
  phrases?: string | null
  manual: boolean
  // §13.1: поведение для таблицы конкурентов
  price_delta_7d?: number | null
  shelves_cnt?: number
  shelf_anchors_cnt?: number
  shelf_avg_pos?: number | null
  shelf_best_pos?: number | null
  clips_cnt?: number
  clips_last_at?: string | null
  clips_authors_cnt?: number
  top10_cnt?: number
  phrases_cnt?: number
  best_pos?: number | null
  dup_min_price?: number | null
  dup_gap_pct?: number | null
  dup_offers_total?: number
  badges?: string[]
  last_activity_at?: string | null
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

export interface WbCardOption {
  nmID: number
  vendorCode?: string | null
  title?: string | null
  brand?: string | null
  photos?: unknown
}

// ---------- §16: подбор конкурентов и массовая привязка ----------

export interface PickCard {
  nmID: number
  company_id?: number | null
  title?: string | null
  brand?: string | null
  vendor_code?: string | null
  subject_name?: string | null
  photo?: string | null
  competitors_cnt: number
  content_cnt: number
}

export interface PickAttachedCard {
  nm_id: number
  title?: string | null
  source?: string | null
}

export type PickMode = 'recommend' | 'competitors' | 'captured'
export type PickSort = 'relevance' | 'title_asc' | 'title_desc'

export interface PickRecommendedBy {
  nm_id: number
  title?: string | null
  source_nm_ids: number[]
}

export interface PickCandidate {
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
  in_a: boolean
  rec_cnt: number
  recommended_by: number[]
  recommended_by_cards: PickRecommendedBy[]
  source_nm_ids: number[]
  captured: boolean
  is_own: boolean
  is_hidden: boolean
  attached_to: PickAttachedCard[]
  queue_status?: QueueStatus | null
  queue_error?: string | null
  queue_processed_at?: string | null
  sources: string[]
  has_content: boolean
  visible: boolean
  can_attach: boolean
}

export interface PickPool {
  items: PickCandidate[]
  total: number
  mode: PickMode
  source_nm_ids: number[]
  offset: number
  limit: number
  sort: PickSort
  desc_min_len: number
  counts: { a_cnt: number; rec_cnt: number; captured_cnt: number }
}

export interface PickAttachResult {
  added: number
  exists: number
  skipped: number
  requested: number
  mode: string
  target_nm_ids: number[]
  skipped_candidates: Array<{ nm_id: number; reason: string }>
  errors: Array<{ nm_id?: number; target_nm_id?: number; error?: string }>
}

// ---------- §17.2: повторный обход устаревших конкурентов ----------

export type RefreshStatus = 'stale' | 'assigned' | 'queued' | 'processing' | 'error'

export interface RefreshRow {
  nm_id: number
  title?: string | null
  brand?: string | null
  seller?: string | null
  photo?: string | null
  collected_at?: string | null
  days_old: number
  attached_to: PickAttachedCard[]
  attached_cnt: number
  captured: boolean
  is_hidden: boolean
  queue_status?: QueueStatus | null
  queue_error?: string | null
  queue_processed_at?: string | null
  requested_at?: string | null
  ui_status: RefreshStatus
}

export interface RefreshList {
  items: RefreshRow[]
  total: number
  days: number
  counts: Record<RefreshStatus, number>
  offset: number
  limit: number
}

export interface RefreshAssignResult {
  assigned: number
  already: number
  in_progress: number
  skipped: number
  requested: number
  days: number
  skipped_candidates: Array<{ nm_id: number; reason: string }>
  errors: Array<{ nm_id?: number; error?: string }>
}

export interface CompetitorPhrase {
  phrase_id?: number | null
  phrase: string
  canon?: string | null
  source_nm_id: number
  source_title?: string | null
  source_vendor_code?: string | null
  is_selected?: boolean
  hit_cnt?: number
  variants_cnt?: number
  /** Фраза есть в нашей базе поисковых запросов — WB её отдаёт. */
  in_db?: boolean
  orders?: number
  freq?: number
  cards_cnt?: number
  model?: string | null
  created_at?: string | null
}

export interface CompetitorDetail {
  nm_id: number
  title?: string | null
  description?: string | null
  brand?: string | null
  seller?: string | null
  subject_name?: string | null
  url?: string | null
  price?: string | number | null
  old_price?: string | number | null
  images: string[]
  preview_image?: string | null
  photo?: string | null
  characteristics: Array<{ name?: string; value?: string[] | string }>
  collected_at?: string | null
  first_collected_at?: string | null
  attached_to: PickAttachedCard[]
  attached_cnt: number
  price_history: Array<{ price?: string | null; old_price?: string | null; at?: string | null }>
  positions?: CompetitorPosition[]
  badges?: string[]
  rating?: number | null
  feedbacks?: number | null
  questions?: number | null
  full_collected_at?: string | null
  phrases?: CompetitorPhrase[]
  shelves?: CompetitorShelves
  clips?: CompetitorClip[]
  clips_cnt?: number
  clips_authors_cnt?: number
  clips_last_at?: string | null
  duplicates?: CompetitorDuplicates | null
  compare?: CompetitorCompare | null
}

export interface CompetitorShelfItem {
  anchor_nm: number
  anchor_title?: string
  preset_id: number
  preset_type?: string
  dest?: number | string | null
  shelf_title?: string
  snapshot_date?: string | null
  position?: number | null
  price?: number | null
  seller?: string | null
}

export interface CompetitorShelfAnchor {
  preset_id: number
  preset_type?: string
  dest?: number | string | null
  shelf_title?: string
  items_cnt?: number
  avg_price?: number | null
  total_candidates?: number | null
  pages_loaded?: number | null
  is_partial?: boolean | number | null
  last_seen_at?: string | null
}

export interface CompetitorShelves {
  as_item: CompetitorShelfItem[]
  as_anchor: CompetitorShelfAnchor[]
  counts: {
    shelves_cnt: number
    anchors_cnt: number
    avg_pos: number | null
    best_pos: number | null
  }
}

export interface CompetitorClip {
  clip_id: number
  type?: string | null
  name?: string | null
  description?: string | null
  duration_s?: number | string | null
  publication_date?: string | null
  author_id?: number | null
  author_name?: string | null
  author_verified?: boolean | number | null
  preview_url?: string | null
  public_url?: string | null
  author_url?: string | null
  nm_count?: number | null
}

export interface CompetitorDuplicateOffer {
  nm_id: number
  name?: string | null
  price?: number | null
  seller?: string | null
  is_anchor?: boolean | number | null
  is_min_price?: boolean | number | null
  price_gap_pct?: number | null
}

export interface CompetitorDuplicates {
  match_id: number
  anchor_nm?: number | null
  anchor_title?: string
  anchor_price?: number | null
  my_price?: number | null
  min_price?: number | null
  min_price_nm?: number | null
  min_price_title?: string
  price_gap_pct?: number | null
  offers_total?: number | null
  snapshot_date?: string | null
  offers: CompetitorDuplicateOffer[]
}

export interface CompetitorCompare {
  nm_id: number
  title?: string | null
  price?: number | string | null
  old_price?: number | string | null
  rating?: number | null
  feedbacks?: number | null
  badges?: string[]
  desc_len?: number
  chars_cnt?: number
  clips_cnt?: number
  collected_at?: string | null
}

export interface CompetitorPosition {
  phrase: string
  source_nm_id: number
  source_title?: string
  last_position?: number | null
  last_price?: number | null
  at?: string | null
  days?: number
  positions: Array<{ position?: number | null; price?: number | null; at?: string | null }>
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

  resetQueries: (nm: number) =>
    api.post(`/api/competitors/new-cards/${nm}/queries/reset`).then((r) => r.data as { reset: number }),

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

  competitorDetails: (nm: number, competitorNm: number) =>
    api.get(`/api/competitors/new-cards/${nm}/competitors/${competitorNm}/details`)
      .then((r) => r.data as CompetitorDetail),

  // поиск наших карточек для привязки (nmID / vendorCode / title)
  searchCards: (q = '', limit = 30) =>
    api.get('/api/wb/cards', { params: { q, limit } }).then((r) => {
      const d = r.data
      return (Array.isArray(d) ? d : (d?.items ?? [])) as WbCardOption[]
    }),

  // ---------- Ш11: фразы + генерация ----------

  phrases: (nm: number) =>
    api.get(`/api/competitors/new-cards/${nm}/phrases`)
      .then((r) => r.data as { nm_id: number; items: NewCardPhrase[]; selected_cnt: number; raw_cnt?: number }),

  analyzePhrases: (nm: number, runId?: string) =>
    api.post(`/api/competitors/new-cards/${nm}/phrases/analyze`, { run_id: runId || '' }, { timeout: 600000 })
      .then((r) => r.data as {
        items: NewCardPhrase[]; selected_cnt: number; model?: string
        competitors_cnt?: number; prompt_version?: string
        merge_prompt_version?: string; prompt_source?: string
        analyzed_cnt?: number; cached_cnt?: number
        groups_cnt?: number; raw_cnt?: number; merged_cnt?: number
        errors?: string[]
      }),

  mergePhrases: (nm: number, runId?: string) =>
    api.post(`/api/competitors/new-cards/${nm}/phrases/merge`, { run_id: runId || '' }, { timeout: 300000 })
      .then((r) => r.data as {
        items: NewCardPhrase[]; selected_cnt: number
        groups_cnt?: number; raw_cnt?: number; merged_cnt?: number; errors?: string[]
        merge_prompt_version?: string
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

  // ---------- §16: подбор конкурентов и массовая привязка ----------

  pickCards: (q = '', limit = 50) =>
    api.get('/api/competitors/pick/cards', { params: { q, limit } })
      .then((r) => r.data as { items: PickCard[]; total: number; desc_min_len: number }),

  pickCandidates: (params: {
    source_nm_ids?: string
    mode?: PickMode
    q?: string
    only_content?: boolean
    only_recommended?: boolean
    limit?: number
    offset?: number
    sort?: PickSort
  }) =>
    api.get('/api/competitors/pick/candidates', { params })
      .then((r) => r.data as PickPool),

  pickDetails: (nm: number) =>
    api.get(`/api/competitors/pick/candidates/${nm}/details`)
      .then((r) => r.data as CompetitorDetail),

  pickAttach: (payload: { nm_ids: number[]; target_nm_ids: number[]; mode?: PickMode }) =>
    api.post('/api/competitors/pick/attach', payload)
      .then((r) => r.data as PickAttachResult),

  // ---------- «Собранные карточки» (capture, §8.5) ----------

  captured: (q = '', includeHidden = false, limit = 300) =>
    api.get('/api/competitors/captured', { params: { q, include_hidden: includeHidden, limit } })
      .then((r) => r.data as { items: CapturedRow[]; total: number }),

  capturedHistory: (nm: number, limit = 50) =>
    api.get(`/api/competitors/captured/${nm}/history`, { params: { limit } })
      .then((r) => r.data as { nm_id: number; items: CapturedHistoryItem[] }),

  capturedDetails: (nm: number) =>
    api.get(`/api/competitors/captured/${nm}/details`)
      .then((r) => r.data as CompetitorDetail),

  attachCaptured: (nm: number, source_nm_id: number) =>
    api.post(`/api/competitors/captured/${nm}/attach`, { source_nm_id })
      .then((r) => r.data as { attached: number; source_nm_id: number; exists: boolean }),

  detachCaptured: (nm: number, source_nm_id: number) =>
    api.post(`/api/competitors/captured/${nm}/detach`, { source_nm_id })
      .then((r) => r.data as { detached: number; source_nm_id: number }),

  hideCaptured: (nm: number, hidden = true) =>
    api.post(`/api/competitors/captured/${nm}/hide`, null, { params: { hidden } })
      .then((r) => r.data as { nm_id: number; is_hidden: boolean }),

  // ---------- §17.2: повторный обход устаревших конкурентов ----------

  refreshList: (params: {
    days?: number
    q?: string
    only_captured?: boolean
    include_hidden?: boolean
    source_nm_id?: number | null
    status?: string
    limit?: number
    offset?: number
  }) =>
    api.get('/api/competitors/refresh', { params })
      .then((r) => r.data as RefreshList),

  refreshAssign: (nm_ids: number[], days = 30) =>
    api.post('/api/competitors/refresh/assign', { nm_ids, days })
      .then((r) => r.data as RefreshAssignResult),
}
