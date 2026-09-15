<template>
  <div class="container-xxl sales-funnel-wb-card page-sales-funnel-wb-card">
    <PageHeaderWidget :title="'Воронка продаж: Карточка WB'" :nm-id="filters.nm_id || card?.nmID || ''" />

    <div class="row mt-3">
      <div class="col-md-6">
        <WbFilterBar
          v-model:nm-id="filters.nm_id"
          v-model:date-from="filters.date_from"
          v-model:date-to="filters.date_to"
          @apply="fetchData"
          @reset="reset"
        />
      </div>
      <div class="col-md-6">
        <div v-if="!filters.nm_id" class="alert alert-warning">
          Выберите артикул WB и нажмите «Применить».
        </div>
      </div>
    </div>

    <div v-if="isLoading" class="text-center p-4 text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка...
    </div>
    <div v-else-if="cardError" class="alert alert-danger mt-3">
      Не удалось загрузить данные воронки.
    </div>
    <template v-else-if="filters.nm_id">
      <SalesFunnelChart :data="chartData" />

      <div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden">
        <div class="card-header text-white d-flex justify-content-between align-items-center" style="background:linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700">
          <span>Воронка - Переход / Корзина / Заказ WB</span>
          <button class="btn btn-sm btn-light" style="font-size:12px; padding:4px 12px; border-radius:6px" @click="exportExcel" :disabled="!rows.length">
            <i class="bi bi-file-earmark-excel me-1"></i> Excel
          </button>
        </div>
        <div v-if="!rows.length" class="p-4 text-center text-muted">
          Нет данных за выбранный период.
        </div>
        <div v-else style="overflow-x:auto">
          <table ref="tableRef" class="table table-bordered table-striped table-hover kv-grid-table funnel-table mb-0" style="font-size:12px; width:100%; table-layout:fixed">
            <thead>
              <tr>
                <th style="width:110px; text-align:center; white-space:nowrap">Дата</th>
                <th style="width:110px; text-align:center; white-space:nowrap">Артикул WB</th>
                <th style="width:90px; text-align:center; white-space:nowrap">Переходов</th>
                <th style="width:80px; text-align:center; white-space:nowrap">Корзин</th>
                <th style="width:80px; text-align:center; white-space:nowrap">CR, %</th>
                <th style="width:80px; text-align:center; white-space:nowrap">Заказов</th>
                <th style="width:110px; text-align:center; white-space:nowrap">CR в заказ, %</th>
                <th style="width:110px; text-align:center; white-space:nowrap">Сумма заказов</th>
                <th style="width:100px; text-align:center; white-space:nowrap">Ср цена, руб</th>
                <th style="width:80px; text-align:center; white-space:nowrap">Выкупили</th>
                <th style="width:80px; text-align:center; white-space:nowrap">SR, %</th>
                <th style="width:110px; text-align:center; white-space:nowrap">Сумма выкупов</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in rows" :key="row.date + '-' + row.nm_id">
                <td style="text-align:center; white-space:nowrap">{{ fmtDate(row.date) }}</td>
                <td style="text-align:center; white-space:nowrap"><a :href="`/wb/detail?nm_id=${row.nm_id}`" target="_blank" style="text-decoration:none">{{ row.nm_id }}</a></td>
                <td style="text-align:right">{{ fmt0(row.open_count) }}</td>
                <td style="text-align:right">{{ fmt0(row.cart_count) }}</td>
                <td style="text-align:right">{{ row.open_to_cart !== null ? fmt2(row.open_to_cart) + '%' : '-' }}</td>
                <td style="text-align:right">{{ fmt0(row.order_count) }}</td>
                <td style="text-align:right">{{ row.cart_to_order !== null ? fmt2(row.cart_to_order) + '%' : '-' }}</td>
                <td style="text-align:right">{{ fmt2(row.order_sum) }}</td>
                <td style="text-align:right">{{ row.order_count > 0 ? fmt2(row.order_sum / row.order_count) : fmt2(0) }}</td>
                <td style="text-align:right">{{ fmt0(row.buyout_count) }}</td>
                <td style="text-align:right">{{ row.order_to_buyout !== null ? fmt2(row.order_to_buyout) + '%' : '-' }}</td>
                <td style="text-align:right">{{ fmt2(row.buyout_sum) }}</td>
              </tr>
            </tbody>
            <tfoot v-if="rows.length">
              <tr class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px">
                <td colspan="2" style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
                <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(totals.open_count) }}</td>
                <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(totals.cart_count) }}</td>
                <td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
                <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(totals.order_count) }}</td>
                <td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
                <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt2(totals.order_sum) }}</td>
                <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ totals.order_count ? fmt2(totals.order_sum / totals.order_count) : fmt2(0) }}</td>
                <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(totals.buyout_count) }}</td>
                <td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
                <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt2(totals.buyout_sum) }}</td>
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
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeaderWidget from '../components/common/PageHeaderWidget.vue'
import WbFilterBar from '../components/common/WbFilterBar.vue'
import SalesFunnelChart from '../components/funnel/SalesFunnelChart.vue'
import { salesFunnelApi } from '../api/salesFunnel'

const route = useRoute()
const router = useRouter()

function getDefaultDates() {
  const today = new Date()
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 13)
  return {
    date_from: from.toISOString().slice(0, 10),
    date_to: today.toISOString().slice(0, 10),
  }
}

const filters = ref({
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
  if (nm) filters.value.nm_id = nm
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
    nextTick(enableResize)
  }
}

const reset = () => {
  filters.value.nm_id = ''
  const dates = getDefaultDates()
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

const enableResize = () => {
  const table = tableRef.value
  if (!table) return
  table.querySelectorAll('th').forEach((th) => {
    if (th.querySelector('.col-resizer')) return
    th.style.position = 'relative'
    const resizer = document.createElement('div')
    resizer.className = 'col-resizer'
    resizer.style.cssText = 'position:absolute; top:0; right:0; width:6px; height:100%; cursor:col-resize; user-select:none; z-index:1'
    th.appendChild(resizer)
    let startX = 0
    let startWidth = 0
    const onMove = (e: MouseEvent) => {
      const width = Math.max(40, startWidth + e.clientX - startX)
      th.style.width = `${width}px`
      th.style.minWidth = `${width}px`
      table.style.width = '100%'
      table.style.tableLayout = 'auto'
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
    }
    resizer.addEventListener('mousedown', (e) => {
      startX = e.clientX
      startWidth = th.offsetWidth
      document.body.style.cursor = 'col-resize'
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
      e.preventDefault()
    })
  })
  const fit = () => {
    if (!table) return
    table.style.width = '100%'
    table.style.tableLayout = 'auto'
  }
  window.addEventListener('resize', fit)
  fit()
}

const fmtDate = (value: string) => value ? new Date(`${value}T00:00:00`).toLocaleDateString('ru-RU') : '—'
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
  nextTick(enableResize)
})
</script>

<style scoped>
.kv-totals > td { background-color:#f2e7c3 !important; box-shadow:none !important; }
.funnel-table { table-layout:fixed; width:100%; }
.funnel-table th { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.funnel-table td { overflow:hidden; text-overflow:ellipsis; }
.funnel-table tbody td { white-space:nowrap; }
</style>
