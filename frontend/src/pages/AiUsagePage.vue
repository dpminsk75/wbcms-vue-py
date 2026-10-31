<template>
  <div class="container-xxl page-ai-usage">
    <div class="row mb-3">
      <h2 class="page-ai-usage__title">Затраты ИИ</h2>
    </div>

    <div class="row mb-3">
      <div class="col-md-12">
        <WbUniversalFilter
          v-model:date-from="filters.date_from"
          v-model:date-to="filters.date_to"
          v-model:product="filters.product"
          v-model:brand="filters.brand"
          v-model:category="filters.category"
          :show-product="false"
          :show-brand-category="false"
          :show-quick="false"
          default-preset="30"
          preset-end="today"
          @apply="load()"
          @reset="onReset()"
        />
      </div>
    </div>

    <div class="row g-2 mb-3 page-ai-usage__filters">
      <div class="col-md-3">
        <label class="form-label">Группировка</label>
        <select v-model="filters.group_by" class="form-select form-select-sm" @change="load()">
          <option v-for="(label, key) in groupOptions" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
      <div class="col-md-3">
        <label class="form-label">Сценарий</label>
        <select v-model="filters.scenario" class="form-select form-select-sm" @change="load()">
          <option value="">Все</option>
          <option v-for="(label, key) in scenarioOptions" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
      <div class="col-md-3">
        <label class="form-label">Провайдер</label>
        <select v-model="filters.provider" class="form-select form-select-sm" @change="load()">
          <option value="">Все</option>
          <option value="openrouter">OpenRouter</option>
          <option value="custom">Другой сервис</option>
        </select>
      </div>
      <div class="col-md-3">
        <label class="form-label">Модель</label>
        <select v-model="filters.model" class="form-select form-select-sm" @change="load()">
          <option value="">Все</option>
          <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
    </div>

    <div class="card">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span>
          {{ groupLabel }}
          <small v-if="isDetail" class="text-muted">— детализация по вызовам<template v-if="detailFilterText"> · {{ detailFilterText }}</template></small>
        </span>
        <div class="d-flex align-items-center gap-2">
          <button v-if="isDetail" class="btn btn-sm btn-light" @click="backToSummary">
            <i class="bi bi-arrow-left me-1"></i> К сводке
          </button>
          <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!rows.length || exporting">
            <i class="bi bi-file-earmark-excel me-1"></i> Excel
          </button>
        </div>
      </div>

      <div v-if="isLoading" class="text-center p-5">
        <div class="spinner-border text-primary" role="status"></div>
        <div class="mt-2 text-muted">Загрузка данных...</div>
      </div>
      <div v-else-if="error" class="p-3 page-ai-usage__err">{{ error }}</div>
      <div v-else-if="!rows.length" class="page-ai-usage__empty">За выбранный период вызовов ИИ не было</div>
      <div v-else class="wb-table-wrap">
        <table class="table table-bordered table-hover mb-0 page-ai-usage__table">
          <thead>
            <tr v-if="!isDetail">
              <th>{{ groupTitle }}</th>
              <th class="page-ai-usage__num">Вызовы</th>
              <th class="page-ai-usage__num">Токены (вход)</th>
              <th class="page-ai-usage__num">Токены (выход)</th>
              <th class="page-ai-usage__num">Всего</th>
              <th v-if="canSeeCost" class="page-ai-usage__num">Стоимость, $</th>
              <th class="page-ai-usage__num">Ошибок</th>
            </tr>
            <tr v-else>
              <th>Дата и время</th>
              <th>Сценарий</th>
              <th>Провайдер</th>
              <th>Модель</th>
              <th>nmID</th>
              <th>Сотрудник</th>
              <th class="page-ai-usage__num">Токены</th>
              <th v-if="canSeeCost" class="page-ai-usage__num">Стоимость, $</th>
              <th>Статус</th>
              <th>Ответ (начало)</th>
            </tr>
          </thead>
          <tbody>
            <template v-if="!isDetail">
              <tr v-for="r in rows" :key="String(r.grp)">
                <td class="page-ai-usage__grp" @click="openGroup(r)">{{ grpTitle(r) }}</td>
                <td class="page-ai-usage__num">{{ r.calls }}</td>
                <td class="page-ai-usage__num">{{ r.prompt_tokens.toLocaleString('ru-RU') }}</td>
                <td class="page-ai-usage__num">{{ r.completion_tokens.toLocaleString('ru-RU') }}</td>
                <td class="page-ai-usage__num">{{ r.total_tokens.toLocaleString('ru-RU') }}</td>
                <td v-if="canSeeCost" class="page-ai-usage__num">{{ fmtCost(r.cost) }}</td>
                <td class="page-ai-usage__num">{{ r.failed || 0 }}</td>
              </tr>
            </template>
            <template v-else>
              <tr v-for="r in rows" :key="r.id">
                <td>{{ fmtDT(r.created_at) }}</td>
                <td>{{ scenarioOptions[r.scenario || ''] || r.scenario }}</td>
                <td>{{ r.provider === 'custom' ? 'Другой сервис' : 'OpenRouter' }}</td>
                <td>{{ r.model }}</td>
                <td>
                  <a v-if="r.nm_id" href="#" @click.prevent="openModal(r)">{{ r.nm_id }}</a>
                  <span v-else>—</span>
                </td>
                <td>{{ r.user_name || (r.user_id ? 'user #' + r.user_id : '—') }}</td>
                <td class="page-ai-usage__num">{{ (r.total_tokens || 0).toLocaleString('ru-RU') }}</td>
                <td v-if="canSeeCost" class="page-ai-usage__num">{{ fmtCost(r.cost) }}</td>
                <td>
                  <span v-if="r.ok" class="page-ai-usage__ok">ок</span>
                  <span v-else class="page-ai-usage__err" :title="r.error">{{ r.error || 'ошибка' }}</span>
                </td>
                <td class="page-ai-usage__preview" @click="openModal(r)">
                  {{ (r.preview || '').slice(0, 160) || '—' }}
                  <i v-if="r.preview" class="bi bi-box-arrow-up-right"></i>
                </td>
              </tr>
            </template>
            <tr v-if="!isDetail" class="kv-totals">
              <td>Итого</td>
              <td class="page-ai-usage__num">{{ totals.calls }}</td>
              <td class="page-ai-usage__num">{{ totals.prompt_tokens.toLocaleString('ru-RU') }}</td>
              <td class="page-ai-usage__num">{{ totals.completion_tokens.toLocaleString('ru-RU') }}</td>
              <td class="page-ai-usage__num">{{ totals.total_tokens.toLocaleString('ru-RU') }}</td>
              <td v-if="canSeeCost" class="page-ai-usage__num">{{ fmtCost(totals.cost) }}</td>
              <td class="page-ai-usage__num">{{ totals.failed }}</td>
            </tr>
            <tr v-else class="kv-totals">
              <td>Итого</td>
              <td colspan="5"></td>
              <td class="page-ai-usage__num">{{ totals.total_tokens.toLocaleString('ru-RU') }}</td>
              <td v-if="canSeeCost" class="page-ai-usage__num">{{ fmtCost(totals.cost) }}</td>
              <td colspan="2"></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="modalOpen" class="page-ai-usage__modal-backdrop" @click.self="closeModal">
      <div class="page-ai-usage__modal-box">
        <div class="page-ai-usage__modal-head">
          <h5 class="page-ai-usage__modal-title"><i class="bi bi-file-text me-1"></i> Вызов ИИ</h5>
          <button type="button" class="btn-close" @click="closeModal" aria-label="Close"></button>
        </div>

        <div class="page-ai-usage__modal-meta">
          <div><b>Дата:</b> {{ fmtDT(modalRow?.created_at) }}</div>
          <div><b>Сценарий:</b> {{ modalRow?.scenario ? (SCENARIO_OPTIONS[modalRow.scenario] || modalRow.scenario) : '—' }}</div>
          <div><b>Провайдер:</b> {{ modalRow?.provider === 'custom' ? 'Другой сервис' : 'OpenRouter' }}</div>
          <div><b>Модель:</b> {{ modalRow?.model || '—' }}</div>
          <div><b>nmID:</b> {{ modalRow?.nm_id || '—' }}</div>
          <div><b>Сотрудник:</b> {{ modalRow?.user_name || (modalRow?.user_id ? 'user #' + modalRow.user_id : '—') }}</div>
          <div><b>HTTP:</b> {{ modalRow?.http_status || '—' }}</div>
          <div><b>Токены:</b> {{ (modalRow?.total_tokens || 0).toLocaleString('ru-RU') }}</div>
          <div v-if="canSeeCost"><b>Стоимость:</b> {{ fmtCost(modalRow?.cost) }}</div>
        </div>

        <div v-if="modalRow?.error" class="page-ai-usage__modal-error">{{ modalRow.error }}</div>

        <div class="page-ai-usage__modal-label">Ответ модели</div>
        <pre class="page-ai-usage__modal-text">{{ modalRow?.preview || '(ответ пустой)' }}</pre>

        <template v-if="modalArtifacts.length">
          <div class="page-ai-usage__modal-label">Что сгенерировали (артефакт)</div>
          <div v-for="(a, i) in modalArtifacts" :key="i" class="page-ai-usage__artifact">
            <div class="page-ai-usage__artifact-title">{{ a.title || '(без заголовка)' }}</div>
            <div class="text-muted small mb-1">{{ a.extra?.model || '' }}</div>
            <div class="page-ai-usage__artifact-text">{{ a.text || a.extra?.old_title || '' }}</div>
          </div>
        </template>
        <div v-else-if="modalLoading" class="text-muted small">Загрузка артефакта...</div>

        <div class="page-ai-usage__modal-foot">
          <button type="button" class="btn btn-secondary btn-sm" @click="closeModal">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-ai-usage.css'
import { ref, reactive, computed, onMounted } from 'vue'
import WbUniversalFilter from '../components/common/WbUniversalFilter.vue'
import { aiUsageApi, type AiUsageRow } from '../api/aiUsage'
import { useDateFmt } from '../composables/useDateFmt'

const { fmtDT } = useDateFmt()

const GROUP_OPTIONS: Record<string, string> = {
  model: 'По модели',
  provider: 'По провайдеру',
  scenario: 'По сценарию',
  company: 'По компании',
  user: 'По сотруднику',
  day: 'По дню',
  month: 'По месяцу',
  detail: 'Детально (по вызовам)',
}
const SCENARIO_OPTIONS: Record<string, string> = {
  seo: 'SEO-рекомендации',
  competitor: 'Анализ конкурента',
  summary: 'Сводка по конкурентам',
  newcard_phrases: 'Фразы (новый товар)',
  newcard_phrases_miner: 'Фразы (фон-разбор)',
  newcard_generate: 'Title+Description (новый товар)',
  review_analysis: 'Разбор жалоб по отзывам',
  test: 'Проба подключения',
  other: 'Прочее',
}

const filters = reactive({
  date_from: '', date_to: '',
  group_by: 'model', scenario: '', provider: '', model: '',
  user_id: '', company_id: '',
  product: '', brand: '', category: '',
})
const rows = ref<AiUsageRow[]>([])
const totals = ref({ calls: 0, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, cost: 0, failed: 0 })
const models = ref<string[]>([])
const canSeeCost = ref(false)
const isLoading = ref(false)
const exporting = ref(false)
const error = ref('')
const modalOpen = ref(false)
const modalRow = ref<AiUsageRow | null>(null)
const modalArtifacts = ref<Array<Record<string, any>>>([])
const modalLoading = ref(false)

const groupOptions = GROUP_OPTIONS
const scenarioOptions = SCENARIO_OPTIONS
const isDetail = computed(() => filters.group_by === 'detail')
const detailFilterText = computed(() => {
  const parts: string[] = []
  if (filters.model) parts.push('модель: ' + filters.model)
  if (filters.provider) parts.push('провайдер: ' + (filters.provider === 'custom' ? 'другой сервис' : 'OpenRouter'))
  if (filters.scenario) parts.push('сценарий: ' + (SCENARIO_OPTIONS[filters.scenario] || filters.scenario))
  if (filters.user_id) parts.push('сотрудник: #' + filters.user_id)
  if (filters.company_id) parts.push('компания: #' + filters.company_id)
  return parts.join(', ')
})
const groupLabel = computed(() => GROUP_OPTIONS[filters.group_by] || 'Сводка')
const groupTitle = computed(() => {
  const g = filters.group_by
  if (g === 'day') return 'День'
  if (g === 'month') return 'Месяц'
  if (g === 'company') return 'Компания'
  if (g === 'user') return 'Сотрудник'
  if (g === 'scenario') return 'Сценарий'
  if (g === 'provider') return 'Провайдер'
  return 'Модель'
})

function grpTitle(r: AiUsageRow): string {
  const g = r.grp
  if (filters.group_by === 'company') return r.company_name || (g ? `Компания #${g}` : '—')
  if (filters.group_by === 'user') return r.user_name || (g ? `user #${g}` : '—')
  if (filters.group_by === 'scenario') return SCENARIO_OPTIONS[String(g)] || String(g ?? '—')
  if (filters.group_by === 'provider') return g === 'custom' ? 'Другой сервис' : 'OpenRouter'
  return String(g ?? '—')
}

function fmtCost(v: number | null | undefined): string {
  const n = Number(v || 0)
  if (!n) return '0'
  return n < 0.01 ? n.toFixed(6) : n.toFixed(4)
}

/** Дефолтный период — последние 30 дней (как пресет «30 дней» фильтра). */
function initDates() {
  const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 29)
  filters.date_from = fmtD(from)
  filters.date_to = fmtD(to)
}

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    const params: Record<string, any> = { group_by: filters.group_by }
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
    if (filters.scenario) params.scenario = filters.scenario
    if (filters.provider) params.provider = filters.provider
    if (filters.model) params.model = filters.model
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.company_id) params.company_id = filters.company_id
    const d = await aiUsageApi.summary(params)
    rows.value = d.rows || []
    totals.value = d.totals || totals.value
    models.value = d.models || []
    canSeeCost.value = !!d.can_see_cost
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    rows.value = []
  } finally {
    isLoading.value = false
  }
}

function onReset() {
  filters.scenario = ''
  filters.provider = ''
  filters.model = ''
  filters.user_id = ''
  filters.company_id = ''
  filters.group_by = 'model'
  initDates()
  load()
}

/** Клик по строке сводки → детализация по этой группе. */
function openGroup(r: AiUsageRow) {
  const g = filters.group_by
  const val = String(r.grp ?? '')
  if (g === 'model') filters.model = val
  else if (g === 'provider') filters.provider = val
  else if (g === 'scenario') filters.scenario = val
  else if (g === 'user') filters.user_id = val
  else if (g === 'company') filters.company_id = val
  else if (g === 'day') { filters.date_from = val; filters.date_to = val }
  else if (g === 'month') {
    // YYYY-MM → первое и последнее число месяца
    const y = Number(val.slice(0, 4)), m = Number(val.slice(5, 7))
    const last = new Date(y, m, 0).getDate()
    filters.date_from = `${val}-01`
    filters.date_to = `${val}-${String(last).padStart(2, '0')}`
  }
  filters.group_by = 'detail'
  load()
}

function backToSummary() {
  filters.group_by = 'model'
  filters.user_id = ''
  filters.company_id = ''
  load()
}

/** Клик по строке/ячейке ответа → модалка с полным текстом и артефактом. */
async function openModal(r: AiUsageRow) {
  modalRow.value = r
  modalOpen.value = true
  modalArtifacts.value = []
  if (r.nm_id && r.scenario) {
    modalLoading.value = true
    try {
      const d = await aiUsageApi.artifacts(r.scenario, r.nm_id)
      modalArtifacts.value = d.items || []
    } catch {
      modalArtifacts.value = []
    } finally {
      modalLoading.value = false
    }
  }
}
function closeModal() {
  modalOpen.value = false
}

async function exportExcel() {
  if (!rows.value.length) return
  exporting.value = true
  try {
    const XLSX = await import('xlsx')
    let data: Array<Record<string, any>>
    if (isDetail.value) {
      data = rows.value.map((r: any) => ({
        'Дата': r.created_at, 'Сценарий': SCENARIO_OPTIONS[r.scenario] || r.scenario,
        'Провайдер': r.provider === 'custom' ? 'Другой сервис' : 'OpenRouter',
        'Модель': r.model, 'nmID': r.nm_id || '',
        'Сотрудник': r.user_name || (r.user_id ? 'user #' + r.user_id : ''),
        'Токены вход': r.prompt_tokens, 'Токены выход': r.completion_tokens,
        'Токены всего': r.total_tokens, 'Стоимость $': r.cost,
        'Статус': r.ok ? 'ок' : (r.error || 'ошибка'), 'Ответ': r.preview || '',
      }))
    } else {
      data = rows.value.map((r: any) => ({
        [groupTitle.value]: grpTitle(r), 'Вызовы': r.calls,
        'Токены (вход)': r.prompt_tokens, 'Токены (выход)': r.completion_tokens,
        'Токены всего': r.total_tokens, 'Стоимость $': r.cost, 'Ошибок': r.failed,
      }))
    }
    const ws = XLSX.utils.json_to_sheet(data)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Затраты ИИ')
    XLSX.writeFile(wb, `ai_usage_${filters.date_from}_${filters.date_to}.xlsx`)
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  initDates()
  load()
})
</script>
