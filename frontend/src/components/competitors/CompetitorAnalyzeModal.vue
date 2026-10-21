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
            <span class="page-analyze__muted">{{ progressText }}</span>
          </template>
          <span v-else class="page-analyze__muted">выбираем модель…</span>
        </div>

        <div class="page-analyze__hint">
          Отдельный запрос к модели на каждого конкурента (до 4 параллельно), затем слияние формулировок.
          Обычно 30–120 секунд. Окно не закрывайте.
        </div>

        <div class="page-analyze__comps">
          <div class="page-analyze__comps-label">
            Описания конкурентов: {{ usableCount }} из {{ competitors.length }}
            <span v-if="skippedCount"> · {{ skippedCount }} без описания пропускаем</span>
            <span v-if="doneIds.size"> · разобрано: {{ doneIds.size }}</span>
          </div>
          <div
            v-for="c in competitors"
            :key="c.nm_id"
            class="page-analyze__comp"
            :class="{ 'page-analyze__comp--done': doneIds.has(String(c.nm_id)) }"
          >
            <span class="page-analyze__comp-nm">{{ c.nm_id }}</span>
            <span class="page-analyze__comp-title" :title="c.title || ''">{{ c.title || '—' }}</span>
            <span class="badge" :class="(c.desc_len || 0) >= descMin ? 'bg-success' : 'bg-secondary'">
              {{ c.desc_len || 0 }} симв.
            </span>
            <i
              v-if="doneIds.has(String(c.nm_id))"
              class="bi bi-check-circle-fill page-analyze__comp-ok"
              title="Разобран"
            ></i>
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
          <span v-if="rawCnt" class="page-analyze__muted">
            · формулировок было {{ rawCnt }}, слито в группы: {{ mergedCnt }}
          </span>
          <span v-if="analyzedCnt" class="page-analyze__muted"> · заново: {{ analyzedCnt }}</span>
          <span v-if="cachedCnt" class="page-analyze__muted"> · из кэша: {{ cachedCnt }}</span>
          <span v-if="model" class="page-analyze__muted"> · модель {{ model }}</span>
          <span v-if="promptVersion" class="page-analyze__muted"> · {{ promptVersion }}</span>
          <span class="page-analyze__muted"> · {{ elapsed }} с</span>
        </div>

        <div v-if="errors.length" class="page-analyze__errors">
          Не удалось разобрать: {{ errors.join('; ') }}
        </div>

        <div class="page-analyze__toolbar">
          <button class="btn btn-sm btn-outline-primary" @click="chooseRecommended">Рекомендованные</button>
          <button class="btn btn-sm btn-outline-secondary" @click="chooseCommon">Только общие</button>
          <button class="btn btn-sm btn-outline-secondary" @click="chooseInDb">Только в базе</button>
          <button class="btn btn-sm btn-outline-secondary" @click="chooseAll(true)">Выбрать все</button>
          <button class="btn btn-sm btn-outline-secondary" @click="chooseAll(false)">Снять все</button>
          <span class="badge bg-primary">выбрано: {{ chosen.length }}</span>
        </div>

        <div class="page-analyze__list">
          <table class="wb-admin-table page-analyze__grid">
            <thead>
              <tr>
                <th class="page-analyze__col-check"></th>
                <th>Фраза</th>
                <th class="text-center" title="У скольких конкурентов встречается — наведите, чтобы увидеть список">Конк.</th>
                <th class="text-center" title="Заказы в нашей базе">Заказы</th>
                <th>База</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in items" :key="p.id">
                <td class="text-center">
                  <input type="checkbox" :checked="chosen.includes(p.phrase)" @change="toggle(p.phrase, $event)" />
                </td>
                <td class="page-analyze__phrase" :title="variantsTitle(p)">
                  <span>{{ p.phrase }}</span>
                  <span v-if="p.variants_cnt > 1" class="page-analyze__variants">
                    +{{ p.variants_cnt - 1 }}
                  </span>
                </td>
                <td class="text-center">
                  <span class="page-analyze__whos">
                    <button type="button" class="btn btn-sm btn-link p-0 page-analyze__whos-btn">
                      {{ p.hit_cnt }}
                    </button>
                    <span class="page-analyze__whos-pop">
                      <span class="page-analyze__whos-title">Фраза встречается у конкурентов:</span>
                      <span v-for="c in p.competitors || []" :key="c.nm_id" class="page-analyze__whos-row">
                        <span class="page-analyze__whos-nm">{{ c.nm_id }}</span>
                        <span class="page-analyze__whos-name">{{ c.title || '—' }}</span>
                      </span>
                      <span v-if="!p.competitors.length" class="page-analyze__muted">нет данных</span>
                    </span>
                  </span>
                </td>
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
const analyzedCnt = ref(0)
const cachedCnt = ref(0)
const groupsCnt = ref(0)
const rawCnt = ref(0)
const mergedCnt = ref(0)
const errors = ref<string[]>([])
const elapsed = ref(0)
const applying = ref(false)
const runInfo = ref<NewCardRunStatus | null>(null)
const promptVersion = ref('')

let timer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let started = 0
let runId = ''

const statusText = computed(() => {
  const phase = runInfo.value?.phase
  if (phase === 'merge') return 'Сливаем формулировки в группы…'
  if (phase === 'extract') return 'Разбираем описания по одному конкуренту…'
  if (elapsed.value < 6) return 'Собираем описания конкурентов…'
  return 'Разбираем описания по одному конкуренту…'
})

/** Прогресс по фазам: сервер знает, что сейчас — разбор или слияние, и ведёт свой счётчик. */
const progressText = computed(() => {
  const r = runInfo.value
  if (!r) return ''
  if (r.phase === 'merge') return `сливаем формулировки: батч ${r.attempt} из ${r.total}`
  return `разобрано конкурентов: ${r.attempt} из ${r.total}`
})

/** nmID конкурентов, которых уже разобрали. */
const doneIds = computed(() => {
  const raw = runInfo.value?.done_ids || ''
  return new Set(raw.split(',').map((x) => x.trim()).filter(Boolean))
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

/** Общие формулировки: используют ≥2 разных конкурента. */
function chooseCommon() {
  chosen.value = items.value.filter((p) => p.hit_cnt >= 2).map((p) => p.phrase)
}

/** Рекомендованные: есть наши заказы И формулировку подтвердили конкуренты. */
function chooseRecommended() {
  chosen.value = items.value.filter((p) => p.orders > 0 && p.hit_cnt >= 2).map((p) => p.phrase)
}

/** Подсказка по фразе: как её формулируют конкуренты (если формулировок несколько). */
function variantsTitle(p: NewCardPhrase): string {
  const variants = p.variants || []
  if (variants.length < 2) return ''
  return 'У конкурентов так:\n' + variants.map((v) => '· ' + v).join('\n')
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
  analyzedCnt.value = 0
  cachedCnt.value = 0
  groupsCnt.value = 0
  rawCnt.value = 0
  mergedCnt.value = 0
  errors.value = []
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
    analyzedCnt.value = d.analyzed_cnt || 0
    cachedCnt.value = d.cached_cnt || 0
    groupsCnt.value = d.groups_cnt || 0
    rawCnt.value = d.raw_cnt || 0
    mergedCnt.value = d.merged_cnt || 0
    errors.value = d.errors || []
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
