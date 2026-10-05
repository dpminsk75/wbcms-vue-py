<template>
  <div class="page-fbs-report__chart-card">
    <div class="page-fbs-report__section-title">Заказы по дням и их исход</div>
    <div class="page-fbs-report__chart" ref="chartEl">
      <VChart v-if="daily.length" :option="chartOption" autoresize class="page-fbs-report__chart-inner" />
      <div v-else class="d-flex align-items-center justify-content-center h-100 text-muted page-fbs-report__empty">Нет данных</div>
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

const props = defineProps<{ daily: any[] }>()

const daily = computed(() => props.daily || [])

const chartOption = computed(() => {
  const data = daily.value
  if (!data.length) return {}
  const dates = data.map((r: any) => {
    try {
      return new Date(r.d + 'T00:00:00').toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
    } catch { return r.d }
  })
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['Выкуплено', 'Новый', 'В сборке', 'Передан WB', 'В пути', 'Ждёт в ПВЗ', 'Отказ на выдаче', 'Отмена покупателя', 'Отмена продавца'], top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 40, right: 16, top: 52, bottom: 30, containLabel: true },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
    series: [
      { name: 'Выкуплено', type: 'bar', stack: 'total', data: data.map((r: any) => r.sold || 0), itemStyle: { color: '#16a34a' }, barWidth: '60%' },
      { name: 'Новый', type: 'bar', stack: 'total', data: data.map((r: any) => r.new || 0), itemStyle: { color: '#c4b5fd' } },
      { name: 'В сборке', type: 'bar', stack: 'total', data: data.map((r: any) => r.assembling || 0), itemStyle: { color: '#a78bfa' } },
      { name: 'Передан WB', type: 'bar', stack: 'total', data: data.map((r: any) => r.handed || 0), itemStyle: { color: '#7c3aed' } },
      { name: 'В пути', type: 'bar', stack: 'total', data: data.map((r: any) => r.transit || 0), itemStyle: { color: '#22c55e' } },
      { name: 'Ждёт в ПВЗ', type: 'bar', stack: 'total', data: data.map((r: any) => r.pickup || 0), itemStyle: { color: '#4ade80' } },
      { name: 'Отказ на выдаче', type: 'bar', stack: 'total', data: data.map((r: any) => r.declined || 0), itemStyle: { color: '#fb7185' } },
      { name: 'Отмена покупателя', type: 'bar', stack: 'total', data: data.map((r: any) => r.buyer_cancel || 0), itemStyle: { color: '#ef4444' } },
      { name: 'Отмена продавца', type: 'bar', stack: 'total', data: data.map((r: any) => r.seller_cancel || 0), itemStyle: { color: '#991b1b' } },
    ],
  }
})
</script>
<style scoped>
.page-fbs-report__chart-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px 18px; margin-bottom:16px; height:100%; }
.page-fbs-report__section-title { font-size:13px; font-weight:600; color:#111827; margin-bottom:10px; }
.page-fbs-report__chart { height:320px; }
.page-fbs-report__chart-inner { height:100%; }
.page-fbs-report__empty { font-size:12px; }
</style>
