<template>
  <div class="container-xxl page-tag-view">
    <div class="card mb-3 page-tag-view__tags-card">
      <div class="card-body">
        <div class="d-flex align-items-center flex-wrap mb-3 page-tag-view__cloud-row">
          <h5 class="m-0 page-tag-view__cloud-title">Теги <span class="text-muted">({{ allTags.length }})</span></h5>
          <div class="d-flex flex-wrap page-tag-view__cloud">
            <router-link
              v-for="t in allTags" :key="t.id"
              :to="`/tag/orders?id=${t.id}&date_from=${dateFrom}&date_to=${dateTo}`"
              class="page-tag-view__pill"
              :class="{ 'page-tag-view__pill--active': String(t.id) === String(tagId) }"
              :style="{ '--tag-color': t.color }"
            >
              <span class="page-tag-view__dot" :style="{ background: t.color }"></span>{{ t.name }}
              <span class="page-tag-view__count">{{ t.cards_count }}</span>
            </router-link>
          </div>
        </div>
        <div class="page-tag-view__filters">
          <div class="page-tag-view__filter">
            <label class="page-tag-view__filter-label">Выбрать тег</label>
            <select v-model="pickedId" class="form-select" @change="onPick"><option v-for="t in allTags" :key="t.id" :value="t.id">{{ t.name }}</option></select>
          </div>
          <div class="page-tag-view__filter">
            <label class="page-tag-view__filter-label">Период</label>
            <div class="d-flex gap-2">
              <input v-model="dateFrom" type="date" class="form-control" />
              <input v-model="dateTo" type="date" class="form-control" />
              <button class="btn btn-primary" @click="fetchData">Применить</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <h1 class="page-title page-tag-view__title">{{ pageTitle }}</h1>

    <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
    <div v-else-if="error" class="p-4 text-center text-danger">Не удалось загрузить аналитику.</div>
    <template v-else>
      <div class="row mb-3">
        <div class="col-md-8">
          <div class="card page-tag-view__chart-card">
            <div class="card-body"><v-chart :option="chartOption" autoresize class="page-tag-view__chart" /></div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card p-0 page-tag-view__cards-panel">
            <div class="page-tag-view__cards-header"><strong>В тег входят</strong><span class="page-tag-view__cards-count">{{ related.length }}</span></div>
            <ul class="page-tag-view__cards-list">
              <li v-for="c in related" :key="c.nmId" class="page-tag-view__card-item">
                <router-link :to="`/wb/detail?nm_id=${c.nmId}`" target="_blank" class="page-tag-view__card-nmid">{{ c.nmId }}</router-link>
                <div class="page-tag-view__card-info">
                  <div class="page-tag-view__card-name">{{ c.card_name || 'Без названия' }}</div>
                  <div class="page-tag-view__card-vendor">{{ c.vendorCode }}</div>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div class="card wb-grid-card mb-3 page-tag-view__grid">
        <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
          <span>Заказы по артикулам с {{ dateFrom }} по {{ dateTo }}</span>
          <button class="btn btn-sm btn-light wb-excel-btn" :disabled="!byProduct.length" @click="onExport"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
        </div>
        <div class="wb-table-wrap page-tag-view__table-wrap">
          <table class="table table-bordered table-striped table-hover mb-0">
            <thead><tr><th>Товар/Заказ</th><th>Количество</th><th>Отменено</th><th>Выкуплено</th><th>Цена, ₽</th><th>Скидка, %</th><th>Цена со ск, ₽</th><th>СПП, %</th><th>Цена прод, ₽</th><th>Сумма заказов, ₽</th><th>Сумма выкупа, ₽</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in byProduct" :key="i">
                <td class="page-tag-view__product-cell">
                  <div class="page-tag-view__product">
                    <img :src="photoOf(r)" alt="" class="page-tag-view__photo" loading="lazy" />
                    <div class="page-tag-view__product-info">
                      <div class="page-tag-view__product-title" :title="r.card_title || ''">{{ r.card_title || '(нет карточки)' }}</div>
                      <div class="page-tag-view__product-meta">
                        <router-link :to="`/feed?nm_id=${r.nm_id}&date_from=${dateFrom}&date_to=${dateTo}`" target="_blank" class="page-tag-view__eye" title="Открыть ленту заказов"><i class="bi bi-eye-fill"></i></router-link>{{ r.card_subject_name || '' }} • {{ r.card_brand || '' }}
                      </div>
                      <div class="page-tag-view__product-meta">{{ r.card_vendor_code || '' }}</div>
                      <div class="page-tag-view__product-meta"><router-link :to="`/wb/detail?nm_id=${r.nm_id}`" target="_blank" class="page-tag-view__wb-link" data-pjax="0">WB: {{ r.nm_id }}</router-link></div>
                    </div>
                  </div>
                </td>
                <td class="text-end fw-bold">{{ fmt0(r.cnt) }}</td>
                <td class="text-end">{{ fmt0(r.cns) }}</td>
                <td class="text-end">{{ fmt0(r.byt) }}</td>
                <td class="text-end">{{ fmt2(r.tp) }}</td>
                <td class="text-end">{{ fmt2(r.dsc) }}</td>
                <td class="text-end">{{ fmt2(r.apwd) }}</td>
                <td class="text-end">{{ fmt2(r.spp) }}</td>
                <td class="text-end fw-bold">{{ fmt2(r.finished_price) }}</td>
                <td class="text-end fw-bold">{{ fmt2(r.sum_ord) }}</td>
                <td class="text-end fw-bold">{{ fmt2(r.sum_byt) }}</td>
              </tr>
              <tr v-if="!byProduct.length"><td colspan="11" class="text-center text-muted p-3">Нет данных</td></tr>
            </tbody>
            <!-- Итоги Kartik pageSummary → Vue: слова «Итого» нет, первая ячейка пустая; суммы только там, где в Yii2 pageSummary=true (cnt/cns/byt/sum_ord/sum_byt), средние — пусто -->
            <tfoot v-if="byProduct.length"><tr class="kv-totals page-tag-view__totals">
              <td></td>
              <td>{{ fmt0(totP.cnt) }}</td>
              <td>{{ fmt0(totP.cns) }}</td>
              <td>{{ fmt0(totP.byt) }}</td>
              <td></td><td></td><td></td><td></td><td></td>
              <td>{{ fmt2(totP.sum_ord) }}</td>
              <td>{{ fmt2(totP.sum_byt) }}</td>
            </tr></tfoot>
          </table>
        </div>
      </div>

      <div class="card wb-grid-card mb-3 page-tag-view__grid">
        <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
          <span>Заказы по датам</span>
          <button class="btn btn-sm btn-light wb-excel-btn" :disabled="!byDate.length" @click="onExportDates"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
        </div>
        <div class="wb-table-wrap page-tag-view__table-wrap">
          <table class="table table-bordered table-striped table-hover mb-0">
            <thead><tr><th>Дата</th><th>Кол-во</th><th>Отмена</th><th>Сумма, ₽</th><th>Цена Рзн, ₽</th><th>Скидка, %</th><th>Цена со ск, ₽</th><th>СПП, %</th><th>Цена зкз, ₽</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in byDate" :key="i">
                <td>{{ fmtDate(r.odate) }}</td>
                <td class="text-end fw-bold">{{ fmt0(r.cnt) }}</td>
                <td class="text-end fw-bold">{{ fmt0(r.cns) }}</td>
                <td class="text-end fw-bold">{{ fmt2(r.sum_ord) }}</td>
                <td class="text-end">{{ fmt2(r.tp) }}</td>
                <td class="text-end">{{ fmt2(r.dsc) }}</td>
                <td class="text-end">{{ fmt2(r.apwd) }}</td>
                <td class="text-end">{{ fmt2(r.spp) }}</td>
                <td class="text-end fw-bold">{{ fmt2(r.finished_price) }}</td>
              </tr>
              <tr v-if="!byDate.length"><td colspan="9" class="text-center text-muted p-3">Нет данных</td></tr>
            </tbody>
            <!-- Итоги Kartik pageSummary → Vue: суммы cnt/cns/sum_ord, остальное пусто -->
            <tfoot v-if="byDate.length"><tr class="kv-totals page-tag-view__totals">
              <td></td>
              <td>{{ fmt0(totD.cnt) }}</td>
              <td>{{ fmt0(totD.cns) }}</td>
              <td>{{ fmt2(totD.sum_ord) }}</td>
              <td></td><td></td><td></td><td></td><td></td>
            </tr></tfoot>
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
import { tagsApi } from '@/api/tags'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const tagId = computed(() => String(route.params.id || route.query.id || ''))
const pickedId = ref(tagId.value)
const drLegacy = String(route.query.date_range || '')
const dateFrom = ref(String(route.query.date_from || ''))
const dateTo = ref(String(route.query.date_to || ''))
if (drLegacy.includes(' - ')) {
  const [a, b] = drLegacy.split(' - ')
  dateFrom.value = dateFrom.value || a.trim()
  dateTo.value = dateTo.value || b.trim()
}
if (!dateFrom.value || !dateTo.value) {
  const t = new Date()
  const f = new Date(t)
  f.setDate(t.getDate() - 29)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  dateFrom.value = dateFrom.value || fmt(f)
  dateTo.value = dateTo.value || fmt(t)
}

const pageTitle = ref('Теги')
const allTags = ref<any[]>([])
const byProduct = ref<any[]>([])
const byDate = ref<any[]>([])
const related = ref<any[]>([])
const chartRows = ref<any[]>([])
const isLoading = ref(false)
const error = ref('')

const chartOption = computed(() => {
  // палитра 1в1 из _lochart.php:123-134 (зелёные тона, без радуги echarts)
  const palette = ['#005a32', '#238b45', '#41ab5d', '#74c476', '#a1d99b', '#c7e9c0', '#e5f5e0']
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
    lineStyle: { color: '#005a32', width: 2 },
    itemStyle: { color: '#005a32' },
    data: chartRows.value.map((r: any) => [r.date, r.total_cnt ?? 0]),
  } as any)
  return {
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: any) => fmt0(v),
    },
    legend: { type: 'scroll' },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', name: 'Кол-во (шт)' },
    series,
  }
})

const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)
const fmtDate = (v: any) => {
  if (!v) return '—'
  const d = new Date(String(v).includes('T') ? String(v) : `${v}T00:00:00`)
  return isNaN(+d) ? String(v) : d.toLocaleDateString('ru-RU')
}
// фото в wbcards.photos лежит двойным JSON (см. view.php:241-250) — разбираем так же
const photoOf = (r: any) => {
  let photos: any = r.card_photos
  for (let i = 0; i < 2; i++) {
    if (typeof photos === 'string') {
      try { photos = JSON.parse(photos) } catch { return '/images/no-photo.png' }
    }
  }
  return Array.isArray(photos) && photos[0] ? photos[0] : '/images/no-photo.png'
}

function onPick() {
  router.push(`/tag/orders?id=${pickedId.value}&date_from=${dateFrom.value}&date_to=${dateTo.value}`)
}

async function fetchData() {
  // как Yii2 actionView: без id показываем первый тег, а не список
  if (!tagId.value) {
    isLoading.value = true
    error.value = ''
    try {
      const list = await tagsApi.list()
      if (list.length) {
        router.replace(`/tag/orders?id=${list[0].id}&date_from=${dateFrom.value}&date_to=${dateTo.value}`)
        return
      }
      pageTitle.value = 'Теги: Заказы по тегу'
      allTags.value = []
    } catch {
      error.value = 'load'
    } finally {
      isLoading.value = false
    }
    return
  }
  isLoading.value = true
  error.value = ''
  try {
    const a = await tagsApi.analytics(tagId.value, dateFrom.value, dateTo.value)
    pageTitle.value = `Теги: Заказы по тегу - ${a.tag?.name ?? ''}`
    document.title = pageTitle.value
    allTags.value = a.allTags ?? []
    byProduct.value = a.byProduct ?? []
    byDate.value = a.byDate ?? []
    related.value = a.relatedCards ?? []
    chartRows.value = a.chartData ?? []
    pickedId.value = tagId.value
  } catch {
    error.value = 'load'
  } finally {
    isLoading.value = false
  }
}

async function onExport() {
  if (!tagId.value || !byProduct.value.length) return
  await tagsApi.exportByProduct(tagId.value, dateFrom.value, dateTo.value)
}

async function onExportDates() {
  if (!tagId.value || !byDate.value.length) return
  await tagsApi.exportByDate(tagId.value, dateFrom.value, dateTo.value)
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

onMounted(fetchData)
watch(() => route.fullPath, () => {
  dateFrom.value = String(route.query.date_from || dateFrom.value)
  dateTo.value = String(route.query.date_to || dateTo.value)
  fetchData()
})
</script>
