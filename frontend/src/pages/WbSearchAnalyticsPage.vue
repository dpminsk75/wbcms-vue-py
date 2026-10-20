<template>
  <div class="container-xxl page-wb-search-analytics">
    <div class="row mb-3">
      <h2 class="page-wb-search-analytics__title">Частотность поисковых запросов</h2>
    </div>

    <div class="row mb-3">
      <div class="col-md-12">
        <WbSearchFilter
          label="Поиск по запросам"
          :data="phraseOptions"
          placeholder="Часть фразы..."
          v-model:phrase="filters.q"
          v-model:date-from="filters.date_from"
          v-model:date-to="filters.date_to"
          default-preset="30"
          preset-end="yesterday"
          @apply="onApply"
          @reset="onReset"
        />
      </div>
    </div>

    <div class="row page-wb-search-analytics__grid mb-3 mt-3">
      <div class="col-md-12">
        <div class="card">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span>
              Частотность запросов
              <span v-if="prevFrom" class="page-wb-search-analytics__period">
                с {{ fmtD(filters.date_from) }} по {{ fmtD(filters.date_to) }} в сравнении с {{ fmtD(prevFrom) }} по {{ fmtD(prevTo) }}
              </span>
            </span>
            <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!models.length || exporting"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
          </div>
          <div v-if="isLoading" class="text-center p-5">
            <div class="spinner-border text-primary" role="status"></div>
            <div class="mt-2 text-muted">Загрузка данных...</div>
          </div>
          <div v-else class="wb-table-wrap page-wb-search-analytics__table-wrap">
            <table class="table table-bordered table-hover mb-0 page-wb-search-analytics__table">
              <thead>
                <tr>
                  <th class="page-wb-search-analytics__th--num">#</th>
                  <th class="page-wb-search-analytics__phrase">Поисковый запрос</th>
                  <th class="page-wb-search-analytics__sort" @click="setSort('freq')">Запросов {{ sortMark('freq') }}</th>
                  <th class="page-wb-search-analytics__sort" @click="setSort('delta')">Динамика {{ sortMark('delta') }}</th>
                  <th class="page-wb-search-analytics__sort" @click="setSort('day')">В день {{ sortMark('day') }}</th>
                  <th class="page-wb-search-analytics__sort" @click="setSort('goods')">Товаров {{ sortMark('goods') }}</th>
                  <th class="page-wb-search-analytics__sort" @click="setSort('pos')">Ср. позиция {{ sortMark('pos') }}</th>
                  <th class="page-wb-search-analytics__sort" @click="setSort('best')">Лучшая {{ sortMark('best') }}</th>
                  <th>Клики</th>
                  <th class="page-wb-search-analytics__sort" @click="setSort('orders')">Заказы {{ sortMark('orders') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!models.length"><td colspan="10" class="text-center text-muted p-4">Нет данных</td></tr>
                <tr v-for="(m, i) in models" :key="m.phrase">
                  <td class="text-center">{{ (page - 1) * pageSize + i + 1 }}</td>
                  <td class="page-wb-search-analytics__phrase" :title="m.phrase">
                    <router-link :to="`/wb-search/phrase?phrase=${encodeURIComponent(m.phrase)}&date_from=${filters.date_from}&date_to=${filters.date_to}`" target="_blank">{{ m.phrase }}</router-link>
                  </td>
                  <td class="text-end">{{ fmt0(m.total) }}</td>
                  <td class="text-end" :class="deltaClass(m.delta_total, m.is_new)">{{ deltaText(m.delta_total, m.is_new) }}</td>
                  <td class="text-end">
                    <div>{{ fmt0(m.freq) }}</div>
                    <div class="page-wb-search-analytics__sub" :class="deltaClass(m.delta, m.is_new)">{{ deltaText(m.delta, m.is_new) }}</div>
                  </td>
                  <td class="text-center">{{ fmt0(m.goods) }}</td>
                  <td class="text-center">{{ m.avg_pos ?? '—' }}</td>
                  <td class="text-center">{{ m.best_pos ?? '—' }}</td>
                  <td class="text-end">{{ fmt0(m.clicks) }}</td>
                  <td class="text-end">{{ fmt0(m.orders) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="totalPages > 1" class="card-footer d-flex gap-2 align-items-center">
            <button class="btn btn-sm btn-outline-secondary" :disabled="page <= 1" @click="goPage(page - 1)">‹ Назад</button>
            <span class="text-muted">Стр {{ page }} / {{ totalPages }}</span>
            <button class="btn btn-sm btn-outline-secondary" :disabled="page >= totalPages" @click="goPage(page + 1)">Вперед ›</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-search-analytics.css'
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbSearchFilter from '@/components/common/WbSearchFilter.vue'
import { wbSearchApi } from '@/api/search'

const route = useRoute()
const router = useRouter()

const today = new Date()
const defTo = new Date(today.getTime() - 864e5).toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 30 * 864e5).toISOString().slice(0, 10)

const filters = reactive({
  q: String(route.query.q || ''),
  date_from: String(route.query.date_from || defFrom),
  date_to: String(route.query.date_to || defTo),
})
const sort = ref(String(route.query.sort || 'freq'))

const models = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const prevFrom = ref('')
const prevTo = ref('')
const isLoading = ref(false)
const exporting = ref(false)
const phraseOptions = ref<Array<{ value: string; label: string }>>([])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtD = (s: string) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || ''); return m ? `${m[3]}.${m[2]}.${m[1]}` : s }

const sortMark = (k: string) => (sort.value === k ? '⇅' : '')
const deltaClass = (d: any, isNew: boolean) => {
  if (isNew) return 'page-wb-search-analytics__delta--new'
  if (Number(d) > 0) return 'page-wb-search-analytics__delta--up'
  if (Number(d) < 0) return 'page-wb-search-analytics__delta--down'
  return ''
}
const deltaText = (d: any, isNew: boolean) => {
  if (isNew) return 'new'
  const v = Number(d) || 0
  if (v > 0) return `▲ ${fmt0(v)}`
  if (v < 0) return `▼ ${fmt0(-v)}`
  return '0'
}

async function fetchData() {
  isLoading.value = true
  try {
    const data = await wbSearchApi.analytics(filters.q, filters.date_from, filters.date_to, sort.value, page.value)
    models.value = data.models || []
    total.value = Number(data.total) || 0
    pageSize.value = Number(data.page_size) || 50
    prevFrom.value = data.prev_from || ''
    prevTo.value = data.prev_to || ''
    document.title = 'Частотность поисковых запросов'
  } catch {
    models.value = []
  } finally {
    isLoading.value = false
  }
}

function syncRoute() {
  router.replace({
    path: '/wb-search/analytics',
    query: { q: filters.q || undefined, date_from: filters.date_from, date_to: filters.date_to, sort: sort.value },
  })
}

function onApply() {
  page.value = 1
  syncRoute()
  fetchData()
}

function onReset() {
  filters.q = ''
  filters.date_from = defFrom
  filters.date_to = defTo
  page.value = 1
  syncRoute()
  fetchData()
}

function setSort(k: string) {
  sort.value = k
  page.value = 1
  syncRoute()
  fetchData()
}

function goPage(p: number) {
  page.value = p
  fetchData()
}

async function exportExcel() {
  if (!models.value.length || exporting.value) return
  exporting.value = true
  try {
    const XLSX = await import('xlsx')
    const data = await wbSearchApi.analytics(filters.q, filters.date_from, filters.date_to, sort.value, 1, 5000)
    const rows = (data.models || []).map((m: any) => ({
      'Фраза': m.phrase,
      'Запросов': m.total,
      'Динамика': m.is_new ? 'new' : m.delta_total,
      'В день': m.freq,
      'Товаров': m.goods,
      'Ср. позиция': m.avg_pos ?? '',
      'Лучшая': m.best_pos ?? '',
      'Клики': m.clicks,
      'Заказы': m.orders,
    }))
    const ws = XLSX.utils.json_to_sheet(rows)
    ws['!cols'] = [{ wch: 40 }, { wch: 12 }, { wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 10 }]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Частотность')
    XLSX.writeFile(wb, `wb-search-analytics_${filters.date_from}_${filters.date_to}.xlsx`)
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  try {
    const list = await wbSearchApi.phrases()
    phraseOptions.value = list.map((p) => ({ value: p.phrase, label: `${p.phrase} (${p.max_frequency})` }))
  } catch {
    phraseOptions.value = []
  }
  await fetchData()
})
</script>
