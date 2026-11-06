<template>
  <div class="fbs-kpi">
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Заказы FBS</div>
      <div class="fbs-kpi__value">{{ fmt0(kpi.orders_cnt) }}</div>
      <div class="fbs-kpi__sub">{{ pctLine(delta.orders_cnt_pct) }}</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Заказы (до СПП)</div>
      <div class="fbs-kpi__value">{{ fmtMoney(kpi.orders_sum) }}</div>
      <div class="fbs-kpi__sub">{{ pctLine(delta.orders_sum_pct) }}</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Выкуп</div>
      <div class="fbs-kpi__value">{{ fmtPct(kpi.buyout_pct) }}</div>
      <div class="fbs-kpi__sub">{{ ppLine(delta.buyout_pp) }}</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Ещё в движении</div>
      <div class="fbs-kpi__value">{{ fmt0(kpi.in_transit_cnt) }}</div>
      <div class="fbs-kpi__sub">{{ pctLine(delta.in_transit_pct) }}</div>
    </div>
    <div class="fbs-kpi__card fbs-kpi__card--danger">
      <div class="fbs-kpi__label">Отменено</div>
      <div class="fbs-kpi__value">{{ fmt0(kpi.canceled_cnt) }}</div>
      <div class="fbs-kpi__sub">продавец {{ fmt0(kpi.canceled_seller) }} · покупатель {{ fmt0(kpi.canceled_buyer) }}</div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
defineProps<{ kpi: any, delta: any }>()

const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtSignedPct = (v: any) => (Number(v) >= 0 ? '+' : '') + new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
const pctLine = (v: any) => v == null ? '— к прошлому периоду' : ('▲ ' + fmtSignedPct(v) + ' к прошлому периоду')
const ppLine = (v: any) => (Number(v) >= 0 ? '+' : '') + new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' п.п. к прошлому периоду'
</script>
