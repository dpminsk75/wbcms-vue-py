<template>
  <div class="container-xxl page-feedback-insights">
    <WbWorkspaceHead :title="$route.meta.title || 'Инсайты'" :workspace-tabs="FEEDBACK_TABS" workspace-active="insights" />

    <!-- Фильтр (тот же, что в /geo/sales-map) -->
    <WbUniversalFilter
      v-model:product="filters.product"
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:brand="filters.brand"
      v-model:category="filters.category"
      :brands="brands"
      :categories="categories"
      @apply="load"
      @reset="onReset"
    />

    <!-- Запуск: показаны инсайты только этого задания -->
    <div v-if="jobId" class="page-feedback-insights__job-note">
      <i class="bi bi-filters"></i>
      Показаны инсайты задания <b>#{{ jobId }}</b>.
      <button class="btn btn--outline btn-sm ms-2" @click="showAllJobs">Показать все</button>
    </div>

    <div v-if="error" class="wb-error mb-3">{{ error }}</div>

    <!-- Таблица инсайтов — блок темы .tbl-card -->
    <div class="tbl-card page-feedback-insights__card">
      <div class="card__hd">
        <span>Инсайты</span>
        <span class="hd-badge">Разборов: {{ total }}</span>
        <span class="spacer"></span>
        <ExcelButton :disabled="!insights.length" @click="exportExcel" />
      </div>
      <p class="page-feedback-insights__note">
        Строка — ИИ-разбор одной карточки по отзывам за период; строки сгруппированы по запускам разбора.
      </p>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="page-feedback-insights__col-check"></th>
              <th class="page-feedback-insights__col-card t-left">Карточка</th>
              <th class="t-center">Отзывов</th>
              <th class="t-center">Ср. оценка</th>
              <th class="t-left">Что делать</th>
              <th class="t-center">Период отзывов</th>
              <th class="t-center">Разобрано</th>
              <th class="page-feedback-insights__col-check"></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="g in grouped" :key="g.key">
            <tr class="page-feedback-insights__group">
              <td :colspan="8">
                <span class="page-feedback-insights__group-title">
                  {{ g.job != null ? 'Запуск #' + g.job : 'Без запуска' }}
                </span>
                <span class="page-feedback-insights__group-meta">{{ g.at }} · {{ g.items.length }} карточек</span>
              </td>
            </tr>
            <template v-for="it in g.items" :key="it.id">
            <tr :class="{ 'page-feedback-insights__row--picked': openInsight === it.id }">
              <td class="t-center">
                <button class="btn btn--outline btn-sm"
                        @click="openInsight = openInsight === it.id ? 0 : it.id">
                  <i class="bi" :class="openInsight === it.id ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                </button>
              </td>
              <td class="t-left">
                <ProductCell
                  :photo="it.card_photos"
                  :title="it.card_title || ''"
                  :brand="it.brand || ''"
                  :subject="it.subject_name || ''"
                  :vendor="it.vendor_code || ''"
                  :nm-id="it.nm_id"
                  :link="'/wb/detail?nm_id=' + it.nm_id"
                  :link-label="'WB: ' + it.nm_id"
                  copy-nm
                  copy-link
                />
              </td>
              <td class="t-center">{{ it.reviews_cnt }}</td>
              <td class="t-center">{{ it.avg_rating ?? '—' }}</td>
              <td class="t-left">{{ it.summary || '—' }}</td>
              <td class="t-center num page-feedback-insights__small">
                {{ fmtD(it.period_from) }} — {{ fmtD(it.period_to) }}
              </td>
              <td class="t-center num page-feedback-insights__muted page-feedback-insights__small">
                {{ fmtDT(it.created_at) }}
              </td>
              <td class="t-center num">
                <button class="btn btn--outline btn-sm"
                        title="Скопировать ссылку на инсайт" @click="copyLink(it)">
                  <i class="bi bi-link-45deg"></i>
                  <span v-if="copiedId === it.id" class="page-feedback-insights__copied">Скопировано</span>
                  <span v-else>Ссылка</span>
                </button>
                <a class="btn btn--outline btn-sm ms-1" :href="insightPath(it.id)"
                   target="_blank" rel="noopener" title="Открыть в новой вкладке">
                  <i class="bi bi-box-arrow-up-right"></i>
                </a>
              </td>
            </tr>

            <tr v-if="openInsight === it.id" class="page-feedback-insights__expand-row">
              <td :colspan="8">
                <!-- О чём говорят покупатели -->
                <div class="page-feedback-insights__panel">
                  <div class="page-feedback-insights__panel-head">
                    <span class="page-feedback-insights__panel-title">О чём говорят покупатели</span>
                    <span class="page-feedback-insights__panel-stat">{{ it.reviews_cnt }} отзыва</span>
                    <span class="page-feedback-insights__panel-stat panel-stat--pos">👍 {{ posPct(it) }}%</span>
                    <span class="page-feedback-insights__panel-stat panel-stat--neg">👎 {{ negPct(it) }}%</span>
                  </div>
                  <div class="page-feedback-insights__panel-cols">
                    <div>
                      <div class="page-feedback-insights__col-head">👍 Чаще всего упоминаемые плюсы</div>
                      <div v-if="!it.panel.plus.length" class="page-feedback-insights__muted page-feedback-insights__small">—</div>
                      <div v-for="g in it.panel.plus" :key="'p-' + g.title"
                           class="page-feedback-insights__group group--pos">
                        <div class="page-feedback-insights__group-title">
                          <span class="mk">+</span> {{ g.title }}
                        </div>
                        <ul>
                          <li v-for="(s, j) in g.items" :key="'pi' + j">{{ s }}</li>
                        </ul>
                      </div>
                    </div>
                    <div>
                      <div class="page-feedback-insights__col-head">👎 Чаще всего упоминаемые проблемы</div>
                      <div v-if="!it.panel.minus.length" class="page-feedback-insights__muted page-feedback-insights__small">—</div>
                      <div v-for="g in it.panel.minus" :key="'m-' + g.title"
                           class="page-feedback-insights__group group--neg">
                        <div class="page-feedback-insights__group-title">
                          <span class="mk">−</span> {{ g.title }}
                        </div>
                        <ul>
                          <li v-for="(s, j) in g.items" :key="'mi' + j">{{ s }}</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Что сделать с описанием -->
                <div class="page-feedback-insights__h3">Что сделать с описанием</div>
                <div v-if="!it.card_rec" class="page-feedback-insights__muted page-feedback-insights__small">Ничего конкретного нет.</div>
                <div v-else class="page-feedback-insights__act">
                  <span class="badge" :class="priorityClass(it.card_rec.priority)">
                    {{ priorityLabel(it.card_rec.priority) }}</span>
                  <div class="page-feedback-insights__act-issue">{{ it.card_rec.issue }}</div>
                  <div v-if="it.card_rec.fix" class="page-feedback-insights__act-fix">
                    <i class="bi bi-wrench"></i> {{ it.card_rec.fix }}
                  </div>
                  <div v-for="(ev, j) in it.card_rec.evidence" :key="'e' + j"
                       class="page-feedback-insights__quote">«{{ ev }}»</div>

                  <div v-if="(it.card_rec.desc_add || []).length" class="mt-2">
                    <div class="page-feedback-insights__fix-head">Дописать</div>
                    <ul class="page-feedback-insights__fix-list">
                      <li v-for="(x, j) in it.card_rec.desc_add" :key="'da' + j">{{ x }}</li>
                    </ul>
                  </div>
                  <div v-if="(it.card_rec.desc_change || []).length" class="mt-2">
                    <div class="page-feedback-insights__fix-head">Изменить</div>
                    <div v-for="(ch, j) in it.card_rec.desc_change" :key="'dc' + j"
                         class="page-feedback-insights__change">
                      <span class="page-feedback-insights__change-was">{{ ch.was }}</span>
                      <i class="bi bi-arrow-right"></i>
                      <span class="page-feedback-insights__change-now">{{ ch.now }}</span>
                    </div>
                  </div>
                  <div v-if="(it.card_rec.desc_remove || []).length" class="mt-2">
                    <div class="page-feedback-insights__fix-head">Убрать</div>
                    <ul class="page-feedback-insights__fix-list">
                      <li v-for="(x, j) in it.card_rec.desc_remove" :key="'dr' + j">{{ x }}</li>
                    </ul>
                  </div>
                  <div v-if="it.card_rec.highlight" class="page-feedback-insights__hl">
                    <b>Что подчеркнуть:</b> {{ it.card_rec.highlight }}
                  </div>
                  <div v-if="it.card_rec.desc_new" class="mt-2">
                    <div class="row g-2">
                      <div class="col-12 col-md-6">
                        <div class="page-feedback-insights__cap">Было — описание</div>
                        <pre class="page-feedback-insights__pre">{{ it.card_rec.desc_old }}</pre>
                      </div>
                      <div class="col-12 col-md-6">
                        <div class="page-feedback-insights__cap">
                          Стало — черновик (проверьте ключи и факты)</div>
                        <pre class="page-feedback-insights__pre">{{ it.card_rec.desc_new }}</pre>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Что улучшить в товаре -->
                <div class="page-feedback-insights__h3">Что улучшить в товаре</div>
                <div v-if="!it.product_rec" class="page-feedback-insights__muted page-feedback-insights__small">Ничего конкретного нет.</div>
                <div v-else class="page-feedback-insights__act">
                  <span class="badge" :class="priorityClass(it.product_rec.priority)">
                    {{ priorityLabel(it.product_rec.priority) }}</span>
                  <div class="page-feedback-insights__act-issue">{{ it.product_rec.issue }}</div>
                  <div v-if="it.product_rec.action" class="page-feedback-insights__act-fix">
                    <i class="bi bi-tools"></i> {{ it.product_rec.action }}
                  </div>
                  <div v-for="(ev, j) in it.product_rec.evidence" :key="'pe' + j"
                       class="page-feedback-insights__quote">«{{ ev }}»</div>
                </div>
              </td>
            </tr>
            </template>
            </template>
            <tr v-if="!insights.length">
              <td colspan="8" class="t-center page-feedback-insights__empty">Инсайтов пока нет</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="wb-pager">
        <button class="btn btn--outline btn-sm" :disabled="page <= 1" @click="page--; load()">‹ Назад</button>
        <span class="wb-pager__label">Стр. {{ page }} из {{ totalPages }}</span>
        <button class="btn btn--outline btn-sm" :disabled="page >= totalPages" @click="page++; load()">
          Вперёд ›</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-feedback-insights.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import ProductCell from '@/components/common/ProductCell.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import { FEEDBACK_TABS } from '@/components/common/workspaceTabs'
import { feedbackInsightsApi, type FeedbackInsight } from '@/api/feedbackInsights'
import { useDateFmt } from '@/composables/useDateFmt'
import { exportXlsx } from '@/utils/exportXlsx'
import { daysAgoStr, todayStr } from '@/utils/dates'

const route = useRoute()
const router = useRouter()
const { fmtDT } = useDateFmt()

const brands = ref<string[]>([])
const categories = ref<string[]>([])

const filters = ref({
  date_from: String(route.query.date_from || daysAgoStr(30)),
  date_to: String(route.query.date_to || todayStr()),
  product: String(route.query.product || route.query.q || ''),
  brand: String(route.query.brand || ''),
  category: String(route.query.category || ''),
})

const insights = ref<FeedbackInsight[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const error = ref('')
const openInsight = ref(0)
const copiedId = ref(0)
const jobId = ref<number | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

/**
 * Разборы, сгруппированные по запуску (job_id): запусков у пользователя
 * 2–3, а строк — по числу карточек в каждом запуске (десятки). Без
 * группировки таблица выглядит «огромной» и непонятно, что в ней.
 */
const grouped = computed(() => {
  const map = new Map<string, { key: string; job: number | null; at: string; items: FeedbackInsight[] }>()
  for (const it of insights.value) {
    const key = it.job_id != null ? String(it.job_id) : 'none'
    let g = map.get(key)
    if (!g) {
      g = { key, job: it.job_id ?? null, at: '', items: [] }
      map.set(key, g)
    }
    if (!g.at) g.at = fmtDT(it.created_at) || ''
    g.items.push(it)
  }
  return Array.from(map.values())
})

function fmtD(v: string | null): string {
  return v ? String(v).slice(0, 10) : '—'
}

function buildParams() {
  const p: Record<string, any> = {
    date_from: filters.value.date_from || undefined,
    date_to: filters.value.date_to || undefined,
    q: filters.value.product || undefined,
    brand: filters.value.brand || undefined,
    category: filters.value.category || undefined,
    job_id: jobId.value || undefined,
    page: page.value,
    page_size: pageSize,
  }
  return p
}

async function load() {
  error.value = ''
  try {
    const data = await feedbackInsightsApi.insights(buildParams())
    insights.value = data.items || []
    total.value = data.total || 0
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    insights.value = []
    total.value = 0
  }
  syncRoute()
}

function syncRoute() {
  const q: Record<string, string> = {}
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  if (filters.value.product) q.product = filters.value.product
  if (filters.value.brand) q.brand = filters.value.brand
  if (filters.value.category) q.category = filters.value.category
  if (jobId.value) q.job = String(jobId.value)
  // параметр deep-link'а сохраняем: без него router.replace стирает его,
  // и applyDeepLink() успевает прочитать уже пустое значение — ссылка
  // на инсайт открывала страницу, но нужный разбор не раскрывался.
  const ins = Number(route.query.insight || 0)
  if (ins > 0) q.insight = String(ins)
  router.replace({ path: route.path, query: q }).catch(() => {})
}

function onReset() {
  filters.value = {
    date_from: filters.value.date_from,
    date_to: filters.value.date_to,
    product: '',
    brand: '',
    category: '',
  }
  page.value = 1
  load()
}

function showAllJobs() {
  jobId.value = null
  page.value = 1
  load()
}

// --- ссылка на инсайт ---
/** Путь строит роутер — он знает базу приложения (location.origin + route.path
 *  её не знает: на сервере приложение живёт не в корне домена). */
function insightPath(id: number): string {
  return router.resolve({ path: route.path, query: { insight: id } }).href
}
/** Абсолютный URL — для буфера обмена. */
function insightUrl(id: number): string {
  return location.origin + insightPath(id)
}

/**
 * Копирование в буфер. Clipboard API есть только в secure context
 * (https/localhost) — на http приложение живёт без него, и `navigator.clipboard`
 * там undefined. Поэтому запасной путь — execCommand через скрытое поле.
 */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (window.isSecureContext && navigator.clipboard) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch { /* пробуем запасной способ */ }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.top = '-1000px'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    ta.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

async function copyLink(it: FeedbackInsight) {
  const url = insightUrl(it.id)
  const ok = await copyToClipboard(url)
  if (ok) {
    copiedId.value = it.id
    setTimeout(() => { if (copiedId.value === it.id) copiedId.value = 0 }, 2000)
  } else {
    // буфер недоступен — показываем саму ссылку, чтобы скопировать руками
    error.value = 'Буфер обмена недоступен — скопируйте ссылку вручную: ' + url
  }
}

async function applyDeepLink() {
  const id = Number(route.query.insight || 0)
  if (!id) return
  openInsight.value = id
  if (insights.value.some((i) => i.id === id)) return
  try {
    const one = await feedbackInsightsApi.insight(id)
    if (one && !insights.value.some((i) => i.id === one.id)) {
      insights.value = [one, ...insights.value]
    }
  } catch {
    error.value = 'инсайт по ссылке не найден или нет доступа'
  }
}

function priorityClass(p: number): string {
  if (p === 1) return 'badge--bad'
  if (p === 2) return 'badge--warn'
  return 'badge--neutral'
}
function priorityLabel(p: number): string {
  if (p === 1) return 'критично'
  if (p === 2) return 'важно'
  return 'мелочь'
}
function posPct(it: FeedbackInsight): number {
  const n = it.reviews_cnt || 0
  if (!n) return 0
  return Math.round((Math.max(0, n - (it.neg_cnt || 0)) * 100) / n)
}
function negPct(it: FeedbackInsight): number {
  const n = it.reviews_cnt || 0
  if (!n) return 0
  return Math.round(((it.neg_cnt || 0) * 100) / n)
}

async function exportExcel() {
  if (!insights.value.length) return
  const rowsOut = insights.value.map((it) => ({
    'Карточка': it.card_title || '',
    'nmID': it.nm_id,
    'Бренд': it.brand || '',
    'Категория': it.subject_name || '',
    'Артикул': it.vendor_code || '',
    'Период отзывов': `${it.period_from || ''} — ${it.period_to || ''}`,
    'Отзывов': it.reviews_cnt,
    'Ср. оценка': it.avg_rating ?? '',
    'Что делать': it.summary || '',
    'Проблемы (темы)': (it.panel.minus || []).map((g) => `${g.title}: ${g.items.join('; ')}`).join(' | '),
    'Плюсы (темы)': (it.panel.plus || []).map((g) => `${g.title}: ${g.items.join('; ')}`).join(' | '),
    'Описание: проблема': it.card_rec ? it.card_rec.issue : '',
    'Описание: что сделать': it.card_rec ? (it.card_rec.fix || '') : '',
    'Описание: подчеркнуть': it.card_rec ? (it.card_rec.highlight || '') : '',
    'Описание: дописать': it.card_rec ? (it.card_rec.desc_add || []).join(' | ') : '',
    'Описание: изменить': it.card_rec
      ? (it.card_rec.desc_change || []).map((c) => `${c.was} → ${c.now}`).join(' | ') : '',
    'Описание: убрать': it.card_rec ? (it.card_rec.desc_remove || []).join(' | ') : '',
    'Товар: проблема': it.product_rec ? it.product_rec.issue : '',
    'Товар: что сделать': it.product_rec ? (it.product_rec.action || '') : '',
    'Разобрано': it.created_at || '',
  }))
  await exportXlsx({
    rows: rowsOut,
    filename: 'insighty_otzyvov.xlsx',
    sheetName: 'Инсайты',
    cols: [
      { wch: 38 }, { wch: 12 }, { wch: 16 }, { wch: 22 }, { wch: 16 }, { wch: 24 },
      { wch: 9 }, { wch: 11 }, { wch: 44 },
      { wch: 50 }, { wch: 50 },
      { wch: 42 }, { wch: 46 }, { wch: 40 }, { wch: 46 }, { wch: 46 }, { wch: 40 }, { wch: 50 },
      { wch: 42 }, { wch: 46 },
      { wch: 19 },
    ],
  })
}

watch(() => route.query.insight, () => {
  if (insights.value.length) applyDeepLink()
})

onMounted(async () => {
  const j = Number(route.query.job || 0)
  jobId.value = j > 0 ? j : null
  try {
    const f = await feedbackInsightsApi.filters()
    brands.value = f.brands || []
    categories.value = f.categories || []
  } catch { /* списки пустые — фильтр работает без них */ }
  await load()
  await applyDeepLink()
})
</script>
