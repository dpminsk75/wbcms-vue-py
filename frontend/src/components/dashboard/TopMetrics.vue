<template>
  <div v-if="busy || hasData || isError" class="page-dashboard__top-metrics">
    <div class="row g-3 mb-4">
      <div class="col-md-3 col-sm-6">
        <div class="card shadow-sm border-0 bg-light text-dark h-100 p-3 page-dashboard__metric">
          <div class="page-dashboard__metric-head">
            <span>Выручка (30 дн)</span>
            <span class="page-dashboard__metric-pct">100,0%</span>
          </div>
          <div class="page-dashboard__metric-total page-dashboard__metric-total--sales">{{ fmt(sales) }} ₽</div>
          <div class="page-dashboard__metric-bar">
            <div class="page-dashboard__metric-seg" :style="{ width: salesBar.net + '%', background: '#3aa876' }" />
            <div class="page-dashboard__metric-seg" :style="{ width: salesBar.ret + '%', background: '#e0525c' }" />
          </div>
          <ul class="page-dashboard__metric-rows">
            <li v-for="r in salesRows" :key="r.label" class="page-dashboard__metric-row">
              <span v-if="r.color" class="page-dashboard__metric-dot" :style="{ background: r.color }" />
              <span class="page-dashboard__metric-label">{{ r.label }}</span>
              <span v-if="r.qty" class="page-dashboard__metric-qty">{{ r.qty }}</span>
              <span class="page-dashboard__metric-val">{{ r.val }}</span>
              <span v-if="r.pct" class="page-dashboard__metric-rowpct">{{ r.pct }}</span>
            </li>
          </ul>
        </div>
      </div>
      <div class="col-md-3 col-sm-6">
        <div class="card shadow-sm border-0 bg-light text-dark h-100 p-3 page-dashboard__metric">
          <div class="page-dashboard__metric-head">
            <span>Все расходы (30 дн)</span>
            <span class="page-dashboard__metric-pct">{{ headPct(expenses) }}</span>
          </div>
          <div class="page-dashboard__metric-total page-dashboard__metric-total--expenses">{{ fmt(expenses) }} ₽</div>
          <div class="page-dashboard__metric-bar">
            <div v-for="s in expSegs" :key="s.label" class="page-dashboard__metric-seg" :style="{ width: s.w + '%', background: s.color }" />
          </div>
          <ul class="page-dashboard__metric-rows">
            <li v-for="r in expRows" :key="r.label" class="page-dashboard__metric-row">
              <span class="page-dashboard__metric-dot" :style="{ background: r.color }" />
              <span class="page-dashboard__metric-label">{{ r.label }}</span>
              <span class="page-dashboard__metric-val">{{ r.val }}</span>
              <span class="page-dashboard__metric-rowpct">{{ r.pct }}</span>
            </li>
          </ul>
        </div>
      </div>
      <div class="col-md-3 col-sm-6">
        <div class="card shadow-sm border-0 h-100 p-3 page-dashboard__metric" :class="netProfit < 0 ? 'bg-danger text-white' : 'bg-light text-dark'">
          <div class="page-dashboard__metric-head">
            <span>Итого к оплате (30 дн)</span>
            <span class="page-dashboard__metric-pct">{{ headPct(netProfit) }}</span>
          </div>
          <div class="page-dashboard__metric-total text-info">{{ fmt(netProfit) }} ₽</div>
          <div class="page-dashboard__metric-bar">
            <div v-for="s in paySegs" :key="s.label" class="page-dashboard__metric-seg" :style="{ width: s.w + '%', background: s.color }" />
          </div>
          <ul class="page-dashboard__metric-rows">
            <li v-for="r in payRows" :key="r.label" class="page-dashboard__metric-row">
              <span class="page-dashboard__metric-dot" :style="{ background: r.color }" />
              <span class="page-dashboard__metric-label">{{ r.label }}</span>
              <span class="page-dashboard__metric-val">{{ r.val }}</span>
              <span class="page-dashboard__metric-rowpct">{{ r.pct }}</span>
            </li>
          </ul>
        </div>
      </div>
      <div class="col-md-3 col-sm-6">
        <div class="card shadow-sm border-0 bg-light text-dark h-100 p-3 text-center">
          <div class="page-dashboard__metric-head page-dashboard__metric-head--light">
            <span>Маржа (30 дн)</span>
            <span class="page-dashboard__metric-pct page-dashboard__metric-pct--light">{{ pctStr(margin) }}</span>
          </div>
          <div class="h3 font-weight-bold mt-2 text-success">{{ fmt(margin) }} ₽</div>
        </div>
      </div>
    </div>
    <div class="card shadow-sm border-0 mb-4">
      <div class="card-body p-2">
        <VChart :option="chartOption" autoresize class="page-dashboard__metric-chart" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const auth = useAuthStore()
// companyId в ключе: смена компании обязана дёрнуть refetch, иначе покажем чужой кэш
const { data, isLoading, isFetching, isError } = useQuery({ queryKey: computed(() => ['top-metrics', auth.companyId] as const), queryFn: dashboardApi.topMetrics })

// пустой блок: нет точек за 30д — прячемся, Dashboard покажет заглушку если все пустые
const report = inject<(n:string,h:boolean)=>void>('dashReport', ()=>{})
const hasData = computed(() => (((data.value as any)?.chart45Data || []) as any[]).length > 0)
const busy = computed(() => isLoading.value || isFetching.value)
watchEffect(() => { if (!busy.value) report('top-metrics', hasData.value || !!isError.value) })

const kpi = computed(() => ((data.value as any)?.kpi45Data || {}) as any)
const num = (v: any) => Number(v) || 0
// Итоговые цифры — как сейчас: headline выручки = SUM(amount), без нетто-пересчёта
const sales = computed(() => num(kpi.value.total_sales_rub))
const ret = computed(() => num(kpi.value.total_return_rub))
const orders = computed(() => num(kpi.value.total_orders_cnt))
const salesQnt = computed(() => num(kpi.value.total_sales_qnt))
const retQnt = computed(() => num(kpi.value.total_return_qnt))
const netProfit = computed(() => num(kpi.value.total_profit_rub))
const nds = computed(() => num(kpi.value.total_nds))
const cost = computed(() => num(kpi.value.total_cost))
const tax = computed(() => num(kpi.value.tax_amount))
const margin = computed(() => num(kpi.value.clean_margin))
const expenses = computed(() => num(kpi.value.total_expenses))
const commission = computed(() => num(kpi.value.total_commission))
const delivery = computed(() => num(kpi.value.total_delivery))
const adv = computed(() => num(kpi.value.total_adv))
const storage = computed(() => num(kpi.value.total_storage_fee))
const cashback = computed(() => num(kpi.value.total_cashback))
const restExp = computed(() => expenses.value - commission.value - delivery.value - adv.value - storage.value - cashback.value)
const avgCheck = computed(() => (orders.value ? sales.value / orders.value : 0))
const retail = computed(() => num(kpi.value.total_retail_amount))
const sppAvg = computed(() => num(kpi.value.total_spp_avg))

const pctStr = (v: number) => {
  if (!sales.value) return '0,0%'
  return `${pct1((v / sales.value) * 100)}%`
}
// Доли у заголовков блоков 2–3 — от базы «расходы + к оплате» (в сумме 100%).
// От выручки нельзя: в legacy-формуле total_expenses дважды считает f_otziv/f_adv
// (они уже сидят внутри f_deduction), а net_profit уже за вычетом возвратов.
const pct1 = (x: number) => new Intl.NumberFormat('ru-RU',{minimumFractionDigits:1,maximumFractionDigits:1}).format(x)
const headBase = computed(() => expenses.value + netProfit.value)
const headPct = (v: number) => {
  if (!headBase.value) return '0,0%'
  return `${pct1((v / headBase.value) * 100)}%`
}
const salesBar = computed(() => {
  if (!sales.value) return { net: 0, ret: 0 }
  return { net: Math.max(0, ((sales.value - ret.value) / sales.value) * 100), ret: Math.max(0, (ret.value / sales.value) * 100) }
})
const salesRows = computed(() => [
  { label: 'Выкупы', qty: `${fmt(salesQnt.value)} шт`, val: `${fmt(sales.value)} ₽`, pct: '100,0%', color: '#3aa876' },
  { label: 'Возвраты', qty: `${fmt(retQnt.value)} шт`, val: `${fmt(ret.value)} ₽`, pct: pctStr(ret.value), color: '#e0525c' },
  { label: 'Заказы', qty: `${fmt(orders.value)} шт`, val: `${fmt(retail.value)} ₽`, pct: '', color: '' },
  { label: 'К оплате на Р/С', qty: '', val: `${fmt(netProfit.value)} ₽`, pct: '', color: '' },
  { label: 'Средний чек', qty: '', val: `${fmt(avgCheck.value)} ₽`, pct: '', color: '' },
  { label: 'СПП', qty: '', val: sppFmt(sppAvg.value), pct: '', color: '' },
])
const expSegs = computed(() => [
  { label: 'Комиссия', w: wExp(commission.value), color: '#f5a623' },
  { label: 'Логистика', w: wExp(delivery.value), color: '#5bc0de' },
  { label: 'Реклама', w: wExp(adv.value), color: '#8a2be0' },
  { label: 'Хранение', w: wExp(storage.value), color: '#e3c766' },
  { label: 'Кешбэк', w: wExp(cashback.value), color: '#e0525c' },
  { label: 'Остальные', w: wExp(restExp.value), color: '#9aa0a8' },
])
const expRows = computed(() => [
  { label: 'Комиссия', val: `${fmt(commission.value)} ₽`, pct: pctStr(commission.value), color: '#f5a623' },
  { label: 'Логистика', val: `${fmt(delivery.value)} ₽`, pct: pctStr(delivery.value), color: '#5bc0de' },
  { label: 'Реклама', val: `${fmt(adv.value)} ₽`, pct: pctStr(adv.value), color: '#8a2be0' },
  { label: 'Хранение', val: `${fmt(storage.value)} ₽`, pct: pctStr(storage.value), color: '#e3c766' },
  { label: 'Кешбэк', val: `${fmt(cashback.value)} ₽`, pct: pctStr(cashback.value), color: '#e0525c' },
  { label: 'Остальные', val: `${fmt(restExp.value)} ₽`, pct: pctStr(restExp.value), color: '#9aa0a8' },
])
// Полосы — в масштабе своего headline (сегменты в сумме = 100%),
// чтобы пустой остаток трека не выглядел лишним сегментом. Проценты в строках — от выручки.
const wExp = (v: number) => (expenses.value ? Math.max(0, (v / expenses.value) * 100) : 0)
const wPay = (v: number) => (netProfit.value ? Math.max(0, (v / netProfit.value) * 100) : 0)
const paySegs = computed(() => [
  { label: 'Себестоимость', w: wPay(cost.value), color: '#f0b429' },
  { label: 'НДС', w: wPay(nds.value), color: '#f57f17' },
  { label: 'Налог на прибыль', w: wPay(tax.value), color: '#e0525c' },
  { label: 'Маржа', w: wPay(margin.value), color: '#1e9e7c' },
])
const payRows = computed(() => [
  { label: 'Себестоимость', val: `${fmt(cost.value)} ₽`, pct: pctStr(cost.value), color: '#f0b429' },
  { label: 'НДС', val: `${fmt(nds.value)} ₽`, pct: pctStr(nds.value), color: '#f57f17' },
  { label: 'Налог на прибыль', val: `${fmt(tax.value)} ₽`, pct: pctStr(tax.value), color: '#e0525c' },
  { label: 'Маржа', val: `${fmt(margin.value)} ₽`, pct: pctStr(margin.value), color: '#1e9e7c' },
])
const chartOption = computed(()=>{
  const raw = (data.value as any)?.chart45Data || []
  if(!raw.length) return {}
  return {
    tooltip:{trigger:'axis', backgroundColor:'rgba(33,37,41,.92)', borderWidth:0, textStyle:{color:'#fff', fontSize:12}, valueFormatter:(v:any)=>`${new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))} ₽`},
    legend:{data:['Расходы','НДС','Себестоимость','Налог на прибыль','Маржа'], bottom:0, left:'center', icon:'roundRect', itemWidth:12, itemHeight:12, textStyle:{fontSize:11, fontFamily:'"Segoe UI",Roboto,Helvetica,Arial,sans-serif'}},
    grid:{left:8, right:16, top:10, bottom:40, containLabel:true},
    xAxis:{type:'category', data: raw.map((r:any)=> { const d=new Date(r.date); return `${String(d.getMonth() + 1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }), axisLine:{lineStyle:{color:'#dee2e6'}}, axisTick:{show:false}, axisLabel:{fontSize:11, color:'#888', fontFamily:'"Segoe UI",Roboto,Helvetica,Arial,sans-serif', interval:2}},
    yAxis:{type:'value', splitLine:{lineStyle:{color:'#eef1f4'}}, axisLabel:{fontSize:11, color:'#888', formatter:(v:number)=>v>=1000?`${new Intl.NumberFormat('ru-RU').format(v/1000)} тыс.`:String(v)}},
    series:[
      {name:'Расходы', type:'bar', stack:'total', barWidth:'55%', data: raw.map((r:any)=> Math.round(r.total_expenses)), itemStyle:{color:'#b2c0d2'}},
      {name:'НДС', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.total_nds)), itemStyle:{color:'#dcdcdc'}},
      {name:'Себестоимость', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.total_cost)), itemStyle:{color:'#FF9E1B'}},
      {name:'Налог на прибыль', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.tax_amount)), itemStyle:{color:'#ff6b6b'}},
      {name:'Маржа', type:'bar', stack:'total', data: raw.map((r:any)=> Math.round(r.clean_margin)), itemStyle:{color:'#2ec4b6', borderRadius:[4,4,0,0]}},
    ]
  }
})
const fmt = (v:any) => new Intl.NumberFormat('ru-RU').format(Math.round(v||0))
const sppFmt = (v:any) => `${new Intl.NumberFormat('ru-RU',{minimumFractionDigits:1,maximumFractionDigits:1}).format(Number(v)||0)}%`
</script>

<style scoped>
.page-dashboard__top-metrics { font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
.page-dashboard__metric-head { display: flex; justify-content: space-between; align-items: baseline; font-size: 13px; font-weight: 600; }
.page-dashboard__metric-head--light { color: rgba(255,255,255,.75); font-weight: 400; }
.page-dashboard__metric-pct { color: #888; font-weight: 400; }
.page-dashboard__metric-pct--light { color: #fff; opacity: .85; }
.page-dashboard__metric-total { font-size: 24px; font-weight: 700; margin: 4px 0 8px; }
.page-dashboard__metric-total--sales { color: #1e9e7c; }
.page-dashboard__metric-total--expenses { color: #d97a06; }
.page-dashboard__metric-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: #e9ecef; margin-bottom: 8px; }
.page-dashboard__metric-seg { height: 100%; }
.page-dashboard__metric-rows { list-style: none; margin: 0; padding: 0; font-size: 12px; }
.page-dashboard__metric-row { display: flex; align-items: center; gap: 6px; padding: 2px 0; }
.page-dashboard__metric-dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.page-dashboard__metric-label { flex: 1 1 auto; color: #555; }
.page-dashboard__metric-qty { color: #888; white-space: nowrap; }
.page-dashboard__metric-val { font-weight: 600; white-space: nowrap; }
.page-dashboard__metric-rowpct { color: #888; min-width: 36px; text-align: right; }
.page-dashboard__metric-chart { height: 340px; }
</style>
