<template>
  <ul class="nav nav-pills page-fbs__tabs mb-3">
    <li v-for="t in tabs" :key="t.label" class="nav-item">
      <router-link v-if="t.to" class="nav-link" :class="{ active: active === t.id }" :to="t.to">{{ t.label }}</router-link>
      <span v-else class="nav-link disabled" title="Скоро">{{ t.label }}</span>
    </li>
  </ul>
</template>
<script setup lang="ts">
// Общее мини-меню FBS-отчётов (как табы 10X). Активная страница — через prop active.
defineProps<{ active: string }>()
const tabs = [
  { id: 'summary', label: 'Сводка', to: '/fbs-report' },
  { id: 'orders', label: 'Заказы', to: '/fbs-orders' },
  { id: 'cancels', label: 'Отмены', to: '/fbs-cancels' },
  { id: 'commission', label: 'Комиссия', to: '/fbs-commission' },
  { id: 'pvz', label: 'Путь до ПВЗ', to: '/fbs-pvz' },
]
</script>
<style scoped>
.page-fbs__tabs { flex-wrap: wrap; gap: 4px; }
.page-fbs__tabs .nav-link { font-size: 12px; }
.page-fbs__tabs .nav-link.disabled { color: #9ca3af; }
</style>
