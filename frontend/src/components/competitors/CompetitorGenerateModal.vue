<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="close">
    <div class="wb-modal-box page-gen__box">
      <div class="page-gen__head">
        <h5 class="page-gen__title">
          <i class="bi bi-magic"></i> Генерация title + description
          <span class="badge bg-dark">{{ nmId }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="close"></button>
      </div>

      <!-- прогресс -->
      <div v-if="state === 'running'" class="page-gen__running">
        <div class="page-gen__status">
          <span class="spinner-border spinner-border-sm text-success"></span>
          <span class="page-gen__status-text">{{ statusText }}</span>
          <span class="page-gen__timer">{{ elapsed }} с</span>
        </div>

        <div class="page-gen__model">
          <template v-if="runInfo?.model">
            модель: <b>{{ modelLabel() }}</b>
            <span class="badge" :class="runInfo.is_free ? 'bg-info text-dark' : 'bg-secondary'">
              {{ runInfo.is_free ? 'бесплатная' : 'платная' }}
            </span>
            <span class="page-gen__muted">попытка {{ runInfo.attempt }} из {{ runInfo.total }}</span>
          </template>
          <span v-else class="page-gen__muted">выбираем модель…</span>
        </div>

        <ol class="page-gen__steps">
          <li :class="stepClass(1)">
            <i class="bi" :class="stepIcon(1)"></i>
            Собираем данные: карточка, фразы, описания конкурентов
          </li>
          <li :class="stepClass(2)">
            <i class="bi" :class="stepIcon(2)"></i>
            Модель пишет заголовок и описание
            <span class="page-gen__step-hint">обычно 20–90 секунд</span>
          </li>
          <li :class="stepClass(3)">
            <i class="bi" :class="stepIcon(3)"></i>
            Проверяем длину и сохраняем в сводку
          </li>
        </ol>

        <div class="page-gen__input">
          <div class="page-gen__input-label">Что уходит в модель</div>
          <div class="page-gen__input-row">
            <span class="page-gen__muted">Карточка:</span>
            <span class="page-gen__card-title" :title="cardTitle || ''">{{ cardTitle || '—' }}</span>
          </div>
          <div class="page-gen__input-row">
            <span class="page-gen__muted">Конкурентов с описанием:</span>
            <span class="badge bg-success">{{ competitorsCnt }}</span>
            <span class="page-gen__muted">·</span>
            <span class="page-gen__muted">фраз:</span>
            <span class="badge bg-primary">{{ sentPhrases.length }}</span>
            <span v-if="phrases.length > sentPhrases.length" class="page-gen__muted">
              (из {{ phrases.length }}, в промпт идут первые {{ sentPhrases.length }})
            </span>
          </div>
          <div class="page-gen__chips">
            <span v-for="p in sentPhrases" :key="p" class="page-gen__chip">{{ p }}</span>
          </div>
        </div>
      </div>

      <!-- ошибка -->
      <div v-else-if="state === 'error'" class="page-gen__error">
        <div class="wb-error">{{ error }}</div>
        <div class="wb-modal-actions">
          <button class="btn btn-sm btn-primary" @click="run">Повторить</button>
          <button class="btn btn-sm btn-secondary" @click="close">Закрыть</button>
        </div>
      </div>

      <!-- результат -->
      <div v-else-if="state === 'done' && result" class="page-gen__done">
        <div class="page-gen__done-head">
          <span class="page-gen__done-ok"><i class="bi bi-check-circle-fill"></i> Готово</span>
          <span class="page-gen__muted">{{ result.model || '—' }} · {{ elapsed }} с</span>
        </div>
        <div v-if="copyError" class="wb-error">{{ copyError }}</div>

        <div class="page-gen__block">
          <div class="page-gen__block-head">
            <span class="page-gen__label">Заголовок</span>
            <span class="badge" :class="result.title_len > 60 ? 'bg-danger' : 'bg-success'">
              {{ result.title_len }} / 60
            </span>
            <button class="btn btn-sm btn-outline-secondary" @click="copy(result.title)">Копировать</button>
          </div>
          <div class="page-gen__title">{{ result.title }}</div>
        </div>

        <div class="page-gen__block">
          <div class="page-gen__block-head">
            <span class="page-gen__label">Описание</span>
            <span
              class="badge"
              :class="result.desc_len < result.desc_min || result.desc_len > result.desc_max ? 'bg-warning text-dark' : 'bg-success'"
            >
              {{ result.desc_len }} симв. (норма {{ result.desc_min }}–{{ result.desc_max }})
            </span>
            <button class="btn btn-sm btn-outline-secondary" @click="copy(result.description)">Копировать</button>
          </div>
          <div class="page-gen__desc">{{ result.description }}</div>
        </div>

        <div class="page-gen__meta">
          конкурентов: {{ result.competitor_count }} · фраз: {{ result.phrases.length }}
          <template v-if="result.phrases_used">
            · использовано: {{ result.phrases_used.length }} из {{ result.phrases.length }}
          </template>
          <template v-if="result.prompt_source">
            · промпт: {{ result.prompt_source === 'company' ? 'компании' : 'встроенный' }}
          </template>
          <template v-if="result.prompt_version"> · {{ result.prompt_version }}</template>
          <template v-if="resultAt"> · {{ resultAt }}</template>
        </div>
        <div v-if="result.phrases_missing?.length" class="page-gen__hint">
          Не вошли дословно: {{ result.phrases_missing.join('; ') }}
        </div>
        <div class="page-gen__hint">
          Сохранено в «Сводку» карточки. В саму карточку WB не пишется.
        </div>

        <div class="wb-modal-actions">
          <button class="btn btn-sm btn-outline-secondary" :disabled="copying" @click="copyAll">
            <i class="bi bi-clipboard"></i> Копировать всё
          </button>
          <button class="btn btn-sm btn-success" @click="run">
            <i class="bi bi-arrow-repeat"></i> Ещё раз
          </button>
          <button class="btn btn-sm btn-secondary" @click="close">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import {
  competitorsNewcardApi,
  type NewCardGenerateResult,
  type NewCardRunStatus,
} from '../../api/competitorsNewcard'
import { copyText } from '../../utils/clipboard'

const props = defineProps<{
  open: boolean
  nmId: number | string | null | undefined
  cardTitle?: string | null
  phrases: string[]
  competitorsCnt: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'done', result: NewCardGenerateResult): void
}>()

const state = ref<'running' | 'done' | 'error'>('running')
const error = ref('')
const result = ref<NewCardGenerateResult | null>(null)
const elapsed = ref(0)
const resultAt = ref('')
const copying = ref(false)
const copyError = ref('')
const runInfo = ref<NewCardRunStatus | null>(null)

const MAX_PROMPT_PHRASES = 12
const sentPhrases = computed(() => props.phrases.slice(0, MAX_PROMPT_PHRASES))

let timer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let started = 0
let runId = ''

const statusText = computed(() => {
  if (elapsed.value < 5) return 'Готовим промпт…'
  if (elapsed.value < 15) return 'Отправляем в модель…'
  return 'Модель пишет заголовок и описание…'
})

function stepDone(step: number): boolean {
  if (state.value === 'done') return true
  if (step === 1) return elapsed.value >= 1
  return false
}

function stepActive(step: number): boolean {
  if (state.value !== 'running') return false
  if (step === 1) return elapsed.value < 1
  if (step === 2) return elapsed.value >= 1
  return false
}

function stepClass(step: number) {
  return {
    'page-gen__step': true,
    'page-gen__step--done': stepDone(step),
    'page-gen__step--active': stepActive(step),
  }
}

function stepIcon(step: number): string {
  if (stepDone(step)) return 'bi-check-circle-fill'
  if (stepActive(step)) return 'bi-arrow-repeat'
  return 'bi-circle'
}

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function newRunId(): string {
  const c = (globalThis as any).crypto
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  return `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
}

async function pollRun(nm: number) {
  if (!runId) return
  try {
    runInfo.value = await competitorsNewcardApi.runStatus(nm, runId)
  } catch {
    /* 404 пока сервер не создал запись — это нормально */
  }
}

function modelLabel(): string {
  const m = runInfo.value?.model || ''
  return m.replace(/^.*\//, '')
}

function close() {
  stopTimer()
  stopPolling()
  emit('close')
}

async function run() {
  const nm = Number(props.nmId || 0)
  if (!nm) return
  state.value = 'running'
  error.value = ''
  copyError.value = ''
  result.value = null
  runInfo.value = null
  elapsed.value = 0
  started = Date.now()
  runId = newRunId()
  stopTimer()
  stopPolling()
  timer = setInterval(() => {
    elapsed.value = Math.max(0, Math.round((Date.now() - started) / 1000))
  }, 1000)
  pollTimer = setInterval(() => { void pollRun(nm) }, 1500)
  void pollRun(nm)
  try {
    const d = await competitorsNewcardApi.generate(
      nm,
      props.phrases.length ? props.phrases : undefined,
      runId,
    )
    result.value = d
    resultAt.value = new Date().toLocaleString('ru-RU')
    elapsed.value = Math.max(1, Math.round((Date.now() - started) / 1000))
    state.value = 'done'
    emit('done', d)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось сгенерировать'
    state.value = 'error'
  } finally {
    stopTimer()
    stopPolling()
  }
}

async function copy(text: string) {
  copyError.value = ''
  if (!await copyText(text || '')) {
    copyError.value = 'Не удалось скопировать текст'
  }
}

async function copyAll() {
  if (!result.value) return
  copying.value = true
  try {
    await copy(`${result.value.title}\n\n${result.value.description}`)
  } finally {
    copying.value = false
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) run()
    else {
      stopTimer()
      stopPolling()
    }
  },
)

onBeforeUnmount(() => {
  stopTimer()
  stopPolling()
})
</script>
