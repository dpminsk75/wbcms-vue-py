<template>
  <div class="container-xxl page-competitor page-positions">
    <!-- Шапка: название + варианты отчёта (как в FBS — варианты справа) -->
    <div class="page-positions__head">
      <h2 class="page-competitor__title">Выдача WB</h2>
      <ul class="nav nav-pills page-positions__variants">
        <li v-for="v in variants" :key="v.id" class="nav-item">
          <button
            class="nav-link"
            :class="{ active: tab === v.id }"
            @click="setTab(v.id)"
          >{{ v.label }}</button>
        </li>
      </ul>
    </div>

    <!-- Фильтры: компактно, как на рабочем месте FBS -->
    <div class="page-positions__filter-card mb-3">
      <div class="page-positions__presets mb-2">
        <button
          v-for="p in presets"
          :key="p.id"
          class="btn btn-sm"
          :class="activePreset === p.id ? 'btn-primary' : 'btn-outline-secondary'"
          @click="applyPreset(p.id)"
        >{{ p.label }}</button>
      </div>
      <div class="row g-2 align-items-end">
        <div class="col-md-2">
          <label class="form-label mb-1 page-positions__label">Дата с</label>
          <WbDateInput v-model="dateFrom" />
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-positions__label">Дата по</label>
          <WbDateInput v-model="dateTo" />
        </div>
        <div class="col-md-4">
          <label class="form-label mb-1 page-positions__label">Фраза</label>
          <input
            v-model="q"
            class="form-control form-control-sm"
            placeholder="например: календарь 2027"
            @keyup.enter="load"
          />
        </div>
        <div class="col-md-4 d-flex gap-2">
          <button class="btn btn-primary" @click="load">Применить</button>
          <button class="btn btn-light" @click="reset">Сбросить</button>
          <span class="badge bg-secondary align-self-center ms-auto">
            {{ tab === 'phrases' ? 'Запросов: ' + phrases.length : tab === 'cards' ? 'Наших карточек: ' + cards.length : 'Ниш: ' + niches.length }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="loading" class="text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка…
    </div>

    <!-- ================= по запросам ================= -->
    <template v-else-if="tab === 'phrases'">
      <!-- список запросов -->
      <template v-if="!detail">
        <div v-if="!phrases.length" class="alert alert-info">
          Сохранённых запросов пока нет. Откройте поиск WB — расширение сохранит выдачу.
        </div>

      <div v-if="phrases.length" class="page-positions__requeue">
        <label class="page-positions__check">
          <input type="checkbox" :checked="allSelected" @change="toggleAll" />
          <span>выбрать все</span>
        </label>
        <button
          class="btn btn-sm btn-primary"
          :disabled="!selected.length || requeueBusy"
          title="Отправить отмеченные фразы в расширение — оно пересоберёт выдачу по ним"
          @click="sendRequeue"
        >
          <i class="bi bi-arrow-repeat"></i>
          Отправить на пересборку<span v-if="selected.length"> ({{ selected.length }})</span>
        </button>
        <span v-if="requeueNotice" class="page-positions__note">{{ requeueNotice }}</span>
      </div>

        <table v-if="phrases.length" class="wb-admin-table page-positions__grid">
          <thead>
            <tr>
              <th style="width: 28px"></th>
              <th title="Поисковая фраза, по которой собирали выдачу WB">Фраза</th>
              <th class="text-center" title="Сколько раз мы заходили в поиск по этой фразе">Сборов</th>
              <th class="text-center" title="В скольких днях были наблюдения">Дней</th>
              <th class="text-center" title="Сколько разных товаров было в выдаче">Товаров</th>
              <th class="text-center" title="Сколько наших товаров было в выдаче (наведи — список)">Наших</th>
              <th title="Когда собирали">Период</th>
              <th title="Кто и с какого устройства собирал">Кто собрал</th>
              <th title="Пересборка выдачи расширением">Пересборка</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in phrases"
              :key="r.phrase"
              class="page-positions__row"
              @click="openPhrase(r)"
            >
              <td>
                <input
                  type="checkbox"
                  :checked="isSelected(r.phrase)"
                  @click.stop
                  @change="toggleOne(r.phrase)"
                />
              </td>
              <td>
                <span class="page-positions__phrase">{{ r.phrase }}</span>
                <div v-if="(r.phrase_variants || []).length > 1" class="page-positions__note">
                  варианты: {{ r.phrase_variants.join(' | ') }}
                </div>
              </td>
              <td class="text-center">{{ r.collections ?? r.days }}</td>
              <td class="text-center">{{ r.days }}</td>
              <td class="text-center">{{ r.products }}</td>
              <td class="text-center">
                <span v-if="!r.sources.length" class="page-positions__note">—</span>
                <span v-else class="page-positions__ours" :title="sourcesTitle(r)">
                  {{ r.sources.length }}
                </span>
              </td>
              <td class="page-positions__date">{{ period(r) }}</td>
              <td>
                <span v-for="u in r.saved_by" :key="u.id" class="page-positions__note">
                  {{ u.username || ('user ' + u.id) }}
                </span>
                <span v-if="!r.saved_by.length" class="page-positions__note">—</span>
              </td>
              <td>
                <span
                  v-if="r.requeue_status"
                  class="badge"
                  :class="requeueBadge(r.requeue_status)"
                  :title="r.requeue_error || (r.requeue_at ? 'обновлено: ' + r.requeue_at : '')"
                >{{ requeueLabel(r.requeue_status) }}</span>
                <span v-else class="page-positions__note">—</span>
              </td>
              <td class="page-positions__chev"><i class="bi bi-chevron-right"></i></td>
            </tr>
          </tbody>
        </table>
      </template>

      <!-- Выдача по запросу: строка = дата сбора, в ней карточки выдачи -->
      <div v-else class="page-positions__detail">
        <div class="page-positions__detail-head">
          <button class="btn btn-sm btn-outline-secondary" @click="closePhrase">
            <i class="bi bi-arrow-left"></i> Все запросы
          </button>
          <h3 class="page-positions__detail-title">«{{ detail.phrase }}»</h3>
          <span class="text-muted small">сборов: {{ (detail.slices || []).length }}</span>
          <div class="btn-group btn-group-sm" role="group" aria-label="Сколько карточек показывать">
            <button
              v-for="o in limitOptions"
              :key="o.value"
              class="btn"
              :class="cardLimit === o.value ? 'btn-primary' : 'btn-outline-secondary'"
              @click="cardLimit = o.value"
            >{{ o.label }}</button>
          </div>
        </div>

        <div v-if="!(detail.slices || []).length" class="alert alert-info">
          По этой фразе нет сохранённых срезов.
        </div>

        <div v-for="sl in detail.slices || []" :key="sl.stamp || sl.date" class="page-positions__slice">
          <div class="page-positions__slice-date">
            <div class="page-positions__slice-day">{{ sl.date }}</div>
            <div v-if="sl.time" class="page-positions__slice-time">{{ sl.time }}</div>
            <div class="text-muted small">товаров: {{ sl.items.length }}</div>
          </div>
          <div class="page-positions__cards">
            <WbSearchCard
              v-for="c in sliceCards(sl.items)"
              :key="c.nm_id"
              :card="c"
              @open="openCard"
            />
            <div v-if="sl.items.length > cardLimit" class="page-positions__more">
              +{{ sl.items.length - cardLimit }}
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ================= по нашим товарам ================= -->
    <template v-else-if="tab === 'cards'">
      <div class="page-positions__toolbar">
        <div class="btn-group btn-group-sm" role="group" aria-label="Сколько конкурентов показывать">
          <button
            v-for="o in topOptions"
            :key="o.value"
            class="btn"
            :class="top === o.value ? 'btn-primary' : 'btn-outline-secondary'"
            @click="setTop(o.value)"
          >{{ o.label }}</button>
        </div>
      </div>

      <div v-if="!cards.length" class="alert alert-info">
        Наблюдений по нашим карточкам пока нет — наши карточки ещё не попадали в собранную выдачу.
      </div>

      <table v-else class="wb-admin-table page-positions__grid">
        <thead>
          <tr>
            <th>Наша карточка</th>
            <th class="text-center" title="Сколько запросов, где наша карточка была в выдаче">Запросов</th>
            <th class="text-center">Дней</th>
            <th class="text-center" title="Лучшая позиция за период">Лучшая позиция</th>
            <th>Последний</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in cards"
            :key="c.nm_id"
            class="page-positions__row"
            :class="{ 'page-positions__row--active': selectedCard === c.nm_id }"
            @click="openCardById(c.nm_id)"
          >
            <td>
              <div class="page-positions__phrase">{{ c.title || ('nm ' + c.nm_id) }}</div>
              <div class="text-muted small">
                <a :href="wbUrl(c.nm_id)" target="_blank" rel="noopener">WB: {{ c.nm_id }}</a>
                <span v-if="c.brand"> · {{ c.brand }}</span>
                <span v-if="c.vendor"> · {{ c.vendor }}</span>
              </div>
            </td>
            <td class="text-center">{{ c.phrases }}</td>
            <td class="text-center">{{ c.days }}</td>
            <td class="text-center">{{ c.best_position ?? '—' }}</td>
            <td class="page-positions__date">{{ c.last_at || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <div v-if="cardDetail" class="page-positions__detail">
        <div class="page-positions__detail-head">
          <h3 class="page-positions__detail-title">
            {{ cardDetail.card.title || ('nm ' + cardDetail.card.nm_id) }}
          </h3>
          <span class="text-muted small">запросов: {{ cardDetail.phrases.length }}</span>
          <button class="btn btn-sm btn-outline-secondary ms-auto" @click="cardDetail = null">Свернуть</button>
        </div>

        <div v-if="!cardDetail.phrases.length" class="alert alert-info">
          По этой карточке наблюдений в выбранном периоде нет.
        </div>

        <div v-for="p in cardDetail.phrases" :key="p.phrase" class="page-positions__block">
          <div class="page-positions__block-head">
            <span class="page-positions__phrase">{{ p.phrase }}</span>
            <span class="badge" :class="p.last_position ? 'bg-primary' : 'bg-secondary'">
              наша позиция: {{ p.last_position ?? '—' }}
              <template v-if="p.last_position_api"> · WB: {{ p.last_position_api }}</template>
            </span>
            <span v-if="p.best_position" class="badge bg-light text-dark">лучшая: {{ p.best_position }}</span>
            <span v-if="p.best_position_api" class="badge bg-light text-dark">
              лучшая WB: {{ p.best_position_api }}
            </span>
            <span class="text-muted small">срез: {{ p.last_day || '—' }} · дней: {{ p.days.length }}</span>
          </div>

          <table class="wb-admin-table">
            <thead>
              <tr>
                <th class="text-center" title="Позиция в DOM (с рекламой)">Поз.</th>
                <th class="text-center" title="Позиция в JSON-выдаче (органика)">Поз. JSON</th>
                <th>Конкурент</th>
                <th>Продавец</th>
                <th>Цена</th>
                <th class="text-center">Рейтинг</th>
                <th class="text-center">Отзывы</th>
                <th>Бейджи</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in p.competitors" :key="`${p.phrase}-${c.nm_id}`">
                <td class="text-center">{{ c.position }}</td>
                <td class="text-center">{{ c.position_api ?? '—' }}</td>
                <td>
                  <a :href="wbUrl(c.nm_id)" target="_blank" rel="noopener">{{ c.title || ('nm ' + c.nm_id) }}</a>
                  <span class="text-muted small"> · {{ c.nm_id }}</span>
                </td>
                <td>{{ c.seller || c.brand || '—' }}</td>
                <td>{{ money(c.price) }}</td>
                <td class="text-center">{{ c.rating || '—' }}</td>
                <td class="text-center">{{ c.reviews ?? c.feedbacks ?? '—' }}</td>
                <td>
                  <span v-for="b in c.badges" :key="b" class="badge bg-warning text-dark me-1">{{ b }}</span>
                </td>
              </tr>
              <tr v-if="!p.competitors.length">
                <td colspan="8" class="text-muted">В этом срезе конкурентов не записали.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ================= ниши и реклама ================= -->
    <template v-else>
      <div class="page-positions__toolbar">
        <span class="badge bg-secondary">Снимков с рекламой: {{ adsRows.length }}</span>
      </div>

      <div v-if="!niches.length && !adsRows.length" class="alert alert-info">
        Профили ниш ещё не собраны — расширение сохранит их при первом поиске на WB.
      </div>

      <h3 v-if="niches.length" class="page-positions__section">Профиль ниш (фильтры выдачи)</h3>
      <table v-if="niches.length" class="wb-admin-table page-positions__grid">
        <thead>
          <tr>
            <th>Фраза</th>
            <th class="text-center">Объём ниши</th>
            <th>Цены, ₽</th>
            <th class="text-center">Доставка, ч</th>
            <th>Бренды</th>
            <th>Продавцы</th>
            <th>Акции</th>
            <th>Фасеты</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="n in niches" :key="n.phrase + n.date">
            <td>
              <div class="page-positions__phrase">{{ n.phrase }}</div>
              <div class="text-muted small">{{ n.date }}</div>
              <div v-if="(n.phrase_variants || []).length" class="text-muted small">
                варианты: {{ n.phrase_variants.join(' | ') }}
              </div>
            </td>
            <td class="text-center">{{ n.total ?? '—' }}</td>
            <td>{{ n.price_min ?? '—' }} … {{ n.price_max ?? '—' }}</td>
            <td class="text-center">{{ n.delivery_min ?? '—' }} … {{ n.delivery_max ?? '—' }}</td>
            <td class="small">{{ n.brands.map((b) => b.name).join(', ') || '—' }}</td>
            <td class="small">{{ n.sellers.map((s) => s.name).join(', ') || '—' }}</td>
            <td class="small">
              <span v-if="n.sale_factions.length" class="badge bg-warning text-dark">
                {{ n.sale_factions.map((f) => f.name).join(', ') }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="small">
              <span
                v-for="(f, k) in n.facets || {}"
                :key="k"
                class="badge bg-light text-dark me-1"
                :title="(f.items || []).map((i) => i.name).join(', ')"
              >{{ f.name || k }}: {{ (f.items || []).length }}</span>
              <span v-if="!n.facets || !Object.keys(n.facets).length" class="text-muted">—</span>
            </td>
          </tr>
        </tbody>
      </table>

      <h3 v-if="adsRows.length" class="page-positions__section">Реклама и полки в поиске</h3>
      <div v-for="a in adsRows" :key="a.phrase + a.date" class="page-positions__block">
        <div class="page-positions__block-head">
          <span class="page-positions__phrase">{{ a.phrase }}</span>
          <span class="badge bg-secondary">баннеров: {{ a.banner_cnt }}</span>
          <span class="badge bg-secondary">полок: {{ a.shelf_cnt }}</span>
          <span class="badge bg-secondary">товаров в полках: {{ a.shelf_products_cnt }}</span>
          <span class="text-muted small">{{ a.date }}</span>
        </div>
        <table v-if="a.banners.length" class="wb-admin-table">
          <thead>
            <tr>
              <th>Рекламодатель</th>
              <th>CPM</th>
              <th>Тип</th>
              <th>ЕРИД</th>
              <th>Ссылка</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(b, i) in a.banners" :key="i">
              <td class="small">{{ b.mark || '—' }}</td>
              <td class="small">{{ b.cpm || '—' }}</td>
              <td class="small">{{ b.type || '—' }}</td>
              <td class="small">{{ b.erid || '—' }}</td>
              <td class="small">
                <a v-if="b.url" :href="'https://www.wildberries.ru' + b.url" target="_blank" rel="noopener">открыть</a>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-for="(s, i) in a.shelfs" :key="'s' + i" class="page-positions__history">
          <span class="badge bg-light text-dark">{{ s.title || 'полка' }}</span>
          <span class="badge bg-light text-dark">{{ s.mark }}</span>
          <span class="badge bg-light text-dark">товаров: {{ s.products.length }}</span>
        </div>
      </div>
    </template>

    <!-- Клик по конкуренту — досье конкурента; клик по нашей карточке — сводка -->
    <CompetitorDetailsModal
      :open="competitorNm !== null"
      :nm-id="competitorNm"
      @close="competitorNm = null"
    />
    <OurCardModal
      :open="ourCardNm !== null"
      :nm-id="ourCardNm"
      :date-from="dateFrom"
      :date-to="dateTo"
      @close="ourCardNm = null"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import WbDateInput from '@/components/common/WbDateInput.vue'
import WbSearchCard from '@/components/positions/WbSearchCard.vue'
import OurCardModal from '@/components/positions/OurCardModal.vue'
import CompetitorDetailsModal from '@/components/competitors/CompetitorDetailsModal.vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'
import {
  competitorsPositionsApi,
  type PositionsPhraseRow,
  type PositionsPhraseDetail,
  type PositionsCardRow,
  type PositionsCardDetail,
  type PositionsItem,
  type NicheRow,
  type SearchAdsRow,
} from '@/api/competitorsPositions'

const { fmt0 } = useMoneyFmt()

type Tab = 'phrases' | 'cards' | 'niches'

const variants: Array<{ id: Tab; label: string }> = [
  { id: 'phrases', label: 'По запросам' },
  { id: 'cards', label: 'По нашим товарам' },
  { id: 'niches', label: 'Ниши и реклама' },
]

const tab = ref<Tab>('phrases')
const dateFrom = ref('')
const dateTo = ref('')
const q = ref('')
const loading = ref(false)
const error = ref('')

const phrases = ref<PositionsPhraseRow[]>([])
const cards = ref<PositionsCardRow[]>([])
const niches = ref<NicheRow[]>([])
const adsRows = ref<SearchAdsRow[]>([])

const selectedPhrase = ref('')
const detail = ref<PositionsPhraseDetail | null>(null)

const selectedCard = ref<number | null>(null)
const cardDetail = ref<PositionsCardDetail | null>(null)

// сколько карточек показывать в строке среза
const cardLimit = ref(10)
const limitOptions = [
  { value: 5, label: '5' },
  { value: 10, label: '10' },
  { value: 15, label: '15' },
  { value: 25, label: '25' },
  { value: 40, label: '40' },
  { value: 0, label: 'Все' },
]

// ТОП-6 / ТОП-12 / Все (по нашим товарам)
const top = ref(12)
const topOptions = [
  { value: 6, label: 'ТОП-6' },
  { value: 12, label: 'ТОП-12' },
  { value: 0, label: 'Все' },
]

// --- пересборка выдачи по отмеченным фразам ---
const selected = ref<string[]>([])
const requeueBusy = ref(false)
const requeueNotice = ref('')

const REQUEUE_LABEL: Record<string, string> = {
  pending: 'в очереди', processing: 'собираем', done: 'готово', error: 'ошибка',
}
const REQUEUE_BADGE: Record<string, string> = {
  pending: 'bg-secondary', processing: 'bg-info text-dark', done: 'bg-success', error: 'bg-danger',
}
const requeueLabel = (s: string) => REQUEUE_LABEL[s] || s
const requeueBadge = (s: string) => REQUEUE_BADGE[s] || 'bg-light text-dark'

function isSelected(phrase: string): boolean {
  return selected.value.includes(phrase)
}
function toggleOne(phrase: string) {
  selected.value = isSelected(phrase)
    ? selected.value.filter((p) => p !== phrase)
    : [...selected.value, phrase]
}
const allSelected = computed(
  () => phrases.value.length > 0 && phrases.value.every((p) => isSelected(p.phrase)),
)
function toggleAll() {
  selected.value = allSelected.value ? [] : phrases.value.map((p) => p.phrase)
}

async function sendRequeue() {
  if (!selected.value.length || requeueBusy.value) return
  requeueBusy.value = true
  requeueNotice.value = ''
  try {
    const r = await competitorsPositionsApi.requeue({ phrases: selected.value })
    const skipped = r.skipped?.length ? `, не влезло: ${r.skipped.length}` : ''
    requeueNotice.value = `в очереди: ${r.queued}${skipped}`
    selected.value = []
    await load()
  } catch (e: any) {
    requeueNotice.value = errText(e)
  } finally {
    requeueBusy.value = false
  }
}

const competitorNm = ref<number | null>(null)
const ourCardNm = ref<number | null>(null)

function money(v: any): string {
  if (v == null || v === '' || Number(v) === 0) return '—'
  return `${fmt0(v)} ₽`
}
function wbUrl(nm: number): string {
  return `https://www.wildberries.ru/catalog/${nm}/detail.aspx`
}
function sliceCards(items: PositionsItem[]): PositionsItem[] {
  return cardLimit.value > 0 ? items.slice(0, cardLimit.value) : items
}
function fmtDay(d: string): string {
  if (!d) return '—'
  const parts = d.split('-')
  return parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : d
}
function period(r: PositionsPhraseRow): string {
  if (!r.first_at) return '—'
  if (r.first_at === r.last_at) return fmtDay(r.first_at)
  return `${fmtDay(r.first_at)} — ${fmtDay(r.last_at)}`
}
function sourcesTitle(r: PositionsPhraseRow): string {
  return r.sources.map((s) => `${s.nm_id} · ${s.title || ''}`).join('\n')
}
function errText(e: any): string {
  const d = e?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d) && d.length) {
    const it = d[0] || {}
    const loc = Array.isArray(it.loc) ? it.loc.join('.') : ''
    const msg = it.msg || JSON.stringify(it)
    return loc ? `${msg} (${loc})` : msg
  }
  return String(e?.message || e)
}

function fmtD(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
function initRange() {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 29)
  dateTo.value = fmtD(to)
  dateFrom.value = fmtD(from)
}

/* пресеты периода (как в WbUniversalFilter) */
const activePreset = ref('30')
const presets = [
  { id: 'today', label: 'Сегодня' },
  { id: 'yesterday', label: 'Вчера' },
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
  { id: '365', label: '365 дней' },
  { id: 'year', label: 'С начала года' },
]

function applyPreset(id: string) {
  activePreset.value = id
  const t = new Date()
  if (id === 'today') {
    dateFrom.value = fmtD(t)
    dateTo.value = fmtD(t)
  } else if (id === 'yesterday') {
    const y = new Date()
    y.setDate(y.getDate() - 1)
    dateFrom.value = fmtD(y)
    dateTo.value = fmtD(y)
  } else if (id === 'year') {
    dateFrom.value = fmtD(new Date(t.getFullYear(), 0, 1))
    dateTo.value = fmtD(t)
  } else {
    const f = new Date()
    f.setDate(f.getDate() - (Number(id) - 1))
    dateFrom.value = fmtD(f)
    dateTo.value = fmtD(t)
  }
  load()
}

function setTab(t: Tab) {
  tab.value = t
  load()
}

function setTop(v: number) {
  top.value = v
  if (selectedCard.value) openCardById(selectedCard.value)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { date_from: dateFrom.value || undefined, date_to: dateTo.value || undefined }
    if (tab.value === 'phrases') {
      const res = await competitorsPositionsApi.phrases({ ...params, q: q.value || undefined })
      phrases.value = res.items || []
      if (selectedPhrase.value && !phrases.value.some((p) => p.phrase === selectedPhrase.value)) {
        selectedPhrase.value = ''
        detail.value = null
      }
    } else if (tab.value === 'cards') {
      const res = await competitorsPositionsApi.cards(params)
      cards.value = res.items || []
    } else {
      const [n, a] = await Promise.all([
        competitorsPositionsApi.niches(params),
        competitorsPositionsApi.ads(params),
      ])
      niches.value = n.items || []
      adsRows.value = a.items || []
    }
  } catch (e: any) {
    error.value = errText(e)
  } finally {
    loading.value = false
  }
}

async function openPhrase(r: PositionsPhraseRow) {
  if (selectedPhrase.value === r.phrase) {
    closePhrase()
    return
  }
  selectedPhrase.value = r.phrase
  await loadPhrase()
}

function closePhrase() {
  selectedPhrase.value = ''
  detail.value = null
}

async function loadPhrase() {
  if (!selectedPhrase.value) return
  try {
    const res = await competitorsPositionsApi.phrase({
      phrase: selectedPhrase.value,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
    })
    detail.value = res
  } catch (e: any) {
    error.value = errText(e)
  }
}

function openCard(c: PositionsItem) {
  if (c.is_ours) {
    ourCardNm.value = c.nm_id
  } else {
    competitorNm.value = c.nm_id
  }
}

async function openCardById(nm: number) {
  try {
    const res = await competitorsPositionsApi.card({
      nm_id: nm,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      top: top.value,
    })
    cardDetail.value = res
  } catch (e: any) {
    error.value = errText(e)
  }
}

function reset() {
  activePreset.value = '30'
  initRange()
  q.value = ''
  load()
}

onMounted(() => {
  initRange()
  load()
})
</script>

<style scoped>
.page-positions__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.page-positions__variants { margin: 0; }
.page-positions__variants .nav-link { font-size: 13px; }

.page-positions__filter-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
}
.page-positions__label { font-size: 13px; color: #6b7280; }
.page-positions__presets { display: flex; gap: 6px; flex-wrap: wrap; }

.page-positions__grid { width: 100%; font-size: 15px; }
.page-positions__grid thead th {
  font-size: 13px;
  color: #6b7280;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .02em;
}
.page-positions__row { cursor: pointer; }
.page-positions__row td { padding: 10px 8px; }
.page-positions__row:hover { background: #f6f8fc; }
.page-positions__phrase { font-weight: 600; font-size: 15px; }
.page-positions__note { color: #9ca3af; font-size: 13px; }
.page-positions__ours {
  display: inline-block;
  min-width: 26px;
  padding: 1px 8px;
  border-radius: 12px;
  background: #e8f0fe;
  color: #1f6fd0;
  font-weight: 600;
  font-size: 14px;
}
.page-positions__date { white-space: nowrap; color: #4b5563; }
.page-positions__chev { width: 26px; color: #c3c8d0; text-align: right; }
.page-positions__toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.page-positions__requeue {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.page-positions__check { display: flex; gap: 6px; align-items: center; font-size: 14px; color: #4b5563; }

.page-positions__detail {
  margin-top: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
}
.page-positions__detail-head {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.page-positions__detail-title { font-size: 16px; font-weight: 700; margin: 0; }

/* срез = дата сбора, в нём карточки выдачи горизонтально */
.page-positions__slice {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  border-top: 1px solid #eef0f3;
  padding: 10px 0;
}
.page-positions__slice-date { width: 96px; flex: 0 0 96px; }
.page-positions__slice-day { font-weight: 700; font-size: 13px; }
.page-positions__slice-time { font-weight: 700; font-size: 15px; color: #1f6fd0; }
.page-positions__cards {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 6px;
}
.page-positions__more {
  flex: 0 0 auto;
  align-self: center;
  color: #6b7280;
  font-size: 12px;
  white-space: nowrap;
}

.page-positions__block { border-top: 1px solid #e5e7eb; padding-top: 10px; margin-top: 10px; }
.page-positions__block-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.page-positions__history { margin-bottom: 6px; }
.page-positions__section { font-size: 14px; font-weight: 700; margin: 18px 0 8px; }
</style>
