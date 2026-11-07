<template>
  <section v-if="busy || hasData || isError" class="wb-panel">
    <div class="dsp-today__head">
      <div class="dsp-tabs">
        <button
          v-for="t in tabs" :key="t.value" class="dsp-tab" :class="{ 'is-on': tab === t.value }"
          @click="tab = t.value"
        >{{ t.label }}</button>
      </div>
      <span class="dsp-today__note">Обновлено в {{ updatedAt }}</span>
      <span class="spacer"></span>
      <label class="dsp-today__check" :style="trimVisible ? '' : 'visibility:hidden'">
        <input type="checkbox" v-model="trimPast" :disabled="!trimVisible" /> по сегодня
      </label>
      <select class="dsp-select" v-model="period">
        <option v-for="p in periods" :key="p.value" :value="p.value">{{ p.label }}</option>
      </select>
    </div>

    <div class="wb-panel__bd">
      <div class="grid-4 dsp-today__kpi">
        <div class="tile tile--1">
          <div class="tile__label">Количество</div>
          <div class="tile__value">{{ fmt0(main?.cnt) }}</div>
          <div v-for="o in others" :key="o.key" class="dsp-delta" :class="cmp(main?.cnt, totals[o.key]?.cnt) >= 0 ? 'dsp-delta--up' : 'dsp-delta--down'">
            {{ cmp(main?.cnt, totals[o.key]?.cnt) >= 0 ? '↑' : '↓' }} {{ fmt0(Math.abs(cmp(main?.cnt, totals[o.key]?.cnt))) }} — {{ o.name }}
          </div>
        </div>

        <div class="tile tile--1">
          <div class="tile__label">Сумма</div>
          <div class="tile__value">{{ fmt2(main?.sum) }} ₽</div>
          <div v-for="o in others" :key="o.key" class="dsp-delta" :class="cmp(main?.sum, totals[o.key]?.sum) >= 0 ? 'dsp-delta--up' : 'dsp-delta--down'">
            {{ cmp(main?.sum, totals[o.key]?.sum) >= 0 ? '↑' : '↓' }} {{ fmt2(Math.abs(cmp(main?.sum, totals[o.key]?.sum))) }} ₽ — {{ o.name }}
          </div>
        </div>

        <div class="tile tile--1">
          <div class="tile__label">СПП (среднее)</div>
          <div class="tile__value">{{ fmt1(main?.spp) }}%</div>
          <div v-for="o in others" :key="o.key" class="dsp-delta" :class="cmp(main?.spp, totals[o.key]?.spp) >= 0 ? 'dsp-delta--up' : 'dsp-delta--down'">
            {{ cmp(main?.spp, totals[o.key]?.spp) >= 0 ? '↑' : '↓' }} {{ fmt1(Math.abs(cmp(main?.spp, totals[o.key]?.spp))) }} п.п. — {{ o.name }}
          </div>
        </div>

        <div class="dsp-prev">
          <div class="tile__label">{{ prev?.name }}</div>
          <div class="dsp-prev__rows"><b>{{ fmt0(prev?.cnt) }}</b> - заказов</div>
          <div class="dsp-prev__rows"><b>{{ fmt2(prev?.sum) }}</b> ₽ - на сумму</div>
          <div class="dsp-prev__rows"><b>{{ fmt1(prev?.spp) }}</b> % - СПП</div>
        </div>
      </div>

      <div style="margin-top: 14px">
        <VChart :option="chartOption" autoresize class="dsp-today__chart" />
        <div v-if="axisCaption" class="dsp-today__cap">{{ axisCaption }}</div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * «Сегодня» (черновик) — блок темы вместо dashboard/TodayStatsWidget.vue.
 * ECharts-опции 1:1 с боевым виджетом (палитра серий §5.9 фиксированная).
 */
import { ref, computed, inject, watchEffect, nextTick, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi, type Period } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import { theme } from '../../theme'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const tab = ref<'orders' | 'sales'>('orders')
const period = ref<Period>('today')
const trimPast = ref(true)
const tabs = [{ label: 'Заказы', value: 'orders' as const }, { label: 'Продажи', value: 'sales' as const }]
const periods: { label: string, value: Period }[] = [
  { label: 'За сегодня', value: 'today' },
  { label: 'За вчера', value: 'yesterday' },
  { label: 'С начала недели', value: 'week_to_date' },
  { label: 'За прошлую неделю', value: 'last_week' },
  { label: 'За месяц', value: 'month_to_date' },
  { label: 'За прошлый месяц', value: 'last_month' },
]
const trimVisible = computed(() => period.value === 'month_to_date' || period.value === 'last_month')

const auth = useAuthStore()
const { data, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => ['today-stats', period.value, tab.value, trimPast.value, auth.companyId] as const),
  queryFn: () => dashboardApi.todayStats(period.value, tab.value, trimPast.value),
})

const hasData = computed(() => {
  const totals = ((data.value as any)?.totals || {}) as Record<string, any>
  return Object.values(totals).some((t: any) => (Number(t?.cnt) || 0) > 0 || (Number(t?.sum) || 0) !== 0)
})
const busy = computed(() => isLoading.value || isFetching.value)
const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})
watchEffect(() => { if (!busy.value) report('today', hasData.value || !!isError.value) })

const updatedAt = computed(() => {
  const raw = (data.value as any)?.updated_at
  if (raw) {
    try {
      const d = new Date(String(raw).replace(' ', 'T'))
      if (!isNaN(d.getTime())) return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
      const m = String(raw).match(/(\d{2}):(\d{2})/)
      if (m) return `${m[1]}:${m[2]}`
    } catch { /* не разобрали — ниже */ }
    return String(raw).slice(11, 16) || String(raw)
  }
  return new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
})

const main = computed(() => (data.value as any)?.totals?.[(data.value as any)?.seriesMeta?.[0]?.key] ?? null)
const totals = computed(() => ((data.value as any)?.totals ?? {}) as Record<string, any>)
const axisCaption = computed(() => String((data.value as any)?.axisCaption || ''))
const others = computed(() => (((data.value as any)?.seriesMeta ?? []) as any[]).slice(1))
const prev = computed(() => {
  const o = others.value[0]
  if (!o) return null
  const t = totals.value[o.key]
  if (!t) return null
  return { name: o.name, cnt: t.cnt, sum: t.sum, spp: t.spp }
})

const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmt1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0)
const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)
const cmp = (a: any, b: any) => (Number(a) || 0) - (Number(b) || 0)

/* ---------- цвета серий: фиксированная палитра §5.9 ---------- */
const cssVar = (name: string, fallback: string) => {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}
const colors = computed(() => [
  cssVar('--chart-today-1', '#4B61EC'),
  cssVar('--chart-today-2', '#F042B7'),
  cssVar('--chart-today-3', '#3AC1C7'),
])
const tick = ref(0)
watch(theme, () => { nextTick(() => { tick.value++ }) })

const chartOption = computed(() => {
  void tick.value
  const d = data.value as any
  if (!d || !d.categories) return {}
  const pal = colors.value
  const ink = cssVar('--ink', '#111315')
  const inkMuted = cssVar('--ink-muted', '#969CA1')
  const font = cssVar('--font-ui', 'system-ui, sans-serif')
  const series: any[] = []
  /* СПП-бары — фон, рисуем первыми */
  if (d.granularity === 'day') {
    d.seriesMeta.forEach((m: any, idx: number) => {
      series.push({
        name: m.name + ' — СПП', type: 'bar', yAxisIndex: 1,
        data: d.series[m.key].map((p: any) => p.spp ?? null),
        itemStyle: { color: pal[idx], opacity: 0.28 },
        z: 0,
      })
    })
  }
  /* Линии — неделю назад фон → вчера → сегодня верх */
  const order = [...d.seriesMeta].map((_: any, i: number) => i).reverse()
  order.forEach((idx: number) => {
    const m = d.seriesMeta[idx]
    series.push({
      name: m.name, type: 'line',
      data: d.series[m.key].map((p: any) => p.sum ?? null),
      smooth: false, connectNulls: false,
      lineStyle: { width: idx === 0 ? 3 : 2, type: idx === 2 ? 'dashed' : 'solid' },
      itemStyle: { color: pal[idx] },
      z: 3 - idx,
    })
  })
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: d.seriesMeta.map((m: any) => m.name), top: 0, textStyle: { fontSize: 11, color: ink, fontFamily: font } },
    grid: { left: 40, right: 20, top: 30, bottom: 30, containLabel: true },
    xAxis: { type: 'category', data: d.categories, axisLabel: { color: inkMuted, fontFamily: font } },
    yAxis: [
      { type: 'value', min: 0, axisLabel: { color: inkMuted, fontFamily: font } },
      { type: 'value', min: 0, max: 100, axisLabel: { color: inkMuted, fontFamily: font } },
    ],
    series,
  }
})
</script>
