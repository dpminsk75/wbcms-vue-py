import { api } from './client'

/** Очередь сбора — /api/queue (страница «Очередь»). */

export interface QueueCardRow {
  id: number
  nm_id: number
  status: string
  source: string
  owner_company_id: number | null
  requested_at?: string | null
  claimed_at?: string | null
  processed_at?: string | null
  title?: string | null
  brand?: string | null
  seller?: string | null
  price?: number | number[] | null
  preview_image?: string | null
  is_hidden: number | boolean
}

export interface QueueCounts {
  total: number
  pending?: number
  need_update?: number
  processing?: number
  done?: number
  error?: number
  gone?: number
  hidden?: number
}

export interface QueueCardList {
  items: QueueCardRow[]
  total: number
  limit: number
  offset: number
  counts: QueueCounts
}

export interface SearchQueueRow {
  id: number
  nm_id: number
  phrase: string
  status: string
  is_active?: number
  priority?: number
  updated_at?: string | null
  active_cnt?: number
  /** Режим «Все»: у каждой строки указана её очередь (seo|compquery|phrases). */
  src?: string
}

export interface SearchQueueList {
  source: string
  items: SearchQueueRow[]
  total: number
  limit: number
  offset: number
  counts: Record<string, Record<string, number>>
}

export type SearchSource = 'seo' | 'compquery' | 'phrases'

const qs = (p: Record<string, unknown>) => {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(p)) {
    if (v === undefined || v === null || v === '' || v === false) continue
    u.set(k, String(v))
  }
  const s = u.toString()
  return s ? `?${s}` : ''
}

/* ---------- Сбор карточек ---------- */

export const queueApi = {
  cards: (p: { queue?: string; status?: string; q?: string; hidden?: boolean; limit?: number; offset?: number }) =>
    api.get(`/api/queue/cards${qs(p)}`).then(r => r.data as QueueCardList),

  /** Сколько конкурентов у нашей карточки (для кнопки «Добавить (N)»). */
  competitorsCount: (sourceNmId: number) =>
    api.get('/api/queue/cards/competitors-count', { params: { source_nm_id: sourceNmId } })
      .then(r => r.data as { count: number; hidden: number }),

  /** Конкуренты нашей карточки → очередь (как seed расширения). */
  seedFromCard: (sourceNmId: number) =>
    api.post('/api/queue/cards/seed', { source_nm_id: sourceNmId })
      .then(r => r.data as { checked: number; added: number; skipped_hidden: number; already: number }),

  /** Только счётчики (лёгкий запрос при смене очереди) — queue: watch|plain|all. */
  cardsCounts: (queue: string) =>
    api.get('/api/queue/cards/counts', { params: { queue } })
      .then(r => r.data as QueueCounts),

  cardsAdd: (nmId: number) =>
    api.post('/api/queue/cards', { nm_id: nmId }).then(r => r.data),

  cardsRequeue: (id: number) =>
    api.post(`/api/queue/cards/${id}/requeue`).then(r => r.data),

  cardsDelete: (id: number) =>
    api.delete(`/api/queue/cards/${id}`).then(r => r.data),

  /** Блокировать / разблокировать будущее добавление (capture.is_hidden, §19.4). */
  cardsBlock: (nmId: number, hidden: boolean) =>
    api.post('/api/queue/cards/block', { nm_id: nmId, hidden }).then(r => r.data),
}

/* ---------- Сбор поисковой выдачи ---------- */

export const queueSearchApi = {
  /** Только счётчики по всем трём очередям (лёгкий запрос при смене очереди). */
  counts: () => api.get('/api/queue/search/counts').then(r => r.data as SearchQueueList['counts']),

  list: (p: { source: string; status?: string; q?: string; limit?: number; offset?: number }) =>
    api.get(`/api/queue/search${qs(p)}`).then(r => r.data as SearchQueueList),

  add: (p: { source: SearchSource; nm_id?: number; phrase: string; priority?: number }) =>
    api.post('/api/queue/search', p).then(r => r.data),

  requeue: (source: SearchSource, id: number) =>
    api.post(`/api/queue/search/${source}/${id}/requeue`).then(r => r.data),

  remove: (source: SearchSource, id: number) =>
    api.delete(`/api/queue/search/${source}/${id}`).then(r => r.data),
}

/** Расшифровка ошибки axios → текст алерта (detail из бэка). */
export function queueErrorOf(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || (e instanceof Error ? e.message : 'Ошибка')
}
