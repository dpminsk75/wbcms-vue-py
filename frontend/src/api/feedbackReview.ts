import { api } from './client'

export interface ReviewStatus {
  flags: { running: boolean; paused: boolean; interval_sec: number }
  counts: { done: number; error: number; pending: number; queue_has_more: boolean }
  settings: { auto: boolean; batch: number }
  prompt_set: boolean
  scenario: string
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
  async pause(paused: boolean): Promise<{ running: boolean; paused: boolean }> {
    const { data } = await api.post('/api/feedback/review/pause', { paused })
    return data
  },
  async run(limit = 20): Promise<{ taken: number; ok: number; errors: number; fatal: string }> {
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
