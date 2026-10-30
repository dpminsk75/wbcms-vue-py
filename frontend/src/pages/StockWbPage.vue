<template>
  <div class="container-xxl page-stock-wb">
    <!-- шапка рабочего места + вкладки раздела (новый вид: .stab--line) -->
    <div class="wsp">
      <div class="wsp__head">
        <h3 class="wsp__title">Анализ остатков</h3>
        <nav class="wsp__menu">
          <a class="mn mn--on" href="/wb-sales-analysis">Отчёты</a>
          <a class="mn" href="/wb-order/feed-aggregated">Заказы</a>
          <a class="mn" href="/wb-stock-reports/balance">Склад</a>
        </nav>
      </div>
      <WbSectionTabs v-model="tab" :tabs="TABS" />
    </div>

    <!-- фильтр отчёта: WbUniversalFilter (даты, товар, бренд, категория) + поля страницы -->
    <div class="mt-3">
      <WbUniversalFilter
        v-model:date-from="dateFrom"
        v-model:date-to="dateTo"
        v-model:product="product"
        v-model:brand="brand"
        v-model:category="category"
        :brands="brands"
        :categories="categories"
        :show-product="true"
        :show-brand-category="true"
        @apply="applyFilters"
        @reset="resetFilters"
      >
        <template #extra>
          <WbChipGroup v-if="tab === 'turnover'" v-model="demand" label="Спрос" :options="DEMAND_OPTS" />
          <WbChipGroup v-if="tab === 'turnover'" v-model="deficitDays" label="Порог дней" :options="DEFICIT_OPTS" />
          <WbChipGroup v-model="priceMode" label="Цена" :options="PRICE_OPTS" />
          <WbChipGroup v-if="tab === 'sklads'" v-model="topLimit" label="ТОП" :options="TOP_OPTS" />
          <WbChipGroup v-if="tab === 'sklads'" v-model="skladMode" label="Склады" :options="SKLAD_OPTS" />
        </template>
      </WbUniversalFilter>
    </div>

    <p v-if="periodText" class="page-stock-wb__note">
      Данные продаж по <b>{{ dataDate || '—' }}</b> · окно спроса <b>{{ periodText }}</b> ·
      остатки — срез <b>{{ snapshotDate || '—' }}</b> ·
      спрос по складу <b>«Склад WB»</b> (FBO): остатки складов WB обслуживают только FBO-продажи.
    </p>

    <div v-if="isError" class="wb-panel mt-3">
      <div class="wb-panel__bd">
        <span class="badge badge--bad">Ошибка загрузки</span>
        <div class="mt-2">Не удалось получить данные отчёта. Проверьте выбор компании и повторите.</div>
      </div>
    </div>

    <div v-if="isLoading" class="text-center py-5">
      <div class="spinner-border" role="status"></div>
      <div class="text-muted mt-2">Загрузка данных...</div>
    </div>

    <template v-else-if="tab === 'turnover'">
      <div v-if="isEmpty" class="wb-panel mt-3">
        <div class="wb-panel__bd page-stock-wb__empty">
          <div class="page-stock-wb__empty-icon"><i class="bi bi-inboxes"></i></div>
          <div class="page-stock-wb__empty-title">Нет данных за выбранный период</div>
          <div class="page-stock-wb__empty-sub">
            Продажи WB доступны по {{ dataDate || '—' }}, а период задан позже —
            выберите период, который заканчивается не позже даты данных, или сбросьте фильтр.
          </div>
          <button type="button" class="btn btn--outline btn-sm mt-3" @click="resetFilters">Сбросить фильтр</button>
        </div>
      </div>

      <template v-else>
        <div class="grid-4 mt-3">
          <KpiTile
            variant="tile--10"
            label="Скоро кончится"
            :value="kpi.deficit"
            :delta="deficitDeltaText"
            foot="остаток менее чем на порог фильтра"
          />
          <KpiTile
            variant="tile--9"
            label="Нет в наличии"
            :value="kpi.out_of_stock"
            foot="есть спрос, остатка нет"
          />
          <KpiTile
            variant="tile--11"
            label="Излишки"
            :value="kpi.excess"
            foot="более 60 дней или нет продаж"
          />
          <KpiTile
            variant="tile--1"
            label="Остаток на складах WB"
            :value="fmt0(kpi.stock_total) + ' шт'"
            :delta="stockDeltaText"
            :foot="fmt0(kpi.stock_items) + ' товаров'"
          />
        </div>

        <div class="mt-3">
          <TurnoverTable
            :title="'Скоро кончится: остаток менее чем на ' + deficitDays + ' дней'"
            variant="deficit"
            :rows="deficitRows"
            :total="deficitTotal"
            :date-from="periodFrom"
            :date-to="periodTo"
          />
        </div>
        <div class="mt-3">
          <TurnoverTable
            title="Нет в наличии: товары кончились, но есть спрос"
            variant="out_of_stock"
            :rows="outRows"
            :total="outTotal"
            :date-from="periodFrom"
            :date-to="periodTo"
          />
        </div>
        <div class="mt-3">
          <TurnoverTable
            title="Излишки и неликвиды: запас более 60 дней или нет продаж"
            variant="excess"
            :rows="excessRows"
            :total="excessTotal"
            :date-from="periodFrom"
            :date-to="periodTo"
          />
        </div>
      </template>
    </template>

    <template v-else>
      <div v-if="isEmpty" class="wb-panel mt-3">
        <div class="wb-panel__bd page-stock-wb__empty">
          <div class="page-stock-wb__empty-icon"><i class="bi bi-inboxes"></i></div>
          <div class="page-stock-wb__empty-title">Нет данных за выбранный период</div>
          <div class="page-stock-wb__empty-sub">
            Продажи WB доступны по {{ dataDate || '—' }} — выберите период, который заканчивается не позже даты данных.
          </div>
          <button type="button" class="btn btn--outline btn-sm mt-3" @click="resetFilters">Сбросить фильтр</button>
        </div>
      </div>
      <SkladDemandTable
        v-else
        class="mt-3"
        :warehouses="warehouses"
        :total="warehousesTotal"
        :top-rows="topRows"
        :top-total="topTotal"
        :top-limit="Number(topLimit)"
        :date-from="periodFrom"
        :date-to="periodTo"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-stock-wb.css'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'
import { useNumFmt } from '@/composables/useNumFmt'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import WbChipGroup from '@/components/common/WbChipGroup.vue'
import WbSectionTabs from '@/components/common/WbSectionTabs.vue'
import KpiTile from '@/components/common/KpiTile.vue'
import TurnoverTable from '@/components/stock-wb/TurnoverTable.vue'
import SkladDemandTable from '@/components/stock-wb/SkladDemandTable.vue'

const route = useRoute()
const router = useRouter()
const { fmt0 } = useNumFmt()

const TABS = [
  { id: 'turnover', label: 'Оборачиваемость' },
  { id: 'sklads', label: 'По складам' },
]
const DEMAND_OPTS = [
  { value: 'fbo', label: 'FBO' },
  { value: 'all', label: 'FBO+FBS' },
]
const DEFICIT_OPTS = [
  { value: '3', label: '3' },
  { value: '7', label: '7' },
  { value: '14', label: '14' },
  { value: '30', label: '30' },
]
const PRICE_OPTS = [
  { value: 'wb', label: 'Со скидкой' },
  { value: 'cost', label: 'Себестоимость' },
]
const TOP_OPTS = [
  { value: '20', label: '20' },
  { value: '50', label: '50' },
  { value: '100', label: '100' },
  { value: '500', label: '500' },
]
const SKLAD_OPTS = [
  { value: 'all', label: 'Все' },
  { value: 'top', label: 'ТОП-20' },
]

const q = (v: unknown): string => (Array.isArray(v) ? String(v[0] ?? '') : String(v ?? ''))

/** Локальная дата (toISOString даёт UTC и сдвигает сутки). */
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const lastDays = (n: number): [string, string] => {
  const to = new Date()
  const from = new Date(to)
  from.setDate(from.getDate() - (n - 1))
  return [fmtD(from), fmtD(to)]
}
const [defFrom, defTo] = lastDays(14)

const tab = ref(q(route.query.tab) === 'sklads' ? 'sklads' : 'turnover')
const dateFrom = ref(q(route.query.date_from) || defFrom)
const dateTo = ref(q(route.query.date_to) || defTo)
const product = ref(q(route.query.product))
const brand = ref(q(route.query.brand))
const category = ref(q(route.query.category))
const demand = ref(q(route.query.demand) || 'fbo')
const deficitDays = ref(q(route.query.threshold) || '7')
const priceMode = ref(q(route.query.price) || 'wb')
const topLimit = ref(q(route.query.top) || '50')
const skladMode = ref(q(route.query.mode) || 'all')

const brands = ref<string[]>([])
const categories = ref<string[]>([])

const { data: optionsData } = useQuery({
  queryKey: ['stock-analytics-options'],
  queryFn: () => api.get('/api/stock-analytics/options').then(r => r.data),
  staleTime: 300_000,
})

watch(optionsData, (d: any) => {
  brands.value = d?.brands || []
  categories.value = d?.categories || []
})

const commonParams = computed(() => ({
  date_from: dateFrom.value || undefined,
  date_to: dateTo.value || undefined,
  product: product.value || undefined,
  brand: brand.value || undefined,
  category: category.value || undefined,
  price_mode: priceMode.value,
}))

const turnoverQuery = useQuery({
  queryKey: computed(() => ['stock-analytics-turnover', commonParams.value, demand.value, deficitDays.value] as const),
  queryFn: () => api.get('/api/stock-analytics/turnover', {
    params: { ...commonParams.value, fbo_only: demand.value === 'fbo' ? 1 : 0, threshold: Number(deficitDays.value) },
  }).then(r => r.data),
  enabled: computed(() => tab.value === 'turnover'),
})

const skladsQuery = useQuery({
  queryKey: computed(() => ['stock-analytics-sklads', commonParams.value, topLimit.value, skladMode.value] as const),
  queryFn: () => api.get('/api/stock-analytics/sklads', {
    params: { ...commonParams.value, top: Number(topLimit.value), mode: skladMode.value },
  }).then(r => r.data),
  enabled: computed(() => tab.value === 'sklads'),
})

const isLoading = computed(() => tab.value === 'turnover' ? turnoverQuery.isLoading.value : skladsQuery.isLoading.value)
const isError = computed(() => tab.value === 'turnover' ? turnoverQuery.isError.value : skladsQuery.isError.value)

const report = computed<any>(() => (tab.value === 'turnover' ? turnoverQuery.data.value : skladsQuery.data.value) || {})
const isEmpty = computed(() => !!report.value.empty)

const kpi = computed<any>(() => report.value.kpi || { deficit: 0, out_of_stock: 0, excess: 0, stock_total: 0, stock_delta: 0, stock_items: 0 })
const deficitRows = computed<any[]>(() => report.value.deficit?.rows || [])
const deficitTotal = computed<number>(() => report.value.deficit?.total || 0)
const outRows = computed<any[]>(() => report.value.out_of_stock?.rows || [])
const outTotal = computed<number>(() => report.value.out_of_stock?.total || 0)
const excessRows = computed<any[]>(() => report.value.excess?.rows || [])
const excessTotal = computed<number>(() => report.value.excess?.total || 0)
const warehouses = computed<any[]>(() => report.value.warehouses || [])
const warehousesTotal = computed<any>(() => report.value.warehouses_total || {})
const topRows = computed<any[]>(() => report.value.top?.rows || [])
const topTotal = computed<number>(() => report.value.top?.total || 0)

const dataDate = computed(() => report.value.data_date || '')
const snapshotDate = computed(() => report.value.snapshot_date || '')
const periodFrom = computed(() => report.value.period?.from || dateFrom.value)
const periodTo = computed(() => report.value.period?.to || dateTo.value)
const periodText = computed(() => {
  const p = report.value.period
  return p?.from && p?.to ? `${p.from} — ${p.to} (${p.days} дн.)` : ''
})

/** Дельта дефицита: «+3 товара к 22.10» (дата снимка, с которым сравниваем). */
const deficitDeltaText = computed(() => {
  const d = kpi.value.deficit_delta
  const prev = report.value.prev_snapshot_date
  if (d === null || d === undefined || !prev) return ''
  return `${d > 0 ? '+' : ''}${d} товара к ${prev}`
})

/** Дельта остатка: «+142 за сутки». */
const stockDeltaText = computed(() => {
  const d = Number(kpi.value.stock_delta || 0)
  if (!d) return ''
  return `${d > 0 ? '+' : ''}${fmt0(d)} за сутки`
})

function applyFilters() {
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      tab: tab.value,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      product: product.value || undefined,
      brand: brand.value || undefined,
      category: category.value || undefined,
      demand: demand.value,
      threshold: deficitDays.value,
      price: priceMode.value,
      top: topLimit.value,
      mode: skladMode.value,
    },
  })
}

function resetFilters() {
  const [f, t0] = lastDays(14)
  dateFrom.value = f
  dateTo.value = t0
  product.value = ''
  brand.value = ''
  category.value = ''
  demand.value = 'fbo'
  deficitDays.value = '7'
  priceMode.value = 'wb'
  topLimit.value = '50'
  skladMode.value = 'all'
  applyFilters()
}

watch([tab, demand, deficitDays, priceMode, topLimit, skladMode], () => {
  applyFilters()
})
</script>
