<template>
  <div class="wb-universal-filter">
    <div class="wb-universal-filter__presets">
      <div class="wb-universal-filter__presets-group">
        <button v-for="p in presets" :key="p.id" class="btn btn-sm" :class="activePreset === p.id ? 'btn-primary' : 'btn-outline-secondary'" @click="applyPreset(p.id)">{{ p.label }}</button>
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
      <div v-if="showProduct" class="col-md-4">
        <label class="form-label mb-1 wb-universal-filter__label">Товар</label>
        <input v-model="product" :list="listId" placeholder="nm_id, артикул или часть названия..." class="form-control" autocomplete="off" />
        <datalist :id="listId">
          <option v-for="c in suggestions" :key="c.nmID" :value="String(c.vendorCode || c.nmID)">{{ c.nmID }} | {{ c.title }}</option>
        </datalist>
      </div>
      <template v-if="showBrandCategory">
        <div class="col-md-2">
          <label class="form-label mb-1 wb-universal-filter__label">Бренд</label>
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
    <div class="wb-universal-filter__btns">
      <button class="btn btn-primary wb-universal-filter__apply" @click="emit('apply')">Применить</button>
      <button class="btn btn-light wb-universal-filter__apply" @click="onReset">Сбросить</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { api } from '@/api/client'
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
  listId?: string
  showQuick?: boolean
  quickButtonsProp?: any[] | null
}>(), {
  brands: () => [], categories: () => [],
  showProduct: true, showBrandCategory: true,
  defaultPreset: '30', presetEnd: 'today',
  categoryLabel: 'Категория', listId: 'wbuf-product-list',
  showQuick: true, quickButtonsProp: null,
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

const presets = [
  { id: 'today', label: 'Сегодня' },
  { id: 'yesterday', label: 'Вчера' },
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
  { id: '365', label: '365 дней' },
  { id: 'ytd', label: 'С начала года' },
]
const activePreset = ref(props.defaultPreset)
const suggestions = ref<any[]>([])
// быстрые кнопки как в WbFilterBar (backend/config/quick_buttons.json + фолбэк)
const defaultQuickButtons = [
  { icon: 'bi bi-journal-text', label: 'Дневник', nm_id: 526443466 },
  { icon: 'bi bi-grid-3x3-gap', label: 'Амигуруми', nm_id: 210001374 },
  { icon: 'bi bi-palette', label: 'Амигуруми ч.2', nm_id: 534186046 },
  { icon: 'bi bi-scissors', label: 'Бум. лоза', nm_id: 264750923 },
]
const quickButtonsStatic = ref<any[]>([...defaultQuickButtons])
const quickButtons = computed(() => props.quickButtonsProp ?? quickButtonsStatic.value)

const onQuickClick = (btn: any) => {
  // цифры = подстрока nmID ≈ точное попадание; маска-семантика сохраняется
  product.value = String(btn.nm_id)
  emit('apply')
}
let searchTimer: ReturnType<typeof setTimeout> | null = null
let reqSeq = 0

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
  for (const p of presets) {
    const r = rangeOf(p.id)
    if (r && r[0] === dateFrom.value && r[1] === dateTo.value) { activePreset.value = p.id; return }
  }
  activePreset.value = ''
}

function onReset() {
  activePreset.value = props.defaultPreset
  product.value = ''
  brand.value = ''
  category.value = ''
  emit('reset')
}

watch([dateFrom, dateTo], syncPresetToDates, { immediate: true })
watch(() => product.value, (v) => {  if (!props.showProduct) return
  if (searchTimer) clearTimeout(searchTimer)
  const q = String(v || '').trim()
  if (q.length < 2) { suggestions.value = []; return }
  searchTimer = setTimeout(async () => {
    const my = ++reqSeq
    try {
      const { data: d } = await api.get('/api/wb/cards', { params: { q, limit: 20 } })
      if (my !== reqSeq) return
      suggestions.value = Array.isArray(d) ? d : (d?.items ?? [])
    } catch { /* noop */ }
  }, 300)
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
.wb-universal-filter { padding: 15px; margin-bottom: 16px; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; }
.wb-universal-filter__presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; justify-content: space-between; align-items: center; }
.wb-universal-filter__presets-group { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.wb-universal-filter__presets-group--right { margin-left: auto; }
.wb-universal-filter__label { font-size: 12px; font-weight: 600; }
.wb-universal-filter__btns { margin-top: 12px; display: flex; gap: 8px; }
.wb-universal-filter__apply { width: 120px; }
</style>
