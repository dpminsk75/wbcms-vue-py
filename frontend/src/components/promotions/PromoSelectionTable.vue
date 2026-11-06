<template>
  <div class="tbl-card tbl-card--sticky tbl-card--compact page-wb-promotions__card">
    <div class="card__hd">
      <span>{{ title }}</span>
      <span class="hd-badge">{{ filteredCount }}</span>
      <span class="spacer"></span>
      <span class="hd-badge" :title="basisTitle">{{ basis }}</span>
      <span v-if="pages > 1" class="page-wb-promotions__range">{{ rangeText }}</span>
      <span v-if="pages > 1" class="page-wb-promotions__pagesize">
        <label>строк:</label>
        <select class="wb-select page-wb-promotions__pagesize-sel" :value="pageSize" @change="onPageSize">
          <option v-for="n in PAGE_SIZES" :key="n" :value="n">{{ n }}</option>
        </select>
      </span>
      <span v-if="pages > 1" class="page-wb-promotions__pager">
        <button class="page-wb-promotions__pg" :disabled="page <= 1" title="Назад" @click="page = page - 1">‹</button>
        <button
          v-for="p in pageNumbers"
          :key="p"
          class="page-wb-promotions__pg"
          :class="{ 'is-on': p === page }"
          @click="page = p"
        >{{ p }}</button>
        <button class="page-wb-promotions__pg" :disabled="page >= pages" title="Вперёд" @click="page = page + 1">›</button>
      </span>
      <button class="hd-btn" :disabled="!filteredCount" title="Выгрузить таблицу в Excel" @click="$emit('export', filtered)">
        <i class="bi bi-file-earmark-excel me-1"></i>Excel
      </button>
    </div>

    <div v-if="loading" class="page-wb-promotions__loading">
      <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
      <span>Считаем маржу…</span>
    </div>
    <div v-else-if="!rows.length" class="page-wb-promotions__empty">Нет товаров</div>
    <div v-else class="tbl-wrap">
      <table class="tbl page-wb-promotions__table">
        <thead>
          <tr>
            <th class="page-wb-promotions__pick"></th>
            <th class="t-left">Товар</th>
            <th class="t-right">Продано</th>
            <th class="t-right">Ост. WB</th>
            <th class="t-right">Ост. прод.</th>
            <th class="t-right" title="Оборачиваемость, дней">Обор-сть</th>
            <th class="t-right">Цена тек.</th>
            <th class="t-right">Скидка тек.</th>
            <th class="t-right" title="Цена в акции и минимальная цена WB">Цена план.</th>
            <th class="t-right">Скидка план.</th>

            <!-- экономика на единицу при акционной цене -->
            <th class="t-right page-wb-promotions__sep">Выручка</th>
            <th class="t-right">Ком. WB</th>
            <th class="t-right">Эквайринг</th>
            <th class="t-right">Приёмка</th>
            <th class="t-right">Лог-ка</th>
            <th class="t-right">Хранение</th>
            <th v-if="show('include_penalties')" class="t-right">Штрафы</th>
            <th v-if="show('include_reviews')" class="t-right">Отзывы</th>
            <th v-if="show('include_adv')" class="t-right">Реклама</th>
            <th v-if="show('include_cashback')" class="t-right">Кэшбек</th>
            <th class="t-right">Итого</th>
            <th class="t-right">НДС</th>
            <th class="t-right">Себ-ть</th>
            <th class="t-right">Прибыль</th>
            <th class="t-right">Налог</th>
            <!-- маржа: ₽ / % / Δ — одной колонкой в три строки -->
            <th class="t-right page-wb-promotions__sep">Маржа</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="r in pageRows" :key="r.nm_id">
            <!-- выбор: у товара «в акции» птичка стоит и не снимается -->
            <td class="page-wb-promotions__pick">
              <input
                type="checkbox"
                :checked="r.selected"
                :disabled="r.in_action"
                :title="r.in_action ? 'Товар уже участвует в акции' : ''"
                @change="onCheck(r, $event)"
              >
              <span v-if="r.in_action" class="page-wb-promotions__inact">в акции</span>
            </td>
            <td class="t-left">
              <ProductCell
                compact
                :photo="r.photos"
                :title="r.title || ''"
                :vendor="r.vendor_code || ''"
                :brand="r.brand || ''"
                :subject="r.subject || ''"
                :nm-id="r.nm_id"
                :link="'/wb/detail?nm_id=' + r.nm_id"
                :link-label="'WB: ' + r.nm_id"
                copy-nm
                copy-link
              />
              <!-- пометки и причина — под карточкой товара -->
              <div v-if="r.manual && r.selected && !r.recommend" class="page-wb-promotions__marks">
                <span class="page-wb-promotions__mark">добавлено вами</span>
              </div>
              <div v-if="r.reason" class="page-wb-promotions__marks">
                <span class="page-wb-promotions__reason">{{ r.reason }}</span>
              </div>
            </td>
            <td class="t-right num">{{ r.sold_qty }}</td>
            <td class="t-right num">{{ r.stock_wb }}</td>
            <td class="t-right num">{{ r.stock_fbs }}</td>
            <td class="t-right num" :title="r.turnover_days != null ? r.turnover_days + ' дн.' : ''">{{ r.turnover_days != null ? r.turnover_days : '—' }}</td>
            <td class="t-right num">{{ money(r.price_now) }}</td>
            <td class="t-right num">{{ r.discount }} %</td>
            <!-- цена в акции; ниже — минимальная цена WB -->
            <td class="t-right num page-wb-promotions__price">
              <span>
                {{ money(r.price_new) }}
                <i v-if="r.price_mismatch" class="page-wb-promotions__warn" title="Плановая цена WB заметно отличается от «цена × (1 − скидка)» — взята цена WB">?</i>
              </span>
              <template v-if="minOf(r) != null">
                <span class="page-wb-promotions__minlbl">мин</span>
                <span>{{ money(minOf(r)) }}</span>
              </template>
            </td>
            <td class="t-right num">{{ r.plan_discount }} %</td>

            <td class="t-right num page-wb-promotions__sep">{{ money(r.unit.revenue) }}</td>
            <td class="t-right num t-neg">{{ money(r.unit.commission) }}</td>
            <td class="t-right num t-neg">{{ money(r.unit.acquiring) }}</td>
            <td class="t-right num t-neg">{{ money(r.unit.acceptance) }}</td>
            <td class="t-right num t-neg">{{ money(r.unit.delivery) }}</td>
            <td class="t-right num t-neg">{{ money(r.unit.storage) }}</td>
            <td v-if="show('include_penalties')" class="t-right num t-neg">{{ money(r.unit.penalty) }}</td>
            <td v-if="show('include_reviews')" class="t-right num t-neg">{{ money(r.unit.reviews) }}</td>
            <td v-if="show('include_adv')" class="t-right num t-neg">{{ money(r.unit.adv) }}</td>
            <td v-if="show('include_cashback')" class="t-right num t-neg">{{ money(r.unit.cashback) }}</td>
            <td class="t-right num" :class="cls(r.unit.net_profit)">{{ money(r.unit.net_profit) }}</td>
            <td class="t-right num t-neg">{{ money(r.unit.nds) }}</td>
            <td class="t-right num t-neg">{{ money(r.unit.cost) }}</td>
            <td class="t-right num" :class="cls(r.unit.profit_before_tax)">{{ money(r.unit.profit_before_tax) }}</td>
            <td class="t-right num t-neg">{{ money(r.unit.tax) }}</td>
            <!-- маржа: три значения одной колонкой; сумма — жирная, если положительна -->
            <td class="t-right num page-wb-promotions__margin">
              <span :class="[cls(r.unit.margin_rub), { 'is-bold': (r.unit.margin_rub ?? 0) > 0 }]">{{ money(r.unit.margin_rub) }}</span>
              <span :class="cls(r.unit.margin_pct)">{{ pct(r.unit.margin_pct) }}</span>
              <span :class="dropClass(r)">{{ drop(r) }}</span>
            </td>
          </tr>
        </tbody>

        <tfoot v-if="rows.length" class="tbl__total">
          <tr>
            <td :colspan="FOOTER_LABEL_COLS" class="t-left">Итого по отмеченным ({{ selectedCount }} шт.)</td>
            <td class="t-right">{{ money(avg('revenue')) }}</td>
            <td class="t-right">{{ money(avg('commission')) }}</td>
            <td class="t-right">{{ money(avg('acquiring')) }}</td>
            <td class="t-right">{{ money(avg('acceptance')) }}</td>
            <td class="t-right">{{ money(avg('delivery')) }}</td>
            <td class="t-right">{{ money(avg('storage')) }}</td>
            <td v-if="show('include_penalties')" class="t-right">{{ money(avg('penalty')) }}</td>
            <td v-if="show('include_reviews')" class="t-right">{{ money(avg('reviews')) }}</td>
            <td v-if="show('include_adv')" class="t-right">{{ money(avg('adv')) }}</td>
            <td v-if="show('include_cashback')" class="t-right">{{ money(avg('cashback')) }}</td>
            <td class="t-right">{{ money(avg('net_profit')) }}</td>
            <td class="t-right">{{ money(avg('nds')) }}</td>
            <td class="t-right">{{ money(avg('cost')) }}</td>
            <td class="t-right">{{ money(avg('profit_before_tax')) }}</td>
            <td class="t-right">{{ money(avg('tax')) }}</td>
            <td class="t-right page-wb-promotions__margin">
              <span>{{ money(avg('margin_rub')) }}</span>
              <span>{{ pct(avg('margin_pct')) }}</span>
              <span>{{ avgDrop != null ? avgDrop.toFixed(1) : '—' }}</span>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ProductCell from '@/components/common/ProductCell.vue'
import type { PromoAnalysisRow, PromoCalcParams, PromoUnit } from '@/api/promotions'

/** Варианты размера страницы. */
const PAGE_SIZES = [50, 100, 200, 500, 1000]

/** Подпись итога занимает первые 10 колонок, дальше идут числовые. */
const FOOTER_LABEL_COLS = 10

/** Статьи, колонка которых показывается только при включённом тумблере. */
const OPT_KEYS = ['include_penalties', 'include_reviews', 'include_adv', 'include_cashback']

const props = withDefaults(defineProps<{
  rows: PromoAnalysisRow[]
  title?: string
  loading?: boolean
  /** Подпись «на чём посчитано» — показывается в шапке блока. */
  basis?: string
  /** Параметры расчёта (какие статьи учтены) — в подсказке подписи. */
  params?: Partial<PromoCalcParams>
  /** Сортировка: margin | sales | name. */
  sort?: string
  /** Порядок: asc | desc. */
  order?: string
  /** Фильтр «В акции»: all | yes | no. */
  inAction?: string
  /** Строк на страницу. */
  pageSize?: number
}>(), { params: () => ({}), sort: 'sales', order: 'desc', inAction: 'no', pageSize: 100 })

const emit = defineEmits<{
  (e: 'toggle', r: PromoAnalysisRow): void
  (e: 'export', rows: PromoAnalysisRow[]): void
  (e: 'update:page-size', n: number): void
}>()

/** Текущая страница. */
const page = ref(1)

/** Колонка статьи показывается, только если её тумблер включён. */
const show = (key: string) => (props.params as any)?.[key] === true

/** Подпись с составом расчёта. */
const basisTitle = computed(() => {
  const base = 'Все суммы — в рублях на единицу товара. Расчёт по средним за окно истории '
    + '(куб продаж WB), цена подставляется акционная.'
  const labels: Record<string, string> = {
    include_reviews: 'отзывы',
    include_adv: 'реклама',
    include_cashback: 'кэшбек',
    include_penalties: 'штрафы',
  }
  const on = OPT_KEYS.filter(k => show(k)).map(k => labels[k])
  return on.length ? base + ' Учтены: ' + on.join(', ') + '.' : base + ' Отзывы, реклама, кэшбек и штрафы не учтены.'
})

/** Фильтр «В акции»: all | yes | no. */
const inAction = computed(() => props.inAction || 'no')

/** Строки: сначала фильтр «В акции», потом сортировка и порядок. */
const filtered = computed(() => {
  let rows = props.rows
  if (inAction.value === 'yes') rows = rows.filter(r => r.in_action)
  else if (inAction.value === 'no') rows = rows.filter(r => !r.in_action)

  const dir = props.order === 'asc' ? 1 : -1
  const key = props.sort || 'margin'
  const val = (r: PromoAnalysisRow): number | string => {
    if (key === 'sales') return Number(r.sold_qty || 0)
    if (key === 'name') return String(r.title || '').toLowerCase()
    return Number(r.margin_new_rub ?? -Infinity)
  }
  return [...rows].sort((a, b) => {
    const x = val(a)
    const y = val(b)
    if (typeof x === 'string' || typeof y === 'string') {
      return String(x).localeCompare(String(y), 'ru') * dir
    }
    return (x - y) * dir
  })
})

const filteredCount = computed(() => filtered.value.length)
const pages = computed(() => Math.max(1, Math.ceil(filteredCount.value / Math.max(1, props.pageSize))))
const pageRows = computed(() => {
  const size = Math.max(1, props.pageSize)
  const from = (page.value - 1) * size
  return filtered.value.slice(from, from + size)
})

/** «1–100 из 977» — границы текущей страницы. */
const rangeText = computed(() => {
  if (!filteredCount.value) return ''
  const size = Math.max(1, props.pageSize)
  const from = (page.value - 1) * size + 1
  const to = Math.min(filteredCount.value, page.value * size)
  return `${from}–${to} из ${filteredCount.value}`
})

/** Номера страниц: первые, последние и вокруг текущей. */
const pageNumbers = computed(() => {
  const total = pages.value
  const cur = page.value
  const out = new Set<number>([1, total])
  for (let i = cur - 1; i <= cur + 1; i++) if (i > 0 && i <= total) out.add(i)
  return [...out].sort((a, b) => a - b)
})

/** Смена размера страницы — настройка пользователя. */
const onPageSize = (e: Event) => {
  const n = Number((e.target as HTMLSelectElement).value)
  if (!Number.isFinite(n) || n <= 0) return
  emit('update:page-size', n)
}

/** Смена фильтра/сортировки/размера — на первую страницу. */
watch([filtered, () => props.pageSize], () => { page.value = 1 })
watch(pages, (n) => { if (page.value > n) page.value = n })

const selectedCount = computed(() => props.rows.filter(r => r.selected).length)

/**
 * Птичка. Товар «в акции» не трогаем. Товар ниже порога маржи включаем
 * только после подтверждения пользователя.
 */
const onCheck = (r: PromoAnalysisRow, ev: Event) => {
  const el = ev.target as HTMLInputElement
  const want = el.checked
  if (want && !r.recommend && !r.in_action) {
    const ok = window.confirm(
      'Маржа товара ниже порога.\n\nВсё равно включить его в акцию?')
    if (!ok) {
      el.checked = r.selected
      return
    }
  }
  emit('toggle', r)
}

/** Минимальная цена WB. Если она совпадает с текущей ценой — показывать нечего. */
const minOf = (r: PromoAnalysisRow): number | null => {
  if (r.min_price == null) return null
  if (r.price_now != null && Math.round(r.min_price) === Math.round(r.price_now)) return null
  return r.min_price
}

/** Среднее по отмеченным товарам (на штуку). */
function avgOf(get: (r: PromoAnalysisRow) => number | null | undefined): number | null {
  const vals = props.rows.filter(r => r.selected).map(get).filter((v): v is number => typeof v === 'number')
  if (!vals.length) return null
  return vals.reduce((a, b) => a + b, 0) / vals.length
}
const avg = (key: keyof PromoUnit) => avgOf(r => r.unit[key])

const avgDrop = computed(() => {
  const now = props.rows.filter(r => r.selected).map(r => r.margin_now_pct).filter((v): v is number => v != null)
  const nw = props.rows.filter(r => r.selected).map(r => r.margin_new_pct).filter((v): v is number => v != null)
  if (!now.length || !nw.length) return null
  const a = now.reduce((x, y) => x + y, 0) / now.length
  const b = nw.reduce((x, y) => x + y, 0) / nw.length
  return a - b
})

const money = (v: number | null | undefined) => {
  if (v == null) return '—'
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(v)
}
const pct = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(1) + ' %')
const drop = (r: PromoAnalysisRow) => (r.margin_drop_pp == null ? '—' : r.margin_drop_pp.toFixed(1))
const cls = (v: number | null | undefined) => (v == null ? '' : (v < 0 ? 't-neg' : 't-pos'))
const dropClass = (r: PromoAnalysisRow) => {
  if (r.margin_drop_pp == null) return ''
  return r.margin_drop_pp > 0 ? 't-neg' : 't-pos'
}
</script>
