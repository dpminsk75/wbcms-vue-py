<template>
  <div class="tbl-wrap margin-table__wrap" ref="wrapRef">
    <table ref="tableRef" class="tbl margin-table" :class="{ 'margin-table--compact': compact }">
      <thead>
        <tr>
          <th class="margin-table__th--num">#</th>
          <th class="t-left margin-table__th--product">Линейка</th>
          <th class="num">Карточек</th>
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
        </tr>
      </thead>
      <tbody>
        <tr v-if="!rows.length">
          <td colspan="23" class="text-center p-4 text-muted">Нет данных за выбранный период</td>
        </tr>
        <template v-for="(r, i) in rows" :key="r.product_id">
          <tr>
            <td class="margin-table__pos">
              <span class="margin-table__num">{{ i + 1 }}</span>
              <button
                class="margin-table__eye"
                :title="expanded === r.product_id ? 'Скрыть состав' : 'Состав линейки'"
                @click.stop="toggle(r)"
              >
                <i :class="expanded === r.product_id ? 'bi bi-chevron-up' : 'bi bi-chevron-down'"></i>
              </button>
            </td>
            <td class="t-left margin-table__cell-product">
              <div class="margin-table__order-text">
                <div class="margin-table__title" :title="r.product_name || ''">{{ r.product_name || '—' }}</div>
                <div class="margin-table__details">
                  <span v-if="r.product_type">{{ r.product_type }}</span>
                  <span v-if="r.product_type && r.brand"> • </span>
                  <span v-if="r.brand">{{ r.brand }}</span>
                </div>
                <div class="margin-table__details">
                  <span class="margin-table__cost-badge" :class="costBadgeClass(r)">{{ costBadgeText(r) }}</span>
                  <i
                    v-if="r.p_incomplete"
                    class="bi bi-exclamation-triangle margin-table__warn ms-1"
                    title="Сумма долей (p) по этой карточке в линейке не равна 100 — доли нормализованы"
                  ></i>
                </div>
              </div>
            </td>
            <td class="num">{{ r.cards_count }}</td>
            <td class="num">{{ fmt0(r.qnt) }}</td>
            <td class="num">{{ fmt0(r.amount) }}</td>
            <td class="num t-neg">{{ fmt0(r.commission) }}</td>
            <td class="num t-neg">{{ fmt0(r.f_acquiring_fee) }}</td>
            <td class="num t-neg">{{ fmt0(r.f_acceptance) }}</td>
            <td class="num t-neg">{{ fmt0(r.f_delivery) }}</td>
            <td class="num t-neg">{{ fmt0(r.f_storage_fee) }}</td>
            <td class="num t-neg">{{ fmt0(r.f_penalty) }}</td>
            <td class="num t-pos">{{ fmt0(r.f_otziv) }}</td>
            <td class="num">{{ fmt0(r.f_adv) }}</td>
            <td class="num t-neg">{{ fmt0(r.f_cashback) }}</td>
            <td class="num" :class="r.net_profit < 0 ? 't-neg' : 't-pos'">{{ fmt0(r.net_profit) }}</td>
            <td class="num">{{ fmt0(r.total_nds) }}</td>
            <td class="num">
              {{ fmt0(r.total_cost) }}
              <i
                v-if="r.no_cost"
                class="bi bi-question-circle margin-table__warn"
                title="Себестоимость не посчитана: нет ни ручной цены линейки, ни закупочной цены карточек"
              ></i>
            </td>
            <td class="num" :class="r.profit_before_tax < 0 ? 't-neg' : ''">{{ fmt0(r.profit_before_tax) }}</td>
            <td class="num t-neg">{{ fmt0(r.tax_amount) }}</td>
            <td class="num" :class="r.clean_margin < 0 ? 't-neg' : 't-pos'">{{ fmt0(r.clean_margin) }}</td>
            <td class="num margin-table__per-item">{{ fmt2(r.amount_per_item) }}</td>
            <td class="num margin-table__per-item" :class="r.profit_per_item < 0 ? 't-neg' : 't-pos'">{{ fmt2(r.profit_per_item) }}</td>
            <td class="num margin-table__per-item" :class="r.clear_per_item < 0 ? 't-neg' : 't-pos'">{{ fmt2(r.clear_per_item) }}</td>
          </tr>
          <!-- состав линейки -->
          <tr v-if="expanded === r.product_id" class="margin-table__cards-row">
            <td colspan="23" class="margin-table__cards-cell">
              <div v-if="cardsLoading" class="text-muted p-2">Загрузка состава…</div>
              <div v-else-if="!cards.length" class="text-muted p-2">Состав не задан</div>
              <table v-else class="tbl margin-table__cards">
                <thead>
                  <tr>
                    <th class="t-left">Арт WB</th>
                    <th class="t-left">Наименование</th>
                    <th class="t-left">Артикул</th>
                    <th class="num">q, шт</th>
                    <th class="num">p, %</th>
                    <th class="num">p норм., %</th>
                    <th class="num">Закупка/шт</th>
                    <th class="num">Вклад в себ-ть</th>
                    <th class="num">Кол-во</th>
                    <th class="num">Выручка</th>
                    <th class="num">Итого</th>
                    <th class="num">НДС</th>
                    <th class="num">Прибыль</th>
                    <th class="num">Маржа</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="c in cards" :key="c.nm_id">
                    <td class="t-left"><a :href="`/wb/detail?nm_id=${c.nm_id}`" target="_blank" class="margin-table__wb-link">{{ c.nm_id }}</a></td>
                    <td class="t-left" :title="c.title || ''">{{ c.title || '—' }}</td>
                    <td class="t-left">{{ c.vendor_code || '' }}</td>
                    <td class="num">{{ c.q }}</td>
                    <td class="num">
                      {{ c.p }}
                      <i
                        v-if="Math.abs(c.p_sum - 100) > 0.01"
                        class="bi bi-exclamation-triangle margin-table__warn"
                        :title="`Сумма долей по карточке в линейках = ${c.p_sum}% (норма 100) — доли нормализованы`"
                      ></i>
                    </td>
                    <td class="num">{{ fmt2(c.p_norm) }}</td>
                    <td class="num">{{ fmt2(c.cost_price) }}</td>
                    <td class="num">{{ fmt2(c.cost_contribution) }}</td>
                    <td class="num">{{ fmt0(c.qnt) }}</td>
                    <td class="num">{{ fmt0(c.amount) }}</td>
                    <td class="num">{{ fmt0(c.net_profit) }}</td>
                    <td class="num">{{ fmt0(c.total_nds) }}</td>
                    <td class="num">{{ fmt0(c.profit_before_tax) }}</td>
                    <td class="num" :class="c.clean_margin < 0 ? 't-neg' : 't-pos'">{{ fmt0(c.clean_margin) }}</td>
                  </tr>
                </tbody>
                <tfoot v-if="cards.length">
                  <tr class="tbl__total">
                    <td colspan="7" class="t-left">Итого по составу</td>
                    <td class="num">{{ fmt2(cardsTotalCost) }}</td>
                    <td class="num">{{ fmt0(sumCards('qnt')) }}</td>
                    <td class="num">{{ fmt0(sumCards('amount')) }}</td>
                    <td class="num">{{ fmt0(sumCards('net_profit')) }}</td>
                    <td class="num">{{ fmt0(sumCards('total_nds')) }}</td>
                    <td class="num">{{ fmt0(sumCards('profit_before_tax')) }}</td>
                    <td class="num">{{ fmt0(sumCards('clean_margin')) }}</td>
                  </tr>
                </tfoot>
              </table>
            </td>
          </tr>
        </template>
      </tbody>
      <tfoot v-if="rows.length">
        <tr class="tbl__total">
          <td colspan="2" class="t-left">{{ footerLabel }}</td>
          <td class="num">{{ totals.cards_count }}</td>
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
        </tr>
      </tfoot>
    </table>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/components/margin-table.css'
import { ref, computed, watch } from 'vue'
import { api } from '@/api/client'
import { useMoneyFmt } from '@/composables/useMoneyFmt'
import type { ProductCardRow, ProductMarginRow } from '@/api/profitProducts'

const props = withDefaults(defineProps<{
  rows: ProductMarginRow[]
  totals: ProductMarginRow
  footerLabel: string
  dateFrom?: string
  dateTo?: string
  /** Плотный вариант (широкие реестры). */
  compact?: boolean
}>(), { footerLabel: 'Итого:', compact: false })

const { fmt0, fmt2, sumCol } = useMoneyFmt()

const expanded = ref<number | null>(null)
const cards = ref<ProductCardRow[]>([])
const cardsLoading = ref(false)

const cardsTotalCost = computed(() => sumCol(cards.value, 'cost_contribution'))
const sumCards = (k: string) => sumCol(cards.value, k)

const costBadgeText = (r: ProductMarginRow): string => {
  if (r.cost_source === 'manual') return 'себестоимость: вручную'
  if (r.cost_source === 'derived') return 'себестоимость: производная'
  return 'себестоимость: нет'
}
const costBadgeClass = (r: ProductMarginRow): string => {
  if (r.cost_source === 'manual') return 'margin-table__cost-badge--manual'
  if (r.cost_source === 'derived') return 'margin-table__cost-badge--derived'
  return 'margin-table__cost-badge--none'
}

const toggle = async (r: ProductMarginRow) => {
  if (expanded.value === r.product_id) {
    expanded.value = null
    cards.value = []
    return
  }
  expanded.value = r.product_id
  cards.value = []
  cardsLoading.value = true
  try {
    const { data } = await api.get(`/api/wb-profit/products/${r.product_id}/cards`, {
      params: { date_from: props.dateFrom, date_to: props.dateTo },
    })
    cards.value = (data?.rows as ProductCardRow[]) || []
  } catch {
    cards.value = []
  } finally {
    cardsLoading.value = false
  }
}

// при смене периода раскрытый состав сбрасываем (данные устарели)
watch(() => [props.dateFrom, props.dateTo], () => {
  expanded.value = null
  cards.value = []
})
</script>

<style scoped>
/* Общие правила таблиц маржи — вынесены в assets/css/components/margin-table.css
   (общие для MarginTable и ProductMarginTable, чтобы не дублировать):
   плотные отступы, первая колонка (номер + шеврон), тоны колонок, правая
   крайняя колонка, потолок ширины колонки линейки.
   Здесь — только то, что есть в этой таблице. */
.margin-table__th--product { width: 240px; min-width: 220px; }
.margin-table__order-text { display: flex; flex-direction: column; gap: 2px; }
.margin-table__title { font-weight: 700; font-size: calc(12.5px * var(--fs)); }
.margin-table__details { font-size: calc(10.5px * var(--fs)); color: var(--ink-muted); }
.margin-table__wb-link { font-weight: 700; color: var(--brand); text-decoration: none; }
.margin-table__wb-link:hover { color: var(--brand-hover); text-decoration: underline; }
.margin-table__warn { color: var(--warn); }

/* Бейдж источника себестоимости */
.margin-table__cost-badge { display: inline-block; padding: 1px 5px; border-radius: 8px; font-size: 9px; line-height: 1.4; }
.margin-table__cost-badge--manual { background: var(--info-tint); color: var(--info-deep); }
.margin-table__cost-badge--derived { background: var(--good-tint); color: var(--good-deep); }
.margin-table__cost-badge--none { background: var(--bad-tint); color: var(--bad-deep); }

/* Раскрытый состав линейки — плотная вложенная таблица */
.margin-table__cards-row > .margin-table__cards-cell { background: var(--surface-2); padding: 8px 10px; white-space: normal; }
.margin-table__cards th { padding: 4px 6px; font-size: calc(10px * var(--fs)); }
.margin-table__cards td { padding: 3px 6px; font-size: calc(11px * var(--fs)); }

/* Плотный вариант (широкие реестры) */
.margin-table--compact .margin-table__title { font-size: calc(11px * var(--fs)); }
.margin-table--compact .margin-table__details { font-size: calc(10px * var(--fs)); }
.margin-table--compact .margin-table__cost-badge { font-size: 8.5px; }
</style>
