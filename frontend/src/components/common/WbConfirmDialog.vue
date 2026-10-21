<template>
  <!--
    Подтверждение действия — свой диалог, а не нативный confirm().
    Нативный confirm() блокирует поток страницы: повторный клик, сделанный
    пока диалог открыт, ставится в очередь и срабатывает уже после закрытия —
    пользователь получает «Отвязать? Отвязать?». Здесь поток не блокируется,
    лишние клики уходят в подложку.
  -->
  <div v-if="open" class="wb-modal-backdrop" @click.self="emit('cancel')">
    <div class="wb-modal-box wb-confirm__box">
      <div class="wb-confirm__text">{{ text }}</div>
      <div v-if="hint" class="wb-confirm__hint">{{ hint }}</div>
      <div class="wb-modal-actions">
        <button
          class="btn btn-sm"
          :class="danger ? 'btn-danger' : 'btn-primary'"
          :disabled="busy"
          @click="emit('confirm')"
        >
          <span v-if="busy" class="spinner-border spinner-border-sm"></span>
          {{ confirmText || 'Подтвердить' }}
        </button>
        <button class="btn btn-sm btn-secondary" :disabled="busy" @click="emit('cancel')">
          {{ cancelText || 'Отмена' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  open: boolean
  text: string
  hint?: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  busy?: boolean
}>()

const emit = defineEmits<{ (e: 'confirm'): void; (e: 'cancel'): void }>()
</script>
