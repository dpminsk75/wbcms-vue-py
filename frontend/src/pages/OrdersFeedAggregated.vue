<template>
  <div class="container-xxl page-orders-feed-aggregated">
    <h1 class="page-title">Сводка по товарам (заказы)</h1>

    <!-- Фильтр: обязателен WbFilterBar.vue для однообразия (как OrdersFeed.vue) — row col-md-6 + col-md-3 сортировка как php feed-aggregated.php:23 -->
    <div class="row">
      <WbFilterBar v-model:nm-id="filters.nm_id" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" @apply="page=1; fetchData()" @reset="reset()" />
      <div class="col-md-3 mb-3">
          <div class="page-orders-feed-aggregated__sort-card">
          <label class="form-label mb-1 page-orders-feed-aggregated__sort-label">Сортировка</label>
          <select v-model="filters.sort_by" class="form-control" @change="page=1; fetchData()">
            <option value="count">По количеству</option>
            <option value="sum">По сумме</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Сводка 4 карточки как feed.php:48 grid_orderfeed_summary -->
    <div v-if="summary" class="grid_orderfeed_summary">
      <div class="summary-card">
        <div class="summary-label">Количество заказов</div>
        <div class="summary-value">{{ fmt0(summary.count) }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">Из них</div>
        <div class="summary-split">
          <span class="summary-split-item">
            <b>{{ fmt0(summary.fbs_count) }}</b>
            <span class="mini-badge fbs">FBS</span>
          </span>
          <span class="summary-split-item">
            <b>{{ fmt0(summary.fbo_count) }}</b>
            <span class="mini-badge fbo">FBO</span>
          </span>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-label">Сумма</div>
        <div class="summary-value">{{ fmt2(summary.sum) }} ₽</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">СПП (среднее)</div>
        <div class="summary-value">{{ fmt1(summary.avg_spp) }}%</div>
      </div>
    </div>

    <!-- Воронка + график -->
    <div class="row mb-3" v-if="funnel">
      <div class="col-12">
        <OrderFunnel :funnel="funnel" :chart-data="chartData" />
      </div>
    </div>

    <!-- Таблица как feed-aggregated.php:300 grid_orderfeed -->
    <div class="row grid_orderfeed grid_wbstat grid_no_kv-panel-before">
      <div class="col-12">
        <div class="card wb-grid-card page-orders-feed-aggregated__grid">
          <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
            <span>Сводка по товарам ({{ fmtDate(filters.date_from) }}<span v-if="filters.date_from!==filters.date_to"> — {{ fmtDate(filters.date_to) }}</span>)</span>
            <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!items.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
          </div>
          <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
          <div v-else class="wb-table-wrap page-orders-feed-aggregated__table-wrap" ref="wrapRef">
            <table ref="tbl" class="table table-bordered table-striped table-hover kv-grid-table mb-0 page-orders-feed-aggregated__table">
              <thead>
                <tr>
                  <th style="width:280px; text-align:center">Товар</th>
                  <th style="width:55px; text-align:center">Заказов</th>
                  <th style="width:45px; text-align:center" class="mobile-hide-col">Отмен</th>
                  <th style="width:65px; text-align:center" class="mobile-hide-col">Цена в кар-ке (ср.)</th>
                  <th style="width:55px; text-align:center" class="mobile-hide-col">Скидка, % (ср.)</th>
                  <th style="width:85px; text-align:center">Общая сумма</th>
                  <th style="width:70px; text-align:center" class="mobile-hide-col">Цена со скидкой (ср.)</th>
                  <th style="width:45px; text-align:center" class="mobile-hide-col">СПП (ср.)</th>
                  <th style="width:75px; text-align:center">Сумма продаж</th>
                  <th style="width:65px; text-align:center">Цена продажи (ср.)</th>
                  <th style="width:70px; text-align:center" class="mobile-hide-col">Комиссия</th>
                  <th style="width:60px; text-align:center" class="mobile-hide-col">Эквайринг</th>
                  <th style="width:65px; text-align:center">Логистика (сумма)</th>
                  <th style="width:55px; text-align:center" class="mobile-hide-col">Логистика (ср.)</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="items.length===0"><td colspan="14" class="text-center text-muted">Нет данных</td></tr>
                <tr v-for="r in items" :key="r.nm_id">
                  <td class="page-orders-feed-aggregated__cell-product">
                    <div class="page-orders-feed-aggregated__order">
                      <img :src="photo(r)" class="page-orders-feed-aggregated__photo" @error="(e:any)=>e.target.src='/images/no-photo.png'" />
                      <div class="page-orders-feed-aggregated__order-text">
                        <div class="cart-item-title" :title="r.card_title || ''">{{ r.card_title || '(нет карточки)' }}</div>
                        <div class="cart-item-details">{{ r.card_subject_name || '' }} • {{ r.card_brand || '' }}</div>
                        <div class="cart-item-details">{{ r.card_vendor_code || '' }}</div>
                        <div class="cart-item-details"><a :href="'/wb/detail?DPFilterForm[nm_id]='+r.nm_id" target="_blank" class="page-orders-feed-aggregated__wb-link">WB: {{ r.nm_id }}</a></div>
                      </div>
                    </div>
                  </td>
                  <td class="page-orders-feed-aggregated__num--bold">{{ fmt0(r.orders_cnt) }}</td>
                  <td class="mobile-hide-col page-orders-feed-aggregated__num"><span :style="{color: r.cancelled_cnt>0 ? '#c0392b' : ''}">{{ r.cancelled_cnt ?? 0 }}</span></td>
                  <td class="mobile-hide-col page-orders-feed-aggregated__num">{{ fmtVal(r.avg_total_price) }}</td>
                  <td class="mobile-hide-col page-orders-feed-aggregated__num">{{ fmtVal(r.avg_discount,1) }}</td>
                  <td class="page-orders-feed-aggregated__num--bold page-orders-feed-aggregated__num--nowrap">{{ fmtVal(r.sum_price_with_disc) }}<span v-if="r.sum_price_with_disc!=null"> ₽</span></td>
                  <td class="mobile-hide-col page-orders-feed-aggregated__num">{{ fmtVal(r.avg_price_with_disc) }}</td>
                  <td class="mobile-hide-col page-orders-feed-aggregated__num">{{ r.avg_spp!=null ? fmt1(r.avg_spp)+'%' : '—' }}</td>
                  <td class="page-orders-feed-aggregated__num page-orders-feed-aggregated__num--nowrap">{{ r.sum_finished!=null ? fmt2(r.sum_finished)+' ₽' : '—' }}</td>
                  <td class="page-orders-feed-aggregated__num">{{ fmtVal(r.avg_finished) }}</td>
                  <td class="mobile-hide-col page-orders-feed-aggregated__num page-orders-feed-aggregated__num--nowrap">
                    <template v-if="r.sum_commission!=null || r.avg_commission_pct!=null">
                      <i class="page-orders-feed-aggregated__sub">{{ r.sum_commission!=null ? fmt2(r.sum_commission)+' ₽' : '—' }}</i><br><span class="page-orders-feed-aggregated__sub-note"><i>{{ r.avg_commission_pct!=null ? fmt1(r.avg_commission_pct)+'%' : '' }}</i></span>
                    </template>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="mobile-hide-col page-orders-feed-aggregated__num page-orders-feed-aggregated__num--nowrap">
                    <template v-if="r.sum_acquiring!=null || r.avg_acquiring_pct!=null">
                      <i class="page-orders-feed-aggregated__sub">{{ r.sum_acquiring!=null ? fmt2(r.sum_acquiring)+' ₽' : '—' }}</i><br><span class="page-orders-feed-aggregated__sub-note"><i>{{ r.avg_acquiring_pct!=null ? fmt1(r.avg_acquiring_pct)+'%' : '' }}</i></span>
                    </template>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="page-orders-feed-aggregated__num page-orders-feed-aggregated__num--nowrap">
                    <i v-if="r.sum_delivery!=null" class="page-orders-feed-aggregated__sub">{{ fmt2(r.sum_delivery) }} ₽</i>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="mobile-hide-col page-orders-feed-aggregated__num page-orders-feed-aggregated__num--nowrap">
                    <i v-if="r.avg_delivery!=null" class="page-orders-feed-aggregated__sub">{{ fmt2(r.avg_delivery) }} ₽</i>
                    <span v-else class="text-muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="page-orders-feed-aggregated__pager">
          <button class="btn btn-outline-secondary btn-sm" :disabled="page<=1" @click="page--; fetchData()">Назад</button>
          <span class="page-orders-feed-aggregated__pager-label">Стр {{ page }} / {{ totalPages }} ({{ total }})</span>
          <button class="btn btn-outline-secondary btn-sm" :disabled="page>=totalPages" @click="page++; fetchData()">Вперед</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-orders-feed-aggregated.css'
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { api } from '../api/client'
import OrderFunnel from '../components/dashboard/OrderFunnel.vue'
import WbFilterBar from '../components/common/WbFilterBar.vue'

const fmtDate = (d:any)=> d ? new Date(d).toLocaleDateString('ru-RU') : '—'
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt1 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:1, maximumFractionDigits:1}).format(Number(v)||0)
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const fmtVal = (v:any, dec=2)=>{
  if(v===null || v==='' || v===undefined) return '—'
  return new Intl.NumberFormat('ru-RU',{minimumFractionDigits:dec, maximumFractionDigits:dec}).format(Number(v))
}

const today = new Date()
const fourteenDaysAgo = new Date(Date.now() - 13*864e5).toISOString().slice(0,10) // 14 дней включительно как в php -6д → 7д, тут -13д → 14д = 2 недели
const filters = ref({ nm_id:'', date_from: fourteenDaysAgo, date_to: today.toISOString().slice(0,10), sort_by:'count' })
const items = ref<any[]>([]), total = ref(0), page = ref(1), isLoading = ref(false)
const summary = ref<any>({count:0,fbs_count:0,fbo_count:0,sum:0,avg_spp:0})
const funnel = ref<any>({total_cnt:0,total_sum:0,bought_cnt:0,bought_sum:0,bought_pct:0,delivery_cnt:0,delivery_sum:0,delivery_pct:0,cancel_cnt:0,cancel_sum:0,cancel_pct:0,returns_cnt:0,returns_sum:0,returns_pct:0,buyout_pct:0})
const chartData = ref<any[]>([])
const tbl = ref<HTMLTableElement|null>(null)
const totalPages = computed(()=> Math.max(1, Math.ceil(total.value/50)))

const photo = (r:any)=>{ try{ let p=r.card_photos; if(typeof p==='string') p=JSON.parse(p); if(typeof p==='string') p=JSON.parse(p); if(Array.isArray(p)&&p[0]) return p[0]; }catch{} return '/images/no-photo.png' }

const reset = ()=>{ filters.value.nm_id=''; filters.value.sort_by='count'; filters.value.date_from=fourteenDaysAgo; filters.value.date_to=today.toISOString().slice(0,10); page.value=1; fetchData() }

const enableResize = ()=>{
  const table = tbl.value; if(!table) return
  const ths = table.querySelectorAll('th') as NodeListOf<HTMLTableCellElement>
  ths.forEach(th=>{
    if(th.querySelector('.col-resizer')) return
    th.style.position='relative'
    const r=document.createElement('div')
    r.className='col-resizer'
    r.style.cssText='position:absolute; top:0; right:0; width:6px; height:100%; cursor:col-resize; user-select:none; z-index:1'
    th.appendChild(r)
    let sx=0, sw=0
    const onMove=(e:MouseEvent)=>{ const w=Math.max(40, sw + e.clientX - sx); th.style.width=w+'px'; th.style.minWidth=w+'px'; table.style.tableLayout='fixed'; table.style.width='100%' }
    const onUp=()=>{ document.removeEventListener('mousemove',onMove); document.removeEventListener('mouseup',onUp); document.body.style.cursor='' }
    r.addEventListener('mousedown',(e:MouseEvent)=>{ sx=e.clientX; sw=th.offsetWidth; document.body.style.cursor='col-resize'; document.addEventListener('mousemove',onMove); document.addEventListener('mouseup',onUp); e.preventDefault() })
  })
  // резина как в OrdersFeed.vue / feed.php:492+517 — table 100% auto, fit не форсирует fixed
  const fit = ()=>{
    if(!table) return
    table.style.width='100%'
    // не ставим fixed — оставляем auto для резины как в GridView responsive
    if(table.style.tableLayout==='fixed') return
  }
  window.addEventListener('resize', fit)
  fit()
}

const fetchData = async()=>{
  isLoading.value=true
  const q = new URLSearchParams({date_from: filters.value.date_from, date_to: filters.value.date_to, sort_by: filters.value.sort_by, page: String(page.value)} as any)
  if(filters.value.nm_id) q.set('nm_id', filters.value.nm_id)
  const { data } = await api.get(`/api/orders/feed-aggregated?${q}`)
  items.value = data.items || []; total.value = data.total || 0
  summary.value = data.summary || summary.value
  funnel.value = data.funnel || funnel.value
  chartData.value = data.chart || []
  isLoading.value=false
  nextTick(enableResize)
}
const exportExcel = async()=>{
  if(!items.value.length) return
  const XLSX = await import('xlsx')
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
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{wch:10},{wch:28},{wch:14},{wch:16},{wch:12},{wch:8},{wch:8},{wch:12},{wch:10},{wch:12},{wch:14},{wch:10},{wch:12},{wch:14},{wch:12},{wch:10},{wch:12},{wch:10},{wch:12},{wch:12}]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Сводка')
  XLSX.writeFile(wb, `feed-aggregated_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
}
onMounted(()=>{ fetchData() })
watch(items, ()=> nextTick(enableResize))
</script>
