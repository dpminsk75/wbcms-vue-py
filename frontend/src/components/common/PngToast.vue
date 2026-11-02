<template>
  <Transition name="png-toast">
    <div v-if="message" class="png-toast" :class="`png-toast--${tone}`" role="status">
      <i class="bi png-toast__icon" :class="icon"></i>
      <span>{{ message }}</span>
    </div>
  </Transition>
</template>

<script setup lang="ts">
/**
 * Всплывающее уведомление о результате выгрузки PNG.
 *
 * В проекте тостов нет — страницы показывают `alert` в потоке страницы
 * (`CompetitorImagesPage.vue:35`, `AdminMenu.vue:19`). Для выгрузки это
 * не годится: сообщение должно показаться поверх таблицы и исчезнуть.
 */
import { computed, onBeforeUnmount, ref } from 'vue'

type Tone = 'ok' | 'warn' | 'info'

const message = ref('')
const tone = ref<Tone>('ok')
let timer: ReturnType<typeof setTimeout> | null = null

/** Иконка по тону — без класса `bi` (он уже есть в шаблоне). */
const ICONS: Record<Tone, string> = {
  ok: 'bi-check2',
  warn: 'bi-info-circle',
  info: 'bi-hourglass-split',
}

const icon = computed(() => ICONS[tone.value])

/**
 * Показать сообщение; само гаснет через 3,2 с.
 *
 * @param sticky «залипнуть»: не гаснуть по таймеру. Для долгих операций
 *               («Готовим PNG…» во время сбора картинки) — сообщение
 *               висит, пока его не заменит результат.
 */
function show(text: string, kind: Tone = 'ok', sticky = false) {
  tone.value = kind
  message.value = text
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
  if (!sticky) timer = setTimeout(() => { message.value = '' }, 3200)
}

/** Скрыть сообщение сразу (напр., «Готовим PNG…» при открытии модалки). */
function clear() {
  if (timer) clearTimeout(timer)
  timer = null
  message.value = ''
}

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})

defineExpose({ show, clear })
</script>

<style scoped>
.png-toast {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 1080;
  display: flex;
  align-items: center;
  gap: 9px;
  max-width: 380px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: #1B2532;
  color: #fff;
  font-size: calc(13px * var(--fs));
  box-shadow: var(--shadow-2);
}
.png-toast__icon { color: #7FD1A6; flex: none; }
.png-toast--warn { background: var(--warn-deep); }
.png-toast--warn .png-toast__icon { color: #FFD79A; }
.png-toast--info .png-toast__icon { color: #8AB4E8; }
.png-toast-enter-active, .png-toast-leave-active { transition: opacity .18s ease, transform .18s ease; }
.png-toast-enter-from, .png-toast-leave-to { opacity: 0; transform: translateY(6px); }
</style>
