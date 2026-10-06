<template>
  <div class="page-fbs-report__chart-card">
    <div class="page-fbs-report__section-title">Заказы по дням и их исход</div>
    <div class="page-fbs-report__chart" ref="chartEl">
      <VChart v-if="daily.length" :option="chartOption" autoresize class="page-fbs-report__chart-inner" />
      <div v-else class="d-flex align-items-center justify-content-center h-100 text-muted page-fbs-report__empty">Нет данных</div>
    </div>
    <div v-if="daily.length" class="page-fbs-report__legend">
      <span v-for="s in SERIES" :key="s.name" class="page-fbs-report__legend-item">
        <span class="page-fbs-report__legend-dot" :style="{ background: s.color }"></span>{{ s.name }}
      </span>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, GridComponent, TooltipComponent, DatasetComponent, CanvasRenderer])

const props = defineProps<{ daily: any[] }>()

const daily = computed(() => props.daily || [])

// Порядок снизу вверх в стеке; скруглён только верх стека (как TopMetrics.vue).
const SERIES = [
  { name: 'Выкуплено', key: 'sold', color: '#16a34a' },
  { name: 'Новый', key: 'new', color: '#c4b5fd' },
  { name: 'В сборке', key: 'assembling', color: '#a78bfa' },
  { name: 'Передан WB', key: 'handed', color: '#7c3aed' },
  { name: 'В пути', key: 'transit', color: '#22c55e' },
  { name: 'Ждёт в ПВЗ', key: 'pickup', color: '#4ade80' },
  { name: 'Отказ на выдаче', key: 'declined', color: '#fb7185' },
  { name: 'Отмена покупателя', key: 'buyer_cancel', color: '#ef4444' },
  { name: 'Отмена продавца', key: 'seller_cancel', color: '#991b1b' },
]

const chartOption = computed(() => {
  const data = daily.value
  if (!data.length) return {}
  const dates = data.map((r: any) => {
    try {
      const _d = new Date(r.d + 'T00:00:00'); return `${String(_d.getMonth() + 1).padStart(2, '0')}-${String(_d.getDate()).padStart(2, '0')}`
    } catch { return r.d }
  })
  // Верх каждого бара: последний ненулевой сегмент дня — со скруглением.
  const topIdx = data.map((r: any) => {
    for (let i = SERIES.length - 1; i >= 0; i--) {
      if ((r[SERIES[i].key] || 0) > 0) return i
    }
    return -1
  })
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 8, right: 8, top: 16, bottom: 30, containLabel: true },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
    series: SERIES.map((s, i) => ({
      name: s.name,
      type: 'bar',
      stack: 'total',
      data: data.map((r: any, d: number) => ({
        value: r[s.key] || 0,
        itemStyle: {
          color: s.color,
          borderRadius: topIdx[d] === i ? [4, 4, 0, 0] : [0, 0, 0, 0],
        },
      })),
      barWidth: '60%',
    })),
  }
})
</script>
<style scoped>
.page-fbs-report__chart-card { background:#fff; border:1px solid #d5dae1; border-radius:10px; box-shadow:0 1px 3px rgba(16,24,40,.08); padding:16px 18px; margin-bottom:16px; height:100%; }
.page-fbs-report__section-title { font-size:13px; font-weight:600; color:#111827; margin-bottom:10px; }
.page-fbs-report__chart { height:320px; }
.page-fbs-report__chart-inner { height:100%; }
.page-fbs-report__empty { font-size:12px; }
.page-fbs-report__legend { display:grid; grid-template-columns:repeat(5, 1fr); justify-items:center; gap:6px 12px; max-width:820px; margin:10px auto 0; }
.page-fbs-report__legend-item { display:flex; align-items:center; gap:6px; font-size:11px; color:#374151; white-space:nowrap; overflow:hidden; }
.page-fbs-report__legend-dot { display:inline-block; width:12px; height:12px; border-radius:4px; flex-shrink:0; }
</style>
