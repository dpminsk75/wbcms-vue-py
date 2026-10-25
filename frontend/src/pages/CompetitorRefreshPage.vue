<template>
  <div class="container-xxl page-competitor page-refresh">
    <WbWorkspaceHead title="Конкуренты: Обновление" :subtabs="COMPETITOR_SUB_TABS" workspace-active="competitors" />
    <p class="text-muted">
      Конкуренты, контент которых собирали давно. Назначьте обновление — расширение
      обойдёт карточки в режиме «Обновление старых» и обновит описание, характеристики,
      цену и рекомендации.
    </p>

    <div class="page-pick__toolbar page-refresh__toolbar">
      <input
        v-model="q"
        class="form-control form-control-sm page-refresh__search"
        placeholder="Название, бренд, продавец, nmID"
        @keyup.enter="load()"
      />
      <button class="btn btn-sm btn-primary" :disabled="loading" @click="load()">
        <i class="bi bi-search"></i> Найти
      </button>
      <select v-model.number="days" class="form-select form-select-sm page-refresh__days" @change="load()">
        <option :value="7">старше 7 дней</option>
        <option :value="14">старше 14 дней</option>
        <option :value="30">старше 30 дней</option>
        <option :value="60">старше 60 дней</option>
        <option :value="90">старше 90 дней</option>
      </select>
      <select v-model.number="sourceNmId" class="form-select form-select-sm page-refresh__source" @change="load()">
        <option :value="0">Все наши карточки</option>
        <option v-for="c in sourceOptions" :key="c.nmID" :value="c.nmID">
          {{ c.nmID }} · {{ c.title || c.vendor_code || 'без названия' }}
        </option>
      </select>
      <label class="page-pick__check">
        <input v-model="onlyCaptured" type="checkbox" @change="load()" />
        только собранные
      </label>
      <label class="page-pick__check">
        <input v-model="includeHidden" type="checkbox" @change="load()" />
        показать скрытые
      </label>
      <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="reset">Сброс</button>
      <button class="btn btn-sm btn-outline-secondary" :disabled="loading || !selectableRows.length" @click="toggleSelectAll">
        {{ allSelected ? 'Снять выбор' : 'Выбрать все' }}
      </button>
      <span class="badge bg-secondary">Найдено: {{ total }}</span>
    </div>

    <div class="page-refresh__tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="page-refresh__tab"
        :class="{ 'is-active': statusFilter === tab.key }"
        @click="setStatus(tab.key)"
      >
        {{ tab.label }}
        <span class="page-refresh__tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="notice" class="page-pick__notice">{{ notice }}</div>

    <div v-if="loading" class="text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка…
    </div>
    <div v-else-if="!rows.length" class="alert alert-info">
      <template v-if="statusFilter !== 'all'">В этом статусе ничего нет.</template>
      <template v-else>Нет конкурентов старше {{ days }} дней. Уменьшите порог или измените фильтры.</template>
    </div>

    <table v-else class="wb-admin-table page-refresh__grid">
      <thead>
        <tr>
          <th class="page-pick__col-check">
            <input
              type="checkbox"
              :checked="allSelected"
              :disabled="!selectableRows.length"
              title="Выбрать все доступные для обновления"
              @change="toggleSelectAll"
            />
          </th>
          <th class="page-refresh__col-product">Конкурент</th>
          <th class="page-refresh__col-date">Собрано</th>
          <th class="page-refresh__col-attach">Привязан к</th>
          <th class="page-refresh__col-status">Статус</th>
          <th class="page-refresh__col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="r in rows"
          :key="r.nm_id"
          :class="{
            'page-pick__row--picked': isSelected(r.nm_id),
            'page-pick__row--disabled': !canAssign(r),
          }"
        >
          <td class="text-center">
            <input
              type="checkbox"
              :checked="isSelected(r.nm_id)"
              :disabled="!canAssign(r)"
              :title="canAssign(r) ? '' : 'Уже назначено или обновляется'"
              @change="toggleSelect(r)"
            />
          </td>
          <td>
            <div class="page-competitor__product">
              <img :src="r.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb" loading="lazy" />
              <div class="page-competitor__product-text">
                <div class="page-competitor__product-title" :title="r.title || ''">{{ r.title || '—' }}</div>
                <div class="page-competitor__product-sub">
                  <a
                    :href="`https://www.wildberries.ru/catalog/${r.nm_id}/detail.aspx`"
                    target="_blank"
                    rel="noopener"
                    class="page-competitor__wb-link"
                  >WB: {{ r.nm_id }}</a>
                  <span v-if="r.brand"> · {{ r.brand }}</span>
                  <span v-if="r.seller && r.seller !== r.brand"> · {{ r.seller }}</span>
                </div>
                <div class="page-refresh__badges">
                  <span v-if="r.captured" class="badge bg-success">собран</span>
                  <span v-else class="badge bg-light text-dark">только привязан</span>
                  <span v-if="r.is_hidden" class="badge bg-secondary">скрыт</span>
                </div>
              </div>
            </div>
          </td>
          <td class="page-refresh__date">
            <div class="page-refresh__days">{{ r.days_old }} дн.</div>
            <div class="page-refresh__date-full" :title="fmtFull(r.collected_at)">{{ fmtAgo(r.collected_at) }}</div>
          </td>
          <td class="page-refresh__attach">
            <template v-if="r.attached_to?.length">
              <a
                v-for="a in r.attached_to.slice(0, 4)"
                :key="a.nm_id"
                :href="`/wb/detail?nm_id=${a.nm_id}`"
                target="_blank"
                rel="noopener"
                class="badge bg-primary page-pick__attach-tag"
                :title="a.title || ''"
              >{{ a.nm_id }}</a>
              <span v-if="r.attached_to.length > 4" class="page-pick__muted">+{{ r.attached_to.length - 4 }}</span>
            </template>
            <span v-else class="text-muted small">не привязан</span>
          </td>
          <td>
            <span
              class="badge"
              :class="statusClass(r)"
              :title="statusTitle(r)"
            >{{ statusLabel(r) }}</span>
          </td>
          <td class="page-refresh__actions">
            <button
              v-if="canAssign(r)"
              class="btn btn-sm btn-primary"
              :disabled="assigning"
              @click="assignOne(r)"
            >{{ r.ui_status === 'error' ? 'Повторить' : 'Назначить' }}</button>
            <button
              v-if="r.ui_status === 'gone'"
              class="btn btn-sm btn-outline-success"
              :disabled="assigning"
              title="Проверил на WB: карточка есть — снять блокировку «нет на WB»"
              @click="restoreOne(r)"
            >Появилась</button>
            <button class="btn btn-sm btn-outline-secondary" @click="openDetails(r)">Открыть</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="!loading && total > rows.length" class="page-refresh__more">
      Показано {{ rows.length }} из {{ total }}. Сузьте фильтр, чтобы увидеть остальные.
    </div>

    <div v-if="selected.length" class="page-pick__bar page-refresh__bar">
      <div class="page-pick__bar-info">
        Выбрано: <b>{{ selected.length }}</b>
        <div class="page-pick__preview">Порог: старше {{ days }} дней</div>
      </div>
      <div class="page-pick__bar-actions">
        <button class="btn btn-sm btn-primary" :disabled="assigning" @click="assignSelected">
          <span v-if="assigning" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-arrow-repeat"></i>
          Назначить обновление ({{ selected.length }})
        </button>
        <button class="btn btn-sm btn-outline-secondary" :disabled="assigning" @click="clearSelected">Снять выбор</button>
      </div>
    </div>

    <CompetitorDetailsModal
      :open="detailsOpen"
      :nm-id="active?.nm_id"
      scope="pick"
      @close="detailsOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  competitorsNewcardApi,
  type PickCard,
  type RefreshAssignResult,
  type RefreshRow,
  type RefreshStatus,
} from '../api/competitorsNewcard'
import CompetitorDetailsModal from '../components/competitors/CompetitorDetailsModal.vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { COMPETITOR_SUB_TABS } from '@/components/common/workspaceTabs'
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-pick.css'
import '@/assets/css/pages/page-competitor-refresh.css'

const rows = ref<RefreshRow[]>([])
const total = ref(0)
const counts = ref<Record<RefreshStatus, number>>({
  stale: 0, assigned: 0, queued: 0, processing: 0, error: 0, gone: 0,
})
const days = ref(30)
const q = ref('')
const onlyCaptured = ref(false)
const includeHidden = ref(false)
const sourceNmId = ref(0)
const sourceOptions = ref<PickCard[]>([])
const statusFilter = ref<'all' | RefreshStatus>('all')
const loading = ref(false)
const assigning = ref(false)
const error = ref('')
const notice = ref('')
const selected = ref<number[]>([])
const detailsOpen = ref(false)
const active = ref<RefreshRow | null>(null)

const allCount = computed(() => Object.values(counts.value).reduce((sum, n) => sum + n, 0))

const tabs = computed(() => [
  { key: 'all' as const, label: 'Все', count: allCount.value },
  { key: 'stale' as const, label: 'Пора обновить', count: counts.value.stale },
  { key: 'assigned' as const, label: 'Назначено', count: counts.value.assigned },
  { key: 'queued' as const, label: 'В очереди', count: counts.value.queued },
  { key: 'processing' as const, label: 'Обновляется', count: counts.value.processing },
  { key: 'error' as const, label: 'Ошибка', count: counts.value.error },
  { key: 'gone' as const, label: 'Нет на WB', count: counts.value.gone },
])

const selectableRows = computed(() => rows.value.filter(canAssign))
const allSelected = computed(() =>
  selectableRows.value.length > 0 && selectableRows.value.every((r) => isSelected(r.nm_id)),
)

function canAssign(r: RefreshRow): boolean {
  return !r.is_hidden && (r.ui_status === 'stale' || r.ui_status === 'error')
}

function isSelected(nm: number): boolean {
  return selected.value.includes(nm)
}

function toggleSelect(r: RefreshRow) {
  if (!canAssign(r)) return
  const i = selected.value.indexOf(r.nm_id)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(r.nm_id)
}

function toggleSelectAll() {
  if (allSelected.value) {
    selected.value = []
    return
  }
  selected.value = selectableRows.value.map((r) => r.nm_id)
}

function setStatus(key: 'all' | RefreshStatus) {
  if (statusFilter.value === key) return
  statusFilter.value = key
  selected.value = []
  load()
}

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.refreshList({
      days: days.value,
      q: q.value.trim(),
      only_captured: onlyCaptured.value,
      include_hidden: includeHidden.value,
      source_nm_id: sourceNmId.value || undefined,
      status: statusFilter.value === 'all' ? '' : statusFilter.value,
      limit: 300,
      offset: 0,
    })
    rows.value = d.items || []
    total.value = d.total || 0
    counts.value = d.counts || counts.value
    const allowed = new Set(rows.value.filter(canAssign).map((r) => r.nm_id))
    selected.value = selected.value.filter((id) => allowed.has(id))
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось загрузить устаревшие карточки'
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function loadSources() {
  try {
    const d = await competitorsNewcardApi.pickCards('', 200)
    sourceOptions.value = d.items || []
  } catch {
    sourceOptions.value = []
  }
}

async function doAssign(ids: number[]) {
  if (!ids.length || assigning.value) return
  assigning.value = true
  error.value = ''
  notice.value = ''
  try {
    const res: RefreshAssignResult = await competitorsNewcardApi.refreshAssign(ids, days.value)
    const parts: string[] = []
    if (res.assigned) parts.push(`назначено: ${res.assigned}`)
    if (res.already) parts.push(`уже было: ${res.already}`)
    if (res.in_progress) parts.push(`в работе: ${res.in_progress}`)
    if (res.skipped) parts.push(`пропущено: ${res.skipped}`)
    notice.value = parts.length ? parts.join(', ') : 'Нечего назначать'
    selected.value = selected.value.filter((id) => !ids.includes(id))
    await load(true)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось назначить обновление'
  } finally {
    assigning.value = false
  }
}

function assignOne(r: RefreshRow) {
  doAssign([r.nm_id])
}

async function restoreOne(r: RefreshRow) {
  if (assigning.value) return
  assigning.value = true
  error.value = ''
  notice.value = ''
  try {
    const res = await competitorsNewcardApi.refreshRestore([r.nm_id])
    notice.value = res.restored ? 'Разблокировано — можно назначить обновление' : 'Статус не изменён'
    await load(true)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось разблокировать карточку'
  } finally {
    assigning.value = false
  }
}

function assignSelected() {
  doAssign([...selected.value])
}

function clearSelected() {
  selected.value = []
}

function reset() {
  q.value = ''
  days.value = 30
  onlyCaptured.value = false
  includeHidden.value = false
  sourceNmId.value = 0
  statusFilter.value = 'all'
  selected.value = []
  notice.value = ''
  load()
}

function openDetails(r: RefreshRow) {
  active.value = r
  detailsOpen.value = true
}

function statusLabel(r: RefreshRow): string {
  if (r.ui_status === 'assigned') return 'назначено'
  if (r.ui_status === 'queued') return 'в очереди'
  if (r.ui_status === 'processing') return 'обновляется'
  if (r.ui_status === 'error') return 'ошибка'
  if (r.ui_status === 'gone') return 'нет на WB'
  return 'пора обновить'
}

function statusClass(r: RefreshRow): string {
  if (r.ui_status === 'assigned') return 'bg-primary'
  if (r.ui_status === 'queued') return 'bg-warning text-dark'
  if (r.ui_status === 'processing') return 'bg-info text-dark'
  if (r.ui_status === 'error') return 'bg-danger'
  if (r.ui_status === 'gone') return 'bg-dark'
  return 'bg-secondary'
}

function statusTitle(r: RefreshRow): string {
  if (r.ui_status === 'error') return r.queue_error || 'ошибка сбора'
  if (r.ui_status === 'gone') {
    const when = r.queue_not_found_at ? fmtFull(r.queue_not_found_at) : ''
    return `WB отдала «ничего не найдено»${when ? ` ${when}` : ''} · обновление заблокировано`
  }
  if (r.requested_at) return `назначено: ${fmtFull(r.requested_at)}`
  if (r.queue_processed_at) return `обработано: ${fmtFull(r.queue_processed_at)}`
  return ''
}

function fmtAgo(v?: string | null): string {
  if (!v) return '—'
  const t = new Date(v).getTime()
  if (!isFinite(t)) return String(v)
  const m = Math.round((Date.now() - t) / 60000)
  if (m < 60) return `${Math.max(1, m)} мин назад`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} ч назад`
  const d = Math.round(h / 24)
  if (d < 30) return `${d} дн назад`
  return new Date(v).toLocaleDateString('ru-RU')
}

function fmtFull(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

onMounted(() => {
  load()
  loadSources()
})
</script>
