<template>
  <div class="container-xxl page-stock-reports">
    <!-- Шапка блока «Отчёты»: заголовок + правое меню (пилюли темы) -->
    <WbWorkspaceHead
      :title="tabLabel"
      :workspace-tabs="STOCK_REPORTS_TABS"
      :workspace-active="tab"
    />

    <!-- Фильтр — панель темы (.wb-filter-panel).
         Период — стандартный фильтр дат темы (WbDateRangeFilter, режим bare):
         пресеты 7/14/30/90/365/год + «Период с/по». Свои кнопки компонента
         в bare не рисуются — кнопки отчёта свои (theme.md §5.6.1). -->
    <div class="wb-filter-panel">
      <div class="page-stock-reports__filter-top">
        <WbDateRangeFilter
          v-if="hasPeriod"
          :key="tab"
          v-model:from="dateFrom"
          v-model:to="dateTo"
          :default-preset="tab === 'card' ? '' : '30'"
          bare
          @apply="onDates"
        />

        <div class="page-stock-reports__fields">
          <div v-if="companyOptions.length > 1" class="wb-field">
            <label class="wb-field__label">Компания</label>
            <select v-model="companyId" class="wb-select">
              <option v-for="c in companyOptions" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>

          <div class="wb-field">
            <label class="wb-field__label">Склад</label>
            <select v-model="warehouseId" class="wb-select" @change="reload()">
              <option value="all">Все склады</option>
              <option v-for="w in warehouses" :key="w.id" :value="String(w.id)">{{ w.name }}</option>
            </select>
          </div>

          <div v-if="tab === 'balance'" class="wb-field">
            <label class="wb-field__label">На дату (пусто = сейчас)</label>
            <WbDateInput v-model="onDate" />
          </div>
          <div v-if="tab === 'balance'" class="wb-field">
            <label class="wb-field__label">Только с наличием</label>
            <div class="form-check">
              <input id="only-avail" v-model="onlyAvailable" type="checkbox" class="form-check-input" @change="reload()">
              <label class="form-check-label wb-check-label" for="only-avail">показывать</label>
            </div>
          </div>

          <div v-if="tab === 'card'" class="wb-field">
            <label class="wb-field__label">Баркод / артикул / название</label>
            <input v-model="term" class="wb-input" placeholder="начните вводить" @keyup.enter="reload()">
          </div>

          <div v-if="tab === 'nonliquid'" class="wb-field">
            <label class="wb-field__label">Без движений, дней</label>
            <input v-model.number="days" type="number" min="1" max="365" class="wb-input" @change="reload()">
          </div>

          <div v-if="tab !== 'card'" class="wb-field">
            <label class="wb-field__label">Поиск</label>
            <input v-model="q" class="wb-input" placeholder="sku / артикул / название" @keyup.enter="reload()">
          </div>
        </div>
      </div>

      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" @click="reload()">
          <i class="bi bi-search me-1"></i>Показать
        </button>
        <button class="btn btn--outline" @click="reset()">Сбросить</button>
      </div>
    </div>

    <!-- Таблица — блок темы .tbl-card (theme.md §5.5) -->
    <div class="tbl-card">
      <div class="card__hd">
        <span>{{ tabLabel }}</span>
        <span class="hd-badge">{{ total }} поз.</span>
        <span class="spacer"></span>
        <ExcelButton :disabled="!rows.length" @click="exportExcel" />
      </div>

      <div v-if="loading" class="page-stock-reports__loading">
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span>Загрузка данных…</span>
      </div>
      <div v-else-if="isError" class="page-stock-reports__msg">
        <div class="wb-panel">
          <div class="wb-panel__bd">
            <span class="badge badge--bad">Ошибка загрузки</span>
            <div class="mt-2">{{ errorText }}</div>
          </div>
        </div>
      </div>
      <div v-else-if="!companyId" class="page-stock-reports__msg">
        <div class="wb-panel">
          <div class="wb-panel__bd">
            <span class="badge badge--warn">Нужна компания</span>
            <div class="mt-2">Отчёты по складу считаются в разрезе одной компании. Выберите компанию в фильтре.</div>
          </div>
        </div>
      </div>
      <div v-else-if="!rows.length" class="page-stock-reports__msg">
        <div class="wb-panel">
          <div class="wb-panel__bd">
            <span class="badge badge--neutral">{{ emptyBadge }}</span>
            <div class="mt-2">{{ emptyText }}</div>
          </div>
        </div>
      </div>
      <div v-else class="tbl-wrap">
        <table class="tbl page-stock-reports__table">
          <thead>
            <tr>
              <th v-for="c in cols" :key="c.key" :class="c.cls">{{ c.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in rows" :key="i">
              <td v-for="c in cols" :key="c.key" :class="c.cls">
                <ProductCell
                  v-if="c.key === 'product'"
                  :photo="r.photos"
                  :title="r.title || ''"
                  :vendor="r.vendorCode || ''"
                  :brand="r.brand || ''"
                  :subject="r.subjectName || ''"
                  :nm-id="r.nmID"
                  :link="'/wb/detail?nm_id=' + r.nmID"
                  :link-label="'WB: ' + r.nmID"
                  copy-nm
                  copy-link
                />
                <template v-else-if="c.key === 'sku'">
                  <span class="num">{{ r.sku }}</span>
                </template>
                <template v-else-if="c.key === 'warehouse'">
                  {{ r.warehouse_name || r.warehouseId || '—' }}
                </template>
                <template v-else-if="c.key === 'delta'">
                  <span :class="Number(r.qty_delta) < 0 ? 't-neg' : 't-pos'">
                    {{ Number(r.qty_delta) > 0 ? '+' : '' }}{{ r.qty_delta }}
                  </span>
                </template>
                <template v-else-if="c.key === 'signed'">
                  <span :class="Number(r[c.key]) > 0 ? 't-pos' : (Number(r[c.key]) < 0 ? 't-neg' : '')">
                    {{ Number(r[c.key]) > 0 ? '+' : '' }}{{ r[c.key] }}
                  </span>
                </template>
                <template v-else-if="c.key === 'doc'">
                  {{ r.doc_type }}<span v-if="r.doc_id"> #{{ r.doc_id }}</span>
                </template>
                <template v-else-if="c.key === 'created_at'">
                  {{ String(r.created_at || '').slice(0, 16).replace('T', ' ') }}
                </template>
                <template v-else>{{ r[c.key] ?? '—' }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="wb-pager">
        <button class="btn btn--outline btn-sm" :disabled="page <= 1" @click="page--; reload()">‹ Назад</button>
        <span class="wb-pager__label">Стр. {{ page }} / {{ pages }} · показано {{ rows.length }} из {{ total }}</span>
        <button class="btn btn--outline btn-sm" :disabled="page >= pages" @click="page++; reload()">Вперёд ›</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-stock-reports.css'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'
import { useAuthStore } from '../stores/auth'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import WbDateRangeFilter from '@/components/common/WbDateRangeFilter.vue'
import WbDateInput from '@/components/common/WbDateInput.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import ProductCell from '@/components/common/ProductCell.vue'
import { STOCK_REPORTS_TABS } from '@/components/common/workspaceTabs'
import { exportXlsx } from '@/utils/exportXlsx'

type TabKey = 'balance' | 'turnover' | 'card' | 'nonliquid'

const TABS: { key: TabKey, label: string }[] = [
  { key: 'balance', label: 'Наличие' },
  { key: 'turnover', label: 'Оборотная ведомость' },
  { key: 'card', label: 'Карточка товара' },
  { key: 'nonliquid', label: 'Неликвиды' },
]

const COLS: Record<TabKey, { key: string, label: string, cls?: string }[]> = {
  balance: [
    { key: 'product', label: 'Товар', cls: 't-left' },
    { key: 'sku', label: 'Баркод', cls: 't-center' },
    { key: 'warehouse', label: 'Склад', cls: 't-left' },
    { key: 'quantity', label: 'Остаток', cls: 't-right num' },
  ],
  turnover: [
    { key: 'product', label: 'Товар', cls: 't-left' },
    { key: 'sku', label: 'Баркод', cls: 't-center' },
    { key: 'start_qty', label: 'Нач.', cls: 't-right num' },
    { key: 'receipt', label: 'Приход', cls: 't-right num' },
    { key: 'expense', label: 'Расход', cls: 't-right num' },
    { key: 't_in', label: 'Перем+', cls: 't-right num' },
    { key: 't_out', label: 'Перем-', cls: 't-right num' },
    { key: 'inv', label: 'Инв.', cls: 't-right num' },
    { key: 'adj', label: 'Корр.', cls: 't-right num' },
    { key: 'end_qty', label: 'Кон.', cls: 't-right num' },
    { key: 'turnover', label: 'Оборот', cls: 't-right num' },
  ],
  card: [
    { key: 'product', label: 'Товар', cls: 't-left' },
    { key: 'sku', label: 'Баркод', cls: 't-center' },
    { key: 'created_at', label: 'Дата', cls: 't-left' },
    { key: 'doc', label: 'Док', cls: 't-left' },
    { key: 'warehouse', label: 'Склад', cls: 't-left' },
    { key: 'delta', label: 'Дельта', cls: 't-right num' },
    { key: 'qty_before', label: 'До', cls: 't-right num' },
    { key: 'qty_after', label: 'После', cls: 't-right num' },
    { key: 'username', label: 'Юзер', cls: 't-left' },
  ],
  nonliquid: [
    { key: 'product', label: 'Товар', cls: 't-left' },
    { key: 'sku', label: 'Баркод', cls: 't-center' },
    { key: 'warehouse', label: 'Склад', cls: 't-left' },
    { key: 'quantity', label: 'Остаток', cls: 't-right num' },
    { key: 'last_move', label: 'Последнее движение', cls: 't-left' },
  ],
}

const route = useRoute()
const qc = useQueryClient()
const auth = useAuthStore()

const pathTab = (): TabKey => {
  const p = String(route.path || '')
  if (p.includes('turnover')) return 'turnover'
  if (p.includes('card')) return 'card'
  if (p.includes('nonliquid')) return 'nonliquid'
  return 'balance'
}

const tab = ref<TabKey>(pathTab())
watch(() => route.path, () => {
  const next = pathTab()
  if (next === tab.value) return
  tab.value = next
  // Период — под пресет своей вкладки: у «Карточки товара» пусто (весь журнал),
  // у «Оборотной ведомости» — 30 дней.
  const [f, t] = periodForTab(next)
  dateFrom.value = f
  dateTo.value = t
  page.value = 1
})

const tabLabel = computed(() => TABS.find(t => t.key === tab.value)?.label || 'Отчеты склада')
const cols = computed(() => COLS[tab.value])

const warehouseId = ref('all')
const warehouses = ref<any[]>([])
const q = ref('')
const term = ref('')
const onDate = ref('')
const days = ref(30)
const onlyAvailable = ref(false)
const page = ref(1)
const pageSize = 100

/* Период — через стандартный фильтр дат темы (WbDateRangeFilter): пресеты
   7/14/30/90/365/год + ручные даты. Отчёты с периодом — «Оборотная ведомость»
   и «Карточка товара»; в «Наличии» период не нужен (там одна дата снимка),
   в «Неликвидах» — окно «без движений N дней». */
const hasPeriod = computed(() => tab.value === 'turnover' || tab.value === 'card')

/** Дата в формате YYYY-MM-DD по локальному времени (toISOString сдвигает сутки). */
function fmtD(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Период по умолчанию — последние 30 дней (пресет «30 дней» фильтра дат). */
function defaultPeriod(): [string, string] {
  const to = new Date()
  const from = new Date(to)
  from.setDate(from.getDate() - 29)
  return [fmtD(from), fmtD(to)]
}

/* «Оборотная ведомость» — период по умолчанию 30 дней (как у пресета фильтра).
   «Карточка товара» — период пустой: без дат бэк отдаёт весь журнал проводок по
   SKU, и ограничение 30 днями прятало бы старые движения. */
function periodForTab(t: TabKey): [string, string] {
  return t === 'card' ? ['', ''] : defaultPeriod()
}
const [initFrom, initTo] = periodForTab(pathTab())
const dateFrom = ref(initFrom)
const dateTo = ref(initTo)

/* Отчёты по складу — company-scoped (остатки/проводки лежат в company-scoped
   таблицах). В режиме «Все компании» бэк отвечает 400 — поэтому страница
   имеет свой селектор компании: он шлёт company_id в query (deps._resolve_company_id
   читает query-параметр раньше заголовка X-Company-Id) и не меняет глобальную
   область действия приложения. */
const companyOptions = computed(() => auth.companies || [])
const companyId = ref<number | null>(null)

function syncCompany() {
  if (auth.companyId !== 'all') {
    companyId.value = Number(auth.companyId)
    return
  }
  // «Все компании» — берём первую доступную, чтобы данные появились сразу.
  const first = companyOptions.value[0]
  companyId.value = first ? Number(first.id) : null
}

syncCompany()
watch(() => auth.companyId, () => { syncCompany() })
watch(() => auth.companies.length, () => { syncCompany() })
watch(companyId, () => {
  page.value = 1
  loadWarehouses()
  qc.invalidateQueries({ queryKey: ['stock-reports'] })
})

const params = computed(() => {
  const p: Record<string, any> = { warehouse_id: warehouseId.value, page: page.value, page_size: pageSize }
  if (companyId.value) p.company_id = companyId.value
  if (tab.value === 'balance') {
    if (onDate.value) p.date = onDate.value
    if (onlyAvailable.value) p.only_available = 1
    if (q.value) p.q = q.value
  } else if (tab.value === 'turnover') {
    if (dateFrom.value) p.date_from = dateFrom.value
    if (dateTo.value) p.date_to = dateTo.value
    if (q.value) p.q = q.value
  } else if (tab.value === 'card') {
    p.sku = term.value
    if (dateFrom.value) p.date_from = dateFrom.value
    if (dateTo.value) p.date_to = dateTo.value
  } else {
    p.days = days.value
    if (q.value) p.q = q.value
  }
  return p
})

const { data, isLoading: loading, isError, error } = useQuery({
  queryKey: computed(() => ['stock-reports', tab.value, JSON.stringify(params.value)] as const),
  queryFn: () => api.get(`/api/stock-reports/${tab.value}`, { params: params.value })
    .then(r => r.data),
  enabled: computed(() => companyId.value !== null),
})

const rows = computed<any[]>(() => (data.value?.rows as any[]) || [])
const total = computed(() => Number(data.value?.total || 0))
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const errorText = computed(() => {
  const e: any = error.value
  return e?.response?.data?.detail || e?.message || 'Не удалось получить данные отчёта.'
})

/* Пустое состояние. «Карточка товара» — журнал проводок по ОДНОМУ товару:
   бэк без поискового запроса (barcode/артикул/название) отдаёт пустоту, поэтому
   подсказка должна говорить, что искать, а не «проверьте фильтры». */
const emptyBadge = computed(() => (tab.value === 'card' ? 'Нужен товар' : 'Нет данных'))
const emptyText = computed(() => (tab.value === 'card'
  ? 'Введите баркод, артикул или название товара в поле выше — покажем журнал проводок по нему.'
  : 'По выбранной компании нет записей. Проверьте фильтры или склад.'))

const reload = () => {
  page.value = 1
  qc.invalidateQueries({ queryKey: ['stock-reports'] })
}

/** Пресет периода из WbDateRangeFilter — значения уже в v-model, чистим страницу. */
const onDates = (p: { from: string, to: string }) => {
  dateFrom.value = p.from
  dateTo.value = p.to
  page.value = 1
}

const reset = () => {
  warehouseId.value = 'all'
  q.value = ''
  term.value = ''
  onDate.value = ''
  days.value = 30
  onlyAvailable.value = false
  const [f, t] = periodForTab(tab.value)
  dateFrom.value = f
  dateTo.value = t
  reload()
}

async function loadWarehouses() {
  if (!companyId.value) {
    warehouses.value = []
    return
  }
  const res = await api.get('/api/stock-reports/warehouses', { params: { company_id: companyId.value } })
    .then(r => r.data).catch(() => ({ rows: [] }))
  warehouses.value = res.rows || []
}
loadWarehouses()

// Экспорт — общий exportXlsx (utils/exportXlsx.ts): он собирает лист через
// json_to_sheet, поэтому строки — объекты с русскими ключами-подписями колонок.
const exportExcel = async () => {
  if (!rows.value.length) return
  const cs = cols.value
  const cell = (r: any, c: any) => {
    if (c.key === 'product') return `${r.vendorCode || ''} ${r.nmID || ''} ${r.title || ''}`.trim()
    if (c.key === 'created_at') return String(r.created_at || '').slice(0, 16).replace('T', ' ')
    if (c.key === 'doc') return `${r.doc_type || ''}${r.doc_id ? ' #' + r.doc_id : ''}`
    if (c.key === 'warehouse') return r.warehouse_name || r.warehouseId || ''
    if (c.key === 'signed') return Number(r[c.key]) > 0 ? `+${r[c.key]}` : (r[c.key] ?? '')
    return r[c.key] ?? ''
  }
  const data = rows.value.map((r: any) => {
    const o: Record<string, any> = {}
    for (const c of cs) o[c.key === 'product' ? 'Товар' : c.label] = cell(r, c)
    return o
  })
  await exportXlsx({
    rows: data,
    filename: `wb-stock-${tab.value}_${new Date().toISOString().slice(0, 10)}.xlsx`,
    sheetName: tabLabel.value.slice(0, 30),
  })
}
</script>
