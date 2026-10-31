<template>
  <div v-if="open" class="page-wb-detail__modal-backdrop" @click.self="$emit('close')">
    <div
      ref="boxRef"
      class="page-wb-detail__modal-box page-wb-detail__modal-box--xl"
      :style="boxStyle"
      data-modal-drag="own"
    >
      <div class="page-wb-detail__modal-head" v-on="dragHandlers">
        <h5 class="page-wb-detail__modal-title">
          <i class="bi bi-collection"></i> Полки и баджи
          <span class="page-wb-detail__modal-count">{{ nmId || '—' }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <!-- бейджи нашей карточки + цена + состояние сбора -->
      <div class="page-wb-detail__shelf-head mt-2">
        <div>
          <div class="page-wb-detail__shelf-badges">
            <span
              v-for="(b, i) in data?.badges || []"
              :key="i"
              class="page-wb-detail__shelf-badge"
              :class="badgeClass(b)"
            >{{ b }}</span>
            <button
              class="btn btn-sm btn-light"
              title="История наборов бейджей — снимки при сборе карточки"
              @click="historyOpen = true"
            >
              <i class="bi bi-clock-history"></i> история
            </button>
          </div>
          <div class="page-wb-detail__shelf-state">
            <span
              class="page-wb-detail__shelf-chip"
              :class="data?.full_collected ? 'page-wb-detail__shelf-chip--ok' : ''"
            >{{ data?.full_collected ? 'собрано' : (data?.collected ? 'только из выдачи' : 'не собрано') }}</span>
            <span v-if="data?.collected_at" class="page-wb-detail__shelf-chip">
              сбор: {{ fmt(data.collected_at) }}
            </span>
            <span v-if="data?.in_queue" class="page-wb-detail__shelf-chip page-wb-detail__shelf-chip--queue">
              в очереди сбора
            </span>
          </div>
        </div>
        <div class="page-wb-detail__shelf-price">
          <b>{{ money(data?.price) }}</b>
          <s v-if="data?.old_price">{{ money(data.old_price) }}</s>
          <div class="page-wb-detail__shelf-price-note">цена на карточке WB</div>
        </div>
      </div>

      <!-- табы -->
      <div class="page-wb-detail__shelf-tabs">
        <button
          class="page-wb-detail__shelf-tab"
          :class="{ 'page-wb-detail__shelf-tab--on': tab === 'blocks' }"
          @click="tab = 'blocks'"
        >Полки в нашей карточке</button>
        <button
          class="page-wb-detail__shelf-tab"
          :class="{ 'page-wb-detail__shelf-tab--on': tab === 'where' }"
          @click="switchTab('where')"
        >Где мы на полках</button>
      </div>

      <!-- ============ вкладка 1: полки на нашей карточке ============ -->
      <template v-if="tab === 'blocks'">
        <div v-if="loading" class="text-muted small">
          <span class="spinner-border spinner-border-sm"></span> Загрузка...
        </div>
        <div v-if="error" class="text-danger small">{{ error }}</div>

        <div v-if="!loading && !(data?.blocks || []).length" class="page-wb-detail__shelf-empty">
          Полок на карточке пока нет — их собирает расширение, когда открывает
          страницу. Нажмите «Собрать сейчас».
        </div>

        <div
          v-for="b in data?.blocks || []"
          :key="b.shelf_id"
          class="page-wb-detail__shelf-block"
        >
          <div class="page-wb-detail__shelf-block-head">
            <span class="page-wb-detail__shelf-block-title">{{ b.title }}</span>
            <span class="page-wb-detail__shelf-block-meta">
              {{ b.date }} · {{ b.items_cnt }} карточек
              <template v-if="b.is_partial">· снято не целиком</template>
            </span>
          </div>

          <div v-if="b.items.length" class="page-wb-detail__shelf-row" data-drag-scroll v-on="rowDrag.dragHandlers">
            <ShelfItemCard
              v-for="(it, i) in b.items"
              :key="`${b.shelf_id}:${it.nm_id}:${it.position}:${i}`"
              :item="it"
            />
          </div>
          <div v-else class="page-wb-detail__shelf-empty">
            За срез {{ b.date }} позиций нет.
          </div>

          <!-- старые срезы этого блока -->
          <div v-for="row in olderRows[b.shelf_id] || []" :key="row.date">
            <div class="page-wb-detail__shelf-block-head mt-2">
              <span class="page-wb-detail__shelf-block-meta">срез {{ row.date }}</span>
            </div>
            <div v-if="row.items.length" class="page-wb-detail__shelf-row" data-drag-scroll v-on="rowDrag.dragHandlers">
              <ShelfItemCard
                v-for="(it, i) in row.items"
                :key="`${b.shelf_id}:${row.date}:${it.nm_id}:${it.position}:${i}`"
                :item="it"
              />
            </div>
            <div v-else class="page-wb-detail__shelf-empty">За срез {{ row.date }} позиций нет.</div>
          </div>

          <button
            v-if="nextOlder(b)"
            class="btn btn-sm btn-light"
            :disabled="loadingOlder === b.shelf_id"
            @click="showOlder(b)"
          >
            <span v-if="loadingOlder === b.shelf_id" class="spinner-border spinner-border-sm"></span>
            показать срез от {{ nextOlder(b) }}
          </button>
        </div>
      </template>

      <!-- ============ вкладка 2: где мы на полках ============ -->
      <template v-else>
        <WbDateRangeFilter :from="dateFrom" :to="dateTo" compact @apply="onRange" />

        <p class="page-wb-detail__shelf-hint">
          Карточки конкурентов, в чьих полках нас рекомендуют. Цифра в правом
          верхнем углу — наша позиция в этой полке; клик по ней открывает всю
          собранную полку конкурента. Под оценками — дата среза.
        </p>

        <div v-if="whereLoading" class="text-muted small">
          <span class="spinner-border spinner-border-sm"></span> Загрузка...
        </div>
        <div v-else-if="!anchors.length" class="page-wb-detail__shelf-empty">
          За выбранный период нас не видели в полках конкурентов.
        </div>
        <div v-else class="page-wb-detail__shelf-row" data-drag-scroll v-on="rowDrag.dragHandlers">
          <div
            v-for="a in anchors"
            :key="a.shelf_id"
            class="page-wb-detail__shelf-anchor"
            :title="`Вся полка у конкурента ${a.anchor_nm}`"
          >
            <!-- Клик открывает полку ТОЛЬКО по цифре позиции (наша позиция
                 в полке конкурента) — сама карточка не кликабельна. -->
            <ShelfItemCard
              :item="anchorItem(a)"
              :our-position="a.position"
              :snap-date="a.date"
              :shelf-title="a.shelf_title"
              @open-position="openBlock(a)"
            />
          </div>
        </div>
      </template>

      <div class="page-wb-detail__modal-foot">
        <button class="btn btn-sm btn-outline-primary" :disabled="busy" @click="doCollect">
          <i class="bi bi-box-arrow-in-down"></i> Собрать сейчас
        </button>
        <button class="btn btn-sm btn-outline-secondary" :disabled="busy" @click="load">
          <i class="bi bi-arrow-repeat"></i> Обновить
        </button>
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>
    </div>

    <ShelfBlockModal
      :open="blockOpen"
      :nm-id="nmId"
      :shelf-id="blockShelfId"
      :date="blockDate"
      @close="blockOpen = false"
    />
    <OurCardBadgesModal :open="historyOpen" :nm-id="nmId" @close="historyOpen = false" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ourCardApi,
  type OurCardData,
  type ShelfAnchor,
  type ShelfBlock,
  type ShelfItem,
} from '@/api/ourCard'
import ShelfItemCard from './ShelfItemCard.vue'
import ShelfBlockModal from './ShelfBlockModal.vue'
import OurCardBadgesModal from './OurCardBadgesModal.vue'
import WbDateRangeFilter from './WbDateRangeFilter.vue'
import { useDraggable } from '@/composables/useDraggable'
import { useDragScroll } from '@/composables/useDragScroll'

/** Полки и баджи нашей карточки (/wb/detail).
 *
 *  Вкладка 1 — блоки на нашей карточке («Смотрите также», «Продавец
 *  рекомендует»): ряд карточек, как в блоке WB; старые срезы — кнопкой.
 *  Вкладка 2 — «Где мы на полках»: конкуренты, в чьих полках нас видели; у
 *  нас в углу — наша позиция, клик открывает всю полку конкурента.
 */
const props = defineProps<{ open: boolean; nmId: number | string | null | undefined }>()
defineEmits<{ (e: 'close'): void }>()

const data = ref<OurCardData | null>(null)
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const tab = ref<'blocks' | 'where'>('blocks')

/** Старые срезы блоков: shelf_id -> [{date, items}] */
const olderRows = ref<Record<number, { date: string; items: ShelfItem[] }[]>>({})
const loadingOlder = ref(0)

/** «Где мы на полках» */
const anchors = ref<ShelfAnchor[]>([])
const whereLoading = ref(false)
const dateFrom = ref('')
const dateTo = ref('')

const historyOpen = ref(false)
const blockOpen = ref(false)
const blockShelfId = ref<number | null>(null)
const blockDate = ref('')

// Модалку тянем за шапку (composables/useDraggable), ленты карточек — мышью
// (composables/useDragScroll).
const boxRef = ref<HTMLElement | null>(null)
const { boxStyle, dragHandlers } = useDraggable(boxRef)
const rowDrag = useDragScroll()

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function todayIso(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function load() {
  const nm = Number(props.nmId || 0)
  if (!nm) {
    data.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    data.value = await ourCardApi.card(nm)
    olderRows.value = {}
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки'
    data.value = null
  } finally {
    loading.value = false
  }
}

async function loadWhere() {
  const nm = Number(props.nmId || 0)
  if (!nm) {
    anchors.value = []
    return
  }
  whereLoading.value = true
  try {
    const d = await ourCardApi.where(nm, dateFrom.value, dateTo.value)
    anchors.value = d.items || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки'
    anchors.value = []
  } finally {
    whereLoading.value = false
  }
}

function switchTab(t: 'blocks' | 'where') {
  tab.value = t
  if (t === 'where' && !anchors.value.length) loadWhere()
}

function onRange(p: { from: string; to: string }) {
  dateFrom.value = p.from
  dateTo.value = p.to
  loadWhere()
}

/** Следующий старый срез блока (ISO-даты сравниваются строкой). */
function nextOlder(b: ShelfBlock): string {
  const cur = b.date
  const older = (b.dates || []).filter((d) => d && d < cur)
  if (!older.length) return ''
  const shown = (olderRows.value[b.shelf_id] || []).map((r) => r.date)
  const left = older.filter((d) => !shown.includes(d))
  return left.length ? left[0] : ''
}

async function showOlder(b: ShelfBlock) {
  const nm = Number(props.nmId || 0)
  const date = nextOlder(b)
  if (!nm || !date) return
  loadingOlder.value = b.shelf_id
  try {
    const d = await ourCardApi.block(nm, b.shelf_id, date)
    const list = olderRows.value[b.shelf_id] || []
    olderRows.value = {
      ...olderRows.value,
      [b.shelf_id]: [...list, { date, items: d.items || [] }],
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки среза'
  } finally {
    loadingOlder.value = 0
  }
}

function openBlock(a: ShelfAnchor) {
  blockShelfId.value = a.shelf_id
  blockDate.value = a.date
  blockOpen.value = true
}

function anchorItem(a: ShelfAnchor): ShelfItem {
  return {
    nm_id: a.anchor_nm,
    position: a.position,
    title: a.title,
    brand: a.brand,
    seller: a.seller,
    price: a.price,
    old_price: a.old_price,
    rating: a.rating,
    review_rating: a.review_rating,
    feedbacks: a.feedbacks,
    cashback: null,
    is_new: 0,
    is_own: 0,
    image_url: a.image_url,
    badges: a.badges || [],
  }
}

async function doCollect() {
  const nm = Number(props.nmId || 0)
  if (!nm || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const r = await ourCardApi.collect(nm)
    notice.value = r?.queued
      ? 'Карточка в очереди сбора — расширение её соберёт.'
      : (r?.detail || 'Карточка уже в работе.')
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка постановки в очередь'
  } finally {
    busy.value = false
  }
}

watch(
  () => [props.open, props.nmId],
  ([open]) => {
    if (!open) return
    notice.value = ''
    error.value = ''
    tab.value = 'blocks'
    anchors.value = []
    olderRows.value = {}
    dateFrom.value = isoDaysAgo(29)
    dateTo.value = todayIso()
    load()
  },
)

function badgeClass(b: string): string {
  const s = String(b || '').toLowerCase()
  if (/ресейл|resale/.test(s)) return 'page-wb-detail__shelf-badge--resale'
  if (/%/.test(s) || /^[-−]/.test(s)) return 'page-wb-detail__shelf-badge--sale'
  if (/кэшбэк|cashback/.test(s)) return 'page-wb-detail__shelf-badge--cash'
  if (/цена|выгод|дешев/.test(s)) return 'page-wb-detail__shelf-badge--price'
  if (/11\.11|черн|день|распродаж|акци/.test(s)) return 'page-wb-detail__shelf-badge--promo'
  if (/премиум|руководител|эксклюзив|вкус/.test(s)) return 'page-wb-detail__shelf-badge--vip'
  return 'page-wb-detail__shelf-badge--plain'
}

function fmt(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

function money(v?: number | string | null): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return String(v)
  return `${n.toLocaleString('ru-RU')} ₽`
}
</script>

<style scoped>
/* Карточка конкурента во вкладке «Где мы на полках»: кликабельна только
   цифра позиции (внутри ShelfItemCard), сама карточка — нет. */
.page-wb-detail__shelf-anchor {
  border-radius: 12px;
}
</style>
