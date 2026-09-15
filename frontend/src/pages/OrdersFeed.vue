<template>
  <div class="container-xxl page-orders-feed">
    <h1 class="page-title">Лента заказов</h1>
    <div class="row">
      <div class="col-md-6"><WbFilterBar v-model:nm-id="filters.nm_id" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" @apply="page=1; fetchFeed()" @reset="reset()" /></div>
      <div class="col-md-6"><!-- слот для доп. фильтров страницы --></div>
    </div>

    <div v-if="summary" class="page-orders-feed__summary">
      <div class="page-orders-feed__card"><div class="page-orders-feed__card-label">Количество заказов</div><div class="page-orders-feed__card-value">{{ summary.count }}</div></div>
      <div class="page-orders-feed__card"><div class="page-orders-feed__card-label">Из них</div><div class="page-orders-feed__card-split"><span class="page-orders-feed__split-item"><b>{{ summary.fbs_count }}</b><span class="page-orders-feed__badge page-orders-feed__badge--fbs">FBS</span></span><span class="page-orders-feed__split-item"><b>{{ summary.fbo_count }}</b><span class="page-orders-feed__badge page-orders-feed__badge--fbo">FBO</span></span></div></div>
      <div class="page-orders-feed__card"><div class="page-orders-feed__card-label">Сумма</div><div class="page-orders-feed__card-value">{{ fmt2(summary.sum) }} ₽</div></div>
      <div class="page-orders-feed__card"><div class="page-orders-feed__card-label">СПП (среднее)</div><div class="page-orders-feed__card-value">{{ summary.avg_spp.toFixed(1) }}%</div></div>
    </div>

    <div class="card grid_orderfeed page-orders-feed__grid">
      <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
        <span>Заказы ({{ fmtDate(filters.date_from) }}<span v-if="filters.date_from!==filters.date_to"> — {{ fmtDate(filters.date_to) }}</span>)</span>
        <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!items.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
      </div>
      <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
      <div v-else class="wb-table-wrap page-orders-feed__table-wrap" ref="wrapRef">
        <table ref="tbl" class="table table-bordered table-striped table-hover kv-grid-table mb-0 page-orders-feed__table">
          <thead>
            <tr>
              <th style="width:280px; text-align:center">Заказ</th>
              <th style="text-align:center">Дата заказа</th>
              <th style="text-align:center">Обновлен</th>
              <th style="width:100px; text-align:center">Статус<br><select v-model="filters.status" class="form-select" @change="page=1; fetchFeed()"><option value="">Все</option><option v-for="s in statuses" :key="s" :value="s">{{ s }}</option></select></th>
              <th style="width:100px; text-align:center">Откуда<br><select v-model="filters.warehouse_name" class="form-select" @change="page=1; fetchFeed()"><option value="">Все</option><option v-for="w in warehouses" :key="w" :value="w">{{ w }}</option></select></th>
              <th style="width:100px; text-align:center">Куда<br><select v-model="filters.region_name" class="form-select" @change="page=1; fetchFeed()"><option value="">Все</option><option v-for="r in regions" :key="r" :value="r">{{ r }}</option></select></th>
              <th style="width:50px; text-align:center">Цена в кар-ке</th>
              <th style="text-align:center">Скидка, %</th>
              <th style="width:50px; text-align:center">Цена со скидкой</th>
              <th style="text-align:center">СПП</th>
              <th style="width:50px; text-align:center">Цена продажи</th>
              <th style="text-align:center">Комиссия</th>
              <th style="text-align:center">Эквайринг</th>
              <th style="text-align:center">Кешбэк</th>
              <th style="text-align:center">Логистика</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in items" :key="r.id">
              <td style="width:280px; overflow:hidden">
                <div class="page-orders-feed__order">
                  <img :src="photo(r)" class="page-orders-feed__photo" @error="(e:any)=>e.target.src='/images/no-photo.png'" />
                  <div class="page-orders-feed__order-text">
                    <div class="cart-item-title" :title="r.card_title || '(нет карточки)'">{{ r.card_title || '(нет карточки)' }}</div>
                    <div class="cart-item-details d-flex align-items-center"><a :href="'/wb-order/view?id='+r.id" target="_blank" style="text-decoration:none; margin-right:4px"><i class="bi bi-eye-fill lh-1"></i></a>{{ r.card_subject_name }} • {{ r.card_brand }}</div>
                    <div class="cart-item-details" :title="r.card_vendor_code">{{ r.card_vendor_code }}</div>
                    <div class="cart-item-details"><a :href="'/wb/detail?DPFilterForm[nm_id]='+r.nm_id" target="_blank" style="text-decoration:none">WB: {{ r.nm_id }}</a></div>
                  </div>
                </div>
              </td>
              <td><div class="page-orders-feed__date-main">{{ fmtDate(r.date) }}</div><div class="page-orders-feed__date-sub">{{ fmtTime(r.date) }}</div></td>
              <td><div class="page-orders-feed__date-main">{{ fmtDate(r.fbs_status_changed_at || r.last_change_date) }}</div><div class="page-orders-feed__date-sub">{{ fmtTime(r.fbs_status_changed_at || r.last_change_date) }}</div></td>
              <td style="width:100px; text-align:center"><span :class="'status-badge '+statusCls(r)">{{ statusLabel(r) }}</span></td>
              <td style="width:100px;"><div class="page-orders-feed__place-main">{{ r.warehouse_name || '—' }}</div><div class="page-orders-feed__place-sub">{{ r.warehouse_type }}</div></td>
              <td style="width:100px;"><div class="page-orders-feed__place-main">{{ r.region_name || '—' }}</div><div class="page-orders-feed__place-sub">{{ r.destination_city || '' }}</div></td>
              <td style="text-align:right; width:50px;">{{ r.total_price ? fmt2(r.total_price) : '—' }}</td>
              <td style="text-align:right">{{ r.discount_percent ?? '—' }}</td>
              <td style="text-align:right; width:50px; font-weight:bold;">{{ r.price_with_disc }}</td>
              <td style="text-align:right">{{ r.spp }}</td>
              <td style="text-align:right; width:50px;">{{ r.finished_price ?? '—' }}</td>
              <td style="text-align:right; white-space:nowrap">{{ r.commission_fee ?? '—' }}</td>
              <td style="text-align:right; white-space:nowrap">{{ r.acquiring_fee ?? '—' }}</td>
              <td style="text-align:right">{{ r.cashback_amount ?? '—' }}</td>
              <td style="text-align:right; white-space:nowrap">{{ r.delivery_rub ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="page-orders-feed__pager">
      <button class="btn btn-outline-secondary btn-sm" :disabled="page<=1" @click="page--; fetchFeed()">Назад</button>
      <span class="page-orders-feed__pager-label">Стр {{ page }} / {{ Math.ceil(total/50) }} ({{ total }})</span>
      <button class="btn btn-outline-secondary btn-sm" :disabled="page>=Math.ceil(total/50)" @click="page++; fetchFeed()">Вперед</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-orders-feed.css'
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import WbFilterBar from '../components/common/WbFilterBar.vue'
const route = useRoute()
const router = useRouter()
const filters = ref({nm_id:'', date_from: new Date().toISOString().slice(0,10), date_to: new Date().toISOString().slice(0,10), status:'', warehouse_name:'', region_name:''})
function initFromQuery(){
  const q: any = route.query
  const pick = (...keys: string[]) => { for(const k of keys) if(q[k]) return String(q[k]); return '' }
  const df = pick('date_from','DPFilterForm[date_from]')
  const dt = pick('date_to','DPFilterForm[date_to]')
  const nm = pick('nm_id','DPFilterForm[nm_id]')
  if(df) filters.value.date_from = df
  if(dt) filters.value.date_to = dt
  if(nm) filters.value.nm_id = nm
  if(q.status) filters.value.status = String(q.status)
  if(q.warehouse_name) filters.value.warehouse_name = String(q.warehouse_name)
  if(q.region_name) filters.value.region_name = String(q.region_name)
  if(q.page) page.value = parseInt(String(q.page))||1
}
const statuses = ['Новый','Сборка','В пути','На ПВЗ','Выкуплен','Отменён','Отмена клиентом','Брак']
const items = ref<any[]>([]), total = ref(0), page = ref(1), isLoading = ref(false), summary = ref({count:0,fbs_count:0,fbo_count:0,sum:0,avg_spp:0})
const warehouses = ref<string[]>([]), regions = ref<string[]>([])
const tbl = ref<HTMLTableElement|null>(null), wrapRef = ref<HTMLDivElement|null>(null)
const photo = (r:any)=>{ try{ let p=r.card_photos; if(typeof p==='string') p=JSON.parse(p); if(typeof p==='string') p=JSON.parse(p); if(Array.isArray(p)&&p[0]) return p[0]; }catch{} return '/images/no-photo.png' }
const fmtDate = (d:any)=> d ? new Date(d).toLocaleDateString('ru-RU') : '—'
const fmtTime = (d:any)=> d ? new Date(d).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}) : ''
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(v||0)
const statusLabel = (r:any)=>{
  const isFbs = r.warehouse_type==='Склад продавца'
  if(isFbs){
    if(!r.fbs_supply_id) return 'Новый'
    if(r.fbs_wb_status==='waiting' && r.fbs_supplier_status==='new') return 'Новый'
    if(r.fbs_wb_status==='waiting' && r.fbs_supplier_status==='confirm') return 'Сборка'
    if(r.fbs_wb_status==='waiting' && r.fbs_supplier_status==='complete') return 'В пути'
    if(r.fbs_wb_status==='sorted') return 'В пути'
    if(r.fbs_wb_status==='ready_for_pickup') return 'На ПВЗ'
    if(r.fbs_wb_status==='sold') return 'Выкуплен'
    if(r.fbs_wb_status==='canceled' || r.fbs_wb_status==='canceled_by_client') return 'Отменён'
  } else {
    if(r.is_cancel) return 'Отменён'
    if(r.sale_date) return 'Выкуплен'
    return 'В пути'
  }
  return r.fbs_wb_status || r.status || '—'
}
const statusCls = (r:any)=>{
  const l=statusLabel(r)
  if(['Новый'].includes(l)) return 'st-blue'
  if(['Сборка'].includes(l)) return 'st-blue'
  if(['В пути','На ПВЗ'].includes(l)) return 'st-lightgreen'
  if(['Выкуплен'].includes(l)) return 'st-green'
  if(['Отменён','Отмена клиентом'].includes(l)) return 'st-lightred'
  if(['Брак'].includes(l)) return 'st-darkred'
  return 'st-unknown'
}
const reset = ()=>{ filters.value.nm_id=''; filters.value.status=''; filters.value.warehouse_name=''; filters.value.region_name=''; filters.value.date_from=new Date().toISOString().slice(0,10); filters.value.date_to=new Date().toISOString().slice(0,10); page.value=1; fetchFeed() }
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
  // резина как в оригинале: table 100% auto, fit не форсирует fixed
  const fit = ()=>{
    if(!table) return
    table.style.width='100%'
    // не ставим fixed — оставляем auto для резины как в GridView responsive
    if(table.style.tableLayout==='fixed') return
  }
  window.addEventListener('resize', fit)
  fit()
}
const fetchFeed = async()=>{
  isLoading.value=true
  syncRoute()
  const q = new URLSearchParams({date_from: filters.value.date_from, date_to: filters.value.date_to, page: String(page.value)} as any)
  if(filters.value.nm_id) q.set('nm_id', filters.value.nm_id)
  if(filters.value.status) q.set('status', filters.value.status)
  if(filters.value.warehouse_name) q.set('warehouse_name', filters.value.warehouse_name)
  if(filters.value.region_name) q.set('region_name', filters.value.region_name)
  const { data } = await api.get(`/api/orders/feed?${q}`)
  items.value = data.items || []; total.value = data.total || 0; summary.value = data.summary || summary.value
  const optQ = new URLSearchParams({date_from: filters.value.date_from, date_to: filters.value.date_to} as any)
  if(filters.value.nm_id) optQ.set('nm_id', filters.value.nm_id)
  try{ const { data:od } = await api.get(`/api/orders/feed/options?${optQ}`); warehouses.value=od.warehouses||[]; regions.value=od.regions||[] }catch{}
  isLoading.value=false
  nextTick(enableResize)
}
const exportExcel = async()=>{
  if(!items.value.length) return
  const XLSX = await import('xlsx')
  const data = items.value.map((r:any)=> ({
    'Дата заказа': r.date, 'nmID': r.nm_id, 'Цена со скидкой': r.price_with_disc, 'СПП': r.spp,
    'Склад': r.warehouse_name, 'Регион': r.region_name, 'Статус': statusLabel(r),
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Лента')
  XLSX.writeFile(wb, `feed_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
}
let syncing = false
const syncRoute = ()=>{
  const q: any = {}
  if(filters.value.date_from) q.date_from = filters.value.date_from
  if(filters.value.date_to) q.date_to = filters.value.date_to
  if(filters.value.nm_id) q.nm_id = filters.value.nm_id
  if(filters.value.status) q.status = filters.value.status
  if(filters.value.warehouse_name) q.warehouse_name = filters.value.warehouse_name
  if(filters.value.region_name) q.region_name = filters.value.region_name
  if(page.value>1) q.page = String(page.value)
  syncing = true
  router.replace({ path:'/feed', query: q }).finally(()=> setTimeout(()=> syncing=false, 50))
}
onMounted(()=>{ initFromQuery(); fetchFeed() })
watch(items, ()=> nextTick(enableResize))
watch(()=> route.query, ()=>{
  if(syncing) return
  const q:any = route.query
  const cur:any = { date_from: filters.value.date_from, date_to: filters.value.date_to, nm_id: filters.value.nm_id||'', status: filters.value.status||'', warehouse_name: filters.value.warehouse_name||'', region_name: filters.value.region_name||'', page: page.value>1?String(page.value):'' }
  const changed = ['date_from','date_to','nm_id','status','warehouse_name','region_name','page'].some(k=> String(q[k]||'')!==String(cur[k]||''))
  if(changed){ initFromQuery(); fetchFeed() }
})
</script>
