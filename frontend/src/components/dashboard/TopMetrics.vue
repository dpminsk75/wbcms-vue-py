<template>
  <div v-if="busy || hasData || balHas || isError" class="page-dashboard__top-metrics">
    <div style="margin-bottom:8px">
      <span style="font-size:20px; font-weight:700; color:#111827">Показатели</span>
    </div>
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
        <div class="d-flex flex-column gap-3 h-100">
          <div class="card shadow-sm border-0 bg-light text-dark p-3 text-center page-dashboard__margin-card">
            <div class="page-dashboard__metric-head page-dashboard__metric-head--light">
              <span>Маржа (30 дн)</span>
              <span class="page-dashboard__metric-pct page-dashboard__metric-pct--light">{{ pctStr(margin) }}</span>
            </div>
            <div class="h3 font-weight-bold mt-2 text-success">{{ fmt(margin) }} ₽</div>
          </div>
          <div class="card shadow-sm border-0 bg-white p-3 page-dashboard__balance">
            <div class="page-dashboard__metric-head">
              <span>Баланс</span>
              <i v-if="balHas" :class="showBal ? 'bi bi-eye-slash' : 'bi bi-eye'" class="page-dashboard__balance-eye" title="Показать/скрыть суммы" @click="showBal = !showBal" />
            </div>
            <div class="page-dashboard__metric-total">{{ balMain }}</div>
            <ul class="page-dashboard__metric-rows">
              <li v-if="balSub" class="page-dashboard__metric-row">
                <span class="page-dashboard__metric-label">Можно вывести</span>
                <span class="page-dashboard__metric-val">{{ balSub }}</span>
              </li>
              <li v-if="!balHas" class="page-dashboard__metric-row">
                <span class="page-dashboard__metric-label">Нет данных — дождитесь среза cron</span>
              </li>
            </ul>
            <div v-if="balFetched" class="page-dashboard__balance-ts">Обновлено {{ balFetched }}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="card shadow-sm border-0 mb-4">
      <div class="card-body p-2">
        <VChart :option="chartOption" autoresize class="page-dashboard__metric-chart page-dashboard__metric-chart--click" @click="onChartClick" />
        <div class="page-dashboard__day-hint">Нажмите на столбец дня, чтобы открыть детализацию за этот день</div>
      </div>
    </div>
    <div v-if="selDate" class="page-dashboard__day-overlay" @mousedown.self="selDate = null">
      <div class="page-dashboard__day-box" role="dialog" aria-modal="true" aria-label="Показатели за день">
        <div class="page-dashboard__day-head">
          <span class="page-dashboard__day-title">Показатели за {{ dayLabel }}</span>
          <button class="btn btn-sm btn-link page-dashboard__day-close" title="Закрыть" @click="selDate = null">✕</button>
        </div>
        <div v-if="dayBusy" class="page-dashboard__day-state"><span class="spinner-border spinner-border-sm me-2"></span> Загрузка дня…</div>
        <div v-else-if="dayIsError" class="alert alert-warning page-dashboard__day-state">Не удалось загрузить день {{ dayLabel }}</div>
        <div v-else-if="dayView && dayEmpty" class="alert alert-info page-dashboard__day-state">За {{ dayLabel }} данных нет (agg_daily_summary пуст)</div>
        <div v-else-if="dayView" class="row g-3">
          <div class="col-md-4 col-sm-6">
            <div class="card shadow-sm border-0 bg-light text-dark h-100 p-3 page-dashboard__metric">
              <div class="page-dashboard__metric-head">
                <span>Выручка ({{ dayLabel }})</span>
                <span class="page-dashboard__metric-pct">100,0%</span>
              </div>
              <div class="page-dashboard__metric-total page-dashboard__metric-total--sales">{{ fmt(dayView.sales) }} ₽</div>
              <div class="page-dashboard__metric-bar">
                <div class="page-dashboard__metric-seg" :style="{ width: dayView.salesBar.net + '%', background: '#3aa876' }" />
                <div class="page-dashboard__metric-seg" :style="{ width: dayView.salesBar.ret + '%', background: '#e0525c' }" />
              </div>
              <ul class="page-dashboard__metric-rows">
                <li v-for="r in dayView.salesRows" :key="r.label" class="page-dashboard__metric-row">
                  <span v-if="r.color" class="page-dashboard__metric-dot" :style="{ background: r.color }" />
                  <span class="page-dashboard__metric-label">{{ r.label }}</span>
                  <span v-if="r.qty" class="page-dashboard__metric-qty">{{ r.qty }}</span>
                  <span class="page-dashboard__metric-val">{{ r.val }}</span>
                  <span v-if="r.pct" class="page-dashboard__metric-rowpct">{{ r.pct }}</span>
                </li>
              </ul>
            </div>
          </div>
          <div class="col-md-4 col-sm-6">
            <div class="card shadow-sm border-0 bg-light text-dark h-100 p-3 page-dashboard__metric">
              <div class="page-dashboard__metric-head">
                <span>Все расходы ({{ dayLabel }})</span>
                <span class="page-dashboard__metric-pct">{{ dayView.headExp }}</span>
              </div>
              <div class="page-dashboard__metric-total page-dashboard__metric-total--expenses">{{ fmt(dayView.expenses) }} ₽</div>
              <div class="page-dashboard__metric-bar">
                <div v-for="s in dayView.expSegs" :key="s.label" class="page-dashboard__metric-seg" :style="{ width: s.w + '%', background: s.color }" />
              </div>
              <ul class="page-dashboard__metric-rows">
                <li v-for="r in dayView.expRows" :key="r.label" class="page-dashboard__metric-row">
                  <span class="page-dashboard__metric-dot" :style="{ background: r.color }" />
                  <span class="page-dashboard__metric-label">{{ r.label }}</span>
                  <button v-if="(r as any).popup" class="page-dashboard__metric-val page-dashboard__exp-link" :title="'Детализация: ' + r.label" @click="openDayPop((r as any).popup)">{{ r.val }}</button>
                  <span v-else class="page-dashboard__metric-val">{{ r.val }}</span>
                  <span class="page-dashboard__metric-rowpct">{{ r.pct }}</span>
                </li>
              </ul>
            </div>
          </div>
          <div class="col-md-4 col-sm-6">
            <div class="card shadow-sm border-0 h-100 p-3 page-dashboard__metric" :class="dayView.netProfit < 0 ? 'bg-danger text-white' : 'bg-light text-dark'">
              <div class="page-dashboard__metric-head">
                <span>Итого к оплате ({{ dayLabel }})</span>
                <span class="page-dashboard__metric-pct">{{ dayView.headPay }}</span>
              </div>
              <div class="page-dashboard__metric-total text-info">{{ fmt(dayView.netProfit) }} ₽</div>
              <div class="page-dashboard__metric-bar">
                <div v-for="s in dayView.paySegs" :key="s.label" class="page-dashboard__metric-seg" :style="{ width: s.w + '%', background: s.color }" />
              </div>
              <ul class="page-dashboard__metric-rows">
                <li v-for="r in dayView.payRows" :key="r.label" class="page-dashboard__metric-row">
                  <span class="page-dashboard__metric-dot" :style="{ background: r.color }" />
                  <span class="page-dashboard__metric-label">{{ r.label }}</span>
                  <span class="page-dashboard__metric-val">{{ r.val }}</span>
                  <span class="page-dashboard__metric-rowpct">{{ r.pct }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
        <div v-if="dayView && !dayEmpty" class="page-dashboard__day-links">
          <span class="page-dashboard__day-links-cap">Детализация:</span>
          <button v-if="dayView.penalty" class="page-dashboard__exp-link" title="Детализация штрафов" @click="openDayPop('shf')">Штрафы</button>
          <button v-if="dayView.deduction" class="page-dashboard__exp-link" title="Детализация удержаний" @click="openDayPop('udr')">Удержания</button>
          <button class="page-dashboard__exp-link" title="Детализация отзывов" @click="openDayPop('feedback')">Отзывы</button>
          <button v-if="dayView.acceptance" class="page-dashboard__exp-link" title="Детализация приёмки" @click="openDayPop('acceptance')">Приёмка</button>
        </div>
      </div>
    </div>
    <FinancePopup v-if="finPop" :kind="finPop.kind" :date-from="finPop.dateFrom" :date-to="finPop.dateTo" @close="finPop = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import VChart from 'vue-echarts'
import FinancePopup, { type FinancePopupKind } from './FinancePopup.vue'
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
const acquiring = computed(() => num(kpi.value.total_acquiring_fee))
const delivery = computed(() => num(kpi.value.total_delivery))
const adv = computed(() => num(kpi.value.total_adv))
const storage = computed(() => num(kpi.value.total_storage_fee))
const cashback = computed(() => num(kpi.value.total_cashback))
const restExp = computed(() => expenses.value - commission.value - acquiring.value - delivery.value - adv.value - storage.value - cashback.value)
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
  { label: 'Эквайринг', w: wExp(acquiring.value), color: '#3b82f6' },
  { label: 'Логистика', w: wExp(delivery.value), color: '#5bc0de' },
  { label: 'Реклама', w: wExp(adv.value), color: '#8a2be0' },
  { label: 'Хранение', w: wExp(storage.value), color: '#e3c766' },
  { label: 'Кешбэк', w: wExp(cashback.value), color: '#e0525c' },
  { label: 'Остальные', w: wExp(restExp.value), color: '#9aa0a8' },
])
const expRows = computed(() => [
  { label: 'Комиссия', val: `${fmt(commission.value)} ₽`, pct: pctStr(commission.value), color: '#f5a623' },
  { label: 'Эквайринг', val: `${fmt(acquiring.value)} ₽`, pct: pctStr(acquiring.value), color: '#3b82f6' },
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

// Баланс ЛК WB: последний срез крона (wb_finance_balance), вид как виджет портала.
// retry:1 — таблицы/крона может ещё не быть, не спамим 404.
const { data: balData } = useQuery({ queryKey: computed(() => ['finance-balance', auth.companyId] as const), queryFn: dashboardApi.financeBalance, retry: 1 } as any)
const balHas = computed(() => !!(balData.value as any)?.has_data)
const showBal = ref(true)
const fmt2 = (v:any) => new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v)||0)
const balMain = computed(() => {
  if (!balHas.value) return '—'
  return showBal.value ? `${fmt2((balData.value as any).current)} ₽` : '••• ₽'
})
const balSub = computed(() => {
  if (!balHas.value || !showBal.value) return ''
  return `${fmt2((balData.value as any).for_withdraw)} ₽`
})
const balFetched = computed(() => {
  const f = (balData.value as any)?.fetched_at
  if (!f) return ''
  const d = new Date(f)
  return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
})

// Попап дня: клик по столбцу графика открывает те же 3 карточки за один день,
// в заголовках вместо «(30 дн)» — дата дня. Данные — GET /api/dashboard/top-metrics-day.
const selDate = ref<string | null>(null)
const dayLabel = computed(() => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(selDate.value || '')
  return m ? `${m[3]}.${m[2]}.${m[1]}` : (selDate.value || '')
})
const onChartClick = (p: any) => {
  const idx = p?.dataIndex
  if (idx === undefined || idx === null) return
  const raw = (((data.value as any)?.chart45Data || []) as any[])
  const row = raw[idx]
  if (!row) return
  const iso = String((row as any).date ?? '').slice(0, 10)
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) selDate.value = iso
}
const { data: dayData, isLoading: dayLoading, isFetching: dayFetching, isError: dayError } = useQuery({
  queryKey: computed(() => ['top-metrics-day', auth.companyId, selDate.value] as const),
  queryFn: () => dashboardApi.topMetricsDay(selDate.value as string),
  enabled: computed(() => !!selDate.value),
} as any)
const dayKpi = computed(() => ((dayData.value as any)?.kpi || null) as any)
const dayBusy = computed(() => dayLoading.value || dayFetching.value)
const dayIsError = computed(() => !!dayError.value)
// Формулы 1в1 с 30д-блоком выше, но от kpi одного дня.
const dayView = computed(() => {
  const k = dayKpi.value
  if (!k) return null
  const n = (v: any) => Number(v) || 0
  const sales = n(k.total_sales_rub)
  const dPct1 = (x: number) => new Intl.NumberFormat('ru-RU',{minimumFractionDigits:1,maximumFractionDigits:1}).format(x)
  const dPctStr = (v: number) => (!sales ? '0,0%' : `${dPct1((v / sales) * 100)}%`)
  const ret = n(k.total_return_rub)
  const orders = n(k.total_orders_cnt)
  const salesQnt = n(k.total_sales_qnt)
  const retQnt = n(k.total_return_qnt)
  const netProfit = n(k.total_profit_rub)
  const ndsv = n(k.total_nds)
  const costv = n(k.total_cost)
  const taxv = n(k.tax_amount)
  const marginv = n(k.clean_margin)
  const expenses = n(k.total_expenses)
  const commission = n(k.total_commission)
  const acquiring = n(k.total_acquiring_fee)
  const delivery = n(k.total_delivery)
  const advv = n(k.total_adv)
  const storage = n(k.total_storage_fee)
  const cashback = n(k.total_cashback)
  const restExp = expenses - commission - acquiring - delivery - advv - storage - cashback
  const penalty = n(k.total_penalty)
  const deduction = n(k.total_deduction)
  const acceptance = n(k.total_acceptance)
  const avgCheck = orders ? sales / orders : 0
  const retail = n(k.total_retail_amount)
  const sppAvg = n(k.total_spp_avg)
  const headBase = expenses + netProfit
  const headP = (v: number) => (!headBase ? '0,0%' : `${dPct1((v / headBase) * 100)}%`)
  const wE = (v: number) => (expenses ? Math.max(0, (v / expenses) * 100) : 0)
  const wP = (v: number) => (netProfit ? Math.max(0, (v / netProfit) * 100) : 0)
  return {
    sales, ret, orders, expenses, netProfit, penalty, deduction, acceptance,
    salesBar: !sales ? { net: 0, ret: 0 } : { net: Math.max(0, ((sales - ret) / sales) * 100), ret: Math.max(0, (ret / sales) * 100) },
    salesRows: [
      { label: 'Выкупы', qty: `${fmt(salesQnt)} шт`, val: `${fmt(sales)} ₽`, pct: '100,0%', color: '#3aa876' },
      { label: 'Возвраты', qty: `${fmt(retQnt)} шт`, val: `${fmt(ret)} ₽`, pct: dPctStr(ret), color: '#e0525c' },
      { label: 'Заказы', qty: `${fmt(orders)} шт`, val: `${fmt(retail)} ₽`, pct: '', color: '' },
      { label: 'К оплате на Р/С', qty: '', val: `${fmt(netProfit)} ₽`, pct: '', color: '' },
      { label: 'Средний чек', qty: '', val: `${fmt(avgCheck)} ₽`, pct: '', color: '' },
      { label: 'СПП', qty: '', val: sppFmt(sppAvg), pct: '', color: '' },
    ],
    expSegs: [
      { label: 'Комиссия', w: wE(commission), color: '#f5a623' },
      { label: 'Эквайринг', w: wE(acquiring), color: '#3b82f6' },
      { label: 'Логистика', w: wE(delivery), color: '#5bc0de' },
      { label: 'Реклама', w: wE(advv), color: '#8a2be0' },
      { label: 'Хранение', w: wE(storage), color: '#e3c766' },
      { label: 'Кешбэк', w: wE(cashback), color: '#e0525c' },
      { label: 'Остальные', w: wE(restExp), color: '#9aa0a8' },
    ],
    expRows: [
      { label: 'Комиссия', val: `${fmt(commission)} ₽`, pct: dPctStr(commission), color: '#f5a623' },
      { label: 'Эквайринг', val: `${fmt(acquiring)} ₽`, pct: dPctStr(acquiring), color: '#3b82f6' },
      { label: 'Логистика', val: `${fmt(delivery)} ₽`, pct: dPctStr(delivery), color: '#5bc0de' },
      { label: 'Реклама', val: `${fmt(advv)} ₽`, pct: dPctStr(advv), color: '#8a2be0', popup: 'adv' },
      { label: 'Хранение', val: `${fmt(storage)} ₽`, pct: dPctStr(storage), color: '#e3c766', popup: 'storage' },
      { label: 'Кешбэк', val: `${fmt(cashback)} ₽`, pct: dPctStr(cashback), color: '#e0525c' },
      { label: 'Остальные', val: `${fmt(restExp)} ₽`, pct: dPctStr(restExp), color: '#9aa0a8' },
    ],
    paySegs: [
      { label: 'Себестоимость', w: wP(costv), color: '#f0b429' },
      { label: 'НДС', w: wP(ndsv), color: '#f57f17' },
      { label: 'Налог на прибыль', w: wP(taxv), color: '#e0525c' },
      { label: 'Маржа', w: wP(marginv), color: '#1e9e7c' },
    ],
    payRows: [
      { label: 'Себестоимость', val: `${fmt(costv)} ₽`, pct: dPctStr(costv), color: '#f0b429' },
      { label: 'НДС', val: `${fmt(ndsv)} ₽`, pct: dPctStr(ndsv), color: '#f57f17' },
      { label: 'Налог на прибыль', val: `${fmt(taxv)} ₽`, pct: dPctStr(taxv), color: '#e0525c' },
      { label: 'Маржа', val: `${fmt(marginv)} ₽`, pct: dPctStr(marginv), color: '#1e9e7c' },
    ],
    headExp: headP(expenses),
    headPay: headP(netProfit),
  }
})
const dayEmpty = computed(() => {
  const v = dayView.value
  return !!v && !v.sales && !v.expenses && !v.netProfit && !v.orders
})
const onEsc = (e: KeyboardEvent) => {
  if (e.key !== 'Escape') return
  if (finPop.value) return // внутренний попап детализации закрывается сам
  selDate.value = null
}
onMounted(() => window.addEventListener('keydown', onEsc))
onUnmounted(() => window.removeEventListener('keydown', onEsc))

// Внутренний попап детализации затрат за выбранный день (период — один день).
const finPop = ref<{ kind: FinancePopupKind, dateFrom: string, dateTo: string } | null>(null)
const openDayPop = (kind: FinancePopupKind) => {
  if (!selDate.value) return
  finPop.value = { kind, dateFrom: selDate.value, dateTo: selDate.value }
}
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
.page-dashboard__metric-chart--click { cursor: pointer; }
.page-dashboard__day-hint { font-size: 11px; color: #888; text-align: center; padding: 2px 0 4px; }
.page-dashboard__day-overlay { position: fixed; inset: 0; z-index: 1050; background: rgba(17,24,39,.5); display: flex; align-items: flex-start; justify-content: center; padding: 40px 16px; overflow: auto; }
.page-dashboard__day-box { background: #fff; border-radius: 14px; max-width: 1120px; width: 100%; box-shadow: 0 12px 40px rgba(0,0,0,.28); padding: 16px 18px 18px; }
.page-dashboard__day-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.page-dashboard__day-title { font-size: 16px; font-weight: 700; color: #111827; }
.page-dashboard__day-close { text-decoration: none; font-size: 14px; }
.page-dashboard__day-state { margin: 0; }
.page-dashboard__day-links { display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; margin-top: 12px; font-size: 12px; }
.page-dashboard__day-links-cap { color: #888; }
.page-dashboard__margin-card { flex: 1 1 auto; display: flex; flex-direction: column; justify-content: center; }
.page-dashboard__balance-eye { cursor: pointer; color: #888; font-size: 12px; }
.page-dashboard__balance-ts { font-size: 11px; color: #999; margin-top: 2px; }
</style>
