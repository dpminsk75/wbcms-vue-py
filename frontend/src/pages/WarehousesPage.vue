<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">{{ $route.meta.title || 'Склады' }}</h1>
      <button class="btn btn-primary btn-sm" @click="openCreate">
        <i class="bi bi-plus-lg me-1"></i> Добавить склад
      </button>
    </div>

    <div v-if="!fbsId" class="alert alert-danger py-2 small">
      <i class="bi bi-exclamation-triangle me-1"></i>
      Нет склада с признаком <b>FBS (оперативный)</b> — списание FBS-заказов из виртуальных
      остатков не работает (робот отвечает «нет склада our_warehouse is_fbs=1»).
    </div>
    <div v-else-if="!centralId" class="alert alert-warning py-2 small">
      <i class="bi bi-exclamation-triangle me-1"></i>
      Нет центрального склада — импорт остатков центрального склада работать не будет.
    </div>

    <div class="card shadow-sm">
      <div class="card-header text-white bg-wb-green-deep-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0"><i class="bi bi-box-seam me-2"></i>Свои склады</h5>
        <span class="badge bg-light text-dark">{{ rows.length }}</span>
      </div>
      <div class="card-body p-0">
        <div v-if="loading" class="text-center p-5">
          <div class="spinner-border text-primary" role="status"></div>
        </div>
        <div v-else-if="!rows.length" class="p-4 text-center text-muted">
          Складов пока нет. Добавьте центральный склад и склад FBS.
        </div>
        <div v-else class="table-responsive">
          <table class="table table-bordered table-striped table-hover align-middle mb-0">
            <thead>
              <tr>
                <th style="width:60px">ID</th>
                <th>Название</th>
                <th>Код</th>
                <th>Адрес</th>
                <th class="text-center">Центральный</th>
                <th class="text-center">FBS</th>
                <th class="text-center">Учитывать заказы</th>
                <th class="text-center">Активен</th>
                <th style="width:140px"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in rows" :key="w.id" :class="{ 'table-muted': !w.is_active }">
                <td>{{ w.id }}</td>
                <td class="fw-bold">{{ w.name }}</td>
                <td>{{ w.code || '—' }}</td>
                <td class="small text-muted">{{ w.address || '—' }}</td>
                <td class="text-center">
                  <button class="btn btn-xs btn-sm" :class="w.is_central ? 'btn-success' : 'btn-outline-secondary'"
                          @click="toggle(w, 'is_central')">{{ w.is_central ? 'Да' : 'Нет' }}</button>
                </td>
                <td class="text-center">
                  <button class="btn btn-xs btn-sm" :class="w.is_fbs ? 'btn-success' : 'btn-outline-secondary'"
                          @click="toggle(w, 'is_fbs')">{{ w.is_fbs ? 'Да' : 'Нет' }}</button>
                </td>
                <td class="text-center">
                  <button class="btn btn-xs btn-sm" :class="w.consider_orders ? 'btn-info' : 'btn-outline-secondary'"
                          @click="toggle(w, 'consider_orders')">{{ w.consider_orders ? 'Да' : 'Нет' }}</button>
                </td>
                <td class="text-center">
                  <button class="btn btn-xs btn-sm" :class="w.is_active ? 'btn-success' : 'btn-outline-secondary'"
                          @click="toggle(w, 'is_active')">{{ w.is_active ? 'Да' : 'Нет' }}</button>
                </td>
                <td class="text-end text-nowrap">
                  <button class="btn btn-sm btn-outline-secondary me-1" @click="openEdit(w)">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-danger" @click="remove(w)">
                    <i class="bi bi-trash"></i>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- форма создания/правки -->
    <div class="modal fade" :class="{ show: modalOpen }" tabindex="-1" @click.self="closeModal">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">{{ editing ? 'Склад: правка' : 'Новый склад' }}</h6>
            <button type="button" class="btn-close" @click="closeModal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-2">
              <label class="form-label small mb-1">Название *</label>
              <input v-model="form.name" class="form-control form-control-sm" type="text">
            </div>
            <div class="row g-2">
              <div class="col-6 mb-2">
                <label class="form-label small mb-1">Код</label>
                <input v-model="form.code" class="form-control form-control-sm" type="text">
              </div>
              <div class="col-6 mb-2">
                <label class="form-label small mb-1">Адрес</label>
                <input v-model="form.address" class="form-control form-control-sm" type="text">
              </div>
            </div>
            <div class="row g-2">
              <div class="col-6 mb-1">
                <div class="form-check">
                  <input id="wh-central" v-model="form.is_central" class="form-check-input" type="checkbox">
                  <label class="form-check-label small" for="wh-central">Центральный склад</label>
                </div>
              </div>
              <div class="col-6 mb-1">
                <div class="form-check">
                  <input id="wh-fbs" v-model="form.is_fbs" class="form-check-input" type="checkbox">
                  <label class="form-check-label small" for="wh-fbs">FBS (оперативный)</label>
                </div>
              </div>
              <div class="col-6 mb-1">
                <div class="form-check">
                  <input id="wh-consider" v-model="form.consider_orders" class="form-check-input" type="checkbox">
                  <label class="form-check-label small" for="wh-consider">Учитывать заказы</label>
                </div>
              </div>
              <div class="col-6 mb-1">
                <div class="form-check">
                  <input id="wh-active" v-model="form.is_active" class="form-check-input" type="checkbox">
                  <label class="form-check-label small" for="wh-active">Активен</label>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm btn-light" @click="closeModal">Отмена</button>
            <button class="btn btn-sm btn-primary" @click="save" :disabled="!form.name.trim()">
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="modalOpen" class="modal-backdrop fade show"></div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'
import type { Warehouse, WarehousesResponse, WarehouseToggle } from '@/api/warehouses'

const qc = useQueryClient()

const { data, isLoading: loading } = useQuery({
  queryKey: ['warehouses'],
  queryFn: () => api.get('/api/warehouses').then(r => r.data as WarehousesResponse),
})

const rows = computed<Warehouse[]>(() => (data.value?.rows as Warehouse[]) || [])
const centralId = computed(() => data.value?.central_id ?? null)
const fbsId = computed(() => data.value?.fbs_id ?? null)

const modalOpen = ref(false)
const editing = ref<Warehouse | null>(null)
const form = reactive({
  name: '', code: '', address: '',
  is_central: false, is_fbs: false, consider_orders: false, is_active: true,
})

const openCreate = () => {
  editing.value = null
  form.name = ''; form.code = ''; form.address = ''
  form.is_central = false; form.is_fbs = false; form.consider_orders = false; form.is_active = true
  modalOpen.value = true
}

const openEdit = (w: Warehouse) => {
  editing.value = w
  form.name = w.name || ''
  form.code = w.code || ''
  form.address = w.address || ''
  form.is_central = !!w.is_central
  form.is_fbs = !!w.is_fbs
  form.consider_orders = !!w.consider_orders
  form.is_active = !!w.is_active
  modalOpen.value = true
}

const closeModal = () => { modalOpen.value = false }

const reload = () => qc.invalidateQueries({ queryKey: ['warehouses'] })

const save = async () => {
  const payload = {
    name: form.name.trim(),
    code: form.code.trim() || null,
    address: form.address.trim() || null,
    is_central: form.is_central ? 1 : 0,
    is_fbs: form.is_fbs ? 1 : 0,
    consider_orders: form.consider_orders ? 1 : 0,
    is_active: form.is_active ? 1 : 0,
  }
  if (editing.value) {
    await api.put(`/api/warehouses/${editing.value.id}`, payload)
  } else {
    await api.post('/api/warehouses', payload)
  }
  modalOpen.value = false
  reload()
}

const toggle = async (w: Warehouse, field: WarehouseToggle) => {
  await api.post(`/api/warehouses/${w.id}/toggle`, { field })
  reload()
}

const remove = async (w: Warehouse) => {
  if (!confirm(`Удалить склад «${w.name}»?`)) return
  try {
    await api.delete(`/api/warehouses/${w.id}`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось удалить склад')
    return
  }
  reload()
}
</script>
