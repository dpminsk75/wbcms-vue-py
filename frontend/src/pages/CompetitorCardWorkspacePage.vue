<template>
  <div class="container-xxl page-competitor page-workspace">
    <div class="page-workspace__crumbs">
      <router-link to="/competitor/new-cards"><i class="bi bi-arrow-left"></i> К списку карточек</router-link>
    </div>

    <div v-if="loading" class="text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка…
    </div>
    <div v-else-if="error && !detail" class="wb-error">{{ error }}</div>

    <template v-if="detail">
      <!-- наша карточка -->
      <div class="page-workspace__card">
        <img :src="detail.card.photo || '/images/no-photo.png'" alt="" class="page-workspace__thumb" />
        <div class="page-workspace__card-text">
          <div class="page-workspace__title">{{ detail.card.title || '—' }}</div>
          <div class="page-workspace__meta">
            <a :href="`/wb/detail?nm_id=${detail.card.nmID}`" target="_blank">WB: {{ detail.card.nmID }}</a>
            <span v-if="detail.card.vendor_code"> · {{ detail.card.vendor_code }}</span>
            <span v-if="detail.card.brand"> · {{ detail.card.brand }}</span>
            <span v-if="detail.card.subject_name"> · {{ detail.card.subject_name }}</span>
          </div>
          <div class="page-workspace__badges">
            <span class="badge bg-light text-dark">описание: {{ detail.card.desc_len }}</span>
            <span class="badge bg-light text-dark">характеристик: {{ (detail.card.characteristics || []).length }}</span>
            <span class="badge" :class="detail.counts.queries_cnt ? 'bg-primary' : 'bg-light text-dark'">запросов: {{ detail.counts.queries_cnt }}</span>
            <span class="badge" :class="detail.counts.competitors_cnt ? 'bg-primary' : 'bg-light text-dark'">конкурентов: {{ detail.counts.competitors_cnt }}</span>
            <span class="badge" :class="detail.counts.content_cnt ? 'bg-success' : 'bg-light text-dark'">с контентом: {{ detail.counts.content_cnt }}</span>
            <span class="badge" :class="detail.counts.selected_cnt ? 'bg-primary' : 'bg-light text-dark'">фраз выбрано: {{ detail.counts.selected_cnt }}</span>
          </div>
          <details v-if="(detail.card.characteristics || []).length" class="page-workspace__chars">
            <summary>Показать характеристики</summary>
            <div v-for="(c, i) in detail.card.characteristics" :key="i" class="page-workspace__char">
              <b>{{ c.name }}</b>: {{ charValue(c.value) }}
            </div>
          </details>
        </div>
      </div>

      <div v-if="error" class="wb-error">{{ error }}</div>
      <div v-if="notice" class="page-workspace__notice">{{ notice }}</div>

      <!-- шаг 1: конкуренты -->
      <section class="page-workspace__step">
        <div class="page-workspace__step-head">
          <h4><span class="page-workspace__step-num">1</span> Конкуренты и их описания</h4>
          <div class="page-workspace__step-actions">
            <button
              class="btn btn-sm btn-primary"
              :disabled="!detail.competitors.length"
              :title="detail.competitors.length ? '' : 'Сначала привяжите конкурентов'"
              @click="analyzeOpen = true"
            >
              <i class="bi bi-stars"></i>
              Анализировать описания конкурентов
            </button>
          </div>
        </div>

        <div v-if="!detail.competitors.length" class="alert alert-info mb-0">
          Конкурентов нет. Добавьте их в карточке WB (кнопка «Конкуренты») или привяжите собранные
          на странице <router-link to="/competitor/captured">«Собранные карточки»</router-link>.
        </div>
        <div v-else-if="!detail.counts.content_cnt" class="alert alert-warning mb-0">
          Ни у одного конкурента нет собранного описания. Откройте карточки конкурентов на WB —
          расширение соберёт контент (или «Собрать текущую» в попапе).
        </div>

        <table v-if="detail.competitors.length" class="wb-admin-table page-workspace__grid">
          <thead>
            <tr>
              <th>Конкурент</th>
              <th class="text-center">Описание</th>
              <th class="text-center">Хар-ки</th>
              <th>Собрано</th>
              <th class="text-center">Разбор</th>
              <th class="text-center page-workspace__col-detach"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in detail.competitors" :key="c.nm_id">
              <td>
                <div class="page-workspace__comp">
                  <img :src="c.photo || '/images/no-photo.png'" alt="" class="page-workspace__comp-thumb" loading="lazy" />
                  <div>
                    <div class="page-workspace__comp-title" :title="c.title || ''">{{ c.title || '—' }}</div>
                    <div class="page-workspace__comp-sub">
                      <a :href="`https://www.wildberries.ru/catalog/${c.nm_id}/detail.aspx`" target="_blank" rel="noopener">
                        nm {{ c.nm_id }}
                      </a>
                      <span v-if="c.seller"> · {{ c.seller }}</span>
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
              <td class="page-workspace__muted">{{ fmtAgo(c.collected_at) }}</td>
              <td class="text-center">
                <span v-if="c.analysis_status === 'analyzed'" class="badge bg-success">есть</span>
                <span v-else class="page-workspace__muted">—</span>
              </td>
              <td class="text-center">
                <button
                  class="btn btn-sm btn-link text-danger"
                  title="Отвязать конкурента (контент останется в «Собранных карточках»)"
                  @click="detachCompetitor(c)"
                >
                  <i class="bi bi-x-lg"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- шаг 2: фразы -->
      <section class="page-workspace__step">
        <div class="page-workspace__step-head">
          <h4><span class="page-workspace__step-num">2</span> Фразы для генерации</h4>
          <span class="badge bg-primary">выбрано: {{ selectedCnt }}</span>
        </div>

        <div class="page-workspace__toolbar">
          <input v-model="phraseQ" class="form-control form-control-sm page-workspace__search" placeholder="Фильтр фраз…" />
          <label class="page-workspace__check"><input v-model="onlyInDb" type="checkbox" /> только в базе</label>
          <label class="page-workspace__check"><input v-model="onlySelected" type="checkbox" /> только выбранные</label>
          <button class="btn btn-sm btn-outline-secondary" :disabled="!filteredPhrases.length" @click="selectAll(true)">Выбрать все</button>
          <button class="btn btn-sm btn-outline-secondary" :disabled="!selectedCnt" @click="selectAll(false)">Снять все</button>
          <div class="page-workspace__add">
            <input
              v-model="newPhrase"
              class="form-control form-control-sm"
              placeholder="своя фраза"
              @keyup.enter="addPhrase"
            />
            <button class="btn btn-sm btn-outline-primary" :disabled="!newPhrase.trim()" @click="addPhrase">
              <i class="bi bi-plus-lg"></i>
            </button>
          </div>
        </div>

        <div v-if="!detail.phrases.length" class="page-workspace__empty">
          Фраз пока нет. Нажмите «Анализировать описания конкурентов» на шаге 1 или добавьте свою фразу.
        </div>
        <table v-else class="wb-admin-table page-workspace__grid page-workspace__phrases">
          <thead>
            <tr>
              <th class="page-workspace__col-check"></th>
              <th>Фраза</th>
              <th class="text-center" title="У скольких конкурентов встретилась в описании">Конкуренты</th>
              <th class="text-center" title="Заказы в нашей базе wb_sr_report_item_phrases">Заказы</th>
              <th class="text-center" title="Частота в нашей базе">Частота</th>
              <th class="text-center" title="Карточек в нашей базе">Карточки</th>
              <th>Источник</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in filteredPhrases" :key="p.id" :class="{ 'page-workspace__row--sel': p.is_selected }">
              <td class="text-center">
                <input type="checkbox" :checked="p.is_selected" @change="onToggle(p, $event)" />
              </td>
              <td class="page-workspace__phrase">{{ p.phrase }}</td>
              <td class="text-center"><span class="badge bg-light text-dark">{{ p.hit_cnt }}</span></td>
              <td class="text-center">{{ p.orders || '—' }}</td>
              <td class="text-center">{{ p.freq || '—' }}</td>
              <td class="text-center">{{ p.cards_cnt || '—' }}</td>
              <td>
                <span v-if="p.in_db" class="badge bg-success" title="Есть в нашей базе поисковых фраз">в базе</span>
                <span v-else class="badge bg-warning text-dark" title="Нет в нашей базе — новая">новая</span>
                <span v-if="p.in_targets" class="badge bg-primary" title="Уже в целевых фразах">в целевых</span>
                <span v-if="p.source === 'manual'" class="badge bg-light text-dark">вручную</span>
              </td>
              <td class="text-center">
                <button class="btn btn-sm btn-link text-danger" title="Удалить" @click="removePhrase(p)">
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- шаг 3: генерация -->
      <section class="page-workspace__step">
        <div class="page-workspace__step-head">
          <h4><span class="page-workspace__step-num">3</span> Генерация</h4>
          <button
            class="btn btn-sm btn-success"
            :disabled="!selectedCnt || !detail.counts.content_cnt"
            :title="!selectedCnt ? 'Выберите фразы на шаге 2' : (!detail.counts.content_cnt ? 'Нет описаний конкурентов' : '')"
            @click="generateOpen = true"
          >
            <i class="bi bi-magic"></i>
            Сгенерировать title + description
          </button>
        </div>

        <div v-if="!selectedCnt" class="page-workspace__empty">
          Выберите фразы на шаге 2 — они пойдут в заголовок и описание как обязательные ключевые слова.
        </div>

        <div v-if="result" class="page-workspace__result">
          <div class="page-workspace__result-head">
            <span class="page-workspace__result-label">Заголовок</span>
            <span class="badge" :class="result.title_len > 60 ? 'bg-danger' : 'bg-success'">{{ result.title_len }} / 60</span>
            <button class="btn btn-sm btn-outline-secondary" @click="copy(result.title)">Копировать</button>
          </div>
          <div class="page-workspace__result-title">{{ result.title }}</div>

          <div class="page-workspace__result-head">
            <span class="page-workspace__result-label">Описание</span>
            <span class="badge bg-light text-dark">{{ result.desc_len }} симв. (норма {{ result.desc_min }}–{{ result.desc_max }})</span>
            <button class="btn btn-sm btn-outline-secondary" @click="copy(result.description)">Копировать</button>
          </div>
          <div class="page-workspace__result-desc">{{ result.description }}</div>

          <div class="page-workspace__result-meta">
            модель: {{ result.model || '—' }} · конкурентов: {{ result.competitor_count }} · фраз: {{ result.phrases.length }}
            <template v-if="resultAt"> · {{ resultAt }}</template>
          </div>
          <div class="page-workspace__hint">
            Сохранено в «Сводку» карточки (модалка «Сводка» в карточке WB). В саму карточку WB не пишется.
          </div>
        </div>

        <div v-else-if="detail.summary && detail.summary.suggested_description" class="page-workspace__result">
          <div class="page-workspace__result-head">
            <span class="page-workspace__result-label">Последняя сводка</span>
            <span class="badge bg-secondary">{{ detail.summary.created_at || '' }}</span>
          </div>
          <div class="page-workspace__result-title">{{ detail.summary.suggested_title }}</div>
          <div class="page-workspace__result-desc">{{ detail.summary.suggested_description }}</div>
          <div class="page-workspace__result-meta">
            модель: {{ detail.summary.model || '—' }} · конкурентов: {{ detail.summary.competitor_count || 0 }}
          </div>
        </div>
      </section>
    </template>

    <CompetitorAnalyzeModal
      :open="analyzeOpen"
      :nm-id="detail?.card.nmID"
      :competitors="detail?.competitors || []"
      :desc-min="descMinLen"
      @close="analyzeOpen = false"
      @done="onAnalyzed"
    />

    <CompetitorGenerateModal
      :open="generateOpen"
      :nm-id="detail?.card.nmID"
      :card-title="detail?.card.title"
      :phrases="selectedPhrases"
      :competitors-cnt="detail?.counts.content_cnt || 0"
      @close="generateOpen = false"
      @done="onGenerated"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-new-cards.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  competitorsNewcardApi,
  type CompetitorRow,
  type NewCardDetail,
  type NewCardGenerateResult,
  type NewCardPhrase,
} from '../api/competitorsNewcard'
import CompetitorAnalyzeModal from '../components/competitors/CompetitorAnalyzeModal.vue'
import CompetitorGenerateModal from '../components/competitors/CompetitorGenerateModal.vue'

const route = useRoute()
const nm = computed(() => Number(route.params.nm || 0))

const detail = ref<NewCardDetail | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const descMinLen = ref(50)

const analyzeOpen = ref(false)
const generateOpen = ref(false)

const phraseQ = ref('')
const onlyInDb = ref(false)
const onlySelected = ref(false)
const newPhrase = ref('')

const result = ref<NewCardGenerateResult | null>(null)
const resultAt = ref('')

const selectedCnt = computed(() => (detail.value?.phrases || []).filter((p) => p.is_selected).length)
const selectedPhrases = computed(() => (detail.value?.phrases || []).filter((p) => p.is_selected).map((p) => p.phrase))

const filteredPhrases = computed(() => {
  const q = phraseQ.value.trim().toLowerCase()
  return (detail.value?.phrases || []).filter((p) => {
    if (onlyInDb.value && !p.in_db) return false
    if (onlySelected.value && !p.is_selected) return false
    if (q && !p.phrase.toLowerCase().includes(q)) return false
    return true
  })
})

function charValue(v: any): string {
  if (Array.isArray(v)) return v.join('; ')
  return v == null ? '' : String(v)
}

function fmtAgo(v?: string | null): string {
  if (!v) return '—'
  const t = new Date(v).getTime()
  if (!isFinite(t)) return String(v)
  const m = Math.round((Date.now() - t) / 60000)
  if (m < 1) return 'только что'
  if (m < 60) return `${m} мин назад`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} ч назад`
  const d = Math.round(h / 24)
  if (d < 30) return `${d} дн назад`
  return new Date(v).toLocaleDateString('ru-RU')
}

async function load() {
  if (!nm.value) return
  loading.value = true
  error.value = ''
  try {
    detail.value = await competitorsNewcardApi.detail(nm.value)
    descMinLen.value = 50
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function loadPhrases() {
  if (!detail.value || !nm.value) return
  try {
    const d = await competitorsNewcardApi.phrases(nm.value)
    detail.value.phrases = d.items || []
    detail.value.counts.phrases_cnt = (d.items || []).length
    detail.value.counts.selected_cnt = d.selected_cnt || 0
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось загрузить фразы'
  }
}

async function onAnalyzed() {
  await loadPhrases()
  notice.value = 'Фразы обновлены, выберите нужные для генерации'
}

async function detachCompetitor(c: CompetitorRow) {
  if (!nm.value) return
  if (!confirm(`Отвязать конкурента nm ${c.nm_id}?\n\nКонтент и история останутся в «Собранных карточках», привязку можно вернуть.`)) return
  error.value = ''
  notice.value = ''
  try {
    await competitorsNewcardApi.detachCompetitor(nm.value, c.nm_id)
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось отвязать конкурента'
  }
}

async function setSelected(phrases: string[], selected: boolean) {
  if (!nm.value || !phrases.length) return
  error.value = ''
  try {
    await competitorsNewcardApi.selectPhrases(nm.value, phrases, selected)
    const set = new Set(phrases)
    for (const p of detail.value?.phrases || []) if (set.has(p.phrase)) p.is_selected = selected
    if (detail.value) detail.value.counts.selected_cnt = selectedCnt.value
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось изменить выбор'
  }
}

function onToggle(p: NewCardPhrase, e: Event) {
  setSelected([p.phrase], (e.target as HTMLInputElement).checked)
}

function selectAll(selected: boolean) {
  setSelected(filteredPhrases.value.map((p) => p.phrase), selected)
}

async function addPhrase() {
  const p = newPhrase.value.trim()
  if (!nm.value || !p) return
  error.value = ''
  try {
    await competitorsNewcardApi.addPhrase(nm.value, p)
    newPhrase.value = ''
    await loadPhrases()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось добавить фразу'
  }
}

async function removePhrase(p: NewCardPhrase) {
  if (!nm.value) return
  if (!confirm(`Удалить фразу «${p.phrase}»?`)) return
  error.value = ''
  try {
    await competitorsNewcardApi.removePhrase(nm.value, p.id)
    await loadPhrases()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось удалить фразу'
  }
}

async function onGenerated(res: NewCardGenerateResult) {
  result.value = res
  resultAt.value = new Date().toLocaleString('ru-RU')
  notice.value = 'Готово, сохранено в сводку'
  await load()
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text || '')
    notice.value = 'Скопировано'
  } catch {
    error.value = 'Браузер не дал доступ к буферу обмена'
  }
}

watch(() => route.params.nm, () => {
  result.value = null
  resultAt.value = ''
  notice.value = ''
  analyzeOpen.value = false
  generateOpen.value = false
  load()
})

onMounted(load)
</script>
