<template>
  <div class="container-xxl page-wb-orders">
    <h1 class="page-title">{{ $route.meta.title || 'Список заказов' }}</h1>
    <div class="card card-body page-wb-orders__filter-card mb-3">
      <div v-if="quickButtons.length" class="panel-btns page-wb-orders__quick">
        <button v-for="btn in quickButtons" :key="btn.nm_id" class="btn btn-panel" :title="'nm_id ' + btn.nm_id" @click="onQuick(btn)">
          <i v-if="btn.icon" :class="btn.icon"></i> {{ btn.label }}
        </button>
      </div>
      <div class="row g-2">
        <div class="col-md-3 col-6"><label class="form-label">Номер заказа</label><input v-model="filters.g_number" class="form-control form-control-sm" placeholder="g_number" /></div>
        <div class="col-md-3 col-6"><label class="form-label">Статус</label>
          <select v-model="filters.is_cancel" class="form-select form-select-sm">
            <option value="">Все</option>
            <option value="0">Ок</option>
            <option value="1">Отмена</option>
          </select>
        </div>
        <div class="col-md-3 col-6"><label class="form-label">Бренд</label>
          <select v-model="filters.brand" class="form-select form-select-sm">
            <option value="">Все</option>
            <option v-for="b in brandOptions" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>
        <div class="col-md-3 col-6"><label class="form-label">Категория</label>
          <select v-model="filters.category" class="form-select form-select-sm">
            <option value="">Все</option>
            <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>
      <WbFilterBar embedded v-model:nm-id="filters.nm_id" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" @apply="onApply" @reset="onReset" />
    </div>

    <div class="card">
      <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
        <span>Заказы WB</span>
        <span class="badge bg-light text-dark">{{ total }}</span>
      </div>
      <div v-if="isLoading" class="text-center p-5">
        <div class="spinner-border text-primary" role="status"></div>
        <div class="mt-2 text-muted">Загрузка данных...</div>
      </div>
      <div v-else class="wb-table-wrap page-wb-orders__table-wrap">
        <vxe-table
          :data="rows"
          class="page-wb-orders__grid"
          border
          stripe
          size="mini"
          auto-resize
          show-overflow="title"
          header-align="center"
          :row-config="{ isHover: true, keyField: 'id' }"
          :sort-config="{ remote: true, trigger: 'cell' }"
          :column-config="{ resizable: true }"
          @sort-change="onSortChange"
        >
          <vxe-column title="" :width="30" align="center">
            <template #default="{ row }">
              <a href="#" class="page-wb-orders__view-btn" title="Детали заказа" @click.prevent="openDetail(row.id)"><i class="bi bi-eye-fill"></i></a>
            </template>
          </vxe-column>
          <vxe-column field="date" title="Дата" :width="112" align="center" sortable>
            <template #default="{ row }"><span class="page-wb-orders__date-main">{{ fmtDateTime(row.date) }}</span></template>
          </vxe-column>
          <vxe-column field="nm_id" title="Арт WB" :width="84" align="center" sortable>
            <template #default="{ row }">
              <a v-if="row.nm_id" :href="`https://www.wildberries.ru/catalog/${row.nm_id}/detail.aspx`" target="_blank" class="page-wb-orders__wb-link">{{ row.nm_id }}</a>
              <span v-else>—</span>
            </template>
          </vxe-column>
          <vxe-column field="supplier_article" title="Артикул" :width="130" align="center">
            <template #header>
              <div>Артикул</div>
              <input v-model="filters.supplier_article" class="form-control page-wb-orders__head-filter" placeholder="фильтр…" title="Фильтр — Enter" @click.stop @mousedown.stop @keydown.enter="onApply" />
            </template>
          </vxe-column>
          <vxe-column field="card_title" title="Товар / Детали заказа" :min-width="220" :show-overflow="false" sortable>
            <template #header>
              <div>Товар / Детали заказа{{ sortMark('card_title') }}</div>
              <input v-model="filters.card_title" class="form-control page-wb-orders__head-filter" placeholder="фильтр…" title="Фильтр — Enter" @click.stop @mousedown.stop @keydown.enter="onApply" />
            </template>
            <template #default="{ row }">
              <div class="page-wb-orders__product-title">{{ row.card_title || '—' }}</div>
              <div class="page-wb-orders__product-sub"><b>{{ row.subject || '' }}</b> | <b>{{ row.brand || '' }}</b></div>
              <div class="page-wb-orders__product-sub">Склад: <b>{{ row.warehouse_name || '—' }} ({{ row.warehouse_type || '—' }})</b></div>
            </template>
          </vxe-column>
          <vxe-column field="total_price" title="Цена в карт." :width="70" align="right" :formatter="fmtMoneyCol" class-name="page-wb-orders__money" />
          <vxe-column field="discount_percent" title="Скидка" :width="64" align="right" :formatter="fmtMoneyCol" class-name="page-wb-orders__money" />
          <vxe-column field="price_with_disc" title="Цена со ск." :width="70" align="right" :formatter="fmtMoneyCol" class-name="page-wb-orders__money" />
          <vxe-column field="spp" title="СПП" :width="64" align="right" :formatter="fmtMoneyCol" class-name="page-wb-orders__money" />
          <vxe-column field="finished_price" title="Цена" :width="70" align="right" sortable :formatter="fmtMoneyCol" class-name="page-wb-orders__money" />
          <vxe-column field="country_name" title="Страна / регион" :min-width="150" :show-overflow="false">
            <template #default="{ row }">
              <div class="page-wb-orders__geo">{{ row.country_name || '—' }}, {{ row.oblast_okrug_name || '—' }}, {{ row.region_name || '—' }}</div>
            </template>
          </vxe-column>
          <vxe-column field="is_cancel" title="Статус" :width="76" align="center">
            <template #default="{ row }">
              <span class="page-wb-orders__status" :class="row.is_cancel ? 'page-wb-orders__status--cancel' : 'page-wb-orders__status--ok'">{{ row.is_cancel ? 'Отмена' : 'Ок' }}</span>
            </template>
          </vxe-column>
        </vxe-table>
        <div v-if="!rows.length" class="page-wb-orders__empty">Нет данных</div>
      </div>
    </div>
    <div class="page-wb-orders__pager">
      <button class="btn btn-outline-secondary btn-sm" :disabled="page <= 1" @click="page--; fetchData()">Назад</button>
      <span class="page-wb-orders__pager-label">Стр {{ page }} / {{ totalPages }} ({{ total }})</span>
      <button class="btn btn-outline-secondary btn-sm" :disabled="page >= totalPages" @click="page++; fetchData()">Вперед</button>
    </div>

    <div v-if="drawerOpen">
      <div class="page-wb-orders__backdrop" @click="drawerOpen = false"></div>
      <div class="page-wb-orders__drawer" role="dialog" aria-label="Детали заказа">
        <div class="page-wb-orders__drawer-head">
          <h3 class="page-wb-orders__drawer-title">Детали заказа: {{ detail?.g_number || '' }}</h3>
          <button class="btn btn-sm btn-light" @click="drawerOpen = false"><i class="bi bi-x-lg"></i></button>
        </div>
        <div class="page-wb-orders__drawer-body">
          <div v-if="detailLoading" class="text-center text-muted p-4">Загрузка...</div>
          <template v-else-if="detail">
            <div v-for="f in detailFields" :key="f.key" class="page-wb-orders__drawer-row">
              <div class="page-wb-orders__drawer-key">{{ f.label }}</div>
              <div class="page-wb-orders__drawer-val">{{ fmtDetail(detail[f.key]) }}</div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-orders.css'
import 'vxe-table/lib/style.css'
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VxeTable, VxeColumn } from 'vxe-table'
import WbFilterBar from '../components/common/WbFilterBar.vue'
import { api } from '../api/client'
import { wbOrdersApi, type WbOrderRow } from '../api/wbOrders'

const route = useRoute()
const router = useRouter()

const filters = reactive({
  nm_id: '',
  date_from: '',
  date_to: '',
  supplier_article: '',
  brand: '',
  category: '',
  card_title: '',
  g_number: '',
  is_cancel: '',
})
const sort = ref('-date')
const page = ref(1)
const pageSize = 100
const rows = ref<WbOrderRow[]>([])
const total = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const isLoading = ref(false)
const quickButtons = ref<any[]>([])
// Списки для дропдаунов — из строк таблицы (накапливаются по мере просмотра страниц)
const brandOpts = ref<string[]>([])
const categoryOpts = ref<string[]>([])
const brandOptions = computed(() => (filters.brand && !brandOpts.value.includes(filters.brand) ? [filters.brand, ...brandOpts.value] : brandOpts.value))
const categoryOptions = computed(() => (filters.category && !categoryOpts.value.includes(filters.category) ? [filters.category, ...categoryOpts.value] : categoryOpts.value))
function sortMark(field: string) {
  if (sort.value.replace(/^-/, '') !== field) return ''
  return sort.value.startsWith('-') ? ' ▼' : ' ▲'
}

const drawerOpen = ref(false)
const detail = ref<WbOrderRow | null>(null)
const detailLoading = ref(false)
const detailFields = [
  { key: 'id', label: 'ID' }, { key: 'srid', label: 'SRID' }, { key: 'g_number', label: '№ Заказа' },
  { key: 'date', label: 'Дата заказа' }, { key: 'last_change_date', label: 'Обновлен' },
  { key: 'supplier_article', label: 'Артикул' }, { key: 'nm_id', label: 'WB Артикул' },
  { key: 'barcode', label: 'Баркод' }, { key: 'tech_size', label: 'Размер' },
  { key: 'total_price', label: 'Цена в карт' }, { key: 'discount_percent', label: 'Скидка %' },
  { key: 'price_with_disc', label: 'Цена со скидкой' }, { key: 'finished_price', label: 'Цена продажи' },
  { key: 'for_pay', label: 'К выплате' }, { key: 'spp', label: 'СПП' },
  { key: 'warehouse_name', label: 'Склад' }, { key: 'warehouse_type', label: 'Склад тип' },
  { key: 'country_name', label: 'Страна' }, { key: 'oblast_okrug_name', label: 'Округ' },
  { key: 'region_name', label: 'Регион' }, { key: 'income_id', label: '№ Поставки' },
  { key: 'sale_id', label: 'ID Продажи' }, { key: 'odid', label: 'ODID' },
  { key: 'subject', label: 'Предмет' }, { key: 'category', label: 'Категория' },
  { key: 'brand', label: 'Бренд' }, { key: 'is_cancel', label: 'Статус' },
  { key: 'order_type', label: 'Тип' }, { key: 'sticker', label: 'Стикер' },
  { key: 'created_at', label: 'Дата загрузки в БД' },
]

function initFromQuery() {
  const q: any = route.query
  const pick = (...keys: string[]) => { for (const k of keys) if (q[k] !== undefined && q[k] !== '') return String(q[k]); return '' }
  filters.nm_id = pick('nm_id', 'WbOrderSearch[nm_id]')
  filters.date_from = pick('date_from', 'WbOrderSearch[date]')
  filters.date_to = pick('date_to') || filters.date_from
  filters.supplier_article = pick('supplier_article', 'WbOrderSearch[supplier_article]')
  filters.brand = pick('brand', 'WbOrderSearch[brand]')
  filters.category = pick('category', 'WbOrderSearch[category]')
  filters.card_title = pick('card_title', 'WbOrderSearch[cardTitle]')
  filters.g_number = pick('g_number', 'WbOrderSearch[g_number]')
  filters.is_cancel = pick('is_cancel', 'WbOrderSearch[is_cancel]')
  if (q.sort) sort.value = String(q.sort)
  if (q.page) page.value = parseInt(String(q.page)) || 1
}

const fmtDateTime = (d: any) => {
  if (!d) return '—'
  const dt = new Date(String(d).replace(' ', 'T'))
  if (isNaN(+dt)) return String(d)
  return dt.toLocaleDateString('ru-RU') + ' ' + dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}
const fmtMoney = (v: any) => (v === null || v === undefined || v === '' ? '—' : new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v)))
const fmtMoneyCol = ({ cellValue }: any) => fmtMoney(cellValue)
const fmtDetail = (v: any) => {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') return fmtMoney(v)
  return String(v)
}

function buildParams() {
  const p: Record<string, any> = { sort: sort.value, page: page.value, page_size: pageSize }
  if (filters.date_from) p.date_from = filters.date_from
  if (filters.date_to) p.date_to = filters.date_to
  if (filters.nm_id) p.nm_id = filters.nm_id
  if (filters.supplier_article) p.supplier_article = filters.supplier_article
  if (filters.brand) p.brand = filters.brand
  if (filters.category) p.category = filters.category
  if (filters.card_title) p.card_title = filters.card_title
  if (filters.g_number) p.g_number = filters.g_number
  if (filters.is_cancel !== '') p.is_cancel = filters.is_cancel
  return p
}

let syncing = false
function syncRoute() {
  const q: any = {}
  if (filters.date_from) q.date_from = filters.date_from
  if (filters.date_to) q.date_to = filters.date_to
  if (filters.nm_id) q.nm_id = filters.nm_id
  if (filters.supplier_article) q.supplier_article = filters.supplier_article
  if (filters.brand) q.brand = filters.brand
  if (filters.category) q.category = filters.category
  if (filters.card_title) q.card_title = filters.card_title
  if (filters.g_number) q.g_number = filters.g_number
  if (filters.is_cancel !== '') q.is_cancel = filters.is_cancel
  if (sort.value !== '-date') q.sort = sort.value
  if (page.value > 1) q.page = String(page.value)
  syncing = true
  router.replace({ path: '/wb-order/index', query: q }).finally(() => setTimeout(() => (syncing = false), 50))
}

async function fetchData() {
  isLoading.value = true
  syncRoute()
  try {
    const data = await wbOrdersApi.list(buildParams())
    rows.value = data.items || []
    total.value = data.total || 0
    mergeOpts(brandOpts, rows.value.map((r) => r.brand))
    mergeOpts(categoryOpts, rows.value.map((r) => (r as any).category))
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    isLoading.value = false
  }
}

function onApply() { page.value = 1; fetchData() }
function mergeOpts(list: { value: string[] }, vals: any[]) {
  const set = new Set(list.value)
  for (const v of vals) if (v !== null && v !== undefined && String(v) !== '') set.add(String(v))
  list.value = [...set].sort((a, b) => a.localeCompare(b, 'ru'))
}
function onReset() {
  filters.nm_id = ''
  filters.date_from = ''
  filters.date_to = ''
  filters.supplier_article = ''
  filters.brand = ''
  filters.category = ''
  filters.card_title = ''
  filters.g_number = ''
  filters.is_cancel = ''
  sort.value = '-date'
  page.value = 1
  fetchData()
}
async function loadQuickButtons() {
  try {
    const { data } = await api.get('/api/config/quick-buttons')
    if (Array.isArray(data) && data.length) quickButtons.value = data
  } catch { /* без кнопок */ }
}
function onQuick(btn: any) {
  filters.nm_id = String(btn.nm_id)
  page.value = 1
  fetchData()
}
function onSortChange({ field, order }: any) {
  if (!field) { sort.value = '-date'; page.value = 1; fetchData(); return }
  sort.value = (order === 'asc' ? '' : '-') + field
  page.value = 1
  fetchData()
}
async function openDetail(id: number) {
  drawerOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await wbOrdersApi.get(id)
  } catch {
    detail.value = null
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => { initFromQuery(); loadQuickButtons(); fetchData() })
watch(() => route.query, () => {
  if (syncing) return
  initFromQuery()
  fetchData()
})
</script>
