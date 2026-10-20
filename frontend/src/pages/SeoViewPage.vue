<template>
  <div class="container-xxl page-seo">
    <div class="page-seo__head">
      <h2 class="page-seo__title">SEO рекомендация #{{ id }}</h2>
      <router-link :to="{ path: '/seo/index', query: { status: rec?.status || 'new' } }" class="btn btn-sm btn-outline-secondary">← К списку</router-link>
    </div>
    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="loading" class="text-muted">Загрузка…</div>
    <div v-if="rec && !loading" class="page-seo__view-stack">
      <div class="card">
        <div class="card-body page-seo__view-product">
          <img :src="rec.card?.photo || '/images/no-photo.png'" alt="" class="page-seo__thumb page-seo__thumb--lg" />
          <div>
            <div class="fw-semibold">{{ rec.card?.title }}</div>
            <div class="small text-muted">nmID {{ rec.nmID }} • {{ rec.card?.subjectName }} • {{ rec.card?.brand }} • {{ rec.card?.vendorCode }}</div>
            <div>
              <a :href="`/wb/detail?nm_id=${rec.nmID}`" target="_blank" class="page-seo__ext-link">WB:{{ rec.nmID }}</a>
              <a :href="`/wb-search/card?nm_id=${rec.nmID}`" target="_blank" class="page-seo__ext-link">фразы</a>
            </div>
          </div>
          <div class="page-seo__view-actions">
            <button @click="startProcess()" class="btn btn-sm btn-primary"><i class="bi bi-robot"></i> Обработать с AI</button>
            <button v-if="rec.status === 'new'" @click="markViewed" class="btn btn-sm btn-success"><i class="bi bi-check"></i> Просмотрено</button>
            <button @click="requeue" class="btn btn-sm btn-outline-warning" title="Вернуть в обработку"><i class="bi bi-arrow-counterclockwise"></i> В обработку</button>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">Rationale</div>
        <div class="card-body page-seo__pre">{{ rec.rationale || '' }}</div>
      </div>
      <div class="page-seo__view-cols">
        <div class="card">
          <div class="card-header">Старое: {{ (rec.old_title || '').length }} / {{ (rec.old_description || '').length }}</div>
          <div class="card-body">
            <div class="page-seo__text-box">{{ rec.old_title || '' }}</div>
            <div class="page-seo__text-box page-seo__text-box--scroll">{{ rec.old_description || '' }}</div>
          </div>
        </div>
        <div class="card">
          <div class="card-header page-seo__new-head">Новое: {{ (rec.new_title || '').length }} / {{ (rec.new_description || '').length }}</div>
          <div class="card-body">
            <div class="page-seo__text-box page-seo__text-box--new">{{ rec.new_title || '' }}</div>
            <div class="page-seo__text-box page-seo__text-box--new page-seo__text-box--scroll">{{ rec.new_description || '' }}</div>
          </div>
        </div>
      </div>
      <div v-if="(rec.keywords_added || []).length || (rec.keywords_removed || []).length" class="card">
        <div class="card-header">Ключи</div>
        <div class="card-body">
          <span v-for="k in rec.keywords_added || []" :key="'a' + k" class="badge bg-success page-seo__key">{{ k }}</span>
          <span v-for="k in rec.keywords_removed || []" :key="'r' + k" class="badge bg-light text-dark page-seo__key">{{ k }}</span>
        </div>
      </div>
      <div class="card">
        <div class="card-header">Целевые фразы</div>
        <div class="card-body">
          <ul class="page-seo__targets">
            <li v-for="t in rec.targets || []" :key="t.id">
              {{ t.phrase }} <span class="text-muted small">(приоритет {{ t.priority }})</span>
              <a href="#" @click.prevent="removeTarget(t.id)" class="page-seo__perm-drop" title="Удалить">×</a>
            </li>
            <li v-if="!(rec.targets || []).length" class="text-muted">нет целевых фраз</li>
          </ul>
          <form @submit.prevent="addTarget" class="page-seo__target-form">
            <input v-model="newPhrase" class="form-control form-control-sm page-seo__target-input" placeholder="Новая фраза (до 500 симв)" maxlength="500" />
            <button type="submit" class="btn btn-sm btn-outline-primary">Добавить</button>
          </form>
        </div>
      </div>
      <div class="card">
        <div class="card-header page-seo__phrases-head">
          <span>Поисковые фразы из расчета {{ dispPeriod ? `(${dispPeriod})` : '' }}</span>
          <span class="small text-muted">Источник: wb_sr_report_item_phrases • сгруппировано по phrase, ORDER BY clicks</span>
        </div>
        <div class="card-body">
          <form @submit.prevent="applyPeriod" class="page-seo__phrases-filter">
            <label class="page-seo__phrases-date">с <input v-model="dateFrom" type="date" class="form-control form-control-sm" /></label>
            <label class="page-seo__phrases-date">по <input v-model="dateTo" type="date" class="form-control form-control-sm" /></label>
            <button type="button" @click="preset(30)" class="btn btn-sm btn-outline-secondary">30 дней</button>
            <button type="button" @click="preset(90)" class="btn btn-sm btn-outline-secondary">90 дней</button>
            <button type="submit" class="btn btn-sm btn-outline-primary" :disabled="liveLoading">Применить</button>
            <button v-if="isLive" type="button" @click="resetPeriod" class="btn btn-sm btn-link">Сброс</button>
            <span v-if="isLive" class="badge bg-info">пересчитано за {{ liveData?.period }}</span>
            <span v-if="liveLoading" class="small text-muted">Считаю…</span>
          </form>
          <div v-if="liveError" class="alert alert-danger py-1 small">{{ liveError }}</div>
          <div v-if="!hasPhrases" class="alert alert-warning mb-0">Нет фраз за период — ИИ строил только по карточке. Проверь <code>wb_sr_report_item_phrases</code> для nmID {{ rec.nmID }}</div>
          <template v-else>
            <h6 v-if="dispTop.length">Топ по кликам ({{ dispTop.length }})</h6>
            <div v-if="dispTop.length" class="table-responsive mb-3">
              <table class="table table-sm table-bordered align-middle page-seo__mini-table">
                <thead class="table-light"><tr><th>Фраза</th><th>Част</th><th>Поз</th><th>Клики</th><th>Заказы</th></tr></thead>
                <tbody>
                  <tr v-for="r in dispTop" :key="'t' + r.phrase"><td>{{ r.phrase }}</td><td class="text-end">{{ r.freq }}</td><td class="text-end">{{ r.avg_pos }}</td><td class="text-end">{{ r.clicks }}</td><td class="text-end">{{ r.orders }}</td></tr>
                </tbody>
              </table>
            </div>
            <h6 v-if="dispOrders.length">С заказами ({{ dispOrders.length }})</h6>
            <div v-if="dispOrders.length" class="table-responsive mb-3">
              <table class="table table-sm table-bordered align-middle page-seo__mini-table">
                <thead class="table-light"><tr><th>Фраза</th><th>Част</th><th>Поз</th><th>Клики</th><th>Заказы</th></tr></thead>
                <tbody>
                  <tr v-for="r in dispOrders" :key="'o' + r.phrase" class="table-success"><td>{{ r.phrase }}</td><td class="text-end">{{ r.freq }}</td><td class="text-end">{{ r.avg_pos }}</td><td class="text-end">{{ r.clicks }}</td><td class="text-end"><b>{{ r.orders }}</b></td></tr>
                </tbody>
              </table>
            </div>
            <h6 v-if="dispOpp.length">Opportunity поз 11-50 ({{ dispOpp.length }})</h6>
            <div v-if="dispOpp.length" class="table-responsive mb-3">
              <table class="table table-sm table-bordered align-middle page-seo__mini-table">
                <thead class="table-light"><tr><th>Фраза</th><th>Част</th><th>Поз</th><th>Клики</th></tr></thead>
                <tbody>
                  <tr v-for="r in dispOpp" :key="'p' + r.phrase" class="table-warning"><td>{{ r.phrase }}</td><td class="text-end">{{ r.freq }}</td><td class="text-end">{{ r.avg_pos }}</td><td class="text-end">{{ r.clicks }}</td></tr>
                </tbody>
              </table>
            </div>
            <div class="small text-muted">Сырые данные: <code>wb_sr_report_item_phrases WHERE nmID={{ rec.nmID }} AND date BETWEEN ...</code> • Если пусто — товар новый/нет отчетов sr.</div>
          </template>
        </div>
      </div>
      <div v-if="isAdmin" class="small text-muted">Модель: {{ rec.model || '—' }} • conf: {{ rec.confidence ?? '—' }} • prompt: {{ rec.prompt_tokens ?? '—' }} • compl: {{ rec.completion_tokens ?? '—' }}</div>
    </div>
    <SeoBatchModal :job-id="batchJobId" :open="batchOpen" @close="batchOpen = false" @done="onBatchDone" @fallback="onBatchFallback" />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-seo.css'
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { seoApi, type SeoRec, type SeoPhrases } from '../api/seo'
import { useAuthStore } from '../stores/auth'
import SeoBatchModal from '../components/seo/SeoBatchModal.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const id = Number(route.params.id)
const rec = ref<(SeoRec & { targets?: Array<{ id: number; nmID: number; phrase: string; priority: number }>; raw_json?: any }) | null>(null)
const loading = ref(false)
const error = ref('')
const newPhrase = ref('')
const isAdmin = computed(() => auth.isAdmin)
const batchJobId = ref<number | null>(null)
const batchOpen = ref(false)

async function startProcess(fallback = false) {
  if (!rec.value) return
  try {
    // окно фраз — из фильтра блока (как в PHP: даты влияют на AI)
    const r = await seoApi.process([rec.value.nmID], { date_from: dateFrom.value || undefined, date_to: dateTo.value || undefined, fallback })
    batchJobId.value = r.job_id
    batchOpen.value = true
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
function onBatchFallback() {
  startProcess(true)
}
function onBatchDone() {
  load()
}

// --- Блок «Поисковые фразы из расчета»: снапшот из raw_json.prompt + живой пересчёт ---
const liveData = ref<SeoPhrases | null>(null)
const liveLoading = ref(false)
const liveError = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const isLive = computed(() => liveData.value !== null)
const snap = computed(() => rec.value?.raw_json?.prompt || null)
const dispTop = computed(() => liveData.value?.top_phrases_by_clicks || snap.value?.top_phrases_by_clicks || [])
const dispOrders = computed(() => liveData.value?.phrases_with_orders || snap.value?.phrases_with_orders || [])
const dispOpp = computed(() => liveData.value?.opportunity_phrases_pos_11_50 || snap.value?.opportunity_phrases_pos_11_50 || [])
const dispPeriod = computed(() => liveData.value?.period || snap.value?.period || '')
const hasPhrases = computed(() => dispTop.value.length + dispOrders.value.length + dispOpp.value.length > 0)

function iso(d: Date) { return d.toISOString().slice(0, 10) }
function yesterday(): Date { return new Date(Date.now() - 864e5) }
function preset(days: number) {
  const to = yesterday()
  const from = new Date(to.getTime() - (days - 1) * 864e5)
  dateTo.value = iso(to)
  dateFrom.value = iso(from)
  applyPeriod()
}
function initDatesFromSnap() {
  if (dateFrom.value && dateTo.value) return
  const m = String(snap.value?.period || '').match(/(\d{4}-\d{2}-\d{2})\s*—\s*(\d{4}-\d{2}-\d{2})/)
  if (m) { dateFrom.value = m[1]; dateTo.value = m[2]; return }
  presetSilent(30)
}
function presetSilent(days: number) {
  const to = yesterday()
  dateTo.value = iso(to)
  dateFrom.value = iso(new Date(to.getTime() - (days - 1) * 864e5))
}
async function applyPeriod() {
  if (!dateFrom.value || !dateTo.value) return
  liveLoading.value = true
  liveError.value = ''
  try {
    liveData.value = await seoApi.phrases(id, dateFrom.value, dateTo.value)
  } catch (e: any) {
    liveError.value = e?.response?.data?.detail || String(e)
  } finally {
    liveLoading.value = false
  }
}
function resetPeriod() {
  liveData.value = null
  liveError.value = ''
  initDatesFromSnap()
}

async function load() {
  loading.value = true
  error.value = ''
  liveData.value = null
  try {
    rec.value = await seoApi.view(id)
    initDatesFromSnap()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}
async function markViewed() {
  if (!confirm('Отметить как просмотрено?')) return
  await seoApi.markViewed(id)
  router.replace({ path: '/seo/index', query: { status: 'viewed' } })
}
async function requeue() {
  await seoApi.requeue(id)
  load()
}
async function addTarget() {
  if (!newPhrase.value.trim() || !rec.value) return
  try {
    await seoApi.addTarget(rec.value.nmID, newPhrase.value.trim())
    newPhrase.value = ''
    load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
async function removeTarget(tid: number) {
  await seoApi.removeTarget(tid)
  load()
}
onMounted(load)
</script>
