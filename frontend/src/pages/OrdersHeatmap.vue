<template>
  <div class="container-xxl" style="padding:20px 15px; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
    <div v-if="card">
      <div style="display:flex; gap:12px; align-items:center; margin-bottom:12px">
        <img v-if="cardPhoto" :src="cardPhoto" style="width:60px; height:80px; object-fit:cover; border-radius:6px; flex-shrink:0" @error="(e:any)=>e.target.src='/images/no-photo.png'" />
        <div>
          <h1 style="font-size:18px; font-weight:700; margin:0">{{ card.title }}</h1>
          <div style="font-size:12px; color:#6b7280">WB: {{ card.nmID }} · {{ card.vendorCode }} · {{ card.brand }}</div>
        </div>
      </div>
    </div>
    <template v-else>
      <h1 style="font-size:20px; font-weight:700; margin-bottom:4px">Тепловая карта заказов 7×24</h1>
      <p class="text-muted" style="font-size:13px;">Время добавления заказа по дням и часам — для расписания рекламы. Источник: <code>wb_order.date</code>.</p>
    </template>

    <!-- Фильтр: WbFilterBar обязательно -->
    <div class="row">
      <WbFilterBar v-model:nm-id="filters.nm_id" v-model:date-from="filters.date_from" v-model:date-to="filters.date_to" @apply="fetchData()" @reset="reset()" />
    </div>

    <div class="heatmap-top" style="display:flex; flex-wrap:wrap; gap:16px; margin:12px 0 16px;">
      <div class="heatmap-summary" style="font-size:13px; color:#6b7280;">
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
          <div class="card" style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
            <div class="card-header d-flex justify-content-between align-items-center" style="background:#fff; font-size:13px; font-weight:600;">
              <span>Теплокарта 7×24 — заказы</span>
              <span class="text-muted" style="font-weight:400; font-size:12px;">Клик по ячейке → детали справа</span>
            </div>
            <div class="table-responsive" style="overflow-x:auto;">
              <table class="heatmap-table" style="width:100%; border-collapse:collapse; font-size:12px;">
                <thead>
                  <tr>
                    <th style="padding:8px; min-width:60px; background:#f9fafb; border:1px solid #e5e7eb;">День / Час</th>
                    <th v-for="h in 24" :key="h" style="padding:6px 2px; text-align:center; min-width:36px; background:#f9fafb; border:1px solid #e5e7eb;">{{ String(h-1).padStart(2,'0') }}:00</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(day, wd) in days" :key="wd">
                    <th style="padding:6px 8px; text-align:left; background:#f9fafb; border:1px solid #e5e7eb;">{{ day }}</th>
                    <td v-for="hr in 24" :key="hr" class="heatmap-cell" :class="{'is-active': activeWd===wd && activeHr===(hr-1)}"
                      :style="cellStyle(wd, hr-1)" @click="selectCell(wd, hr-1)">
                      {{ cellCnt(wd, hr-1) || '0' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div style="display:flex; align-items:center; gap:8px; padding:8px 12px; font-size:11px; color:#6b7280;">
              <span>0</span><div style="flex:1; height:10px; background:linear-gradient(to right, #ffffff, rgba(47,107,255,1)); border:1px solid #e5e7eb; border-radius:4px;"></div><span>{{ data.maxCnt }}</span><span style="margin-left:8px;">заказов в ячейке</span>
            </div>
          </div>
        </div>
        <div class="col-lg-3">
          <div id="heatmap-detail" class="card" style="border:1px solid #e5e7eb; border-radius:10px; position:sticky; top:12px;">
            <div class="card-header" style="background:#fff; font-weight:600; font-size:13px;">Детали часа</div>
            <div class="card-body" style="font-size:13px;">
              <div class="text-muted" style="font-size:12px; margin-bottom:8px;">Кликните по ячейке, чтобы закрепить и разобрать причины.</div>
              <div style="font-weight:700; margin-bottom:10px;">{{ detailTitle }}</div>
              <div class="row g-2" style="font-size:12px;">
                <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Заказы</div><div style="font-weight:700; font-size:16px;">{{ detail.cnt }}</div></div></div>
                <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Сумма</div><div style="font-weight:700;">{{ detail.sumStr }}</div></div></div>
                <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Средний чек</div><div>{{ detail.avgStr }}</div></div></div>
                <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Доля периода</div><div>{{ detail.shareStr }}</div></div></div>
              </div>
              <div class="text-muted" style="font-size:11px; margin-top:10px;">Выберите ячейку — подсветка зафиксируется.</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="data.recommend" style="margin-top:18px;">
        <h5 style="font-weight:700; margin-bottom:4px;">Рекомендации лучших окон</h5>
        <p class="text-muted" style="font-size:12px; margin-bottom:12px;">Топ-3 временных окна по объёму, чеку и надёжности — для планирования рекламы. Окно 2 часа, агрегация по всем 7 дням периода.</p>
        <div class="row g-3">
          <div v-for="key in (['byVolume','byAvg','byReli'] as const)" :key="key" class="col-lg-4">
            <div class="card h-100" style="border:1px solid #e5e7eb; border-radius:10px;">
              <div class="card-body">
                <div class="d-flex justify-content-between align-items-center" style="margin-bottom:8px;">
                  <div style="font-weight:700; font-size:13px;">{{ cardsMeta[key].icon }} {{ cardsMeta[key].title }}</div>
                  <span class="badge" style="font-size:10px; color:#fff;" :style="{background: confidenceColor(data.recommend[key].best)}">Уверенность: {{ confidence(data.recommend[key].best) }}</span>
                </div>
                <div class="text-muted" style="font-size:11px; margin-bottom:8px;">{{ cardsMeta[key].sub }}</div>
                <div class="border rounded p-2 mb-2" style="background:#f8fafc;">
                  <div style="font-weight:800; font-size:14px;">{{ data.recommend[key].best?.label }}</div>
                  <div class="text-muted" style="font-size:11px;">Окно даёт {{ fmt2(data.recommend[key].best?.share) }}% всех заказов · спрос {{ demand(data.recommend[key].best) }}</div>
                </div>
                <div class="row g-2" style="font-size:11px;">
                  <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Заказов</div><div style="font-weight:700;">{{ data.recommend[key].best?.cnt }}</div><div class="text-muted">Доля {{ fmt2(data.recommend[key].best?.share) }}%</div></div></div>
                  <div class="col-6"><div class="border rounded p-2"><div class="text-muted">Средний чек</div><div style="font-weight:700;">{{ fmt0(data.recommend[key].best?.avg) }} ₽</div><div class="text-muted">Отмен {{ fmt1(data.recommend[key].best?.cancel_rate) }}%</div></div></div>
                </div>
                <div style="font-weight:700; font-size:11px; margin:10px 0 6px;">Топ-3 окна</div>
                <div v-for="(w,i) in data.recommend[key].top3" :key="w.label" class="border rounded p-2 mb-1" style="font-size:11px;" :style="{background: i===0 ? '#f0f7ff' : '#fff'}">
                  <div style="font-weight:600;">{{ i+1 }}. {{ w.label }}: {{ w.cnt }} зак. · {{ fmt0(w.avg) }} ₽ · отмен {{ fmt1(w.cancel_rate) }}%</div>
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
import { ref, computed, onMounted } from 'vue'
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
  const r = await fetch(`/api/orders/heatmap?${q}`)
  data.value = await r.json()
  isLoading.value = false
}

onMounted(fetchData)
</script>
<style>
.heatmap-table th { white-space:nowrap; }
.heatmap-cell:hover { outline:2px solid #2f6bff; outline-offset:-2px; }
.heatmap-cell.is-active { outline:2px solid #111827 !important; outline-offset:-2px; box-shadow:inset 0 0 0 1px #111827; }
@media (max-width: 992px) { .heatmap-table { font-size:11px; } }
</style>
