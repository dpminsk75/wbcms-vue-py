<template>
  <div class="container-xxl page-competitor">
    <h2 class="page-competitor__title">Конкуренты — nmID {{ nmId }}</h2>
    <p>
      <router-link to="/competitor/index">← Конкуренты</router-link>
      <router-link :to="`/competitor/select/${nmId}`" class="btn btn-sm btn-outline-secondary page-competitor__head-btn">Изменить фразы</router-link>
      <button @click="analyzeAll" :disabled="jobActive" class="btn btn-sm btn-primary page-competitor__head-btn">
        <i class="bi bi-robot"></i> Анализ всех отмеченных
      </button>
    </p>
    <div v-if="error" class="wb-error">{{ error }}</div>

    <div v-if="job.job.value" class="alert alert-info page-competitor__job">
      <span v-if="!job.finished.value" class="spinner-border spinner-border-sm text-primary"></span>
      Задача #{{ job.job.value.id }}: {{ job.job.value.done }}/{{ job.job.value.total }} ({{ job.progress.value }}%)
      <span v-if="job.finished.value">— {{ job.job.value.status }}</span>
      <ul class="page-competitor__job-items">
        <li v-for="it in job.job.value.items" :key="it.id">
          <span v-if="it.status === 'done'" class="text-success"><i class="bi bi-check-circle"></i></span>
          <span v-else-if="it.status === 'error'" class="text-danger"><i class="bi bi-x-circle"></i></span>
          <span v-else class="spinner-border spinner-border-sm text-primary"></span>
          {{ it.label }}<span v-if="it.error" class="text-danger"> — {{ it.error }}</span>
        </li>
      </ul>
    </div>

    <div v-if="summary || summaryLoading" class="card page-competitor__block">
      <div class="card-header page-competitor__block-head">
        <span><i class="bi bi-stars"></i> Сводная рекомендация{{ summary?.cached ? ` (кэш${summary.cache_age_days != null ? `, ${summary.cache_age_days} дн.` : ''})` : '' }}</span>
        <button v-if="!summary || summary.can_recalc" @click="loadSummary(true)" class="btn btn-sm btn-outline-secondary">Пересчитать</button>
      </div>
      <div class="card-body">
        <div v-if="summaryLoading" class="text-muted">Генерация сводки (платная модель, до минуты)…</div>
        <div v-else-if="summary && summary.success">
          <div class="page-competitor__summary-title">{{ summary.result?.title }}</div>
          <div class="page-competitor__pre">{{ summary.result?.description }}</div>
          <details v-if="(summary.result?.priority_actions || []).length" class="page-competitor__details">
            <summary>Приоритетные действия ({{ summary.result.priority_actions.length }})</summary>
            <ul><li v-for="(a, i) in summary.result.priority_actions" :key="i">{{ a }}</li></ul>
          </details>
        </div>
        <div v-else-if="summary && !summary.success" class="wb-error">{{ summary.error }}</div>
        <div v-else class="text-muted">Нет сводки — нажмите «Сводка».</div>
        <button v-if="!summary && !summaryLoading" @click="loadSummary(false)" class="btn btn-sm btn-outline-primary">Сводка</button>
      </div>
    </div>
    <p v-else><button @click="loadSummary(false)" class="btn btn-sm btn-outline-primary">Сводка</button></p>

    <div v-if="loading" class="text-muted">Загрузка…</div>
    <div v-if="!loading && !competitors.length" class="alert alert-info">
      Нет отобранных конкурентов. <router-link :to="`/competitor/select/${nmId}`">Выбрать фразы</router-link>
    </div>

    <div v-for="c in competitors" :key="c.nm_id" class="card page-competitor__block">
      <div class="card-header page-competitor__block-head">
        <span>nmID <b>{{ c.nm_id }}</b> · {{ c.detail?.brand || '' }}</span>
        <span v-if="c.analysis?.status === 'analyzed'" class="badge bg-success">проанализирован</span>
        <span v-else class="badge bg-secondary">отмечен</span>
      </div>
      <div class="card-body">
        <div class="fw-semibold">{{ c.detail?.title || '—' }}</div>
        <div class="small text-muted page-competitor__queries">
          <span v-for="q in c.queries" :key="q.phrase + q.position" class="badge bg-light text-dark page-competitor__query">
            {{ q.phrase }} #{{ q.position }}
          </span>
        </div>
        <div v-if="c.detail?.description" class="page-competitor__comp-desc">{{ shortDesc(c.detail.description) }}</div>
        <div class="page-competitor__row-btns">
          <button @click="analyzeOne(c)" :disabled="jobActive" class="btn btn-sm btn-outline-primary"><i class="bi bi-robot"></i> Анализ</button>
          <button @click="removeOne(c.nm_id)" class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button>
          <span v-if="itemStatus(c.nm_id) === 'pending' || itemStatus(c.nm_id) === 'processing'" class="page-competitor__inline-loader" :title="itemNote(c.nm_id) || 'Анализ идёт, задача выполняется на сервере'">
            <span class="spinner-border spinner-border-sm text-primary"></span>
            <span class="text-muted small">идёт анализ</span>
          </span>
          <span v-else-if="itemStatus(c.nm_id) === 'error'" class="badge bg-danger" :title="itemError(c.nm_id)">ошибка AI</span>
        </div>
        <details v-if="aiData(c)" class="page-competitor__details">
          <summary>AI-разбор</summary>
          <div v-if="aiData(c)?.competitor_better?.length" class="page-competitor__ai-block">
            <div class="small text-muted">Лучше у конкурента:</div>
            <ul><li v-for="(t, i) in aiData(c).competitor_better" :key="'cb' + i">{{ t }}</li></ul>
          </div>
          <div v-if="aiData(c)?.we_better?.length" class="page-competitor__ai-block">
            <div class="small text-muted">Лучше у нас:</div>
            <ul><li v-for="(t, i) in aiData(c).we_better" :key="'wb' + i">{{ t }}</li></ul>
          </div>
          <div v-if="aiData(c)?.recommendations?.length" class="page-competitor__ai-block">
            <div class="small text-muted">Рекомендации:</div>
            <ul><li v-for="(t, i) in aiData(c).recommendations" :key="'rc' + i">{{ t }}</li></ul>
          </div>
          <div v-else-if="typeof aiData(c)?.raw === 'string'" class="page-competitor__pre">{{ aiData(c).raw }}</div>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { competitorApi, type CompetitorDetail } from '../api/competitor'
import { useAiJob } from '../composables/useAiJob'

const route = useRoute()
const nmId = Number(route.params.nm)
const competitors = ref<CompetitorDetail[]>([])
const loading = ref(false)
const error = ref('')
const summary = ref<any>(null)
const summaryLoading = ref(false)
const job = useAiJob()
const jobActive = computed(() => job.polling.value && !job.finished.value)

const shortDesc = (t: any) => String(t || '').slice(0, 600)
function jobItem(nm: number) {
  return job.job.value?.items.find((i) => i.label === `nm ${nm}`) || null
}
const itemStatus = (nm: number) => jobItem(nm)?.status || null
const itemError = (nm: number) => jobItem(nm)?.error || ''
const itemNote = (nm: number) => jobItem(nm)?.note || ''
function aiData(c: CompetitorDetail): any {
  const raw = c.analysis?.ai_result
  if (!raw) return null
  if (typeof raw === 'object') return raw
  try {
    const p = JSON.parse(raw)
    return typeof p === 'object' && p ? p : null
  } catch {
    return null
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await competitorApi.selected(nmId)
    competitors.value = r.competitors
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

async function runJob(p: Promise<{ job_id: number }>) {
  try {
    const r = await p
    job.start(r.job_id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
function analyzeOne(c: CompetitorDetail) {
  if (!c.analysis) {
    runJob(competitorApi.analyzeDirect(nmId, c.nm_id).then((r) => { load(); return r }))
  } else {
    runJob(competitorApi.analyze(c.analysis.id).then((r) => { load(); return r }))
  }
}
function analyzeAll() {
  runJob(competitorApi.analyzeAll(nmId).then((r) => { load(); return r }))
}
async function removeOne(cnm: number) {
  if (!confirm('Убрать из отбора?')) return
  await competitorApi.remove(nmId, cnm)
  load()
}
async function loadSummary(force: boolean) {
  summaryLoading.value = true
  try {
    summary.value = await competitorApi.summary(nmId, force)
  } catch (e: any) {
    summary.value = { success: false, error: e?.response?.data?.detail || String(e) }
  } finally {
    summaryLoading.value = false
  }
}

onMounted(() => {
  load()
  loadSummary(false)
})
watch(() => job.finished.value, (f) => { if (f) load() })
</script>
