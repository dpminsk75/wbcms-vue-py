<template>
  <div class="container-xxl page-wb-profit">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">{{ 'Маржинальный учёт' }}</h1>
    </div>

    <!-- Вкладки раздела — чипы темы (.stab--line) -->
    <div class="page-wb-profit__tabs">
      <button v-for="t in TABS" :key="t.key" type="button"
              class="stab stab--line" :class="{ 'stab--on': tab === t.key }"
              @click="setTab(t.key)">
        <i :class="t.icon" class="me-1"></i>{{ t.label }}
      </button>
    </div>

    <!-- 1. Год к году (график + карточки) -->
    <div v-if="tab === 'yoy'">
      <YoyTab />
    </div>

    <!-- 2. Финансовая аналитика (с 2025 года) -->
    <div v-else-if="tab === 'monthly'">
      <MonthlyProfitTable />
    </div>

    <!-- 3. Топ товаров -->
    <div v-else-if="tab === 'top'" class="tbl-card tbl-card--compact page-wb-profit__block">
      <div class="card__hd">
        <span><i class="bi bi-crown me-2"></i>Топ 20 товаров</span>
        <span class="spacer"></span>
        <span class="hd-badge">{{ topPeriod }}</span>
        <ExcelButton :disabled="!topRows.length" @click="exportTop" />
      </div>
      <div class="page-wb-profit__filter">
        <WbDateRangeFilter v-model:from="topFrom" v-model:to="topTo" default-preset="90" bare />
        <div class="wb-filter-panel__btns">
          <button class="btn btn--brand wb-filter-panel__apply" @click="onTopApply">Применить</button>
          <button class="btn btn--outline wb-filter-panel__apply" @click="onTopReset">Сбросить</button>
        </div>
      </div>
      <div v-if="topLoading" class="text-center p-4 text-muted">
        <span class="spinner-border spinner-border-sm"></span> Загрузка данных...
      </div>
      <MarginTable
        v-else
        :rows="topRows"
        footer-label="Итого по ТОП-20:"
        :period="topPeriod"
        :date-from="topFrom"
        :date-to="topTo"
        resize-key="profit-sku-rank-top"
        compact
        show-breakdown
      />
    </div>

    <!-- 4. Худшие товары -->
    <div v-else class="tbl-card tbl-card--compact page-wb-profit__block">
      <div class="card__hd">
        <span><i class="bi bi-exclamation-triangle me-2"></i>Худшие 20 товаров</span>
        <span class="spacer"></span>
        <span class="hd-badge">{{ worstPeriod }}</span>
        <ExcelButton :disabled="!worstRows.length" @click="exportWorst" />
      </div>
      <div class="page-wb-profit__filter">
        <WbDateRangeFilter v-model:from="worstFrom" v-model:to="worstTo" default-preset="90" bare />
        <div class="wb-filter-panel__btns">
          <button class="btn btn--brand wb-filter-panel__apply" @click="onWorstApply">Применить</button>
          <button class="btn btn--outline wb-filter-panel__apply" @click="onWorstReset">Сбросить</button>
        </div>
      </div>
      <div v-if="worstLoading" class="text-center p-4 text-muted">
        <span class="spinner-border spinner-border-sm"></span> Загрузка данных...
      </div>
      <MarginTable
        v-else
        :rows="worstRows"
        footer-label="Итого по худшим-20:"
        :period="worstPeriod"
        :date-from="worstFrom"
        :date-to="worstTo"
        resize-key="profit-sku-rank-worst"
        compact
        show-breakdown
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-profit.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'
import { exportMarginExcel } from '@/api/profit'
import MarginTable from '@/components/profit/MarginTable.vue'
import MonthlyProfitTable from '@/components/profit/MonthlyProfitTable.vue'
import YoyTab from '@/components/profit/YoyTab.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import WbDateRangeFilter from '@/components/common/WbDateRangeFilter.vue'

type TabKey = 'yoy' | 'monthly' | 'top' | 'worst'

const TABS = [
  { key: 'yoy' as TabKey, label: 'Год к году', icon: 'bi bi-bar-chart-line' },
  { key: 'monthly' as TabKey, label: 'Аналитика (с 2025 года)', icon: 'bi bi-graph-up' },
  { key: 'top' as TabKey, label: 'Топ-20 товаров', icon: 'bi bi-crown' },
  { key: 'worst' as TabKey, label: 'Худшие-20 товаров', icon: 'bi bi-exclamation-triangle' },
]

const route = useRoute()
const router = useRouter()

// --- активный таб живёт в URL (?tab=top|worst) — ссылку можно переслать ---
const TAB_KEYS: TabKey[] = ['yoy', 'monthly', 'top', 'worst']
const tabFromRoute = computed<TabKey>(() => {
  const t = String(route.query.tab || '')
  return (TAB_KEYS as string[]).includes(t) ? (t as TabKey) : 'yoy'
})
const tab = ref<TabKey>(tabFromRoute.value)
// назад/вперёд в браузере — тоже меняют таб
watch(tabFromRoute, (v) => { if (v !== tab.value) tab.value = v })

function setTab(key: TabKey) {
  tab.value = key
  const q: Record<string, any> = { ...route.query }
  if (key === 'yoy') delete q.tab
  else q.tab = key
  router.push({ path: route.path, query: q })
}

// --- период списков товаров (у Топ-20 и Худших-20 свой) ---
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const lastDays = (n: number): [string, string] => {
  const to = new Date()
  const from = new Date(to)
  from.setDate(from.getDate() - (n - 1))
  return [fmtD(from), fmtD(to)]
}
const [defFrom, defTo] = lastDays(90)

// Даты фильтра живут в URL (?top_from/top_to, ?worst_from/worst_to) —
// ссылку на период можно переслать, кнопки «назад/вперёд» работают.
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const qDate = (v: unknown): string => {
  const s = Array.isArray(v) ? String(v[0] ?? '') : String(v ?? '')
  return DATE_RE.test(s) ? s : ''
}

const topFrom = ref(qDate(route.query.top_from) || defFrom)
const topTo = ref(qDate(route.query.top_to) || defTo)
const worstFrom = ref(qDate(route.query.worst_from) || defFrom)
const worstTo = ref(qDate(route.query.worst_to) || defTo)
// applied — периоды, по которым реально запрошены данные (запрос — по кнопке «Применить»)
const topApplied = ref({ from: topFrom.value, to: topTo.value })
const worstApplied = ref({ from: worstFrom.value, to: worstTo.value })

/** Записать периоды в URL (replace — чтобы не засорять историю браузера). */
const pushDates = (patch: Record<string, string>) => {
  const q: Record<string, any> = { ...route.query, ...patch }
  router.replace({ path: route.path, query: q })
}

const onTopApply = () => {
  topApplied.value = { from: topFrom.value, to: topTo.value }
  pushDates({ top_from: topFrom.value, top_to: topTo.value })
}
const onTopReset = () => {
  topFrom.value = defFrom
  topTo.value = defTo
  onTopApply()
}
const onWorstApply = () => {
  worstApplied.value = { from: worstFrom.value, to: worstTo.value }
  pushDates({ worst_from: worstFrom.value, worst_to: worstTo.value })
}
const onWorstReset = () => {
  worstFrom.value = defFrom
  worstTo.value = defTo
  onWorstApply()
}

// Назад/вперёд в браузере — периоды подхватываются из URL.
watch(() => [route.query.top_from, route.query.top_to,
  route.query.worst_from, route.query.worst_to] as const,
  ([tf, tt, wf, wt]) => {
    const nTopFrom = qDate(tf) || defFrom
    const nTopTo = qDate(tt) || defTo
    if (nTopFrom !== topFrom.value || nTopTo !== topTo.value) {
      topFrom.value = nTopFrom
      topTo.value = nTopTo
    }
    const nWorstFrom = qDate(wf) || defFrom
    const nWorstTo = qDate(wt) || defTo
    if (nWorstFrom !== worstFrom.value || nWorstTo !== worstTo.value) {
      worstFrom.value = nWorstFrom
      worstTo.value = nWorstTo
    }
  })

// При первом открытии кладём дефолтные периоды (90 дней) в URL —
// ссылка всегда несёт конкретный период.
onMounted(() => {
  const patch: Record<string, string> = {}
  if (!qDate(route.query.top_from) || !qDate(route.query.top_to)) {
    patch.top_from = topFrom.value
    patch.top_to = topTo.value
  }
  if (!qDate(route.query.worst_from) || !qDate(route.query.worst_to)) {
    patch.worst_from = worstFrom.value
    patch.worst_to = worstTo.value
  }
  if (Object.keys(patch).length) pushDates(patch)
})

const { data: topData, isLoading: topLoading } = useQuery({
  queryKey: computed(() => ['wb-profit-sku-rank', 'desc', topApplied.value.from, topApplied.value.to] as const),
  queryFn: () => api.get('/api/wb-profit/sku-rank', {
    params: { order: 'desc', date_from: topApplied.value.from, date_to: topApplied.value.to, limit: 20 },
  }).then(r => r.data),
  enabled: computed(() => tab.value === 'top'),
})

const { data: worstData, isLoading: worstLoading } = useQuery({
  queryKey: computed(() => ['wb-profit-sku-rank', 'asc', worstApplied.value.from, worstApplied.value.to] as const),
  queryFn: () => api.get('/api/wb-profit/sku-rank', {
    params: { order: 'asc', date_from: worstApplied.value.from, date_to: worstApplied.value.to, limit: 20 },
  }).then(r => r.data),
  enabled: computed(() => tab.value === 'worst'),
})

const topRows = computed<any[]>(() => (topData.value?.rows as any[]) || [])
const worstRows = computed<any[]>(() => (worstData.value?.rows as any[]) || [])

// период показываем из ответа бэка (фактический срез), иначе — запрошенный
const topPeriod = computed(() => {
  const from = String(topData.value?.date_from || topFrom.value)
  const to = String(topData.value?.date_to || topTo.value)
  return from && to ? `${from} — ${to}` : ''
})
const worstPeriod = computed(() => {
  const from = String(worstData.value?.date_from || worstFrom.value)
  const to = String(worstData.value?.date_to || worstTo.value)
  return from && to ? `${from} — ${to}` : ''
})

const exportTop = () => exportMarginExcel(topRows.value, `wb-profit_top_${topFrom.value}_${topTo.value}.xlsx`, 'Топ-20')
const exportWorst = () => exportMarginExcel(worstRows.value, `wb-profit_worst_${worstFrom.value}_${worstTo.value}.xlsx`, 'Худшие-20')
</script>
