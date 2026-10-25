<script setup lang="ts">
import '@/assets/css/pages/page-seo-watch.css'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbDateInput from '@/components/common/WbDateInput.vue'
import WbCardSelect from '@/components/common/WbCardSelect.vue'
import WbWorkspaceTabs from '@/components/common/WbWorkspaceTabs.vue'
import { WORKSPACE_TABS, type WorkspaceTab } from '@/components/common/workspaceTabs'
import CompetitorDetailsModal from '@/components/competitors/CompetitorDetailsModal.vue'
import OurCardModal from '@/components/positions/OurCardModal.vue'
import WbSearchCard from '@/components/positions/WbSearchCard.vue'
import type { PositionsItem } from '@/api/competitorsPositions'
import {
  seoWatchApi,
  type WatchMatrix,
  type WatchMatrixRow,
  type WatchPhraseDay,
  type WatchPhraseDetail,
  type WatchPhraseItem,
  type WatchSummary,
} from '@/api/seoWatch'

/** Табы рабочего места — общий список (FBS-модель, §Шаг 4 плана 2026-10-23). */
const tabs: WorkspaceTab[] = WORKSPACE_TABS

const PRESETS = [
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
]

const iso = (d: Date) => {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
const today = () => iso(new Date())
const daysAgo = (n: number) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return iso(d)
}

const dateFrom = ref(daysAgo(29))
const dateTo = ref(today())
const activePreset = ref('30')

/* ---------- Фильтры панели: карточка / запросы / ранг фраз ---------- */

/** ПОИСК нашей карточки (WbCardSelect): nmID/vendorCode/title, '' = все наши. */
const fCardNm = ref('')
/** ТОП-N запросов карточки; 0 = «как сейчас» (порог компании top_phrases_n). */
const fQueries = ref(0)
const QUERIES_OPTIONS = [
  { v: 0, label: 'как сейчас (ТОП-20 к. × 5 ф.)' },
  { v: 10, label: 'ТОП-10 на карточку' },
  { v: 20, label: 'ТОП-20 на карточку' },
]
/** Ранг фраз: по заказам (как раньше) или по частотности (метрика analytics). */
const fRank = ref<'orders' | 'freq'>('orders')
const RANK_OPTIONS = [
  { v: 'orders', label: 'по заказам' },
  { v: 'freq', label: 'по частотности' },
]

/** Применённый срез — меняется только по «Применить», селекты до того свободны. */
const apCardNm = ref(0)
const apQueries = ref(0)
const apRank = ref<'orders' | 'freq'>('orders')

/** Параметры фильтров для API (п-less: нули/дефолты не шлём). */
const filterParams = computed(() => {
  const p: { card_nm?: number; rank?: string; queries?: number } = {}
  if (apCardNm.value) {
    p.card_nm = apCardNm.value
    if (apQueries.value) p.queries = apQueries.value
  }
  if (apRank.value !== 'orders') p.rank = apRank.value
  return p
})

/** Активный срез фильтра — серой подписью под кнопками (как на мокапе). */
const activeFilterNote = computed(() => {
  const f = matrix.value?.filter
  if (!f || (!f.card_nm && f.rank === 'orders')) return ''
  const parts: string[] = []
  if (f.card_nm) {
    parts.push(`карточка ${f.card_nm}`)
    parts.push(`ТОП-${f.queries_n || 0} запросов`)
  }
  parts.push(f.rank === 'freq' ? 'ранг «по частотности»' : 'ранг «по заказам»')
  return `фильтр: ${parts.join(' · ')}`
})

function applyFilters() {
  apCardNm.value = Math.max(0, parseInt(fCardNm.value, 10) || 0)
  apQueries.value = apCardNm.value ? fQueries.value : 0
  apRank.value = fRank.value
  load()
  syncUrl()
}

/* ---------- URL ↔ фильтры: F5 и «поделиться» восстанавливают срез ---------- */

const route = useRoute()
const router = useRouter()

function isoOk(v: unknown): string {
  const s = String(v || '')
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : ''
}

/** Разбор query на старте: даты + применённый срез фильтров (до первой загрузки). */
function initFromUrl() {
  const q = route.query || {}
  const df = isoOk(q.date_from)
  const dt = isoOk(q.date_to)
  if (df) dateFrom.value = df
  if (dt) dateTo.value = dt
  // подсветка пресета — только если даты URL совпали с одним из них
  activePreset.value = ''
  for (const p of PRESETS) {
    if (dateFrom.value === daysAgo(Number(p.id) - 1) && dateTo.value === today()) {
      activePreset.value = p.id
      break
    }
  }
  const cn = Math.max(0, parseInt(String(q.card_nm || ''), 10) || 0)
  if (cn) {
    fCardNm.value = String(cn)
    apCardNm.value = cn
    const qn = parseInt(String(q.queries || ''), 10) || 0
    fQueries.value = qn
    apQueries.value = qn
  }
  if (String(q.rank || '') === 'freq') {
    fRank.value = 'freq'
    apRank.value = 'freq'
  }
}

/** Отражение применённого среза в query: даты пишем всегда — ссылка должна
 *  показывать тот же срез и завтра (у адресата свои «сегодня»). */
function syncUrl() {
  const q: Record<string, string> = {
    date_from: dateFrom.value,
    date_to: dateTo.value,
  }
  if (apCardNm.value) q.card_nm = String(apCardNm.value)
  if (apCardNm.value && apQueries.value) q.queries = String(apQueries.value)
  if (apRank.value !== 'orders') q.rank = apRank.value
  router.replace({ path: '/seo-watch', query: q }).catch(() => {})
}

const summary = ref<WatchSummary | null>(null)
const matrix = ref<WatchMatrix | null>(null)
const loading = ref(false)
const error = ref('')

const expanded = ref<string>('')
const detail = ref<WatchPhraseDetail | null>(null)
const detailLoading = ref(false)
/** Сколько карточек показано по каждому срезу (ключ = дата+время захода). */
const shownByDay = ref<Record<string, number>>({})
const SLICE_STEP = 10

/** Показываем только свежий заход (остальные — в отчёте «Поисковые запросы»). */
const visibleDays = computed(() => (detail.value?.days || []).slice(0, 1))

function sliceKey(day: { date: string; time?: string }): string {
  return `${day.date} ${day.time || ''}`
}
function sliceLimit(day: { date: string; time?: string }): number {
  return shownByDay.value[sliceKey(day)] || SLICE_STEP
}
function showMore(day: { date: string; time?: string }) {
  const k = sliceKey(day)
  shownByDay.value = { ...shownByDay.value, [k]: sliceLimit(day) + SLICE_STEP }
}

const selected = ref<string[]>([])
const actionBusy = ref('')
const actionNotice = ref('')

const competitorNm = ref<number | null>(null)
const ourCardNm = ref<number | null>(null)

const items = computed<WatchMatrixRow[]>(() => matrix.value?.items || [])
const hasRows = computed(() => items.value.length > 0)
const eventRows = computed(() => items.value.filter((i) => i.new_cnt || i.price_moves_cnt))

/** Подпись KPI «Фраз на наблюдении»: в карточном фильтре — запросы карточки. */
const phrasesKpiNote = computed(() => {
  const f = matrix.value?.filter
  if (f?.card_nm) return `ТОП-${f.queries_n} запросов карточки`
  return `ТОП-${summary.value?.settings?.top_phrases_n} на карточку`
})

/** Формат «1 234» для колонки «Запросов» (аналитика /wb-search/analytics). */
function fmtCnt(v: number | null | undefined): string {
  if (v == null) return '—'
  return new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)))
}

/** Тайминги последнего расчёта матрицы: «4,3 с (slices 3,9 с, counts 0,3 с)». */
const timingsNote = computed(() => {
  const t = matrix.value?.timings
  if (!t || !Object.keys(t).length) return ''
  const total = t.total ?? Object.values(t).reduce((a, b) => a + b, 0)
  const top = Object.entries(t)
    .filter(([k]) => k !== 'total')
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([k, v]) => `${k} ${v.toFixed(1)} с`)
    .join(', ')
  return `${total.toFixed(1)} с${top ? ` (${top})` : ''}`
})

function applyPreset(id: string) {
  activePreset.value = id
  dateFrom.value = daysAgo(Number(id) - 1)
  dateTo.value = today()
  load()
  syncUrl()
}

function resetFilters() {
  activePreset.value = '30'
  dateFrom.value = daysAgo(29)
  dateTo.value = today()
  fCardNm.value = ''
  fQueries.value = 0
  fRank.value = 'orders'
  apCardNm.value = 0
  apQueries.value = 0
  apRank.value = 'orders'
  selected.value = []
  load()
  syncUrl()
}

function wbUrl(nm: number): string {
  return `https://www.wildberries.ru/catalog/${nm}/detail.aspx`
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null || v === '') return '—'
  return `${new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)))} ₽`
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${Number(v).toFixed(1).replace('.', ',')}%`
}

/** Метка захода «20261022_131023» → «22.10.2026 13:10».
 * Псевдо-метка легаси (…_000000) — только дата: время того сбора неизвестно. */
function sliceLabel(row: WatchMatrixRow): string {
  const stamp = row.last_stamp || ''
  if (stamp.length >= 15 && stamp[8] === '_') {
    const dt = `${stamp.slice(6, 8)}.${stamp.slice(4, 6)}.${stamp.slice(0, 4)}`
    const tm = `${stamp.slice(9, 11)}:${stamp.slice(11, 13)}`
    return tm === '00:00' ? dt : `${dt} ${tm}`
  }
  return row.last_at ? row.last_at.split('-').reverse().join('.') : ''
}

function collectedTitle(row: WatchMatrixRow): string {
  const lab = sliceLabel(row)
  if (!lab) return 'Сбора выдачи по фразе ещё не было'
  const age = row.days_old != null ? `, ${row.days_old} дн. назад` : ''
  return `Последний заход в поиск WB: ${lab}${age}`
}

/* ---------- Цена vs ТОП-40 ---------- */

/** Тон бейджа: насколько наша цена дороже медианы конкурентов в ТОП-40, %.
 * Зелёный — дешевле более чем на 5%, серый — от −5% до 10%, дальше
 * оранжевый / пастельный красный / красный по нарастанию перевеса. */
function priceTone(delta: number | null | undefined): string {
  if (delta == null) return 'gray'
  if (delta < -5) return 'green'
  if (delta <= 10) return 'gray'
  if (delta <= 50) return 'orange'
  if (delta <= 100) return 'pale'
  return 'red'
}

function priceDeltaLabel(delta: number | null | undefined): string {
  if (delta == null) return '—'
  return `${delta > 0 ? '+' : ''}${delta.toFixed(1).replace('.', ',')}%`
}

/** Карточка для показа — лидер по позиции среди наших в ТОП-40 (обсудили 2026-10-24 п.3). */
function priceLeader(row: WatchMatrixRow): WatchOurPosition | null {
  const ours = row.our_positions || []
  return ours.find((o) => o.position != null) ?? ours[0] ?? null
}

const PRICE_COL_TITLE =
  'Наша цена против медианы конкурентов в ТОП-40 того же захода. ' +
  'Зелёный: дешевле медианы на 5%+, серый: от −5% до +10%, ' +
  'оранжевый: +10–50%, светло-красный: +50–100%, красный: дороже медианы более чем на 100%'

function priceTitle(row: WatchMatrixRow, o: WatchOurPosition | null): string {
  if (!o) return 'Наших карточек в первых 40 позициях нет'
  const parts = [`Наша ${fmtMoney(o.price)}`]
  if (row.price_median != null) parts.push(`медиана ТОП-40 ${fmtMoney(row.price_median)} (${row.price_cnt ?? 0} цен конкурентов)`)
  if (o.cheaper_cnt != null) parts.push(`дешевле нас ${o.cheaper_cnt} из ${row.price_cnt ?? 0}`)
  if (row.price_min != null) parts.push(`минимум у конкурентов ${fmtMoney(row.price_min)}`)
  return parts.join(' · ')
}

/** Наш товар из выдачи → карточка товара на WB (клик по позиции). */
function openCard(card: PositionsItem) {
  if (card.is_ours) ourCardNm.value = card.nm_id
  else competitorNm.value = card.nm_id
}

/** Строки среза → формат карточки товара (общий WbSearchCard). */
function asPositionsItem(c: WatchPhraseItem): PositionsItem {
  return {
    position: c.position,
    // position_api — номер в JSON-каталоге WB (другой, чем позиция в списке).
    // Здесь показываем DOM-позицию (что видит покупатель) — как в строке матрицы.
    position_api: null,
    nm_id: c.nm_id,
    title: c.title,
    brand: c.brand,
    seller: c.seller,
    price: c.price,
    old_price: c.old_price ?? null,
    price_api: c.price_api ?? null,
    old_price_api: null,
    rating: c.rating ?? null,
    review_rating: c.review_rating ?? null,
    feedbacks: c.feedbacks ?? null,
    reviews: c.reviews ?? null,
    badges: c.badges || [],
    promo_id: null,
    is_adv: 0,
    image_url: c.image_url,
    is_ours: !!c.is_ours,
    source_nm_id: c.source_nm_id,
    source_title: '',
    source_vendor: '',
    created_by: null,
    username: '',
    at: '',
  }
}

const REQUEUE_BADGE: Record<string, string> = {
  pending: 'bg-secondary',
  processing: 'bg-info text-dark',
  done: 'bg-success',
  error: 'bg-danger',
}
const REQUEUE_LABEL: Record<string, string> = {
  pending: 'в очереди',
  processing: 'собираем',
  done: 'готово',
  error: 'ошибка',
}
function requeueBadge(s: string): string {
  return REQUEUE_BADGE[s] || ''
}
function requeueLabel(s: string): string {
  return REQUEUE_LABEL[s] || s
}

/** КПЭ сводки — локально из матрицы: `/summary` на бекенде считал ровно то же
 * из тех же items, а параллельные Promise.all кэшу не подчинялись и считали
 * матрицу дважды (watch_service.py:524). Один запрос = половина нагрузки. */
function summaryFromMatrix(m: WatchMatrix): WatchSummary {
  const rows = m.items || []
  const fresh = rows.filter((i) => i.fresh)
  const positions = rows
    .map((i) => i.best_position)
    .filter((p): p is number => p != null && p > 0)
  const top3 = positions.filter((p) => p <= 3).length
  const top10 = positions.filter((p) => p <= 10).length
  return {
    settings: m.settings,
    filter: m.filter,
    date_from: m.date_from,
    date_to: m.date_to,
    cards_cnt: m.cards_cnt,
    phrases_cnt: rows.length,
    phrases_total: m.phrases_total,
    fresh_cnt: fresh.length,
    stale_cnt: rows.length - fresh.length,
    with_position_cnt: positions.length,
    top3_cnt: top3,
    top10_cnt: top10,
    top3_pct: rows.length ? Math.round((top3 / rows.length) * 100) : 0,
    top10_pct: rows.length ? Math.round((top10 / rows.length) * 100) : 0,
    avg_position: positions.length
      ? Math.round((positions.reduce((a, b) => a + b, 0) / positions.length) * 10) / 10
      : null,
    new_cnt: rows.reduce((a, i) => a + (i.new_cnt || 0), 0),
    price_moves_cnt: rows.reduce((a, i) => a + (i.price_moves_cnt || 0), 0),
  }
}

async function load() {
  loading.value = true
  error.value = ''
  actionNotice.value = ''
  try {
    const params = { date_from: dateFrom.value, date_to: dateTo.value, ...filterParams.value }
    const m = await seoWatchApi.matrix(params)
    matrix.value = m
    summary.value = summaryFromMatrix(m)
    if (expanded.value && !m.items.some((i) => i.phrase === expanded.value)) {
      expanded.value = ''
      detail.value = null
    }
    selected.value = selected.value.filter((p) => m.items.some((i) => i.phrase === p))
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

async function toggleExpand(row: WatchMatrixRow) {
  if (expanded.value === row.phrase) {
    expanded.value = ''
    detail.value = null
    return
  }
  expanded.value = row.phrase
  detail.value = null
  onlyNew.value = false
  onlyPriceChanged.value = false
  shownByDay.value = {}
  detailLoading.value = true
  try {
    detail.value = await seoWatchApi.phrase({
      phrase: row.phrase,
      date_from: dateFrom.value,
      date_to: dateTo.value,
    })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки срезов'
  } finally {
    detailLoading.value = false
  }
}

/** Фильтры выдачи: только новые карточки / только изменившиеся цены. */
const onlyNew = ref(false)
const onlyPriceChanged = ref(false)

/**
 * Карточки среза после фильтров (чекбоксы «новые»/«изменилась цена»).
 * Флаги — из ответа /phrase (бэкенд считает их по тому же заходу, что открыт).
 */
function visibleItems(day: WatchPhraseDay): WatchPhraseItem[] {
  const items = day.items || []
  if (!onlyNew.value && !onlyPriceChanged.value) return items
  return items.filter((c) => {
    if (onlyNew.value && onlyPriceChanged.value) return !!c.is_new || !!c.price_changed
    return onlyNew.value ? !!c.is_new : !!c.price_changed
  })
}

function isSelected(phrase: string): boolean {
  return selected.value.includes(phrase)
}
const allSelected = computed(() => hasRows.value && items.value.every((i) => isSelected(i.phrase)))
/** Чекбокс «выбрать все» (v-model с геттером/сеттером). */
const allChecked = computed({
  get: () => allSelected.value,
  set: (v: boolean) => {
    selected.value = v ? items.value.map((i) => i.phrase) : []
  },
})

/** Фразы с устаревшим сбором выдачи (последний заход старше порога компании). */
const stalePhrases = computed(() => items.value.filter((i) => !i.fresh).map((i) => i.phrase))

/** Глубина захода для «Обновить устаревшие»: ТОП-10/20/40 позиций выдачи. */
const cardTop = ref(20)
const CARD_TOP_OPTIONS = [
  { v: 10, label: 'ТОП-10' },
  { v: 20, label: 'ТОП-20' },
  { v: 40, label: 'ТОП-40' },
]

/**
 * Целевые фразы для действий: отмеченные в матрице, иначе — все фразы набора.
 * Так же считает и бэкенд (пустой список фраз → весь watch set), поэтому
 * цифра в кнопке совпадает с тем, что реально соберётся.
 */
const targetPhrases = computed<Set<string>>(
  () =>
    selected.value.length
      ? new Set(selected.value)
      : new Set(items.value.map((i) => i.phrase)),
)

/** Пул «Собрать новые и изменённые»: уникальные карточки событий матрицы
 * (new_items + price_moves), ещё не собранные свежее события. Карточки с
 * fresh=true бэкенд пропускает — их в счётчик не берём. */
const newPoolCnt = computed(() => {
  const ids = new Set<number>()
  for (const row of items.value) {
    for (const n of row.new_items || []) {
      if (!n.fresh) ids.add(n.nm_id)
    }
    for (const mv of row.price_moves || []) {
      if (!mv.fresh) ids.add(mv.nm_id)
    }
  }
  return ids.size
})

/**
 * Уникальные карточки окна ТОП-`depth` последнего захода по целевым фразам со
 * статусом контента из `kinds` (0 актуальный / 1 устаревший / 2 без описания).
 * Данные — `row.pool` из матрицы: одна карточка в ТОП-40 нескольких фраз
 * считается здесь один раз, поэтому цифра кнопки ровно совпадает с тем, что
 * бэкенд поставит в очередь (старая «сумма по фразам» с 22 фактических
 * показывала 953).
 */
function poolUnique(depth: number, kinds: number[]): number {
  const ids = new Set<number>()
  for (const row of items.value) {
    if (!targetPhrases.value.has(row.phrase)) continue
    for (const [nm, pos, st] of row.pool || []) {
      if (pos <= depth && kinds.includes(st)) ids.add(nm)
    }
  }
  return ids.size
}

/**
 * Пул «Собрать отсутствующие»: карточки ТОП-40 без описания — контент по ним
 * не собирали ни разу (в т.ч. наши карточки из выдачи).
 */
const missingCardsCnt = computed(() => poolUnique(40, [2]))

/** Пул «Обновить устаревшие»: устаревший или отсутствующий контент на глубине «из:». */
const staleCardsCnt = computed(() => poolUnique(cardTop.value, [1, 2]))

/**
 * Пересборка выдачи: фразы -> `wb_search_phrase_queue` -> расширение
 * («Поисковые фразы» в попапе). Без отметок — все фразы с устаревшим сбором.
 */
async function doRequeue() {
  if (actionBusy.value) return
  const target = selected.value.length ? selected.value : stalePhrases.value
  if (!target.length) return
  actionBusy.value = 'requeue'
  try {
    const r = await seoWatchApi.requeue(target, dateFrom.value, filterParams.value)
    selected.value = []
    await load()
    actionNotice.value = `в очереди на пересборку: ${r.queued}`
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка постановки в очередь'
  } finally {
    actionBusy.value = ''
  }
}

/**
 * Обновление содержимого ТОП-10 карточек выдачи: `wb_enrich_queue`
 * (source='watch') — расширение забирает в режиме «SEO-мониторинг».
 * Целевые фразы: отмеченные, иначе все (бэкенд сам подставит watch set).
 * Пропускаются только карточки, собранные сегодня.
 */
async function doRefresh() {
  if (actionBusy.value) return
  actionBusy.value = 'refresh'
  try {
    const r = await seoWatchApi.refresh(selected.value, 10, dateFrom.value, dateTo.value, filterParams.value)
    const over = r.overflow ? `, сверх лимита не взято: ${r.overflow}` : ''
    const today = r.skipped_today ? `, собрано сегодня — пропущено ${r.skipped_today}` : ''
    selected.value = []
    await load()
    actionNotice.value =
      `в очередь enrich: ${r.assigned} (в пуле ${r.candidates}${today}, пропущено ${r.skipped}${over})`
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка постановки в очередь'
  } finally {
    actionBusy.value = ''
  }
}

/**
 * Сбор карточек SEO-мониторинга в очередь enrich (source='watch') — расширение
 * забирает её отдельным режимом «SEO-мониторинг», отдельно от общей кучи.
 * - `changed` — новые в выдаче и сдвиги цены (по всей матрице);
 * - `stale`   — карточки старше порога компании; если отмечены фразы — только
 *               по ним (как «Пересобрать выдачу»).
 * - `missing` — карточки, у которых описания нет вовсе (контент не собирали).
 */
async function doCollect(mode: 'changed' | 'stale' | 'missing') {
  if (actionBusy.value) return
  actionBusy.value = mode
  try {
    const phrases = mode === 'changed' ? [] : selected.value
    // «Собрать отсутствующие» — окно анализа (ТОП-40), ровно то, что в колонке
    // «А|У|Н»; «Обновить устаревшие» — выбранная глубина «из:».
    const top = mode === 'missing' ? 40 : cardTop.value
    const r = await seoWatchApi.collect(mode, phrases, top, dateFrom.value, dateTo.value, filterParams.value)
    const notice = mode === 'stale'
      ? `в очередь enrich: ${r.assigned} (устаревших ${r.candidates}, пропущено ${r.skipped}, порог ${r.stale_days} дн.)`
      : mode === 'missing'
        ? `в очередь enrich: ${r.assigned} (без описания ${r.candidates}, пропущено ${r.skipped} — описание уже есть)`
        : `в очередь enrich: ${r.assigned} (новых и изменённых ${r.candidates}, пропущено ${r.skipped})`
    selected.value = []
    await load()
    actionNotice.value = notice
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка постановки в очередь'
  } finally {
    actionBusy.value = ''
  }
}

onMounted(() => {
  initFromUrl()
  load()
})
</script>

<template>
  <div class="container-xxl page-seo-watch">
    <div class="wb-workspace-head">
      <h1 class="page-title">SEO-мониторинг</h1>
      <WbWorkspaceTabs active="summary" :tabs="tabs" />
    </div>

    <div class="page-seo-watch__filters">
      <div class="page-seo-watch__presets">
        <button
          v-for="p in PRESETS"
          :key="p.id"
          class="btn btn-sm"
          :class="activePreset === p.id ? 'btn-primary' : 'btn-outline-secondary'"
          @click="applyPreset(p.id)"
        >{{ p.label }}</button>
      </div>
      <div class="row g-2 align-items-end">
        <div class="col-md-2">
          <label class="form-label mb-1 page-seo-watch__label">Дата с</label>
          <WbDateInput v-model="dateFrom" />
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-seo-watch__label">Дата по</label>
          <WbDateInput v-model="dateTo" />
        </div>
        <div class="col-md-8 d-flex gap-3 justify-content-end flex-wrap">
          <div class="page-seo-watch__fcol page-seo-watch__fcol-card">
            <label class="form-label mb-1 page-seo-watch__label">Наша карточка</label>
            <WbCardSelect
              v-model:nm-id="fCardNm"
              placeholder="nmID / артикул / название..."
            />
          </div>
          <div class="page-seo-watch__fcol">
            <label
              class="form-label mb-1 page-seo-watch__label"
              :class="{ 'text-muted': !apCardNm && !fCardNm }"
            >Запросы</label>
            <select
              v-model.number="fQueries"
              class="form-select form-select-sm page-seo-watch__fsel"
              :disabled="!apCardNm && !fCardNm"
              title="Сколько верхних запросов выбранной карточки берём в наблюдение"
            >
              <option v-for="o in QUERIES_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
            </select>
          </div>
        </div>
      </div>
      <div class="row g-2 align-items-end mt-1">
        <div class="col-md-8 d-flex gap-3 align-items-end flex-wrap">
          <div class="page-seo-watch__fcol">
            <label
              class="form-label mb-1 page-seo-watch__label"
              title="Ранг действует на весь набор: им выбираются ТОП-фразы каждой карточки и сортируются строки"
            >Ранг фраз</label>
            <select
              v-model="fRank"
              class="form-select form-select-sm page-seo-watch__fsel"
            >
              <option v-for="o in RANK_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
            </select>
          </div>
          <button class="btn btn-primary" :disabled="loading" @click="applyFilters">Применить</button>
          <button class="btn btn-light" @click="resetFilters">Сбросить</button>
          <span v-if="activeFilterNote" class="page-seo-watch__filter-note">{{ activeFilterNote }}</span>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="loading" class="text-muted page-seo-watch__loading">
      <span class="spinner-border spinner-border-sm"></span> Загрузка…
    </div>

    <template v-if="summary">
      <div class="page-seo-watch__kpi">
        <div class="page-seo-watch__kpi-card">
          <div class="page-seo-watch__kpi-label">Карточек в ТОП</div>
          <div class="page-seo-watch__kpi-value">{{ summary.cards_cnt }}</div>
          <div class="page-seo-watch__kpi-note">
            <template v-if="summary.filter?.card_nm">фильтр карточки: {{ summary.filter.card_nm }}</template>
            <template v-else>по заказам, {{ summary.date_from }} — {{ summary.date_to }}</template>
          </div>
        </div>
        <div class="page-seo-watch__kpi-card">
          <div class="page-seo-watch__kpi-label">Фраз на наблюдении</div>
          <div class="page-seo-watch__kpi-value">{{ summary.phrases_total ?? summary.phrases_cnt }}</div>
          <div class="page-seo-watch__kpi-note">
            <template v-if="(summary.phrases_total ?? summary.phrases_cnt) > summary.phrases_cnt">
              анализируется {{ summary.phrases_cnt }} (лимит компании) · {{ phrasesKpiNote }}
            </template>
            <template v-else>{{ phrasesKpiNote }}</template>
          </div>
        </div>
        <div class="page-seo-watch__kpi-card" :class="{ 'page-seo-watch__kpi-card--warn': summary.stale_cnt > 0 }">
          <div class="page-seo-watch__kpi-label">Сбор выдачи</div>
          <div class="page-seo-watch__kpi-value">{{ summary.fresh_cnt }} / {{ summary.phrases_cnt }}</div>
          <div class="page-seo-watch__kpi-note">протухло: {{ summary.stale_cnt }} (порог {{ summary.settings.stale_days }} дн.)</div>
        </div>
        <div class="page-seo-watch__kpi-card">
          <div class="page-seo-watch__kpi-label">Мы в ТОП-3 / ТОП-10</div>
          <div class="page-seo-watch__kpi-value">{{ summary.top3_pct }}% / {{ summary.top10_pct }}%</div>
          <div class="page-seo-watch__kpi-note">
            ср. позиция: {{ summary.avg_position != null ? summary.avg_position : '—' }}
            (из {{ summary.with_position_cnt }})
          </div>
        </div>
        <div class="page-seo-watch__kpi-card">
          <div class="page-seo-watch__kpi-label">Новых карточек</div>
          <div class="page-seo-watch__kpi-value">{{ summary.new_cnt }}</div>
          <div class="page-seo-watch__kpi-note">последний срез против предыдущего</div>
        </div>
        <div class="page-seo-watch__kpi-card">
          <div class="page-seo-watch__kpi-label">Сдвигов цен</div>
          <div class="page-seo-watch__kpi-value">{{ summary.price_moves_cnt }}</div>
          <div class="page-seo-watch__kpi-note">от {{ summary.settings.price_delta_pct }}%</div>
        </div>
      </div>

      <div class="wb-grid-card page-seo-watch__block page-seo-watch__actions">
        <div class="page-seo-watch__actions-title">Действия</div>
        <div class="page-seo-watch__actions-groups row d-flex flex-nowrap">
          <!-- фразы → пересборка выдачи (расширение «Поисковые фразы») -->
          <div class="page-seo-watch__actions-phrases col-md-4">
            <label class="page-seo-watch__check ms-2">
              <input type="checkbox" v-model="allChecked" />
              <span>выбрать все</span>
            </label>
            <button
              class="btn btn-sm btn-primary"
              :disabled="!!actionBusy || (!selected.length && !stalePhrases.length)"
              :title="selected.length
                ? 'Отправить выбранные фразы в расширение — оно пересоберёт выдачу по ним'
                : 'Отправить в расширение все фразы с устаревшим сбором выдачи'"
              @click="doRequeue"
            >
              <i class="bi bi-arrow-repeat"></i>
              Пересобрать выдачу
              <span class="page-seo-watch__cnt">({{ selected.length || stalePhrases.length }})</span>
            </button>
          </div>
          <!-- карточки: раскладка предопределена grid-областями — всегда 2 строки
               («собрать» над «обновить»), колонки выровнены, счётчики в
               фикс-слоте: ширина кнопок не зависит от цифр, панели нечему
               переверстываться и прыгать при каждом клике -->
          <div class="page-seo-watch__actions-cards col d-block">
            <div class="row">
              <div class="col-md-6">
                
            <button
              class="btn btn-sm btn-outline-primary page-seo-watch__act--stale"
              :disabled="!!actionBusy || !staleCardsCnt"
              :title="`${selected.length
                ? `Карточки с устаревшим или отсутствующим описанием только по отмеченным фразам (${selected.length}), порог компании`
                : 'Карточки с устаревшим или отсутствующим описанием по всем фразам мониторинга, порог компании'}. Глубина захода — «из:» рядом (колонка А|У|Н считает по ТОП-40, кнопка — по своей глубине). В скобках: УНИКАЛЬНЫХ карточек к обновлению — ровно столько встанет в очередь ${staleCardsCnt}`"
              @click="doCollect('stale')"
            >
              <i class="bi bi-archive"></i>
              Обновить устаревшие
              <span class="page-seo-watch__cnt">({{ staleCardsCnt }})</span>
            </button>
            <label
              class="page-seo-watch__depth page-seo-watch__act--depth"
              title="Какие первые позиции последнего захода каждой фразы попадут в пул «Обновить устаревшие». На остальные кнопки не влияет"
            >
              <span class="ms-3">из:</span> 
              <select v-model.number="cardTop" class="form-select form-select-sm">
                <option v-for="o in CARD_TOP_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
              </select>
            </label>


              </div>
              <div class="col-md-6 text-end">
            <button
              class="btn btn-sm btn-outline-primary page-seo-watch__act--refresh"
              :disabled="!!actionBusy || !items.length"
              :title="`ТОП-10 позиций последнего среза ${selected.length
                ? `по отмеченным фразам (${selected.length})`
                : 'по всем фразам мониторинга'} → в очередь enrich (режим «SEO-мониторинг»). Пропускаем только карточки, собранные сегодня; наши карточки тоже обновляем — нужны их бэджи и цены`"
              @click="doRefresh"
            >
              <i class="bi bi-box-arrow-in-down"></i>
              Обновить ТОП-10
            </button>

              </div>

            </div>
            <div class="row">
              <div class="col-md-6">
            <button
              class="btn btn-sm btn-outline-primary page-seo-watch__act--missing"
              :disabled="!!actionBusy || !missingCardsCnt"
              :title="`${selected.length
                ? `Карточки ТОП-40, у которых описания нет вовсе (контент не собирали ни разу), только по отмеченным фразам (${selected.length})`
                : 'Карточки ТОП-40, у которых описания нет вовсе (контент не собирали ни разу), по всем фразам мониторинга'}. В скобках: УНИКАЛЬНЫХ карточек к сбору — ровно столько встанет в очередь (дубль в нескольких фразах считается один раз). Описание есть, но старое — для них «Обновить устаревшие»`"
              @click="doCollect('missing')"
            >
              <i class="bi bi-inboxes"></i>
              Собрать отсутствующие
              <span class="page-seo-watch__cnt">({{ missingCardsCnt }})</span>
            </button>

              </div>
              <div class="col-md-6 text-end"> 
            <button
              class="btn btn-sm btn-outline-primary page-seo-watch__act--changed"
              :disabled="!!actionBusy || !newPoolCnt"
              :title="`Карточки из событий «новые в выдаче» и «сдвиг цены» по всем фразам матрицы → в очередь enrich (расширение соберёт). Контент, собранный не раньше старого захода фразы, уже отражает событие — такие карточки пропускаем (повторный клик не ставит их в очередь заново). В скобках: карточек к сбору сейчас ${newPoolCnt}`"
              @click="doCollect('changed')"
            >
              <i class="bi bi-stars"></i>
              Собрать новые и изм.
              <span class="page-seo-watch__cnt">({{ newPoolCnt }})</span>
            </button>
              </div>
            </div>



          </div>
        </div>
        <div class="page-seo-watch__actions-foot"> 
          <span v-if="actionNotice" class="page-seo-watch__notice">{{ actionNotice }}</span>
        </div>
      </div>

      <div class="wb-grid-card page-seo-watch__block">
        <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header wb-card-header--sm page-seo-watch__matrix-head">
          <span>Матрица мониторинга</span>
          <span class="page-seo-watch__head-actions">
            <span v-if="timingsNote" class="page-seo-watch__head-note">расчёт: {{ timingsNote }}</span>
            <span class="page-seo-watch__head-note">отмечено: {{ selected.length }}</span>
          </span>
        </div>
        <div v-if="!hasRows" class="alert alert-info m-3 mb-0">
          <template v-if="matrix?.filter?.card_nm">
            У карточки {{ matrix.filter.card_nm }} нет запросов в Search Reports
            за {{ summary.date_from }} — {{ summary.date_to }} (или их меньше ТОП-{{ matrix.filter.queries_n }}).
            Проверьте, что Search Reports загружены за период.
          </template>
          <template v-else>
            Пока нет фраз в мониторинге: проверьте, что есть заказы и загружены Search Reports.
          </template>
        </div>
        <div v-else class="wb-table-wrap">
          <table class="wb-admin-table page-seo-watch__grid">
            <thead>
              <tr>
                <th class="page-seo-watch__col-check">
                  <input type="checkbox" v-model="allChecked" />
                </th>
                <th class="page-seo-watch__col-phrase">Фраза</th>
                <th class="text-center" title="Заказы по фразе у наших карточек ТОП (Search Reports)">Заказы</th>
                <th
                  class="text-center"
                  title="«Запросов» за период — как /wb-search/analytics: MAX(week_frequency) по nmID за день → AVG по дням присутствия × дней периода"
                >Запросов</th>
                <th class="text-center page-seo-watch__col-ours" title="Наши позиции в выдаче (все наши карточки)" style="min-width: 300px;">Наши позиции</th>
                <th class="text-center" :title="PRICE_COL_TITLE">Цена vs ТОП-40</th>
                <th class="text-center" title="Лучшая наша позиция в выдаче">Лучшая</th>
                <th class="text-center" title="Наших карточек в первых 40 позициях выдачи">В ТОП-40</th> 
                <th
                  class="text-center page-seo-watch__col-cards"
                  :title="`А|У|Н — карточек окна позиций 1..40 последнего захода: Актуальных / Устаревших / Нет описания.\nА — описание собрано и полный сбор не старше ${summary?.settings.card_stale_days ?? 30} дн. (порог — в настройках компании).\nУ — описание есть, но старше порога.\nН — описания нет вовсе (контент не собирали ни разу; лёгкая строка из наблюдения выдачи описанием не считается).\nЭто окно ПОЗИЦИЙ, а не 40 карточек: если фраза собрана по нескольким нашим карточкам, разные конкуренты занимают одни и те же позиции — карточек может быть и 41.\n«Обновить устаревшие» берёт У+Н на своей глубине («из:»), «Собрать отсутствующие» — только Н по ТОП-40; в скобках кнопок — уникальные карточки, одна в нескольких фразах считается один раз`"
                >А|У|Н</th>
                <th class="text-center" title="Свежесть сбора выдачи">Сбор</th>
                <th class="text-center" title="Новые карточки в выдаче">Новые</th>
                <th class="text-center" title="Изменения цен конкурентов между заходами">Цены</th>
                <th class="text-center">Очередь</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="row in items" :key="row.phrase">
                <tr
                  class="page-seo-watch__row"
                  :class="{
                    'page-seo-watch__row--stale': !row.fresh,
                    'page-seo-watch__row--open': expanded === row.phrase,
                  }"
                >
                  <td>
                    <input type="checkbox" v-model="selected" :value="row.phrase" @click.stop />
                  </td>
                  <td class="page-seo-watch__col-phrase">
                    <span class="page-seo-watch__phrase" :title="row.phrase">{{ row.phrase }}</span>
                    <div class="page-seo-watch__note page-seo-watch__cards-line">
                      <span>наши карточки: {{ row.cards.map((c) => c.nm_id).join(', ') || '—' }}</span>
                      <span
                        v-if="sliceLabel(row)"
                        class="page-seo-watch__collected"
                        :title="collectedTitle(row)"
                      >{{ sliceLabel(row) }}</span>
                    </div>
                  </td>
                  <td class="text-center">{{ row.orders_max }}</td>
                  <td class="text-center page-seo-watch__col-freq" :title="`Запросов за период (метрика /wb-search/analytics)${row.freq ? '' : ' — нет данных частотности'}`">{{ fmtCnt(row.freq) }}</td>
                  <td class="text-center page-seo-watch__col-ours">
                    <span v-if="row.our_positions.length" class="page-seo-watch__ours">
                      <button
                        v-for="o in row.our_positions"
                        :key="o.nm_id"
                        class="btn btn-sm btn-link p-0 page-seo-watch__ours-pos"
                        :title="`ID: ${o.nm_id} Арт: ${o.vendor_code || '—'}`"
                        @click.stop="ourCardNm = o.nm_id"
                      >{{ o.position ?? '—' }}</button>
                    </span>
                    <span v-else class="page-seo-watch__note" title="Наших карточек в первых 40 позициях выдачи нет">нет в ТОП-40</span>
                  </td>
                  <td class="text-center">
                    <template v-if="priceLeader(row)">
                      <div
                        class="page-seo-watch__price-val"
                        :title="priceTitle(row, priceLeader(row))"
                      >{{ fmtMoney(priceLeader(row)!.price) }}</div>
                      <div
                        v-if="priceLeader(row)!.price_delta_pct != null"
                        class="page-seo-watch__price-badge"
                        :class="`page-seo-watch__price--${priceTone(priceLeader(row)!.price_delta_pct)}`"
                        :title="priceTitle(row, priceLeader(row))"
                      >{{ priceDeltaLabel(priceLeader(row)!.price_delta_pct) }}</div>
                      <div
                        v-if="priceLeader(row)!.cheaper_cnt != null && row.price_cnt"
                        class="page-seo-watch__note"
                        :title="priceTitle(row, priceLeader(row))"
                      >{{ priceLeader(row)!.cheaper_cnt }}/{{ row.price_cnt }}</div>
                    </template>
                    <span v-else class="page-seo-watch__note" :title="priceTitle(row, null)">—</span>
                  </td>
                  <td class="text-center">{{ row.best_position ?? '—' }}</td>
                  <td class="text-center">{{ row.top_ours_cnt ?? row.ours_cnt }}</td>
                  <td class="text-center page-seo-watch__col-cards">
                    <span
                      v-if="row.last_stamp"
                      class="page-seo-watch__cards-state"
                      :class="{ 'page-seo-watch__cards-state--warn': (row.cards_stale ?? 0) > 0, 'page-seo-watch__cards-state--missing': (row.cards_missing ?? 0) > 0 }"
                      :title="`${row.cards_fresh ?? 0} актуальных / ${row.cards_stale ?? 0} устаревших / ${row.cards_missing ?? 0} без описания — из ${row.cards_cnt ?? '—'} карточек ТОП-40.\nУстаревшая — описание есть, но полный сбор старше ${summary?.settings.card_stale_days ?? 30} дн. (порог компании)`"
                    >{{ row.cards_fresh ?? 0 }} / {{ row.cards_stale ?? 0 }} / {{ row.cards_missing ?? 0 }}</span>
                    <span v-else class="page-seo-watch__note" title="Сборов выдачи по фразе не было">—</span>
                  </td>
                  <td class="text-center">
                    <span
                      class="badge"
                      :class="row.fresh ? 'bg-success' : 'bg-danger'"
                      :title="row.last_at ? `последний сбор ${row.last_at}` : 'сборов не было'"
                    >{{ row.fresh ? `${row.days_old} дн.` : `протухло: ${row.days_old ?? '—'}` }}</span>
                  </td>
                  <td class="text-center">
                    <span v-if="row.new_cnt" class="badge bg-info text-dark">{{ row.new_cnt }}</span>
                    <span v-else class="page-seo-watch__note">—</span>
                  </td>
                  <td class="text-center">
                    <span v-if="row.price_moves_cnt" class="badge bg-warning text-dark">{{ row.price_moves_cnt }}</span>
                    <span v-else class="page-seo-watch__note">—</span>
                  </td>
                  <td class="text-center">
                    <span
                      v-if="row.requeue_status"
                      class="badge"
                      :class="requeueBadge(row.requeue_status)"
                      :title="row.requeue_at ? 'обновлено: ' + row.requeue_at : ''"
                    >{{ requeueLabel(row.requeue_status) }}</span>
                    <span v-else class="page-seo-watch__note">—</span>
                  </td>
                  <td class="page-seo-watch__chev">
                    <button class="btn btn-sm btn-link p-0" @click="toggleExpand(row)">
                      <i class="bi" :class="expanded === row.phrase ? 'bi-chevron-down' : 'bi-chevron-right'"></i>
                    </button>
                  </td>
                </tr>
                <tr v-if="expanded === row.phrase" class="page-seo-watch__detail-row">
                  <td colspan="14">
                    <div v-if="detailLoading" class="text-muted p-2">
                      <span class="spinner-border spinner-border-sm"></span> Загрузка срезов…
                    </div>
                    <div v-else-if="detail && detail.days.length" class="page-seo-watch__detail">
                      <div v-for="day in visibleDays" :key="day.date + (day.time || '')" class="page-seo-watch__slice">
                        <div class="page-seo-watch__slice-head">
                          <span class="page-seo-watch__slice-day">{{ day.date }}</span>
                          <span v-if="day.time" class="page-seo-watch__slice-time">{{ day.time }}</span>
                          <span class="page-seo-watch__note">показано {{ visibleItems(day).length }} из {{ day.items.length }}</span>
                          <span class="page-seo-watch__detail-filters">
                            <label class="page-seo-watch__check">
                              <input type="checkbox" v-model="onlyPriceChanged" />
                              <span>изменилась цена</span>
                            </label>
                            <label class="page-seo-watch__check">
                              <input type="checkbox" v-model="onlyNew" />
                              <span>новые карточки</span>
                            </label>
                          </span>
                        </div>
                        <div class="page-seo-watch__cards">
                          <WbSearchCard
                            v-for="c in visibleItems(day).slice(0, sliceLimit(day))"
                            :key="c.nm_id"
                            :card="asPositionsItem(c)"
                            :is-new="!!c.is_new"
                            :price-changed="!!c.price_changed"
                            :price-prev="c.price_prev ?? null"
                            :price-pct="c.price_pct ?? null"
                            @open="openCard"
                          />
                        </div>
                        <div v-if="visibleItems(day).length > sliceLimit(day)" class="page-seo-watch__more">
                          <button class="btn btn-outline-primary btn-sm page-seo-watch__more-btn" @click="showMore(day)">
                            Увидеть больше
                          </button>
                        </div>
                      </div>
                    </div>
                    <div v-else class="text-muted p-2">Срезов по этой фразе за период нет.</div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="eventRows.length" class="wb-grid-card page-seo-watch__block">
        <div class="card-header text-white wb-card-header wb-card-header--sm">События по фразам мониторинга</div>
        <div class="page-seo-watch__events">
          <div v-for="row in eventRows" :key="row.phrase" class="page-seo-watch__event">
            <div class="page-seo-watch__event-phrase">
              {{ row.phrase }} <span class="page-seo-watch__note">({{ row.last_at }})</span>
            </div>
            <div v-if="row.new_cnt" class="page-seo-watch__event-line">
              <i class="bi bi-plus-circle text-info"></i>
              новые в выдаче:
              <span v-for="n in row.new_items" :key="n.nm_id" class="page-seo-watch__event-item">
                <a :href="wbUrl(n.nm_id)" target="_blank" rel="noopener">{{ n.title || ('nm ' + n.nm_id) }}</a>
                <span class="page-seo-watch__note"> поз. {{ n.position }}<template v-if="n.price"> · {{ fmtMoney(n.price) }}</template></span>
              </span>
            </div>
            <div v-for="mv in row.price_moves" :key="'mv' + mv.nm_id" class="page-seo-watch__event-line">
              <i class="bi bi-cash-coin text-warning"></i>
              сдвиг цены:
              <button class="btn btn-sm btn-link p-0 page-seo-watch__event-link" @click="competitorNm = mv.nm_id">
                {{ mv.title || ('nm ' + mv.nm_id) }}
              </button>
              <span class="page-seo-watch__note">
                {{ fmtMoney(mv.from) }} → {{ fmtMoney(mv.to) }} ({{ fmtPct(mv.pct) }})
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Действия менеджера — панелью над матрицей (page-seo-watch__actions) -->
    </template>

    <CompetitorDetailsModal :open="competitorNm !== null" :nm-id="competitorNm" @close="competitorNm = null" />
    <OurCardModal :open="ourCardNm !== null" :nm-id="ourCardNm" :date-from="dateFrom" :date-to="dateTo" @close="ourCardNm = null" />
  </div>
</template>