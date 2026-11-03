<template>
  <!-- Карточка графика — блок темы: .wb-panel + шапка .card__hd (§5.9). -->
  <div class="wb-panel page-feedback-dashboard__chart">
    <div class="card__hd">
      <span>{{ title }}</span>
    </div>
    <div class="wb-panel__bd page-feedback-dashboard__chart-body">
      <VChart v-if="data.length" :option="option" autoresize
               class="page-feedback-dashboard__chart-inner" />
      <div v-else class="page-feedback-dashboard__empty">Нет данных</div>
    </div>
    <div v-if="data.length" class="page-feedback-dashboard__legend">
      <button v-for="d in data" :key="d.name" type="button"
              class="page-feedback-dashboard__legend-item page-feedback-dashboard__legend-btn"
              :class="{ 'page-feedback-dashboard__legend-item--off': hidden.includes(d.name) }"
              :title="hidden.includes(d.name) ? 'Показать' : 'Скрыть'"
              @click="toggle(d.name)">
        <span class="page-feedback-dashboard__legend-dot" :style="{ background: d.color }"></span>
        {{ d.name }}
        <b>{{ pctOf(d) }}%</b>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { LegendComponent, GraphicComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { resolveTokenColor } from '@/utils/chartTheme'

use([PieChart, TooltipComponent, LegendComponent, GraphicComponent, CanvasRenderer])

export interface DonutItem {
  name: string
  value: number
  color: string
}

const props = defineProps<{
  title: string
  data: DonutItem[]
  total?: number
}>()

const total = computed(() => props.total ?? props.data.reduce((s, d) => s + (d.value || 0), 0))

// процент сектора от общего ( DonutItem pct не приходит из бэка — считаем тут)
const pctOf = (d: DonutItem) =>
  total.value ? Math.round((d.value || 0) * 100 / total.value) : 0

// выключенные сектора (клик по легенде)
const hidden = ref<string[]>([])
const toggle = (name: string) => {
  hidden.value = hidden.value.includes(name)
    ? hidden.value.filter((n) => n !== name)
    : [...hidden.value, name]
}

const option = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { show: false },
  series: [{
    type: 'pie', radius: ['58%', '80%'], center: ['50%', '50%'],
    avoidLabelOverlap: true,
    // разделитель секторов — цвет поверхности (тема), не hex в коде
    itemStyle: { borderColor: resolveTokenColor('--surface'), borderWidth: 2 },
    label: { show: false },
    emphasis: { label: { show: true, fontSize: 20, fontWeight: 700, formatter: '{d}%' } },
    data: props.data
      .filter((d) => !hidden.value.includes(d.name))
      .map((d) => ({
        name: d.name,
        value: d.value,
        itemStyle: { color: d.color },
      })),
  }],
  graphic: props.data.length && total.value
    ? [{
        type: 'text',
        left: 'center',
        top: 'middle',
        style: {
          text: `${total.value}\nвсего`,
          textAlign: 'center',
          fill: resolveTokenColor('--ink'),
          fontSize: 13,
          fontWeight: 700,
          lineHeight: 16,
        },
      }]
    : [],
}))
</script>
