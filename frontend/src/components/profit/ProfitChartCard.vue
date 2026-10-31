<template>
  <div class="wb-panel profit-chart-card">
    <div class="card__hd">
      <span class="text-truncate">{{ title }}</span>
      <span class="spacer"></span>
      <div class="d-flex align-items-center gap-1 flex-shrink-0">
        <slot name="header" />
        <!-- Глаз: показать/скрыть значения (подписи) на графике -->
        <button
          type="button"
          class="ch-icon-btn"
          :title="showLabels ? 'Скрыть значения' : 'Показать значения'"
          @click="showLabels = !showLabels"
        >
          <i :class="showLabels ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
        </button>
        <!-- Распахнуть: во всю ширину строки -->
        <button
          type="button"
          class="ch-icon-btn"
          :title="expanded ? 'Свернуть' : 'На всю ширину'"
          @click="emit('toggle-expand')"
        >
          <i :class="expanded ? 'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen'"></i>
        </button>
      </div>
    </div>
    <div class="wb-panel__bd">
      <slot name="legend" />
      <VChart :option="effectiveOption" autoresize class="profit-chart-card__canvas" :style="{ height: chartHeight + 'px' }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// Регистрация нужных модулей echarts (глобальная).
use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  title: string
  option: any
  expanded?: boolean
  height?: number
}>(), { expanded: false, height: 450 })

const emit = defineEmits<{ 'toggle-expand': [] }>()

// Показывать ли подписи значений на сериях.
const showLabels = ref(true)

const chartHeight = computed(() => (props.expanded ? 700 : props.height))

/** Подписи включаются/выключаются локально (кнопка «глаз»). */
const effectiveOption = computed(() => {
  const o = props.option
  if (!o || !Array.isArray(o.series)) return o
  const on = showLabels.value
  return {
    ...o,
    series: o.series.map((s: any) => {
      const base: any = {
        ...s,
        // noShow — серия без подписей даже при включённом «глазе» (напр. линия количества).
        label: { ...(s.label || {}), show: s.label && s.label.noShow ? false : on },
      }
      // Подписи, заданные на уровне точки данных (напр. в «Структуре затрат»),
      // имеют приоритет над series.label — их тоже нужно гасить.
      if (Array.isArray(s.data)) {
        base.data = s.data.map((it: any) => {
          if (!it || typeof it !== 'object' || !it.label) return it
          return on ? it : { ...it, label: { ...it.label, show: false } }
        })
      }
      return base
    }),
  }
})
</script>

<style scoped>
.profit-chart-card { overflow: hidden; height: 100%; }
.profit-chart-card__canvas { width: 100%; }
</style>
