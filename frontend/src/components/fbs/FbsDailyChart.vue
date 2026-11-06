<template>
  <div class="fbs-chart-card">
    <div class="fbs-chart-card__title">Заказы по дням и их исход</div>
    <div class="fbs-chart" ref="chartEl">
      <VChart v-if="daily.length" :option="chartOption" autoresize class="fbs-chart__inner" />
      <div v-else class="d-flex align-items-center justify-content-center h-100 fbs-empty">Нет данных</div>
    </div>
    <div v-if="daily.length" class="fbs-legend">
      <span v-for="s in SERIES" :key="s.name" class="fbs-legend__item">
        <span class="fbs-legend__dot" :style="{ background: s.color }"></span>{{ s.name }}
      </span>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { resolveTokenColor } from '@/utils/chartTheme'

use([BarChart, GridComponent, TooltipComponent, DatasetComponent, CanvasRenderer])

const props = defineProps<{ daily: any[] }>()

const daily = computed(() => props.daily || [])

// Порядок снизу вверх в стеке; скруглён только верх стека (как TopMetrics.vue).
// Цвета серий — токены темы (--fbs-1…9), значения те же, что были зашиты в страницу.
const SERIES = [
  { name: 'Выкуплено', key: 'sold', color: resolveTokenColor('--fbs-6') },
  { name: 'Новый', key: 'new', color: resolveTokenColor('--fbs-1') },
  { name: 'В сборке', key: 'assembling', color: resolveTokenColor('--fbs-2') },
  { name: 'Передан WB', key: 'handed', color: resolveTokenColor('--fbs-3') },
  { name: 'В пути', key: 'transit', color: resolveTokenColor('--fbs-4') },
  { name: 'Ждёт в ПВЗ', key: 'pickup', color: resolveTokenColor('--fbs-5') },
  { name: 'Отказ на выдаче', key: 'declined', color: resolveTokenColor('--fbs-7') },
  { name: 'Отмена покупателя', key: 'buyer_cancel', color: resolveTokenColor('--fbs-8') },
  { name: 'Отмена продавца', key: 'seller_cancel', color: resolveTokenColor('--fbs-9') },
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
