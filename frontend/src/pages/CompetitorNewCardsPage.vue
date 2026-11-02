<template>
  <div class="container-xxl page-competitor page-competitor-new-cards">
    <WbWorkspaceHead title="Конкуренты: Ручная привязка" :subtabs="COMPETITOR_SUB_TABS" workspace-active="competitors" />
    <p class="text-muted">
      Карточки в работе: у них есть поисковые запросы или привязанные конкуренты. Откройте карточку,
      чтобы разобрать описания конкурентов, выбрать фразы и сгенерировать title и description.
    </p>

    <div class="page-competitor__toolbar">
      <input
        v-model="q"
        class="wb-input page-competitor__search"
        placeholder="Поиск в работе: nmID, vendorCode, название, бренд"
        @keyup.enter="load"
      />
      <button class="btn btn-sm btn--brand" :disabled="loading" @click="load">
        <i class="bi bi-search"></i> Найти
      </button>
      <button class="btn btn-sm btn--outline" :disabled="loading" @click="reset">Сброс</button>
      <label class="page-competitor__check">
        <input v-model="includeAll" type="checkbox" @change="load()" />
        все карточки
      </label>
      <span class="badge badge--neutral">В работе: {{ rows.length }}</span>
    </div>

    <div class="page-competitor__picker">
      <div class="page-competitor__picker-label">
        <i class="bi bi-plus-circle"></i> Добавить карточку из общего списка
      </div>
      <div class="page-competitor__picker-row">
        <input
          v-model="pick"
          :list="pickListId"
          class="wb-input"
          placeholder="nmID, артикул или часть названия…"
          autocomplete="off"
          @keyup.enter="openPicked"
        />
        <datalist :id="pickListId">
          <option v-for="c in picks" :key="c.nmID" :value="String(c.nmID)">
            {{ c.vendorCode || '—' }} | {{ c.title || 'без названия' }}
          </option>
        </datalist>
        <button class="btn btn-sm btn--outline" :disabled="!pickedNm" @click="openPicked">
          <i class="bi bi-arrow-right"></i> Открыть
        </button>
      </div>
      <div class="page-competitor__picker-hint">
        Любая наша карточка: добавите ей поисковые запросы/конкурентов — появится в списке «в работе».
      </div>
    </div>

    <div v-if="error" class="wb-error">{{ error }}</div>

    <div v-if="loading" class="text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка…
    </div>

    <div v-else-if="!rows.length" class="wb-panel page-competitor__empty">
      <div class="wb-panel__bd">
        <template v-if="q || includeAll">Ничего не найдено.</template>
        <template v-else>
          Карточек в работе нет. Добавьте поисковые запросы или конкурентов в карточке товара
          (или откройте любую карточку через поле выше).
        </template>
      </div>
    </div>

    <div v-else class="tbl-card">
      <div class="card__hd">
        <span>Карточки в работе</span>
        <span class="spacer"></span>
        <span class="hd-badge">Карточек: {{ rows.length }}</span>
      </div>
      <div class="tbl-wrap">
      <table class="tbl page-competitor__grid">
      <thead>
        <tr>
          <th class="t-left page-competitor__col-product">Товар</th>
          <th class="t-center page-competitor__col-num" title="Поисковые запросы (широкие, для сбора конкурентов)">Запросы</th>
          <th class="t-center page-competitor__col-num" title="Привязанные конкуренты">Конкуренты</th>
          <th class="t-center page-competitor__col-num" title="Конкуренты с собранным описанием">С контентом</th>
          <th class="t-center page-competitor__col-num" title="Фразы из описаний конкурентов: выбрано / всего">Фразы</th>
          <th class="t-center page-competitor__col-num" title="Есть сгенерированные title + description">Сводка</th>
          <th class="t-left page-competitor__col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.nmID">
          <td>
            <ProductCell
              compact
              :nm-id="r.nmID"
              :photo="r.photo || ''"
              :title="r.title || ''"
              :vendor="r.vendor_code || ''"
              :brand="r.brand || ''"
              :subject="r.subject_name || ''"
              :link="`/wb/detail?nm_id=${r.nmID}`"
              :link-label="'WB: ' + r.nmID"
              copy-nm
              copy-link
            />
          </td>
          <td class="t-center">
            <span class="badge" :class="r.queries_cnt ? 'badge--brand' : 'badge--neutral'">{{ r.queries_cnt }}</span>
          </td>
          <td class="t-center">
            <span class="badge" :class="r.competitors_cnt ? 'badge--brand' : 'badge--neutral'">{{ r.competitors_cnt }}</span>
          </td>
          <td class="t-center">
            <span class="badge" :class="r.content_cnt ? 'badge--ok' : 'badge--neutral'">{{ r.content_cnt }}</span>
          </td>
          <td class="t-center">
            <button
              type="button"
              class="badge page-competitor-new-cards__phrases"
              :class="r.phrases_cnt ? 'badge--brand' : 'badge--neutral'"
              title="Фразы из описаний конкурентов (ИИ-разбор) — выбрано / всего"
              @click="openPhrases(r)"
            >{{ r.selected_cnt }}/{{ r.phrases_cnt }}</button>
          </td>
          <td class="t-center">
            <span v-if="r.summary_cnt" class="badge badge--ok"><i class="bi bi-check-lg"></i></span>
            <span v-else class="page-competitor__dash">—</span>
          </td>
          <td class="page-competitor__actions">
            <router-link :to="`/competitor/new-cards/${r.nmID}`" class="btn btn-sm btn--brand">
              <i class="bi bi-magic"></i> Открыть
            </router-link>
          </td>
        </tr>
      </tbody>
      </table>
      </div>
    </div>
    <CompetitorPhrasesModal
      :open="phrasesOpen"
      :nm-id="phrasesRow?.nmID"
      :title="phrasesRow?.title"
      source="comp"
      :count="phrasesCount"
      @close="phrasesOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-new-cards.css'
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import ProductCell from '@/components/common/ProductCell.vue'
import { useRoute, useRouter } from 'vue-router'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import CompetitorPhrasesModal from '@/components/competitors/CompetitorPhrasesModal.vue'
import { COMPETITOR_SUB_TABS } from '@/components/common/workspaceTabs'
import { api } from '../api/client'
import { competitorsNewcardApi, type NewCardRow } from '../api/competitorsNewcard'

const route = useRoute()
const router = useRouter()
const rows = ref<NewCardRow[]>([])
const q = ref('')
const includeAll = ref(false)
/** Модалка «Фразы карточки» (заготовка). */
const phrasesOpen = ref(false)
const phrasesRow = ref<NewCardRow | null>(null)
const phrasesCount = ref<number | null>(null)
const loading = ref(false)
const error = ref('')
const descMinLen = ref(50)

const pick = ref('')
const picks = ref<Array<{ nmID: number; title?: string; vendorCode?: string }>>([])
const pickListId = 'newcard-pick-list'

const pickedNm = computed(() => {
  const v = pick.value.trim()
  if (!v) return 0
  const exact = picks.value.find((c) => String(c.nmID) === v)
  if (exact) return exact.nmID
  const byCode = picks.value.find((c) => String(c.vendorCode || '') === v)
  if (byCode) return byCode.nmID
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? n : 0
})

let pickTimer: ReturnType<typeof setTimeout> | null = null
let pickSeq = 0

watch(pick, (v) => {
  if (pickTimer) clearTimeout(pickTimer)
  const s = String(v || '').trim()
  if (s.length < 2) {
    picks.value = []
    return
  }
  pickTimer = setTimeout(async () => {
    const my = ++pickSeq
    try {
      const { data } = await api.get('/api/wb/cards', { params: { q: s, limit: 20 } })
      if (my !== pickSeq) return
      const list = Array.isArray(data) ? data : (data?.items ?? [])
      picks.value = list.map((c: any) => ({ nmID: Number(c.nmID), title: c.title, vendorCode: c.vendorCode }))
    } catch {
      picks.value = []
    }
  }, 300)
})

function openPicked() {
  const nm = pickedNm.value
  if (!nm) return
  router.push(`/competitor/new-cards/${nm}`)
}

async function load() {
  syncUrl()
  loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.list(q.value.trim(), 300, includeAll.value)
    rows.value = d.items || []
    descMinLen.value = d.desc_min_len || 50
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

function reset() {
  q.value = ''
  includeAll.value = false
  load()
}

onBeforeUnmount(() => {
  if (pickTimer) clearTimeout(pickTimer)
  pickSeq++
})

onMounted(() => {
  applyQuery()
  load()
})

/** Состояние страницы → адресная строка: поиск и фильтр переживают перезагрузку. */
function syncUrl() {
  const qs: Record<string, any> = { ...route.query }
  const put = (k: string, v: any) => {
    if (v === '' || v === null || v === undefined || v === false) delete qs[k]
    else qs[k] = String(v)
  }
  put('q', q.value.trim())
  put('all', includeAll.value ? '1' : '')
  const target = { path: route.path, query: qs }
  if (route.fullPath === router.resolve(target).fullPath) return
  router.replace(target).catch(() => {})
}

/** Адресная строка → состояние. true — что-то изменилось (нужен перезагруз). */
function applyQuery(): boolean {
  const p = route.query
  let changed = false
  if (p.q !== undefined) {
    const v = String(p.q ?? '')
    if (v !== q.value.trim()) { q.value = v; changed = true }
  }
  if (p.all !== undefined) {
    const a = String(p.all ?? '') === '1'
    if (a !== includeAll.value) { includeAll.value = a; changed = true }
  }
  return changed
}

// «назад/вперёд» в браузере и переход по ссылке — применяем состояние из адресной строки
watch(() => route.query, () => {
  if (applyQuery()) load()
})

/** Модалка «Фразы карточки» (заготовка). */
function openPhrases(r: NewCardRow) {
  phrasesRow.value = r
  phrasesCount.value = r.phrases_cnt ?? null
  phrasesOpen.value = true
}

</script>
