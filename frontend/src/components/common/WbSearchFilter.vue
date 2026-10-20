<template>
  <div class="wb-universal-filter">
    <div class="wb-universal-filter__presets">
      <div class="wb-universal-filter__presets-group">
        <button v-for="p in presets" :key="p.id" class="btn btn-sm" :class="activePreset === p.id ? 'btn-primary' : 'btn-outline-secondary'" @click="applyPreset(p.id)">{{ p.label }}</button>
      </div>
    </div>
    <div class="row g-2 align-items-start">
      <div class="col-md-6">
        <label class="form-label mb-1 wb-universal-filter__label">{{ label }}</label>
        <div style="position:relative" ref="selectWrapRef">
          <div class="form-control" @click="toggleList" style="width:100%; height:38px; display:flex; align-items:center; justify-content:space-between; cursor:pointer; background:#fff;" :style="{borderColor: showList ? '#86b7fe' : '#dee2e6', boxShadow: showList ? '0 0 0 0.25rem rgba(13,110,253,.25)' : 'none'}">
            <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:12px;" :style="{color: selectedLabel ? '#212529' : '#6c757d'}">{{ selectedLabel || placeholder }}</span>
            <span style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
              <i v-if="phrase" class="bi bi-x-circle" style="color:#adb5bd; cursor:pointer;" @click.stop="onClear" title="Очистить"></i>
              <i class="bi" :class="showList ? 'bi-chevron-up' : 'bi-chevron-down'" style="color:#6c757d;"></i>
            </span>
          </div>
          <div v-if="showList" style="position:absolute; top:100%; left:0; right:0; background:#fff; border:1px solid #86b7fe; border-top:none; border-radius:0 0 6px 6px; z-index:1050; box-shadow:0 4px 12px rgba(0,0,0,.15)">
            <div style="padding:6px; border-bottom:1px solid #e9ecef; position:relative">
              <input v-model="searchQuery" placeholder="Поиск..." class="form-control" style="height:32px; font-size:12px; padding-right:30px;" ref="searchInputRef" @keydown.esc="showList=false" />
              <i class="bi bi-search" style="position:absolute; right:14px; top:50%; transform:translateY(-50%); color:#adb5bd; font-size:12px;"></i>
            </div>
            <div style="max-height:240px; overflow:auto;">
              <div v-if="!filteredOptions.length && !(allowCustom && searchQuery.trim())" style="padding:10px; font-size:12px; color:#6c757d; text-align:center;">Ничего не найдено</div>
              <div v-if="allowCustom && searchQuery.trim()" @mousedown.prevent="selectCustom(searchQuery.trim())" style="padding:6px 10px; cursor:pointer; font-size:12px; border-bottom:1px solid #f1f5f9; background:#eef4ff">
                Использовать «{{ searchQuery.trim() }}»
              </div>
              <div v-for="opt in filteredOptions.slice(0,50)" :key="String(opt.value)" @mousedown.prevent="selectOption(opt)" style="padding:6px 10px; cursor:pointer; font-size:12px; border-bottom:1px solid #f1f5f9" :style="{background: String(opt.value)===String(phrase) ? '#0d6efd' : '#fff', color: String(opt.value)===String(phrase) ? '#fff' : '#212529'}">
                {{ opt.label }}
              </div>
            </div>
          </div>
        </div>
        <div v-if="phrase" class="wb-universal-filter__selected">Выбрано: {{ phrase }}</div>
      </div>
    </div>
    <div class="row g-2 align-items-start">
      <div class="col-md-3">
        <label class="form-label mb-1 wb-universal-filter__label">Дата с</label>
        <WbDateInput v-model="dateFrom" class="wb-search-filter__date" />
      </div>
      <div class="col-md-3">
        <label class="form-label mb-1 wb-universal-filter__label">Дата по</label>
        <WbDateInput v-model="dateTo" class="wb-search-filter__date" />
      </div>
    </div>
    <div class="wb-universal-filter__btns">
      <button class="btn btn-primary wb-universal-filter__apply" @click="emit('apply')">Применить</button>
      <button class="btn btn-light wb-universal-filter__apply" @click="onReset">Сбросить</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onBeforeUnmount, watch } from 'vue'
import WbDateInput from './WbDateInput.vue'

// Общий фильтр wb-search: пресеты дат (как WbUniversalFilter) + селект фразы
// со свободным вводом (как UniversalFilter allowCustom) + даты. Товара нет.
const props = withDefaults(defineProps<{
  label?: string
  placeholder?: string
  data?: Array<{ value: string; label: string }>
  allowCustom?: boolean
  defaultPreset?: string
  presetEnd?: 'today' | 'yesterday'
}>(), {
  label: 'Фраза',
  placeholder: 'Введите фразу...',
  data: () => [],
  allowCustom: true,
  defaultPreset: '30',
  presetEnd: 'yesterday',
})

const phrase = defineModel<string>('phrase', { default: '' })
const dateFrom = defineModel<string>('dateFrom', { default: '' })
const dateTo = defineModel<string>('dateTo', { default: '' })

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

const selectWrapRef = ref<HTMLDivElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)
const searchQuery = ref('')
const showList = ref(false)

const normalizedOptions = computed(() => (props.data || []).map((row: any) => ({
  value: String(row.value ?? ''),
  label: String(row.label ?? row.value ?? ''),
})))

const selectedLabel = computed(() => {
  if (!phrase.value) return ''
  const found = normalizedOptions.value.find((o) => o.value === phrase.value)
  return found ? found.label : phrase.value
})

const filteredOptions = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return normalizedOptions.value
  return normalizedOptions.value.filter((opt) =>
    opt.label.toLowerCase().includes(q) || opt.value.toLowerCase().includes(q))
})

const toggleList = () => {
  showList.value = !showList.value
  if (showList.value) {
    searchQuery.value = ''
    setTimeout(() => searchInputRef.value?.focus(), 50)
  }
}

const selectOption = (opt: any) => {
  phrase.value = String(opt.value)
  showList.value = false
  searchQuery.value = ''
}

const selectCustom = (text: string) => {
  phrase.value = text
  showList.value = false
  searchQuery.value = ''
}

const onClear = () => {
  phrase.value = ''
  searchQuery.value = ''
  showList.value = false
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
  if (id === 'yesterday') { const y = new Date(t); if (props.presetEnd !== 'yesterday') y.setDate(y.getDate() - 1); return [fmtD(y), fmtD(y)] }
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

function syncPresetToDates() {
  for (const p of presets) {
    const r = rangeOf(p.id)
    if (r && r[0] === dateFrom.value && r[1] === dateTo.value) { activePreset.value = p.id; return }
  }
  activePreset.value = ''
}

function onReset() {
  activePreset.value = props.defaultPreset
  phrase.value = ''
  searchQuery.value = ''
  showList.value = false
  emit('reset')
}

const onDocClick = (e: MouseEvent) => {
  if (!showList.value) return
  const el = selectWrapRef.value
  if (el && !el.contains(e.target as Node)) showList.value = false
}

watch([dateFrom, dateTo], syncPresetToDates, { immediate: true })

document.addEventListener('mousedown', onDocClick)
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))
</script>
<style scoped>
.wb-universal-filter {
  padding: 15px;
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}
.wb-universal-filter__presets {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  align-items: center;
}
.wb-universal-filter__presets-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.wb-universal-filter__label {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
}
.wb-universal-filter__selected {
  margin-top: 6px;
  font-size: 11px;
  color: #7c1af8;
}
.wb-universal-filter__btns {
  margin-top: 14px;
  display: flex;
  gap: 8px;
}
.wb-universal-filter__apply {
  width: 120px;
}
.wb-search-filter__date {
  max-width: 220px;
}
</style>
