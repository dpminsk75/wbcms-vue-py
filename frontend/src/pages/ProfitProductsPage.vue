<template>
  <div class="container-xxl page-wb-profit">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">{{ $route.meta.title || 'Маржа по продуктам' }}</h1>
      <div class="d-flex gap-2 align-items-center">
        <span class="hd-badge">{{ period }}</span>
        <ExcelButton :disabled="!rows.length" @click="exportExcel" />
      </div>
    </div>

    <div class="tbl-card tbl-card--compact page-wb-profit__block">
      <div class="card__hd">
        <span><i class="bi bi-box-seam me-2"></i>Маржа по линейкам (продуктам)</span>
      </div>
      <div class="page-wb-profit__filter">
        <WbDateRangeFilter v-model:from="from" v-model:to="to" default-preset="30" bare />
        <div class="wb-filter-panel__btns">
          <button class="btn btn--brand wb-filter-panel__apply" @click="onApply">Применить</button>
          <button class="btn btn--outline wb-filter-panel__apply" @click="onReset">Сбросить</button>
        </div>
      </div>

      <!-- предупреждения -->
      <div v-if="warnings.length" class="page-wb-profit__warnings">
        <div v-for="w in warnings" :key="w.text" class="alert alert-warning py-2 px-3 mb-2 small">
          <i class="bi bi-exclamation-triangle me-1"></i>{{ w.text }}
        </div>
      </div>

      <div v-if="loading" class="text-center p-4 text-muted">
        <span class="spinner-border spinner-border-sm"></span> Загрузка данных...
      </div>
      <ProductMarginTable
        v-else
        :rows="rows"
        :totals="totals"
        footer-label="Итого по линейкам:"
        :date-from="from"
        :date-to="to"
        compact
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-profit.css'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'
import { useMoneyFmt } from '@/composables/useMoneyFmt'
import type { ProductMarginResponse, ProductMarginRow } from '@/api/profitProducts'
import ProductMarginTable from '@/components/profit/ProductMarginTable.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import WbDateRangeFilter from '@/components/common/WbDateRangeFilter.vue'

const route = useRoute()
const router = useRouter()
const { fmt0, sumCol } = useMoneyFmt()

// локальное время (toISOString даёт UTC и сдвигает сутки)
// дефолт — 30 суток (как пресет «30 дней»)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const lastDays = (n: number): [string, string] => {
  const to = new Date()
  const from = new Date(to)
  from.setDate(from.getDate() - (n - 1))
  return [fmtD(from), fmtD(to)]
}
const [defFrom, defTo] = lastDays(30)

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const qDate = (v: unknown): string => {
  const s = Array.isArray(v) ? String(v[0] ?? '') : String(v ?? '')
  return DATE_RE.test(s) ? s : ''
}

const from = ref(qDate(route.query.date_from) || defFrom)
const to = ref(qDate(route.query.date_to) || defTo)
// applied — период, по которому реально запрошены данные (запрос — по кнопке «Применить»)
const applied = ref({ from: from.value, to: to.value })

const onApply = () => {
  applied.value = { from: from.value, to: to.value }
  router.replace({ path: route.path, query: { ...route.query, date_from: from.value, date_to: to.value } })
}
const onReset = () => {
  from.value = defFrom
  to.value = defTo
  onApply()
}

watch(() => [route.query.date_from, route.query.date_to], () => {
  const f = qDate(route.query.date_from) || defFrom
  const t = qDate(route.query.date_to) || defTo
  if (f !== from.value) from.value = f
  if (t !== to.value) to.value = t
})

const { data, isLoading: loading } = useQuery({
  queryKey: computed(() => ['wb-profit-products', applied.value.from, applied.value.to] as const),
  queryFn: () => api.get('/api/wb-profit/products', {
    params: { date_from: applied.value.from, date_to: applied.value.to },
  }).then(r => r.data as ProductMarginResponse),
})

const rows = computed<ProductMarginRow[]>(() => (data.value?.rows as ProductMarginRow[]) || [])

const period = computed(() => {
  const f = String(data.value?.date_from || applied.value.from)
  const t = String(data.value?.date_to || applied.value.to)
  return f && t ? `${f} — ${t}` : ''
})

// итоговая строка (тот же набор колонок, что и у строк)
const totals = computed<ProductMarginRow>(() => {
  const src = (data.value?.totals || {}) as any
  const out: any = { ...src }
  for (const k of [
    'qnt', 'amount', 'commission', 'f_acquiring_fee', 'f_acceptance', 'f_delivery',
    'f_storage_fee', 'f_penalty', 'f_deduction', 'f_otziv', 'f_adv', 'f_cashback',
    'net_profit', 'total_nds', 'total_cost', 'profit_before_tax', 'tax_amount', 'clean_margin',
  ]) {
    out[k] = src[k] !== undefined ? Number(src[k]) : sumCol(rows.value, k)
  }
  out.cards_count = src.cards_count ?? rows.value.length
  return out as ProductMarginRow
})

const warnings = computed(() => {
  const w = data.value?.warnings
  if (!w) return [] as { text: string }[]
  const list: { text: string }[] = []
  if (w.duplicated_cards > 0) {
    list.push({
      text: `${w.duplicated_cards} карточек входят сразу в несколько линеек — их выручка посчитана в отчёте несколько раз (${fmt0(w.duplicated_amount)} ₽).`
        + ' Выручка берётся по карточкам без весов — так же, как в отчёте по карточкам.',
    })
  }
  if (w.p_incomplete_cards > 0) {
    list.push({
      text: `У ${w.p_incomplete_cards} карточек сумма долей в линейках не равна 100% — доли нормализованы (p_norm = p / сумма p).`,
    })
  }
  if (w.products_without_cost > 0) {
    list.push({
      text: `У ${w.products_without_cost} линеек нет себестоимости: ни ручной цены, ни закупочной цены карточек — маржа по ним завышена.`,
    })
  }
  return list
})

const exportExcel = async () => {
  if (!rows.value.length) return
  const { default: XLSX } = await import('xlsx')
  const data2 = rows.value.map((r, i) => ({
    '#': i + 1,
    'Линейка': r.product_name,
    'Тип': r.product_type,
    'Бренд': r.brand,
    'Карточек': r.cards_count,
    'Кол-во': r.qnt,
    'Выручка': r.amount,
    'Ком. WB': r.commission,
    'Экв.': r.f_acquiring_fee,
    'Приёмка': r.f_acceptance,
    'Лог-ка': r.f_delivery,
    'Хранение': r.f_storage_fee,
    'Штрафы': r.f_penalty,
    'Отзывы': r.f_otziv,
    'Реклама': r.f_adv,
    'Кэшбек': r.f_cashback,
    'Итого': r.net_profit,
    'НДС': r.total_nds,
    'Себ-ть': r.total_cost,
    'Источник себ-ти': r.cost_source === 'manual' ? 'вручную' : (r.cost_source === 'derived' ? 'производная' : 'нет'),
    'Прибыль': r.profit_before_tax,
    'Налог 7%': r.tax_amount,
    'Маржа': r.clean_margin,
    'Цена/шт': r.amount_per_item,
    'Итог/шт': r.profit_per_item,
    'Маржа/шт': r.clear_per_item,
  }))
  const t = totals.value
  data2.push({
    '#': '', 'Линейка': 'ИТОГО', 'Тип': '', 'Бренд': '', 'Карточек': t.cards_count,
    'Кол-во': t.qnt, 'Выручка': t.amount, 'Ком. WB': t.commission, 'Экв.': t.f_acquiring_fee,
    'Приёмка': t.f_acceptance, 'Лог-ка': t.f_delivery, 'Хранение': t.f_storage_fee,
    'Штрафы': t.f_penalty, 'Отзывы': t.f_otziv, 'Реклама': t.f_adv, 'Кэшбек': t.f_cashback,
    'Итого': t.net_profit, 'НДС': t.total_nds, 'Себ-ть': t.total_cost, 'Источник себ-ти': '',
    'Прибыль': t.profit_before_tax, 'Налог 7%': t.tax_amount, 'Маржа': t.clean_margin,
    'Цена/шт': null, 'Итог/шт': null, 'Маржа/шт': null,
  } as any)
  const ws = XLSX.utils.json_to_sheet(data2)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Маржа по линейкам')
  XLSX.writeFile(wb, `wb-profit_products_${applied.value.from}_${applied.value.to}.xlsx`)
}
</script>
