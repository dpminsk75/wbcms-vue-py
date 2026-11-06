<template>
  <div class="fbs-kpi">
    <div class="fbs-kpi__card fbs-kpi__card--main">
      <div class="fbs-kpi__label">Среднее время Заказ → ПВЗ</div>
      <div class="fbs-kpi__value">{{ fmtDur(k.avg_total_h) }}</div>
      <div class="fbs-kpi__sub">весь путь до пункта выдачи</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Среднее время Заказ → СЦ</div>
      <div class="fbs-kpi__value">{{ fmtDur(k.avg_leg1_h) }}</div>
      <div class="fbs-kpi__sub">ваша зона: собрать и передать</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Среднее время СЦ → ПВЗ</div>
      <div class="fbs-kpi__value">{{ fmtDur(k.avg_leg2_h) }}</div>
      <div class="fbs-kpi__sub">зона логистики Wildberries</div>
    </div>
    <div class="fbs-kpi__card">
      <div class="fbs-kpi__label">Заказов в замере</div>
      <div class="fbs-kpi__value">{{ fmt0(k.measured_cnt) }}</div>
      <div class="fbs-kpi__sub">только дошедшие до ПВЗ</div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
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
