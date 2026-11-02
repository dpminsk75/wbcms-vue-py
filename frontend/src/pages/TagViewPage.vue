<template>
  <div class="container-xxl page-tag-view">
    <WbWorkspaceHead title="Заказы по тегу" :workspace-tabs="TAGS_WORKSPACE_TABS" workspace-active="orders" />

    <!-- Облаво тегов — быстрый выбор тега (в нём же счётчик карточек) -->
    <div class="wb-panel page-tag-view__cloud">
      <div class="wb-panel__bd">
        <TagCloud :tags="allTags" :active-id="tagId" @pick="onPickTag" />
      </div>
    </div>

    <!-- Фильтр: период + кнопки отчёта -->
    <div class="wb-filter-panel">
      <WbDateRangeFilter
        v-model:from="filters.date_from"
        v-model:to="filters.date_to"
        default-preset="30"
        bare
      />
      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" :disabled="isLoading" @click="onApply">
          Применить
        </button>
        <button class="btn btn--outline" :disabled="isLoading" @click="onReset">Сбросить</button>
      </div>
    </div>

    <div v-if="isLoading" class="wb-panel page-tag-view__state">Загрузка…</div>
    <div v-else-if="error" class="wb-panel page-tag-view__state page-tag-view__state--bad">{{ error }}</div>

    <template v-else>
      <div class="page-tag-view__top">
        <!-- График -->
        <div class="wb-panel">
          <div class="card__hd">
            <span>Заказы по дням</span>
            <span class="spacer"></span>
            <span class="hd-badge">{{ applied.date_from }} — {{ applied.date_to }}</span>
          </div>
          <div class="wb-panel__bd page-tag-view__chart-body">
            <v-chart :option="chartOption" autoresize class="page-tag-view__chart" />
          </div>
        </div>

        <!-- Карточки тега -->
        <div class="wb-panel">
          <div class="card__hd">
            <span>В тег входят</span>
            <span class="spacer"></span>
            <span class="hd-badge">{{ related.length }}</span>
          </div>
          <ul class="page-tag-view__cards-list">
            <li v-for="c in related" :key="c.nmId" class="page-tag-view__card-item">
              <ProductCell
                compact
                :nm-id="c.nmId"
                :photo="c.photos"
                :title="c.card_name"
                :vendor="c.vendorCode"
                :brand="c.brand"
                :subject="c.subjectName"
                :link="`/wb/detail?nm_id=${c.nmId}`"
                :link-label="`WB: ${c.nmId}`"
              />
            </li>
            <li v-if="!related.length" class="page-tag-view__card-item page-tag-view__empty">
              В тег пока не входят карточки
            </li>
          </ul>
        </div>
      </div>

      <!-- Заказы по артикулам -->
      <div class="tbl-card tbl-card--compact">
        <div class="card__hd">
          <span>Заказы по артикулам с {{ applied.date_from }} по {{ applied.date_to }}</span>
          <span class="spacer"></span>
          <span class="hd-badge">Карточек: {{ byProduct.length }}</span>
          <ExcelButton :disabled="!byProduct.length" @click="onExport" />
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">Товар/Заказ</th>
                <th class="t-right">Количество</th>
                <th class="t-right">Отменено</th>
                <th class="t-right">Выкуплено</th>
                <th class="t-right">Цена, ₽</th>
                <th class="t-right">Скидка, %</th>
                <th class="t-right">Цена со ск, ₽</th>
                <th class="t-right">СПП, %</th>
                <th class="t-right">Цена прод, ₽</th>
                <th class="t-right">Сумма заказов, ₽</th>
                <th class="t-right">Сумма выкупа, ₽</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in byProduct" :key="i">
                <td class="t-left">
                  <div class="page-tag-view__cell">
                    <ProductCell
                      compact
                      :nm-id="r.nm_id"
                      :photo="r.card_photos"
                      :title="r.card_title"
                      :vendor="r.card_vendor_code"
                      :brand="r.card_brand"
                      :subject="r.card_subject_name"
                      :link="`/wb/detail?nm_id=${r.nm_id}`"
                      :link-label="`WB: ${r.nm_id}`"
                      copy-nm
                      copy-link
                    />
                    <router-link
                      :to="`/feed?nm_id=${r.nm_id}&date_from=${applied.date_from}&date_to=${applied.date_to}`"
                      target="_blank"
                      class="page-tag-view__feed"
                      title="Открыть ленту заказов"
                    >
                      <i class="bi bi-eye-fill"></i>
                    </router-link>
                  </div>
                </td>
                <td class="t-right num page-tag-view__strong">{{ fmt0(r.cnt) }}</td>
                <td class="t-right num">{{ fmt0(r.cns) }}</td>
                <td class="t-right num">{{ fmt0(r.byt) }}</td>
                <td class="t-right num">{{ fmt2(r.tp) }}</td>
                <td class="t-right num">{{ fmt2(r.dsc) }}</td>
                <td class="t-right num">{{ fmt2(r.apwd) }}</td>
                <td class="t-right num">{{ fmt2(r.spp) }}</td>
                <td class="t-right num page-tag-view__strong">{{ fmt2(r.finished_price) }}</td>
                <td class="t-right num page-tag-view__strong">{{ fmt2(r.sum_ord) }}</td>
                <td class="t-right num page-tag-view__strong">{{ fmt2(r.sum_byt) }}</td>
              </tr>
              <tr v-if="!byProduct.length">
                <td colspan="11" class="t-center page-tag-view__empty">Нет данных</td>
              </tr>
            </tbody>
            <!-- Итоги: суммы только там, где в PHP-оригинале pageSummary=true -->
            <tfoot v-if="byProduct.length">
              <tr class="tbl__total tbl__total--plain">
                <td class="t-left"></td>
                <td>{{ fmt0(totP.cnt) }}</td>
                <td>{{ fmt0(totP.cns) }}</td>
                <td>{{ fmt0(totP.byt) }}</td>
                <td></td><td></td><td></td><td></td><td></td>
                <td>{{ fmt2(totP.sum_ord) }}</td>
                <td>{{ fmt2(totP.sum_byt) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Заказы по датам -->
      <div class="tbl-card">
        <div class="card__hd">
          <span>Заказы по датам</span>
          <span class="spacer"></span>
          <span class="hd-badge">Дней: {{ byDate.length }}</span>
          <ExcelButton :disabled="!byDate.length" @click="onExportDates" />
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">Дата</th>
                <th class="t-right">Кол-во</th>
                <th class="t-right">Отмена</th>
                <th class="t-right">Сумма, ₽</th>
                <th class="t-right">Цена Рзн, ₽</th>
                <th class="t-right">Скидка, %</th>
                <th class="t-right">Цена со ск, ₽</th>
                <th class="t-right">СПП, %</th>
                <th class="t-right">Цена зкз, ₽</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in byDate" :key="i">
                <td class="t-left">{{ fmtDate(r.odate) }}</td>
                <td class="t-right num page-tag-view__strong">{{ fmt0(r.cnt) }}</td>
                <td class="t-right num page-tag-view__strong">{{ fmt0(r.cns) }}</td>
                <td class="t-right num page-tag-view__strong">{{ fmt2(r.sum_ord) }}</td>
                <td class="t-right num">{{ fmt2(r.tp) }}</td>
                <td class="t-right num">{{ fmt2(r.dsc) }}</td>
                <td class="t-right num">{{ fmt2(r.apwd) }}</td>
                <td class="t-right num">{{ fmt2(r.spp) }}</td>
                <td class="t-right num page-tag-view__strong">{{ fmt2(r.finished_price) }}</td>
              </tr>
              <tr v-if="!byDate.length">
                <td colspan="9" class="t-center page-tag-view__empty">Нет данных</td>
              </tr>
            </tbody>
            <tfoot v-if="byDate.length">
              <tr class="tbl__total tbl__total--plain">
                <td class="t-left"></td>
                <td>{{ fmt0(totD.cnt) }}</td>
                <td>{{ fmt0(totD.cns) }}</td>
                <td>{{ fmt2(totD.sum_ord) }}</td>
                <td></td><td></td><td></td><td></td><td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-tag-view.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import WbDateRangeFilter from '@/components/common/WbDateRangeFilter.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import ProductCell from '@/components/common/ProductCell.vue'
import TagCloud from '@/components/tags/TagCloud.vue'
import { tagsApi, type TagItem } from '@/api/tags'
import { exportXlsx } from '@/utils/exportXlsx'
import { greenSeries, greenTotal, resolveTokenColor } from '@/utils/chartTheme'
import { TAGS_WORKSPACE_TABS } from '@/components/common/workspaceTabs'
import { useDateFmt } from '../composables/useDateFmt'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const { fmtDate } = useDateFmt()

/** Тег — из пути (/tags/:id) или из query (/tag/orders?id=…). */
const tagId = computed(() => String(route.params.id || route.query.id || ''))

// локальное время (toISOString даёт UTC и сдвигает сутки) — период всегда заканчивается сегодня
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const defaultDates = () => {
  const to = new Date()
  const from = new Date(to.getFullYear(), to.getMonth(), to.getDate() - 29)
  return { date_from: fmtD(from), date_to: fmtD(to) }
}
const fromRoute = (q: any) => {
  const d = defaultDates()
  return {
    date_from: String(q.date_from || d.date_from),
    date_to: String(q.date_to || d.date_to),
  }
}

// filters — черновик периода, applied — период, по которому запрошены данные
const filters = ref(fromRoute(route.query))
const applied = ref({ ...filters.value })

const pageTitle = ref('Теги')
const allTags = ref<any[]>([])
const byProduct = ref<any[]>([])
const byDate = ref<any[]>([])
const related = ref<any[]>([])
const chartRows = ref<any[]>([])
const isLoading = ref(false)
const error = ref('')

const chartOption = computed(() => {
  // Палитра серий — из токенов темы (--chart-green-1…7): зелёная шкала, как была.
  const palette = greenSeries()
  const totalColor = greenTotal()
  const totals = new Map<string, number>()
  for (const r of chartRows.value) {
    for (const k of Object.keys(r)) {
      if (!k.startsWith('value_')) continue
      const id = k.slice(6)
      totals.set(id, (totals.get(id) ?? 0) + (Number(r[k]) || 0))
    }
  }
  const ids = [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([id]) => id)
  const series = ids.map((id, i) => {
    const color = palette[i % palette.length]
    return {
      name: `Арт: ${id}`, type: 'line', stack: 'total', smooth: true,
      lineStyle: { color, width: 1 },
      itemStyle: { color },
      areaStyle: { color, opacity: 0.7 },
      data: chartRows.value.map((r) => [r.date, r[`value_${id}`] ?? 0]),
    }
  })
  series.push({
    name: 'Итого заказов', type: 'line', smooth: true,
    lineStyle: { color: totalColor, width: 2 },
    itemStyle: { color: totalColor },
    data: chartRows.value.map((r: any) => [r.date, r.total_cnt ?? 0]),
  } as any)
  return {
    tooltip: {
      trigger: 'axis',
      // Своя разметка: у time-оси echarts в подсказку уходит время 00:00:00 —
      // показываем только дату, как в PHP-оригинале.
      formatter: (params: any) => {
        const list: any[] = Array.isArray(params) ? params : [params]
        if (!list.length) return ''
        const head = `<div style="font-weight:700;margin-bottom:4px">${dayLabel(list[0].axisValue)}</div>`
        const rows = list.map((p) => {
          const val = fmt0(p?.value?.[1] ?? p?.value)
          const color = p?.color || 'var(--brand)'
          return `<div style="display:flex;align-items:center;gap:6px;line-height:1.5">`
            + `<span style="width:9px;height:9px;border-radius:50%;background:${color};display:inline-block;flex:none"></span>`
            + `<span style="flex:1">${p?.seriesName ?? ''}</span>`
            + `<b style="margin-left:14px">${val}</b></div>`
        }).join('')
        return head + rows
      },
    },
    // Легенда снизу, кружком своего цвета, в несколько строк — как в PHP-оригинале.
    // type: 'plain' — без постраничной навигации («1/2» со стрелками).
    legend: {
      type: 'plain',
      bottom: 0,
      left: 'center',
      width: '62%',
      icon: 'circle',
      itemWidth: 12,
      itemHeight: 12,
      itemGap: 18,
      textStyle: { color: resolveTokenColor('--ink-soft'), fontSize: 12 },
    },
    // Место под легенду (низу) и под подпись оси Y.
    grid: { top: 18, left: 46, right: 16, bottom: 96 },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', name: 'Кол-во (шт)' },
    series,
  }
})

const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)

/** Дата для подсказки: без времени (time-ось echarts подставляет 00:00:00). */
const dayLabel = (v: any): string => {
  const s = String(v ?? '')
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10)
  const d = new Date(typeof v === 'number' ? v : s)
  if (Number.isNaN(d.getTime())) return s
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** фильтры → URL (replace, чтобы не плодить историю) */
let syncing = false
function syncRoute() {
  const q: Record<string, string> = {
    date_from: applied.value.date_from,
    date_to: applied.value.date_to,
  }
  if (tagId.value) q.id = tagId.value
  syncing = true
  router.replace({ path: route.path, query: q })
    .finally(() => setTimeout(() => (syncing = false), 50))
}

/** URL → фильтры (навигация назад/вперёд, чужая ссылка, выбор тега из облака). */
let lastTagId = ''
function applyFromRoute(nq: any) {
  const next = fromRoute(nq)
  const cur = applied.value
  const nextTag = String(route.params.id || nq.id || '')
  const tagChanged = nextTag !== lastTagId
  if (tagChanged || cur.date_from !== next.date_from || cur.date_to !== next.date_to) {
    filters.value = { ...next }
    applied.value = { ...next }
    lastTagId = nextTag
    fetchData()
  }
}

async function fetchData() {
  // как в PHP-оригинале: без id показываем первый тег, а не пустой отчёт
  if (!tagId.value) {
    isLoading.value = true
    error.value = ''
    try {
      const list = await tagsApi.list()
      if (list.length) {
        router.replace({
          path: '/tag/orders',
          query: { id: String(list[0].id), date_from: applied.value.date_from, date_to: applied.value.date_to },
        }).catch(() => {})
        return
      }
      pageTitle.value = 'Теги: Заказы по тегу'
      allTags.value = []
    } catch {
      error.value = 'Не удалось загрузить теги.'
    } finally {
      isLoading.value = false
    }
    return
  }
  isLoading.value = true
  error.value = ''
  try {
    const a = await tagsApi.analytics(tagId.value, applied.value.date_from, applied.value.date_to)
    pageTitle.value = `Теги: Заказы по тегу - ${a.tag?.name ?? ''}`
    document.title = pageTitle.value
    allTags.value = a.allTags ?? []
    byProduct.value = a.byProduct ?? []
    byDate.value = a.byDate ?? []
    related.value = a.relatedCards ?? []
    chartRows.value = a.chartData ?? []
  } catch {
    error.value = 'Не удалось загрузить аналитику.'
  } finally {
    isLoading.value = false
  }
}

/** Выбор тега в облаве — переход к заказам по нему (период сохраняется). */
function onPickTag(t: TagItem) {
  router.push({
    path: '/tag/orders',
    query: { id: String(t.id), date_from: applied.value.date_from, date_to: applied.value.date_to },
  }).catch(() => {})
}

/** Применить период: черновик → применённое → URL → запрос. */
function onApply() {
  applied.value = { ...filters.value }
  syncRoute()
  fetchData()
}

/** Сбросить период к дефолту (30 дней). */
function onReset() {
  const d = defaultDates()
  filters.value = { ...d }
  applied.value = { ...d }
  syncRoute()
  fetchData()
}

async function onExport() {
  if (!tagId.value) return
  const a = await tagsApi.analytics(tagId.value, applied.value.date_from, applied.value.date_to)
  await exportXlsx({
    rows: (a.byProduct ?? []).map((r: any) => ({
      'Арт WB': r.nm_id, 'Товар': r.card_title, 'Артикул': r.card_vendor_code,
      'Количество': r.cnt, 'Отменено': r.cns, 'Выкуплено': r.byt,
      'Цена': r.tp, 'Скидка %': r.dsc, 'Цена со ск': r.apwd, 'СПП %': r.spp,
      'Цена прод': r.finished_price, 'Сумма заказов': r.sum_ord, 'Сумма выкупа': r.sum_byt,
    })),
    filename: `tag-${tagId.value}-products.xlsx`,
    sheetName: 'tag-products',
    cols: [{ wch: 12 }, { wch: 32 }, { wch: 18 }, { wch: 10 }, { wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 10 }, { wch: 12 }, { wch: 10 }, { wch: 12 }, { wch: 15 }, { wch: 14 }],
  })
}

async function onExportDates() {
  if (!tagId.value) return
  const a = await tagsApi.analytics(tagId.value, applied.value.date_from, applied.value.date_to)
  await exportXlsx({
    rows: (a.byDate ?? []).map((r: any) => ({
      'Дата': r.odate, 'Кол-во': r.cnt, 'Отмена': r.cns, 'Сумма': r.sum_ord,
      'Цена Рзн': r.tp, 'Скидка %': r.dsc, 'Цена со ск': r.apwd, 'СПП %': r.spp, 'Цена зкз': r.finished_price,
    })),
    filename: `tag-${tagId.value}-dates.xlsx`,
    sheetName: 'tag-dates',
    cols: [{ wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 14 }, { wch: 12 }, { wch: 10 }, { wch: 12 }, { wch: 10 }, { wch: 12 }],
  })
}

const sumCol = (rows: any[], k: string) => rows.reduce((a, r) => a + (Number(r[k]) || 0), 0)
const totP = computed(() => ({
  cnt: sumCol(byProduct.value, 'cnt'),
  cns: sumCol(byProduct.value, 'cns'),
  byt: sumCol(byProduct.value, 'byt'),
  sum_ord: sumCol(byProduct.value, 'sum_ord'),
  sum_byt: sumCol(byProduct.value, 'sum_byt'),
}))
const totD = computed(() => ({
  cnt: sumCol(byDate.value, 'cnt'),
  cns: sumCol(byDate.value, 'cns'),
  sum_ord: sumCol(byDate.value, 'sum_ord'),
}))

watch(() => route.query, (nq) => {
  if (syncing) return
  applyFromRoute(nq)
})

onMounted(() => {
  lastTagId = tagId.value
  fetchData()
})
</script>
