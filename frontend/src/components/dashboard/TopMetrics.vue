<template>
  <div style="font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
    <div class="row g-3 mb-4">
      <div class="col-md-3 col-sm-6">
        <div class="card shadow-sm border-0 bg-light text-dark h-100 p-3 text-center">
          <div class="small font-weight-bold">Выручка (30 дн)</div>
          <div class="h3 font-weight-bold mt-2 text-primary">{{ fmt(kpis[0]?.value) }} ₽</div>
          <div class="row justify-content-left g-2">
            <div class="col-auto small mt-1">Возвраты: {{ fmt(kpis[0]?.sub1) }} ₽</div>
            <div class="col-auto small mt-1">Заказы: {{ kpis[0]?.sub2 }} шт</div>
          </div>
        </div>
      </div>
      <div class="col-md-3 col-sm-6">
        <div class="card shadow-sm border-0 bg-light text-dark h-100 p-3 text-center">
          <div class="small font-weight-bold">Все расходы (30 дн)</div>
          <div class="h3 font-weight-bold mt-2">{{ fmt(kpis[1]?.value) }} ₽</div>
          <div class="row justify-content-left g-2">
            <div class="col-auto small mt-1">Реклама: {{ fmt(kpis[1]?.sub1) }} ₽</div>
            <div class="col-auto small mt-1">Кешбэк: {{ fmt(kpis[1]?.sub2) }} ₽</div>
          </div>
        </div>
      </div>
      <div class="col-md-3 col-sm-6">
        <div class="card shadow-sm border-0 h-100 p-3 text-center" :class="kpis[2]?.value < 0 ? 'bg-danger text-white' : 'bg-light text-dark'">
          <div class="small font-weight-bold">Итого к оплате (30 дн)</div>
          <div class="h3 font-weight-bold mt-2 text-info">{{ fmt(kpis[2]?.value) }} ₽</div>
          <div class="row justify-content-left g-2">
            <div class="col-auto small text-danger mt-1">НДС: {{ fmt(kpis[2]?.sub1) }} ₽</div>
            <div class="col-auto small text-danger mt-1">Себ-сть: {{ fmt(kpis[2]?.sub2) }} ₽</div>
          </div>
        </div>
      </div>
      <div class="col-md-3 col-sm-6">
        <div class="card shadow-sm border-0 bg-light text-dark h-100 p-3 text-center">
          <div class=" small font-weight-bold">Маржа (30 дн)</div>
          <div class="h3 font-weight-bold mt-2 text-success">{{ fmt(kpis[3]?.value) }} ₽</div>
        </div>
      </div>
    </div>
    <div class="card shadow-sm border-0 mb-4">
      <div class="card-body p-2">
        <VChart :option="chartOption" autoresize style="height:340px" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const { data } = useQuery({ queryKey: ['top-metrics'], queryFn: dashboardApi.topMetrics })

const kpis = computed(() => {
  const d = (data.value as any)?.kpi45Data; if(!d) return [{},{},{},{}] as any
  return [
    {value:d.total_sales_rub, sub1:d.total_return_rub, sub2:d.total_orders_cnt},
    {value:d.total_expenses, sub1:d.total_adv, sub2:d.total_cashback},
    {value:d.total_profit_rub, sub1:d.total_nds, sub2:d.total_cost},
    {value:d.clean_margin},
  ]
})
const chartOption = computed(()=>{
  const raw = (data.value as any)?.chart45Data || []
  if(!raw.length) return {}
  return {
    tooltip:{trigger:'axis'},
    legend:{data:['Расходы','НДС','Себестоимость','Налог на прибыль','Маржа'], bottom:0, left:'center', itemWidth:12, itemHeight:12, textStyle:{fontSize:11, fontFamily:'"Segoe UI",Roboto,Helvetica,Arial,sans-serif'}},
    grid:{left:50, right:10, top:20, bottom:40, containLabel:true},
    xAxis:{type:'category', data: raw.map((r:any)=> { const d=new Date(r.date); return `${String(d.getDate()).padStart(2,'0')} ${d.toLocaleString('ru-RU',{month:'short'})}.`; }), axisLabel:{fontSize:11, fontFamily:'"Segoe UI",Roboto,Helvetica,Arial,sans-serif', rotate:-45}},
    yAxis:{type:'value', axisLabel:{fontSize:11}},
    series:[
      {name:'Расходы', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.total_expenses)), itemStyle:{color:'#b2c0d2'}},
      {name:'НДС', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.total_nds)), itemStyle:{color:'#dcdcdc'}},
      {name:'Себестоимость', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.total_cost)), itemStyle:{color:'#FF9E1B'}},
      {name:'Налог на прибыль', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.tax_amount)), itemStyle:{color:'#ff6b6b'}},
      {name:'Маржа', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.clean_margin)), itemStyle:{color:'#2ec4b6'}},
    ]
  }
})
const fmt = (v:any) => new Intl.NumberFormat('ru-RU').format(Math.round(v||0))
</script>
