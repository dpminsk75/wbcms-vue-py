<template>
  <!-- Браузеро-независимый ввод даты: вид всегда YYYY-MM-DD (нативный type=date рисует по локали браузера) -->
  <div class="wb-date-input input-group">
    <input
      ref="txtRef"
      :value="text"
      :id="inputId || undefined"
      :required="required"
      placeholder="YYYY-MM-DD"
      inputmode="numeric"
      maxlength="10"
      autocomplete="off"
      spellcheck="false"
      class="form-control"
      :class="[inputClass, { 'is-invalid': !isValid }]"
      @input="onInput"
      @blur="onBlur"
    />
    <button type="button" class="btn btn-outline-secondary wb-date-input__cal" title="Выбрать в календаре" @click="openPicker">
      <i class="bi bi-calendar3"></i>
    </button>
    <input ref="pickerRef" type="date" :value="model" tabindex="-1" aria-hidden="true" class="wb-date-input__picker" @input="onPick" />
  </div>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'

const model = defineModel<string>({ default: '' })
withDefaults(defineProps<{ inputClass?: string; inputId?: string; required?: boolean }>(), { inputClass: '', inputId: '', required: false })

const txtRef = ref<HTMLInputElement | null>(null)
const pickerRef = ref<HTMLInputElement | null>(null)
const text = ref(model.value || '')
const isValid = ref(true)

const isIsoDate = (s: string): boolean => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return false
  const y = +m[1], mo = +m[2], d = +m[3]
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return false
  const dim = new Date(y, mo, 0).getDate()
  return d <= dim
}

// Маска: только цифры, дефисы после ГГГГ и ММ
const onInput = (e: Event) => {
  const digits = (e.target as HTMLInputElement).value.replace(/\D/g, '').slice(0, 8)
  let t = digits
  if (t.length > 4) t = t.slice(0, 4) + '-' + t.slice(4)
  if (t.length > 7) t = t.slice(0, 7) + '-' + t.slice(7)
  text.value = t
  if (t === '') {
    isValid.value = true
    if (model.value !== '') model.value = ''
    return
  }
  if (t.length === 10) {
    if (isIsoDate(t)) {
      isValid.value = true
      if (model.value !== t) model.value = t
    } else {
      isValid.value = false
    }
  } else {
    isValid.value = true
  }
}

const onBlur = () => {
  if (text.value !== '' && !isIsoDate(text.value)) {
    text.value = model.value || '' // откат к последнему валидному
  }
  isValid.value = true
}

const onPick = (e: Event) => {
  const v = (e.target as HTMLInputElement).value // натив всегда отдает YYYY-MM-DD
  if (v && isIsoDate(v)) {
    text.value = v
    model.value = v
    isValid.value = true
  }
}

const openPicker = () => {
  const p = pickerRef.value
  if (!p) return
  try {
    if (typeof p.showPicker === 'function') p.showPicker()
    else { p.focus(); p.click() }
  } catch { p.focus() }
}

// Внешние изменения (пресеты, сброс) — подтягиваем, пока поле не в фокусе
watch(model, (v) => {
  if (document.activeElement !== txtRef.value && text.value !== (v || '')) text.value = v || ''
})
</script>
<style scoped>
.wb-date-input__picker {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
  border: 0;
  padding: 0;
}
.wb-date-input__cal {
  flex: 0 0 auto;
}
</style>
