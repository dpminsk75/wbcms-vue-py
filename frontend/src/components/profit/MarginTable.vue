<template>
  <div class="margin-table__wrap wb-table-wrap" ref="wrapRef">
    <table ref="tableRef" class="table table-bordered table-striped table-hover margin-table">
      <thead>
        <tr>
          <th class="margin-table__th--num">#</th>
          <th class="margin-table__th--product">Товар</th>
          <th>Кол-во</th>
          <th>Выручка</th>
          <th>Ком. WB</th>
          <th>Экв.</th>
          <th>Приёмка</th>
          <th>Лог-ка</th>
          <th>Хранение</th>
          <th>Штрафы</th>
          <th>Отзывы</th>
          <th>Реклама</th>
          <th>Кэшбек</th>
          <th class="margin-table__net-cell">Итого</th>
          <th>НДС</th>
          <th>Себ-ть</th>
          <th class="margin-table__profit-cell">Прибыль</th>
          <th>Налог (7%)</th>
          <th class="margin-table__margin-cell">Маржа</th>
          <th class="margin-table__per-item">Цена</th>
          <th class="margin-table__per-item">Итог/шт</th>
          <th class="margin-table__per-item">Маржа/шт</th>
          <th v-if="showStock" class="margin-table__stock-cell">Остаток</th>
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
          <td class="margin-table__cell-product">
            <div class="margin-table__order-text">
              <div class="margin-table__title" :title="r.title || ''">{{ formatTitle(r.title) }}</div>
              <div class="margin-table__details">{{ r.brand || '' }} • {{ r.vendor_code || '' }}</div>
              <div class="margin-table__details">
                <a :href="`/wb/detail?nm_id=${r.nm_id}`" target="_blank" class="margin-table__wb-link">WB: {{ r.nm_id }}</a>
              </div>
            </div>
          </td>
          <td class="text-center fw-bold">{{ fmt0(r.qnt) }}</td>
          <td class="text-end">{{ fmt0(r.amount) }}</td>
          <td class="text-end text-danger">{{ fmt0(r.commission) }}</td>
          <td class="text-end text-danger">{{ fmt0(r.f_acquiring_fee) }}</td>
          <td class="text-end text-danger">
            <button v-if="num(r.f_acceptance)" class="wb-cell-link" title="Детализация приёмки" @click="openCell('acceptance', r)">{{ fmt0(r.f_acceptance) }}</button>
            <template v-else>{{ fmt0(r.f_acceptance) }}</template>
          </td>
          <td class="text-end text-danger fw-medium">
            <button v-if="num(r.f_delivery)" class="wb-cell-link" title="Детализация логистики" @click="openCell('delivery', r)">{{ fmt0(r.f_delivery) }}</button>
            <template v-else>{{ fmt0(r.f_delivery) }}</template>
          </td>
          <td class="text-end text-danger fw-medium">
            <button v-if="num(r.f_storage_fee)" class="wb-cell-link" title="Детализация хранения" @click="openCell('storage', r)">{{ fmt0(r.f_storage_fee) }}</button>
            <template v-else>{{ fmt0(r.f_storage_fee) }}</template>
          </td>
          <td class="text-end text-danger">
            <button v-if="num(r.f_penalty)" class="wb-cell-link" title="Детализация штрафов" @click="openCell('penalty', r)">{{ fmt0(r.f_penalty) }}</button>
            <template v-else>{{ fmt0(r.f_penalty) }}</template>
          </td>
          <td class="text-end text-success">
            <button v-if="num(r.f_otziv)" class="wb-cell-link" title="Детализация отзывов" @click="openCell('otziv', r)">{{ fmt0(r.f_otziv) }}</button>
            <template v-else>{{ fmt0(r.f_otziv) }}</template>
          </td>
          <td class="text-end text-primary">
            <button v-if="num(r.f_adv)" class="wb-cell-link" title="Детализация рекламы" @click="openCell('adv', r)">{{ fmt0(r.f_adv) }}</button>
            <template v-else>{{ fmt0(r.f_adv) }}</template>
          </td>
          <td class="text-end text-danger">
            <button v-if="num(r.f_cashback)" class="wb-cell-link" title="Детализация кэшбека" @click="openCell('cashback', r)">{{ fmt0(r.f_cashback) }}</button>
            <template v-else>{{ fmt0(r.f_cashback) }}</template>
          </td>
          <td class="text-end fw-bold" :class="r.net_profit < 0 ? 'text-danger' : 'text-success'">{{ fmt0(r.net_profit) }}</td>
          <td class="text-end">{{ fmt0(r.total_nds) }}</td>
          <td class="text-end">{{ fmt0(r.total_cost) }}</td>
          <td class="text-end fw-bold" :class="r.profit_before_tax < 0 ? 'text-danger' : ''">{{ fmt0(r.profit_before_tax) }}</td>
          <td class="text-end margin-table__orange">{{ fmt0(r.tax_amount) }}</td>
          <td class="text-end fw-bold" :class="r.clean_margin < 0 ? 'text-danger' : 'text-success'">{{ fmt0(r.clean_margin) }}</td>
          <td class="text-end margin-table__per-item">{{ fmt2(r.amount_per_item) }}</td>
          <td class="text-end margin-table__per-item fw-bold" :class="r.profit_per_item < 0 ? 'text-danger' : 'text-success'">{{ fmt2(r.profit_per_item) }}</td>
          <td class="text-end margin-table__per-item fw-bold" :class="r.clear_per_item < 0 ? 'text-danger' : 'text-success'">{{ fmt2(r.clear_per_item) }}</td>
          <td v-if="showStock" class="text-end margin-table__stock-cell">{{ fmt0(r.stock || 0) }}</td>
        </tr>
      </tbody>
      <tfoot v-if="rows.length" class="margin-table__total-row">
        <tr>
          <td colspan="2" class="text-center">{{ footerLabel }}</td>
          <td class="text-center">{{ fmt0(totals.qnt) }}</td>
          <td class="text-end">{{ fmt0(totals.amount) }}</td>
          <td class="text-end">{{ fmt0(totals.commission) }}</td>
          <td class="text-end">{{ fmt0(totals.f_acquiring_fee) }}</td>
          <td class="text-end">{{ fmt0(totals.f_acceptance) }}</td>
          <td class="text-end">{{ fmt0(totals.f_delivery) }}</td>
          <td class="text-end">{{ fmt0(totals.f_storage_fee) }}</td>
          <td class="text-end">{{ fmt0(totals.f_penalty) }}</td>
          <td class="text-end">{{ fmt0(totals.f_otziv) }}</td>
          <td class="text-end">{{ fmt0(totals.f_adv) }}</td>
          <td class="text-end">{{ fmt0(totals.f_cashback) }}</td>
          <td class="text-end" :class="totals.net_profit < 0 ? 'text-danger' : 'text-success'">{{ fmt0(totals.net_profit) }}</td>
          <td class="text-end">{{ fmt0(totals.total_nds) }}</td>
          <td class="text-end">{{ fmt0(totals.total_cost) }}</td>
          <td class="text-end" :class="totals.profit_before_tax < 0 ? 'text-danger' : ''">{{ fmt0(totals.profit_before_tax) }}</td>
          <td class="text-end">{{ fmt0(totals.tax_amount) }}</td>
          <td class="text-end" :class="totals.clean_margin < 0 ? 'text-danger' : 'text-success'">{{ fmt0(totals.clean_margin) }}</td>
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
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'
import { marginTotals } from '@/api/profit'
import type { MarginKind } from '@/api/margin'
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
}>(), { basis: 'product', detail: 1 })

const { fmt0, fmt2, formatTitle } = useMoneyFmt()
const totals = computed(() => marginTotals(props.rows))

const tableRef = ref<HTMLTableElement | null>(null)
const wrapRef = ref<HTMLDivElement | null>(null)

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

const fit = () => {
  const table = tableRef.value
  if (!table || table.style.tableLayout === 'fixed') return
  table.style.width = '100%'
}

const enableResize = () => {
  const table = tableRef.value
  if (!table) return
  const ths = table.querySelectorAll('th') as NodeListOf<HTMLTableCellElement>
  ths.forEach((th) => {
    if (th.querySelector('.col-resizer')) return
    th.style.position = 'relative'
    const r = document.createElement('div')
    r.className = 'col-resizer'
    r.style.cssText = 'position:absolute; top:0; right:0; width:6px; height:100%; cursor:col-resize; user-select:none; z-index:1'
    th.appendChild(r)
    let startX = 0, startW = 0
    const onMove = (e: MouseEvent) => {
      const w = Math.max(40, startW + e.clientX - startX)
      th.style.width = w + 'px'
      th.style.minWidth = w + 'px'
    }
    const onUp = () => {
      table.style.tableLayout = 'fixed'
      table.style.width = '100%'
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
    }
    r.addEventListener('mousedown', (e: MouseEvent) => {
      startX = e.clientX
      startW = th.offsetWidth
      document.body.style.cursor = 'col-resize'
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
      e.preventDefault()
    })
  })
}

onMounted(() => {
  nextTick(enableResize)
  window.addEventListener('resize', fit)
  fit()
})

watch(() => props.rows, () => {
  nextTick(enableResize)
  fit()
})
</script>

<style scoped>
.margin-table__wrap { overflow-x: auto; border-radius: 8px; border: 1px solid #dee2e6; background: #fff; }
.margin-table { font-size: 12px; margin-bottom: 0; white-space: nowrap; table-layout: auto; width: 100%; }
.margin-table th { background-color: #f8f9fa; font-weight: 500; vertical-align: middle; text-align: center; padding: 8px 4px; font-size: 11px; white-space: normal; word-break: break-word; }
.margin-table td { vertical-align: middle; padding: 4px 3px; font-size: 13px; }
.margin-table__th--num { width: 25px; min-width: 25px; }
/* Позиция+глазик: flex на <td> ломает высоту строки, поэтому глазик — absolute от низа ячейки */
.margin-table td.margin-table__pos { position: relative; vertical-align: top; text-align: center; padding-top: 3px; padding-bottom: 15px; }
.margin-table__num { display: block; line-height: 1.1; }
.margin-table__eye { position: absolute; left: 0; right: 0; bottom: 2px; text-align: center; border: 0; background: transparent; color: #9aa0a8; padding: 0; font-size: 12px; line-height: 1; cursor: pointer; }
.margin-table__eye:hover { color: #8a2be0; }
.margin-table__th--product { width: 280px; min-width: 220px; }
.margin-table__cell-product { max-width: 280px; white-space: normal; word-wrap: break-word; }
.margin-table__order-text { display: flex; flex-direction: column; gap: 2px; }
.margin-table__title { font-weight: 700; font-size: 12px; }
.margin-table__details { font-size: 10px; }
.margin-table__wb-link { font-weight: 700; color: #2980b9; text-decoration: none; }
.margin-table__wb-link:hover { text-decoration: underline; }
.margin-table__total-row { background-color: #f8f9fa; font-weight: 700; }
.margin-table__profit-cell { background-color: #fcf3cf; }
.margin-table__margin-cell { background-color: #d4efdf; }
.margin-table__net-cell { background-color: #e8f8f5; }
.margin-table__per-item { font-style: italic; background-color: #fafafa; }
.margin-table__orange { color: #d35400; }
.margin-table__stock-cell { background-color: #eef4fb; }
</style>
