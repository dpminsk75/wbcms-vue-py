<template>
  <div class="container-xxl page-top-products">
    <h1 class="page-title">{{ $route.meta.title || 'ТОП товаров за период' }}</h1>

    <!-- Блок фильтров -->
    <div class="card page-top-products__filter-card card-body mb-4 shadow-sm">
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
          <label class="form-label fw-bold">Сортировать по</label>
          <select v-model="filters.sort_by" class="form-select">
            <option value="qnt">Количеству продаж (шт)</option>
            <option value="amount">Выручке (руб)</option>
            <option value="net_profit">По итогу от WB (руб)</option>
            <option value="clean_margin">Марже после налогов (руб)</option>
          </select>
        </div>

        <div class="col-md-2">
          <label class="form-label fw-bold">Показать товаров</label>
          <select v-model.number="filters.limit" class="form-select">
            <option :value="20">ТОП-20</option>
            <option :value="50">ТОП-50</option>
            <option :value="200">ТОП-200</option>
            <option :value="500">ТОП-500</option>
            <option :value="1000">ТОП-1000</option>
          </select>
        </div>

        <div class="col-md-3 d-flex gap-2">
          <button class="btn btn-primary flex-grow-1" @click="refetch" :disabled="isLoading">
            <i class="bi bi-filter me-1"></i> Применить
          </button>
          <button class="btn btn-light" title="Сбросить" @click="resetFilters">
            <i class="bi bi-arrow-counterclockwise"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- Таблица результатов -->
    <div class="card shadow-sm">
      <div class="card-header text-white bg-wb-green-deep-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0"><i class="bi bi-crown me-2"></i>ТОП-{{ filters.limit }} товаров</h5>
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

        <MarginTable v-else :rows="rows" footer-label="Итого по ТОПу:" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-top-products.css'
import { ref, computed, onMounted } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'
import MarginTable from '@/components/profit/MarginTable.vue'
import { exportMarginExcel } from '@/api/profit'

const today = new Date()
const defTo = today.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 30 * 864e5).toISOString().slice(0, 10)

const filters = ref({
  date_from: defFrom,
  date_to: defTo,
  sort_by: 'qnt',
  limit: 20
})

const { data: rowsRaw, isLoading, refetch } = useQuery({
  queryKey: computed(() => ['top-products', filters.value.date_from, filters.value.date_to, filters.value.sort_by, filters.value.limit]),
  queryFn: () => api.get('/api/wb-profit/top-products', { params: filters.value }).then(r => r.data),
  initialData: [] as any[]
})

const rows = computed(() => Array.isArray(rowsRaw.value) ? rowsRaw.value : [])

const resetFilters = () => {
  filters.value = {
    date_from: defFrom,
    date_to: defTo,
    sort_by: 'qnt',
    limit: 20
  }
}

const exportExcel = () => exportMarginExcel(
  rows.value,
  `top-products_${filters.value.date_from}_${filters.value.date_to}.xlsx`,
  'ТОП товаров',
)

onMounted(() => {
  document.title = 'ТОП товаров за период — wbcms'
})
</script>
