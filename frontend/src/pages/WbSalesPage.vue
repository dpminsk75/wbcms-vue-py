<template>
  <div class="container-xxl page-wb-sales">
    <h1 class="page-title">{{ $route.meta.title || 'Список продаж' }}</h1>
    <div class="card card-body page-wb-sales__filter-card mb-3">
      <div class="row mb-3">

        <div class="col-md-8">
          <div v-if="quickButtons.length" class="panel-btns page-wb-sales__quick">
            <button v-for="btn in quickButtons" :key="btn.nm_id" class="btn btn-panel" :title="'nm_id ' + btn.nm_id" @click="onQuick(btn)">
              <i v-if="btn.icon" :class="btn.icon"></i> {{ btn.label }}
            </button>
          </div>
          <div class="row">
            <div class="col-md-4 col-6"><label class="form-label">Бренд</label>
              <select v-model="filters.brand" class="form-select form-select-sm">
                <option value="">Все</option>
                <option v-for="b in brandOptions" :key="b" :value="b">{{ b }}</option>
              </select>
            </div>
            <div class="col-md-4 col-6"><label class="form-label">Категория</label>
              <select v-model="filters.category" class="form-select form-select-sm">
                <option value="">Все</option>
                <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
          </div>
          <div class="row">
            <WbFilterBar embedded v-model:nm-id="filters.nm_id" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" @apply="onApply" @reset="onReset" />
          </div>
        </div>
        <div class="col-md-4">
          <div class="page-wb-sales__field"><label class="form-label page-wb-sales__field-label">ID продажи</label><input v-model="filters.sale_id" class="form-control form-control-sm page-wb-sales__field-input" placeholder="S…/R…" /></div>
          <div class="page-wb-sales__field"><label class="form-label page-wb-sales__field-label">SRID</label><input v-model="filters.srid" class="form-control form-control-sm page-wb-sales__field-input" /></div>
          <div class="page-wb-sales__field"><label class="form-label page-wb-sales__field-label">Номер заказа</label><input v-model="filters.number" class="form-control form-control-sm page-wb-sales__field-input" /></div>
          <div class="page-wb-sales__prices">
            <div class="page-wb-sales__field"><label class="form-label page-wb-sales__field-label">Цена до (=)</label><input v-model="filters.total_price" class="form-control form-control-sm page-wb-sales__field-input" inputmode="decimal" /></div>
            <div class="page-wb-sales__field"><label class="form-label page-wb-sales__field-label">Цена продажи (=)</label><input v-model="filters.finished_price" class="form-control form-control-sm page-wb-sales__field-input" inputmode="decimal" /></div>
          </div>
        </div>


        
      </div>
    </div>

    <div class="card">
      <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
        <span>Продажи на WB</span>
        <span class="badge bg-light text-dark">{{ total }}</span>
      </div>
      <div v-if="isLoading" class="text-center p-5">
        <div class="spinner-border text-primary" role="status"></div>
        <div class="mt-2 text-muted">Загрузка данных...</div>
      </div>
      <div v-else class="wb-table-wrap page-wb-sales__table-wrap">
        <vxe-table
          :data="rows"
          class="page-wb-sales__grid"
          border
          stripe
          size="mini"
          auto-resize
          show-overflow="title"
          header-align="center"
          :row-config="{ isHover: true, keyField: 'saleID' }"
          :sort-config="{ remote: true, trigger: 'cell' }"
          :column-config="{ resizable: true }"
          @sort-change="onSortChange"
        >
          <vxe-column title="" :width="30" align="center">
            <template #default="{ row }">
              <a href="#" class="page-wb-sales__view-btn" title="Детали продажи" @click.prevent="openDetail(row.saleID)"><i class="bi bi-eye-fill"></i></a>
            </template>
          </vxe-column>
          <vxe-column field="date" title="Дата" :width="112" align="center" sortable>
            <template #default="{ row }"><span class="page-wb-sales__date-main">{{ fmtDateTime(row.date) }}</span></template>
          </vxe-column>
          <vxe-column field="nmId" title="Арт WB" :width="84" align="center" sortable>
            <template #default="{ row }">
              <a v-if="row.nmId" :href="`https://www.wildberries.ru/catalog/${row.nmId}/detail.aspx`" target="_blank" class="page-wb-sales__wb-link">{{ row.nmId }}</a>
              <span v-else>—</span>
            </template>
          </vxe-column>
          <vxe-column field="supplierArticle" title="Артикул" :width="130" align="center" sortable>
            <template #header>
              <div>Артикул{{ sortMark('supplierArticle') }}</div>
              <input v-model="filters.supplier_article" class="form-control page-wb-sales__head-filter" placeholder="фильтр…" title="Фильтр — Enter" @click.stop @mousedown.stop @keydown.enter="onApply" />
            </template>
          </vxe-column>
          <vxe-column field="cardTitle" title="Товар / Детали заказа" :min-width="220" :show-overflow="false">
            <template #header>
              <div>Товар / Детали заказа</div>
              <input v-model="filters.card_title" class="form-control page-wb-sales__head-filter" placeholder="фильтр…" title="Фильтр — Enter" @click.stop @mousedown.stop @keydown.enter="onApply" />
            </template>
            <template #default="{ row }">
              <div class="page-wb-sales__product-title">{{ row.cardTitle || '—' }}</div>
              <div class="page-wb-sales__product-sub">Цена в карт: <b>{{ fmtMoney(row.totalPrice) }} ₽</b> | Своя скидка: <b>{{ fmtMoney(row.discountPercent) }} %</b> | Цена со ск: <b>{{ fmtMoney(row.priceWithDisc) }} ₽</b></div>
              <div class="page-wb-sales__product-sub">Склад: <b>{{ row.warehouseName || '—' }} ({{ row.warehouseType || '—' }})</b></div>
            </template>
          </vxe-column>
          <vxe-column field="totalPrice" title="Цена до ск." :width="70" align="right" sortable :formatter="fmtMoneyCol" class-name="page-wb-sales__money" />
          <vxe-column field="discountPercent" title="Скидка %" :width="70" align="right" :formatter="fmtMoneyCol" class-name="page-wb-sales__money" />
          <vxe-column field="priceWithDisc" title="Цена со ск." :width="70" align="right" :formatter="fmtMoneyCol" class-name="page-wb-sales__money" />
          <vxe-column field="spp" title="СПП" :width="70" align="center" sortable>
            <template #default="{ row }">{{ row.spp === null || row.spp === undefined || row.spp === '' ? '—' : `${row.spp}%` }}</template>
          </vxe-column>
          <vxe-column field="finishedPrice" title="Цена продажи" :width="70" align="right" :formatter="fmtMoneyCol" class-name="page-wb-sales__money" />
          <vxe-column field="forPay" title="К оплате" :width="70" align="right" :formatter="fmtMoneyCol" class-name="page-wb-sales__money" />
          <vxe-column field="countryName" title="Регион покупки" :min-width="150" :show-overflow="false">
            <template #header>
              <div>Регион покупки</div>
              <input v-model="filters.geo" class="form-control page-wb-sales__head-filter" placeholder="фильтр…" title="Поиск по стране, области и региону — Enter" @click.stop @mousedown.stop @keydown.enter="onApply" />
            </template>
            <template #default="{ row }">
              <div class="page-wb-sales__geo">{{ row.countryName || '—' }}, {{ row.oblastOkrugName || '—' }}, <b>{{ row.regionName || '—' }}</b></div>
            </template>
          </vxe-column>
        </vxe-table>
        <div v-if="!rows.length" class="page-wb-sales__empty">Нет данных</div>
      </div>
    </div>
    <div class="page-wb-sales__pager">
      <button class="btn btn-outline-secondary btn-sm" :disabled="page <= 1" @click="page--; fetchData()">Назад</button>
      <span class="page-wb-sales__pager-label">Стр {{ page }} / {{ totalPages }} ({{ total }})</span>
      <button class="btn btn-outline-secondary btn-sm" :disabled="page >= totalPages" @click="page++; fetchData()">Вперед</button>
    </div>

    <div v-if="drawerOpen">
      <div class="page-wb-sales__backdrop" @click="drawerOpen = false"></div>
      <div class="page-wb-sales__drawer" role="dialog" aria-label="Детали продажи">
        <div class="page-wb-sales__drawer-head">
          <h3 class="page-wb-sales__drawer-title">Продажа: {{ detail?.saleID || '' }}</h3>
          <button class="btn btn-sm btn-light" @click="drawerOpen = false"><i class="bi bi-x-lg"></i></button>
        </div>
        <div class="page-wb-sales__drawer-body">
          <div v-if="detailLoading" class="text-center text-muted p-4">Загрузка...</div>
          <template v-else-if="detail">
            <div v-for="f in detailFields" :key="f.key" class="page-wb-sales__drawer-row">
              <div class="page-wb-sales__drawer-key">{{ f.label }}</div>
              <div class="page-wb-sales__drawer-val">{{ fmtDetail(f.key, detail[f.key]) }}</div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-sales.css'
import 'vxe-table/lib/style.css'
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VxeTable, VxeColumn } from 'vxe-table'
import WbFilterBar from '../components/common/WbFilterBar.vue'
import { api } from '../api/client'
import { wbSalesApi, type WbSaleRow } from '../api/wbSales'

const route = useRoute()
const router = useRouter()

// Дефолт — последние 3 дня включительно (всю таблицу не тянем)
const todayD = new Date()
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const defTo = fmtD(todayD)
const defFrom = fmtD(new Date(todayD.getFullYear(), todayD.getMonth(), todayD.getDate() - 2))

const filters = reactive({
  nm_id: '', date_from: defFrom, date_to: defTo, supplier_article: '', card_title: '',
  sale_id: '', srid: '', number: '', brand: '', category: '', subject: '',
  warehouse_name: '', warehouse_type: '', total_price: '', finished_price: '',
  geo: '',
})
const sort = ref('-date')
const page = ref(1)
const pageSize = 20
const rows = ref<WbSaleRow[]>([])
const total = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const isLoading = ref(false)
const quickButtons = ref<any[]>([])
// Списки для дропдаунов — из строк таблицы (накапливаются по мере просмотра страниц)
const brandOpts = ref<string[]>([])
const categoryOpts = ref<string[]>([])
const warehouseOpts = ref<string[]>([])
function withCurrent(cur: string, list: string[]) {
  return cur && !list.includes(cur) ? [cur, ...list] : list
}
const brandOptions = computed(() => withCurrent(filters.brand, brandOpts.value))
const categoryOptions = computed(() => withCurrent(filters.category, categoryOpts.value))
const warehouseOptions = computed(() => withCurrent(filters.warehouse_name, warehouseOpts.value))
function mergeOpts(list: { value: string[] }, vals: any[]) {
  const set = new Set(list.value)
  for (const v of vals) if (v !== null && v !== undefined && String(v) !== '') set.add(String(v))
  list.value = [...set].sort((a, b) => a.localeCompare(b, 'ru'))
}

const drawerOpen = ref(false)
const detail = ref<WbSaleRow | null>(null)
const detailLoading = ref(false)
// Drawer — все поля wb_sales (structure.sql:2084-2125), подписи 1в1 из WbSales::attributeLabels
const detailFields = [
  { key: 'saleID', label: 'ID продажи (WB)' }, { key: 'srid', label: 'ID заказа (SRID)' },
  { key: 'number', label: 'Номер заказа' }, { key: 'gNumber', label: 'Номер задания' },
  { key: 'date', label: 'Дата продажи' }, { key: 'lastChangeDate', label: 'Дата обновления' },
  { key: 'nmId', label: 'Артикул WB' }, { key: 'supplierArticle', label: 'Артикул' },
  { key: 'barcode', label: 'Баркод' }, { key: 'brand', label: 'Бренд' },
  { key: 'subject', label: 'Предмет' }, { key: 'category', label: 'Категория' },
  { key: 'techSize', label: 'Размер' }, { key: 'totalPrice', label: 'Цена до скидок' },
  { key: 'discountPercent', label: 'Скидка %' }, { key: 'priceWithDisc', label: 'Цена со скидкой' },
  { key: 'spp', label: 'СПП' }, { key: 'finishedPrice', label: 'Цена продажи' },
  { key: 'paymentSaleAmount', label: 'Оплачено покупателем' }, { key: 'forPay', label: 'К оплате' },
  { key: 'warehouseName', label: 'Склад отгрузки' }, { key: 'warehouseType', label: 'Тип склада' },
  { key: 'countryName', label: 'Страна' }, { key: 'oblastOkrugName', label: 'Область / Регион' },
  { key: 'regionName', label: 'Округ' }, { key: 'incomeID', label: 'Номер поставки' },
  { key: 'isSupply', label: 'Поставка' }, { key: 'isRealization', label: 'Реализация' },
  { key: 'orderType', label: 'Тип заказа' }, { key: 'saleEvents', label: 'События продажи' },
  { key: 'sticker', label: 'Стикер' }, { key: 'created_at', label: 'Дата загрузки в БД' },
]

function initFromQuery() {
  const q: any = route.query
  const pick = (...keys: string[]) => { for (const k of keys) if (q[k] !== undefined && q[k] !== '') return String(q[k]); return '' }
  filters.nm_id = pick('nm_id', 'WbSalesSearch[nmId]')
  { const df = pick('date_from', 'WbSalesSearch[date]'); if (df) filters.date_from = df }
  { const dt = pick('date_to'); if (dt) filters.date_to = dt }
  for (const [local, ...aliases] of [
    ['supplier_article', 'WbSalesSearch[supplierArticle]'], ['card_title', 'WbSalesSearch[cardTitle]'],
    ['sale_id', 'WbSalesSearch[saleID]'], ['srid', 'WbSalesSearch[srid]'], ['number', 'WbSalesSearch[number]'],
    ['brand', 'WbSalesSearch[brand]'], ['category', 'WbSalesSearch[category]'],
    ['subject', 'WbSalesSearch[subject]'], ['warehouse_name', 'WbSalesSearch[warehouseName]'],
    ['warehouse_type', 'WbSalesSearch[warehouseType]'],
    ['total_price', 'WbSalesSearch[totalPrice]'],
    ['finished_price', 'WbSalesSearch[finishedPrice]'],
    ['geo'],
  ] as const) {
    ;(filters as any)[local] = pick(local, ...aliases)
  }
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
const fmtDetail = (key: string, v: any) => {
  if (v === null || v === undefined || v === '') return '—'
  if (key === 'isSupply' || key === 'isRealization') return Number(v) ? 'Да' : 'Нет'
  if (typeof v === 'number') return fmtMoney(v)
  return String(v)
}

function buildParams() {
  const p: Record<string, any> = { sort: sort.value, page: page.value, page_size: pageSize }
  const strKeys = ['date_from', 'date_to', 'supplier_article', 'card_title', 'sale_id', 'srid', 'number', 'brand', 'category', 'subject', 'warehouse_name', 'warehouse_type', 'geo'] as const
  for (const k of strKeys) if ((filters as any)[k]) p[k] = (filters as any)[k]
  if (filters.nm_id) p.nm_id = Number(filters.nm_id) || filters.nm_id
  if (filters.total_price !== '') p.total_price = filters.total_price
  if (filters.finished_price !== '') p.finished_price = filters.finished_price
  return p
}

let syncing = false
function syncRoute() {
  const q: any = {}
  for (const k of Object.keys(filters) as (keyof typeof filters)[]) if ((filters as any)[k] !== '') q[k] = (filters as any)[k]
  if (sort.value !== '-date') q.sort = sort.value
  if (page.value > 1) q.page = String(page.value)
  syncing = true
  router.replace({ path: '/wb-sales/index', query: q }).finally(() => setTimeout(() => (syncing = false), 50))
}

async function fetchData() {
  isLoading.value = true
  syncRoute()
  try {
    const data = await wbSalesApi.list(buildParams())
    rows.value = data.items || []
    total.value = data.total || 0
    mergeOpts(brandOpts, rows.value.map((r) => r.brand))
    mergeOpts(categoryOpts, rows.value.map((r) => r.category))
    mergeOpts(warehouseOpts, rows.value.map((r) => r.warehouseName))
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    isLoading.value = false
  }
}

function onApply() { page.value = 1; fetchData() }
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
function onReset() {
  for (const k of Object.keys(filters) as (keyof typeof filters)[]) (filters as any)[k] = ''
  filters.date_from = defFrom
  filters.date_to = defTo
  sort.value = '-date'
  page.value = 1
  fetchData()
}
function onSortChange({ field, order }: any) {
  if (!field) { sort.value = '-date'; page.value = 1; fetchData(); return }
  sort.value = (order === 'asc' ? '' : '-') + field
  page.value = 1
  fetchData()
}
function sortMark(field: string) {
  if (sort.value.replace(/^-/, '') !== field) return ''
  return sort.value.startsWith('-') ? ' ▼' : ' ▲'
}
async function openDetail(saleID: string) {
  drawerOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await wbSalesApi.get(saleID)
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
