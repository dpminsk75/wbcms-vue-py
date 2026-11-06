import { api } from './client'

export interface TaxVersion {
  id: number
  company_id: number
  valid_from: string
  valid_to: string | null
  mode: 'none' | 'income' | 'profit' | 'osno'
  mode_label: string
  main_rate: number
  vat_source: 'cards' | 'none'
  profit_rate: number | null
  reason: string | null
  created_by: number | null
  created_by_name: string | null
  created_at: string
  updated_at: string
  is_current: boolean
}

export interface NdsCoverage {
  total: number
  with_rate: number
  missing: number
  last_load_date: string | null
  rates: { rate: number; cards: number }[]
}

export interface TaxPreviewDay {
  date: string
  sales: number
  returns: number
  net: number
  vat: number
  vat_missing_rows: number
  vat_missing_amount: number
  cost: number
  commission: number
  acquiring: number
  acceptance: number
  delivery: number
  storage: number
  penalty: number
  deduction: number
  otziv: number
  adv: number
  cashback: number
  manual: number
  income_base: number
  profit_base: number
  tax: number
  total_tax: number
}

export interface TaxPreview {
  mode: string
  mode_label: string
  main_rate: number
  vat_source: string
  date_from: string
  date_to: string
  days: TaxPreviewDay[]
  totals: Record<string, number>
  partial: boolean
  notes: string[]
}

export const taxSettingsApi = {
  async meta() {
    const { data } = await api.get('/api/tax-settings/meta')
    return data as {
      modes: { value: string; label: string }[]
      vat_sources: { value: string; label: string }[]
      main_rates: number[]
    }
  },
  async versions() {
    const { data } = await api.get('/api/tax-settings/versions')
    return (data?.rows || []) as TaxVersion[]
  },
  async current(onDate?: string) {
    const { data } = await api.get('/api/tax-settings/current', { params: { on_date: onDate } })
    return (data?.row || null) as TaxVersion | null
  },
  async create(payload: {
    mode: string
    main_rate: number
    vat_source: string
    profit_rate?: number | null
    valid_from: string
    reason: string
  }) {
    const { data } = await api.post('/api/tax-settings/versions', payload)
    return data as { ok: boolean; valid_from: string; closed_previous_to: string }
  },
  async ndsCoverage() {
    const { data } = await api.get('/api/tax-settings/nds-coverage')
    return data as NdsCoverage
  },
  async ndsMissing(q = '', limit = 500) {
    const { data } = await api.get('/api/tax-settings/nds-missing', { params: { q, limit } })
    return (data?.rows || []) as { nmID: number; vendorCode: string; title: string }[]
  },
  async preview(payload: {
    date_from: string
    date_to: string
    mode?: string
    main_rate?: number
    vat_source?: string
  }) {
    const { data } = await api.post('/api/tax-settings/preview', payload)
    return data as TaxPreview
  },
}
