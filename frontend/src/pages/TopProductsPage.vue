<template>
  <div class="container-xxl page-top-products">
    <h1 class="page-title">{{ $route.meta.title || 'ТОП товаров за период' }}</h1>

    <!-- Фильтр: панель темы — пресеты + даты, поля страницы отдельной строкой, кнопки внизу -->
    <div class="wb-filter-panel page-top-products__filter">
      <WbDateRangeFilter v-model:from="filters.date_from" v-model:to="filters.date_to" default-preset="30" bare>
        <template #inline>
          <div class="page-top-products__fields">
            <div class="wb-field">
              <label class="wb-field__label">Сортировать по</label>
              <select v-model="filters.sort_by" class="form-control">
                <option value="qnt">Количеству продаж (шт)</option>
                <option value="amount">Выручке (руб)</option>
                <option value="net_profit">По итогу от WB (руб)</option>
                <option value="clean_margin">Марже после налогов (руб)</option>
              </select>
            </div>
            <div class="wb-field">
              <label class="wb-field__label">Показать товаров</label>
              <select v-model.number="filters.limit" class="form-control">
                <option :value="20">ТОП-20</option>
                <option :value="50">ТОП-50</option>
                <option :value="200">ТОП-200</option>
                <option :value="500">ТОП-500</option>
                <option :value="1000">ТОП-1000</option>
              </select>
            </div>
            <div class="wb-field">
              <label class="wb-field__label">Остаток</label>
              <label class="page-top-products__stock">
                <input type="checkbox" v-model="filters.with_stock" />
                <span>Выводить остаток</span>
              </label>
              <span v-if="stockDate" class="page-top-products__stock-date">на {{ stockDate }}</span>
            </div>
          </div>
        </template>
      </WbDateRangeFilter>
      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" @click="onApply" :disabled="isLoading">
          {{ isLoading ? 'Загрузка...' : 'Сформировать' }}
        </button>
        <button class="btn btn--outline wb-filter-panel__apply" @click="resetFilters" :disabled="isLoading">Сбросить</button>
      </div>
    </div>

    <!-- Таблица: стандарт темы (.tbl-card → .card__hd → .tbl-wrap → .tbl) -->
    <div class="tbl-card tbl-card--compact page-top-products__card">
      <div class="card__hd">
        <span><i class="bi bi-crown me-2"></i>ТОП-{{ filters.limit }} товаров</span>
        <span class="spacer"></span>
        <span class="hd-badge">{{ filters.date_from }} — {{ filters.date_to }}</span>
        <ExcelButton :disabled="!rows.length" @click="exportExcel" />
      </div>
      <div v-if="isLoading" class="text-center p-4 text-muted">
        <span class="spinner-border spinner-border-sm"></span> Загрузка данных...
      </div>
      <MarginTable
        v-else
        :rows="rows"
        footer-label="Итого по ТОПу:"
        :show-stock="filters.with_stock"
        :period="`${filters.date_from} — ${filters.date_to}`"
        :date-from="filters.date_from"
        :date-to="filters.date_to"
        resize-key="profit-top-products"
        compact
        show-breakdown
      />
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
import ExcelButton from '@/components/common/ExcelButton.vue'
import WbDateRangeFilter from '@/components/common/WbDateRangeFilter.vue'
import { exportMarginExcel } from '@/api/profit'

const route = useRoute()
const router = useRouter()

// локальное время (toISOString даёт UTC и сдвигает сутки)
// дефолт — 30 суток (как пресет «30 дней»)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const defaultDates = () => {
  const to = new Date()
  const from = new Date(to.getFullYear(), to.getMonth(), to.getDate() - 29)
  return { date_from: fmtD(from), date_to: fmtD(to) }
}

const SORTS = ['qnt', 'amount', 'net_profit', 'clean_margin']
const LIMITS = [20, 50, 200, 500, 1000]

const defaults = () => {
  const d = defaultDates()
  return { date_from: d.date_from, date_to: d.date_to, sort_by: 'qnt', limit: 20, with_stock: false }
}

const fromRoute = (q: any) => {
  const s = String(q.sort_by || '')
  const l = Number(q.limit)
  const d = defaultDates()
  return {
    date_from: String(q.date_from || d.date_from),
    date_to: String(q.date_to || d.date_to),
    sort_by: SORTS.includes(s) ? s : 'qnt',
    limit: LIMITS.includes(l) ? l : 20,
    with_stock: q.with_stock === '1',
  }
}

// Фильтры живут в URL: F5 сохраняет отчёт, ссылку можно отправить.
const filters = ref(fromRoute(route.query))
// applied — значения, по которым реально запрошены данные (запрос — по кнопке «Сформировать»)
const applied = ref({ ...filters.value })

const { data: rowsRaw, isLoading, refetch } = useQuery({
  queryKey: computed(() => ['top-products', applied.value.date_from, applied.value.date_to, applied.value.sort_by, applied.value.limit, applied.value.with_stock]),
  queryFn: () => api.get('/api/wb-profit/top-products', { params: { ...applied.value, with_stock: applied.value.with_stock ? 1 : 0 } }).then(r => r.data),
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
  const next = fromRoute(nq)
  const cur = filters.value
  if (cur.date_from !== next.date_from || cur.date_to !== next.date_to ||
      cur.sort_by !== next.sort_by || cur.limit !== next.limit ||
      cur.with_stock !== next.with_stock) {
    filters.value = next
    applied.value = { ...next }
  }
}

// фильтры → URL (replace, чтобы не плодить историю)
let syncing = false
function syncRoute() {
  const q: Record<string, string> = {
    date_from: applied.value.date_from,
    date_to: applied.value.date_to
  }
  if (applied.value.sort_by !== 'qnt') q.sort_by = applied.value.sort_by
  if (applied.value.limit !== 20) q.limit = String(applied.value.limit)
  if (applied.value.with_stock) q.with_stock = '1'
  syncing = true
  router.replace({ path: '/wb-profit/top-products', query: q })
    .finally(() => setTimeout(() => (syncing = false), 50))
}

/** Применение фильтра: значения полей → запрос (если поля не менялись — дёргаем вручную). */
const onApply = () => {
  const same = JSON.stringify(applied.value) === JSON.stringify(filters.value)
  applied.value = { ...filters.value }
  syncRoute()
  if (same) refetch()
}

watch(() => route.query, (nq) => {
  if (syncing) return
  applyFromRoute(nq)
})

const resetFilters = () => {
  const same = JSON.stringify(applied.value) === JSON.stringify(defaults())
  filters.value = defaults()
  applied.value = { ...filters.value }
  syncRoute()
  if (same) refetch()
}

const exportExcel = () => exportMarginExcel(
  rows.value,
  `top-products_${applied.value.date_from}_${applied.value.date_to}.xlsx`,
  'ТОП товаров',
  applied.value.with_stock,
)

onMounted(() => {
  document.title = 'ТОП товаров за период — SelBI'
})
</script>
