<template>
  <div class="container-xxl page-fbs-pvz">
    <h1 class="page-title">FBS Путь до ПВЗ <span class="badge bg-secondary page-fbs-pvz__beta">Beta</span></h1>
    <FbsTabs active="pvz" />

    <!-- Фильтр как в дашборде -->
    <div class="page-fbs-pvz__filter-card mb-3">
      <div class="page-fbs-pvz__presets page-fbs-pvz__presets--top">
        <button v-for="p in presets" :key="p.id" class="btn btn-sm" :class="activePreset === p.id ? 'btn-primary' : 'btn-outline-secondary'" @click="applyPreset(p.id)">{{ p.label }}</button>
      </div>
      <div class="row g-2 align-items-start">
        <div class="col-md-2">
          <label class="form-label mb-1 page-fbs-pvz__filter-label">Дата с</label>
          <input v-model="filters.date_from" type="date" class="form-control" />
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-fbs-pvz__filter-label">Дата по</label>
          <input v-model="filters.date_to" type="date" class="form-control" />
        </div>
        <div class="col-md-4">
          <label class="form-label mb-1 page-fbs-pvz__filter-label">Товар</label>
          <FbsCardSelect v-model:nm-id="filters.nm_id" />
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-fbs-pvz__filter-label">Бренд</label>
          <select v-model="filters.brand" class="form-control" @change="fetchData()">
            <option value="">Все</option>
            <option v-for="b in brands" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-fbs-pvz__filter-label">Категория</label>
          <select v-model="filters.category" class="form-control" @change="fetchData()">
            <option value="">Все</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>
      <div class="page-fbs-pvz__filter-btns">
        <button class="btn btn-primary" style="width:120px" @click="fetchData()">Применить</button>
        <button class="btn btn-light" style="width:120px" @click="reset()">Сбросить</button>
      </div>
    </div>

    <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-else-if="data">
      <div class="page-fbs-pvz__section-line">Путь заказа до пункта выдачи</div>
      <FbsPvzKpi :k="data.kpi" />
      <FbsPvzMatrix :matrix="data.matrix || []" :dirs="data.directions || []" :products="data.products || []" v-model:dirs-count="dirsCount" :date-from="filters.date_from" :date-to="filters.date_to" />
    </template>
  </div>
</template>
<script setup lang="ts">
import '../assets/css/pages/page-fbs-pvz.css'
import { ref, onMounted, watch } from 'vue'
import FbsTabs from '../components/fbs/FbsTabs.vue'
import FbsCardSelect from '../components/fbs/FbsCardSelect.vue'
import FbsPvzKpi from '../components/fbs_pvz/FbsPvzKpi.vue'
import FbsPvzMatrix from '../components/fbs_pvz/FbsPvzMatrix.vue'
import { fbsPvzApi } from '../api/fbsPvz'
import { fbsApi } from '../api/fbs'

const iso = (d: Date) => d.toISOString().slice(0, 10)
const today = () => iso(new Date())
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d) }

const filters = ref({ nm_id: '', date_from: daysAgo(13), date_to: today(), brand: '', category: '' })
const dirsCount = ref(7)
const brands = ref<string[]>([])
const categories = ref<string[]>([])
const data = ref<any>(null)
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

function params(): Record<string, any> {
  const p: Record<string, any> = { date_from: filters.value.date_from, date_to: filters.value.date_to, top_dirs: dirsCount.value }
  if (filters.value.nm_id) p.nm_id = filters.value.nm_id
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
    const [s, o] = await Promise.all([
      fbsPvzApi.summary(params()),
      fbsApi.options(filters.value.date_from, filters.value.date_to),
    ])
    data.value = s
    brands.value = o.brands || []
    categories.value = o.categories || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки'
  } finally {
    isLoading.value = false
  }
}

function reset() {
  filters.value = { nm_id: '', date_from: daysAgo(13), date_to: today(), brand: '', category: '' }
  activePreset.value = '14'
  fetchData()
}

watch(dirsCount, fetchData)

onMounted(fetchData)
</script>
