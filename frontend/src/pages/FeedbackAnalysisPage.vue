<template>
  <div class="container-xxl page-feedback-analysis">
    <FeedbackHead :title="$route.meta.title || 'Разбор'" active="analysis" />

    <!-- Фильтр (тот же, что в /geo/sales-map) -->
    <WbUniversalFilter
      v-model:product="filters.product"
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:brand="filters.brand"
      v-model:category="filters.category"
      :brands="brands"
      :categories="categories"
      @apply="onApply"
      @reset="onReset"
    />

    <div v-if="error" class="wb-error mb-3">{{ error }}</div>

    <!-- Панель запуска -->
    <div class="page-feedback-analysis__bar">
      <div class="page-feedback-analysis__bar-info">
        <template v-if="selected.length">
          Отмечено карточек: <b>{{ selected.length }}</b>
          <span class="page-feedback-analysis__bar-hint">
            ИИ разберёт отзывы по этим карточкам</span>
        </template>
        <template v-else>
          <i class="bi bi-hand-index"></i>
          <span class="page-feedback-analysis__bar-hint">
            Отметьте карточки галочками слева — и нажмите «Проанализировать»</span>
        </template>
      </div>
      <div class="page-feedback-analysis__bar-actions">
        <button class="btn btn-sm btn-outline-secondary" @click="openPrompt">
          <i class="bi bi-sliders"></i> Промпт
          <span v-if="promptIsCustom" class="page-feedback-analysis__bar-dot"
                title="Используется свой промпт"></span>
        </button>
        <button class="btn btn-sm btn-outline-secondary" :disabled="!rows.length"
                @click="toggleAll">
          {{ allSelected ? 'Снять выбор со страницы' : 'Выбрать все на странице' }}
        </button>
        <button class="btn btn-sm btn-primary" :disabled="!selected.length || running" @click="run">
          <span v-if="running" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-robot"></i>
          Проанализировать<template v-if="selected.length"> ({{ selected.length }})</template>
        </button>
        <button v-if="selected.length" class="btn btn-sm btn-outline-secondary"
                @click="selected = []">Снять выбор</button>
      </div>
    </div>

    <!-- Прогресс ИИ-задачи -->
    <div v-if="job.job.value" class="alert alert-info page-feedback-analysis__job">
      <span v-if="!job.finished.value" class="spinner-border spinner-border-sm text-primary"></span>
      <i v-else-if="job.job.value.status === 'done'" class="bi bi-check-circle text-success"></i>
      <i v-else class="bi bi-x-circle text-danger"></i>
      Задача #{{ job.job.value.id }}: {{ job.job.value.done }}/{{ job.job.value.total }}
      ({{ job.progress.value }}%) <span v-if="elapsed">· прошло {{ elapsed }} с</span>
      <span v-if="job.finished.value"> — {{ job.job.value.status }}</span>
      <button v-if="job.finished.value && job.job.value.status === 'done'"
              class="btn btn-sm btn-primary ms-2" @click="goToInsights">
        <i class="bi bi-arrow-right"></i> К инсайтам
      </button>
      <ul class="page-feedback-analysis__job-items">
        <li v-for="it in job.job.value.items" :key="it.id">
          <span v-if="it.status === 'done'" class="text-success"><i class="bi bi-check-circle"></i></span>
          <span v-else-if="it.status === 'error'" class="text-danger"><i class="bi bi-x-circle"></i></span>
          <span v-else class="spinner-border spinner-border-sm text-primary"></span>
          {{ it.label }}
          <span v-if="it.note && it.status !== 'done' && it.status !== 'error'" class="text-muted small">
            — {{ it.note }}</span>
          <span v-if="it.error" class="text-danger small"> — {{ it.error }}</span>
        </li>
      </ul>
    </div>

    <!-- Карточки с отзывами -->
    <div class="card mb-3">
      <div class="wb-card-header">
        Карточки с отзывами — отметьте, что разбирать
        <span class="page-feedback-analysis__count">Всего: {{ total }}</span>
      </div>
      <div class="card-body p-0">
        <div class="wb-table-wrap">
          <table class="table table-striped align-middle mb-0">
            <thead>
              <tr>
                <th class="page-feedback-analysis__col-check">
                  <input type="checkbox" :checked="allSelected" :disabled="!rows.length"
                         title="Выбрать все на странице" @change="toggleAll" />
                </th>
                <th>Карточка</th>
                <th class="page-feedback-analysis__col-num">Отзывов</th>
                <th class="page-feedback-analysis__col-num">Ср. оценка</th>
                <th class="page-feedback-analysis__col-num">👍 / 👎</th>
                <th class="page-feedback-analysis__col-num">Дней</th>
                <th>Последняя</th>
                <th class="page-feedback-analysis__col-num">Разбор</th>
                <th class="page-feedback-analysis__col-check"></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="c in rows" :key="c.nm_id">
              <tr :class="{ 'page-feedback-analysis__row--picked': isSelected(c.nm_id) }">
                <td class="text-center">
                  <input type="checkbox" :checked="isSelected(c.nm_id)"
                         @change="toggle(c.nm_id)" />
                </td>
                <td>
                  <div class="page-feedback-analysis__title">{{ c.title || '(без названия)' }}</div>
                  <div class="page-feedback-analysis__sub">
                    <span v-if="c.brand">{{ c.brand }} · </span>
                    <span v-if="c.subject_name">{{ c.subject_name }} · </span>
                    <span v-if="c.vendor_code">{{ c.vendor_code }} · </span>
                    WB: {{ c.nm_id }}
                  </div>
                </td>
                <td class="text-center">{{ c.cnt }}</td>
                <td class="text-center">{{ c.avg_rating ?? '—' }}</td>
                <td class="text-center text-nowrap">
                  <span class="text-success">{{ c.pos_pct }}%</span>
                  <span class="text-muted"> / </span>
                  <span class="text-danger">{{ c.neg_pct }}%</span>
                </td>
                <td class="text-center">{{ c.days_cnt }}</td>
                <td class="text-nowrap">{{ fmtDT(c.last_at) }}</td>
                <td class="text-center text-nowrap">
                  <span v-if="c.last_insight_at" class="text-muted small">
                    {{ fmtDT(c.last_insight_at) }}
                  </span>
                  <span v-else class="text-muted small">—</span>
                </td>
                <td class="text-center">
                  <button class="btn btn-sm btn-outline-secondary"
                          @click="toggleExpand(c.nm_id)">
                    {{ expanded === c.nm_id ? 'Скрыть' : 'Отзывы' }}
                  </button>
                </td>
              </tr>
              <tr v-if="expanded === c.nm_id" class="page-feedback-analysis__expand-row">
                <td :colspan="9">
                  <div v-if="loadingReviews" class="text-muted small">Загрузка отзывов…</div>
                  <div v-else-if="!reviews.length" class="text-muted small">Отзывов не найдено.</div>
                  <div v-else class="page-feedback-analysis__reviews">
                    <div v-for="rv in reviews" :key="rv.id" class="page-feedback-analysis__review">
                      <span class="badge" :class="ratingClass(rv.rating)">{{ rv.rating }} ★</span>
                      <span class="page-feedback-analysis__review-date">{{ fmtDT(rv.created_at) }}</span>
                      <div v-if="rv.text" class="page-feedback-analysis__review-text">{{ rv.text }}</div>
                      <div v-if="rv.cons" class="page-feedback-analysis__review-cons">
                        <b>Минусы:</b> {{ rv.cons }}
                      </div>
                      <div v-if="rv.pros" class="page-feedback-analysis__review-pros">
                        <b>Плюсы:</b> {{ rv.pros }}
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
              </template>
              <tr v-if="!rows.length">
                <td colspan="9" class="text-center text-muted p-4">Отзывов не найдено</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="card-body page-feedback-analysis__pager">
        <button class="btn btn-sm btn-light" :disabled="page <= 1" @click="page--; load()">‹ Назад</button>
        <span class="page-feedback-analysis__pager-label">Стр. {{ page }} из {{ totalPages }}</span>
        <button class="btn btn-sm btn-light" :disabled="page >= totalPages" @click="page++; load()">
          Вперёд ›</button>
      </div>
    </div>

    <!-- Модалка: промпт разбора -->
    <div v-if="promptOpen" class="wb-modal-backdrop" @click.self="promptOpen = false">
      <div class="wb-modal-box wb-modal-box--wide page-feedback-analysis__prompt-modal">
        <h5 class="mb-0"><i class="bi bi-sliders"></i> Промпт разбора отзывов</h5>
        <PromptField label="Промпт разбора отзывов" @saved="onPromptSaved" />
        <div class="wb-modal-actions">
          <button class="btn btn-sm btn-light" @click="promptOpen = false">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-feedback-analysis.css'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import FeedbackHead from '@/components/feedback/FeedbackHead.vue'
import PromptField from '@/components/cms/PromptField.vue'
import { feedbackInsightsApi, type FeedbackCard, type FeedbackItem } from '@/api/feedbackInsights'
import { useAiJob } from '@/composables/useAiJob'
import { useDateFmt } from '@/composables/useDateFmt'
import { daysAgoStr, todayStr } from '@/utils/dates'

const route = useRoute()
const router = useRouter()
const { fmtDT } = useDateFmt()
const job = useAiJob()

const brands = ref<string[]>([])
const categories = ref<string[]>([])

const filters = ref({
  date_from: String(route.query.date_from || daysAgoStr(30)),
  date_to: String(route.query.date_to || todayStr()),
  product: String(route.query.product || route.query.q || ''),
  brand: String(route.query.brand || ''),
  category: String(route.query.category || ''),
})

const rows = ref<FeedbackCard[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const error = ref('')

const selected = ref<number[]>([])
const running = ref(false)

const expanded = ref(0)
const reviews = ref<FeedbackItem[]>([])
const loadingReviews = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const allSelected = computed(() =>
  rows.value.length > 0 && rows.value.every((r) => selected.value.includes(r.nm_id)))

// Таймер «прошло N с» — видно, что фоновая задача жива, а не зависла
const nowTs = ref(Date.now())
let tickTimer: ReturnType<typeof setInterval> | null = null
const elapsed = computed(() => {
  const j = job.job.value
  if (!j || !j.created_at) return 0
  const started = new Date(j.created_at).getTime()
  if (!started) return 0
  return Math.max(0, Math.round((nowTs.value - started) / 1000))
})

// --- промпт разбора (настройка компании) ---
const promptOpen = ref(false)
const promptIsCustom = ref(false)

async function openPrompt() {
  promptOpen.value = true
  try {
    const d = await feedbackInsightsApi.prompt()
    promptIsCustom.value = !!d.is_custom
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

function onPromptSaved() {
  promptIsCustom.value = true
}

function isSelected(nm: number) { return selected.value.includes(nm) }
function toggle(nm: number) {
  const i = selected.value.indexOf(nm)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(nm)
}
function toggleAll() {
  if (allSelected.value) {
    selected.value = selected.value.filter((nm) => !rows.value.some((r) => r.nm_id === nm))
    return
  }
  for (const r of rows.value) {
    if (!selected.value.includes(r.nm_id)) selected.value.push(r.nm_id)
  }
}

function buildParams() {
  const p: Record<string, any> = {
    date_from: filters.value.date_from || undefined,
    date_to: filters.value.date_to || undefined,
    q: filters.value.product || undefined,
    brand: filters.value.brand || undefined,
    category: filters.value.category || undefined,
    page: page.value,
    page_size: pageSize,
  }
  return p
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await feedbackInsightsApi.reviews(buildParams())
    rows.value = data.items || []
    total.value = data.total || 0
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
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
  router.replace({ path: route.path, query: q }).catch(() => {})
}

function onApply() {
  page.value = 1
  expanded.value = 0
  load()
}

function onReset() {
  filters.value = {
    date_from: filters.value.date_from,
    date_to: filters.value.date_to,
    product: '',
    brand: '',
    category: '',
  }
  selected.value = []
  onApply()
}

async function toggleExpand(nm: number) {
  if (expanded.value === nm) {
    expanded.value = 0
    return
  }
  expanded.value = nm
  loadingReviews.value = true
  try {
    const data = await feedbackInsightsApi.cardReviews(nm, {
      date_from: filters.value.date_from,
      date_to: filters.value.date_to,
      limit: 100,
    })
    reviews.value = data.items || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    reviews.value = []
  } finally {
    loadingReviews.value = false
  }
}

async function run() {
  if (!selected.value.length) return
  running.value = true
  error.value = ''
  try {
    const r = await feedbackInsightsApi.run({
      nm_ids: selected.value,
      date_from: filters.value.date_from,
      date_to: filters.value.date_to,
    })
    job.start(r.job_id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    running.value = false
  }
}

// После разбора — на страницу инсайтов этого запуска
function goToInsights() {
  const jid = job.job.value?.id
  router.push({ path: '/wb-feedback-insights', query: jid ? { job: String(jid) } : {} })
}

watch(() => job.finished.value, (f) => {
  if (f && job.job.value?.status === 'done') goToInsights()
})

function ratingClass(r: number | null): string {
  const v = Number(r || 0)
  if (v <= 2) return 'bg-danger'
  if (v === 3) return 'bg-warning text-dark'
  if (v === 4) return 'bg-info text-dark'
  return 'bg-success'
}

onMounted(async () => {
  try {
    const f = await feedbackInsightsApi.filters()
    brands.value = f.brands || []
    categories.value = f.categories || []
  } catch { /* списки пустые — фильтр работает без них */ }
  await load()
  tickTimer = setInterval(() => { nowTs.value = Date.now() }, 1000)
})
onUnmounted(() => {
  if (tickTimer) clearInterval(tickTimer)
})
</script>
