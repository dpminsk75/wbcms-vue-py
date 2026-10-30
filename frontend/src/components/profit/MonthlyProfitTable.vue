<template>
  <div v-if="busy || allRows.length || isError">
    <!-- Выбор годов (общий с «Год к году», в URL) — слева, ДО таблицы -->
    <div class="d-flex justify-content-start mb-2">
      <YearPicker :available="availableYears" :model-value="appliedYears" @apply="onApply" />
    </div>

    <div class="tbl-card tbl-card--compact page-wb-profit__block">
      <div class="card__hd">
        <span>Финансовая аналитика (с 2025 года)</span>
        <span class="spacer"></span>
        <span class="hd-badge">{{ rows.length }} мес.</span>
      </div>
      <div v-if="isLoading" class="text-center p-4 text-muted">
        <span class="spinner-border spinner-border-sm"></span> Загрузка финансовой аналитики...
      </div>
      <div v-else class="tbl-wrap">
        <table class="tbl page-wb-profit__monthly">
          <thead>
            <tr>
              <th class="t-center">Месяц</th>
              <th class="num">Кол-во</th>
              <th class="num">Продажи</th>
              <th class="num">Ком. WB</th>
              <th class="num">Эквайринг</th>
              <th class="num">Приёмка</th>
              <th class="num">Логистика</th>
              <th class="num">Хранение</th>
              <th class="num">Штрафы</th>
              <th class="num">Удержан.</th>
              <th class="num">Отзывы</th>
              <th class="num">Реклама</th>
              <th class="num">Кэшбек</th>
              <th class="num page-wb-profit__monthly-net">Общий итог</th>
              <th class="num">НДС</th>
              <th class="num">Себ-ть</th>
              <th class="num page-wb-profit__monthly-profit">Прибыль</th>
              <th class="num">Налог 7%</th>
              <th class="num page-wb-profit__monthly-margin">Маржа</th>
            </tr>
          </thead>
          <tbody>
            <!-- Итого -->
            <tr class="tbl__total tbl__total--top">
              <td class="t-center">Итого</td>
              <td class="num">{{ fmt0(totals.qnt) }}</td>
              <td class="num">{{ fmt0(totals.amount) }}</td>
              <td class="num">{{ fmt0(totals.commission) }}</td>
              <td class="num">{{ fmt0(totals.f_acquiring_fee) }}</td>
              <td class="num">{{ fmt0(totals.f_acceptance) }}</td>
              <td class="num">{{ fmt0(totals.f_delivery) }}</td>
              <td class="num">{{ fmt0(totals.f_storage_fee) }}</td>
              <td class="num">{{ fmt0(totals.f_penalty) }}</td>
              <td class="num">{{ fmt0(totals.f_deduction) }}</td>
              <td class="num">{{ fmt0(totals.f_otziv) }}</td>
              <td class="num">{{ fmt0(totals.f_adv) }}</td>
              <td class="num">{{ fmt0(totals.f_cashback) }}</td>
              <td class="num">{{ fmt0(totals.net_profit) }}</td>
              <td class="num">{{ fmt0(totals.total_nds) }}</td>
              <td class="num">{{ fmt0(totals.total_cost) }}</td>
              <td class="num">{{ fmt0(totals.profit_before_tax) }}</td>
              <td class="num">{{ fmt0(totals.tax_amount) }}</td>
              <td class="num">{{ fmt0(totals.clean_margin) }}</td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="19" class="text-center text-muted py-3">Нет данных за выбранные годы</td>
            </tr>
            <tr v-for="r in rows" :key="r.month">
              <td class="t-center page-wb-profit__monthly-month">{{ r.month }}</td>
              <td class="num">{{ fmt0(r.qnt) }}</td>
              <td class="num">{{ fmt0(r.amount) }}</td>
              <td class="num t-neg">{{ fmt0(r.commission) }}</td>
              <td class="num t-neg">{{ fmt0(r.f_acquiring_fee) }}</td>
              <td class="num t-neg">
                <button v-if="num(r.f_acceptance)" class="wb-cell-link" title="Детализация приёмки" @click="openPop('acceptance', r.month)">{{ fmt0(r.f_acceptance) }}</button>
                <template v-else>{{ fmt0(r.f_acceptance) }}</template>
              </td>
              <td class="num t-neg">
                <button v-if="num(r.f_delivery)" class="wb-cell-link" title="Детализация логистики" @click="openCell('delivery', r.month)">{{ fmt0(r.f_delivery) }}</button>
                <template v-else>{{ fmt0(r.f_delivery) }}</template>
              </td>
              <td class="num t-neg">
                <button v-if="num(r.f_storage_fee)" class="wb-cell-link" title="Детализация хранения" @click="openPop('storage', r.month)">{{ fmt0(r.f_storage_fee) }}</button>
                <template v-else>{{ fmt0(r.f_storage_fee) }}</template>
              </td>
              <td class="num t-neg">
                <button v-if="num(r.f_penalty)" class="wb-cell-link" title="Детализация штрафов" @click="openPop('shf', r.month)">{{ fmt0(r.f_penalty) }}</button>
                <template v-else>{{ fmt0(r.f_penalty) }}</template>
              </td>
              <td class="num t-neg">
                <button v-if="num(r.f_deduction)" class="wb-cell-link" title="Детализация удержаний" @click="openPop('udr', r.month)">{{ fmt0(r.f_deduction) }}</button>
                <template v-else>{{ fmt0(r.f_deduction) }}</template>
              </td>
              <td class="num t-pos">
                <button v-if="num(r.f_otziv)" class="wb-cell-link" title="Детализация отзывов" @click="openPop('feedback', r.month)">{{ fmt0(r.f_otziv) }}</button>
                <template v-else>{{ fmt0(r.f_otziv) }}</template>
              </td>
              <td class="num">
                <button v-if="num(r.f_adv)" class="wb-cell-link" title="Детализация рекламы" @click="openPop('adv', r.month)">{{ fmt0(r.f_adv) }}</button>
                <template v-else>{{ fmt0(r.f_adv) }}</template>
              </td>
              <td class="num t-neg">
                <button v-if="num(r.f_cashback)" class="wb-cell-link" title="Детализация кэшбека" @click="openCell('cashback', r.month)">{{ fmt0(r.f_cashback) }}</button>
                <template v-else>{{ fmt0(r.f_cashback) }}</template>
              </td>
              <td class="num" :class="r.net_profit < 0 ? 't-neg' : 't-pos'">{{ fmt0(r.net_profit) }}</td>
              <td class="num">{{ fmt0(r.total_nds) }}</td>
              <td class="num">{{ fmt0(r.total_cost) }}</td>
              <td class="num" :class="r.profit_before_tax < 0 ? 't-neg' : ''">{{ fmt0(r.profit_before_tax) }}</td>
              <td class="num t-neg">{{ fmt0(r.tax_amount) }}</td>
              <td class="num" :class="r.clean_margin < 0 ? 't-neg' : 't-pos'">{{ fmt0(r.clean_margin) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <FinancePopup v-if="finPop" :kind="finPop.kind" :date-from="finPop.dateFrom" :date-to="finPop.dateTo" @close="finPop = null" />
    <MarginBreakdownModal
      v-if="cellModal"
      :kind="cellModal.kind"
      basis="month"
      :date-from="cellModal.dateFrom"
      :date-to="cellModal.dateTo"
      :detail="0"
      @close="cellModal = null"
    />
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import { useSelectedYears } from '@/composables/useSelectedYears'
import FinancePopup, { type FinancePopupKind } from '../dashboard/FinancePopup.vue'
import MarginBreakdownModal from './MarginBreakdownModal.vue'
import YearPicker from '@/components/common/YearPicker.vue'
import type { MarginKind } from '@/api/margin'
const emit = defineEmits<{ report: [ok: boolean] }>()
const auth = useAuthStore()
// Без initialData: isLoading=true до первых данных — виден спиннер загрузки.
const { data: rowsRaw, isLoading, isFetching, isError } = useQuery({ queryKey: computed(() => ['monthly-finance', auth.companyId] as const), queryFn: ()=> (dashboardApi as any).monthly() })
const busy = computed(() => isLoading.value || isFetching.value)
const allRows = computed(()=> (rowsRaw.value as any[]) ?? [])

// --- выбор годов (общий с «Год к году», состояние — в URL) ---------------
const { hasParam, selectedYears, setYears } = useSelectedYears()
const availableYears = computed(() => {
  const s = new Set<number>()
  for (const r of allRows.value) {
    const y = Number(String(r.month || '').slice(0, 4))
    if (y) s.add(y)
  }
  return [...s].sort((a, b) => a - b)
})
const appliedYears = computed<number[]>(() => {
  const avail = availableYears.value
  if (!hasParam.value) return avail
  return avail.filter(y => selectedYears.value.includes(y))
})
const onApply = (list: number[]) => setYears(list)

// Строки только выбранных годов; «Итого» считается по ним (totals ниже).
const rows = computed(() => {
  const sel = appliedYears.value
  if (!sel.length) return allRows.value
  return allRows.value.filter((r: any) => sel.includes(Number(String(r.month || '').slice(0, 4))))
})
const totals = computed(()=>{
  const sum = (k:string)=> rows.value.reduce((s:number,r:any)=> s + (Number(r[k])||0), 0)
  return {
    qnt: sum('qnt'), amount: sum('amount'), commission: sum('commission'),
    f_acquiring_fee: sum('f_acquiring_fee'), f_acceptance: sum('f_acceptance'),
    f_delivery: sum('f_delivery'), f_storage_fee: sum('f_storage_fee'),
    f_penalty: sum('f_penalty'), f_deduction: sum('f_deduction'),
    f_otziv: sum('f_otziv'), f_adv: sum('f_adv'), f_cashback: sum('f_cashback'),
    net_profit: sum('net_profit'), total_nds: sum('total_nds'), total_cost: sum('total_cost'),
    profit_before_tax: sum('profit_before_tax'), tax_amount: sum('tax_amount'), clean_margin: sum('clean_margin'),
  }
})
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const num = (v:any)=> Number(v) || 0
// Попапы детализации (порт trigger-detail-popup/trigger-feedback-popup из Yii2).
// Период попапа — месяц строки, как в PHP ($model['month'] . '-01' … конец месяца).
const finPop = ref<{ kind: FinancePopupKind, dateFrom: string, dateTo: string } | null>(null)
const monthEnd = (month: string) => {
  const m = /^(\d{4})-(\d{2})$/.exec(month || '')
  if (!m) return month
  return `${month}-${String(new Date(Number(m[1]), Number(m[2]), 0).getDate()).padStart(2, '0')}`
}
const openPop = (kind: FinancePopupKind, month: string) => {
  finPop.value = { kind, dateFrom: `${month}-01`, dateTo: monthEnd(month) }
}
// Единая модалка-расшифровка (пока только «по дням» — без товара детализация не нужна).
const cellModal = ref<{ kind: MarginKind, dateFrom: string, dateTo: string } | null>(null)
const openCell = (kind: MarginKind, month: string) => {
  cellModal.value = { kind, dateFrom: `${month}-01`, dateTo: monthEnd(month) }
}
const hasData = computed(() => rows.value.length > 0)
watchEffect(() => { if (!busy.value) emit('report', hasData.value || !!isError.value) })
</script>
<style scoped>
/* Таблица широкая (19 колонок) — плотные горизонтальные отступы,
   чтобы укладываться в контейнер 1320px с запасом. */
.page-wb-profit__monthly.tbl td { padding-left: 4px; padding-right: 4px; }
.page-wb-profit__monthly.tbl thead th { padding-left: 5px; padding-right: 5px; }
/* Тон колонок — на токенах (не легаси-жёлтый/зелёный) */
.page-wb-profit__monthly-net { background: color-mix(in srgb, var(--info) 8%, transparent); }
.page-wb-profit__monthly-profit { background: color-mix(in srgb, var(--warn) 10%, transparent); }
.page-wb-profit__monthly-margin { background: color-mix(in srgb, var(--good) 10%, transparent); }
.page-wb-profit__monthly-month { font-weight: 700; }
</style>
