<template>
  <!-- Срез оборачиваемости: дефицит / нет в наличии / излишки.
       Формулы — 1в1 из Yii2 (WbStockController::actionAnalytics). -->
  <div class="tbl-card tbl-card--compact">
    <div class="card__hd">
      <span>{{ title }}</span>
      <span class="hd-badge">{{ total }}</span>
      <span class="spacer"></span>
      <ExcelButton :disabled="!rows.length" @click="exportExcel" />
    </div>

    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th class="t-left">Товар</th>
            <template v-if="variant === 'out_of_stock'">
              <th>Потенциал, ед/день</th>
              <th>Продано, шт</th>
              <th>Продано, ₽</th>
              <th>Ср. цена, ₽</th>
              <th>Упущено, ₽/день</th>
            </template>
            <template v-else>
              <th>Остаток, шт</th>
              <th>Остаток, ₽</th>
              <template v-if="variant === 'deficit'">
                <th>Продано, шт</th>
                <th>Продано, ₽</th>
                <th>Скорость, ед/день</th>
              </template>
              <th>Дней до 0</th>
              <template v-if="variant === 'excess'">
                <th>Продано, шт</th>
                <th>Продажи, ₽</th>
              </template>
              <th class="t-center">Статус</th>
            </template>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in visible" :key="r.nm_id">
            <td class="t-left">
              <ProductCell
                :photo="r.photos"
                :title="r.title"
                :sub="r.brand"
                :vendor="r.vendor_code"
                :link="'/wb/detail?nm_id=' + r.nm_id"
                :link-label="'WB: ' + r.nm_id"
              />
            </td>
            <template v-if="variant === 'out_of_stock'">
              <td class="num">{{ fmt2(r.speed) }}</td>
              <td class="num">{{ fmt0(r.sold_qty) }}</td>
              <td class="num">{{ fmtMoney(r.sold_money) }}</td>
              <td class="num">{{ fmtVal(r.price_used, 2) }}</td>
              <td class="num t-neg">{{ fmtMoney(r.lost_per_day) }}</td>
            </template>
            <template v-else>
              <td class="num">{{ fmt0(r.stock) }}</td>
              <td class="num">{{ fmtMoney(r.stock_money) }}</td>
              <template v-if="variant === 'deficit'">
                <td class="num">{{ fmt0(r.sold_qty) }}</td>
                <td class="num">{{ fmtMoney(r.sold_money) }}</td>
                <td class="num">{{ fmt2(r.speed) }}</td>
              </template>
              <td class="num" :class="r.days_left === null ? '' : 't-neg'">
                {{ r.days_left === null ? 'Нет продаж' : fmtVal(r.days_left, 1) }}
              </td>
              <template v-if="variant === 'excess'">
                <td class="num">{{ fmt0(r.sold_qty) }}</td>
                <td class="num">{{ fmtMoney(r.sold_money) }}</td>
              </template>
              <td class="t-center"><span class="badge" :class="statusCls(r)">{{ statusText(r) }}</span></td>
            </template>
          </tr>
          <tr v-if="!rows.length">
            <td class="t-center" :colspan="variant === 'out_of_stock' ? 6 : 7">
              <span class="text-muted">Нет данных за выбранный период</span>
            </td>
          </tr>
        </tbody>
        <tfoot v-if="rows.length">
          <tr class="tbl__total">
            <td class="t-left">Итого</td>
            <template v-if="variant === 'out_of_stock'">
              <td class="num">{{ fmt2(sum('speed')) }}</td>
              <td class="num">{{ fmt0(sum('sold_qty')) }}</td>
              <td class="num">{{ fmtMoney(sum('sold_money')) }}</td>
              <td>—</td>
              <td class="num">{{ fmtMoney(sum('lost_per_day')) }}</td>
            </template>
            <template v-else>
              <td class="num">{{ fmt0(sum('stock')) }}</td>
              <td class="num">{{ fmtMoney(sum('stock_money')) }}</td>
              <template v-if="variant === 'deficit'">
                <td class="num">{{ fmt0(sum('sold_qty')) }}</td>
                <td class="num">{{ fmtMoney(sum('sold_money')) }}</td>
                <td>—</td>
              </template>
              <td>—</td>
              <template v-if="variant === 'excess'">
                <td class="num">{{ fmt0(sum('sold_qty')) }}</td>
                <td class="num">{{ fmtMoney(sum('sold_money')) }}</td>
              </template>
              <td></td>
            </template>
          </tr>
        </tfoot>
      </table>
    </div>

    <div v-if="rows.length > FOLD" class="expand-btn-wrapper page-stock-wb__more">
      <button type="button" class="btn btn--outline btn-sm" @click="expanded = !expanded">
        {{ expanded ? 'Свернуть' : 'Увидеть ещё ' + (rows.length - FOLD) }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ExcelButton from '../common/ExcelButton.vue'
import ProductCell from '../common/ProductCell.vue'
import { useNumFmt } from '@/composables/useNumFmt'
import { exportXlsx } from '@/utils/exportXlsx'

/** Сколько строк показываем до кнопки «Увидеть ещё» (правило темы: длинная таблица свёрнута). */
const FOLD = 10

const props = withDefaults(defineProps<{
  title: string
  /** deficit | out_of_stock | excess */
  variant: 'deficit' | 'out_of_stock' | 'excess'
  rows: any[]
  total?: number
  dateFrom?: string
  dateTo?: string
}>(), { total: 0, dateFrom: '', dateTo: '' })

const { fmt0, fmt2, fmtVal, fmtMoney } = useNumFmt()
const expanded = ref(false)

const visible = computed(() => (expanded.value ? props.rows : props.rows.slice(0, FOLD)))

watch(() => props.rows, () => { expanded.value = false })

const sum = (k: string) => props.rows.reduce((a, r) => a + (Number(r[k]) || 0), 0)

function statusText(r: any): string {
  if (props.variant === 'out_of_stock') return 'Нет в наличии'
  if (props.variant === 'excess') return r.speed > 0 ? 'Излишек' : 'Нет продаж'
  return (r.days_left ?? 99) <= 3 ? 'Критично' : 'Скоро'
}

function statusCls(r: any): string {
  if (props.variant === 'out_of_stock') return 'badge--bad'
  if (props.variant === 'excess') return r.speed > 0 ? 'badge--info' : 'badge--neutral'
  return (r.days_left ?? 99) <= 3 ? 'badge--bad' : 'badge--warn'
}

const exportExcel = async () => {
  if (!props.rows.length) return
  const head: Record<string, string> = props.variant === 'out_of_stock'
    ? {
      'Арт WB': 'nm_id', 'Товар': 'title', 'Бренд': 'brand', 'Артикул': 'vendor_code',
      'Потенциал, ед/день': 'speed', 'Продано, шт': 'sold_qty', 'Продано, ₽': 'sold_money',
      'Ср. цена, ₽': 'price_used', 'Упущено, ₽/день': 'lost_per_day',
    }
    : props.variant === 'deficit'
      ? {
        'Арт WB': 'nm_id', 'Товар': 'title', 'Бренд': 'brand', 'Артикул': 'vendor_code',
        'Остаток, шт': 'stock', 'Остаток, ₽': 'stock_money', 'Продано, шт': 'sold_qty',
        'Продано, ₽': 'sold_money', 'Скорость, ед/день': 'speed', 'Дней до 0': 'days_left',
      }
      : {
        'Арт WB': 'nm_id', 'Товар': 'title', 'Бренд': 'brand', 'Артикул': 'vendor_code',
        'Остаток, шт': 'stock', 'Остаток, ₽': 'stock_money', 'Хватит на (дней)': 'days_left',
        'Продано, шт': 'sold_qty', 'Продажи, ₽': 'sold_money',
      }
  const data = props.rows.map((r: any) => {
    const o: Record<string, any> = {}
    for (const [title, key] of Object.entries(head)) {
      const v = r[key]
      o[title] = v === null || v === undefined ? '' : v
    }
    return o
  })
  await exportXlsx({
    rows: data,
    filename: `analiz-ostatkov_${props.variant}_${props.dateFrom}_${props.dateTo}.xlsx`,
    sheetName: props.title.slice(0, 30),
    cols: Object.keys(head).map(() => ({ wch: 16 })),
  })
}
</script>
