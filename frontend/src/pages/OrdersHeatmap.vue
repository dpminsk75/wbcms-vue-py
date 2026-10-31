<template>
  <div class="container-xxl page-orders-heatmap">
    <div v-if="card" class="page-orders-heatmap__card-head">
      <ProductCell
        :photo="card.photos"
        :title="card.title"
        :sub="card.brand"
        :vendor="card.vendorCode"
        :link="'/wb/detail?nm_id=' + card.nmID"
        :link-label="'WB: ' + card.nmID"
      />
    </div>
    <template v-else>
      <h1 class="page-title">Тепловая карта заказов 7×24</h1>
      <p class="text-muted page-orders-heatmap__lede">Время добавления заказа по дням и часам — для расписания рекламы. Источник: <code>wb_order.date</code>.</p>
    </template>

    <!-- Фильтр: универсальная компонента (карточка + даты + быстрые кнопки) -->
    <div class="row">
      <div class="col-md-12">
        <WbUniversalFilter
          v-model:product="filters.nm_id"
          v-model:date-from="filters.date_from"
          v-model:date-to="filters.date_to"
          :show-brand-category="false"
          :show-quick="true"
          @apply="fetchData()"
          @reset="reset()"
        />
      </div>
    </div>

    <!-- Сводка периода -->
    <div class="grid-4 page-orders-heatmap__summary">
      <div class="tile">
        <div class="tile__label">Период</div>
        <div class="tile__value page-orders-heatmap__summary-value">{{ data?.dateFrom }} — {{ data?.dateTo }}</div>
      </div>
      <div class="tile">
        <div class="tile__label">Заказов</div>
        <div class="tile__value">{{ fmt0(data?.totalCnt) }}</div>
      </div>
      <div class="tile">
        <div class="tile__label">Сумма</div>
        <div class="tile__value">{{ fmt0(data?.totalSum) }} ₽</div>
      </div>
      <div class="tile">
        <div class="tile__label">Макс в ячейке</div>
        <div class="tile__value">{{ data?.maxCnt ?? 0 }}</div>
      </div>
    </div>

    <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
    <template v-else-if="data">
      <div class="row">
        <div class="col-lg-9">
          <div class="tbl-card">
            <div class="card__hd">
              <span>Теплокарта 7×24 — заказы</span>
              <span class="spacer"></span>
              <span class="page-orders-heatmap__matrix-hint">Клик по ячейке → детали справа</span>
            </div>
            <div class="table-responsive page-orders-heatmap__matrix-wrap">
              <table class="heatmap-table page-orders-heatmap__matrix-table">
                <thead>
                  <tr>
                    <th class="page-orders-heatmap__matrix-corner">Д / Ч</th>
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
          <div id="heatmap-detail" class="wb-panel page-orders-heatmap__detail-card">
            <div class="card__hd">Детали часа</div>
            <div class="wb-panel__bd page-orders-heatmap__detail-body">
              <div class="text-muted page-orders-heatmap__detail-hint">Кликните по ячейке, чтобы закрепить и разобрать причины.</div>
              <div class="page-orders-heatmap__detail-title">{{ detailTitle }}</div>
              <div class="page-orders-heatmap__detail-stats">
                <div class="tile page-orders-heatmap__stat">
                  <div class="tile__label">Заказы</div>
                  <div class="tile__value">{{ detail.cnt }}</div>
                </div>
                <div class="tile page-orders-heatmap__stat">
                  <div class="tile__label">Сумма</div>
                  <div class="tile__value page-orders-heatmap__stat-value--sm">{{ detail.sumStr }}</div>
                </div>
                <div class="tile page-orders-heatmap__stat">
                  <div class="tile__label">Средний чек</div>
                  <div class="tile__value page-orders-heatmap__stat-value--sm">{{ detail.avgStr }}</div>
                </div>
                <div class="tile page-orders-heatmap__stat">
                  <div class="tile__label">Доля периода</div>
                  <div class="tile__value page-orders-heatmap__stat-value--sm">{{ detail.shareStr }}</div>
                </div>
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
            <div class="tile page-orders-heatmap__reco-card">
              <div class="page-orders-heatmap__reco-head">
                <div class="page-orders-heatmap__reco-name">{{ cardsMeta[key].icon }} {{ cardsMeta[key].title }}</div>
                <span class="badge page-orders-heatmap__reco-badge" :class="confidenceBadge(data.recommend[key].best)">Уверенность: {{ confidence(data.recommend[key].best) }}</span>
              </div>
              <div class="text-muted page-orders-heatmap__reco-sub">{{ cardsMeta[key].sub }}</div>
              <div class="page-orders-heatmap__reco-best">
                <div class="page-orders-heatmap__reco-best-title">{{ data.recommend[key].best?.label }}</div>
                <div class="text-muted page-orders-heatmap__reco-best-sub">Окно даёт {{ fmt2(data.recommend[key].best?.share) }}% всех заказов · спрос {{ demand(data.recommend[key].best) }}</div>
              </div>
              <div class="page-orders-heatmap__reco-list">
                <div class="tile page-orders-heatmap__stat">
                  <div class="tile__label">Заказов</div>
                  <div class="tile__value page-orders-heatmap__stat-value--sm">{{ data.recommend[key].best?.cnt }}</div>
                  <div class="text-muted">Доля {{ fmt2(data.recommend[key].best?.share) }}%</div>
                </div>
                <div class="tile page-orders-heatmap__stat">
                  <div class="tile__label">Средний чек</div>
                  <div class="tile__value page-orders-heatmap__stat-value--sm">{{ fmt0(data.recommend[key].best?.avg) }} ₽</div>
                  <div class="text-muted">Отмен {{ fmt1(data.recommend[key].best?.cancel_rate) }}%</div>
                </div>
              </div>
              <div class="page-orders-heatmap__reco-list-title">Топ-3 окна</div>
              <div v-for="(w,i) in data.recommend[key].top3" :key="w.label" class="page-orders-heatmap__reco-item" :class="{ 'is-top': i===0 }">
                <div class="page-orders-heatmap__reco-item-title">{{ i+1 }}. {{ w.label }}: {{ w.cnt }} зак. · {{ fmt0(w.avg) }} ₽ · отмен {{ fmt1(w.cancel_rate) }}%</div>
                <div class="text-muted">Доля {{ fmt2(w.share) }}% · {{ key==='byVolume' ? 'объём' : key==='byAvg' ? 'чек' : 'надёжность' }} за 7 дней</div>
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
import WbUniversalFilter from '../components/common/WbUniversalFilter.vue'
import ProductCell from '../components/common/ProductCell.vue'
import { useNumFmt } from '../composables/useNumFmt'

const { fmt0, fmt1, fmt2 } = useNumFmt()

const days = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
const dayFull = ['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье']

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
/** Бейдж уверенности — статусные цвета темы. */
const confidenceBadge = (best:any)=>{
  const c = confidence(best)
  return c==='высокая' ? 'badge--ok' : c==='средняя' ? 'badge--info' : 'badge--neutral'
}
const demand = (best:any)=>{
  if(!best) return ''
  if(best.cnt>=20) return 'высокий'
  if(best.cnt>=10) return 'средний'
  return 'низкий'
}

const cellCnt = (wd:number, hr:number)=> data.value?.matrix?.[wd]?.[hr]?.cnt ?? 0
const cellSum = (wd:number, hr:number)=> data.value?.matrix?.[wd]?.[hr]?.sum ?? 0
/** Шкала тепловой карты — фиксированная (синяя), не зависит от акцента темы.
    Цвета — токены темы (--heat-blue-rgb/--heat-ink/--heat-empty-ink), значения прежние. */
const cellStyle = (wd:number, hr:number)=>{
  const cnt = cellCnt(wd, hr)
  const max = data.value?.maxCnt || 0
  const alpha = max > 0 ? (cnt / max) : 0
  let bg = 'var(--surface)', color = 'var(--heat-empty-ink)'
  if(cnt>0){
    bg = `rgba(var(--heat-blue-rgb),${(0.08 + alpha*0.92).toFixed(2)})`
    color = alpha > 0.5 ? 'var(--surface)' : 'var(--heat-ink)'
  }
  return `padding:6px 2px; text-align:center; border:1px solid var(--line); background:${bg}; color:${color}; cursor:pointer; font-weight:${cnt>0?'600':'400'};`
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
