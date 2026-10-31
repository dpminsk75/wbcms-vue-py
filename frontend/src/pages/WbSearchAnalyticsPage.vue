<template>
  <div class="container-xxl page-wb-search-analytics">
    <h1 class="page-title">Частотность поисковых запросов</h1>

    <!-- Фильтр: общий WbUniversalFilter (пресеты дат + «Применить/Сбросить»),
         поиск по запросам — в слоте #fields (общий WbPhraseSelect). -->
    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      :show-product="false"
      :show-brand-category="false"
      :show-quick="false"
      @apply="onApply"
      @reset="onReset"
    >
      <template #fields>
        <div class="wb-field wb-field--wide">
          <label class="wb-field__label">Поиск по запросам</label>
          <WbPhraseSelect v-model="filters.q" :options="phraseOptions" placeholder="Часть фразы..." />
        </div>
      </template>
    </WbUniversalFilter>

    <div class="row page-wb-search-analytics__grid mb-3 mt-3">
      <div class="col-md-12">
        <div class="tbl-card">
          <div class="card__hd">
            <span>
              Частотность запросов
              <span v-if="prevFrom" class="page-wb-search-analytics__period">
                с {{ fmtD(filters.date_from) }} по {{ fmtD(filters.date_to) }} в сравнении с {{ fmtD(prevFrom) }} по {{ fmtD(prevTo) }}
              </span>
            </span>
            <span class="spacer"></span>
            <ExcelButton :disabled="!models.length || exporting" @click="exportExcel" />
          </div>
          <div v-if="isLoading" class="text-center p-4">
            <span class="spinner-border spinner-border-sm"></span> Загрузка...
          </div>
          <div v-else class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="t-center page-wb-search-analytics__pos">#</th>
                  <th class="t-left page-wb-search-analytics__sticky">Поисковый запрос</th>
                  <th class="num page-wb-search-analytics__sort" @click="setSort('freq')">Запросов {{ sortMark('freq') }}</th>
                  <th class="num page-wb-search-analytics__sort" @click="setSort('delta')">Динамика {{ sortMark('delta') }}</th>
                  <th class="num page-wb-search-analytics__sort" @click="setSort('day')">В день {{ sortMark('day') }}</th>
                  <th class="num page-wb-search-analytics__sort" @click="setSort('goods')">Товаров {{ sortMark('goods') }}</th>
                  <th class="num page-wb-search-analytics__sort" @click="setSort('pos')">Ср. позиция {{ sortMark('pos') }}</th>
                  <th class="num page-wb-search-analytics__sort" @click="setSort('best')">Лучшая {{ sortMark('best') }}</th>
                  <th class="num">Клики</th>
                  <th class="num page-wb-search-analytics__sort" @click="setSort('orders')">Заказы {{ sortMark('orders') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!models.length"><td colspan="10" class="text-center text-muted p-4">Нет данных</td></tr>
                <tr v-for="(m, i) in models" :key="m.phrase">
                  <td class="t-center page-wb-search-analytics__pos">{{ (page - 1) * pageSize + i + 1 }}</td>
                  <td class="t-left page-wb-search-analytics__sticky" :title="m.phrase">
                    <router-link class="wb-query-link" :to="phraseUrl(m.phrase)">{{ m.phrase }}</router-link>
                  </td>
                  <td class="num">{{ fmt0(m.total) }}</td>
                  <td class="num" :class="deltaClass(m.delta_total, m.is_new)">{{ deltaText(m.delta_total, m.is_new) }}</td>
                  <td class="num">
                    <div>{{ fmt0(m.freq) }}</div>
                    <div class="page-wb-search-analytics__sub" :class="deltaClass(m.delta, m.is_new)">{{ deltaText(m.delta, m.is_new) }}</div>
                  </td>
                  <td class="num">{{ fmt0(m.goods) }}</td>
                  <td class="num">{{ m.avg_pos ?? '—' }}</td>
                  <td class="num">{{ m.best_pos ?? '—' }}</td>
                  <td class="num">{{ fmt0(m.clicks) }}</td>
                  <td class="num">{{ fmt0(m.orders) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <Pager :page="page" :total-pages="totalPages" :total="total" @change="goPage" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-search-analytics.css'
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import WbPhraseSelect from '@/components/common/WbPhraseSelect.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import Pager from '@/components/common/Pager.vue'
import { exportXlsx } from '@/utils/exportXlsx'
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

/** Ссылка на разбор фразы: единый параметр (phrase) + период. */
const phraseUrl = (phrase: string) =>
  `/wb-search/phrase?phrase=${encodeURIComponent(phrase)}&date_from=${filters.date_from}&date_to=${filters.date_to}`

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
    await exportXlsx({
      rows,
      filename: `wb-search-analytics_${filters.date_from}_${filters.date_to}.xlsx`,
      sheetName: 'Частотность',
      cols: [{ wch: 40 }, { wch: 12 }, { wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 10 }],
    })
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
