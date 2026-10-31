import { api } from './client'

/** Локальный кэш фото WB — /api/images/* (робот + настройки). */

export interface ImagesSettings {
  /** Сколько дней хранить фото, которое больше не встречается в источниках. */
  ttl_days: number
  /** Интервал тика робота, сек. */
  interval_sec: number
  /** Сколько фото скачивать за тик. */
  batch_limit: number
  /** Сколько проверять за тик в недельном обходе. */
  sweep_limit: number
}

export interface ImagesStatus {
  running: boolean
  paused: boolean
  manual_running: boolean
  last_tick: string | null
  last_error: string | null
  last_result: Record<string, any>
  /** collect — обходим базы; watch — обход собранного раз в неделю. */
  phase: 'collect' | 'watch'
  phase_label: string
  counts: { pending: number; ok: number; error: number; gone: number }
  total: number
  /** Файлов в кэше на диске. */
  files: number
  /** Размер кэша на диске, байт. */
  bytes: number
  /** Всего событий в истории смены фото (для бейджа на вкладке). */
  history_total: number
  /** Всего строк в журнале робота (для бейджа на вкладке). */
  log_total: number
  /** Версия кода кэша — чтобы видеть, какая выкатка на сервере. */
  version?: string
  settings: ImagesSettings
}

export interface ImagesQueueRow {
  id: number
  nm_id: number | null
  state: string
  src_url: string
  width: number | null
  height: number | null
  bytes: number | null
  attempts: number
  last_error: string | null
  first_seen_at: string
  last_seen_at: string
  downloaded_at: string | null
  checked_at: string | null
}

export interface ImagesLogRow {
  id: number
  level: string
  action: string
  message: string | null
  nm_id: number | null
  created_at: string
}

export interface ImagesHistoryRow {
  id: number
  nm_id: number | null
  event: string
  src_url: string | null
  prev_src_url: string | null
  content_hash: string | null
  prev_content_hash: string | null
  message: string | null
  changed_at: string
}

export interface ImagesList<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export const imagesApi = {
  status: () => api.get<ImagesStatus>('/api/images/status').then(r => r.data),

  queue: (params: { state?: string; nm_id?: number; limit?: number; offset?: number }) =>
    api.get<ImagesList<ImagesQueueRow>>('/api/images/queue', { params }).then(r => r.data),

  log: (params: { level?: string; action?: string; limit?: number; offset?: number }) =>
    api.get<ImagesList<ImagesLogRow>>('/api/images/log', { params }).then(r => r.data),

  history: (params: { nm_id?: number; limit?: number; offset?: number }) =>
    api.get<ImagesList<ImagesHistoryRow>>('/api/images/history', { params }).then(r => r.data),

  settings: () => api.get<{ settings: ImagesSettings }>('/api/images/settings').then(r => r.data.settings),

  saveSettings: (s: Partial<ImagesSettings>) =>
    api.put<{ ok: boolean; settings: ImagesSettings }>('/api/images/settings', s).then(r => r.data),

  /** Поставить фото карточки в очередь на скачивание. */
  addToQueue: (nmId: number) =>
    api.post<{ ok: boolean; nm_id: number; url: string; source: string }>(
      '/api/images/queue', { nm_id: nmId },
    ).then(r => r.data),

  /** Вернуть фото в очередь (перекачать). */
  requeue: (id: number) =>
    api.post<{ ok: boolean }>(`/api/images/queue/${id}/requeue`).then(r => r.data),

  /** Прогнать порцию скачивания прямо сейчас. */
  run: (limit = 50) =>
    api.post<{ ok: boolean; error?: string }>('/api/images/run', { limit }).then(r => r.data),

  /** Пауза/старт фонового цикла. */
  pause: (paused: boolean) =>
    api.post<{ ok: boolean; paused: boolean }>('/api/images/pause', { paused }).then(r => r.data),
}
