<template>
  <div class="container-xxl page-seo">
    <WbWorkspaceHead title="SEO рекомендации" :subtabs="seoSubTabs" workspace-active="seo" />

    <div class="card page-seo__filter-card">
      <div class="card-body">
        <form @submit.prevent="applyQ" class="page-seo__filter-form">
          <div>
            <label class="form-label small">Поиск (nmID / название / артикул)</label>
            <input v-model="qInput" type="text" class="form-control form-control-sm page-seo__q" placeholder="526443466, Сваты, 11/25 ..." />
          </div>
          <div class="page-seo__filter-btns">
            <button type="submit" class="btn btn-sm btn-outline-secondary">Фильтр</button>
            <button type="button" class="btn btn-sm btn-link" @click="resetFilters">Сброс</button>
            <button type="button" class="btn btn-sm btn-outline-warning" :class="{ active: showUnprocessed }" @click="toggleUnprocessed" title="Карточки по запросу без рекомендации (если пусто — топ 20)">
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
      <div class="card-footer small text-muted">Топ необработанные по <code>agg_daily_summary 30д</code> • Кнопка обработает видимые (до 20) фоном с опросом.</div>
    </div>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="loading" class="text-muted">Загрузка…</div>

    <div v-if="!loading" class="wb-table-wrap">
      <table class="page-seo__table page-seo__feed">
        <colgroup><col class="page-seo__feed-col-product" /><col /></colgroup>
        <thead><tr><th>Товар</th><th>Что изменится</th></tr></thead>
        <tbody>
          <template v-for="m in items" :key="m.id">
            <!-- Сводная строка: карточка + что поменялось (как в мокапе 1b) -->
            <tr class="page-seo__feed-row">
              <td class="page-seo__feed-product">
                <div class="page-seo__product-top">
                  <img :src="m.card?.photo || '/images/no-photo.png'" class="page-seo__thumb" alt="" />
                  <div class="page-seo__product-text">
                    <div class="page-seo__product-title" :title="m.card?.title || ''">{{ shortTitle(m.card?.title) }}</div>
                    <div class="page-seo__product-sub">{{ (m.card?.subjectName || '') + ' • ' + (m.card?.brand || '') }}</div>
                    <div>
                      <a :href="`/wb/detail?nm_id=${m.nmID}`" target="_blank" class="page-seo__ext-link">WB:{{ m.nmID }}</a>
                      <a :href="`/wb-search/card?nm_id=${m.nmID}`" target="_blank" class="page-seo__ext-link">фразы</a>
                    </div>
                  </div>
                </div>
                <div class="page-seo__row-btns">
                  <router-link :to="`/seo/view/${m.id}`" class="btn btn-xs btn-outline-primary" title="Открыть"><i class="bi bi-eye"></i></router-link>
                  <button v-if="m.status === 'new'" class="btn btn-xs btn-outline-success" title="Отметить просмотренным" @click.stop="markViewed(m.id)"><i class="bi bi-check"></i></button>
                  <span v-else class="btn btn-xs btn-success" title="Просмотрено"><i class="bi bi-check"></i></span>
                  <button class="btn btn-xs" :class="m.status === 'viewed' ? 'btn-warning' : 'btn-outline-warning'" title="Вернуть в обработку" @click.stop="requeue(m.id)"><i class="bi bi-arrow-counterclockwise"></i></button>
                </div>
                <div class="page-seo__rec-id">#{{ m.id }} • {{ fmtDT(m.created_at) }} • conf {{ confPct(m.confidence) }}</div>
              </td>
              <td class="page-seo__feed-changes">
                <div class="page-seo__feed-metric">
                  <span class="page-seo__feed-label">Заголовок</span>
                  <template v-if="titleChanged(m)">
                    <span class="page-seo__feed-old" :title="m.old_title || ''">{{ titleDiff(m).old }}</span>
                    <i class="bi bi-arrow-right page-seo__feed-arrow"></i>
                    <b :title="m.new_title || ''">{{ titleDiff(m).neu }}</b>
                  </template>
                  <template v-else><b>без изменений</b></template>
                  <span class="page-seo__feed-tag">{{ (m.old_title || '').length }}→{{ (m.new_title || '').length }}</span>
                </div>
                <div class="page-seo__feed-metric">
                  <span class="page-seo__feed-label">Описание</span>
                  {{ (m.old_description || '').length }} → <b>{{ (m.new_description || '').length }}</b>
                  <span class="page-seo__feed-tag page-seo__feed-tag--g">+{{ (m.keywords_added || []).length }} / −{{ (m.keywords_removed || []).length }} ключей</span>
                  <span v-if="!m.phrases_count" class="page-seo__feed-tag page-seo__feed-tag--warn">фраз 0</span>
                </div>
                <div v-if="(m.keywords_added || []).length" class="page-seo__feed-metric">
                  <span class="page-seo__feed-label">Ключи</span>
                  <span class="page-seo__feed-keys-text">{{ keyPreview(m) }}</span>
                </div>
              </td>
            </tr>

            <!-- Раскрытый блок — всегда виден (как в мокапе 1b «развёрнутый») -->
            <tr class="page-seo__feed-detail-row">
              <td colspan="2">
                <div class="page-seo__feed-detail">
                  <div class="page-seo__feed-two">
                    <div class="page-seo__feed-box">
                      <div class="page-seo__feed-box-head">Было — ЗАГОЛОВОК {{ (m.old_title || '').length }}</div>
                      <div class="page-seo__feed-box-text">{{ m.old_title || '—' }}</div>
                    </div>
                    <div class="page-seo__feed-box page-seo__feed-box--new">
                      <div class="page-seo__feed-box-head">Стало — ЗАГОЛОВОК {{ (m.new_title || '').length }}</div>
                      <div class="page-seo__feed-box-text">{{ m.new_title || '—' }}</div>
                    </div>
                  </div>

                  <div class="page-seo__feed-section">
                    <div class="page-seo__feed-section-head">Описания (было {{ (m.old_description || '').length }} / стало {{ (m.new_description || '').length }})</div>
                    <div class="page-seo__feed-two">
                      <div class="page-seo__feed-box">
                        <div class="page-seo__feed-box-head">Было</div>
                        <div class="page-seo__feed-box-text">{{ m.old_description || '—' }}</div>
                      </div>
                      <div class="page-seo__feed-box page-seo__feed-box--new">
                        <div class="page-seo__feed-box-head">Стало</div>
                        <div class="page-seo__feed-box-text">{{ m.new_description || '—' }}</div>
                      </div>
                    </div>
                  </div>

                  <div v-if="m.rationale" class="page-seo__feed-section">
                    <div class="page-seo__feed-section-head">Почему (ИИ)</div>
                    <div class="page-seo__feed-text">{{ m.rationale }}</div>
                  </div>

                  <div v-if="(m.keywords_added || []).length || (m.keywords_removed || []).length" class="page-seo__feed-section">
                    <div class="page-seo__feed-section-head">Ключи: + добавлены {{ (m.keywords_added || []).length }} / − удалены {{ (m.keywords_removed || []).length }}</div>
                    <div v-if="(m.keywords_added || []).length" class="page-seo__feed-keys">
                      <span v-for="k in m.keywords_added" :key="'ka' + k" class="page-seo__feed-key page-seo__feed-key--add">{{ k }}</span>
                    </div>
                    <div v-if="(m.keywords_removed || []).length" class="page-seo__feed-keys" style="margin-top: 6px">
                      <span v-for="k in m.keywords_removed" :key="'kr' + k" class="page-seo__feed-key page-seo__feed-key--rm">{{ k }}</span>
                    </div>
                  </div>

                  <div class="page-seo__feed-meta">
                    <span v-if="m.card?.vendorCode">Артикул: {{ m.card?.vendorCode }}</span>
                    <span v-if="isAdmin">{{ m.model || '-' }} • prompt {{ m.prompt_tokens ?? '—' }}/compl {{ m.completion_tokens ?? '—' }}</span>
                  </div>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="!items.length"><td colspan="2" class="page-seo__empty">Нет рекомендаций. Запусти обработку карточек — рекомендации появятся здесь.</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Пагинация: 20 записей на страницу, всё в URL -->
    <div v-if="!loading && total" class="page-seo__pager">
      <div class="small text-muted">Показаны записи {{ from }}–{{ to }} из {{ total }}</div>
      <nav aria-label="Страницы ленты">
        <ul class="pagination pagination-sm mb-0">
          <li class="page-item" :class="{ disabled: page <= 1 }">
            <a class="page-link" href="#" @click.prevent="goPage(page - 1)">‹</a>
          </li>
          <template v-for="(p, i) in pageItems" :key="'pg' + i">
            <li v-if="p === '…'" class="page-item disabled"><span class="page-link">…</span></li>
            <li v-else class="page-item" :class="{ active: p === page }">
              <a class="page-link" href="#" @click.prevent="goPage(p)">{{ p }}</a>
            </li>
          </template>
          <li class="page-item" :class="{ disabled: page >= pages }">
            <a class="page-link" href="#" @click.prevent="goPage(page + 1)">›</a>
          </li>
        </ul>
      </nav>
    </div>

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
                <div class="small text-muted">nmID {{ c.nmID }} • {{ c.subjectName || '' }} • {{ c.brand || '' }} • {{ c.vendorCode || '' }}</div>
              </td>
              <td class="text-center"><button @click="startBatch([c.nmID])" class="btn btn-sm btn-outline-primary"><i class="bi bi-robot"></i> Обработать с AI</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <SeoBatchModal :job-id="batchJobId" :open="batchOpen" @close="batchOpen = false" @done="onBatchDone" @fallback="onBatchFallback" />
    <WbConfirmDialog
      :open="confirmState.open"
      :text="confirmState.text"
      :hint="confirmState.hint"
      :confirm-text="confirmState.confirmText"
      :busy="confirmBusy"
      @confirm="onConfirm"
      @cancel="confirmState.open = false"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-seo.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { seoApi, type SeoRec } from '../api/seo'
import { useAuthStore } from '../stores/auth'
import SeoBatchModal from '../components/seo/SeoBatchModal.vue'
import WbConfirmDialog from '@/components/common/WbConfirmDialog.vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { type SubTab } from '@/components/common/workspaceTabs'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/** Размер страницы ленты — совпадает с backend PAGE_SIZE (seo_service.PAGE_SIZE). */
const PAGE_SIZE = 20

/** Состояние ленты живёт в URL: status / q / page / unprocessed. */

/** Статус ленты: all (все) | new (к просмотру) | viewed (просмотренные). */
const status = computed<'all' | 'new' | 'viewed'>(() => {
  const s = String(route.query.status || '')
  return s === 'new' || s === 'viewed' || s === 'all' ? s : 'all'
})
/** Поисковый запрос — из URL. */
const q = computed(() => String(route.query.q || ''))
const qInput = ref(q.value)
/** Номер страницы — из URL. */
const page = computed(() => Math.max(1, Number(route.query.page || 1) || 1))

const items = ref<SeoRec[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

/** Подменю ленты рекомендаций: Все / Просмотр / Просмотренные (без счётчиков). */
const seoSubTabs = computed<SubTab[]>(() => [
  { id: 'all', label: 'Все', to: '/seo/index?status=all',
    title: 'Все рекомендации — и просмотренные, и ещё нет' },
  { id: 'new', label: 'Просмотр', to: '/seo/index?status=new',
    title: 'Ещё не просмотренные — ждут просмотра' },
  { id: 'viewed', label: 'Просмотренные', to: '/seo/index?status=viewed',
    title: 'Уже просмотренные рекомендации' },
])

/** Детали рекомендации раскрыты всегда — кликать не нужно. */

/** Пагинация. */
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const from = computed(() => (total.value ? (page.value - 1) * PAGE_SIZE + 1 : 0))
const to = computed(() => Math.min(page.value * PAGE_SIZE, total.value))
/** Номера страниц: 1 … ±2 … последняя. */
const pageItems = computed<Array<number | string>>(() => {
  const n = pages.value
  const p = page.value
  if (n <= 7) return Array.from({ length: n }, (_, i) => i + 1)
  const out: Array<number | string> = [1]
  if (p > 4) out.push('…')
  for (let i = Math.max(2, p - 1); i <= Math.min(n - 1, p + 1); i++) out.push(i)
  if (p < n - 3) out.push('…')
  out.push(n)
  return out
})
function goPage(p: number | string) {
  if (typeof p !== 'number' || !Number.isFinite(p)) return
  if (p < 1 || p > pages.value || p === page.value) return
  applyRoute({ page: p })
}

/**
 * Запись состояния в URL. Единственная точка записи: сравниваем целевой URL
 * с текущим и делаем replace только при реальном изменении — иначе цикл
 * watch(query) → load() → replace(query) → watch(...)
 */
function applyRoute(patch: { q?: string; page?: number } = {}) {
  const nq = (patch.q !== undefined ? patch.q : q.value).trim()
  const np = patch.page !== undefined ? Math.max(1, patch.page) : 1
  const query: Record<string, string> = { status: status.value }
  if (nq) query.q = nq
  if (np > 1) query.page = String(np)
  if (showUnprocessed.value) query.unprocessed = '1'
  const target = router.resolve({ path: '/seo/index', query }).fullPath
  if (target !== route.fullPath) router.replace(target)
}
function applyQ() { applyRoute({ q: qInput.value, page: 1 }) }
function resetFilters() { qInput.value = ''; applyRoute({ q: '', page: 1 }) }
function toggleUnprocessed() {
  showUnprocessed.value = !showUnprocessed.value
  applyRoute({ page: 1 })
  if (showUnprocessed.value) loadUnprocessed()
  else unprocessed.value = []
}

// Диалог подтверждения вместо нативного confirm()
const confirmBusy = ref(false)
const confirmState = ref({
  open: false,
  text: '',
  hint: '',
  confirmText: 'Подтвердить',
  action: null as null | (() => Promise<void>),
})

async function onConfirm() {
  const action = confirmState.value.action
  if (!action || confirmBusy.value) return
  confirmBusy.value = true
  try {
    await action()
    confirmState.value.open = false
  } finally {
    confirmBusy.value = false
  }
}
const showUnprocessed = ref(route.query.unprocessed !== undefined)
const unprocessed = ref<Array<{ nmID: number; title?: string; subjectName?: string; brand?: string; vendorCode?: string; photo?: string | null; total_qnt: number }>>([])
const cards = ref<Array<{ nmID: number; title?: string; subjectName?: string; brand?: string; vendorCode?: string; photo?: string | null }>>([])
const cardsTotal = ref(0)
const allIds = ref<number[]>([])
const batchJobId = ref<number | null>(null)
const batchOpen = ref(false)
const lastLaunch = ref<{ nmIds: number[]; opts?: { date_from?: string; date_to?: string; fallback?: boolean } } | null>(null)

const isAdmin = computed(() => auth.isAdmin)
import { useDateFmt } from '../composables/useDateFmt'
const { fmtDT } = useDateFmt()
const shortTitle = (t: any) => (t || '').slice(0, 60)
const confPct = (c: any) => c != null ? Math.round(Number(c) * 100) + '%' : '—'
const titleChanged = (m: SeoRec) => (m.old_title || '') !== (m.new_title || '')
/**
 * Компактный показ смены заголовка: общая часть — один раз (зачёркнутая),
 * новая часть — после «…». Так видно, что именно изменилось, и строка не рвётся.
 */
function titleDiff(m: SeoRec): { old: string; neu: string } {
  const o = m.old_title || ''
  const n = m.new_title || ''
  let l = 0
  while (l < o.length && l < n.length && o[l] === n[l]) l++
  const common = o.slice(0, l).trim()
  const tail = n.slice(l).trim()
  if (!common) return { old: o.length > 40 ? o.slice(0, 40) + '…' : o, neu: n.length > 40 ? n.slice(0, 40) + '…' : n }
  return { old: common, neu: tail ? '…' + tail : n }
}
/** Ключи в свёрнутой строке — коротким текстом (как в мокапе), полный список — в раскрытии. */
function keyPreview(m: SeoRec): string {
  const ks = m.keywords_added || []
  const short = ks.slice(0, 2).map((k) => (k.length > 28 ? k.slice(0, 28) + '…' : k)).join(', ')
  return ks.length > 2 ? `${short} · ещё ${ks.length - 2} →` : short
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await seoApi.list(status.value, q.value, page.value)
    items.value = r.items
    total.value = r.total
    if (status.value === 'new' && !r.total && q.value) await loadCards()
    else { cards.value = []; cardsTotal.value = 0; allIds.value = [] }
    // Страница вышла за диапазон (после просмотра/удаления) — вернуть на последнюю
    if (total.value && page.value > pages.value) applyRoute({ page: pages.value })
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

async function markViewed(id: number) {
  if (confirmState.value.open) return
  confirmState.value = {
    open: true,
    text: 'Отметить рекомендацию как просмотренную?',
    hint: 'Она уйдёт из списка «новые».',
    confirmText: 'Отметить',
    action: async () => {
      await seoApi.markViewed(id)
      load()
    },
  }
}
async function requeue(id: number) {
  await seoApi.requeue(id)
  load()
}
async function startBatch(nmIds: number[], opts?: { date_from?: string; date_to?: string; fallback?: boolean }) {
  if (!nmIds.length) return
  lastLaunch.value = { nmIds, opts }
  try {
    const r = await seoApi.process(nmIds, opts)
    batchJobId.value = r.job_id
    batchOpen.value = true
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}
function onBatchFallback() {
  const l = lastLaunch.value
  if (l) startBatch(l.nmIds, { ...l.opts, fallback: true })
}
function onBatchDone() {
  load()
  if (showUnprocessed.value) loadUnprocessed()
}

/** URL → состояние → перезагрузка выборки. */
function onQueryChange() {
  qInput.value = q.value
  showUnprocessed.value = route.query.unprocessed !== undefined
  if (showUnprocessed.value) {
    if (!unprocessed.value.length) loadUnprocessed()
  } else {
    unprocessed.value = []
  }
  load()
}

onMounted(() => {
  load()
  if (showUnprocessed.value) loadUnprocessed()
})
watch(() => route.query, onQueryChange)
</script>
