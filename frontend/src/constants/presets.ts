/**
 * Пресеты периодов — общий набор для фильтров дат.
 *
 * Живёт отдельным модулем, а не экспортом из `<script setup>`: SFC в
 * `<script setup>` не допускает именованных экспортов (vite:vue падает на
 * компиляции всего бандла).
 */

/** Для `WbDateRangeFilter.vue` — только «дни». */
export const DEFAULT_PRESETS = [
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
  { id: '365', label: '365 дней' },
  { id: 'ytd', label: 'С начала года' },
]

/** Для `WbUniversalFilter.vue` — плюс «Сегодня»/«Вчера». */
export const DEFAULT_PRESETS_UNIVERSAL = [
  { id: 'today', label: 'Сегодня' },
  { id: 'yesterday', label: 'Вчера' },
  ...DEFAULT_PRESETS,
]
