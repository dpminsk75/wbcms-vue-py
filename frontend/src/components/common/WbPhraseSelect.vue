<template>
  <div class="wb-phrase-select" ref="wrapRef">
    <input
      :value="inputValue"
      class="wb-input"
      :placeholder="placeholder"
      autocomplete="off"
      @input="onInput"
      @focus="showList = true"
      @keydown.esc="showList = false"
    />
    <div v-if="showList && (filtered.length || canUseCustom)" class="wb-phrase-select__list">
      <button
        v-for="o in filtered.slice(0, 50)"
        :key="o.value"
        type="button"
        class="wb-phrase-select__row"
        @mousedown.prevent="pick(o.value)"
      >
        {{ o.label }}
      </button>
      <button
        v-if="canUseCustom"
        type="button"
        class="wb-phrase-select__row wb-phrase-select__row--custom"
        @mousedown.prevent="pickCustom"
      >
        Использовать «{{ query.trim() }}»
      </button>
    </div>
    <div v-if="model" class="wb-phrase-select__status">Выбрано: {{ selectedLabel }}</div>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

/**
 * Выбор поисковой фразы — общий компонент для раздела «Поиск» (/wb-search/*).
 *
 * Поле с подсказками из списка фраз + свободный ввод (корень фразы).
 * На блоках темы: .wb-input + попап на токенах (как .wb-card-select).
 * Значение наружу — v-model (строка): id фразы из списка или введённый текст.
 */
const props = withDefaults(defineProps<{
  /** Варианты: значение + подпись («фраза (частота)»). */
  options?: { value: string; label: string }[]
  placeholder?: string
  /** Разрешить произвольный ввод (корень фразы / часть запроса). */
  allowCustom?: boolean
}>(), { options: () => [], placeholder: 'Введите фразу...', allowCustom: true })

const model = defineModel<string>({ default: '' })

const wrapRef = ref<HTMLDivElement | null>(null)
const query = ref('')
const showList = ref(false)

const normalized = computed(() =>
  (props.options || []).map((o: any) => ({ value: String(o.value ?? ''), label: String(o.label ?? o.value ?? '') })))

/** Подпись выбранного: у совпадения — из списка, иначе сам введённый текст. */
const selectedLabel = computed(() => {
  const found = normalized.value.find((o) => o.value === model.value)
  return found ? found.label : model.value
})

/** В поле — подпись выбранного, пока пользователь не печатает. */
const inputValue = computed(() => (query.value ? query.value : selectedLabel.value))

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return normalized.value
  return normalized.value.filter((o) =>
    o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q))
})

const canUseCustom = computed(() => {
  const q = query.value.trim()
  if (!props.allowCustom || !q) return false
  return !normalized.value.some((o) => o.value.toLowerCase() === q.toLowerCase())
})

function onInput(e: Event) {
  query.value = (e.target as HTMLInputElement).value
  showList.value = true
}

function pick(v: string) {
  model.value = v
  query.value = ''
  showList.value = false
}

function pickCustom() {
  model.value = query.value.trim()
  showList.value = false
}

const onDocClick = (e: MouseEvent) => {
  if (!showList.value) return
  const el = wrapRef.value
  if (el && !el.contains(e.target as Node)) showList.value = false
}
document.addEventListener('mousedown', onDocClick)
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))

/* Внешнее изменение значения (из URL, «Сбросить») — показываем его в поле. */
watch(model, () => { query.value = '' })
</script>
<style scoped>
.wb-phrase-select { position: relative; }
.wb-phrase-select__list {
  position: absolute; top: 100%; left: 0; right: 0; z-index: 1050;
  margin-top: 4px; max-height: 260px; overflow: auto;
  background: var(--surface); border: 1px solid var(--line-strong);
  border-radius: var(--radius-sm); box-shadow: var(--shadow-1);
}
.wb-phrase-select__row {
  display: block; width: 100%; text-align: left;
  border: 0; background: transparent; cursor: pointer;
  padding: 7px 10px; font: inherit; font-size: calc(12.5px * var(--fs));
  color: var(--ink); border-bottom: 1px solid var(--line);
}
.wb-phrase-select__row:hover { background: var(--brand-tint); }
.wb-phrase-select__row--custom { color: var(--brand); font-weight: 600; }
.wb-phrase-select__status { margin-top: 5px; font-size: calc(11px * var(--fs)); color: var(--ink-muted); }
</style>
