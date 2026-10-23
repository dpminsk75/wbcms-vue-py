<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box margin-breakdown" role="dialog" aria-modal="true" aria-label="Структура затрат">
      <div class="margin-breakdown__head">
        <div class="margin-breakdown__titles">
          <span class="margin-breakdown__name" :title="row?.title || ''">{{ title }}</span>
          <span class="margin-breakdown__sub">
            <a v-if="row?.nm_id" :href="`/wb/detail?nm_id=${row.nm_id}`" target="_blank" class="margin-breakdown__wb">WB: {{ row.nm_id }}</a>
            <span v-if="row?.vendor_code"> · {{ row.vendor_code }}</span>
            <span v-if="qty"> · {{ qty }} шт</span>
          </span>
        </div>
        <button class="btn btn-sm btn-link margin-breakdown__close" title="Закрыть" @click="$emit('close')">✕</button>
      </div>

      <table class="table table-sm mb-0 margin-breakdown__table">
        <thead>
          <tr>
            <th>Статья</th>
            <th class="text-end">₽</th>
            <th class="text-end margin-breakdown__th-pct">% от выручки</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in lines" :key="l.key" :class="l.cls">
            <td class="margin-breakdown__label">{{ l.label }}</td>
            <td class="text-end margin-breakdown__val">{{ l.value }}</td>
            <td class="text-end margin-breakdown__pct">{{ l.pct }}</td>
          </tr>
        </tbody>
      </table>

      <div class="margin-breakdown__note">
        Проценты — от выручки (продажи). «Удержания WB» — все списания WB (включая отзывы).
        «Реклама (кампании)» и «Хранение (по отчёту WB)» считаются отдельно: в удержания не входят
        и вычитаются из прибыли сверх «Итого затрат WB».
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'

const props = defineProps<{ open: boolean, row: any }>()
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

type Line = { key: string, label: string, value: string, pct: string, cls: string }

const lines = computed<Line[]>(() => {
  const r = props.row || {}
  const n = (k: string) => Number(r[k]) || 0

  // В отчёте колонки «Отзывы»/«Реклама» = ff_otziv / ff_adv:
  //   ff_otziv — списания за отзывы (те же деньги, что агрегатное f_otziv, ⊂ f_deduction ⊂ net_profit);
  //   ff_adv   — расходы на рекламные кампании (другой источник, в f_deduction НЕ входят).
  const otziv = n('f_otziv')
  const adv = n('f_adv')
  const storage = n('f_storage_fee')
  const deductions = n('f_deduction')
  // Затраты WB из выплаты (как считает агрегат): комиссия+эквайринг+приёмка+доставка+штраф+удержания+кэшбек.
  // Хранение (ff_storage_fee) и реклама (ff_adv) — отдельные расходы, в этот список НЕ входят.
  const wbCosts = n('commission') + n('f_acquiring_fee') + n('f_acceptance') + n('f_delivery')
    + n('f_penalty') + deductions + n('f_cashback')

  const out: Line[] = []
  const add = (key: string, label: string, v: number, cls = '') =>
    out.push({ key, label, value: money(v), pct: pctText(v), cls })

  add('amount', 'Выручка (продажи)', base.value, 'margin-breakdown__row--base')
  add('return', 'Возвраты (вычет)', -n('return_sum'), 'margin-breakdown__row--info')

  add('commission', 'Комиссия WB', n('commission'))
  add('f_acquiring_fee', 'Эквайринг', n('f_acquiring_fee'))
  add('f_acceptance', 'Приёмка', n('f_acceptance'))
  add('f_delivery', 'Логистика (доставка)', n('f_delivery'))
  add('f_penalty', 'Штрафы', n('f_penalty'))
  add('f_deduction', 'Удержания WB (все)', deductions)
  add('f_cashback', 'Кэшбек', n('f_cashback'))
  add('wb_costs', 'Итого затрат WB', wbCosts, 'margin-breakdown__row--total')

  add('f_otziv', '⊂ Отзывы (в удержаниях)', otziv, 'margin-breakdown__row--info')
  add('f_adv', 'Реклама (кампании, отдельно)', adv)
  add('f_storage_fee', 'Хранение (по отчёту WB, отдельно)', storage)

  add('total_nds', 'НДС', n('total_nds'))
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
</script>

<style scoped>
/* z-index — глобальный .wb-modal-backdrop его не имеет, попап иначе уйдёт под навбар */
.wb-modal-backdrop { z-index: 1050; }
.margin-breakdown { min-width: 420px; max-width: 560px; }
.margin-breakdown__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
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
.margin-breakdown__th-pct, .margin-breakdown__pct { background-color: #fdebd0; }
.margin-breakdown__pct { white-space: nowrap; }
.margin-breakdown__row--base td { font-weight: 700; border-bottom: 1px solid #e5e7eb; }
.margin-breakdown__row--info td { color: #9ca3af; }
.margin-breakdown__row--total td { font-weight: 700; border-top: 1px solid #e5e7eb; background-color: #f8fafc; }
.margin-breakdown__row--profit td { font-weight: 700; background-color: #eaf6ef; }
.margin-breakdown__note { font-size: 10.5px; color: #9ca3af; line-height: 1.35; }
</style>
