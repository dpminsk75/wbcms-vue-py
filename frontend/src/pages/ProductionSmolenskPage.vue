<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">Смоленск — остатки и движения</h1>
      <ul class="nav nav-pills">
        <li class="nav-item">
          <button class="nav-link" :class="{ active: tab === 'snapshots' }" @click="tab = 'snapshots'">Остатки (снапшоты)</button>
        </li>
        <li class="nav-item">
          <button class="nav-link" :class="{ active: tab === 'movements' }" @click="tab = 'movements'">Движения</button>
        </li>
        <li class="nav-item">
          <button class="nav-link" :class="{ active: tab === 'import' }" @click="tab = 'import'">Импорт Excel</button>
        </li>
      </ul>
    </div>

    <div class="alert alert-info py-2 small">
      Баланс Смоленска = <code>qty_start</code> последнего снапшота + все движения после его даты.
      Данные учитываются в отчёте «Производство» (колонки СМЛ). Карточки ищутся по компании.
    </div>

    <!-- =========================== TAB: СНАПШОТЫ =========================== -->
    <div v-if="tab === 'snapshots'">
      <div class="card shadow-sm mb-3">
        <div class="card-body py-2 d-flex flex-wrap gap-2 align-items-end">
          <div>
            <label class="form-label small mb-1">Месяц</label>
            <input v-model="snapQ.period" type="month" class="form-control form-control-sm" style="width:160px">
          </div>
          <div>
            <label class="form-label small mb-1">Поиск</label>
            <input v-model="snapQ.q" class="form-control form-control-sm" style="width:240px" placeholder="артикул / название / nmID">
          </div>
          <button class="btn btn-sm btn-primary" @click="snapQ.page = 1; loadSnapshots()"><i class="bi bi-search me-1"></i>Показать</button>
          <button class="btn btn-sm btn-outline-primary" @click="importAvailable = !importAvailable">
            <i class="bi bi-upload me-1"></i>Наличия из Excel
          </button>
          <button class="btn btn-sm btn-outline-success" @click="snapFormOpen = true"><i class="bi bi-plus-lg me-1"></i>Добавить</button>
        </div>
        <div v-if="importAvailable" class="card-body border-top py-2 d-flex flex-wrap gap-2 align-items-end">
          <div>
            <label class="form-label small mb-1">Период снапшотов</label>
            <input v-model="availPeriod" type="date" class="form-control form-control-sm" style="width:160px">
          </div>
          <div>
            <label class="form-label small mb-1">Файл (.xlsx): nmID/vendorCode + Количество</label>
            <input ref="availFileRef" type="file" class="form-control form-control-sm" accept=".xlsx,.xls">
          </div>
          <button class="btn btn-sm btn-primary" :disabled="availLoading" @click="parseAvailability">
            {{ availLoading ? 'Разбор...' : 'Разобрать' }}
          </button>
        </div>
      </div>

      <div v-if="availItems.length" class="card shadow-sm mb-3 border-primary">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span>Найдено позиций: <strong>{{ availItems.length }}</strong> · пропущено {{ availSkipped.length }}</span>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-success" :disabled="!availItems.length || availSaving" @click="saveAvailability">
              {{ availSaving ? 'Сохранение...' : 'Сохранить все наличия' }}
            </button>
            <button class="btn btn-sm btn-light" @click="availItems = []; availSkipped = []">Отмена</button>
          </div>
        </div>
        <div class="card-body p-0">
          <div class="table-responsive" style="max-height:300px">
            <table class="table table-sm table-bordered table-striped mb-0">
              <thead><tr><th style="width:90px">Стр</th><th style="width:110px">nmID</th><th>Артикул</th><th>Товар</th><th style="width:120px">Наличие</th></tr></thead>
              <tbody>
                <tr v-for="(it, i) in availItems" :key="i">
                  <td>{{ it.row }}</td>
                  <td>{{ it.nm_id }}</td>
                  <td class="fw-bold">{{ it.vendor_code }}</td>
                  <td class="small text-truncate" style="max-width:300px" :title="it.title">{{ it.title }}</td>
                  <td><input v-model.number="it.qty" type="number" class="form-control form-control-sm"></td>
                </tr>
                <tr v-if="!availItems.length"><td colspan="5" class="text-center text-muted py-2">Ничего не найдено</td></tr>
              </tbody>
            </table>
          </div>
          <div v-if="availSkipped.length" class="card-body py-1 small text-danger">
            {{ availSkipped.slice(0, 5).join('; ') }}<template v-if="availSkipped.length > 5"> … ещё {{ availSkipped.length - 5 }}</template>
          </div>
        </div>
      </div>

      <div class="card shadow-sm">
        <div class="card-body p-0">
          <div v-if="snapLoading" class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
          <div v-else-if="!snapRows.length" class="p-4 text-center text-muted">Снапшотов за период нет</div>
          <div v-else class="table-responsive">
            <table class="table table-bordered table-striped table-hover align-middle mb-0">
              <thead>
                <tr>
                  <th style="width:110px">nmID</th><th>Артикул</th><th>Товар</th>
                  <th style="width:130px">Период</th>
                  <th class="text-end" style="width:110px">qty_start</th>
                  <th class="text-end" style="width:150px">Баланс сегодня</th>
                  <th style="width:130px"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in snapRows" :key="s.id">
                  <td>{{ s.nm_id }}</td>
                  <td class="fw-bold">{{ s.vendorCode || '—' }}</td>
                  <td class="small text-truncate" style="max-width:280px" :title="s.title">{{ s.title || '—' }}</td>
                  <td>{{ fmtDateS(s.period_date) }}</td>
                  <td class="text-end fw-bold">{{ s.qty_start }}</td>
                  <td class="text-end">{{ s.balance_today }}</td>
                  <td class="text-end text-nowrap">
                    <button class="btn btn-sm btn-outline-secondary me-1" title="Правка" @click="openSnapEdit(s)"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-warning me-1" title="Сверить (ввести факт)" @click="reconcileRow(s)"><i class="bi bi-arrow-left-right"></i></button>
                    <button class="btn btn-sm btn-outline-danger" title="Удалить" @click="deleteSnap(s)"><i class="bi bi-trash"></i></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-if="snapTotal > snapQ.page_size" class="card-footer d-flex justify-content-between align-items-center">
          <span class="small text-muted">Страница {{ snapQ.page }} · всего {{ snapTotal }}</span>
          <div class="btn-group">
            <button class="btn btn-sm btn-outline-secondary" :disabled="snapQ.page <= 1" @click="snapQ.page--; loadSnapshots()">←</button>
            <button class="btn btn-sm btn-outline-secondary" :disabled="snapQ.page * snapQ.page_size >= snapTotal" @click="snapQ.page++; loadSnapshots()">→</button>
          </div>
        </div>
      </div>
    </div>

    <!-- =========================== TAB: ДВИЖЕНИЯ =========================== -->
    <div v-if="tab === 'movements'">
      <div class="card shadow-sm mb-3">
        <div class="card-body py-2 d-flex flex-wrap gap-2 align-items-end">
          <div>
            <label class="form-label small mb-1">Тип</label>
            <select v-model="movQ.type" class="form-select form-select-sm" style="width:200px">
              <option value="">все</option>
              <option value="production_in">Приход от производства</option>
              <option value="adjustment">Корректировка (сверка)</option>
              <option value="loss">Списание / брак</option>
            </select>
          </div>
          <div>
            <label class="form-label small mb-1">Дата с</label>
            <input v-model="movQ.date_from" type="date" class="form-control form-control-sm" style="width:150px">
          </div>
          <div>
            <label class="form-label small mb-1">Дата по</label>
            <input v-model="movQ.date_to" type="date" class="form-control form-control-sm" style="width:150px">
          </div>
          <div>
            <label class="form-label small mb-1">Поиск</label>
            <input v-model="movQ.q" class="form-control form-control-sm" style="width:220px" placeholder="артикул / название / nmID">
          </div>
          <button class="btn btn-sm btn-primary" @click="movQ.page = 1; loadMovements()"><i class="bi bi-search me-1"></i>Показать</button>
          <button class="btn btn-sm btn-outline-success" @click="movFormOpen = true"><i class="bi bi-plus-lg me-1"></i>Добавить</button>
        </div>
      </div>

      <div class="card shadow-sm">
        <div class="card-body p-0">
          <div v-if="movLoading" class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
          <div v-else-if="!movRows.length" class="p-4 text-center text-muted">Движений нет</div>
          <div v-else class="table-responsive">
            <table class="table table-bordered table-striped table-hover align-middle mb-0">
              <thead>
                <tr>
                  <th style="width:110px">Дата</th><th style="width:110px">Тип</th>
                  <th style="width:110px">nmID</th><th>Артикул</th><th>Товар</th>
                  <th class="text-end" style="width:90px">Qty</th>
                  <th>Комментарий</th><th style="width:90px">Источник</th>
                  <th style="width:110px"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in movRows" :key="m.id">
                  <td>{{ fmtDateS(m.movement_date) }}</td>
                  <td><span class="badge" :class="typeBadge(m.type)">{{ typeShort(m.type) }}</span></td>
                  <td>{{ m.nm_id }}</td>
                  <td class="fw-bold">{{ m.vendorCode || '—' }}</td>
                  <td class="small text-truncate" style="max-width:240px" :title="m.title">{{ m.title || '—' }}</td>
                  <td class="text-end fw-bold">{{ m.qty }}</td>
                  <td class="small">{{ m.comment || '—' }}</td>
                  <td class="small text-muted">{{ m.source === 'excel_import' ? 'Excel' : 'ручное' }}</td>
                  <td class="text-end text-nowrap">
                    <button class="btn btn-sm btn-outline-secondary me-1" @click="openMovEdit(m)"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger" @click="deleteMov(m)"><i class="bi bi-trash"></i></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-if="movTotal > movQ.page_size" class="card-footer d-flex justify-content-between align-items-center">
          <span class="small text-muted">Страница {{ movQ.page }} · всего {{ movTotal }}</span>
          <div class="btn-group">
            <button class="btn btn-sm btn-outline-secondary" :disabled="movQ.page <= 1" @click="movQ.page--; loadMovements()">←</button>
            <button class="btn btn-sm btn-outline-secondary" :disabled="movQ.page * movQ.page_size >= movTotal" @click="movQ.page++; loadMovements()">→</button>
          </div>
        </div>
      </div>
    </div>

    <!-- =========================== TAB: ИМПОРТ ДВИЖЕНИЙ ===================== -->
    <div v-if="tab === 'import'">
      <div class="card shadow-sm mb-3">
        <div class="card-body py-2 d-flex flex-wrap gap-3 align-items-end">
          <div>
            <label class="form-label small mb-1">Режим</label>
            <select v-model="impMode" class="form-select form-select-sm" style="width:260px">
              <option value="production_in">Приход от производства (qty из файла)</option>
              <option value="adjustment">Сверка остатков (факт − расчётный)</option>
            </select>
          </div>
          <div>
            <label class="form-label small mb-1">Дата движения</label>
            <input v-model="impDate" type="date" class="form-control form-control-sm" style="width:160px">
          </div>
          <div>
            <label class="form-label small mb-1">Файл (.xlsx): nmID/vendorCode + Количество</label>
            <input ref="impFileRef" type="file" class="form-control form-control-sm" accept=".xlsx,.xls" style="width:280px">
          </div>
          <button class="btn btn-sm btn-primary" :disabled="impLoading" @click="onImport">
            {{ impLoading ? 'Импорт...' : 'Загрузить и импортировать' }}
          </button>
        </div>
      </div>
      <div v-if="impResult" class="card shadow-sm">
        <div class="card-body">
          <div>Обработано строк: <strong>{{ impResult.processed }}</strong>, создано движений: <strong>{{ impResult.created }}</strong>, пропущено: <strong>{{ impResult.skipped.length }}</strong></div>
          <div v-if="impResult.skipped.length" class="mt-2 small text-danger">
            <div v-for="(s, i) in impResult.skipped" :key="i">{{ s }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ======================== МОДАЛКА: снапшот ============================ -->
    <div class="modal fade" :class="{ show: snapFormOpen }" tabindex="-1" @click.self="snapFormOpen = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">{{ snapForm.id ? 'Снапшот: правка' : 'Новый снапшот' }}</h6>
            <button type="button" class="btn-close" @click="snapFormOpen = false"></button>
          </div>
          <div class="modal-body">
            <div class="row g-2">
              <div class="col-4">
                <label class="form-label small mb-1">nmID *</label>
                <input v-model="snapForm.nm_id" type="number" class="form-control form-control-sm">
              </div>
              <div class="col-5">
                <label class="form-label small mb-1">Период *</label>
                <input v-model="snapForm.period_date" type="date" class="form-control form-control-sm">
              </div>
              <div class="col-3">
                <label class="form-label small mb-1">qty_start *</label>
                <input v-model.number="snapForm.qty_start" type="number" class="form-control form-control-sm">
              </div>
            </div>
            <div class="mt-2">
              <button class="btn btn-sm btn-outline-secondary" :disabled="!snapForm.nm_id" @click="suggestBalance">
                <i class="bi bi-magic me-1"></i>Подставить расчётный баланс
              </button>
              <span v-if="snapForm.suggested !== null" class="ms-2 small text-success">расчётный: {{ snapForm.suggested }}</span>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm btn-light" @click="snapFormOpen = false">Отмена</button>
            <button class="btn btn-sm btn-primary" @click="saveSnap">Сохранить</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="snapFormOpen" class="modal-backdrop fade show"></div>

    <!-- ======================== МОДАЛКА: движение ============================ -->
    <div class="modal fade" :class="{ show: movFormOpen }" tabindex="-1" @click.self="movFormOpen = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">{{ movForm.id ? 'Движение: правка' : 'Новое движение' }}</h6>
            <button type="button" class="btn-close" @click="movFormOpen = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-2 position-relative">
              <label class="form-label small mb-1">Товар (артикул / название / nmID)</label>
              <input v-model="cardSearchQ" class="form-control form-control-sm" @input="searchCards" placeholder="начните вводить...">
              <ul v-if="cardOptions.length" class="list-group position-absolute shadow-sm" style="z-index:1000; max-height:220px; overflow:auto">
                <li v-for="c in cardOptions" :key="c.nmID" class="list-group-item list-group-item-action small"
                    style="cursor:pointer" @click="pickCard(c)">
                  {{ c.vendorCode }} / {{ c.nmID }} — {{ c.title }}
                </li>
              </ul>
              <div v-if="movForm.nm_id" class="small text-muted mt-1">выбран nmID {{ movForm.nm_id }}</div>
            </div>
            <div class="row g-2">
              <div class="col-6">
                <label class="form-label small mb-1">Тип *</label>
                <select v-model="movForm.type" class="form-select form-select-sm">
                  <option value="production_in">Приход от производства</option>
                  <option value="adjustment">Корректировка (сверка)</option>
                  <option value="loss">Списание / брак</option>
                </select>
              </div>
              <div class="col-3">
                <label class="form-label small mb-1">Qty *</label>
                <input v-model.number="movForm.qty" type="number" class="form-control form-control-sm">
              </div>
              <div class="col-3">
                <label class="form-label small mb-1">Дата *</label>
                <input v-model="movForm.movement_date" type="date" class="form-control form-control-sm">
              </div>
            </div>
            <div class="mt-2">
              <label class="form-label small mb-1">Комментарий</label>
              <input v-model="movForm.comment" class="form-control form-control-sm" maxlength="255">
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm btn-light" @click="movFormOpen = false">Отмена</button>
            <button class="btn btn-sm btn-primary" @click="saveMov">Сохранить</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="movFormOpen" class="modal-backdrop fade show"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/api/client'

const tab = ref<'snapshots' | 'movements' | 'import'>('snapshots')

const TYPE_LABELS: Record<string, string> = {
  production_in: 'Приход',
  adjustment: 'Сверка',
  loss: 'Списание',
}
const typeShort = (t: string) => TYPE_LABELS[t] || t
const typeBadge = (t: string) => ({ production_in: 'bg-success', adjustment: 'bg-warning text-dark', loss: 'bg-danger' }[t] || 'bg-secondary')
const fmtDateS = (v: any) => (v ? String(v).slice(0, 10) : '—')

// --- снапшоты -----------------------------------------------------------
const snapQ = reactive({ period: new Date().toISOString().slice(0, 7), q: '', page: 1, page_size: 20 })
const snapRows = ref<any[]>([])
const snapTotal = ref(0)
const snapLoading = ref(false)

const loadSnapshots = async () => {
  snapLoading.value = true
  try {
    const row = await api.get('/api/production/smolensk/snapshots', {
      params: { period: snapQ.period, q: snapQ.q || undefined, page: snapQ.page, page_size: snapQ.page_size },
    }).then(r => r.data)
    const list = row.rows || []
    // баланс на сегодня подставляем батчем построчно (страница ≤ 200 строк)
    for (const r of list) {
      r.balance_today = '…'
    }
    snapRows.value = list
    snapTotal.value = row.total || 0
    await Promise.all(list.map(async (r: any) => {
      try {
        const b = await api.get('/api/production/smolensk/balance', { params: { nm_id: r.nm_id } }).then(x => x.data)
        r.balance_today = b.balance
      } catch { r.balance_today = '—' }
    }))
  } finally { snapLoading.value = false }
}

// форма снапшота
const snapFormOpen = ref(false)
const snapForm = reactive<any>({ id: null, nm_id: '', period_date: '', qty_start: 0, suggested: null })
const openSnapEdit = (s: any) => {
  Object.assign(snapForm, { id: s.id, nm_id: s.nm_id, period_date: fmtDateS(s.period_date), qty_start: s.qty_start, suggested: null })
  snapFormOpen.value = true
}
const saveSnap = async () => {
  try {
    const payload = { nm_id: snapForm.nm_id, period_date: snapForm.period_date, qty_start: snapForm.qty_start }
    if (snapForm.id) await api.put(`/api/production/smolensk/snapshots/${snapForm.id}`, payload)
    else await api.post('/api/production/smolensk/snapshots', payload)
    snapFormOpen.value = false
    loadSnapshots()
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось сохранить')
  }
}
const deleteSnap = async (s: any) => {
  if (!confirm(`Удалить снапшот ${s.nm_id} на ${fmtDateS(s.period_date)}?`)) return
  try {
    await api.delete(`/api/production/smolensk/snapshots/${s.id}`)
    loadSnapshots()
  } catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось удалить') }
}
const suggestBalance = async () => {
  try {
    const b = await api.get('/api/production/smolensk/balance', {
      params: { nm_id: snapForm.nm_id, on_date: snapForm.period_date },
    }).then(x => x.data)
    snapForm.suggested = b.balance
    snapForm.qty_start = b.balance
  } catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка расчёта') }
}
const reconcileRow = async (s: any) => {
  const val = prompt(`Ввести факт инвентаризации для ${s.nm_id} на ${fmtDateS(s.period_date)}\n(ожидается qty_start = ${s.qty_start})`)
  if (val === null) return
  try {
    const res = await api.post('/api/production/smolensk/reconcile', {
      nm_id: s.nm_id, period_date: fmtDateS(s.period_date), actual_qty: Number(val),
    }).then(r => r.data)
    alert(res.message)
    loadSnapshots()
  } catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка сверки') }
}

// наличия из Excel -> снапшоты
const importAvailable = ref(false)
const availFileRef = ref<HTMLInputElement | null>(null)
const availPeriod = ref(new Date().toISOString().slice(0, 10))
const availLoading = ref(false)
const availSaving = ref(false)
const availItems = ref<any[]>([])
const availSkipped = ref<string[]>([])

const readGrid = async (el: HTMLInputElement | null): Promise<any[][] | null> => {
  const file = el?.files?.[0]
  if (!file) { alert('Выберите файл'); return null }
  const XLSX = await import('xlsx')
  const buf = await file.arrayBuffer()
  const wb = XLSX.read(buf, { type: 'array' })
  const ws = wb.Sheets[wb.SheetNames[0]]
  return XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
}

const parseAvailability = async () => {
  const grid = await readGrid(availFileRef.value)
  if (!grid) return
  availLoading.value = true
  try {
    const res = await api.post('/api/production/smolensk/snapshots/parse-availability', { grid }).then(r => r.data)
    availItems.value = (res.matched || []).map((m: any, i: number) => ({ ...m, row: i + 2, qty: m.qty }))
    availSkipped.value = res.skipped || []
    if (!availItems.value.length) alert('Совпадений нет — смотрите пропущенные строки')
  } catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка разбора') }
  finally { availLoading.value = false }
}
const saveAvailability = async () => {
  if (!confirm(`Сохранить ${availItems.value.length} наличий как снапшоты на ${availPeriod.value}?`)) return
  availSaving.value = true
  try {
    const res = await api.post('/api/production/smolensk/snapshots/save-availability', {
      rows: (availItems.value || []).map(it => ({ nm_id: it.nm_id, period_date: availPeriod.value, qty_start: it.qty })),
    }).then(r => r.data)
    alert(`Сохранено: ${res.saved}, пропущено: ${(res.skipped || []).length}`)
    availItems.value = []; availSkipped.value = []
    loadSnapshots()
  } catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка сохранения') }
  finally { availSaving.value = false }
}

// --- движения -------------------------------------------------------------
const today = new Date().toISOString().slice(0, 10)
const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10)
const movQ = reactive({ type: '', date_from: monthAgo, date_to: today, q: '', page: 1, page_size: 20 })
const movRows = ref<any[]>([])
const movTotal = ref(0)
const movLoading = ref(false)

const loadMovements = async () => {
  movLoading.value = true
  try {
    const res = await api.get('/api/production/smolensk/movements', {
      params: {
        type: movQ.type || undefined, date_from: movQ.date_from || undefined,
        date_to: movQ.date_to || undefined, q: movQ.q || undefined,
        page: movQ.page, page_size: movQ.page_size,
      },
    }).then(r => r.data)
    movRows.value = res.rows || []
    movTotal.value = res.total || 0
  } finally { movLoading.value = false }
}

// форма движения с поиском карточки
const movFormOpen = ref(false)
const movForm = reactive<any>({ id: null, nm_id: null, type: 'production_in', qty: 0, movement_date: today, comment: '' })
const cardSearchQ = ref('')
const cardOptions = ref<any[]>([])
let cardTimer: ReturnType<typeof setTimeout> | null = null

const openMovEdit = (m: any) => {
  Object.assign(movForm, { id: m.id, nm_id: m.nm_id, type: m.type, qty: m.qty, movement_date: fmtDateS(m.movement_date), comment: m.comment || '' })
  cardSearchQ.value = m.vendorCode ? `${m.vendorCode} / ${m.nm_id}` : `${m.nm_id}`
  cardOptions.value = []
  movFormOpen.value = true
}
const searchCards = () => {
  if (cardTimer) clearTimeout(cardTimer)
  cardTimer = setTimeout(async () => {
    if (!cardSearchQ.value.trim() || cardSearchQ.value.includes('/')) { cardOptions.value = []; return }
    try {
      const res = await api.get('/api/wb/cards', { params: { q: cardSearchQ.value, limit: 10 } }).then(r => r.data)
      cardOptions.value = (res || []).slice(0, 10)
    } catch { cardOptions.value = [] }
  }, 300)
}
const pickCard = (c: any) => {
  movForm.nm_id = c.nmID
  cardSearchQ.value = `${c.vendorCode} / ${c.nmID}`
  cardOptions.value = []
}
const saveMov = async () => {
  try {
    const payload = {
      nm_id: movForm.nm_id, type: movForm.type, qty: movForm.qty,
      movement_date: movForm.movement_date, comment: movForm.comment, source: 'manual',
    }
    if (movForm.id) await api.put(`/api/production/smolensk/movements/${movForm.id}`, payload)
    else await api.post('/api/production/smolensk/movements', payload)
    movFormOpen.value = false
    loadMovements()
  } catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось сохранить') }
}
const deleteMov = async (m: any) => {
  if (!confirm(`Удалить движение #${m.id} (${m.nm_id}, ${fmtDateS(m.movement_date)})?`)) return
  try { await api.delete(`/api/production/smolensk/movements/${m.id}`); loadMovements() }
  catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось удалить') }
}

// --- импорт движений ------------------------------------------------------
const impMode = ref<'production_in' | 'adjustment'>('production_in')
const impDate = ref(today)
const impFileRef = ref<HTMLInputElement | null>(null)
const impLoading = ref(false)
const impResult = ref<any>(null)

const onImport = async () => {
  const grid = await readGrid(impFileRef.value)
  if (!grid) return
  impLoading.value = true
  impResult.value = null
  try {
    impResult.value = await api.post('/api/production/smolensk/movements/import', {
      grid, type: impMode.value, movement_date: impDate.value,
    }).then(r => r.data)
  } catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка импорта') }
  finally { impLoading.value = false }
}

watch(tab, (v) => {
  if (v === 'snapshots') loadSnapshots()
  if (v === 'movements') loadMovements()
})

onMounted(loadSnapshots)
</script>
