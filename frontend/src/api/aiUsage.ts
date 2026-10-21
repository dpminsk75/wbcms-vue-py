import { api } from './client'

export interface AiUsageTotals {
  calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost: number
  failed: number
}

export interface AiUsageRow {
  calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost: number
  failed: number
  grp?: string | number | null
  company_name?: string
  user_name?: string
  // detail
  id?: number
  created_at?: string
  company_id?: number | null
  user_id?: number | null
  provider?: string
  model?: string
  scenario?: string
  nm_id?: number | null
  job_id?: number | null
  preview?: string
  http_status?: number | null
  ok?: boolean
  error?: string
}

export interface AiUsageResponse {
  rows: AiUsageRow[]
  totals: AiUsageTotals
  group_by: string
  group_labels: Record<string, string>
  scenario_labels: Record<string, string>
  models: string[]
  can_see_cost: boolean
}

export const aiUsageApi = {
  summary: (params: Record<string, any>) =>
    api.get('/api/seo/ai-usage', { params }).then((r) => r.data as AiUsageResponse),

  artifacts: (scenario: string, nmId: number) =>
    api.get('/api/seo/ai-usage/artifacts', { params: { scenario, nm_id: nmId } })
      .then((r) => r.data as { items: Array<Record<string, any>> }),
}
