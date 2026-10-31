import { api } from './client'

export interface ReviewBalanceCompany {
  company_id: number
  paused: boolean
  until: string | null
  left_sec: number
  reason: string
}

export interface ReviewFlags {
  running: boolean
  paused: boolean
  interval_sec: number
  /** Пауза из-за отсутствия токенов у ИИ-провайдера (3 ч) */
  balance_paused: boolean
  balance_pause_until: string | null
  balance_pause_left_sec: number
  balance_pause_reason: string
  balance_companies: ReviewBalanceCompany[]
  /** Идёт ручной запуск разбора (кнопка «Разобрать порцию») */
  manual_running: boolean
}

export interface ReviewQuota {
  /** Проверка применима (провайдер — MiniMax Token Plan) */
  applicable: boolean
  ok: boolean
  error?: string
  model?: string
  /** Остаток 5-часового окна, % */
  percent?: number | null
  status?: number
  active?: boolean | null
  /** Сброс окна — ISO со смещением */
  reset_at?: string
  reset_left?: string
  reset_left_sec?: number
  /** Остаток недельного окна, % */
  weekly_percent?: number | null
  weekly_reset_at?: string
  /** Пауза = сброс + 30 мин */
  pause_until?: string
  checked_at?: string
}

export interface ReviewStatus {
  flags: ReviewFlags
  counts: { done: number; error: number; pending: number; queue_has_more: boolean }
  settings: { auto: boolean; batch: number }
  prompt_set: boolean
  scenario: string
  quota?: ReviewQuota
}

export interface ReviewQueueItem {
  id: string
  nm_id: number | null
  rating: number | null
  text: string | null
  created_at: string | null
}

export interface ReviewLogItem {
  id: number
  company_id: number | null
  level: string
  action: string
  message: string | null
  created_at: string | null
}

export interface ReviewCostBlock {
  calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost: number
  failed: number
}

export interface ReviewStatusFull extends ReviewStatus {
  ai_usage?: {
    today: ReviewCostBlock
    week: ReviewCostBlock
    month: ReviewCostBlock
    by_model: ReviewCostBlock[]
  }
}

export const feedbackReviewApi = {
  async status(): Promise<ReviewStatusFull> {
    const { data } = await api.get('/api/feedback/review/status')
    return data
  },
  async queue(limit = 50, offset = 0): Promise<{
    items: ReviewQueueItem[]
    has_more: boolean
  }> {
    const { data } = await api.get('/api/feedback/review/queue', { params: { limit, offset } })
    return data
  },
  async log(level: string | null, limit = 50, offset = 0): Promise<{
    items: ReviewLogItem[]
    total: number
    error?: string
  }> {
    const { data } = await api.get('/api/feedback/review/log', {
      params: { level: level || undefined, limit, offset },
    })
    return data
  },
  async errors(limit = 100): Promise<{ items: any[]; total: number }> {
    const { data } = await api.get('/api/feedback/review/errors', { params: { limit } })
    return data
  },
  async pause(paused: boolean): Promise<ReviewFlags> {
    const { data } = await api.post('/api/feedback/review/pause', { paused })
    return data
  },
  async run(limit = 20): Promise<{
    started?: boolean
    limit?: number
    reason?: string
    paused?: boolean
    pause_until?: string | null
    pause_reason?: string
  }> {
    const { data } = await api.post('/api/feedback/review/run', { limit })
    return data
  },
  async retryAll(): Promise<{ ok: boolean; count: number }> {
    const { data } = await api.post('/api/feedback/review/retry-all')
    return data
  },
  async settings(): Promise<{ auto: boolean; batch: number; prompt: string }> {
    const { data } = await api.get('/api/feedback/review/settings')
    return data
  },
  async saveSettings(settings: { auto?: boolean; batch?: number }): Promise<{
    auto: boolean
    batch: number
    prompt: string
  }> {
    const { data } = await api.put('/api/feedback/review/settings', settings)
    return data
  },
  async prompt(): Promise<{ prompt: string }> {
    const { data } = await api.get('/api/feedback/review/prompt')
    return data
  },
  async savePrompt(prompt: string): Promise<{ ok: boolean; prompt: string }> {
    const { data } = await api.put('/api/feedback/review/prompt', { prompt })
    return data
  },
}
