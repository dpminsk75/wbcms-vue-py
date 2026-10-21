<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="close">
    <div class="wb-modal-box page-analyze__box">
      <div class="page-analyze__head">
        <h5 class="page-analyze__title">
          <i class="bi bi-stars"></i> Анализ описаний конкурентов
          <span class="badge bg-dark">{{ nmId }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="close"></button>
      </div>

      <!-- прогресс -->
      <div v-if="state === 'running'" class="page-analyze__running">
        <div class="page-analyze__status">
          <span class="spinner-border spinner-border-sm text-primary"></span>
          <span class="page-analyze__status-text">{{ statusText }}</span>
          <span class="page-analyze__timer">{{ elapsed }} с</span>
        </div>

        <div class="page-analyze__bar"><div class="page-analyze__bar-fill"></div></div>

        <div class="page-analyze__model">
          <template v-if="runInfo?.model">
            модель: <b>{{ modelLabel() }}</b>
            <span class="badge" :class="runInfo.is_free ? 'bg-info text-dark' : 'bg-secondary'">
              {{ runInfo.is_free ? 'бесплатная' : 'платная' }}
            </span>
            <span class="page-analyze__muted">попытка {{ runInfo.attempt }} из {{ runInfo.total }}</span>
          </template>
          <span v-else class="page-analyze__muted">выбираем модель…</span>
        </div>

        <div class="page-analyze__hint">
          Один запрос к модели по всем собранным описаниям — обычно 20–60 секунд. Окно не закрывайте.
        </div>

        <div class="page-analyze__comps">
          <div class="page-analyze__comps-label">
            Описания конкурентов: {{ usableCount }} из {{ competitors.length }}
            <span v-if="skippedCount"> · {{ skippedCount }} без описания пропускаем</span>
          </div>
          <div v-for="c in competitors" :key="c.nm_id" class="page-analyze__comp">
            <span class="page-analyze__comp-nm">{{ c.nm_id }}</span>
            <span class="page-analyze__comp-title" :title="c.title || ''">{{ c.title || '—' }}</span>
            <span class="badge" :class="(c.desc_len || 0) >= descMin ? 'bg-success' : 'bg-secondary'">
              {{ c.desc_len || 0 }} симв.
            </span>
          </div>
        </div>
      </div>

      <!-- ошибка -->
      <div v-else-if="state === 'error'" class="page-analyze__error">
        <div class="wb-error">{{ error }}</div>
        <div class="wb-modal-actions">
          <button class="btn btn-sm btn-primary" @click="run">Повторить</button>
          <button class="btn btn-sm btn-secondary" @click="close">Закрыть</button>
        </div>
      </div>

      <!-- результат -->
      <div v-else-if="state === 'done'" class="page-analyze__done">
        <div class="page-analyze__summary">
          Найдено <b>{{ items.length }}</b> фраз по <b>{{ competitorsCnt }}</b> конкурентам
          <span v-if="model" class="page-analyze__muted"> · модель {{ model }}</span>
          <span v-if="promptVersion" class="page-analyze__muted"> · {{ promptVersion }}</span>
          <span class="page-analyze__muted"> · {{ elapsed }} с</span>
        </div>

        <div class="page-analyze__toolbar">
          <button class="btn btn-sm btn-outline-secondary" @click="chooseAll(true)">Выбрать все</button>
          <button class="btn btn-sm btn-outline-secondary" @click="chooseInDb">Только в базе</button>
          <button class="btn btn-sm btn-outline-secondary" @click="chooseAll(false)">Снять все</button>
          <span class="badge bg-primary">выбрано: {{ chosen.length }}</span>
        </div>

        <div class="page-analyze__list">
          <table class="wb-admin-table page-analyze__grid">
            <thead>
              <tr>
                <th class="page-analyze__col-check"></th>
                <th>Фраза</th>
                <th class="text-center" title="У скольких конкурентов встречается">Конк.</th>
                <th class="text-center" title="Заказы в нашей базе">Заказы</th>
                <th>База</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in items" :key="p.id">
                <td class="text-center">
                  <input type="checkbox" :checked="chosen.includes(p.phrase)" @change="toggle(p.phrase, $event)" />
                </td>
                <td class="page-analyze__phrase">{{ p.phrase }}</td>
                <td class="text-center">{{ p.hit_cnt }}</td>
                <td class="text-center">{{ p.orders || '—' }}</td>
                <td>
                  <span v-if="p.in_db" class="badge bg-success">в базе</span>
                  <span v-else class="badge bg-warning text-dark">новая</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="wb-modal-actions">
          <button class="btn btn-sm btn-primary" :disabled="applying || !chosen.length" @click="apply">
            <span v-if="applying" class="spinner-border spinner-border-sm"></span>
            {{ applying ? 'Сохраняем…' : 'Применить выбор' }}
          </button>
          <button class="btn btn-sm btn-secondary" :disabled="applying" @click="close">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import {
  competitorsNewcardApi,
  type CompetitorRow,
  type NewCardPhrase,
  type NewCardRunStatus,
} from '../../api/competitorsNewcard'

const props = defineProps<{
  open: boolean
  nmId: number | string | null | undefined
  competitors: CompetitorRow[]
  descMin?: number
}>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'done'): void }>()

const descMin = computed(() => props.descMin || 50)
const usableCount = computed(() => props.competitors.filter((c) => (c.desc_len || 0) >= descMin.value).length)
const skippedCount = computed(() => props.competitors.length - usableCount.value)

const state = ref<'running' | 'done' | 'error'>('running')
const error = ref('')
const items = ref<NewCardPhrase[]>([])
const chosen = ref<string[]>([])
const model = ref('')
const competitorsCnt = ref(0)
const elapsed = ref(0)
const applying = ref(false)
const runInfo = ref<NewCardRunStatus | null>(null)
const promptVersion = ref('')

let timer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let started = 0
let runId = ''

const statusText = computed(() => {
  if (elapsed.value < 6) return 'Собираем описания конкурентов…'
  if (elapsed.value < 15) return 'Отправляем описания в модель…'
  return 'Модель извлекает поисковые фразы…'
})

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

function toggle(phrase: string, e: Event) {
  const on = (e.target as HTMLInputElement).checked
  chosen.value = chosen.value.filter((x) => x !== phrase)
  if (on) chosen.value.push(phrase)
}

function chooseAll(on: boolean) {
  chosen.value = on ? items.value.map((p) => p.phrase) : []
}

function chooseInDb() {
  chosen.value = items.value.filter((p) => p.in_db).map((p) => p.phrase)
}

async function run() {
  const nm = Number(props.nmId || 0)
  if (!nm) return
  state.value = 'running'
  error.value = ''
  items.value = []
  chosen.value = []
  model.value = ''
  competitorsCnt.value = 0
  promptVersion.value = ''
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
    const d = await competitorsNewcardApi.analyzePhrases(nm, runId)
    items.value = d.items || []
    chosen.value = (d.items || []).filter((p) => p.is_selected).map((p) => p.phrase)
    model.value = d.model || ''
    competitorsCnt.value = d.competitors_cnt || 0
    promptVersion.value = d.prompt_version || ''
    elapsed.value = Math.max(1, Math.round((Date.now() - started) / 1000))
    state.value = 'done'
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось проанализировать описания'
    state.value = 'error'
  } finally {
    stopTimer()
    stopPolling()
  }
}

async function apply() {
  const nm = Number(props.nmId || 0)
  if (!nm || applying.value) return
  applying.value = true
  error.value = ''
  try {
    const all = items.value.map((p) => p.phrase)
    const on = new Set(chosen.value)
    const toSelect = all.filter((p) => on.has(p))
    const toClear = all.filter((p) => !on.has(p))
    if (toSelect.length) await competitorsNewcardApi.selectPhrases(nm, toSelect, true)
    if (toClear.length) await competitorsNewcardApi.selectPhrases(nm, toClear, false)
    emit('done')
    stopTimer()
    emit('close')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось сохранить выбор'
  } finally {
    applying.value = false
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
