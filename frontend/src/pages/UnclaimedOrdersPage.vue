<template>
  <div class="container-xxl unclaimed-orders-page page-unclaimed-orders">
    <h1 class="page-title">Невыкупленные товары (Unclaimed)</h1>

    <div class="row">
      <div class="col-md-6">
        <WbFilterBar
          :show-card="true"
          v-model:nm-id="filters.nm_id"
          v-model:date-from="filters.date_from"
          v-model:date-to="filters.date_to"
          @apply="onApply"
          @reset="onReset"
        />
      </div>
      <div class="col-md-6">
        <div class="row g-2">
          <div class="col-6">
            <label class="form-label page-unclaimed-orders__filter-label">Порог отмен, %</label>
            <select v-model.number="filters.percent" class="form-select page-unclaimed-orders__filter-select" @change="onApply">
              <option :value="5">5%</option>
              <option :value="10">10%</option>
              <option :value="20">20%</option>
              <option :value="30">30%</option>
              <option :value="40">40%</option>
              <option :value="50">50%</option>
              <option :value="60">60%</option>
              <option :value="70">70%</option>
            </select>
          </div>
          <div class="col-6">
            <label class="form-label page-unclaimed-orders__filter-label">Мин. заказов</label>
            <select v-model.number="filters.min_orders" class="form-select page-unclaimed-orders__filter-select" @change="onApply">
              <option :value="1">1</option>
              <option :value="5">5</option>
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </div>
          <div class="col-6">
            <label class="form-label page-unclaimed-orders__filter-label">Сортировка</label>
            <select v-model="filters.sort" class="form-select page-unclaimed-orders__filter-select" @change="onSortChange">
              <option value="nm_id">Артикул WB</option>
              <option value="card_name">Название товара</option>
              <option value="vendorCode">Артикул продавца</option>
              <option value="rate">% Отмен</option>
              <option value="alls">Заказов</option>
              <option value="cancel">Отмен</option>
            </select>
          </div>
          <div class="col-6">
            <label class="form-label page-unclaimed-orders__filter-label">Направление</label>
            <select v-model="filters.dir" class="form-select page-unclaimed-orders__filter-select" @change="onSortChange">
              <option value="DESC">По убыванию</option>
              <option value="ASC">По возрастанию</option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <div class="card unclaimed-table-card wb-grid-card page-unclaimed-orders__grid">
      <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
        <span>Невыкупленные товары (с {{ tableDateFrom }})</span>
        <div class="d-flex align-items-center gap-2">
          <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!items.length">
            <i class="bi bi-file-earmark-excel me-1"></i>Excel
          </button>
          <span class="text-white-50 page-unclaimed-orders__head-count">Всего: {{ fmt0(total) }} · Стр {{ page }} / {{ totalPages }}</span>
        </div>
      </div>
      <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
      <div v-else-if="error" class="p-4 text-center text-danger">Не удалось загрузить данные.</div>
      <div v-else class="wb-table-wrap page-unclaimed-orders__table-wrap">
        <table ref="tableRef" class="table table-bordered table-striped table-hover kv-grid-table mb-0 unclaimed-table page-unclaimed-orders__table">
          <thead>
            <tr>
              <th style="width:100px; min-width:100px; text-align:center">Артикул WB</th>
              <th style="width:260px; min-width:220px; max-width:280px; text-align:center">Название товара</th>
              <th style="width:120px; min-width:120px; text-align:center">Артикул продавца</th>
              <th style="width:80px; min-width:80px; text-align:center">Заказов, шт</th>
              <th style="width:70px; min-width:70px; text-align:center">Отмен, шт</th>
              <th style="width:80px; min-width:80px; text-align:center">% Отмен</th>
              <th style="width:80px; min-width:80px; text-align:center">Выкупили, шт</th>
              <th style="width:110px; min-width:110px; text-align:center">Сумма выкупа, ₽</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="items.length === 0"><td colspan="8" class="text-center text-muted">Нет данных</td></tr>
            <tr v-for="row in items" :key="row.nm_id">
              <td class="page-unclaimed-orders__cell-id">
                <a :href="`/wb/detail?nm_id=${row.nm_id}`" target="_blank" class="page-unclaimed-orders__nm-link">{{ row.nm_id }}</a>
              </td>
              <td class="page-unclaimed-orders__cell-name" :title="row.card_name">{{ row.card_name || '—' }}</td>
              <td class="page-unclaimed-orders__cell-name" :title="row.vendorCode">{{ row.vendorCode || '—' }}</td>
              <td class="page-unclaimed-orders__cell-num">{{ fmtVal(row.alls, 0) }}</td>
              <td class="page-unclaimed-orders__cell-num" :style="{ color: row.cancel > 0 ? '#d9534f' : '' }">{{ fmtVal(row.cancel, 0) }}</td>
              <td class="page-unclaimed-orders__cell-num" :style="{ color: row.rate > 0.3 ? '#d9534f' : '' }">{{ fmt1(row.rate * 100) }}%</td>
              <td class="page-unclaimed-orders__cell-num">{{ fmtVal(row.bought, 0) }}</td>
              <td class="page-unclaimed-orders__cell-num">{{ fmtVal(row.sum_price, 2) }} ₽</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="page-unclaimed-orders__pager">
      <button class="btn btn-outline-secondary btn-sm" :disabled="page <= 1" @click="page--; fetchData()">Назад</button>
      <button class="btn btn-outline-secondary btn-sm" :disabled="page >= totalPages" @click="page++; fetchData()">Вперед</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-unclaimed-orders.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import WbFilterBar from '../components/common/WbFilterBar.vue'

const toIsoDate = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
const defaultDates = () => {
  const today = new Date()
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 14)
  return { date_from: toIsoDate(from), date_to: toIsoDate(today) }
}

interface UnclaimedParams {
  date_from: string
  date_to: string
  percent: number
  min_orders: number
  sort: string
  dir: string
}

interface UnclaimedItem {
  nm_id: number
  card_name: string
  vendorCode: string
  alls: number
  cancel: number
  rate: number
  bought: number
  sum_price: number | null
}

interface UnclaimedData {
  items: UnclaimedItem[]
  total: number
  page: number
  page_size: number
  params: UnclaimedParams
}

const route = useRoute()
const router = useRouter()
const PAGE_SIZE = 50

const defaultDateValues = defaultDates()
const filters = ref({
  date_from: defaultDateValues.date_from,
  date_to: defaultDateValues.date_to,
  nm_id: '',
  percent: 20,
  min_orders: 5,
  sort: 'rate',
  dir: 'DESC',
  page: 1,
})
const items = ref<UnclaimedItem[]>([])
const total = ref(0)
const page = ref(1)
const isLoading = ref(false)
const error = ref('')
const syncing = ref(false)
const tableRef = ref<HTMLTableElement | null>(null)
const data = ref<UnclaimedData | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const tableDateFrom = computed(() => data.value?.params.date_from || filters.value.date_from || '—')

const initFromQuery = () => {
  const q: Record<string, any> = route.query || {}
  const pick = (...keys: string[]) => {
    for (const key of keys) if (q[key]) return String(q[key])
    return ''
  }
  const df = pick('date_from', 'DPFilterForm[date_from]')
  const dt = pick('date_to', 'DPFilterForm[date_to]')
  const nm = pick('nm_id', 'DPFilterForm[nm_id]')
  const percent = pick('percent')
  const minOrders = pick('min_orders')
  const sort = pick('sort')
  const dir = pick('dir', 'sort_dir')
  const queryPage = pick('page')
  if (df) filters.value.date_from = df
  if (dt) filters.value.date_to = dt
  if (nm) filters.value.nm_id = nm
  if (percent) filters.value.percent = Number(percent)
  if (minOrders) filters.value.min_orders = Number(minOrders)
  if (sort) filters.value.sort = sort
  if (dir) filters.value.dir = dir.toUpperCase()
  if (queryPage) filters.value.page = Math.max(1, Number(queryPage) || 1)
}

const syncRoute = async () => {
  const q: Record<string, string> = {}
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  if (filters.value.nm_id) q.nm_id = filters.value.nm_id
  if (filters.value.percent !== 20) q.percent = String(filters.value.percent)
  if (filters.value.min_orders !== 5) q.min_orders = String(filters.value.min_orders)
  if (filters.value.sort !== 'rate') q.sort = filters.value.sort
  if (filters.value.dir !== 'DESC') q.dir = filters.value.dir
  if (filters.value.page > 1) q.page = String(filters.value.page)
  if (!Object.keys(q).length) return
  syncing.value = true
  try {
    await router.replace({ path: route.path, query: q })
  } finally {
    syncing.value = false
  }
}

const fetchData = async () => {
  isLoading.value = true
  error.value = ''
  const q = new URLSearchParams({
    date_from: filters.value.date_from,
    date_to: filters.value.date_to,
    percent: String(filters.value.percent),
    min_orders: String(filters.value.min_orders),
    sort: filters.value.sort,
    dir: filters.value.dir,
    page: String(filters.value.page),
    page_size: String(PAGE_SIZE),
  })
  if (filters.value.nm_id) q.set('nm_id', filters.value.nm_id)
  try {
    const { data:payload } = await api.get(`/api/unclaimed-orders?${q}`)
    items.value = Array.isArray(payload.items) ? payload.items : []
    total.value = Number(payload.total) || 0
    page.value = Number(payload.page) || filters.value.page
    if (payload.params) {
      filters.value.date_from = payload.params.date_from
      filters.value.date_to = payload.params.date_to
      filters.value.percent = Number(payload.params.percent)
      filters.value.min_orders = Number(payload.params.min_orders)
      filters.value.sort = payload.params.sort
      filters.value.dir = String(payload.params.dir).toUpperCase()
    }
    data.value = payload
  } catch {
    error.value = 'Не удалось загрузить данные.'
  } finally {
    isLoading.value = false
  }
}

const exportExcel = async () => {
  if (!items.value.length) return

  const XLSX = await import('xlsx')
  const data = items.value.map((row: UnclaimedItem) => ({
    'Артикул WB': row.nm_id,
    'Артикул продавца': row.vendorCode,
    'Название товара': row.card_name,
    'Заказов, шт': fmt0(row.alls),
    'Отмен, шт': fmt0(row.cancel),
    '% Отмен': fmt1(row.rate * 100),
    'Выкупили, шт': fmt0(row.bought),
    'Сумма выкупа, ₽': fmt2(row.sum_price ?? 0),
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [
    { wch: 12 },
    { wch: 18 },
    { wch: 32 },
    { wch: 12 },
    { wch: 12 },
    { wch: 12 },
    { wch: 14 },
    { wch: 18 },
  ]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Невыкупленные')
  XLSX.writeFile(wb, 'unclaimed-orders.xlsx')
}

const onApply = () => {
  filters.value.page = 1
  syncRoute()
  fetchData()
}

const onSortChange = () => {
  filters.value.page = 1
  syncRoute()
  fetchData()
}

const onReset = () => {
  const defaults = defaultDates()
  filters.value.nm_id = ''
  filters.value.date_from = defaults.date_from
  filters.value.date_to = defaults.date_to
  filters.value.percent = 20
  filters.value.min_orders = 5
  filters.value.sort = 'rate'
  filters.value.dir = 'DESC'
  filters.value.page = 1
  syncRoute()
  fetchData()
}

const fmt0 = (value: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(value) || 0))
const fmt1 = (value: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(value) || 0)
const fmt2 = (value: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value) || 0)
const fmtVal = (value: any, digits: number) => {
  if (value === null || value === undefined || value === '') return '—'
  if (digits === 0) return fmt0(value)
  if (digits === 1) return fmt1(value)
  return fmt2(value)
}

onMounted(() => {
  initFromQuery()
  fetchData()
})

watch(() => route.query, () => {
  if (syncing.value) return
  initFromQuery()
  fetchData()
})
</script>
