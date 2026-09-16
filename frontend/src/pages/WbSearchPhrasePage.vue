<template>
  <div class="container-xxl page-wb-search-phrase">
    <div class="row mb-3">
      <h2 class="page-wb-search-phrase__title">{{ pageTitle }}</h2>
    </div>

    <div class="row mb-3">
      <div class="col-md-6">
        <UniversalFilter
          label="Поисковая фраза"
          :data="phraseOptions"
          v-model="filters.phrase_id"
          v-model:date-from="filters.date_from"
          v-model:date-to="filters.date_to"
          :default-days="70"
          @apply="onApply"
          @reset="onReset"
        />
      </div>
    </div>

    <div v-if="phrase && models.length" class="row page-wb-search-phrase__grid mb-3">
      <div class="col-md-12">
        <PhrasesMatrix :rows="models" :dates="uniqueDates" :is-loading="isLoading" :show-excel="true" mode="by-card" :heading="phrase ? `Товары по запросу: ${phrase}` : null" />
      </div>
    </div>
    <div v-else-if="phrase && !isLoading" class="alert alert-warning border-0 shadow-sm">
      По фразе <strong>"{{ phrase }}"</strong> данных не найдено.
    </div>

    <div v-if="phraseId && chartData.length" class="card border-0 shadow-sm mb-4 bg-light">
      <div class="card-body">
        <h5 class="card-title">Динамика ТОП-5 карточек (по кликам) и частотности запроса</h5>
        <v-chart :option="chartOption" autoresize class="page-wb-search-phrase__chart" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-search-phrase.css'
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import UniversalFilter from '@/components/common/UniversalFilter.vue'
import PhrasesMatrix from '@/components/common/PhrasesMatrix.vue'
import { wbSearchApi } from '@/api/search'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()

const today = new Date()
const yesterday = new Date(today.getTime() - 864e5)
const defTo = yesterday.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 70 * 864e5).toISOString().slice(0, 10)

const filters = reactive({
  phrase_id: String(route.query.phrase_id || ''),
  date_from: String(route.query.date_from || defFrom),
  date_to: String(route.query.date_to || defTo),
})

const phraseOptions = ref<Array<{ value: string; label: string }>>([])
const phrase = ref<string | null>(null)
const phraseId = ref<number | null>(null)
const models = ref<any[]>([])
const uniqueDates = ref<string[]>([])
const chartData = ref<any[]>([])
const top5Info = ref<Record<string, string>>({})
const isLoading = ref(false)

const pageTitle = computed(() => `Анализ фразы: ${phrase.value || 'выберите запрос'}`)

const truncate = (s: string, n: number) => (!s ? 'Запрос' : s.length > n ? s.slice(0, n).trim() + '...' : s)

// палитра серий как в phrase.php:540
const cardPalette = ['#0d6efd', '#198754', '#d63384', '#0dcaf0', '#6610f2']

const chartOption = computed(() => {
  const ids = Object.keys(top5Info.value)
  const series: any[] = [
    {
      name: phrase.value || 'Частотность',
      type: 'line',
      yAxisIndex: 1,
      lineStyle: { color: '#ffb74d', width: 2, type: 'dashed' },
      itemStyle: { color: '#ffb74d' },
      areaStyle: { color: '#ffb74d', opacity: 0.15 },
      data: chartData.value.map((r) => [r.date, r.frequency ?? 0]),
    },
  ]
  ids.forEach((nmId, i) => {
    const color = cardPalette[i % cardPalette.length]
    series.push({
      name: truncate(top5Info.value[nmId], 27),
      type: 'line',
      smooth: true,
      lineStyle: { color, width: 2.5 },
      itemStyle: { color },
      data: chartData.value.map((r) => [r.date, r[`card_${nmId}`] ?? 0]),
    })
  })
  return {
    tooltip: { trigger: 'axis' },
    legend: { type: 'scroll' },
    xAxis: { type: 'time' },
    yAxis: [{ type: 'value', name: 'Клики' }, { type: 'value', name: 'Частотность' }],
    series,
  }
})

async function fetchOptions() {
  try {
    const list = await wbSearchApi.phrases()
    phraseOptions.value = list.map((p) => ({ value: String(p.id), label: `${p.phrase} (${p.max_frequency})` }))
  } catch {
    phraseOptions.value = []
  }
}

async function fetchData() {
  if (!filters.phrase_id) {
    models.value = []
    phrase.value = null
    return
  }
  isLoading.value = true
  try {
    const data = await wbSearchApi.phrase(filters.phrase_id, filters.date_from, filters.date_to)
    phrase.value = data.phrase
    phraseId.value = data.phrase_id
    models.value = data.models || []
    uniqueDates.value = data.uniqueDates || []
    chartData.value = data.chartData || []
    top5Info.value = data.top5Info || {}
    document.title = `Анализ фразы: ${data.phrase || 'выберите запрос'}`
  } catch {
    models.value = []
  } finally {
    isLoading.value = false
  }
}

function onApply() {
  router.replace({ path: '/wb-search/phrase', query: { phrase_id: filters.phrase_id || undefined, date_from: filters.date_from, date_to: filters.date_to } })
  fetchData()
}

function onReset() {
  filters.phrase_id = ''
  filters.date_from = defFrom
  filters.date_to = defTo
  router.replace({ path: '/wb-search/phrase' })
  fetchData()
}

onMounted(async () => {
  await fetchOptions()
  await fetchData()
})
</script>
