<template>
  <div class="fbs-kpi">
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Заработано скидкой</div>
      <div class="fbs-kpi__value">{{ fmtMoney(s.earned) }}</div>
    </div>
    <div class="fbs-kpi__card fbs-kpi__card--danger">
      <div class="fbs-kpi__label">Потеряно списанием</div>
      <div class="fbs-kpi__value">{{ fmtMoney(s.lost) }}</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Чистый эффект</div>
      <div class="fbs-kpi__value">{{ fmtMoney(s.net) }}</div>
      <div class="fbs-kpi__sub">экономия минус потери</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Можно забрать ещё</div>
      <div class="fbs-kpi__value">{{ fmtMoney(s.potential) }}</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Быстрых ≤13 ч</div>
      <div class="fbs-kpi__value">—</div>
      <div class="fbs-kpi__sub">{{ fmt0(s.fast_cnt) }} из {{ fmt0(s.measured_cnt) }}</div>
    </div>
  </div>
  <div class="fbs-note">Суммы ≈ по статусам сдачи ({{ fmt0(s.measured_cnt) }} из {{ fmt0(s.tasks_cnt) }}); скан WB учитываем, когда он есть.</div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
defineProps<{ s: any }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
</script>
