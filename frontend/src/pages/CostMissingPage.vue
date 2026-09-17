<template>
  <div class="container-xxl page-cost-missing">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="page-title mb-0">Нет себестоимости</h1>
      <div class="d-flex gap-2 align-items-center">
        <div class="page-cost-missing__actions" ref="actionsRef">
          <button class="btn btn-light page-cost-missing__actions-btn" type="button" @click="actionsOpen = !actionsOpen">
            Действия с Excel <i class="bi ms-1" :class="actionsOpen ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
          </button>
          <div v-if="actionsOpen" class="page-cost-missing__actions-list">
            <button class="page-cost-missing__actions-item" :disabled="!rows.length" @click="actionsOpen = false; exportExcel()"><i class="bi bi-download me-2"></i>Скачать файл с товарами</button>
            <button class="page-cost-missing__actions-item" @click="actionsOpen = false; downloadTemplate()"><i class="bi bi-file-earmark-spreadsheet me-2"></i>Скачать шаблон</button>
          </div>
        </div>
        <router-link to="/cost-import/list" class="btn btn-outline-secondary btn-sm">К себестоимости</router-link>
      </div>
    </div>

    <div class="card card-body mb-3 page-cost-missing__filter">
      <div class="row g-3 align-items-end">
        <div class="col-md-4">
          <label class="form-label fw-bold">Период заказов</label>
          <div class="d-flex gap-2 align-items-center">
            <input v-model="filters.date_from" type="date" class="form-control" />
            <span>|</span>
            <input v-model="filters.date_to" type="date" class="form-control" />
          </div>
        </div>
        <div class="col-md-2">
          <button class="btn btn-primary w-100" :disabled="isLoading" @click="onApply">Применить</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div v-if="isLoading" class="text-center p-5">
        <div class="spinner-border text-primary" role="status"></div>
        <div class="mt-2 text-muted">Загрузка данных...</div>
      </div>
      <div v-else class="wb-table-wrap">
        <vxe-table
          :data="rows"
          class="page-cost-missing__grid"
          border
          stripe
          size="mini"
          auto-resize
          show-overflow="title"
          header-align="center"
          :edit-config="{ trigger: 'click', mode: 'cell' }"
          :row-config="{ isHover: true }"
          :scroll-x="{ enabled: true, gt: 0 }"
        >
          <vxe-column field="nmID" title="Артикул WB" :width="90" align="center" sortable />
          <vxe-column field="vendorCode" title="Артикул" :width="170" align="center" />
          <vxe-column field="title" title="Товар" :min-width="220" :show-overflow="false" header-align="center" sortable />
          <vxe-column field="chrtID" title="ID Размера" :width="95" align="center" />
          <vxe-column field="sku" title="Баркод" :width="125" align="center" />
          <vxe-column field="orders_cnt" title="Заказов" :width="60" align="center" sortable />
          <vxe-column field="first_order" title="Первый заказ" :width="95" align="center" />
          <vxe-column field="cost_date" title="Дата себ." :width="130" align="center" class-name="page-cost-missing__editable" :edit-render="{}">
            <template #edit="{ row }"><input v-model="row.cost_date" type="date" class="form-control form-control-sm" /></template>
          </vxe-column>
          <vxe-column field="cost_price" title="Себ-ть" :width="100" align="right" class-name="page-cost-missing__editable" :edit-render="{}">
            <template #default="{ row }">
              <span class="page-cost-missing__price">{{ row.cost_price }}</span>
              <span v-if="row.state" class="small ms-2" :class="row.stateCls">{{ row.state }}</span>
            </template>
            <template #edit="{ row }"><input v-model="row.cost_price" class="form-control form-control-sm text-end" /></template>
          </vxe-column>
          <vxe-column title="" :width="60" align="center">
            <template #default="{ row }">
              <button class="btn btn-sm btn-success" :disabled="row.saving" @click="saveRow(row)">OK</button>
            </template>
          </vxe-column>
        </vxe-table>
        <div v-if="!rows.length" class="text-center text-muted py-4">Все заказанные товары с себестоимостью</div>
          <div v-if="totalPages > 1" class="d-flex gap-2 align-items-center p-2">
            <button class="btn btn-sm btn-outline-secondary" :disabled="page <= 1" @click="goPage(page - 1)">‹ Назад</button>
            <span class="text-muted">Стр {{ page }} / {{ totalPages }} (всего {{ total }})</span>
            <button class="btn btn-sm btn-outline-secondary" :disabled="page >= totalPages" @click="goPage(page + 1)">Вперед ›</button>
          </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-cost-missing.css'
import 'vxe-table/lib/style.css'
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { VxeTable, VxeColumn } from 'vxe-table'
import { costApi } from '@/api/cost'

const today = new Date()
const defTo = today.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 120 * 864e5).toISOString().slice(0, 10)

const filters = reactive({ date_from: defFrom, date_to: defTo })
const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const isLoading = ref(false)
const actionsOpen = ref(false)
const actionsRef = ref<HTMLDivElement | null>(null)

const dayBefore = (iso: string) => {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

async function fetchData() {
  isLoading.value = true
  try {
    const data = await costApi.missing(filters.date_from, filters.date_to, page.value)
    rows.value = (data.models || []).map((r: any) => ({
      ...r,
      cost_date: dayBefore(r.first_order),
      cost_price: '',
      saving: false,
      state: '',
      stateCls: '',
    }))
    total.value = Number(data.total) || 0
    pageSize.value = Number(data.page_size) || 100
    document.title = 'Нет себестоимости — wbcms'
  } catch {
    rows.value = []
  } finally {
    isLoading.value = false
  }
}

function goPage(p: number) {
  page.value = p
  fetchData()
}

function onApply() {
  page.value = 1
  fetchData()
}

function onDocClick(e: MouseEvent) {
  if (actionsOpen.value && actionsRef.value && !actionsRef.value.contains(e.target as Node)) {
    actionsOpen.value = false
  }
}

async function saveRow(r: any) {
  if (!String(r.cost_price).trim() || !r.cost_date) {
    r.state = 'заполни дату и цену'
    r.stateCls = 'text-danger'
    return
  }
  r.saving = true
  try {
    const res = await costApi.save(r.cost_date, [{
      nmID: String(r.nmID),
      price: Number(String(r.cost_price).replace(',', '.')),
      chrtID: r.chrtID ? String(r.chrtID) : undefined,
      sku: r.sku || undefined,
    }])
    if (!res.success) throw new Error(res.message)
    r.state = '✓ сохранено'
    r.stateCls = 'text-success'
    setTimeout(() => {
      rows.value = rows.value.filter((x) => x !== r)
    }, 800)
  } catch (e: any) {
    r.state = e?.response?.data?.message || e?.message || 'Ошибка'
    r.stateCls = 'text-danger'
  } finally {
    r.saving = false
  }
}

async function exportExcel() {
  if (!rows.value.length) return
  const XLSX = await import('xlsx')
  const data = rows.value.map((r) => ({
    'Артикул WB': r.nmID, 'Артикул': r.vendorCode, 'Товар': r.title,
    'ID Размера': r.chrtID, 'Баркод': r.sku, 'Заказов': r.orders_cnt,
    'Первый заказ': r.first_order, 'Дата себестоимости': r.cost_date, 'Себестоимость': r.cost_price,
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{ wch: 12 }, { wch: 16 }, { wch: 32 }, { wch: 12 }, { wch: 18 }, { wch: 10 }, { wch: 13 }, { wch: 16 }, { wch: 14 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Нет себестоимости')
  XLSX.writeFile(wb, 'cost-missing.xlsx')
}

async function downloadTemplate() {
  const XLSX = await import('xlsx')
  const ws = XLSX.utils.json_to_sheet([{ 'Артикул продавца': '', Баркод: '', Цена: '' }])
  ws['!cols'] = [{ wch: 20 }, { wch: 18 }, { wch: 12 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Шаблон')
  XLSX.writeFile(wb, 'cost-template.xlsx')
}

onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  fetchData()
})

onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))
</script>
