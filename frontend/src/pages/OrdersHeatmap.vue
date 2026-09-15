<template>
  <div class="container-xxl page-orders-heatmap">
    <div v-if="card">
      <div class="page-orders-heatmap__card-head">
        <img v-if="cardPhoto" :src="cardPhoto" class="page-orders-heatmap__card-photo" @error="(e:any)=>e.target.src='/images/no-photo.png'" />
        <div>
          <h1 class="page-orders-heatmap__card-title">{{ card.title }}</h1>
          <div class="page-orders-heatmap__card-sub">WB: {{ card.nmID }} · {{ card.vendorCode }} · {{ card.brand }}</div>
        </div>
      </div>
    </div>
    <template v-else>
      <h1 class="page-title">Тепловая карта заказов 7×24</h1>
      <p class="text-muted page-orders-heatmap__lede">Время добавления заказа по дням и часам — для расписания рекламы. Источник: <code>wb_order.date</code>.</p>
    </template>

    <!-- Фильтр: WbFilterBar обязательно -->
    <div class="row">
      <WbFilterBar v-model:nm-id="filters.nm_id" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" @apply="fetchData()" @reset="reset()" />
    </div>

    <div class="heatmap-top">
      <div class="heatmap-summary">
        Период: <b>{{ data?.dateFrom }} — {{ data?.dateTo }}</b> ·
        Заказов: <b>{{ fmt0(data?.totalCnt) }}</b> ·
        Сумма: <b>{{ fmt0(data?.totalSum) }} ₽</b> ·
        Макс в ячейке: <b>{{ data?.maxCnt }}</b>
      </div>
    </div>

    <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
    <template v-else-if="data">
      <div class="row">
        <div class="col-lg-9">
          <div class="card page-orders-heatmap__matrix-card">
            <div class="card-header d-flex justify-content-between align-items-center page-orders-heatmap__matrix-head">
              <span>Теплокарта 7×24 — заказы</span>
              <span class="text-muted page-orders-heatmap__matrix-hint">Клик по ячейке → детали справа</span>
            </div>
            <div class="table-responsive page-orders-heatmap__matrix-wrap">
              <table class="heatmap-table page-orders-heatmap__matrix-table">
                <thead>
                  <tr>
                    <th class="page-orders-heatmap__matrix-corner">День / Час</th>
                    <th v-for="h in 24" :key="h" class="page-orders-heatmap__matrix-hour">{{ String(h-1).padStart(2,'0') }}:00</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(day, wd) in days" :key="wd">
                    <th class="page-orders-heatmap__matrix-day">{{ day }}</th>
                    <td v-for="hr in 24" :key="hr" class="heatmap-cell" :class="{'is-active': activeWd===wd && activeHr===(hr-1)}"
                      :style="cellStyle(wd, hr-1)" @click="selectCell(wd, hr-1)">
                      {{ cellCnt(wd, hr-1) || '0' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="page-orders-heatmap__legend">
              <span>0</span><div class="page-orders-heatmap__legend-bar"></div><span>{{ data.maxCnt }}</span><span class="page-orders-heatmap__legend-gap">заказов в ячейке</span>
            </div>
          </div>
        </div>
        <div class="col-lg-3">
          <div id="heatmap-detail" class="card page-orders-heatmap__detail-card">
            <div class="card-header page-orders-heatmap__detail-head">Детали часа</div>
            <div class="card-body page-orders-heatmap__detail-body">
              <div class="text-muted page-orders-heatmap__detail-hint">Кликните по ячейке, чтобы закрепить и разобрать причины.</div>
              <div class="page-orders-heatmap__detail-title">{{ detailTitle }}</div>
              <div class="row g-2 page-orders-heatmap__detail-stats">
                <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Заказы</div><div class="page-orders-heatmap__stat-value">{{ detail.cnt }}</div></div></div>
                <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Сумма</div><div class="page-orders-heatmap__stat-value--sm">{{ detail.sumStr }}</div></div></div>
                <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Средний чек</div><div>{{ detail.avgStr }}</div></div></div>
                <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Доля периода</div><div>{{ detail.shareStr }}</div></div></div>
              </div>
              <div class="text-muted page-orders-heatmap__detail-foot">Выберите ячейку — подсветка зафиксируется.</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="data.recommend" class="page-orders-heatmap__reco">
        <h5 class="page-orders-heatmap__reco-title">Рекомендации лучших окон</h5>
        <p class="text-muted page-orders-heatmap__reco-lede">Топ-3 временных окна по объёму, чеку и надёжности — для планирования рекламы. Окно 2 часа, агрегация по всем 7 дням периода.</p>
        <div class="row g-3">
          <div v-for="key in (['byVolume','byAvg','byReli'] as const)" :key="key" class="col-lg-4">
            <div class="card h-100 page-orders-heatmap__reco-card">
              <div class="card-body">
                <div class="d-flex justify-content-between align-items-center page-orders-heatmap__reco-head">
                  <div class="page-orders-heatmap__reco-name">{{ cardsMeta[key].icon }} {{ cardsMeta[key].title }}</div>
                  <span class="badge page-orders-heatmap__reco-badge" :style="{background: confidenceColor(data.recommend[key].best)}">Уверенность: {{ confidence(data.recommend[key].best) }}</span>
                </div>
                <div class="text-muted page-orders-heatmap__reco-sub">{{ cardsMeta[key].sub }}</div>
                <div class="border rounded p-2 mb-2 page-orders-heatmap__reco-best">
                  <div class="page-orders-heatmap__reco-best-title">{{ data.recommend[key].best?.label }}</div>
                  <div class="text-muted page-orders-heatmap__reco-best-sub">Окно даёт {{ fmt2(data.recommend[key].best?.share) }}% всех заказов · спрос {{ demand(data.recommend[key].best) }}</div>
                </div>
                <div class="row g-2 page-orders-heatmap__reco-list">
                  <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Заказов</div><div class="page-orders-heatmap__stat-value--sm">{{ data.recommend[key].best?.cnt }}</div><div class="text-muted">Доля {{ fmt2(data.recommend[key].best?.share) }}%</div></div></div>
                  <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Средний чек</div><div class="page-orders-heatmap__stat-value--sm">{{ fmt0(data.recommend[key].best?.avg) }} ₽</div><div class="text-muted">Отмен {{ fmt1(data.recommend[key].best?.cancel_rate) }}%</div></div></div>
                </div>
                <div class="page-orders-heatmap__reco-list-title">Топ-3 окна</div>
                <div v-for="(w,i) in data.recommend[key].top3" :key="w.label" class="border rounded p-2 mb-1 page-orders-heatmap__reco-item" :style="{background: i===0 ? '#f0f7ff' : '#fff'}">
                  <div class="page-orders-heatmap__reco-item-title">{{ i+1 }}. {{ w.label }}: {{ w.cnt }} зак. · {{ fmt0(w.avg) }} ₽ · отмен {{ fmt1(w.cancel_rate) }}%</div>
                  <div class="text-muted">Доля {{ fmt2(w.share) }}% · {{ key==='byVolume' ? 'объём' : key==='byAvg' ? 'чек' : 'надёжность' }} за 7 дней</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-orders-heatmap.css'
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client'
import WbFilterBar from '../components/common/WbFilterBar.vue'

const days = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
const dayFull = ['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье']

const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt1 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:1, maximumFractionDigits:1}).format(Number(v)||0)
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)

const filters = ref({ nm_id:'', date_from: '', date_to: '' })
const data = ref<any>(null)
const isLoading = ref(false)
const activeWd = ref<number|null>(null)
const activeHr = ref<number|null>(null)

// init dates как в php getDPWidget::getParams(14) → 14д = today-14 .. yesterday
const initDates = ()=>{
  const to = new Date(Date.now() - 864e5).toISOString().slice(0,10)
  const from = new Date(Date.now() - 14*864e5).toISOString().slice(0,10)
  filters.value.date_from = from
  filters.value.date_to = to
}
initDates()

const card = computed(()=> data.value?.card || null)
const cardPhoto = computed(()=>{
  const p = card.value?.photos
  if(!p) return ''
  try{ let v=p; if(typeof v==='string') v=JSON.parse(v); if(typeof v==='string') v=JSON.parse(v); if(Array.isArray(v)&&v[0]) return v[0]}catch{}
  return ''
})

const cardsMeta:any = {
  byVolume: {title:'Лучшее окно по объёму', sub:'Окно даёт максимум заказов', icon:'📊'},
  byAvg: {title:'Лучшее окно по чеку', sub:'Максимальный средний чек', icon:'%'},
  byReli: {title:'Лучшее окно по надёжности', sub:'Минимум отмен', icon:'🛡️'},
}
const confidence = (best:any)=>{
  if(!best) return '—'
  if(best.cnt >= 30) return 'высокая'
  if(best.cnt >= 10) return 'средняя'
  return 'низкая'
}
const confidenceColor = (best:any)=>{
  const c = confidence(best)
  return c==='высокая' ? '#16a34a' : c==='средняя' ? '#2f6bff' : '#111827'
}
const demand = (best:any)=>{
  if(!best) return ''
  if(best.cnt>=20) return 'высокий'
  if(best.cnt>=10) return 'средний'
  return 'низкий'
}

const cellCnt = (wd:number, hr:number)=> data.value?.matrix?.[wd]?.[hr]?.cnt ?? 0
const cellSum = (wd:number, hr:number)=> data.value?.matrix?.[wd]?.[hr]?.sum ?? 0
const cellStyle = (wd:number, hr:number)=>{
  const cnt = cellCnt(wd, hr)
  const max = data.value?.maxCnt || 0
  const alpha = max > 0 ? (cnt / max) : 0
  let bg = '#ffffff', color = '#bbb'
  if(cnt>0){
    bg = `rgba(47,107,255,${(0.08 + alpha*0.92).toFixed(2)})`
    color = alpha > 0.5 ? '#fff' : '#1f2937'
  }
  return `padding:6px 2px; text-align:center; border:1px solid #e5e7eb; background:${bg}; color:${color}; cursor:pointer; font-weight:${cnt>0?'600':'400'};`
}

const selectCell = (wd:number, hr:number)=>{
  activeWd.value = wd
  activeHr.value = hr
}
const detailTitle = computed(()=>{
  if(activeWd.value===null || activeHr.value===null) return '—'
  const wd = dayFull[activeWd.value]
  const hr = activeHr.value
  const hr2 = (hr+1)%24
  return `${wd} ${String(hr).padStart(2,'0')}:00–${String(hr2).padStart(2,'0')}:00`
})
const detail = computed(()=>{
  if(activeWd.value===null || activeHr.value===null || !data.value) return {cnt:'—', sumStr:'—', avgStr:'—', shareStr:'—'}
  const cnt = cellCnt(activeWd.value, activeHr.value)
  const sum = cellSum(activeWd.value, activeHr.value)
  const total = data.value.totalCnt || 0
  return {
    cnt: String(cnt),
    sumStr: fmt0(sum) + ' ₽',
    avgStr: cnt>0 ? fmt0(sum/cnt) + ' ₽' : '—',
    shareStr: total>0 ? fmt2(cnt/total*100) + ' %' : '—',
  }
})

const reset = ()=>{
  filters.value.nm_id = ''
  initDates()
  fetchData()
}
const fetchData = async()=>{
  isLoading.value = true
  const q = new URLSearchParams({date_from: filters.value.date_from, date_to: filters.value.date_to} as any)
  if(filters.value.nm_id) q.set('nm_id', filters.value.nm_id)
  const { data:d } = await api.get(`/api/orders/heatmap?${q}`)
  data.value = d
  isLoading.value = false
}

onMounted(fetchData)
</script>
