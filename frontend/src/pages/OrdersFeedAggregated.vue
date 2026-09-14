<template>
  <div class="container-xxl" style="padding:20px 15px; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
    <h1 style="font-size:20px; font-weight:700; margin-bottom:12px">Сводка по товарам (заказы)</h1>

    <!-- Фильтр: обязателен WbFilterBar.vue для однообразия (как OrdersFeed.vue) — row col-md-6 + col-md-3 сортировка как php feed-aggregated.php:23 -->
    <div class="row">
      <WbFilterBar v-model:nm-id="filters.nm_id" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" @apply="page=1; fetchData()" @reset="reset()" />
      <div class="col-md-3 mb-3">
        <div style="background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:15px; height:100%; display:flex; flex-direction:column; justify-content:center">
          <label class="form-label mb-1" style="font-size:12px;">Сортировка</label>
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
        <div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden">
          <div class="card-header text-white d-flex justify-content-between align-items-center" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700">
            <span>Сводка по товарам ({{ fmtDate(filters.date_from) }}<span v-if="filters.date_from!==filters.date_to"> — {{ fmtDate(filters.date_to) }}</span>)</span>
            <button class="btn btn-sm btn-light" style="font-size:12px; padding:4px 12px; border-radius:6px" @click="exportExcel" :disabled="!items.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
          </div>
          <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
          <div v-else style="overflow-x:auto" ref="wrapRef">
            <table ref="tbl" class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:12px; width:100%">
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
                  <td style="overflow:hidden">
                    <div style="display:flex; gap:10px; align-items:flex-start">
                      <img :src="photo(r)" style="width:50px; height:66px; object-fit:cover; border-radius:4px; flex-shrink:0" @error="(e:any)=>e.target.src='/images/no-photo.png'" />
                      <div style="min-width:0; overflow:hidden">
                        <div class="cart-item-title" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:210px; font-weight:bold; color:#2c3e50; font-size:13px" :title="r.card_title || ''">{{ r.card_title || '(нет карточки)' }}</div>
                        <div class="cart-item-details" style="color:#666; font-size:11px">{{ r.card_subject_name || '' }} • {{ r.card_brand || '' }}</div>
                        <div class="cart-item-details" style="color:#666; font-size:11px">{{ r.card_vendor_code || '' }}</div>
                        <div class="cart-item-details" style="font-size:11px"><a :href="'/wb/detail?DPFilterForm[nm_id]='+r.nm_id" target="_blank" style="text-decoration:none">WB: {{ r.nm_id }}</a></div>
                      </div>
                    </div>
                  </td>
                  <td style="text-align:right; font-weight:bold; overflow:hidden; text-overflow:ellipsis">{{ fmt0(r.orders_cnt) }}</td>
                  <td class="mobile-hide-col" style="text-align:right; overflow:hidden; text-overflow:ellipsis"><span :style="{color: r.cancelled_cnt>0 ? '#c0392b' : ''}">{{ r.cancelled_cnt ?? 0 }}</span></td>
                  <td class="mobile-hide-col" style="text-align:right; overflow:hidden; text-overflow:ellipsis">{{ fmtVal(r.avg_total_price) }}</td>
                  <td class="mobile-hide-col" style="text-align:right; overflow:hidden; text-overflow:ellipsis">{{ fmtVal(r.avg_discount,1) }}</td>
                  <td style="text-align:right; font-weight:bold; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">{{ fmtVal(r.sum_price_with_disc) }}<span v-if="r.sum_price_with_disc!=null"> ₽</span></td>
                  <td class="mobile-hide-col" style="text-align:right; overflow:hidden; text-overflow:ellipsis">{{ fmtVal(r.avg_price_with_disc) }}</td>
                  <td class="mobile-hide-col" style="text-align:right; overflow:hidden; text-overflow:ellipsis">{{ r.avg_spp!=null ? fmt1(r.avg_spp)+'%' : '—' }}</td>
                  <td style="text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">{{ r.sum_finished!=null ? fmt2(r.sum_finished)+' ₽' : '—' }}</td>
                  <td style="text-align:right; overflow:hidden; text-overflow:ellipsis">{{ fmtVal(r.avg_finished) }}</td>
                  <td class="mobile-hide-col" style="text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">
                    <template v-if="r.sum_commission!=null || r.avg_commission_pct!=null">
                      <i style="color:#888;">{{ r.sum_commission!=null ? fmt2(r.sum_commission)+' ₽' : '—' }}</i><br><span style="font-size:11px; color:#aaa;"><i>{{ r.avg_commission_pct!=null ? fmt1(r.avg_commission_pct)+'%' : '' }}</i></span>
                    </template>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="mobile-hide-col" style="text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">
                    <template v-if="r.sum_acquiring!=null || r.avg_acquiring_pct!=null">
                      <i style="color:#888;">{{ r.sum_acquiring!=null ? fmt2(r.sum_acquiring)+' ₽' : '—' }}</i><br><span style="font-size:11px; color:#aaa;"><i>{{ r.avg_acquiring_pct!=null ? fmt1(r.avg_acquiring_pct)+'%' : '' }}</i></span>
                    </template>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td style="text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">
                    <i v-if="r.sum_delivery!=null" style="color:#888;">{{ fmt2(r.sum_delivery) }} ₽</i>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="mobile-hide-col" style="text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">
                    <i v-if="r.avg_delivery!=null" style="color:#888;">{{ fmt2(r.avg_delivery) }} ₽</i>
                    <span v-else class="text-muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div style="display:flex; gap:8px; justify-content:center; margin:12px 0">
          <button class="btn btn-outline-secondary btn-sm" :disabled="page<=1" @click="page--; fetchData()">Назад</button>
          <span style="align-self:center; font-size:12px">Стр {{ page }} / {{ totalPages }} ({{ total }})</span>
          <button class="btn btn-outline-secondary btn-sm" :disabled="page>=totalPages" @click="page++; fetchData()">Вперед</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
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
  const r = await fetch(`/api/orders/feed-aggregated?${q}`)
  const data = await r.json()
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
<style>
.grid_orderfeed_summary {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin: 16px 0 24px;
}
.grid_orderfeed_summary .summary-card {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 16px 22px;
    min-width: 160px;
    flex: 1 1 160px;
    transition: box-shadow .15s ease, border-color .15s ease;
}
.grid_orderfeed_summary .summary-card:hover {
    border-color: #d1d5db;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}
.grid_orderfeed_summary .summary-label {
    font-size: 12px;
    color: #8a8f98;
    margin-bottom: 8px;
}
.grid_orderfeed_summary .summary-value {
    font-size: 24px;
    font-weight: 700;
    color: #1f2937;
    white-space: nowrap;
}
.grid_orderfeed_summary .summary-split {
    display: flex;
    gap: 16px;
    margin-top: 4px;
}
.grid_orderfeed_summary .summary-split-item {
    font-size: 20px;
    color: #1f2937;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.grid_orderfeed_summary .mini-badge {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 8px;
    letter-spacing: .02em;
    margin-top: 4px;
}
.grid_orderfeed_summary .mini-badge.fbs { background: #fef3c7; color: #d97706; }
.grid_orderfeed_summary .mini-badge.fbo { background: #ffedd5; color: #ea580c; }
@media (max-width: 767px) {
    .grid_orderfeed_summary .summary-card {
        flex: 1 1 45%;
        min-width: 0;
    }
}
/* 1в1 из feed.php:517 — ленты 10+ колонок резина */
.grid_orderfeed .cart-item-title { font-weight: bold; color: #2c3e50; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 210px; }
.grid_orderfeed .cart-item-details { color: #666; font-size: 11px; }
.grid_orderfeed td:not(:first-child) { font-size: 12px !important; vertical-align: middle; }
.grid_orderfeed th { white-space: normal !important; word-break: break-word; font-weight: 500 !important; color: #444; text-align: center; vertical-align: middle; }
.grid_orderfeed th:not(:first-child) { font-size: 11px !important; }
.grid_orderfeed .form-select { padding: 3px; font-size: 12px; width: 92%; margin: 0 auto; }
@media (max-width: 767px) {
    .grid_orderfeed .mobile-hide-col { display: none !important; }
}
.col-resizer:hover{ background:#4A3A8C; opacity:0.2 }
</style>
