<template>
  <section v-if="busy || hasData || isError" class="dsp-top">
    <h2 class="dsp-h2">Показатели</h2>

    <div class="grid-4">
      <!-- Выручка -->
      <div class="tile tile--1">
        <div class="dsp-metric">
          <div class="dsp-metric__head">
            <span>Выручка (30 дн)</span>
            <span class="dsp-metric__pct">100,0%</span>
          </div>
          <div class="dsp-metric__total dsp-metric__total--sales">{{ fmt(sales) }} ₽</div>
          <div class="dsp-metric__bar">
            <div class="dsp-metric__seg" :style="{ width: salesBar.net + '%', background: C.sales }" />
            <div class="dsp-metric__seg" :style="{ width: salesBar.ret + '%', background: C.return }" />
          </div>
          <ul class="dsp-metric__rows">
            <li v-for="r in salesRows" :key="r.label" class="dsp-metric__row">
              <span v-if="r.color" class="dsp-metric__dot" :style="{ background: r.color }" />
              <span class="dsp-metric__label">{{ r.label }}</span>
              <span v-if="r.qty" class="dsp-metric__qty">{{ r.qty }}</span>
              <span class="dsp-metric__val">{{ r.val }}</span>
              <span v-if="r.pct" class="dsp-metric__pctrow">{{ r.pct }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Все расходы -->
      <div class="tile tile--1">
        <div class="dsp-metric">
          <div class="dsp-metric__head">
            <span>Все расходы (30 дн)</span>
            <span class="dsp-metric__pct">{{ headPct(expenses) }}</span>
          </div>
          <div class="dsp-metric__total dsp-metric__total--expenses">{{ fmt(expenses) }} ₽</div>
          <div class="dsp-metric__bar">
            <div
              v-for="s in expSegs" :key="s.label" class="dsp-metric__seg"
              :style="{ width: s.w + '%', background: s.color }"
            />
          </div>
          <ul class="dsp-metric__rows">
            <li v-for="r in expRows" :key="r.label" class="dsp-metric__row">
              <span class="dsp-metric__dot" :style="{ background: r.color }" />
              <span class="dsp-metric__label">{{ r.label }}</span>
              <span class="dsp-metric__val">{{ r.val }}</span>
              <span v-if="r.pct" class="dsp-metric__pctrow">{{ r.pct }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Итого к оплате -->
      <div class="tile tile--1">
        <div class="dsp-metric">
          <div class="dsp-metric__head">
            <span>Итого к оплате (30 дн)</span>
            <span class="dsp-metric__pct">{{ headPct(netProfit) }}</span>
          </div>
          <div class="dsp-metric__total dsp-metric__total--pay">{{ fmt(netProfit) }} ₽</div>
          <div class="dsp-metric__bar">
            <div
              v-for="s in paySegs" :key="s.label" class="dsp-metric__seg"
              :style="{ width: s.w + '%', background: s.color }"
            />
          </div>
          <ul class="dsp-metric__rows">
            <li v-for="r in payRows" :key="r.label" class="dsp-metric__row">
              <span class="dsp-metric__dot" :style="{ background: r.color }" />
              <span class="dsp-metric__label">{{ r.label }}</span>
              <span class="dsp-metric__val">{{ r.val }}</span>
              <span v-if="r.pct" class="dsp-metric__pctrow">{{ r.pct }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Hero «Маржа» + баланс -->
      <div class="dsp-col4">
        <div class="tile tile--1 dsp-metric--hero">
          <div class="dsp-metric__head">
            <span>Маржа (30 дн)</span>
            <span class="dsp-metric__pct">{{ pctStr(margin) }}</span>
          </div>
          <div class="dsp-metric__total">{{ fmt(margin) }} ₽</div>
        </div>
        <div class="tile tile--1">
          <div class="dsp-metric__head">
            <span>Баланс</span>
            <span class="dsp-metric__pct" style="cursor: pointer" :title="showBal ? 'Скрыть суммы' : 'Показать суммы'" @click="showBal = !showBal">
              <i class="bi" :class="showBal ? 'bi-eye' : 'bi-eye-slash'"></i>
            </span>
          </div>
          <div class="dsp-metric__total">{{ balMain }}</div>
          <ul class="dsp-metric__rows">
            <li v-if="balSub" class="dsp-metric__row">
              <span class="dsp-metric__label">Можно вывести</span>
              <span class="dsp-metric__val">{{ balSub }}</span>
            </li>
            <li v-if="!balHas" class="dsp-metric__row">
              <span class="dsp-metric__label">Нет данных — дождитесь среза cron</span>
            </li>
          </ul>
          <div v-if="balFetched" class="dsp-metric__qty" style="margin-top: 5px">Обновлено {{ balFetched }}</div>
        </div>
      </div>
    </div>

    <!-- Структура по дням (стек 30 дней) — без шапки над графиком -->
    <div class="wb-panel" style="margin-top: 16px">
      <div class="wb-panel__bd wb-panel__bd--flush">
        <VChart :option="chartOption" autoresize class="dsp-chart" @click="onChartClick" />
        <div class="dsp-chart__hint">Нажмите на столбец дня, чтобы открыть детализацию за этот день</div>
      </div>
    </div>

    <!-- Модалка «Показатели за день» -->
    <div v-if="selDate" class="dsp-modal" @mousedown.self="selDate = null">
      <div class="dsp-modal__box" role="dialog" aria-modal="true" aria-label="Показатели за день">
        <div class="dsp-modal__head">
          <span class="dsp-modal__title">Показатели за {{ dayLabel }}</span>
          <button class="btn btn-sm btn--ghost" title="Закрыть" @click="selDate = null">✕</button>
        </div>

        <div v-if="dayBusy" class="dsp__empty">Загрузка дня…</div>
        <div v-else-if="dayIsError" class="dsp__empty dsp__empty--warn">Не удалось загрузить день {{ dayLabel }}</div>
        <div v-else-if="dayView && dayEmpty" class="dsp__empty">За {{ dayLabel }} данных нет</div>
        <div v-else-if="dayView" class="grid-3">
          <div class="tile tile--1">
            <div class="dsp-metric">
              <div class="dsp-metric__head">
                <span>Выручка ({{ dayLabel }})</span>
                <span class="dsp-metric__pct">100,0%</span>
              </div>
              <div class="dsp-metric__total dsp-metric__total--sales">{{ fmt(dayView.sales) }} ₽</div>
              <div class="dsp-metric__bar">
                <div class="dsp-metric__seg" :style="{ width: dayView.salesBar.net + '%', background: C.sales }" />
                <div class="dsp-metric__seg" :style="{ width: dayView.salesBar.ret + '%', background: C.return }" />
              </div>
              <ul class="dsp-metric__rows">
                <li v-for="r in dayView.salesRows" :key="r.label" class="dsp-metric__row">
                  <span v-if="r.color" class="dsp-metric__dot" :style="{ background: r.color }" />
                  <span class="dsp-metric__label">{{ r.label }}</span>
                  <span v-if="r.qty" class="dsp-metric__qty">{{ r.qty }}</span>
                  <span class="dsp-metric__val">{{ r.val }}</span>
                  <span v-if="r.pct" class="dsp-metric__pctrow">{{ r.pct }}</span>
                </li>
              </ul>
            </div>
          </div>

          <div class="tile tile--1">
            <div class="dsp-metric">
              <div class="dsp-metric__head">
                <span>Все расходы ({{ dayLabel }})</span>
                <span class="dsp-metric__pct">{{ dayView.headExp }}</span>
              </div>
              <div class="dsp-metric__total dsp-metric__total--expenses">{{ fmt(dayView.expenses) }} ₽</div>
              <div class="dsp-metric__bar">
                <div
                  v-for="s in dayView.expSegs" :key="s.label" class="dsp-metric__seg"
                  :style="{ width: s.w + '%', background: s.color }"
                />
              </div>
              <ul class="dsp-metric__rows">
                <li v-for="r in dayView.expRows" :key="r.label" class="dsp-metric__row">
                  <span class="dsp-metric__dot" :style="{ background: r.color }" />
                  <span class="dsp-metric__label">{{ r.label }}</span>
                  <button
                    v-if="r.popup" class="dsp-modal__link dsp-metric__val"
                    :title="'Детализация: ' + r.label" @click="openDayPop(r.popup)"
                  >{{ r.val }}</button>
                  <span v-else class="dsp-metric__val">{{ r.val }}</span>
                  <span v-if="r.pct" class="dsp-metric__pctrow">{{ r.pct }}</span>
                </li>
              </ul>
            </div>
          </div>

          <div class="tile tile--1">
            <div class="dsp-metric">
              <div class="dsp-metric__head">
                <span>Итого к оплате ({{ dayLabel }})</span>
                <span class="dsp-metric__pct">{{ dayView.headPay }}</span>
              </div>
              <div class="dsp-metric__total dsp-metric__total--pay">{{ fmt(dayView.netProfit) }} ₽</div>
              <div class="dsp-metric__bar">
                <div
                  v-for="s in dayView.paySegs" :key="s.label" class="dsp-metric__seg"
                  :style="{ width: s.w + '%', background: s.color }"
                />
              </div>
              <ul class="dsp-metric__rows">
                <li v-for="r in dayView.payRows" :key="r.label" class="dsp-metric__row">
                  <span class="dsp-metric__dot" :style="{ background: r.color }" />
                  <span class="dsp-metric__label">{{ r.label }}</span>
                  <span class="dsp-metric__val">{{ r.val }}</span>
                  <span v-if="r.pct" class="dsp-metric__pctrow">{{ r.pct }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div v-if="dayView && !dayEmpty" class="dsp-modal__links">
          <span class="dsp-modal__links-cap">Детализация:</span>
          <button v-if="dayView.penalty" class="dsp-modal__link" title="Детализация штрафов" @click="openDayPop('shf')">Штрафы</button>
          <button v-if="dayView.deduction" class="dsp-modal__link" title="Детализация удержаний" @click="openDayPop('udr')">Удержания</button>
          <button class="dsp-modal__link" title="Детализация отзывов" @click="openDayPop('feedback')">Отзывы</button>
          <button v-if="dayView.acceptance" class="dsp-modal__link" title="Детализация приёмки" @click="openDayPop('acceptance')">Приёмка</button>
        </div>
      </div>
    </div>

    <FinancePopup
      v-if="finPop" :kind="finPop.kind" :date-from="finPop.dateFrom" :date-to="finPop.dateTo"
      @close="finPop = null"
    />
  </section>
</template>

<script setup lang="ts">
/**
 * Показатели (черновик) — блок темы вместо dashboard/TopMetrics.vue.
 * Формулы и опции графика 1:1 с боевым виджетом, разметка — на блоках темы.
 * Цвета статей расходов — код данных (--d-* в tokens.css), значения те же.
 */
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import { theme } from '../../theme'
import VChart from 'vue-echarts'
import FinancePopup, { type FinancePopupKind } from './FinancePopup.vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const auth = useAuthStore()
const canFinance = computed(() => auth.canDomain('viewFinance'))
const { data, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => ['top-metrics', auth.companyId] as const),
  queryFn: dashboardApi.topMetrics,
})

const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})
const hasData = computed(() => (((data.value as any)?.chart45Data || []) as any[]).length > 0)
const busy = computed(() => isLoading.value || isFetching.value)
watchEffect(() => { if (!busy.value) report('top-metrics', hasData.value || !!isError.value) })

/* ---------- цвета: токены темы (canvas не рисует color(srgb …) — читаем hex) ---------- */
const cssVar = (name: string, fallback: string) => {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}
const C = computed(() => ({
  sales: cssVar('--d-sales', '#3aa876'),
  return: cssVar('--d-return', '#e0525c'),
  comm: cssVar('--d-comm', '#f5a623'),
  acq: cssVar('--d-acq', '#3b82f6'),
  log: cssVar('--d-log', '#5bc0de'),
  adv: cssVar('--d-adv', '#8a2be0'),
  rev: cssVar('--d-rev', '#16a085'),
  storage: cssVar('--d-storage', '#e3c766'),
  cashback: cssVar('--d-cashback', '#e0525c'),
  other: cssVar('--d-other', '#9aa0a8'),
  cost: cssVar('--d-cost', '#f0b429'),
  nds: cssVar('--d-nds', '#f57f17'),
  tax: cssVar('--d-tax', '#e0525c'),
  margin: cssVar('--d-margin', '#1e9e7c'),
}))
const CHART = computed(() => ({
  exp: cssVar('--chart-dash-exp', '#b2c0d2'),
  nds: cssVar('--chart-dash-nds', '#dcdcdc'),
  cost: cssVar('--chart-dash-cost', '#FF9E1B'),
  tax: cssVar('--chart-dash-tax', '#ff6b6b'),
  margin: cssVar('--chart-dash-margin', '#2ec4b6'),
}))

/* пересчёт при смене темы: оси/легенда берут токены */
const tick = ref(0)
watch(theme, () => { nextTick(() => { tick.value++ }) })

/* ---------- цифры ---------- */
const kpi = computed(() => ((data.value as any)?.kpi45Data || {}) as any)
const num = (v: any) => Number(v) || 0
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
const otziv = computed(() => num(kpi.value.total_otziv))
const storage = computed(() => num(kpi.value.total_storage_fee))
const cashback = computed(() => num(kpi.value.total_cashback))
const restExp = computed(() => expenses.value - commission.value - acquiring.value - delivery.value - adv.value - otziv.value - storage.value - cashback.value)
const avgCheck = computed(() => (orders.value ? sales.value / orders.value : 0))
const retail = computed(() => num(kpi.value.total_retail_amount))
const sppAvg = computed(() => num(kpi.value.total_spp_avg))

const fmt = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(v || 0))
const pct1 = (x: number) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(x)
const sppFmt = (v: any) => `${pct1(Number(v) || 0)}%`
const pctStr = (v: number) => (sales.value ? `${pct1((v / sales.value) * 100)}%` : '0,0%')
const headBase = computed(() => expenses.value + netProfit.value)
const headPct = (v: number) => (headBase.value ? `${pct1((v / headBase.value) * 100)}%` : '0,0%')

const salesBar = computed(() => {
  if (!sales.value) return { net: 0, ret: 0 }
  return {
    net: Math.max(0, ((sales.value - ret.value) / sales.value) * 100),
    ret: Math.max(0, (ret.value / sales.value) * 100),
  }
})
const salesRows = computed(() => [
  { label: 'Выкупы', qty: `${fmt(salesQnt.value)} шт`, val: `${fmt(sales.value)} ₽`, pct: '', color: C.value.sales },
  { label: 'Возвраты', qty: `${fmt(retQnt.value)} шт (${pctStr(ret.value)})`, val: `${fmt(ret.value)} ₽`, pct: '', color: C.value.return },
  { label: 'Заказы', qty: `${fmt(orders.value)} шт`, val: `${fmt(retail.value)} ₽`, pct: '', color: '' },
  { label: 'К оплате на Р/С', qty: '', val: `${fmt(netProfit.value)} ₽`, pct: '', color: '' },
  { label: 'Средний чек', qty: '', val: `${fmt(avgCheck.value)} ₽`, pct: '', color: '' },
  { label: 'СПП', qty: '', val: sppFmt(sppAvg.value), pct: '', color: '' },
])

/* Полосы — в масштабе своего заголовка (сегменты = 100%), проценты в строках — от выручки. */
const wExp = (v: number) => (expenses.value ? Math.max(0, (v / expenses.value) * 100) : 0)
const wPay = (v: number) => (netProfit.value ? Math.max(0, (v / netProfit.value) * 100) : 0)

const expSegs = computed(() => [
  { label: 'Комиссия', w: wExp(commission.value), color: C.value.comm },
  { label: 'Эквайринг', w: wExp(acquiring.value), color: C.value.acq },
  { label: 'Логистика', w: wExp(delivery.value), color: C.value.log },
  { label: 'Реклама', w: wExp(adv.value), color: C.value.adv },
  { label: 'Отзывы', w: wExp(otziv.value), color: C.value.rev },
  { label: 'Хранение', w: wExp(storage.value), color: C.value.storage },
  { label: 'Кешбэк', w: wExp(cashback.value), color: C.value.cashback },
  { label: 'Остальные', w: wExp(restExp.value), color: C.value.other },
])
const expRows = computed(() => [
  { label: 'Комиссия', val: `${fmt(commission.value)} ₽`, pct: pctStr(commission.value), color: C.value.comm },
  { label: 'Эквайринг', val: `${fmt(acquiring.value)} ₽`, pct: pctStr(acquiring.value), color: C.value.acq },
  { label: 'Логистика', val: `${fmt(delivery.value)} ₽`, pct: pctStr(delivery.value), color: C.value.log },
  { label: 'Реклама', val: `${fmt(adv.value)} ₽`, pct: pctStr(adv.value), color: C.value.adv },
  { label: 'Отзывы', val: `${fmt(otziv.value)} ₽`, pct: pctStr(otziv.value), color: C.value.rev },
  { label: 'Хранение', val: `${fmt(storage.value)} ₽`, pct: pctStr(storage.value), color: C.value.storage },
  { label: 'Кешбэк', val: `${fmt(cashback.value)} ₽`, pct: pctStr(cashback.value), color: C.value.cashback },
  { label: 'Остальные', val: `${fmt(restExp.value)} ₽`, pct: pctStr(restExp.value), color: C.value.other },
])
const paySegs = computed(() => [
  { label: 'Себестоимость', w: wPay(cost.value), color: C.value.cost },
  { label: 'НДС', w: wPay(nds.value), color: C.value.nds },
  { label: 'Налог на прибыль', w: wPay(tax.value), color: C.value.tax },
  { label: 'Маржа', w: wPay(margin.value), color: C.value.margin },
])
const payRows = computed(() => [
  { label: 'Себестоимость', val: `${fmt(cost.value)} ₽`, pct: pctStr(cost.value), color: C.value.cost },
  { label: 'НДС', val: `${fmt(nds.value)} ₽`, pct: pctStr(nds.value), color: C.value.nds },
  { label: 'Налог на прибыль', val: `${fmt(tax.value)} ₽`, pct: pctStr(tax.value), color: C.value.tax },
  { label: 'Маржа', val: `${fmt(margin.value)} ₽`, pct: pctStr(margin.value), color: C.value.margin },
])

/* ---------- график: стек 30 дней (опции 1:1 с боевым виджетом) ---------- */
const chartOption = computed(() => {
  void tick.value // пересчёт при смене темы
  const raw = ((data.value as any)?.chart45Data || []) as any[]
  if (!raw.length) return {}
  const palette = CHART.value
  const inkMuted = cssVar('--ink-muted', '#969CA1')
  const ink = cssVar('--ink', '#111315')
  const font = cssVar('--font-ui', 'system-ui, sans-serif')
  /* Скругление — у ВЕРХНЕГО блока столбца. Когда маржа уходит в минус, её сегмент
     уезжает под ноль — скруглять надо верхний положительный сегмент, а не маржу. */
  const STACK_KEYS = ['total_expenses', 'total_nds', 'total_cost', 'tax_amount', 'clean_margin']
  const stackRows = raw.map((r: any) => {
    const vals = STACK_KEYS.map(k => Math.round(r[k] || 0))
    let top = -1
    vals.forEach((v, i) => { if (v > 0) top = i })
    return { vals, top }
  })
  const stackSeries = (name: string, si: number, color: string) => ({
    name, type: 'bar', stack: 'total', ...(si === 0 ? { barWidth: '55%' } : {}),
    data: stackRows.map(r => ({
      value: r.vals[si],
      itemStyle: { color, borderRadius: si === r.top ? [4, 4, 0, 0] : 0 },
    })),
  })
  return {
    tooltip: {
      trigger: 'axis', backgroundColor: 'rgba(33,37,41,.92)', borderWidth: 0,
      textStyle: { color: '#fff', fontSize: 12 },
      valueFormatter: (v: any) => `${new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))} ₽`,
    },
    legend: {
      data: ['Расходы', 'НДС', 'Себестоимость', 'Налог на прибыль', 'Маржа'],
      bottom: 0, left: 'center', icon: 'roundRect', itemWidth: 12, itemHeight: 12,
      textStyle: { fontSize: 11, color: ink, fontFamily: font },
    },
    grid: { left: 8, right: 16, top: 10, bottom: 40, containLabel: true },
    xAxis: {
      type: 'category',
      data: raw.map((r: any) => {
        const d = new Date(r.date)
        return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      }),
      axisLine: { lineStyle: { color: cssVar('--line-strong', '#CBD0D4') } },
      axisTick: { show: false },
      axisLabel: { fontSize: 11, color: inkMuted, fontFamily: font, interval: 2 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: cssVar('--line', '#E1E3E6') } },
      axisLabel: {
        fontSize: 11, color: inkMuted, fontFamily: font,
        formatter: (v: number) => (v >= 1000 ? `${new Intl.NumberFormat('ru-RU').format(v / 1000)} тыс.` : String(v)),
      },
    },
    series: [
      stackSeries('Расходы', 0, palette.exp),
      stackSeries('НДС', 1, palette.nds),
      stackSeries('Себестоимость', 2, palette.cost),
      stackSeries('Налог на прибыль', 3, palette.tax),
      stackSeries('Маржа', 4, palette.margin),
    ],
  }
})

/* ---------- баланс ---------- */
const { data: balData } = useQuery({
  queryKey: computed(() => ['finance-balance', auth.companyId] as const),
  queryFn: dashboardApi.financeBalance, retry: 1,
  enabled: computed(() => canFinance.value),
} as any)
const balHas = computed(() => !!(balData.value as any)?.has_data)
const showBal = ref(true)
const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)
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
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

/* ---------- модалка дня ---------- */
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

const dayView = computed(() => {
  const k = dayKpi.value
  if (!k) return null
  const n = (v: any) => Number(v) || 0
  const c = C.value
  const dSales = n(k.total_sales_rub)
  const dPct1 = (x: number) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(x)
  const dPctStr = (v: number) => (!dSales ? '0,0%' : `${dPct1((v / dSales) * 100)}%`)
  const dRet = n(k.total_return_rub)
  const dOrders = n(k.total_orders_cnt)
  const dNetProfit = n(k.total_profit_rub)
  const dNds = n(k.total_nds)
  const dCost = n(k.total_cost)
  const dTax = n(k.tax_amount)
  const dMargin = n(k.clean_margin)
  const dExpenses = n(k.total_expenses)
  const dCommission = n(k.total_commission)
  const dAcquiring = n(k.total_acquiring_fee)
  const dDelivery = n(k.total_delivery)
  const dAdv = n(k.total_adv)
  const dOtziv = n(k.total_otziv)
  const dStorage = n(k.total_storage_fee)
  const dCashback = n(k.total_cashback)
  const dRest = dExpenses - dCommission - dAcquiring - dDelivery - dAdv - dOtziv - dStorage - dCashback
  const dHeadBase = dExpenses + dNetProfit
  const headP = (v: number) => (!dHeadBase ? '0,0%' : `${dPct1((v / dHeadBase) * 100)}%`)
  const wE = (v: number) => (dExpenses ? Math.max(0, (v / dExpenses) * 100) : 0)
  const wP = (v: number) => (dNetProfit ? Math.max(0, (v / dNetProfit) * 100) : 0)
  return {
    sales: dSales, ret: dRet, orders: dOrders, expenses: dExpenses, netProfit: dNetProfit,
    penalty: n(k.total_penalty), deduction: n(k.total_deduction), acceptance: n(k.total_acceptance),
    salesBar: !dSales ? { net: 0, ret: 0 } : {
      net: Math.max(0, ((dSales - dRet) / dSales) * 100),
      ret: Math.max(0, (dRet / dSales) * 100),
    },
    salesRows: [
      { label: 'Выкупы', qty: `${fmt(n(k.total_sales_qnt))} шт`, val: `${fmt(dSales)} ₽`, pct: '', color: c.sales },
      { label: 'Возвраты', qty: `${fmt(n(k.total_return_qnt))} шт (${dPctStr(dRet)})`, val: `${fmt(dRet)} ₽`, pct: '', color: c.return },
      { label: 'Заказы', qty: `${fmt(dOrders)} шт`, val: `${fmt(n(k.total_retail_amount))} ₽`, pct: '', color: '' },
      { label: 'К оплате на Р/С', qty: '', val: `${fmt(dNetProfit)} ₽`, pct: '', color: '' },
      { label: 'Средний чек', qty: '', val: `${fmt(dOrders ? dSales / dOrders : 0)} ₽`, pct: '', color: '' },
      { label: 'СПП', qty: '', val: sppFmt(n(k.total_spp_avg)), pct: '', color: '' },
    ],
    expSegs: [
      { label: 'Комиссия', w: wE(dCommission), color: c.comm },
      { label: 'Эквайринг', w: wE(dAcquiring), color: c.acq },
      { label: 'Логистика', w: wE(dDelivery), color: c.log },
      { label: 'Реклама', w: wE(dAdv), color: c.adv },
      { label: 'Отзывы', w: wE(dOtziv), color: c.rev },
      { label: 'Хранение', w: wE(dStorage), color: c.storage },
      { label: 'Кешбэк', w: wE(dCashback), color: c.cashback },
      { label: 'Остальные', w: wE(dRest), color: c.other },
    ],
    expRows: [
      { label: 'Комиссия', val: `${fmt(dCommission)} ₽`, pct: dPctStr(dCommission), color: c.comm, popup: '' },
      { label: 'Эквайринг', val: `${fmt(dAcquiring)} ₽`, pct: dPctStr(dAcquiring), color: c.acq, popup: '' },
      { label: 'Логистика', val: `${fmt(dDelivery)} ₽`, pct: dPctStr(dDelivery), color: c.log, popup: '' },
      { label: 'Реклама', val: `${fmt(dAdv)} ₽`, pct: dPctStr(dAdv), color: c.adv, popup: 'adv' },
      { label: 'Отзывы', val: `${fmt(dOtziv)} ₽`, pct: dPctStr(dOtziv), color: c.rev, popup: '' },
      { label: 'Хранение', val: `${fmt(dStorage)} ₽`, pct: dPctStr(dStorage), color: c.storage, popup: 'storage' },
      { label: 'Кешбэк', val: `${fmt(dCashback)} ₽`, pct: dPctStr(dCashback), color: c.cashback, popup: '' },
      { label: 'Остальные', val: `${fmt(dRest)} ₽`, pct: dPctStr(dRest), color: c.other, popup: '' },
    ],
    paySegs: [
      { label: 'Себестоимость', w: wP(dCost), color: c.cost },
      { label: 'НДС', w: wP(dNds), color: c.nds },
      { label: 'Налог на прибыль', w: wP(dTax), color: c.tax },
      { label: 'Маржа', w: wP(dMargin), color: c.margin },
    ],
    payRows: [
      { label: 'Себестоимость', val: `${fmt(dCost)} ₽`, pct: dPctStr(dCost), color: c.cost },
      { label: 'НДС', val: `${fmt(dNds)} ₽`, pct: dPctStr(dNds), color: c.nds },
      { label: 'Налог на прибыль', val: `${fmt(dTax)} ₽`, pct: dPctStr(dTax), color: c.tax },
      { label: 'Маржа', val: `${fmt(dMargin)} ₽`, pct: dPctStr(dMargin), color: c.margin },
    ],
    headExp: headP(dExpenses),
    headPay: headP(dNetProfit),
  }
})
const dayEmpty = computed(() => {
  const v = dayView.value
  return !!v && !v.sales && !v.expenses && !v.netProfit && !v.orders
})

/* попап детализации затрат за выбранный день */
const finPop = ref<{ kind: FinancePopupKind, dateFrom: string, dateTo: string } | null>(null)
const openDayPop = (kind: FinancePopupKind) => {
  if (!selDate.value) return
  finPop.value = { kind, dateFrom: selDate.value, dateTo: selDate.value }
}

const onEsc = (e: KeyboardEvent) => {
  if (e.key !== 'Escape') return
  if (finPop.value) return
  selDate.value = null
}
onMounted(() => window.addEventListener('keydown', onEsc))
onUnmounted(() => window.removeEventListener('keydown', onEsc))
</script>
