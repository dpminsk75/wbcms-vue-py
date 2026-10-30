<template>
  <div class="container-xxl page-wb-search-cannibalization">
    <WbWorkspaceHead title="Каннибализация запросов" :workspace-tabs="[]" />

    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:product="filters.product"
      v-model:brand="filters.brand"
      v-model:category="filters.category"
      :presets="presets"
      default-preset="70"
      :brands="filterLists.brands"
      :categories="filterLists.categories"
      @apply="onApply"
      @reset="onReset"
    />

    <div class="tbl-card">
      <div class="card__hd">
        <span>Список фраз, по которым ранжируются 2 и более ваших товаров</span>
        <span class="spacer"></span>
        <span class="hd-badge">Фраз: {{ total }}</span>
        <ExcelButton :disabled="!rows.length" @click="exportRows" />
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="t-left">Поисковый запрос</th>
              <th class="t-center">Ср. част</th>
              <th class="t-center">Кол-во артикулов</th>
              <th class="t-left">Ваши товары в выдаче</th>
              <th class="t-center">Всего кликов</th>
              <th class="t-center">Всего заказов</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td colspan="6" class="text-center text-muted py-3">
                {{ loading ? 'Загрузка…' : 'Нет фраз за выбранный период' }}
              </td>
            </tr>
            <tr v-for="r in rows" :key="r.phrase">
              <td class="t-left">
                <router-link class="page-wb-search-cannibalization__phrase" :to="phraseUrl(r.phrase)">
                  {{ r.phrase }}
                </router-link>
              </td>
              <td class="t-center num">{{ fmt0(r.avg_freq) }}</td>
              <td class="t-center">
                <span class="badge" :class="r.cards_count >= 3 ? 'badge--bad' : 'badge--warn'">
                  {{ r.cards_count }}
                </span>
              </td>
              <td class="t-left page-wb-search-cannibalization__cards">
                <router-link
                  v-for="c in r.cards"
                  :key="c.nm_id"
                  class="badge badge--brand me-1"
                  :to="cardUrl(c.nm_id)"
                  :title="c.title || String(c.nm_id)"
                >
                  {{ c.nm_id }}<template v-if="c.avg_pos"> · поз. {{ fmt0(c.avg_pos) }}</template>
                </router-link>
              </td>
              <td class="t-center num">{{ fmt0(r.total_clicks) }}</td>
              <td class="t-center num">{{ fmt0(r.total_orders) }}</td>
            </tr>
          </tbody>
          <tfoot v-if="rows.length">
            <tr class="tbl__total">
              <td class="t-left">Итого (на странице)</td>
              <td class="t-center">—</td>
              <td class="t-center">{{ sumCards }}</td>
              <td class="t-left">—</td>
              <td class="t-center">{{ sumClicks }}</td>
              <td class="t-center">{{ sumOrders }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <Pager :page="page" :total-pages="totalPages" :total="total" @change="goPage" />
  </div>
</template>

<script setup lang="ts">
/**
 * Каннибализация запросов — порт Yii2 `wb-search/cannibalization`
 * (WbSearchController::actionCannibalization).
 *
 * Смысл: фразы, по которым в выдаче WB ранжируются ≥2 наших карточек —
 * они «размывают» продажи между своими же карточками.
 *
 * Отличия от PHP:
 *  * позиция карточки по фразе (в Yii2 её не было) — из того же отчёта WB;
 *  * пагинация (в PHP её не было, GROUP_CONCAT резался на 1024 байтах);
 *  * N+1 убран — карточки приходят одним запросом с агрегатом.
 */
import '@/assets/css/pages/page-wb-search-cannibalization.css'
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { wbSearchApi } from '@/api/search'
import { DEFAULT_PRESETS_UNIVERSAL } from '@/constants/presets'
import { useNumFmt } from '@/composables/useNumFmt'
import { exportXlsx } from '@/utils/exportXlsx'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import Pager from '@/components/common/Pager.vue'

const { fmt0 } = useNumFmt()

// локальное время (toISOString даёт UTC и сдвигает сутки)
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const defaultDates = () => {
  const to = new Date()
  const from = new Date(to.getTime())
  from.setDate(from.getDate() - 69)
  return { date_from: iso(from), date_to: iso(to) }
}
const defaults = defaultDates()

/** Пресет «70 дней» — период PHP по умолчанию (getDPWidget::getParams(70)). */
const presets = [...DEFAULT_PRESETS_UNIVERSAL, { id: '70', label: '70 дней' }]

const filters = ref({
  product: '',
  brand: '',
  category: '',
  date_from: defaults.date_from,
  date_to: defaults.date_to,
})

const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
/** Справочники для селектов «Бренд» / «Категория» — из карточек компании. */
const filterLists = ref<{ brands: string[]; categories: string[] }>({ brands: [], categories: [] })

const loadFilterLists = async () => {
  try {
    const { data } = await api.get('/api/wb-cards/filters')
    filterLists.value = {
      brands: Array.isArray(data?.brands) ? data.brands : [],
      categories: Array.isArray(data?.subjectNames) ? data.subjectNames : [],
    }
  } catch {
    filterLists.value = { brands: [], categories: [] }
  }
}

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)))
const sumCards = computed(() => rows.value.reduce((s, r) => s + (r.cards_count || 0), 0))
const sumClicks = computed(() => rows.value.reduce((s, r) => s + (r.total_clicks || 0), 0))
const sumOrders = computed(() => rows.value.reduce((s, r) => s + (r.total_orders || 0), 0))

const phraseUrl = (phrase: string) => `/wb-search/phrase?phrase=${encodeURIComponent(phrase)}`
const cardUrl = (nmId: number) => `/wb-search/card?nm_id=${nmId}`

/** WbUniversalFilter отдаёт свободную маску (nm_id/артикул/название) — резолвим в nm_id. */
const resolveNmId = async (mask: string): Promise<number | null> => {
  const q = String(mask || '').trim()
  if (!q) return null
  if (/^\d+$/.test(q)) return Number(q)
  try {
    const { data } = await api.get('/api/wb/cards', { params: { q, limit: 20 } })
    const list: any[] = Array.isArray(data) ? data : []
    const exact = list.find((c: any) => String(c.nmID) === q || String(c.vendorCode || '') === q)
    if (exact) return Number(exact.nmID)
    return list.length === 1 ? Number(list[0].nmID) : null
  } catch {
    return null
  }
}

const load = async () => {
  loading.value = true
  try {
    const nmId = await resolveNmId(filters.value.product)
    const data = await wbSearchApi.cannibalization(filters.value.date_from, filters.value.date_to, {
      nmId,
      brand: filters.value.brand || undefined,
      category: filters.value.category || undefined,
      page: page.value,
      pageSize,
    })
    rows.value = Array.isArray(data?.models) ? data.models : []
    total.value = Number(data?.total || 0)
  } catch (e) {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const onApply = () => { page.value = 1; load() }
const onReset = () => {
  filters.value.product = ''
  filters.value.brand = ''
  filters.value.category = ''
  filters.value.date_from = defaults.date_from
  filters.value.date_to = defaults.date_to
  page.value = 1
  load()
}
const goPage = (p: number) => { page.value = p; load() }

/** Excel: русские заголовки + ширины колонок. */
const exportRows = async () => {
  const data = rows.value.map((r) => {
    const row: Record<string, any> = {
      'Поисковый запрос': r.phrase,
      'Ср. част': r.avg_freq,
      'Кол-во артикулов': r.cards_count,
      'Ваши товары': (r.cards || []).map((c: any) => `${c.nm_id} (поз. ${c.avg_pos ?? '—'})`).join(', '),
      'Всего кликов': r.total_clicks,
      'Всего заказов': r.total_orders,
    }
    return row
  })
  await exportXlsx({
    rows: data,
    filename: 'каннибализация-запросов.xlsx',
    sheetName: 'Каннибализация',
    cols: [{ wch: 34 }, { wch: 10 }, { wch: 16 }, { wch: 40 }, { wch: 14 }, { wch: 14 }],
  })
}

onMounted(() => { loadFilterLists(); load() })
</script>
