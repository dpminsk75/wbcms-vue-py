<template>
  <div class="pager">
    <button type="button" class="btn btn--outline btn-sm" :disabled="page <= 1" @click="$emit('change', page - 1)">Назад</button>
    <span class="pager__label">
      Стр {{ page }} / {{ totalPages }}<span v-if="total"> ({{ total }})</span>
    </span>
    <button type="button" class="btn btn--outline btn-sm" :disabled="page >= totalPages" @click="$emit('change', page + 1)">Вперёд</button>
  </div>
</template>
<script setup lang="ts">
/** Пагинация «Назад / Стр N из M (всего) / Вперёд» — единая для всех страниц. */
withDefaults(defineProps<{ page: number; totalPages: number; total?: number }>(), { total: 0 })
defineEmits<{ (e: 'change', page: number): void }>()
</script>
<style scoped>
.pager { display: flex; gap: 8px; justify-content: center; align-items: center; margin: 12px 0; }
.pager__label { align-self: center; font-size: calc(12px * var(--fs)); color: var(--ink-soft); font-variant-numeric: tabular-nums; }
</style>
