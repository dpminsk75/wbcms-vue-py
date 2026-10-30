<template>
  <div v-if="options.length" class="year-picker">
    <WbChipGroup
      :options="options"
      :model-value="selected"
      multiple
      @update:model-value="onPick"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * Выбор лет — чипами класса `.opt` (как переключатель палитры на
 * `/settings/appearance`): нажатый чип = заливка акцентом.
 *
 * Применяется **сразу** по клику (как переключатель палитры), без отдельной
 * кнопки «Сформировать»: страница сама решает, что делать с набором
 * (записать в URL, перезапросить отчёт) — по событию `apply`.
 *
 * Общий компонент: новые страницы и `/wb-profit` пользуются одним.
 */
import { computed, ref, watch } from 'vue'
import WbChipGroup from './WbChipGroup.vue'

const props = withDefaults(defineProps<{
  /** Годы, за которые есть данные. */
  available: number[]
  /** Применённый выбор (снаружи — v-model). */
  modelValue: number[]
}>(), { modelValue: () => [] })

const emit = defineEmits<{
  (e: 'update:modelValue', years: number[]): void
  (e: 'apply', years: number[]): void
}>()

/** Что выбрано прямо сейчас (отражается сразу, не дожидаясь ответа страницы). */
const selected = ref<number[]>([...props.modelValue])

watch(
  () => props.modelValue,
  (v) => {
    const cur = [...selected.value].sort().join(',')
    if (cur !== [...v].sort().join(',')) selected.value = [...v]
  },
  { deep: true },
)

/**
 * Годы с данными, по убыванию (свежий — первым).
 * Именно computed, а не функция: в шаблоне используются `options.length` и
 * `v-for="o in options"` — с функцией чипы не рисуются вовсе.
 */
const options = computed(() => [...props.available].sort((a, b) => b - a).map((y) => ({
  value: y,
  label: String(y),
})))

/** Клик по чипу: последний год снять нельзя — сравнение без годов бессмысленно. */
function onPick(list: any) {
  const next = (Array.isArray(list) ? list : []).map(Number).filter((n) => Number.isInteger(n))
  if (!next.length) return
  const sorted = [...next].sort((a, b) => a - b)
  selected.value = sorted
  emit('update:modelValue', sorted)
  emit('apply', sorted)
}
</script>

<style scoped>
.year-picker { display: inline-flex; align-items: center; gap: 10px; flex-wrap: wrap; }
</style>
