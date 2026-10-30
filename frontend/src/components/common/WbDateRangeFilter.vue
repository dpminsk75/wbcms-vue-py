<template>
  <div class="wb-range-filter" :class="{ 'wb-range-filter--bare': props.bare || props.compact }">
    <div class="wb-range-filter__presets">
      <button
        v-for="p in presets"
        :key="p.id"
        class="btn btn-sm"
        :class="activePreset === p.id ? 'btn--brand' : 'btn--outline'"
        @click="applyPreset(p.id)"
      >
        {{ p.label }}
      </button>
    </div>
    <div class="row g-2 align-items-end" :class="{ 'wb-range-filter__row--inline': !!$slots.inline }">
      <div class="col-auto">
        <label class="wb-field__label">Дата с</label>
        <WbDateInput v-model="draftFrom" />
      </div>
      <div class="col-auto">
        <label class="wb-field__label">Дата по</label>
        <WbDateInput v-model="draftTo" />
      </div>
      <!-- Поля страницы — в одну горизонталь с датами (слот #inline).
           Выравнивание по верху: подписи на одной высоте, поля одинаковой высоты. -->
      <div v-if="$slots.inline" class="col-auto flex-grow-1 wb-range-filter__inline">
        <slot name="inline" />
      </div>
      <div v-if="!props.bare" class="col-auto wb-range-filter__btns">
        <button class="btn btn--brand btn-sm" @click="applyManual">Применить</button>
        <button class="btn btn--outline btn-sm" @click="applyPreset(defaultPreset)">Сбросить</button>
      </div>
    </div>
    <!-- доп. поле страницы (например, выбор кампании) -->
    <div class="wb-range-filter__extra">
      <slot name="extra" />
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
 *
 * Период всегда заканчивается сегодня.
 */
const props = withDefaults(defineProps<{
  defaultPreset?: string
  /** Компактный вид: без белой плашки с рамкой (для модалок). */
  compact?: boolean
  /** Без своей плашки — когда блок лежит внутри панели фильтров страницы. */
  bare?: boolean
}>(), { defaultPreset: '30', compact: false, bare: false })

/**
 * Диапазон дат — двусторонняя модель (v-model:from / v-model:to).
 * Раньше было только props from/to + событие apply: в режиме bare (кнопок у компонента нет)
 * введённые вручную даты до страницы не доходили, и кнопка отчёта «Применить»
 * применяла старые даты. Теперь черновик отдаётся наружу сразу.
 */
const fromModel = defineModel<string>('from', { default: '' })
const toModel = defineModel<string>('to', { default: '' })

const emit = defineEmits<{ apply: [payload: { from: string, to: string }] }>()

const presets = [
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
  { id: '365', label: '365 дней' },
  { id: 'ytd', label: 'С начала года' },
]

const draftFrom = ref(fromModel.value)
const draftTo = ref(toModel.value)
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

// внешнее изменение применённого диапазона (например, из URL или по «Сбросить») — синхронизируем черновик
watch(() => [fromModel.value, toModel.value], ([f, t]) => {
  if (f && f !== draftFrom.value) draftFrom.value = f
  if (t && t !== draftTo.value) draftTo.value = t
  activePreset.value = matchPreset(f, t)
})

// ручной ввод дат — наружу сразу (в bare режиме своей кнопки «Применить» у компонента нет)
watch(draftFrom, (v) => { if (v !== fromModel.value) fromModel.value = v })
watch(draftTo, (v) => { if (v !== toModel.value) toModel.value = v })
</script>
<style scoped>
.wb-range-filter {
  padding: 14px;
  margin-bottom: 12px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
}
/* Без своей плашки: bare (в панели фильтров страницы) и compact (в модалках). */
.wb-range-filter--bare {
  padding: 0;
  margin-bottom: 0;
  background: transparent;
  border: 0;
  border-radius: 0;
}
.wb-range-filter__presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.wb-range-filter__btns { display: flex; gap: 8px; }
/* Поля страницы в строке с датами: выравнивание по верху, иначе поле с подписью
   «Выбрано: …» (ниже контрола) поднимает остальные поля ряда. */
.wb-range-filter__row--inline { align-items: flex-start; }
.wb-range-filter__inline { min-width: 0; }
.wb-range-filter__extra:not(:empty) { margin-top: 12px; display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }

/* Поля дат — на токенах темы (внутри компонента Bootstrap form-control). */
.wb-range-filter :deep(.form-control) {
  height: 38px;
  font-size: calc(12.5px * var(--fs));
  color: var(--ink);
  background: var(--surface);
  border-color: var(--line-strong);
}
.wb-range-filter :deep(.form-control:focus) {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-tint);
}
.wb-range-filter :deep(.wb-date-input__cal) {
  border-color: var(--line-strong);
  color: var(--ink-soft);
}
</style>
