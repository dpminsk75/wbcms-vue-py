<template>
  <div v-if="open" class="page-wb-detail__modal-backdrop" @click.self="$emit('close')">
    <div class="page-wb-detail__modal-box page-wb-detail__modal-box--wide comp-modal">
      <div class="page-wb-detail__modal-head">
        <h5 class="page-wb-detail__modal-title">
          <i class="bi bi-people"></i> Конкуренты
          <span class="page-wb-detail__modal-count">{{ items.length }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div class="page-wb-detail__add-row">
        <input
          v-model="addInput"
          class="form-control form-control-sm"
          placeholder="nmID конкурентов через запятую: 123456, 789012"
          :disabled="busy"
          @keyup.enter="addMany"
        />
        <button class="btn btn-sm btn-outline-primary" :disabled="busy || !addInput.trim()" @click="addMany">
          <i class="bi bi-plus-lg"></i> Добавить
        </button>
      </div>
      <div class="page-wb-detail__add-row">
        <input
          v-model="fromCard"
          class="form-control form-control-sm"
          placeholder="скопировать конкурентов с нашей карточки (nmID)"
          :disabled="busy"
          @keyup.enter="copyFrom"
        />
        <button class="btn btn-sm btn-outline-secondary" :disabled="busy || !fromCard.trim()" @click="copyFrom">
          <i class="bi bi-files"></i> Из карточки
        </button>
      </div>

      <div v-if="loading" class="text-muted small mt-2">
        <span class="spinner-border spinner-border-sm"></span> Загрузка...
      </div>
      <div v-if="error" class="text-danger small mt-2">{{ error }}</div>
      <div v-if="notice" class="text-success small mt-2">{{ notice }}</div>

      <div v-if="items.length" class="comp-table__filters">
        <button
          v-for="f in FILTERS"
          :key="f.key"
          class="btn btn-sm"
          :class="filters[f.key] ? 'btn-primary' : 'btn-outline-secondary'"
          @click="filters[f.key] = !filters[f.key]"
        >{{ f.label }}</button>
        <span class="comp-table__filters-note">
          {{ visibleItems.length }} из {{ items.length }}
        </span>
      </div>

      <div v-if="items.length" class="comp-table__wrap">
        <table class="wb-admin-table comp-table">
          <thead>
            <tr>
              <th>Конкурент</th>
              <th class="text-end comp-table__sortable" @click="sortBy('price')">
                Цена <i class="bi" :class="sortIcon('price')"></i>
              </th>
              <th
                class="text-center comp-table__sortable"
                title="В скольких полках WB он стоит и средняя позиция в них"
                @click="sortBy('shelves')"
              >
                Полки <i class="bi" :class="sortIcon('shelves')"></i>
              </th>
              <th
                class="text-center comp-table__sortable"
                title="Клипы, привязанные к этой карточке, и дата последнего"
                @click="sortBy('clips')"
              >
                Клипы <i class="bi" :class="sortIcon('clips')"></i>
              </th>
              <th
                class="text-center comp-table__sortable"
                title="В скольких наших фразах он в топ-10 и лучшая позиция"
                @click="sortBy('top10')"
              >
                Поиск <i class="bi" :class="sortIcon('top10')"></i>
              </th>
              <th
                class="text-center comp-table__sortable"
                title="Описание (символов) / характеристик"
                @click="sortBy('content')"
              >
                Контент <i class="bi" :class="sortIcon('content')"></i>
              </th>
              <th class="text-center">Статус</th>
              <th class="text-center"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in visibleItems" :key="c.nm_id">
              <td>
                <div class="comp-table__product">
                  <img v-if="c.photo" :src="c.photo" class="comp-table__photo" alt="" loading="lazy" />
                  <div v-else class="comp-table__photo comp-table__photo--empty"><i class="bi bi-image"></i></div>
                  <div class="comp-table__text">
                    <a
                      class="comp-table__title"
                      :href="wbCardUrl(c.nm_id)"
                      target="_blank"
                      rel="noopener"
                      :title="c.title || ''"
                    >{{ c.title || 'nmID ' + c.nm_id }}</a>
                    <div class="comp-table__sub">
                      <span class="comp-table__nm">{{ c.nm_id }}</span>
                      <span v-if="c.seller"> · {{ c.seller }}</span>
                      <span v-else-if="c.brand"> · {{ c.brand }}</span>
                      <span v-if="c.sources.includes('capture')" class="badge bg-secondary">собрано</span>
                      <span v-if="c.manual" class="badge bg-info text-dark">вручную</span>
                    </div>
                    <div v-if="c.badges && c.badges.length" class="comp-table__badges">
                      <span v-for="(b, i) in c.badges.slice(0, 2)" :key="i" class="badge bg-light text-dark">{{ b }}</span>
                    </div>
                  </div>
                </div>
              </td>
              <td class="text-end comp-table__price">
                <div class="comp-table__price-now">{{ c.price ? money(c.price) : '—' }}</div>
                <div v-if="c.old_price" class="comp-table__price-old">{{ money(c.old_price) }}</div>
                <div
                  v-if="c.price_delta_7d != null"
                  class="comp-table__delta"
                  :class="c.price_delta_7d < 0 ? 'text-danger' : 'text-success'"
                  title="Изменение цены за 7 дней"
                >{{ c.price_delta_7d < 0 ? '↓' : '↑' }}{{ Math.abs(c.price_delta_7d) }}%</div>
              </td>
              <td class="text-center">
                <template v-if="c.shelves_cnt">
                  <span class="comp-table__num">{{ c.shelves_cnt }}</span>
                  <span v-if="c.shelf_avg_pos != null" class="comp-table__muted"> · {{ c.shelf_avg_pos }}</span>
                  <div class="comp-table__hint">
                    {{ c.shelf_anchors_cnt || 0 }} якор. · лучшая {{ c.shelf_best_pos ?? '—' }}
                  </div>
                </template>
                <span v-else class="comp-table__muted">—</span>
              </td>
              <td class="text-center">
                <template v-if="c.clips_cnt">
                  <span class="comp-table__num">{{ c.clips_cnt }}</span>
                  <div class="comp-table__hint">{{ fmtShort(c.clips_last_at) }}</div>
                </template>
                <span v-else class="comp-table__muted">—</span>
              </td>
              <td class="text-center">
                <template v-if="c.phrases_cnt">
                  <span class="comp-table__num">топ-10: {{ c.top10_cnt || 0 }}</span>
                  <div class="comp-table__hint">
                    из {{ c.phrases_cnt }} · лучшая {{ c.best_pos ?? '—' }}
                  </div>
                </template>
                <span v-else class="comp-table__muted">—</span>
              </td>
              <td class="text-center">
                <span class="comp-table__num" :class="c.desc_len >= 50 ? '' : 'text-danger'">{{ c.desc_len }}</span>
                <span class="comp-table__muted"> / {{ c.chars_cnt }}</span>
              </td>
              <td class="text-center">
                <span v-if="c.analysis_status === 'analyzed'" class="badge bg-success">разобран</span>
                <span v-else-if="analyzing === c.nm_id" class="badge bg-warning text-dark">
                  <span class="spinner-border spinner-border-sm"></span>
                </span>
                <span v-else class="comp-table__muted">—</span>
                <div v-if="c.queue_status" class="comp-table__hint">{{ queueLabel(c.queue_status) }}</div>
              </td>
              <td class="text-center">
                <div class="comp-table__actions">
                  <button
                    class="btn btn-sm btn-outline-secondary"
                    title="Открыть досье конкурента"
                    @click="detailsNm = c.nm_id"
                  >
                    <i class="bi bi-eye"></i>
                  </button>
                  <button
                    v-if="c.analysis_status !== 'analyzed'"
                    class="btn btn-sm btn-outline-primary"
                    :disabled="!!analyzing"
                    title="Анализ описания"
                    @click="analyze(c.nm_id)"
                  >
                    <i class="bi bi-stars"></i>
                  </button>
                  <button
                    class="btn btn-sm btn-outline-danger"
                    :disabled="busy"
                    title="Отвязать конкурента от этой карточки (контент и история останутся в «Собранных карточках»)"
                    @click="askDetach(c.nm_id)"
                  >
                    <i class="bi bi-link-45deg"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="!loading" class="text-muted small mt-3">
        Пока нет конкурентов — добавь nmID или скопируй с другой карточки.
      </div>
      <div v-if="items.length && !visibleItems.length" class="text-muted small mt-2">
        Под фильтры ничего не подошло.
      </div>

      <Teleport to="body">
        <CompetitorDetailsModal
          :open="detailsNm !== null"
          :nm-id="detailsNm"
          :source-nm-id="nmId"
          @close="detailsNm = null"
        />
      </Teleport>

      <div class="page-wb-detail__modal-foot">
        <button class="btn btn-sm btn-outline-warning" :disabled="busy || !items.length" @click="makeSummary">
          <i class="bi bi-magic"></i> Сводка title + description
        </button>
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>

      <div v-if="summary" class="page-wb-detail__summary">
        <div class="page-wb-detail__summary-title">{{ summary.title || '—' }}</div>
        <div class="page-wb-detail__summary-desc">{{ summary.description }}</div>
        <div class="page-wb-detail__modal-footnote">
          конкурентов: {{ summary.competitor_count || 0 }}
          <span v-if="summary.model"> · модель: {{ summary.model }}</span>
          <span v-if="summary.created_at"> · {{ summary.created_at }}</span>
        </div>
      </div>

      <!-- Подтверждение отвязки (свой диалог: нативный confirm() ставит лишние клики в очередь) -->
      <WbConfirmDialog
        :open="pendingDetach !== null"
        :text="`Отвязать конкурента nm ${pendingDetach ?? ''} от карточки ${nmId ?? ''}?`"
        hint="Описание и история останутся в «Собранных карточках» — конкурент не пропадёт совсем."
        confirm-text="Отвязать"
        danger
        :busy="busy"
        @confirm="doDetach"
        @cancel="pendingDetach = null"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api } from '@/api/client'
import { aiJobsApi } from '@/api/aiJobs'
import { competitorsNewcardApi, type CompetitorRow } from '@/api/competitorsNewcard'
import WbConfirmDialog from '../common/WbConfirmDialog.vue'
import CompetitorDetailsModal from './CompetitorDetailsModal.vue'

const props = defineProps<{ open: boolean; nmId: number | string | null | undefined }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'changed'): void }>()

const items = ref<CompetitorRow[]>([])
const addInput = ref('')
const fromCard = ref('')
const busy = ref(false)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const analyzing = ref<number | null>(null)
const pendingDetach = ref<number | null>(null)
const summary = ref<any>(null)

// §13.1: поведенческие колонки — сортировка и фильтры.
type SortKey = 'price' | 'shelves' | 'clips' | 'top10' | 'content'
const detailsNm = ref<number | null>(null)
const sortKey = ref<SortKey | 'default'>('default')
const sortDir = ref<-1 | 1>(-1)
const filters = reactive({ clips: false, shelves: false, pricedrop: false, nocontent: false })
const FILTERS: Array<{ key: keyof typeof filters; label: string }> = [
  { key: 'clips', label: 'с клипами' },
  { key: 'shelves', label: 'в полках' },
  { key: 'pricedrop', label: 'снизил цену' },
  { key: 'nocontent', label: 'без контента' },
]

const QUEUE_LABELS: Record<string, string> = {
  pending: 'в очереди',
  processing: 'собираем',
  done: 'собрано',
  error: 'ошибка',
}

const nm = () => Number(props.nmId || 0)

function queueLabel(s?: string | null): string {
  return s ? (QUEUE_LABELS[s] || s) : ''
}

function wbCardUrl(n: number): string {
  return `https://www.wildberries.ru/catalog/${n}/detail.aspx`
}

function money(v?: string | number | null): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = typeof v === 'number' ? v : Number(String(v).replace(/[^\d.-]/g, ''))
  if (Number.isFinite(n) && n > 0) return `${n.toLocaleString('ru-RU')} ₽`
  return String(v)
}

function fmtShort(v?: string | null): string {
  if (!v) return ''
  const d = new Date(v)
  return isFinite(d.getTime())
    ? d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
    : ''
}

function sortBy(key: SortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === -1 ? 1 : -1
  } else {
    sortKey.value = key
    sortDir.value = key === 'price' ? 1 : -1
  }
}

function sortIcon(key: SortKey): string {
  if (sortKey.value !== key) return 'bi-arrow-down-up text-muted'
  return sortDir.value === -1 ? 'bi-sort-down' : 'bi-sort-up'
}

function sortValue(c: CompetitorRow): number {
  switch (sortKey.value) {
    case 'price': return Number(String(c.price ?? '').replace(/[^\d.-]/g, '')) || Number.MAX_SAFE_INTEGER
    case 'shelves': return c.shelves_cnt || 0
    case 'clips': return c.clips_cnt || 0
    case 'top10': return c.top10_cnt || 0
    case 'content': return c.desc_len || 0
    default: return 0
  }
}

const visibleItems = computed(() => {
  const list = items.value.filter((c) => {
    if (filters.clips && !c.clips_cnt) return false
    if (filters.shelves && !c.shelves_cnt) return false
    if (filters.pricedrop && !(c.price_delta_7d != null && c.price_delta_7d < 0)) return false
    if (filters.nocontent && (c.desc_len || 0) >= 50) return false
    return true
  })
  if (sortKey.value === 'default') return list
  return [...list].sort((a, b) => (sortValue(a) - sortValue(b)) * sortDir.value)
})

async function load() {
  const id = nm()
  if (!id) return
  loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.competitors(id)
    items.value = d.items || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось загрузить конкурентов'
    items.value = []
  } finally {
    loading.value = false
  }
}

function parseIds(raw: string): number[] {
  return String(raw)
    .split(/[^0-9]+/)
    .map((x) => Number(x))
    .filter((n) => Number.isFinite(n) && n > 0)
}

async function addMany() {
  const id = nm()
  const ids = parseIds(addInput.value)
  if (!id || !ids.length || busy.value) {
    if (!ids.length) error.value = 'Нужен хотя бы один nmID'
    return
  }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const r = await competitorsNewcardApi.addCompetitors(id, ids)
    notice.value = `Добавлено: ${r.added} из ${r.requested}. Сбор запустится из попапа расширения.`
    addInput.value = ''
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось добавить конкурентов'
  } finally {
    busy.value = false
  }
}

async function copyFrom() {
  const id = nm()
  const src = Number(fromCard.value || 0)
  if (!id || !src || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const r = await competitorsNewcardApi.fromCard(id, src)
    notice.value = `Скопировано: ${r.added} конкурентов с карточки ${r.source_nm_id}.`
    fromCard.value = ''
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось скопировать'
  } finally {
    busy.value = false
  }
}

async function analyze(competitorNm: number) {
  const id = nm()
  if (!id || analyzing.value) return
  analyzing.value = competitorNm
  error.value = ''
  try {
    const { data } = await api.post('/api/competitors/analyze-direct', {
      source_nm_id: id,
      competitor_nm_id: competitorNm,
    })
    await pollJob(Number(data.job_id))
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось запустить анализ'
  } finally {
    analyzing.value = null
  }
}

/** Отвязать конкурента от нашей карточки: удаляем все строки пары. */
function askDetach(competitorNm: number) {
  if (busy.value || pendingDetach.value !== null) return
  pendingDetach.value = competitorNm
}

async function doDetach() {
  const competitorNm = pendingDetach.value
  if (competitorNm === null || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await competitorsNewcardApi.detachCompetitor(nm(), competitorNm)
    // убираем строку локально — без перезагрузки списка (и без прыжка скролла)
    const i = items.value.findIndex((x) => x.nm_id === competitorNm)
    if (i >= 0) items.value.splice(i, 1)
    pendingDetach.value = null
    notice.value = `Конкурент nm ${competitorNm} отвязан.`
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось отвязать конкурента'
  } finally {
    busy.value = false
  }
}

async function pollJob(jobId: number) {
  const finished = new Set(['done', 'error', 'interrupted'])
  for (let i = 0; i < 300; i++) {
    await new Promise((r) => setTimeout(r, 2000))
    try {
      const j = await aiJobsApi.get(jobId)
      if (finished.has(j.status)) {
        if (j.status !== 'done') error.value = j.error || 'Анализ завершился с ошибкой'
        return
      }
    } catch {
      return
    }
  }
  error.value = 'Анализ идёт дольше 10 минут — проверьте позже'
}

async function makeSummary() {
  const id = nm()
  if (!id || busy.value) return
  busy.value = true
  error.value = ''
  try {
    // force=false: пересчёт кэша 30д — только админ (не трогаем, §2 п.8 плана)
    const { data } = await api.post(`/api/competitors/${id}/summary`, {})
    if (data && data.success === false) {
      error.value = data.error || 'Сводка недоступна'
      summary.value = null
      return
    }
    const res = (data && data.result) || {}
    summary.value = data
      ? {
          title: res.title || '',
          description: res.description || '',
          competitor_count: data.competitor_count,
          model: data.cached_model,
          created_at: data.cached_at,
        }
      : null
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось получить сводку'
  } finally {
    busy.value = false
  }
}

watch(
  () => [props.open, props.nmId] as const,
  ([isOpen]) => {
    if (!isOpen) {
      detailsNm.value = null
      return
    }
    addInput.value = ''
    fromCard.value = ''
    notice.value = ''
    error.value = ''
    pendingDetach.value = null
    summary.value = null
    detailsNm.value = null
    load()
  },
)
</script>

<style scoped>
.comp-modal { max-width: 1120px; }
.comp-table__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 8px 0;
}
.comp-table__filters-note { margin-left: auto; font-size: 12px; color: #6b7280; }
.comp-table__wrap { overflow-x: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
.comp-table { width: 100%; min-width: 980px; margin: 0; font-size: 13px; }
.comp-table th { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #6b7280; white-space: nowrap; }
.comp-table td, .comp-table th { padding: 6px 8px; vertical-align: middle; }
.comp-table__sortable { cursor: pointer; user-select: none; }
.comp-table__sortable:hover { color: #0d6efd; }
.comp-table__product { display: flex; align-items: center; gap: 8px; min-width: 240px; }
.comp-table__photo {
  width: 40px; height: 52px; object-fit: contain; border-radius: 4px;
  background: #f8f9fa; border: 1px solid #eef0f2; flex: 0 0 40px;
}
.comp-table__photo--empty { display: flex; align-items: center; justify-content: center; color: #adb5bd; }
.comp-table__text { min-width: 0; }
.comp-table__title {
  display: block; max-width: 320px; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; color: #1f2937; text-decoration: none; font-weight: 500;
}
.comp-table__title:hover { color: #0d6efd; text-decoration: underline; }
.comp-table__sub { font-size: 11px; color: #6b7280; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.comp-table__nm { font-family: monospace; color: #0d6efd; }
.comp-table__badges { display: flex; gap: 3px; margin-top: 3px; }
.comp-table__badges .badge { font-size: 9px; font-weight: 500; }
.comp-table__price-now { font-weight: 600; white-space: nowrap; }
.comp-table__price-old { font-size: 11px; color: #9ca3af; text-decoration: line-through; }
.comp-table__delta { font-size: 11px; font-weight: 600; }
.comp-table__num { font-weight: 600; }
.comp-table__muted { color: #9ca3af; }
.comp-table__hint { font-size: 10px; color: #9ca3af; white-space: nowrap; }
.comp-table__actions { display: flex; gap: 4px; justify-content: flex-end; }
</style>
