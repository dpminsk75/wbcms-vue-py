<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">
        {{ isEdit ? `Документ №${docId} — правка` : 'Новый документ' }}
        <span v-if="typeLabel" class="badge bg-primary ms-2">{{ typeLabel }}</span>
      </h1>
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-light" @click="goBack">
          <i class="bi bi-arrow-left me-1"></i>К списку
        </button>
        <button class="btn btn-sm btn-primary" :disabled="saving || !canSave" @click="save">
          <i class="bi bi-save me-1"></i>{{ saving ? 'Сохранение...' : 'Сохранить' }}
        </button>
      </div>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-body row g-3">
        <div class="col-md-3">
          <label class="form-label small mb-1">Тип</label>
          <input class="form-control form-control-sm" :value="typeLabel" disabled>
        </div>
        <div class="col-md-3">
          <label class="form-label small mb-1">
            {{ type === 'TRANSFER' ? 'Склад (откуда)' : 'Склад' }} *
          </label>
          <select v-model.number="form.warehouse_id" class="form-select form-select-sm">
            <option :value="0">— выберите —</option>
            <option v-for="w in warehouses" :key="w.id" :value="w.id">
              {{ w.name }}{{ w.is_central ? ' (центральный)' : '' }}{{ w.is_fbs ? ' (FBS)' : '' }}
            </option>
          </select>
        </div>
        <div v-if="type === 'TRANSFER'" class="col-md-3">
          <label class="form-label small mb-1">Склад (куда) *</label>
          <select v-model.number="form.to_warehouse_id" class="form-select form-select-sm">
            <option :value="0">— выберите —</option>
            <option v-for="w in warehouses" :key="w.id" :value="w.id">{{ w.name }}</option>
          </select>
        </div>
        <div class="col-md-3">
          <label class="form-label small mb-1">Дата</label>
          <input v-model="form.date" type="datetime-local" class="form-control form-control-sm">
        </div>
        <div class="col-12">
          <label class="form-label small mb-1">
            Комментарий<span v-if="type === 'ADJUSTMENT'" class="text-danger"> *</span>
          </label>
          <input v-model="form.comment" type="text" class="form-control form-control-sm"
                 placeholder="для корректировки — обязательно (причина)">
        </div>
      </div>
    </div>

    <div class="card shadow-sm">
      <div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
        <span class="fw-bold">Позиции</span>
        <div class="d-flex gap-2 align-items-center">
          <button class="btn btn-sm btn-outline-success" @click="fileRef?.click()">
            <i class="bi bi-file-earmark-excel me-1"></i>Импорт из Excel
          </button>
          <input ref="fileRef" type="file" class="d-none" accept=".xlsx,.xls" @change="onFile">
          <button class="btn btn-sm btn-outline-primary" @click="addRow">
            <i class="bi bi-plus-lg me-1"></i>Добавить позицию
          </button>
        </div>
      </div>
      <div class="card-body p-0">
        <div v-if="importInfo" class="alert alert-info py-2 px-3 small mb-0 rounded-0">
          Импорт: найдено {{ importInfo.matched }}, не найдено {{ importInfo.skipped.length }}
          <div v-if="importInfo.skipped.length" class="mt-1 small text-muted"
               style="max-height:120px; overflow:auto; white-space:pre-wrap">
            {{ importInfo.skipped.join('\n') }}
          </div>
        </div>
        <div class="table-responsive">
          <table class="table table-bordered table-striped table-hover align-middle mb-0">
            <thead>
              <tr>
                <th style="width:150px">Баркод</th>
                <th>Товар</th>
                <th v-if="type === 'INVENTORY'" style="width:110px">По учету</th>
                <th v-if="type === 'INVENTORY'" style="width:110px">Факт</th>
                <th v-else style="width:110px">
                  {{ type === 'ADJUSTMENT' ? 'Корректировка' : 'Количество' }}
                </th>
                <th v-if="type === 'INVENTORY'" style="width:110px">Разница</th>
                <th style="width:60px"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(it, i) in items" :key="i">
                <td>
                  <input v-model="it.sku" class="form-control form-control-sm" type="text"
                         list="sku-options" @change="resolveRow(it)">
                  <datalist id="sku-options">
                    <option v-for="o in searchOptions" :key="o.sku" :value="o.sku">
                      {{ o.label }}
                    </option>
                  </datalist>
                </td>
                <td class="small">
                  <div>{{ it.title || '' }}</div>
                  <div class="text-muted">{{ it.vendorCode || '' }}</div>
                </td>
                <td v-if="type === 'INVENTORY'">
                  <input v-model.number="it.qty_before" class="form-control form-control-sm text-end"
                         type="number" @change="it.qty_fact = it.qty_fact ?? null">
                </td>
                <td v-if="type === 'INVENTORY'">
                  <input v-model.number="it.qty_fact" class="form-control form-control-sm text-end" type="number">
                </td>
                <td v-else>
                  <input v-model.number="it.qty" class="form-control form-control-sm text-end" type="number">
                </td>
                <td v-if="type === 'INVENTORY'" class="text-end fw-bold"
                    :class="deltaClass(it)">
                  {{ delta(it) > 0 ? '+' : '' }}{{ delta(it) }}
                </td>
                <td class="text-end">
                  <button class="btn btn-sm btn-outline-danger" @click="items.splice(i, 1)">
                    <i class="bi bi-trash"></i>
                  </button>
                </td>
              </tr>
              <tr v-if="!items.length">
                <td :colspan="type === 'INVENTORY' ? 6 : 4" class="text-center text-muted py-3">
                  Позиций нет — добавьте вручную или импортируйте из Excel
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
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { DOC_TYPES, type DocItem, type DocMeta, type DocType } from '@/api/stockDocs'

const route = useRoute()
const router = useRouter()

const docId = computed(() => Number(route.params.id || 0) || 0)
const isEdit = computed(() => docId.value > 0)

const type = ref<DocType>((route.query.type as DocType) || 'RECEIPT')
const typeLabel = computed(() => DOC_TYPES.find(t => t.value === type.value)?.label || type.value)

const warehouses = ref<DocMeta['warehouses']>([])
const items = ref<DocItem[]>([])
const searchOptions = ref<{ sku: string, label: string }[]>([])
const fileRef = ref<HTMLInputElement | null>(null)
const saving = ref(false)
const importInfo = ref<{ matched: number, skipped: string[] } | null>(null)

const form = ref({
  warehouse_id: 0,
  to_warehouse_id: 0,
  date: new Date().toISOString().slice(0, 16),
  comment: '',
})

const canSave = computed(() => {
  if (!form.value.warehouse_id) return false
  if (type.value === 'TRANSFER' && !form.value.to_warehouse_id) return false
  if (type.value === 'ADJUSTMENT' && !form.value.comment.trim()) return false
  return true
})

const delta = (it: DocItem) => {
  const fact = Number(it.qty_fact ?? it.qty ?? 0)
  const before = Number(it.qty_before ?? 0)
  return fact - before
}
const deltaClass = (it: DocItem) => {
  const d = delta(it)
  return d > 0 ? 'text-success' : (d < 0 ? 'text-danger' : '')
}

const goBack = () => router.push('/wb-doc')

onMounted(async () => {
  const meta = await api.get('/api/stock-docs/meta').then(r => r.data as DocMeta)
  warehouses.value = meta.warehouses || []
  if (isEdit.value) {
    const doc = await api.get(`/api/stock-docs/${docId.value}`).then(r => r.data)
    type.value = doc.type
    form.value = {
      warehouse_id: doc.warehouseId,
      to_warehouse_id: doc.to_warehouseId || 0,
      date: String(doc.date || '').slice(0, 16),
      comment: doc.comment || '',
    }
    items.value = (doc.items || []).map((i: any) => ({
      sku: i.sku,
      nm_id: i.nmID,
      chrt_id: i.chrtID,
      qty: Number(i.qty || 0),
      qty_before: i.qty_before,
      qty_fact: i.qty_fact,
      vendorCode: i.vendorCode,
      title: i.title,
    }))
  } else if (!form.value.warehouse_id && warehouses.value.length) {
    form.value.warehouse_id = warehouses.value[0].id
    if (type.value === 'TRANSFER' && warehouses.value.length > 1) {
      form.value.to_warehouse_id = warehouses.value[1].id
    }
  }
})

const addRow = () => {
  items.value.push({ sku: '', qty: 0, qty_before: null, qty_fact: null })
}

/** Подставить название/артикул по введённому баркоду. */
const resolveRow = async (it: DocItem) => {
  const sku = it.sku?.trim()
  if (!sku) return
  if (!searchOptions.value.length || !searchOptions.value.some(o => o.sku === sku)) {
    const res = await api.get('/api/stock-docs/search-product', { params: { term: sku } })
      .then(r => r.data).catch(() => ({ rows: [] }))
    searchOptions.value = res.rows || []
  }
  const hit = searchOptions.value.find(o => o.sku === sku)
  if (hit) {
    it.title = (hit as any).title
    it.vendorCode = (hit as any).vendorCode
    it.nm_id = (hit as any).nmID
    it.chrt_id = (hit as any).chrtID
  }
  if (type.value === 'INVENTORY' && it.qty_before === null && form.value.warehouse_id) {
    const b = await api.get('/api/stock-docs/balance', {
      params: { sku, warehouse_id: form.value.warehouse_id },
    }).then(r => r.data).catch(() => null)
    if (b) it.qty_before = Number(b.qty || 0)
  }
}

const onFile = async (ev: Event) => {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const XLSX = await import('xlsx')
    const buf = await file.arrayBuffer()
    const wb = XLSX.read(buf, { type: 'array' })
    const ws = wb.Sheets[wb.SheetNames[0]]
    const grid: any[][] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
    const res = await api.post('/api/stock-docs/parse', { rows: grid }).then(r => r.data)
    const matched = res.matched || []
    importInfo.value = { matched: matched.length, skipped: res.skipped || [] }
    for (const m of matched) {
      const row: DocItem = {
        sku: m.sku, nm_id: m.nm_id, chrt_id: m.chrt_id,
        qty: m.qty, qty_before: null, qty_fact: null,
      }
      if (type.value === 'INVENTORY') {
        row.qty_fact = m.qty
        row.qty = m.qty
        const b = await api.get('/api/stock-docs/balance', {
          params: { sku: m.sku, warehouse_id: form.value.warehouse_id },
        }).then(r => r.data).catch(() => null)
        row.qty_before = b ? Number(b.qty || 0) : 0
      }
      items.value.push(row)
      await resolveRow(row)
    }
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Ошибка разбора файла')
  } finally {
    input.value = ''
  }
}

const save = async () => {
  saving.value = true
  try {
    const payload = {
      type: type.value,
      warehouse_id: form.value.warehouse_id,
      to_warehouse_id: form.value.to_warehouse_id || null,
      date: form.value.date,
      comment: form.value.comment,
      items: items.value.filter(i => i.sku?.trim()).map(i => ({
        sku: i.sku.trim(),
        qty: Number(i.qty || 0),
        qty_before: i.qty_before ?? null,
        qty_fact: i.qty_fact ?? null,
      })),
    }
    if (isEdit.value) {
      await api.put(`/api/stock-docs/${docId.value}`, payload)
      router.push(`/wb-doc/${docId.value}`)
    } else {
      const doc = await api.post('/api/stock-docs', payload).then(r => r.data)
      router.push(`/wb-doc/${doc.id}`)
    }
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось сохранить')
  } finally {
    saving.value = false
  }
}
</script>
