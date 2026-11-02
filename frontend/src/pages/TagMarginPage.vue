<template>
  <div class="container-xxl page-tag-margin">
    <WbWorkspaceHead title="Маржа по тегу" :workspace-tabs="TAGS_WORKSPACE_TABS" workspace-active="margin" />

    <!-- Облаво тегов — выбор тега (общий компонент раздела) -->
    <div class="wb-panel page-tag-margin__cloud">
      <div class="wb-panel__bd">
        <TagCloud :tags="tagOptions" :active-id="filters.tag_id" @pick="onPickTag" />
      </div>
    </div>

    <!-- Фильтр: даты + поля отчёта (в одну строку) + кнопки отчёта -->
    <div class="wb-filter-panel">
      <WbDateRangeFilter
        v-model:from="filters.date_from"
        v-model:to="filters.date_to"
        default-preset="30"
        bare
      >
        <template #inline>
          <div class="page-tag-margin__fields">
            <div class="wb-field">
              <label class="wb-field__label" for="tm-sort">Сортировать по</label>
              <select id="tm-sort" v-model="filters.sort_by" class="wb-select">
                <option value="qnt">Количеству продаж (шт)</option>
                <option value="amount">Выручке (руб)</option>
                <option value="net_profit">По итогу от WB (руб)</option>
                <option value="clean_margin">Марже после налогов (руб)</option>
              </select>
            </div>
            <button
              type="button"
              class="opt page-tag-margin__stock"
              :aria-pressed="filters.with_stock"
              @click="filters.with_stock = !filters.with_stock"
            >
              Остатки
            </button>
            <span v-if="stockDate" class="page-tag-margin__hint">Остатки на {{ stockDate }}</span>
          </div>
        </template>
      </WbDateRangeFilter>

      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" :disabled="isLoading" @click="onApply">
          Применить
        </button>
        <button class="btn btn--outline" :disabled="isLoading" @click="onReset">Сбросить</button>
      </div>
    </div>

    <!-- Отчёт -->
    <div class="tbl-card">
      <div class="card__hd">
        <span>{{ headerLabel }}</span>
        <span class="spacer"></span>
        <span class="hd-badge">{{ applied.date_from }} — {{ applied.date_to }}</span>
        <ExcelButton :disabled="!rows.length" @click="exportExcel" />
      </div>

      <div v-if="isLoading" class="wb-panel__bd page-tag-margin__state">
        <span class="page-tag-margin__spin" aria-hidden="true"></span>Загрузка данных…
      </div>
      <div v-else-if="error" class="wb-panel__bd page-tag-margin__state page-tag-margin__state--bad">
        {{ error }}
      </div>
      <MarginTable
        v-else
        :rows="rows"
        footer-label="Итого по тегу:"
        :show-stock="applied.with_stock"
        :period="`${applied.date_from} — ${applied.date_to}`"
        :date-from="applied.date_from"
        :date-to="applied.date_to"
        show-breakdown
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-tag-margin.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import WbDateRangeFilter from '@/components/common/WbDateRangeFilter.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import TagCloud from '@/components/tags/TagCloud.vue'
import MarginTable from '@/components/profit/MarginTable.vue'
import { exportMarginExcel } from '@/api/profit'
import { tagsApi, type TagItem } from '@/api/tags'
import { TAGS_WORKSPACE_TABS } from '@/components/common/workspaceTabs'

const route = useRoute()
const router = useRouter()

const SORTS = ['qnt', 'amount', 'net_profit', 'clean_margin']

// локальное время (toISOString даёт UTC и сдвигает сутки) — период всегда заканчивается сегодня
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const defaultDates = () => {
  const to = new Date()
  const from = new Date(to.getFullYear(), to.getMonth(), to.getDate() - 29)
  return { date_from: fmtD(from), date_to: fmtD(to) }
}

const defaults = () => {
  const d = defaultDates()
  return { date_from: d.date_from, date_to: d.date_to, tag_id: '', sort_by: 'qnt', with_stock: false }
}

/** URL → фильтры (значения по умолчанию — если параметра нет). */
const fromRoute = (q: any) => {
  const d = defaultDates()
  const s = String(q.sort_by || '')
  return {
    date_from: String(q.date_from || d.date_from),
    date_to: String(q.date_to || d.date_to),
    tag_id: String(q.id || ''),
    sort_by: SORTS.includes(s) ? s : 'qnt',
    with_stock: q.with_stock === '1',
  }
}

// filters — черновик (что выбрал пользователь), applied — по чему реально запрошены данные
const filters = ref(fromRoute(route.query))
const applied = ref({ ...filters.value })

const tagOptions = ref<TagItem[]>([])
const rows = ref<any[]>([])
const isLoading = ref(false)
const error = ref('')

const currentTag = computed(() => tagOptions.value.find((t) => String(t.id) === String(applied.value.tag_id)))
const headerLabel = computed(() => currentTag.value ? `Маржа: ${currentTag.value.name}` : 'Маржа по тегу')

// Фактическая дата снимка остатков (может быть < date_to — фолбэк)
const stockDate = computed(() => {
  if (!applied.value.with_stock) return ''
  const d = rows.value[0]?.stock_date
  return d ? String(d).slice(0, 10) : ''
})

/** URL → фильтры (навигация назад/вперёд, чужая ссылка). */
function applyFromRoute(nq: any) {
  const next = fromRoute(nq)
  const cur = applied.value
  if (cur.date_from !== next.date_from || cur.date_to !== next.date_to ||
      cur.tag_id !== next.tag_id || cur.sort_by !== next.sort_by ||
      cur.with_stock !== next.with_stock) {
    filters.value = { ...next }
    applied.value = { ...next }
    fetchData()
  }
}

// фильтры → URL (replace, чтобы не плодить историю)
let syncing = false
function syncRoute() {
  const q: Record<string, string> = {
    date_from: applied.value.date_from,
    date_to: applied.value.date_to,
  }
  if (applied.value.tag_id) q.id = String(applied.value.tag_id)
  if (applied.value.sort_by !== 'qnt') q.sort_by = applied.value.sort_by
  if (applied.value.with_stock) q.with_stock = '1'
  syncing = true
  router.replace({ path: '/tag/margin', query: q })
    .finally(() => setTimeout(() => (syncing = false), 50))
}

async function fetchTags() {
  try {
    tagOptions.value = await tagsApi.list()
  } catch {
    tagOptions.value = []
  }
}

async function fetchData() {
  if (!applied.value.tag_id) {
    rows.value = []
    return
  }
  isLoading.value = true
  error.value = ''
  try {
    rows.value = await tagsApi.margin(
      applied.value.tag_id, applied.value.date_from, applied.value.date_to,
      applied.value.sort_by, applied.value.with_stock,
    )
    document.title = `${currentTag.value ? currentTag.value.name : 'Маржа по тегу'} — маржа — SelBI`
  } catch {
    error.value = 'Не удалось загрузить маржу по тегу.'
    rows.value = []
  } finally {
    isLoading.value = false
  }
}

/** Выбор тега в облаве — меняет черновик; отчёт перезапрашивается по «Применить». */
function onPickTag(t: TagItem) {
  filters.value.tag_id = String(t.id)
}

/** Применить фильтры: черновик → применённое → URL → запрос. */
function onApply() {
  applied.value = { ...filters.value }
  syncRoute()
  fetchData()
}

/** Сбросить фильтры к значениям по умолчанию (период 30 дней, первый тег, сортировка qnt). */
function onReset() {
  const d = defaults()
  d.tag_id = tagOptions.value.length ? String(tagOptions.value[0].id) : ''
  filters.value = { ...d }
  applied.value = { ...d }
  syncRoute()
  fetchData()
}

function exportExcel() {
  exportMarginExcel(
    rows.value,
    `tag-margin_${applied.value.tag_id}_${applied.value.date_from}_${applied.value.date_to}.xlsx`,
    'Маржа тега',
    applied.value.with_stock,
  )
}

watch(() => route.query, (nq) => {
  if (syncing) return
  applyFromRoute(nq)
})

onMounted(async () => {
  await fetchTags()
  if (!applied.value.tag_id && tagOptions.value.length) {
    const first = String(tagOptions.value[0].id)
    filters.value.tag_id = first
    applied.value.tag_id = first
    syncRoute()
  }
  await fetchData()
})
</script>
