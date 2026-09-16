<template>
  <div class="container-xxl page-tag-margin">
    <h1 class="page-title page-tag-margin__title">{{ pageTitle }}</h1>

    <div class="card page-tag-margin__filter-card card-body mb-4 shadow-sm">
      <div class="row g-3 align-items-end">
        <div class="col-md-4">
          <label class="form-label fw-bold">Период анализа</label>
          <div class="d-flex gap-2 align-items-center">
            <input type="date" v-model="filters.date_from" class="form-control">
            <span>|</span>
            <input type="date" v-model="filters.date_to" class="form-control">
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

        <MarginTable v-else :rows="rows" footer-label="Итого по тегу:" />
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

const route = useRoute()
const router = useRouter()

const today = new Date()
const defTo = today.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 30 * 864e5).toISOString().slice(0, 10)

const filters = ref({
  date_from: String(route.query.date_from || defFrom),
  date_to: String(route.query.date_to || defTo),
  tag_id: String(route.query.id || ''),
  sort_by: String(route.query.sort_by || 'qnt'),
})

const tagOptions = ref<TagItem[]>([])
const rows = ref<any[]>([])
const isLoading = ref(false)
const error = ref('')

const currentTag = computed(() => tagOptions.value.find((t) => String(t.id) === String(filters.value.tag_id)))
const pageTitle = computed(() => currentTag.value ? `Маржа по тегу - ${currentTag.value.name}` : 'Маржа по тегам')
const headerLabel = computed(() => currentTag.value ? `Маржа: ${currentTag.value.name}` : 'Маржа по тегу')

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
    rows.value = await tagsApi.margin(filters.value.tag_id, filters.value.date_from, filters.value.date_to, filters.value.sort_by)
    document.title = `${pageTitle.value} — wbcms`
  } catch {
    error.value = 'load'
    rows.value = []
  } finally {
    isLoading.value = false
  }
}

function onApply() {
  router.replace({ path: '/tag/margin', query: { id: filters.value.tag_id, date_from: filters.value.date_from, date_to: filters.value.date_to, sort_by: filters.value.sort_by } })
  fetchData()
}

function exportExcel() {
  exportMarginExcel(rows.value, `tag-margin_${filters.value.tag_id}_${filters.value.date_from}_${filters.value.date_to}.xlsx`, 'Маржа тега')
}

onMounted(async () => {
  await fetchTags()
  await fetchData()
})

watch(() => route.query.id, (id) => {
  if (id && String(id) !== String(filters.value.tag_id)) {
    filters.value.tag_id = String(id)
    fetchData()
  }
})
</script>
