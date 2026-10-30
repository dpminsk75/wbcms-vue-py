<template>
  <div class="tile" :class="variant">
    <div class="tile__label">{{ label }}</div>
    <div class="tile__value">{{ value }}</div>
    <div v-if="foot || delta" class="tile__foot">
      <span v-if="delta" class="tile__delta" :class="{ 'tile__delta--down': deltaDown }">{{ delta }}</span>
      <span v-if="foot">{{ foot }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * KPI-плитка отчёта — обёртка над классами темы (.tile + .tile--N).
 * Фон выбирается пользователем вручную при вёрстке страницы (theme.md §2.4):
 * variant = 'tile--1' … 'tile--12'. Значение — крупное число, foot — сноска,
 * delta — плашка изменения (вниз = .tile__delta--down, красный).
 */
withDefaults(defineProps<{
  /** Подпись метрики. */
  label: string
  /** Значение (число или строка с единицами). */
  value: string | number
  /** Фон плитки: tile--1 … tile--12. */
  variant?: string
  /** Сноска под значением. */
  foot?: string
  /** Плашка изменения («+3 товара»). */
  delta?: string
  /** Плашка изменения вниз (отрицательная). */
  deltaDown?: boolean
}>(), { variant: 'tile--1', foot: '', delta: '', deltaDown: false })
</script>
