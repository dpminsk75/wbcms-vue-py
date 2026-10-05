<template>
  <div class="page-fbs-report__kpi">
    <div class="page-fbs-report__kpi-card">
      <div class="page-fbs-report__kpi-label">Заказы FBS</div>
      <div class="page-fbs-report__kpi-value">{{ fmt0(kpi.orders_cnt) }}</div>
      <div class="page-fbs-report__kpi-sub">{{ pctLine(delta.orders_cnt_pct) }}</div>
    </div>
    <div class="page-fbs-report__kpi-card">
      <div class="page-fbs-report__kpi-label">Заказы (до СПП)</div>
      <div class="page-fbs-report__kpi-value">{{ fmtMoney(kpi.orders_sum) }}</div>
      <div class="page-fbs-report__kpi-sub">{{ pctLine(delta.orders_sum_pct) }}</div>
    </div>
    <div class="page-fbs-report__kpi-card">
      <div class="page-fbs-report__kpi-label">Выкуп</div>
      <div class="page-fbs-report__kpi-value">{{ fmtPct(kpi.buyout_pct) }}</div>
      <div class="page-fbs-report__kpi-sub">{{ ppLine(delta.buyout_pp) }}</div>
    </div>
    <div class="page-fbs-report__kpi-card">
      <div class="page-fbs-report__kpi-label">Ещё в движении</div>
      <div class="page-fbs-report__kpi-value">{{ fmt0(kpi.in_transit_cnt) }}</div>
      <div class="page-fbs-report__kpi-sub">{{ pctLine(delta.in_transit_pct) }}</div>
    </div>
    <div class="page-fbs-report__kpi-card page-fbs-report__kpi-card--danger">
      <div class="page-fbs-report__kpi-label">Отменено</div>
      <div class="page-fbs-report__kpi-value">{{ fmt0(kpi.canceled_cnt) }}</div>
      <div class="page-fbs-report__kpi-sub">продавец {{ fmt0(kpi.canceled_seller) }} · покупатель {{ fmt0(kpi.canceled_buyer) }}</div>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ kpi: any, delta: any }>()

const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtSignedPct = (v: any) => (Number(v) >= 0 ? '+' : '') + new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
const pctLine = (v: any) => v == null ? '— к прошлому периоду' : ('▲ ' + fmtSignedPct(v) + ' к прошлому периоду')
const ppLine = (v: any) => (Number(v) >= 0 ? '+' : '') + new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' п.п. к прошлому периоду'
</script>
<style scoped>
.page-fbs-report__kpi { display:flex; flex-wrap:wrap; gap:12px; margin-bottom:16px; }
.page-fbs-report__kpi-card { flex:1 1 200px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:14px 16px; min-width:180px; }
.page-fbs-report__kpi-card--danger { background:#fef2f2; border-color:#fecaca; }
.page-fbs-report__kpi-card--danger .page-fbs-report__kpi-value { color:#b91c1c; }
.page-fbs-report__kpi-label { font-size:12px; color:#6b7280; margin-bottom:4px; }
.page-fbs-report__kpi-value { font-size:24px; font-weight:800; color:#111827; white-space:nowrap; }
.page-fbs-report__kpi-sub { font-size:11px; color:#6b7280; margin-top:4px; }
</style>
