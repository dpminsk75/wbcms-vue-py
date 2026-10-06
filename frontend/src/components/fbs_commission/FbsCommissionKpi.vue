<template>
  <div class="page-fbs-commission__kpi">
    <div class="page-fbs-commission__kpi-card">
      <div class="page-fbs-commission__kpi-label">Заработано скидкой</div>
      <div class="page-fbs-commission__kpi-value">{{ fmtMoney(s.earned) }}</div>
    </div>
    <div class="page-fbs-commission__kpi-card page-fbs-commission__kpi-card--danger">
      <div class="page-fbs-commission__kpi-label">Потеряно списанием</div>
      <div class="page-fbs-commission__kpi-value">{{ fmtMoney(s.lost) }}</div>
    </div>
    <div class="page-fbs-commission__kpi-card">
      <div class="page-fbs-commission__kpi-label">Чистый эффект</div>
      <div class="page-fbs-commission__kpi-value">{{ fmtMoney(s.net) }}</div>
      <div class="page-fbs-commission__kpi-sub">экономия минус потери</div>
    </div>
    <div class="page-fbs-commission__kpi-card">
      <div class="page-fbs-commission__kpi-label">Можно забрать ещё</div>
      <div class="page-fbs-commission__kpi-value">{{ fmtMoney(s.potential) }}</div>
    </div>
    <div class="page-fbs-commission__kpi-card">
      <div class="page-fbs-commission__kpi-label">Быстрых ≤13 ч</div>
      <div class="page-fbs-commission__kpi-value">—</div>
      <div class="page-fbs-commission__kpi-sub">{{ fmt0(s.fast_cnt) }} из {{ fmt0(s.measured_cnt) }}</div>
    </div>
  </div>
  <div class="page-fbs-commission__note">Суммы ≈ по статусам сдачи ({{ fmt0(s.measured_cnt) }} из {{ fmt0(s.tasks_cnt) }}); скан WB учитываем, когда он есть.</div>
</template>
<script setup lang="ts">
defineProps<{ s: any }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
</script>
<style scoped>
.page-fbs-commission__kpi { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }
.page-fbs-commission__kpi-card { flex: 1 1 160px; background: #fff; border: 1px solid #d5dae1; box-shadow: 0 1px 3px rgba(16,24,40,.08); border-radius: 10px; padding: 14px 16px; min-width: 150px; }
.page-fbs-commission__kpi-card--danger { background: #fef2f2; border-color: #fecaca; }
.page-fbs-commission__kpi-card--danger .page-fbs-commission__kpi-value { color: #b91c1c; }
.page-fbs-commission__kpi-label { font-size: 11px; color: #6b7280; margin-bottom: 4px; }
.page-fbs-commission__kpi-value { font-size: 24px; font-weight: 800; color: #111827; white-space: nowrap; }
.page-fbs-commission__kpi-sub { font-size: 11px; color: #6b7280; margin-top: 4px; }
.page-fbs-commission__note { font-size: 11px; color: #9ca3af; margin-bottom: 16px; }
</style>
