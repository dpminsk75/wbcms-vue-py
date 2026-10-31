<template>
  <div class="wb-panel page-sales-funnel-wb-card__chart">
    <div class="card__hd">
      <span>Воронка продаж</span>
      <span class="spacer"></span>
      <button type="button" class="ch-icon-btn" @click="showValues = !showValues" :title="showValues ? 'Скрыть значения' : 'Показать значения'">
        <i :class="showValues ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
      </button>
    </div>
    <div class="wb-panel__bd">
      <div v-if="!data.length" class="sales-funnel-chart-empty">Нет данных для графика</div>
      <VChart v-else :option="chartOption" autoresize class="page-sales-funnel-wb-card__chart-canvas" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const props = defineProps<{
  data: Array<any>
}>()

const selected = ref({ openCount: true, cartCount: true, orderCount: true })
const showValues = ref(true)

/* Цвета серий — палитра отчёта (theme.md 5.9): клики / корзины / заказы. Фиксированные. */
const C_OPEN = '#2563EB'
const C_CART = '#059669'
const C_ORDER = '#DB2777'

/** Токены темы для осей и сетки (в ECharts нужен конкретный цвет). */
const cssVar = (n: string): string => {
  try {
    return (typeof document !== 'undefined' ? getComputedStyle(document.documentElement).getPropertyValue(n).trim() : '') || ''
  } catch {
    return ''
  }
}

const norm = (rows: any[]) => (rows || []).map((r: any) => ({
  date: String(r.date ?? r.odate ?? '').slice(0, 10),
  openCount: Number(r.openCount ?? r.open_count ?? 0),
  cartCount: Number(r.cartCount ?? r.cart_count ?? 0),
  orderCount: Number(r.orderCount ?? r.order_count ?? 0),
}))

// ось как у amCharts: шаг из ряда 1-2-2.5-5 под ~7 линий, верх покрывает raw (58.8 → шаг 10 → 70, 234.3 → шаг 50 → 250)
const NICE_STEPS = [1, 2, 2.5, 5]
const niceAxis = (raw: number) => {
  if (!(raw > 0)) return { top: 1, step: 1 }
  const exp = Math.floor(Math.log10(raw / 7))
  const mag = Math.pow(10, exp)
  const n = raw / 7 / mag
  const s = NICE_STEPS.find(v => v >= n) ?? 10
  const step = s * mag
  return { top: Math.ceil(raw / step) * step, step }
}

const chartOption = computed(() => {
  const data = norm(props.data || [])
  if (!data.length) return {}

  const axis = cssVar('--ink-muted') || '#969CA1'
  const line = cssVar('--line') || '#E1E3E6'
  const soft = cssVar('--ink-soft') || '#4C5257'

  // запас как в _chart.php: левая +20%, правая +10%, верх и шаг — круглые
  const leftMax = data.reduce((m, r) => Math.max(m, r.cartCount || 0, r.orderCount || 0), 0)
  const rightMax = data.reduce((m, r) => Math.max(m, r.openCount || 0), 0)
  const L = niceAxis(leftMax * 1.2)
  const R = niceAxis(rightMax * 1.1)

  return {
    tooltip: { trigger: 'axis' },
    legend: {
      bottom: 0,
      data: ['Переходы', 'Корзины', 'Заказы'],
      selected: {
        openCount: selected.value.openCount,
        cartCount: selected.value.cartCount,
        orderCount: selected.value.orderCount,
      },
      textStyle: { fontSize: 12, color: soft },
    },
    grid: { left: 48, right: 24, top: 55, bottom: 80, containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(row => row.date),
      axisLabel: { fontSize: 11, color: axis },
      axisLine: { lineStyle: { color: line } },
    },
    yAxis: [
      {
        type: 'value', name: 'Корзины / заказы',
        nameTextStyle: { fontSize: 11, color: axis },
        axisLabel: { fontSize: 11, color: axis },
        axisLine: { lineStyle: { color: line } },
        splitLine: { lineStyle: { color: line } },
        min: 0, max: L.top, interval: L.step,
      },
      {
        type: 'value', name: 'Переходы',
        nameTextStyle: { fontSize: 11, color: axis },
        axisLabel: { fontSize: 11, color: axis },
        axisLine: { lineStyle: { color: line } },
        splitLine: { show: false },
        min: 0, max: R.top, interval: R.step,
      },
    ],
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', height: 18, bottom: 28 },
    ],
    series: [
      {
        name: 'Переходы',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        data: data.map(row => row.openCount || 0),
        z: 10, zlevel: 3,
        lineStyle: { width: 2.5, color: C_OPEN, opacity: 1 },
        itemStyle: { color: C_OPEN, opacity: 1, borderColor: '#ffffff', borderWidth: 1.5 },
        areaStyle: { color: C_OPEN, opacity: 0.08 },
        label: { show: showValues.value, position: 'top', distance: 10, fontSize: 11, fontWeight: 700, color: C_OPEN, opacity: 1, backgroundColor: '#ffffff', borderColor: C_OPEN, borderWidth: 1.5, borderRadius: 6, padding: [3, 6] },
        labelLayout: { hideOverlap: false, moveOverlap: 'shiftY', minMargin: 3 },
      },
      {
        name: 'Корзины',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        data: data.map(row => row.cartCount || 0),
        z: 10, zlevel: 3,
        lineStyle: { width: 2.5, color: C_CART, opacity: 1 },
        itemStyle: { color: C_CART, opacity: 1, borderColor: '#ffffff', borderWidth: 1.5 },
        areaStyle: { color: C_CART, opacity: 0.08 },
        label: { show: showValues.value, position: 'top', distance: 10, fontSize: 11, fontWeight: 700, color: C_CART, opacity: 1, backgroundColor: '#ffffff', borderColor: C_CART, borderWidth: 1.5, borderRadius: 6, padding: [3, 6] },
        labelLayout: { hideOverlap: false, moveOverlap: 'shiftY', minMargin: 3 },
      },
      {
        name: 'Заказы',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        data: data.map(row => row.orderCount || 0),
        z: 11, zlevel: 3,
        lineStyle: { width: 2.5, color: C_ORDER, opacity: 1 },
        itemStyle: { color: C_ORDER, opacity: 1, borderColor: '#ffffff', borderWidth: 1.5 },
        areaStyle: { color: C_ORDER, opacity: 0.08 },
        label: { show: showValues.value, position: 'top', distance: 10, fontSize: 11, fontWeight: 700, color: C_ORDER, opacity: 1, backgroundColor: '#ffffff', borderColor: C_ORDER, borderWidth: 1.5, borderRadius: 6, padding: [3, 6] },
        labelLayout: { hideOverlap: false, moveOverlap: 'shiftY', minMargin: 3 },
      },
    ],
  }
})
</script>

<style scoped>
.page-sales-funnel-wb-card__chart-canvas { height: 380px; }
.sales-funnel-chart-empty {
  height: 380px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-muted);
  font-size: calc(13px * var(--fs));
}
</style>
