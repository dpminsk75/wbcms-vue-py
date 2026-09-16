<template>
  <div class="container-xxl page-wb-search-trend">
    <div class="row mb-3">
      <h2 class="page-wb-search-trend__title">{{ pageTitle }}</h2>
    </div>

    <div class="row mb-3">
      <div class="col-md-6">
        <UniversalFilter
          label="Корень фразы"
          :data="phraseOptions"
          :allow-custom="true"
          placeholder="Введите корень фразы..."
          v-model="filters.phrase_text"
          v-model:date-from="filters.date_from"
          v-model:date-to="filters.date_to"
          :default-days="90"
          @apply="onApply"
          @reset="onReset"
        />
      </div>
    </div>

    <div class="row page-wb-search-trend__grid mb-3 mt-3">
      <div class="col-md-12">
        <div class="card">
          <div class="card-header">Анализ вхождений</div>
          <div v-if="isLoading" class="text-center p-5">
            <div class="spinner-border text-primary" role="status"></div>
            <div class="mt-2 text-muted">Загрузка данных...</div>
          </div>
          <div v-else class="wb-table-wrap page-wb-search-trend__table-wrap">
            <table class="table table-bordered table-hover mb-0 page-wb-search-trend__table">
              <thead>
                <tr>
                  <th class="page-wb-search-trend__th--num">#</th>
                  <th class="page-wb-search-trend__phrase">Фраза</th>
                  <th>Част</th>
                  <th>Клики</th>
                  <th>Заказы</th>
                  <th>CR %</th>
                  <th v-for="w in weeks" :key="w" class="text-center small">{{ w.slice(2) }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!models.length"><td :colspan="6 + weeks.length" class="text-center text-muted p-4">Нет данных</td></tr>
                <tr v-for="(m, i) in models" :key="m.phrase" class="page-wb-search-trend__row" @click="sel = m.phrase" :class="{ 'page-wb-search-trend__row--selected': sel === m.phrase }">
                  <td class="text-center">{{ (page - 1) * pageSize + i + 1 }}</td>
                  <td class="page-wb-search-trend__phrase">
                    <router-link :to="`/wb-search/phrase?phrase_id=${m.phrase_id ?? ''}&date_from=${filters.date_from}&date_to=${filters.date_to}`" target="_blank">{{ m.phrase }}</router-link>
                  </td>
                  <td class="text-end">{{ fmt0(m.avg_freq) }}</td>
                  <td class="text-end">{{ fmt0(m.total_clicks) }}</td>
                  <td class="text-end">{{ fmt0(m.total_orders) }}</td>
                  <td class="text-center" :style="crStyle(m)">{{ m.conversion }}</td>
                  <td v-for="w in weeks" :key="w" class="text-center" :style="heatStyle(m, w)">{{ heatVal(m, w) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="totalPages > 1" class="card-footer d-flex gap-2 align-items-center">
            <button class="btn btn-sm btn-outline-secondary" :disabled="page <= 1" @click="goPage(page - 1)">‹ Назад</button>
            <span class="text-muted">Стр {{ page }} / {{ totalPages }}</span>
            <button class="btn btn-sm btn-outline-secondary" :disabled="page >= totalPages" @click="goPage(page + 1)">Вперед ›</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="chartData.length" class="card my-3 shadow-sm">
      <div class="card-body">
        <v-chart :option="chartOption" autoresize class="page-wb-search-trend__chart" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-search-trend.css'
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import UniversalFilter from '@/components/common/UniversalFilter.vue'
import { wbSearchApi } from '@/api/search'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()

const today = new Date()
const yesterday = new Date(today.getTime() - 864e5)
const defTo = yesterday.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 90 * 864e5).toISOString().slice(0, 10)

const filters = reactive({
  phrase_text: String(route.query.phrase_text || ''),
  date_from: String(route.query.date_from || defFrom),
  date_to: String(route.query.date_to || defTo),
})

const models = ref<any[]>([])
const weeks = ref<string[]>([])
const chartData = ref<any[]>([])
const topPhrases = ref<Array<{ phrase: string }>>([])
const phraseOptions = ref<Array<{ value: string; label: string }>>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const isLoading = ref(false)
const sel = ref('')

const pageTitle = computed(() => `Анализ фразы: ${filters.phrase_text || 'выберите запрос'}`)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))

// CR-подсветка как trend.php:80-86
const crStyle = (m: any) => {
  if (Number(m.conversion) > 10) return { backgroundColor: '#d4edda', color: '#155724', fontWeight: 'bold' }
  if (Number(m.total_orders) === 0 && Number(m.total_clicks) > 50) return { backgroundColor: '#f8d7da', color: '#721c24' }
  return {}
}

// heatmap 9 градаций как trend.php:109-127 (динамика из JS)
const heatStyle = (m: any, w: string) => {
  const val = Number(m[w]) || 0
  if (val <= 0) return {}
  const avg = Number(m.avg_freq) || 1
  const ratio = val / avg
  if (ratio > 2.5) return { backgroundColor: '#1862aa', color: '#fff' }
  if (ratio > 1.95) return { backgroundColor: '#2171b5', color: '#fff' }
  if (ratio > 1.3) return { backgroundColor: '#4292c6', color: '#fff' }
  if (ratio > 1.1) return { backgroundColor: '#6baed6', color: '#fff' }
  if (ratio > 0.9) return { backgroundColor: '#9ecae1', color: '#333' }
  if (ratio > 0.4) return { backgroundColor: '#c6dbef', color: '#333' }
  if (ratio > 0.2) return { backgroundColor: '#cedff1', color: '#333' }
  if (ratio > 0.1) return { backgroundColor: '#d6e5f4', color: '#555' }
  return { backgroundColor: '#deebf7', color: '#555' }
}
const heatVal = (m: any, w: string) => {
  const val = Number(m[w]) || 0
  return val > 0 ? fmt0(val) : ''
}

// палитра как trend.php:228-232
const trendPalette = ['#6794dc', '#67b7dc', '#67dc75', '#dca867', '#dc67ce', '#095256', '#087f8c', '#5aaa95', '#86a873']

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { type: 'scroll' },
  xAxis: { type: 'category', data: chartData.value.map((r) => r.week) },
  yAxis: { type: 'value' },
  series: topPhrases.value.map((tp, i) => ({
    name: tp.phrase,
    type: 'line',
    lineStyle: { color: trendPalette[i % trendPalette.length], width: 2 },
    itemStyle: { color: trendPalette[i % trendPalette.length] },
    data: chartData.value.map((r) => r[`val_${i}`] ?? 0),
  })),
}))

async function fetchOptions() {
  try {
    const list = await wbSearchApi.phrases()
    phraseOptions.value = list.map((p) => ({ value: p.phrase, label: `${p.phrase} (${p.max_frequency})` }))
  } catch {
    phraseOptions.value = []
  }
}

async function fetchData() {
  isLoading.value = true
  try {
    const data = await wbSearchApi.trend(filters.phrase_text, filters.date_from, filters.date_to, page.value)
    models.value = data.models || []
    weeks.value = data.weeks || []
    chartData.value = data.chartData || []
    topPhrases.value = data.topPhrases || []
    total.value = Number(data.total) || 0
    pageSize.value = Number(data.page_size) || 50
    document.title = `Анализ фразы: ${filters.phrase_text || 'выберите запрос'}`
  } catch {
    models.value = []
  } finally {
    isLoading.value = false
  }
}

function syncRoute() {
  router.replace({
    path: '/wb-search/trend',
    query: { phrase_text: filters.phrase_text || undefined, date_from: filters.date_from, date_to: filters.date_to },
  })
}

function onApply() {
  page.value = 1
  syncRoute()
  fetchData()
}

function onReset() {
  filters.phrase_text = ''
  filters.date_from = defFrom
  filters.date_to = defTo
  page.value = 1
  syncRoute()
  fetchData()
}

function goPage(p: number) {
  page.value = p
  fetchData()
}

onMounted(async () => {
  await fetchOptions()
  await fetchData()
})
</script>
