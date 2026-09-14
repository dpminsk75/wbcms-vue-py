<template>
  <div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden; margin-bottom:16px">
    <div class="card-header text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; display:flex; justify-content:space-between; align-items:center">
      <span>Воронка продаж</span>
      <button class="btn btn-sm" :class="showValues?'btn-light':'btn-outline-light'" style="width:32px; height:28px; padding:0" @click="showValues=!showValues" :title="showValues?'Скрыть значения':'Показать значения'">
        <i :class="showValues?'bi bi-eye':'bi bi-eye-slash'"></i>
      </button>
    </div>
    <div v-if="!data.length" class="sales-funnel-chart-empty">Нет данных для графика</div>
    <VChart v-else :option="chartOption" autoresize style="height:380px" />
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
      textStyle: { fontSize: 12 },
    },
    grid: { left: 48, right: 24, top: 55, bottom: 80, containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(row => row.date),
      axisLabel: { fontSize: 11, rotate: 35 },
    },
    yAxis: [
      { type: 'value', name: 'Корзины / заказы', nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 }, min: 0, max: L.top, interval: L.step },
      { type: 'value', name: 'Переходы', nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 }, min: 0, max: R.top, interval: R.step },
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
        lineStyle: { width: 2.5, color: '#f44336', opacity: 1 },
        itemStyle: { color: '#f44336', opacity: 1, borderColor: '#ffffff', borderWidth: 1.5 },
        areaStyle: { color: 'rgba(244,67,54,0.08)' },
        label: { show: showValues.value, position: 'top', distance: 10, fontSize: 11, fontWeight: 700, color: '#f44336', opacity: 1, backgroundColor: '#ffffff', borderColor: '#f44336', borderWidth: 1.5, borderRadius: 6, padding: [3, 6] },
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
        lineStyle: { width: 2.5, color: '#660ec8', opacity: 1 },
        itemStyle: { color: '#660ec8', opacity: 1, borderColor: '#ffffff', borderWidth: 1.5 },
        areaStyle: { color: 'rgba(102,14,200,0.08)' },
        label: { show: showValues.value, position: 'top', distance: 10, fontSize: 11, fontWeight: 700, color: '#660ec8', opacity: 1, backgroundColor: '#ffffff', borderColor: '#660ec8', borderWidth: 1.5, borderRadius: 6, padding: [3, 6] },
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
        lineStyle: { width: 2.5, color: '#5067de', opacity: 1 },
        itemStyle: { color: '#5067de', opacity: 1, borderColor: '#ffffff', borderWidth: 1.5 },
        areaStyle: { color: 'rgba(80,103,222,0.08)' },
        label: { show: showValues.value, position: 'top', distance: 10, fontSize: 11, fontWeight: 700, color: '#5067de', opacity: 1, backgroundColor: '#ffffff', borderColor: '#5067de', borderWidth: 1.5, borderRadius: 6, padding: [3, 6] },
        labelLayout: { hideOverlap: false, moveOverlap: 'shiftY', minMargin: 3 },
      },
    ],
  }
})
</script>

<style scoped>
.sales-funnel-chart-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 16px;
  margin-bottom: 16px;
}
.sales-funnel-chart-empty {
  height: 380px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 13px;
}
</style>
