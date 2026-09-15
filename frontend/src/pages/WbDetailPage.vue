<template>
  <div class="container-xxl wb-detail-report page-wb-detail">
    <div class="mb-2 page-wb-detail__crumbs"><a href="/" class="page-wb-detail__crumbs-link">Главная</a> <span class="mx-1">/</span> <a href="#" class="page-wb-detail__crumbs-link">Данные</a> <span class="mx-1">/</span> <span class="text-dark">О карточке</span></div>
    <div class="mb-3 page-wb-detail__head">
      <h1 class="mb-0 page-wb-detail__title">{{ card?.title || 'Карточка WB' }}</h1>
      <div v-if="filters.nm_id || card?.nmID" class="page-wb-detail__id-group">
        <span class="text-muted page-wb-detail__id-label">ID:</span>
        <span class="badge bg-dark page-wb-detail__id-badge">{{ card?.nmID || filters.nm_id }}</span>
        <button class="btn btn-sm btn-outline-secondary page-wb-detail__icon-btn" @click="copyId"><i class="bi bi-clipboard"></i></button>
        <a :href="'https://www.wildberries.ru/catalog/'+(card?.nmID||filters.nm_id)+'/detail.aspx'" target="_blank" class="btn btn-sm btn-outline-primary page-wb-detail__icon-btn"><i class="bi bi-eye"></i></a>
      </div>
    </div>

    <!-- ВСЕГДА виден фильтр, правая колонка — карточка или заглушка, стартуют на одном уровне -->
    <div class="row align-items-start">
      <div class="col-md-6">
        <WbFilterBar v-model:nm-id="filters.nm_id" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" @apply="onApply" @reset="onReset" />
        <template v-if="filters.nm_id">
          <AdvTable :nm-id="filters.nm_id" :date-from="filters.date_from" :date-to="filters.date_to" class="mt-3" />
          <StocksPanel :nm-id="filters.nm_id" class="mt-3" />
          <PaidStorageTable :nm-id="filters.nm_id" :date-from="filters.date_from" :date-to="filters.date_to" class="mt-3" />
        </template>
      </div>
      <div class="col-md-6">
        <div v-if="!filters.nm_id" class="alert alert-warning">Выберите карточку — укажите артикул WB (nmID) и нажмите Применить.</div>
        <div v-else-if="cardLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка карточки...</div>
        <div v-else-if="cardError" class="alert alert-danger">Карточка {{ filters.nm_id }} не найдена.</div>
        <div v-else-if="card" class="card page-wb-detail__product-card">
          <div class="card-header page-wb-detail__product-head">
            <span>Товар: {{ card.title }}</span>
            <span class="page-wb-detail__product-wb">WB: {{ card.nmID }}</span>
          </div>
          <div class="card-body">
            <div class="row mb-2">
              <div class="col-md-6 card_characteristics">
                <dl class="mb-0 page-wb-detail__facts">
                  <div class="dl_item"><dt class="card_characteristics__dt">Арт. WB:</dt><dd class="card_characteristics__dd"><a :href="'https://www.wildberries.ru/catalog/'+card.nmID+'/detail.aspx'" target="_blank"><b>{{ card.nmID }}</b></a></dd></div>
                  <div class="dl_item"><dt class="card_characteristics__dt">Арт.:</dt><dd class="card_characteristics__dd"><b>{{ card.vendorCode }}</b></dd></div>
                  <div class="dl_item"><dt class="card_characteristics__dt">Бренд:</dt><dd class="card_characteristics__dd"><b>{{ card.brand }}</b></dd></div>
                  <div class="dl_item"><dt class="card_characteristics__dt">Размер:</dt><dd class="card_characteristics__dd">{{ dimensions }}</dd></div>
                </dl>
                <div class="mt-2 d-flex gap-2">
                  <a :href="'/seo/index?status=new&q='+filters.nm_id" target="_blank" class="btn btn-sm btn-outline-primary page-wb-detail__card-actions"><i class="fas fa-robot me-1"></i> AI рек.</a>
                  <button class="btn btn-sm btn-outline-warning page-wb-detail__card-actions" data-bs-toggle="modal" data-bs-target="#seoTargetsModal"><i class="fas fa-bullseye me-1"></i> Целевые</button>
                </div>
              </div>
              <div class="col-md-6">
                <div class="panel_stats">
                  <div class="page-wb-detail__period">с <b>{{ filters.date_from }}</b> по <b>{{ dateTo14 }}</b></div>
                  <div class="orders_total">
                    <div class="ot-row"><span>Всего заказов <b>{{ fmt0(orderStats.alls) }}</b></span><span>На сумму <b>{{ fmt2(orderStats.sLO) }}</b></span></div>
                    <div class="ot-row"><span>Отказов <b>{{ fmt0(orderStats.cancel) }}</b></span><span>Процент выкупа <span :class="buyoutClass + ' fw-bold'">{{ buyoutPct }}%</span></span></div>
                    <div class="ot-row"><span>Выкупили <b>{{ fmt0(orderStats.bought) }}</b></span><span>На сумму <b>{{ fmt2(orderStats.sum) }}</b></span></div>
                    <div class="ot-row"><span>Не выкупили <b>{{ fmt0(notBought) }}</b></span><span>К оплате <b>{{ fmt2(orderStats.sFP) }}</b></span></div>
                  </div>
                </div>
              </div>
            </div>
            <div class="wb-card-gallery-scroll page-wb-detail__gallery mt-3">
              <div v-if="card.video" class="page-wb-detail__gallery-video">
                <video :src="card.video" controls :poster="photos[0]||''" class="page-wb-detail__gallery-video-el"></video>
              </div>
              <img v-for="(u,i) in photos" :key="i" :src="u" loading="lazy" class="page-wb-detail__gallery-photo" @error="(e:any)=>e.target.style.display='none'" />
              <div v-if="!photos.length && !card.video" class="text-muted page-wb-detail__gallery-empty">Нет фото</div>
            </div>
            <div class="row mt-3 expandable-container" :class="{'is-expanded': descExpanded}" :style="{maxHeight: descExpanded ? '20000px' : '450px', overflow:'hidden', position:'relative', transition:'max-height .5s'}">
              <div class="col-md-6">
                <div class="page-wb-detail__section-title">Характеристики</div>
                <div v-if="characteristics.length" class="card_characteristics">
                  <dl class="mb-0">
                    <div v-for="(c,i) in characteristics" :key="i" class="dl_item">
                      <dt class="card_characteristics__dt">{{ c.name || c.key }}</dt>
                      <dd class="card_characteristics__dd">{{ Array.isArray(c.value) ? c.value.join(', ') : c.value }}</dd>
                    </div>
                  </dl>
                </div>
                <div v-else class="text-muted page-wb-detail__empty">Нет характеристик</div>
              </div>
              <div class="col-md-6">
                <div class="page-wb-detail__section-title">Описание</div>
                <div v-if="card.description" class="card_description page-wb-detail__description">{{ card.description }}</div>
              </div>
            </div>
            <div v-if="(characteristics.length || card.description) && (String(card.description||'').length>300 || characteristics.length>8)" class="expand-btn-wrapper page-wb-detail__expand-btn">
              <button class="btn btn-outline-primary btn-sm page-wb-detail__more-btn" @click="descExpanded=!descExpanded">{{ descExpanded ? 'Свернуть' : 'Увидеть больше' }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template v-if="filters.nm_id && card">
      <OrderFunnel :nm-id="filters.nm_id" :date-from="filters.date_from" :date-to="filters.date_to" class="mt-3" />
      <DailyTables :nm-id="filters.nm_id" :date-from="filters.date_from" :date-to="filters.date_to" />
      <DetailCharts :nm-id="filters.nm_id" :date-from="filters.date_from" :date-to="filters.date_to" />
      <div class="mt-3">
        <WeeklyFinanceTable :rows="weeklyRows" :is-loading="weeklyLoading" title="Аналитика продаж по неделям" />
      </div>
      <div class="mt-3">
        <PhrasesMatrix :rows="phraseModels" :dates="phraseDates" :is-loading="phraseLoading" />
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-wb-detail.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import WbFilterBar from '../components/common/WbFilterBar.vue'
import WeeklyFinanceTable from '../components/common/WeeklyFinanceTable.vue'
import PhrasesMatrix from '../components/common/PhrasesMatrix.vue'
import StocksPanel from '../components/wb-detail/StocksPanel.vue'
import PaidStorageTable from '../components/wb-detail/PaidStorageTable.vue'
import AdvTable from '../components/wb-detail/AdvTable.vue'
import OrderFunnel from '../components/wb-detail/OrderFunnel.vue'
import DailyTables from '../components/wb-detail/DailyTables.vue'
import DetailCharts from '../components/wb-detail/DetailCharts.vue'

const route = useRoute()
const router = useRouter()

function mondayOfWeek(d: Date){
  const day=d.getDay(); const diff = day===0 ? -6 : 1-day
  const m=new Date(d); m.setDate(d.getDate()+diff); m.setHours(0,0,0,0); return m
}
function fmt(d:Date){ return d.toISOString().slice(0,10) }
const today=new Date()
const yesterday=new Date(today); yesterday.setDate(today.getDate()-1)
const ts70=new Date(today); ts70.setDate(today.getDate()-70)
const defFrom=fmt(mondayOfWeek(ts70))
const defTo=fmt(yesterday)

const filters = ref({ nm_id: '', date_from: defFrom, date_to: defTo })
const dateTo14 = computed(()=>{ const d=new Date(filters.value.date_to); d.setDate(d.getDate()-14); return fmt(d) })

function initFromQuery(){
  const q:any=route.query
  const pick=(...keys:string[])=>{ for(const k of keys) if(q[k]) return String(q[k]); return '' }
  const df=pick('date_from','DPFilterForm[date_from]')
  const dt=pick('date_to','DPFilterForm[date_to]')
  const nm=pick('nm_id','DPFilterForm[nm_id]','nmID')
  if(df) filters.value.date_from=df
  else if(!q.date_from && !q['DPFilterForm[date_from]']) filters.value.date_from=defFrom
  if(dt) filters.value.date_to=dt
  else if(!q.date_to && !q['DPFilterForm[date_to]']) filters.value.date_to=defTo
  if(nm) filters.value.nm_id=nm
}
let syncing=false
const syncRoute=()=>{
  const q:any={}
  if(filters.value.nm_id) q.nm_id=filters.value.nm_id
  if(filters.value.date_from) q.date_from=filters.value.date_from
  if(filters.value.date_to) q.date_to=filters.value.date_to
  syncing=true
  router.replace({ path:'/wb/detail', query:q }).finally(()=> setTimeout(()=> syncing=false,50))
}
const descExpanded=ref(false)
const card=ref<any>(null)
const cardLoading=ref(false)
const cardError=ref(false)
const photos=computed(()=>{ const p=card.value?.photos; return Array.isArray(p)? p.filter(Boolean):[] })
const characteristics=computed(()=>{
  const c=card.value?.characteristics
  const arr = Array.isArray(c) ? [...c] : (c && typeof c==='object' ? Object.entries(c).map(([k,v]:any)=>({name:k, value:v})) : [])
  // как WbCard.php:192 ArrayHelper::multisort($chars,'id',SORT_ASC)
  arr.sort((a:any,b:any)=> (Number(a?.id ?? 0) - Number(b?.id ?? 0)))
  return arr
})
const dimensions=computed(()=>{
  const d=card.value?.dimensions; if(!d) return ''
  const len=d.length??'', wid=d.width??'', hei=d.height??'', w=d.weightBrutto??''
  if(!len && !wid && !hei) return ''
  return `${len} × ${wid} × ${hei} см, вес: ${w} кг`
})
const updateDetailTitle = ()=>{
  if(card.value?.title) document.title = `Карточка: ${card.value.title} — wbcms`
  else if(filters.value.nm_id) document.title = `Карточка: ${filters.value.nm_id} — wbcms`
  else document.title = 'Карточка: Выберите артикул — wbcms'
}
const fetchCard=async()=>{
  if(!filters.value.nm_id) { card.value=null; updateDetailTitle(); return }
  cardLoading.value=true; cardError.value=false
  try{ const { data:d } = await api.get(`/api/wb/card/${filters.value.nm_id}`); card.value=d; updateDetailTitle() }catch{ cardError.value=true; card.value=null; updateDetailTitle() } finally{ cardLoading.value=false }
}
watch(card, updateDetailTitle)
watch(()=>filters.value.nm_id, updateDetailTitle)
const weeklyRows=ref<any[]>([])
const weeklyLoading=ref(false)
const orderStats=ref<any>({alls:0,sLO:0,cancel:0,notb:0,bought:0,sum:0,sFP:0})
// как detail.php:316-318
const notBought=computed(()=> orderStats.value.cancel > 0 ? orderStats.value.notb - orderStats.value.cancel : 0)
const buyoutPct=computed(()=> {
  const c = Number(orderStats.value.cancel)||0, a = Number(orderStats.value.alls)||0
  return c > 0 && a > 0 ? (100 - Math.round(c/a*100*10)/10) : 0
})
const buyoutClass=computed(()=> buyoutPct.value > 90 ? 'text-success' : buyoutPct.value > 80 ? 'text-warning' : 'text-danger')
const fmt0=(v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2=(v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const phraseModels=ref<any[]>([])
const phraseDates=ref<string[]>([])
const phraseLoading=ref(false)
const fetchWeekly=async()=>{
  if(!filters.value.nm_id) return
  weeklyLoading.value=true
  try{ const { data:d } = await api.get(`/api/wb/detail/weekly?nm_id=${filters.value.nm_id}&date_from=${filters.value.date_from}&date_to=${filters.value.date_to}`); weeklyRows.value=d }catch{ weeklyRows.value=[] } finally{ weeklyLoading.value=false }
}
const fetchPhrases=async()=>{
  if(!filters.value.nm_id) return
  phraseLoading.value=true
  try{
    const { data:j } = await api.get(`/api/wb/detail/phrases?nm_id=${filters.value.nm_id}&date_from=${filters.value.date_from}&date_to=${filters.value.date_to}`)
    phraseModels.value=j.models||[]; phraseDates.value=j.dates||[]
  }catch{ phraseModels.value=[]; phraseDates.value=[] } finally{ phraseLoading.value=false }
}
const fetchOrderStats=async()=>{
  if(!filters.value.nm_id) return
  try{
    const { data:d } = await api.get(`/api/wb/detail/order-stats?nm_id=${filters.value.nm_id}&date_from=${filters.value.date_from}&date_to=${filters.value.date_to}`)
    orderStats.value=d
  }catch{ orderStats.value={alls:0,sLO:0,cancel:0,notb:0,bought:0,sum:0,sFP:0} }
}
const fetchAll=()=>{ fetchCard(); fetchWeekly(); fetchPhrases(); fetchOrderStats() }
const onApply=()=>{ syncRoute(); fetchAll() }
const onReset=()=>{ filters.value.nm_id=''; filters.value.date_from=defFrom; filters.value.date_to=defTo; syncRoute(); card.value=null; weeklyRows.value=[]; phraseModels.value=[]; orderStats.value={alls:0,sLO:0,cancel:0,notb:0,bought:0,sum:0,sFP:0} }
const copyId=()=>{ if(card.value?.nmID) navigator.clipboard.writeText(String(card.value.nmID)) }
onMounted(()=>{ initFromQuery(); if(filters.value.nm_id) fetchAll() })
watch(()=>route.query, ()=>{
  if(syncing) return
  const q:any=route.query
  const cur={ nm_id:filters.value.nm_id||'', date_from:filters.value.date_from, date_to:filters.value.date_to }
  const changed=['nm_id','date_from','date_to'].some(k=> String(q[k]||'')!==String((cur as any)[k]||''))
  if(changed){ initFromQuery(); if(filters.value.nm_id) fetchAll() }
})
</script>
<style scoped>
.card_characteristics dl{font-size:11px; align-items:start}
.card_characteristics .dl_item{display:grid; grid-template-columns:1fr 2fr; gap:5px; border-bottom:1px dashed #999}
.card_characteristics__dt{grid-column:1; font-weight:bold; color:#555}
.card_characteristics__dd{grid-column:2; padding-bottom:2px; margin:0}
/* синий бокс статистики как .panel_stats/.orders_total в detail.php:1115-1132 */
.panel_stats{background:#aed7ff; padding:5px 10px; border:1px solid rgb(74 128 180); border-radius:10px; font-size:12px; color:#555}
.orders_total{display:flex; flex-direction:column}
.ot-row{display:flex; flex-direction:row; flex-wrap:wrap; justify-content:space-between; gap:8px; width:100%}
.ot-row span{white-space:nowrap}
.ot-row span:last-child{text-align:right}
.wb-card-gallery-scroll::-webkit-scrollbar{height:6px}
.wb-card-gallery-scroll::-webkit-scrollbar-thumb{background:#ddd; border-radius:3px}
.wb-detail-report .card-header{font-size:13px}
.expandable-container:not(.is-expanded)::after{content:""; position:absolute; bottom:0; left:0; width:100%; height:50px; background:linear-gradient(transparent, white); pointer-events:none}
</style>
