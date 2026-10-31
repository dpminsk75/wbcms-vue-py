<template>
  <div class="wb-universal-filter">
    <div class="wb-universal-filter__presets">
      <div class="wb-universal-filter__presets-group">
        <button v-for="p in presets" :key="p.id" class="btn btn-sm" :class="activePreset === p.id ? 'btn--brand' : 'btn--outline'" @click="applyPreset(p.id)">{{ p.label }}</button>
      </div>
      <div v-if="showQuick && quickButtons.length" class="wb-universal-filter__presets-group wb-universal-filter__presets-group--right">
        <button v-for="btn in quickButtons" :key="btn.nm_id" class="btn btn-panel btn-sm" @click="onQuickClick(btn)" :title="'nm_id ' + btn.nm_id">
          <i v-if="btn.icon" :class="btn.icon"></i> {{ btn.label }}
        </button>
      </div>
    </div>
    <div class="row g-2 align-items-start">
      <div class="col-md-2">
        <label class="form-label mb-1 wb-universal-filter__label">Дата с</label>
        <WbDateInput v-model="dateFrom" />
      </div>
      <div class="col-md-2">
        <label class="form-label mb-1 wb-universal-filter__label">Дата по</label>
        <WbDateInput v-model="dateTo" />
      </div>
      <div v-if="showProduct" class="col-md-4 wb-universal-filter__product">
        <label class="form-label mb-1 wb-universal-filter__label">Товар</label>
        <input
          :value="productLabel"
          class="form-control"
          placeholder="nm_id, артикул или часть названия..."
          autocomplete="off"
          @input="onProductInput"
          @focus="popupOpen = suggestions.length > 0"
          @blur="closeSuggest"
        />
        <!-- свой попап вместо нативного <datalist>: браузерный уезжает в сторону и перекрывает страницу -->
        <div v-if="popupOpen && suggestions.length" class="wb-universal-filter__suggest">
          <button
            v-for="c in suggestions"
            :key="c.nmID"
            type="button"
            class="wb-universal-filter__suggest-row"
            @mousedown.prevent="pickSuggestion(c)"
          >
            <span class="wb-universal-filter__suggest-nm">{{ c.nmID }}</span>
            <span class="wb-universal-filter__suggest-title">{{ c.title }}</span>
            <span v-if="c.vendorCode" class="wb-universal-filter__suggest-vc">{{ c.vendorCode }}</span>
          </button>
        </div>
        <!-- выбранная карточка: значение + сброс (как в WbCardSelect) -->
        <div v-if="product" class="wb-universal-filter__picked">
          <span class="wb-universal-filter__picked-label">Выбрано: {{ product }}</span>
          <button type="button" class="btn btn-sm btn-light wb-universal-filter__picked-btn"
                  @mousedown.prevent @click="clearProduct">
            × Сбросить
          </button>
        </div>
      </div>
      <template v-if="showBrandCategory">
        <div class="col-md-2">
          <label class="form-label mb-1 wb-universal-filter__label">{{ brandLabel }}</label>
          <select v-model="brand" class="form-control" @change="emit('apply')">
            <option value="">Все</option>
            <option v-for="b in brands" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 wb-universal-filter__label">{{ categoryLabel }}</label>
          <select v-model="category" class="form-control" @change="emit('apply')">
            <option value="">Все</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </template>
    </div>
    <!-- поля страницы — своей строкой над кнопками (слот #fields) -->
    <div v-if="$slots.fields" class="wb-universal-filter__fields">
      <slot name="fields" />
    </div>
    <div class="wb-universal-filter__btns">
      <button class="btn btn--brand wb-universal-filter__apply" @click="emit('apply')">Применить</button>
      <button class="btn btn--outline wb-universal-filter__apply" @click="onReset">Сбросить</button>
      <!-- доп. поля конкретной страницы (слот #extra) -->
      <slot name="extra" />
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { api } from '@/api/client'
import { DEFAULT_PRESETS_UNIVERSAL } from '@/constants/presets'
import WbDateInput from './WbDateInput.vue'

// Общий фильтр в духе fbs-report: пресеты + даты + Товар-маска + Бренд + Категория.
// Товар — свободная маска (часть nm_id/vendorCode/названия, резолвит бэк),
// выбор из подсказок подставляет vendorCode (тоже маска, не жёсткий nm_id).
// Пустой товар + пустые бренд/категория = все продажи.
const props = withDefaults(defineProps<{
  brands?: string[]
  categories?: string[]
  showProduct?: boolean
  showBrandCategory?: boolean
  defaultPreset?: string
  presetEnd?: 'today' | 'yesterday'
  categoryLabel?: string
  brandLabel?: string
  listId?: string
  showQuick?: boolean
  quickButtonsProp?: any[] | null
  /** Свой набор пресетов (по умолчанию — DEFAULT_PRESETS). */
  presets?: { id: string; label: string }[]
}>(), {
  brands: () => [], categories: () => [],
  showProduct: true, showBrandCategory: true,
  defaultPreset: '30', presetEnd: 'today',
  categoryLabel: 'Категория', brandLabel: 'Бренд', listId: 'wbuf-product-list',
  showQuick: true, quickButtonsProp: null,
  presets: () => DEFAULT_PRESETS_UNIVERSAL,
})

const dateFrom = defineModel<string>('dateFrom', { default: '' })
const dateTo = defineModel<string>('dateTo', { default: '' })
const product = defineModel<string>('product', { default: '' })
const brand = defineModel<string>('brand', { default: '' })
const category = defineModel<string>('category', { default: '' })

const emit = defineEmits<{
  (e: 'apply'): void
  (e: 'reset'): void
}>()

/** Пресеты по умолчанию — из общего модуля (экспорт из .vue запрещён). */
const activePreset = ref(props.defaultPreset)
const suggestions = ref<any[]>([])
const popupOpen = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null
let reqSeq = 0

// Поле «Товар»: наружу уходит `product` (то, что бэк должен фильтровать),
// в инпуте показывается `productLabel` (при выборе карточки — «nmID | название»).
// Разделение нужно, чтобы на бэк уходил однозначный nmID, а не подпись.
const productLabel = ref(String(product.value || ''))
let lastSet = String(product.value || '')   // что выставили сами — чтобы отличить внешнее изменение

/** Программная подстановка: попап закрываем, поиск подсказок не запускаем. */
const setProduct = (value: string, label?: string) => {
  lastSet = value
  product.value = value
  productLabel.value = label ?? value
  suggestions.value = []
  popupOpen.value = false
}

/** Поиск подсказок по введённому тексту (debounce 300 мс). */
const scheduleSuggest = (raw: string) => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = String(raw || '').trim()
  if (q.length < 2) { suggestions.value = []; popupOpen.value = false; return }
  searchTimer = setTimeout(async () => {
    const my = ++reqSeq
    try {
      const { data: d } = await api.get('/api/wb/cards', { params: { q, limit: 20 } })
      if (my !== reqSeq) return
      suggestions.value = Array.isArray(d) ? d : (d?.items ?? [])
      popupOpen.value = suggestions.value.length > 0
    } catch { /* noop */ }
  }, 300)
}

/** Ручной ввод: значение — и подпись, и фильтр (маска). */
const onProductInput = (e: Event) => {
  const v = (e.target as HTMLInputElement).value
  productLabel.value = v
  lastSet = v
  product.value = v
  scheduleSuggest(v)
}

/** Выбор карточки из подсказок: наружу — чистый nmID, в поле — «nmID | название», фильтр применяется. */
const pickSuggestion = (c: any) => {
  const nm = String(c.nmID ?? '')
  const title = String(c.title || '').trim()
  setProduct(nm, title ? `${nm} | ${title}` : nm)
  emit('apply')
}

/** Сброс выбранной карточки — фильтр сразу применяется без товара. */
const clearProduct = () => {
  setProduct('')
  emit('apply')
}

/** Название карточки по nmID (для быстрых кнопок) — с кэшем. */
const titleCache = ref<Record<string, string>>({})
const loadCardTitle = async (nm: string): Promise<string> => {
  if (!nm) return ''
  if (titleCache.value[nm]) return titleCache.value[nm]
  try {
    const { data } = await api.get('/api/wb/cards', { params: { q: nm, limit: 20 } })
    const list: any[] = Array.isArray(data) ? data : (data?.items ?? [])
    const card = list.find((x: any) => String(x.nmID) === nm)
    const title = String(card?.title || '').trim()
    if (title) titleCache.value[nm] = title
    return title
  } catch {
    return ''
  }
}

// blur срабатывает раньше mousedown по кнопке — закрываем с задержкой
const closeSuggest = () => { setTimeout(() => { popupOpen.value = false }, 120) }
// быстрые кнопки как в WbFilterBar (backend/config/quick_buttons.json + фолбэк)
const defaultQuickButtons = [
  { icon: 'bi bi-journal-text', label: 'Дневник', nm_id: 526443466 },
  { icon: 'bi bi-grid-3x3-gap', label: 'Амигуруми', nm_id: 210001374 },
  { icon: 'bi bi-palette', label: 'Амигуруми ч.2', nm_id: 534186046 },
  { icon: 'bi bi-scissors', label: 'Бум. лоза', nm_id: 264750923 },
]
const quickButtonsStatic = ref<any[]>([...defaultQuickButtons])
const quickButtons = computed(() => props.quickButtonsProp ?? quickButtonsStatic.value)

const onQuickClick = async (btn: any) => {
  // быстрые кнопки — это конкретная карточка: подставляем её nmID и применяем
  const nm = String(btn.nm_id)
  setProduct(nm)
  emit('apply')
  // название карточки догружаем отдельно — как при выборе из списка
  const title = await loadCardTitle(nm)
  if (title && product.value === nm) productLabel.value = `${nm} | ${title}`
}


// локальное время (toISOString даёт UTC и сдвигает сутки)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const endDate = () => {
  const d = new Date()
  if (props.presetEnd === 'yesterday') d.setDate(d.getDate() - 1)
  return d
}

function rangeOf(id: string): [string, string] | null {
  const t = endDate()
  if (id === 'today') return [fmtD(t), fmtD(t)]
  if (id === 'yesterday') { const y = new Date(t); y.setDate(y.getDate() - (props.presetEnd === 'yesterday' ? 0 : 1)); return [fmtD(y), fmtD(y)] }
  if (id === 'ytd') return [fmtD(new Date(t.getFullYear(), 0, 1)), fmtD(t)]
  const n = Number(id)
  if (!Number.isFinite(n)) return null
  const f = new Date(t); f.setDate(f.getDate() - (n - 1)); return [fmtD(f), fmtD(t)]
}

function applyPreset(id: string) {
  const r = rangeOf(id)
  if (!r) return
  activePreset.value = id
  dateFrom.value = r[0]
  dateTo.value = r[1]
  emit('apply')
}

// подсветка следует за датами: ссылка/ручной ввод сами выбирают пресет, иначе — без подсветки
function syncPresetToDates() {
  for (const p of props.presets) {
    const r = rangeOf(p.id)
    if (r && r[0] === dateFrom.value && r[1] === dateTo.value) { activePreset.value = p.id; return }
  }
  activePreset.value = ''
}

function onReset() {
  activePreset.value = props.defaultPreset
  setProduct('')
  brand.value = ''
  category.value = ''
  emit('reset')
}

watch([dateFrom, dateTo], syncPresetToDates, { immediate: true })
// Внешнее изменение `product` (из URL, со сброса фильтра на странице) —
// синхронизируем подпись; собственные подстановки (lastSet) игнорируем.
watch(() => product.value, (v) => {
  const val = String(v || '')
  if (val === lastSet) return
  lastSet = val
  productLabel.value = val
  suggestions.value = []
  popupOpen.value = false
})
onMounted(async () => {
  if (props.quickButtonsProp === null && props.showQuick) {
    try {
      const { data: d } = await api.get('/api/config/quick-buttons')
      if (Array.isArray(d) && d.length) quickButtonsStatic.value = d
    } catch { /* noop: остаётся фолбэк */ }
  }
})
onBeforeUnmount(() => { if (searchTimer) clearTimeout(searchTimer); reqSeq++ })
</script>
<style scoped>
.wb-universal-filter { padding: 14px; margin-bottom: 14px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-md); }
.wb-universal-filter__presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; justify-content: space-between; align-items: center; }
.wb-universal-filter__presets-group { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.wb-universal-filter__presets-group--right { margin-left: auto; }
.wb-universal-filter__label { font-size: calc(12px * var(--fs)); font-weight: 600; color: var(--ink-soft); }
.wb-universal-filter__btns { margin-top: 12px; display: flex; gap: 8px; align-items: flex-end; }
.wb-universal-filter__apply { width: 120px; }

/* Поля страницы (слот #fields) — отдельная строка над кнопками, сетка с равными колонками */
.wb-universal-filter__fields {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 585px));
  gap: 10px;
  align-items: start;
}

/* Поля фильтра — на токенах темы */
.wb-universal-filter :deep(.form-control) {
  color: var(--ink);
  background: var(--surface);
  border-color: var(--line-strong);
  font-size: calc(12.5px * var(--fs));
}
.wb-universal-filter :deep(.form-control:focus) {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-tint);
}

/* Попап подсказок по товару (свой, вместо нативного <datalist>) */
.wb-universal-filter__product { position: relative; }
.wb-universal-filter__suggest {
  position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 30;
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-md);
  box-shadow: var(--shadow-1);
  max-height: 260px; overflow-y: auto;
}
.wb-universal-filter__suggest-row {
  display: flex; align-items: baseline; gap: 8px; width: 100%;
  padding: 6px 10px; border: 0; background: none; text-align: left; font-size: calc(12px * var(--fs));
}
.wb-universal-filter__suggest-row:hover { background: var(--surface-3); }
.wb-universal-filter__suggest-nm { font-weight: 700; color: var(--ink); }
.wb-universal-filter__suggest-title { color: var(--ink-soft); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wb-universal-filter__suggest-vc { margin-left: auto; color: var(--ink-muted); font-size: calc(11px * var(--fs)); white-space: nowrap; }

/* Выбранная карточка: «Выбрано: nmID» + сброс (как в WbCardSelect) */
.wb-universal-filter__picked { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.wb-universal-filter__picked-label { font-size: calc(11px * var(--fs)); color: var(--brand); }
.wb-universal-filter__picked-btn { font-size: calc(11px * var(--fs)); padding: 2px 8px; }
</style>
