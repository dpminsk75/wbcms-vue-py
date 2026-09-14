<template>
  <div class="sales-funnel-chart-card">
    <div v-if="!data.length" class="sales-funnel-chart-empty">Нет данных для графика</div>
    <VChart v-else :option="chartOption" autoresize style="height:380px" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const props = defineProps<{
  data: Array<{
    date: string
    openCount: number
    cartCount: number
    orderCount: number
  }>
}>()

const selected = ref({ openCount: true, cartCount: true, orderCount: true })

const chartOption = computed(() => {
  const data = props.data || []
  if (!data.length) return {}

  return {
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      data: ['Переходы', 'Корзины', 'Заказы'],
      selected: {
        openCount: selected.value.openCount,
        cartCount: selected.value.cartCount,
        orderCount: selected.value.orderCount,
      },
      textStyle: { fontSize: 12 },
    },
    grid: { left: 48, right: 24, top: 42, bottom: 54, containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(row => row.date),
      axisLabel: { fontSize: 11, rotate: 35 },
    },
    yAxis: [
      { type: 'value', name: 'Корзины / заказы', nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
      { type: 'value', name: 'Переходы', nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
    ],
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', height: 18, bottom: 8 },
    ],
    series: [
      {
        name: 'Переходы',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: data.map(row => row.openCount || 0),
        lineStyle: { width: 3, color: '#f44336' },
        itemStyle: { color: '#f44336' },
        areaStyle: { color: 'rgba(244,67,54,0.08)' },
      },
      {
        name: 'Корзины',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: data.map(row => row.cartCount || 0),
        lineStyle: { width: 3, color: '#660ec8' },
        itemStyle: { color: '#660ec8' },
        areaStyle: { color: 'rgba(102,14,200,0.08)' },
      },
      {
        name: 'Заказы',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: data.map(row => row.orderCount || 0),
        lineStyle: { width: 3, color: '#5067de' },
        itemStyle: { color: '#5067de' },
        areaStyle: { color: 'rgba(80,103,222,0.08)' },
      },
    ],
  }
})
</script>

<style scoped>
.sales-funnel-chart-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 16px;
  margin-bottom: 16px;
}
.sales-funnel-chart-empty {
  height: 380px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 13px;
}
</style>
