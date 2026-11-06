<template>
  <div class="container-xxl page-fbs-virtual">
    <!-- Шапка блока «Документы»: заголовок + правое меню (пилюли темы) -->
    <WbWorkspaceHead
      title="FBS Остатки: центр + виртуальные"
      :workspace-tabs="STOCK_DOCS_TABS"
      workspace-active="virtual"
    />

    <!-- Пояснение — тонированная панель темы -->
    <div class="wb-panel page-fbs-virtual__note">
      <div class="wb-panel__bd">
        Источник: <b>Центральный</b> (склад is_central) — колонка «Остаток» |
        <b>Оперативный (FBS)</b> (склад is_fbs) — колонка «Количество»
        (редактируется, через Перемещение).
      </div>
    </div>

    <!-- Фильтр — панель темы -->
    <div class="wb-filter-panel">
      <div class="row g-2">
        <div class="col-auto">
          <label class="wb-field__label">Поиск</label>
          <input v-model="q" class="wb-input" placeholder="sku / артикул / название / nmID" @keyup.enter="reload()">
        </div>
        <div class="col-auto">
          <label class="wb-field__label">Количество</label>
          <select v-model="qty" class="wb-select" @change="reload()">
            <option value="all">Все</option>
            <option value="not_found">Не найдено</option>
            <option value="zero">Ноль</option>
            <option value="1_9">1-9</option>
          </select>
        </div>
        <div class="col-auto">
          <label class="wb-field__label">Склад выгрузки</label>
          <select v-model="whFilter" class="wb-select">
            <option value="all">Все склады</option>
            <option v-for="w in vWarehouses" :key="w.id" :value="String(w.warehouseId)">
              {{ w.name }}
            </option>
          </select>
        </div>
        <div class="col-auto">
          <label class="wb-field__label">Режим выгрузки</label>
          <div class="form-check">
            <input id="test-mode" v-model="testMode" type="checkbox" class="form-check-input">
            <label class="form-check-label wb-check-label" for="test-mode">Тест (без выгрузки в WB)</label>
          </div>
        </div>
      </div>

      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" @click="reload()">
          <i class="bi bi-search me-1"></i>Фильтр
        </button>
        <button class="btn btn--outline" @click="fileCentral?.click()">
          <i class="bi bi-file-earmark-excel me-1"></i>Центр. склад
        </button>
        <button class="btn btn--outline" @click="fileVirtual?.click()">
          <i class="bi bi-file-earmark-excel me-1"></i>Вирт. остатки
        </button>
        <input ref="fileCentral" type="file" class="d-none" accept=".xlsx,.xls" @change="onFile($event, 'central')">
        <input ref="fileVirtual" type="file" class="d-none" accept=".xlsx,.xls" @change="onFile($event, 'virtual')">
        <button class="btn btn--soft" :disabled="uploading" @click="uploadAll">
          <i class="bi bi-cloud-upload me-1"></i>{{ uploading ? 'Выгрузка...' : 'Выгрузить' }}
        </button>
        <button class="btn btn--outline" @click="showWarehouses = true">
          <i class="bi bi-boxes me-1"></i>Вирт. склады
        </button>
        <button class="btn btn--outline" @click="showLog = true">
          <i class="bi bi-journal-text me-1"></i>Лог списаний
        </button>
        <span class="page-fbs-virtual__count">Записей: {{ total }}</span>
      </div>
    </div>

    <div v-if="msg" class="wb-panel page-fbs-virtual__msg" :class="msg.ok ? 'page-fbs-virtual__msg--ok' : 'page-fbs-virtual__msg--bad'">
      <div class="wb-panel__bd">
        <pre class="mb-0 page-fbs-virtual__pre">{{ msg.text }}</pre>
      </div>
    </div>

    <!-- Остатки — таблица темы .tbl-card -->
    <div class="tbl-card">
      <div class="card__hd">
        <span>Остатки: центральный и виртуальные</span>
        <span class="hd-badge">{{ total }}</span>
      </div>

      <div v-if="loading" class="page-fbs-virtual__loading">
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span>Загрузка данных…</span>
      </div>
      <div v-else class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="t-left">Товар</th>
              <th class="t-left page-fbs-virtual__col-sku">Баркод</th>
              <th class="t-center page-fbs-virtual__col-qty">Остаток</th>
              <th class="t-center page-fbs-virtual__col-qty">Количество</th>
              <th class="t-center page-fbs-virtual__col-act">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.sku">
              <td class="t-left">
                <div class="page-fbs-virtual__vendor">{{ r.vendorCode }}</div>
                <div class="page-fbs-virtual__sub">{{ r.nmID }} — {{ r.title }}</div>
              </td>
              <td class="t-left">
                <span class="num">{{ r.sku }}</span>
                <button class="btn btn--ghost btn-sm p-0 ms-1" title="Скопировать"
                        @click="copy(r.sku)"><i class="bi bi-clipboard"></i></button>
              </td>
              <td class="t-center num page-fbs-virtual__cell-central">
                {{ r.central_qty === null ? '—' : r.central_qty }}
              </td>
              <td class="t-center page-fbs-virtual__cell-vint">
                <input v-model.number="edits[r.sku]" class="wb-input wb-input--num" type="number"
                       :placeholder="r.virtual_qty === null ? '' : String(r.virtual_qty)">
              </td>
              <td class="t-center text-nowrap">
                <button class="btn btn--outline btn-sm me-1" title="Выгрузить в WB"
                        @click="uploadOne(r)"><i class="bi bi-cloud-upload"></i></button>
                <button class="btn btn--danger btn-sm" title="Очистить (возврат на центр)"
                        @click="removeVirtual(r)"><i class="bi bi-trash"></i></button>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="5" class="t-center page-fbs-virtual__empty">Ничего не найдено</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="wb-pager">
        <button class="btn btn--outline btn-sm" :disabled="page <= 1" @click="page--; reload()">‹ Назад</button>
        <span class="wb-pager__label">Стр. {{ page }} / {{ pages }} · всего {{ total }}</span>
        <button class="btn btn--outline btn-sm" :disabled="page >= pages" @click="page++; reload()">Вперёд ›</button>
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
            <table class="tbl page-fbs-virtual__table--compact">
              <thead>
                <tr>
                  <th class="t-center">ID</th><th class="t-left">Название</th>
                  <th class="t-center">Виртуальный</th>
                  <th class="t-center">Учитывать заказы</th>
                  <th class="t-right"></th><th class="t-right"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="w in warehouses" :key="w.id" :class="{ 'page-fbs-virtual__row--processing': !w.is_processing }">
                  <td class="t-center num">{{ w.warehouseId }}</td>
                  <td class="t-left">{{ w.name }}<br><small class="page-fbs-virtual__sub">{{ w.address }}</small></td>
                  <td class="t-center">
                    <span class="badge" :class="w.is_virtual ? 'badge--ok' : 'badge--neutral'">
                      {{ w.is_virtual ? 'Да' : 'Нет' }}
                    </span>
                  </td>
                  <td class="t-center">
                    <span class="badge" :class="w.consider_orders ? 'badge--info' : 'badge--neutral'">
                      {{ w.consider_orders ? 'Да' : 'Нет' }}
                    </span>
                  </td>
                  <td class="t-right">
                    <button class="btn btn--outline btn-sm w-100"
                            @click="toggleWh(w, 'is_virtual')">
                      {{ w.is_virtual ? 'Снять' : 'Сделать виртуальным' }}
                    </button>
                  </td>
                  <td class="t-right">
                    <button class="btn btn--outline btn-sm w-100"
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
            <p class="page-fbs-virtual__sub">
              Данные из wb_stock_ledger (doc_type='fbs_order'). Ожидающих списаний: {{ logPending }}.
            </p>
            <table class="tbl page-fbs-virtual__table--compact">
              <thead>
                <tr><th class="t-left">Дата</th><th class="t-left">Заказ</th><th class="t-left">Склад</th>
                  <th class="t-left">Баркод</th><th class="t-right num">Дельта</th>
                  <th class="t-right num">До</th><th class="t-right num">После</th></tr>
              </thead>
              <tbody>
                <tr v-for="l in logRows" :key="l.id">
                  <td class="t-left page-fbs-virtual__sub">{{ l.created_at }}</td>
                  <td class="t-left page-fbs-virtual__sub">{{ l.doc_id }}</td>
                  <td class="t-left page-fbs-virtual__sub">{{ l.warehouse_name || l.warehouseId }}</td>
                  <td class="t-left num">{{ l.sku }}</td>
                  <td class="t-right num" :class="l.qty_delta < 0 ? 't-neg' : 't-pos'">{{ l.qty_delta }}</td>
                  <td class="t-right num">{{ l.qty_before }}</td>
                  <td class="t-right num">{{ l.qty_after }}</td>
                </tr>
                <tr v-if="!logRows.length">
                  <td colspan="7" class="t-center page-fbs-virtual__empty">Списаний пока нет</td>
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
import '@/assets/css/pages/page-fbs-virtual.css'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { STOCK_DOCS_TABS } from '@/components/common/workspaceTabs'

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
