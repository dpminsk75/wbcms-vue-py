<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3 no-print">
      <h1 class="page-title mb-0">
        Документ №{{ doc?.id }}
        <span class="badge bg-primary ms-2">{{ doc?.type_label }}</span>
        <span class="badge ms-2" :class="statusClass">{{ doc?.status_label }}</span>
      </h1>
      <div class="d-flex gap-2 flex-wrap">
        <button class="btn btn-sm btn-light" @click="router.push('/wb-doc')">
          <i class="bi bi-arrow-left me-1"></i>К списку
        </button>
        <button v-if="doc?.status !== 'posted'" class="btn btn-sm btn-outline-secondary"
                @click="router.push(`/wb-doc/${docId}/edit`)">
          <i class="bi bi-pencil me-1"></i>Редактировать
        </button>
        <button v-if="doc?.status === 'draft'" class="btn btn-sm btn-outline-success" @click="post">
          <i class="bi bi-check2-circle me-1"></i>Провести
        </button>
        <button v-if="doc?.status === 'posted'" class="btn btn-sm btn-outline-warning" @click="cancel">
          <i class="bi bi-arrow-counterclockwise me-1"></i>Отменить (сторно)
        </button>
        <button v-if="doc?.status !== 'posted'" class="btn btn-sm btn-outline-danger" @click="remove">
          <i class="bi bi-trash me-1"></i>Удалить
        </button>
        <button class="btn btn-sm btn-light" @click="printPage">
          <i class="bi bi-printer me-1"></i>Печать
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-center p-5">
      <div class="spinner-border text-primary" role="status"></div>
    </div>

    <div v-else-if="doc" class="card shadow-sm">
      <div class="card-body">
        <div class="row g-3 mb-3">
          <div class="col-md-3">
            <div class="text-muted small">Тип</div>
            <div class="fw-bold">{{ doc.type_label }}</div>
          </div>
          <div class="col-md-3">
            <div class="text-muted small">Склад</div>
            <div class="fw-bold">{{ doc.warehouse_name || doc.warehouseId }}</div>
          </div>
          <div class="col-md-3">
            <div class="text-muted small">Дата</div>
            <div class="fw-bold">{{ formatDate(doc.date) }}</div>
          </div>
          <div class="col-md-3">
            <div class="text-muted small">Комментарий</div>
            <div class="fw-bold">{{ doc.comment || '—' }}</div>
          </div>
          <div v-if="doc.type === 'TRANSFER'" class="col-md-3">
            <div class="text-muted small">Склад (куда)</div>
            <div class="fw-bold">{{ doc.to_warehouse_name || doc.to_warehouseId }}</div>
          </div>
        </div>

        <div class="table-responsive">
          <table class="table table-bordered table-striped table-hover align-middle mb-0">
            <thead>
              <tr>
                <th style="width:150px">Баркод</th>
                <th>Товар</th>
                <th v-if="doc.type === 'INVENTORY'" class="text-end" style="width:110px">По учету</th>
                <th v-if="doc.type === 'INVENTORY'" class="text-end" style="width:110px">Факт</th>
                <th v-else class="text-end" style="width:120px">
                  {{ doc.type === 'ADJUSTMENT' ? 'Корректировка' : 'Количество' }}
                </th>
                <th v-if="doc.type === 'INVENTORY'" class="text-end" style="width:110px">Разница</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in doc.items || []" :key="it.id">
                <td class="font-monospace small">{{ it.sku }}</td>
                <td class="small">
                  <div>{{ it.title || '' }}</div>
                  <div class="text-muted">{{ it.vendorCode || '' }}</div>
                </td>
                <td v-if="doc.type === 'INVENTORY'" class="text-end">{{ it.qty_before ?? 0 }}</td>
                <td v-if="doc.type === 'INVENTORY'" class="text-end">{{ it.qty_fact ?? it.qty }}</td>
                <td v-else class="text-end">{{ it.qty }}</td>
                <td v-if="doc.type === 'INVENTORY'" class="text-end fw-bold"
                    :class="deltaClass(it)">
                  {{ delta(it) > 0 ? '+' : '' }}{{ delta(it) }}
                </td>
              </tr>
              <tr v-if="!(doc.items || []).length">
                <td :colspan="doc.type === 'INVENTORY' ? 6 : 4" class="text-center text-muted py-3">
                  Позиций нет
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="doc.type === 'INVENTORY'" class="mt-3">
          <div class="row">
            <div class="col">
              <div class="text-muted small">Итого по учету</div>
              <div class="fw-bold">{{ sum('qty_before') }}</div>
            </div>
            <div class="col">
              <div class="text-muted small">Итого факт</div>
              <div class="fw-bold">{{ sum('qty_fact') }}</div>
            </div>
            <div class="col">
              <div class="text-muted small">Разница</div>
              <div class="fw-bold" :class="sumDelta > 0 ? 'text-success' : (sumDelta < 0 ? 'text-danger' : '')">
                {{ sumDelta > 0 ? '+' : '' }}{{ sumDelta }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { StockDoc } from '@/api/stockDocs'

const route = useRoute()
const router = useRouter()
const docId = computed(() => Number(route.params.id || 0))
const doc = ref<StockDoc | null>(null)
const loading = ref(true)

const statusClass = computed(() => ({
  draft: 'bg-secondary',
  posted: 'bg-success',
  canceled: 'bg-dark',
}[doc.value?.status || 'draft']))

const formatDate = (s: string) => (s ? String(s).slice(0, 16).replace('T', ' ') : '—')

const delta = (it: any) => Number(it.qty_fact ?? it.qty ?? 0) - Number(it.qty_before ?? 0)
const deltaClass = (it: any) => {
  const d = delta(it)
  return d > 0 ? 'text-success' : (d < 0 ? 'text-danger' : '')
}
const sum = (key: string) => (doc.value?.items || []).reduce(
  (a: number, it: any) => a + Number(key === 'qty_fact' ? (it.qty_fact ?? it.qty ?? 0) : (it[key] ?? 0)), 0)
const sumDelta = computed(() => (doc.value?.items || []).reduce((a: number, it: any) => a + delta(it), 0))

const load = async () => {
  loading.value = true
  try {
    doc.value = await api.get(`/api/stock-docs/${docId.value}`).then(r => r.data)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const post = async () => {
  if (!confirm('Провести документ? Остатки изменятся.')) return
  try {
    await api.post(`/api/stock-docs/${docId.value}/post`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось провести')
    return
  }
  load()
}

const cancel = async () => {
  if (!confirm('Отменить документ? Будет создано сторно.')) return
  try {
    await api.post(`/api/stock-docs/${docId.value}/cancel`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось отменить')
    return
  }
  load()
}

const remove = async () => {
  if (!confirm('Удалить документ?')) return
  try {
    await api.delete(`/api/stock-docs/${docId.value}`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось удалить')
    return
  }
  router.push('/wb-doc')
}

const printPage = () => window.print()
</script>

<style>
@media print {
  .no-print { display: none !important; }
  body { background: #fff; }
}
</style>
