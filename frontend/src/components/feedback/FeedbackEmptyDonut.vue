<template>
  <div class="page-feedback-dashboard__chart-card">
    <div class="page-feedback-dashboard__section-title">{{ title }}</div>
    <div class="page-feedback-dashboard__empty-note">
      <i class="bi bi-stars"></i>
      <div>Появится после ИИ-анализа отзывов</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<style scoped>
.page-feedback-dashboard__chart-card {
  background: #fff;
  border: 1px solid #d5dae1;
  border-radius: 10px;
  padding: 16px 18px;
  height: 100%;
}
.page-feedback-dashboard__section-title { font-size: 13px; font-weight: 600; color: #111827; }
.page-feedback-dashboard__empty-note {
  height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
  font-size: 13px;
  text-align: center;
}
.page-feedback-dashboard__empty-note i { font-size: 26px; }
</style>
