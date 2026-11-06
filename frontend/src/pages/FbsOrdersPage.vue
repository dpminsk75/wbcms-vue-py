<template>
  <div class="container-xxl page-fbs-orders">
    <!-- Шапка блока «FBS»: заголовок + правое меню блока (пилюли темы) -->
    <WbWorkspaceHead
      title="FBS Заказы"
      :workspace-tabs="STOCK_FBS_TABS"
      workspace-active="orders"
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
          <label class="wb-field__label">Склад</label>
          <select v-model="filters.warehouse_id" class="wb-select" @change="fetchData()">
            <option value="">Все склады</option>
            <option v-for="w in warehouses" :key="String(w.warehouse_id)" :value="String(w.warehouse_id)">{{ w.name }}</option>
          </select>
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
      <div v-if="dataUpdated" class="fbs-note">Данные на {{ dataUpdated }}</div>
    </div>

    <div v-if="isLoading" class="fbs-loading">Загрузка данных…</div>
    <div v-else-if="error" class="wb-panel">
      <div class="wb-panel__bd page-fbs-orders__error">{{ error }}</div>
    </div>
    <template v-else-if="economy">
      <div class="fbs-section-line">Экономика периода{{ warehouseName ? ' · ' + warehouseName : '' }}</div>
      <FbsEconomyCards :e="economy" />
      <div class="fbs-section-line">Динамика по дням{{ warehouseName ? ' · ' + warehouseName : '' }}</div>
      <FbsDynamicsCharts :days="dynamics" :labels="dynamicsLabels" />
      <FbsAssemblyQueue :q="assemblyQuota" :risk="assemblyRisk" :warehouses="assemblyWh" />
    </template>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { ref, computed, onMounted } from 'vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { STOCK_FBS_TABS } from '@/components/common/workspaceTabs'
import FbsEconomyCards from '../components/fbs_orders/FbsEconomyCards.vue'
import FbsDynamicsCharts from '../components/fbs_orders/FbsDynamicsCharts.vue'
import FbsAssemblyQueue from '../components/fbs_orders/FbsAssemblyQueue.vue'
import WbDateInput from '../components/common/WbDateInput.vue'
import { fbsOrdersApi } from '../api/fbsOrders'
import { fbsApi } from '../api/fbs'

const iso = (d: Date) => d.toISOString().slice(0, 10)
const today = () => iso(new Date())
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d) }

const filters = ref({ warehouse_id: '', date_from: daysAgo(13), date_to: today(), brand: '', category: '' })
const warehouses = ref<{ warehouse_id: number | null; name: string }[]>([])
const brands = ref<string[]>([])
const categories = ref<string[]>([])
const economy = ref<any>(null)
const dynamics = ref<any[]>([])
const dynamicsLabels = ref<string[]>([])
const assemblyQuota = ref<any>({})
const assemblyRisk = ref<any>({})
const assemblyWh = ref<any[]>([])
const dataUpdated = ref('')
const isLoading = ref(false)
const error = ref('')
const activePreset = ref('14')

const presets = [
  { id: 'today', label: 'Сегодня' },
  { id: 'yesterday', label: 'Вчера' },
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
]

const warehouseName = computed(() => {
  if (!filters.value.warehouse_id) return ''
  const w = warehouses.value.find((x) => String(x.warehouse_id) === filters.value.warehouse_id)
  return w ? 'Склад «' + w.name + '»' : ''
})

function params(): Record<string, string> {
  const p: Record<string, string> = { date_from: filters.value.date_from, date_to: filters.value.date_to }
  if (filters.value.warehouse_id) p.warehouse_id = filters.value.warehouse_id
  if (filters.value.brand) p.brand = filters.value.brand
  if (filters.value.category) p.category = filters.value.category
  return p
}

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
    const [e, d, a, o] = await Promise.all([
      fbsOrdersApi.economy(params()),
      fbsOrdersApi.dynamics(params()),
      fbsOrdersApi.assembly(params()),
      fbsApi.options(filters.value.date_from, filters.value.date_to),
    ])
    economy.value = e
    dynamics.value = d.days || []
    dynamicsLabels.value = d.bucket_labels || []
    assemblyQuota.value = a.quota || {}
    assemblyRisk.value = a.risk || {}
    assemblyWh.value = a.warehouses || []
    dataUpdated.value = a.now || ''
    brands.value = o.brands || []
    categories.value = o.categories || []
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Ошибка загрузки'
  } finally {
    isLoading.value = false
  }
}

function reset() {
  filters.value = { warehouse_id: '', date_from: daysAgo(13), date_to: today(), brand: '', category: '' }
  activePreset.value = '14'
  fetchData()
}

onMounted(async () => {
  try { warehouses.value = await fbsOrdersApi.warehouses() } catch { /* noop */ }
  fetchData()
})
</script>
