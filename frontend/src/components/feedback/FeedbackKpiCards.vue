<template>
  <!-- KPI дашборда отзывов: три плитки темы (.tile). Внутри — полоса «с текстом %»,
       шкала звёзд и шкала NPS: их нет в .tile, поэтому это обычные блоки
       на токенах темы (тема §5.3 — плитка, §5.4 — панель). -->
  <div class="grid-3 page-feedback-dashboard__kpi">
    <!-- Отзывы -->
    <div class="tile tile--1">
      <div class="tile__label">Отзывы</div>
      <div class="tile__value">{{ kpi.reviews_cnt }}</div>
      <div class="page-feedback-dashboard__kpi-sub">
        <span v-if="delta.reviews_cnt_pct != null"
              :class="delta.reviews_cnt_pct >= 0 ? 'page-feedback-dashboard__delta-up' : 'page-feedback-dashboard__delta-down'">
          ▲{{ Math.abs(delta.reviews_cnt_pct) }}%
        </span>
        <span v-else class="page-feedback-dashboard__kpi-muted">— к прошлому периоду</span>
      </div>
      <div class="page-feedback-dashboard__kpi-note">
        Из них с текстом {{ kpi.with_text_pct }}%
      </div>
      <div class="page-feedback-dashboard__bar">
        <div class="page-feedback-dashboard__bar-fill"
             :style="{ width: Math.min(100, kpi.with_text_pct) + '%' }"></div>
      </div>
      <div class="page-feedback-dashboard__bar-scale">
        <span>0</span><span>100%</span>
      </div>
    </div>

    <!-- Средняя оценка -->
    <div class="tile tile--1">
      <div class="tile__label">Средняя оценка</div>
      <div class="tile__value">
        <span class="page-feedback-dashboard__star">★</span>{{ kpi.avg_rating ?? '—' }}
        <span v-if="delta.avg_rating_pp != null" class="page-feedback-dashboard__kpi-delta"
              :class="delta.avg_rating_pp >= 0 ? 'page-feedback-dashboard__delta-up' : 'page-feedback-dashboard__delta-down'">
          ▲{{ Math.abs(delta.avg_rating_pp) }}
        </span>
      </div>
      <div class="page-feedback-dashboard__stars">
        <div v-for="r in ratings" :key="r.rating" class="page-feedback-dashboard__star-row">
          <span class="page-feedback-dashboard__star-num">{{ r.rating }} ★</span>
          <div class="page-feedback-dashboard__star-bar">
            <div class="page-feedback-dashboard__star-fill"
                 :style="{ width: r.pct + '%' }"></div>
          </div>
          <span class="page-feedback-dashboard__star-pct">{{ r.pct }}%</span>
        </div>
      </div>
    </div>

    <!-- NPS -->
    <div class="tile tile--1">
      <div class="tile__label">Лояльность (NPS)</div>
      <div class="tile__value">
        {{ kpi.nps ?? '—' }}
        <span v-if="delta.nps_pp != null" class="page-feedback-dashboard__kpi-delta"
              :class="delta.nps_pp >= 0 ? 'page-feedback-dashboard__delta-up' : 'page-feedback-dashboard__delta-down'">
          ▲{{ Math.abs(delta.nps_pp) }}
        </span>
      </div>
      <div class="page-feedback-dashboard__nps-scale">
        <div class="page-feedback-dashboard__nps-track">
          <div class="page-feedback-dashboard__nps-mid"></div>
          <div class="page-feedback-dashboard__nps-marker"
               :style="{ left: npsPos + '%' }"></div>
        </div>
        <div class="page-feedback-dashboard__nps-labels">
          <span>−100%</span><span>0</span><span>100%</span>
        </div>
        <div class="page-feedback-dashboard__nps-note">
          {{ npsLabel }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DashDelta, DashKpi, DashRating } from '@/api/feedbackDashboard'

const props = defineProps<{
  kpi: DashKpi
  delta: DashDelta
  ratings: DashRating[]
}>()

// NPS на шкале −100…100
const npsPos = computed(() => {
  const v = props.kpi.nps
  if (v == null) return 50
  return Math.max(0, Math.min(100, (v + 100) / 2))
})
const npsLabel = computed(() => {
  const v = props.kpi.nps
  if (v == null) return '—'
  if (v >= 50) return 'Отличная лояльность'
  if (v >= 20) return 'Хорошая лояльность'
  if (v >= 0) return 'Слабая лояльность'
  return 'Отрицательная лояльность'
})
</script>
