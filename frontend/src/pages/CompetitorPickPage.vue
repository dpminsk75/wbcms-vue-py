<template>
  <div class="container-xxl page-competitor page-pick">
    <div class="page-competitor__head">
      <h2 class="page-competitor__title">Подбор конкурентов</h2>
      <div class="page-competitor__head-actions">
        <router-link to="/competitor/new-cards" class="btn btn-sm btn-outline-secondary">
          <i class="bi bi-box"></i> Новые карточки
        </router-link>
        <router-link to="/competitor/captured" class="btn btn-sm btn-outline-secondary">
          <i class="bi bi-collection"></i> Собранные карточки
        </router-link>
      </div>
    </div>
    <p class="text-muted">
      Выберите наши карточки, соберите пул конкурентов и привяжите выбранных сразу к нескольким
      нашим карточкам. Пул можно строить из конкурентов выбранных карточек и их рекомендаций
      или из всей собранной базы компании.
    </p>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="notice" class="page-pick__notice">{{ notice }}</div>

    <!-- шаг 1: наши карточки-источники -->
    <section class="page-pick__step">
      <div class="page-pick__step-head">
        <h4><span class="page-pick__step-num">1</span> Наши карточки</h4>
        <span class="badge bg-primary">выбрано: {{ selectedSources.length }}</span>
      </div>

      <div class="page-pick__toolbar">
        <div class="page-pick__search">
          <i class="bi bi-search"></i>
          <input
            v-model="cardQ"
            class="form-control form-control-sm"
            placeholder="nmID, артикул WB или название"
            autocomplete="off"
            @keyup.enter="loadCards"
          />
          <span v-if="cardsLoading" class="spinner-border spinner-border-sm text-secondary"></span>
        </div>
        <button class="btn btn-sm btn-outline-secondary" :disabled="cardsLoading || !cardQ.trim()" @click="loadCards">
          Найти
        </button>
        <span class="page-pick__muted">Показано: {{ cards.length }}</span>
      </div>

      <div v-if="selectedSources.length" class="page-pick__chips">
        <span class="page-pick__chips-label">Источники:</span>
        <button
          v-for="c in selectedSources"
          :key="c.nmID"
          type="button"
          class="page-pick__chip"
          :title="c.title || ''"
          @click="removeSource(c)"
        >
          {{ c.nmID }} <i class="bi bi-x"></i>
        </button>
      </div>

      <div v-if="cardsLoading && !cards.length" class="text-muted">
        <span class="spinner-border spinner-border-sm"></span> Загрузка…
      </div>
      <div v-else-if="!cards.length" class="alert alert-info mb-0">
        <template v-if="!cardQ.trim()">Введите запрос и нажмите «Найти».</template>
        <template v-else>Ничего не найдено. Уточните запрос.</template>
      </div>
      <table v-else class="wb-admin-table page-competitor__grid page-pick__grid">
        <thead>
          <tr>
            <th class="page-pick__col-check"></th>
            <th class="page-competitor__col-product">Наша карточка</th>
            <th class="text-center page-competitor__col-num">Конкуренты</th>
            <th class="text-center page-competitor__col-num">С контентом</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in cards"
            :key="c.nmID"
            :class="{ 'page-pick__row--picked': isSource(c.nmID) }"
            @click="toggleSource(c)"
          >
            <td class="text-center">
              <input
                type="checkbox"
                :checked="isSource(c.nmID)"
                @click.stop
                @change="toggleSource(c)"
              />
            </td>
            <td>
              <div class="page-competitor__product">
                <img :src="c.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb" loading="lazy" />
                <div class="page-competitor__product-text">
                  <div class="page-competitor__product-title" :title="c.title || ''">{{ c.title || '—' }}</div>
                  <div class="page-competitor__product-sub">
                    <a
                      :href="`/wb/detail?nm_id=${c.nmID}`"
                      target="_blank"
                      class="page-competitor__wb-link"
                      @click.stop
                    >WB: {{ c.nmID }}</a>
                    <span v-if="c.vendor_code"> · {{ c.vendor_code }}</span>
                    <span v-if="c.brand"> · {{ c.brand }}</span>
                  </div>
                  <div v-if="c.subject_name" class="page-competitor__product-sub">{{ c.subject_name }}</div>
                </div>
              </div>
            </td>
            <td class="text-center">
              <span class="badge" :class="c.competitors_cnt ? 'bg-primary' : 'bg-light text-dark'">
                {{ c.competitors_cnt }}
              </span>
            </td>
            <td class="text-center">
              <span class="badge" :class="c.content_cnt ? 'bg-success' : 'bg-light text-dark'">
                {{ c.content_cnt }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- шаг 2: куда привязать -->
    <section class="page-pick__step">
      <div class="page-pick__step-head">
        <h4><span class="page-pick__step-num">2</span> Куда привязать</h4>
        <span class="badge bg-primary">целей: {{ selectedTargets.length }}</span>
      </div>

      <div class="page-pick__toolbar">
        <div class="page-pick__search">
          <i class="bi bi-search"></i>
          <input
            v-model="targetQ"
            class="form-control form-control-sm"
            placeholder="nmID, артикул WB или название"
            autocomplete="off"
            @keyup.enter="loadTargets"
          />
          <span v-if="targetLoading" class="spinner-border spinner-border-sm text-secondary"></span>
        </div>
        <button class="btn btn-sm btn-outline-secondary" :disabled="targetLoading || !targetQ.trim()" @click="loadTargets">
          Найти
        </button>
        <span class="page-pick__muted">Показано: {{ targetOptions.length }}</span>
      </div>

      <div v-if="selectedTargets.length" class="page-pick__chips">
        <span class="page-pick__chips-label">Цели:</span>
        <button
          v-for="c in selectedTargets"
          :key="c.nmID"
          type="button"
          class="page-pick__chip page-pick__chip--target"
          :title="c.title || ''"
          @click="removeTarget(c)"
        >
          {{ c.nmID }} <i class="bi bi-x"></i>
        </button>
      </div>

      <div v-if="targetLoading && !targetOptions.length" class="text-muted small p-2">
        <span class="spinner-border spinner-border-sm"></span> Загрузка…
      </div>
      <div v-else-if="!targetOptions.length" class="alert alert-info mb-0">
        <template v-if="!targetQ.trim()">Введите запрос и нажмите «Найти».</template>
        <template v-else>Ничего не найдено.</template>
      </div>
      <table v-else class="wb-admin-table page-competitor__grid page-pick__grid page-pick__targets-table">
        <thead>
          <tr>
            <th class="page-pick__col-check"></th>
            <th class="page-competitor__col-product">Наша карточка</th>
            <th class="text-center page-competitor__col-num">Конкуренты</th>
            <th class="text-center page-competitor__col-num">С контентом</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in targetOptions"
            :key="c.nmID"
            :class="{ 'page-pick__row--picked': isTarget(c.nmID) }"
            @click="toggleTarget(c)"
          >
            <td class="text-center">
              <input
                type="checkbox"
                :checked="isTarget(c.nmID)"
                @click.stop
                @change="toggleTarget(c)"
              />
            </td>
            <td>
              <div class="page-competitor__product">
                <img :src="c.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb" loading="lazy" />
                <div class="page-competitor__product-text">
                  <div class="page-competitor__product-title" :title="c.title || ''">{{ c.title || '—' }}</div>
                  <div class="page-competitor__product-sub">
                    <a
                      :href="`/wb/detail?nm_id=${c.nmID}`"
                      target="_blank"
                      class="page-competitor__wb-link"
                      @click.stop
                    >WB: {{ c.nmID }}</a>
                    <span v-if="c.vendor_code"> · {{ c.vendor_code }}</span>
                    <span v-if="c.brand"> · {{ c.brand }}</span>
                  </div>
                  <div v-if="c.subject_name" class="page-competitor__product-sub">{{ c.subject_name }}</div>
                </div>
              </div>
            </td>
            <td class="text-center">
              <span class="badge" :class="c.competitors_cnt ? 'bg-primary' : 'bg-light text-dark'">
                {{ c.competitors_cnt }}
              </span>
            </td>
            <td class="text-center">
              <span class="badge" :class="c.content_cnt ? 'bg-success' : 'bg-light text-dark'">
                {{ c.content_cnt }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- шаг 3: пул кандидатов -->
    <section class="page-pick__step">
      <div class="page-pick__step-head">
        <h4><span class="page-pick__step-num">3</span> Пул кандидатов</h4>
        <span class="badge bg-secondary">в пуле: {{ poolTotal }}</span>
      </div>

      <div class="page-pick__toolbar page-pick__toolbar--wrap">
        <div class="btn-group btn-group-sm" role="group" aria-label="Режим пула">
          <button
            type="button"
            class="btn"
            :class="mode === 'recommend' ? 'btn-primary' : 'btn-outline-primary'"
            title="Конкуренты выбранных карточек + их рекомендации"
            @click="setMode('recommend')"
          >Конкуренты + рекомендации</button>
          <button
            type="button"
            class="btn"
            :class="mode === 'competitors' ? 'btn-primary' : 'btn-outline-primary'"
            title="Только конкуренты выбранных карточек"
            @click="setMode('competitors')"
          >Конкуренты</button>
          <button
            type="button"
            class="btn"
            :class="mode === 'captured' ? 'btn-primary' : 'btn-outline-primary'"
            title="Вся собранная база компании"
            @click="setMode('captured')"
          >Собранные</button>
        </div>

        <input
          v-model="poolQ"
          class="form-control form-control-sm page-pick__pool-search"
          placeholder="Фильтр: название, бренд, продавец, nmID"
          @keyup.enter="loadPool"
        />
        <select
          v-model="sortMode"
          class="form-select form-select-sm page-pick__sort"
          title="Сортировка списка"
          @change="loadPool"
        >
          <option value="relevance">по релевантности</option>
          <option value="title_asc">по алфавиту А–Я</option>
          <option value="title_desc">по алфавиту Я–А</option>
        </select>
        <label class="page-pick__check">
          <input v-model="onlyContent" type="checkbox" @change="loadPool" />
          только с описанием
        </label>
        <label class="page-pick__check">
          <input v-model="onlyRecommended" type="checkbox" @change="loadPool" />
          только из рекомендаций конкурентов
        </label>
        <label
          class="page-pick__check"
          :title="selectedTargets.length ? '' : 'Сначала выберите цели в шаге 2'"
        >
          <input v-model="hideAttachedAll" type="checkbox" :disabled="!selectedTargets.length" />
          скрыть уже привязанные ко всем целям
        </label>
        <button
          class="btn btn-sm btn-primary"
          :disabled="poolLoading || !canLoadPool"
          :title="canLoadPool ? '' : 'Выберите хотя бы одну нашу карточку'"
          @click="loadPool"
        >
          <span v-if="poolLoading" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-diagram-3"></i>
          Собрать пул
        </button>
        <button
          class="btn btn-sm btn-outline-secondary"
          :disabled="poolLoading || !pool.length"
          @click="selectAll"
        >
          {{ allSelected ? 'Снять выбор' : 'Выбрать все' }}
        </button>
      </div>

      <div v-if="mode === 'captured' || selectedSources.length" class="page-pick__hint">
        Конкуренты и рекомендации привязываются даже без записи в «Собранных»:
        описание и характеристики берутся из общей базы, собранной поиском или очередью.
        Серые строки — скрытые и наши карточки: для них привязка недоступна.
        Колонка «Уже привязан к» показывает только выбранные источники и цели.
      </div>
      <div v-if="mode !== 'captured' && selectedSources.length" class="page-pick__hint page-pick__hint--sources">
        Пул от источников: <b>{{ selectedSources.map((c) => c.nmID).join(', ') }}</b>.
        Рекомендации (B) берутся из карточек конкурентов этих источников.
        В колонке «Рекомендации конкурентов» после ID показан source, к которому привязан конкурент.
        <button
          v-if="selectedTargets.length"
          type="button"
          class="btn btn-link btn-sm p-0 align-baseline"
          @click="useTargetsAsSources"
        >Использовать цели как источники</button>
      </div>
      <div v-if="mode !== 'captured' && !selectedSources.length" class="alert alert-info mb-0">
        Выберите наши карточки в шаге 1 — из них соберутся конкуренты.
        Для режима «Собранные» источники не нужны.
      </div>
      <div v-else-if="poolLoading && !pool.length" class="text-muted">
        <span class="spinner-border spinner-border-sm"></span> Собираем пул…
      </div>
      <div v-else-if="!visiblePool.length" class="alert alert-info mb-0">
        <template v-if="pool.length && hideAttachedAll">
          Все кандидаты уже привязаны ко всем выбранным целям.
        </template>
        <template v-else>Пул пуст. Нажмите «Собрать пул» или измените фильтры.</template>
      </div>

      <table v-else class="wb-admin-table page-pick__grid page-pick__pool">
        <thead>
          <tr>
            <th class="page-pick__col-check"></th>
            <th class="page-pick__col-product">Кандидат</th>
            <th class="text-center" title="Длина описания">Описание</th>
            <th class="text-center" title="Количество характеристик">Хар-ки</th>
            <th
              class="page-pick__col-rec"
              title="ID конкурентов A, которые рекомендуют товар. Стрелка — наша source-карточка, к которой привязан этот конкурент."
            >Рекомендации конкурентов</th>
            <th class="page-pick__col-status">Статус</th>
            <th class="page-pick__col-attach" title="Только выбранные источники и цели">Уже привязан к</th>
            <th class="text-center" title="Статус сбора описаний">Очередь</th>
            <th class="text-center page-pick__col-open">Открыть</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in visiblePool"
            :key="c.nm_id"
            :class="{
              'page-pick__row--picked': isCandidate(c.nm_id),
              'page-pick__row--disabled': !c.can_attach,
            }"
          >
            <td class="text-center">
              <input
                type="checkbox"
                :checked="isCandidate(c.nm_id)"
                :disabled="!c.can_attach"
                :title="c.can_attach ? '' : (c.is_own ? 'Наша карточка — привязка недоступна' : 'Скрыта — сначала верните в «Собранных»')"
                @change="toggleCandidate(c)"
              />
            </td>
            <td>
              <div class="page-competitor__product">
                <img :src="c.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb" loading="lazy" />
                <div class="page-competitor__product-text">
                  <div class="page-competitor__product-title" :title="c.title || ''">{{ c.title || '—' }}</div>
                  <div class="page-competitor__product-sub">
                    <a
                      :href="`https://www.wildberries.ru/catalog/${c.nm_id}/detail.aspx`"
                      target="_blank"
                      rel="noopener"
                      class="page-competitor__wb-link"
                    >WB: {{ c.nm_id }}</a>
                    <span v-if="c.brand"> · {{ c.brand }}</span>
                    <span v-if="c.seller && c.seller !== c.brand"> · {{ c.seller }}</span>
                    <span v-if="c.price"> · {{ c.price }} ₽</span>
                  </div>
                  <div v-if="c.sources.length" class="page-competitor__product-sub">
                    источник: {{ c.sources.join(', ') }}
                  </div>
                </div>
              </div>
            </td>
            <td class="text-center">
              <span class="badge" :class="c.desc_len >= descMinLen ? 'bg-success' : 'bg-danger'">{{ c.desc_len }}</span>
            </td>
            <td class="text-center">
              <span class="badge" :class="c.chars_cnt ? 'bg-success' : 'bg-light text-dark'">{{ c.chars_cnt }}</span>
            </td>
            <td class="page-pick__rec">
              <template v-if="c.rec_cnt">
                <span class="badge bg-info text-dark" :title="`рекомендуют конкурентов: ${c.rec_cnt}`">
                  {{ c.rec_cnt }}
                </span>
                <div class="page-pick__rec-list">
                  <div
                    v-for="(g, gi) in recGroups(c)"
                    :key="gi"
                    class="page-pick__rec-group"
                  >
                    <span
                      class="page-pick__rec-src"
                      title="Наша карточка-источник, к которой привязаны эти конкуренты"
                    >← {{ g.sources.length ? g.sources.join(', ') : 'источник ?' }}:</span>
                    <span
                      v-for="(r, i) in g.items"
                      :key="r.nm_id"
                      class="page-pick__rec-id"
                    >
                      <a
                        :href="`/wb/detail?nm_id=${r.nm_id}`"
                        target="_blank"
                        class="page-pick__rec-link"
                        :title="r.title || `конкурент ${r.nm_id}`"
                      >{{ r.nm_id }}</a><span v-if="i < g.items.length - 1">,</span>
                    </span>
                  </div>
                  <div
                    v-if="c.rec_cnt > (c.recommended_by_cards || []).length"
                    class="page-pick__rec-more"
                  >
                    +{{ c.rec_cnt - (c.recommended_by_cards || []).length }} ещё
                  </div>
                </div>
              </template>
              <span v-else class="page-competitor__dash">—</span>
            </td>
            <td>
              <div class="page-pick__badges">
                <span v-if="c.in_a" class="badge bg-primary">конкурент выбранных</span>
                <span v-if="c.rec_cnt" class="badge bg-info text-dark">рекомендован конкурентом</span>
                <span v-if="!c.has_content" class="badge bg-warning text-dark">нет контента</span>
                <span v-if="c.is_hidden" class="badge bg-secondary">скрыта</span>
                <span v-if="c.is_own" class="badge bg-warning text-dark">наша карточка</span>
                <span v-if="isAttachedToTarget(c)" class="badge bg-success">уже привязан к цели</span>
              </div>
            </td>
            <td class="page-pick__attach">
              <template v-if="visibleAttached(c).length">
                <a
                  v-for="a in visibleAttached(c).slice(0, 4)"
                  :key="a.nm_id"
                  :href="`/wb/detail?nm_id=${a.nm_id}`"
                  target="_blank"
                  class="badge bg-primary page-pick__attach-tag"
                  :title="a.title || ''"
                >{{ a.nm_id }}</a>
                <span v-if="visibleAttached(c).length > 4" class="page-pick__muted">+{{ visibleAttached(c).length - 4 }}</span>
              </template>
              <span v-else class="text-muted small">не привязан</span>
            </td>
            <td class="text-center">
              <span
                v-if="c.queue_status"
                class="badge"
                :class="queueClass(c.queue_status)"
                :title="c.queue_error || (c.queue_processed_at ? 'обработано: ' + c.queue_processed_at : '')"
              >{{ queueLabel(c.queue_status) }}</span>
              <span v-else class="page-competitor__dash">—</span>
            </td>
            <td class="text-center">
              <button
                type="button"
                class="btn btn-sm btn-outline-secondary"
                title="Открыть карточку конкурента"
                @click="openDetails(c)"
              >
                <i class="bi bi-eye"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- нижняя панель -->
    <div v-if="selectedCandidates.length" class="page-pick__bar">
      <div class="page-pick__bar-info">
        <div>
          Выбрано конкурентов: <b>{{ selectedCandidates.length }}</b>
          · целей: <b>{{ selectedTargets.length }}</b>
        </div>
        <div class="page-pick__preview">
          добавится: <b>{{ preview.added }}</b>
          · уже есть: <b>{{ preview.exists }}</b>
          · пропущено: <b>{{ preview.skipped }}</b>
        </div>
      </div>
      <div class="page-pick__bar-actions">
        <span v-if="!selectedTargets.length" class="page-pick__muted">Выберите цели в шаге 3</span>
        <button
          class="btn btn-sm btn-success"
          :disabled="attaching || !selectedTargets.length || !preview.added"
          @click="attachSelected"
        >
          <span v-if="attaching" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-link-45deg"></i>
          Привязать выбранные
        </button>
        <button class="btn btn-sm btn-outline-secondary" :disabled="attaching" @click="selectedIds = []">
          Снять выбор
        </button>
      </div>
    </div>

    <CompetitorDetailsModal
      :open="detailsOpen"
      :nm-id="activeCandidate?.nm_id"
      scope="pick"
      @close="detailsOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-pick.css'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  competitorsNewcardApi,
  type PickAttachedCard,
  type PickCandidate,
  type PickCard,
  type PickMode,
  type PickRecommendedBy,
  type PickSort,
} from '../api/competitorsNewcard'
import CompetitorDetailsModal from '../components/competitors/CompetitorDetailsModal.vue'

const route = useRoute()
const router = useRouter()

const cards = ref<PickCard[]>([])
const cardQ = ref('')
const cardsLoading = ref(false)
const selectedSources = ref<PickCard[]>([])

const targetOptions = ref<PickCard[]>([])
const targetQ = ref('')
const targetLoading = ref(false)
const selectedTargets = ref<PickCard[]>([])

const mode = ref<PickMode>('recommend')
const pool = ref<PickCandidate[]>([])
const poolTotal = ref(0)
const poolQ = ref('')
const onlyContent = ref(false)
const onlyRecommended = ref(false)
const hideAttachedAll = ref(false)
const sortMode = ref<PickSort>('relevance')
const poolLoading = ref(false)
const selectedIds = ref<number[]>([])
const descMinLen = ref(50)

const detailsOpen = ref(false)
const activeCandidate = ref<PickCandidate | null>(null)

const error = ref('')
const notice = ref('')
const attaching = ref(false)

let cardTimer: ReturnType<typeof setTimeout> | null = null
let targetTimer: ReturnType<typeof setTimeout> | null = null
let poolTimer: ReturnType<typeof setTimeout> | null = null
let cardSeq = 0
let targetSeq = 0
let poolSeq = 0
let restoring = true
let ready = false

function queryIds(value: unknown): number[] {
  const raw = Array.isArray(value) ? value.join(',') : String(value ?? '')
  const out: number[] = []
  for (const part of raw.split(/[,;\s]+/)) {
    const n = Number(part)
    if (Number.isInteger(n) && n > 0 && !out.includes(n)) out.push(n)
  }
  return out
}

function queryStr(value: unknown): string {
  return String(Array.isArray(value) ? value[0] ?? '' : value ?? '').trim()
}

function queryBool(value: unknown): boolean {
  const s = queryStr(value).toLowerCase()
  return s === '1' || s === 'true' || s === 'yes' || s === 'on'
}

/** Состояние страницы в URL: F5 и ссылки восстанавливают выбор и фильтры. */
function syncUrl() {
  if (!ready) return
  const q: Record<string, string> = {}
  if (selectedSources.value.length) q.source_nm_ids = selectedSources.value.map((c) => c.nmID).join(',')
  if (selectedTargets.value.length) q.target_nm_ids = selectedTargets.value.map((c) => c.nmID).join(',')
  if (selectedIds.value.length) q.candidate_nm_ids = selectedIds.value.join(',')
  if (cardQ.value.trim()) q.card_q = cardQ.value.trim()
  if (targetQ.value.trim()) q.target_q = targetQ.value.trim()
  if (poolQ.value.trim()) q.pool_q = poolQ.value.trim()
  if (mode.value !== 'recommend') q.mode = mode.value
  if (onlyContent.value) q.only_content = '1'
  if (onlyRecommended.value) q.only_recommended = '1'
  if (hideAttachedAll.value) q.hide_attached_all = '1'
  if (sortMode.value !== 'relevance') q.sort = sortMode.value
  router.replace({ query: q }).catch(() => {})
}

const canLoadPool = computed(() => mode.value === 'captured' || selectedSources.value.length > 0)
/** Скрыть кандидатов, которые уже привязаны ко всем выбранным целям. */
const visiblePool = computed(() => {
  if (!hideAttachedAll.value || !selectedTargets.value.length) return pool.value
  return pool.value.filter((c) => !selectedTargets.value.every((t) => isAttachedTo(c, t.nmID)))
})
const selectablePool = computed(() => visiblePool.value.filter((c) => c.can_attach))
const allSelected = computed(() =>
  selectablePool.value.length > 0 && selectablePool.value.every((c) => isCandidate(c.nm_id)),
)
const selectedCandidates = computed(() => visiblePool.value.filter((c) => isCandidate(c.nm_id)))

const preview = computed(() => {
  let added = 0
  let exists = 0
  let skipped = 0
  for (const c of selectedCandidates.value) {
    for (const t of selectedTargets.value) {
      if (isAttachedTo(c, t.nmID)) exists++
      else if (!c.can_attach) skipped++
      else added++
    }
  }
  return { added, exists, skipped }
})

function isSource(nm: number): boolean {
  return selectedSources.value.some((c) => c.nmID === nm)
}

function isTarget(nm: number): boolean {
  return selectedTargets.value.some((c) => c.nmID === nm)
}

function isCandidate(nm: number): boolean {
  return selectedIds.value.includes(nm)
}

function isAttachedTo(c: PickCandidate, nm: number): boolean {
  return c.attached_to.some((a) => Number(a.nm_id) === nm)
}

function isAttachedToTarget(c: PickCandidate): boolean {
  return selectedTargets.value.some((t) => isAttachedTo(c, t.nmID))
}

/** В колонке «Привязка» показываем только выбранные источники и цели, а не всю базу компании. */
function visibleAttached(c: PickCandidate): PickAttachedCard[] {
  const ids = new Set<number>([
    ...selectedSources.value.map((x) => Number(x.nmID)),
    ...selectedTargets.value.map((x) => Number(x.nmID)),
  ])
  return c.attached_to.filter((a) => ids.has(Number(a.nm_id)))
}

/** Группируем рекомендовавших конкурентов по нашей source-карточке. */
function recGroups(c: PickCandidate) {
  const groups: Array<{ sources: number[]; items: PickRecommendedBy[] }> = []
  for (const r of c.recommended_by_cards || []) {
    const key = r.source_nm_ids.join(',')
    let g = groups.find((x) => x.sources.join(',') === key)
    if (!g) {
      g = { sources: r.source_nm_ids, items: [] }
      groups.push(g)
    }
    g.items.push(r)
  }
  return groups
}

function openDetails(c: PickCandidate) {
  activeCandidate.value = c
  detailsOpen.value = true
}

function useTargetsAsSources() {
  if (!selectedTargets.value.length) return
  selectedSources.value = [...selectedTargets.value]
  selectedIds.value = []
  loadPool()
}

function toggleSource(c: PickCard) {
  const i = selectedSources.value.findIndex((x) => x.nmID === c.nmID)
  if (i >= 0) selectedSources.value.splice(i, 1)
  else selectedSources.value.push(c)
}

function removeSource(c: PickCard) {
  selectedSources.value = selectedSources.value.filter((x) => x.nmID !== c.nmID)
}

function toggleTarget(c: PickCard) {
  const i = selectedTargets.value.findIndex((x) => x.nmID === c.nmID)
  if (i >= 0) selectedTargets.value.splice(i, 1)
  else selectedTargets.value.push(c)
}

function removeTarget(c: PickCard) {
  selectedTargets.value = selectedTargets.value.filter((x) => x.nmID !== c.nmID)
}

function toggleCandidate(c: PickCandidate) {
  if (!c.can_attach) return
  const i = selectedIds.value.indexOf(c.nm_id)
  if (i >= 0) selectedIds.value.splice(i, 1)
  else selectedIds.value.push(c.nm_id)
}

function selectAll() {
  if (allSelected.value) {
    selectedIds.value = []
    return
  }
  selectedIds.value = selectablePool.value.map((c) => c.nm_id)
}

function setMode(m: PickMode) {
  if (mode.value === m) return
  mode.value = m
  pool.value = []
  poolTotal.value = 0
  selectedIds.value = []
}

function queueLabel(s: string): string {
  if (s === 'pending') return 'в очереди'
  if (s === 'processing') return 'собираем'
  if (s === 'done') return 'готово'
  if (s === 'error') return 'ошибка'
  if (s === 'need_update') return 'назначено'
  return s
}

function queueClass(s: string): string {
  if (s === 'pending') return 'bg-warning text-dark'
  if (s === 'processing') return 'bg-info text-dark'
  if (s === 'done') return 'bg-success'
  if (s === 'error') return 'bg-danger'
  if (s === 'need_update') return 'bg-primary'
  return 'bg-light text-dark'
}

async function loadCards() {
  const my = ++cardSeq
  const q = cardQ.value.trim()
  if (!q) {
    cards.value = []
    cardsLoading.value = false
    return
  }
  cardsLoading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.pickCards(q, 50)
    if (my !== cardSeq) return
    cards.value = d.items || []
    descMinLen.value = d.desc_min_len || descMinLen.value
  } catch (e: any) {
    if (my !== cardSeq) return
    error.value = e?.response?.data?.detail || 'Не удалось загрузить наши карточки'
  } finally {
    if (my === cardSeq) cardsLoading.value = false
  }
}

async function loadTargets() {
  const my = ++targetSeq
  const q = targetQ.value.trim()
  if (!q) {
    targetOptions.value = []
    targetLoading.value = false
    return
  }
  targetLoading.value = true
  try {
    const d = await competitorsNewcardApi.pickCards(q, 50)
    if (my !== targetSeq) return
    targetOptions.value = d.items || []
  } catch (e: any) {
    if (my !== targetSeq) return
    targetOptions.value = []
    error.value = e?.response?.data?.detail || 'Не удалось загрузить наши карточки'
  } finally {
    if (my === targetSeq) targetLoading.value = false
  }
}

async function ensureCard(nm: number): Promise<PickCard | null> {
  let c = cards.value.find((x) => Number(x.nmID) === nm)
    || targetOptions.value.find((x) => Number(x.nmID) === nm)
  if (c) return c
  try {
    const d = await competitorsNewcardApi.pickCards(String(nm), 10)
    c = (d.items || []).find((x) => Number(x.nmID) === nm) || null
  } catch {
    c = null
  }
  return c
}

async function loadPool() {
  if (!canLoadPool.value) {
    error.value = 'Выберите хотя бы одну нашу карточку в шаге 1'
    return
  }
  const my = ++poolSeq
  poolLoading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.pickCandidates({
      source_nm_ids: selectedSources.value.map((c) => c.nmID).join(','),
      mode: mode.value,
      q: poolQ.value.trim(),
      only_content: onlyContent.value,
      only_recommended: onlyRecommended.value,
      limit: 300,
      sort: sortMode.value,
    })
    if (my !== poolSeq) return
    pool.value = d.items || []
    poolTotal.value = d.total || 0
    descMinLen.value = d.desc_min_len || descMinLen.value
    const ids = new Set(visiblePool.value.map((c) => c.nm_id))
    selectedIds.value = selectedIds.value.filter((id) => ids.has(id))
  } catch (e: any) {
    if (my !== poolSeq) return
    error.value = e?.response?.data?.detail || 'Не удалось собрать пул'
    pool.value = []
    poolTotal.value = 0
  } finally {
    if (my === poolSeq) poolLoading.value = false
  }
}

async function attachSelected() {
  if (attaching.value || !selectedCandidates.value.length || !selectedTargets.value.length) return
  attaching.value = true
  error.value = ''
  notice.value = ''
  try {
    const res = await competitorsNewcardApi.pickAttach({
      nm_ids: selectedCandidates.value.map((c) => c.nm_id),
      target_nm_ids: selectedTargets.value.map((c) => c.nmID),
      mode: mode.value,
    })
    const parts = [`привязано: ${res.added}`]
    if (res.exists) parts.push(`уже было: ${res.exists}`)
    if (res.skipped) parts.push(`пропущено: ${res.skipped}`)
    notice.value = parts.join(', ')
    selectedIds.value = []
    await Promise.all([loadCards(), loadTargets(), loadPool()])
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось привязать конкурентов'
  } finally {
    attaching.value = false
  }
}

watch(cardQ, (v) => {
  if (restoring) return
  if (cardTimer) clearTimeout(cardTimer)
  const q = String(v || '').trim()
  if (q.length === 1) return
  cardTimer = setTimeout(loadCards, 300)
})

watch(targetQ, (v) => {
  if (restoring) return
  if (targetTimer) clearTimeout(targetTimer)
  const q = String(v || '').trim()
  if (q.length === 1) return
  targetTimer = setTimeout(loadTargets, 300)
})

watch(poolQ, (v) => {
  if (restoring) return
  if (poolTimer) clearTimeout(poolTimer)
  const q = String(v || '').trim()
  if (q.length === 1 || !canLoadPool.value) return
  poolTimer = setTimeout(loadPool, 450)
})

watch(
  [selectedSources, selectedTargets, selectedIds, cardQ, targetQ, poolQ,
    mode, onlyContent, onlyRecommended, hideAttachedAll, sortMode],
  () => syncUrl(),
  { deep: true },
)

watch([hideAttachedAll, selectedTargets], () => {
  if (!ready) return
  const ids = new Set(visiblePool.value.map((c) => c.nm_id))
  selectedIds.value = selectedIds.value.filter((id) => ids.has(id))
}, { deep: true })

onMounted(async () => {
  const q = route.query
  // Совместимость со старыми ссылками: source_nm_id / target_nm_id.
  const sourceIds = queryIds(q.source_nm_ids || q.source_nm_id)
  const targetIds = queryIds(q.target_nm_ids || q.target_nm_id)
  const candidateIds = queryIds(q.candidate_nm_ids)

  cardQ.value = queryStr(q.card_q)
  targetQ.value = queryStr(q.target_q)
  poolQ.value = queryStr(q.pool_q)
  onlyContent.value = queryBool(q.only_content)
  onlyRecommended.value = queryBool(q.only_recommended)
  hideAttachedAll.value = queryBool(q.hide_attached_all)

  const qMode = queryStr(q.mode)
  if (qMode === 'captured' || qMode === 'competitors' || qMode === 'recommend') mode.value = qMode
  const qSort = queryStr(q.sort)
  if (qSort === 'relevance' || qSort === 'title_asc' || qSort === 'title_desc') sortMode.value = qSort

  if (cardQ.value) await loadCards()
  if (targetQ.value) await loadTargets()

  const missing: number[] = []
  if (sourceIds.length) {
    const found = await Promise.all(sourceIds.map(ensureCard))
    selectedSources.value = found.filter((x): x is PickCard => !!x)
    sourceIds.forEach((id, i) => { if (!found[i]) missing.push(id) })
  }
  if (targetIds.length) {
    const found = await Promise.all(targetIds.map(ensureCard))
    selectedTargets.value = found.filter((x): x is PickCard => !!x)
    targetIds.forEach((id, i) => { if (!found[i]) missing.push(id) })
  }
  selectedIds.value = candidateIds
  restoring = false
  ready = true
  syncUrl()

  if (canLoadPool.value) await loadPool()
  if (missing.length && !error.value) {
    error.value = `Наши карточки не найдены: ${missing.join(', ')}`
  }
  syncUrl()
})

onBeforeUnmount(() => {
  if (cardTimer) clearTimeout(cardTimer)
  if (targetTimer) clearTimeout(targetTimer)
  if (poolTimer) clearTimeout(poolTimer)
  cardSeq++
  targetSeq++
  poolSeq++
})
</script>
