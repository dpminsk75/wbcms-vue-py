<template>
  <div class="container-xxl page-competitor page-captured">
    <!-- Шапка рабочего места: заголовок + меню рабочих мест (общий компонент темы) -->
    <WbWorkspaceHead title="Собранные карточки" workspace-active="captured" />
    <p class="text-muted">
      Контент конкурентов, который расширение собрало в общую базу. Привязка, отвязка и
      исключение из сбора — только отсюда. Исключённая карточка больше не собирается:
      расширение её не открывает и не скроллит.
    </p>

    <!-- Тулбар: только поиск -->
    <div class="page-captured__toolbar">
      <input
        v-model="q"
        class="wb-input page-captured__search"
        placeholder="Название, бренд, продавец, nmID"
        @keyup.enter="applyFilters"
      />
      <button class="btn btn-sm btn--brand" :disabled="loading" @click="applyFilters">
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
            <input v-model="collectedFrom" type="date" class="wb-input" @change="applyFilters" />
            <span>по</span>
            <input v-model="collectedTo" type="date" class="wb-input" @change="applyFilters" />
          </label>
          <label class="page-captured__field">
            <span>Появление: с</span>
            <input v-model="firstSeenFrom" type="date" class="wb-input" @change="applyFilters" />
            <span>по</span>
            <input v-model="firstSeenTo" type="date" class="wb-input" @change="applyFilters" />
          </label>
          <label class="page-captured__field">
            <span>Фраза</span>
            <input
              v-model="phraseFilter"
              class="wb-input"
              placeholder="фраза из выдачи или формулировка конкурента"
              @keyup.enter="applyFilters"
              @change="applyFilters"
            />
          </label>
          <label class="page-captured__field">
            <span>Привязка вручную</span>
            <select v-model="attachedFilter" class="form-select form-select-sm" @change="applyFilters">
              <option value="">любая</option>
              <option value="yes">привязана вручную</option>
              <option value="no">не привязана вручную</option>
            </select>
          </label>
          <label class="page-captured__field">
            <span>Источник</span>
            <select v-model="sourceFilter" class="form-select form-select-sm" @change="applyFilters">
              <option value="">любой</option>
              <option value="manual">карточка</option>
              <option value="sibling">аналог</option>
              <option value="capture">сбор</option>
              <option value="search">поиск</option>
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
          <button class="btn btn-sm btn--outline" @click="resetFilters">Сбросить фильтры</button>
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
          class="btn btn-sm btn--outline"
          :disabled="!!collecting || !selectedRows.length"
          title="Все помеченные — в очередь сбора («SEO-мониторинг»)"
          @click="collectSelected()"
        >
          <span v-if="collecting === 'bulk'" class="spinner-border spinner-border-sm"></span>
          <i v-else class="bi bi-cloud-download"></i> Собрать ({{ selectedRows.length }})
        </button>
        <button
          class="btn btn-sm btn--outline"
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

    <div v-else-if="!rows.length" class="wb-panel page-captured__empty">
      <div class="wb-panel__bd">
      Пока ничего не собрано. Откройте карточку конкурента на WB — расширение пришлёт контент автоматически.
    </div>
    </div>

    <div v-else class="tbl-card">
      <div class="card__hd">
        <span>Собранные карточки</span>
        <span class="spacer"></span>
        <span class="hd-badge">Карточек: {{ rows.length }}</span>
      </div>
      <div class="tbl-wrap">
    <table class="tbl page-captured__grid">
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
          <th class="t-left page-captured__col-product">
            <button type="button" class="page-captured__sort" @click="toggleSort('title')">
              Товар <i class="bi" :class="sortIcon('title')"></i>
            </button>
          </th>
          <th class="t-center page-captured__col-num">
            <button type="button" class="page-captured__sort" @click="toggleSort('price')">
              Цена <i class="bi" :class="sortIcon('price')"></i>
            </button>
          </th>
          <th class="t-center page-captured__col-desc" title="Длина описания">
            <button type="button" class="page-captured__sort" @click="toggleSort('desc_len')">
              Описание <i class="bi" :class="sortIcon('desc_len')"></i>
            </button>
          </th>
          <th class="t-center page-captured__col-num" title="Количество характеристик">
            <button type="button" class="page-captured__sort" @click="toggleSort('chars_cnt')">
              Хар-ки <i class="bi" :class="sortIcon('chars_cnt')"></i>
            </button>
          </th>
          <th class="t-center page-captured__col-phrase" title="серая — фразы в выдаче, синяя — формулировок после ИИ-разбора (/competitor/phrase-miner)">Фразы</th>
          <th class="page-captured__col-date" title="Когда контент собран последний раз">
            <button type="button" class="page-captured__sort" @click="toggleSort('collected_at')">
              Собрано <i class="bi" :class="sortIcon('collected_at')"></i>
            </button>
          </th>
          <th class="t-center page-captured__col-chg" title="Снимков с изменённым контентом">Изменений</th>
          <th
            class="page-captured__col-attach"
            title="Ручные привязки к нашим карточкам (привязка вручную: из «Собранных карточек» или из пула подбора). В досье конкурента — те же привязки с пометкой источника"
          >
            <button type="button" class="page-captured__sort" @click="toggleSort('attached_cnt')">
              Привязана вручную <i class="bi" :class="sortIcon('attached_cnt')"></i>
            </button>
          </th>
          <th class="page-competitor__col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.nm_id" :class="{ 'page-captured__row--hidden': r.is_hidden, 'page-pick__row--picked': isSelected(r.nm_id) }">
          <td class="t-center">
            <input
              type="checkbox"
              :checked="isSelected(r.nm_id)"
              :disabled="!canSelect(r)"
              :title="canSelect(r) ? '' : (r.is_own ? 'Наша карточка — привязка недоступна' : 'Исключена — сначала верните')"
              @change="toggleSelect(r)"
            />
          </td>
          <td class="t-left">
            <!-- Клик по названию или по фото открывает досье конкурента — как «глазик». -->
            <div class="page-captured__cell" @click="onCellClick($event, r)">
              <CompetitorRow
                compact
                :nm-id="r.nm_id"
                :title="r.title || ''"
                :photo="r.photo || ''"
                :seller="r.seller || ''"
                :brand="r.brand || ''"
                :badges="capturedBadges(r)"
                :wb-url="wbUrl(r)"
                :phrases-url="'/competitor/phrase-miner'"
                show-nm
                copy-nm
                copy-wb-link
                @open="openDetails(r)"
              />
            </div>
          </td>
          <td class="t-center page-captured__price">{{ r.price ? `${r.price} ₽` : '—' }}</td>
          <td class="t-center">
            <span class="badge" :class="r.desc_len ? 'badge--ok' : 'badge--bad'">{{ r.desc_len }}</span>
          </td>
          <td class="t-center">
            <span class="badge" :class="r.chars_cnt ? 'badge--ok' : 'badge--bad'">{{ r.chars_cnt }}</span>
          </td>
          <td class="t-center page-captured__phrases">
            <template v-if="r.positions_cnt || r.phrases_cnt">
              <button
                v-if="r.positions_cnt"
                type="button"
                class="badge badge--neutral page-captured__phrase-badge page-captured__phrase-badge--btn"
                title="Фраз, по которым карточка замечена в выдаче (wb_competitor_position)"
                @click="openPhrases(r, 'search', r.positions_cnt)"
              >{{ r.positions_cnt }}</button>
              <button
                v-if="r.phrases_cnt"
                type="button"
                class="badge badge--info page-captured__phrase-badge page-captured__phrase-badge--btn"
                title="Формулировок после ИИ-разбора (wb_competitor_phrase_comp)"
                @click="openPhrases(r, 'comp', r.phrases_cnt)"
              >{{ r.phrases_cnt }}</button>
            </template>
            <span
              v-else
              class="page-captured__phrase-none"
              title="Фраз нет — разбор запускается фоном в /competitor/phrase-miner"
            >—</span>
          </td>
          <td class="page-captured__date" :title="collectedTitle(r)">{{ fmtDateTime(collectedAt(r)) }}</td>
          <td class="t-center">
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
                class="badge badge--brand page-captured__attach-tag"
                :title="a.title || ''"
              >{{ a.nm_id }}</a>
            </div>
            <span v-else class="text-muted small">не привязана вручную</span>
          </td>
          <td class="page-competitor__actions">
            <div class="page-captured__acts">
              <button
                class="btn btn-sm page-captured__act page-captured__act--attach"
                :disabled="busy === r.nm_id"
                title="Привязать к нашей карточке"
                @click="openAttach(r)"
              ><i class="bi bi-link-45deg"></i></button>
              <button
                class="btn btn-sm page-captured__act page-captured__act--collect"
                :disabled="!!collecting || !canCollect(r)"
                :title="canCollect(r) ? 'В очередь сбора («SEO-мониторинг») — соберёт расширение фоном' : 'Исключена из сбора — сначала верните'"
                @click="collectOne(r)"
              >
                <span v-if="collecting === r.nm_id" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-cloud-download"></i>
              </button>
              <button
                class="btn btn-sm page-captured__act page-captured__act--view"
                title="Открыть контент карточки"
                @click="openDetails(r)"
              ><i class="bi bi-eye"></i></button>
              <button
                class="btn btn-sm page-captured__act page-captured__act--history"
                title="История изменений контента"
                @click="openHistory(r)"
              ><i class="bi bi-clock-history"></i></button>
              <button
                class="btn btn-sm page-captured__act"
                :class="r.is_hidden ? 'page-captured__act--restore' : 'page-captured__act--exclude'"
                :disabled="busy === r.nm_id || !canExclude(r)"
                :title="r.is_hidden ? 'Вернуть в сбор' : (canExclude(r) ? 'Исключить из сбора — расширение её больше не собирает' : 'Карточка не в нашем реестре — исключать нечего')"
                @click="toggleHidden(r)"
              ><i class="bi" :class="r.is_hidden ? 'bi-eye' : 'bi-eye-slash'"></i></button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    </div>
    </div>

    <!-- Пагинация -->
    <div v-if="!loading" class="wb-pager">
      <button class="btn btn-sm btn--outline" :disabled="page <= 1" @click="goPage(page - 1)">
        <i class="bi bi-chevron-left"></i> Назад
      </button>
      <span class="wb-pager__label">
        Стр. {{ page }} из {{ totalPages }} · показано {{ rows.length }} из {{ total }}
      </span>
      <button class="btn btn-sm btn--outline" :disabled="page >= totalPages" @click="goPage(page + 1)">
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

    <CompetitorPhrasesModal
      :open="phrasesOpen"
      :nm-id="phrasesRow?.nm_id"
      :title="phrasesRow?.title"
      :source="phrasesSource"
      :count="phrasesCount"
      @close="phrasesOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-captured.css'
import '@/assets/css/pages/page-competitor-pick.css'
import CompetitorRow from '@/components/common/CompetitorRow.vue'
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { competitorsNewcardApi, type CapturedRow, type PickAttachResult } from '../api/competitorsNewcard'
import { seoWatchApi } from '../api/seoWatch'
import { useAuthStore } from '../stores/auth'
import { copyText } from '../utils/clipboard'
import CompetitorAttachModal from '../components/competitors/CompetitorAttachModal.vue'
import CompetitorBulkAttachModal from '../components/competitors/CompetitorBulkAttachModal.vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import CompetitorDetailsModal from '../components/competitors/CompetitorDetailsModal.vue'
import CompetitorPhrasesModal from '../components/competitors/CompetitorPhrasesModal.vue'
import CompetitorHistoryModal from '../components/competitors/CompetitorHistoryModal.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

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
const phrasesOpen = ref(false)
const phrasesRow = ref<CapturedRow | null>(null)
const phrasesSource = ref<'capture' | 'comp' | 'search'>('comp')
const phrasesCount = ref<number | null>(null)
const detailsOpen = ref(false)
const historyOpen = ref(false)
const copiedNm = ref<number | null>(null)
let copiedTimer: ReturnType<typeof setTimeout> | null = null

async function load(silent = false) {
  syncUrl()
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

/** Состояние страницы → адресная строка: фильтры переживают перезагрузку, ссылкой можно поделиться. */
function syncUrl() {
  const qs: Record<string, any> = { ...route.query }
  const put = (k: string, v: any) => {
    if (v === '' || v === null || v === undefined || v === false) delete qs[k]
    else qs[k] = String(v)
  }
  put('q', q.value)
  put('scope', scope.value)
  put('sort', sortKey.value)
  put('dir', sortDir.value)
  put('page', page.value > 1 ? page.value : '')
  put('size', pageSize.value)
  put('collected_from', collectedFrom.value)
  put('collected_to', collectedTo.value)
  put('seen_from', firstSeenFrom.value)
  put('seen_to', firstSeenTo.value)
  put('content', contentFilter.value)
  put('attached', attachedFilter.value)
  put('source', sourceFilter.value)
  put('phrase', phraseFilter.value)
  put('hidden', includeHidden.value ? '1' : '')
  const target = { path: route.path, query: qs }
  if (route.fullPath === router.resolve(target).fullPath) return
  router.replace(target).catch(() => {})
}

/** Адресная строка → состояние. true — что-то изменилось (нужен перезагруз). */
function applyQuery(): boolean {
  const p = route.query
  const s = (k: string) => (p[k] === undefined ? '' : String(p[k]))
  let changed = false
  const set = (cur: any, val: string) => {
    if (String(cur ?? '') !== String(val ?? '')) changed = true
  }
  if (p.q !== undefined) { set(q.value, s('q')); q.value = s('q') }
  if (p.scope !== undefined) {
    const sc = s('scope')
    if (sc === 'captured' || sc === 'all_details') { set(scope.value, sc); scope.value = sc }
  }
  if (p.sort !== undefined) { set(sortKey.value, s('sort')); sortKey.value = s('sort') }
  if (p.dir !== undefined) {
    const d = s('dir')
    if (d === 'asc' || d === 'desc') { set(sortDir.value, d); sortDir.value = d }
  }
  if (p.page !== undefined) {
    const pg = Math.max(1, Number(s('page')) || 1)
    if (pg !== page.value) { changed = true; page.value = pg }
  }
  if (p.size !== undefined) {
    const sz = Number(s('size')) || 50
    if (sz !== pageSize.value) { changed = true; pageSize.value = sz }
  }
  if (p.collected_from !== undefined) { set(collectedFrom.value, s('collected_from')); collectedFrom.value = s('collected_from') }
  if (p.collected_to !== undefined) { set(collectedTo.value, s('collected_to')); collectedTo.value = s('collected_to') }
  if (p.seen_from !== undefined) { set(firstSeenFrom.value, s('seen_from')); firstSeenFrom.value = s('seen_from') }
  if (p.seen_to !== undefined) { set(firstSeenTo.value, s('seen_to')); firstSeenTo.value = s('seen_to') }
  if (p.content !== undefined) { set(contentFilter.value, s('content')); contentFilter.value = s('content') }
  if (p.attached !== undefined) { set(attachedFilter.value, s('attached')); attachedFilter.value = s('attached') }
  if (p.source !== undefined) { set(sourceFilter.value, s('source')); sourceFilter.value = s('source') }
  if (p.phrase !== undefined) { set(phraseFilter.value, s('phrase')); phraseFilter.value = s('phrase') }
  if (p.hidden !== undefined) {
    const hh = s('hidden') === '1'
    if (hh !== includeHidden.value) { changed = true; includeHidden.value = hh }
  }
  return changed
}

/** Глобальный админ в режиме «все компании» — по умолчанию общий кэш. */
function defaultScope(): 'captured' | 'all_details' {
  return auth.companyId === 'all' ? 'all_details' : 'captured'
}

/** Бейджи состояния карточки (общий формат CompetitorRow: {label, tone}). */
function capturedBadges(r: any): Array<{ label: string; tone: string }> {
  const out: Array<{ label: string; tone: string }> = []
  if (r.is_own) out.push({ label: 'наша карточка', tone: 'warn' })
  if (r.is_hidden) out.push({ label: 'исключено', tone: 'gray' })
  if (scope.value === 'all_details' && r.captured_by_us) out.push({ label: 'собрано нами', tone: 'info' })
  if (r.companies_cnt > 1) out.push({ label: 'компаний: ' + r.companies_cnt, tone: 'gray' })
  return out
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

/** Клик по названию или по фото карточки — то же, что «глазик»: открыть досье конкурента.
 *  Только название и фото: подпись, бейджи и ссылки остаются неактивными. */
function onCellClick(e: MouseEvent, r: CapturedRow) {
  const t = e.target as HTMLElement | null
  if (!t) return
  // ссылка «фразы» в строке — открываем модалку фраз (общий компонент не перехватываем)
  if (t.closest('.prod-cell__more')) {
    e.preventDefault()
    openPhrases(r, 'comp', r.phrases_cnt)
    return
  }
  if (!t.closest('.prod-cell__title, .prod-cell__img')) return
  openDetails(r)
}

/** Модалка «Фразы карточки» (заготовка): из строки, из цифр колонки «Фразы». */
function openPhrases(r: CapturedRow, source: 'capture' | 'comp' | 'search', count?: number | null) {
  phrasesRow.value = r
  phrasesSource.value = source
  phrasesCount.value = count ?? null
  phrasesOpen.value = true
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
  // скоуп из ссылки, иначе — по компании
  scope.value = defaultScope()
  applyQuery()
  load()
})

// «назад/вперёд» в браузере и переход по ссылке — применяем состояние из адресной строки
watch(() => route.query, () => {
  if (applyQuery()) load()
})
onBeforeUnmount(() => {
  if (copiedTimer) clearTimeout(copiedTimer)
})
</script>
