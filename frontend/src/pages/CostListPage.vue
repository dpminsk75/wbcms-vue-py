<template>
  <div class="container-xxl page-cost-list">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="page-title mb-0">Себестоимость: просмотр и редактирование</h1>
      <div class="d-flex gap-2 align-items-center">
        <router-link to="/cost-import/missing" class="btn btn-outline-warning btn-sm"><i class="bi bi-exclamation-triangle me-1"></i>Нет себестоимости</router-link>
        <div class="page-cost-list__actions" ref="actionsRef">
        <button class="btn btn-light page-cost-list__actions-btn" type="button" @click="actionsOpen = !actionsOpen">
          Действия с Excel <i class="bi ms-1" :class="actionsOpen ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
        </button>
        <div v-if="actionsOpen" class="page-cost-list__actions-list">
          <button class="page-cost-list__actions-item" @click="actionsOpen = false; downloadTemplate()"><i class="bi bi-file-earmark-spreadsheet me-2"></i>Скачать шаблон</button>
          <button class="page-cost-list__actions-item" :disabled="!rows.length" @click="actionsOpen = false; exportExcel()"><i class="bi bi-download me-2"></i>Скачать файл с товарами</button>
          <router-link to="/cost-import" class="page-cost-list__actions-item" @click="actionsOpen = false"><i class="bi bi-upload me-2"></i>Загрузить файл с товарами</router-link>
        </div>
      </div>
      </div>
    </div>

    <div class="row mb-3 g-3">
      <div class="col-md-8">
        <div class="card card-body page-cost-list__filter h-100">
          <label class="form-label fw-bold">Карточка товара</label>
          <div class="page-cost-list__combo" ref="comboRef">
            <div class="d-flex gap-2">
              <input
                v-model="cardQuery"
                class="form-control"
                placeholder="nmID, артикул, название, баркод..."
                @focus="comboOpen = true; fetchCards(cardQuery)"
                @input="onCardQuery"
                @keydown.esc="comboOpen = false"
                @keydown.enter="pickFirst"
              />
              <button v-if="filters.nm_id" class="btn btn-light" title="Очистить карточку (без запроса)" @click="clearCard">×</button>
            </div>
            <div v-if="comboOpen && cardOptions.length" class="page-cost-list__combo-list">
              <div
                v-for="c in cardOptions" :key="c.nmID"
                class="page-cost-list__combo-item"
                @mousedown.prevent="pickCard(c)"
              >
                <div><b>{{ c.nmID }}</b> · {{ c.vendorCode || '' }}</div>
                <div class="text-muted small">{{ c.title || '' }}</div>
                <div v-if="c.sizes?.length" class="text-muted small">sku: {{ c.sizes.map((s: any) => s.sku).join(', ') }}</div>
              </div>
            </div>
            <div v-if="comboOpen && !cardOptions.length" class="page-cost-list__combo-list">
              <div class="text-muted small p-2">Ничего не найдено</div>
            </div>
          </div>
          <div v-if="filters.nm_id" class="mt-1 small text-muted">Выбрано: {{ filters.nm_id }}{{ filters.sku ? ` · ${filters.sku}` : '' }}</div>
          <div v-if="isDirty" class="small text-warning">Есть неприменённые изменения — нажмите «Применить»</div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card card-body page-cost-list__filter h-100 justify-content-end">
          <div class="d-flex gap-2">
            <button class="btn btn-primary flex-grow-1" :disabled="isLoading || !isDirty" @click="onApply">
              <i class="bi bi-filter me-1"></i>Применить
            </button>
            <button class="btn btn-light" title="Сбросить фильтры" :disabled="isLoading" @click="onReset">
              <i class="bi bi-arrow-counterclockwise"></i>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="d-flex justify-content-end mb-2">
      <button class="btn btn-success btn-sm" @click="openAdd = true"><i class="bi bi-plus-lg me-1"></i>Добавить</button>
    </div>
    <div class="card">
      <div v-if="isLoading" class="text-center p-5">
        <div class="spinner-border text-primary" role="status"></div>
        <div class="mt-2 text-muted">Загрузка данных...</div>
      </div>
      <div v-else class="wb-table-wrap">
        <vxe-table
          :data="rows"
          class="page-cost-list__grid"
          border
          stripe
          size="mini"
          auto-resize
          show-overflow="title"
          header-align="center"
          :edit-config="{ trigger: 'click', mode: 'cell' }"
          :row-config="{ isHover: true, keyField: 'id' }"
          @edit-actived="onEditActived"
          @edit-closed="onEditClosed"
        >
          <vxe-column field="load_date" title="Дата" :width="150" align="center" class-name="page-cost-list__editable" :edit-render="{}">
            <template #edit="{ row }"><input v-model="row.load_date" type="date" class="form-control form-control-sm page-cost-list__date-input" /></template>
          </vxe-column>
          <vxe-column field="nmID" title="Артикул WB" :width="110" align="center" />
          <vxe-column field="vendorCode" title="Артикул" :width="170" align="center" />
          <vxe-column field="product_name" title="Товар" :min-width="260" :show-overflow="false" header-align="center">
            <template #default="{ row }"><div>{{ row.product_name || '—' }}</div></template>
          </vxe-column>
          <vxe-column field="chrtID" title="ID Размера" :width="110" align="center" />
          <vxe-column field="sku" title="Баркод" :width="140" align="center" />
          <vxe-column field="price" title="Себестоимость" :width="130" align="right" class-name="page-cost-list__editable" :edit-render="{}">
            <template #default="{ row }">
              <span class="page-cost-list__price">{{ row.price }}</span>
              <span v-if="states[row.id]" class="small ms-2" :class="states[row.id].cls">{{ states[row.id].text }}</span>
            </template>
            <template #edit="{ row }">
              <input v-model="row.price" class="form-control form-control-sm" @keydown.enter="$event.target.blur()" />
            </template>
          </vxe-column>
          <vxe-column title="" :width="50" align="center">
            <template #default="{ row }">
              <button class="btn btn-sm btn-link text-danger p-0" title="Удалить" @click="onDelete(row)"><i class="bi bi-trash"></i></button>
            </template>
          </vxe-column>
        </vxe-table>
        <div v-if="!rows.length" class="text-center text-muted py-4">Нет данных</div>
      </div>
    </div>

    <div v-if="openAdd" class="wb-modal-backdrop">
      <form class="wb-modal-box" @submit.prevent="onAddSave">
        <h3 class="page-cost-list__modal-title">Добавить себестоимость</h3>
        <label>Дата<input v-model="addForm.date" type="date" required class="form-control" /></label>
        <label>Карточка
          <div class="page-cost-list__combo" ref="addComboRef">
            <input
              v-model="addQuery"
              class="form-control"
              placeholder="nmID, артикул, название..."
              @focus="addComboOpen = true; fetchAddCards(addQuery)"
              @input="onAddQuery"
              @keydown.esc="addComboOpen = false"
              @keydown.enter="pickAddFirst"
            />
            <div v-if="addComboOpen && addCardOptions.length" class="page-cost-list__combo-list">
              <div
                v-for="c in addCardOptions" :key="c.nmID"
                class="page-cost-list__combo-item"
                @mousedown.prevent="pickAddCard(c)"
              >
                <div><b>{{ c.nmID }}</b> · {{ c.vendorCode || '' }}</div>
                <div class="text-muted small">{{ c.title || '' }}</div>
              </div>
            </div>
          </div>
        </label>
        <label>ID Размера
          <select v-if="addSizes.length > 1" v-model="addForm.chrtID" class="form-select" @change="onAddSize">
            <option value="">Выберите размер...</option>
            <option v-for="s in addSizes" :key="s.chrtID" :value="s.chrtID">{{ s.chrtID }} · {{ s.sku }}</option>
          </select>
          <input v-else v-model="addForm.chrtID" class="form-control" placeholder="chrtID" readonly />
        </label>
        <label>Баркод<input v-model="addForm.sku" class="form-control" placeholder="sku" :readonly="addSizes.length > 0" /></label>
        <label>Себестоимость<input v-model="addForm.price" required class="form-control" placeholder="0.00" /></label>
        <div v-if="addError" class="text-danger">{{ addError }}</div>
        <div class="wb-modal-actions">
          <button type="button" class="btn btn-light" @click="openAdd = false">Отмена</button>
          <button type="submit" class="btn btn-success" :disabled="addSaving">{{ addSaving ? 'Сохранение...' : 'Сохранить' }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-cost-list.css'
import 'vxe-table/lib/style.css'
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VxeTable, VxeColumn } from 'vxe-table'
import { api } from '@/api/client'
import { costApi, type CostRow } from '@/api/cost'

const route = useRoute()
const router = useRouter()

const filters = reactive({
  nm_id: String(route.query.nm_id || ''),
  sku: String(route.query.sku || ''),
})
// Применённое состояние: запрос уходит только по «Применить», выбор карточки сам не фетчит
const applied = reactive({ ...filters })
const isDirty = computed(() =>
  filters.nm_id !== applied.nm_id || filters.sku !== applied.sku,
)
const cardQuery = ref('')
const cardOptions = ref<any[]>([])
const comboOpen = ref(false)
const comboRef = ref<HTMLDivElement | null>(null)
const actionsRef = ref<HTMLDivElement | null>(null)
const actionsOpen = ref(false)

const rows = ref<CostRow[]>([])
const states = ref<Record<number, { text: string; cls: string }>>({})
const originals = ref<Record<number, { price: unknown; load_date: unknown }>>({})
const isLoading = ref(false)

const openAdd = ref(false)
const addSaving = ref(false)
const addError = ref('')
const addSizes = ref<Array<{ chrtID: string; sku: string }>>([])
const addQuery = ref('')
const addCardOptions = ref<any[]>([])
const addComboOpen = ref(false)
const addComboRef = ref<HTMLDivElement | null>(null)
const addForm = reactive({
  date: new Date().toISOString().slice(0, 10),
  nmID: '',
  chrtID: '',
  sku: '',
  price: '',
})

function parseSizes(raw: any): Array<{ chrtID: string; sku: string }> {
  let v: any = raw
  for (let i = 0; i < 2 && typeof v === 'string'; i++) {
    try { v = JSON.parse(v) } catch { return [] }
  }
  if (!Array.isArray(v)) return []
  return v.map((s: any) => ({ chrtID: String(s.chrtID ?? ''), sku: String(s.skus?.[0] ?? '') })).filter((s) => s.chrtID)
}

async function fetchCards(q = '') {
  try {
    const { data } = await api.get('/api/cost-import/cards', { params: { q: q || undefined, limit: 50 } })
    const list = Array.isArray(data) ? data : []
    cardOptions.value = list
    if (!q && !filters.nm_id) {
      // полный список для выбора без ввода — уже лимит 50 свежих
    }
  } catch {
    cardOptions.value = []
  }
}

let queryTimer: any = null
function onCardQuery() {
  clearTimeout(queryTimer)
  queryTimer = setTimeout(() => {
    fetchCards(cardQuery.value.trim())
    comboOpen.value = true
  }, 300)
}

function pickCard(c: any) {
  filters.nm_id = String(c.nmID)
  const skus = (c.sizes || []).map((s: any) => s.sku).filter(Boolean).join(', ')
  cardQuery.value = `${c.nmID} | ${c.title || c.vendorCode || ''}${skus ? ` | ${skus}` : ''}`
  filters.sku = skus && skus.indexOf(',') < 0 ? skus : ''
  comboOpen.value = false
  // без автозапроса: пользователь жмёт «Применить»
}

function clearCard() {
  filters.nm_id = ''
  filters.sku = ''
  cardQuery.value = ''
}

function pickFirst() {
  if (cardOptions.value.length) pickCard(cardOptions.value[0])
}

function onDocClick(e: MouseEvent) {
  const t = e.target as Node
  if (comboOpen.value && comboRef.value && !comboRef.value.contains(t)) {
    comboOpen.value = false
  }
  if (actionsOpen.value && actionsRef.value && !actionsRef.value.contains(t)) {
    actionsOpen.value = false
  }
  const addCombo = addComboRef.value
  if (addComboOpen.value && addCombo && !addCombo.contains(t)) {
    addComboOpen.value = false
  }
}

async function resolveCardLabel(nmId: string) {
  try {
    const { data } = await api.get('/api/cost-import/cards', { params: { q: nmId, limit: 10 } })
    const list = Array.isArray(data) ? data : []
    const found = list.find((c: any) => String(c.nmID) === String(nmId))
    if (found) {
      const skus = (found.sizes || []).map((s: any) => s.sku).filter(Boolean).join(', ')
      cardQuery.value = `${found.nmID} | ${found.title || found.vendorCode || ''}${skus ? ` | ${skus}` : ''}`
      if (!filters.sku && skus && skus.indexOf(',') < 0) filters.sku = skus
    } else {
      cardQuery.value = nmId
    }
  } catch {
    cardQuery.value = nmId
  }
}

async function fetchData() {
  isLoading.value = true
  try {
    rows.value = await costApi.list('', '', filters.nm_id, filters.sku)
    document.title = 'Себестоимость: просмотр и редактирование'
  } catch {
    rows.value = []
  } finally {
    isLoading.value = false
  }
}

function onApply() {
  applied.nm_id = filters.nm_id
  applied.sku = filters.sku
  router.replace({
    path: '/cost-import/list',
    query: {
      nm_id: filters.nm_id || undefined,
      sku: filters.sku || undefined,
    },
  })
  fetchData()
}

function onReset() {
  filters.nm_id = ''
  filters.sku = ''
  cardQuery.value = ''
  comboOpen.value = false
  fetchCards()
  // если ничего не было применено — таблица уже полная, запрос не нужен
  if (!applied.nm_id && !applied.sku) return
  onApply()
}

function setState(id: number, text: string, cls: string, clear = true) {
  states.value[id] = { text, cls }
  if (text && clear) {
    setTimeout(() => {
      if (states.value[id]?.text === text) delete states.value[id]
    }, 2000)
  }
}

function onEditActived({ row }: any) {
  originals.value[row.id] = { price: row.price, load_date: row.load_date }
}

async function onEditClosed({ row }: any) {
  const orig = originals.value[row.id] || {}
  const newPrice = String(row.price ?? '').trim()
  const newDate = String(row.load_date ?? '').trim()
  const payload: Record<string, string> = {}
  if (newPrice !== String(orig.price ?? '').trim()) payload.price = newPrice
  if (newDate !== String(orig.load_date ?? '').trim()) payload.load_date = newDate
  if (!Object.keys(payload).length) return
  const res = await costApi.updateRow(row.id, payload).catch((e) => ({
    success: false,
    message: e?.response?.data?.message || 'Ошибка запроса',
  }))
  if (res.success) {
    if (res.price !== undefined) row.price = res.price
    if (res.load_date) row.load_date = res.load_date
    setState(row.id, '✓ сохранено', 'text-success')
  } else {
    await fetchData()
    setState(row.id, res.message || 'Ошибка', 'text-danger', false)
  }
}

async function onAddCard() {
  addSizes.value = []
  const nm = addForm.nmID.trim()
  if (!/^\d+$/.test(nm)) return
  try {
    const { data } = await api.get(`/api/wb/card/${nm}`)
    addSizes.value = parseSizes(data.sizes)
    applyAddSize()
  } catch { /* ручной ввод */ }
}

function applyAddSize() {
  if (addSizes.value.length === 1) {
    addForm.chrtID = addSizes.value[0].chrtID
    addForm.sku = addSizes.value[0].sku
  }
}

function onAddSize() {
  const found = addSizes.value.find((s) => s.chrtID === addForm.chrtID)
  addForm.sku = found ? found.sku : ''
}

async function fetchAddCards(q = '') {
  try {
    const { data } = await api.get('/api/wb/cards', { params: { q: q || undefined, limit: 50 } })
    addCardOptions.value = Array.isArray(data) ? data : (data.items ?? [])
  } catch {
    addCardOptions.value = []
  }
}

let addQueryTimer: any = null
function onAddQuery() {
  clearTimeout(addQueryTimer)
  addQueryTimer = setTimeout(() => {
    fetchAddCards(addQuery.value.trim())
    addComboOpen.value = true
  }, 300)
}

function pickAddCard(c: any) {
  addForm.nmID = String(c.nmID)
  addQuery.value = `${c.nmID} · ${c.vendorCode || c.title || ''}`
  addComboOpen.value = false
  onAddCard()
}

function pickAddFirst() {
  if (addCardOptions.value.length) pickAddCard(addCardOptions.value[0])
}

async function onAddSave() {
  addSaving.value = true
  addError.value = ''
  try {
    const res = await costApi.save(addForm.date, [{
      nmID: addForm.nmID.trim(),
      price: Number(String(addForm.price).replace(',', '.')),
      chrtID: addForm.chrtID.trim() || undefined,
      sku: addForm.sku.trim() || undefined,
    }])
    if (!res.success) throw new Error(res.message)
    openAdd.value = false
    addForm.chrtID = ''
    addForm.sku = ''
    addForm.price = ''
    await fetchData()
  } catch (e: any) {
    addError.value = e?.response?.data?.message || e?.message || String(e)
  } finally {
    addSaving.value = false
  }
}

async function exportExcel() {
  if (!rows.value.length) return
  const XLSX = await import('xlsx')
  const data = rows.value.map((r) => ({
    'Дата': r.load_date, 'Артикул WB': r.nmID, 'Артикул': r.vendorCode, 'Товар': r.product_name,
    'ID Размера': r.chrtID, 'Баркод': r.sku, 'Себестоимость': r.price,
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{ wch: 12 }, { wch: 12 }, { wch: 16 }, { wch: 32 }, { wch: 12 }, { wch: 18 }, { wch: 14 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Себестоимость')
  XLSX.writeFile(wb, 'costs.xlsx')
}

async function downloadTemplate() {
  const XLSX = await import('xlsx')
  const ws = XLSX.utils.json_to_sheet([
    { 'Артикул продавца': '', Баркод: '', Цена: '' },
  ])
  ws['!cols'] = [{ wch: 20 }, { wch: 18 }, { wch: 12 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Шаблон')
  XLSX.writeFile(wb, 'cost-template.xlsx')
}

async function onDelete(row: CostRow) {
  if (!confirm(`Удалить себестоимость ${row.nmID} / ${row.chrtID || '—'} за ${row.load_date}?`)) return
  try {
    await costApi.remove(row.id)
    rows.value = rows.value.filter((r) => r.id !== row.id)
  } catch (e: any) {
    alert(e?.response?.data?.detail || String(e))
  }
}

onMounted(async () => {
  document.addEventListener('mousedown', onDocClick)
  if (filters.nm_id) {
    addForm.nmID = filters.nm_id
    await resolveCardLabel(filters.nm_id)
  }
  await fetchCards()
  await fetchData()
})

onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))
</script>
