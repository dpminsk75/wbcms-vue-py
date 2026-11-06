<template>
  <div class="container-xxl page-stock-warehouses">
    <!-- Шапка блока «Документы»: заголовок + правое меню (пилюли темы) -->
    <WbWorkspaceHead
      :title="$route.meta.title || 'Склады'"
      :workspace-tabs="STOCK_DOCS_TABS"
      workspace-active="warehouses"
    />

    <div class="page-stock-warehouses__head">
      <span class="spacer"></span>
      <button class="btn btn--brand btn-sm" @click="openCreate">
        <i class="bi bi-plus-lg me-1"></i>Добавить склад
      </button>
    </div>

    <!-- Предупреждения — тонированные панели темы -->
    <div v-if="!fbsId" class="wb-panel page-stock-warehouses__note page-stock-warehouses__note--bad">
      <div class="wb-panel__bd">
        <i class="bi bi-exclamation-triangle me-1"></i>
        Нет склада с признаком <b>FBS (оперативный)</b> — списание FBS-заказов из виртуальных
        остатков не работает (робот отвечает «нет склада our_warehouse is_fbs=1»).
      </div>
    </div>
    <div v-else-if="!centralId" class="wb-panel page-stock-warehouses__note page-stock-warehouses__note--warn">
      <div class="wb-panel__bd">
        <i class="bi bi-exclamation-triangle me-1"></i>
        Нет центрального склада — импорт остатков центрального склада работать не будет.
      </div>
    </div>

    <!-- Свои склады — таблица темы .tbl-card -->
    <div class="tbl-card">
      <div class="card__hd">
        <span>Свои склады</span>
        <span class="hd-badge">{{ rows.length }}</span>
      </div>

      <div v-if="loading" class="page-stock-warehouses__loading">
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span>Загрузка данных…</span>
      </div>
      <div v-else-if="!rows.length" class="page-stock-warehouses__empty">
        Складов пока нет. Добавьте центральный склад и склад FBS.
      </div>
      <div v-else class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="t-center page-stock-warehouses__col-id">ID</th>
              <th class="t-left">Название</th>
              <th class="t-left">Код</th>
              <th class="t-left">Адрес</th>
              <th class="t-center">Центральный</th>
              <th class="t-center">FBS</th>
              <th class="t-center">Учитывать заказы</th>
              <th class="t-center">Активен</th>
              <th class="t-right page-stock-warehouses__col-act"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in rows" :key="w.id" :class="{ 'page-stock-warehouses__row--off': !w.is_active }">
              <td class="t-center num">{{ w.id }}</td>
              <td class="t-left">{{ w.name }}</td>
              <td class="t-left">{{ w.code || '—' }}</td>
              <td class="t-left page-stock-warehouses__sub">{{ w.address || '—' }}</td>
              <td class="t-center">
                <button class="btn btn-sm page-stock-warehouses__toggle"
                        :class="w.is_central ? 'btn--outline-ok' : 'btn--outline'"
                        @click="toggle(w, 'is_central')">{{ w.is_central ? 'Да' : 'Нет' }}</button>
              </td>
              <td class="t-center">
                <button class="btn btn-sm page-stock-warehouses__toggle"
                        :class="w.is_fbs ? 'btn--outline-ok' : 'btn--outline'"
                        @click="toggle(w, 'is_fbs')">{{ w.is_fbs ? 'Да' : 'Нет' }}</button>
              </td>
              <td class="t-center">
                <button class="btn btn-sm page-stock-warehouses__toggle"
                        :class="w.consider_orders ? 'btn--outline-ok' : 'btn--outline'"
                        @click="toggle(w, 'consider_orders')">{{ w.consider_orders ? 'Да' : 'Нет' }}</button>
              </td>
              <td class="t-center">
                <button class="btn btn-sm page-stock-warehouses__toggle"
                        :class="w.is_active ? 'btn--outline-ok' : 'btn--outline'"
                        @click="toggle(w, 'is_active')">{{ w.is_active ? 'Да' : 'Нет' }}</button>
              </td>
              <td class="t-right text-nowrap">
                <button class="btn btn--outline btn-sm me-1" title="Править" @click="openEdit(w)">
                  <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn--danger btn-sm" title="Удалить" @click="remove(w)">
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
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
              <label class="wb-field__label">Название *</label>
              <input v-model="form.name" class="wb-input" type="text">
            </div>
            <div class="row g-2">
              <div class="col-6 mb-2">
                <label class="wb-field__label">Код</label>
                <input v-model="form.code" class="wb-input" type="text">
              </div>
              <div class="col-6 mb-2">
                <label class="wb-field__label">Адрес</label>
                <input v-model="form.address" class="wb-input" type="text">
              </div>
            </div>
            <div class="row g-2">
              <div class="col-6 mb-1">
                <div class="form-check">
                  <input id="wh-central" v-model="form.is_central" class="form-check-input" type="checkbox">
                  <label class="form-check-label wb-check-label" for="wh-central">Центральный склад</label>
                </div>
              </div>
              <div class="col-6 mb-1">
                <div class="form-check">
                  <input id="wh-fbs" v-model="form.is_fbs" class="form-check-input" type="checkbox">
                  <label class="form-check-label wb-check-label" for="wh-fbs">FBS (оперативный)</label>
                </div>
              </div>
              <div class="col-6 mb-1">
                <div class="form-check">
                  <input id="wh-consider" v-model="form.consider_orders" class="form-check-input" type="checkbox">
                  <label class="form-check-label wb-check-label" for="wh-consider">Учитывать заказы</label>
                </div>
              </div>
              <div class="col-6 mb-1">
                <div class="form-check">
                  <input id="wh-active" v-model="form.is_active" class="form-check-input" type="checkbox">
                  <label class="form-check-label wb-check-label" for="wh-active">Активен</label>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn--outline btn-sm" @click="closeModal">Отмена</button>
            <button class="btn btn--brand btn-sm" @click="save" :disabled="!form.name.trim()">
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
import '@/assets/css/pages/page-stock-warehouses.css'
import { reactive, ref, computed } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { STOCK_DOCS_TABS } from '@/components/common/workspaceTabs'

const qc = useQueryClient()

const modalOpen = ref(false)
const editing = ref<any>(null)

const form = reactive({
  id: 0,
  name: '',
  code: '',
  address: '',
  is_central: false,
  is_fbs: false,
  consider_orders: false,
  is_active: true,
})

const { data, isLoading: loading } = useQuery({
  queryKey: ['warehouses'],
  queryFn: () => api.get('/api/warehouses').then(r => r.data),
})

const rows = computed<any[]>(() => (data.value?.rows as any[]) || [])
const centralId = computed(() => (data.value?.central_id ?? null))
const fbsId = computed(() => (data.value?.fbs_id ?? null))

const reload = () => qc.invalidateQueries({ queryKey: ['warehouses'] })

const openCreate = () => {
  editing.value = null
  Object.assign(form, {
    id: 0, name: '', code: '', address: '',
    is_central: false, is_fbs: false, consider_orders: false, is_active: true,
  })
  modalOpen.value = true
}

const openEdit = (w: any) => {
  editing.value = w
  Object.assign(form, {
    id: w.id,
    name: w.name || '',
    code: w.code || '',
    address: w.address || '',
    is_central: !!w.is_central,
    is_fbs: !!w.is_fbs,
    consider_orders: !!w.consider_orders,
    is_active: !!w.is_active,
  })
  modalOpen.value = true
}

const closeModal = () => { modalOpen.value = false }

const toggle = async (w: any, field: string) => {
  await api.post(`/api/warehouses/${w.id}/toggle`, { field })
  reload()
}

const save = async () => {
  try {
    if (editing.value) await api.put(`/api/warehouses/${form.id}`, { ...form })
    else await api.post('/api/warehouses', { ...form })
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось сохранить')
    return
  }
  closeModal()
  reload()
}

const remove = async (w: any) => {
  if (!confirm(`Удалить склад «${w.name}»?`)) return
  try {
    await api.delete(`/api/warehouses/${w.id}`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось удалить')
    return
  }
  reload()
}
</script>
