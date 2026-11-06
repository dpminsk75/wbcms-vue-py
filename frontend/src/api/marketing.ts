import { api } from './client'

export interface MarketingChannel {
  id: number
  name: string
  channel_type: string
  channel_type_label: string
  website_or_contact: string | null
  contact_name: string | null
  contact_phone: string | null
  inn: string | null
  comment: string | null
  is_active: number
  documents_cnt: number
  total_amount: number
  created_at: string
  updated_at: string
}

export interface MarketingLine {
  id?: number
  nm_id: number
  vendor_code: string
  product_title: string
  amount: number
  comment?: string | null
}

export interface MarketingDocument {
  id: number
  document_key: string
  document_date: string
  /** Начало периода размещения (расход «работает» с этой даты). */
  period_start: string
  /** Окончание периода размещения. */
  period_end: string
  /** Дней в периоде размещения. */
  period_days?: number
  channel_id: number | null
  channel_name: string | null
  doc_type: string
  doc_type_label: string
  title: string
  comment: string | null
  total_amount: number
  lines_cnt: number
  created_at: string
  lines?: MarketingLine[]
}

export interface MarketingSummaryRow {
  doc_type?: string
  label?: string
  channel?: string
  documents: number
  total: number
  in_report: number
}

export interface MarketingSummary {
  documents: number
  channels: number
  total: number
  /** Часть суммы, растянутая по периодам размещения и попавшая в окно отчёта. */
  in_report: number
  by_type: MarketingSummaryRow[]
  by_channel: MarketingSummaryRow[]
}

export interface MarketingImportPreview {
  documents: {
    document_key: string
    document_date: string
    channel: string
    channel_found: boolean
    channel_id: number | null
    doc_type: string
    title: string
    total_amount: number
    lines: { nm_id: number; vendor_code: string; product_title: string; amount: number }[]
  }[]
  errors: { row: number; reason: string; raw: string }[]
  ok_rows: number
}

export const marketingApi = {
  async meta() {
    const { data } = await api.get('/api/marketing/meta')
    return data as {
      channel_types: { value: string; label: string }[]
      doc_types: { value: string; label: string }[]
      xlsx_columns: string[]
    }
  },
  async channels(q = '', includeArchived = false) {
    const { data } = await api.get('/api/marketing/channels', {
      params: { q, include_archived: includeArchived ? 1 : 0 },
    })
    return (data?.rows || []) as MarketingChannel[]
  },
  async createChannel(payload: Record<string, unknown>) {
    const { data } = await api.post('/api/marketing/channels', payload)
    return data as { ok: boolean; id: number }
  },
  async updateChannel(id: number, payload: Record<string, unknown>) {
    const { data } = await api.put(`/api/marketing/channels/${id}`, payload)
    return data as { ok: boolean }
  },
  async deleteChannel(id: number) {
    const { data } = await api.delete(`/api/marketing/channels/${id}`)
    return data as { ok: boolean; archived: boolean; message?: string }
  },
  async documents(params: {
    date_from?: string
    date_to?: string
    channel_id?: number | null
    q?: string
    limit?: number
  }) {
    const { data } = await api.get('/api/marketing/documents', { params })
    return (data?.rows || []) as MarketingDocument[]
  },
  async document(id: number) {
    const { data } = await api.get(`/api/marketing/documents/${id}`)
    return data as MarketingDocument
  },
  async createDocument(payload: Record<string, unknown>) {
    const { data } = await api.post('/api/marketing/documents', payload)
    return data as { ok: boolean; id: number; document_key: string; total_amount: number }
  },
  async updateDocument(id: number, payload: Record<string, unknown>) {
    const { data } = await api.put(`/api/marketing/documents/${id}`, payload)
    return data as { ok: boolean; total_amount: number }
  },
  async deleteDocument(id: number) {
    const { data } = await api.delete(`/api/marketing/documents/${id}`)
    return data as { ok: boolean }
  },
  /** Копия документа («по образцу») — новая запись с теми же позициями. */
  async copyDocument(id: number) {
    const { data } = await api.post(`/api/marketing/documents/${id}/copy`)
    return data as { ok: boolean; id: number; document_key: string; total_amount: number }
  },
  /** Сводка по окну фильтра: документы, площадки, суммы, «в отчёт» (растянуто по периодам). */
  async summary(params: { date_from?: string; date_to?: string; channel_id?: number | null; q?: string }) {
    const { data } = await api.get('/api/marketing/summary', { params })
    return data as MarketingSummary
  },
  async importPreview(rows: any[][]) {
    const { data } = await api.post('/api/marketing/import/preview', { rows })
    return data as MarketingImportPreview
  },
  async importSave(documents: any[]) {
    const { data } = await api.post('/api/marketing/import/save', { documents })
    return data as { ok: boolean; saved: number; skipped: number; errors: { document_key: string; reason: string }[] }
  },
  async exportRows(params: { date_from?: string; date_to?: string; channel_id?: number | null }) {
    const { data } = await api.get('/api/marketing/export', { params })
    return (data?.rows || []) as Record<string, any>[]
  },
  async searchCards(q: string, limit = 20) {
    const { data } = await api.get('/api/marketing/cards/search', { params: { q, limit } })
    return (data?.rows || []) as { nm_id: number; vendor_code: string; title: string }[]
  },
}
