<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">{{ $route.meta.title || 'Документы склада' }}</h1>
      <div class="d-flex gap-2 flex-wrap">
        <button
          v-for="t in DOC_TYPES"
          :key="t.value"
          class="btn btn-sm btn-outline-primary"
          @click="create(t.value)"
        >
          <i class="bi bi-plus-lg me-1"></i>{{ t.label }}
        </button>
      </div>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-body py-2 d-flex align-items-center gap-2 flex-wrap">
        <select v-model="typeFilter" class="form-select form-select-sm" style="width:220px" @change="reload">
          <option value="">Все типы</option>
          <option v-for="t in DOC_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
        <span class="text-muted small">Записей: {{ total }}</span>
        <div class="ms-auto d-flex align-items-center gap-2">
          <button class="btn btn-sm btn-light" :disabled="page <= 1" @click="page--; reload()">
            <i class="bi bi-chevron-left"></i>
          </button>
          <span class="small">{{ page }} / {{ pages }}</span>
          <button class="btn btn-sm btn-light" :disabled="page >= pages" @click="page++; reload()">
            <i class="bi bi-chevron-right"></i>
          </button>
        </div>
      </div>
    </div>

    <div class="card shadow-sm">
      <div class="card-body p-0">
        <div v-if="loading" class="text-center p-5">
          <div class="spinner-border text-primary" role="status"></div>
        </div>
        <div v-else-if="!rows.length" class="p-4 text-center text-muted">Документов пока нет</div>
        <div v-else class="table-responsive">
          <table class="table table-bordered table-striped table-hover align-middle mb-0">
            <thead>
              <tr>
                <th style="width:70px">ID</th>
                <th style="width:150px">Дата</th>
                <th style="width:150px">Тип</th>
                <th style="width:120px">Статус</th>
                <th>Склад</th>
                <th style="width:90px">Позиций</th>
                <th>Комментарий</th>
                <th style="width:230px"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in rows" :key="d.id">
                <td>{{ d.id }}</td>
                <td class="small">{{ formatDate(d.date) }}</td>
                <td>{{ d.type_label }}</td>
                <td>
                  <span class="badge" :class="statusClass(d.status)">{{ d.status_label }}</span>
                </td>
                <td class="small">
                  {{ d.warehouse_name || d.warehouseId }}
                  <span v-if="d.type === 'TRANSFER'">
                    <i class="bi bi-arrow-right"></i> {{ d.to_warehouse_name || d.to_warehouseId }}
                  </span>
                </td>
                <td class="text-center">{{ d.items_count }}</td>
                <td class="small text-muted">{{ d.comment || '' }}</td>
                <td class="text-end text-nowrap">
                  <router-link class="btn btn-sm btn-outline-secondary" :to="`/wb-doc/${d.id}`">
                    <i class="bi bi-eye"></i>
                  </router-link>
                  <button v-if="d.status !== 'posted'" class="btn btn-sm btn-outline-secondary ms-1"
                          @click="edit(d)"><i class="bi bi-pencil"></i></button>
                  <button v-if="d.status === 'draft'" class="btn btn-sm btn-outline-success ms-1"
                          @click="post(d)"><i class="bi bi-check2-circle"></i></button>
                  <button v-if="d.status === 'posted'" class="btn btn-sm btn-outline-warning ms-1"
                          @click="cancel(d)"><i class="bi bi-arrow-counterclockwise"></i></button>
                  <button v-if="d.status !== 'posted'" class="btn btn-sm btn-outline-danger ms-1"
                          @click="remove(d)"><i class="bi bi-trash"></i></button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'
import { DOC_TYPES, type DocStatus, type DocType, type StockDoc } from '@/api/stockDocs'

const router = useRouter()
const qc = useQueryClient()

const typeFilter = ref('')
const page = ref(1)
const pageSize = 20

const { data, isLoading: loading } = useQuery({
  queryKey: ['stock-docs', typeFilter.value, page.value],
  queryFn: () => api.get('/api/stock-docs', {
    params: { type: typeFilter.value || undefined, page: page.value, page_size: pageSize },
  }).then(r => r.data),
})

const rows = computed<StockDoc[]>(() => (data.value?.rows as StockDoc[]) || [])
const total = computed(() => Number(data.value?.total || 0))
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const reload = () => qc.invalidateQueries({ queryKey: ['stock-docs'] })

const formatDate = (s: string) => (s ? String(s).slice(0, 16).replace('T', ' ') : '—')

const statusClass = (s: DocStatus) => ({
  draft: 'bg-secondary',
  posted: 'bg-success',
  canceled: 'bg-dark',
}[s] || 'bg-secondary')

const create = (t: DocType) => router.push({ path: '/wb-doc/create', query: { type: t } })
const edit = (d: StockDoc) => router.push({ path: `/wb-doc/${d.id}/edit` })

const post = async (d: StockDoc) => {
  if (!confirm(`Провести документ №${d.id}? Остатки изменятся.`)) return
  try {
    await api.post(`/api/stock-docs/${d.id}/post`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось провести')
    return
  }
  reload()
}

const cancel = async (d: StockDoc) => {
  if (!confirm(`Отменить документ №${d.id}? Будет создано сторно.`)) return
  try {
    await api.post(`/api/stock-docs/${d.id}/cancel`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось отменить')
    return
  }
  reload()
}

const remove = async (d: StockDoc) => {
  if (!confirm(`Удалить документ №${d.id}?`)) return
  try {
    await api.delete(`/api/stock-docs/${d.id}`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось удалить')
    return
  }
  reload()
}
</script>
