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
  async trend(phraseText: string, dateFrom: string, dateTo: string, page = 1): Promise<any> {
    const { data } = await api.get('/api/wb-search/trend', {
      params: { phrase_text: phraseText || undefined, date_from: dateFrom, date_to: dateTo, page },
    })
    return data
  },
}
