<template>
  <div class="wb-range-filter">
    <div class="wb-range-filter__presets">
      <button
        v-for="p in presets"
        :key="p.id"
        class="btn btn-sm"
        :class="activePreset === p.id ? 'btn-primary' : 'btn-outline-secondary'"
        @click="applyPreset(p.id)"
      >
        {{ p.label }}
      </button>
    </div>
    <div class="row g-2 align-items-end">
      <div class="col-auto">
        <label class="form-label mb-1 wb-range-filter__label">Дата с</label>
        <WbDateInput v-model="draftFrom" />
      </div>
      <div class="col-auto">
        <label class="form-label mb-1 wb-range-filter__label">Дата по</label>
        <WbDateInput v-model="draftTo" />
      </div>
      <div class="col-auto wb-range-filter__btns">
        <button class="btn btn-primary btn-sm" @click="applyManual">Применить</button>
        <button class="btn btn-light btn-sm" @click="applyPreset(defaultPreset)">Сбросить</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import WbDateInput from './WbDateInput.vue'

/**
 * Фильтр по диапазону дат — облегчённая версия WbUniversalFilter:
 * пресеты (7/14/30/90/365/с начала года) + ручной ввод дат.
 *
 * Родитель держит применённый диапазон (props from/to), компонент —
 * черновик (draft). Пресет применяется сразу, ручные даты — по кнопке.
 */
const props = withDefaults(defineProps<{
  from: string
  to: string
  defaultPreset?: string
}>(), { defaultPreset: '30' })

const emit = defineEmits<{ apply: [payload: { from: string, to: string }] }>()

const presets = [
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
  { id: '365', label: '365 дней' },
  { id: 'ytd', label: 'С начала года' },
]

const draftFrom = ref(props.from)
const draftTo = ref(props.to)
const activePreset = ref(props.defaultPreset)

// локальное время (toISOString даёт UTC и сдвигает сутки)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

function rangeOf(id: string): [string, string] | null {
  const t = new Date()
  if (id === 'ytd') return [fmtD(new Date(t.getFullYear(), 0, 1)), fmtD(t)]
  const n = Number(id)
  if (!Number.isFinite(n) || n <= 0) return null
  const f = new Date(t)
  f.setDate(f.getDate() - (n - 1))
  return [fmtD(f), fmtD(t)]
}

function applyPreset(id: string) {
  const r = rangeOf(id)
  if (!r) return
  activePreset.value = id
  draftFrom.value = r[0]
  draftTo.value = r[1]
  emit('apply', { from: r[0], to: r[1] })
}

function applyManual() {
  if (!draftFrom.value || !draftTo.value) return
  activePreset.value = matchPreset(draftFrom.value, draftTo.value)
  emit('apply', { from: draftFrom.value, to: draftTo.value })
}

/** Подсветка пресета — только если даты точно совпадают с пресетом. */
function matchPreset(from: string, to: string): string {
  for (const p of presets) {
    const r = rangeOf(p.id)
    if (r && r[0] === from && r[1] === to) return p.id
  }
  return ''
}

function onReset() {
  applyPreset(props.defaultPreset)
}

// внешнее изменение применённого диапазона (например, из URL) — синхронизируем черновик
watch(() => [props.from, props.to], ([f, t]) => {
  if (f && f !== draftFrom.value) draftFrom.value = f
  if (t && t !== draftTo.value) draftTo.value = t
  activePreset.value = matchPreset(f, t)
})
</script>

<style scoped>
.wb-range-filter { padding: 12px 14px; margin-bottom: 12px; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; }
.wb-range-filter__presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.wb-range-filter__label { font-size: 12px; font-weight: 600; }
.wb-range-filter__btns { display: flex; gap: 8px; }
</style>
