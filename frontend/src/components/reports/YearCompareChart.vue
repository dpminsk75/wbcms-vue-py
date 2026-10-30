<template>
  <div class="wb-panel" :class="{ 'year-compare-chart--full': expanded }">
    <div class="card__hd">
      <span>{{ title }}</span>
      <span class="spacer"></span>
      <button
        type="button"
        class="ch-icon-btn"
        @click="showValues = !showValues"
        :title="showValues ? 'Скрыть значения' : 'Показать значения'"
      >
        <i :class="showValues ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
      </button>
      <button
        type="button"
        class="ch-icon-btn"
        @click="toggleFull()"
        :title="expanded ? 'Свернуть' : 'На весь экран'"
      >
        <i :class="expanded ? 'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen'"></i>
      </button>
    </div>
    <div ref="chartRef" class="year-compare-chart__box"></div>
  </div>
</template>

<script setup lang="ts">
/**
 * График «по годам» — бары по месяцам, по одному на каждый выбранный год.
 *
 * Палитра серий ФИКСИРОВАННАЯ и от темы не зависит (theme.md 5.9, вариант V2):
 * 2024 #E64980 · 2025 #2B8A3E · 2026 #3B5BDB. Поэтому выбор ограничен тремя годами.
 * Оси — --ink-muted, легенда — --ink; при смене темы график перерисовывается,
 * цвета серий не меняются.
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { theme } from '@/theme'

const props = withDefaults(defineProps<{
  /** 12 строк: { m, name, qty_<год>, amount_<год> }. */
  months: any[]
  /** Выбранные годы. */
  years: number[]
  /** Заголовок в шапке блока. */
  title?: string
  /** Что показывать: amount (сумма) или qty (количество). */
  metric?: 'amount' | 'qty'
}>(), { title: 'Динамика по месяцам', metric: 'amount' })

const chartRef = ref<HTMLDivElement | null>(null)
const showValues = ref(true)
const expanded = ref(false)
let chart: any = null

/** Фиксированная палитра годов (V2) — не зависит от темы. */
const YEAR_COLORS: Record<string, string> = {
  '2024': '#E64980',
  '2025': '#2B8A3E',
  '2026': '#3B5BDB',
}
const FALLBACK = ['#3B5BDB', '#E64980', '#2B8A3E']

const cssVar = (name: string): string =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim()

const colorOf = (year: number, i: number): string =>
  YEAR_COLORS[String(year)] || FALLBACK[i % FALLBACK.length]

const render = () => {
  if (!chartRef.value) return
  const axisColor = cssVar('--ink-muted') || '#969CA1'
  const inkColor = cssVar('--ink') || '#111315'
  const years = props.years.slice().sort((a, b) => a - b)
  const months = Array.isArray(props.months) ? props.months : []
  const cats = months.map((m: any) => String(m.name || '').slice(0, 3))
  const suffix = props.metric === 'qty' ? 'шт' : '₽'

  const series = years.map((y, i) => {
    const c = colorOf(y, i)
    return {
      name: String(y),
      type: 'bar',
      data: months.map((m: any) => Number(m[`${props.metric}_${y}`] || 0)),
      itemStyle: { color: c, borderRadius: [3, 3, 0, 0] },
      label: {
        show: showValues.value,
        position: 'top',
        distance: 6,
        fontSize: 10,
        fontWeight: 700,
        color: c,
        backgroundColor: '#ffffff',
        borderColor: c,
        borderWidth: 1.5,
        borderRadius: 6,
        padding: [2, 5],
        formatter: (p: any) => (props.metric === 'qty' ? p.value : Math.round(Number(p.value || 0) / 1000)),
      },
      labelLayout: { hideOverlap: false, moveOverlap: 'shiftY', minMargin: 3 },
    }
  })

  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: years.map(String),
      bottom: 18,
      itemGap: 16,
      itemWidth: 16,
      itemHeight: 9,
      textStyle: { color: inkColor, fontSize: 11 },
    },
    grid: { left: 60, right: 24, top: 36, bottom: 92 },
    xAxis: {
      type: 'category',
      data: cats,
      axisLabel: { margin: 12, fontSize: 11, color: axisColor },
    },
    yAxis: {
      type: 'value',
      name: suffix,
      min: 0,
      axisLabel: { color: axisColor, fontSize: 11 },
      nameTextStyle: { color: axisColor },
    },
    series,
  }, true)
}

const toggleFull = () => {
  expanded.value = !expanded.value
  nextTick(() => {
    chart?.resize()
    render()
  })
}

const onResize = () => chart?.resize()

watch(() => [props.months, props.years, props.metric], () => nextTick(render))
watch(showValues, () => render())
// смена темы — перерисовать оси/легенду (цвета серий остаются фиксированными)
watch(theme, () => render(), { deep: true })

onMounted(() => {
  nextTick(render)
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.year-compare-chart__box { width: 100%; height: 340px; }
/* «На весь экран» — карточка поверх страницы (не модалка: каркас модалок
   на токенах в теме ещё нет, theme.md §12). */
.year-compare-chart--full {
  position: fixed;
  inset: 0;
  z-index: 90;
  border-radius: 0;
  overflow: auto;
}
.year-compare-chart--full .year-compare-chart__box { height: calc(100vh - 60px); }
</style>
