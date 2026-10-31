<template>
  <div class="wb-panel order-funnel">
    <div class="card__hd">Распределение статусов заказов</div>
    <div class="wb-panel__bd">
      <div class="order-funnel__chart" ref="chartEl">
        <VChart v-if="chartData.length" :option="chartOption" autoresize style="height:100%" />
        <div v-else class="d-flex align-items-center justify-content-center h-100 text-muted" style="font-size:calc(12px * var(--fs))">Нет данных для графика</div>
      </div>

      <div v-if="hasData" class="order-funnel__progress" title="Доли по количеству заказов">
        <div v-if="funnel.bought_pct > 0" :style="{ width: funnel.bought_pct + '%', background: C_BUYOUT }" :title="'Выкупленные ' + fmtPct(funnel.bought_pct)"></div>
        <div v-if="funnel.delivery_pct > 0" :style="{ width: funnel.delivery_pct + '%', background: C_DELIVERY }" :title="'В доставке ' + fmtPct(funnel.delivery_pct)"></div>
        <div v-if="funnel.cancel_pct > 0" :style="{ width: funnel.cancel_pct + '%', background: C_CANCEL }" :title="'Отменённые ' + fmtPct(funnel.cancel_pct)"></div>
        <div v-if="funnel.returns_pct > 0" :style="{ width: Math.max(0.6, funnel.returns_pct) + '%', background: C_RETURNS }" :title="'Возвраты ' + fmtPct(funnel.returns_pct)"></div>
      </div>

      <div class="grid-6 order-funnel__cards">
        <div class="tile">
          <div class="tile__label">Заказы</div>
          <div class="tile__value">{{ fmtMoney(funnel.total_sum) }}</div>
          <div class="tile__foot">{{ fmt0(funnel.total_cnt) }} шт.</div>
        </div>
        <div class="tile">
          <div class="tile__label"><span class="order-funnel__dot" :style="{ background: C_BUYOUT }"></span>Выкупленные</div>
          <div class="tile__value">{{ fmtMoney(funnel.bought_sum) }}</div>
          <div class="tile__foot">{{ fmtPct(funnel.bought_pct) }} · {{ fmt0(funnel.bought_cnt) }} шт.</div>
        </div>
        <div class="tile">
          <div class="tile__label"><span class="order-funnel__dot" :style="{ background: C_DELIVERY }"></span>В доставке</div>
          <div class="tile__value">{{ fmtMoney(funnel.delivery_sum) }}</div>
          <div class="tile__foot">{{ fmtPct(funnel.delivery_pct) }} · {{ fmt0(funnel.delivery_cnt) }} шт.</div>
        </div>
        <div class="tile">
          <div class="tile__label"><span class="order-funnel__dot" :style="{ background: C_CANCEL }"></span>Отменённые</div>
          <div class="tile__value">{{ fmtMoney(funnel.cancel_sum) }}</div>
          <div class="tile__foot">{{ fmtPct(funnel.cancel_pct) }} · {{ fmt0(funnel.cancel_cnt) }} шт.</div>
        </div>
        <div class="tile">
          <div class="tile__label"><span class="order-funnel__dot" :style="{ background: C_RETURNS }"></span>Возвраты</div>
          <div class="tile__value">{{ fmtMoney(funnel.returns_sum) }}</div>
          <div class="tile__foot">{{ fmtPct(funnel.returns_pct) }} · {{ fmt0(funnel.returns_cnt) }} шт.</div>
        </div>
        <div class="tile tile--4 order-funnel__buyout">
          <div class="tile__label">Процент выкупа</div>
          <div class="tile__value">{{ fmtPct(funnel.buyout_pct) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useNumFmt } from '@/composables/useNumFmt'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, DatasetComponent, CanvasRenderer])

const props = defineProps<{ funnel: any, chartData: any[] }>()

const { fmt0, fmtMoney, fmtPct } = useNumFmt()

const hasData = computed(()=> (props.funnel?.total_cnt ?? 0) > 0)

/* Цвета серий — как в PHP-оригинале (feed-aggregated): обсуждаются отдельно, тема их не меняет. */
const C_BUYOUT = '#5B9CD6'
const C_DELIVERY = '#9AA0A8'
const C_CANCEL = '#F5A623'
const C_RETURNS = '#E74C3C'

const chartOption = computed(()=>{
  const data = props.chartData || []
  if(!data.length) return {}
  const dates = data.map((r:any)=>{
    try{
      const d = new Date(r.date)
      return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    }catch{ return r.date }
  })
  return {
    tooltip:{ trigger:'axis', axisPointer:{type:'shadow'} },
    legend:{ data:['Выкупленные','В доставке','Отменённые','Возвраты'], top:0, textStyle:{fontSize:11} },
    grid:{ left:40, right:16, top:30, bottom:30, containLabel:true },
    xAxis:{ type:'category', data: dates, axisLabel:{fontSize:11} },
    yAxis:{ type:'value', minInterval:1, axisLabel:{fontSize:11} },
    series:[
      { name:'Выкупленные', type:'bar', stack:'total', data: data.map((r:any)=> r.bought_cnt||0), itemStyle:{color:C_BUYOUT}, barWidth:'60%' },
      { name:'В доставке', type:'bar', stack:'total', data: data.map((r:any)=> r.delivery_cnt||0), itemStyle:{color:C_DELIVERY} },
      { name:'Отменённые', type:'bar', stack:'total', data: data.map((r:any)=> r.cancel_cnt||0), itemStyle:{color:C_CANCEL} },
      { name:'Возвраты', type:'bar', stack:'total', data: data.map((r:any)=> r.returns_cnt||0), itemStyle:{color:C_RETURNS} },
    ]
  }
})
</script>
<style scoped>
.order-funnel__chart { height: 300px; }
.order-funnel__progress {
  display: flex; height: 22px; border-radius: 7px; overflow: hidden;
  margin: 12px 0 16px; background: var(--surface-2);
}
.order-funnel__progress > div { height: 100%; }
.order-funnel__progress > div:first-child { border-radius: 7px 0 0 7px; }
.order-funnel__progress > div:last-child { border-radius: 0 7px 7px 0; }
.order-funnel__progress > div:only-child { border-radius: 7px; }
.order-funnel__cards { align-items: stretch; }
/* кружок статуса не должен липнуть к подписи */
.order-funnel__cards .tile__label { display: flex; align-items: center; gap: 6px; }
.order-funnel__dot {
  display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex: none;
}
.order-funnel__buyout { display: flex; flex-direction: column; justify-content: center; }
</style>
