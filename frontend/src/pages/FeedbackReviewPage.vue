<template>
  <div class="container-xxl page-feedback-review">
    <FeedbackHead :title="$route.meta.title || 'Разбор отзывов (фон)'" active="review" />

    <div class="row mb-3 d-flex align-items-center">
      <div class="col-auto d-flex gap-2 align-items-center">
        <span v-if="st?.flags?.paused" class="badge text-bg-warning">Пауза</span>
        <span v-else-if="st?.flags?.running" class="badge text-bg-success">Работает</span>
        <span v-else class="badge text-bg-secondary">Не запущен</span>
        <button class="btn btn-sm" :class="st?.flags?.paused ? 'btn-success' : 'btn-outline-warning'"
                :disabled="!st || toggling" @click="togglePause">
          <i class="bi me-1" :class="st?.flags?.paused ? 'bi-play-fill' : 'bi-pause-fill'"></i>
          {{ st?.flags?.paused ? 'Возобновить' : 'Пауза' }}
        </button>
        <button class="btn btn-sm btn-light" @click="refreshAll" :disabled="loading">
          <i class="bi bi-arrow-clockwise me-1"></i> Обновить
        </button>
      </div>
    </div>

    <div v-if="loadErr" class="alert alert-danger py-2">{{ loadErr }}</div>
    <div v-if="msg" class="alert alert-info py-2">{{ msg }}</div>

    <!-- Статус -->
    <div class="card mb-3">
      <div class="card-header"><i class="bi bi-activity me-1"></i> Статус</div>
      <div class="card-body">
        <div class="row g-3 page-feedback-review__status">
          <div class="col-12 col-md-6 col-xl-3">
            <div class="page-feedback-review__k">Очередь</div>
            <div class="mb-1">
              <b>{{ st?.counts?.queue_count || 0 }}</b> неразобранных отзывов
              <span class="text-muted small">(за 30 дней)</span>
            </div>
            <div class="mb-1">ждут повторного разбора: <b>{{ st?.counts?.pending || 0 }}</b></div>
            <div>готово: <b>{{ st?.counts?.done || 0 }}</b> · ошибок: <b>{{ st?.counts?.error || 0 }}</b></div>
          </div>

          <div class="col-12 col-md-6 col-xl-3">
            <div class="page-feedback-review__k">Настройки</div>
            <div class="form-check form-switch mb-2">
              <input id="fr-auto" v-model="auto" class="form-check-input" type="checkbox" />
              <label class="form-check-label" for="fr-auto">Авторазбор в фоне</label>
            </div>
            <div class="d-flex align-items-center gap-2">
              <label class="small text-muted text-nowrap" for="fr-batch">Отзывов за прогон</label>
              <input id="fr-batch" v-model.number="batch" type="number" min="1" max="500"
                     class="form-control form-control-sm" style="width:72px" />
              <button class="btn btn-sm btn-outline-secondary" :disabled="saving" @click="onSaveSettings">
                Сохранить
              </button>
            </div>
          </div>

          <div class="col-12 col-md-6 col-xl-3">
            <div class="page-feedback-review__k">Промпт</div>
            <div class="mb-2">
              <span v-if="st?.prompt_set" class="text-success">задан</span>
              <span v-else class="text-danger">не задан — разбор не пойдёт</span>
            </div>
            <button class="btn btn-sm btn-outline-secondary" @click="openPrompt">
              {{ st?.prompt_set ? 'Изменить' : 'Задать' }}
            </button>
          </div>

          <div class="col-12 col-md-6 col-xl-3">
            <div class="page-feedback-review__k">Разобрать сейчас</div>
            <button class="btn btn-sm btn-primary mb-2" :disabled="running || !st?.prompt_set" @click="onRun">
              <span v-if="running" class="spinner-border spinner-border-sm me-1"></span>
              {{ running ? 'Разбираем...' : 'Разобрать порцию' }}
            </button>
            <div class="page-feedback-review__hint">Фоновый цикл: каждые {{ st?.flags?.interval_sec || 60 }} с</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Вкладки -->
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'queue' }" @click="switchTab('queue')">
          Очередь
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'errors' }" @click="switchTab('errors')">
          Ошибки <span class="badge bg-light text-dark">{{ st?.counts?.error || 0 }}</span>
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'log' }" @click="switchTab('log')">
          Лог работы <span class="badge bg-light text-dark">{{ logTotal }}</span>
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'cost' }" @click="switchTab('cost')">
          Затраты ИИ
        </button>
      </li>
    </ul>

    <!-- ===== Очередь ===== -->
    <div v-show="tab === 'queue'">
      <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span><i class="bi bi-list-ol me-1"></i> Неразобранные отзывы</span>
          <button class="btn btn-sm btn-light" @click="loadQueue">Обновить</button>
        </div>
        <div class="card-body p-0">
          <div v-if="!queue.length" class="text-center text-muted p-4">Очередь пуста</div>
          <table v-else class="table table-sm table-striped mb-0">
            <thead>
              <tr><th>Дата</th><th>nmID</th><th>★</th><th>Отзыв</th></tr>
            </thead>
            <tbody>
              <tr v-for="it in queue" :key="it.id">
                <td class="text-nowrap small">{{ it.created_at }}</td>
                <td class="small">{{ it.nm_id }}</td>
                <td class="text-center small">{{ it.rating }}</td>
                <td class="small">{{ (it.text || '').slice(0, 200) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ===== Ошибки ===== -->
    <div v-show="tab === 'errors'">
      <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span><i class="bi bi-exclamation-triangle me-1"></i> Ошибки разбора</span>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-secondary" @click="onRetryAll"
                    :disabled="!(st?.counts?.error || 0)">
              Вернуть все в очередь
            </button>
            <button class="btn btn-sm btn-light" @click="loadErrors">Обновить</button>
          </div>
        </div>
        <div class="card-body p-0">
          <div v-if="!errors.length" class="text-center text-muted p-4">Ошибок нет</div>
          <table v-else class="table table-sm table-striped mb-0">
            <thead>
              <tr><th>Дата</th><th>Товар</th><th>Отзыв</th><th>Ошибка</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="e in errors" :key="e.feedback_id">
                <td class="text-nowrap small">{{ e.created_at }}</td>
                <td class="small">{{ e.product_title || e.nm_id }}</td>
                <td class="small">{{ (e.text || '').slice(0, 120) }}</td>
                <td class="small text-danger" :title="e.error || ''">
                  {{ (e.error || '').slice(0, 80) }}
                </td>
                <td class="text-end">
                  <button class="btn btn-sm btn-outline-secondary" @click="onRetryOne(e)">
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
      <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span><i class="bi bi-journal-text me-1"></i> Лог работы</span>
          <div class="d-flex gap-2 align-items-center">
            <select v-model="logLevel" class="form-select form-select-sm w-auto" @change="logOffset = 0; loadLog()">
              <option value="">Все уровни</option>
              <option value="info">info</option>
              <option value="warn">warn</option>
              <option value="error">error</option>
            </select>
            <button class="btn btn-sm btn-light" @click="loadLog">Обновить</button>
          </div>
        </div>
        <div class="card-body p-0">
          <div v-if="logErr" class="alert alert-warning py-2 mb-0 rounded-0 border-0">{{ logErr }}</div>
          <div v-if="!logItems.length" class="text-center text-muted p-4">Журнал пуст</div>
          <table v-else class="table table-sm table-striped mb-0">
            <thead>
              <tr><th>Время</th><th>Уровень</th><th>Событие</th><th>Сообщение</th></tr>
            </thead>
            <tbody>
              <tr v-for="l in logItems" :key="l.id">
                <td class="text-nowrap small">{{ l.created_at }}</td>
                <td class="small" :class="l.level === 'error' ? 'text-danger' : ''">{{ l.level }}</td>
                <td class="small">{{ l.action }}</td>
                <td class="small">{{ l.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ===== Затраты ИИ ===== -->
    <div v-show="tab === 'cost'">
      <div class="card">
        <div class="card-header"><i class="bi bi-cash-coin me-1"></i> Затраты ИИ (сценарий feedback_review)</div>
        <div class="card-body">
          <div class="row g-3 mb-3">
            <div class="col-md-3" v-for="p in costPeriods" :key="p.key">
              <div class="page-feedback-review__k">{{ p.label }}</div>
              <div>вызовов: <b>{{ p.block.calls || 0 }}</b></div>
              <div class="small text-muted">токенов: {{ p.block.total_tokens || 0 }}</div>
              <div v-if="st?.can_see_cost" class="small">$ {{ p.block.cost || 0 }}</div>
            </div>
          </div>
          <div v-if="(st?.ai_usage?.by_model || []).length">
            <div class="page-feedback-review__k mb-1">По моделям</div>
            <table class="table table-sm table-striped mb-0">
              <thead>
                <tr><th>Модель</th><th>Вызовов</th><th>Токенов</th><th v-if="st?.can_see_cost">$</th></tr>
              </thead>
              <tbody>
                <tr v-for="m in st?.ai_usage?.by_model || []" :key="m.grp">
                  <td class="small">{{ m.grp }}</td>
                  <td class="small">{{ m.calls || 0 }}</td>
                  <td class="small">{{ m.total_tokens || 0 }}</td>
                  <td v-if="st?.can_see_cost" class="small">{{ m.cost || 0 }}</td>
                </tr>
              </tbody>
            </table>
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
            <h5 class="modal-title">Промпт разбора отзыва</h5>
            <button type="button" class="btn-close" @click="promptOpen = false"></button>
          </div>
          <div class="modal-body">
            <p class="text-muted small">
              Промпт применяется к каждому отзыву отдельно. Модель — «Модель (сводка)».
              Формат ответа: JSON с полями emotion, constructiveness, tone.
            </p>
            <textarea v-model="promptText" class="form-control font-monospace" rows="18"></textarea>
          </div>
          <div class="modal-footer py-2">
            <span v-if="promptMsg" class="me-auto small" :class="promptMsgOk ? 'text-success' : 'text-danger'">
              {{ promptMsg }}
            </span>
            <button class="btn btn-light" @click="promptOpen = false">Закрыть</button>
            <button class="btn btn-primary" :disabled="promptSaving" @click="onSavePrompt">
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
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { feedbackApi } from '@/api/feedback'
import {
  feedbackReviewApi,
  type ReviewLogItem,
  type ReviewQueueItem,
  type ReviewStatusFull,
} from '@/api/feedbackReview'
import FeedbackHead from '@/components/feedback/FeedbackHead.vue'

const route = useRoute()

const st = ref<ReviewStatusFull | null>(null)
const queue = ref<ReviewQueueItem[]>([])
const errors = ref<any[]>([])
const logItems = ref<ReviewLogItem[]>([])
const logTotal = ref(0)
const logErr = ref('')
const logLevel = ref('')
const tab = ref<'queue' | 'errors' | 'log' | 'cost'>('queue')
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

const costPeriods = computed(() => {
  const u = st.value?.ai_usage
  return [
    { key: 'today', label: 'Сегодня', block: u?.today || { calls: 0, total_tokens: 0, cost: 0 } },
    { key: 'week', label: '7 дней', block: u?.week || { calls: 0, total_tokens: 0, cost: 0 } },
    { key: 'month', label: '30 дней', block: u?.month || { calls: 0, total_tokens: 0, cost: 0 } },
  ]
})

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

function switchTab(t: string) {
  tab.value = t as any
  refreshAll()
}

async function togglePause() {
  toggling.value = true
  msg.value = ''
  try {
    const f = await feedbackReviewApi.pause(!st.value?.flags?.paused)
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
    msg.value = d.fatal
      ? `Остановлено: ${d.fatal}`
      : `Взято ${d.taken}, разобрано ${d.ok}, ошибок ${d.errors}`
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

onMounted(refreshAll)
</script>
