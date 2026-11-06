<template>
  <div class="container-xxl page-wb-promotions page-wb-promotions--selection">
    <WbWorkspaceHead
      title="Акции WB"
      :workspace-tabs="PROMOTIONS_TABS"
      workspace-active="selection"
    />

    <!-- Фильтр: выбор акции — над датами; даты = окно истории для маржи, маска товара, пороги -->
    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:product="filters.product"
      :show-brand-category="false"
      default-preset="30"
      @apply="onApply"
      @reset="onReset"
    >
      <template #top>
        <div class="wb-field page-wb-promotions__promo-field">
          <label class="wb-field__label">Акция</label>
          <PromoSelect v-model="filters.promo" :rows="promos" @change="onApply" />
        </div>
      </template>
      <template #fields>
        <PromoParamsPanel v-model="params" :is-auto="isAuto" />
      </template>
    </WbUniversalFilter>

    <div v-if="error" class="page-wb-promotions__alert">
      <i class="bi bi-exclamation-triangle"></i>
      <span>{{ error }}</span>
    </div>

    <PromoCard
      v-if="appliedFilters.promo"
      class="mb-3"
      :promo="promo"
      :rows="rows"
      :selected-count="uploadCount"
      :updated-at="updatedAt"
      :report="reportMeta"
      :params="params"
      :sort="appliedFilters.sort"
      :order="appliedFilters.order"
      :in-action="appliedFilters.in_action"
      :stock="appliedFilters.stock"
      @update:params="onParamsUpdate"
      @update:sort="onSortUpdate('sort', $event)"
      @update:order="onSortUpdate('order', $event)"
      @update:in-action="onSortUpdate('in_action', $event)"
      @update:stock="onSortUpdate('stock', $event)"
      @reload="reloadProducts"
      @upload="onUpload"
      @quarantine-check="onQuarantineCheck"
    />

    <div v-else-if="!loading" class="page-wb-promotions__empty">
      Выберите акцию — список товаров и расчёт маржи появятся под карточкой акции
    </div>

    <template v-if="appliedFilters.promo">
      <!-- KPI: в обычной акции отметка = «включить в акцию», в автоакции —
           наоборот: прошедшие пороги попадают в акцию автоматом, а помеченные
           мы исключаем. Поэтому подписи и значения разные. -->
      <div class="grid-4 page-wb-promotions__kpi">
        <div class="tile tile--8">
          <div class="tile__label">{{ kpiMain.label }}</div>
          <div class="tile__value">{{ kpiMain.value }}</div>
          <div class="tile__foot">{{ kpiMain.foot }}</div>
        </div>
        <div class="tile tile--10">
          <div class="tile__label">{{ kpiMark.label }}</div>
          <div class="tile__value">{{ kpiMark.value }}</div>
          <div class="tile__foot">{{ kpiMark.foot }}</div>
        </div>
        <div class="tile tile--1">
          <div class="tile__label">Окно истории</div>
          <div class="tile__value">{{ windowInfo.days }} дн</div>
          <div class="tile__foot">{{ windowInfo.date_from }} — {{ windowInfo.date_to }}</div>
        </div>
        <div class="tile tile--1">
          <div class="tile__label">Отмечено вручную</div>
          <div class="tile__value">{{ manualCount }}</div>
          <div class="tile__foot">добавлено вами</div>
        </div>
      </div>

      <!-- Действия с файлами — над таблицей (по AGENTS.md) -->
      <div class="page-wb-promotions__excel">
        <div class="page-wb-promotions__excel-wrap" ref="excelWrapRef">
          <button class="btn btn-light page-wb-promotions__excel-btn" type="button" @click="excelOpen = !excelOpen">
            Действия с Excel <i class="bi ms-1" :class="excelOpen ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
          </button>
          <div v-if="excelOpen" class="page-wb-promotions__excel-list">
            <button class="page-wb-promotions__excel-item" @click="excelOpen = false; doExportTemplate()">
              <i class="bi bi-file-earmark-spreadsheet me-2"></i>Скачать шаблон
            </button>
            <button class="page-wb-promotions__excel-item" @click="excelOpen = false; pickTemplate()">
              <i class="bi bi-upload me-2"></i>Загрузить из шаблона
            </button>
            <button class="page-wb-promotions__excel-item" title="Форма отчёта WB — загрузить в ЛК, чтобы исключить товары из акции" @click="excelOpen = false; doExportExclude()">
              <i class="bi bi-file-earmark-excel me-2"></i>Список для исключения
            </button>
            <button class="page-wb-promotions__excel-item" title="Цены и скидки отмеченных товаров — форма 00_DAY" @click="excelOpen = false; doExportWbPrices()">
              <i class="bi bi-file-earmark-spreadsheet me-2"></i>Список цен для каталога
            </button>
          </div>
        </div>
        <input ref="templateFileEl" type="file" accept=".xlsx,.xls" class="d-none" @change="onTemplateFile">
      </div>

      <!-- Таблица -->
      <PromoSelectionTable
        :rows="rows"
        :params="appliedFilters"
        :loading="analyzing"
        :basis="basisText"
        :sort="appliedFilters.sort"
        :order="appliedFilters.order"
        :in-action="appliedFilters.in_action"
        :stock="appliedFilters.stock"
        :sel="selFilter"
        :page-size="pageSize"
        @toggle="onToggle"
        @export="doExport"
        @update:page-size="onPageSize"
        @update:sel="selFilter = $event"
      />

      <!-- Превью загрузки отчёта: что распознано и что изменится -->
      <WbConfirmDialog
        :open="previewOpen"
        :text="previewText"
        :hint="previewHint"
        confirm-text="Загрузить"
        :busy="savingReport"
        @confirm="onPreviewConfirm"
        @cancel="onPreviewCancel"
      />

      <!-- Загрузка цен и скидок: риски карантина перед отправкой в WB -->
      <div v-if="pricesDialog" class="wb-modal-backdrop" @click.self="pricesDialog = false">
        <div class="wb-modal-box wb-confirm__box">
          <div class="wb-confirm__text">
            Загрузить цены и скидки в WB: {{ sendItems.length }} товаров
          </div>
          <div v-if="riskyItems.length" class="wb-confirm__hint">
            <b>Риск карантина:</b> цена со скидкой ниже трети текущей — WB отправит
            их в карантин и продолжит продавать по старой цене
            <template v-if="pricesPrep?.items.length"> · проверка по текущим ценам WB</template>
            <ul class="wb-confirm__list">
              <li v-for="x in riskyItems" :key="x.nm_id">
                {{ x.title || 'Арт. ' + x.nm_id }} ({{ x.nm_id }}): было
                {{ fmtRub(x.old_discounted) }} → станет {{ fmtRub(x.new_discounted) }}
              </li>
            </ul>
          </div>
          <div class="wb-modal-actions">
            <button class="btn btn-sm btn-primary" :disabled="uploading" @click="sendPrices(true)">
              <span v-if="uploading" class="spinner-border spinner-border-sm"></span>
              Отправить всё
            </button>
            <button v-if="riskyItems.length" class="btn btn-sm btn-secondary" :disabled="uploading" @click="sendPrices(false)">
              Отправить без рискованных
            </button>
            <button class="btn btn-sm btn-secondary" :disabled="uploading" @click="pricesDialog = false">Отмена</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-promotions.css'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import WbConfirmDialog from '@/components/common/WbConfirmDialog.vue'
import PromoCard from '@/components/promotions/PromoCard.vue'
import PromoParamsPanel from '@/components/promotions/PromoParamsPanel.vue'
import PromoSelect from '@/components/promotions/PromoSelect.vue'
import PromoSelectionTable from '@/components/promotions/PromoSelectionTable.vue'
import { PROMOTIONS_TABS } from '@/components/common/workspaceTabs'
import { clearPromoPrefs, loadPromoPrefs, savePromoPrefs } from '@/composables/usePromoParams'
import {
  DEFAULT_CALC_PARAMS,
  exportPromoExclude,
  exportPromoRows,
  exportPromoTemplate,
  exportPromoWbPrices,
  parseWbPromoReport,
  promotionsApi,
  type PromoAnalysisRow,
  type PromoCalcParams,
  type PromoReportItem,
  type PromoRow,
} from '@/api/promotions'

const route = useRoute()
const router = useRouter()

const promos = ref<PromoRow[]>([])
const rows = ref<PromoAnalysisRow[]>([])
const promo = ref<PromoRow | null>(null)
const error = ref('')
const loading = ref(false)
/** Загруженный отчёт WB по акции. */
const reportMeta = ref<{ count: number; loaded_at: string | null }>({ count: 0, loaded_at: null })
const analyzing = ref(false)
const refreshing = ref(false)

const params = ref<PromoCalcParams>({ ...DEFAULT_CALC_PARAMS })

const windowInfo = ref({ date_from: '', date_to: '', days: 30 })
const summary = reactive({ total: 0, recommend: 0, reject: 0, selected: 0 })

const isAuto = computed(() => (promo.value?.promo_type || '') === 'auto')
const selectedCount = computed(() => rows.value.filter(r => r.selected).length)
const selectedIds = computed(() => rows.value.filter(r => r.selected).map(r => r.nm_id))
/** Отправлять в WB имеет смысл только отмеченные товары, не «уже в акции». */
const selectedRows = computed(() => rows.value.filter(r => r.selected && !r.in_action))
const manualCount = computed(() => rows.value.filter(r => r.manual).length)

/** Товаров, которые уже в акции по данным WB (отчёт): у них птичка стоит
 *  и не снимается. Без загруженного отчёта их нет. */
const inActionCount = computed(() => rows.value.filter(r => r.in_action).length)

/** Помечено нами для исключения из акции: отмеченные и НЕ «уже в акции»
 *  (товары, которые WB сама поставила в акцию, исключением не считаем). */
const excludedCount = computed(() => rows.value.filter(r => r.selected && !r.in_action).length)

/** Наша оценка: сколько товаров попадёт в акцию — все строки минус исключённые.
 *  Числа самого WB (сколько он насчитал участников) — в карточке акции. */
const willJoinCount = computed(() => Math.max(0, rows.value.length - excludedCount.value))

/** Плитки KPI. В обычной акции отметка = «включить в акцию» (в неё добавляем
 *  выбранные), в автоакции наоборот: прошедшие пороги WB включает сам, а
 *  помеченные мы исключаем. */
const kpiMain = computed(() => isAuto.value
  ? {
      label: 'Попадут в акцию',
      value: willJoinCount.value,
      foot: inActionCount.value
        ? `наша оценка, из них ${inActionCount.value} уже в акции по отчёту WB`
        : 'наша оценка: подходящих минус исключённые',
    }
  : {
      label: 'В акции',
      value: inActionCount.value,
      foot: 'уже участвуют, птичка заблокирована',
    })

const kpiMark = computed(() => isAuto.value
  ? {
      label: 'Помечено для исключения',
      value: excludedCount.value,
      foot: 'не прошли пороги — исключаем из акции',
    }
  : {
      label: 'Отмечено',
      value: selectedCount.value,
      foot: `из ${Math.max(0, rows.value.length - inActionCount.value)} не в акции`,
    })

/** Сколько строк реально уйдёт в WB (отмеченные, кроме «уже в акции»). */
const uploadCount = computed(() => selectedRows.value.length)

const basisText = computed(() => `на единицу · окно ${windowInfo.value.days} дн (${windowInfo.value.date_from} — ${windowInfo.value.date_to})`)

/** Актуальность данных — из кэша (его наполняет воркер promotions_sync). */
const updatedAt = computed(() => {
  const t = promo.value?.fetched_at || ''
  return t ? t.slice(0, 16).replace('T', ' ') : ''
})

function isoDate(d: Date): string {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
}
function defaultRange(days: number): { date_from: string; date_to: string } {
  const to = new Date()
  const from = new Date(to.getTime())
  from.setDate(from.getDate() - (days - 1))
  return { date_from: isoDate(from), date_to: isoDate(to) }
}

/** Сортировки и фильтр «В акции» — тоже в URL. */
const SORTS = ['margin', 'sales', 'name']
const ORDERS = ['asc', 'desc']
const IN_ACTIONS = ['all', 'yes', 'no']

/** Сохранённые настройки пользователя (localStorage) — значения по умолчанию. */
const prefs = loadPromoPrefs()

/** Строк на страницу — настройка пользователя (по умолчанию 100). */
const pageSize = ref<number>(Number(prefs.rows) > 0 ? Number(prefs.rows) : 100)

/** Отбор строк по отметке (кнопки в шапке таблицы): all | sel | unsel.
 *  Живёт только в памяти страницы — при перезагрузке сбрасывается. */
const selFilter = ref('all')

/** Фильтры (акция + окно истории + пороги) живут в URL. */
const fromRoute = (q: any) => {
  const d = defaultRange(30)
  const num = (v: any, def: number) => (v === undefined || v === null || v === '' ? def : Number(v))
  const b = (v: any, def: boolean) => (v === undefined || v === null || v === '' ? def : v === '1' || v === 'true')
  // «Падение маржи, %»; старый URL-параметр max_drop_pp — тот же смысл
  const maxDrop = q.max_drop_pct === undefined || q.max_drop_pct === null || q.max_drop_pct === ''
    ? (q.max_drop_pp !== undefined && q.max_drop_pp !== '' ? Number(q.max_drop_pp)
        : (prefs.max_drop_pct ?? DEFAULT_CALC_PARAMS.max_drop_pct))
    : Number(q.max_drop_pct)
  const sort = String(q.sort || prefs.sort || 'sales')
  const order = String(q.order || prefs.order || 'desc')
  const inAction = String(q.in_action || prefs.in_action || 'no')
  const stock = String(q.stock || prefs.stock || 'all')
  // «Учитывать»: только Мин маржу (1) или все параметры (0)
  const onlyMin = q.only_min !== undefined && q.only_min !== null && q.only_min !== ''
    ? (q.only_min === '1' || q.only_min === 'true')
    : Boolean(prefs.only_min_margin)
  const dateFrom = String(q.date_from || d.date_from)
  const dateTo = String(q.date_to || d.date_to)
  return {
    promo: String(q.promo || ''),
    date_from: dateFrom,
    date_to: dateTo,
    // окно в днях — всегда по датам (в URL его нет)
    days: windowDays({ date_from: dateFrom, date_to: dateTo }),
    product: String(q.nm_id || ''),
    min_margin_rub: num(q.min_margin_rub, prefs.min_margin_rub ?? DEFAULT_CALC_PARAMS.min_margin_rub),
    max_drop_pct: maxDrop,
    max_drop_rub: num(q.max_drop_rub, prefs.max_drop_rub ?? DEFAULT_CALC_PARAMS.max_drop_rub),
    only_min_margin: onlyMin,
    min_stock_wb: num(q.min_stock_wb, prefs.min_stock_wb ?? DEFAULT_CALC_PARAMS.min_stock_wb),
    auto_discount: num(q.auto_discount, prefs.auto_discount ?? DEFAULT_CALC_PARAMS.auto_discount),
    include_reviews: b(q.reviews, prefs.include_reviews ?? DEFAULT_CALC_PARAMS.include_reviews),
    include_adv: b(q.adv, prefs.include_adv ?? DEFAULT_CALC_PARAMS.include_adv),
    include_cashback: b(q.cashback, prefs.include_cashback ?? DEFAULT_CALC_PARAMS.include_cashback),
    include_penalties: b(q.penalties, prefs.include_penalties ?? DEFAULT_CALC_PARAMS.include_penalties),
    tax_rate: DEFAULT_CALC_PARAMS.tax_rate,
    nm_id: String(q.nm_id || ''),
    sort: SORTS.includes(sort) ? sort : 'sales',
    order: ORDERS.includes(order) ? order : 'desc',
    in_action: IN_ACTIONS.includes(inAction) ? inAction : 'no',
    stock: ['all', 'in'].includes(stock) ? stock : 'all',
  }
}

type Filters = ReturnType<typeof fromRoute>

/** Окно истории в днях: считаем по выбранным датам (они всегда видны в фильтре),
 *  отдельного поля «дней» больше нет; фолбэк — 30 дней. */
function windowDays(a: { date_from: string; date_to: string }): number {
  const from = new Date(a.date_from + 'T00:00:00')
  const to = new Date(a.date_to + 'T00:00:00')
  const diff = Math.round((to.getTime() - from.getTime()) / 86400000) + 1
  return Number.isFinite(diff) && diff > 0 ? Math.min(diff, 365) : 30
}

/** Поля панели порогов — живут в params; даты, акция и сортировка — в filters.
 *  Сливаем только их: иначе правки панели затирают даты, а «Применить» сбрасывает
 *  правки панели на значения из URL. */
const PARAM_KEYS = [
  'min_margin_rub', 'max_drop_pct', 'max_drop_rub', 'only_min_margin',
  'min_stock_wb', 'auto_discount', 'include_reviews', 'include_adv',
  'include_cashback', 'include_penalties',
] as const

function withParams(base: Filters, p: PromoCalcParams): Filters {
  const out: any = { ...base }
  for (const k of PARAM_KEYS) out[k] = (p as any)[k]
  return out as Filters
}

const filters = ref<Filters>(fromRoute(route.query))
const appliedFilters = ref<Filters>({ ...filters.value })
params.value = { ...appliedFilters.value }

let syncing = false
function syncRoute() {
  const a = appliedFilters.value
  const q: Record<string, string> = {
    promo: a.promo,
    date_from: a.date_from,
    date_to: a.date_to,
    max_drop_pct: String(a.max_drop_pct),
    max_drop_rub: String(a.max_drop_rub),
    min_margin_rub: String(a.min_margin_rub),
    min_stock_wb: String(a.min_stock_wb),
    auto_discount: String(a.auto_discount),
  }
  if (a.only_min_margin) q.only_min = '1'
  if (a.product) q.nm_id = a.product
  if (a.include_reviews) q.reviews = '1'
  if (a.include_adv) q.adv = '1'
  if (a.include_cashback) q.cashback = '1'
  if (a.include_penalties) q.penalties = '1'
  if (a.sort) q.sort = a.sort  // «по продажам» тоже пишем — чтобы URL был однозначным
  if (a.order && a.order !== 'desc') q.order = a.order
  if (a.in_action && a.in_action !== 'no') q.in_action = a.in_action
  if (a.stock && a.stock !== 'all') q.stock = a.stock
  syncing = true
  router.replace({ path: '/wb-promotions/selection', query: q })
    .finally(() => setTimeout(() => (syncing = false), 50))
}

/** Сортировка / порядок / фильтры «В акции» и «Наличие» — сразу применяются и пишутся в URL. */
const onSortUpdate = (key: 'sort' | 'order' | 'in_action' | 'stock', value: string) => {
  appliedFilters.value = { ...appliedFilters.value, [key]: value } as Filters
  syncRoute()
}

/** Тумблеры «учитывать …» из карточки акции — в черновик параметров. */
const onParamsUpdate = (p: Partial<PromoCalcParams>) => {
  params.value = { ...params.value, ...p } as PromoCalcParams
}

/** Сохраняем настройки пользователя (localStorage) — пороги, тумблеры, вид таблицы. */
function persistPrefs() {
  const a = appliedFilters.value
  savePromoPrefs({
    max_drop_pct: a.max_drop_pct ?? 10,
    max_drop_rub: a.max_drop_rub ?? 5,
    only_min_margin: a.only_min_margin,
    min_margin_rub: a.min_margin_rub,
    min_stock_wb: a.min_stock_wb,
    auto_discount: a.auto_discount,
    include_reviews: a.include_reviews,
    include_adv: a.include_adv,
    include_cashback: a.include_cashback,
    include_penalties: a.include_penalties,
    sort: a.sort,
    order: a.order,
    in_action: a.in_action,
    stock: a.stock,
    rows: pageSize.value,
  })
}

/** Размер страницы — настройка пользователя. */
const onPageSize = (n: number) => {
  pageSize.value = n
  persistPrefs()
}

/* ------------------ действия с Excel ------------------ */

const excelOpen = ref(false)
const excelWrapRef = ref<HTMLElement | null>(null)
const templateFileEl = ref<HTMLInputElement | null>(null)

/** Клик вне дропдауна — закрываем. */
function onDocClick(e: MouseEvent) {
  if (!excelOpen.value) return
  const el = excelWrapRef.value
  if (el && !el.contains(e.target as Node)) excelOpen.value = false
}
onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))

/** Шаблон WB — пустой файл с одними названиями колонок. */
const doExportTemplate = async () => {
  await exportPromoTemplate(`wb_шаблон_${stamp()}.xlsx`)
}

/** Список для исключения — форма отчёта WB с нашими товарами. */
const doExportExclude = async () => {
  const list = rows.value.filter(r => r.selected && !r.in_action)
  await exportPromoExclude(list.length ? list : rows.value, `wb_exclude_${stamp()}.xlsx`)
}

/** Список цен для каталога (00_DAY) — цены и скидки отмеченных товаров. */
const doExportWbPrices = async () => {
  const list = rows.value.filter(r => r.selected && !r.in_action)
  await exportPromoWbPrices(list.length ? list : rows.value, `wb_prices_${stamp()}.xlsx`)
}

/* ------------------ загрузка из шаблона ------------------ */

const previewOpen = ref(false)
const savingReport = ref(false)
const previewData = ref<any>(null)
const pendingItems = ref<PromoReportItem[]>([])

/** Выбор файла шаблона. */
const pickTemplate = () => templateFileEl.value?.click()

const onTemplateFile = async (e: Event) => {
  const t = e.target as HTMLInputElement
  const f = t.files && t.files[0]
  t.value = ''
  if (!f || !appliedFilters.value.promo) return
  error.value = ''
  try {
    const items = await parseWbPromoReport(f)
    const res = await promotionsApi.previewReport(Number(appliedFilters.value.promo), items)
    previewData.value = res
    pendingItems.value = items
    previewOpen.value = true
  } catch (e: any) {
    error.value = 'Файл не разобрался: ' + (e?.response?.data?.detail || e?.message || 'неизвестная ошибка')
  }
}

const previewText = computed(() => {
  const p = previewData.value
  if (!p) return ''
  return `В файле ${p.total} товаров, распознано ${p.known}.`
})

const previewHint = computed(() => {
  const p = previewData.value
  if (!p) return ''
  const parts: string[] = []
  if (p.unknown_count) parts.push(`не найдено в нашем ассортименте: ${p.unknown_count}`)
  if (p.new_count) parts.push(`новых: ${p.new_count}`)
  if (p.changed_count) parts.push(`изменится значений: ${p.changed_count}`)
  if (!parts.length) parts.push('изменений не будет')
  parts.push('таблица и маржа будут посчитаны только по этому списку')
  return parts.join(' · ')
})

const onPreviewCancel = () => {
  previewOpen.value = false
  previewData.value = null
  pendingItems.value = []
}

const onPreviewConfirm = async () => {
  if (!appliedFilters.value.promo) return
  savingReport.value = true
  error.value = ''
  try {
    const res = await promotionsApi.saveReport(Number(appliedFilters.value.promo), pendingItems.value)
    reportMeta.value = { count: res.count ?? pendingItems.value.length, loaded_at: res.loaded_at ?? null }
    onPreviewCancel()
    await analyze()
  } catch (e: any) {
    error.value = 'Отчёт WB: ' + (e?.response?.data?.detail || e?.message || 'не удалось сохранить')
  } finally {
    savingReport.value = false
  }
}

const loadCalendar = async () => {
  try {
    const res = await api.get('/api/promotions/calendar', { params: {} }).then(r => r.data)
    promos.value = (res.rows || []) as PromoRow[]
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Не удалось загрузить календарь'
  }
}

const analyze = async () => {
  if (!appliedFilters.value.promo) return
  analyzing.value = true
  error.value = ''
  try {
    const res = await api.post(`/api/promotions/${appliedFilters.value.promo}/analyze`, {
      params: {
        date_from: appliedFilters.value.date_from,
        date_to: appliedFilters.value.date_to,
        days: windowDays(appliedFilters.value),
        q: appliedFilters.value.product,
        min_margin_rub: appliedFilters.value.min_margin_rub,
        max_drop_pct: appliedFilters.value.max_drop_pct,
        max_drop_rub: appliedFilters.value.max_drop_rub,
        only_min_margin: appliedFilters.value.only_min_margin,
        min_stock_wb: appliedFilters.value.min_stock_wb,
        auto_discount: appliedFilters.value.auto_discount,
        include_reviews: appliedFilters.value.include_reviews,
        include_adv: appliedFilters.value.include_adv,
        include_cashback: appliedFilters.value.include_cashback,
        include_penalties: appliedFilters.value.include_penalties,
      },
    }).then(r => r.data)
    rows.value = (res.rows || []) as PromoAnalysisRow[]
    windowInfo.value = res.window || windowInfo.value
    Object.assign(summary, res.summary || {})
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Не удалось посчитать маржу'
  } finally {
    analyzing.value = false
  }
}

const loadPromo = async (promoId: string) => {
  rows.value = []
  promo.value = null
  if (!promoId) return
  loading.value = true
  error.value = ''
  try {
    const p = await api.get(`/api/promotions/${promoId}`).then(r => r.data)
    promo.value = p
    const rep = await api.get(`/api/promotions/${promoId}/report`).then(r => r.data).catch(() => null)
    reportMeta.value = { count: Number(rep?.count || 0), loaded_at: rep?.loaded_at || null }
    await analyze()
    // кэш номенклатуры пуст — забираем товары из WB (один запрос)
    if (!rows.value.length && p?.promo_type !== 'auto') {
      await reloadProducts()
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Не удалось загрузить акцию'
  } finally {
    loading.value = false
  }
}

/** Перезабрать список товаров из WB (кнопка ↻ в карточке акции). */
const reloadProducts = async () => {
  if (!appliedFilters.value.promo) return
  refreshing.value = true
  error.value = ''
  try {
    await api.get(`/api/promotions/${appliedFilters.value.promo}/products`, {
      params: { refresh: 1, auto_discount: appliedFilters.value.auto_discount },
    }).then(r => r.data)
    await analyze()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Не удалось обновить список товаров'
  } finally {
    refreshing.value = false
  }
}

/** Применение формы: поля → запрос + запись в URL + запоминание настроек. */
const onApply = () => {
  // даты/акция/сортировка — из filters, пороги и тумблеры — из панели (params)
  appliedFilters.value = withParams({ ...filters.value }, params.value)
  syncRoute()
  persistPrefs()
  loadPromo(appliedFilters.value.promo)
}

/** Сброс: к дефолтам, сохранённые настройки тоже чистим. */
const onReset = () => {
  const d = defaultRange(30)
  clearPromoPrefs()
  const fresh = fromRoute({})
  filters.value = {
    ...fresh,
    date_from: d.date_from,
    date_to: d.date_to,
  }
  onApply()
}

/** Галочка — финальный выбор пользователя; сохраняем в базу. */
const onToggle = async (r: PromoAnalysisRow) => {
  r.selected = !r.selected
  r.manual = true
  try {
    await api.post(`/api/promotions/${appliedFilters.value.promo}/decisions`, {
      items: rows.value.map(x => ({ nm_id: x.nm_id, selected: x.selected })),
    })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Не удалось сохранить пометки'
  }
}

/** Передать отмеченные товары в акцию (регулярные — init upload; автоакции —
    цены и скидки через upload/task с проверкой карантина). */
const onUpload = async () => {
  if (!appliedFilters.value.promo) return
  const list = selectedRows.value
  if (!list.length) {
    error.value = 'Не отмечено ни одного товара'
    return
  }
  if (isAuto.value) {
    await preparePricesSend(list)
    return
  }
  error.value = ''
  try {
    const res = await promotionsApi.upload(Number(appliedFilters.value.promo), list.map(r => r.nm_id))
    await analyze()
    window.alert(`Передано в акцию: ${res.uploaded}`)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Не удалось отправить в WB'
  }
}

/* ------------- загрузка цен и скидок (автоакции) ------------- */

const pricesDialog = ref(false)
const pricesPrep = ref<any>(null)
const sendItems = ref<PromoAnalysisRow[]>([])
const uploading = ref(false)

/** Приём: подготовка отправки — если есть риски карантина, спрашиваем. */
const preparePricesSend = async (list: PromoAnalysisRow[]) => {
  error.value = ''
  try {
    pricesPrep.value = await promotionsApi.preparePrices(Number(appliedFilters.value.promo), list)
    sendItems.value = list
    pricesDialog.value = true
  } catch (e: any) {
    error.value = 'Подготовка цен: ' + (e?.response?.data?.detail || e?.message || 'не удалось проверить текущие цены')
  }
}

const riskyItems = computed(() => {
  const prep = pricesPrep.value as any
  return (prep?.risky || []) as any[]
})

const sendPrices = async (withRisky: boolean) => {
  if (!appliedFilters.value.promo) return
  uploading.value = true
  error.value = ''
  try {
    const res = await promotionsApi.uploadPrices(
      Number(appliedFilters.value.promo), sendItems.value, withRisky)
    pricesDialog.value = false
    let msg = `Отправлено в WB: ${res.sent}`
    if (res.skipped_risky) msg += ` (без рискованных: ${res.skipped_risky} — они останутся по старой цене)`
    if (res.tasks.length) msg += `. Задача WB: ${res.tasks.map(t => t.id ?? '—').join(', ')}`
    msg += ' — статус загрузки и карантин проверьте кнопкой «Проверить карантин»'
    window.alert(msg)
  } catch (e: any) {
    error.value = 'Загрузка цен в WB: ' + (e?.response?.data?.detail || e?.message || 'не удалось отправить')
    pricesDialog.value = false
  } finally {
    uploading.value = false
  }
}

/** Кто реально в карантине (после загрузки — WB /quarantine/goods). */
const onQuarantineCheck = async () => {
  error.value = ''
  try {
    const res = await promotionsApi.quarantine()
    const rows = res.rows || []
    if (!rows.length) {
      window.alert('Карантин цен WB: пусто — ни один товар не в карантине')
      return
    }
    window.alert(`В карантине WB: ${rows.length}\n\n` + rows.slice(0, 20).map(
      (x: any) => `${x.nm_id}: было ${fmtRub(x.old_price * (1 - x.old_discount / 100))} → стало ${fmtRub(x.new_price * (1 - x.new_discount / 100))}`
    ).join('\n') + (rows.length > 20 ? `\n… и ещё ${rows.length - 20}` : ''))
  } catch (e: any) {
    error.value = 'Карантин WB: ' + (e?.response?.data?.detail || e?.message || 'не удалось получить список')
  }
}

const fmtRub = (v: number | null | undefined) =>
  v == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(v)

const stamp = () => new Date().toISOString().slice(0, 10)

/** Кнопка «Excel» в шапке таблицы — выгружаем всю таблицу (её содержимое). */
const doExport = async (list?: PromoAnalysisRow[]) => {
  const src = list && list.length ? list : rows.value
  await exportPromoRows(src, `akcii_podbor_${stamp()}.xlsx`)
}

// Пересчёт при смене порогов (с задержкой — чтобы не дёргать БД на каждый ввод).
let timer: any = null
watch(params, () => {
  if (!appliedFilters.value.promo) return
  clearTimeout(timer)
  timer = setTimeout(() => {
    // пороги из панели — в appliedFilters; даты и прочее не трогаем
    appliedFilters.value = withParams({ ...appliedFilters.value }, params.value)
    syncRoute()
    persistPrefs()
    analyze()
  }, 600)
}, { deep: true })

watch(() => route.query, (nq) => {
  if (syncing) return
  const next = fromRoute(nq)
  if (JSON.stringify(next) === JSON.stringify(appliedFilters.value)) return
  filters.value = { ...next }
  appliedFilters.value = { ...next }
  params.value = { ...next }
  loadPromo(next.promo)
})

loadCalendar()
if (appliedFilters.value.promo) loadPromo(appliedFilters.value.promo)
</script>
