<template>
  <div class="container-xxl page-feedback-review">
    <WbWorkspaceHead :title="$route.meta.title || 'Разбор отзывов (фон)'" :workspace-tabs="FEEDBACK_TABS" workspace-active="review" />

    <!-- Панель статуса — блок темы .wb-panel (theme.md §5.7.9) -->
    <div class="wb-panel page-feedback-review__panel">
      <div class="card__hd">
        <span><i class="bi bi-activity me-1"></i> Статус фонового разбора</span>
        <span class="spacer"></span>
        <span v-if="st?.flags?.paused" class="badge badge--warn">Пауза</span>
        <span v-else-if="st?.flags?.balance_paused" class="badge badge--warn">Пауза ИИ</span>
        <span v-else-if="st?.flags?.manual_running" class="badge badge--info">Разбор идёт</span>
        <span v-else-if="st?.flags?.running" class="badge badge--ok">Работает</span>
        <span v-else class="badge badge--neutral">Не запущен</span>
        <button class="hd-btn" :disabled="!st || toggling" @click="togglePause">
          <i class="bi me-1" :class="isPaused ? 'bi-play-fill' : 'bi-pause-fill'"></i>
          {{ isPaused ? 'Возобновить' : 'Пауза' }}
        </button>
        <button class="hd-btn" :disabled="loading" @click="refreshAll">
          <i class="bi bi-arrow-clockwise me-1"></i> Обновить
        </button>
      </div>
      <div class="wb-panel__bd">
        <div v-if="loadErr" class="page-feedback-review__alert page-feedback-review__alert--bad">{{ loadErr }}</div>
        <div v-if="msg" class="page-feedback-review__alert page-feedback-review__alert--info">{{ msg }}</div>
        <div v-if="st?.flags?.balance_paused" class="page-feedback-review__alert page-feedback-review__alert--warn">
          <i class="bi bi-pause-circle"></i>
          <span>
            У ИИ-провайдера кончились токены
            ({{ st?.flags?.balance_pause_reason || 'insufficient_balance' }}) —
            разбор на паузе до {{ fmtTime(st?.flags?.balance_pause_until) }}
            <span class="page-feedback-review__muted">(осталось {{ fmtLeft(st?.flags?.balance_pause_left_sec) }})</span>
          </span>
          <button class="btn btn--outline btn-sm ms-auto" :disabled="toggling" @click="togglePause">
            Возобновить сейчас
          </button>
        </div>

        <div class="row g-3 page-feedback-review__status">
          <div class="col-12 col-md-6 col-xl-3">
            <div class="page-feedback-review__k">Очередь</div>
            <div class="mb-1">
              <b>{{ st?.counts?.queue_count || 0 }}</b> неразобранных отзывов
              <span class="page-feedback-review__muted page-feedback-review__small">(за 30 дней)</span>
            </div>
            <div class="mb-1">ждут повторного разбора: <b>{{ st?.counts?.pending || 0 }}</b></div>
            <div>готово: <b>{{ st?.counts?.done || 0 }}</b> · ошибок: <b>{{ st?.counts?.error || 0 }}</b></div>
            <div v-if="st?.quota?.ok" class="mt-1 page-feedback-review__small">
              Лимит ИИ: <b>{{ st?.quota?.percent }}%</b>
              <span class="page-feedback-review__muted">· сброс в {{ fmtClock(st?.quota?.reset_at) }}
                <template v-if="st?.quota?.reset_left">· осталось {{ st?.quota?.reset_left }}</template>
              </span>
            </div>
            <div v-else-if="st?.quota?.applicable && !st?.quota?.ok" class="mt-1 page-feedback-review__muted page-feedback-review__small">
              Лимит ИИ: не удалось проверить ({{ st?.quota?.error || 'нет данных' }})
            </div>
            <div v-if="st?.quota?.weekly_percent !== null && st?.quota?.weekly_percent !== undefined && st?.quota?.weekly_percent < 10"
                 class="page-feedback-review__small page-feedback-review__warn">
              Недельный лимит: {{ st?.quota?.weekly_percent }}%
            </div>
          </div>

          <div class="col-12 col-md-6 col-xl-3">
            <div class="page-feedback-review__k">Настройки</div>
            <div class="form-check form-switch mb-2">
              <input id="fr-auto" v-model="auto" class="form-check-input" type="checkbox" />
              <label class="form-check-label" for="fr-auto">Авторазбор в фоне</label>
            </div>
            <div class="page-feedback-review__settings">
              <label class="page-feedback-review__muted page-feedback-review__small" for="fr-batch">Отзывов за прогон</label>
              <input id="fr-batch" v-model.number="batch" type="number" min="1" max="500"
                     class="wb-input page-feedback-review__batch" />
              <button class="btn btn--outline btn-sm" :disabled="saving" @click="onSaveSettings">
                Сохранить
              </button>
            </div>
          </div>

          <div class="col-12 col-md-6 col-xl-3">
            <div class="page-feedback-review__k">Промпт</div>
            <div class="mb-2">
              <span v-if="st?.prompt_set" class="page-feedback-review__ok">задан</span>
              <span v-else class="page-feedback-review__bad">не задан — разбор не пойдёт</span>
            </div>
            <button class="btn btn--outline btn-sm" @click="openPrompt">
              {{ st?.prompt_set ? 'Изменить' : 'Задать' }}
            </button>
          </div>

          <div class="col-12 col-md-6 col-xl-3">
            <div class="page-feedback-review__k">Разобрать сейчас</div>
            <button class="btn btn--brand btn-sm mb-2" :disabled="running || !st?.prompt_set || st?.flags?.balance_paused" @click="onRun">
              <span v-if="running" class="spinner-border spinner-border-sm me-1"></span>
              {{ running ? 'Разбираем...' : 'Разобрать порцию' }}
            </button>
            <div class="page-feedback-review__hint">Фоновый цикл: каждые {{ st?.flags?.interval_sec || 60 }} с</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Вкладки — чипы темы (§5.6.3) -->
    <div class="page-feedback-review__tabs">
      <WbChipGroup v-model="tab" :options="tabOptions" />
    </div>

    <!-- ===== Очередь ===== -->
    <div v-show="tab === 'queue'">
      <div class="tbl-card page-feedback-review__card">
        <div class="card__hd">
          <span><i class="bi bi-list-ol me-1"></i> Неразобранные отзывы</span>
          <span class="spacer"></span>
          <button class="hd-btn" @click="loadQueue">Обновить</button>
        </div>
        <div v-if="!queue.length" class="page-feedback-review__empty">Очередь пуста</div>
        <div v-else class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr><th class="t-left">Дата</th><th class="t-left">nmID</th><th class="t-center">★</th><th class="t-left">Отзыв</th></tr>
            </thead>
            <tbody>
              <tr v-for="it in queue" :key="it.id">
                <td class="t-left num page-feedback-review__small">{{ it.created_at }}</td>
                <td class="t-left page-feedback-review__small">{{ it.nm_id }}</td>
                <td class="t-center page-feedback-review__small">{{ it.rating }}</td>
                <td class="t-left page-feedback-review__small">{{ (it.text || '').slice(0, 200) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ===== Ошибки ===== -->
    <div v-show="tab === 'errors'">
      <div class="tbl-card page-feedback-review__card">
        <div class="card__hd">
          <span><i class="bi bi-exclamation-triangle me-1"></i> Ошибки разбора</span>
          <span class="spacer"></span>
          <button class="hd-btn" :disabled="!(st?.counts?.error || 0)" @click="onRetryAll">
            Вернуть все в очередь
          </button>
          <button class="hd-btn" @click="loadErrors">Обновить</button>
        </div>
        <div v-if="!errors.length" class="page-feedback-review__empty">Ошибок нет</div>
        <div v-else class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr><th class="t-left">Дата</th><th class="t-left">Товар</th><th class="t-left">Отзыв</th><th class="t-left">Ошибка</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="e in errors" :key="e.feedback_id">
                <td class="t-left num page-feedback-review__small">{{ e.created_at }}</td>
                <td class="t-left page-feedback-review__small">{{ e.product_title || e.nm_id }}</td>
                <td class="t-left page-feedback-review__small">{{ (e.text || '').slice(0, 120) }}</td>
                <td class="t-left page-feedback-review__small page-feedback-review__bad" :title="e.error || ''">
                  {{ (e.error || '').slice(0, 80) }}
                </td>
                <td class="t-right">
                  <button class="btn btn--outline btn-sm" @click="onRetryOne(e)">
                    В очередь
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ===== Лог ===== -->
    <div v-show="tab === 'log'">
      <div class="tbl-card page-feedback-review__card">
        <div class="card__hd">
          <span><i class="bi bi-journal-text me-1"></i> Лог работы</span>
          <span class="spacer"></span>
          <select v-model="logLevel" class="wb-select page-feedback-review__level" @change="logOffset = 0; loadLog()">
            <option value="">Все уровни</option>
            <option value="info">info</option>
            <option value="warn">warn</option>
            <option value="error">error</option>
          </select>
          <button class="hd-btn" @click="loadLog">Обновить</button>
        </div>
        <div v-if="logErr" class="page-feedback-review__alert page-feedback-review__alert--warn">{{ logErr }}</div>
        <div v-if="!logItems.length" class="page-feedback-review__empty">Журнал пуст</div>
        <div v-else class="tbl-wrap">
          <table class="tbl tbl-card--compact">
            <thead>
              <tr><th class="t-left">Время</th><th class="t-left">Уровень</th><th class="t-left">Событие</th><th class="t-left">Сообщение</th></tr>
            </thead>
            <tbody>
              <tr v-for="l in logItems" :key="l.id">
                <td class="t-left num page-feedback-review__small">{{ l.created_at }}</td>
                <td class="t-left page-feedback-review__small" :class="l.level === 'error' ? 'page-feedback-review__bad' : ''">{{ l.level }}</td>
                <td class="t-left page-feedback-review__small">{{ l.action }}</td>
                <td class="t-left page-feedback-review__small">{{ l.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ===== Затраты ИИ ===== -->
    <div v-show="tab === 'cost'">
      <div class="tbl-card page-feedback-review__card">
        <div class="card__hd">
          <span><i class="bi bi-cash-coin me-1"></i> Затраты ИИ (сценарий feedback_review)</span>
        </div>
        <div class="wb-panel__bd">
          <div class="row g-3 mb-3">
            <div class="col-md-3" v-for="p in costPeriods" :key="p.key">
              <div class="page-feedback-review__k">{{ p.label }}</div>
              <div>вызовов: <b>{{ p.block.calls || 0 }}</b></div>
              <div class="page-feedback-review__muted page-feedback-review__small">токенов: {{ p.block.total_tokens || 0 }}</div>
              <div v-if="st?.can_see_cost" class="page-feedback-review__small">$ {{ p.block.cost || 0 }}</div>
            </div>
          </div>
          <div v-if="(st?.ai_usage?.by_model || []).length">
            <div class="page-feedback-review__k mb-1">По моделям</div>
            <div class="tbl-wrap">
              <table class="tbl tbl-card--compact">
                <thead>
                  <tr><th class="t-left">Модель</th><th class="t-center">Вызовов</th><th class="t-center">Токенов</th><th v-if="st?.can_see_cost" class="t-center">$</th></tr>
                </thead>
                <tbody>
                  <tr v-for="m in st?.ai_usage?.by_model || []" :key="m.grp">
                    <td class="t-left page-feedback-review__small">{{ m.grp }}</td>
                    <td class="t-center page-feedback-review__small">{{ m.calls || 0 }}</td>
                    <td class="t-center page-feedback-review__small">{{ m.total_tokens || 0 }}</td>
                    <td v-if="st?.can_see_cost" class="t-center page-feedback-review__small">{{ m.cost || 0 }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Промпт -->
    <div v-if="promptOpen" class="modal d-block page-feedback-review__modal" tabindex="-1"
         @click.self="promptOpen = false">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header py-2">
            <span class="modal-title page-feedback-review__modal-title">Промпт разбора отзыва</span>
            <button type="button" class="btn-close" @click="promptOpen = false"></button>
          </div>
          <div class="modal-body">
            <p class="page-feedback-review__muted page-feedback-review__small">
              Промпт применяется к каждому отзыву отдельно. Модель — «Модель (сводка)».
              Формат ответа: JSON с полями emotion, constructiveness, tone.
            </p>
            <textarea v-model="promptText" class="wb-input page-feedback-review__prompt" rows="18"></textarea>
          </div>
          <div class="modal-footer py-2">
            <span v-if="promptMsg" class="me-auto page-feedback-review__small"
                  :class="promptMsgOk ? 'page-feedback-review__ok' : 'page-feedback-review__bad'">
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
import '@/assets/css/pages/page-feedback-review.css'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { feedbackApi } from '@/api/feedback'
import {
  feedbackReviewApi,
  type ReviewLogItem,
  type ReviewQueueItem,
  type ReviewStatusFull,
} from '@/api/feedbackReview'
import WbChipGroup from '@/components/common/WbChipGroup.vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { FEEDBACK_TABS } from '@/components/common/workspaceTabs'

const route = useRoute()

const st = ref<ReviewStatusFull | null>(null)
const queue = ref<ReviewQueueItem[]>([])
const errors = ref<any[]>([])
const logItems = ref<ReviewLogItem[]>([])
const logTotal = ref(0)
const logErr = ref('')
const logLevel = ref('')
const tab = ref<'queue' | 'errors' | 'log' | 'cost'>('queue')

/** Вкладки — чипы темы (§5.6.3). */
const tabOptions = computed(() => [
  { value: 'queue', label: 'Очередь' },
  { value: 'errors', label: `Ошибки (${st.value?.counts?.error || 0})` },
  { value: 'log', label: `Лог работы (${logTotal.value})` },
  { value: 'cost', label: 'Затраты ИИ' },
])
const loading = ref(false)
const loadErr = ref('')
const msg = ref('')
const toggling = ref(false)
const running = ref(false)
const saving = ref(false)
const auto = ref(false)
const batch = ref(100)
const promptOpen = ref(false)
const promptText = ref('')
const promptSaving = ref(false)
const promptMsg = ref('')
const promptMsgOk = ref(true)

/** Авто-обновление статуса/лога, пока разбор идёт в фоне. */
let timer: ReturnType<typeof setInterval> | null = null

const costPeriods = computed(() => {
  const u = st.value?.ai_usage
  return [
    { key: 'today', label: 'Сегодня', block: u?.today || { calls: 0, total_tokens: 0, cost: 0 } },
    { key: 'week', label: '7 дней', block: u?.week || { calls: 0, total_tokens: 0, cost: 0 } },
    { key: 'month', label: '30 дней', block: u?.month || { calls: 0, total_tokens: 0, cost: 0 } },
  ]
})

/** Пауза активна: ручная или по отсутствию токенов у провайдера. */
const isPaused = computed(() => !!st.value?.flags?.paused || !!st.value?.flags?.balance_paused)

function fmtTime(v: string | null | undefined): string {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 16)
}

function fmtLeft(sec: number | null | undefined): string {
  const m = Math.max(0, Math.round((sec || 0) / 60))
  if (m < 60) return `${m} мин`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest ? `${h} ч ${rest} мин` : `${h} ч`
}

/** Время сброса окна лимита — в таймзоне браузера (бэк отдаёт ISO со смещением). */
function fmtClock(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

async function loadStatus() {
  st.value = await feedbackReviewApi.status()
  auto.value = !!st.value.settings?.auto
  batch.value = st.value.settings?.batch || 100
}

async function loadQueue() {
  const d = await feedbackReviewApi.queue(50, 0)
  queue.value = d.items || []
}

async function loadErrors() {
  const d = await feedbackReviewApi.errors(100)
  errors.value = d.items || []
}

async function loadLog() {
  const d = await feedbackReviewApi.log(logLevel.value || null, 50, 0)
  logItems.value = d.items || []
  logTotal.value = d.total || 0
  logErr.value = d.error || ''
}

async function refreshAll() {
  loading.value = true
  loadErr.value = ''
  try {
    await loadStatus()
    // лог тянем сразу — чтобы бейдж на вкладке не показывал «0»
    await loadLog()
    if (tab.value === 'queue') await loadQueue()
    if (tab.value === 'errors') await loadErrors()
  } catch (e: any) {
    loadErr.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

/** Смена вкладки — перезагружаем данные вкладки. */
watch(tab, () => {
  refreshAll()
})

async function togglePause() {
  toggling.value = true
  msg.value = ''
  try {
    const f = await feedbackReviewApi.pause(!isPaused.value)
    if (st.value) st.value.flags = { ...st.value.flags, ...f }
    msg.value = f.paused ? 'Разбор на паузе' : 'Разбор возобновлён'
  } catch (e: any) {
    loadErr.value = e?.response?.data?.detail || String(e)
  } finally {
    toggling.value = false
  }
}

async function onSaveSettings() {
  saving.value = true
  msg.value = ''
  try {
    await feedbackReviewApi.saveSettings({ auto: auto.value, batch: batch.value })
    await loadStatus()
    msg.value = 'Настройки сохранены'
  } catch (e: any) {
    loadErr.value = e?.response?.data?.detail || String(e)
  } finally {
    saving.value = false
  }
}

async function onRun() {
  running.value = true
  msg.value = ''
  try {
    const d = await feedbackReviewApi.run(batch.value || 20)
    msg.value = d.paused
      ? `Пауза ИИ (нет токенов) до ${fmtTime(d.pause_until)} — разбор пропущен`
      : d.started
        ? `Запущено в фоне: ${d.limit} отзывов. Прогресс — во вкладке «Лог работы»`
        : (d.reason || 'Запуск не удался')
    await refreshAll()
  } catch (e: any) {
    loadErr.value = e?.response?.data?.detail || String(e)
  } finally {
    running.value = false
  }
}

async function onRetryOne(e: any) {
  msg.value = ''
  try {
    await feedbackApi.reviewRetry(e.feedback_id)
    msg.value = 'Отзыв возвращён в очередь'
    await refreshAll()
  } catch (err: any) {
    loadErr.value = err?.response?.data?.detail || String(err)
  }
}

async function onRetryAll() {
  msg.value = ''
  try {
    const d = await feedbackReviewApi.retryAll()
    msg.value = `В очередь возвращено: ${d.count}`
    await refreshAll()
  } catch (e: any) {
    loadErr.value = e?.response?.data?.detail || String(e)
  }
}

async function openPrompt() {
  promptMsg.value = ''
  try {
    const d = await feedbackReviewApi.prompt()
    promptText.value = d.prompt || ''
    promptOpen.value = true
  } catch (e: any) {
    loadErr.value = e?.response?.data?.detail || String(e)
  }
}

async function onSavePrompt() {
  promptSaving.value = true
  promptMsg.value = ''
  try {
    await feedbackReviewApi.savePrompt(promptText.value)
    promptMsg.value = 'Промпт сохранён'
    promptMsgOk.value = true
    await loadStatus()
  } catch (e: any) {
    promptMsg.value = e?.response?.data?.detail || String(e)
    promptMsgOk.value = false
  } finally {
    promptSaving.value = false
  }
}

onMounted(() => {
  refreshAll()
  // разбор идёт в фоне минутами — подтягиваем статус и лог, чтобы видеть прогресс
  timer = setInterval(() => {
    loadStatus().catch(() => {})
    if (tab.value === 'log') loadLog().catch(() => {})
  }, 15000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>
