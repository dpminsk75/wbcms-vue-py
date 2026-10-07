<template>
  <div class="container-xxl page-admin-timers">
    <h2 class="page-admin-timers__title">Таймеры воркеров</h2>
    <p class="text-muted">systemd вместо крона: статус, вкл/выкл, разовый старт, смена OnCalendar, хвост journalctl. Только admin.</p>

    <div v-if="error" class="wb-error">{{ error }}</div>

    <div v-if="loading" class="text-muted">Загрузка…</div>
    <div v-else-if="!rows.length" class="alert alert-info">Таймеров нет — systemd недоступен или юниты не стоят (<code>deploy/*.timer</code>).</div>
    <div v-else class="wb-table-wrap">
      <table class="table table-sm align-middle page-admin-timers__grid">
        <thead>
          <tr>
            <th>Таймер</th>
            <th>Расписание</th>
            <th class="text-center">Вкл</th>
            <th>Состояние</th>
            <th>След. запуск</th>
            <th>Прошлый запуск</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id" :class="{ 'page-admin-timers__row--off': !r.enabled }">
            <td>
              <div>{{ r.title }}</div>
              <code class="page-admin-timers__id">{{ r.id }}</code>
              <div v-if="r.load_state && r.load_state !== 'loaded'" class="mt-1">
                <span class="badge text-bg-warning" title="Юнит не стоит в /etc/systemd/system — скопируй deploy/*.service+timer и сделай daemon-reload">нет юнита</span>
              </div>
            </td>
            <td>
              <code>{{ (r.on_calendar || []).join(' / ') || '—' }}</code>
              <div class="page-admin-timers__sched">
                <input v-model="schedEdits[r.id]" :placeholder="r.default" title="OnCalendar, напр. 04:00 или *:00,30"
                  class="form-control form-control-sm page-admin-timers__sched-input" />
                <button @click="onSched(r)" :disabled="busy[r.id]" class="btn btn-sm btn-outline-secondary" title="Сохранить расписание">✓</button>
                <button @click="onSchedReset(r)" :disabled="busy[r.id]" class="btn btn-sm btn-link" title="Вернуть дефолт">дефолт</button>
              </div>
            </td>
            <td class="text-center">
              <input type="checkbox" :checked="r.enabled" @change="onToggle(r, ($event.target as HTMLInputElement).checked)"
                class="form-check-input" :title="r.enabled ? 'Выключить' : 'Включить'" />
            </td>
            <td class="text-center text-nowrap">
              <span :class="r.active_state === 'active' ? 'badge text-bg-success' : 'badge text-bg-secondary'">{{ r.active_state || '—' }}</span>
              <div class="text-muted small">{{ r.sub_state || '' }}</div>
            </td>
            <td class="small text-nowrap" :title="r.next || ''">{{ fmtNext(r.next) }}</td>
            <td class="small text-nowrap" :title="lastTitle(r)">
              <span v-if="!r.svc_last_start" class="text-muted">—</span>
              <template v-else>
                {{ fmtNext(r.svc_last_start) }}
                <span v-if="r.svc_exec_status == null || String(r.svc_exec_status) === '0'" class="badge text-bg-success" title="exit 0">✓</span>
                <span v-else class="badge text-bg-danger" :title="`exit ${r.svc_exec_status}`">✗ {{ r.svc_exec_status }}</span>
              </template>
            </td>
            <td>
              <div class="page-admin-timers__actions">
                <button @click="onRun(r)" :disabled="busy[r.id]" class="btn btn-sm btn-outline-primary" title="Запустить .service разово сейчас">
                  <i class="bi bi-play-fill"></i>
                </button>
                <button @click="onLog(r)" class="btn btn-sm btn-outline-secondary" title="Хвост journalctl">
                  <i class="bi bi-journal-text"></i>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="logFor" class="card page-admin-timers__log">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span>Лог <code>{{ logFor }}</code> (последние 100)</span>
        <button @click="logFor = ''; logLines = []" class="btn btn-sm btn-link">закрыть</button>
      </div>
      <pre class="card-body page-admin-timers__log-body">{{ logLines.join('\n') || 'пусто' }}</pre>
    </div>
    <div class="text-muted small mt-2">Примеры OnCalendar: <code>04:00</code>, <code>*:00,30</code>, <code>00,03,06,09,12,15,18,21:05</code>, <code>daily</code>. Проверка — <code>systemd-analyze calendar</code> на бэке до записи.</div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-admin-timers.css'
import { ref, reactive, onMounted } from 'vue'
import { adminTimersApi, type AdminTimerRow } from '../api/adminTimers'

const rows = ref<AdminTimerRow[]>([])
const loading = ref(false)
const error = ref('')
const busy = reactive<Record<string, boolean>>({})
const schedEdits = reactive<Record<string, string>>({})
const logFor = ref('')
const logLines = ref<string[]>([])

function fmtNext(v: string | null | undefined): string {
  if (!v || v === 'n/a') return '—'
  if (/^\d+\s*y/.test(v)) return 'по интервалу'  // монотонный таймер (healthcheck)
  const m = /(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/.exec(v)
  if (m) return `${m[3]}.${m[2]} ${m[4]}`
  return v
}
function lastTitle(r: any): string {
  return [r.svc_last_start, r.svc_result ? `result=${r.svc_result}` : ''].filter(Boolean).join(' ')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await adminTimersApi.list()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

async function onToggle(r: AdminTimerRow, on: boolean) {
  error.value = ''
  busy[r.id] = true
  try {
    if (on) await adminTimersApi.enable(r.id)
    else await adminTimersApi.disable(r.id)
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    busy[r.id] = false
  }
}

async function onRun(r: AdminTimerRow) {
  error.value = ''
  busy[r.id] = true
  try {
    await adminTimersApi.run(r.id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    busy[r.id] = false
  }
}

async function onSched(r: AdminTimerRow, preset?: string) {
  const v = preset ?? schedEdits[r.id] ?? ''
  if (!v.trim()) { error.value = 'Пусто: укажите OnCalendar или нажмите «дефолт»'; return }
  error.value = ''
  busy[r.id] = true
  try {
    await adminTimersApi.schedule(r.id, v.trim())
    schedEdits[r.id] = ''
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    busy[r.id] = false
  }
}

function onSchedReset(r: AdminTimerRow) {
  schedEdits[r.id] = r.default
  onSched(r, r.default)
}

async function onLog(r: AdminTimerRow) {
  error.value = ''
  try {
    const out = await adminTimersApi.log(r.id, 100)
    logFor.value = r.service
    logLines.value = out.lines || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

onMounted(load)
</script>
