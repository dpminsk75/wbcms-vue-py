<template>
  <div v-if="open" class="page-wb-detail__modal-backdrop" @click.self="$emit('close')">
    <div class="page-wb-detail__modal-box page-wb-detail__modal-box--wide">
      <div class="page-wb-detail__modal-head">
        <h5 class="page-wb-detail__modal-title">
          <i class="bi bi-search"></i> Поисковые запросы
          <span class="page-wb-detail__modal-count">{{ items.length }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>
      <p class="page-wb-detail__modal-hint">
        Широкие запросы — нужны только для сбора конкурентов. В промпт описания они <b>не идут</b>
        (там целевые фразы). Запуск — в попапе расширения, источник «Запросы конкурентов».
      </p>

      <div class="page-wb-detail__chips">
        <span v-for="q in items" :key="q.id" class="badge bg-light text-dark page-wb-detail__chip page-wb-detail__chip--query">
          {{ q.phrase }}
          <span class="page-wb-detail__chip-status" :class="'is-' + q.status">{{ statusLabel(q.status) }}</span>
          <span v-if="q.status === 'done' || q.found_cnt" class="page-wb-detail__chip-found" title="Сколько конкурентов найдено по этому запросу">
            найдено {{ q.found_cnt || 0 }}<template v-if="q.best_position"> · лучшая {{ q.best_position }}</template>
          </span>
          <a href="#" class="page-wb-detail__chip-x" title="Удалить" @click.prevent="remove(q.id)">×</a>
        </span>
        <span v-if="!items.length" class="text-muted small">Пока нет — добавь ниже</span>
      </div>

      <form class="d-flex gap-2 mt-3 page-wb-detail__suggest-wrap" @submit.prevent="add()">
        <div class="position-relative flex-grow-1">
          <input
            v-model="phrase"
            class="form-control form-control-sm"
            placeholder="напр: дневник школьника"
            maxlength="500"
            :disabled="busy"
            @input="onInput"
            @focus="suggestVisible = true"
            @blur="hideSuggest"
          />
          <div v-if="suggestVisible && (suggest.length || suggestLoading)" class="page-wb-detail__suggest">
            <div v-if="suggestLoading" class="page-wb-detail__suggest-row text-muted">
              <span class="spinner-border spinner-border-sm"></span> ищем в базе...
            </div>
            <button
              v-for="s in suggest"
              :key="s.phrase"
              type="button"
              class="page-wb-detail__suggest-row"
              :class="{ 'is-added': s.added }"
              :disabled="s.added"
              @mousedown.prevent="pick(s)"
            >
              <span class="page-wb-detail__suggest-phrase">{{ s.phrase }}</span>
              <span class="page-wb-detail__suggest-meta">
                <span v-if="s.added" class="text-success">уже добавлен</span>
                <template v-else>{{ s.orders }} заказов · {{ s.cards }} карточек</template>
              </span>
            </button>
            <div v-if="!suggestLoading && !suggest.length" class="page-wb-detail__suggest-row text-muted">
              в базе нет совпадений
            </div>
          </div>
        </div>
        <button type="submit" class="btn btn-sm btn-outline-primary" :disabled="busy || !phrase.trim()">
          <i class="bi bi-plus-lg"></i> Добавить
        </button>
      </form>

      <div v-if="loading" class="text-muted small mt-2"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
      <div v-if="error" class="text-danger small mt-2">{{ error }}</div>
      <div v-if="subject" class="page-wb-detail__modal-footnote">Подсказки фильтруются по предмету: {{ subject }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { competitorsNewcardApi, type CompetitorQuery, type CompetitorQuerySuggest } from '@/api/competitorsNewcard'

const props = defineProps<{ open: boolean; nmId: number | string | null | undefined }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'changed'): void }>()

const items = ref<CompetitorQuery[]>([])
const phrase = ref('')
const subject = ref('')
const busy = ref(false)
const loading = ref(false)
const error = ref('')

const suggest = ref<CompetitorQuerySuggest[]>([])
const suggestVisible = ref(false)
const suggestLoading = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let pollInFlight = false
let seq = 0

const nm = () => Number(props.nmId || 0)

const STATUS: Record<string, string> = {
  pending: 'в очереди', processing: 'собираем', done: 'готово', error: 'ошибка',
}
const statusLabel = (s: string) => STATUS[s] || s

async function load(silent = false) {
  const id = nm()
  if (!id) return
  if (!silent) {
    loading.value = true
    error.value = ''
  }
  try {
    const d = await competitorsNewcardApi.queries(id)
    items.value = d.items || []
  } catch (e: any) {
    if (!silent) {
      error.value = e?.response?.data?.detail || 'Не удалось загрузить запросы'
      items.value = []
    }
  } finally {
    if (!silent) loading.value = false
  }
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPoll() {
  stopPoll()
  pollTimer = setInterval(async () => {
    if (pollInFlight || loading.value || busy.value) return
    pollInFlight = true
    try { await load(true) } finally { pollInFlight = false }
  }, 3000)
}

function onInput() {
  if (timer) clearTimeout(timer)
  const q = phrase.value.trim()
  if (q.length < 2) { suggest.value = []; return }
  timer = setTimeout(() => runSuggest(q), 250)
}

async function runSuggest(q: string) {
  const id = nm()
  if (!id) return
  const my = ++seq
  suggestLoading.value = true
  try {
    const d = await competitorsNewcardApi.suggest(id, q)
    if (my !== seq) return
    suggest.value = d.items || []
    subject.value = d.subject_name || ''
    suggestVisible.value = true
  } catch {
    if (my === seq) suggest.value = []
  } finally {
    if (my === seq) suggestLoading.value = false
  }
}

function hideSuggest() {
  // задержка: клик по подсказке идёт mousedown'ом раньше blur
  setTimeout(() => { suggestVisible.value = false }, 120)
}

async function pick(s: CompetitorQuerySuggest) {
  if (s.added) return
  phrase.value = s.phrase
  await add()
}

async function add() {
  const p = phrase.value.trim()
  const id = nm()
  if (!p || !id || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await competitorsNewcardApi.addQuery(id, p)
    phrase.value = ''
    suggest.value = []
    suggestVisible.value = false
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось добавить запрос'
  } finally {
    busy.value = false
  }
}

async function remove(qid: number) {
  const id = nm()
  if (!id) return
  error.value = ''
  try {
    await competitorsNewcardApi.removeQuery(id, qid)
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось удалить запрос'
  }
}

watch(
  () => [props.open, props.nmId] as const,
  ([isOpen]) => {
    if (isOpen) {
      phrase.value = ''
      suggest.value = []
      load()
      startPoll()
    } else {
      stopPoll()
    }
  },
)

onUnmounted(() => {
  if (timer) clearTimeout(timer)
  stopPoll()
})
</script>
