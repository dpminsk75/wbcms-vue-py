import { ref, computed, onUnmounted } from 'vue'
import { aiJobsApi, type AiJob } from '../api/aiJobs'

const POLL_MS = 2000
const FINISHED = new Set(['done', 'error', 'interrupted'])

/** Вариант B: опрос фоновой AI-задачи. start(jobId) → поллит до финала, стоп на размонтировании. */
export function useAiJob() {
  const job = ref<AiJob | null>(null)
  const polling = ref(false)
  const error = ref('')
  let timer: ReturnType<typeof setInterval> | null = null

  const progress = computed(() => {
    const j = job.value
    if (!j || !j.total) return 0
    return Math.round((j.done / j.total) * 100)
  })
  const finished = computed(() => !!job.value && FINISHED.has(job.value.status))

  function stop() {
    if (timer) clearInterval(timer)
    timer = null
    polling.value = false
  }

  async function tick(jobId: number) {
    try {
      job.value = await aiJobsApi.get(jobId)
      const j = job.value
      const active = (j.items || []).filter((i) => i.status === 'pending' || i.status === 'processing')
      const activeStr = active.map((i) => (i.note ? `${i.label} [${i.note}]` : `${i.label}`)).join(', ')
      console.debug('[ai-job]', `#${j.id} ${j.kind}`, j.status, `${j.done}/${j.total}`, activeStr ? `active: ${activeStr}` : '', j.error || '')
      if (finished.value) stop()
    } catch (e: any) {
      error.value = e?.response?.data?.detail || String(e)
      stop()
    }
  }

  function start(jobId: number) {
    stop()
    error.value = ''
    polling.value = true
    tick(jobId)
    timer = setInterval(() => tick(jobId), POLL_MS)
  }

  onUnmounted(stop)
  return { job, progress, finished, polling, error, start, stop }
}
