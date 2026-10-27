<template>
  <div class="year-selector">
    <span class="year-selector__label">Годы:</span>
    <label v-for="y in years" :key="y" class="year-selector__item">
      <input type="checkbox" :value="y" v-model="pending" />
      <span>{{ y }}</span>
    </label>
    <button type="button" class="btn btn-sm btn-primary year-selector__btn" @click="apply">
      Сформировать
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  /** Годы, которые есть в данных. */
  years: number[]
  /** Применённый выбор (из URL). */
  modelValue: number[]
}>()

const emit = defineEmits<{ apply: [number[]] }>()

// Черновик выбора: применяется только по кнопке «Сформировать».
const pending = ref<number[]>([...props.modelValue])

watch(() => props.modelValue, (v) => {
  const cur = [...pending.value].sort().join(',')
  if (cur !== [...v].sort().join(',')) pending.value = [...v]
}, { deep: true })

function apply() {
  emit('apply', [...pending.value].sort((a, b) => a - b))
}
</script>

<style scoped>
.year-selector {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
}
.year-selector__label { color: #7f8c8d; font-weight: 700; text-transform: uppercase; font-size: 10px; }
.year-selector__item { display: inline-flex; align-items: center; gap: 3px; cursor: pointer; color: #2c3e50; }
.year-selector__item input { margin: 0; }
.year-selector__btn { font-size: 12px; padding: 3px 12px; }
</style>
