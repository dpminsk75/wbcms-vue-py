<template>
  <div class="page-wb-promotions__tl">
    <div v-if="!rows.length" class="page-wb-promotions__empty">Нет акций за выбранный период</div>
    <div v-else ref="scrollRef" class="page-wb-promotions__tl-scroll" @scroll.passive="onScroll">
      <div class="page-wb-promotions__tl-inner" :style="{ minWidth: innerWidth }">
        <!-- Ось дней — РОВНО выбранный период (не мин/макс по акциям) -->
        <div class="page-wb-promotions__tl-head">
          <div class="page-wb-promotions__tl-head-lbl">Акция</div>
          <div class="page-wb-promotions__tl-days" :style="daysStyle">
            <div
              v-for="d in days"
              :key="d.iso"
              class="page-wb-promotions__tl-day"
              :class="{
                'page-wb-promotions__tl-day--wknd': d.weekend,
                'page-wb-promotions__tl-day--today': d.today,
              }"
            >
              <b>{{ d.day }}</b>{{ d.month }}
            </div>
          </div>
        </div>

        <!-- Ряды акций: название и полоса — ссылки на подбор товаров -->
        <div v-for="p in rows" :key="p.promo_id" class="page-wb-promotions__tl-row">
          <div
            class="page-wb-promotions__tl-name page-wb-promotions__tl-name--link"
            role="link"
            :title="'Открыть подбор товаров — ' + p.name"
            @click="$emit('open', p)"
          >
            {{ p.name }}
            <i>{{ typeLabel(p) }} · {{ fmtDate(p.start_date) }} — {{ fmtDate(p.end_date) }}</i>
          </div>
          <div class="page-wb-promotions__tl-lane" :style="daysStyle">
            <div
              class="page-wb-promotions__tl-bar page-wb-promotions__tl-bar--link"
              :class="barClass(p)"
              :style="barStyle(p)"
              role="link"
              :title="`${p.name} · ${fmtDate(p.start_date)} — ${fmtDate(p.end_date)} — открыть подбор`"
              @click="$emit('open', p)"
            >
              <div class="page-wb-promotions__tl-bar-t">{{ p.name }}</div>
              <div class="page-wb-promotions__tl-bar-m">
                <span class="page-wb-promotions__tl-st" :class="statusClass(p)">{{ statusLabel(p) }}</span>
                <span v-if="participation(p)" class="page-wb-promotions__tl-disc">
                  ⌃ {{ participation(p) }}
                </span>
              </div>
              <div v-if="p.in_promo_total" class="page-wb-promotions__tl-bar-f">
                {{ p.in_promo_leftovers ?? 0 }} из {{ p.in_promo_total }} товаров участвуют
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { PromoRow } from '@/api/promotions'
import { promoDate, promoStatus, promoStatusLabel, promoTypeLabel } from '@/api/promotions'

/** Ширина колонки дня, px — иначе при 90+ днях подписи слипаются. */
const DAY_W = 26
/** Ширина колонки с названием акции, px. */
const NAME_W = 250

const props = withDefaults(defineProps<{
  rows: PromoRow[]
  /** Выбранный период — ось календаря строится по нему. */
  dateFrom?: string
  dateTo?: string
  /** Позиция горизонтальной прокрутки (из URL) — восстанавливается. */
  scroll?: number
}>(), { scroll: 0 })

const emit = defineEmits<{
  (e: 'open', p: PromoRow): void
  (e: 'scroll', x: number): void
}>()

const scrollRef = ref<HTMLElement | null>(null)

/** Прокрутка наружу — страница пишет её в URL. */
const onScroll = () => {
  emit('scroll', scrollRef.value?.scrollLeft || 0)
}

/** После появления акций возвращаем прокрутку из URL. */
watch(() => props.rows.length, async () => {
  if (!props.scroll) return
  await nextTick()
  if (scrollRef.value) scrollRef.value.scrollLeft = props.scroll
})

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

function fmtDate(isoStr: string): string {
  const d = promoDate(isoStr)
  if (!d) return '—'
  return String(d.getDate()).padStart(2, '0') + '.' + String(d.getMonth() + 1).padStart(2, '0')
}

function addDays(d: Date, n: number): Date {
  const x = new Date(d.getTime())
  x.setDate(x.getDate() + n)
  return x
}

function iso(d: Date): string {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
}

/** Ось: выбранный период; если его нет — по датам показанных акций. */
const axis = computed(() => {
  const from = promoDate(props.dateFrom)
  const to = promoDate(props.dateTo)
  let min = from
  let max = to
  if (!min || !max) {
    const dates: Date[] = []
    for (const p of props.rows) {
      const a = promoDate(p.start_date)
      const b = promoDate(p.end_date)
      if (a) dates.push(a)
      if (b) dates.push(b)
    }
    if (!dates.length) return { from: null as Date | null, to: null as Date | null, days: [] as any[] }
    min = new Date(Math.min(...dates.map(d => d.getTime())))
    max = new Date(Math.max(...dates.map(d => d.getTime())))
  }
  if (max.getTime() < min.getTime()) max = min
  const out: any[] = []
  const today = new Date()
  const todayIso = iso(today)
  for (let d = new Date(min.getTime()); d <= max; d = addDays(d, 1)) {
    const wd = d.getDay()
    out.push({
      iso: iso(d),
      day: d.getDate(),
      month: d.getDate() === 1 || d.getDate() === 15 ? MONTHS[d.getMonth()] : '',
      weekend: wd === 0 || wd === 6,
      today: iso(d) === todayIso,
    })
  }
  return { from: min, to: max, days: out }
})

const days = computed(() => axis.value.days)

const daysStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.max(1, days.value.length)}, minmax(${DAY_W}px, 1fr))`,
}))

/** Минимальная ширина, чтобы колонки не схлопывались. */
const innerWidth = computed(() => `${NAME_W + days.value.length * DAY_W + 24}px`)

/** Индексы колонок полосы внутри оси. */
function span(p: PromoRow): { start: number; end: number } | null {
  const a = promoDate(p.start_date)
  const b = promoDate(p.end_date)
  if (!a || !b || !axis.value.from) return null
  const from = axis.value.from.getTime()
  const daysTotal = days.value.length
  let s = Math.round((a.getTime() - from) / 86400000)
  let e = Math.round((b.getTime() - from) / 86400000)
  // полоса обрезается по оси: за её пределами акция не показывается
  if (e < 0 || s > daysTotal - 1) return null
  s = Math.max(0, Math.min(daysTotal - 1, s))
  e = Math.max(0, Math.min(daysTotal - 1, e))
  if (e < s) e = s
  return { start: s + 1, end: e + 1 }
}

const barStyle = (p: PromoRow) => {
  const sp = span(p)
  if (!sp) return { display: 'none' }
  return { gridColumn: `${sp.start} / ${sp.end + 1}` }
}

const status = (p: PromoRow) => promoStatus(p)

const barClass = (p: PromoRow) => ({
  'page-wb-promotions__tl-bar--auto': p.promo_type === 'auto' && status(p) === 'active',
  'page-wb-promotions__tl-bar--reg': p.promo_type === 'regular' && status(p) === 'active',
  'page-wb-promotions__tl-bar--ann': status(p) === 'announce',
  'page-wb-promotions__tl-bar--fin': status(p) === 'finished',
})

const typeLabel = (p: PromoRow) => promoTypeLabel(p)
const statusLabel = (p: PromoRow) => promoStatusLabel(p)

const statusClass = (p: PromoRow) => ({
  'page-wb-promotions__tl-st--ann': status(p) === 'announce',
  'page-wb-promotions__tl-st--act': status(p) === 'active',
  'page-wb-promotions__tl-st--fin': status(p) === 'finished',
})

/** Участие в акции: «366 из 1021» — счётчики из WB (details). */
const participation = (p: PromoRow) => {
  if (!p.in_promo_total) return ''
  return `${p.in_promo_leftovers ?? 0} из ${p.in_promo_total}`
}
</script>
