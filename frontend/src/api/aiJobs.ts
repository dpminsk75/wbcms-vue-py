import { api } from '../api/client'

export type AiJobStatus = 'queued' | 'running' | 'done' | 'error' | 'interrupted'
export type AiJobItemStatus = 'pending' | 'processing' | 'done' | 'error'

export interface AiJobItem {
  id: number; label: string | null; ref_id: number | null;
  status: AiJobItemStatus; result?: any; error?: string | null; note?: string | null;
}

export interface AiJob {
  id: number; company_id: number | null; kind: string; nm_id: number | null;
  status: AiJobStatus; total: number; done: number; error?: string | null;
  items: AiJobItem[]; created_at?: string; updated_at?: string;
}

export const aiJobsApi = {
  get: (jobId: number) => api.get(`/api/ai-jobs/${jobId}`).then((r) => r.data as AiJob),
}
