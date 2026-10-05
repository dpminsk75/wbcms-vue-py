<template>
  <div class="page-fbs-pvz__kpi">
    <div class="page-fbs-pvz__kpi-card page-fbs-pvz__kpi-card--main">
      <div class="page-fbs-pvz__kpi-label">Среднее время Заказ → ПВЗ</div>
      <div class="page-fbs-pvz__kpi-value">{{ fmtDur(k.avg_total_h) }}</div>
      <div class="page-fbs-pvz__kpi-sub">весь путь до пункта выдачи</div>
    </div>
    <div class="page-fbs-pvz__kpi-card">
      <div class="page-fbs-pvz__kpi-label">Среднее время Заказ → СЦ</div>
      <div class="page-fbs-pvz__kpi-value">{{ fmtDur(k.avg_leg1_h) }}</div>
      <div class="page-fbs-pvz__kpi-sub">ваша зона: собрать и передать</div>
    </div>
    <div class="page-fbs-pvz__kpi-card">
      <div class="page-fbs-pvz__kpi-label">Среднее время СЦ → ПВЗ</div>
      <div class="page-fbs-pvz__kpi-value">{{ fmtDur(k.avg_leg2_h) }}</div>
      <div class="page-fbs-pvz__kpi-sub">зона логистики Wildberries</div>
    </div>
    <div class="page-fbs-pvz__kpi-card">
      <div class="page-fbs-pvz__kpi-label">Заказов в замере</div>
      <div class="page-fbs-pvz__kpi-value">{{ fmt0(k.measured_cnt) }}</div>
      <div class="page-fbs-pvz__kpi-sub">только дошедшие до ПВЗ</div>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ k: any }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtDur = (v: any) => {
  if (v == null) return '—'
  const h = Number(v)
  const d = Math.floor(h / 24)
  const hh = Math.round(h % 24)
  return (d > 0 ? d + ' дн ' : '') + hh + ' ч'
}
</script>
<style scoped>
.page-fbs-pvz__kpi { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.page-fbs-pvz__kpi-card { flex: 1 1 200px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; min-width: 180px; }
.page-fbs-pvz__kpi-card--main { background: #f2e9fb; border-color: #d8b4fe; }
.page-fbs-pvz__kpi-card--main .page-fbs-pvz__kpi-value { color: #6d28d9; }
.page-fbs-pvz__kpi-label { font-size: 11px; color: #6b7280; margin-bottom: 4px; }
.page-fbs-pvz__kpi-value { font-size: 24px; font-weight: 800; color: #111827; white-space: nowrap; }
.page-fbs-pvz__kpi-sub { font-size: 11px; color: #6b7280; margin-top: 4px; }
</style>
