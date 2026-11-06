<template>
  <div class="row">
    <div class="col-lg-7">
      <div class="fbs-chart-card">
        <div class="fbs-chart-card__title">Сдано по скорости сборки, шт</div>
        <div class="fbs-chart">
          <VChart v-if="days.length" :option="barOption" autoresize class="fbs-chart__inner" />
          <div v-else class="d-flex align-items-center justify-content-center h-100 fbs-empty">Нет данных</div>
        </div>
      </div>
    </div>
    <div class="col-lg-5">
      <div class="fbs-chart-card">
        <div class="fbs-chart-card__title">Заказов, шт</div>
        <div class="fbs-chart">
          <VChart v-if="days.length" :option="areaOption" autoresize class="fbs-chart__inner" />
          <div v-else class="d-flex align-items-center justify-content-center h-100 fbs-empty">Нет данных</div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { resolveTokenColor } from '@/utils/chartTheme'

use([BarChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{ days: any[], labels?: string[] }>()
const days = computed(() => props.days || [])

// Число корзин НЕ зашито: подписи и бакеты берём из API (assembly_grid —
// единый источник). Если API их не отдал (старый бэк) — выводим по b-ключам строк.
const deriveBucketKeys = (rows: any[]): string[] => {
  const keys = new Set<string>()
  for (const r of rows) {
    for (const k of Object.keys(r || {})) {
      if (/^b\d+$/.test(k)) keys.add(k)
    }
  }
  return [...keys].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)))
}

const bucketKeys = computed(() => {
  if (props.labels && props.labels.length) {
    return Array.from({ length: props.labels.length }, (_, i) => `b${i}`)
  }
  return deriveBucketKeys(days.value)
})

const bucketNames = computed(() => {
  const names = (props.labels && props.labels.length)
    ? [...props.labels]
    : bucketKeys.value.map((_, i) => `Корзина ${i + 1}`)
  return [...names, 'Без сдачи']
})

const axisLabels = computed(() => days.value.map((r: any) => {
  try {
    const d = new Date(r.d + 'T00:00:00')
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch { return String(r.d) }
}))

// Цвета корзин — шкала сроков темы (--fbs-speed-N). Бакетов может быть как угодно;
// i-я корзина красится в --fbs-speed-(i+1), 7-я и далее — в --fbs-speed-6 (самый тёмный).
const speedColor = (i: number) => resolveTokenColor(`--fbs-speed-${Math.min(i + 1, 6)}`)
const SPEED_NONE = resolveTokenColor('--fbs-speed-none')

const barOption = computed(() => {
  const data = days.value
  if (!data.length) return {}
  const names = bucketNames.value
  const series: any[] = []
  for (let i = 0; i < bucketKeys.value.length; i++) {
    series.push({
      name: names[i],
      type: 'bar',
      stack: 'total',
      data: data.map((r: any) => Number(r[bucketKeys.value[i]] || 0)),
      itemStyle: { color: speedColor(i) },
      barWidth: '60%',
    })
  }
  series.push({
    name: names[names.length - 1],
    type: 'bar',
    stack: 'total',
    data: data.map((r: any) => Number(r.un_cnt || 0)),
    itemStyle: { color: SPEED_NONE },
  })
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: names, top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 40, right: 16, top: 36, bottom: 30, containLabel: true },
    xAxis: { type: 'category', data: axisLabels.value, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
    series,
  }
})

const areaOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 48, right: 16, top: 16, bottom: 30, containLabel: true },
  xAxis: { type: 'category', data: axisLabels.value, axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
  series: [{
    type: 'line',
    smooth: true,
    data: days.value.map((r: any) => Number(r.orders_cnt || 0)),
    itemStyle: { color: resolveTokenColor('--chart-blue') },
    lineStyle: { color: resolveTokenColor('--chart-blue') },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(37,99,235,.25)' },
          { offset: 1, color: 'rgba(37,99,235,.02)' },
        ],
      },
    },
  }],
}))
</script>
