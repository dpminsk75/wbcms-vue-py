<template>
  <div v-if="busy || hasData || isError" class="card shadow-sm border-0 mb-4 today-stats-widget" style="border:1px solid #e5e7eb; border-radius:12px; background:#fff">
    <div class="card-body p-3">
      <div class="d-flex align-items-center justify-content-between mb-3 flex-wrap" style="gap:12px">
        <div class="today-stats-tabs">
          <button v-for="t in tabs" :key="t.value" @click="tab=t.value" class="tsw-tab" :class="{active: tab===t.value}">{{ t.label }}</button>
        </div>
        <div class="d-flex align-items-center" style="gap:14px">
          <div class="text-muted small" style="font-size:12px">Обновлено в {{ updatedAt }}</div>
          <label class="small text-muted d-flex align-items-center" style="gap:4px; cursor:pointer; font-size:12px" :style="{visibility: (period==='month_to_date'||period==='last_month') ? 'visible' : 'hidden'}">
            <input type="checkbox" v-model="trimPast" :disabled="!(period==='month_to_date'||period==='last_month')" /> по сегодня
          </label>
          <select v-model="period" class="tsw-period-btn">
            <option v-for="p in periods" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </div>
      </div>

      <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm me-2"></span> Загрузка...</div>
      <div v-else-if="error" class="alert alert-warning">Ошибка {{ String(error) }}</div>
      <template v-else-if="data">
        <div class="row g-4 mb-2">
          <!-- Количество -->
          <div class="col-6 col-md-3">
            <div class="text-muted small" style="font-size:12px; color:#6b7280">Количество</div>
            <div style="font-size:22px; font-weight:700; margin-top:4px">{{ fmt0(main?.cnt) }}</div>
            <div v-for="o in others" :key="o.key" style="font-size:11px; margin-top:4px" :style="{color: (main?.cnt||0) >= (totals[o.key]?.cnt||0) ? '#1E9E7C' : '#E0525C'}">
              {{ (main?.cnt||0) >= (totals[o.key]?.cnt||0) ? '↑' : '↓' }} {{ fmt0(Math.abs((main?.cnt||0)-(totals[o.key]?.cnt||0))) }} — {{ o.name }}
            </div>
          </div>
          <!-- Сумма -->
          <div class="col-6 col-md-3">
            <div class="text-muted small" style="font-size:12px; color:#6b7280">Сумма</div>
            <div style="font-size:22px; font-weight:700; margin-top:4px">{{ fmt2(main?.sum) }} ₽</div>
            <div v-for="o in others" :key="o.key" style="font-size:11px; margin-top:4px" :style="{color: (main?.sum||0) >= (totals[o.key]?.sum||0) ? '#1E9E7C' : '#E0525C'}">
              {{ (main?.sum||0) >= (totals[o.key]?.sum||0) ? '↑' : '↓' }} {{ fmt2(Math.abs((main?.sum||0)-(totals[o.key]?.sum||0))) }} ₽ — {{ o.name }}
            </div>
          </div>
          <!-- СПП -->
          <div class="col-6 col-md-3">
            <div class="text-muted small" style="font-size:12px; color:#6b7280">СПП (среднее)</div>
            <div style="font-size:22px; font-weight:700; margin-top:4px">{{ fmt1(main?.spp) }}%</div>
            <div v-for="o in others" :key="o.key" style="font-size:11px; margin-top:4px" :style="{color: (main?.spp||0) >= (totals[o.key]?.spp||0) ? '#1E9E7C' : '#E0525C'}">
              {{ (main?.spp||0) >= (totals[o.key]?.spp||0) ? '↑' : '↓' }} {{ fmt1(Math.abs((main?.spp||0)-(totals[o.key]?.spp||0))) }} п.п. — {{ o.name }}
            </div>
          </div>
          <!-- Правый бокс — предыдущий период -->
          <div class="col-6 col-md-3">
            <div v-if="prev" style="border:1px solid #4A3A8C; border-radius:8px; padding:10px 12px; background:#fff">
              <div class="text-muted small" style="font-size:12px">{{ prev.name }}</div>
              <div class="small mt-2 text-end"><b>{{ fmt0(prev.cnt) }}</b> - заказов</div>
              <div class="small mt-1 text-end"><b>{{ fmt2(prev.sum) }}</b> ₽ - на сумму</div>
              <div class="small mt-1 text-end"><b>{{ fmt1(prev.spp) }}</b> % - СПП</div>
            </div>
          </div>
        </div>

        <div style="height:260px">
          <VChart :option="chartOption" autoresize style="height:100%" />
        </div>
        <div v-if="data.axisCaption" style="text-align:right; color:#4A3A8C; font-size:11px; margin-top:4px">{{ data.axisCaption }}</div>
      </template>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const tab = ref<'orders'|'sales'>('orders')
const period = ref('today')
const trimPast = ref(true)
const tabs = [{label:'Заказы',value:'orders'},{label:'Продажи',value:'sales'}]
const periods = [
  {label:'За сегодня',value:'today'}, {label:'За вчера',value:'yesterday'},
  {label:'С начала недели',value:'week_to_date'}, {label:'За прошлую неделю',value:'last_week'},
  {label:'За месяц',value:'month_to_date'}, {label:'За прошлый месяц',value:'last_month'},
]

const auth = useAuthStore()
const { data, isLoading, isFetching, isError, error } = useQuery({
  queryKey: computed(()=> ['today-stats', period.value, tab.value, trimPast.value, auth.companyId] as const),
  queryFn: () => dashboardApi.todayStats(period.value as any, tab.value, trimPast.value),
})
const hasData = computed(() => {
  // категории статичны (часы/дни всегда есть) — смотрим итоги: хоть где-то заказы/сумма
  const totals = ((data.value as any)?.totals || {}) as Record<string, any>
  return Object.values(totals).some((t:any) => (Number(t?.cnt)||0) > 0 || (Number(t?.sum)||0) !== 0)
})
const busy = computed(() => isLoading.value || isFetching.value)
const report = inject<(n:string,h:boolean)=>void>('dashReport', ()=>{})
watchEffect(() => { if (!busy.value) report('today', hasData.value || !!isError.value) })

const updatedAt = computed(()=>{
  const raw = (data.value as any)?.updated_at
  if(raw){
    try{
      const d = new Date(String(raw).replace(' ', 'T'))
      if(!isNaN(d.getTime())) return d.toLocaleTimeString('ru-RU',{hour:'2-digit', minute:'2-digit'})
      const m = String(raw).match(/(\d{2}):(\d{2})/)
      if(m) return `${m[1]}:${m[2]}`
    }catch{}
    return String(raw).slice(11,16) || String(raw)
  }
  return new Date().toLocaleTimeString('ru-RU',{hour:'2-digit', minute:'2-digit'})
})

const main = computed(()=> (data.value as any)?.totals?.[(data.value as any)?.seriesMeta?.[0]?.key] ?? null)
const totals = computed(()=> (data.value as any)?.totals ?? {})
const others = computed(()=> ((data.value as any)?.seriesMeta ?? []).slice(1) as any[])
const prev = computed(()=>{
  const o = others.value[0]; if(!o) return null
  const t = totals.value[o.key]; if(!t) return null
  return { name: o.name, cnt: t.cnt, sum: t.sum, spp: t.spp }
})

const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt1 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:1, maximumFractionDigits:1}).format(Number(v)||0)
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)

const chartOption = computed(()=>{
  const d = data.value as any; if(!d || !d.categories) return {}
  const colors = ['#4B61EC','#F042B7','#3AC1C7']
  const series:any[] = []
  // СПП-бары — фон, рисуем первыми
  if(d.granularity==='day'){
    d.seriesMeta.forEach((m:any, idx:number)=>{
      series.push({
        name: m.name+' — СПП', type:'bar', yAxisIndex:1,
        data: d.series[m.key].map((p:any)=> p.spp ?? null),
        itemStyle:{color: colors[idx], opacity:0.28},
        z: 0,
      })
    })
  }
  // Линии — неделю назад фон → вчера → сегодня верх (как amCharts moveValue)
  const order = [...d.seriesMeta].map((_:any,i:number)=>i).reverse() // [2,1,0]
  order.forEach((idx:number)=>{
    const m = d.seriesMeta[idx]
    series.push({
      name: m.name, type:'line',
      data: d.series[m.key].map((p:any)=> p.sum ?? null),
      smooth:false, connectNulls:false,
      lineStyle:{width: idx===0?3:2, type: idx===2?'dashed':'solid'},
      itemStyle:{color: colors[idx]},
      z: 3 - idx, // сегодня 3 верх, неделю назад 1 низ
    })
  })
  return {
    tooltip:{trigger:'axis'},
    legend:{data: d.seriesMeta.map((m:any)=>m.name), top:0, textStyle:{fontSize:11}},
    grid:{left:40, right:20, top:30, bottom:30, containLabel:true},
    xAxis:{type:'category', data: d.categories},
    yAxis:[{type:'value', min:0}, {type:'value', min:0, max:100}],
    series
  }
})
</script>
<style scoped>
.today-stats-tabs .tsw-tab{
  border:none; background:transparent; font-size:14px; font-weight:600; color:#6E6A80;
  padding:6px 4px; margin-right:22px; border-bottom:2px solid transparent; cursor:pointer;
}
.today-stats-tabs .tsw-tab.active{ color:#1D1B2A; border-bottom-color:#4A3A8C; }
.tsw-period-btn{
  border:1px solid #E2E0EC; background:#fff; color:#1D1B2A; font-size:13px; font-weight:600;
  padding:7px 12px; border-radius:8px; cursor:pointer;
}
</style>
