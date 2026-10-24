<script setup lang="ts">
import '@/assets/css/pages/page-seo-watch.css'
import { computed, onMounted, ref } from 'vue'
import WbDateInput from '@/components/common/WbDateInput.vue'
import WbWorkspaceTabs from '@/components/common/WbWorkspaceTabs.vue'
import type { WorkspaceTab } from '@/components/common/workspaceTabs'
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

/** Табы рабочего места — общий каркас (FBS-модель, §Шаг 4 плана 2026-10-23). */
const tabs: WorkspaceTab[] = [
  { id: 'summary', label: 'Сводка', to: '/seo-watch' },
  { id: 'positions', label: 'Выдача WB', to: '/competitor/positions' },
  { id: 'seo', label: 'SEO рекомендации', to: '/seo/index' },
  { id: 'competitors', label: 'Конкуренты', to: '/competitor/new-cards' },
  { id: 'ai', label: 'Затраты ИИ', to: '/seo/ai-usage' },
]

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

/** Показываем только свежий заход (остальные — в отчёте «Выдача WB»). */
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
}

function resetFilters() {
  activePreset.value = '30'
  dateFrom.value = daysAgo(29)
  dateTo.value = today()
  selected.value = []
  load()
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
    const params = { date_from: dateFrom.value, date_to: dateTo.value }
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

/** Глубина захода для «Собрать устаревшие»: ТОП-10/20/40 позиций выдачи. */
const cardTop = ref(20)
const CARD_TOP_OPTIONS = [
  { v: 10, label: 'ТОП-10' },
  { v: 20, label: 'ТОП-20' },
  { v: 40, label: 'ТОП-40' },
]

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
    const r = await seoWatchApi.requeue(target, dateFrom.value)
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
 * Обновление контента ТОП-10 карточек конкурентов: `wb_enrich_queue` ->
 * расширение («Получить список» / сбор карточек). Без отметок — по фразам
 * с устаревшим сбором.
 */
async function doRefresh() {
  if (actionBusy.value) return
  const target = selected.value.length ? selected.value : stalePhrases.value
  if (!target.length) return
  actionBusy.value = 'refresh'
  try {
    const r = await seoWatchApi.refresh(target, 10)
    const over = r.overflow ? `, сверх лимита не взято: ${r.overflow}` : ''
    selected.value = []
    await load()
    actionNotice.value = `в очередь enrich: ${r.assigned} (кандидатов ${r.candidates}, пропущено ${r.skipped}${over})`
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
 */
async function doCollect(mode: 'changed' | 'stale') {
  if (actionBusy.value) return
  actionBusy.value = mode
  try {
    const phrases = mode === 'stale' ? selected.value : []
    const r = await seoWatchApi.collect(mode, phrases, cardTop.value, dateFrom.value)
    const notice = mode === 'stale'
      ? `в очередь enrich: ${r.assigned} (устаревших ${r.candidates}, пропущено ${r.skipped}, порог ${r.stale_days} дн.)`
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

onMounted(load)
</script>

<template>
  <div class="container-xxl page-seo-watch">
    <div class="page-seo-watch__head">
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
        <div class="col-md-4 d-flex gap-2">
          <button class="btn btn-primary" :disabled="loading" @click="load()">Применить</button>
          <button class="btn btn-light" @click="resetFilters">Сбросить</button>
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
          <div class="page-seo-watch__kpi-note">по заказам, {{ summary.date_from }} — {{ summary.date_to }}</div>
        </div>
        <div class="page-seo-watch__kpi-card">
          <div class="page-seo-watch__kpi-label">Фраз на наблюдении</div>
          <div class="page-seo-watch__kpi-value">{{ summary.phrases_cnt }}</div>
          <div class="page-seo-watch__kpi-note">
            ТОП-{{ summary.settings.top_phrases_n }} на карточку
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
        <div class="card-header text-white wb-card-header wb-card-header--sm">Действия</div>
        <div class="page-seo-watch__actions-body">
          <label class="page-seo-watch__check">
            <input type="checkbox" v-model="allChecked" />
            <span>выбрать все ({{ selected.length }} отмечено)</span>
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
            Пересобрать выдачу (фразы)
            <span v-if="selected.length">({{ selected.length }})</span>
            <span v-else-if="stalePhrases.length">({{ stalePhrases.length }})</span>
          </button>
          <label
            class="page-seo-watch__depth"
            title="Какие первые позиции последнего захода каждой фразы попадут в пул «устаревших». На «новые и изменённые» не влияет"
          >
            устаревшие из:
            <select v-model.number="cardTop" class="form-select form-select-sm">
              <option v-for="o in CARD_TOP_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
            </select>
          </label>
          <button
            class="btn btn-sm btn-outline-primary"
            :disabled="!!actionBusy"
            title="Карточки из событий «новые в выдаче» и «сдвиг цены» по всем фразам матрицы → в очередь enrich (расширение соберёт)"
            @click="doCollect('changed')"
          >
            <i class="bi bi-stars"></i>
            Собрать новые и изменённые
          </button>
          <button
            class="btn btn-sm btn-outline-primary"
            :disabled="!!actionBusy || !hasRows"
            :title="selected.length
              ? `Устаревшие карточки только по отмеченным фразам (${selected.length}), порог компании`
              : 'Устаревшие карточки по всем фразам мониторинга, порог компании'"
            @click="doCollect('stale')"
          >
            <i class="bi bi-archive"></i>
            Собрать устаревшие
            <span v-if="selected.length">({{ selected.length }})</span>
          </button>
          <button
            class="btn btn-sm btn-outline-primary"
            :disabled="!!actionBusy || (!selected.length && !stalePhrases.length)"
            title="Взять ТОП-10 карточек последнего среза по фразам и поставить их контент в очередь enrich (расширение соберёт)"
            @click="doRefresh"
          >
            <i class="bi bi-box-arrow-in-down"></i>
            Обновить ТОП-10<span v-if="selected.length"> ({{ selected.length }})</span>
            <span v-else-if="stalePhrases.length"> ({{ stalePhrases.length }})</span>
          </button>
          <span class="page-seo-watch__note">
            Фразы → расширение «Поисковые фразы»; карточки → «Получить список», режим «SEO-мониторинг».
          </span>
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
          Пока нет фраз в мониторинге: проверьте, что есть заказы и загружены Search Reports.
        </div>
        <div v-else class="wb-table-wrap">
          <table class="wb-admin-table page-seo-watch__grid">
            <thead>
              <tr>
                <th class="page-seo-watch__col-check">
                  <input type="checkbox" v-model="allChecked" />
                </th>
                <th>Фраза</th>
                <th class="text-center" title="Заказы по фразе у наших карточек ТОП (Search Reports)">Заказы</th>
                <th class="text-center" title="Наши позиции в выдаче (все наши карточки)">Наши позиции</th>
                <th class="text-center" :title="PRICE_COL_TITLE">Цена vs ТОП-40</th>
                <th class="text-center" title="Лучшая наша позиция в выдаче">Лучшая</th>
                <th class="text-center" title="Наших карточек в первых 40 позициях выдачи">В ТОП-40</th>
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
                  <td>
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
                  <td class="text-center">
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
                  <td colspan="11">
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