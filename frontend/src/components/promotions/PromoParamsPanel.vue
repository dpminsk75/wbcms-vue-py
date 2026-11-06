<template>
  <!-- Пороги и тумблеры расчёта — поля страницы (слот #fields у WbUniversalFilter). -->
  <div class="page-wb-promotions__params">
    <div class="page-wb-promotions__params-row">
      <!-- Окно истории задаётся датами фильтра (сверху), поля «дней» больше нет. -->
      <div class="wb-field">
        <label class="wb-field__label" title="На сколько процентов маржа на цене акции может стать хуже текущей (в рублях). 10 = не хуже −10 %">Падение маржи, %</label>
        <input v-model.number="model.max_drop_pct" type="number" step="0.5" class="wb-input" :disabled="onlyMinMargin">
      </div>
      <div class="wb-field">
        <label class="wb-field__label" title="На сколько рублей на штуку маржа может стать хуже текущей. 5 = не хуже −5 ₽/шт">Падение маржи, ₽</label>
        <input v-model.number="model.max_drop_rub" type="number" step="1" class="wb-input" :disabled="onlyMinMargin">
      </div>
      <div class="wb-field">
        <label class="wb-field__label" title="Маржа на цене акции должна быть строго больше порога. Порог может быть отрицательным: −10 = минус десять рублей недопустимы, −9 — можно">Мин. маржа, ₽</label>
        <input v-model.number="model.min_margin_rub" type="number" step="1" class="wb-input">
      </div>
      <div class="wb-field">
        <label class="wb-field__label">Мин. остаток WB</label>
        <input v-model.number="model.min_stock_wb" type="number" min="0" class="wb-input" :disabled="onlyMinMargin">
      </div>
      <div v-if="isAuto" class="wb-field">
        <label class="wb-field__label" title="Уровень скидки автоакции, % — через API не отдаётся, берётся из карточки акции в ЛК WB">Скидка акции, %</label>
        <input v-model.number="model.auto_discount" type="number" min="0" max="99" class="wb-input">
      </div>
      <div class="wb-field">
        <label class="wb-field__label" title="Какие пороги учитывать в вердикте. «Только Мин маржу» — остальные пороги не проверяются. Выбор сохраняется">Учитывать</label>
        <select v-model="respect" class="wb-select">
          <option value="all">Все параметры</option>
          <option value="min">Только Мин маржу</option>
        </select>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PromoCalcParams } from '@/api/promotions'

const model = defineModel<PromoCalcParams>({ required: true })

defineProps<{ isAuto?: boolean }>()

/** «Учитывать»: all — все пороги, min — только «Мин. маржа, ₽». */
const respect = computed({
  get: () => (model.value.only_min_margin ? 'min' : 'all'),
  // props readonly — мутировать поле нельзя, отдаём новый объект модели
  set: (v: string) => {
    model.value = { ...model.value, only_min_margin: v === 'min' }
  },
})

/** В режиме «Только Мин маржу» остальные пороги не проверяются — гасим их. */
const onlyMinMargin = computed(() => model.value.only_min_margin)
</script>
