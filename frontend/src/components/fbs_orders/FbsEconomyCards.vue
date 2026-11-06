<template>
  <div class="fbs-kpi">
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Заказов, шт</div>
      <div class="fbs-kpi__value">{{ fmt0(e.orders_cnt) }}</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Выручка (до СПП)</div>
      <div class="fbs-kpi__value">{{ fmtMoney(e.revenue_gross) }}</div>
      <div class="fbs-kpi__sub">{{ fmtMoney(e.revenue_net) }} (с СПП)</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Средний чек (до СПП)</div>
      <div class="fbs-kpi__value">{{ fmtMoney(e.avg_check_gross) }}</div>
      <div class="fbs-kpi__sub">{{ fmtMoney(e.avg_check_net) }} (с СПП)</div>
    </div>
    <div class="fbs-kpi__card fbs-kpi__card--danger">
      <div class="fbs-kpi__label">Отменено, шт</div>
      <div class="fbs-kpi__value">{{ fmt0(e.canceled_cnt) }}</div>
      <div class="fbs-kpi__sub">на {{ fmtMoney(e.canceled_sum) }}</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Живых (до СПП)</div>
      <div class="fbs-kpi__value">{{ fmtMoney(e.alive_sum) }}</div>
      <div class="fbs-kpi__sub">{{ fmt0(e.alive_cnt) }} шт без отменённых</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Доля FBS</div>
      <div class="fbs-kpi__value">{{ fmtPct1(e.fbs_share_money_pct) }}</div>
      <div class="fbs-kpi__sub">по деньгам · {{ fmtPct1(e.fbs_share_cnt_pct) }} по штукам</div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
defineProps<{ e: any }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
</script>
