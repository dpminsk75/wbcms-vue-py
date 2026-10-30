<template>
  <!-- Вкладка «По складам»: спрос по складам (FBO/FBS) + ТОП товаров по остатку. -->
  <div class="tbl-card">
    <div class="card__hd">
      <span>Спрос по складам: кто продаёт</span>
      <span class="hd-badge">{{ warehouses.length }}</span>
      <span class="spacer"></span>
      <ExcelButton :disabled="!warehouses.length" @click="exportWarehouses" />
    </div>
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th class="t-left">Склад</th>
            <th class="t-center">Тип</th>
            <th>Продажи, шт</th>
            <th>Продажи, ₽</th>
            <th>Доля</th>
            <th>Товаров</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in warehouses" :key="w.name">
            <td class="t-left">{{ w.name }}</td>
            <td class="t-center"><span class="badge" :class="kindCls(w.kind)">{{ kindText(w.kind) }}</span></td>
            <td class="num">{{ fmt0(w.qty) }}</td>
            <td class="num">{{ fmtMoney(w.money) }}</td>
            <td class="num">{{ fmtPct(w.share, 0) }}</td>
            <td class="num">{{ fmt0(w.nm_cnt) }}</td>
          </tr>
          <tr v-if="!warehouses.length">
            <td class="t-center" colspan="6"><span class="text-muted">Нет данных за выбранный период</span></td>
          </tr>
        </tbody>
        <tfoot v-if="warehouses.length">
          <tr class="tbl__total">
            <td class="t-left">Итого</td>
            <td></td>
            <td class="num">{{ fmt0(total.qty) }}</td>
            <td class="num">{{ fmtMoney(total.money) }}</td>
            <td class="num">100 %</td>
            <td class="num">{{ fmt0(total.nm_cnt) }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
    <p class="page-stock-wb__card-note">
      Склад — это <code>office_name</code> из финансовой детализации: «Склад WB» = FBO (обслуживается остатками складов WB),
      «Склад поставщика — везу на склад WB» = FBS (продавец везёт сам, остатки складов WB его не касаются).
      Складов меньше 20 — не группируем; больше 20 — опция «ТОП-20 / Все».
    </p>
  </div>

  <div class="tbl-card tbl-card--compact mt-3">
    <div class="card__hd">
      <span>ТОП-{{ topLimit }} товаров по остатку на складах WB</span>
      <span class="hd-badge">{{ topTotal }}</span>
      <span class="spacer"></span>
      <ExcelButton :disabled="!topRows.length" @click="exportTop" />
    </div>
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th class="t-left">Товар</th>
            <th>Остаток WB, шт</th>
            <th>Остаток, ₽</th>
            <th>Продажи FBO, шт</th>
            <th>Продажи FBS, шт</th>
            <th>Скорость, ед/день</th>
            <th class="t-center">Дней до 0</th>
            <th class="t-center">Статус</th>
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
            <td class="num">{{ fmt0(r.stock) }}</td>
            <td class="num">{{ fmtMoney(r.stock_money) }}</td>
            <td class="num">{{ fmt0(r.fbo_qty) }}</td>
            <td class="num">{{ fmt0(r.fbs_qty) }}</td>
            <td class="num">{{ fmt2(r.speed) }}</td>
            <td class="num" :class="r.days_left === null ? '' : 't-neg'">
              {{ r.days_left === null ? '—' : fmtVal(r.days_left, 0) }}
            </td>
            <td class="t-center"><span class="badge" :class="statusCls(r)">{{ statusText(r) }}</span></td>
          </tr>
          <tr v-if="!topRows.length">
            <td class="t-center" colspan="8"><span class="text-muted">Нет данных за выбранный период</span></td>
          </tr>
        </tbody>
        <tfoot v-if="topRows.length">
          <tr class="tbl__total">
            <td class="t-left">Итого</td>
            <td class="num">{{ fmt0(sum('stock')) }}</td>
            <td class="num">{{ fmtMoney(sum('stock_money')) }}</td>
            <td class="num">{{ fmt0(sum('fbo_qty')) }}</td>
            <td class="num">{{ fmt0(sum('fbs_qty')) }}</td>
            <td>—</td>
            <td>—</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
    <div v-if="topRows.length > FOLD" class="expand-btn-wrapper page-stock-wb__more">
      <button type="button" class="btn btn--outline btn-sm" @click="expanded = !expanded">
        {{ expanded ? 'Свернуть' : 'Увидеть ещё ' + (topRows.length - FOLD) }}
      </button>
    </div>
    <p class="page-stock-wb__card-note">
      Разбивки остатков по складам WB в данных нет: WB отдаёт остатки одной строкой «Склад WB»,
      поэтому остаток в таблице — общий по складам WB, а по складам показан спрос.
      Бейдж «Только FBS» — товар продаётся лишь со своего склада, на складах WB его нет.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ExcelButton from '../common/ExcelButton.vue'
import ProductCell from '../common/ProductCell.vue'
import { useNumFmt } from '@/composables/useNumFmt'
import { exportXlsx } from '@/utils/exportXlsx'

const FOLD = 10

const props = withDefaults(defineProps<{
  warehouses: any[]
  total: Record<string, any>
  topRows: any[]
  topTotal?: number
  topLimit?: number
  dateFrom?: string
  dateTo?: string
}>(), { topTotal: 0, topLimit: 50, dateFrom: '', dateTo: '' })

const { fmt0, fmt2, fmtVal, fmtMoney, fmtPct } = useNumFmt()
const expanded = ref(false)
const visible = computed(() => (expanded.value ? props.topRows : props.topRows.slice(0, FOLD)))

watch(() => props.topRows, () => { expanded.value = false })

const sum = (k: string) => props.topRows.reduce((a, r) => a + (Number(r[k]) || 0), 0)

function kindText(kind: string): string {
  return kind === 'fbo' ? 'FBO' : kind === 'fbs' ? 'FBS' : 'Прочее'
}
function kindCls(kind: string): string {
  return kind === 'fbo' ? 'badge--ok' : kind === 'fbs' ? 'badge--info' : 'badge--neutral'
}
function statusText(r: any): string {
  if (r.status === 'out_of_stock') return r.fbs_qty > 0 ? 'Только FBS' : 'Нет в наличии'
  if (r.status === 'critical') return 'Критично'
  if (r.status === 'excess') return 'Излишек'
  if (r.status === 'no_sales') return 'Нет продаж'
  return 'Норма'
}
function statusCls(r: any): string {
  if (r.status === 'out_of_stock') return 'badge--bad'
  if (r.status === 'critical') return 'badge--bad'
  if (r.status === 'excess') return 'badge--info'
  if (r.status === 'no_sales') return 'badge--neutral'
  return 'badge--ok'
}

const exportWarehouses = async () => {
  if (!props.warehouses.length) return
  await exportXlsx({
    rows: props.warehouses.map((w: any) => ({
      'Склад': w.name, 'Тип': kindText(w.kind), 'Продажи, шт': w.qty,
      'Продажи, ₽': w.money, 'Доля, %': w.share, 'Товаров': w.nm_cnt,
    })),
    filename: `analiz-ostatkov_sklady_${props.dateFrom}_${props.dateTo}.xlsx`,
    sheetName: 'Склады',
    cols: [{ wch: 42 }, { wch: 8 }, { wch: 12 }, { wch: 14 }, { wch: 9 }, { wch: 10 }],
  })
}

const exportTop = async () => {
  if (!props.topRows.length) return
  await exportXlsx({
    rows: props.topRows.map((r: any) => ({
      'Арт WB': r.nm_id, 'Товар': r.title, 'Бренд': r.brand, 'Артикул': r.vendor_code,
      'Остаток, шт': r.stock, 'Остаток, ₽': r.stock_money,
      'Продажи FBO, шт': r.fbo_qty, 'Продажи FBS, шт': r.fbs_qty,
      'Скорость, ед/день': r.speed, 'Дней до 0': r.days_left, 'Статус': statusText(r),
    })),
    filename: `analiz-ostatkov_top_${props.dateFrom}_${props.dateTo}.xlsx`,
    sheetName: 'ТОП по остатку',
    cols: [{ wch: 12 }, { wch: 40 }, { wch: 14 }, { wch: 14 }, { wch: 11 }, { wch: 14 },
      { wch: 13 }, { wch: 13 }, { wch: 15 }, { wch: 11 }, { wch: 14 }],
  })
}
</script>
