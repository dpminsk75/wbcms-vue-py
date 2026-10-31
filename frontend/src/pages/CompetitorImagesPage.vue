<script setup lang="ts">
import '@/assets/css/pages/page-competitor-images.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import KpiTile from '@/components/common/KpiTile.vue'
import Pager from '@/components/common/Pager.vue'
import WbSectionTabs from '@/components/common/WbSectionTabs.vue'
import {
  imagesApi,
  type ImagesHistoryRow,
  type ImagesList,
  type ImagesLogRow,
  type ImagesQueueRow,
  type ImagesSettings,
  type ImagesStatus,
} from '@/api/images'

/**
 * «Фото карточек (фон)» — рабочее место робота локального кэша фото WB.
 *
 * По образцу `/competitor/phrase-miner`: статус робота, журнал, очередь.
 * Здесь же — история смены фото у карточек и настройки (TTL уборки, интервал
 * тика, лимиты скачивания).
 *
 * Кэш фото **глобальный** (файлы общие для всех компаний), поэтому фильтра
 * по компании тут нет.
 */

const route = useRoute()
const router = useRouter()

const st = ref<ImagesStatus | null>(null)
const loading = ref(false)
const err = ref('')
const notice = ref('')

const tab = ref<string>('queue')

/* ---------------- очередь ---------------- */
const qState = ref('')
const qNm = ref('')
const qData = ref<ImagesList<ImagesQueueRow> | null>(null)
const qOffset = ref(0)
const qLimit = 50
const addNm = ref('')
const addBusy = ref(false)

/* ---------------- журнал ---------------- */
const lLevel = ref('')
const lData = ref<ImagesList<ImagesLogRow> | null>(null)
const lOffset = ref(0)
const lLimit = 50

/* ---------------- история ---------------- */
const hNm = ref('')
const hData = ref<ImagesList<ImagesHistoryRow> | null>(null)
const hOffset = ref(0)
const hLimit = 50

/* ---------------- настройки ---------------- */
const form = ref<ImagesSettings>({
  ttl_days: 180,
  interval_sec: 600,
  batch_limit: 150,
  sweep_limit: 200,
})
const formTouched = ref(false)
const saving = ref(false)

const STATE_OPTIONS = [
  { v: '', label: 'Все' },
  { v: 'pending', label: 'В очереди' },
  { v: 'ok', label: 'Скачано' },
  { v: 'error', label: 'Ошибки' },
  { v: 'gone', label: 'Нет на WB' },
]

const LEVEL_OPTIONS = [
  { v: '', label: 'Все' },
  { v: 'info', label: 'Инфо' },
  { v: 'warn', label: 'Предупреждения' },
  { v: 'error', label: 'Ошибки' },
]

const TABS = [
  { id: 'queue', label: 'Очередь' },
  { id: 'log', label: 'Лог работы' },
  { id: 'history', label: 'История фото' },
  { id: 'settings', label: 'Настройки' },
]

const tabs = computed(() =>
  TABS.map(t => ({
    ...t,
    // счётчики берём из статуса (он уже загружен) — отдельных запросов не нужно
    count: t.id === 'queue' ? (st.value?.counts?.pending || 0)
      : t.id === 'log' ? (st.value?.log_total || 0)
      : t.id === 'history' ? (st.value?.history_total || 0)
      : null,
  })),
)

/* ---------------- загрузка ---------------- */

async function loadStatus() {
  try {
    st.value = await imagesApi.status()
    if (!formTouched.value) form.value = { ...st.value.settings }
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function loadQueue() {
  try {
    qData.value = await imagesApi.queue({
      state: qState.value,
      nm_id: Number(qNm.value) || 0,
      limit: qLimit,
      offset: qOffset.value,
    })
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function loadLog() {
  try {
    lData.value = await imagesApi.log({
      level: lLevel.value,
      limit: lLimit,
      offset: lOffset.value,
    })
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function loadHistory() {
  try {
    hData.value = await imagesApi.history({
      nm_id: Number(hNm.value) || 0,
      limit: hLimit,
      offset: hOffset.value,
    })
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function loadSettings() {
  try {
    form.value = await imagesApi.settings()
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function refreshAll() {
  loading.value = true
  err.value = ''
  await loadStatus()
  if (tab.value === 'queue') await loadQueue()
  else if (tab.value === 'log') await loadLog()
  else if (tab.value === 'history') await loadHistory()
  else await loadSettings()
  loading.value = false
}

/** Загрузить данные вкладки. */
async function loadTab(next: string) {
  if (next === 'queue') await loadQueue()
  else if (next === 'log') await loadLog()
  else if (next === 'history') await loadHistory()
  else await loadSettings()
}

/* Вкладки переключает WbSectionTabs через v-model — значит следим за tab
   сами: иначе новая вкладка осталась бы пустой (данные не запрошены). */
watch(tab, (next) => {
  router.replace({ path: route.path, query: { tab: next } })
  loadTab(next)
})

/* ---------------- действия ---------------- */

async function togglePause() {
  try {
    const res = await imagesApi.pause(!st.value?.paused)
    notice.value = res.paused ? 'Робот на паузе' : 'Робот запущен'
    await loadStatus()
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function runNow() {
  try {
    const res = await imagesApi.run(50)
    notice.value = res.ok ? 'Порция отправлена на скачивание' : (res.error || 'не получилось')
    await loadStatus()
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function addToQueue() {
  const nm = Number(addNm.value)
  if (!nm) {
    notice.value = 'Укажите артикул WB'
    return
  }
  addBusy.value = true
  try {
    const res = await imagesApi.addToQueue(nm)
    notice.value = `Фото карточки ${res.nm_id} в очереди (${res.source})`
    addNm.value = ''
    await Promise.all([loadQueue(), loadStatus()])
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  } finally {
    addBusy.value = false
  }
}

async function requeue(id: number) {
  try {
    await imagesApi.requeue(id)
    await loadQueue()
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const res = await imagesApi.saveSettings({
      ttl_days: Number(form.value.ttl_days),
      interval_sec: Number(form.value.interval_sec),
      batch_limit: Number(form.value.batch_limit),
      sweep_limit: Number(form.value.sweep_limit),
    })
    form.value = { ...res.settings }
    notice.value = 'Настройки сохранены'
    await loadStatus()
  } catch (e: any) {
    err.value = e?.response?.data?.detail || e?.message || String(e)
  } finally {
    saving.value = false
  }
}

/* ---------------- форматирование ---------------- */

function fmtBytes(n: number | null | undefined): string {
  const v = Number(n || 0)
  if (!v) return '—'
  if (v < 1024) return `${v} Б`
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} КБ`
  return `${(v / 1024 / 1024).toFixed(1)} МБ`
}

function fmtTime(v: string | null | undefined): string {
  if (!v) return '—'
  const d = new Date(v)
  if (isNaN(d.getTime())) return String(v)
  return d.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function stateLabel(s: string): string {
  return ({ pending: 'в очереди', ok: 'скачано', error: 'ошибка', gone: 'нет на WB' } as Record<string, string>)[s] || s
}

function eventLabel(e: string): string {
  return ({ new: 'новое фото', replaced: 'фото сменилось', gone: 'фото исчезло', error: 'ошибка' } as Record<string, string>)[e] || e
}

function actionLabel(a: string): string {
  return ({
    collect: 'сбор', download: 'скачивание', sweep: 'обход', gc: 'уборка',
    manual: 'вручную', settings: 'настройки', error: 'ошибка',
  } as Record<string, string>)[a] || a
}

const qPages = computed(() => Math.max(1, Math.ceil((qData.value?.total || 0) / qLimit)))
const lPages = computed(() => Math.max(1, Math.ceil((lData.value?.total || 0) / lLimit)))
const hPages = computed(() => Math.max(1, Math.ceil((hData.value?.total || 0) / hLimit)))

onMounted(async () => {
  const t = String(route.query.tab || '')
  if (t && t !== tab.value) {
    tab.value = t          // -> сработает watch: загрузка вкладки + запись в URL
  } else {
    await loadTab(tab.value)
  }
  await loadStatus()
})
</script>

<template>
  <div class="container-xxl page-competitor-images">
    <div class="row mb-3 d-flex align-items-center">
      <div class="col">
        <h2 class="page-competitor-images__title">Фото карточек (фон)</h2>
        <div class="text-muted small">
          Робот кэширует фото WB локально: один размер 516×688, WebP. Файлы общие для всех компаний.
        </div>
      </div>
      <div class="col-auto d-flex gap-2 align-items-center">
        <span v-if="st?.paused" class="badge text-bg-warning">Пауза</span>
        <span v-else-if="st?.running" class="badge text-bg-success">Работает</span>
        <span v-else class="badge text-bg-secondary">Не запущен</span>
        <button class="btn btn-sm" :class="st?.paused ? 'btn-success' : 'btn-outline-warning'"
                :disabled="!st" @click="togglePause">
          <i class="bi me-1" :class="st?.paused ? 'bi-play-fill' : 'bi-pause-fill'"></i>
          {{ st?.paused ? 'Возобновить' : 'Пауза' }}
        </button>
        <button class="btn btn-sm btn-outline-primary" :disabled="loading" @click="runNow">
          <i class="bi bi-download me-1"></i> Скачать сейчас
        </button>
        <button class="btn btn-sm btn-light" @click="refreshAll" :disabled="loading">
          <i class="bi bi-arrow-clockwise me-1"></i> Обновить
        </button>
      </div>
    </div>

    <div v-if="err" class="alert alert-danger py-2">{{ err }}</div>
    <div v-if="notice" class="alert alert-info py-2">{{ notice }}</div>

    <!-- Статус -->
    <div class="grid-4 mb-3">
      <KpiTile label="Фаза" :value="st?.phase_label || '—'"
               variant="tile--3" :foot="st?.phase === 'watch' ? 'обход собранного — раз в неделю' : 'обходим базы'" />
      <KpiTile label="Скачано" :value="st?.counts?.ok ?? 0" variant="tile--1"
               :foot="`в очереди: ${st?.counts?.pending ?? 0} · ошибок: ${st?.counts?.error ?? 0}`" />
      <KpiTile label="Кэш на диске" :value="fmtBytes(st?.bytes)" variant="tile--1"
               :foot="`файлов: ${st?.files ?? 0}`" />
      <KpiTile label="Хранить фото" :value="`${st?.settings?.ttl_days ?? 180} дн.`" variant="tile--1"
               :foot="`последний тик: ${fmtTime(st?.last_tick)}`" />
    </div>

    <div v-if="st?.last_error" class="alert alert-danger py-2">
      <b>Последняя ошибка цикла:</b> {{ st.last_error }}
    </div>

    <WbSectionTabs v-model="tab" :tabs="tabs" class="mb-3" />

    <!-- ================= Очередь ================= -->
    <div v-show="tab === 'queue'">
      <div class="wb-panel mb-3">
        <div class="wb-panel__bd">
          <div class="row g-2 align-items-end">
            <div class="col-md-3">
              <label class="form-label small mb-1">Статус</label>
              <select v-model="qState" class="form-select form-select-sm" @change="qOffset = 0; loadQueue()">
                <option v-for="o in STATE_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
              </select>
            </div>
            <div class="col-md-3">
              <label class="form-label small mb-1">Артикул WB</label>
              <input v-model="qNm" class="form-control form-control-sm" inputmode="numeric"
                     placeholder="например 123456789" @keyup.enter="qOffset = 0; loadQueue()" />
            </div>
            <div class="col-md-3">
              <label class="form-label small mb-1">Поставить фото в очередь</label>
              <div class="d-flex gap-2">
                <input v-model="addNm" class="form-control form-control-sm" inputmode="numeric"
                       placeholder="артикул WB" @keyup.enter="addToQueue" />
                <button class="btn btn-sm btn-primary text-nowrap" :disabled="addBusy" @click="addToQueue">
                  В очередь
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="tbl-card">
        <div class="card__hd">
          Очередь фото
          <span class="hd-badge">{{ qData?.total ?? 0 }}</span>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">Артикул</th>
                <th class="t-left">Статус</th>
                <th class="t-left">Ссылка</th>
                <th>Размер</th>
                <th>Скачан</th>
                <th class="t-left">Ошибка</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in qData?.items || []" :key="r.id">
                <td class="t-left num">{{ r.nm_id ?? '—' }}</td>
                <td class="t-left">{{ stateLabel(r.state) }}</td>
                <td class="t-left page-competitor-images__url" :title="r.src_url">{{ r.src_url }}</td>
                <td class="num">{{ r.width ? `${r.width}×${r.height}` : '—' }}</td>
                <td class="num">{{ fmtTime(r.downloaded_at) }}</td>
                <td class="t-left small">{{ r.last_error || '' }}</td>
                <td>
                  <button v-if="r.state !== 'pending'" class="btn btn-sm btn-light"
                          title="Вернуть в очередь" @click="requeue(r.id)">
                    <i class="bi bi-arrow-repeat"></i>
                  </button>
                </td>
              </tr>
              <tr v-if="!qData?.items?.length">
                <td colspan="7" class="t-left text-muted">Очередь пуста</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <Pager :page="Math.floor(qOffset / qLimit) + 1" :total-pages="qPages" :total="qData?.total || 0"
             @change="p => { qOffset = (p - 1) * qLimit; loadQueue() }" />
    </div>

    <!-- ================= Лог ================= -->
    <div v-show="tab === 'log'">
      <div class="wb-panel mb-3">
        <div class="wb-panel__bd">
          <div class="row g-2 align-items-end">
            <div class="col-md-3">
              <label class="form-label small mb-1">Уровень</label>
              <select v-model="lLevel" class="form-select form-select-sm" @change="lOffset = 0; loadLog()">
                <option v-for="o in LEVEL_OPTIONS" :key="o.v" :value="o.v">{{ o.label }}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="tbl-card">
        <div class="card__hd">
          Журнал робота
          <span class="hd-badge">{{ lData?.total ?? 0 }}</span>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Время</th>
                <th class="t-left">Уровень</th>
                <th class="t-left">Событие</th>
                <th class="t-left">Сообщение</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in lData?.items || []" :key="r.id">
                <td class="num">{{ fmtTime(r.created_at) }}</td>
                <td class="t-left">{{ r.level }}</td>
                <td class="t-left">{{ actionLabel(r.action) }}</td>
                <td class="t-left">{{ r.message || '' }}</td>
              </tr>
              <tr v-if="!lData?.items?.length">
                <td colspan="4" class="t-left text-muted">Журнал пуст</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <Pager :page="Math.floor(lOffset / lLimit) + 1" :total-pages="lPages" :total="lData?.total || 0"
             @change="p => { lOffset = (p - 1) * lLimit; loadLog() }" />
    </div>

    <!-- ================= История фото ================= -->
    <div v-show="tab === 'history'">
      <div class="wb-panel mb-3">
        <div class="wb-panel__bd">
          <div class="row g-2 align-items-end">
            <div class="col-md-3">
              <label class="form-label small mb-1">Артикул WB</label>
              <input v-model="hNm" class="form-control form-control-sm" inputmode="numeric"
                     placeholder="например 123456789" @keyup.enter="hOffset = 0; loadHistory()" />
            </div>
          </div>
        </div>
      </div>

      <div class="tbl-card">
        <div class="card__hd">
          История смены фото
          <span class="hd-badge">{{ hData?.total ?? 0 }}</span>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Когда</th>
                <th class="t-left">Артикул</th>
                <th class="t-left">Событие</th>
                <th class="t-left">Было</th>
                <th class="t-left">Стало</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in hData?.items || []" :key="r.id">
                <td class="num">{{ fmtTime(r.changed_at) }}</td>
                <td class="t-left num">{{ r.nm_id ?? '—' }}</td>
                <td class="t-left">{{ eventLabel(r.event) }}</td>
                <td class="t-left page-competitor-images__url" :title="r.prev_src_url || ''">
                  {{ r.prev_src_url || '—' }}
                </td>
                <td class="t-left page-competitor-images__url" :title="r.src_url || ''">
                  {{ r.src_url || '—' }}
                </td>
              </tr>
              <tr v-if="!hData?.items?.length">
                <td colspan="5" class="t-left text-muted">Событий пока нет</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <Pager :page="Math.floor(hOffset / hLimit) + 1" :total-pages="hPages" :total="hData?.total || 0"
             @change="p => { hOffset = (p - 1) * hLimit; loadHistory() }" />
    </div>

    <!-- ================= Настройки ================= -->
    <div v-show="tab === 'settings'">
      <div class="wb-panel">
        <div class="wb-panel__bd">
          <div class="row g-3">
            <div class="col-md-6 col-lg-3">
              <label class="form-label small mb-1">Хранить фото, дней</label>
              <input v-model.number="form.ttl_days" type="number" min="1" max="3650"
                     class="form-control form-control-sm" @input="formTouched = true" />
              <div class="form-text small">
                Удаляется фото, которое дольше этого срока не встречается в источниках.
              </div>
            </div>
            <div class="col-md-6 col-lg-3">
              <label class="form-label small mb-1">Интервал тика, секунд</label>
              <input v-model.number="form.interval_sec" type="number" min="30" max="86400"
                     class="form-control form-control-sm" @input="formTouched = true" />
              <div class="form-text small">Как часто робот просыпается (600 = 10 минут).</div>
            </div>
            <div class="col-md-6 col-lg-3">
              <label class="form-label small mb-1">Скачиваний за тик</label>
              <input v-model.number="form.batch_limit" type="number" min="1" max="1000"
                     class="form-control form-control-sm" @input="formTouched = true" />
              <div class="form-text small">Сколько фото качать за один проход.</div>
            </div>
            <div class="col-md-6 col-lg-3">
              <label class="form-label small mb-1">Проверок за тик (обход)</label>
              <input v-model.number="form.sweep_limit" type="number" min="1" max="2000"
                     class="form-control form-control-sm" @input="formTouched = true" />
              <div class="form-text small">Сколько файлов проверяем в недельном обходе.</div>
            </div>
          </div>
          <div class="mt-3 d-flex gap-2">
            <button class="btn btn-sm btn-primary" :disabled="saving" @click="saveSettings">
              <i class="bi bi-check2 me-1"></i> Сохранить
            </button>
            <button class="btn btn-sm btn-light" :disabled="saving" @click="loadSettings">Сбросить</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
