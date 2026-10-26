<template>
  <div class="container-xxl page-competitor page-captured">
    <div class="wb-workspace-head">
      <h2 class="page-competitor__title">Собранные карточки</h2>
      <WbWorkspaceTabs active="captured" :tabs="WORKSPACE_TABS" />
    </div>
    <p class="text-muted">
      Контент конкурентов, который расширение собрало в общую базу. Привязка, отвязка и
      исключение из сбора — только отсюда. Исключённая карточка больше не собирается:
      расширение её не открывает и не скроллит.
    </p>

    <!-- Тулбар: только поиск -->
    <div class="page-captured__toolbar">
      <input
        v-model="q"
        class="form-control form-control-sm page-captured__search"
        placeholder="Название, бренд, продавец, nmID"
        @keyup.enter="applyFilters"
      />
      <button class="btn btn-sm btn-primary" :disabled="loading" @click="applyFilters">
        <i class="bi bi-search"></i> Найти
      </button>
    </div>

    <!-- Полоса: слева фильтры (открыты по умолчанию, закрывает пользователь), справа — общая панель -->
    <div class="page-captured__bar">
      <details class="page-captured__filters" open>
        <summary>
          Фильтры
          <span v-if="activeFilters" class="page-captured__filters-count">{{ activeFilters }}</span>
        </summary>
        <div class="page-captured__filters-list">
          <label class="page-captured__field">
            <span>Сбор: с</span>
            <input v-model="collectedFrom" type="date" class="form-control form-control-sm" @change="applyFilters" />
            <span>по</span>
            <input v-model="collectedTo" type="date" class="form-control form-control-sm" @change="applyFilters" />
          </label>
          <label class="page-captured__field">
            <span>Появление: с</span>
            <input v-model="firstSeenFrom" type="date" class="form-control form-control-sm" @change="applyFilters" />
            <span>по</span>
            <input v-model="firstSeenTo" type="date" class="form-control form-control-sm" @change="applyFilters" />
          </label>
          <label class="page-captured__field">
            <span>Фраза</span>
            <input
              v-model="phraseFilter"
              class="form-control form-control-sm"
              placeholder="фраза из выдачи или формулировка конкурента"
              @keyup.enter="applyFilters"
              @change="applyFilters"
            />
          </label>
          <label class="page-captured__field">
            <span>Привязка</span>
            <select v-model="attachedFilter" class="form-select form-select-sm" @change="applyFilters">
              <option value="">любая</option>
              <option value="yes">привязана</option>
              <option value="no">не привязана</option>
            </select>
          </label>
          <label class="page-captured__field">
            <span>Источник</span>
            <select v-model="sourceFilter" class="form-select form-select-sm" @change="applyFilters">
              <option value="">любой</option>
              <option value="search">выдача</option>
              <option value="manual">вручную</option>
              <option value="sibling">с карточки</option>
              <option value="capture">привязка</option>
            </select>
          </label>
        </div>
        <div class="page-captured__checks">
          <label class="page-captured__check" title="desc_len = 0 — контент не собран">
            <input
              type="checkbox"
              :checked="contentFilter === 'no_desc'"
              @change="toggleNoDesc"
            />
            без описания
          </label>
          <label class="page-captured__check" title="показать исключённые из сбора карточки">
            <input v-model="includeHidden" type="checkbox" @change="applyFilters" />
            показать исключённые
          </label>
        </div>
        <div class="page-captured__filters-actions">
          <button class="btn btn-sm btn-outline-secondary" @click="resetFilters">Сбросить фильтры</button>
        </div>
      </details>

      <!-- Общая панель: режим списка и массовые действия -->
      <div class="page-captured__panel">
        <select
          v-model="scope"
          class="form-select form-select-sm page-captured__panel-scope"
          title="Собранные нами — реестр компании; От всех пользователей — весь собранный контент"
          @change="applyFilters"
        >
          <option value="captured">Собранные нами</option>
          <option value="all_details">От всех пользователей</option>
        </select>
        <div class="page-captured__panel-hint">что показываем в списке</div>
        <button
          class="btn btn-sm btn-outline-success"
          :disabled="!!collecting || !selectedRows.length"
          title="Все помеченные — в очередь сбора («SEO-мониторинг»)"
          @click="collectSelected()"
        >
          <i class="bi bi-cloud-download"></i> Собрать ({{ selectedRows.length }})
        </button>
        <button
          class="btn btn-sm btn-outline-primary"
          :disabled="!selectedRows.length"
          title="Привязать помеченные к нашим карточкам"
          @click="bulkOpen = true"
        >
          <i class="bi bi-link-45deg"></i> Привязать ({{ selectedRows.length }})
        </button>
        <button
          class="page-captured__panel-clear"
          :disabled="!selectedNms.length"
          @click="selectedNms = []"
        >снять выбор</button>
      </div>
    </div>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="notice" class="page-captured__notice">{{ notice }}</div>

    <div v-if="loading" class="text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка…
    </div>

    <div v-else-if="!rows.length" class="alert alert-info">
      Пока ничего не собрано. Откройте карточку конкурента на WB — расширение пришлёт контент автоматически.
    </div>

    <table v-else class="wb-admin-table page-captured__grid">
      <thead>
        <tr>
          <th class="page-pick__col-check">
            <input
              type="checkbox"
              :checked="allSelected"
              :disabled="!selectableRows.length"
              title="Выбрать все доступные для привязки"
              @change="toggleSelectAll"
            />
          </th>
          <th class="page-captured__col-product">
            <button type="button" class="page-captured__sort" @click="toggleSort('title')">
              Товар <i class="bi" :class="sortIcon('title')"></i>
            </button>
          </th>
          <th class="text-center page-captured__col-num">
            <button type="button" class="page-captured__sort" @click="toggleSort('price')">
              Цена <i class="bi" :class="sortIcon('price')"></i>
            </button>
          </th>
          <th class="text-center page-captured__col-desc" title="Длина описания">
            <button type="button" class="page-captured__sort" @click="toggleSort('desc_len')">
              Описание <i class="bi" :class="sortIcon('desc_len')"></i>
            </button>
          </th>
          <th class="text-center page-captured__col-num" title="Количество характеристик">
            <button type="button" class="page-captured__sort" @click="toggleSort('chars_cnt')">
              Хар-ки <i class="bi" :class="sortIcon('chars_cnt')"></i>
            </button>
          </th>
          <th class="text-center page-captured__col-phrase" title="серая — фразы в выдаче, синяя — формулировки после разбора (/competitor/phrase-miner)">Фразы</th>
          <th class="page-captured__col-date" title="Когда контент собран последний раз">
            <button type="button" class="page-captured__sort" @click="toggleSort('collected_at')">
              Собрано <i class="bi" :class="sortIcon('collected_at')"></i>
            </button>
          </th>
          <th class="text-center page-captured__col-chg" title="Снимков с изменённым контентом">Изменений</th>
          <th class="page-captured__col-attach">
            <button type="button" class="page-captured__sort" @click="toggleSort('attached_cnt')">
              Привязка <i class="bi" :class="sortIcon('attached_cnt')"></i>
            </button>
          </th>
          <th class="page-competitor__col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.nm_id" :class="{ 'page-captured__row--hidden': r.is_hidden, 'page-pick__row--picked': isSelected(r.nm_id) }">
          <td class="text-center">
            <input
              type="checkbox"
              :checked="isSelected(r.nm_id)"
              :disabled="!canSelect(r)"
              :title="canSelect(r) ? '' : (r.is_own ? 'Наша карточка — привязка недоступна' : 'Исключена — сначала верните')"
              @change="toggleSelect(r)"
            />
          </td>
          <td>
            <div class="page-competitor__product">
              <img :src="r.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb" loading="lazy" />
              <div class="page-competitor__product-text">
                <div class="page-competitor__product-title" :title="r.title || ''">{{ r.title || '—' }}</div>
                <div class="page-competitor__product-sub">
                  <a :href="wbUrl(r)" target="_blank" rel="noopener" class="page-competitor__wb-link">WB: {{ r.nm_id }}</a>
                  <button
                    type="button"
                    class="page-captured__copy"
                    :title="copiedNm === r.nm_id ? 'Ссылка скопирована' : 'Скопировать ссылку на WB'"
                    @click="copyWb(r)"
                  >
                    <i class="bi" :class="copiedNm === r.nm_id ? 'bi-check2' : 'bi-clipboard'"></i>
                  </button>
                  <span v-if="r.brand"> · {{ r.brand }}</span>
                  <span v-if="r.seller && r.seller !== r.brand"> · {{ r.seller }}</span>
                </div>
                <div class="page-captured__badges">
                  <span v-if="r.is_own" class="badge bg-warning text-dark" title="nm есть в wbcards нашей компании">наша карточка</span>
                  <span v-if="r.is_hidden" class="badge bg-secondary" title="Исключена из сбора — расширение её не собирает">исключено</span>
                  <span v-if="scope === 'all_details' && r.captured_by_us" class="badge bg-info text-dark" title="Собрали мы">собрано нами</span>
                  <span v-if="r.companies_cnt > 1" class="badge bg-light text-dark" :title="`видна компаниям: ${r.companies_cnt}`">компаний: {{ r.companies_cnt }}</span>
                </div>
              </div>
            </div>
          </td>
          <td class="text-center page-captured__price">{{ r.price ? `${r.price} ₽` : '—' }}</td>
          <td class="text-center">
            <span class="badge" :class="r.desc_len ? 'bg-success' : 'bg-danger'">{{ r.desc_len }}</span>
          </td>
          <td class="text-center">
            <span class="badge" :class="r.chars_cnt ? 'bg-success' : 'bg-danger'">{{ r.chars_cnt }}</span>
          </td>
          <td class="text-center page-captured__phrases">
            <template v-if="r.positions_cnt || r.phrases_cnt">
              <span
                v-if="r.positions_cnt"
                class="badge bg-secondary page-captured__phrase-badge"
                title="Фраз, по которым карточка замечена в выдаче (wb_competitor_position)"
              >{{ r.positions_cnt }}</span>
              <span
                v-if="r.phrases_cnt"
                class="badge bg-primary page-captured__phrase-badge"
                title="Формулировок после разбора (wb_competitor_phrase_comp) — разбор идёт фоном: /competitor/phrase-miner"
              >{{ r.phrases_cnt }}</span>
            </template>
            <span
              v-else
              class="page-captured__phrase-none"
              title="Фраз нет — разбор запускается фоном в /competitor/phrase-miner"
            >—</span>
          </td>
          <td class="page-captured__date" :title="collectedTitle(r)">{{ fmtDateTime(collectedAt(r)) }}</td>
          <td class="text-center">
            <button
              v-if="r.history_cnt"
              class="btn btn-link btn-sm page-captured__hist-btn"
              :title="`Снимков: ${r.history_cnt}`"
              @click="openHistory(r)"
            >{{ r.history_cnt }}</button>
            <span v-else class="page-competitor__dash">—</span>
          </td>
          <td class="page-captured__attach">
            <div v-if="r.attached_cnt" class="page-captured__attach-tags">
              <a
                v-for="a in r.attached"
                :key="a.nm_id"
                :href="`/wb/detail?nm_id=${a.nm_id}`"
                target="_blank"
                class="badge bg-primary page-captured__attach-tag"
                :title="a.title || ''"
              >{{ a.nm_id }}</a>
            </div>
            <span v-else class="text-muted small">не привязан</span>
          </td>
          <td class="page-competitor__actions">
            <div class="page-captured__acts">
              <button
                class="btn btn-sm btn-outline-primary"
                :disabled="busy === r.nm_id"
                title="Привязать к нашей карточке"
                @click="openAttach(r)"
              ><i class="bi bi-link-45deg"></i></button>
              <button
                class="btn btn-sm btn-outline-success"
                :disabled="!!collecting || !canCollect(r)"
                :title="canCollect(r) ? 'В очередь сбора («SEO-мониторинг») — соберёт расширение фоном' : 'Исключена из сбора — сначала верните'"
                @click="collectOne(r)"
              ><i class="bi bi-cloud-download"></i></button>
              <button
                class="btn btn-sm btn-outline-secondary"
                title="Открыть контент карточки"
                @click="openDetails(r)"
              ><i class="bi bi-eye"></i></button>
              <button
                class="btn btn-sm btn-outline-secondary"
                title="История изменений контента"
                @click="openHistory(r)"
              ><i class="bi bi-clock-history"></i></button>
              <button
                class="btn btn-sm"
                :class="r.is_hidden ? 'btn-outline-success' : 'btn-outline-warning'"
                :disabled="busy === r.nm_id || !canExclude(r)"
                :title="r.is_hidden ? 'Вернуть в сбор' : (canExclude(r) ? 'Исключить из сбора — расширение её больше не собирает' : 'Карточка не в нашем реестре — исключать нечего')"
                @click="toggleHidden(r)"
              ><i class="bi" :class="r.is_hidden ? 'bi-eye' : 'bi-eye-slash'"></i></button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Пагинация -->
    <div v-if="!loading" class="page-captured__pager">
      <button class="btn btn-sm btn-outline-secondary" :disabled="page <= 1" @click="goPage(page - 1)">
        <i class="bi bi-chevron-left"></i> Назад
      </button>
      <span class="page-captured__pager-label">
        Стр. {{ page }} из {{ totalPages }} · показано {{ rows.length }} из {{ total }}
      </span>
      <button class="btn btn-sm btn-outline-secondary" :disabled="page >= totalPages" @click="goPage(page + 1)">
        Вперёд <i class="bi bi-chevron-right"></i>
      </button>
      <select v-model.number="pageSize" class="form-select form-select-sm page-captured__pagesize" @change="applyFilters">
        <option :value="50">50</option>
        <option :value="100">100</option>
        <option :value="300">300</option>
      </select>
    </div>

    <CompetitorAttachModal
      :open="attachOpen"
      :nm-id="active?.nm_id"
      :title="active?.title"
      :attached="active?.attached || []"
      @close="attachOpen = false"
      @changed="reloadCurrent"
    />

    <CompetitorBulkAttachModal
      :open="bulkOpen"
      :candidates="selectedRows"
      @close="bulkOpen = false"
      @changed="onBulkChanged"
    />

    <CompetitorHistoryModal
      :open="historyOpen"
      :nm-id="active?.nm_id"
      @close="historyOpen = false"
    />

    <CompetitorDetailsModal
      :open="detailsOpen"
      :nm-id="active?.nm_id"
      @close="detailsOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-captured.css'
import '@/assets/css/pages/page-competitor-pick.css'
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { competitorsNewcardApi, type CapturedRow, type PickAttachResult } from '../api/competitorsNewcard'
import { seoWatchApi } from '../api/seoWatch'
import { useAuthStore } from '../stores/auth'
import { copyText } from '../utils/clipboard'
import CompetitorAttachModal from '../components/competitors/CompetitorAttachModal.vue'
import CompetitorBulkAttachModal from '../components/competitors/CompetitorBulkAttachModal.vue'
import WbWorkspaceTabs from '@/components/common/WbWorkspaceTabs.vue'
import { WORKSPACE_TABS } from '@/components/common/workspaceTabs'
import CompetitorDetailsModal from '../components/competitors/CompetitorDetailsModal.vue'
import CompetitorHistoryModal from '../components/competitors/CompetitorHistoryModal.vue'

const auth = useAuthStore()

const rows = ref<CapturedRow[]>([])
const q = ref('')
const includeHidden = ref(false)
const scope = ref<'captured' | 'all_details'>('captured')
const loading = ref(false)
const error = ref('')
const notice = ref('')
const busy = ref<number | null>(null)
const collecting = ref<number | 'bulk' | null>(null)
const selectedNms = ref<number[]>([])
const bulkOpen = ref(false)

// Фильтры
const collectedFrom = ref('')
const collectedTo = ref('')
const firstSeenFrom = ref('')
const firstSeenTo = ref('')
const contentFilter = ref('')
const attachedFilter = ref('')
const sourceFilter = ref('')
const phraseFilter = ref('')

// Сортировка и пагинация
const sortKey = ref('collected_at')
const sortDir = ref<'asc' | 'desc'>('desc')
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const offset = computed(() => (page.value - 1) * pageSize.value)

const activeFilters = computed(() => {
  let n = 0
  if (collectedFrom.value) n++
  if (collectedTo.value) n++
  if (firstSeenFrom.value) n++
  if (firstSeenTo.value) n++
  if (contentFilter.value) n++
  if (attachedFilter.value) n++
  if (sourceFilter.value) n++
  if (phraseFilter.value.trim()) n++
  return n
})

const selectableRows = computed(() => rows.value.filter((r) => canSelect(r)))
const selectedRows = computed(() => rows.value.filter((r) => selectedNms.value.includes(r.nm_id)))
const allSelected = computed(() =>
  selectableRows.value.length > 0 && selectableRows.value.every((r) => isSelected(r.nm_id)),
)

const active = ref<CapturedRow | null>(null)
const attachOpen = ref(false)
const detailsOpen = ref(false)
const historyOpen = ref(false)
const copiedNm = ref<number | null>(null)
let copiedTimer: ReturnType<typeof setTimeout> | null = null

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.captured({
      q: q.value.trim(),
      include_hidden: includeHidden.value,
      limit: pageSize.value,
      offset: offset.value,
      sort: sortKey.value,
      direction: sortDir.value,
      scope: scope.value,
      collected_from: collectedFrom.value,
      collected_to: collectedTo.value,
      first_seen_from: firstSeenFrom.value,
      first_seen_to: firstSeenTo.value,
      content: contentFilter.value,
      attached: attachedFilter.value,
      source: sourceFilter.value,
      phrase: phraseFilter.value.trim(),
    })
    rows.value = d.items || []
    total.value = d.total || 0
    const ids = new Set(rows.value.filter((r) => canSelect(r)).map((r) => r.nm_id))
    selectedNms.value = selectedNms.value.filter((id) => ids.has(id))
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

/** Любой фильтр/поиск/режим — с первой страницы. */
function applyFilters() {
  page.value = 1
  load()
}

function goPage(p: number) {
  const p2 = Math.max(1, Math.min(p, totalPages.value))
  if (p2 === page.value) return
  page.value = p2
  load()
}

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'title' ? 'asc' : 'desc'
  }
  applyFilters()
}

function sortIcon(key: string): string {
  if (sortKey.value !== key) return 'bi-arrow-down-up'
  return sortDir.value === 'asc' ? 'bi-caret-up-fill' : 'bi-caret-down-fill'
}

function canSelect(r: CapturedRow): boolean {
  return !r.is_own && !r.is_hidden
}

/** Исключить можно только то, что есть в нашем реестре (в общем кэше — нечего). */
function canExclude(r: CapturedRow): boolean {
  return scope.value === 'captured' || r.captured_by_us
}

function isSelected(nm: number): boolean {
  return selectedNms.value.includes(nm)
}

function toggleSelect(r: CapturedRow) {
  if (!canSelect(r)) return
  const i = selectedNms.value.indexOf(r.nm_id)
  if (i >= 0) selectedNms.value.splice(i, 1)
  else selectedNms.value.push(r.nm_id)
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedNms.value = []
    return
  }
  selectedNms.value = selectableRows.value.map((r) => r.nm_id)
}

function onBulkChanged(res: PickAttachResult) {
  const parts = [`привязано: ${res.added}`]
  if (res.exists) parts.push(`уже было: ${res.exists}`)
  if (res.skipped) parts.push(`пропущено: ${res.skipped}`)
  notice.value = parts.join(', ')
  bulkOpen.value = false
  selectedNms.value = []
  load(true)
}

/** Исключённые карточки расширение не собирает — кнопку блокируем. */
function canCollect(r: CapturedRow): boolean {
  return !r.is_hidden
}

async function collectOne(r: CapturedRow) {
  if (collecting.value) return
  await doCollect([r.nm_id], r.nm_id, 'single')
}

async function collectSelected() {
  if (collecting.value || !selectedRows.value.length) return
  const ids = selectedRows.value.filter((r) => canCollect(r)).map((r) => r.nm_id)
  if (!ids.length) return
  await doCollect(ids, null, 'bulk')
}

/** Карточки → очередь «SEO-мониторинг» (wb_enrich_queue, source='watch'). */
async function doCollect(nmIds: number[], singleNm: number | null, kind: 'single' | 'bulk') {
  collecting.value = kind === 'single' ? singleNm : 'bulk'
  error.value = ''
  notice.value = ''
  try {
    const res = await seoWatchApi.collectNms(nmIds)
    const parts = [`в очередь («SEO-мониторинг»): ${res.assigned}`]
    if (res.excluded) parts.push(`исключено: ${res.excluded}`)
    if (res.skipped) parts.push(`в работе: ${res.skipped}`)
    notice.value = parts.join(', ')
    if (singleNm) selectedNms.value = selectedNms.value.filter((id) => id !== singleNm)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось поставить в очередь'
  } finally {
    collecting.value = null
  }
}

async function reloadCurrent() {
  const id = active.value?.nm_id
  await load(true)
  if (id) active.value = rows.value.find((r) => r.nm_id === id) || active.value
}

/** Чек «без описания» = content=no_desc (полный селект «Контент» убран за ненадобностью). */
function toggleNoDesc(e: Event) {
  contentFilter.value = (e.target as HTMLInputElement).checked ? 'no_desc' : ''
  applyFilters()
}

function resetFilters(andLoad = true) {
  q.value = ''
  collectedFrom.value = ''
  collectedTo.value = ''
  firstSeenFrom.value = ''
  firstSeenTo.value = ''
  contentFilter.value = ''
  attachedFilter.value = ''
  sourceFilter.value = ''
  phraseFilter.value = ''
  if (andLoad) applyFilters()
}

/** Глобальный админ в режиме «все компании» — по умолчанию общий кэш. */
function defaultScope(): 'captured' | 'all_details' {
  return auth.companyId === 'all' ? 'all_details' : 'captured'
}

function wbUrl(r: CapturedRow): string {
  return r.url || `https://www.wildberries.ru/catalog/${r.nm_id}/detail.aspx`
}

/** Достоверная дата — полный сбор; collected_at может «обновиться» от наблюдения. */
function collectedAt(r: CapturedRow): string | null | undefined {
  return r.full_collected_at || r.collected_at
}

function collectedTitle(r: CapturedRow): string {
  const full = r.full_collected_at ? `полный сбор: ${fmtFull(r.full_collected_at)}` : ''
  const any = r.collected_at ? `последнее обновление: ${fmtFull(r.collected_at)}` : ''
  return [full, any].filter(Boolean).join(' · ') || '—'
}

function fmtDateTime(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

function fmtFull(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

function openAttach(r: CapturedRow) {
  active.value = r
  attachOpen.value = true
}

async function copyWb(r: CapturedRow) {
  if (!await copyText(wbUrl(r))) {
    error.value = 'Не удалось скопировать ссылку'
    return
  }
  copiedNm.value = r.nm_id
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => { copiedNm.value = null }, 1500)
}

function openDetails(r: CapturedRow) {
  active.value = r
  detailsOpen.value = true
}

function openHistory(r: CapturedRow) {
  active.value = r
  historyOpen.value = true
}

async function toggleHidden(r: CapturedRow) {
  if (busy.value) return
  busy.value = r.nm_id
  error.value = ''
  notice.value = ''
  try {
    const next = !r.is_hidden
    await competitorsNewcardApi.hideCaptured(r.nm_id, next)
    notice.value = next
      ? `Исключено из сбора: ${r.nm_id} — расширение её больше не собирает`
      : `Возвращено в сбор: ${r.nm_id}`
    await load(true)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось изменить видимость'
  } finally {
    busy.value = null
  }
}

// Смена компании в шапке — свой реестр против общего кэша
watch(() => auth.companyId, () => {
  scope.value = defaultScope()
  applyFilters()
})

onMounted(() => {
  scope.value = defaultScope()
  load()
})
onBeforeUnmount(() => {
  if (copiedTimer) clearTimeout(copiedTimer)
})
</script>
