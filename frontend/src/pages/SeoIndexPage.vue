<template>
  <div class="container-xxl page-seo">
    <div class="page-seo__head">
      <h2 class="page-seo__title">SEO рекомендации</h2>
      <div class="page-seo__tabs">
        <router-link :to="{ path: '/seo/index', query: { status: 'new' } }" class="btn btn-sm" :class="status === 'new' ? 'btn-primary' : 'btn-outline-primary'">
          К просмотру <span class="badge bg-white text-primary">{{ counts.new }}</span>
        </router-link>
        <router-link :to="{ path: '/seo/index', query: { status: 'viewed' } }" class="btn btn-sm" :class="status === 'viewed' ? 'btn-primary' : 'btn-outline-primary'">
          Просмотренные <span class="badge bg-white text-primary">{{ counts.viewed }}</span>
        </router-link>
      </div>
    </div>

    <div class="card page-seo__filter-card">
      <div class="card-body">
        <form @submit.prevent="applyQ" class="page-seo__filter-form">
          <div>
            <label class="form-label small">Поиск (nmID / название / артикул)</label>
            <input v-model="qInput" type="text" class="form-control form-control-sm page-seo__q" placeholder="526443466, Сваты, 11/25 ..." />
          </div>
          <div class="page-seo__filter-btns">
            <button type="submit" class="btn btn-sm btn-outline-secondary">Фильтр</button>
            <router-link :to="{ path: '/seo/index', query: { status } }" class="btn btn-sm btn-link">Сброс</router-link>
            <button type="button" @click="showUnprocessed = !showUnprocessed; if (showUnprocessed) loadUnprocessed()" class="btn btn-sm btn-outline-warning" title="Карточки по запросу без рекомендации (если пусто — топ 20)">
              <i class="bi bi-exclamation-circle"></i> Необработанные
            </button>
          </div>
          <div class="page-seo__filter-note">agg_daily_summary 30д → OpenRouter → wb_seo_recommendation</div>
        </form>
      </div>
    </div>

    <div v-if="showUnprocessed" class="card page-seo__unprocessed">
      <div class="card-header page-seo__unprocessed-head">
        <span><i class="bi bi-exclamation-circle text-warning"></i> Необработанные{{ q ? ` по “${q}”` : '' }} — {{ unprocessed.length }} шт</span>
        <button v-if="unprocessed.length" @click="startBatch(unprocessed.map((c) => c.nmID))" class="btn btn-sm btn-warning">
          <i class="bi bi-robot"></i> Обработать показанные
        </button>
      </div>
      <div v-if="!unprocessed.length" class="page-seo__empty">Необработанных не найдено — все уже в обработке (анти-спам 14д).</div>
      <div v-else class="wb-table-wrap">
        <table class="table table-bordered table-hover align-middle page-seo__mini-table">
          <thead class="table-light"><tr><th class="page-seo__photo-col">Фото</th><th>Товар</th><th>Продажи 30д</th><th class="page-seo__act-col"></th></tr></thead>
          <tbody>
            <tr v-for="c in unprocessed" :key="c.nmID">
              <td><img :src="c.photo || '/images/no-photo.png'" alt="" class="page-seo__thumb" /></td>
              <td>
                <div class="fw-semibold">{{ c.title }}</div>
                <div class="small text-muted">nmID {{ c.nmID }} • {{ c.subjectName || '' }} • {{ c.brand || '' }} • {{ c.vendorCode || '' }}</div>
              </td>
              <td class="text-end">{{ c.total_qnt }}</td>
              <td class="text-center"><button @click="startBatch([c.nmID])" class="btn btn-sm btn-outline-primary"><i class="bi bi-robot"></i> Обработать с AI</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-footer small text-muted">Топ необработанных по <code>agg_daily_summary 30д</code> • Кнопка обработает видимые (до 20) фоном с опросом.</div>
    </div>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="loading" class="text-muted">Загрузка…</div>

    <div v-if="!loading" class="wb-table-wrap">
      <table class="page-seo__table">
        <colgroup><col class="page-seo__col-product" /><col class="page-seo__col-rationale" /><col class="page-seo__col-old" /><col class="page-seo__col-new" /><col class="page-seo__col-keys" /></colgroup>
        <thead><tr><th>Товар</th><th>Rationale</th><th>Старое</th><th>Новое</th><th>Ключи</th></tr></thead>
        <tbody>
          <tr v-for="m in items" :key="m.id" @click="toggleRow($event)">
            <td class="page-seo__product-cell">
              <div class="page-seo__product-top">
                <img :src="m.card?.photo || '/images/no-photo.png'" alt="" class="page-seo__thumb" />
                <div class="page-seo__product-text">
                  <div class="page-seo__product-title" :title="m.card?.title || ''">{{ shortTitle(m.card?.title) }}</div>
                  <div class="page-seo__product-sub">{{ (m.card?.subjectName || '') + ' • ' + (m.card?.brand || '') }}</div>
                  <div class="page-seo__product-sub">{{ m.card?.vendorCode || '' }}</div>
                  <div>
                    <a :href="`/wb/detail?nm_id=${m.nmID}`" target="_blank" class="page-seo__ext-link">WB:{{ m.nmID }}</a>
                    <a :href="`/wb-search/card?nm_id=${m.nmID}`" target="_blank" class="page-seo__ext-link">фразы</a>
                  </div>
                </div>
              </div>
              <div class="page-seo__row-btns">
                <router-link :to="`/seo/view/${m.id}`" class="btn btn-xs btn-outline-primary" title="Открыть"><i class="bi bi-eye"></i></router-link>
                <button v-if="m.status === 'new'" @click="markViewed(m.id)" class="btn btn-xs btn-success" title="Просмотрено"><i class="bi bi-check"></i></button>
                <span v-else class="badge bg-success">просмотрено</span>
                <button @click="requeue(m.id)" class="btn btn-xs" :class="m.status === 'viewed' ? 'btn-warning' : 'btn-outline-warning'" title="Вернуть в обработку"><i class="bi bi-arrow-counterclockwise"></i></button>
              </div>
              <div class="page-seo__rec-id">#{{ m.id }} • {{ fmtDT(m.created_at) }}</div>
              <div v-if="isAdmin" class="page-seo__admin-block">
                <div>{{ m.model || '-' }}</div>
                <div>conf: {{ confPct(m.confidence) }} • prompt: {{ m.prompt_tokens ?? '—' }} • compl: {{ m.completion_tokens ?? '—' }}</div>
              </div>
            </td>
            <td class="page-seo__rationale"><div class="page-seo__pre">{{ m.rationale || '' }}</div></td>
            <td class="page-seo__old">
              <div class="small text-muted">Заголовок <span class="badge bg-light text-dark">{{ (m.old_title || '').length }}</span></div>
              <div class="page-seo__text-box">{{ m.old_title || '' }}</div>
              <div class="small text-muted">Описание <span class="badge bg-light text-dark">{{ (m.old_description || '').length }}</span></div>
              <div class="page-seo__text-box page-seo__text-box--scroll">{{ shortDesc(m.old_description) }}<router-link v-if="(m.old_description || '').length > 500" :to="`/seo/view/${m.id}`" class="small"> весь →</router-link></div>
              <div class="page-seo__phrases-line">фраз: {{ m.phrases_count }}<span v-if="!m.phrases_count" class="badge bg-warning text-dark">нет данных</span></div>
            </td>
            <td class="page-seo__new">
              <div class="small text-success">Заголовок <span class="badge bg-success">{{ (m.new_title || '').length }}</span></div>
              <div class="page-seo__text-box page-seo__text-box--new">{{ m.new_title || '' }}</div>
              <div class="small text-success">Описание <span class="badge bg-success">{{ (m.new_description || '').length }}</span></div>
              <div class="page-seo__text-box page-seo__text-box--new page-seo__text-box--scroll">{{ shortDesc(m.new_description) }}<router-link v-if="(m.new_description || '').length > 500" :to="`/seo/view/${m.id}`" class="small"> весь →</router-link></div>
              <div v-if="!m.phrases_count" class="small text-danger">фраз нет — проверь</div>
            </td>
            <td class="page-seo__keys">
              <div v-if="(m.keywords_added || []).length">
                <div class="small text-success">+ добавлены</div>
                <div><span v-for="k in m.keywords_added" :key="k" class="badge bg-success page-seo__key">{{ k }}</span></div>
              </div>
              <div v-else class="small text-muted">+ нет</div>
              <div v-if="(m.keywords_removed || []).length">
                <div class="small text-danger">− удалены</div>
                <div><span v-for="k in m.keywords_removed" :key="k" class="badge bg-light text-dark page-seo__key">{{ k }}</span></div>
              </div>
            </td>
          </tr>
          <tr v-if="!items.length"><td colspan="5" class="page-seo__empty">Нет рекомендаций. Запусти <code>php yii seo/analyze --limit=20</code> или обработай карточки ниже.</td></tr>
        </tbody>
      </table>
    </div>
    <div v-if="!loading" class="small text-muted">Показаны записи {{ from }}-{{ to }} из {{ total }}</div>

    <div v-if="status === 'new' && !loading && !total && q" class="card page-seo__cards-card">
      <div class="card-header page-seo__cards-head">
        <span>Карточки по запросу “{{ q }}” — {{ cardsTotal }} шт</span>
        <button v-if="cards.length" @click="startBatch(allIds)" class="btn btn-sm btn-primary"><i class="bi bi-robot"></i> Обработать все ({{ cardsTotal }})</button>
      </div>
      <div v-if="!cards.length" class="page-seo__empty">Карточек не найдено. Попробуй другой запрос.</div>
      <div v-else class="wb-table-wrap">
        <table class="table table-bordered table-hover align-middle page-seo__mini-table">
          <thead class="table-light"><tr><th class="page-seo__photo-col">Фото</th><th>Товар</th><th class="page-seo__act-col"></th></tr></thead>
          <tbody>
            <tr v-for="c in cards" :key="c.nmID">
              <td><img :src="c.photo || '/images/no-photo.png'" alt="" class="page-seo__thumb" /></td>
              <td>
                <div class="fw-semibold">{{ c.title }}</div>
                <div class="small text-muted">nmID {{ c.nmID }} • {{ c.subjectName }} • {{ c.brand }} • {{ c.vendorCode }}</div>
              </td>
              <td class="text-center"><button @click="startBatch([c.nmID])" class="btn btn-sm btn-outline-primary"><i class="bi bi-robot"></i> Обработать с AI</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <SeoBatchModal :job-id="batchJobId" :open="batchOpen" @close="batchOpen = false" @done="onBatchDone" />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-seo.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { seoApi, type SeoRec } from '../api/seo'
import { useAuthStore } from '../stores/auth'
import SeoBatchModal from '../components/seo/SeoBatchModal.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const status = computed(() => route.query.status === 'viewed' ? 'viewed' : 'new')
const q = ref(String(route.query.q || ''))
const qInput = ref(q.value)
const page = ref(Number(route.query.page || 1))
const items = ref<SeoRec[]>([])
const total = ref(0)
const counts = ref({ new: 0, viewed: 0 })
const loading = ref(false)
const error = ref('')
const showUnprocessed = ref(route.query.unprocessed !== undefined)
const unprocessed = ref<Array<{ nmID: number; title?: string; subjectName?: string; brand?: string; vendorCode?: string; photo?: string | null; total_qnt: number }>>([])
const cards = ref<Array<{ nmID: number; title?: string; subjectName?: string; brand?: string; vendorCode?: string; photo?: string | null }>>([])
const cardsTotal = ref(0)
const allIds = ref<number[]>([])
const batchJobId = ref<number | null>(null)
const batchOpen = ref(false)

const isAdmin = computed(() => auth.isAdmin)
const from = computed(() => total.value ? (page.value - 1) * 20 + 1 : 0)
const to = computed(() => Math.min(page.value * 20, total.value))
const fmtDT = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
const shortTitle = (t: any) => (t || '').slice(0, 60)
const shortDesc = (t: any) => (t || '').slice(0, 500)
const confPct = (c: any) => c != null ? Math.round(Number(c) * 100) + '%' : '—'
function toggleRow(e: Event) {
  if ((e.target as HTMLElement).closest('a,button')) return
  const tr = (e.target as HTMLElement).closest('tr')
  tr?.classList.toggle('table-active')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await seoApi.list(status.value, q.value, page.value)
    items.value = r.items
    total.value = r.total
    counts.value = r.counts
    if (status.value === 'new' && !r.total && q.value) await loadCards()
    else { cards.value = []; cardsTotal.value = 0; allIds.value = [] }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

async function loadUnprocessed() {
  try {
    unprocessed.value = (await seoApi.unprocessed(q.value)).items
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

async function loadCards() {
  try {
    const r = await seoApi.cards(q.value)
    cards.value = r.items
    cardsTotal.value = r.total
    allIds.value = r.all_ids
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

function applyQ() {
  page.value = 1
  router.replace({ path: '/seo/index', query: { status: status.value, q: qInput.value || undefined } })
}
function onQueryChange() {
  q.value = String(route.query.q || '')
  qInput.value = q.value
  page.value = Number(route.query.page || 1)
  if (route.query.unprocessed !== undefined && !unprocessed.value.length) loadUnprocessed()
  load()
}

async function markViewed(id: number) {
  if (!confirm('Отметить как просмотрено?')) return
  await seoApi.markViewed(id)
  load()
}
async function requeue(id: number) {
  await seoApi.requeue(id)
  load()
}
async function startBatch(nmIds: number[]) {
  if (!nmIds.length) return
  try {
    const r = await seoApi.process(nmIds)
    batchJobId.value = r.job_id
    batchOpen.value = true
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
function onBatchDone() {
  load()
  if (showUnprocessed.value) loadUnprocessed()
}

onMounted(() => {
  load()
  if (showUnprocessed.value) loadUnprocessed()
})
watch(() => route.query, onQueryChange)
</script>
