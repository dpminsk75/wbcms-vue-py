<template>
  <div class="container-xxl page-feedback-answers">
    <h1 class="page-title">{{ $route.meta.title || 'Отзывы и ответы' }}</h1>
    <div class="bg-light p-3 rounded mb-4 page-feedback-answers__filter">
      <div class="row g-3 mb-3">
        <div class="col-12 col-md-2">
          <label class="form-label fw-medium text-muted small mb-1">С даты</label>
          <input v-model="filters.date_from" type="date" class="form-control" />
        </div>
        <div class="col-12 col-md-2">
          <label class="form-label fw-medium text-muted small mb-1">По дату</label>
          <input v-model="filters.date_to" type="date" class="form-control" />
        </div>
        <div class="col-12 col-md-3">
          <label class="form-label fw-medium text-muted small mb-1">Оценка</label>
          <select v-model="filters.rating" class="form-select">
            <option value="">Все оценки</option>
            <option value="5">5 ★</option>
            <option value="4">4 ★</option>
            <option value="3">3 ★</option>
            <option value="2">2 ★</option>
            <option value="1">1 ★</option>
          </select>
        </div>
        <div class="col-12 col-md-2">
          <label class="form-label fw-medium text-muted small mb-1">Статус ответа</label>
          <select v-model="filters.status" class="form-select">
            <option value="">Все</option>
            <option value="answered">Есть ответ</option>
            <option value="not_answered">Нет ответа</option>
          </select>
        </div>
        <div class="col-12 col-md-3">
          <label class="form-label fw-medium text-muted small mb-1">Товар (артикул)</label>
          <div class="d-flex gap-2">
            <input v-model="cardQuery" class="form-control" placeholder="nmID..." @keydown.enter="onApply" />
            <button v-if="filters.nm_id" class="btn btn-light" title="Очистить" @click="clearCard">×</button>
          </div>
        </div>
      </div>
      <div class="row g-3 align-items-end">
        <div class="col-6 col-md-4 d-flex gap-3">
          <div class="form-check">
            <input id="fa-media" v-model="filters.has_media" type="checkbox" class="form-check-input" />
            <label for="fa-media" class="form-check-label">Только с фото/видео</label>
          </div>
          <div class="form-check">
            <input id="fa-paid" v-model="filters.paid_only" type="checkbox" class="form-check-input" />
            <label for="fa-paid" class="form-check-label">Только платные</label>
          </div>
          <div class="form-check">
            <input id="fa-hide" v-model="filters.hide_answers" type="checkbox" class="form-check-input" />
            <label for="fa-hide" class="form-check-label">Не выводить ответы</label>
          </div>
        </div>
        <div class="col-6 col-md-4 d-flex gap-2">
          <button class="btn btn-primary" :disabled="isLoading" @click="onApply">Применить</button>
          <button class="btn btn-light" @click="onReset">Сбросить</button>
        </div>
        <div class="col-12 col-md-4 text-end text-muted small">Всего: {{ total }}</div>
      </div>
    </div>
    <div class="card">
      <div v-if="isLoading" class="text-center p-5">
        <div class="spinner-border text-primary" role="status"></div>
        <div class="mt-2 text-muted">Загрузка данных...</div>
      </div>
      <div v-else class="wb-table-wrap">
        <table class="table table-striped align-middle mb-0">
          <thead>
            <tr>
              <th>Товар</th>
              <th>Отзыв</th>
              <th v-if="!filters.hide_answers">Ответ</th>
              <th class="text-center">Правило</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fb in rows" :key="fb.id">
              <td>
                <div class="fw-bold">{{ fb.product_title || '(без названия)' }}</div>
                <div class="small text-muted">Арт WB:
                  <router-link :to="`/wb/detail?nm_id=${fb.nmID}`" target="_blank" class="adv-link">{{ fb.nmID }}</router-link>
                </div>
                <div v-if="Number(fb.f_cost) > 0" class="mt-1"><span class="badge bg-warning text-dark">Оплачен: {{ fb.f_cost }} ₽</span></div>
              </td>
              <td>
                <div class="d-flex gap-2 align-items-center mb-1">
                  <span class="text-muted small">{{ fmtDate(fb.createdDate) }}</span>
                  <span class="badge" :style="{ background: ratingColor(Number(fb.productValuation)) }">{{ fb.productValuation }} ★</span>
                </div>
                <div v-if="fb.text" class="mb-1"><b>Отзыв:</b> {{ fb.text }}</div>
                <div v-if="fb.pros" class="mb-1"><b>Плюсы:</b> {{ fb.pros }}</div>
                <div v-if="fb.cons" class="mb-1"><b>Минусы:</b> {{ fb.cons }}</div>
                <div v-if="fb.bables?.length" class="d-flex flex-wrap gap-1">
                  <span v-for="t in fb.bables" :key="t" class="badge" :class="tagClass(t)">{{ t }}</span>
                </div>
              </td>
              <td v-if="!filters.hide_answers">
                <div v-if="fb.answer_text">
                  <div class="text-muted small mb-1">{{ fmtDate(fb.updatedDate) }}</div>
                  <div class="page-feedback-answers__answer">{{ fb.answer_text }}</div>
                </div>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="text-center">
                <span v-if="fb.rule_id" class="page-feedback-answers__rule" :title="ruleTitle(fb)">{{ fb.rule_id }}</span>
                <span v-else class="text-muted">—</span>
              </td>
            </tr>
            <tr v-if="!rows.length"><td :colspan="filters.hide_answers ? 3 : 4" class="text-center text-muted p-4">Отзывов не найдено</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="page-feedback-answers__pager">
      <button class="btn btn-sm btn-light" :disabled="page <= 1" @click="goPage(page - 1)">‹ Назад</button>
      <span class="page-feedback-answers__pager-label">Стр. {{ page }} из {{ totalPages }}</span>
      <button class="btn btn-sm btn-light" :disabled="page >= totalPages" @click="goPage(page + 1)">Вперёд ›</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-feedback-answers.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { feedbackApi, type FeedbackAnswer } from '@/api/feedback'

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
  hide_answers: route.query.hide_answers === '1',
})
const cardQuery = ref(filters.value.nm_id)
const rows = ref<FeedbackAnswer[]>([])
const total = ref(0)
const page = ref(Number(route.query.page || 1))
const pageSize = 30
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const isLoading = ref(false)
const tagsSentiment = ref<Record<string, string>>({})
const rulesById = ref<Record<string, string>>({})

function buildParams() {
  const p: Record<string, any> = {
    date_from: filters.value.date_from || undefined,
    date_to: filters.value.date_to || undefined,
    nm_id: filters.value.nm_id || undefined,
    rating: filters.value.rating || undefined,
    status: filters.value.status || undefined,
    page: page.value,
    page_size: pageSize,
  }
  if (filters.value.has_media) p.has_media = true
  if (filters.value.paid_only) p.paid_only = true
  return p
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
  if (filters.value.hide_answers) q.hide_answers = '1'
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

function onApply() {
  filters.value.nm_id = cardQuery.value.trim()
  page.value = 1
  fetchData()
}
function onReset() {
  filters.value = {
    date_from: twoDaysAgo(), date_to: today(), nm_id: '', rating: '',
    status: '', has_media: false, paid_only: false, hide_answers: false,
  }
  cardQuery.value = ''
  page.value = 1
  fetchData()
}
function clearCard() {
  cardQuery.value = ''
  filters.value.nm_id = ''
  page.value = 1
  fetchData()
}
function goPage(p: number) {
  page.value = p
  fetchData()
}

function fmtDate(v: any) {
  if (!v) return ''
  const d = new Date(String(v).replace(' ', 'T'))
  if (isNaN(d.getTime())) return String(v)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`
}
function ratingColor(r: number) {
  if (r === 5) return '#198754'
  if (r === 4) return '#ffc107'
  if (r === 3) return '#6c757d'
  return '#dc3545'
}
function tagClass(t: string) {
  const s = tagsSentiment.value[t] || 'neutral'
  return s === 'positive' ? 'bg-success' : s === 'negative' ? 'bg-danger' : 'bg-secondary'
}
function ruleTitle(fb: FeedbackAnswer) {
  return rulesById.value[String(fb.rule_id)] || 'Неизвестное правило'
}

onMounted(fetchData)
watch(() => route.query, () => {
  if (syncing) return
  fetchData()
})
</script>
