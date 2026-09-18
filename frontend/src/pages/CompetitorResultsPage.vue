<template>
  <div class="container-xxl page-competitor">
    <nav aria-label="breadcrumb">
      <ol class="breadcrumb page-competitor__crumbs">
        <li class="breadcrumb-item"><router-link to="/">Главная</router-link></li>
        <li class="breadcrumb-item"><router-link to="/competitor/index">Конкуренты</router-link></li>
        <li class="breadcrumb-item active" aria-current="page">Результаты анализа</li>
      </ol>
    </nav>
    <h2 class="page-competitor__title">Результаты анализа конкурентов</h2>
    <div v-if="card" class="card page-competitor__own-card">
      <div class="card-body page-competitor__own-body">
        <img :src="card.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb page-competitor__thumb--lg" />
        <div class="page-competitor__own-text">
          <div class="fw-semibold">{{ card.title || '' }}</div>
          <div class="small text-muted">{{ card.brand || '' }}</div>
          <div class="small">
            Артикул WB:
            <a :href="`/wb/detail?nm_id=${nmId}`" target="_blank" class="page-competitor__wb-link">{{ nmId }}</a>
            <span v-if="card.vendor_code" class="text-muted"> · Артикул: {{ card.vendor_code }}</span>
          </div>
        </div>
        <div class="page-competitor__own-actions">
          <router-link :to="`/competitor/selected/${nmId}`" class="btn btn-sm btn-outline-secondary">К отбору</router-link>
          <button @click="analyzeAll" :disabled="jobActive" class="btn btn-sm btn-primary">
            <i class="bi bi-robot"></i> Анализ всех отмеченных
          </button>
        </div>
      </div>
    </div>
    <div v-else>
      <router-link to="/competitor/index">← Конкуренты</router-link>
      <router-link :to="`/competitor/selected/${nmId}`" class="btn btn-sm btn-outline-secondary page-competitor__head-btn">К отбору</router-link>
      <button @click="analyzeAll" :disabled="jobActive" class="btn btn-sm btn-primary page-competitor__head-btn">
        <i class="bi bi-robot"></i> Анализ всех отмеченных
      </button>
    </div>
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
          {{ it.label }}
          <span v-if="it.note && it.status !== 'done' && it.status !== 'error'" class="text-muted small"> — {{ it.note }}</span>
          <span v-if="it.error" class="text-danger"> — {{ it.error }}</span>
        </li>
      </ul>
    </div>

    <div v-if="job.job.value" class="alert alert-info page-competitor__job">
      <span v-if="!job.finished.value" class="spinner-border spinner-border-sm text-primary"></span>
      Задача #{{ job.job.value.id }}: {{ job.job.value.done }}/{{ job.job.value.total }} ({{ job.progress.value }}%)
      <span v-if="job.finished.value">— {{ job.job.value.status }}</span>
    </div>

    <div v-if="loading" class="text-muted">Загрузка…</div>
    <div v-if="!loading && !competitors.length" class="alert alert-info">Конкурентов нет.</div>

    <div v-for="c in competitors" :key="c.nm_id" class="card page-competitor__block">
      <div class="card-body page-competitor__result-grid">
        <div class="page-competitor__result-left">
          <div class="page-competitor__result-top">
            <img v-if="c.image" :src="c.image" alt="Фото конкурента" class="page-competitor__result-img" />
            <div class="page-competitor__product-text">
              <div class="fw-semibold">
                <a :href="`https://www.wildberries.ru/catalog/${c.nm_id}/detail.aspx`" target="_blank" class="text-dark text-decoration-none">
                  {{ c.title || `nmID ${c.nm_id}` }}
                </a>
                <span class="badge bg-secondary page-competitor__title-len">{{ (c.title || '').length }} симв.</span>
              </div>
              <div class="small text-muted">{{ c.brand || '' }}</div>
              <div class="page-competitor__result-actions">
                <button v-if="c.analysis" @click="analyzeOne(c)" :disabled="jobActive" class="btn btn-sm btn-outline-success">
                  <i class="bi bi-robot"></i> {{ c.has_analysis ? 'Повторить AI' : 'AI анализ' }}
                </button>
                <button v-else @click="analyzeDirect(c.nm_id)" :disabled="jobActive" class="btn btn-sm btn-outline-primary">
                  <i class="bi bi-robot"></i> AI анализ
                </button>
                <span v-if="itemStatus(c.nm_id) === 'pending' || itemStatus(c.nm_id) === 'processing'" class="page-competitor__inline-loader" :title="itemNote(c.nm_id) || 'Анализ идёт, задача выполняется на сервере'">
                  <span class="spinner-border spinner-border-sm text-primary"></span>
                  <span class="text-muted small">идёт анализ</span>
                </span>
                <span v-else-if="itemStatus(c.nm_id) === 'error'" class="badge bg-danger" :title="itemError(c.nm_id)">ошибка AI</span>
              </div>
              <table class="page-competitor__specs">
                <tr><td class="text-muted">Цена</td><td><b>{{ priceFmt(c.price) }}</b></td></tr>
                <tr><td class="text-muted">Рейтинг</td><td><span v-if="c.rating">★ {{ c.rating }}</span><span v-else>—</span></td></tr>
                <tr><td class="text-muted">Отзывы</td><td>{{ c.feedbacks ?? '—' }}</td></tr>
              </table>
            </div>
          </div>
          <div v-if="c.description" class="page-competitor__result-desc">
            <div class="small text-muted">Описание конкурента: <b>{{ c.description.length }} симв.</b></div>
            <div class="page-competitor__result-desc-body">{{ shortDesc(c.description) }}</div>
          </div>
          <div v-if="c.phrases.length" class="page-competitor__queries">
            <div class="small fw-bold text-muted">Фразы конкурента:</div>
            <span v-for="q in c.phrases" :key="q.phrase + q.position" class="badge bg-light text-dark page-competitor__query">
              {{ q.phrase }} <span class="text-primary">#{{ q.position }}</span>
            </span>
          </div>
        </div>
        <div class="page-competitor__result-right">
          <div v-if="c.has_analysis" class="small text-muted page-competitor__ai-meta">
            {{ c.model || 'модель?' }} · {{ fmtDT(c.analyzed_at) }}
          </div>
          <div v-if="!c.has_analysis" class="text-muted small">Ещё не проанализировано</div>
          <template v-else-if="aiData(c)">
            <div v-if="(aiData(c).competitor_better || []).length" class="page-competitor__ai-block">
              <div class="text-danger fw-semibold">Лучше у конкурента:</div>
              <ul><li v-for="(t, i) in aiData(c).competitor_better" :key="'cb' + i">{{ t }}</li></ul>
            </div>
            <div v-if="(aiData(c).we_better || []).length" class="page-competitor__ai-block">
              <div class="text-success fw-semibold">Лучше у нас:</div>
              <ul><li v-for="(t, i) in aiData(c).we_better" :key="'wb' + i">{{ t }}</li></ul>
            </div>
            <div v-if="(aiData(c).recommendations || []).length" class="page-competitor__ai-block">
              <div class="text-primary fw-semibold">Рекомендации:</div>
              <ul><li v-for="(t, i) in aiData(c).recommendations" :key="'rc' + i">{{ t }}</li></ul>
            </div>
            <div v-if="!hasRec(c)" class="alert alert-warning">
              Анализ выполнен, но рекомендаций нет. Попробуйте <a href="#" @click.prevent="analyzeOne(c)" class="alert-link">повторить AI</a>.
            </div>
          </template>
          <div v-else class="alert alert-warning">Анализ выполнен, но рекомендаций нет.</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { competitorApi } from '../api/competitor'
import { useAiJob } from '../composables/useAiJob'

interface Row {
  nm_id: number; title?: string | null; brand?: string | null;
  price?: number | null; rating?: number | null; feedbacks?: number | null;
  image?: string | null; description?: string | null;
  phrases: Array<{ phrase: string; position: number | null }>;
  analysis?: { id: number; status: string } | null; has_analysis: boolean; ai_result?: any;
}

const route = useRoute()
const nmId = Number(route.params.nm)
const competitors = ref<Row[]>([])
const card = ref<{ title?: string; brand?: string; vendor_code?: string | null; photo?: string | null } | null>(null)
const loading = ref(false)
const error = ref('')
const job = useAiJob()
const jobActive = computed(() => job.polling.value && !job.finished.value)

const shortDesc = (t: any) => String(t || '').slice(0, 800)
const fmtDT = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
const priceFmt = (p: any) => p ? `${Number(p / 100).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽` : '—'
// Статус текущей задачи для карточки (лоадер/ошибка у самой записи)
function jobItem(nm: number) {
  return job.job.value?.items.find((i) => i.label === `nm ${nm}`) || null
}
const itemStatus = (nm: number) => jobItem(nm)?.status || null
const itemError = (nm: number) => jobItem(nm)?.error || ''
const itemNote = (nm: number) => jobItem(nm)?.note || ''
function aiData(c: Row): any {
  const raw = c.ai_result
  if (!raw) return null
  if (typeof raw === 'object') return raw
  try {
    const p = JSON.parse(raw)
    return typeof p === 'object' && p ? p : null
  } catch {
    return { raw }
  }
}
function hasRec(c: Row): boolean {
  const d = aiData(c) || {}
  return !!((d.competitor_better || []).length || (d.we_better || []).length || (d.recommendations || []).length)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await competitorApi.results(nmId)
    competitors.value = r.competitors
    card.value = r.card
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}
async function runJob(p: Promise<{ job_id: number }>) {
  try {
    job.start((await p).job_id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
function analyzeOne(c: Row) {
  if (c.analysis) runJob(competitorApi.analyze(c.analysis.id))
}
function analyzeDirect(cnm: number) {
  runJob(competitorApi.analyzeDirect(nmId, cnm))
}
function analyzeAll() {
  runJob(competitorApi.analyzeAll(nmId))
}

onMounted(load)
watch(() => job.finished.value, (f) => { if (f) load() })
</script>
