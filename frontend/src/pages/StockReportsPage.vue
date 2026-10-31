<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">{{ tabLabel }}</h1>
      <span class="badge bg-light text-dark">{{ total }} поз.</span>
    </div>

    <ul class="nav nav-tabs mb-3">
      <li class="nav-item" v-for="t in TABS" :key="t.key">
        <button class="nav-link" :class="{ active: tab === t.key }" @click="setTab(t.key)">
          {{ t.label }}
        </button>
      </li>
    </ul>

    <div class="card shadow-sm mb-3">
      <div class="card-body py-2 d-flex align-items-end gap-2 flex-wrap">
        <div>
          <label class="form-label small mb-1">Склад</label>
          <select v-model="warehouseId" class="form-select form-select-sm" style="width:200px">
            <option value="all">Все склады</option>
            <option v-for="w in warehouses" :key="w.id" :value="String(w.id)">{{ w.name }}</option>
          </select>
        </div>
        <template v-if="tab === 'balance'">
          <div>
            <label class="form-label small mb-1">На дату (пусто = сейчас)</label>
            <input v-model="onDate" type="date" class="form-control form-control-sm">
          </div>
          <div class="form-check ms-1 mb-2">
            <input id="only-avail" v-model="onlyAvailable" class="form-check-input" type="checkbox">
            <label class="form-check-label small" for="only-avail">Только с наличием</label>
          </div>
        </template>
        <template v-if="tab === 'turnover'">
          <div>
            <label class="form-label small mb-1">Дата с</label>
            <input v-model="dateFrom" type="date" class="form-control form-control-sm">
          </div>
          <div>
            <label class="form-label small mb-1">Дата по</label>
            <input v-model="dateTo" type="date" class="form-control form-control-sm">
          </div>
        </template>
        <template v-if="tab === 'card'">
          <div>
            <label class="form-label small mb-1">Баркод / артикул / название</label>
            <input v-model="term" class="form-control form-control-sm" style="width:260px"
                   placeholder="начните вводить" @keyup.enter="reload()">
          </div>
          <div>
            <label class="form-label small mb-1">Дата с</label>
            <input v-model="dateFrom" type="date" class="form-control form-control-sm">
          </div>
          <div>
            <label class="form-label small mb-1">Дата по</label>
            <input v-model="dateTo" type="date" class="form-control form-control-sm">
          </div>
        </template>
        <template v-if="tab === 'nonliquid'">
          <div>
            <label class="form-label small mb-1">Без движений, дней</label>
            <input v-model.number="days" type="number" min="1" max="365" class="form-control form-control-sm" style="width:110px">
          </div>
        </template>
        <div v-if="tab !== 'card'">
          <div>
            <label class="form-label small mb-1">Поиск</label>
            <input v-model="q" class="form-control form-control-sm" style="width:230px"
                   placeholder="sku / артикул / название" @keyup.enter="reload()">
          </div>
        </div>
        <button class="btn btn-sm btn-primary mb-2" @click="reload()">
          <i class="bi bi-search me-1"></i>Показать
        </button>
        <button class="btn btn-sm btn-light mb-2" @click="exportExcel" :disabled="!rows.length">
          <i class="bi bi-file-earmark-excel me-1"></i>Excel
        </button>
      </div>
    </div>

    <div class="card shadow-sm">
      <div class="card-body p-0">
        <div v-if="loading" class="text-center p-5">
          <div class="spinner-border text-primary" role="status"></div>
        </div>
        <div v-else-if="!rows.length" class="p-4 text-center text-muted">Нет данных</div>
        <div v-else class="table-responsive">
          <table class="table table-bordered table-striped table-hover align-middle mb-0">
            <thead><tr><template v-for="c in cols" :key="c.key">
              <th :class="c.cls">{{ c.label }}</th>
            </template></tr></thead>
            <tbody>
              <tr v-for="(r, i) in rows" :key="i">
                <template v-for="c in cols" :key="c.key">
                  <td :class="c.cls">
                    <template v-if="c.key === 'product'">
                      <div class="fw-bold">{{ r.vendorCode }}</div>
                      <div class="small text-muted">{{ r.nmID }} — {{ r.title }}</div>
                    </template>
                    <template v-else-if="c.key === 'sku'">
                      <span class="font-monospace">{{ r.sku }}</span>
                    </template>
                    <template v-else-if="c.key === 'warehouse'">
                      {{ r.warehouse_name || r.warehouseId || '—' }}
                    </template>
                    <template v-else-if="c.key === 'delta'">
                      <span :class="Number(r.qty_delta) < 0 ? 'text-danger' : 'text-success'">
                        {{ Number(r.qty_delta) > 0 ? '+' : '' }}{{ r.qty_delta }}
                      </span>
                    </template>
                    <template v-else-if="c.key === 'signed'">
                      <span :class="Number(r[c.key]) > 0 ? 'text-success' : (Number(r[c.key]) < 0 ? 'text-danger' : '')">
                        {{ Number(r[c.key]) > 0 ? '+' : '' }}{{ r[c.key] }}
                      </span>
                    </template>
                    <template v-else-if="c.key === 'doc'">
                      {{ r.doc_type }}<span v-if="r.doc_id"> #{{ r.doc_id }}</span>
                    </template>
                    <template v-else-if="c.key === 'created_at'">
                      {{ String(r.created_at || '').slice(0, 16).replace('T', ' ') }}
                    </template>
                    <template v-else>{{ r[c.key] ?? '—' }}</template>
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="d-flex justify-content-between align-items-center mt-2">
      <span class="small text-muted">Стр. {{ page }} / {{ pages }}</span>
      <div class="btn-group">
        <button class="btn btn-sm btn-light" :disabled="page <= 1" @click="page--; reload()">
          <i class="bi bi-chevron-left"></i>
        </button>
        <button class="btn btn-sm btn-light" :disabled="page >= pages" @click="page++; reload()">
          <i class="bi bi-chevron-right"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'

type TabKey = 'balance' | 'turnover' | 'card' | 'nonliquid'

const TABS: { key: TabKey, label: string }[] = [
  { key: 'balance', label: 'Наличие' },
  { key: 'turnover', label: 'Оборотная ведомость' },
  { key: 'card', label: 'Карточка товара' },
  { key: 'nonliquid', label: 'Неликвиды' },
]

const COLS: Record<TabKey, { key: string, label: string, cls?: string }[]> = {
  balance: [
    { key: 'product', label: 'Товар' },
    { key: 'sku', label: 'Баркод' },
    { key: 'warehouse', label: 'Склад' },
    { key: 'quantity', label: 'Остаток', cls: 'text-end' },
  ],
  turnover: [
    { key: 'product', label: 'Товар' },
    { key: 'sku', label: 'Баркод' },
    { key: 'start_qty', label: 'Нач.', cls: 'text-end' },
    { key: 'receipt', label: 'Приход', cls: 'text-end' },
    { key: 'expense', label: 'Расход', cls: 'text-end' },
    { key: 't_in', label: 'Перем+', cls: 'text-end' },
    { key: 't_out', label: 'Перем-', cls: 'text-end' },
    { key: 'inv', label: 'Инв.', cls: 'text-end' },
    { key: 'adj', label: 'Корр.', cls: 'text-end' },
    { key: 'end_qty', label: 'Кон.', cls: 'text-end' },
    { key: 'turnover', label: 'Оборот', cls: 'text-end' },
  ],
  card: [
    { key: 'product', label: 'Товар' },
    { key: 'sku', label: 'Баркод' },
    { key: 'created_at', label: 'Дата' },
    { key: 'doc', label: 'Док' },
    { key: 'warehouse', label: 'Склад' },
    { key: 'delta', label: 'Дельта', cls: 'text-end' },
    { key: 'qty_before', label: 'До', cls: 'text-end' },
    { key: 'qty_after', label: 'После', cls: 'text-end' },
    { key: 'username', label: 'Юзер' },
  ],
  nonliquid: [
    { key: 'product', label: 'Товар' },
    { key: 'sku', label: 'Баркод' },
    { key: 'warehouse', label: 'Склад' },
    { key: 'quantity', label: 'Остаток', cls: 'text-end' },
    { key: 'last_move', label: 'Последнее движение' },
  ],
}

const route = useRoute()
const router = useRouter()
const qc = useQueryClient()

const pathTab = (): TabKey => {
  const p = String(route.path || '')
  if (p.includes('turnover')) return 'turnover'
  if (p.includes('card')) return 'card'
  if (p.includes('nonliquid')) return 'nonliquid'
  return 'balance'
}

const tab = ref<TabKey>(pathTab())
watch(() => route.path, () => { tab.value = pathTab() })

const setTab = (k: TabKey) => {
  const map: Record<TabKey, string> = {
    balance: '/wb-stock-reports/balance',
    turnover: '/wb-stock-reports/turnover',
    card: '/wb-stock-reports/card',
    nonliquid: '/wb-stock-reports/nonliquid',
  }
  router.push(map[k])
}

const tabLabel = computed(() => TABS.find(t => t.key === tab.value)?.label || 'Отчеты склада')
const cols = computed(() => COLS[tab.value])

const warehouseId = ref('all')
const warehouses = ref<any[]>([])
const q = ref('')
const term = ref('')
const onDate = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const days = ref(30)
const onlyAvailable = ref(false)
const page = ref(1)
const pageSize = 100

const params = computed(() => {
  const p: Record<string, any> = { warehouse_id: warehouseId.value, page: page.value, page_size: pageSize }
  if (tab.value === 'balance') {
    if (onDate.value) p.date = onDate.value
    if (onlyAvailable.value) p.only_available = 1
    if (q.value) p.q = q.value
  } else if (tab.value === 'turnover') {
    if (dateFrom.value) p.date_from = dateFrom.value
    if (dateTo.value) p.date_to = dateTo.value
    if (q.value) p.q = q.value
  } else if (tab.value === 'card') {
    p.sku = term.value
    if (dateFrom.value) p.date_from = dateFrom.value
    if (dateTo.value) p.date_to = dateTo.value
  } else {
    p.days = days.value
    if (q.value) p.q = q.value
  }
  return p
})

const { data, isLoading: loading } = useQuery({
  queryKey: computed(() => ['stock-reports', tab.value, JSON.stringify(params.value)] as const),
  queryFn: () => api.get(`/api/stock-reports/${tab.value}`, { params: params.value })
    .then(r => r.data),
})

const rows = computed<any[]>(() => (data.value?.rows as any[]) || [])
const total = computed(() => Number(data.value?.total || 0))
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const reload = () => {
  page.value = 1
  qc.invalidateQueries({ queryKey: ['stock-reports'] })
}

const loadWarehouses = async () => {
  const res = await api.get('/api/stock-reports/warehouses').then(r => r.data).catch(() => ({ rows: [] }))
  warehouses.value = res.rows || []
}
loadWarehouses()

const exportExcel = async () => {
  if (!rows.value.length) return
  const { default: XLSX } = await import('xlsx')
  const head = cols.value.map(c => (c.key === 'product' ? 'Товар' : c.label))
  const data = rows.value.map((r: any) => cols.value.map((c: any) => {
    if (c.key === 'product') return `${r.vendorCode || ''} ${r.nmID || ''} ${r.title || ''}`
    if (c.key === 'created_at') return String(r.created_at || '').slice(0, 16).replace('T', ' ')
    if (c.key === 'doc') return `${r.doc_type || ''}${r.doc_id ? ' #' + r.doc_id : ''}`
    return r[c.key] ?? ''
  }))
  const ws = XLSX.utils.aoa_to_sheet([head, ...data])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, tabLabel.value.slice(0, 30))
  XLSX.writeFile(wb, `wb-stock-${tab.value}_${new Date().toISOString().slice(0, 10)}.xlsx`)
}
</script>
