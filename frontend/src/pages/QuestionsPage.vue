<template>
  <div class="container-xxl page-questions">
    <h1 class="page-title">Вопросы</h1>

    <!-- Фильтр: общий WbUniversalFilter — даты + товар. Статус и поиск — поля страницы
         (слот #fields), кнопка синка — слот #extra (в строке кнопок). -->
    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:product="filters.product"
      :show-brand-category="false"
      @apply="onApply"
      @reset="onReset"
    >
      <template #fields>
        <div class="wb-field">
          <label class="wb-field__label">Статус</label>
          <select v-model="filters.status" class="form-control">
            <option value="">Все</option>
            <option value="unanswered">Без ответа</option>
            <option value="answered">С ответом</option>
            <option value="rejected">Отклонённые</option>
            <option value="warned">Подозрительные</option>
          </select>
        </div>
        <div class="wb-field">
          <label class="wb-field__label">Поиск</label>
          <input
            v-model="filters.q"
            class="form-control"
            placeholder="текст вопроса или ответа"
            @keydown.enter="onApply"
          />
        </div>
      </template>
      <template #extra>
        <button
          v-if="canSync"
          class="btn btn--outline"
          :disabled="syncRunning"
          title="Забрать вопросы из WB API за выбранный период"
          @click="onSync"
        >
          <i class="bi bi-arrow-repeat"></i>
          {{ syncRunning ? 'Синхронизация…' : 'Синхронизировать' }}
        </button>
      </template>
    </WbUniversalFilter>

    <div v-if="syncMsg" class="alert alert-info py-1 px-2 small mb-3">{{ syncMsg }}</div>

    <!-- KPI: счётчики за выбранный период -->
    <div class="grid-4 page-questions__kpi">
      <KpiTile label="Всего вопросов" :value="stats.total" variant="tile--1" :foot="periodLabel" />
      <KpiTile label="Без ответа" :value="stats.unanswered" variant="tile--10" foot="ждут ответа" />
      <KpiTile label="С ответом" :value="stats.answered" variant="tile--8" foot="ответили продавцу" />
      <KpiTile label="Отклонённые" :value="stats.rejected" variant="tile--12" foot="скрыты покупателям" />
    </div>

    <!-- Таблица: стандарт темы (.tbl-card → .card__hd → .tbl-wrap → .tbl) -->
    <div class="tbl-card page-questions__card">
      <div class="card__hd">
        <span>Вопросы</span>
        <span v-if="stats.warned" class="hd-badge" title="WB помечает вопрос как подозрительный">подозрительных: {{ stats.warned }}</span>
        <span class="spacer"></span>
        <span class="page-questions__count">Всего: {{ total }} · Стр {{ page }} / {{ totalPages }}</span>
        <ExcelButton :disabled="!items.length" @click="exportExcel" />
      </div>
      <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
      <div v-else-if="error" class="p-4 text-center text-danger">Не удалось загрузить данные.</div>
      <div v-else class="tbl-wrap">
        <table class="tbl page-questions__table">
          <thead>
            <tr>
              <th class="t-left">Дата</th>
              <th class="t-left">Товар</th>
              <th class="t-left">Вопрос</th>
              <th class="t-left">Ответ</th>
              <th class="t-left">Статус</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!items.length">
              <td colspan="5" class="text-center text-muted">Нет данных</td>
            </tr>
            <tr
              v-for="q in items"
              :key="q.id"
              class="page-questions__row"
              @click="openQuestion(q)"
            >
              <td class="t-left num">{{ fmtDate(q.created_date) }}</td>
              <td class="t-left">
                <ProductCell
                  :photo="q.card_photos"
                  :title="q.card_title || q.product_name || ''"
                  :sub="subLine(q)"
                  :vendor="q.supplier_article || q.card_vendor || ''"
                  :link="q.nm_id ? '/wb/detail?nm_id=' + q.nm_id : ''"
                  :link-label="q.nm_id ? 'WB: ' + q.nm_id : ''"
                />
              </td>
              <td class="t-left"><div class="page-questions__text">{{ q.q_text || '—' }}</div></td>
              <td class="t-left"><div class="page-questions__text">{{ q.answer_text || '—' }}</div></td>
              <td class="t-left">
                <span class="badge" :class="stateClass(q)">{{ q.state_label }}</span>
                <span
                  v-if="q.is_warned"
                  class="badge badge--bad ms-1"
                  title="WB помечает вопрос как подозрительный"
                >
                  <i class="bi bi-exclamation-triangle"></i>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Pager :page="page" :total-pages="totalPages" :total="total" @change="onPage" />

    <!-- Полный текст вопроса и ответа -->
    <div v-if="modalOpen && current" class="wb-modal-backdrop" @click.self="modalOpen = false">
      <div class="wb-modal-box wb-modal-box--wide page-questions__modal">
        <div class="d-flex align-items-center gap-2">
          <h5 class="mb-0">Вопрос покупателя</h5>
          <span class="badge" :class="stateClass(current)">{{ current.state_label }}</span>
          <span v-if="current.is_warned" class="badge badge--bad" title="WB помечает вопрос как подозрительный">
            <i class="bi bi-exclamation-triangle"></i> подозрительный
          </span>
          <button type="button" class="btn-close ms-auto" aria-label="Закрыть" @click="modalOpen = false"></button>
        </div>
        <div class="page-questions__modal-meta small text-muted">
          {{ fmtDate(current.created_date) }}
          <template v-if="current.nm_id">
            · WB:
            <router-link :to="`/wb/detail?nm_id=${current.nm_id}`" target="_blank" class="adv-link">{{ current.nm_id }}</router-link>
          </template>
          <template v-if="current.supplier_article"> · арт. продавца: {{ current.supplier_article }}</template>
          <template v-if="current.brand_name"> · {{ current.brand_name }}</template>
        </div>
        <div><b>Вопрос:</b> {{ current.q_text || '—' }}</div>
        <div v-if="current.answer_text"><b>Ответ:</b> {{ current.answer_text }}</div>
        <div v-else class="text-muted">Ответа нет</div>
        <div v-if="current.answer_date" class="small text-muted">Ответ: {{ fmtDate(current.answer_date) }}</div>
        <div class="wb-modal-actions">
          <button class="btn btn--outline" @click="modalOpen = false">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-questions.css'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { questionsApi, type QuestionItem, type QuestionsStats } from '@/api/questions'
import { useAuthStore } from '../stores/auth'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import ProductCell from '@/components/common/ProductCell.vue'
import ExcelButton from '@/components/common/ExcelButton.vue'
import Pager from '@/components/common/Pager.vue'
import KpiTile from '@/components/common/KpiTile.vue'

// локальное время (toISOString даёт UTC и сдвигает сутки)
const toIsoDate = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
const defaultDates = () => {
  const today = new Date()
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 29)
  return { date_from: toIsoDate(from), date_to: toIsoDate(today) }
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const PAGE_SIZE = 30

const defaults = defaultDates()
const filters = ref({
  date_from: defaults.date_from,
  date_to: defaults.date_to,
  product: '',
  nm_id: '',
  status: '',
  q: '',
  page: 1,
})
const items = ref<QuestionItem[]>([])
const total = ref(0)
const page = ref(1)
const stats = ref<QuestionsStats>({ total: 0, unanswered: 0, answered: 0, rejected: 0, warned: 0, last_sync: null })
const isLoading = ref(false)
const error = ref('')
/** Флаг «меняем URL сами» — чтобы watcher не перезапрашивал данные второй раз. */
const routeSync = ref(false)
const syncing = ref(false)
const syncMsg = ref('')
const modalOpen = ref(false)
const current = ref<QuestionItem | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const periodLabel = computed(() => {
  const from = filters.value.date_from || '—'
  const to = filters.value.date_to || '—'
  return from === to ? from : `${from} — ${to}`
})
const syncRunning = computed(() => syncing.value)
/** Кнопку синк видит только тот, кому разрешено запускать (v3: manageFeedback). */
const canSync = computed(() => auth.canDomain('manageFeedback'))

/** WbUniversalFilter даёт свободную маску (nm_id/артикул/название) — резолвим в nm_id. */
const resolveNmId = async (mask: string): Promise<string> => {
  const q = String(mask || '').trim()
  if (!q) return ''
  try {
    const { data } = await api.get('/api/wb/cards', { params: { q, limit: 20 } })
    const list: any[] = Array.isArray(data) ? data : (data?.items ?? [])
    const exact = list.find((c: any) => String(c.nmID) === q || String(c.vendorCode || '') === q)
    if (exact) return String(exact.nmID)
    return list.length === 1 ? String(list[0].nmID) : ''
  } catch {
    return ''
  }
}

const initFromQuery = () => {
  const q: Record<string, any> = route.query || {}
  const pick = (...keys: string[]) => {
    for (const key of keys) if (q[key]) return String(q[key])
    return ''
  }
  const df = pick('date_from', 'DPFilterForm[date_from]')
  const dt = pick('date_to', 'DPFilterForm[date_to]')
  const nm = pick('nm_id', 'DPFilterForm[nm_id]')
  const product = pick('product')
  const status = pick('status')
  const search = pick('q')
  const queryPage = pick('page')
  if (df) filters.value.date_from = df
  if (dt) filters.value.date_to = dt
  if (nm) { filters.value.nm_id = nm; filters.value.product = product || nm }
  else if (product) filters.value.product = product
  if (status) filters.value.status = status
  if (search) filters.value.q = search
  if (queryPage) filters.value.page = Math.max(1, Number(queryPage) || 1)
}

const syncRoute = async () => {
  const q: Record<string, string> = {}
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  if (filters.value.nm_id) q.nm_id = filters.value.nm_id
  if (filters.value.status) q.status = filters.value.status
  if (filters.value.q) q.q = filters.value.q
  if (filters.value.page > 1) q.page = String(filters.value.page)
  if (!Object.keys(q).length) return
  routeSync.value = true
  try {
    await router.replace({ path: route.path, query: q })
  } finally {
    routeSync.value = false
  }
}

const fetchData = async () => {
  isLoading.value = true
  error.value = ''
  try {
    const payload = await questionsApi.list({
      date_from: filters.value.date_from,
      date_to: filters.value.date_to,
      nm_id: filters.value.nm_id || undefined,
      status: filters.value.status || undefined,
      q: filters.value.q || undefined,
      page: filters.value.page,
      page_size: PAGE_SIZE,
    })
    items.value = Array.isArray(payload.items) ? payload.items : []
    total.value = Number(payload.total) || 0
    page.value = Number(payload.page) || filters.value.page
    if (payload.stats) stats.value = payload.stats
  } catch {
    error.value = 'Не удалось загрузить данные.'
  } finally {
    isLoading.value = false
  }
}

const exportExcel = async () => {
  if (!items.value.length) return
  const XLSX = await import('xlsx')
  const data = items.value.map((q: QuestionItem) => ({
    'Дата': fmtDate(q.created_date),
    'Товар': q.card_title || q.product_name || '',
    'Артикул WB': q.nm_id || '',
    'Артикул продавца': q.supplier_article || q.card_vendor || '',
    'Вопрос': q.q_text || '',
    'Ответ': q.answer_text || '',
    'Статус': q.state_label || '',
    'Дата ответа': q.answer_date ? fmtDate(q.answer_date) : '',
    'Подозрительный': q.is_warned ? 'да' : 'нет',
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [
    { wch: 16 }, { wch: 32 }, { wch: 12 }, { wch: 16 },
    { wch: 60 }, { wch: 60 }, { wch: 14 }, { wch: 16 }, { wch: 14 },
  ]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Вопросы')
  XLSX.writeFile(wb, 'wb-questions.xlsx')
}

/** Применение фильтра: маска товара → nm_id, значения полей → запрос. */
const onApply = async () => {
  filters.value.nm_id = await resolveNmId(filters.value.product)
  filters.value.page = 1
  await syncRoute()
  await fetchData()
}

/** Сброс фильтра: дефолтные значения (даты — 30 суток). */
const onReset = async () => {
  const d = defaultDates()
  filters.value.product = ''
  filters.value.nm_id = ''
  filters.value.status = ''
  filters.value.q = ''
  filters.value.date_from = d.date_from
  filters.value.date_to = d.date_to
  filters.value.page = 1
  await syncRoute()
  await fetchData()
}

/** Смена страницы пагинации. */
const onPage = async (p: number) => {
  filters.value.page = p
  await syncRoute()
  await fetchData()
}

/** Полный текст вопроса — модалка. */
const openQuestion = (q: QuestionItem) => {
  current.value = q
  modalOpen.value = true
}

/** Синк с WB API за выбранный период (фоном, статус — опросом). */
let pollTimer: ReturnType<typeof setTimeout> | null = null
const onSync = async () => {
  if (syncing.value) return
  syncing.value = true
  syncMsg.value = 'Запущен синк вопросов из WB API...'
  try {
    await questionsApi.sync({
      mode: 'fresh',
      date_from: filters.value.date_from,
      date_to: filters.value.date_to,
      nm_id: filters.value.nm_id ? Number(filters.value.nm_id) : undefined,
    })
    pollStatus()
  } catch (e: any) {
    syncing.value = false
    syncMsg.value = 'Не удалось запустить синк: ' + (e?.response?.data?.detail || e?.message || 'ошибка')
  }
}

const pollStatus = async () => {
  try {
    const st = await questionsApi.syncStatus()
    if (st.running) {
      pollTimer = setTimeout(pollStatus, 2000)
      return
    }
    syncing.value = false
    const res = st.result || {}
    if (res.error) syncMsg.value = 'Синк завершился с ошибкой: ' + res.error
    else if (res.skipped) syncMsg.value = 'Синк пропущен: ' + res.skipped
    else syncMsg.value = 'Синк завершён.'
    await fetchData()
  } catch {
    syncing.value = false
    syncMsg.value = 'Не удалось получить статус синка.'
  }
}

/** Подпись под названием товара: бренд и предмет одной строкой. */
const subLine = (q: QuestionItem) => {
  const subject = String(q.card_subject || '')
  const brand = String(q.card_brand || q.brand_name || '')
  if (subject && brand) return subject + ' • ' + brand
  return subject || brand
}

/** Статус вопроса → класс бейджа темы (только про ответ/отклонение).
    Подозрительность (is_warned) — отдельный бейдж, чтобы «Есть ответ»
    не был красным у части строк. */
const stateClass = (q: QuestionItem) => {
  if (q.state === 'none') return 'badge--neutral'
  if (q.has_answer) return 'badge--ok'
  return 'badge--warn'
}

/** Дата из БД ('YYYY-MM-DD HH:MM:SS') → 'ДД.ММ.ГГГГ ЧЧ:ММ'. */
const fmtDate = (value: string | null | undefined) => {
  const s = String(value || '')
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T]?(\d{2}):(\d{2})/.exec(s)
  if (!m) return s || '—'
  return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}`
}

onMounted(async () => {
  initFromQuery()
  await fetchData()
})

watch(() => route.query, async () => {
  if (routeSync.value) return
  initFromQuery()
  await fetchData()
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>
