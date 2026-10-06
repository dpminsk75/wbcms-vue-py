<template>
  <div class="container-xxl page-fbs-cancels">
    <div class="page-fbs__head">
      <h1 class="page-title">FBS Отмены</h1>
      <FbsTabs active="cancels" />
    </div>

    <!-- Фильтр как в дашборде: пресеты + даты + товар + бренд/категория (без склада) -->
    <div class="page-fbs-cancels__filter-card mb-3">
      <div class="page-fbs-cancels__presets page-fbs-cancels__presets--top">
        <button v-for="p in presets" :key="p.id" class="btn btn-sm" :class="activePreset === p.id ? 'btn-primary' : 'btn-outline-secondary'" @click="applyPreset(p.id)">{{ p.label }}</button>
      </div>
      <div class="row g-2 align-items-start">
        <div class="col-md-2">
          <label class="form-label mb-1 page-fbs-cancels__filter-label">Дата с</label>
          <WbDateInput v-model="filters.date_from" />
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-fbs-cancels__filter-label">Дата по</label>
          <WbDateInput v-model="filters.date_to" />
        </div>
        <div class="col-md-4">
          <label class="form-label mb-1 page-fbs-cancels__filter-label">Товар</label>
          <FbsCardSelect v-model:nm-id="filters.nm_id" />
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-fbs-cancels__filter-label">Бренд</label>
          <select v-model="filters.brand" class="form-control" @change="fetchData()">
            <option value="">Все</option>
            <option v-for="b in brands" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-fbs-cancels__filter-label">Категория</label>
          <select v-model="filters.category" class="form-control" @change="fetchData()">
            <option value="">Все</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>
      <div class="page-fbs-cancels__filter-btns">
        <button class="btn btn-primary" style="width:120px" @click="fetchData()">Применить</button>
        <button class="btn btn-light" style="width:120px" @click="reset()">Сбросить</button>
      </div>
    </div>

    <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-else-if="summary">
      <div class="page-fbs-cancels__section-line">Отмены за период</div>
      <FbsCancelKpi :s="summary" @show="(b) => openModal(cancelTitle(b), b, null, false)" />
      <FbsCancelWarehouses :items="whItems" @show="(wid) => openModal('Отмены склада', 'all', wid, true)" />
      <FbsCancelOrdersModal :title="modalTitle" :orders="modalOrders" :loading="modalLoading" @close="modalOrders = null" />
    </template>
  </div>
</template>
<script setup lang="ts">
import '../assets/css/pages/page-fbs-cancels.css'
import { ref, onMounted } from 'vue'
import FbsTabs from '../components/fbs/FbsTabs.vue'
import FbsCardSelect from '../components/fbs/FbsCardSelect.vue'
import FbsCancelKpi from '../components/fbs_cancels/FbsCancelKpi.vue'
import FbsCancelWarehouses from '../components/fbs_cancels/FbsCancelWarehouses.vue'
import FbsCancelOrdersModal from '../components/fbs_cancels/FbsCancelOrdersModal.vue'
import { fbsCancelsApi } from '../api/fbsCancels'
import { fbsApi } from '../api/fbs'
import WbDateInput from '../components/common/WbDateInput.vue'

const iso = (d: Date) => d.toISOString().slice(0, 10)
const today = () => iso(new Date())
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d) }

const filters = ref({ nm_id: '', date_from: daysAgo(13), date_to: today(), brand: '', category: '' })
const brands = ref<string[]>([])
const categories = ref<string[]>([])
const summary = ref<any>(null)
const whItems = ref<any[]>([])
const modalTitle = ref('')
const modalOrders = ref<any[] | null>(null)
const modalLoading = ref(false)

const cancelTitle = (b: string) => b === 'seller_cancel' ? 'Отменил продавец' : b === 'buyer_cancel' ? 'Отменил покупатель' : b === 'declined' ? 'Отказ при получении' : 'Все отмены'

async function openModal(title: string, bucket: string, wid: number | null, byWarehouse: boolean) {
  modalTitle.value = title
  modalOrders.value = []
  modalLoading.value = true
  try {
    const p: Record<string, string> = { bucket, date_from: filters.value.date_from, date_to: filters.value.date_to }
    if (filters.value.nm_id) p.nm_id = filters.value.nm_id
    if (filters.value.brand) p.brand = filters.value.brand
    if (filters.value.category) p.category = filters.value.category
    // byWarehouse=false (KPI): без фильтра склада; true: конкретный склад (null -> группа «без склада» = 0)
    if (byWarehouse) p.warehouse_id = wid === null ? '0' : String(wid)
    const r = await fbsCancelsApi.orders(p as any)
    modalOrders.value = r.items || []
  } catch { modalOrders.value = [] } finally {
    modalLoading.value = false
  }
}
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

function params(): Record<string, string> {
  const p: Record<string, string> = { date_from: filters.value.date_from, date_to: filters.value.date_to }
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
    const [s, w, o] = await Promise.all([
      fbsCancelsApi.summary(params()),
      fbsCancelsApi.byWarehouse(params()),
      fbsApi.options(filters.value.date_from, filters.value.date_to),
    ])
    summary.value = s
    whItems.value = w.items || []
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

onMounted(fetchData)
</script>
