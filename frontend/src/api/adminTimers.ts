import { api } from '../api/client'

export interface AdminTimerRow {
  id: string; timer: string; service: string; title: string; default: string;
  enabled: boolean; unit_file_state?: string | null; load_state?: string | null;
  active_state?: string | null; sub_state?: string | null;
  next?: string | null; last_trigger?: string | null;
  on_calendar: string[];
  svc_state?: string | null; svc_sub?: string | null; svc_result?: string | null;
  svc_exec_status?: string | null; svc_last_start?: string | null;
}

export const adminTimersApi = {
  list: () => api.get('/api/admin/timers').then((r) => r.data as AdminTimerRow[]),
  enable: (id: string) => api.post(`/api/admin/timers/${id}/enable`).then((r) => r.data),
  disable: (id: string) => api.post(`/api/admin/timers/${id}/disable`).then((r) => r.data),
  run: (id: string) => api.post(`/api/admin/timers/${id}/run`).then((r) => r.data),
  schedule: (id: string, onCalendar: string) =>
    api.put(`/api/admin/timers/${id}/schedule`, { on_calendar: onCalendar }).then((r) => r.data),
  log: (id: string, lines = 100) =>
    api.get(`/api/admin/timers/${id}/log`, { params: { lines } }).then((r) => r.data as { lines: string[] }),
}
