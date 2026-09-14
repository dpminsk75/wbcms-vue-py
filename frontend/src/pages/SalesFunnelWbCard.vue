<template>
  <div class="sales-funnel-wb-card" style="padding:20px 15px">
    <PageHeaderWidget :title="'Воронка продаж: Карточка WB'" :nm-id="filters.nm_id || card?.nmID || ''" />

    <div v-if="!filters.nm_id" class="alert alert-warning mt-3">
      Выберите артикул WB и нажмите «Применить».
    </div>

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
    </div>

    <div v-if="isLoading" class="text-center p-4 text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка...
    </div>
    <div v-else-if="cardError" class="alert alert-danger mt-3">
      Не удалось загрузить данные воронки.
    </div>
    <template v-else-if="filters.nm_id">
      <div v-if="card" class="card mb-3" style="border:1px solid #e5e7eb; border-radius:12px; overflow:hidden">
        <div class="card-header text-white" style="background:linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700">
          <span>{{ card.title || 'Без названия' }}</span>
          <span class="text-white-50" style="font-weight:400">WB: {{ card.nmID }} · {{ card.vendorCode || 'без артикула' }}</span>
        </div>
        <div class="card-body">
          <div class="row g-2">
            <div class="col-md-3">
              <div class="p-2" style="background:#f8f9fa; border-radius:8px">
                <div style="font-size:11px; color:#888">Бренд</div>
                <div style="font-weight:700">{{ card.brand || '—' }}</div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="p-2" style="background:#f8f9fa; border-radius:8px">
                <div style="font-size:11px; color:#888">Предмет</div>
                <div style="font-weight:700">{{ card.subject || '—' }}</div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="p-2" style="background:#f8f9fa; border-radius:8px">
                <div style="font-size:11px; color:#888">Период</div>
                <div style="font-weight:700; font-size:12px">{{ fmtDate(filters.date_from) }} — {{ fmtDate(filters.date_to) }}</div>
              </div>
            </div>
            <div class="col-md-3">
              <div class="p-2" style="background:#f8f9fa; border-radius:8px">
                <div style="font-size:11px; color:#888">Строк в таблице</div>
                <div style="font-weight:700">{{ rows.length }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <SalesFunnelChart :data="chartData" />

      <div class="row g-2 mb-3">
        <div class="col-md-2 col-sm-4">
          <div class="summary-box"><div>Переходы</div><b>{{ fmt0(totals.open_count) }}</b></div>
        </div>
        <div class="col-md-2 col-sm-4">
          <div class="summary-box cart"><div>Корзины</div><b>{{ fmt0(totals.cart_count) }}</b></div>
        </div>
        <div class="col-md-2 col-sm-4">
          <div class="summary-box order"><div>Заказы</div><b>{{ fmt0(totals.order_count) }}</b></div>
        </div>
        <div class="col-md-2 col-sm-4">
          <div class="summary-box buyout"><div>Выкупы</div><b>{{ fmt0(totals.buyout_count) }}</b></div>
        </div>
        <div class="col-md-2 col-sm-4">
          <div class="summary-box money"><div>Сумма заказов</div><b>{{ fmtMoney(totals.order_sum) }}</b></div>
        </div>
        <div class="col-md-2 col-sm-4">
          <div class="summary-box money"><div>Сумма выкупов</div><b>{{ fmtMoney(totals.buyout_sum) }}</b></div>
        </div>
      </div>

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
          <table ref="tableRef" class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:12px; width:100%; table-layout:auto">
            <thead>
              <tr>
                <th style="width:120px; text-align:center">Дата</th>
                <th style="width:100px; text-align:center">Артикул WB</th>
                <th style="width:260px; text-align:center">Товар</th>
                <th style="width:130px; text-align:center">Артикул продавца</th>
                <th style="width:100px; text-align:center">Бренд</th>
                <th style="width:90px; text-align:center">Переходы</th>
                <th style="width:90px; text-align:center">Корзины</th>
                <th style="width:120px; text-align:center">CR переход→корзина, %</th>
                <th style="width:90px; text-align:center">Заказы</th>
                <th style="width:120px; text-align:center">CR корзина→заказ, %</th>
                <th style="width:120px; text-align:center">Сумма заказов, ₽</th>
                <th style="width:110px; text-align:center">Ср. заказ, ₽</th>
                <th style="width:90px; text-align:center">Выкупы</th>
                <th style="width:90px; text-align:center">SR, %</th>
                <th style="width:120px; text-align:center">Сумма выкупов, ₽</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in rows" :key="row.date + '-' + row.nm_id">
                <td style="text-align:center; white-space:nowrap">{{ fmtDate(row.date) }}</td>
                <td style="text-align:center; white-space:nowrap"><a :href="`/wb/detail?nm_id=${row.nm_id}`" target="_blank" style="text-decoration:none">{{ row.nm_id }}</a></td>
                <td style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap" :title="row.card_name">{{ row.card_name || 'Без названия' }}</td>
                <td style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap">{{ row.vendor_code || '—' }}</td>
                <td style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap">{{ row.brand || '—' }}</td>
                <td style="text-align:right; font-weight:700">{{ fmt0(row.open_count) }}</td>
                <td style="text-align:right; font-weight:700">{{ fmt0(row.cart_count) }}</td>
                <td style="text-align:right">{{ row.open_to_cart !== null ? fmt2(row.open_to_cart) : '—' }}</td>
                <td style="text-align:right; font-weight:700">{{ fmt0(row.order_count) }}</td>
                <td style="text-align:right">{{ row.cart_to_order !== null ? fmt2(row.cart_to_order) : '—' }}</td>
                <td style="text-align:right">{{ fmtMoney(row.order_sum) }}</td>
                <td style="text-align:right">{{ fmtMoney(row.avg_order) }}</td>
                <td style="text-align:right; font-weight:700">{{ fmt0(row.buyout_count) }}</td>
                <td style="text-align:right">{{ row.order_to_buyout !== null ? fmt2(row.order_to_buyout) : '—' }}</td>
                <td style="text-align:right">{{ fmtMoney(row.buyout_sum) }}</td>
              </tr>
            </tbody>
            <tfoot v-if="rows.length">
              <tr style="font-weight:700; background:#fff3cd">
                <td colspan="5" style="text-align:right">Итого</td>
                <td style="text-align:right">{{ fmt0(totals.open_count) }}</td>
                <td style="text-align:right">{{ fmt0(totals.cart_count) }}</td>
                <td style="text-align:right">{{ totals.open_to_cart !== null ? fmt2(totals.open_to_cart) : '—' }}</td>
                <td style="text-align:right">{{ fmt0(totals.order_count) }}</td>
                <td style="text-align:right">{{ totals.cart_to_order !== null ? fmt2(totals.cart_to_order) : '—' }}</td>
                <td style="text-align:right">{{ fmtMoney(totals.order_sum) }}</td>
                <td style="text-align:right">{{ totals.order_count ? fmtMoney(totals.order_sum / totals.order_count) : '—' }}</td>
                <td style="text-align:right">{{ fmt0(totals.buyout_count) }}</td>
                <td style="text-align:right">{{ totals.order_to_buyout !== null ? fmt2(totals.order_to_buyout) : '—' }}</td>
                <td style="text-align:right">{{ fmtMoney(totals.buyout_sum) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeaderWidget from '../components/common/PageHeaderWidget.vue'
import WbFilterBar from '../components/common/WbFilterBar.vue'
import SalesFunnelChart from '../components/dashboard/SalesFunnelChart.vue'
import { salesFunnelApi } from '../api/salesFunnel'

const route = useRoute()
const router = useRouter()

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

const getDefaultDates = () => {
  const today = new Date()
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 13)
  return {
    date_from: from.toISOString().slice(0, 10),
    date_to: today.toISOString().slice(0, 10),
  }
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
.summary-box {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px 14px;
  min-height: 74px;
}
.summary-box div:first-child {
  color: #6b7280;
  font-size: 11px;
  margin-bottom: 5px;
}
.summary-box b {
  font-size: 20px;
  color: #1f2937;
}
.summary-box.cart b { color:#660ec8 }
.summary-box.order b { color:#5067de }
.summary-box.buyout b { color:#1e9e7c }
.summary-box.money b { color:#8a2be0 }
</style>
