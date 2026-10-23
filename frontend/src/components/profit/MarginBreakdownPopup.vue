<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div
      ref="boxRef"
      class="wb-modal-box margin-breakdown"
      role="dialog"
      aria-modal="true"
      aria-label="Структура затрат"
      :style="{ transform: `translate(${pos.x}px, ${pos.y}px)` }"
    >
      <div
        class="margin-breakdown__head"
        title="Потяните, чтобы переместить"
        @pointerdown="dragStart"
        @pointermove="dragMove"
        @pointerup="dragEnd"
      >
        <div class="margin-breakdown__titles">
          <span class="margin-breakdown__name" :title="row?.title || ''">{{ title }}</span>
          <span class="margin-breakdown__sub">
            <a v-if="row?.nm_id" :href="`/wb/detail?nm_id=${row.nm_id}`" target="_blank" class="margin-breakdown__wb">WB: {{ row.nm_id }}</a>
            <span v-if="row?.vendor_code"> · {{ row.vendor_code }}</span>
            <span v-if="qty"> · {{ qty }} шт</span>
          </span>
          <span v-if="period" class="margin-breakdown__sub">Период: {{ period }}</span>
        </div>
        <button class="btn btn-sm btn-link margin-breakdown__close" title="Закрыть" @click="$emit('close')">✕</button>
      </div>

      <table class="table table-sm mb-0 margin-breakdown__table">
        <thead>
          <tr>
            <th>Статья</th>
            <th class="text-end">₽</th>
            <th class="text-end margin-breakdown__th-pct">% от выручки</th>
            <th class="text-end">на 1 шт</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in lines" :key="l.key" :class="l.cls">
            <td class="margin-breakdown__label">{{ l.label }}</td>
            <td class="text-end margin-breakdown__val">{{ l.value }}</td>
            <td class="text-end margin-breakdown__pct">{{ l.pct }}</td>
            <td class="text-end margin-breakdown__per">{{ l.per }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'

const props = defineProps<{ open: boolean, row: any, period?: string }>()
const emit = defineEmits<{ close: [] }>()

const { formatTitle } = useMoneyFmt()

const nf0 = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const nf2 = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const title = computed(() => formatTitle(props.row?.title || ''))
const qty = computed(() => Number(props.row?.qnt) || 0)

// База процентов — выручка (брутто, продажи)
const base = computed(() => Number(props.row?.amount) || 0)

const money = (v: number) => nf0.format(Math.round(Number(v) || 0))
const percent = (v: number) => (base.value ? (v / base.value) * 100 : 0)
const pctText = (v: number) => nf2.format(percent(v)) + ' %'
// на 1 реализованный экземпляр (кол-во продаж минус возвраты)
const perText = (v: number) => (qty.value ? nf2.format((Number(v) || 0) / qty.value) : '—')

// НДС выделяется из цены, поэтому его % = ставка в цене без НДС:
//   НДС ÷ (оборот − НДС),  оборот = продажи − возвраты
const netTurnover = computed(() => base.value - (Number(props.row?.return_sum) || 0))
const ndsPct = computed(() => {
  const nds = Number(props.row?.total_nds) || 0
  const den = netTurnover.value - nds
  if (!(den > 0)) return '—'
  return nf2.format((nds / den) * 100) + ' %'
})

type Line = { key: string, label: string, value: string, pct: string, per: string, cls: string }

const lines = computed<Line[]>(() => {
  const r = props.row || {}
  const n = (k: string) => Number(r[k]) || 0

  // В отчёте колонки «Отзывы»/«Реклама»/«Хранение» = ff_otziv / ff_adv / ff_storage_fee
  // (в отчёте по товарам — это ff_*, см. profit_columns.py).
  const otziv = n('f_otziv')
  const adv = n('f_adv')
  const storage = n('f_storage_fee')
  // Итого затрат WB = сумма строк расходного блока
  const wbCosts = n('commission') + n('f_acquiring_fee') + n('f_acceptance') + n('f_delivery')
    + n('f_penalty') + otziv + n('f_cashback') + adv + storage

  const out: Line[] = []
  const add = (key: string, label: string, v: number, cls = '', pct?: string) =>
    out.push({ key, label, value: money(v), pct: pct ?? pctText(v), per: perText(v), cls })

  add('amount', 'Выручка (продажи)', base.value, 'margin-breakdown__row--base')
  add('return', 'Возвраты (вычет)', -n('return_sum'), 'margin-breakdown__row--info')

  add('commission', 'Комиссия WB', n('commission'))
  add('f_acquiring_fee', 'Эквайринг', n('f_acquiring_fee'))
  add('f_acceptance', 'Приёмка', n('f_acceptance'))
  add('f_delivery', 'Логистика (доставка)', n('f_delivery'))
  add('f_storage_fee', 'Хранение', storage)
  add('f_penalty', 'Штрафы', n('f_penalty'))
  add('f_otziv', 'Отзывы', otziv)
  add('f_cashback', 'Кэшбек', n('f_cashback'))
  add('f_adv', 'Реклама (кампании)', adv)
  add('wb_costs', 'Итого затрат WB', wbCosts, 'margin-breakdown__row--total')

  add('net_profit', 'Итого', n('net_profit'), 'margin-breakdown__row--subtotal')
  add('total_nds', 'НДС', n('total_nds'), '', ndsPct.value)
  add('total_cost', 'Себестоимость', n('total_cost'))

  add('profit_before_tax', 'Прибыль до налога', n('profit_before_tax'), 'margin-breakdown__row--profit')
  add('tax_amount', 'Налог на прибыль 7 %', n('tax_amount'))
  add('clean_margin', 'Маржа', n('clean_margin'), 'margin-breakdown__row--profit')

  return out
})

const onEsc = (e: KeyboardEvent) => {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onEsc))
onUnmounted(() => window.removeEventListener('keydown', onEsc))

// Перетаскивание модалки за шапку (pointer events — как в NewsBlock.vue/NewCards.vue)
const boxRef = ref<HTMLElement | null>(null)
const pos = ref({ x: 0, y: 0 })
const dragging = ref(false)
let dragX = 0
let dragY = 0
let origX = 0
let origY = 0

// не даём утащить за пределы экрана (8px от края)
function clamp(x: number, y: number) {
  const el = boxRef.value
  if (!el) return { x, y }
  const w = el.offsetWidth
  const h = el.offsetHeight
  const vw = window.innerWidth
  const vh = window.innerHeight
  const baseLeft = (vw - w) / 2
  const baseTop = (vh - h) / 2
  let nx = x
  let ny = y
  if (baseLeft + nx < 8) nx = 8 - baseLeft
  if (baseLeft + nx + w > vw - 8) nx = vw - 8 - w - baseLeft
  if (baseTop + ny < 8) ny = 8 - baseTop
  if (baseTop + ny + h > vh - 8) ny = vh - 8 - h - baseTop
  return { x: nx, y: ny }
}

function dragStart(e: PointerEvent) {
  if (e.button !== 0) return
  const t = e.target as HTMLElement
  if (t && t.closest('button, a')) return
  dragging.value = true
  dragX = e.clientX
  dragY = e.clientY
  origX = pos.value.x
  origY = pos.value.y
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
}

function dragMove(e: PointerEvent) {
  if (!dragging.value) return
  pos.value = clamp(origX + (e.clientX - dragX), origY + (e.clientY - dragY))
}

function dragEnd(e: PointerEvent) {
  if (!dragging.value) return
  dragging.value = false
  try { (e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId) } catch { /* noop */ }
}
</script>

<style scoped>
/* z-index — глобальный .wb-modal-backdrop его не имеет, попап иначе уйдёт под навбар */
.wb-modal-backdrop { z-index: 1050; }
.margin-breakdown { min-width: 420px; max-width: 560px; }
.margin-breakdown__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; cursor: move; touch-action: none; user-select: none; }
.margin-breakdown__titles { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.margin-breakdown__name { font-size: 13px; font-weight: 700; color: #111827; line-height: 1.25; }
.margin-breakdown__sub { font-size: 11px; color: #6b7280; }
.margin-breakdown__wb { color: #2980b9; text-decoration: none; }
.margin-breakdown__wb:hover { text-decoration: underline; }
.margin-breakdown__close { text-decoration: none; font-size: 14px; }
.margin-breakdown__table { font-size: 12px; }
.margin-breakdown__table thead th { font-size: 10.5px; text-transform: uppercase; letter-spacing: .03em; color: #9ca3af; border-bottom: 1px solid #e5e7eb; padding: 4px 6px; }
.margin-breakdown__table tbody td { padding: 3px 6px; vertical-align: middle; }
.margin-breakdown__label { color: #374151; }
.margin-breakdown__val { white-space: nowrap; }
.margin-breakdown__per { white-space: nowrap; color: #6b7280; }
.margin-breakdown__th-pct, .margin-breakdown__pct { background-color: #fdebd0; }
.margin-breakdown__pct { white-space: nowrap; }
.margin-breakdown__row--base td { font-weight: 700; border-bottom: 1px solid #e5e7eb; }
.margin-breakdown__row--info td { color: #9ca3af; }
.margin-breakdown__row--total td { font-weight: 700; border-top: 1px solid #e5e7eb; background-color: #f8fafc; }
.margin-breakdown__row--subtotal td { font-weight: 700; background-color: #eef4fb; border-top: 1px solid #dbe7f3; border-bottom: 2px solid #b9d2ea; }
.margin-breakdown__row--profit td { font-weight: 700; background-color: #eaf6ef; }
</style>
