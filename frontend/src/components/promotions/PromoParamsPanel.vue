<template>
  <!-- Пороги и тумблеры расчёта — поля страницы (слот #fields у WbUniversalFilter). -->
  <div class="page-wb-promotions__params">
    <div class="page-wb-promotions__params-row">
      <div class="wb-field">
        <label class="wb-field__label">Окно истории, дней</label>
        <input v-model.number="model.days" type="number" min="1" max="365" class="wb-input">
      </div>
      <div class="wb-field">
        <label class="wb-field__label">Мин. маржа, %</label>
        <input v-model.number="model.min_margin_pct" type="number" step="0.5" class="wb-input">
      </div>
      <div class="wb-field">
        <label class="wb-field__label">Макс. падение, п.п.</label>
        <input v-model.number="model.max_drop_pp" type="number" step="0.5" class="wb-input">
      </div>
      <div class="wb-field">
        <label class="wb-field__label">Мин. маржа, ₽/шт</label>
        <input v-model.number="model.min_margin_rub" type="number" step="1" class="wb-input">
      </div>
      <div class="wb-field">
        <label class="wb-field__label">Мин. остаток WB</label>
        <input v-model.number="model.min_stock_wb" type="number" min="0" class="wb-input">
      </div>
      <div v-if="isAuto" class="wb-field">
        <label class="wb-field__label" title="Уровень скидки автоакции, % — через API не отдаётся, берётся из карточки акции в ЛК WB">Скидка акции, %</label>
        <input v-model.number="model.auto_discount" type="number" min="0" max="99" class="wb-input">
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PromoCalcParams } from '@/api/promotions'

const model = defineModel<PromoCalcParams>({ required: true })

defineProps<{ isAuto?: boolean }>()
</script>
