<template>
  <div>
    <div class="order-funnel-chart-card">
      <div style="font-size:13px; color:#6b7280; margin-bottom:8px;">Распределение статуса заказов</div>
      <div style="height:300px" ref="chartEl">
        <VChart v-if="chartData.length" :option="chartOption" autoresize style="height:100%" />
        <div v-else class="d-flex align-items-center justify-content-center h-100 text-muted" style="font-size:12px">Нет данных для графика</div>
      </div>
    </div>

    <div v-if="hasData" class="order-funnel-progress" title="Доли по количеству заказов">
      <div v-if="funnel.bought_pct > 0" :style="{width: funnel.bought_pct + '%', background:'#5B9CD6'}" :title="'Выкупленные ' + fmtPct(funnel.bought_pct)"></div>
      <div v-if="funnel.delivery_pct > 0" :style="{width: funnel.delivery_pct + '%', background:'#9AA0A8'}" :title="'В доставке ' + fmtPct(funnel.delivery_pct)"></div>
      <div v-if="funnel.cancel_pct > 0" :style="{width: funnel.cancel_pct + '%', background:'#F5A623'}" :title="'Отменённые ' + fmtPct(funnel.cancel_pct)"></div>
      <div v-if="funnel.returns_pct > 0" :style="{width: Math.max(0.6, funnel.returns_pct) + '%', background:'#E74C3C'}" :title="'Возвраты ' + fmtPct(funnel.returns_pct)"></div>
    </div>

    <div class="order-funnel-cards">
      <div class="of-card">
        <div class="of-label">Заказы <span title="Всего заказов за период" style="cursor:help; color:#aaa;">?</span></div>
        <div class="of-value">{{ fmtMoney(funnel.total_sum) }}</div>
        <div class="of-sub">{{ fmt0(funnel.total_cnt) }} шт.</div>
      </div>
      <div class="of-card">
        <div class="of-label"><span class="dot" style="background:#5B9CD6;"></span> Выкупленные <span title="s.saleID NOT LIKE 'R%' и не отменён" style="cursor:help; color:#aaa;">?</span></div>
        <div class="of-value">{{ fmtMoney(funnel.bought_sum) }}</div>
        <div class="of-sub">{{ fmtPct(funnel.bought_pct) }}</div>
        <div class="of-sub">{{ fmt0(funnel.bought_cnt) }} шт.</div>
      </div>
      <div class="of-card">
        <div class="of-label"><span class="dot" style="background:#9AA0A8;"></span> В доставке <span title="is_cancel=0 и srid без продажи" style="cursor:help; color:#aaa;">?</span></div>
        <div class="of-value">{{ fmtMoney(funnel.delivery_sum) }}</div>
        <div class="of-sub">{{ fmtPct(funnel.delivery_pct) }}</div>
        <div class="of-sub">{{ fmt0(funnel.delivery_cnt) }} шт.</div>
      </div>
      <div class="of-card">
        <div class="of-label"><span class="dot" style="background:#F5A623;"></span> Отменённые <span title="is_cancel=1" style="cursor:help; color:#aaa;">?</span></div>
        <div class="of-value">{{ fmtMoney(funnel.cancel_sum) }}</div>
        <div class="of-sub">{{ fmtPct(funnel.cancel_pct) }}</div>
        <div class="of-sub">{{ fmt0(funnel.cancel_cnt) }} шт.</div>
      </div>
      <div class="of-card">
        <div class="of-label"><span class="dot" style="background:#E74C3C;"></span> Возвраты <span title="s.saleID LIKE 'R%'" style="cursor:help; color:#aaa;">?</span></div>
        <div class="of-value">{{ fmtMoney(funnel.returns_sum) }}</div>
        <div class="of-sub">{{ fmtPct(funnel.returns_pct) }}</div>
        <div class="of-sub">{{ fmt0(funnel.returns_cnt) }} шт.</div>
      </div>
      <div class="of-card of-buyout">
        <div class="of-label" style="justify-content:center;">Процент выкупа</div>
        <div class="of-value">{{ fmtPct(funnel.buyout_pct) }}</div>
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

use([BarChart, GridComponent, TooltipComponent, LegendComponent, DatasetComponent, CanvasRenderer])

const props = defineProps<{ funnel: any, chartData: any[] }>()

const hasData = computed(()=> (props.funnel?.total_cnt ?? 0) > 0)

const fmtMoney = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:0, maximumFractionDigits:0}).format(Number(v)||0) + ' ₽'
const fmtPct = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0) + ' %'
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))

const chartOption = computed(()=>{
  const data = props.chartData || []
  if(!data.length) return {}
  const dates = data.map((r:any)=>{
    try{
      const d = new Date(r.date)
      return d.toLocaleDateString('ru-RU',{day:'2-digit', month:'short'}).replace('.','')
    }catch{ return r.date }
  })
  return {
    tooltip:{ trigger:'axis', axisPointer:{type:'shadow'} },
    legend:{ data:['Выкупленные','В доставке','Отменённые','Возвраты'], top:0, textStyle:{fontSize:11} },
    grid:{ left:40, right:16, top:30, bottom:30, containLabel:true },
    xAxis:{ type:'category', data: dates, axisLabel:{fontSize:11} },
    yAxis:{ type:'value', minInterval:1, axisLabel:{fontSize:11} },
    series:[
      { name:'Выкупленные', type:'bar', stack:'total', data: data.map((r:any)=> r.bought_cnt||0), itemStyle:{color:'#5B9CD6'}, barWidth:'60%' },
      { name:'В доставке', type:'bar', stack:'total', data: data.map((r:any)=> r.delivery_cnt||0), itemStyle:{color:'#9AA0A8'} },
      { name:'Отменённые', type:'bar', stack:'total', data: data.map((r:any)=> r.cancel_cnt||0), itemStyle:{color:'#F5A623'} },
      { name:'Возвраты', type:'bar', stack:'total', data: data.map((r:any)=> r.returns_cnt||0), itemStyle:{color:'#E74C3C'} },
    ]
  }
})
</script>
<style scoped>
.order-funnel-chart-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px 18px; margin-bottom:16px; }
.order-funnel-progress { display:flex; height:25px; border-radius:7px; overflow:hidden; margin:10px 0 18px; background: transparent; }
.order-funnel-progress > div { height:100%; }
.order-funnel-progress > div:first-child { border-radius: 7px 0 0 7px; }
.order-funnel-progress > div:last-child { border-radius: 0 7px 7px 0; }
.order-funnel-progress > div:only-child { border-radius: 7px; }
.order-funnel-cards { display:flex; flex-wrap:wrap; gap:12px; }
.order-funnel-cards .of-card { flex:1 1 160px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:14px 16px; min-width:140px; }
.order-funnel-cards .of-card .of-label { font-size:12px; color:#8a8f98; margin-bottom:6px; display:flex; align-items:center; gap:6px; }
.order-funnel-cards .of-card .of-value { font-size:20px; font-weight:700; color:#1f2937; white-space:nowrap; }
.order-funnel-cards .of-card .of-sub { font-size:12px; color:#6b7280; margin-top:2px; }
.order-funnel-cards .of-card.of-buyout { background:#f9fafb; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; }
.order-funnel-cards .of-card.of-buyout .of-value { font-size:26px; font-weight:800; }
.order-funnel-cards .of-card .of-label .dot { display:inline-block; width:10px; height:10px; border-radius:50%; flex-shrink:0; }
@media (max-width: 767px) {
  .order-funnel-cards .of-card { flex:1 1 45%; }
}
</style>
