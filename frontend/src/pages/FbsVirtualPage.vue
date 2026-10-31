<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">FBS Остатки: центр + виртуальные</h1>
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-light" @click="showLog = true">
          <i class="bi bi-journal-text me-1"></i>Лог списаний
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="showWarehouses = true">
          <i class="bi bi-boxes me-1"></i>Вирт. склады
        </button>
      </div>
    </div>

    <div class="alert alert-info py-2 small">
      Источник: <b>Центральный</b> (склад is_central) — колонка «Остаток» |
      <b>Оперативный (FBS)</b> (склад is_fbs) — колонка «Количество»
      (редактируется, через Перемещение).
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-body py-2 d-flex align-items-end gap-2 flex-wrap">
        <div>
          <label class="form-label small mb-1">Поиск</label>
          <input v-model="q" class="form-control form-control-sm" style="width:280px"
                 placeholder="sku / артикул / название / nmID" @keyup.enter="reload()">
        </div>
        <div>
          <label class="form-label small mb-1">Количество</label>
          <select v-model="qty" class="form-select form-select-sm" style="width:170px" @change="reload()">
            <option value="all">Все</option>
            <option value="not_found">Не найдено</option>
            <option value="zero">Ноль</option>
            <option value="1_9">1-9</option>
          </select>
        </div>
        <div>
          <label class="form-label small mb-1">Склад выгрузки</label>
          <select v-model="whFilter" class="form-select form-select-sm" style="width:200px">
            <option value="all">Все склады</option>
            <option v-for="w in vWarehouses" :key="w.id" :value="String(w.warehouseId)">
              {{ w.name }}
            </option>
          </select>
        </div>
        <div class="form-check ms-1 mb-2">
          <input id="test-mode" v-model="testMode" class="form-check-input" type="checkbox">
          <label class="form-check-label small" for="test-mode">Тест (без выгрузки в WB)</label>
        </div>
        <div class="d-flex gap-2 mb-2">
          <button class="btn btn-sm btn-primary" @click="reload()">
            <i class="bi bi-search me-1"></i>Фильтр
          </button>
          <button class="btn btn-sm btn-outline-success" @click="fileCentral?.click()">
            <i class="bi bi-file-earmark-excel me-1"></i>Центр. склад
          </button>
          <button class="btn btn-sm btn-outline-success" @click="fileVirtual?.click()">
            <i class="bi bi-file-earmark-excel me-1"></i>Вирт. остатки
          </button>
          <input ref="fileCentral" type="file" class="d-none" accept=".xlsx,.xls" @change="onFile($event, 'central')">
          <input ref="fileVirtual" type="file" class="d-none" accept=".xlsx,.xls" @change="onFile($event, 'virtual')">
          <button class="btn btn-sm btn-warning" :disabled="uploading" @click="uploadAll">
            <i class="bi bi-cloud-upload me-1"></i>{{ uploading ? 'Выгрузка...' : 'Выгрузить' }}
          </button>
        </div>
        <div class="ms-auto text-muted small mb-2">Записей: {{ total }}</div>
      </div>
    </div>

    <div v-if="msg" class="alert py-2 small" :class="msg.ok ? 'alert-success' : 'alert-danger'">
      <pre class="mb-0" style="white-space:pre-wrap">{{ msg.text }}</pre>
    </div>

    <div class="card shadow-sm">
      <div class="card-body p-0">
        <div v-if="loading" class="text-center p-5">
          <div class="spinner-border text-primary" role="status"></div>
        </div>
        <div v-else class="table-responsive">
          <table class="table table-bordered table-striped table-hover align-middle mb-0">
            <thead>
              <tr>
                <th>Товар</th>
                <th style="width:170px">Баркод</th>
                <th class="text-center" style="width:100px">Остаток</th>
                <th class="text-center" style="width:130px">Количество</th>
                <th class="text-center" style="width:120px">Действия</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.sku">
                <td>
                  <div class="fw-bold">{{ r.vendorCode }}</div>
                  <div class="small text-muted">{{ r.nmID }} — {{ r.title }}</div>
                </td>
                <td class="font-monospace small">
                  {{ r.sku }}
                  <button class="btn btn-sm btn-link p-0 ms-1" title="Копировать"
                          @click="copy(r.sku)"><i class="bi bi-clipboard"></i></button>
                </td>
                <td class="text-center" style="background:#f0f6ff">
                  {{ r.central_qty === null ? '—' : r.central_qty }}
                </td>
                <td class="text-center" style="background:#fff8e1">
                  <input v-model.number="edits[r.sku]" class="form-control form-control-sm text-end"
                         type="number" style="width:90px; display:inline-block"
                         :placeholder="r.virtual_qty === null ? '' : String(r.virtual_qty)">
                </td>
                <td class="text-center text-nowrap">
                  <button class="btn btn-sm btn-outline-secondary me-1" title="Выгрузить в WB"
                          @click="uploadOne(r)"><i class="bi bi-cloud-upload"></i></button>
                  <button class="btn btn-sm btn-outline-danger" title="Очистить (возврат на центр)"
                          @click="removeVirtual(r)"><i class="bi bi-trash"></i></button>
                </td>
              </tr>
              <tr v-if="!rows.length">
                <td colspan="5" class="text-center text-muted py-3">Ничего не найдено</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="d-flex justify-content-between align-items-center mt-2">
      <span class="small text-muted">Стр. {{ page }} / {{ pages }}</span>
      <div class="btn-group">
        <button class="btn btn-sm btn-light" :disabled="page <= 1" @click="page--; reload()">
          <i class="bi bi-chevron-left"></i>
        </button>
        <button class="btn btn-sm btn-light" :disabled="page >= pages" @click="page++; reload()">
          <i class="bi bi-chevron-right"></i>
        </button>
      </div>
    </div>

    <!-- склады WB -->
    <div class="modal fade" :class="{ show: showWarehouses }" tabindex="-1" @click.self="showWarehouses = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">Склады WB (виртуальные / учёт заказов)</h6>
            <button type="button" class="btn-close" @click="showWarehouses = false"></button>
          </div>
          <div class="modal-body">
            <table class="table table-sm table-bordered table-striped align-middle mb-0">
              <thead>
                <tr>
                  <th>ID</th><th>Название</th><th class="text-center">Виртуальный</th>
                  <th class="text-center">Учитывать заказы</th><th></th><th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="w in warehouses" :key="w.id" :style="w.is_processing ? '' : 'background:#fff3cd'">
                  <td>{{ w.warehouseId }}</td>
                  <td>{{ w.name }}<br><small class="text-muted">{{ w.address }}</small></td>
                  <td class="text-center">
                    <span class="badge" :class="w.is_virtual ? 'bg-success' : 'bg-secondary'">
                      {{ w.is_virtual ? 'Да' : 'Нет' }}
                    </span>
                  </td>
                  <td class="text-center">
                    <span class="badge" :class="w.consider_orders ? 'bg-info' : 'bg-secondary'">
                      {{ w.consider_orders ? 'Да' : 'Нет' }}
                    </span>
                  </td>
                  <td>
                    <button class="btn btn-xs btn-sm w-100"
                            :class="w.is_virtual ? 'btn-warning' : 'btn-success'"
                            @click="toggleWh(w, 'is_virtual')">
                      {{ w.is_virtual ? 'Снять' : 'Сделать виртуальным' }}
                    </button>
                  </td>
                  <td>
                    <button class="btn btn-xs btn-sm w-100"
                            :class="w.consider_orders ? 'btn-info' : 'btn-secondary'"
                            @click="toggleWh(w, 'consider_orders')">
                      {{ w.consider_orders ? 'Не учитывать' : 'Учитывать' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showWarehouses" class="modal-backdrop fade show"></div>

    <!-- лог списаний -->
    <div class="modal fade" :class="{ show: showLog }" tabindex="-1" @click.self="showLog = false">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">Лог вычета заказов из виртуальных остатков</h6>
            <button type="button" class="btn-close" @click="showLog = false"></button>
          </div>
          <div class="modal-body">
            <p class="small text-muted">
              Данные из wb_stock_ledger (doc_type='fbs_order'). Ожидающих списаний: {{ logPending }}.
            </p>
            <table class="table table-sm table-striped table-bordered align-middle mb-0">
              <thead>
                <tr><th>Дата</th><th>Заказ</th><th>Склад</th><th>Баркод</th>
                  <th class="text-end">Дельта</th><th class="text-end">До</th><th class="text-end">После</th></tr>
              </thead>
              <tbody>
                <tr v-for="l in logRows" :key="l.id">
                  <td class="small">{{ l.created_at }}</td>
                  <td class="small">{{ l.doc_id }}</td>
                  <td class="small">{{ l.warehouse_name || l.warehouseId }}</td>
                  <td class="font-monospace small">{{ l.sku }}</td>
                  <td class="text-end" :class="l.qty_delta < 0 ? 'text-danger' : 'text-success'">{{ l.qty_delta }}</td>
                  <td class="text-end">{{ l.qty_before }}</td>
                  <td class="text-end">{{ l.qty_after }}</td>
                </tr>
                <tr v-if="!logRows.length">
                  <td colspan="7" class="text-center text-muted py-3">Списаний пока нет</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showLog" class="modal-backdrop fade show"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'

const qc = useQueryClient()

const q = ref('')
const qty = ref('all')
const whFilter = ref('all')
const testMode = ref(true)
const page = ref(1)
const pageSize = 100
const edits = reactive<Record<string, number | null>>({})
const msg = ref<{ ok: boolean, text: string } | null>(null)
const uploading = ref(false)
const fileCentral = ref<HTMLInputElement | null>(null)
const fileVirtual = ref<HTMLInputElement | null>(null)

const showWarehouses = ref(false)
const showLog = ref(false)
const warehouses = ref<any[]>([])
const logRows = ref<any[]>([])
const logPending = ref(0)

const { data, isLoading: loading } = useQuery({
  queryKey: ['fbs-virtual-stocks', q.value, qty.value, page.value],
  queryFn: () => api.get('/api/fbs-virtual/stocks', {
    params: { q: q.value || undefined, qty: qty.value, page: page.value, page_size: pageSize },
  }).then(r => r.data),
})

const rows = computed<any[]>(() => (data.value?.rows as any[]) || [])
const total = computed(() => Number(data.value?.total || 0))
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const vWarehouses = computed(() => warehouses.value.filter(w => w.is_virtual))

const reload = () => qc.invalidateQueries({ queryKey: ['fbs-virtual-stocks'] })

const loadWarehouses = async () => {
  const res = await api.get('/api/fbs-virtual/warehouses').then(r => r.data).catch(() => ({ rows: [] }))
  warehouses.value = res.rows || []
}

const loadLog = async () => {
  const res = await api.get('/api/fbs-virtual/deduct-log', { params: { limit: 200 } })
    .then(r => r.data).catch(() => ({ rows: [], pending_orders: 0 }))
  logRows.value = res.rows || []
  logPending.value = Number(res.pending_orders || 0)
}

onMounted(loadWarehouses)
watch(showLog, (v) => { if (v) loadLog() })

const toggleWh = async (w: any, field: string) => {
  await api.post(`/api/fbs-virtual/warehouses/${w.id}/toggle`, { field })
  await loadWarehouses()
}

const copy = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}

/** Сбор правок: измененные инпуты + импортированные значения. */
const collectChanges = (): { sku: string, qty: number }[] => {
  const out: { sku: string, qty: number }[] = []
  for (const r of rows.value) {
    const v = edits[r.sku]
    if (v !== undefined && v !== null && !Number.isNaN(Number(v))) {
      out.push({ sku: r.sku, qty: Number(v) })
    }
  }
  return out
}

const onFile = async (ev: Event, target: 'central' | 'virtual') => {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const XLSX = await import('xlsx')
    const buf = await file.arrayBuffer()
    const wb = XLSX.read(buf, { type: 'array' })
    const ws = wb.Sheets[wb.SheetNames[0]]
    const grid: any[][] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
    const res = await api.post('/api/fbs-virtual/parse', { rows: grid }).then(r => r.data)
    const matched = res.matched || []
    const skipped = res.skipped || []
    const changes = matched.map((m: any) => ({ sku: m.sku, qty: m.qty }))
    const saved = await api.post(
      target === 'central' ? '/api/fbs-virtual/save-central' : '/api/fbs-virtual/save-virtual',
      { changes },
    ).then(r => r.data)
    msg.value = {
      ok: true,
      text: `Импорт (${target === 'central' ? 'центральный' : 'виртуальные'}): `
        + `найдено ${matched.length}, не найдено ${skipped.length}, сохранено ${saved.processed}`
        + (skipped.length ? `\n` + skipped.join('\n') : ''),
    }
    reload()
  } catch (e: any) {
    msg.value = { ok: false, text: e?.response?.data?.detail || 'Ошибка импорта' }
  } finally {
    input.value = ''
  }
}

const uploadAll = async () => {
  uploading.value = true
  msg.value = null
  try {
    const res = await api.post('/api/fbs-virtual/upload-all', {
      test: testMode.value,
      warehouse_id: whFilter.value,
    }).then(r => r.data)
    const lines = (res.results || []).map((x: any) =>
      `склад ${x.warehouseId}${x.chunk ? ` чанк ${x.chunk}` : ''}: ${x.ok ? 'ok' : 'ошибка ' + (x.status || '')}`)
    msg.value = { ok: true, text: `${res.dry ? '[ТЕСТ] ' : ''}Выгрузка завершена:\n` + lines.join('\n') }
  } catch (e: any) {
    msg.value = { ok: false, text: e?.response?.data?.detail || 'Ошибка выгрузки' }
  } finally {
    uploading.value = false
  }
}

const uploadOne = async (r: any) => {
  const amount = edits[r.sku] !== undefined && edits[r.sku] !== null
    ? Number(edits[r.sku]) : (r.virtual_qty ?? 0)
  try {
    const res = await api.post('/api/fbs-virtual/upload-one', {
      sku: r.sku,
      amount,
      test: testMode.value,
      warehouse_id: whFilter.value,
    }).then(r => r.data)
    msg.value = {
      ok: true,
      text: `${res.dry ? '[ТЕСТ] ' : ''}Выгружено ${r.sku} (${amount}): `
        + (res.results || []).map((x: any) => `склад ${x.warehouseId} — ${x.ok ? 'ok' : 'ошибка'}`).join('; '),
    }
  } catch (e: any) {
    msg.value = { ok: false, text: e?.response?.data?.detail || 'Ошибка выгрузки' }
  }
}

const removeVirtual = async (r: any) => {
  if (!confirm(`Очистить количество для ${r.sku}? Остаток вернётся на центральный склад.`)) return
  try {
    await api.post('/api/fbs-virtual/delete-virtual', { sku: r.sku })
  } catch (e: any) {
    msg.value = { ok: false, text: e?.response?.data?.detail || 'Ошибка' }
    return
  }
  reload()
}
</script>
