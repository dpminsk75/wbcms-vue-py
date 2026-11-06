<template>
  <div class="container-xxl page-fbs-report">
    <!-- Шапка блока «FBS»: заголовок + правое меню блока (пилюли темы) -->
    <WbWorkspaceHead
      title="FBS — продажа со своего склада"
      :workspace-tabs="STOCK_FBS_TABS"
      workspace-active="summary"
    />

    <!-- Фильтр: панель темы (.wb-filter-panel) -->
    <div class="wb-filter-panel mb-3">
      <div class="fbs-filter__presets">
        <button v-for="p in presets" :key="p.id" class="btn" :class="activePreset === p.id ? 'btn--brand' : 'btn--outline'" @click="applyPreset(p.id)">{{ p.label }}</button>
      </div>
      <div class="row g-2 align-items-start">
        <div class="col-md-2">
          <label class="wb-field__label">Дата с</label>
          <WbDateInput v-model="filters.date_from" />
        </div>
        <div class="col-md-2">
          <label class="wb-field__label">Дата по</label>
          <WbDateInput v-model="filters.date_to" />
        </div>
        <div class="col-md-4">
          <label class="wb-field__label">Товар</label>
          <FbsCardSelect v-model:nm-id="filters.nm_id" />
        </div>
        <div class="col-md-2">
          <label class="wb-field__label">Бренд</label>
          <select v-model="filters.brand" class="wb-select" @change="fetchData()">
            <option value="">Все</option>
            <option v-for="b in brands" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="wb-field__label">Категория</label>
          <select v-model="filters.category" class="wb-select" @change="fetchData()">
            <option value="">Все</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>
      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" @click="fetchData()">Применить</button>
        <button class="btn btn--outline" @click="reset()">Сбросить</button>
      </div>
    </div>

    <div v-if="isLoading" class="fbs-loading">Загрузка данных…</div>
    <div v-else-if="error" class="wb-panel">
      <div class="wb-panel__bd page-fbs-report__error">{{ error }}</div>
    </div>
    <template v-else-if="data">
      <FbsKpiCards :kpi="data.kpi" :delta="data.delta" />
      <FbsPipelineBar :pipeline="data.pipeline" />
      <div class="row">
        <div class="col-lg-8"><FbsDailyChart :daily="data.daily" /></div>
        <div class="col-lg-4"><FbsHandlingTime :handling="data.handling" /></div>
      </div>
      <FbsBreakdownTable :items="breakdownItems" v-model:mode="breakdownMode" :loading="breakdownLoading" />
    </template>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { ref, onMounted, watch } from 'vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { STOCK_FBS_TABS } from '@/components/common/workspaceTabs'
import FbsCardSelect from '../components/fbs/FbsCardSelect.vue'
import FbsKpiCards from '../components/fbs/FbsKpiCards.vue'
import FbsPipelineBar from '../components/fbs/FbsPipelineBar.vue'
import FbsDailyChart from '../components/fbs/FbsDailyChart.vue'
import FbsHandlingTime from '../components/fbs/FbsHandlingTime.vue'
import FbsBreakdownTable from '../components/fbs/FbsBreakdownTable.vue'
import WbDateInput from '../components/common/WbDateInput.vue'
import { fbsApi } from '../api/fbs'

const iso = (d: Date) => d.toISOString().slice(0, 10)
const today = () => { const d = new Date(); return iso(d) }
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d) }

const filters = ref({ nm_id: '', date_from: daysAgo(13), date_to: today(), brand: '', category: '' })
const brands = ref<string[]>([])
const categories = ref<string[]>([])
const data = ref<any>(null)
const isLoading = ref(false)
const error = ref('')
const activePreset = ref('14')
const breakdownMode = ref('products')
const breakdownItems = ref<any[]>([])
const breakdownLoading = ref(false)

const presets = [
  { id: 'today', label: 'Сегодня' },
  { id: 'yesterday', label: 'Вчера' },
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
]

function applyPreset(id: string) {
  activePreset.value = id
  const t = today()
  if (id === 'today') { filters.value.date_from = t; filters.value.date_to = t }
  else if (id === 'yesterday') { const y = daysAgo(1); filters.value.date_from = y; filters.value.date_to = y }
  else { filters.value.date_from = daysAgo(Number(id) - 1); filters.value.date_to = t }
  fetchData()
}

async function fetchData() {
  isLoading.value = true
  error.value = ''
  try {
    const p: Record<string, string> = { date_from: filters.value.date_from, date_to: filters.value.date_to }
    if (filters.value.nm_id) p.nm_id = filters.value.nm_id
    if (filters.value.brand) p.brand = filters.value.brand
    if (filters.value.category) p.category = filters.value.category
    const [s, o] = await Promise.all([
      fbsApi.summary(p),
      fbsApi.options(filters.value.date_from, filters.value.date_to),
    ])
    data.value = s
    brands.value = o.brands || []
    categories.value = o.categories || []
    fetchBreakdown()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки'
  } finally {
    isLoading.value = false
  }
}

async function fetchBreakdown() {
  breakdownLoading.value = true
  try {
    const p: Record<string, string> = { mode: breakdownMode.value, date_from: filters.value.date_from, date_to: filters.value.date_to }
    if (filters.value.nm_id) p.nm_id = filters.value.nm_id
    if (filters.value.brand) p.brand = filters.value.brand
    if (filters.value.category) p.category = filters.value.category
    const b = await fbsApi.breakdown(p as any)
    breakdownItems.value = b.items || []
  } catch { breakdownItems.value = [] } finally {
    breakdownLoading.value = false
  }
}

watch(breakdownMode, fetchBreakdown)

function reset() {
  filters.value = { nm_id: '', date_from: daysAgo(13), date_to: today(), brand: '', category: '' }
  activePreset.value = '14'
  fetchData()
}

onMounted(fetchData)
</script>
