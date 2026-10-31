<template>
  <div class="container-xxl sales-funnel-wb-card page-sales-funnel-wb-card">
    <PageHeaderWidget :title="'Воронка продаж: Карточка WB'" :nm-id="filters.nm_id || card?.nmID || ''" />

    <!-- Фильтр: общий WbUniversalFilter — карточка + даты, кнопки «Применить/Сбросить» -->
    <WbUniversalFilter
      v-model:product="filters.product"
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      :show-brand-category="false"
      @apply="onApply"
      @reset="onReset"
    />

    <div v-if="!filters.nm_id" class="alert alert-warning page-sales-funnel-wb-card__hint">
      Выберите карточку WB и нажмите «Применить».
    </div>

    <div v-if="isLoading" class="text-center p-4 text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка...
    </div>
    <div v-else-if="cardError" class="alert alert-danger mt-3">
      Не удалось загрузить данные воронки.
    </div>
    <template v-else-if="filters.nm_id">
      <SalesFunnelChart :data="chartData" />

      <div class="tbl-card page-sales-funnel-wb-card__table-card">
        <div class="card__hd">
          <span>Воронка — Переход / Корзина / Заказ WB</span>
          <span class="spacer"></span>
          <ExcelButton :disabled="!rows.length" @click="exportExcel" />
        </div>
        <div v-if="!rows.length" class="p-4 text-center text-muted">
          Нет данных за выбранный период.
        </div>
        <div v-else class="tbl-wrap">
          <table ref="tableRef" class="tbl page-sales-funnel-wb-card__table">
            <thead>
              <tr>
                <th class="t-center">Дата</th>
                <th class="t-center">Артикул WB</th>
                <th class="num">Переходов</th>
                <th class="num">Корзин</th>
                <th class="num">CR, %</th>
                <th class="num">Заказов</th>
                <th class="num">CR в заказ, %</th>
                <th class="num">Сумма заказов</th>
                <th class="num">Ср цена, руб</th>
                <th class="num">Выкупили</th>
                <th class="num">SR, %</th>
                <th class="num">Сумма выкупов</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in rows" :key="row.date + '-' + row.nm_id">
                <td class="t-center">{{ fmtDate(row.date) }}</td>
                <td class="t-center"><a :href="`/wb/detail?nm_id=${row.nm_id}`" target="_blank" class="page-sales-funnel-wb-card__nm-link">{{ row.nm_id }}</a></td>
                <td class="num">{{ fmt0(row.open_count) }}</td>
                <td class="num">{{ fmt0(row.cart_count) }}</td>
                <td class="num">{{ row.open_to_cart !== null ? fmt2(row.open_to_cart) + '%' : '—' }}</td>
                <td class="num">{{ fmt0(row.order_count) }}</td>
                <td class="num">{{ row.cart_to_order !== null ? fmt2(row.cart_to_order) + '%' : '—' }}</td>
                <td class="num">{{ fmt2(row.order_sum) }}</td>
                <td class="num">{{ row.order_count > 0 ? fmt2(row.order_sum / row.order_count) : fmt2(0) }}</td>
                <td class="num">{{ fmt0(row.buyout_count) }}</td>
                <td class="num">{{ row.order_to_buyout !== null ? fmt2(row.order_to_buyout) + '%' : '—' }}</td>
                <td class="num">{{ fmt2(row.buyout_sum) }}</td>
              </tr>
            </tbody>
            <tfoot v-if="rows.length">
              <tr class="tbl__total">
                <td></td>
                <td></td>
                <td>{{ fmt0(totals.open_count) }}</td>
                <td>{{ fmt0(totals.cart_count) }}</td>
                <td></td>
                <td>{{ fmt0(totals.order_count) }}</td>
                <td></td>
                <td>{{ fmt2(totals.order_sum) }}</td>
                <td>{{ totals.order_count ? fmt2(totals.order_sum / totals.order_count) : fmt2(0) }}</td>
                <td>{{ fmt0(totals.buyout_count) }}</td>
                <td></td>
                <td>{{ fmt2(totals.buyout_sum) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-sales-funnel-wb-card.css'
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { useDateFmt } from '../composables/useDateFmt'
import { useTableResize } from '../composables/useTableResize'
import PageHeaderWidget from '../components/common/PageHeaderWidget.vue'
import WbUniversalFilter from '../components/common/WbUniversalFilter.vue'
import ExcelButton from '../components/common/ExcelButton.vue'
import SalesFunnelChart from '../components/funnel/SalesFunnelChart.vue'
import { salesFunnelApi } from '../api/salesFunnel'

const route = useRoute()
const router = useRouter()

// локальное время (toISOString даёт UTC и сдвигает сутки)
// дефолт — ровно 14 суток (как пресет «14 дней»)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const getDefaultDates = () => {
  const to = new Date()
  const from = new Date(to.getFullYear(), to.getMonth(), to.getDate() - 13)
  return { date_from: fmtD(from), date_to: fmtD(to) }
}

const filters = ref({
  product: '',
  nm_id: '',
  date_from: getDefaultDates().date_from,
  date_to: getDefaultDates().date_to,
})

const card = ref<any>(null)
const rows = ref<any[]>([])
const chartData = ref<any[]>([])
const totals = ref<any>({
  open_count: 0,
  cart_count: 0,
  order_count: 0,
  order_sum: 0,
  buyout_count: 0,
  buyout_sum: 0,
  open_to_cart: null,
  cart_to_order: null,
  order_to_buyout: null,
})
const isLoading = ref(false)
const cardError = ref(false)
const tableRef = ref<HTMLTableElement | null>(null)

// ресайзер колонок — общий (ширины запоминаются, слушатели снимаются)
useTableResize(tableRef, { storeKey: 'sales-funnel-wb-card' })

/** WbUniversalFilter даёт свободную маску (nm_id/артикул/название) — резолвим в nm_id. */
const resolveNmId = async (mask: string): Promise<string> => {
  const q = String(mask || '').trim()
  if (!q) return ''
  if (/^\d+$/.test(q)) return q
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
  const q = route.query as Record<string, any>
  const pick = (...keys: string[]) => {
    for (const key of keys) if (q[key]) return String(q[key])
    return ''
  }
  const df = pick('date_from', 'dateFrom', 'DPFilterForm[date_from]', 'DPFilterForm%5Bdate_from%5D')
  const dt = pick('date_to', 'dateTo', 'DPFilterForm[date_to]', 'DPFilterForm%5Bdate_to%5D')
  const nm = pick('nm_id', 'nmId', 'DPFilterForm[nm_id]', 'DPFilterForm%5Bnm_id%5D')
  if (df) filters.value.date_from = df
  if (dt) filters.value.date_to = dt
  if (nm) { filters.value.nm_id = nm; filters.value.product = nm }
}

const syncRoute = () => {
  const q: Record<string, string> = {}
  if (filters.value.nm_id) q.nm_id = filters.value.nm_id
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  router.replace({ path: route.path, query: q }).catch(() => {})
}

const fetchData = async () => {
  if (!filters.value.nm_id) return
  isLoading.value = true
  cardError.value = false
  try {
    const data = await salesFunnelApi.get({
      nm_id: Number(filters.value.nm_id),
      date_from: filters.value.date_from,
      date_to: filters.value.date_to,
    })
    card.value = data.card || null
    rows.value = data.rows || []
    chartData.value = data.chartData || []
    totals.value = data.totals || totals.value
  } catch {
    cardError.value = true
  } finally {
    isLoading.value = false
  }
}

/** Применение фильтра: маска карточки → nm_id, затем запрос. */
const onApply = async () => {
  filters.value.nm_id = await resolveNmId(filters.value.product)
  syncRoute()
  fetchData()
}

/** Сброс фильтра: карточка пустая, даты — 14 суток. */
const onReset = () => {
  const dates = getDefaultDates()
  filters.value.product = ''
  filters.value.nm_id = ''
  filters.value.date_from = dates.date_from
  filters.value.date_to = dates.date_to
  card.value = null
  rows.value = []
  chartData.value = []
  totals.value = {
    open_count: 0,
    cart_count: 0,
    order_count: 0,
    order_sum: 0,
    buyout_count: 0,
    buyout_sum: 0,
    open_to_cart: null,
    cart_to_order: null,
    order_to_buyout: null,
  }
  syncRoute()
}

const { fmtDate } = useDateFmt()
const fmt0 = (value: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(value) || 0))
const fmt1 = (value: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(value) || 0)
const fmt2 = (value: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value) || 0)
const fmtMoney = (value: any) => fmt2(value) + ' ₽'

const exportExcel = async () => {
  if (!filters.value.nm_id) return
  const blob = await salesFunnelApi.exportExcel({
    nm_id: Number(filters.value.nm_id),
    date_from: filters.value.date_from,
    date_to: filters.value.date_to,
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `wb_sales_funnel_${filters.value.nm_id}_${filters.value.date_from}_${filters.value.date_to}.xlsx`
  link.click()
  URL.revokeObjectURL(url)
}

watch(() => [filters.value.nm_id, filters.value.date_from, filters.value.date_to], () => {
  syncRoute()
})

onMounted(() => {
  initFromQuery()
  fetchData()
})
</script>
