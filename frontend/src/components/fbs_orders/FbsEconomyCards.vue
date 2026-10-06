<template>
  <div class="page-fbs-orders__kpi">
    <div class="page-fbs-orders__kpi-card">
      <div class="page-fbs-orders__kpi-label">Заказов, шт</div>
      <div class="page-fbs-orders__kpi-value">{{ fmt0(e.orders_cnt) }}</div>
    </div>
    <div class="page-fbs-orders__kpi-card">
      <div class="page-fbs-orders__kpi-label">Выручка (до СПП)</div>
      <div class="page-fbs-orders__kpi-value">{{ fmtMoney(e.revenue_gross) }}</div>
      <div class="page-fbs-orders__kpi-sub">{{ fmtMoney(e.revenue_net) }} (с СПП)</div>
    </div>
    <div class="page-fbs-orders__kpi-card">
      <div class="page-fbs-orders__kpi-label">Средний чек (до СПП)</div>
      <div class="page-fbs-orders__kpi-value">{{ fmtMoney(e.avg_check_gross) }}</div>
      <div class="page-fbs-orders__kpi-sub">{{ fmtMoney(e.avg_check_net) }} (с СПП)</div>
    </div>
    <div class="page-fbs-orders__kpi-card page-fbs-orders__kpi-card--danger">
      <div class="page-fbs-orders__kpi-label">Отменено, шт</div>
      <div class="page-fbs-orders__kpi-value">{{ fmt0(e.canceled_cnt) }}</div>
      <div class="page-fbs-orders__kpi-sub">на {{ fmtMoney(e.canceled_sum) }}</div>
    </div>
    <div class="page-fbs-orders__kpi-card">
      <div class="page-fbs-orders__kpi-label">Живых (до СПП)</div>
      <div class="page-fbs-orders__kpi-value">{{ fmtMoney(e.alive_sum) }}</div>
      <div class="page-fbs-orders__kpi-sub">{{ fmt0(e.alive_cnt) }} шт без отменённых</div>
    </div>
    <div class="page-fbs-orders__kpi-card">
      <div class="page-fbs-orders__kpi-label">Доля FBS</div>
      <div class="page-fbs-orders__kpi-value">{{ fmtPct1(e.fbs_share_money_pct) }}</div>
      <div class="page-fbs-orders__kpi-sub">по деньгам · {{ fmtPct1(e.fbs_share_cnt_pct) }} по штукам</div>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ e: any }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
</script>
<style scoped>
.page-fbs-orders__kpi { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.page-fbs-orders__kpi-card { flex: 1 1 160px; background: #fff; border: 1px solid #d5dae1; box-shadow: 0 1px 3px rgba(16,24,40,.08); border-radius: 10px; padding: 14px 16px; min-width: 150px; }
.page-fbs-orders__kpi-card--danger { background: #fef2f2; border-color: #fecaca; }
.page-fbs-orders__kpi-card--danger .page-fbs-orders__kpi-value { color: #b91c1c; }
.page-fbs-orders__kpi-label { font-size: 11px; color: #6b7280; text-transform: uppercase; margin-bottom: 4px; }
.page-fbs-orders__kpi-value { font-size: 22px; font-weight: 800; color: #111827; white-space: nowrap; }
.page-fbs-orders__kpi-sub { font-size: 11px; color: #6b7280; margin-top: 4px; }
</style>
