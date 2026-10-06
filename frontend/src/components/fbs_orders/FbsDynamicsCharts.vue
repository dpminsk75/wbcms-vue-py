<template>
  <div class="row">
    <div class="col-lg-7">
      <div class="page-fbs-orders__chart-card">
        <div class="page-fbs-orders__section-title">Сдано по скорости сборки, шт</div>
        <div class="page-fbs-orders__chart">
          <VChart v-if="days.length" :option="barOption" autoresize class="page-fbs-orders__chart-inner" />
          <div v-else class="d-flex align-items-center justify-content-center h-100 text-muted page-fbs-orders__empty">Нет данных</div>
        </div>
      </div>
    </div>
    <div class="col-lg-5">
      <div class="page-fbs-orders__chart-card">
        <div class="page-fbs-orders__section-title">Заказов, шт</div>
        <div class="page-fbs-orders__chart">
          <VChart v-if="days.length" :option="areaOption" autoresize class="page-fbs-orders__chart-inner" />
          <div v-else class="d-flex align-items-center justify-content-center h-100 text-muted page-fbs-orders__empty">Нет данных</div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{ days: any[], labels?: string[] }>()
const days = computed(() => props.days || [])
// Подписи бакетов — из API (assembly_grid, единый источник); фолбэк на случай старого бэка.
const bucketNames = computed(() => props.labels && props.labels.length >= 6
  ? [...props.labels, 'Без сдачи']
  : ['0–13 ч', '13–42 ч', '42–48 ч', '48–54 ч', '54–60 ч', 'от 60 ч', 'Без сдачи'])
const labels = computed(() => days.value.map((r: any) => {
  try { return new Date(r.d + 'T00:00:00').toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }) }
  catch { return r.d }
}))
const grid = { left: 48, right: 16, top: 16, bottom: 30, containLabel: true }
const ax = { type: 'category', data: labels.value, axisLabel: { fontSize: 11 } }

const barOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: bucketNames.value, top: 0, textStyle: { fontSize: 11 } },
  grid: { left: 40, right: 16, top: 36, bottom: 30, containLabel: true },
  xAxis: ax, yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
    series: [
      { name: bucketNames.value[0], type: 'bar', stack: 'total', data: days.value.map((r: any) => r.b0 || 0), itemStyle: { color: '#16a34a' }, barWidth: '60%' },
      { name: bucketNames.value[1], type: 'bar', stack: 'total', data: days.value.map((r: any) => r.b1 || 0), itemStyle: { color: '#22c55e' } },
      { name: bucketNames.value[2], type: 'bar', stack: 'total', data: days.value.map((r: any) => r.b2 || 0), itemStyle: { color: '#9AA0A8' } },
      { name: bucketNames.value[3], type: 'bar', stack: 'total', data: days.value.map((r: any) => r.b3 || 0), itemStyle: { color: '#fb7185' } },
      { name: bucketNames.value[4], type: 'bar', stack: 'total', data: days.value.map((r: any) => r.b4 || 0), itemStyle: { color: '#ef4444' } },
      { name: bucketNames.value[5], type: 'bar', stack: 'total', data: days.value.map((r: any) => r.b5 || 0), itemStyle: { color: '#991b1b' } },
      { name: bucketNames.value[6], type: 'bar', stack: 'total', data: days.value.map((r: any) => r.un_cnt || 0), itemStyle: { color: '#cbd5e1' } },
    ],
}))
const areaOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid, xAxis: ax, yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
  series: [{ type: 'line', smooth: true, data: days.value.map((r: any) => r.orders_cnt || 0),
    itemStyle: { color: '#2563eb' }, lineStyle: { color: '#2563eb' },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(37,99,235,.25)' }, { offset: 1, color: 'rgba(37,99,235,.02)' }] } } }],
}))
</script>
<style scoped>
.page-fbs-orders__chart-card { background: #fff; border: 1px solid #d5dae1; box-shadow: 0 1px 3px rgba(16,24,40,.08); border-radius: 10px; padding: 16px 18px; margin-bottom: 16px; height: 100%; }
.page-fbs-orders__section-title { font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 10px; }
.page-fbs-orders__chart { height: 300px; }
.page-fbs-orders__chart-inner { height: 100%; }
.page-fbs-orders__empty { font-size: 12px; }
</style>
