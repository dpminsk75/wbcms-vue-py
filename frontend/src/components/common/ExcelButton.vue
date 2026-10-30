<template>
  <button type="button" class="hd-btn" :disabled="disabled" @click="$emit('click')">
    <i class="bi bi-file-earmark-excel me-1"></i>{{ label }}
  </button>
</template>
<script setup lang="ts">
/** Кнопка «Excel» в шапке блока — одинаковая на всех страницах. */
withDefaults(defineProps<{ label?: string; disabled?: boolean }>(), { label: 'Excel', disabled: false })
defineEmits<{ (e: 'click'): void }>()
</script>
