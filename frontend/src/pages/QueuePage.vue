<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbWorkspaceTabs from '@/components/common/WbWorkspaceTabs.vue'
import { WORKSPACE_TABS, type WorkspaceTab } from '@/components/common/workspaceTabs'
import { api } from '@/api/client'
import {
  queueApi,
  queueSearchApi,
  queueErrorOf,
  type QueueCardList,
  type SearchQueueList,
  type SearchQueueRow,
  type SearchSource,
} from '@/api/queue'

/**
 * Страница «Очередь»: обе вкладки по единому каркасу —
 * фильтры слева (col-md-4) с кнопкой «Применить», действия справа (col-md-8).
 * Пункты «Очереди» — 1:1 с попапа расширения.
 */

const tabs: WorkspaceTab[] = WORKSPACE_TABS
const route = useRoute()
const router = useRouter()

const TABS = [
  { id: 'cards', label: 'Сбор карточек' },
  { id: 'search', label: 'Сбор поисковой выдачи' },
] as const
const tab = ref<'cards' | 'search'>('cards')
function setTab(t: 'cards' | 'search') {
  tab.value = t
  syncUrl()
}

/* ================= Сбор карточек ================= */

const cardsLoading = ref(false)
const cardsError = ref('')
const cardsNotice = ref('')
const cardsData = ref<QueueCardList | null>(null)
const cardsQ = ref('')
// «Очередь» — пункты попапа «Что собирать»; значения:
// watch=Из SEO-мониторинга, new=Только новые (куча + «В очереди»),
// refresh=Обновить старые (куча + «На обновлении»), all=фильтр не ставится.
const cardsQueue = ref<'watch' | 'new' | 'refresh' | 'all'>('watch')
const cardsStatus = ref('pending') // 'hidden' — пункт «Исключено» (capture.is_hidden)
// Пагинация: 50/100/300/Все (0); смена лимита — со страницы 1, перезагрузка сразу
const LIMIT_OPTIONS = [
  { v: 50, label: '50' },
  { v: 100, label: '100' },
  { v: 300, label: '300' },
  { v: 0, label: 'Все' },
]
const cardsLimit = ref(50)
const cardsOffset = ref(0)
function onCardsLimitChange() { cardsOffset.value = 0; cardsStale.value = false; loadCards() }
function cardsPage(dir: number) { cardsOffset.value += dir * cardsLimit.value; loadCards() }

const CARDS_QUEUE_OPTIONS = [
  { v: 'watch', label: 'Из SEO-мониторинга' },
  { v: 'new', label: 'Только новые' },
  { v: 'refresh', label: 'Обновить старые' },
  { v: 'all', label: 'Все' },
] as const

// Порядок как в мокапе: сначала «В очереди» (дефолт), потом «Все».
const CARD_STATUS_OPTIONS = [
  { v: 'pending', label: 'В очереди' },
  { v: '', label: 'Все' },
  { v: 'need_update', label: 'На обновлении' },
  { v: 'processing', label: 'В работе' },
  { v: 'done', label: 'Собрано' },
  { v: 'error', label: 'Ошибки' },
  { v: 'gone', label: 'Нет на WB' },
  { v: 'hidden', label: 'Исключено' },
]

const CARD_STATUS_BADGE: Record<string, string> = {
  pending: 'bg-primary',
  need_update: 'bg-warning text-dark',
  processing: 'bg-info text-dark',
  done: 'bg-success',
  error: 'bg-danger',
  gone: 'bg-secondary',
}

const CARD_SOURCE_BADGE: Record<string, string> = {
  watch: 'SEO-мониторинг',
  '': 'Общая куча',
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: 'в очереди', need_update: 'на обновлении', processing: 'в работе',
    done: 'собран', error: 'ошибка', gone: 'нет на WB',
  }
  return map[s] || s
}

/** Числовой счётчик статуса из последнего ответа (для выпадающего списка). */
function countOf(v: string): number | null {
  if (!cardsData.value?.counts) return null
  if (v === '') return cardsData.value.counts.total
  if (v === 'hidden') return cardsData.value.counts.hidden ?? 0
  return (cardsData.value.counts as Record<string, number | undefined>)[v] ?? 0
}

/** Подпись пункта статуса: «В очереди (221)». */
function statusCountLabel(v: string): string {
  const c = countOf(v)
  return c === null ? '' : ` (${c})`
}

// «Только новые» / «Обновить старые» — шорткаты: задают и очередь, и статус.
// Статус от шортката при уходе на watch/all возвращается на «В очереди».
// Смена очереди обновляет ТОЛЬКО счётчики (лёгкий запрос) — сам список
// страницы большой, он грузится по «Применить».
const cardsStatusManual = ref(false)
const cardsStale = ref(false) // фильтры изменены — список ждёт «Применить»
function onCardsStatusChange() { cardsStatusManual.value = true; cardsStale.value = true }
function cardsQueueChanged() {
  if (cardsQueue.value === 'new') { cardsStatus.value = 'pending'; cardsStatusManual.value = false }
  else if (cardsQueue.value === 'refresh') { cardsStatus.value = 'need_update'; cardsStatusManual.value = false }
  else if (!cardsStatusManual.value) cardsStatus.value = 'pending'
  const queue = cardsQueue.value === 'watch' ? 'watch'
    : cardsQueue.value === 'all' ? 'all' : 'plain'
  cardsStale.value = true
  queueApi.cardsCounts(queue)
    .then((counts) => {
      cardsData.value = cardsData.value
        ? { ...cardsData.value, counts }
        : { items: [], total: 0, limit: 0, offset: 0, counts }
    })
    .catch(() => {})
}

const cardsRows = computed(() => cardsData.value?.items || [])

async function loadCards() {
  cardsLoading.value = true
  cardsError.value = ''
  try {
    const hidden = cardsStatus.value === 'hidden'
    const queue = cardsQueue.value === 'watch' ? 'watch'
      : cardsQueue.value === 'all' ? 'all' : 'plain'
    cardsData.value = await queueApi.cards({
      queue,
      status: hidden ? '' : cardsStatus.value,
      q: cardsQ.value,
      hidden,
      limit: cardsLimit.value,
      offset: cardsOffset.value,
    })
  } catch (e) {
    cardsError.value = queueErrorOf(e)
  } finally {
    cardsLoading.value = false
  }
}

function applyCards() {
  cardsOffset.value = 0
  cardsStale.value = false
  loadCards()
  syncUrl()
}

/* ---------- Действие 1: добавить nmID ---------- */

const addNm = ref('')
const addNmBusy = ref(false)

async function doAddNm() {
  const n = parseInt(addNm.value, 10)
  if (!Number.isFinite(n) || n <= 0) { cardsError.value = 'Укажите числовой nmID'; return }
  if (addNmBusy.value) return
  cardsError.value = ''
  cardsNotice.value = ''
  addNmBusy.value = true
  try {
    await queueApi.cardsAdd(n)
    cardsNotice.value = `Карточка ${n} добавлена в очередь`
    addNm.value = ''
    await loadCards()
  } catch (e) { cardsError.value = queueErrorOf(e) }
  finally { addNmBusy.value = false }
}

/* ---------- Действие 2: добавить из нашей карточки ---------- */

// Поиск своей карточки, как в WbUniversalFilter: /api/wb/cards?q= → подсказки.
// Выбранная карточка → счётчик конкурентов → «Добавить (N)» = seed её
// конкурентов в очередь (дублей нет, скрытые пропускаются).
interface OurCard { nmID: number; vendorCode?: string; title?: string }
const addQ = ref('')
const addSug = ref<OurCard[]>([])
const addSugOpen = ref(false)
function closeSugSoon() { setTimeout(() => { addSugOpen.value = false }, 150) }
const addChosen = ref<OurCard | null>(null)
const addCount = ref<number | null>(null)
const addBusy = ref(false)
let addTimer: ReturnType<typeof setTimeout> | null = null
let addSeq = 0

function pickCard(c: OurCard) {
  addChosen.value = c
  addCount.value = null
  addSugOpen.value = false
  queueApi.competitorsCount(c.nmID)
    .then(r => { if (addChosen.value?.nmID === c.nmID) addCount.value = r.count })
    .catch(e => {
      if (addChosen.value?.nmID === c.nmID) {
        addChosen.value = null
        cardsError.value = queueErrorOf(e)
      }
    })
}

function resolveAdd(s: string, list: OurCard[]) {
  const num = Number(s)
  if (Number.isFinite(num) && num > 0) {
    const hit = list.find(c => Number(c.nmID) === num)
    pickCard(hit || { nmID: num })
    return
  }
  const hit = list.find(c => String(c.vendorCode || '') === s)
  if (hit) pickCard(hit)
}

watch(addQ, (v) => {
  const s = String(v || '').trim()
  addChosen.value = null
  addCount.value = null
  if (addTimer) clearTimeout(addTimer)
  if (s.length < 2) { addSug.value = []; return }
  const my = ++addSeq
  addTimer = setTimeout(async () => {
    try {
      const { data } = await api.get('/api/wb/cards', { params: { q: s, limit: 20 } })
      if (my !== addSeq) return
      const list: OurCard[] = Array.isArray(data) ? data : (data?.items ?? [])
      addSug.value = list
      addSugOpen.value = true
      resolveAdd(s, list)
    } catch { if (my === addSeq) addSug.value = [] }
  }, 300)
})

async function doSeedAdd() {
  if (!addChosen.value || addBusy.value) return
  cardsError.value = ''
  cardsNotice.value = ''
  const c = addChosen.value
  addBusy.value = true
  try {
    const r = await queueApi.seedFromCard(c.nmID)
    const parts = [`добавлено ${r.added}`]
    if (r.already) parts.push(`уже в очереди ${r.already}`)
    if (r.skipped_hidden) parts.push(`скрытых пропущено ${r.skipped_hidden}`)
    cardsNotice.value = `Карточка ${c.nmID}: ${parts.join(', ')} из ${r.checked}`
    addQ.value = ''
    addSug.value = []
    addChosen.value = null
    addCount.value = null
    await loadCards()
  } catch (e) { cardsError.value = queueErrorOf(e) }
  finally { addBusy.value = false }
}

/* ---------- Строки ---------- */

async function requeueCard(id: number) {
  cardsError.value = ''
  try {
    await queueApi.cardsRequeue(id)
    await loadCards()
  } catch (e) { cardsError.value = queueErrorOf(e) }
}

async function deleteCard(row: { id: number; nm_id: number }) {
  cardsError.value = ''
  cardsNotice.value = ''
  if (!window.confirm(`Удалить карточку ${row.nm_id} из очереди сбора?\n` +
    'Если её не заблокировать — она вернётся при следующем засеве очереди.')) return
  try {
    await queueApi.cardsDelete(row.id)
    cardsNotice.value = `Карточка ${row.nm_id} удалена из очереди`
    await loadCards()
  } catch (e) { cardsError.value = queueErrorOf(e) }
}

async function blockCard(row: { nm_id: number; is_hidden: boolean | number }) {
  cardsError.value = ''
  const h = Boolean(row.is_hidden)
  if (!h && !window.confirm(`Блокировать карточку ${row.nm_id}?\n` +
    'Её нельзя будет добавить в очередь и соберёт расширение — до разблокировки.')) return
  try {
    await queueApi.cardsBlock(row.nm_id, !h)
    cardsNotice.value = !h ? `Карточка ${row.nm_id} заблокирована` : `Карточка ${row.nm_id} разблокирована`
    await loadCards()
  } catch (e) { cardsError.value = queueErrorOf(e) }
}

const fmtMoney = (v: unknown): string => {
  // цена в competitor-таблицах — рубли (миграция 20261021: cards/details в рубли)
  if (v === null || v === undefined || v === '') return ''
  const n = Array.isArray(v) ? Number(v[0]) : Number(v)
  if (!n) return ''
  return `${n.toFixed(0)} ₽`
}

/* ================= Сбор поисковой выдачи ================= */
// «Очередь» — селект «Источник поиска» попапа 1:1 (popup.html:212-218):
// phrases=Из SEO-мониторинга, seo=По фразам из карточки,
// report=ТОП-20 (на лету, очереди нет — баннер), compquery=Запросы конкурентов,
// both=SEO + ТОП-20 (очередь seo + баннер), all=Все (UNION трёх очередей).
const SEARCH_QUEUE_OPTIONS = [
  { v: 'phrases', label: 'Из SEO-мониторинга' },
  { v: 'seo', label: 'По фразам из карточки' },
  { v: 'report', label: 'ТОП-20 поисковых фраз' },
  { v: 'compquery', label: 'Запросы конкурентов' },
  { v: 'both', label: 'SEO + ТОП-20' },
  { v: 'all', label: 'Все' },
] as const

type SearchQueueValue = (typeof SEARCH_QUEUE_OPTIONS)[number]['v']
const searchQueue = ref<SearchQueueValue>('phrases')
const searchStatus = ref('pending')
const searchQ = ref('')
const searchData = ref<SearchQueueList | null>(null)
const searchLoading = ref(false)
const searchError = ref('')
const searchNotice = ref('')
const searchStale = ref(false) // фильтры изменены — список ждёт «Применить»
const searchLimit = ref(50)
const searchOffset = ref(0)
function onSearchLimitChange() { searchOffset.value = 0; searchStale.value = false; loadSearch() }
function searchPage(dir: number) { searchOffset.value += dir * searchLimit.value; loadSearch() }
const addPhr = ref('')
const addSearchNm = ref('')

const SEARCH_STATUS_OPTIONS = [
  { v: 'pending', label: 'В очереди' },
  { v: '', label: 'Все' },
  { v: 'processing', label: 'В работе' },
  { v: 'done', label: 'Собрано' },
  { v: 'error', label: 'Ошибки' },
]

const SEARCH_STATUS_BADGE: Record<string, string> = {
  pending: 'bg-primary', processing: 'bg-info text-dark',
  done: 'bg-success', error: 'bg-danger',
}

const SEARCH_SRC_BADGE: Record<string, string> = {
  seo: 'По фразам из карточки',
  compquery: 'Запросы конкурентов',
  phrases: 'Из SEO-мониторинга',
}

/** Очередь селекта → source API (report не в API: там баннер; both = seo). */
const effSearchSource = computed((): string => {
  const v = searchQueue.value
  if (v === 'report') return ''
  if (v === 'both') return 'seo'
  return v // phrases | seo | compquery | all
})

function onSearchQueueChange() {
  // лёгкий запрос: только счётчики, таблицу не трогаем — грузится по «Применить»
  searchStale.value = true
  queueSearchApi.counts()
    .then((counts) => {
      searchData.value = { ...(searchData.value || {
        source: '', items: [], total: 0, limit: 0, offset: 0, counts,
      }), counts }
    })
    .catch(() => {})
}

function searchStatusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: 'в очереди', processing: 'в работе', done: 'собран', error: 'ошибка',
  }
  return map[s] || s
}

/** Счётчики статусов по выбранной очереди (для «Все» — сумма трёх). */
const searchCounts = computed((): Record<string, number> => {
  const c = searchData.value?.counts || {}
  if (searchQueue.value === 'all') {
    const out: Record<string, number> = {}
    for (const src of ['seo', 'compquery', 'phrases']) {
      for (const [k, v] of Object.entries(c[src] || {})) out[k] = (out[k] || 0) + (v || 0)
    }
    return out
  }
  if (effSearchSource.value === '') return {}
  return c[effSearchSource.value] || {}
})

function searchCountOf(v: string): string {
  if (searchQueue.value === 'report') return ''
  const c = searchCounts.value
  const n = v === '' ? Object.values(c).reduce((a, b) => a + b, 0) : (c[v] || 0)
  return ` (${n})`
}

/** «ТОП-20» — баннер вместо списка. report — только баннер,
 * both — баннер + таблица очереди seo. */
const searchHasQueue = computed(() => searchQueue.value !== 'report')

type SearchRow = SearchQueueRow & { src?: string }
const searchRows = computed((): SearchRow[] =>
  (searchData.value?.items || []).map(r => ({ ...r, src: r.src || String(searchData.value?.source || '') })))

async function loadSearch() {
  if (!searchHasQueue.value) { searchData.value = null; return }
  searchLoading.value = true
  searchError.value = ''
  try {
    searchData.value = await queueSearchApi.list({
      source: effSearchSource.value,
      status: searchStatus.value,
      q: searchQ.value,
      limit: searchLimit.value,
      offset: searchOffset.value,
    })
  } catch (e) { searchError.value = queueErrorOf(e) }
  finally { searchLoading.value = false }
}

function applySearch() {
  searchOffset.value = 0
  searchStale.value = false
  loadSearch()
  syncUrl()
}

/* ---------- Добавить фразу ---------- */

/** В какую очередь physical-API добавляем (both → seo). null — добавить некуда. */
function addSource(): SearchSource | null {
  const v = searchQueue.value
  if (v === 'phrases') return 'phrases'
  if (v === 'seo' || v === 'both') return 'seo'
  if (v === 'compquery') return 'compquery'
  return null // report — на лету; all — выберите конкретную очередь
}

async function addSearch() {
  const target = addSource()
  if (!target) return
  searchError.value = ''
  searchNotice.value = ''
  const phrase = addPhr.value.trim()
  if (!phrase) { searchError.value = 'Укажите фразу'; return }
  const nmRequired = target !== 'phrases'
  const nm = parseInt(addSearchNm.value, 10) || 0
  if (nmRequired && !nm) {
    searchError.value = 'Укажите nmID нашей карточки'
    return
  }
  try {
    await queueSearchApi.add({ source: target, nm_id: nm || undefined, phrase })
    searchNotice.value = `Фраза «${phrase}» добавлена в очередь (${SEARCH_QUEUE_OPTIONS.find(o => o.v === searchQueue.value)?.label})`
    addPhr.value = ''
    await loadSearch()
  } catch (e) { searchError.value = queueErrorOf(e) }
}

/* ---------- Строки ---------- */

async function requeueSearch(row: SearchRow) {
  searchError.value = ''
  if (searchQueue.value === 'all' && !row.src) return
  try {
    await queueSearchApi.requeue(row.src || effSearchSource.value, row.id)
    await loadSearch()
  } catch (e) { searchError.value = queueErrorOf(e) }
}

function deleteSearch(row: SearchRow & { phrase: string }) {
  searchError.value = ''
  searchNotice.value = ''
  if (searchQueue.value === 'all' && !row.src) return
  const src = row.src || effSearchSource.value
  const what = src === 'seo'
    ? 'Это удалит целевую фразу карточки (то же, что удаление в разделе SEO).'
    : src === 'compquery'
      ? 'Фраза также исчезнет из списка запросов на странице карточки.'
      : 'Фраза просто перестанет пересобираться; собранное остаётся.'
  if (!window.confirm(`Удалить «${row.phrase}» из очереди?\n${what}`)) return
  queueSearchApi.remove(src, row.id)
    .then(() => {
      searchNotice.value = `«${row.phrase}» удалена из очереди`
      return loadSearch()
    })
    .catch((e) => { searchError.value = queueErrorOf(e) })
}

/* ================= URL ================= */

function syncUrl() {
  const q: Record<string, string> = { tab: tab.value }
  if (tab.value === 'search') {
    if (searchQueue.value !== 'phrases') q.source = searchQueue.value
    if (!searchStatus.value) q.status = 'any'
    else if (searchStatus.value !== 'pending') q.status = searchStatus.value
  } else {
    // дефолтные значения (watch + pending) в URL не пишем — восстанавливаются сами
    if (cardsQueue.value !== 'watch') q.queue = cardsQueue.value
    if (!cardsStatus.value) q.status = 'any'
    else if (cardsStatus.value !== 'pending') q.status = cardsStatus.value
  }
  router.replace({ path: '/queue', query: q })
}

function initFromUrl() {
  const t = String(route.query.tab || '') === 'search' ? 'search' : 'cards'
  tab.value = t
  const sq = String(route.query.source || '')
  if ((SEARCH_QUEUE_OPTIONS as readonly { v: string }[]).some(o => o.v === sq)) {
    searchQueue.value = sq as SearchQueueValue
  }
  const st = String(route.query.status || '')
  if (st === 'any') { searchStatus.value = ''; cardsStatus.value = ''; cardsStatusManual.value = true }
  else if (st) { searchStatus.value = st; cardsStatus.value = st; cardsStatusManual.value = true }
  // карточки: очередь (дефолты: watch + pending)
  const qv = String(route.query.queue || '')
  if ((CARDS_QUEUE_OPTIONS as readonly { v: string }[]).some(o => o.v === qv)) {
    cardsQueue.value = qv as typeof cardsQueue.value
  }
}

onMounted(() => {
  initFromUrl()
  if (tab.value === 'cards') loadCards()
  else loadSearch()
})
</script>

<template>
  <div class="container-xxl page-queue">
    <div class="wb-workspace-head">
      <h2 class="wb-workspace-head__title">Очередь</h2>
      <WbWorkspaceTabs active="queue" :tabs="tabs" />
    </div>

    <ul class="nav nav-pills wb-sub-tabs">
      <li v-for="t in TABS" :key="t.id" class="nav-item">
        <a class="nav-link" :class="{ active: tab === t.id }" href="#" @click.prevent="setTab(t.id)">{{ t.label }}</a>
      </li>
    </ul>

    <!-- ============ СБОР КАРТОЧЕК ============ -->
    <template v-if="tab === 'cards'">
      <p class="text-muted">
        Что соберёт расширение: общая куча конкурентов наших карточек и карточки SEO-мониторинга.
        Удалённая строка вернётся при следующем засеве, заблокированная — нет.
      </p>

      <div v-if="cardsError" class="alert alert-danger py-2">{{ cardsError }}</div>
      <div v-else-if="cardsNotice" class="alert alert-success py-2">{{ cardsNotice }}</div>

      <!-- Единый каркас: фильтры слева (col-md-4), действия справа (col-md-8) -->
      <div class="row g-3 mb-3">
        <div class="col-md-4">
          <div class="page-queue__filters">
            <div class="page-queue__field">
              <label class="page-queue__lbl" for="queue-cards-queue">Очередь</label>
              <select id="queue-cards-queue" v-model="cardsQueue" class="form-select form-select-sm" @change="cardsQueueChanged()">
                <option v-for="o in CARDS_QUEUE_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
              </select>
            </div>
            <div class="page-queue__field">
              <label class="page-queue__lbl" for="queue-cards-status">Статус</label>
              <select id="queue-cards-status" v-model="cardsStatus" class="form-select form-select-sm" @change="onCardsStatusChange()">
                <option v-for="o in CARD_STATUS_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}{{ statusCountLabel(o.v) }}</option>
              </select>
            </div>
            <div class="page-queue__field">
              <label class="page-queue__lbl" for="queue-cards-q">Карточка</label>
              <input id="queue-cards-q" v-model="cardsQ" class="form-control form-control-sm"
                placeholder="Название, бренд, продавец, nmID" @input="cardsStale = true" @keyup.enter="applyCards()" />
            </div>
            <div class="page-queue__field">
              <label class="page-queue__lbl" for="queue-cards-limit">Показывать</label>
              <select id="queue-cards-limit" v-model.number="cardsLimit" class="form-select form-select-sm" @change="onCardsLimitChange()">
                <option v-for="o in LIMIT_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
              </select>
            </div>
            <button class="btn btn-sm btn-primary page-queue__apply" :disabled="cardsLoading" @click="applyCards()">
              Применить
            </button>
          </div>
        </div>
        <div class="col-md-8">
          <div class="page-queue__actions">
            <div class="page-queue__ttl">Действия</div>
            <!-- действие 1: просто nmID -->
            <div class="page-queue__actbox">
              <div class="page-queue__actlbl">Добавить nmID на сбор</div>
              <div class="d-flex gap-2">
                <input v-model="addNm" class="form-control form-control-sm"
                  placeholder="nmID карточки WB, например 534186046" @keyup.enter="doAddNm()" />
                <button class="btn btn-sm btn-primary" :disabled="addNmBusy" @click="doAddNm()">Добавить</button>
              </div>
            </div>
            <!-- действие 2: из нашей карточки — конкуренты в очередь -->
            <div class="page-queue__actbox">
              <div class="page-queue__actlbl">Добавить из нашей карточки</div>
              <div class="d-flex gap-2">
                <div class="page-queue__searchbox">
                  <input v-model="addQ" class="form-control form-control-sm"
                    placeholder="nmID, артикул или часть названия…" autocomplete="off"
                    @focus="addSugOpen = addSug.length > 0" @blur="closeSugSoon()" />
                  <div v-if="addSug.length && addSugOpen" class="page-queue__sug">
                    <div v-for="c in addSug" :key="c.nmID"
                      class="page-queue__sug-item"
                      :class="{ 'page-queue__sug-item--sel': addChosen?.nmID === c.nmID }"
                      @mousedown.prevent="pickCard(c)">
                      <b>{{ c.nmID }}</b>
                      <span class="page-queue__sug-vc">{{ c.vendorCode || '—' }}</span>
                      <span class="page-queue__sug-t">{{ c.title }}</span>
                    </div>
                  </div>
                </div>
                <button class="btn btn-sm btn-primary" :disabled="!addChosen || addBusy" @click="doSeedAdd()">
                  Добавить{{ addCount !== null ? ` (${addCount})` : '' }}
                </button>
              </div>
              <div v-if="addChosen" class="page-queue__chosen" :title="addChosen.title || ''">
                Выбрано: <b>{{ addChosen.nmID }}</b>{{
                  addChosen.title ? ` — «${addChosen.title}»` : ''
                }}<template v-if="addCount !== null"> · <b class="page-queue__cnt">конкурентов: {{ addCount }}</b></template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="cardsStale" class="page-queue__notebox">
        Фильтры изменены — нажмите «Применить», чтобы получить список.
      </div>
      <table v-else class="table table-hover align-middle">
        <thead>
          <tr>
            <th>Карточка</th>
            <th class="page-queue__w-status">Статус</th>
            <th>Собрано / обновлено</th>
            <th class="page-queue__w-actions text-end">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="cardsLoading"><td colspan="4" class="text-muted">Загрузка…</td></tr>
          <tr v-else-if="!cardsRows.length"><td colspan="4" class="text-muted">Пусто</td></tr>
          <tr v-for="r in cardsRows" v-else :key="r.id">
            <td>
              <div class="page-competitor__product-text">
                <div class="page-competitor__product-title" :title="r.title || ''">
                  {{ r.title || '—' }}
                  <span v-if="cardsQueue === 'all'" class="badge bg-light text-dark page-queue__qbadge">
                    {{ CARD_SOURCE_BADGE[r.source] || r.source || 'Общая куча' }}
                  </span>
                </div>
                  <div class="page-competitor__product-sub">
                    <a :href="`https://www.wildberries.ru/catalog/${r.nm_id}/detail.aspx`" target="_blank" rel="noopener"
                      class="page-competitor__wb-link">WB: {{ r.nm_id }}</a>
                    <span v-if="r.brand"> · {{ r.brand }}</span>
                    <span v-if="r.price"> · {{ fmtMoney(r.price) }}</span>
                    <span v-if="r.owner_company_id === null" class="badge bg-light text-dark">ничья строка</span>
                  </div>
              </div>
            </td>
            <td>
              <span v-if="r.is_hidden" class="badge bg-dark" title="Исключена из сбора — /next не отдаёт, seed не сеет">исключена</span>
              <span class="badge" :class="CARD_STATUS_BADGE[r.status] || 'bg-light text-dark'">{{ statusLabel(r.status) }}</span>
            </td>
            <td
              class="text-muted small"
              :title="r.requested_at ? `запрошено: ${String(r.requested_at).slice(0, 16).replace('T', ' ')}` : ''"
            >{{ (r.processed_at || r.requested_at || '').slice(0, 16).replace('T', ' ') }}</td>
            <td class="page-queue__w-actions text-end">
              <button v-if="r.is_hidden" class="btn btn-sm btn-outline-success" @click="blockCard(r)" title="Вернуть в сбор">Разблокировать</button>
              <button v-else class="btn btn-sm btn-outline-secondary" @click="blockCard(r)" title="Исключить из сбора: не сеять и не отдавать /next">Блокировать</button>
              <button v-if="['done', 'error', 'gone', 'need_update'].includes(r.status)" class="btn btn-sm btn-outline-primary" @click="requeueCard(r.id)">Вернуть в очередь</button>
              <button class="btn btn-sm btn-outline-danger" @click="deleteCard(r)">Удалить</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="cardsLimit > 0 && cardsData && cardsData.total > cardsRows.length && !cardsStale" class="page-queue__pager">
        <span class="text-muted small">
          Показано {{ cardsOffset + 1 }}–{{ cardsOffset + cardsRows.length }} из {{ cardsData.total }}
        </span>
        <button class="btn btn-sm btn-outline-secondary" :disabled="cardsOffset === 0 || cardsLoading" @click="cardsPage(-1)">
          ← Предыдущая
        </button>
        <span class="text-muted small">стр. {{ Math.floor(cardsOffset / cardsLimit) + 1 }}</span>
        <button class="btn btn-sm btn-outline-secondary" :disabled="cardsOffset + cardsRows.length >= cardsData.total || cardsLoading" @click="cardsPage(1)">
          Следующая →
        </button>
      </div>
    </template>

    <!-- ============ СБОР ПОИСКОВОЙ ВЫДАЧИ ============ -->
    <template v-else>
      <p class="text-muted">
        Очереди расширения для сбора выдачи (источники <code>/api/ext/search_next</code>).
        «ТОП-20» собирается на лету — отдельной очереди у него нет.
      </p>

      <div v-if="searchError" class="alert alert-danger py-2">{{ searchError }}</div>
      <div v-else-if="searchNotice" class="alert alert-success py-2">{{ searchNotice }}</div>

      <!-- Тот же каркас: фильтры слева (col-md-4), действия справа (col-md-8) -->
      <div class="row g-3 mb-3">
        <div class="col-md-4">
          <div class="page-queue__filters">
            <div class="page-queue__field">
              <label class="page-queue__lbl" for="queue-search-queue">Очередь</label>
              <select id="queue-search-queue" v-model="searchQueue" class="form-select form-select-sm" @change="onSearchQueueChange()">
                <option v-for="o in SEARCH_QUEUE_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
              </select>
            </div>
            <div class="page-queue__field">
              <label class="page-queue__lbl" for="queue-search-status">Статус</label>
              <select id="queue-search-status" v-model="searchStatus" class="form-select form-select-sm" @change="searchStale = true">
                <option v-for="o in SEARCH_STATUS_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}{{ searchCountOf(o.v) }}</option>
              </select>
            </div>
            <div class="page-queue__field">
              <label class="page-queue__lbl" for="queue-search-q">Фраза</label>
              <input id="queue-search-q" v-model="searchQ" class="form-control form-control-sm"
                placeholder="Фраза или часть фразы" @input="searchStale = true" @keyup.enter="applySearch()" />
            </div>
            <div class="page-queue__field">
              <label class="page-queue__lbl" for="queue-search-limit">Показывать</label>
              <select id="queue-search-limit" v-model.number="searchLimit" class="form-select form-select-sm" @change="onSearchLimitChange()">
                <option v-for="o in LIMIT_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
              </select>
            </div>
            <button class="btn btn-sm btn-primary page-queue__apply" :disabled="searchLoading" @click="applySearch()">
              Применить
            </button>
          </div>
        </div>
        <div class="col-md-8">
          <div class="page-queue__actions">
            <div class="page-queue__ttl">Действия</div>
            <div class="page-queue__actbox">
              <div class="page-queue__actlbl">Добавить фразу в очередь</div>
              <div class="d-flex gap-2">
                <input v-if="addSource() !== 'phrases'" v-model="addSearchNm" class="form-control form-control-sm page-queue__nm"
                  placeholder="nmID нашей карточки" @keyup.enter="addSearch()" />
                <input v-model="addPhr" class="form-control form-control-sm page-queue__phrase"
                  placeholder="Фраза" @keyup.enter="addSearch()" />
                <button class="btn btn-sm btn-primary" :disabled="!addSource() || searchLoading" @click="addSearch()">
                  Добавить
                </button>
              </div>
              <div v-if="searchQueue === 'both'" class="page-queue__hint">
                Добавление идёт в очередь «По фразам из карточки» (seo). «ТОП-20» — на лету, отдельно не управляется.
              </div>
              <div v-else-if="searchQueue === 'all'" class="page-queue__hint">
                В режиме «Все» добавление отключено — выберите конкретную очередь.
              </div>
              <div v-else-if="searchQueue === 'phrases'" class="page-queue__hint">
                Для «Из SEO-мониторинга» карточку указывать не нужно.
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- «ТОП-20» — report: собирается на лету, очереди нет → баннер вместо списка -->
      <div v-if="searchQueue === 'report'" class="page-queue__notebox">
        «ТОП-20 поисковых фраз» (report) собирается на лету расширением — отдельной очереди в базе нет:
        управлять нечем, список не показывается. Выберите очередь из списка или «Все».
      </div>
      <template v-else>
        <div v-if="searchQueue === 'both'" class="page-queue__notebox">
          «SEO + ТОП-20»: ниже очередь «По фразам из карточки» (seo). «ТОП-20» собирается на лету — отдельной очереди нет.
        </div>
        <div v-if="searchStale" class="page-queue__notebox">
          Фильтры изменены — нажмите «Применить», чтобы получить список.
        </div>

        <table v-else class="table table-hover align-middle">
          <thead>
            <tr>
              <th>Фраза</th>
              <th class="page-queue__w-status">Статус</th>
              <th>Обновлено</th>
              <th class="page-queue__w-actions text-end">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="searchLoading"><td colspan="4" class="text-muted">Загрузка…</td></tr>
            <tr v-else-if="!searchRows.length"><td colspan="4" class="text-muted">Пусто</td></tr>
            <tr v-for="r in searchRows" v-else :key="`${r.src || ''}-${r.id}`">
              <td>
                <div class="page-competitor__sub">
                  {{ r.phrase }}
                  <span v-if="searchQueue === 'all'" class="badge bg-light text-dark page-queue__qbadge">
                    {{ SEARCH_SRC_BADGE[r.src || ''] || r.src }}
                  </span>
                </div>
                <div class="text-muted small">
                  <template v-if="r.nm_id">наша карточка WB: {{ r.nm_id }}</template>
                  <template v-else>без привязки к карточке</template>
                  <span v-if="(r.src || effSearchSource) === 'seo' && (r.active_cnt ?? 0) >= 10">
                    · лимит 10 целевых фраз достигнут
                  </span>
                </div>
              </td>
              <td>
                <span class="badge" :class="SEARCH_STATUS_BADGE[r.status] || 'bg-light text-dark'">{{ searchStatusLabel(r.status) }}</span>
                <span v-if="r.is_active === 0" class="badge bg-secondary">неактивна</span>
              </td>
              <td class="text-muted small">{{ (r.updated_at || '').slice(0, 16).replace('T', ' ') }}</td>
              <td class="page-queue__w-actions text-end">
                <button v-if="['done', 'error'].includes(r.status)" class="btn btn-sm btn-outline-primary" @click="requeueSearch(r)">Вернуть в очередь</button>
                <button class="btn btn-sm btn-outline-danger" @click="deleteSearch(r)">Удалить</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="searchLimit > 0 && searchData && searchData.total > searchRows.length && !searchStale" class="page-queue__pager">
          <span class="text-muted small">
            Показано {{ searchOffset + 1 }}–{{ searchOffset + searchRows.length }} из {{ searchData.total }}
          </span>
          <button class="btn btn-sm btn-outline-secondary" :disabled="searchOffset === 0 || searchLoading" @click="searchPage(-1)">
            ← Предыдущая
          </button>
          <span class="text-muted small">стр. {{ Math.floor(searchOffset / searchLimit) + 1 }}</span>
          <button class="btn btn-sm btn-outline-secondary" :disabled="searchOffset + searchRows.length >= searchData.total || searchLoading" @click="searchPage(1)">
            Следующая →
          </button>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
/* Единый каркас (мокап v3): фильтры слева стопкой + «Применить», действия справа */
.page-queue__filters {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  height: 100%;
}
.page-queue__field { display: flex; flex-direction: column; gap: 4px; }
.page-queue__lbl { font-size: 12px; font-weight: 600; color: #374151; }
.page-queue__apply { width: 100%; }

.page-queue__actions { display: flex; flex-direction: column; gap: 10px; height: 100%; }
.page-queue__ttl { font-size: 12px; font-weight: 700; color: #374151; }
.page-queue__actbox {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
}
.page-queue__actlbl { font-size: 12px; font-weight: 700; color: #111827; margin-bottom: 6px; }
.page-queue__chosen { font-size: .82rem; color: #374151; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.page-queue__cnt { color: #cb11ab; }
.page-queue__hint { font-size: .78rem; color: #6b7280; margin-top: 6px; }
.page-queue__notebox {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  padding: 8px 12px;
  font-size: .87rem;
  color: #92400e;
  margin-bottom: 10px;
}
.page-queue__searchbox { position: relative; flex: 1 1 auto; min-width: 0; }
.page-queue__sug {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  right: 0;
  z-index: 20;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 8px 20px rgba(17, 24, 39, .12);
  max-height: 260px;
  overflow-y: auto;
}
.page-queue__sug-item { padding: 6px 10px; font-size: .82rem; border-bottom: 1px solid #f3f4f6; cursor: pointer; line-height: 1.35; }
.page-queue__sug-item:last-child { border-bottom: 0; }
.page-queue__sug-item:hover, .page-queue__sug-item--sel { background: #fdf0fb; }
.page-queue__sug-vc { color: #6b7280; margin-left: 8px; }
.page-queue__sug-t { margin-left: 8px; color: #111827; }
.page-queue__qbadge { font-size: .7rem; font-weight: 600; }
.page-queue__pager { display: flex; gap: 10px; align-items: center; margin: 10px 0; flex-wrap: wrap; }
.page-queue__nm { max-width: 180px; }
.page-queue__phrase { max-width: 340px; }
.page-queue__w-status { width: 140px; }
.page-queue__w-actions { width: 300px; white-space: nowrap; }
.page-queue__w-actions .btn { margin-left: 4px; }
.page-competitor__sub { font-weight: 500; }
</style>
