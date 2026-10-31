<template>
  <div class="container-xxl page-pminer">
    <div class="row mb-3 d-flex align-items-center">
      <div class="col">
        <h2 class="page-pminer__title">Разбор фраз (фон)</h2>
      </div>
      <div class="col-auto d-flex gap-2 align-items-center">
        <span v-if="st?.paused" class="badge text-bg-warning">Пауза</span>
        <span v-else-if="st?.balance?.paused" class="badge text-bg-warning">Пауза ИИ</span>
        <span v-else-if="st?.running" class="badge text-bg-success">Работает</span>
        <span v-else class="badge text-bg-secondary">Не запущен</span>
        <button class="btn btn-sm" :class="isPaused ? 'btn-success' : 'btn-outline-warning'"
                :disabled="!st || toggling" @click="togglePause">
          <i class="bi me-1" :class="isPaused ? 'bi-play-fill' : 'bi-pause-fill'"></i>
          {{ isPaused ? 'Возобновить' : 'Пауза' }}
        </button>
        <button class="btn btn-sm btn-light" @click="refreshAll" :disabled="loading">
          <i class="bi bi-arrow-clockwise me-1"></i> Обновить
        </button>
      </div>
    </div>

    <div v-if="loadErr" class="alert alert-danger py-2">{{ loadErr }}</div>

    <div v-if="st?.balance?.paused" class="alert alert-warning py-2 d-flex align-items-center gap-2 flex-wrap">
      <i class="bi bi-pause-circle"></i>
      <span>
        У ИИ-провайдера кончились токены
        ({{ st?.balance?.reason || 'insufficient_balance' }}) —
        разбор на паузе до {{ fmtTime(st?.balance?.until) }}
        <span class="text-muted">(осталось {{ fmtLeft(st?.balance?.left_sec) }})</span>
        <span v-if="(st?.balance?.companies || []).length > 1" class="text-muted">
          · компаний на паузе: {{ st?.balance?.companies?.length }}</span>
      </span>
      <button class="btn btn-sm btn-outline-dark ms-auto" :disabled="toggling" @click="togglePause">
        Возобновить сейчас
      </button>
    </div>

    <!-- Полоса статуса: видна всегда, вне вкладок -->
    <div class="card mb-3">
      <div class="card-header"><i class="bi bi-activity me-1"></i> Статус</div>
      <div class="card-body page-pminer__status">
        <div>
          <div class="page-pminer__k">Сейчас обрабатывается</div>
          <div v-if="st?.current">
            <a href="#" class="fw-bold" @click.prevent="openCompetitor(st.current.competitor_nm_id, st.current.source_nm_id, st.current.company_id)">
              {{ st.current.competitor_nm_id }}
            </a>
            <span class="text-muted"> — конкурент, компания #{{ st.current.company_id }},
              наша карточка {{ st.current.source_nm_id || '—' }}</span>
          </div>
          <div v-else class="text-muted">{{ st?.paused ? 'пауза' : 'простаивает (очередь пуста)' }}</div>
        </div>
        <div>
          <div class="page-pminer__k">Очередь</div>
          <div>
            ждут: <b>{{ st?.queue?.counts?.pending || 0 }}</b>
            <span class="text-muted">
              (из мониторинга: {{ st?.queue?.pending_by_priority?.['1'] || 0 }},
              общий: {{ st?.queue?.pending_by_priority?.['2'] || 0 }})
            </span>
          </div>
          <div>готово: {{ st?.queue?.counts?.done || 0 }} · ошибок: {{ st?.queue?.counts?.error || 0 }}</div>
          <div v-if="st?.quota?.ok" class="mt-1 small">
            Лимит ИИ: <b>{{ st?.quota?.percent }}%</b>
            <span class="text-muted">· сброс в {{ fmtClock(st?.quota?.reset_at) }}
              <template v-if="st?.quota?.reset_left">· осталось {{ st?.quota?.reset_left }}</template>
            </span>
          </div>
          <div v-else-if="st?.quota?.applicable && !st?.quota?.ok" class="mt-1 small text-muted">
            Лимит ИИ: не удалось проверить ({{ st?.quota?.error || 'нет данных' }})
          </div>
          <div v-if="st?.quota?.weekly_percent !== null && st?.quota?.weekly_percent !== undefined && st?.quota?.weekly_percent < 10"
               class="small text-warning-emphasis">
            Недельный лимит: {{ st?.quota?.weekly_percent }}%
          </div>
        </div>
        <div>
          <div class="page-pminer__k">Последняя ошибка цикла</div>
          <div v-if="st?.last_error" class="page-pminer__err">{{ st.last_error.msg }}</div>
          <div v-else class="text-muted">—</div>
        </div>
      </div>
    </div>

    <!-- Фильтр компании (глобальный админ) -->
    <div v-if="st?.is_global" class="row g-2 mb-2">
      <div class="col-md-4">
        <select v-model="companyFilter" class="form-select form-select-sm" @change="onCompanyFilter">
          <option :value="''">Все компании</option>
          <option v-for="c in auth.companies" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </div>
    </div>

    <!-- Вкладки -->
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'queue' }" @click="switchTab('queue')">
          Очередь <span class="badge bg-light text-dark">{{ queueTotal }}</span>
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
      <div class="card mb-3">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span><i class="bi bi-list-ol me-1"></i> Очередь работ</span>
          <select v-model="qFilter" class="form-select form-select-sm w-auto" @change="qOffset = 0; loadQueue()">
            <option value="">Все статусы</option>
            <option value="pending">Ожидают</option>
            <option value="processing">В работе</option>
            <option value="done">Готово</option>
            <option value="error">Ошибки</option>
          </select>
        </div>
        <div class="card-body p-0" v-if="q && q.rows.length">
          <div class="table-responsive wb-table-wrap">
            <table class="table table-bordered table-hover table-sm mb-0 page-pminer__table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Конкурент</th>
                  <th>Наша карточка</th>
                  <th>Компания</th>
                  <th>Приоритет</th>
                  <th>Статус</th>
                  <th class="page-pminer__num">Фраз</th>
                  <th>Модель</th>
                  <th class="page-pminer__num">Попытки</th>
                  <th>Ошибка</th>
                  <th>Готово</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in q.rows" :key="r.id">
                  <td>{{ r.id }}</td>
                  <td>
                    <a href="#" @click.prevent="openCompetitor(r.competitor_nm_id, r.source_nm_id, r.company_id)">
                      {{ r.competitor_nm_id }}
                    </a>
                  </td>
                  <td><a :href="`/wb/detail?nm_id=${r.source_nm_id}`" target="_blank" rel="noopener">{{ r.source_nm_id }}</a></td>
                  <td>#{{ r.company_id }}</td>
                  <td>{{ r.priority === 1 ? 'мониторинг' : 'общий' }}</td>
                  <td><span class="badge" :class="statusBadge(r.status)">{{ statusTitle(r.status) }}</span></td>
                  <td class="page-pminer__num">{{ r.phrases_cnt ?? '—' }}</td>
                  <td class="page-pminer__small">{{ r.model || '—' }}</td>
                  <td class="page-pminer__num">{{ r.attempts }}</td>
                  <td class="page-pminer__small page-pminer__err" :title="r.last_error || ''">{{ shortErr(r.last_error) }}</td>
                  <td class="page-pminer__small">{{ r.processed_at || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-else class="card-body text-muted">
          Очередь пуста (или фильтр ничего не дал)
          <span v-if="st && (st.queue?.counts?.done || 0)"> · готово всего: {{ st.queue.counts.done }}</span>
        </div>
        <div v-if="q && q.total > qLimit" class="card-footer d-flex gap-2 align-items-center">
          <button class="btn btn-sm btn-light" :disabled="qOffset === 0" @click="qOffset = Math.max(0, qOffset - qLimit); loadQueue()">
            <i class="bi bi-chevron-left"></i>
          </button>
          <span class="small text-muted">{{ qOffset + 1 }}–{{ Math.min(qOffset + qLimit, q.total) }} из {{ q.total }}</span>
          <button class="btn btn-sm btn-light" :disabled="qOffset + qLimit >= q.total" @click="qOffset += qLimit; loadQueue()">
            <i class="bi bi-chevron-right"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- ===== Лог работы ===== -->
    <div v-show="tab === 'log'">
      <div class="card mb-3">
        <div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
          <span><i class="bi bi-clock-history me-1"></i> Лог работы</span>
          <div class="d-flex gap-2">
            <select v-model="logLevel" class="form-select form-select-sm w-auto" @change="logOffset = 0; loadLog()">
              <option value="">Все уровни</option>
              <option value="info">info</option>
              <option value="warn">warn</option>
              <option value="error">error</option>
            </select>
            <select v-model="logAction" class="form-select form-select-sm w-auto" @change="logOffset = 0; loadLog()">
              <option value="">Все события</option>
              <option value="refill">пополнение</option>
              <option value="start">взяли</option>
              <option value="done">готово</option>
              <option value="error">ошибка</option>
              <option value="skip">пропуск</option>
              <option value="rest">отдых</option>
              <option value="manual">ручной разбор</option>
              <option value="balance-pause">нет токенов</option>
            </select>
          </div>
        </div>
        <div class="card-body p-0" v-if="log && log.rows.length">
          <div class="table-responsive wb-table-wrap">
            <table class="table table-bordered table-hover table-sm mb-0 page-pminer__table">
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Событие</th>
                  <th>Уровень</th>
                  <th>Конкурент</th>
                  <th>Наша карточка</th>
                  <th>Компания</th>
                  <th>Приоритет</th>
                  <th class="page-pminer__num">Фраз</th>
                  <th>Модель</th>
                  <th class="page-pminer__num">Время вызова</th>
                  <th>Сообщение</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="l in log.rows" :key="l.id">
                  <td class="page-pminer__small">{{ l.ts }}</td>
                  <td><span class="badge" :class="actionBadge(l.action)">{{ actionTitle(l.action) }}</span></td>
                  <td><span class="badge" :class="logBadge(l.level)">{{ l.level }}</span></td>
                  <td>
                    <a v-if="l.competitor_nm_id" href="#" @click.prevent="openCompetitor(l.competitor_nm_id, l.source_nm_id, l.company_id)">
                      {{ l.competitor_nm_id }}
                    </a>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>
                    <a v-if="l.source_nm_id" :href="`/wb/detail?nm_id=${l.source_nm_id}`" target="_blank" rel="noopener">
                      {{ l.source_nm_id }}
                    </a>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td>{{ l.company_id ? '#' + l.company_id : '—' }}</td>
                  <td>{{ l.priority === 1 ? 'мониторинг' : (l.priority === 2 ? 'общий' : '—') }}</td>
                  <td class="page-pminer__num">{{ l.phrases_cnt ?? '—' }}</td>
                  <td class="page-pminer__small">{{ l.model || '—' }}</td>
                  <td class="page-pminer__num page-pminer__small">{{ l.ms ? (l.ms / 1000).toFixed(1) + ' с' : '—' }}</td>
                  <td class="page-pminer__small">{{ l.msg }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-else class="card-body text-muted">
          {{ log?.error || 'Журнал пуст (или фильтр ничего не дал)' }}
        </div>
        <div v-if="log && log.total > logLimit" class="card-footer d-flex gap-2 align-items-center">
          <button class="btn btn-sm btn-light" :disabled="logOffset === 0" @click="logOffset = Math.max(0, logOffset - logLimit); loadLog()">
            <i class="bi bi-chevron-left"></i>
          </button>
          <span class="small text-muted">{{ logOffset + 1 }}–{{ Math.min(logOffset + logLimit, log.total) }} из {{ log.total }}</span>
          <button class="btn btn-sm btn-light" :disabled="logOffset + logLimit >= log.total" @click="logOffset += logLimit; loadLog()">
            <i class="bi bi-chevron-right"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- ===== Затраты ИИ ===== -->
    <div v-show="tab === 'cost'">
      <div class="card mb-3">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span><i class="bi bi-cash-coin me-1"></i> Затраты ИИ — сценарий «Фразы (фон-разбор)»</span>
          <router-link class="btn btn-sm btn-light" to="/seo/ai-usage">
            Открыть журнал <i class="bi bi-box-arrow-up-right"></i>
          </router-link>
        </div>
        <div class="card-body" v-if="st">
          <div class="table-responsive wb-table-wrap">
            <table class="table table-bordered table-sm mb-0 page-pminer__table">
              <thead>
                <tr>
                  <th>Период</th>
                  <th class="page-pminer__num">Вызовы</th>
                  <th class="page-pminer__num">Токены (вход)</th>
                  <th class="page-pminer__num">Токены (выход)</th>
                  <th class="page-pminer__num">Всего токенов</th>
                  <th class="page-pminer__num">Ошибки</th>
                  <th v-if="st.can_see_cost" class="page-pminer__num">$</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, key) in costRows" :key="key">
                  <td>{{ costTitles[key as 'today' | 'week' | 'month'] }}</td>
                  <td class="page-pminer__num">{{ (row?.calls || 0).toLocaleString('ru-RU') }}</td>
                  <td class="page-pminer__num">{{ (row?.prompt_tokens || 0).toLocaleString('ru-RU') }}</td>
                  <td class="page-pminer__num">{{ (row?.completion_tokens || 0).toLocaleString('ru-RU') }}</td>
                  <td class="page-pminer__num">{{ (row?.total_tokens || 0).toLocaleString('ru-RU') }}</td>
                  <td class="page-pminer__num">{{ row?.failed || 0 }}</td>
                  <td v-if="st.can_see_cost" class="page-pminer__num">{{ fmtCost(row?.cost) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="st.ai_usage?.by_model?.length" class="mt-3">
            <div class="page-pminer__k mb-1">По моделям (30 дней)</div>
            <div class="table-responsive wb-table-wrap">
              <table class="table table-bordered table-sm mb-0 page-pminer__table">
                <thead>
                  <tr>
                    <th>Модель</th>
                    <th class="page-pminer__num">Вызовы</th>
                    <th class="page-pminer__num">Токены</th>
                    <th class="page-pminer__num">Ошибки</th>
                    <th v-if="st.can_see_cost" class="page-pminer__num">$</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in st.ai_usage.by_model" :key="String(r.grp)">
                    <td>{{ r.grp || '—' }}</td>
                    <td class="page-pminer__num">{{ (r.calls || 0).toLocaleString('ru-RU') }}</td>
                    <td class="page-pminer__num">{{ (r.total_tokens || 0).toLocaleString('ru-RU') }}</td>
                    <td class="page-pminer__num">{{ r.failed || 0 }}</td>
                    <td v-if="st.can_see_cost" class="page-pminer__num">{{ fmtCost(r.cost) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="text-muted small mt-2">Вызовов ИИ за период не было</div>
        </div>
      </div>
    </div>

    <!-- Досье конкурента -->
    <CompetitorDetailsModal
      :open="compNm !== null"
      :nm-id="compNm"
      :source-nm-id="compOur"
      @close="compNm = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '../stores/auth'
import CompetitorDetailsModal from '../components/competitors/CompetitorDetailsModal.vue'
import { phraseMinerApi, type MinerStatus, type MinerQueueResp, type MinerLogResp } from '../api/phraseMiner'

const auth = useAuthStore()

const st = ref<MinerStatus | null>(null)
const q = ref<MinerQueueResp | null>(null)
const log = ref<MinerLogResp | null>(null)
const loadErr = ref('')
const loading = ref(false)
const toggling = ref(false)

const tab = ref<'queue' | 'log' | 'cost'>('queue')
const companyFilter = ref<string>('')

const qFilter = ref('')
const qLimit = 50
const qOffset = ref(0)

const logLevel = ref('')
const logAction = ref('')
const logLimit = 50
const logOffset = ref(0)

const compNm = ref<number | null>(null)
const compOur = ref<number | null>(null)

const costTitles = { today: 'Сегодня', week: '7 дней', month: '30 дней' } as const
const costRows = computed(() => st.value?.ai_usage ?? null)

/** Итоги для бейджей вкладок — всегда из status (без учёта фильтров таблиц). */
const queueTotal = computed(() => Object.values(st.value?.queue?.counts || {})
  .reduce((a, b) => a + (Number(b) || 0), 0))
const logTotal = computed(() => st.value?.log_counts?.total ?? 0)

/** Пауза активна: ручная или по отсутствию токенов у провайдера. */
const isPaused = computed(() => !!st.value?.paused || !!st.value?.balance?.paused)

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

let timer: ReturnType<typeof setInterval> | null = null

/** company_id для запросов: глобальный админ — свой фильтр, остальные — null
 *  (бэкенд сам принудительно берёт компанию селектора). */
function scopeParam(): number | null {
  if (!st.value?.is_global) return null
  return companyFilter.value ? Number(companyFilter.value) : null
}

async function loadStatus() {
  st.value = await phraseMinerApi.status(scopeParam())
}

async function loadQueue() {
  q.value = await phraseMinerApi.queue({
    status: qFilter.value || undefined,
    company_id: scopeParam(),
    limit: qLimit,
    offset: qOffset.value,
  })
}

async function loadLog() {
  log.value = await phraseMinerApi.log({
    level: logLevel.value || undefined,
    action: logAction.value || undefined,
    company_id: scopeParam(),
    limit: logLimit,
    offset: logOffset.value,
  })
}

/** Обновляем активную вкладку + статус (вкладки независимы по пагинации/фильтрам). */
async function refresh() {
  if (loading.value) return
  loading.value = true
  loadErr.value = ''
  try {
    await loadStatus()
    if (tab.value === 'queue') await loadQueue()
    else if (tab.value === 'log') await loadLog()
  } catch (e: any) {
    const detail = String(e?.response?.data?.detail || '')
    loadErr.value = detail.includes('company_id is required')
      ? 'Выберите компанию в верхней панели — иначе не видно данных воркера.'
      : (detail || String(e?.message || e))
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await refresh()
  // обе таблицы — чтобы переключение вкладки не показывало пустоту
  try {
    if (tab.value !== 'queue') await loadQueue()
    if (tab.value !== 'log') await loadLog()
  } catch { /* не критично */ }
}

function switchTab(t: 'queue' | 'log' | 'cost') {
  tab.value = t
  if (t === 'queue') loadQueue().catch(() => {})
  if (t === 'log') loadLog().catch(() => {})
}

async function onCompanyFilter() {
  qOffset.value = 0
  logOffset.value = 0
  await refreshAll()
}

async function togglePause() {
  if (!st.value || toggling.value) return
  toggling.value = true
  try {
    await phraseMinerApi.pause(!isPaused.value, scopeParam())
    await loadStatus()
  } finally {
    toggling.value = false
  }
}

/** Открыть досье конкурента. Эндпоинты модалки company-scoped: если в селекторе
 *  стоит другая компания — переключаем селектор на компанию строки. */
function openCompetitor(nm: number | null | undefined, our: number | null | undefined, company: number | null | undefined) {
  if (!nm) return
  const sel = auth.companyId
  if (sel !== 'all' && company && Number(sel) !== Number(company)) {
    auth.setCompany(company)
  }
  compNm.value = Number(nm)
  compOur.value = our ? Number(our) : null
}

function statusTitle(s: string): string {
  return ({ pending: 'ждёт', processing: 'в работе', done: 'готово', error: 'ошибка' } as Record<string, string>)[s] || s
}
function statusBadge(s: string): string {
  return ({ pending: 'text-bg-secondary', processing: 'text-bg-primary', done: 'text-bg-success', error: 'text-bg-danger' } as Record<string, string>)[s] || 'text-bg-secondary'
}
function logBadge(lvl: string): string {
  return ({ info: 'text-bg-light', warn: 'text-bg-warning', error: 'text-bg-danger' } as Record<string, string>)[lvl] || 'text-bg-light'
}
function actionTitle(a?: string | null): string {
  return ({
    refill: 'пополнение', start: 'взяли', done: 'готово', error: 'ошибка',
    skip: 'пропуск', rest: 'отдых', manual: 'ручной разбор',
  } as Record<string, string>)[String(a || '')] || (a || '—')
}
function actionBadge(a?: string | null): string {
  return ({
    refill: 'text-bg-secondary', start: 'text-bg-primary', done: 'text-bg-success',
    error: 'text-bg-danger', skip: 'text-bg-warning', rest: 'text-bg-light',
    manual: 'text-bg-info',
  } as Record<string, string>)[String(a || '')] || 'text-bg-light'
}
function shortErr(e?: string | null): string {
  if (!e) return '—'
  return e.length > 80 ? e.slice(0, 80) + '…' : e
}
function fmtCost(v: number | null | undefined): string {
  const n = Number(v || 0)
  if (!n) return '0'
  return n < 0.01 ? n.toFixed(6) : n.toFixed(4)
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 3000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.page-pminer__title { font-size: 1.4rem; margin: 0; }
.page-pminer__status { display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 1rem; }
.page-pminer__k { font-size: .8rem; text-transform: uppercase; letter-spacing: .03em; color: #6c757d; margin-bottom: .25rem; }
.page-pminer__num { text-align: right; white-space: nowrap; }
.page-pminer__small { font-size: .82rem; }
.page-pminer__err { color: #b02a37; }
.page-pminer__table { font-size: .88rem; }
</style>
