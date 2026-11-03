<template>
  <!-- Заглушка графика — блок темы: .wb-panel + шапка .card__hd (§5.9). -->
  <div class="wb-panel page-feedback-dashboard__chart">
    <div class="card__hd">
      <span>{{ title }}</span>
    </div>
    <div class="wb-panel__bd page-feedback-dashboard__empty-note">
      <i class="bi bi-stars"></i>
      <div>Появится после ИИ-анализа отзывов</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
</script>
