<template>
  <div class="page-feedback-dashboard__kpi">
    <!-- Отзывы -->
    <div class="page-feedback-dashboard__kpi-card">
      <div class="page-feedback-dashboard__kpi-label">Отзывы</div>
      <div class="page-feedback-dashboard__kpi-value">{{ kpi.reviews_cnt }}</div>
      <div class="page-feedback-dashboard__kpi-sub">
        <span v-if="delta.reviews_cnt_pct != null"
              :class="delta.reviews_cnt_pct >= 0 ? 'text-success' : 'text-danger'">
          ▲{{ Math.abs(delta.reviews_cnt_pct) }}%
        </span>
        <span v-else class="text-muted">— к прошлому периоду</span>
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
    <div class="page-feedback-dashboard__kpi-card">
      <div class="page-feedback-dashboard__kpi-label">Средняя оценка</div>
      <div class="page-feedback-dashboard__kpi-value">
        <span class="page-feedback-dashboard__star">★</span>{{ kpi.avg_rating ?? '—' }}
        <span v-if="delta.avg_rating_pp != null" class="page-feedback-dashboard__kpi-delta"
              :class="delta.avg_rating_pp >= 0 ? 'text-success' : 'text-danger'">
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
    <div class="page-feedback-dashboard__kpi-card">
      <div class="page-feedback-dashboard__kpi-label">Лояльность (NPS)</div>
      <div class="page-feedback-dashboard__kpi-value">
        {{ kpi.nps ?? '—' }}
        <span v-if="delta.nps_pp != null" class="page-feedback-dashboard__kpi-delta"
              :class="delta.nps_pp >= 0 ? 'text-success' : 'text-danger'">
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

<style scoped>
.page-feedback-dashboard__kpi {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.page-feedback-dashboard__kpi-card {
  flex: 1 1 260px;
  background: #fff;
  border: 1px solid #d5dae1;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(16, 24, 40, .08);
  padding: 14px 16px;
  min-width: 240px;
}
.page-feedback-dashboard__kpi-label { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.page-feedback-dashboard__kpi-value { font-size: 24px; font-weight: 800; color: #111827; }
.page-feedback-dashboard__kpi-sub { font-size: 11px; margin-top: 2px; }
.page-feedback-dashboard__kpi-note { font-size: 12px; color: #374151; margin-top: 10px; }
.page-feedback-dashboard__kpi-delta { font-size: 12px; font-weight: 600; margin-left: 4px; }
.page-feedback-dashboard__star { color: #f59e0b; margin-right: 2px; }

.page-feedback-dashboard__bar {
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 4px;
}
.page-feedback-dashboard__bar-fill { height: 100%; background: #2563eb; }
.page-feedback-dashboard__bar-scale {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #9ca3af;
  margin-top: 2px;
}

.page-feedback-dashboard__stars { margin-top: 10px; }
.page-feedback-dashboard__star-row { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.page-feedback-dashboard__star-num { font-size: 11px; color: #6b7280; width: 30px; }
.page-feedback-dashboard__star-bar {
  flex: 1 1 auto;
  height: 8px;
  background: #eef0f3;
  border-radius: 4px;
  overflow: hidden;
}
.page-feedback-dashboard__star-fill { height: 100%; background: #4f7d5b; }
.page-feedback-dashboard__star-pct { font-size: 11px; color: #6b7280; width: 34px; text-align: right; }

.page-feedback-dashboard__nps-scale { margin-top: 10px; }
.page-feedback-dashboard__nps-track {
  position: relative;
  height: 10px;
  background: linear-gradient(90deg, #e8a37a, #f2f5f7 50%, #8fbfa3);
  border-radius: 5px;
}
.page-feedback-dashboard__nps-mid {
  position: absolute;
  left: 50%;
  top: -3px;
  width: 1px;
  height: 16px;
  background: #9ca3af;
}
.page-feedback-dashboard__nps-marker {
  position: absolute;
  top: -4px;
  width: 12px;
  height: 18px;
  margin-left: -6px;
  border-radius: 3px;
  background: #7c3aed;
  border: 2px solid #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, .25);
}
.page-feedback-dashboard__nps-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #9ca3af;
  margin-top: 3px;
}
.page-feedback-dashboard__nps-note { font-size: 12px; color: #374151; margin-top: 6px; }
</style>
