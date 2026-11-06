<template>
  <div class="container-xxl page-wb-promotions">
    <WbWorkspaceHead
      title="Акции WB"
      :workspace-tabs="PROMOTIONS_TABS"
      workspace-active="overview"
      :subtabs="subTabs"
      :active-sub="view"
    />

    <!-- Фильтр: стандартный выбор дат (WbDateRangeFilter) + тип акции -->
    <div class="wb-filter-panel">
      <WbDateRangeFilter
        v-model:from="filters.date_from"
        v-model:to="filters.date_to"
        default-preset="7"
        bare
        @apply="onApply"
      >
        <template #inline>
          <div class="wb-field">
            <label class="wb-field__label">Тип</label>
            <select v-model="filters.type" class="wb-select" @change="onApply">
              <option value="regular">Акции</option>
              <option value="auto">Автоакции</option>
              <option value="">Все</option>
            </select>
          </div>
        </template>
      </WbDateRangeFilter>

      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" @click="onApply">
          <i class="bi bi-search me-1"></i>Показать
        </button>
        <button class="btn btn--outline" :disabled="refreshing" title="Перезабрать календарь из WB (обычно это делает воркер по таймеру)" @click="refreshFromWb">
          <i class="bi bi-arrow-repeat me-1"></i>{{ refreshing ? 'Обновляем…' : 'Перезабрать сейчас' }}
        </button>
      </div>
      <div class="page-wb-promotions__fresh">
        <i class="bi bi-clock-history"></i>
        Календарь обновлён {{ fetchedAt || '—' }}
        <span class="page-wb-promotions__fresh-hint">воркер wbcms-promotions — ежечасно</span>
      </div>
    </div>

    <div v-if="error" class="page-wb-promotions__alert">
      <i class="bi bi-exclamation-triangle"></i>
      <span>{{ error }}</span>
    </div>

    <!-- Вкладка «Календарь» — полосы через даты -->
    <PromoTimeline
      v-if="view === 'calendar'"
      :rows="filtered"
      :date-from="applied.date_from"
      :date-to="applied.date_to"
      :scroll="scrollX"
      @open="openPromo"
      @scroll="onScroll"
    />

    <!-- Вкладка «Список» — таблица -->
    <PromoListTable
      v-else
      :rows="filtered"
      :loading="loading"
      :fetched-at="fetchedAt"
      @open="openPromo"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-promotions.css'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import WbDateRangeFilter from '@/components/common/WbDateRangeFilter.vue'
import PromoTimeline from '@/components/promotions/PromoTimeline.vue'
import PromoListTable from '@/components/promotions/PromoListTable.vue'
import { PROMOTIONS_TABS, type SubTab } from '@/components/common/workspaceTabs'
import type { PromoRow } from '@/api/promotions'

const route = useRoute()
const router = useRouter()
const qc = useQueryClient()

const view = computed(() => (String(route.query.view || '') === 'list' ? 'list' : 'calendar'))

/** Ссылки вкладок собираются из текущих фильтров — переключение их не сбрасывает. */
const tabTo = (id: string) => {
  const q: Record<string, string> = {
    date_from: applied.value.date_from,
    date_to: applied.value.date_to,
    type: applied.value.type,
    view: id,
  }
  const sc = String(route.query.scroll || '')
  if (sc) q.scroll = sc
  return { path: '/wb-promotions', query: q }
}
const subTabs = computed<SubTab[]>(() => [
  { id: 'calendar', label: 'Календарь', to: tabTo('calendar'), title: 'Календарь акций (полосы через даты)' },
  { id: 'list', label: 'Список', to: tabTo('list'), title: 'Список акций (таблица)' },
])

function isoDate(d: Date): string {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
}
/** Дефолтный период — последние N дней (как пресет WbDateRangeFilter). */
function defaultRange(days: number): { date_from: string; date_to: string } {
  const to = new Date()
  const from = new Date(to.getTime())
  from.setDate(from.getDate() - (days - 1))
  return { date_from: isoDate(from), date_to: isoDate(to) }
}

const TYPES = ['', 'regular', 'auto']

/** Фильтры живут в URL: F5 сохраняет подборку, ссылку можно отправить. */
const fromRoute = (q: any) => {
  const d = defaultRange(7)
  const t = String(q.type ?? 'regular')
  return {
    date_from: String(q.date_from || d.date_from),
    date_to: String(q.date_to || d.date_to),
    type: TYPES.includes(t) ? t : 'regular',
  }
}

const filters = ref(fromRoute(route.query))
const applied = ref({ ...filters.value })

const error = ref('')
const refreshing = ref(false)

const params = computed(() => ({
  date_from: applied.value.date_from,
  date_to: applied.value.date_to,
}))

const { data, isLoading: loading } = useQuery({
  queryKey: computed(() => ['promotions', 'calendar', params.value.date_from, params.value.date_to] as const),
  queryFn: () => api.get('/api/promotions/calendar', { params: params.value }).then(r => r.data),
})

const rows = computed<PromoRow[]>(() => (data.value?.rows as PromoRow[]) || [])
const fetchedAt = computed(() => {
  const top = String(data.value?.fetched_at || '')
  if (top) return top.slice(0, 16).replace('T', ' ')
  const t = rows.value.map(r => r.fetched_at || '').sort().pop() || ''
  return t ? t.slice(0, 16).replace('T', ' ') : ''
})
const filtered = computed(() => {
  if (!applied.value.type) return rows.value
  return rows.value.filter(r => r.promo_type === applied.value.type)
})

/** фильтры → URL (replace, чтобы не плодить историю) */
let syncing = false
function syncRoute() {
  const q: Record<string, string> = {
    date_from: applied.value.date_from,
    date_to: applied.value.date_to,
    type: applied.value.type,
  }
  if (view.value === 'list') q.view = 'list'
  const sc = String(route.query.scroll || '')
  if (sc) q.scroll = sc
  syncing = true
  router.replace({ path: '/wb-promotions', query: q })
    .finally(() => setTimeout(() => (syncing = false), 50))
}

/** Прокрутка календаря по горизонтали — тоже в URL: ссылка открывает то же место. */
function syncScroll(x: number) {
  if (syncing) return
  const q: Record<string, string> = {
    date_from: applied.value.date_from,
    date_to: applied.value.date_to,
    type: applied.value.type,
  }
  if (view.value === 'list') q.view = 'list'
  if (x > 0) q.scroll = String(Math.round(x))
  syncing = true
  router.replace({ path: '/wb-promotions', query: q })
    .finally(() => setTimeout(() => (syncing = false), 50))
}

const onApply = () => {
  const same = JSON.stringify(applied.value) === JSON.stringify(filters.value)
  applied.value = { ...filters.value }
  error.value = ''
  syncRoute()
  if (same) qc.invalidateQueries({ queryKey: ['promotions'] })
}

/** URL → фильтры (назад/вперёд, чужая ссылка) */
function applyFromRoute(nq: any) {
  const next = fromRoute(nq)
  if (JSON.stringify(applied.value) !== JSON.stringify(next)) {
    filters.value = { ...next }
    applied.value = { ...next }
  }
}

watch(() => route.query, (nq) => {
  if (syncing) return
  applyFromRoute(nq)
})

const refreshFromWb = async () => {
  refreshing.value = true
  error.value = ''
  try {
    await api.get('/api/promotions/calendar', { params: { ...params.value, refresh: 1 } })
    await qc.invalidateQueries({ queryKey: ['promotions'] })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Не удалось обновить из WB'
  } finally {
    refreshing.value = false
  }
}

const openPromo = (p: PromoRow) => {
  router.push({ path: '/wb-promotions/selection', query: { promo: String(p.promo_id) } })
}

/** Прокрутка календаря — в URL (с задержкой, чтобы не плодить историю). */
const scrollX = computed(() => Number(route.query.scroll || 0) || 0)
let scrollTimer: any = null
const onScroll = (x: number) => {
  if (scrollTimer) clearTimeout(scrollTimer)
  scrollTimer = setTimeout(() => syncScroll(x), 300)
}
</script>
