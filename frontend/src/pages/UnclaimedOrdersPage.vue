<template>
  <div class="container-xxl unclaimed-orders-page page-unclaimed-orders">
    <h1 class="page-title">Возвраты</h1>

    <!-- Фильтр: общий WbUniversalFilter — даты, товар, бренд, категория, быстрые кнопки.
         Поля страницы (порог/мин. заказов/сортировка/направление) — в слоте #fields,
         отдельной строкой над кнопками. Кнопки «Применить/Сбросить» — у компоненты. -->
    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:product="filters.product"
      v-model:brand="filters.brand"
      v-model:category="filters.category"
      :brands="filterLists.brands"
      :categories="filterLists.categories"
      @apply="onApply"
      @reset="onReset"
    >
      <template #fields>
        <div class="wb-field">
          <label class="wb-field__label">Порог отмен, %</label>
          <select v-model.number="filters.percent" class="form-control">
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
        <div class="wb-field">
          <label class="wb-field__label">Мин. заказов</label>
          <select v-model.number="filters.min_orders" class="form-control">
            <option :value="1">1</option>
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </div>
        <div class="wb-field">
          <label class="wb-field__label">Сортировка</label>
          <select v-model="filters.sort" class="form-control">
            <option value="nm_id">Артикул WB</option>
            <option value="card_name">Название товара</option>
            <option value="vendorCode">Артикул продавца</option>
            <option value="rate">% Отмен</option>
            <option value="alls">Заказов</option>
            <option value="cancel">Отмен</option>
          </select>
        </div>
        <div class="wb-field">
          <label class="wb-field__label">Направление</label>
          <select v-model="filters.dir" class="form-control">
            <option value="DESC">По убыванию</option>
            <option value="ASC">По возрастанию</option>
          </select>
        </div>
      </template>
    </WbUniversalFilter>

    <!-- Таблица: стандарт темы (.tbl-card → .card__hd → .tbl-wrap → .tbl) -->
    <div class="tbl-card page-unclaimed-orders__grid">
      <div class="card__hd">
        <span>Возвраты (с {{ tableDateFrom }})</span>
        <span class="spacer"></span>
        <span class="page-unclaimed-orders__head-count">Всего: {{ fmt0(total) }} · Стр {{ page }} / {{ totalPages }}</span>
        <ExcelButton :disabled="!items.length" @click="exportExcel" />
      </div>
      <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
      <div v-else-if="error" class="p-4 text-center text-danger">Не удалось загрузить данные.</div>
      <div v-else class="tbl-wrap">
        <table ref="tableRef" class="tbl page-unclaimed-orders__table">
          <thead>
            <tr>
              <th class="t-left">Товар</th>
              <th class="num">Заказов, шт</th>
              <th class="num">Отмен, шт</th>
              <th class="num">% Отмен</th>
              <th class="num">Выкупили, шт</th>
              <th class="num">Сумма выкупа, ₽</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="items.length === 0"><td colspan="6" class="text-center text-muted">Нет данных</td></tr>
            <tr v-for="row in items" :key="row.nm_id">
              <td class="t-left">
                <ProductCell
                  :photo="row.photos"
                  :title="row.card_name"
                  :sub="subLine(row)"
                  :vendor="row.vendorCode"
                  :link="'/wb/detail?nm_id=' + row.nm_id"
                  :link-label="'WB: ' + row.nm_id"
                />
              </td>
              <td class="num">{{ fmtVal(row.alls, 0) }}</td>
              <td class="num" :class="{ 't-neg': row.cancel > 0 }">{{ fmtVal(row.cancel, 0) }}</td>
              <td class="num" :class="{ 't-neg': row.rate > 0.3 }">{{ fmt1(row.rate * 100) }}%</td>
              <td class="num">{{ fmtVal(row.bought, 0) }}</td>
              <td class="num">{{ fmtVal(row.sum_price, 2) }} ₽</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Pager :page="page" :total-pages="totalPages" :total="total" @change="onPage" />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-unclaimed-orders.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import WbUniversalFilter from '../components/common/WbUniversalFilter.vue'
import ProductCell from '../components/common/ProductCell.vue'
import ExcelButton from '../components/common/ExcelButton.vue'
import Pager from '../components/common/Pager.vue'

// локальное время (toISOString даёт UTC и сдвигает сутки)
// дефолт — ровно 14 суток (как пресет «14 дней»)
const toIsoDate = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
const defaultDates = () => {
  const today = new Date()
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 13)
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
  brand?: string
  subject?: string
  vendorCode: string
  photos?: any
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
  product: '',
  nm_id: '',
  brand: '',
  category: '',
  percent: 20,
  min_orders: 5,
  sort: 'rate',
  dir: 'DESC',
  page: 1,
})
const filterLists = ref<{ brands: string[], categories: string[] }>({ brands: [], categories: [] })
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

/** Списки брендов и предметов для полей фильтра. */
const loadFilterLists = async () => {
  try {
    const { data: d } = await api.get('/api/unclaimed-orders/filters')
    filterLists.value = { brands: d?.brands || [], categories: d?.categories || [] }
  } catch {
    filterLists.value = { brands: [], categories: [] }
  }
}

/** WbUniversalFilter даёт свободную маску (nm_id/артикул/название) — резолвим в nm_id. */
const resolveNmId = async (mask: string): Promise<string> => {
  const q = String(mask || '').trim()
  if (!q) return ''
  try {
    const { data } = await api.get('/api/wb/cards', { params: { q, limit: 20 } })
    const list: any[] = Array.isArray(data) ? data : (data?.items ?? [])
    const exact = list.find((c: any) => String(c.nmID) === q || String(c.vendorCode || '') === q)
    if (exact) return String(exact.nmID)
    return list.length === 1 ? String(list[0].nmID) : ''
  } catch {
    return ''
  }
}

const initFromQuery = () => {
  const q: Record<string, any> = route.query || {}
  const pick = (...keys: string[]) => {
    for (const key of keys) if (q[key]) return String(q[key])
    return ''
  }
  const df = pick('date_from', 'DPFilterForm[date_from]')
  const dt = pick('date_to', 'DPFilterForm[date_to]')
  const nm = pick('nm_id', 'DPFilterForm[nm_id]')
  const product = pick('product')
  const percent = pick('percent')
  const minOrders = pick('min_orders')
  const sort = pick('sort')
  const dir = pick('dir', 'sort_dir')
  const queryPage = pick('page')
  if (df) filters.value.date_from = df
  if (dt) filters.value.date_to = dt
  if (nm) { filters.value.nm_id = nm; filters.value.product = product || nm }
  else if (product) filters.value.product = product
  filters.value.brand = pick('brand')
  filters.value.category = pick('category')
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
  if (filters.value.product) q.product = filters.value.product
  if (filters.value.nm_id) q.nm_id = filters.value.nm_id
  if (filters.value.brand) q.brand = filters.value.brand
  if (filters.value.category) q.category = filters.value.category
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
  if (filters.value.brand) q.set('brand', filters.value.brand)
  if (filters.value.category) q.set('category', filters.value.category)
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
  XLSX.utils.book_append_sheet(wb, ws, 'Возвраты')
  XLSX.writeFile(wb, 'unclaimed-orders.xlsx')
}

/** Применение фильтра: маска товара → nm_id, значения полей → запрос. */
const onApply = async () => {
  filters.value.nm_id = await resolveNmId(filters.value.product)
  filters.value.page = 1
  syncRoute()
  fetchData()
}

/** Сброс фильтра: дефолтные значения (даты — 14 суток, остальные — по умолчанию). */
const onReset = () => {
  const defaults = defaultDates()
  filters.value.product = ''
  filters.value.nm_id = ''
  filters.value.brand = ''
  filters.value.category = ''
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

/** Смена страницы пагинации. */
const onPage = (p: number) => {
  filters.value.page = p
  syncRoute()
  fetchData()
}

/** Подпись под названием товара: предмет и бренд одной строкой (как на остальных страницах). */
const subLine = (r: any) => {
  const subject = String(r.subject || '')
  const brandName = String(r.brand || '')
  if (subject && brandName) return subject + ' • ' + brandName
  return subject || brandName
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
  loadFilterLists()
})

watch(() => route.query, () => {
  if (syncing.value) return
  initFromQuery()
  fetchData()
})
</script>
