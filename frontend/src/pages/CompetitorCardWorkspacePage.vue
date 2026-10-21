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
            <span v-if="queuePending" class="badge bg-warning text-dark" title="Ждут сбора описаний в очереди расширения">
              в очереди: {{ queuePending }}
            </span>
            <span v-if="queueAssigned" class="badge bg-primary" title="Назначено повторное обновление контента">
              назначено: {{ queueAssigned }}
            </span>
            <span v-if="queueProcessing" class="badge bg-info text-dark" title="Расширение сейчас собирает описания">
              собираем: {{ queueProcessing }}
            </span>
            <button class="btn btn-sm btn-outline-secondary" title="Обновить статусы очереди" @click="load()">
              <i class="bi bi-arrow-clockwise"></i>
            </button>
            <button class="btn btn-sm btn-outline-secondary" @click="queriesOpen = true">
              <i class="bi bi-search"></i>
              Поисковые запросы: {{ detail.counts.queries_cnt }}
            </button>
            <router-link
              :to="`/competitor/pick?source_nm_id=${detail.card.nmID}`"
              class="btn btn-sm btn-outline-primary"
              title="Подобрать конкурентов из выбранной карточки и её рекомендаций"
            >
              <i class="bi bi-diagram-3"></i>
              Подобрать
            </router-link>
            <router-link
              :to="`/competitor/pick?mode=captured&target_nm_id=${detail.card.nmID}`"
              class="btn btn-sm btn-outline-secondary"
              title="Привязать конкурентов из собранной базы к этой карточке"
            >
              <i class="bi bi-collection"></i>
              Из собранных
            </router-link>
            <button
              class="btn btn-sm btn-outline-secondary"
              title="Скопировать конкурентов с другой нашей карточки"
              @click="copyOpen = true"
            >
              <i class="bi bi-files"></i>
              С нашей карточки
            </button>
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
              <th class="text-center" title="Статус сбора описаний в очереди обогащения">Очередь</th>
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
              <td class="page-workspace__muted">{{ collectedLabel(c) }}</td>
              <td class="text-center">
                <span
                  v-if="c.queue_status"
                  class="badge"
                  :class="queueClass(c.queue_status)"
                  :title="c.queue_error || (c.queue_processed_at ? 'обработано: ' + c.queue_processed_at : '')"
                >{{ queueLabel(c.queue_status) }}</span>
                <span v-else class="page-workspace__muted">—</span>
              </td>
              <td class="text-center">
                <span v-if="c.analysis_status === 'analyzed'" class="badge bg-success">есть</span>
                <span v-else class="page-workspace__muted">—</span>
              </td>
              <td class="text-center">
                <div class="page-workspace__row-actions">
                  <button
                    class="btn btn-sm btn-outline-secondary"
                    title="Посмотреть карточку конкурента"
                    @click="openDetails(c)"
                  >
                    <i class="bi bi-eye"></i>
                  </button>
                  <button
                    class="btn btn-sm btn-link text-danger"
                    title="Отвязать конкурента (контент останется в «Собранных карточках»)"
                    @click="detachCompetitor(c)"
                  >
                    <i class="bi bi-x-lg"></i>
                  </button>
                </div>
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
          <button
            class="btn btn-sm btn-outline-primary"
            :disabled="merging"
            :title="rawPhrasesCnt
              ? 'Объединить похожие формулировки в группы (1–3 запроса к модели, разбор описаний не повторяется)'
              : 'Нужен анализ описаний конкурентов: формулировки по конкурентам ещё не собраны'"
            @click="mergePhrases"
          >
            <span v-if="merging" class="spinner-border spinner-border-sm"></span>
            <i v-else class="bi bi-intersect"></i>
            {{ merging ? (mergeTotal ? `Сливаем ${mergeAttempt}/${mergeTotal}…` : 'Сливаем…') : 'Слить формулировки' }}
          </button>
          <span v-if="mergeInfo" class="page-workspace__muted">{{ mergeInfo }}</span>
          <span v-else-if="rawPhrasesCnt" class="page-workspace__muted">
            формулировок по конкурентам: {{ rawPhrasesCnt }}
          </span>
          <span v-else-if="detail.phrases.length" class="page-workspace__warn">
            фразы без привязки к конкурентам — обновите «Анализ описаний конкурентов» на шаге 1
          </span>
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
              <th class="text-center" title="У скольких конкурентов встретилась в описании — наведите, чтобы увидеть список">Конкуренты</th>
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
              <td class="page-workspace__phrase" :title="variantsTitle(p)">
                <span>{{ p.phrase }}</span>
                <span v-if="p.variants_cnt > 1" class="page-analyze__variants">+{{ p.variants_cnt - 1 }}</span>
              </td>
              <td class="text-center">
                <span class="page-analyze__whos">
                  <button type="button" class="btn btn-sm btn-link p-0 page-analyze__whos-btn">
                    <span class="badge bg-light text-dark">{{ p.hit_cnt }}</span>
                  </button>
                  <span class="page-analyze__whos-pop">
                    <span class="page-analyze__whos-title">Фраза встречается у конкурентов:</span>
                    <span v-for="c in p.competitors || []" :key="c.nm_id" class="page-analyze__whos-row">
                      <span class="page-analyze__whos-nm">{{ c.nm_id }}</span>
                      <span class="page-analyze__whos-name">{{ c.title || '—' }}</span>
                    </span>
                    <span v-if="!p.competitors.length" class="page-analyze__muted">нет данных</span>
                  </span>
                </span>
              </td>
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

    <CompetitorsQueriesModal
      :open="queriesOpen"
      :nm-id="detail?.card.nmID"
      @close="closeQueries"
      @changed="load"
    />

    <CompetitorDetailsModal
      :open="detailsOpen"
      :nm-id="activeCompetitor?.nm_id"
      :source-nm-id="nm"
      @close="detailsOpen = false"
    />

    <CompetitorCopyFromCardModal
      :open="copyOpen"
      :target-nm="detail?.card.nmID"
      @close="copyOpen = false"
      @done="onCopied"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import '@/assets/css/pages/page-competitor-new-cards.css'
import '@/assets/css/pages/page-wb-detail.css'
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  competitorsNewcardApi,
  type CompetitorRow,
  type NewCardDetail,
  type NewCardGenerateResult,
  type NewCardPhrase,
} from '../api/competitorsNewcard'
import { copyText } from '../utils/clipboard'
import CompetitorAnalyzeModal from '../components/competitors/CompetitorAnalyzeModal.vue'
import CompetitorCopyFromCardModal from '../components/competitors/CompetitorCopyFromCardModal.vue'
import CompetitorDetailsModal from '../components/competitors/CompetitorDetailsModal.vue'
import CompetitorGenerateModal from '../components/competitors/CompetitorGenerateModal.vue'
import CompetitorsQueriesModal from '../components/competitors/CompetitorsQueriesModal.vue'

const route = useRoute()
const nm = computed(() => Number(route.params.nm || 0))

const detail = ref<NewCardDetail | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const descMinLen = ref(50)

const analyzeOpen = ref(false)
const generateOpen = ref(false)
const detailsOpen = ref(false)
const queriesOpen = ref(false)
const copyOpen = ref(false)
const activeCompetitor = ref<CompetitorRow | null>(null)

const phraseQ = ref('')
const onlyInDb = ref(false)
const onlySelected = ref(false)
const newPhrase = ref('')
const merging = ref(false)
const mergeInfo = ref('')
const rawPhrasesCnt = ref(0)
const mergeAttempt = ref(0)
const mergeTotal = ref(0)

const result = ref<NewCardGenerateResult | null>(null)
const resultAt = ref('')

const selectedCnt = computed(() => (detail.value?.phrases || []).filter((p) => p.is_selected).length)
const selectedPhrases = computed(() => (detail.value?.phrases || []).filter((p) => p.is_selected).map((p) => p.phrase))
const queuePending = computed(() => (detail.value?.competitors || []).filter((c) => c.queue_status === 'pending').length)
const queueAssigned = computed(() => (detail.value?.competitors || []).filter((c) => c.queue_status === 'need_update').length)
const queueProcessing = computed(() => (detail.value?.competitors || []).filter((c) => c.queue_status === 'processing').length)

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

function collectedLabel(c: CompetitorRow): string {
  if (c.desc_len > 0 || c.chars_cnt > 0) return fmtAgo(c.collected_at)
  if (c.queue_status === 'done') return 'пусто'
  return '—'
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

async function load(silent = false) {
  if (!nm.value) return
  if (!silent) {
    loading.value = true
    error.value = ''
  }
  try {
    detail.value = await competitorsNewcardApi.detail(nm.value)
    descMinLen.value = 50
  } catch (e: any) {
    if (!silent) {
      error.value = e?.response?.data?.detail || String(e)
      detail.value = null
    }
  } finally {
    if (!silent) loading.value = false
  }
}

async function loadPhrases() {
  if (!detail.value || !nm.value) return
  try {
    const d = await competitorsNewcardApi.phrases(nm.value)
    detail.value.phrases = d.items || []
    detail.value.counts.phrases_cnt = (d.items || []).length
    detail.value.counts.selected_cnt = d.selected_cnt || 0
    rawPhrasesCnt.value = d.raw_cnt || 0
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось загрузить фразы'
  }
}

/** Только слияние формулировок в группы — разбор описаний не повторяется. */
async function mergePhrases() {
  if (!nm.value || merging.value) return
  if (!rawPhrasesCnt.value) {
    error.value = 'Сначала запустите «Анализ описаний конкурентов» на шаге 1 — нужны формулировки по конкурентам'
    return
  }
  merging.value = true
  error.value = ''
  mergeInfo.value = ''
  const runId = newRunId()
  const poll = setInterval(() => { void pollMergeRun(runId) }, 1500)
  void pollMergeRun(runId)
  try {
    const d = await competitorsNewcardApi.mergePhrases(nm.value, runId)
    await loadPhrases()
    const groups = d.groups_cnt || 0
    const raw = d.raw_cnt || 0
    const merged = d.merged_cnt || 0
    mergeInfo.value = `групп: ${groups}${raw ? ` из ${raw} формулировок` : ''}${merged ? ` · слито ${merged}` : ''}`
    if (d.errors?.length) {
      error.value = `Слияние: ${d.errors.join('; ')}`
    } else {
      notice.value = 'Формулировки объединены в группы'
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось слить формулировки'
  } finally {
    clearInterval(poll)
    merging.value = false
  }
}

async function pollMergeRun(runId: string) {
  if (!nm.value) return
  try {
    const r = await competitorsNewcardApi.runStatus(nm.value, runId)
    mergeAttempt.value = r.attempt || 0
    mergeTotal.value = r.total || 0
  } catch {
    /* прогона ещё нет — это нормально */
  }
}

function newRunId(): string {
  const c = (globalThis as any).crypto
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  return `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
}

async function onAnalyzed() {
  await loadPhrases()
  notice.value = 'Фразы обновлены, выберите нужные для генерации'
}

function openDetails(c: CompetitorRow) {
  activeCompetitor.value = c
  detailsOpen.value = true
}

function closeQueries() {
  queriesOpen.value = false
  load()
}

async function onCopied(res: { added: number; source_nm_id: number }) {
  copyOpen.value = false
  notice.value = `Скопировано конкурентов: ${res.added} (источник ${res.source_nm_id}). Они добавлены в очередь на сбор описаний.`
  await load()
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

/** Подсказка по фразе: как её формулируют конкуренты (если формулировок несколько). */
function variantsTitle(p: NewCardPhrase): string {
  const variants = p.variants || []
  if (variants.length < 2) return ''
  return 'У конкурентов так:\n' + variants.map((v) => '· ' + v).join('\n')
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
  if (!await copyText(text || '')) {
    error.value = 'Не удалось скопировать текст'
    return
  }
  notice.value = 'Скопировано'
}

watch(() => route.params.nm, () => {
  result.value = null
  resultAt.value = ''
  notice.value = ''
  analyzeOpen.value = false
  generateOpen.value = false
  detailsOpen.value = false
  queriesOpen.value = false
  activeCompetitor.value = null
  load()
})

let queuePoll: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  load()
  queuePoll = setInterval(() => {
    if (queuePending.value || queueProcessing.value) load(true)
  }, 5000)
})

onUnmounted(() => {
  if (queuePoll) clearInterval(queuePoll)
})
</script>
