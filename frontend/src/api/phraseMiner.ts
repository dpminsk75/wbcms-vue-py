import { api } from './client'

export interface MinerQueueTot {
  calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  failed: number
  /** «$» — только глобальному админу (can_see_cost); иначе ключа нет */
  cost?: number
}

export interface MinerLogRow {
  id: number
  ts: string
  level: 'info' | 'warn' | 'error'
  /** refill | start | done | error | skip | rest | manual */
  action?: string | null
  msg: string
  company_id?: number | null
  source_nm_id?: number | null
  competitor_nm_id?: number | null
  queue_id?: number | null
  priority?: number | null
  phrases_cnt?: number | null
  model?: string | null
  ms?: number | null
}

export interface MinerCurrent {
  competitor_nm_id: number
  company_id: number
  source_nm_id: number
  /** unix seconds */
  since?: number
}

export interface MinerBalanceCompany {
  company_id: number
  until: string | null
  left_sec: number
  reason: string
}

export interface MinerBalance {
  /** В скоупе есть компания на паузе «нет токенов» */
  paused: boolean
  until: string | null
  left_sec: number
  reason: string
  companies: MinerBalanceCompany[]
}

export interface MinerQuota {
  applicable: boolean
  ok: boolean
  error?: string
  percent?: number | null
  active?: boolean | null
  reset_at?: string
  reset_left?: string
  reset_left_sec?: number
  weekly_percent?: number | null
  weekly_reset_at?: string
  pause_until?: string
  checked_at?: string
}

export interface MinerStatus {
  running: boolean
  paused: boolean
  current: MinerCurrent | null
  last_error: { msg: string; ts: number } | null
  scenario: string
  balance?: MinerBalance
  quota?: MinerQuota
  queue: {
    counts: Record<string, number>
    pending_by_priority: Record<string, number>
  }
  /** Счётчики журнала по уровням + total (для бейджа вкладки) */
  log_counts?: Record<string, number>
  can_see_cost: boolean
  /** Глобальный админ (может фильтровать по любой компании) */
  is_global?: boolean
  company_scope?: number | null
  ai_usage: {
    today: MinerQueueTot
    week: MinerQueueTot
    month: MinerQueueTot
    by_model: Array<MinerQueueTot & { grp?: string | null }>
  }
}

export interface MinerQueueRow {
  id: number
  company_id: number
  source_nm_id: number
  competitor_nm_id: number
  priority: number
  status: string
  attempts: number
  last_error?: string | null
  error_until?: string | null
  model?: string | null
  phrases_cnt?: number | null
  created_at?: string | null
  processed_at?: string | null
}

export interface MinerQueueResp {
  total: number
  rows: MinerQueueRow[]
  limit: number
  offset: number
}

export interface MinerLogResp {
  total: number
  rows: MinerLogRow[]
  limit: number
  offset: number
  /** Подсказка, если журнал недоступен (например, не применена миграция) */
  error?: string
}

export const phraseMinerApi = {
  status: (companyId?: number | null) =>
    api.get('/api/phrases/miner/status', { params: companyId ? { company_id: companyId } : {} })
      .then((r) => r.data as MinerStatus),

  queue: (params: { status?: string; company_id?: number | null; limit?: number; offset?: number }) =>
    api.get('/api/phrases/miner/queue', { params }).then((r) => r.data as MinerQueueResp),

  log: (params: { level?: string; action?: string; company_id?: number | null; limit?: number; offset?: number }) =>
    api.get('/api/phrases/miner/log', { params }).then((r) => r.data as MinerLogResp),

  pause: (paused: boolean, companyId?: number | null) =>
    api.post('/api/phrases/miner/pause', { paused }, { params: companyId ? { company_id: companyId } : {} })
      .then((r) => r.data as { ok: boolean; paused: boolean }),
}
