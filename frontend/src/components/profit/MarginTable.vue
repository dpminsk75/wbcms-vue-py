<template>
  <div class="tbl-wrap margin-table__wrap" ref="wrapRef">
    <table ref="tableRef" class="tbl margin-table">
      <thead>
        <tr>
          <th class="margin-table__th--num">#</th>
          <th class="t-left">Товар</th>
          <th class="num">Кол-во</th>
          <th class="num">Выручка</th>
          <th class="num">Ком. WB</th>
          <th class="num">Экв.</th>
          <th class="num">Приёмка</th>
          <th class="num">Лог-ка</th>
          <th class="num">Хранение</th>
          <th class="num">Штрафы</th>
          <th class="num">Отзывы</th>
          <th class="num">Реклама</th>
          <th class="num">Кэшбек</th>
          <th class="num margin-table__net-cell">Итого</th>
          <th class="num">НДС</th>
          <th class="num">Себ-ть</th>
          <th class="num margin-table__profit-cell">Прибыль</th>
          <th class="num">Налог (7%)</th>
          <th class="num margin-table__margin-cell">Маржа</th>
          <th class="num margin-table__per-item">Цена</th>
          <th class="num margin-table__per-item">Итог/шт</th>
          <th class="num margin-table__per-item">Маржа/шт</th>
          <th v-if="showStock" class="num margin-table__stock-cell">Остаток</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!rows.length">
          <td :colspan="showStock ? 23 : 22" class="text-center p-4 text-muted">Нет данных за выбранный период</td>
        </tr>
        <tr v-for="(r, i) in rows" :key="r.nm_id">
          <td class="margin-table__pos">
            <span class="margin-table__num">{{ i + 1 }}</span>
            <button
              v-if="showBreakdown"
              class="margin-table__eye"
              title="Структура затрат"
              @click.stop="openBreakdown(r)"
            >
              <i class="bi bi-eye"></i>
            </button>
          </td>
          <td class="t-left margin-table__cell-product">
            <ProductCell
              :photo="r.photos"
              :title="r.title"
              :sub="subLine(r)"
              :brand="r.brand"
              :subject="r.subject"
              :vendor="r.vendor_code"
              :link="'/wb/detail?nm_id=' + r.nm_id"
              :link-label="'WB: ' + r.nm_id"
              :compact="compact"
            />
          </td>
          <td class="num">{{ fmt0(r.qnt) }}</td>
          <td class="num">{{ fmt0(r.amount) }}</td>
          <td class="num t-neg">{{ fmt0(r.commission) }}</td>
          <td class="num t-neg">{{ fmt0(r.f_acquiring_fee) }}</td>
          <td class="num t-neg">
            <button v-if="num(r.f_acceptance)" class="wb-cell-link" title="Детализация приёмки" @click="openCell('acceptance', r)">{{ fmt0(r.f_acceptance) }}</button>
            <template v-else>{{ fmt0(r.f_acceptance) }}</template>
          </td>
          <td class="num t-neg">
            <button v-if="num(r.f_delivery)" class="wb-cell-link" title="Детализация логистики" @click="openCell('delivery', r)">{{ fmt0(r.f_delivery) }}</button>
            <template v-else>{{ fmt0(r.f_delivery) }}</template>
          </td>
          <td class="num t-neg">
            <button v-if="num(r.f_storage_fee)" class="wb-cell-link" title="Детализация хранения" @click="openCell('storage', r)">{{ fmt0(r.f_storage_fee) }}</button>
            <template v-else>{{ fmt0(r.f_storage_fee) }}</template>
          </td>
          <td class="num t-neg">
            <button v-if="num(r.f_penalty)" class="wb-cell-link" title="Детализация штрафов" @click="openCell('penalty', r)">{{ fmt0(r.f_penalty) }}</button>
            <template v-else>{{ fmt0(r.f_penalty) }}</template>
          </td>
          <td class="num t-pos">
            <button v-if="num(r.f_otziv)" class="wb-cell-link" title="Детализация отзывов" @click="openCell('otziv', r)">{{ fmt0(r.f_otziv) }}</button>
            <template v-else>{{ fmt0(r.f_otziv) }}</template>
          </td>
          <td class="num">
            <button v-if="num(r.f_adv)" class="wb-cell-link" title="Детализация рекламы" @click="openCell('adv', r)">{{ fmt0(r.f_adv) }}</button>
            <template v-else>{{ fmt0(r.f_adv) }}</template>
          </td>
          <td class="num t-neg">
            <button v-if="num(r.f_cashback)" class="wb-cell-link" title="Детализация кэшбека" @click="openCell('cashback', r)">{{ fmt0(r.f_cashback) }}</button>
            <template v-else>{{ fmt0(r.f_cashback) }}</template>
          </td>
          <td class="num" :class="r.net_profit < 0 ? 't-neg' : 't-pos'">{{ fmt0(r.net_profit) }}</td>
          <td class="num">{{ fmt0(r.total_nds) }}</td>
          <td class="num">{{ fmt0(r.total_cost) }}</td>
          <td class="num" :class="r.profit_before_tax < 0 ? 't-neg' : ''">{{ fmt0(r.profit_before_tax) }}</td>
          <td class="num t-neg">{{ fmt0(r.tax_amount) }}</td>
          <td class="num" :class="r.clean_margin < 0 ? 't-neg' : 't-pos'">{{ fmt0(r.clean_margin) }}</td>
          <td class="num margin-table__per-item">{{ fmt2(r.amount_per_item) }}</td>
          <td class="num margin-table__per-item" :class="r.profit_per_item < 0 ? 't-neg' : 't-pos'">{{ fmt2(r.profit_per_item) }}</td>
          <td class="num margin-table__per-item" :class="r.clear_per_item < 0 ? 't-neg' : 't-pos'">{{ fmt2(r.clear_per_item) }}</td>
          <td v-if="showStock" class="num margin-table__stock-cell">{{ fmt0(r.stock || 0) }}</td>
        </tr>
      </tbody>
      <tfoot v-if="rows.length">
        <tr class="tbl__total">
          <td colspan="2" class="t-left">{{ footerLabel }}</td>
          <td class="num">{{ fmt0(totals.qnt) }}</td>
          <td class="num">{{ fmt0(totals.amount) }}</td>
          <td class="num">{{ fmt0(totals.commission) }}</td>
          <td class="num">{{ fmt0(totals.f_acquiring_fee) }}</td>
          <td class="num">{{ fmt0(totals.f_acceptance) }}</td>
          <td class="num">{{ fmt0(totals.f_delivery) }}</td>
          <td class="num">{{ fmt0(totals.f_storage_fee) }}</td>
          <td class="num">{{ fmt0(totals.f_penalty) }}</td>
          <td class="num">{{ fmt0(totals.f_otziv) }}</td>
          <td class="num">{{ fmt0(totals.f_adv) }}</td>
          <td class="num">{{ fmt0(totals.f_cashback) }}</td>
          <td class="num" :class="totals.net_profit < 0 ? 't-neg' : 't-pos'">{{ fmt0(totals.net_profit) }}</td>
          <td class="num">{{ fmt0(totals.total_nds) }}</td>
          <td class="num">{{ fmt0(totals.total_cost) }}</td>
          <td class="num" :class="totals.profit_before_tax < 0 ? 't-neg' : ''">{{ fmt0(totals.profit_before_tax) }}</td>
          <td class="num">{{ fmt0(totals.tax_amount) }}</td>
          <td class="num" :class="totals.clean_margin < 0 ? 't-neg' : 't-pos'">{{ fmt0(totals.clean_margin) }}</td>
          <td colspan="3"></td>
          <td v-if="showStock"></td>
        </tr>
      </tfoot>
    </table>
  </div>
  <MarginBreakdownPopup v-if="breakdownRow" :open="true" :row="breakdownRow" :period="period" @close="breakdownRow = null" @logistics="onLogistics" />
  <MarginBreakdownModal
    v-if="cellModal"
    :kind="cellModal.kind"
    :basis="basis"
    :date-from="cellModal.dateFrom"
    :date-to="cellModal.dateTo"
    :nm-id="cellModal.nmId"
    :detail="detail"
    @close="cellModal = null"
  />
</template>

<script setup lang="ts">
import '@/assets/css/components/margin-table.css'
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'
import { useTableResize } from '@/composables/useTableResize'
import { marginTotals } from '@/api/profit'
import type { MarginKind } from '@/api/margin'
import ProductCell from '@/components/common/ProductCell.vue'
import MarginBreakdownPopup from './MarginBreakdownPopup.vue'
import MarginBreakdownModal from './MarginBreakdownModal.vue'

const props = withDefaults(defineProps<{
  rows: any[]
  footerLabel: string
  showStock?: boolean
  showBreakdown?: boolean
  period?: string
  dateFrom?: string
  dateTo?: string
  basis?: 'month' | 'product'
  detail?: 0 | 1
  /** Ключ сохранения ширин колонок (у разных страниц — свой). */
  resizeKey?: string
  /** Плотный вариант (широкие реестры): карточка товара — 30×40, одна строка. */
  compact?: boolean
}>(), { basis: 'product', detail: 1, resizeKey: 'profit-margin', compact: false })

const { fmt0, fmt2 } = useMoneyFmt()
const totals = computed(() => marginTotals(props.rows))

const tableRef = ref<HTMLTableElement | null>(null)
const wrapRef = ref<HTMLDivElement | null>(null)

// ресайзер колонок — общий (ширины запоминаются, слушатели снимаются)
useTableResize(tableRef, { storeKey: props.resizeKey })

/** Подпись под названием товара: предмет и бренд одной строкой (как на остальных страницах). */
const subLine = (r: any) => {
  const subject = String(r.subject || '')
  const brandName = String(r.brand || '')
  if (subject && brandName) return subject + ' • ' + brandName
  return subject || brandName
}

// Попап «Структура затрат» по строке (только при showBreakdown)
const breakdownRow = ref<any>(null)
const openBreakdown = (r: any) => { breakdownRow.value = r }

// Модалка-расшифровка значения колонки затрат
const cellModal = ref<{ kind: MarginKind, dateFrom: string, dateTo: string, nmId: number | null } | null>(null)
const num = (v: any) => Number(v) || 0
const splitPeriod = (): { from: string, to: string } => {
  const parts = String(props.period || '').split('—').map(s => s.trim()).filter(Boolean)
  if (parts.length >= 2) return { from: parts[0], to: parts[1] }
  return { from: props.dateFrom || '', to: props.dateTo || '' }
}
const openCell = (kind: MarginKind, r: any) => {
  const p = splitPeriod()
  if (!p.from || !p.to) return
  cellModal.value = { kind, dateFrom: p.from, dateTo: p.to, nmId: r?.nm_id ?? null }
}

// Расшифровка «Логистики» из попапа затрат (период приходит строкой «from — to»)
const onLogistics = (p: { dateFrom: string, dateTo: string }) => {
  const nm = Number(breakdownRow.value?.nm_id) || null
  breakdownRow.value = null
  cellModal.value = { kind: 'delivery', dateFrom: p.dateFrom, dateTo: p.dateTo, nmId: nm }
}
</script>

<style scoped>
/* Общие правила таблиц маржи — вынесены в assets/css/components/margin-table.css
   (общие для MarginTable и ProductMarginTable, чтобы не дублировать):
   плотные отступы, первая колонка (номер + глаз), тоны колонок, правая
   крайняя колонка, ширина колонки товара, отступ фото карточки.
   Здесь — только то, что есть в этой таблице. */
.margin-table__stock-cell { background: color-mix(in srgb, var(--info) 6%, transparent); }
</style>
