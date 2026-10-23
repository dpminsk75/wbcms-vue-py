<template>
  <div class="container-xxl page-top-products">
    <h1 class="page-title">{{ $route.meta.title || 'ТОП товаров за период' }}</h1>

    <!-- Блок фильтров -->
    <div class="card page-top-products__filter-card card-body mb-4 shadow-sm">
      <div class="row g-3 align-items-end">
        <div class="col-md-4">
          <label class="form-label fw-bold">Период анализа</label>
          <div class="d-flex gap-2 align-items-center">
            <WbDateInput v-model="filters.date_from" />
            <span>|</span>
            <WbDateInput v-model="filters.date_to" />
          </div>
        </div>

        <div class="col-md-3">
          <label class="form-label fw-bold">Сортировать по</label>
          <select v-model="filters.sort_by" class="form-select">
            <option value="qnt">Количеству продаж (шт)</option>
            <option value="amount">Выручке (руб)</option>
            <option value="net_profit">По итогу от WB (руб)</option>
            <option value="clean_margin">Марже после налогов (руб)</option>
          </select>
        </div>

        <div class="col-md-2">
          <label class="form-label fw-bold">Показать товаров</label>
          <select v-model.number="filters.limit" class="form-select">
            <option :value="20">ТОП-20</option>
            <option :value="50">ТОП-50</option>
            <option :value="200">ТОП-200</option>
            <option :value="500">ТОП-500</option>
            <option :value="1000">ТОП-1000</option>
          </select>
        </div>

        <div class="col-md-3 d-flex gap-2">
          <button class="btn btn-primary flex-grow-1" @click="refetch" :disabled="isLoading">
            <i class="bi bi-filter me-1"></i> Применить
          </button>
          <button class="btn btn-light" title="Сбросить" @click="resetFilters">
            <i class="bi bi-arrow-counterclockwise"></i>
          </button>
        </div>
      </div>

      <!-- Чекбоксы и подписи -->
      <div class="row g-3 align-items-center">
        <div class="col-md-6 d-flex align-items-center gap-3">
          <div class="form-check mb-0">
            <input id="tp-with-stock" v-model="filters.with_stock" type="checkbox" class="form-check-input" />
            <label class="form-check-label" for="tp-with-stock">Выводить остаток</label>
          </div>
          <span v-if="stockDate" class="text-muted small">Остатки на {{ stockDate }}</span>
        </div>
      </div>
    </div>

    <!-- Таблица результатов -->
    <div class="card shadow-sm">
      <div class="card-header text-white bg-wb-green-deep-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0"><i class="bi bi-crown me-2"></i>ТОП-{{ filters.limit }} товаров</h5>
        <div class="d-flex gap-2">
          <span class="badge bg-light text-dark align-self-center">
            {{ filters.date_from }} — {{ filters.date_to }}
          </span>
          <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!rows.length">
            <i class="bi bi-file-earmark-excel me-1"></i> Excel
          </button>
        </div>
      </div>

      <div class="card-body p-0">
        <div v-if="isLoading" class="text-center p-5">
          <div class="spinner-border text-primary" role="status"></div>
          <div class="mt-2 text-muted">Загрузка данных...</div>
        </div>

        <MarginTable
          v-else
          :rows="rows"
          footer-label="Итого по ТОПу:"
          :show-stock="filters.with_stock"
          :period="`${filters.date_from} — ${filters.date_to}`"
          show-breakdown
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-top-products.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'
import MarginTable from '@/components/profit/MarginTable.vue'
import { exportMarginExcel } from '@/api/profit'
import WbDateInput from '../components/common/WbDateInput.vue'

const route = useRoute()
const router = useRouter()

const today = new Date()
const defTo = today.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 30 * 864e5).toISOString().slice(0, 10)

const SORTS = ['qnt', 'amount', 'net_profit', 'clean_margin']
const LIMITS = [20, 50, 200, 500, 1000]

// Фильтры живут в URL: F5 сохраняет отчёт, ссылку можно отправить.
const filters = ref({
  date_from: String(route.query.date_from || defFrom),
  date_to: String(route.query.date_to || defTo),
  sort_by: SORTS.includes(String(route.query.sort_by)) ? String(route.query.sort_by) : 'qnt',
  limit: LIMITS.includes(Number(route.query.limit)) ? Number(route.query.limit) : 20,
  with_stock: route.query.with_stock === '1'
})

const { data: rowsRaw, isLoading, refetch } = useQuery({
  queryKey: computed(() => ['top-products', filters.value.date_from, filters.value.date_to, filters.value.sort_by, filters.value.limit, filters.value.with_stock]),
  queryFn: () => api.get('/api/wb-profit/top-products', { params: { ...filters.value, with_stock: filters.value.with_stock ? 1 : 0 } }).then(r => r.data),
  initialData: [] as any[]
})

const rows = computed(() => Array.isArray(rowsRaw.value) ? rowsRaw.value : [])

// Фактическая дата снимка остатков (может быть < date_to — фолбэк)
const stockDate = computed(() => {
  if (!filters.value.with_stock) return ''
  const d = rows.value[0]?.stock_date
  return d ? String(d).slice(0, 10) : ''
})

// URL → фильтры (навигация назад/вперёд, чужая ссылка)
function applyFromRoute(nq: any) {
  const s = String(nq.sort_by || '')
  const l = Number(nq.limit)
  const next = {
    date_from: String(nq.date_from || defFrom),
    date_to: String(nq.date_to || defTo),
    sort_by: SORTS.includes(s) ? s : 'qnt',
    limit: LIMITS.includes(l) ? l : 20,
    with_stock: nq.with_stock === '1'
  }
  const cur = filters.value
  if (cur.date_from !== next.date_from || cur.date_to !== next.date_to ||
      cur.sort_by !== next.sort_by || cur.limit !== next.limit ||
      cur.with_stock !== next.with_stock) {
    filters.value = next
  }
}

// фильтры → URL (replace, чтобы не плодить историю)
let syncing = false
function syncRoute() {
  const q: Record<string, string> = {
    date_from: filters.value.date_from,
    date_to: filters.value.date_to
  }
  if (filters.value.sort_by !== 'qnt') q.sort_by = filters.value.sort_by
  if (filters.value.limit !== 20) q.limit = String(filters.value.limit)
  if (filters.value.with_stock) q.with_stock = '1'
  syncing = true
  router.replace({ path: '/wb-profit/top-products', query: q })
    .finally(() => setTimeout(() => (syncing = false), 50))
}

watch(filters, () => syncRoute(), { deep: true })
watch(() => route.query, (nq) => {
  if (syncing) return
  applyFromRoute(nq)
})

const resetFilters = () => {
  filters.value = {
    date_from: defFrom,
    date_to: defTo,
    sort_by: 'qnt',
    limit: 20,
    with_stock: false
  }
}

const exportExcel = () => exportMarginExcel(
  rows.value,
  `top-products_${filters.value.date_from}_${filters.value.date_to}.xlsx`,
  'ТОП товаров',
  filters.value.with_stock,
)

onMounted(() => {
  document.title = 'ТОП товаров за период — SelBI'
})
</script>
