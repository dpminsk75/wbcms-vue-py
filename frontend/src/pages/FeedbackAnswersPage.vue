<template>
  <div class="container-xxl page-feedback-answers">
    <WbWorkspaceHead :title="$route.meta.title || 'Отзывы и ответы'" :workspace-tabs="FEEDBACK_TABS" workspace-active="answers" />

    <!-- Фильтр — общий WbUniversalFilter (theme.md §5.6): поля страницы в слоте #fields -->
    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:product="filters.nm_id"
      :show-brand-category="false"
      @apply="onApply"
      @reset="onReset"
    >
      <template #fields>
        <!-- блок 1: «какой отзыв» — оценка и статус ответа рядом, один логический блок -->
        <div class="wb-field-group">
          <div class="wb-field">
            <label class="wb-field__label">Оценка</label>
            <select v-model="filters.rating" class="wb-select">
              <option value="">Все оценки</option>
              <option value="5">5 ★</option>
              <option value="4">4 ★</option>
              <option value="3">3 ★</option>
              <option value="2">2 ★</option>
              <option value="1">1 ★</option>
            </select>
          </div>
          <div class="wb-field">
            <label class="wb-field__label">Статус ответа</label>
            <select v-model="filters.status" class="wb-select">
              <option value="">Все</option>
              <option value="answered">Есть ответ</option>
              <option value="not_answered">Нет ответа</option>
            </select>
          </div>
        </div>

        <!-- блок 2: «какие отзывы показывать» — фильтры-чипы, применяются сразу -->
        <div class="wb-field-group wb-field-group--sep">
          <div class="wb-field">
            <span class="wb-chip-group__label">Только</span>
            <WbChipGroup v-model="onlyFlags" :options="onlyOptions" multiple
                         @update:model-value="onApply" />
          </div>
        </div>

        <!-- блок 3: переключатель отображения — прячет колонку «Ответ»
             (выборку не меняет, поэтому без apply). Подпись — как у блока 2,
             чтобы чипы стояли на одной линии. -->
        <div class="wb-field-group wb-field-group--sep wb-field-group--one">
          <div class="wb-field">
            <span class="wb-chip-group__label">Ответ</span>
            <WbChipGroup v-model="hideAnswers" :options="hideAnswerOptions" toggle
                         @update:model-value="syncRoute" />
          </div>
        </div>
      </template>
    </WbUniversalFilter>

    <div v-if="reviewMsg" class="page-feedback-answers__msg">{{ reviewMsg }}</div>

    <!-- Таблица — блок темы .tbl-card (theme.md §5.7.9) -->
    <div class="tbl-card page-feedback-answers__card">
      <div class="card__hd">
        <span>Отзывы и ответы</span>
        <span class="hd-badge">Всего: {{ total }}</span>
        <span class="spacer"></span>
        <button type="button" class="hd-btn" @click="openPrompt">Промпт разбора</button>
        <button type="button" class="hd-btn" @click="openErrors">Ошибки разбора</button>
      </div>

      <div v-if="isLoading" class="page-feedback-answers__loading">
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span>Загрузка данных…</span>
      </div>
      <div v-else class="tbl-wrap">
        <table class="tbl page-feedback-answers__table">
          <thead>
            <tr>
              <th class="t-left">Товар</th>
              <th class="t-left">
                Отзыв
                <a href="#" class="page-feedback-answers__sort" title="Сортировка по дате" @click.prevent="onSort('createdDate')">
                  Дата <i class="bi" :class="sortIcon('createdDate')"></i>
                </a>
              </th>
              <th v-if="!filters.hide_answers" class="t-left">Ответ</th>
              <th class="t-center">
                Правило
                <a href="#" class="page-feedback-answers__sort" title="Сортировка по оценке" @click.prevent="onSort('productValuation')">
                  ★ <i class="bi" :class="sortIcon('productValuation')"></i>
                </a>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fb in rows" :key="fb.id">
              <td class="t-left">
                <ProductCell
                  :photo="fb.product_photos"
                  :title="fb.product_title || ''"
                  :brand="fb.product_brand || ''"
                  :subject="fb.product_subject || ''"
                  :vendor="fb.product_vendor_code || ''"
                  :nm-id="fb.nmID"
                  :link="'/wb/detail?nm_id=' + fb.nmID"
                  :link-label="'WB: ' + fb.nmID"
                  copy-nm
                  copy-link
                />
                <div v-if="Number(fb.f_cost) > 0" class="mt-1">
                  <span class="badge badge--warn">Оплачен: {{ fb.f_cost }} ₽</span>
                </div>
              </td>
              <td class="t-left">
                <div class="page-feedback-answers__row-head">
                  <span class="page-feedback-answers__date">{{ fmtDate(fb.createdDate) }}</span>
                  <span class="badge" :class="ratingBadge(Number(fb.productValuation))">{{ fb.productValuation }} ★</span>
                </div>
                <div v-if="fb.text" class="mb-1"><b>Отзыв:</b> {{ fb.text }}</div>
                <div v-if="fb.pros" class="mb-1"><b>Плюсы:</b> {{ fb.pros }}</div>
                <div v-if="fb.cons" class="mb-1"><b>Минусы:</b> {{ fb.cons }}</div>
                <div v-if="mediaOf(fb).video || mediaOf(fb).photos.length" class="mt-3 page-feedback-answers__media">
                  <div v-if="mediaOf(fb).video" class="page-feedback-answers__media-item">
                    <video :src="mediaOf(fb).video.link" controls :poster="mediaOf(fb).video.poster" class="page-feedback-answers__video" :style="{ height: (bigVideo[fb.id] ? 360 : 120) + 'px' }"></video>
                    <div class="mt-1 page-feedback-answers__media-acts">
                      <a href="#" class="page-feedback-answers__media-btn" @click.prevent="bigVideo[fb.id] = !bigVideo[fb.id]">{{ bigVideo[fb.id] ? 'Уменьшить' : 'Развернуть' }}</a>
                      <a :href="mediaOf(fb).video.link" target="_blank" rel="noopener" class="page-feedback-answers__media-btn">Открыть видео</a>
                    </div>
                  </div>
                  <a v-for="(p, i) in mediaOf(fb).photos" :key="i" :href="p.full" target="_blank" rel="noopener">
                    <img :src="p.mini" loading="lazy" class="page-feedback-answers__photo" />
                  </a>
                </div>
                <div v-if="fb.bables?.length" class="page-feedback-answers__tags">
                  <span v-for="t in fb.bables" :key="t" class="badge" :class="tagClass(t)">{{ t }}</span>
                </div>
                <!-- разбор отзыва через ИИ: эмоциональность / конструктивность / тональность -->
                <div class="mt-2 page-feedback-answers__ai">
                  <template v-if="fb.ai_emotion || fb.ai_status === 'error'">
                    <span class="badge page-feedback-answers__ai-badge"
                          :class="aiClass('ai_emotion', fb)">
                      Эмоциональность: {{ aiLabel('ai_emotion', fb) }}
                    </span>
                    <span class="badge page-feedback-answers__ai-badge"
                          :class="aiClass('ai_constructiveness', fb)">
                      Конструктивность: {{ aiLabel('ai_constructiveness', fb) }}
                    </span>
                    <span class="badge page-feedback-answers__ai-badge"
                          :class="aiClass('ai_tone', fb)">
                      Тональность: {{ aiLabel('ai_tone', fb) }}
                    </span>
                  </template>
                  <span v-else-if="fb.text" class="page-feedback-answers__muted">Отзыв не разобран</span>
                  <button v-if="fb.text" type="button"
                          class="btn btn--outline btn-sm page-feedback-answers__ai-btn"
                          :disabled="reviewingId === fb.id"
                          @click="onReview(fb)">
                    <span v-if="reviewingId === fb.id" class="spinner-border spinner-border-sm me-1"></span>
                    {{ reviewingId === fb.id ? 'Разбираем...' : 'Разобрать' }}
                  </button>
                  <button v-if="fb.ai_status === 'error'" type="button"
                          class="btn btn--outline btn-sm page-feedback-answers__ai-btn"
                          title="Вернуть отзыв в очередь разбора"
                          @click="onRetry(fb)">
                    Вернуть в очередь
                  </button>
                  <span v-if="fb.ai_status === 'error'" class="page-feedback-answers__error"
                        :title="fb.ai_error || ''">ошибка разбора</span>
                </div>
              </td>
              <td v-if="!filters.hide_answers" class="t-left">
                <div v-if="fb.answer_text">
                  <div class="page-feedback-answers__date mb-1">{{ fmtDate(fb.updatedDate) }}</div>
                  <div class="page-feedback-answers__answer">{{ fb.answer_text }}</div>
                </div>
                <span v-else class="page-feedback-answers__muted">—</span>
              </td>
              <td class="t-center">
                <span v-if="fb.rule_id" class="page-feedback-answers__rule" :title="ruleTitle(fb)">{{ fb.rule_id }}</span>
                <span v-else class="page-feedback-answers__muted">—</span>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td :colspan="filters.hide_answers ? 3 : 4" class="t-center page-feedback-answers__empty">Отзывов не найдено</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="wb-pager">
        <button class="btn btn--outline btn-sm" :disabled="page <= 1" @click="goPage(page - 1)">‹ Назад</button>
        <span class="wb-pager__label">
          Стр. {{ page }} из {{ totalPages }}<span v-if="total"> · показано {{ rows.length }} из {{ total }}</span>
        </span>
        <button class="btn btn--outline btn-sm" :disabled="page >= totalPages" @click="goPage(page + 1)">Вперёд ›</button>
      </div>
    </div>

    <!-- Ошибки разбора отзывов — вернуть в очередь -->
    <div v-if="errorsOpen" class="modal d-block page-feedback-answers__errors-modal" tabindex="-1"
         @click.self="errorsOpen = false">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header py-2">
            <span class="modal-title page-feedback-answers__modal-title">Ошибки разбора отзывов ({{ reviewErrors.length }})</span>
            <button type="button" class="btn-close" @click="errorsOpen = false"></button>
          </div>
          <div class="modal-body">
            <div v-if="!reviewErrors.length" class="page-feedback-answers__muted">Ошибок нет.</div>
            <table v-else class="tbl">
              <thead>
                <tr><th class="t-left">Дата</th><th class="t-left">Товар</th><th class="t-left">Отзыв</th><th class="t-left">Ошибка</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="e in reviewErrors" :key="e.feedback_id">
                  <td class="t-left num page-feedback-answers__small">{{ e.created_at }}</td>
                  <td class="t-left page-feedback-answers__small">{{ e.product_title || e.nm_id }}</td>
                  <td class="t-left page-feedback-answers__small">{{ (e.text || '').slice(0, 140) }}</td>
                  <td class="t-left page-feedback-answers__small page-feedback-answers__error" :title="e.error || ''">
                    {{ (e.error || '').slice(0, 80) }}
                  </td>
                  <td class="t-right">
                    <button class="btn btn--outline btn-sm" @click="onRetryError(e)">
                      В очередь
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    <!-- Промпт разбора отзыва (настройка компании) -->
    <div v-if="promptOpen" class="modal d-block page-feedback-answers__errors-modal" tabindex="-1"
         @click.self="promptOpen = false">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header py-2">
            <span class="modal-title page-feedback-answers__modal-title">Промпт разбора отзыва</span>
            <button type="button" class="btn-close" @click="promptOpen = false"></button>
          </div>
          <div class="modal-body">
            <p class="page-feedback-answers__muted page-feedback-answers__small">
              Промпт применяется к каждому отзыву отдельно. Модель — «Модель (сводка)».
              Формат ответа: JSON с полями emotion, constructiveness, tone.
            </p>
            <div class="page-feedback-answers__prompt-opts">
              <div class="form-check">
                <input id="fa-autoreview" v-model="autoReview" type="checkbox" class="form-check-input" />
                <label for="fa-autoreview" class="form-check-label">
                  Авторазбор в фоне (таймер, каждый час)
                </label>
              </div>
              <div class="wb-field page-feedback-answers__prompt-batch">
                <label class="wb-field__label">Отзывов за прогон</label>
                <input v-model.number="reviewBatch" type="number" min="1" max="500" class="wb-input" />
              </div>
            </div>
            <textarea v-model="promptText" class="wb-input page-feedback-answers__prompt-text" rows="18"></textarea>
          </div>
          <div class="modal-footer py-2">
            <span v-if="promptMsg" class="me-auto page-feedback-answers__small"
                  :class="promptMsgOk ? 'page-feedback-answers__ok' : 'page-feedback-answers__error'">
              {{ promptMsg }}
            </span>
            <button class="btn btn--outline" @click="promptOpen = false">Закрыть</button>
            <button class="btn btn--brand" :disabled="promptSaving" @click="onSavePrompt">
              {{ promptSaving ? 'Сохраняем...' : 'Сохранить' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-feedback-answers.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { feedbackApi, type FeedbackAnswer, type FeedbackReviewError } from '@/api/feedback'
import { api } from '@/api/client'
import ProductCell from '@/components/common/ProductCell.vue'
import WbChipGroup from '@/components/common/WbChipGroup.vue'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { FEEDBACK_TABS } from '@/components/common/workspaceTabs'

const route = useRoute()
const router = useRouter()

const twoDaysAgo = () => {
  const d = new Date()
  d.setDate(d.getDate() - 2)
  return d.toISOString().slice(0, 10)
}
const today = () => new Date().toISOString().slice(0, 10)

const filters = ref({
  date_from: String(route.query.date_from || twoDaysAgo()),
  date_to: String(route.query.date_to || today()),
  nm_id: String(route.query.nm_id || ''),
  rating: String(route.query.rating || ''),
  status: String(route.query.status || ''),
  has_media: route.query.has_media === '1',
  paid_only: route.query.paid_only === '1',
  with_text: route.query.with_text === '1',
  hide_answers: route.query.hide_answers === '1',
})

/** Фильтры-чипы «Только …» — применяются сразу (как чипы типов в новостях).
 *  «Фото/видео», «Платные», «Текст» — независимые флаги (можно включить все). */
const onlyOptions = [
  { value: 'media', label: 'Фото/видео' },
  { value: 'paid', label: 'Платные' },
  { value: 'text', label: 'Текст' },
]
const onlyFlags = computed<string[]>({
  get: () => [
    ...(filters.value.has_media ? ['media'] : []),
    ...(filters.value.paid_only ? ['paid'] : []),
    ...(filters.value.with_text ? ['text'] : []),
  ],
  set: (v: string[]) => {
    filters.value.has_media = v.includes('media')
    filters.value.paid_only = v.includes('paid')
    filters.value.with_text = v.includes('text')
  },
})

/** «Без ответов» — не фильтр, а переключатель отображения: колонка «Ответ»
 *  просто пропадает. Отдельный блок, поэтому свой чип (single) и без apply. */
const hideAnswerOptions = [{ value: 'on', label: 'Без ответов' }]
const hideAnswers = computed({
  get: () => (filters.value.hide_answers ? 'on' : ''),
  set: (v: string) => {
    filters.value.hide_answers = v === 'on'
  },
})

const rows = ref<FeedbackAnswer[]>([])
const bigVideo = ref<Record<string, boolean>>({})
const total = ref(0)
const page = ref(Number(route.query.page || 1))
const sort = ref(String(route.query.sort || 'createdDate'))
const order = ref(String(route.query.order || 'desc'))
const pageSize = 30
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const isLoading = ref(false)
const tagsSentiment = ref<Record<string, string>>({})
const rulesById = ref<Record<string, string>>({})

// --- разбор отзыва через ИИ ----------------------------------------------------
const reviewingId = ref('')
const reviewErrors = ref<FeedbackReviewError[]>([])
const errorsOpen = ref(false)
const reviewMsg = ref('')

const AI_LABELS: Record<string, Record<string, string>> = {
  ai_emotion: { low: 'низкая', mid: 'средняя', high: 'высокая' },
  ai_constructiveness: { low: 'низкая', mid: 'средняя', high: 'высокая' },
  ai_tone: { neg: 'негатив', pos: 'позитив', neutral: 'неопределён' },
}

function aiLabel(key: string, fb: FeedbackAnswer) {
  const v = String((fb as any)[key] || '')
  return AI_LABELS[key]?.[v] || v || '—'
}

function aiClass(key: string, fb: FeedbackAnswer) {
  const v = String((fb as any)[key] || '')
  if (key === 'ai_tone') {
    if (v === 'pos') return 'badge--ok'
    if (v === 'neg') return 'badge--bad'
    return 'badge--neutral'
  }
  if (v === 'high') return 'badge--brand'
  if (v === 'mid') return 'badge--info'
  return 'badge--neutral'
}

/** Разобрать отзыв (синхронный вызов ИИ). */
async function onReview(fb: FeedbackAnswer) {
  reviewingId.value = fb.id
  reviewMsg.value = ''
  try {
    await feedbackApi.reviewOne(fb.id)
  } catch (e: any) {
    reviewMsg.value = e?.response?.data?.detail || String(e)
  } finally {
    reviewingId.value = ''
    await fetchData()
  }
}

/** Вернуть отзыв в очередь разбора (после ошибки). */
async function onRetry(fb: FeedbackAnswer) {
  reviewMsg.value = ''
  try {
    await feedbackApi.reviewRetry(fb.id)
    reviewMsg.value = 'Отзыв возвращён в очередь разбора'
  } catch (e: any) {
    reviewMsg.value = e?.response?.data?.detail || String(e)
  }
  await fetchData()
  await loadReviewErrors()
}

async function loadReviewErrors() {
  try {
    const d = await feedbackApi.reviewErrors(100)
    reviewErrors.value = d.items || []
  } catch {
    reviewErrors.value = []
  }
}

async function openErrors() {
  errorsOpen.value = true
  await loadReviewErrors()
}

async function onRetryError(e: FeedbackReviewError) {
  reviewMsg.value = ''
  try {
    await feedbackApi.reviewRetry(e.feedback_id)
    reviewMsg.value = 'Отзыв возвращён в очередь разбора'
  } catch (err: any) {
    reviewMsg.value = err?.response?.data?.detail || String(err)
  }
  await loadReviewErrors()
  await fetchData()
}

// --- промпт разбора отзыва ----------------------------------------------------
const promptOpen = ref(false)
const promptText = ref('')
const promptSaving = ref(false)
const promptMsg = ref('')
const promptMsgOk = ref(true)
const autoReview = ref(false)
const reviewBatch = ref(100)

async function openPrompt() {
  promptMsg.value = ''
  try {
    const s = await feedbackApi.reviewSettings()
    promptText.value = s.prompt || ''
    autoReview.value = !!s.auto
    reviewBatch.value = s.batch || 100
    promptOpen.value = true
  } catch (e: any) {
    promptMsg.value = e?.response?.data?.detail || String(e)
    promptMsgOk.value = false
  }
}

async function onSavePrompt() {
  promptSaving.value = true
  promptMsg.value = ''
  try {
    await feedbackApi.saveReviewPrompt(promptText.value)
    await feedbackApi.saveReviewSettings({ auto: autoReview.value, batch: reviewBatch.value })
    promptMsg.value = 'Промпт и настройки сохранены'
    promptMsgOk.value = true
  } catch (e: any) {
    promptMsg.value = e?.response?.data?.detail || String(e)
    promptMsgOk.value = false
  } finally {
    promptSaving.value = false
  }
}

function buildParams() {
  const p: Record<string, any> = {
    date_from: filters.value.date_from || undefined,
    date_to: filters.value.date_to || undefined,
    nm_id: filters.value.nm_id || undefined,
    rating: filters.value.rating || undefined,
    status: filters.value.status || undefined,
    sort: sort.value,
    order: order.value,
    page: page.value,
    page_size: pageSize,
  }
  if (filters.value.has_media) p.has_media = true
  if (filters.value.paid_only) p.paid_only = true
  if (filters.value.with_text) p.with_text = true
  return p
}

/**
 * WbUniversalFilter даёт свободную маску (nm_id / артикул / название),
 * а бэкенд ждёт чистый nm_id. Резолвим маску так же, как на /wb-questions.
 */
async function resolveNmId(mask: string): Promise<string> {
  const q = String(mask || '').trim()
  if (!q) return ''
  if (/^\d+$/.test(q)) return q
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

let syncing = false
function syncRoute() {
  const q: Record<string, string> = {}
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  if (filters.value.nm_id) q.nm_id = filters.value.nm_id
  if (filters.value.rating) q.rating = filters.value.rating
  if (filters.value.status) q.status = filters.value.status
  if (filters.value.has_media) q.has_media = '1'
  if (filters.value.paid_only) q.paid_only = '1'
  if (filters.value.with_text) q.with_text = '1'
  if (filters.value.hide_answers) q.hide_answers = '1'
  if (sort.value !== 'createdDate' || order.value !== 'desc') {
    q.sort = sort.value
    q.order = order.value
  }
  if (page.value > 1) q.page = String(page.value)
  syncing = true
  router.replace({ path: '/wb-feedback-answers', query: q }).finally(() => setTimeout(() => (syncing = false), 50))
}

async function fetchData() {
  isLoading.value = true
  syncRoute()
  try {
    const data = await feedbackApi.answers(buildParams())
    rows.value = data.items || []
    total.value = data.total || 0
    tagsSentiment.value = data.tags_sentiment || {}
    const map: Record<string, string> = {}
    for (const r of data.rules || []) map[String(r.id)] = r.title
    rulesById.value = map
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    isLoading.value = false
  }
}

async function onApply() {
  filters.value.nm_id = await resolveNmId(filters.value.nm_id)
  page.value = 1
  fetchData()
}
function onReset() {
  filters.value = {
    date_from: twoDaysAgo(), date_to: today(), nm_id: '', rating: '',
    status: '', has_media: false, paid_only: false, with_text: false, hide_answers: false,
  }
  page.value = 1
  fetchData()
}
function goPage(p: number) {
  page.value = p
  fetchData()
}

function onSort(col: string) {
  if (sort.value === col) {
    order.value = order.value === 'asc' ? 'desc' : 'asc'
  } else {
    sort.value = col
    order.value = col === 'createdDate' ? 'desc' : 'asc'
  }
  page.value = 1
  fetchData()
}
function sortIcon(col: string) {
  if (sort.value !== col) return 'bi-arrow-down-up'
  return order.value === 'asc' ? 'bi-sort-up' : 'bi-sort-down'
}

import { useDateFmt } from '../composables/useDateFmt'
const { fmtDateTime: fmtDate } = useDateFmt()
/** Оценка — бейдж темы (theme.md §5.7): без hex в разметке. */
function ratingBadge(r: number) {
  if (r === 5) return 'badge--ok'
  if (r === 4) return 'badge--warn'
  if (r === 3) return 'badge--neutral'
  return 'badge--bad'
}
function tagClass(t: string) {
  const s = tagsSentiment.value[t] || 'neutral'
  return s === 'positive' ? 'badge--ok' : s === 'negative' ? 'badge--bad' : 'badge--neutral'
}
function ruleTitle(fb: FeedbackAnswer) {
  return rulesById.value[String(fb.rule_id)] || 'Неизвестное правило'
}
function mediaOf(fb: FeedbackAnswer) {
  // Порт views/wb-feedback-answers/index.php:229-281:
  // video: link (массив: video['link'], строка: сама ссылка); poster = previewImage || первое фото
  // photos: miniSize || fullSize, ссылка на fullSize; height 120px, lazy
  const photos: Array<{ mini: string; full: string }> = []
  const rawPhotos = Array.isArray(fb.photoLinks) ? fb.photoLinks : []
  for (const p of rawPhotos) {
    if (!p || typeof p !== 'object') continue
    const mini = String(p.miniSize || p.fullSize || '')
    if (mini) photos.push({ mini, full: String(p.fullSize || mini) })
  }
  let video: { link: string; poster: string } | null = null
  const v = fb.video
  if (v) {
    const link = typeof v === 'object' && v !== null ? String(v.link || '') : typeof v === 'string' ? v : ''
    if (link) {
      const poster = (typeof v === 'object' && v !== null && v.previewImage)
        ? String(v.previewImage)
        : (photos.length ? photos[0].mini : '')
      video = { link, poster }
    }
  }
  return { video, photos }
}

onMounted(fetchData)
watch(() => route.query, () => {
  if (syncing) return
  fetchData()
})
</script>
