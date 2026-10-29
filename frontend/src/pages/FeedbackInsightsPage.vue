<template>
  <div class="container-xxl page-feedback-insights">
    <FeedbackHead :title="$route.meta.title || 'Инсайты'" active="insights" />

    <!-- Фильтр (тот же, что в /geo/sales-map) -->
    <WbUniversalFilter
      v-model:product="filters.product"
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:brand="filters.brand"
      v-model:category="filters.category"
      :brands="brands"
      :categories="categories"
      @apply="load"
      @reset="onReset"
    />

    <!-- Запуск: показаны инсайты только этого задания -->
    <div v-if="jobId" class="alert alert-info page-feedback-insights__job-note">
      <i class="bi bi-filters"></i>
      Показаны инсайты задания <b>#{{ jobId }}</b>.
      <button class="btn btn-sm btn-light ms-2" @click="showAllJobs">Показать все</button>
    </div>

    <div v-if="error" class="wb-error mb-3">{{ error }}</div>

    <div class="card">
      <div class="wb-card-header">
        Инсайты
        <span class="page-feedback-insights__count">Всего: {{ total }}</span>
        <span class="page-feedback-insights__spacer"></span>
        <button class="btn btn-light btn-sm wb-excel-btn" @click="exportExcel">
          <i class="bi bi-file-earmark-excel"></i> Excel
        </button>
      </div>
      <div class="card-body p-0">
        <div class="wb-table-wrap">
          <table class="table table-striped align-middle mb-0">
            <thead>
              <tr>
                <th class="page-feedback-insights__col-check"></th>
                <th class="page-feedback-insights__col-card">Карточка</th>
                <th class="page-feedback-insights__col-num">Отзывов</th>
                <th class="page-feedback-insights__col-num">Ср. оценка</th>
                <th>Что делать</th>
                <th class="page-feedback-insights__col-num">Период отзывов</th>
                <th class="page-feedback-insights__col-check"></th>
                <th class="page-feedback-insights__col-check"></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="it in insights" :key="it.id">
              <tr :class="{ 'page-feedback-insights__row--picked': openInsight === it.id }">
                <td class="text-center">
                  <button class="btn btn-sm btn-outline-secondary"
                          @click="openInsight = openInsight === it.id ? 0 : it.id">
                    <i class="bi" :class="openInsight === it.id ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                  </button>
                </td>
                <td>
                  <div class="page-feedback-insights__title">{{ it.card_title || '(без названия)' }}</div>
                  <div class="page-feedback-insights__sub">
                    <span v-if="it.brand">{{ it.brand }} · </span>
                    <span v-if="it.subject_name">{{ it.subject_name }} · </span>
                    <span v-if="it.vendor_code">{{ it.vendor_code }} · </span>
                    WB: {{ it.nm_id }}
                  </div>
                </td>
                <td class="text-center">{{ it.reviews_cnt }}</td>
                <td class="text-center">{{ it.avg_rating ?? '—' }}</td>
                <td>{{ it.summary || '—' }}</td>
                <td class="text-center text-nowrap small">
                  {{ fmtD(it.period_from) }} — {{ fmtD(it.period_to) }}
                </td>
                <td class="text-center text-nowrap">
                  <span class="text-muted small">{{ fmtDT(it.created_at) }}</span>
                </td>
                <td class="text-center text-nowrap">
                  <button class="btn btn-sm btn-outline-secondary"
                          title="Скопировать ссылку на инсайт" @click="copyLink(it)">
                    <i class="bi bi-link-45deg"></i>
                    <span v-if="copiedId === it.id" class="page-feedback-insights__copied">Скопировано</span>
                    <span v-else>Ссылка</span>
                  </button>
                  <button class="btn btn-sm btn-outline-secondary ms-1"
                          title="Открыть в новой вкладке" @click="openInNewTab(it)">
                    <i class="bi bi-box-arrow-up-right"></i>
                  </button>
                </td>
              </tr>

              <tr v-if="openInsight === it.id" class="page-feedback-insights__expand-row">
                <td :colspan="8">
                  <!-- О чём говорят покупатели -->
                  <div class="page-feedback-insights__panel">
                    <div class="page-feedback-insights__panel-head">
                      <span class="page-feedback-insights__panel-title">О чём говорят покупатели</span>
                      <span class="page-feedback-insights__panel-stat">{{ it.reviews_cnt }} отзыва</span>
                      <span class="page-feedback-insights__panel-stat panel-stat--pos">👍 {{ posPct(it) }}%</span>
                      <span class="page-feedback-insights__panel-stat panel-stat--neg">👎 {{ negPct(it) }}%</span>
                    </div>
                    <div class="page-feedback-insights__panel-cols">
                      <div>
                        <div class="page-feedback-insights__col-head">👍 Чаще всего упоминаемые плюсы</div>
                        <div v-if="!it.panel.plus.length" class="text-muted small">—</div>
                        <div v-for="g in it.panel.plus" :key="'p-' + g.title"
                             class="page-feedback-insights__group group--pos">
                          <div class="page-feedback-insights__group-title">
                            <span class="mk">+</span> {{ g.title }}
                          </div>
                          <ul>
                            <li v-for="(s, j) in g.items" :key="'pi' + j">{{ s }}</li>
                          </ul>
                        </div>
                      </div>
                      <div>
                        <div class="page-feedback-insights__col-head">👎 Чаще всего упоминаемые проблемы</div>
                        <div v-if="!it.panel.minus.length" class="text-muted small">—</div>
                        <div v-for="g in it.panel.minus" :key="'m-' + g.title"
                             class="page-feedback-insights__group group--neg">
                          <div class="page-feedback-insights__group-title">
                            <span class="mk">−</span> {{ g.title }}
                          </div>
                          <ul>
                            <li v-for="(s, j) in g.items" :key="'mi' + j">{{ s }}</li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Что сделать с описанием -->
                  <h3 class="page-feedback-insights__h3">Что сделать с описанием</h3>
                  <div v-if="!it.card_rec" class="text-muted small">Ничего конкретного нет.</div>
                  <div v-else class="page-feedback-insights__act">
                    <span class="badge" :class="priorityClass(it.card_rec.priority)">
                      {{ priorityLabel(it.card_rec.priority) }}</span>
                    <div class="page-feedback-insights__act-issue">{{ it.card_rec.issue }}</div>
                    <div v-if="it.card_rec.fix" class="page-feedback-insights__act-fix">
                      <i class="bi bi-wrench"></i> {{ it.card_rec.fix }}
                    </div>
                    <div v-for="(ev, j) in it.card_rec.evidence" :key="'e' + j"
                         class="page-feedback-insights__quote">«{{ ev }}»</div>

                    <div v-if="(it.card_rec.desc_add || []).length" class="mt-2">
                      <div class="page-feedback-insights__fix-head">Дописать</div>
                      <ul class="page-feedback-insights__fix-list">
                        <li v-for="(x, j) in it.card_rec.desc_add" :key="'da' + j">{{ x }}</li>
                      </ul>
                    </div>
                    <div v-if="(it.card_rec.desc_change || []).length" class="mt-2">
                      <div class="page-feedback-insights__fix-head">Изменить</div>
                      <div v-for="(ch, j) in it.card_rec.desc_change" :key="'dc' + j"
                           class="page-feedback-insights__change">
                        <span class="page-feedback-insights__change-was">{{ ch.was }}</span>
                        <i class="bi bi-arrow-right"></i>
                        <span class="page-feedback-insights__change-now">{{ ch.now }}</span>
                      </div>
                    </div>
                    <div v-if="(it.card_rec.desc_remove || []).length" class="mt-2">
                      <div class="page-feedback-insights__fix-head">Убрать</div>
                      <ul class="page-feedback-insights__fix-list">
                        <li v-for="(x, j) in it.card_rec.desc_remove" :key="'dr' + j">{{ x }}</li>
                      </ul>
                    </div>
                    <div v-if="it.card_rec.highlight" class="page-feedback-insights__hl">
                      <b>Что подчеркнуть:</b> {{ it.card_rec.highlight }}
                    </div>
                    <div v-if="it.card_rec.desc_new" class="mt-2">
                      <div class="row g-2">
                        <div class="col-12 col-md-6">
                          <div class="page-feedback-insights__cap">Было — описание</div>
                          <pre class="page-feedback-insights__pre">{{ it.card_rec.desc_old }}</pre>
                        </div>
                        <div class="col-12 col-md-6">
                          <div class="page-feedback-insights__cap">
                            Стало — черновик (проверьте ключи и факты)</div>
                          <pre class="page-feedback-insights__pre">{{ it.card_rec.desc_new }}</pre>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Что улучшить в товаре -->
                  <h3 class="page-feedback-insights__h3">Что улучшить в товаре</h3>
                  <div v-if="!it.product_rec" class="text-muted small">Ничего конкретного нет.</div>
                  <div v-else class="page-feedback-insights__act">
                    <span class="badge" :class="priorityClass(it.product_rec.priority)">
                      {{ priorityLabel(it.product_rec.priority) }}</span>
                    <div class="page-feedback-insights__act-issue">{{ it.product_rec.issue }}</div>
                    <div v-if="it.product_rec.action" class="page-feedback-insights__act-fix">
                      <i class="bi bi-tools"></i> {{ it.product_rec.action }}
                    </div>
                    <div v-for="(ev, j) in it.product_rec.evidence" :key="'pe' + j"
                         class="page-feedback-insights__quote">«{{ ev }}»</div>
                  </div>
                </td>
              </tr>
              </template>
              <tr v-if="!insights.length">
                <td colspan="8" class="text-center text-muted p-4">Инсайтов пока нет</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="card-body page-feedback-insights__pager">
        <button class="btn btn-sm btn-light" :disabled="page <= 1" @click="page--; load()">‹ Назад</button>
        <span class="page-feedback-insights__pager-label">Стр. {{ page }} из {{ totalPages }}</span>
        <button class="btn btn-sm btn-light" :disabled="page >= totalPages" @click="page++; load()">
          Вперёд ›</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-feedback-insights.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import FeedbackHead from '@/components/feedback/FeedbackHead.vue'
import { feedbackInsightsApi, type FeedbackInsight } from '@/api/feedbackInsights'
import { useDateFmt } from '@/composables/useDateFmt'
import { daysAgoStr, todayStr } from '@/utils/dates'

const route = useRoute()
const router = useRouter()
const { fmtDT } = useDateFmt()

const brands = ref<string[]>([])
const categories = ref<string[]>([])

const filters = ref({
  date_from: String(route.query.date_from || daysAgoStr(30)),
  date_to: String(route.query.date_to || todayStr()),
  product: String(route.query.product || route.query.q || ''),
  brand: String(route.query.brand || ''),
  category: String(route.query.category || ''),
})

const insights = ref<FeedbackInsight[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const error = ref('')
const openInsight = ref(0)
const copiedId = ref(0)
const jobId = ref<number | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

function fmtD(v: string | null): string {
  return v ? String(v).slice(0, 10) : '—'
}

function buildParams() {
  const p: Record<string, any> = {
    date_from: filters.value.date_from || undefined,
    date_to: filters.value.date_to || undefined,
    q: filters.value.product || undefined,
    brand: filters.value.brand || undefined,
    category: filters.value.category || undefined,
    job_id: jobId.value || undefined,
    page: page.value,
    page_size: pageSize,
  }
  return p
}

async function load() {
  error.value = ''
  try {
    const data = await feedbackInsightsApi.insights(buildParams())
    insights.value = data.items || []
    total.value = data.total || 0
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    insights.value = []
    total.value = 0
  }
  syncRoute()
}

function syncRoute() {
  const q: Record<string, string> = {}
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  if (filters.value.product) q.product = filters.value.product
  if (filters.value.brand) q.brand = filters.value.brand
  if (filters.value.category) q.category = filters.value.category
  if (jobId.value) q.job = String(jobId.value)
  router.replace({ path: route.path, query: q }).catch(() => {})
}

function onReset() {
  filters.value = {
    date_from: filters.value.date_from,
    date_to: filters.value.date_to,
    product: '',
    brand: '',
    category: '',
  }
  page.value = 1
  load()
}

function showAllJobs() {
  jobId.value = null
  page.value = 1
  load()
}

// --- ссылка на инсайт ---
function insightUrl(id: number): string {
  return `${location.origin}${route.path}?insight=${id}`
}

async function copyLink(it: FeedbackInsight) {
  try {
    await navigator.clipboard.writeText(insightUrl(it.id))
    copiedId.value = it.id
    setTimeout(() => { if (copiedId.value === it.id) copiedId.value = 0 }, 2000)
  } catch {
    error.value = 'не удалось скопировать ссылку'
  }
}

function openInNewTab(it: FeedbackInsight) {
  window.open(insightUrl(it.id), '_blank')
}

async function applyDeepLink() {
  const id = Number(route.query.insight || 0)
  if (!id) return
  openInsight.value = id
  if (insights.value.some((i) => i.id === id)) return
  try {
    const one = await feedbackInsightsApi.insight(id)
    if (one && !insights.value.some((i) => i.id === one.id)) {
      insights.value = [one, ...insights.value]
    }
  } catch {
    error.value = 'инсайт по ссылке не найден или нет доступа'
  }
}

function priorityClass(p: number): string {
  if (p === 1) return 'bg-danger'
  if (p === 2) return 'bg-warning text-dark'
  return 'bg-secondary'
}
function priorityLabel(p: number): string {
  if (p === 1) return 'критично'
  if (p === 2) return 'важно'
  return 'мелочь'
}
function posPct(it: FeedbackInsight): number {
  const n = it.reviews_cnt || 0
  if (!n) return 0
  return Math.round((Math.max(0, n - (it.neg_cnt || 0)) * 100) / n)
}
function negPct(it: FeedbackInsight): number {
  const n = it.reviews_cnt || 0
  if (!n) return 0
  return Math.round(((it.neg_cnt || 0) * 100) / n)
}

async function exportExcel() {
  if (!insights.value.length) return
  const XLSX = await import('xlsx')
  const rowsOut = insights.value.map((it) => ({
    'Карточка': it.card_title || '',
    'nmID': it.nm_id,
    'Бренд': it.brand || '',
    'Категория': it.subject_name || '',
    'Артикул': it.vendor_code || '',
    'Период отзывов': `${it.period_from || ''} — ${it.period_to || ''}`,
    'Отзывов': it.reviews_cnt,
    'Ср. оценка': it.avg_rating ?? '',
    'Что делать': it.summary || '',
    'Проблемы (темы)': (it.panel.minus || []).map((g) => `${g.title}: ${g.items.join('; ')}`).join(' | '),
    'Плюсы (темы)': (it.panel.plus || []).map((g) => `${g.title}: ${g.items.join('; ')}`).join(' | '),
    'Описание: проблема': it.card_rec ? it.card_rec.issue : '',
    'Описание: что сделать': it.card_rec ? (it.card_rec.fix || '') : '',
    'Описание: подчеркнуть': it.card_rec ? (it.card_rec.highlight || '') : '',
    'Описание: дописать': it.card_rec ? (it.card_rec.desc_add || []).join(' | ') : '',
    'Описание: изменить': it.card_rec
      ? (it.card_rec.desc_change || []).map((c) => `${c.was} → ${c.now}`).join(' | ') : '',
    'Описание: убрать': it.card_rec ? (it.card_rec.desc_remove || []).join(' | ') : '',
    'Товар: проблема': it.product_rec ? it.product_rec.issue : '',
    'Товар: что сделать': it.product_rec ? (it.product_rec.action || '') : '',
    'Разобрано': it.created_at || '',
  }))
  const ws = XLSX.utils.json_to_sheet(rowsOut)
  ws['!cols'] = [
    { wch: 38 }, { wch: 12 }, { wch: 16 }, { wch: 22 }, { wch: 16 }, { wch: 24 },
    { wch: 9 }, { wch: 11 }, { wch: 44 },
    { wch: 50 }, { wch: 50 },
    { wch: 42 }, { wch: 46 }, { wch: 40 }, { wch: 46 }, { wch: 46 }, { wch: 40 }, { wch: 50 },
    { wch: 42 }, { wch: 46 },
    { wch: 19 },
  ]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Инсайты')
  XLSX.writeFile(wb, 'insighty_otzyvov.xlsx')
}

watch(() => route.query.insight, () => {
  if (insights.value.length) applyDeepLink()
})

onMounted(async () => {
  const j = Number(route.query.job || 0)
  jobId.value = j > 0 ? j : null
  try {
    const f = await feedbackInsightsApi.filters()
    brands.value = f.brands || []
    categories.value = f.categories || []
  } catch { /* списки пустые — фильтр работает без них */ }
  await load()
  await applyDeepLink()
})
</script>
