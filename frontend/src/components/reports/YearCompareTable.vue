<template>
  <div class="tbl-card">
    <div class="card__hd">
      <span>{{ title }}</span>
      <span v-if="badge" class="hd-badge">{{ badge }}</span>
      <span class="spacer"></span>
      <PngExportGroup
        v-if="showPng"
        :title="pngTitle"
        :subtitle="pngSubtitle"
        :filters="pngFilters"
      />
      <ExcelButton v-if="showExcel" :disabled="!rowCount" @click="$emit('excel')" />
    </div>
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th rowspan="2" class="t-left col-first">
              {{ kind === 'top' ? 'Товар' : 'Отчётный период' }}
            </th>
            <!-- год — по центру своей группы; полоса отделяет группы -->
            <th
              v-for="y in years"
              :key="y"
              :colspan="colsPerYear"
              class="t-center grp-start"
            >{{ y }}</th>
          </tr>
          <tr>
            <template v-for="y in years" :key="y">
              <th
                v-for="(lbl, j) in subLabels"
                :key="`${y}-${lbl}`"
                :class="{ 'grp-start': j === 0 }"
                :title="hintFor(lbl)"
              >{{ lbl }}</th>
            </template>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rowCount">
            <td :colspan="totalCols" class="text-center text-muted py-3">Нет данных</td>
          </tr>

          <!-- Таблица месяцев -->
          <tr v-for="m in kind === 'months' ? months : []" :key="`m${m.m}`">
            <td class="t-left col-first">{{ m.name }}</td>
            <template v-for="y in years" :key="y">
              <template v-for="(v, j) in monthCells(m, y)" :key="`${y}-${j}`">
                <td class="num" :class="{ 'grp-start': j === 0 }">{{ v }}</td>
              </template>
            </template>
          </tr>

          <!-- ТОП товаров -->
          <tr v-for="r in visibleRows" :key="`r${r.nm_id}`">
            <td class="t-left">
              <ProductCell
                :photo="r.photos"
                :title="r.title"
                :sub="subLine(r)"
                :vendor="r.vendor_code"
                :link="cardUrl(r.nm_id)"
                :link-label="'WB: ' + r.nm_id"
              />
            </td>
            <template v-for="y in years" :key="y">
              <template v-for="(v, j) in topCells(r, y)" :key="`${y}-${j}`">
                <td class="num" :class="{ 'grp-start': j === 0 }">{{ v }}</td>
              </template>
            </template>
          </tr>
        </tbody>
        <tfoot v-if="rowCount">
          <tr class="tbl__total">
            <td class="t-left col-first">Итого</td>
            <template v-for="y in years" :key="y">
              <template v-for="(v, j) in totalCells(y)" :key="`${y}-${j}`">
                <td class="num" :class="{ 'grp-start': j === 0 }">{{ v }}</td>
              </template>
            </template>
          </tr>
        </tfoot>
      </table>
    </div>
    <!-- Свёрнутая таблица: показываем 10 строк, дальше — «Увидеть ещё N»
         (механизм как в stock-wb/TurnoverTable.vue) -->
    <div v-if="kind === 'top' && rows.length > FOLD" class="expand-btn-wrapper page-year-compare__more">
      <button type="button" class="btn btn--outline btn-sm" @click="expanded = !expanded">
        {{ expanded ? 'Свернуть' : 'Увидеть ещё ' + (rows.length - FOLD) }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Таблица сравнения по годам — две разновидности:
 *  * kind='months' — месячная сетка (месяц × годы: кол-во, сумма[, возвраты]);
 *  * kind='top'    — ТОП товаров (товар × годы: кол-во, сумма[, возвраты], средняя цена).
 *
 * Кол-во и сумма — NET (продажи минус возвраты); возвраты отдельной колонкой
 * (hasReturns) — на вкладке «Продажи». На вкладке «Заказы» возвратов в кубе нет,
 * поэтому колонки нет.
 *
 * Оформление:
 *  * год — по центру своей группы, группы разделены вертикальной полосой
 *    (`.grp-start` → border-left, первая колонка каждой группы);
 *  * подзаголовки колонок и значения — по правому краю, числа с классом `num`
 *    (nowrap — «1 234 567 ₽» не разваливается на две строки);
 *  * НУЛЬ НЕ ВЫВОДИМ (в т.ч. в строке «Итого»): ячейка пустая — ноль здесь
 *    означает «данных за этот год/месяц не было», а не «продали за ноль»
 *    (см. `fmtCell`); ненулевые значения, включая отрицательные NET-суммы, — как есть;
 *  * итоги — снизу (`.tbl__total`), по всем строкам, не по видимым;
 *  * карточка товара — общий компонент `ProductCell` (как на остальных страницах);
 *  * в ТОП-таблице строк больше 10 — свёрнуты, кнопка «Увидеть ещё N».
 */
import { computed, ref, watch } from 'vue'
import { useNumFmt } from '@/composables/useNumFmt'
import ExcelButton from '@/components/common/ExcelButton.vue'
import PngExportGroup from '@/components/common/PngExportGroup.vue'
import ProductCell from '@/components/common/ProductCell.vue'

const props = withDefaults(defineProps<{
  kind: 'months' | 'top'
  years: number[]
  months?: any[]
  rows?: any[]
  title?: string
  badge?: string
  showExcel?: boolean
  /** Показывать кнопку выгрузки в PNG. */
  showPng?: boolean
  /** Название отчёта для шапки картинки. */
  pngTitle?: string
  /** Подзаголовок шапки картинки: вкладка/срез. */
  pngSubtitle?: string
  /** Фильтры для шапки картинки. */
  pngFilters?: { label: string; value: string }[]
  /** Показывать колонку «Возвраты» (вкладка «Продажи»; в «Заказах» возвратов нет). */
  hasReturns?: boolean
  /** Подсказки к колонкам (что именно считается) — из meta.source отчёта. */
  qtyHint?: string
  amountHint?: string
  returnsHint?: string
  priceHint?: string
}>(), {
  months: () => [], rows: () => [], title: '', badge: '', showExcel: false, showPng: false,
  pngTitle: '', pngSubtitle: '', pngFilters: () => [], hasReturns: false,
  qtyHint: '', amountHint: '', returnsHint: '', priceHint: '',
})

defineEmits<{ (e: 'excel'): void }>()

const { fmt0, fmt2 } = useNumFmt()

/** Деньги с копейками: «118 656,75 ₽» — как в /wb-sales-analysis. */
const fmtMoney2 = (v: any): string => fmt2(v) + ' ₽'

/**
 * Ячейка таблицы: значение 0 НЕ выводим — пустая ячейка вместо «0»/«0,00 ₽».
 *
 * Ноль в этих таблицах означает «данных за этот год/месяц не было»
 * (строки ТОП склеиваются по годам, отсутствующий год = нули), а не
 * «продали за ноль». Пустая ячейка читается однозначнее.
 * Отрицательные значения (NET меньше нуля из-за возвратов) показываются как есть.
 */
const fmtCell = (v: any, fmt: (v: any) => string): string => {
  const n = Number(v) || 0
  return n === 0 ? '' : fmt(n)
}

/** Сколько строк показываем до «Увидеть ещё». */
const FOLD = 10
const expanded = ref(false)
watch(() => props.rows, () => { expanded.value = false })

const subLabels = computed(() => {
  if (props.kind !== 'top') {
    return props.hasReturns ? ['Кол-во', 'Сумма', 'Возвраты'] : ['Кол-во', 'Сумма']
  }
  return props.hasReturns
    ? ['Кол-во', 'Сумма', 'Возвраты', 'Ср. цена']
    : ['Кол-во', 'Сумма', 'Ср. цена']
})
const colsPerYear = computed(() => {
  if (props.kind !== 'top') return props.hasReturns ? 3 : 2
  return props.hasReturns ? 4 : 3
})

/** Подсказка к подзаголовку колонки — что именно считается. */
const hintFor = (lbl: string): string | undefined => {
  if (lbl === 'Кол-во') return props.qtyHint || undefined
  if (lbl === 'Сумма') return props.amountHint || undefined
  if (lbl === 'Возвраты') return props.returnsHint || undefined
  if (lbl === 'Ср. цена') return props.priceHint || undefined
  return undefined
}

const rowCount = computed(() => (props.kind === 'top' ? props.rows.length : props.months.length))
const totalCols = computed(() => 1 + props.years.length * colsPerYear.value)

/** Строки ТОП-таблицы: свёрнуты до FOLD, пока не нажали «Увидеть ещё». */
const visibleRows = computed(() => {
  if (props.kind !== 'top' || expanded.value) return props.rows
  return props.rows.slice(0, FOLD)
})

const cardUrl = (nmId: number) => `/wb/detail/?nm_id=${nmId}`

/** Подпись под названием товара: предмет и бренд одной строкой (как на остальных страницах). */
const subLine = (r: any) => {
  const subject = String(r.subject || '')
  const brand = String(r.brand || '')
  if (subject && brand) return subject + ' • ' + brand
  return subject || brand
}

const monthCells = (m: any, y: number): string[] => {
  const cells = [fmtCell(m[`qty_${y}`], fmt0), fmtCell(m[`amount_${y}`], fmtMoney2)]
  if (props.hasReturns) cells.push(fmtCell(m[`returns_qty_${y}`], fmt0))
  return cells
}

const topCells = (r: any, y: number): string[] => {
  const cells = [fmtCell(r[`qty_${y}`], fmt0), fmtCell(r[`amount_${y}`], fmtMoney2)]
  if (props.hasReturns) cells.push(fmtCell(r[`returns_qty_${y}`], fmt0))
  cells.push(fmtCell(r[`avg_price_${y}`], fmtMoney2))
  return cells
}

const totals = computed(() => {
  const out: Record<string, number> = {}
  const rows = props.kind === 'top' ? props.rows : props.months
  for (const y of props.years) {
    let q = 0
    let a = 0
    let rq = 0
    for (const r of rows) {
      q += Number(r[`qty_${y}`] || 0)
      a += Number(r[`amount_${y}`] || 0)
      rq += Number(r[`returns_qty_${y}`] || 0)
    }
    out[`qty_${y}`] = q
    out[`amount_${y}`] = a
    out[`returns_qty_${y}`] = rq
  }
  return out
})

const totalCells = (y: number): string[] => {
  const cells = [
    fmtCell(totals.value[`qty_${y}`], fmt0),
    fmtCell(totals.value[`amount_${y}`], fmtMoney2),
  ]
  if (props.hasReturns) cells.push(fmtCell(totals.value[`returns_qty_${y}`], fmt0))
  if (props.kind === 'top') cells.push('—')
  return cells
}

/**
 * Описание карточки для варианта «Карточка» — заглушка.
 *
 * Вариант скрыт в интерфейсе (решение 2026-11-02): выбирать нечего,
 * поэтому блок выгрузки в PNG состоит из кнопок «PNG» и «Копировать».
 * Движок отрисовки карточки остался в `utils/exportPng.ts` (`renderCardPng`),
 * вместе с `kpiChangeNote` — чтобы вернуть вариант можно было без новой
 * отрисовки с нуля.
 */
</script>

<style scoped>
/* Вертикальная полоса в начале каждой группы лет — без неё не видно,
   какая колонка к какому году. Ставится на первую колонку группы. */
.grp-start { border-left: 1px solid var(--line-strong); }

/* Ширины колонок заданы явно: в auto-layout ширины делятся по содержимому,
   и первая группа (2024) получалась заметно шире остальных.
   Год-заголовок (colspan) ширины не получает — он занимает обе колонки группы. */
.tbl th.col-first, .tbl td.col-first { width: 280px; }
.tbl thead tr:nth-child(2) th:not(.col-first),
.tbl tbody td:not(.col-first),
.tbl tfoot td:not(.col-first) { width: 110px; }
</style>
