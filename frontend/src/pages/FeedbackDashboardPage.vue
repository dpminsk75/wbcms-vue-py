<template>
  <div class="container-xxl page-feedback-dashboard">
    <FeedbackHead :title="$route.meta.title || 'Отзывы: Обзор'" active="dashboard" />

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
    >
      <!-- дополнительный фильтр блока «Отзывы»: какие отзывы считаем -->
      <template #extra>
        <div class="page-feedback-dashboard__rev-filter">
          <label class="form-label mb-0 small fw-medium text-muted">Отзывы</label>
          <select v-model="filters.rev_mode" class="form-control form-control-sm"
                  @change="load">
            <option v-for="m in revModes" :key="m.id" :value="m.id" :title="m.title">
              {{ m.label }}
            </option>
          </select>
        </div>
      </template>
    </WbUniversalFilter>

    <div v-if="error" class="wb-error mb-3">{{ error }}</div>

    <template v-else-if="summary">
      <!-- 1. Аналитика -->
      <FeedbackKpiCards :kpi="summary.kpi" :delta="summary.delta" :ratings="summary.ratings" />

      <!-- 2. Три доната -->
      <div class="row">
        <div class="col-12 col-md-4">
          <FeedbackDonutChart title="Тональность" :data="toneData" :total="summary.kpi.reviews_cnt" />
        </div>
        <div class="col-12 col-md-4">
          <FeedbackDonutChart v-if="aiParsed" title="Эмоциональность" :data="emotionData" :total="aiParsed" />
          <FeedbackEmptyDonut v-else title="Эмоциональность" />
        </div>
        <div class="col-12 col-md-4">
          <FeedbackDonutChart v-if="aiParsed" title="Конструктивность" :data="constructData" :total="aiParsed" />
          <FeedbackEmptyDonut v-else title="Конструктивность" />
        </div>
      </div>
      <div v-if="aiParsed" class="small text-muted mb-3">
        ИИ-разбор отзывов: {{ aiParsed }} из {{ aiTotal }} (за выбранный период)
        <template v-if="aiToneText"> · ИИ-тон: {{ aiToneText }}</template>
      </div>

      <!-- 3. Динамика -->
      <div class="row mt-3">
        <div class="col-12 col-lg-6">
          <FeedbackLineChart
            title="Динамика отзывов"
            :categories="dayCategories"
            :series="countSeries"
            :periods="periodOptions"
            @update:period="onPeriodChange"
          />
        </div>
        <div class="col-12 col-lg-6">
          <FeedbackLineChart
            title="Динамика средней оценки"
            :categories="dayCategories"
            :series="ratingSeries"
            :periods="periodOptions"
            :y-min="1"
            :y-max="5"
          />
        </div>
      </div>
    </template>

    <!-- 4. Обзор товаров -->
    <div class="mt-3">
      <FeedbackProductsTable
        v-model:limit="cardsLimit"
        :items="cards"
        :loading="cardsLoading"
        :orders-note="ordersNote"
        :empty-text="emptyText"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-feedback-dashboard.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import FeedbackHead from '@/components/feedback/FeedbackHead.vue'
import FeedbackKpiCards from '@/components/feedback/FeedbackKpiCards.vue'
import FeedbackDonutChart, { type DonutItem } from '@/components/feedback/FeedbackDonutChart.vue'
import FeedbackEmptyDonut from '@/components/feedback/FeedbackEmptyDonut.vue'
import FeedbackLineChart, { type LineSeries } from '@/components/feedback/FeedbackLineChart.vue'
import FeedbackProductsTable from '@/components/feedback/FeedbackProductsTable.vue'
import { feedbackDashboardApi, type DashCard, type DashPeriod, type DashRevMode, type DashSummary } from '@/api/feedbackDashboard'
import { daysAgoStr, todayStr } from '@/utils/dates'

const route = useRoute()
const router = useRouter()

const brands = ref<string[]>([])
const categories = ref<string[]>([])

const filters = ref({
  date_from: String(route.query.date_from || daysAgoStr(30)),
  date_to: String(route.query.date_to || todayStr()),
  product: String(route.query.product || ''),
  brand: String(route.query.brand || ''),
  category: String(route.query.category || ''),
  // какие отзывы считаем: all / content (с текстом или тегами) / rated (с оценкой)
  rev_mode: (['all', 'content', 'rated'].includes(String(route.query.rev_mode))
    ? String(route.query.rev_mode)
    : 'all') as DashRevMode,
})

const summary = ref<DashSummary | null>(null)
const cards = ref<DashCard[]>([])
const cardsMeta = ref({ total: 0, withReviews: 0, ordersMissing: false })
const cardsLimit = ref(20)
const cardsLoading = ref(false)
const error = ref('')

// подпись под таблицей: куб заказов пуст или отстал
const ordersNote = computed(() => {
  const m = cardsMeta.value
  if (m.ordersMissing) return 'Заказы: в кубе агрегации нет данных — сортировка по количеству отзывов.'
  return ''
})

// текст вместо «Нет данных» — видно, где обрыв (заказы/отзывы)
const emptyText = computed(() => {
  const m = cardsMeta.value
  if (!m.total && !m.withReviews) return 'Нет данных: за период нет ни отзывов, ни заказов.'
  if (!m.total) return `Нет данных: в кубе заказов нет карточек (${m.withReviews} с отзывами).`
  return `Нет данных: карточек с отзывами не найдено (${m.total} с заказами).`
})

const period = ref<DashPeriod>('day')
const periodOptions = [
  { id: 'day', label: 'Дни' },
  { id: 'week', label: 'Недели' },
  { id: 'month', label: 'Месяцы' },
]

// Фильтр по отзывам: что вообще считаем «отзывом».
const revModes: { id: DashRevMode; label: string; title: string }[] = [
  { id: 'all', label: 'Все', title: 'Все отзывы за период' },
  { id: 'content', label: 'С текстом/тегами', title: 'Отзывы с текстом или с тегами (bables)' },
  { id: 'rated', label: 'Только оценка', title: 'Только отзывы с оценкой (1–5)' },
]

function buildParams() {
  const p: Record<string, any> = {
    date_from: filters.value.date_from,
    date_to: filters.value.date_to,
    period: period.value,
    rev_mode: filters.value.rev_mode,
    q: filters.value.product || undefined,
    brand: filters.value.brand || undefined,
    category: filters.value.category || undefined,
  }
  return p
}

async function load() {
  error.value = ''
  try {
    summary.value = await feedbackDashboardApi.summary(buildParams())
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    summary.value = null
  }
  syncRoute()
  loadCards()
}

async function loadCards() {
  cardsLoading.value = true
  try {
    const p: Record<string, any> = {
      date_from: filters.value.date_from,
      date_to: filters.value.date_to,
      limit: cardsLimit.value,
      rev_mode: filters.value.rev_mode,
      q: filters.value.product || undefined,
      brand: filters.value.brand || undefined,
      category: filters.value.category || undefined,
    }
    const d = await feedbackDashboardApi.cards(p)
    cards.value = d.items || []
    cardsMeta.value = {
      total: d.cards_total || 0,
      withReviews: d.cards_with_reviews || 0,
      ordersMissing: !!d.orders_missing,
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    cards.value = []
  } finally {
    cardsLoading.value = false
  }
}

function onPeriodChange(id: string) {
  period.value = id as DashPeriod
  load()
}

function onReset() {
  filters.value = {
    date_from: filters.value.date_from,
    date_to: filters.value.date_to,
    product: '',
    brand: '',
    category: '',
    rev_mode: 'all',
  }
  load()
}

function syncRoute() {
  const q: Record<string, string> = {}
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  if (filters.value.product) q.product = filters.value.product
  if (filters.value.brand) q.brand = filters.value.brand
  if (filters.value.category) q.category = filters.value.category
  if (period.value !== 'day') q.period = period.value
  if (filters.value.rev_mode !== 'all') q.rev_mode = filters.value.rev_mode
  // замена роута — через useRouter(), у useRoute() нет метода replace
  router.replace({ path: route.path, query: q }).catch(() => {})
}

// --- данные для графиков ---

const toneData = computed<DonutItem[]>(() => {
  const s = summary.value
  if (!s) return []
  const total = s.kpi.reviews_cnt || 1
  const pos = Math.round((s.sentiment.positive || 0) * 100 / total)
  const neg = Math.round((s.sentiment.negative || 0) * 100 / total)
  const none = Math.max(0, 100 - pos - neg)
  return [
    { name: 'Позитив', value: pos, color: '#4f7d5b' },
    { name: 'Негатив', value: neg, color: '#e0a16f' },
    { name: 'Без оценки', value: none, color: '#c9ccd4' },
  ]
})

// --- метки ИИ-разбора отзывов (донаты «Эмоциональность» / «Конструктивность») ---
const AI_LEVELS: Record<string, string> = {
  low: 'низкая', mid: 'средняя', high: 'высокая',
}
const AI_COLORS: Record<string, string> = {
  low: '#c9ccd4', mid: '#e0a16f', high: '#4f7d5b',
}
const aiSentiment = computed(() => summary.value?.ai_sentiment || null)
const aiParsed = computed(() => aiSentiment.value?.parsed || 0)
const aiTotal = computed(() => aiSentiment.value?.total || 0)

const aiData = (levels: { name: string; cnt: number }[] | undefined): DonutItem[] =>
  (levels || []).map((l) => ({
    name: AI_LEVELS[l.name] || l.name,
    value: l.cnt || 0,
    color: AI_COLORS[l.name] || '#c9ccd4',
  }))

const emotionData = computed<DonutItem[]>(() => aiData(aiSentiment.value?.emotion))
const constructData = computed<DonutItem[]>(() => aiData(aiSentiment.value?.constructiveness))

// ИИ-тон текстом — для сверки с «Тональностью» по оценке
const AI_TONE_LABELS: Record<string, string> = {
  pos: 'позитив', neg: 'негатив', neutral: 'неопределён',
}
const aiToneText = computed(() =>
  (aiSentiment.value?.tone || [])
    .filter((t) => t.cnt)
    .map((t) => `${AI_TONE_LABELS[t.name] || t.name} ${t.cnt}`)
    .join(' · '))

const dayCategories = computed(() => (summary.value?.daily || []).map((d) => d.d))
const countSeries = computed<LineSeries[]>(() => [
  { name: 'Всего', color: '#2563eb', values: (summary.value?.daily || []).map((d) => d.cnt) },
  { name: 'Позитив', color: '#4f7d5b', values: (summary.value?.daily || []).map((d) => d.pos) },
  { name: 'Негатив', color: '#e0a16f', values: (summary.value?.daily || []).map((d) => d.neg) },
])
const ratingSeries = computed<LineSeries[]>(() => [
  { name: 'Средняя оценка', color: '#7c3aed', values: (summary.value?.daily || []).map((d) => d.avg_rating) },
])

watch(cardsLimit, () => loadCards())

onMounted(async () => {
  try {
    const o = await feedbackDashboardApi.options()
    brands.value = o.brands || []
    categories.value = o.categories || []
  } catch { /* списки пустые — фильтр работает без них */ }
  await load()
})
</script>
