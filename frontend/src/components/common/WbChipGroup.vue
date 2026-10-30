<template>
  <div class="wb-chip-group">
    <span v-if="label" class="wb-chip-group__label">{{ label }}</span>
    <button
      v-for="o in options"
      :key="String(o.value)"
      type="button"
      class="opt"
      :aria-pressed="isOn(o.value)"
      @click="pick(o.value)"
    >
      {{ o.label }}<span v-if="o.sub" class="opt__sub">{{ o.sub }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
/**
 * Группа чипов-переключателей (класс темы .opt) — для полей конкретного отчёта.
 * Ставится в слот #extra фильтра (WbUniversalFilter) или в панель фильтров.
 *
 * Одиночный выбор по умолчанию; multiple — набор значений (массив).
 * Значение наружу — v-model (defineModel), чтобы страница держала черновик
 * и отдавала применённое значение по кнопке «Применить».
 */
const props = withDefaults(defineProps<{
  /** Подпись слева от чипов («Спрос», «Порог дней»…). */
  label?: string
  /** Варианты: значение + подпись + мелкая подпись справа. */
  options: { value: string | number; label: string; sub?: string }[]
  /** Множественный выбор (значение — массив). */
  multiple?: boolean
}>(), { label: '', multiple: false })

const model = defineModel<any>({ default: '' })

function isOn(v: string | number): boolean {
  if (props.multiple) return Array.isArray(model.value) && model.value.includes(v)
  return model.value === v
}

function pick(v: string | number) {
  if (props.multiple) {
    const cur = Array.isArray(model.value) ? [...model.value] : []
    const i = cur.indexOf(v)
    if (i >= 0) cur.splice(i, 1)
    else cur.push(v)
    model.value = cur
  } else {
    model.value = v
  }
}
</script>

<style scoped>
.wb-chip-group { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.wb-chip-group__label { font-size: calc(11.5px * var(--fs)); color: var(--ink-muted); }
</style>
