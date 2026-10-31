<template>
  <div class="container-xxl page-tag-margin">
    <h1 class="page-title page-tag-margin__title">{{ pageTitle }}</h1>

    <div class="card page-tag-margin__filter-card card-body mb-4 shadow-sm">
      <div class="row g-3 align-items-end">
        <div class="col-md-4">
          <label class="form-label fw-bold">Период анализа</label>
          <div class="d-flex gap-2 align-items-center">
            <WbDateInput v-model="filters.date_from" />
            <span>|</span>
            <WbDateInput v-model="filters.date_to" />
          </div>
        </div>

        <div class="col-md-3">
          <label class="form-label fw-bold">Тег</label>
          <select v-model="filters.tag_id" class="form-select">
            <option v-for="t in tagOptions" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </div>

        <div class="col-md-2">
          <label class="form-label fw-bold">Сортировать по</label>
          <select v-model="filters.sort_by" class="form-select">
            <option value="qnt">Количеству продаж (шт)</option>
            <option value="amount">Выручке (руб)</option>
            <option value="net_profit">По итогу от WB (руб)</option>
            <option value="clean_margin">Марже после налогов (руб)</option>
          </select>
        </div>

        <div class="col-md-3 d-flex gap-2">
          <button class="btn btn-primary flex-grow-1" @click="onApply" :disabled="isLoading">
            <i class="bi bi-filter me-1"></i> Применить
          </button>
        </div>
      </div>

      <!-- Чекбоксы и подписи -->
      <div class="row g-3 align-items-center">
        <div class="col-md-6 d-flex align-items-center gap-3">
          <div class="form-check mb-0">
            <input id="tm-with-stock" v-model="filters.with_stock" type="checkbox" class="form-check-input" />
            <label class="form-check-label" for="tm-with-stock">Выводить остаток</label>
          </div>
          <span v-if="stockDate" class="text-muted small">Остатки на {{ stockDate }}</span>
        </div>
      </div>
    </div>

    <div class="card shadow-sm">
      <div class="card-header text-white bg-wb-green-deep-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0"><i class="bi bi-tag me-2"></i>{{ headerLabel }}</h5>
        <div class="d-flex gap-2">
          <span class="badge bg-light text-dark align-self-center">
            {{ filters.date_from }} — {{ filters.date_to }}
          </span>
          <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!rows.length">
            <i class="bi bi-file-earmark-excel me-1"></i> Excel
          </button>
        </div>
      </div>

      <div class="card-body p-0">
        <div v-if="isLoading" class="text-center p-5">
          <div class="spinner-border text-primary" role="status"></div>
          <div class="mt-2 text-muted">Загрузка данных...</div>
        </div>

        <MarginTable
          v-else
          :rows="rows"
          footer-label="Итого по тегу:"
          :show-stock="filters.with_stock"
          :period="`${filters.date_from} — ${filters.date_to}`"
          :date-from="filters.date_from"
          :date-to="filters.date_to"
          show-breakdown
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-tag-margin.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MarginTable from '@/components/profit/MarginTable.vue'
import { exportMarginExcel } from '@/api/profit'
import { tagsApi, type TagItem } from '@/api/tags'
import WbDateInput from '../components/common/WbDateInput.vue'

const route = useRoute()
const router = useRouter()

const today = new Date()
const defTo = today.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 30 * 864e5).toISOString().slice(0, 10)

const SORTS = ['qnt', 'amount', 'net_profit', 'clean_margin']

// Фильтры живут в URL: F5 сохраняет отчёт, ссылку можно отправить
const filters = ref({
  date_from: String(route.query.date_from || defFrom),
  date_to: String(route.query.date_to || defTo),
  tag_id: String(route.query.id || ''),
  sort_by: SORTS.includes(String(route.query.sort_by)) ? String(route.query.sort_by) : 'qnt',
  with_stock: route.query.with_stock === '1'
})

const tagOptions = ref<TagItem[]>([])
const rows = ref<any[]>([])
const isLoading = ref(false)
const error = ref('')

const currentTag = computed(() => tagOptions.value.find((t) => String(t.id) === String(filters.value.tag_id)))
const pageTitle = computed(() => currentTag.value ? `Маржа по тегу - ${currentTag.value.name}` : 'Маржа по тегам')
const headerLabel = computed(() => currentTag.value ? `Маржа: ${currentTag.value.name}` : 'Маржа по тегу')

// Фактическая дата снимка остатков (может быть < date_to — фолбэк)
const stockDate = computed(() => {
  if (!filters.value.with_stock) return ''
  const d = rows.value[0]?.stock_date
  return d ? String(d).slice(0, 10) : ''
})

// URL → фильтры (навигация назад/вперёд, чужая ссылка)
function applyFromRoute(nq: any) {
  const s = String(nq.sort_by || '')
  const next = {
    date_from: String(nq.date_from || defFrom),
    date_to: String(nq.date_to || defTo),
    tag_id: String(nq.id || filters.value.tag_id),
    sort_by: SORTS.includes(s) ? s : 'qnt',
    with_stock: nq.with_stock === '1'
  }
  const cur = filters.value
  if (cur.date_from !== next.date_from || cur.date_to !== next.date_to ||
      cur.tag_id !== next.tag_id || cur.sort_by !== next.sort_by ||
      cur.with_stock !== next.with_stock) {
    filters.value = next
  }
}

// фильтры → URL (replace, чтобы не плодить историю)
let syncing = false
function syncRoute() {
  const q: Record<string, string> = {
    date_from: filters.value.date_from,
    date_to: filters.value.date_to
  }
  if (filters.value.tag_id) q.id = filters.value.tag_id
  if (filters.value.sort_by !== 'qnt') q.sort_by = filters.value.sort_by
  if (filters.value.with_stock) q.with_stock = '1'
  syncing = true
  router.replace({ path: '/tag/margin', query: q })
    .finally(() => setTimeout(() => (syncing = false), 50))
}

async function fetchTags() {
  try {
    tagOptions.value = await tagsApi.list()
    if (!filters.value.tag_id && tagOptions.value.length) {
      filters.value.tag_id = String(tagOptions.value[0].id)
    }
  } catch {
    tagOptions.value = []
  }
}

async function fetchData() {
  if (!filters.value.tag_id) return
  isLoading.value = true
  error.value = ''
  try {
    rows.value = await tagsApi.margin(
      filters.value.tag_id, filters.value.date_from, filters.value.date_to,
      filters.value.sort_by, filters.value.with_stock)
    document.title = `${pageTitle.value} — SelBI`
  } catch {
    error.value = 'load'
    rows.value = []
  } finally {
    isLoading.value = false
  }
}

function onApply() {
  fetchData()
}

function exportExcel() {
  exportMarginExcel(
    rows.value,
    `tag-margin_${filters.value.tag_id}_${filters.value.date_from}_${filters.value.date_to}.xlsx`,
    'Маржа тега',
    filters.value.with_stock,
  )
}

watch(filters, () => syncRoute(), { deep: true })
watch(() => route.query, (nq) => {
  if (syncing) return
  applyFromRoute(nq)
  fetchData()
})

onMounted(async () => {
  await fetchTags()
  await fetchData()
})
</script>
