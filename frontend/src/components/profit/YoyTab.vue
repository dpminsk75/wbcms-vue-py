<template>
  <div class="page-wb-profit__yoy">
    <div v-if="busy && !rows.length" class="text-center p-5">
      <div class="spinner-border text-primary" role="status"></div>
      <div class="mt-2 text-muted">Загрузка финансовой аналитики...</div>
    </div>

    <template v-else>
      <!-- Выбор годов (применяется кнопкой «Сформировать») — слева -->
      <div class="d-flex justify-content-start mb-2">
        <YearSelector :years="availableYears" :model-value="appliedYears" @apply="onApply" />
      </div>

      <!-- Карточки YTD: два последних выбранных года -->
      <div class="row g-2 mb-3">
        <div v-for="c in cards" :key="c.k" class="col-6 col-lg-3">
          <div class="yoy-card">
            <div class="yoy-card__cap">{{ c.label }}</div>
            <div class="yoy-card__val">{{ c.value }}</div>
            <div class="yoy-card__delta" :class="c.deltaCls">{{ c.delta }}</div>
            <div class="yoy-card__note">{{ c.note }}</div>
          </div>
        </div>
      </div>

      <!-- Графики: 2 в ряд -->
      <div class="row g-3">
        <div :class="colClass('amount')" v-show="expandedId === null || expandedId === 'amount'">
          <ProfitChartCard
            title="Продажи (и количество, справа)"
            :option="optAmount"
            :expanded="expandedId === 'amount'"
            @toggle-expand="toggleExpand('amount')"
          />
        </div>        <div :class="colClass('costs')" v-show="expandedId === null || expandedId === 'costs'">
          <ProfitChartCard
            title="Структура затрат"
            :option="optCosts"
            :expanded="expandedId === 'costs'"
            @toggle-expand="toggleExpand('costs')"
          >
            <template #header>
              <div class="cost-years">
                <button
                  v-for="(y, i) in appliedYears"
                  :key="y"
                  type="button"
                  class="cost-years__chip"
                  :class="{ 'cost-years__chip--off': hiddenYears.includes(y) }"
                  :title="`Скрыть/показать ${y} год`"
                  @click="toggleYear(y)"
                >
                  <span class="cost-years__swatch" :style="{ background: '#ffffff', opacity: 0.5 + 0.5 * yearOpacity(i) }"></span>{{ y }}
                </button>
              </div>
            </template>
          </ProfitChartCard>
        </div>
        <div :class="colClass('net')" v-show="expandedId === null || expandedId === 'net'">
          <ProfitChartCard
            title="Общий итог"
            :option="optNet"
            :expanded="expandedId === 'net'"
            @toggle-expand="toggleExpand('net')"
          />
        </div>
        <div :class="colClass('margin')" v-show="expandedId === null || expandedId === 'margin'">
          <ProfitChartCard
            title="Маржа"
            :option="optMargin"
            :expanded="expandedId === 'margin'"
            @toggle-expand="toggleExpand('margin')"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '@/api/dashboard'
import { useAuthStore } from '@/stores/auth'
import { useSelectedYears } from '@/composables/useSelectedYears'
import YearSelector from './YearSelector.vue'
import ProfitChartCard from './ProfitChartCard.vue'

const auth = useAuthStore()
// Тот же queryKey, что у таблицы «Аналитика» — общий кэш, второй запрос не уходит.
const { data: rowsRaw, isLoading, isFetching } = useQuery({
  queryKey: computed(() => ['monthly-finance', auth.companyId] as const),
  queryFn: () => (dashboardApi as any).monthly(),
} as any)

const busy = computed(() => isLoading.value || isFetching.value)
const rows = computed<any[]>(() => (rowsRaw.value as any[]) ?? [])

const MONTHS = [
  { m: 1, label: 'Янв' }, { m: 2, label: 'Фев' }, { m: 3, label: 'Мар' },
  { m: 4, label: 'Апр' }, { m: 5, label: 'Май' }, { m: 6, label: 'Июн' },
  { m: 7, label: 'Июл' }, { m: 8, label: 'Авг' }, { m: 9, label: 'Сен' },
  { m: 10, label: 'Окт' }, { m: 11, label: 'Ноя' }, { m: 12, label: 'Дек' },
]

// Палитра по годам (по возрастанию): 2025 — серый, 2026 — зелёный, 2027 — синий…
const YEAR_COLORS = ['#b9c6d4', '#1e9e7c', '#2980b9', '#f0b429', '#e0525c', '#8e44ad', '#16a085']
// Тёмные варианты — текст и рамка подписи (светло-серый 2025 нечитаем).
const YEAR_LABEL_COLORS = ['#7f8c8d', '#16806a', '#21618c', '#b9770e', '#c0392b', '#6c3483', '#117a65']

// Статьи затрат — в порядке колонок отчёта «Финансовая аналитика»:
// снизу «Ком. WB» → … → сверху «Кэшбек».
// ВАЖНО: f_adv и f_otziv — подмножества f_deduction (вычет по бонусу), поэтому
// «Удержания» = deduction − adv − otziv, чтобы не считать дважды.
const COST_TYPES = [
  { key: 'commission', name: 'Ком. WB', color: '#2980b9', labelColor: '#21618c' },
  { key: 'acquiring', name: 'Эквайринг', color: '#5499c6', labelColor: '#21618c' },
  { key: 'acceptance', name: 'Приёмка', color: '#7d3c98', labelColor: '#5b2c6f' },
  { key: 'delivery', name: 'Логистика', color: '#e0525c', labelColor: '#c0392b' },
  { key: 'storage', name: 'Хранение', color: '#f39c12', labelColor: '#b9770e' },
  { key: 'penalty', name: 'Штрафы', color: '#7f8c8d', labelColor: '#566573' },
  { key: 'deduction', name: 'Удержания', color: '#95a5a6', labelColor: '#707b7f' },
  { key: 'otziv', name: 'Отзывы', color: '#16a085', labelColor: '#0e6655' },
  { key: 'adv', name: 'Реклама', color: '#8e44ad', labelColor: '#6c3483' },
  { key: 'cashback', name: 'Кэшбек', color: '#d4ac0d', labelColor: '#9a7b0a' },
] as const

// --- разбор данных ------------------------------------------------------
const byMonth = computed(() => {
  const m = new Map<string, any>()
  for (const r of rows.value) m.set(String(r.month || ''), r)
  return m
})
const availableYears = computed(() => {
  const s = new Set<number>()
  for (const r of rows.value) {
    const y = Number(String(r.month || '').slice(0, 4))
    if (y) s.add(y)
  }
  return [...s].sort((a, b) => a - b)
})

// --- выбор годов (URL) --------------------------------------------------
const { hasParam, selectedYears, setYears } = useSelectedYears()
// Параметр не задан → показываем все годы с данными; задан (в т.ч. пустой) →
// ровно выбранные.
const appliedYears = computed<number[]>(() => {
  const avail = availableYears.value
  if (!hasParam.value) return avail
  return avail.filter(y => selectedYears.value.includes(y))
})
const onApply = (list: number[]) => setYears(list)

// --- распахивание графика ------------------------------------------------
const expandedId = ref<string | null>(null)
const toggleExpand = (id: string) => { expandedId.value = expandedId.value === id ? null : id }
/** Раскрытый график занимает всю ширину строки, остальные — по половине. */
const colClass = (id: string) => (expandedId.value === id ? 'col-12' : 'col-12 col-lg-6')

// --- скрытие лет в «Структуре затрат» ------------------------------------
// Статьи скрываются штатной легендой ECharts (внизу графика).
const hiddenYears = ref<number[]>([])
const toggleYear = (y: number) => {
  hiddenYears.value = hiddenYears.value.includes(y)
    ? hiddenYears.value.filter(x => x !== y)
    : [...hiddenYears.value, y]
}
/** Прозрачность столбика года: ранние годы приглушены, свежий — обычный. */
const yearOpacity = (i: number) => Math.max(0.45, 1 - 0.22 * i)

// Последний ПОЛНЫЙ месяц текущего года (текущий месяц ещё не закрыт).
const lastFullMonth = computed(() => {
  const now = new Date()
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
  return now.getDate() >= lastDay ? now.getMonth() + 1 : now.getMonth()
})

/** Сумма поля по месяцам 1..months указанного года. */
const sumFor = (year: number, months: number, field: string): number => {
  let s = 0
  for (let mm = 1; mm <= months; mm++) {
    const r = byMonth.value.get(`${year}-${String(mm).padStart(2, '0')}`)
    if (r) s += Number(r[field]) || 0
  }
  return s
}

const nfMoney = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const nfInt = new Intl.NumberFormat('ru-RU')
const nf0 = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const nf1 = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const fmtMoney = (v: number) => nfMoney.format(Math.round(v || 0))
const fmtInt = (v: number) => nfInt.format(Math.round(v || 0))

/** Запись числа: только миллионы сокращаем (2,12м), тысячи — полностью (300 000). */
const fmtCompact = (v: number): string => {
  const n = Math.abs(Number(v) || 0)
  if (n >= 1_000_000) return `${((Number(v) || 0) / 1_000_000).toFixed(2).replace('.', ',')}м`
  return nfInt.format(Math.round(Number(v) || 0))
}

/** Δ% (null — если базы нет). */
const deltaPct = (cur: number, prev: number | null): number | null => {
  if (prev === null || !prev) return null
  return ((cur - prev) / Math.abs(prev)) * 100
}
const deltaCls = (d: number | null): string => (d === null ? '' : d > 0.05 ? 'yoy-card__delta--up' : d < -0.05 ? 'yoy-card__delta--down' : '')
const deltaText = (d: number | null): string => {
  if (d === null) return '— нет базы'
  return `${d > 0 ? '+' : ''}${nf1.format(d)} %`
}

// --- карточки ------------------------------------------------------------
const cards = computed(() => {
  const ys = appliedYears.value
  const cur = ys.length ? ys[ys.length - 1] : null
  const prev = ys.length > 1 ? ys[ys.length - 2] : null
  const n = lastFullMonth.value
  const sum = (year: number | null, field: string) => (year ? sumFor(year, n, field) : 0)

  const mk = (k: string, label: string, field: string, money: boolean) => {
    const v = sum(cur, field)
    const p = prev === null ? null : sum(prev, field)
    const d = deltaPct(v, p)
    return {
      k, label,
      value: money ? `${fmtMoney(v)} ₽` : fmtInt(v),
      delta: deltaText(d),
      deltaCls: deltaCls(d),
      note: prev === null ? 'нет второго года для сравнения' : `${money ? fmtMoney(p) + ' ₽' : fmtInt(p)} за ${prev} год`,
    }
  }
  return [
    mk('amount', 'Продажи, YTD', 'amount', true),
    mk('net', 'Общий итог, YTD', 'net_profit', true),
    mk('margin', 'Маржа, YTD', 'clean_margin', true),
    mk('qnt', 'Продано штук, YTD', 'qnt', false),
  ]
})

// --- графики -------------------------------------------------------------
type MetricKind = 'amount' | 'net_profit' | 'clean_margin'

const metricValue = (year: number, mm: number, field: string): number | null => {
  const r = byMonth.value.get(`${year}-${String(mm).padStart(2, '0')}`)
  if (!r) return null
  return Math.round(Number(r[field]) || 0)
}

/** Значение статьи затрат за месяц/год (в порядке колонок отчёта). */
const costValue = (year: number, mm: number, key: string): number => {
  const r = byMonth.value.get(`${year}-${String(mm).padStart(2, '0')}`)
  if (!r) return 0
  const n = (k: string) => Number(r[k]) || 0
  const adv = n('f_adv')
  const otziv = n('f_otziv')
  // Часть удержаний, не попавшая в рекламу/отзывы (иначе двойной счёт).
  const restDeduction = n('f_deduction') - adv - otziv
  switch (key) {
    case 'commission': return n('commission')
    case 'acquiring': return n('f_acquiring_fee')
    case 'acceptance': return n('f_acceptance')
    case 'delivery': return n('f_delivery')
    case 'storage': return n('f_storage_fee')
    case 'penalty': return n('f_penalty')
    case 'deduction': return restDeduction
    case 'otziv': return otziv
    case 'adv': return adv
    case 'cashback': return n('f_cashback')
    default: return 0
  }
}

/** Маржа месяца (clean_margin) — показываем в тултипе, чтобы видеть остаток. */
const marginValue = (year: number, mm: number): number => {
  const r = byMonth.value.get(`${year}-${String(mm).padStart(2, '0')}`)
  return r ? Number(r.clean_margin) || 0 : 0
}

/** Шрифт подписей осей (увеличивается при раскрытии графика). */
const axisFont = (scale: number) => ({
  fontSize: Math.round(10 * scale),
  color: '#888',
  fontFamily: '"Segoe UI",Roboto,Helvetica,Arial,sans-serif',
})

/** Значение из params-объекта подписи ECharts (или из «голого» числа). */
const labelValue = (p: any): number | null => {
  const v = p && typeof p === 'object'
    ? (Array.isArray(p.value) ? p.value[1] : p.value)
    : p
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** Подпись значения: белая плашка в рамке цвета серии (как на /wb/detail).
 *  scale — увеличение при раскрытии графика (рамка/скругление/отступы — пропорционально). */
const valueLabel = (position: 'top' | 'inside', color: string, fontSize = 11, scale = 1) => ({
  show: true,
  position,
  // ВАЖНО: formatter у ECharts-подписи получает объект params, а не само значение.
  formatter: (p: any) => {
    const n = labelValue(p)
    return n === null ? '' : fmtCompact(n)
  },
  fontSize,
  fontWeight: 700,
  color,
  backgroundColor: '#fff',
  borderColor: color,
  borderWidth: 1.5 * scale,
  borderRadius: 6 * scale,
  padding: [2 * scale, 6 * scale],
})

/** Опция графика: бары по годам (по возрастанию) + при withQty линия штук по 2-й оси.
 *  При раскрытии графика подписи и оси увеличиваются пропорционально. */
const chartOption = (id: string, kind: MetricKind, withQty = false) => computed(() => {
  const ys = appliedYears.value
  const labels = MONTHS.map(x => x.label)
  const color = (i: number) => YEAR_COLORS[i % YEAR_COLORS.length]
  const labelColor = (i: number) => YEAR_LABEL_COLORS[i % YEAR_LABEL_COLORS.length]
  const scale = expandedId.value === id ? 1.4 : 1
  const af = axisFont(scale)

  const bars = ys.map((y, i) => ({
    name: String(y),
    type: 'bar',
    data: MONTHS.map(x => metricValue(y, x.m, kind)),
    itemStyle: { color: color(i), borderRadius: [3, 3, 0, 0] },
    label: valueLabel('top', labelColor(i), Math.round(11 * scale), scale),
    // Как на /wb/detail: подписи не прячем, а сдвигаем по вертикали (иначе часть
    // значений пропадает из-за перекрытий).
    labelLayout: { hideOverlap: false, moveOverlap: 'shiftY', minMargin: 3 },
  }))
  const lines = withQty ? ys.map((y, i) => ({
    name: `Кол-во ${y}`,
    type: 'line',
    yAxisIndex: 1,
    data: MONTHS.map(x => metricValue(y, x.m, 'qnt')),
    itemStyle: { color: color(i) },
    lineStyle: { type: 'dashed', width: 2, color: color(i) },
    symbol: 'none',
    z: 5,
    // Подписи у линии количества не рисуем — 24 точки, нечитаемо (значения — в тултипе и на 2-й оси).
    label: { ...valueLabel('top', labelColor(i), Math.round(11 * scale), scale), noShow: true },
    labelLayout: { hideOverlap: true },
  })) : []

  const valueAxis = (fmt: (v: number) => string, name: string) => ({
    type: 'value',
    name,
    nameTextStyle: { fontSize: Math.round(10 * scale), color: '#95a5a6' },
    splitLine: { lineStyle: { color: '#eef1f4' } },
    axisLabel: { ...af, formatter: fmt },
    // Запас сверху, чтобы подпись над самым высоким столбиком не обрезалась.
    min: 0,
    max: (v: any) => v.max * 1.08,
  })

  return {
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(33,37,41,.92)',
      borderWidth: 0,
      textStyle: { color: '#fff', fontSize: 12 },
      formatter: (params: any) => {
        const arr = Array.isArray(params) ? params : [params]
        if (!arr.length) return ''
        let s = `${arr[0].axisValue ?? ''}<br/>`
        for (const p of arr) {
          const v = Array.isArray(p.value) ? p.value[1] : p.value
          const isQty = String(p.seriesName).startsWith('Кол-во')
          const txt = v === null || v === undefined ? '—'
            : (isQty ? `${nfInt.format(v)} шт` : `${nfMoney.format(v)} ₽`)
          s += `${p.marker}${p.seriesName}: ${txt}<br/>`
        }
        return s
      },
    },
    legend: {
      data: [...bars.map(b => b.name), ...lines.map(l => l.name)],
      bottom: 0, left: 'center', icon: 'roundRect',
      itemWidth: Math.round(11 * scale), itemHeight: Math.round(11 * scale),
      textStyle: { fontSize: Math.round(10 * scale), fontFamily: '"Segoe UI",Roboto,Helvetica,Arial,sans-serif' },
      type: 'scroll',
    },
    // Одинаковые отступы у всех графиков (у «Структуры затрат» легенда в 2 строки),
    // иначе области построения не совпадают по высоте.
    grid: { left: 4, right: withQty ? 4 : 10, top: Math.round(26 * scale), bottom: 66, containLabel: true },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#dee2e6' } },
      axisTick: { show: false },
      axisLabel: { ...af, interval: 0 },
    },
    yAxis: withQty
      ? [
        valueAxis((v: number) => fmtCompact(v), '₽'),
        valueAxis((v: number) => nfInt.format(v), 'шт'),
      ]
      : [valueAxis((v: number) => fmtCompact(v), '₽')],
    series: [...bars, ...lines],
  }
})

/**
 * «Структура затрат»: в каждом месяце — столбик на каждый год (стек по годам),
 * внутри столбика — разбивка по статьям затрат (цвет = статья).
 * В тултипе — сравнение статей год к году с Δ%.
 */
const optCosts = computed(() => {
  const ys = appliedYears.value
  const visYears = ys.filter(y => !hiddenYears.value.includes(y))
  const scale = expandedId.value === 'costs' ? 1.4 : 1
  const af = axisFont(scale)

  const series: any[] = []
  visYears.forEach((y, yi) => {
    // Итог месяца по году — чтобы подписывать только весомые сегменты (иначе каша).
    const totalsByMonth = MONTHS.map(x => COST_TYPES.reduce((acc, t) => acc + costValue(y, x.m, t.key), 0))
    COST_TYPES.forEach(t => {
      series.push({
        // Имя = статья (одинаковое для обоих лет) → в легенде ECharts это одна
        // строка, клик по ней гасит статью сразу в обоих годах.
        name: t.name,
        type: 'bar',
        stack: `y${y}`,
        data: MONTHS.map((x, xi) => {
          const v = costValue(y, x.m, t.key)
          const tot = totalsByMonth[xi] || 0
          // Подписываем только весомые сегменты (≥12% месяца) — иначе каша.
          return { value: v, label: { show: tot > 0 && Math.abs(v) / tot >= 0.12 } }
        }),
        itemStyle: { color: t.color, opacity: yearOpacity(yi) },
        label: valueLabel('inside', t.labelColor, Math.round(10 * scale), scale),
        labelLayout: { hideOverlap: true },
      })
    })
  })

  return {
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(33,37,41,.94)',
      borderWidth: 0,
      padding: [8, 10],
      textStyle: { color: '#fff', fontSize: Math.round(12 * scale) },
      // Таблица: Статья | 2025 | Сумма | 2026 | Сумма | Δ
      // Фиксированные ширины колонок — иначе «2026» и Δ «плывут» по строкам.
      // Строки — в том же порядке, что серии на графике (сверху вниз).
      formatter: (params: any) => {
        const arr = Array.isArray(params) ? params : [params]
        if (!arr.length) return ''
        const mi = Number(arr[0].dataIndex)
        const month = MONTHS[mi]?.label ?? ''
        const totals: Record<number, number> = {}
        const rowsHtml: string[] = []
        const lastIdx = ys.length - 1

        // % от Продаж этого месяца/года.
        const amountOf = (y: number) => metricValue(y, mi + 1, 'amount') || 0
        const pctOf = (y: number, v: number): string => {
          const a = amountOf(y)
          if (!a) return ''
          const p = (v / a) * 100
          const s = Math.abs(p) < 10 ? nf1.format(p) : nf0.format(p)
          return ` <span style="opacity:.6">(${s}%)</span>`
        }

        for (const t of [...COST_TYPES].reverse()) {
          const cells = ys.map((y, yi) => {
            const v = costValue(y, mi + 1, t.key)
            totals[y] = (totals[y] || 0) + v
            let delta = ''
            if (yi === lastIdx && ys.length >= 2) {
              const cur = costValue(ys[lastIdx], mi + 1, t.key)
              const prev = costValue(ys[lastIdx - 1], mi + 1, t.key)
              if (prev) {
                const d = ((cur - prev) / Math.abs(prev)) * 100
                delta = `<span style="color:${d >= 0 ? '#ff9f9f' : '#9ff5c4'}">${d >= 0 ? '▲' : '▼'} ${nf1.format(Math.abs(d))}%</span>`
              }
            }
            return `<td style="padding:1px 0 1px 6px">${y}</td>`
              + `<td style="padding:1px 6px 1px 0; text-align:right"><b>${fmtCompact(v)}</b>${pctOf(y, v)}</td>`
              + `<td style="padding:1px 0 1px 0; text-align:right">${delta}</td>`
          }).join('')
          rowsHtml.push(
            `<tr><td style="padding:1px 12px 1px 0">`
            + `<span style="display:inline-block;width:9px;height:9px;background:${t.color};border-radius:2px;margin-right:5px"></span>${t.name}`
            + `</td>${cells}</tr>`
          )
        }

        const head = ys.map((y, yi) => `<th style="text-align:left;padding:0 0 4px 6px;font-weight:400;opacity:.65">${y}</th>`
          + `<th style="text-align:right;padding:0 0 4px 0;font-weight:400;opacity:.65"></th>`
          + `<th style="text-align:right;padding:0 0 4px 0;font-weight:400;opacity:.65">${yi === lastIdx ? 'Δ' : ''}</th>`).join('')
        const footRow = (title: string, values: Record<number, number>) => {
          const cells = ys.map(y => `<td style="padding:2px 0 2px 6px">${y}</td>`
            + `<td style="padding:2px 6px 2px 0; text-align:right"><b>${fmtCompact(values[y] || 0)}</b>${pctOf(y, values[y] || 0)}</td>`
            + `<td style="padding:2px 0 2px 0"></td>`).join('')
          return `<tr style="border-top:1px solid rgba(255,255,255,.25)"><td style="padding:4px 12px 2px 0">${title}</td>${cells}</tr>`
        }
        const totalVals: Record<number, number> = { ...totals }
        const marginVals: Record<number, number> = {}
        for (const y of ys) marginVals[y] = marginValue(y, mi + 1)

        const cols = ys.map(() => '<col style="width:34px"><col style="width:96px"><col style="width:52px">').join('')

        return `<div>`
          + `<div style="font-weight:700;margin-bottom:4px">${month}</div>`
          + `<table style="border-collapse:collapse;font-size:${Math.round(11 * scale)}px;line-height:1.4;white-space:nowrap;table-layout:fixed">`
          + `<colgroup><col style="width:auto">${cols}</colgroup>`
          + `<thead><tr><th style="text-align:left;padding:0 12px 3px 0;font-weight:400;opacity:.65">Статья</th>${head}</tr></thead>`
          + `<tbody>${rowsHtml.join('')}</tbody>`
          + `<tfoot>${footRow('Итого расходов WB', totalVals)}${footRow('Маржа', marginVals)}</tfoot>`
          + `</table></div>`
      },
    },
    // Легенда статей — внизу, как у остальных графиков; порядок — как в столбике.
    legend: {
      data: [...COST_TYPES].reverse().map(t => t.name),
      bottom: 0, left: 'center', itemGap: Math.round(10 * scale), icon: 'roundRect',
      itemWidth: Math.round(11 * scale), itemHeight: Math.round(11 * scale),
      textStyle: { fontSize: Math.round(10 * scale), fontFamily: '"Segoe UI",Roboto,Helvetica,Arial,sans-serif' },
    },
    grid: { left: 4, right: 10, top: Math.round(26 * scale), bottom: 66, containLabel: true },
    barGap: '12%',
    barCategoryGap: '32%',
    xAxis: {
      type: 'category',
      data: MONTHS.map(x => x.label),
      axisLine: { lineStyle: { color: '#dee2e6' } },
      axisTick: { show: false },
      axisLabel: { ...af, interval: 0 },
    },
    yAxis: [{
      type: 'value',
      name: '₽',
      nameTextStyle: { fontSize: Math.round(10 * scale), color: '#95a5a6' },
      splitLine: { lineStyle: { color: '#eef1f4' } },
      axisLabel: { ...af, formatter: (v: number) => fmtCompact(v) },
      // Нижняя граница = фактический минимум (без «красивого» отступа вниз),
      // сверху — запас под подписи.
      min: (v: any) => Math.min(0, v.min),
      max: (v: any) => v.max * 1.08,
    }],
    series,
  }
})

const optAmount = chartOption('amount', 'amount', true)
const optNet = chartOption('net', 'net_profit')
const optMargin = chartOption('margin', 'clean_margin')
</script>

<style scoped>
.yoy-card {
  background: #fff;
  border: 1px solid #e3e7eb;
  border-radius: 10px;
  padding: 10px 12px;
  height: 100%;
}
.yoy-card__cap { font-size: 10px; text-transform: uppercase; color: #7f8c8d; font-weight: 700; }
.yoy-card__val { font-size: 19px; font-weight: 700; color: #2c3e50; line-height: 1.25; margin-top: 2px; }
.yoy-card__delta { font-size: 12px; font-weight: 700; color: #7f8c8d; margin-top: 2px; }
.yoy-card__delta--up { color: #1e9e7c; }
.yoy-card__delta--down { color: #e0525c; }
.yoy-card__note { font-size: 10px; color: #95a5a6; margin-top: 2px; }

.cost-years { display: inline-flex; align-items: center; gap: 6px; margin-right: 4px; }
.cost-years__chip {
  display: inline-flex; align-items: center; gap: 4px;
  border: 1px solid rgba(255,255,255,.6); background: transparent; border-radius: 12px;
  font-size: 10px; color: #fff; padding: 1px 7px; cursor: pointer;
}
.cost-years__chip:hover { background: rgba(255,255,255,.15); }
.cost-years__chip--off { opacity: .4; text-decoration: line-through; }
.cost-years__swatch { display: inline-block; width: 9px; height: 9px; border-radius: 2px; background: #fff; }
</style>
