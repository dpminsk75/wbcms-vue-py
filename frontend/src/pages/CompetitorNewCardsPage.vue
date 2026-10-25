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
        class="form-control form-control-sm page-competitor__search"
        placeholder="Поиск в работе: nmID, vendorCode, название, бренд"
        @keyup.enter="load"
      />
      <button class="btn btn-sm btn-primary" :disabled="loading" @click="load">
        <i class="bi bi-search"></i> Найти
      </button>
      <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="reset">Сброс</button>
      <label class="page-competitor__check">
        <input v-model="includeAll" type="checkbox" @change="load()" />
        все карточки
      </label>
      <span class="badge bg-secondary">В работе: {{ rows.length }}</span>
    </div>

    <div class="page-competitor__picker">
      <div class="page-competitor__picker-label">
        <i class="bi bi-plus-circle"></i> Добавить карточку из общего списка
      </div>
      <div class="page-competitor__picker-row">
        <input
          v-model="pick"
          :list="pickListId"
          class="form-control form-control-sm"
          placeholder="nmID, артикул или часть названия…"
          autocomplete="off"
          @keyup.enter="openPicked"
        />
        <datalist :id="pickListId">
          <option v-for="c in picks" :key="c.nmID" :value="String(c.nmID)">
            {{ c.vendorCode || '—' }} | {{ c.title || 'без названия' }}
          </option>
        </datalist>
        <button class="btn btn-sm btn-outline-primary" :disabled="!pickedNm" @click="openPicked">
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

    <div v-else-if="!rows.length" class="alert alert-info">
      <template v-if="q || includeAll">Ничего не найдено.</template>
      <template v-else>
        Карточек в работе нет. Добавьте поисковые запросы или конкурентов в карточке товара
        (или откройте любую карточку через поле выше).
      </template>
    </div>

    <table v-else class="wb-admin-table page-competitor__grid">
      <thead>
        <tr>
          <th class="page-competitor__col-product">Товар</th>
          <th class="text-center page-competitor__col-num" title="Поисковые запросы (широкие, для сбора конкурентов)">Запросы</th>
          <th class="text-center page-competitor__col-num" title="Привязанные конкуренты">Конкуренты</th>
          <th class="text-center page-competitor__col-num" title="Конкуренты с собранным описанием">С контентом</th>
          <th class="text-center page-competitor__col-num" title="Фразы из описаний конкурентов: выбрано / всего">Фразы</th>
          <th class="text-center page-competitor__col-num" title="Есть сгенерированные title + description">Сводка</th>
          <th class="page-competitor__col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.nmID">
          <td>
            <div class="page-competitor__product">
              <img :src="r.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb" loading="lazy" />
              <div class="page-competitor__product-text">
                <div class="page-competitor__product-title" :title="r.title || ''">{{ r.title || '—' }}</div>
                <div class="page-competitor__product-sub">
                  <a
                    :href="`/wb/detail?nm_id=${r.nmID}`"
                    target="_blank"
                    class="page-competitor__wb-link"
                    title="Карточка WB в SelBI"
                  >WB: {{ r.nmID }}</a>
                  <span v-if="r.vendor_code"> · {{ r.vendor_code }}</span>
                </div>
                <div class="page-competitor__product-sub">
                  <span>{{ r.brand || '—' }}</span>
                  <span v-if="r.subject_name"> · {{ r.subject_name }}</span>
                  <span v-if="r.desc_len < descMinLen" class="badge bg-warning text-dark page-competitor__mini">без описания</span>
                </div>
              </div>
            </div>
          </td>
          <td class="text-center">
            <span class="badge" :class="r.queries_cnt ? 'bg-primary' : 'bg-light text-dark'">{{ r.queries_cnt }}</span>
          </td>
          <td class="text-center">
            <span class="badge" :class="r.competitors_cnt ? 'bg-primary' : 'bg-light text-dark'">{{ r.competitors_cnt }}</span>
          </td>
          <td class="text-center">
            <span class="badge" :class="r.content_cnt ? 'bg-success' : 'bg-light text-dark'">{{ r.content_cnt }}</span>
          </td>
          <td class="text-center">
            <span class="badge" :class="r.phrases_cnt ? 'bg-primary' : 'bg-light text-dark'">
              {{ r.selected_cnt }}/{{ r.phrases_cnt }}
            </span>
          </td>
          <td class="text-center">
            <span v-if="r.summary_cnt" class="badge bg-success"><i class="bi bi-check-lg"></i></span>
            <span v-else class="page-competitor__dash">—</span>
          </td>
          <td class="page-competitor__actions">
            <router-link :to="`/competitor/new-cards/${r.nmID}`" class="btn btn-sm btn-primary">
              <i class="bi bi-magic"></i> Открыть
            </router-link>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-new-cards.css'
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { COMPETITOR_SUB_TABS } from '@/components/common/workspaceTabs'
import { api } from '../api/client'
import { competitorsNewcardApi, type NewCardRow } from '../api/competitorsNewcard'

const router = useRouter()
const rows = ref<NewCardRow[]>([])
const q = ref('')
const includeAll = ref(false)
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

onMounted(load)
</script>
