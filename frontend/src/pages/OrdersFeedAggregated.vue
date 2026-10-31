<template>
  <div class="container-xxl page-orders-feed-aggregated">
    <h1 class="page-title">Сводка по товарам (заказы)</h1>

    <!-- Фильтр: единая универсальная компонента (даты + карточка + бренд + категория),
         сортировка — в её слоте #extra, кнопки Применить/Сбросить — её штатные, снизу слева -->
    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:product="filters.nm_id"
      v-model:brand="filters.brand"
      v-model:category="filters.category"
      :brands="brands"
      :categories="categories"
      :show-product="true"
      :show-brand-category="true"
      :show-quick="true"
      default-preset="7"
      @apply="onApply"
      @reset="reset"
    >
      <template #extra>
        <div class="page-orders-feed-aggregated__sort">
          <label class="wb-field__label">Сортировка</label>
          <select v-model="filters.sort_by" class="wb-input" @change="onApply">
            <option value="count">По количеству</option>
            <option value="sum">По сумме</option>
          </select>
        </div>
      </template>
    </WbUniversalFilter>

    <div v-if="filterError" class="alert alert-warning mb-3">{{ filterError }}</div>

    <!-- Сводка -->
    <div v-if="summary" class="grid-4 page-orders-feed-aggregated__summary">
      <div class="tile tile--8">
        <div class="tile__label">Количество заказов</div>
        <div class="tile__value">{{ fmt0(summary.count) }}</div>
      </div>
      <div class="tile">
        <div class="tile__label">Из них</div>
        <div class="tile__split">
          <span class="tile__split-item">{{ fmt0(summary.fbs_count) }}<span class="badge badge--info">FBS</span></span>
          <span class="tile__split-item">{{ fmt0(summary.fbo_count) }}<span class="badge badge--ok">FBO</span></span>
        </div>
      </div>
      <div class="tile">
        <div class="tile__label">Сумма</div>
        <div class="tile__value">{{ fmt2(summary.sum) }} ₽</div>
      </div>
      <div class="tile">
        <div class="tile__label">СПП (среднее)</div>
        <div class="tile__value">{{ fmt1(summary.avg_spp) }} %</div>
      </div>
    </div>

    <!-- Воронка -->
    <div class="row mb-3" v-if="funnel">
      <div class="col-12">
        <OrderFunnel :funnel="funnel" :chart-data="chartData" />
      </div>
    </div>

    <!-- Таблица -->
    <div class="tbl-card tbl-card--compact">
      <div class="card__hd">
        <span>Сводка по товарам ({{ fmtDate(filters.date_from) }}<span v-if="filters.date_from!==filters.date_to"> — {{ fmtDate(filters.date_to) }}</span>)</span>
        <span class="spacer"></span>
        <ExcelButton :disabled="!items.length" @click="exportExcel" />
      </div>
      <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
      <div v-else class="tbl-wrap" ref="wrapRef">
        <table ref="tbl" class="tbl" style="width:100%; table-layout:auto">
          <thead>
            <tr>
              <th class="t-left">Товар</th>
              <th class="t-center">Заказов</th>
              <th class="t-center mobile-hide-col">Отмен</th>
              <th class="t-center mobile-hide-col">Цена в кар-ке (ср.)</th>
              <th class="t-center mobile-hide-col">Скидка, % (ср.)</th>
              <th class="t-center">Общая сумма</th>
              <th class="t-center mobile-hide-col">Цена со скидкой (ср.)</th>
              <th class="t-center mobile-hide-col">СПП (ср.)</th>
              <th class="t-center">Сумма продаж</th>
              <th class="t-center">Цена продажи (ср.)</th>
              <th class="t-center mobile-hide-col">Комиссия</th>
              <th class="t-center mobile-hide-col">Эквайринг</th>
              <th class="t-center">Логистика (сумма)</th>
              <th class="t-center mobile-hide-col">Логистика (ср.)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!items.length"><td colspan="14" class="text-center text-muted">Нет данных</td></tr>
            <tr v-for="r in items" :key="r.nm_id">
              <td class="t-left">
                <ProductCell
                  :photo="r.card_photos"
                  :title="r.card_title"
                  :sub="subLine(r)"
                  :vendor="r.card_vendor_code"
                  :link="'/wb/detail?DPFilterForm[nm_id]=' + r.nm_id"
                  :link-label="'WB: ' + r.nm_id"
                />
              </td>
              <td class="num">{{ fmt0(r.orders_cnt) }}</td>
              <td class="num mobile-hide-col"><span :class="r.cancelled_cnt>0 ? 't-neg' : ''">{{ r.cancelled_cnt ?? 0 }}</span></td>
              <td class="num mobile-hide-col">{{ fmtVal(r.avg_total_price) }}</td>
              <td class="num mobile-hide-col">{{ fmtVal(r.avg_discount,1) }}</td>
              <td class="num">{{ fmtVal(r.sum_price_with_disc) }}<span v-if="r.sum_price_with_disc!=null"> ₽</span></td>
              <td class="num mobile-hide-col">{{ fmtVal(r.avg_price_with_disc) }}</td>
              <td class="num mobile-hide-col">{{ r.avg_spp!=null ? fmt1(r.avg_spp)+'%' : '—' }}</td>
              <td class="num">{{ r.sum_finished!=null ? fmt2(r.sum_finished)+' ₽' : '—' }}</td>
              <td class="num">{{ fmtVal(r.avg_finished) }}</td>
              <td class="num mobile-hide-col page-orders-feed-aggregated__cell-stack">
                <template v-if="r.sum_commission!=null || r.avg_commission_pct!=null">
                  <span class="page-orders-feed-aggregated__sub">{{ r.sum_commission!=null ? fmt2(r.sum_commission)+' ₽' : '—' }}</span>
                  <span class="page-orders-feed-aggregated__sub-note">{{ r.avg_commission_pct!=null ? fmt1(r.avg_commission_pct)+'%' : '' }}</span>
                </template>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="num mobile-hide-col page-orders-feed-aggregated__cell-stack">
                <template v-if="r.sum_acquiring!=null || r.avg_acquiring_pct!=null">
                  <span class="page-orders-feed-aggregated__sub">{{ r.sum_acquiring!=null ? fmt2(r.sum_acquiring)+' ₽' : '—' }}</span>
                  <span class="page-orders-feed-aggregated__sub-note">{{ r.avg_acquiring_pct!=null ? fmt1(r.avg_acquiring_pct)+'%' : '' }}</span>
                </template>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="num">
                <span v-if="r.sum_delivery!=null" class="page-orders-feed-aggregated__sub">{{ fmt2(r.sum_delivery) }} ₽</span>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="num mobile-hide-col page-orders-feed-aggregated__cell-stack">
                <span v-if="r.avg_delivery!=null" class="page-orders-feed-aggregated__sub">{{ fmt2(r.avg_delivery) }} ₽</span>
                <span v-else class="text-muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <Pager :page="page" :total-pages="totalPages" :total="total" @change="onPage" />
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-orders-feed-aggregated.css'
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client'
import OrderFunnel from '../components/dashboard/OrderFunnel.vue'
import WbUniversalFilter from '../components/common/WbUniversalFilter.vue'
import ProductCell from '../components/common/ProductCell.vue'
import ExcelButton from '../components/common/ExcelButton.vue'
import Pager from '../components/common/Pager.vue'
import { useDateFmt } from '../composables/useDateFmt'
import { useNumFmt } from '../composables/useNumFmt'
import { useTableResize } from '../composables/useTableResize'
import { exportXlsx } from '../utils/exportXlsx'

const { fmtDate } = useDateFmt()
const { fmt0, fmt1, fmt2, fmtVal } = useNumFmt()

// локальное время (toISOString даёт UTC и сдвигает сутки)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const today = new Date()
const sixDaysAgo = new Date(today); sixDaysAgo.setDate(sixDaysAgo.getDate() - 6)
// дефолт — 7 дней (как в PHP-оригинале: date('Y-m-d', strtotime('-6 days')))
const defFrom = fmtD(sixDaysAgo)
const defTo = fmtD(today)
const filters = ref({ nm_id:'', date_from: defFrom, date_to: defTo, sort_by:'count', brand:'', category:'' })
const brands = ref<string[]>([])
const categories = ref<string[]>([])
const filterError = ref('')
const items = ref<any[]>([]), total = ref(0), page = ref(1), isLoading = ref(false)
const summary = ref<any>({count:0,fbs_count:0,fbo_count:0,sum:0,avg_spp:0})
const funnel = ref<any>({total_cnt:0,total_sum:0,bought_cnt:0,bought_sum:0,bought_pct:0,delivery_cnt:0,delivery_sum:0,delivery_pct:0,cancel_cnt:0,cancel_sum:0,cancel_pct:0,returns_cnt:0,returns_sum:0,returns_pct:0,buyout_pct:0})
const chartData = ref<any[]>([])
const tbl = ref<HTMLTableElement|null>(null)
const wrapRef = ref<HTMLDivElement|null>(null)
const totalPages = computed(()=> Math.max(1, Math.ceil(total.value/50)))

useTableResize(tbl, { storeKey: 'orders-feed-aggregated' })

/** Применение фильтра: карточка — это nmID (число), маска выбирается из подсказок. */
const onApply = ()=>{
  const nm = String(filters.value.nm_id || '').trim()
  if (nm && !/^\d+$/.test(nm)) {
    filterError.value = 'Карточку нужно выбрать из подсказок: введённое значение не является nmID.'
    return
  }
  filterError.value = ''
  page.value = 1
  fetchData()
}

const onPage = (p: number) => { page.value = p; fetchData() }

const reset = ()=>{
  filters.value.nm_id=''
  filters.value.brand=''
  filters.value.category=''
  filters.value.sort_by='count'
  filters.value.date_from=defFrom
  filters.value.date_to=defTo
  filterError.value=''
  page.value=1
  fetchData()
}

/** Справочники брендов и категорий — с бэкенда (как /api/sales-analysis/filters). */
const loadFilterLists = async ()=>{
  try{
    const { data } = await api.get('/api/orders/feed-aggregated/filters')
    brands.value = Array.isArray(data?.brands) ? data.brands : []
    categories.value = Array.isArray(data?.categories) ? data.categories : []
  }catch{
    brands.value = []
    categories.value = []
  }
}

/** Подпись под названием товара: предмет и бренд одной строкой. */
const subLine = (r: any) => {
  const subject = String(r.card_subject_name || '')
  const brandName = String(r.card_brand || '')
  if (subject && brandName) return subject + ' • ' + brandName
  return subject || brandName
}

const fetchData = async()=>{
  isLoading.value=true
  const q = new URLSearchParams({date_from: filters.value.date_from, date_to: filters.value.date_to, sort_by: filters.value.sort_by, page: String(page.value)} as any)
  if(filters.value.nm_id) q.set('nm_id', filters.value.nm_id)
  if(filters.value.brand) q.set('brand', filters.value.brand)
  if(filters.value.category) q.set('category', filters.value.category)
  const { data } = await api.get(`/api/orders/feed-aggregated?${q}`)
  items.value = data.items || []; total.value = data.total || 0
  summary.value = data.summary || summary.value
  funnel.value = data.funnel || funnel.value
  chartData.value = data.chart || []
  isLoading.value=false
}

const exportExcel = async()=>{
  if(!items.value.length) return
  const data = items.value.map((r:any)=> ({
    'nmID': r.nm_id,
    'Товар': r.card_title || '',
    'Бренд': r.card_brand || '',
    'Предмет': r.card_subject_name || '',
    'Артикул': r.card_vendor_code || '',
    'Заказов': r.orders_cnt,
    'Отмен': r.cancelled_cnt,
    'Цена в карт ср': r.avg_total_price,
    'Скидка ср %': r.avg_discount,
    'Общая сумма': r.sum_price_with_disc,
    'Цена со скид ср': r.avg_price_with_disc,
    'СПП ср %': r.avg_spp,
    'Сумма продаж': r.sum_finished,
    'Цена продажи ср': r.avg_finished,
    'Комиссия сумма': r.sum_commission,
    'Комиссия %': r.avg_commission_pct,
    'Эквайринг сумма': r.sum_acquiring,
    'Эквайринг %': r.avg_acquiring_pct,
    'Логистика сумма': r.sum_delivery,
    'Логистика ср': r.avg_delivery,
  }))
  await exportXlsx({
    rows: data,
    filename: `feed-aggregated_${filters.value.date_from}_${filters.value.date_to}.xlsx`,
    sheetName: 'Сводка',
    cols: [{wch:10},{wch:28},{wch:14},{wch:16},{wch:12},{wch:8},{wch:8},{wch:12},{wch:10},{wch:12},{wch:14},{wch:10},{wch:12},{wch:14},{wch:12},{wch:10},{wch:12},{wch:10},{wch:12},{wch:12}],
  })
}
onMounted(()=>{ loadFilterLists(); fetchData() })
</script>
