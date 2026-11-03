<template>
  <!-- Карточка графика — блок темы: .wb-panel + шапка .card__hd (§5.9). -->
  <div class="wb-panel page-feedback-dashboard__chart">
    <div class="card__hd">
      <span>{{ title }}</span>
      <select v-if="periods.length" v-model="activePeriod" class="page-feedback-dashboard__period"
              @change="$emit('update:period', activePeriod)">
        <option v-for="p in periods" :key="p.id" :value="p.id">{{ p.label }}</option>
      </select>
    </div>
    <div class="wb-panel__bd page-feedback-dashboard__chart-body">
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
import { resolveTokenColor } from '@/utils/chartTheme'

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

const emit = defineEmits<{ (e: 'update:period', id: string): void }>()

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
    // оси — токены темы (theme.md §5.9): подписи приглушенные, линия — линия темы
    axisLabel: { fontSize: 11, color: resolveTokenColor('--ink-muted') },
    axisLine: { lineStyle: { color: resolveTokenColor('--line-strong') } },
  },
  yAxis: {
    type: 'value',
    min: props.yMin,
    max: props.yMax,
    axisLabel: { fontSize: 11, color: resolveTokenColor('--ink-muted') },
    splitLine: { lineStyle: { color: resolveTokenColor('--line') } },
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
