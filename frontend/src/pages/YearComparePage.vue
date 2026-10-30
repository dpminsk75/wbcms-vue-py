<template>
  <div class="container-xxl page-year-compare">
    <!-- Шапка + закладки (тема: .wsp + .stab--line) -->
    <div class="wsp mb-3">
      <div class="wsp__head">
        <h3 class="wsp__title">Сравнение по годам</h3>
      </div>
      <WbSectionTabs :tabs="SUB_TABS" />
    </div>

    <!-- Фильтр: 1 — годы, 2 — товар, 3 — кнопки -->
    <div class="wb-filter-panel">
      <div class="wb-chip-group mb-3">
        <YearPicker
          :available="availableYears"
          :model-value="appliedYears"
          @apply="onApplyYears"
        />
      </div>
      <div class="row">
        <div class="col-12 col-md-5">
          <div class="wb-field">
            <label class="wb-field__label">Товар</label>
            <WbCardSelect v-model:nm-id="nmIdStr" placeholder="nm_id, артикул или часть названия..." />
          </div>
        </div>
      </div>
      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" @click="applyCard">Сформировать</button>
        <button class="btn btn--outline" @click="resetAll">Сбросить</button>
      </div>
    </div>

    <!-- KPI по годам -->
    <div class="grid-3">
      <div
        v-for="(s, i) in summaryYear"
        :key="s.year"
        class="tile"
        :class="i === summaryYear.length - 1 ? 'tile--3' : 'tile--1'"
      >
        <div class="tile__label">{{ tabLabel }} · {{ s.year }}</div>
        <div class="tile__value">{{ fmtMoney(s.amount) }}</div>
        <div class="tile__foot">
          <span v-if="s.change === null" class="tile__delta">база</span>
          <span v-else class="tile__delta" :class="s.change < 0 ? 'tile__delta--down' : ''">
            {{ s.change > 0 ? '+' : '' }}{{ fmt1(s.change) }} %
          </span>
          {{ fmt0(s.qty) }} шт
        </div>
      </div>
    </div>

    <!-- График во всю ширину -->
    <div class="mt-3">
      <YearCompareChart :months="months" :years="years" :title="chartTitle" />
    </div>

    <!-- Сводки: прошлый месяц и текущий месяц (MTD) — рядом, по 50% -->
    <div class="row g-3 mt-0">
      <div class="col-12 col-md-6">
        <div class="tbl-card">
          <div class="card__hd">
            Прошлый месяц · {{ prevMonthName }}
            <span class="hd-badge">целиком</span>
          </div>
          <div class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="t-left">Год</th>
                  <th class="num">Кол-во</th>
                  <th class="num">Сумма</th>
                  <th class="num">Изм. %</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in summaryPrev" :key="`p${s.year}`">
                  <td class="t-left">{{ s.year }}</td>
                  <td class="num">{{ fmt0(s.qty) }}</td>
                  <td class="num">{{ fmtMoney(s.amount) }}</td>
                  <td class="num" :class="s.change === null ? '' : (s.change < 0 ? 't-neg' : 't-pos')">
                    {{ s.change === null ? '—' : `${s.change > 0 ? '+' : ''}${fmt1(s.change)} %` }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="col-12 col-md-6">
        <div class="tbl-card">
          <div class="card__hd">
            Текущий месяц · {{ currMonthName }}
            <span class="hd-badge">с 01 по {{ day }}</span>
          </div>
          <div class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="t-left">Год</th>
                  <th class="num">Кол-во</th>
                  <th class="num">Сумма</th>
                  <th class="num">Изм. %</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in summaryCurr" :key="`c${s.year}`">
                  <td class="t-left">{{ s.year }}</td>
                  <td class="num">{{ fmt0(s.qty) }}</td>
                  <td class="num">{{ fmtMoney(s.amount) }}</td>
                  <td class="num" :class="s.change === null ? '' : (s.change < 0 ? 't-neg' : 't-pos')">
                    {{ s.change === null ? '—' : `${s.change > 0 ? '+' : ''}${fmt1(s.change)} %` }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Таблица месяцев -->
    <div class="mt-3">
      <YearCompareTable
        kind="months"
        :years="years"
        :months="months"
        title="Таблица сравнения по месяцам"
        show-excel
        @excel="exportMonths"
      />
    </div>

    <!-- ТОП товаров: две таблицы одна под другой -->
    <div class="mt-3">
      <YearCompareTable
        kind="top"
        :years="years"
        :rows="topPrev"
        :title="`ТОП за прошлый месяц (${prevMonthName})`"
        :badge="years.join(' / ')"
        show-excel
        @excel="exportTopPrev"
      />
    </div>
    <div class="mt-3">
      <YearCompareTable
        kind="top"
        :years="years"
        :rows="topCurr"
        :title="`ТОП за текущий месяц (${currMonthName}, с 01 по ${day})`"
        badge="MTD"
        show-excel
        @excel="exportTopCurr"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * «Сравнение по годам» — порт Yii2 agg-orders-report/compare + agg-sales-report/compare.
 *
 * Две закладки одного окна:
 *   * «Заказы»  — куб agg_orders_daily_sku (по дате заказа), разбивка по стране заказа;
 *   * «Продажи» — куб agg_sales_daily_sku (по дате продажи), возвраты и «к перечислению».
 *
 * Фильтр по карточке влияет на ВСЕ таблицы и графики; выбор лет — чипами.
 */
import '@/assets/css/pages/page-year-compare.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { reportsApi, type YearCompareResponse } from '@/api/reports'
import { useNumFmt } from '@/composables/useNumFmt'
import { useSelectedYears } from '@/composables/useSelectedYears'
import { exportXlsx } from '@/utils/exportXlsx'
import WbSectionTabs from '@/components/common/WbSectionTabs.vue'
import WbCardSelect from '@/components/common/WbCardSelect.vue'
import YearPicker from '@/components/common/YearPicker.vue'
import YearCompareChart from '@/components/reports/YearCompareChart.vue'
import YearCompareTable from '@/components/reports/YearCompareTable.vue'

const { fmt0, fmt1, fmtMoney } = useNumFmt()
const route = useRoute()

const SUB_TABS = [
  { id: 'orders', label: 'Заказы', to: '/wb-reports/year-compare?tab=orders' },
  { id: 'sales', label: 'Продажи', to: '/wb-reports/year-compare?tab=sales' },
]

const data = ref<YearCompareResponse | null>(null)
const loading = ref(false)

const tab = ref<'orders' | 'sales'>(
  String(route.query.tab || 'orders') === 'sales' ? 'sales' : 'orders',
)
const tabLabel = computed(() => (tab.value === 'orders' ? 'Заказы' : 'Продажи'))
const chartTitle = computed(() =>
  tab.value === 'orders' ? 'Заказы по месяцам' : 'Продажи по месяцам',
)

// --- годы: применённые (URL) + черновик (чипы)
const { hasParam, selectedYears, setYears } = useSelectedYears()
/** Годы с данными. Пока бэк не ответил (или данных нет) — последние 3 календарных,
 *  чтобы чипы выбора были видны сразу, а не после первого ответа. */
const availableYears = computed<number[]>(() => {
  const a = data.value?.available_years || []
  if (a.length) return a
  const y = new Date().getFullYear()
  return [y - 2, y - 1, y]
})
const years = computed<number[]>(() => {
  const avail = availableYears.value
  if (!avail.length) return []
  if (!hasParam.value) return avail
  return avail.filter((y) => selectedYears.value.includes(y))
})

// --- карточка (штатный WbCardSelect: маска с подсказками, строгий nm_id)
const nmId = ref<number | null>(null)
const nmIdStr = computed({
  get: () => (nmId.value ? String(nmId.value) : ''),
  set: (v: string) => { nmId.value = v ? Number(v) : null },
})

const months = computed<any[]>(() => data.value?.months || [])
const summaryPrev = computed<any[]>(() => data.value?.summary_prev || [])
const summaryCurr = computed<any[]>(() => data.value?.summary_curr || [])
const summaryYear = computed<any[]>(() => data.value?.summary_year || [])
const topPrev = computed<any[]>(() => data.value?.top_prev || [])
const topCurr = computed<any[]>(() => data.value?.top_curr || [])
const prevMonthName = computed(() => data.value?.meta?.prev_month?.name || '')
const currMonthName = computed(() => data.value?.meta?.curr_month?.name || '')
const day = computed(() => data.value?.meta?.curr_month?.day || 1)

/** Загрузка с дебаунсом — чтобы «Сформировать» (годы + карточка) не давал два GET. */
let loadTimer: ReturnType<typeof setTimeout> | null = null

const loadNow = async () => {
  loading.value = true
  try {
    data.value = await reportsApi.yearCompare(tab.value, years.value, nmId.value)
  } catch (e) {
    data.value = null
  } finally {
    loading.value = false
  }
}
const load = () => {
  if (loadTimer) clearTimeout(loadTimer)
  loadTimer = setTimeout(loadNow, 120)
}

/** Выбор года применён сразу (чипы работают как переключатель палитры). */
const onApplyYears = (list: number[]) => {
  setYears(list)
}

/** «Сформировать» — перезапросить отчёт с текущей карточкой (выбирается в WbCardSelect). */
const applyCard = () => {
  load()
}
const resetAll = () => {
  nmIdStr.value = ''
  if (availableYears.value.length) setYears([...availableYears.value])
  load()
}

// --- закладка (переход делает WbSectionTabs через router-link — реагируем на маршрут)
watch(() => route.query.tab, (v) => {
  const next = String(v || 'orders') === 'sales' ? 'sales' : 'orders'
  if (next !== tab.value) {
    tab.value = next
    load()
  }
})
// смена набора лет в URL
watch(years, () => load())

// --- Excel
const exportMonths = async () => {
  const rows = months.value.map((m: any) => {
    const row: Record<string, any> = { 'Отчётный период': m.name }
    for (const y of years.value) {
      row[`${y} кол-во`] = m[`qty_${y}`]
      row[`${y} сумма`] = m[`amount_${y}`]
    }
    return row
  })
  await exportXlsx({
    rows,
    filename: `сравнение-по-годам-${tab.value}-месяцы.xlsx`,
    sheetName: 'По месяцам',
    cols: [{ wch: 16 }, ...years.value.flatMap(() => [{ wch: 12 }, { wch: 16 }])],
  })
}

const exportTop = async (list: any[], name: string) => {
  const rows = list.map((r: any) => {
    const row: Record<string, any> = {
      'SKU': r.nm_id,
      'Название': r.title,
      'Бренд': r.brand,
      'Предмет': r.subject,
      'Артикул': r.vendor_code,
    }
    for (const y of years.value) {
      row[`${y} кол-во`] = r[`qty_${y}`]
      row[`${y} сумма`] = r[`amount_${y}`]
      row[`${y} ср. цена`] = r[`avg_price_${y}`]
    }
    return row
  })
  await exportXlsx({
    rows,
    filename: `сравнение-по-годам-${tab.value}-${name}.xlsx`,
    sheetName: 'ТОП товаров',
    cols: [{ wch: 12 }, { wch: 34 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, ...years.value.flatMap(() => [{ wch: 10 }, { wch: 14 }, { wch: 12 }])],
  })
}
const exportTopPrev = () => exportTop(topPrev.value, 'предыдущий-месяц')
const exportTopCurr = () => exportTop(topCurr.value, 'текущий-месяц')

onMounted(load)
</script>
