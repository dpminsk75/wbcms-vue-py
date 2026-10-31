import { api } from './client'

export interface SearchCardResponse {
  cardInfo: { nmID: number; title: string } | null
  models: any[]
  uniqueDates: string[]
  nm_id: number
  date_from: string
  date_to: string
}

export interface SearchPhraseResponse {
  phrase: string | null
  phrase_id: number | null
  models: any[]
  uniqueDates: string[]
  chartData: Array<Record<string, any>>
  top5Info: Record<string, string>
  date_from: string
  date_to: string
}

export const wbSearchApi = {
  async card(nmId: string, dateFrom: string, dateTo: string): Promise<SearchCardResponse> {
    const { data } = await api.get('/api/wb-search/card', { params: { nm_id: nmId, date_from: dateFrom, date_to: dateTo } })
    return data
  },
  async phrases(q?: string): Promise<Array<{ id: number; phrase: string; max_frequency: number }>> {
    const { data } = await api.get('/api/wb-search/phrases', { params: { q: q || undefined, limit: 1000 } })
    return Array.isArray(data) ? data : []
  },
  async phrase(phraseId: string, dateFrom: string, dateTo: string): Promise<SearchPhraseResponse> {
    const params: Record<string, string> = { date_from: dateFrom, date_to: dateTo }
    if (/^\d+$/.test(phraseId)) params.phrase_id = phraseId
    else params.phrase = phraseId
    const { data } = await api.get('/api/wb-search/phrase', { params })
    return data
  },
  async trend(phraseText: string, dateFrom: string, dateTo: string, page = 1, pageSize = 50): Promise<any> {
    const { data } = await api.get('/api/wb-search/trend', {
      params: { phrase_text: phraseText || undefined, date_from: dateFrom, date_to: dateTo, page, page_size: pageSize },
    })
    return data
  },
  async analytics(q: string, dateFrom: string, dateTo: string, sort = 'freq', page = 1, pageSize = 50): Promise<any> {
    const { data } = await api.get('/api/wb-search/analytics', {
      params: { q: q || undefined, date_from: dateFrom, date_to: dateTo, sort, page, page_size: pageSize },
    })
    return data
  },
  /** Каннибализация: фразы, по которым ранжируются ≥2 наших карточек. */
  async cannibalization(
    dateFrom: string,
    dateTo: string,
    opts: {
      q?: string
      nmId?: number | null
      brand?: string
      category?: string
      page?: number
      pageSize?: number
      /** Порядок строк: orders (по умолчанию) / freq / cards / phrase. */
      sort?: string
    } = {},
  ): Promise<any> {
    const { data } = await api.get('/api/wb-search/cannibalization', {
      params: {
        date_from: dateFrom,
        date_to: dateTo,
        q: opts.q || undefined,
        nm_id: opts.nmId || undefined,
        brand: opts.brand || undefined,
        category: opts.category || undefined,
        page: opts.page ?? 1,
        page_size: opts.pageSize ?? 50,
        sort: opts.sort || undefined,
      },
    })
    return data
  },
}
