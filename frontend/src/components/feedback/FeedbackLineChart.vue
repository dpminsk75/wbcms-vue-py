<template>
  <div class="page-feedback-dashboard__chart-card">
    <div class="page-feedback-dashboard__chart-head">
      <span class="page-feedback-dashboard__section-title">{{ title }}</span>
      <select v-if="periods.length" v-model="activePeriod" class="form-select form-select-sm w-auto">
        <option v-for="p in periods" :key="p.id" :value="p.id">{{ p.label }}</option>
      </select>
    </div>
    <div class="page-feedback-dashboard__chart">
      <VChart v-if="series.length" :option="option" autoresize
               class="page-feedback-dashboard__chart-inner" />
      <div v-else class="page-feedback-dashboard__empty">Нет данных</div>
    </div>
    <div v-if="legend.length" class="page-feedback-dashboard__legend">
      <button v-for="l in legend" :key="l.name" type="button"
              class="page-feedback-dashboard__legend-item page-feedback-dashboard__legend-btn"
              :class="{ 'page-feedback-dashboard__legend-item--off': l.off }"
              :title="l.off ? 'Показать серию' : 'Скрыть серию'"
              @click="toggle(l.name)">
        <span class="page-feedback-dashboard__legend-dot" :style="{ background: l.color }"></span>
        {{ l.name }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

export interface LineSeries {
  name: string
  color: string
  values: (number | null)[]
}

const props = withDefaults(defineProps<{
  title: string
  categories: string[]
  series: LineSeries[]
  periods?: Array<{ id: string; label: string }>
  yMin?: number
  yMax?: number
  smooth?: boolean
}>(), {
  periods: () => [],
  yMin: undefined,
  yMax: undefined,
  smooth: true,
})

const activePeriod = ref(props.periods[0]?.id || '')
watch(() => props.periods, (v) => {
  if (!v.some((p) => p.id === activePeriod.value)) activePeriod.value = v[0]?.id || ''
})

// выключенные серии (клик по легенде) — их нет в графике и в тултипе
const hidden = ref<string[]>([])
const toggle = (name: string) => {
  hidden.value = hidden.value.includes(name)
    ? hidden.value.filter((n) => n !== name)
    : [...hidden.value, name]
}

const legend = computed(() => props.series.map((s) => ({
  name: s.name,
  color: s.color,
  off: hidden.value.includes(s.name),
})))

const option = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { show: false },
  grid: { left: 46, right: 18, top: 20, bottom: 34, containLabel: true },
  xAxis: {
    type: 'category',
    data: props.categories,
    boundaryGap: false,
    axisLabel: { fontSize: 11, color: '#6b7280' },
    axisLine: { lineStyle: { color: '#d5dae1' } },
  },
  yAxis: {
    type: 'value',
    min: props.yMin,
    max: props.yMax,
    axisLabel: { fontSize: 11, color: '#6b7280' },
    splitLine: { lineStyle: { color: '#f0f1f4' } },
  },
  series: props.series
    .filter((s) => !hidden.value.includes(s.name))
    .map((s) => ({
      name: s.name,
      type: 'line',
      smooth: props.smooth,
      data: s.values,
      itemStyle: { color: s.color },
      lineStyle: { color: s.color, width: 2 },
      symbol: 'circle',
      symbolSize: 5,
      connectNulls: false,
    })),
}))
</script>

<style scoped>
.page-feedback-dashboard__chart-card {
  background: #fff;
  border: 1px solid #d5dae1;
  border-radius: 10px;
  padding: 16px 18px;
  height: 100%;
}
.page-feedback-dashboard__chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.page-feedback-dashboard__section-title { font-size: 13px; font-weight: 600; color: #111827; }
.page-feedback-dashboard__chart { height: 300px; margin-top: 8px; }
.page-feedback-dashboard__chart-inner { height: 100%; }
.page-feedback-dashboard__empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 13px;
}
.page-feedback-dashboard__legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px 14px;
  margin-top: 10px;
}
.page-feedback-dashboard__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #374151;
}
/* легенда-кнопка: клик отключает серию */
.page-feedback-dashboard__legend-btn {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  cursor: pointer;
}
.page-feedback-dashboard__legend-btn:hover { color: #111827; }
.page-feedback-dashboard__legend-item--off {
  opacity: .4;
  text-decoration: line-through;
}
.page-feedback-dashboard__legend-dot { width: 10px; height: 10px; border-radius: 3px; }
</style>
