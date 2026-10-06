<template>
  <div class="page-fbs-cancels__kpi">
    <div class="page-fbs-cancels__kpi-card page-fbs-cancels__kpi-card--danger page-fbs-cancels__kpi-card--click" @click="emit('show', 'seller_cancel')" title="Показать заказы">
      <div class="page-fbs-cancels__kpi-label">Потеряно · отменил продавец</div>
      <div class="page-fbs-cancels__kpi-value">≈{{ fmtMoney(s.seller.sum) }}</div>
      <div class="page-fbs-cancels__kpi-sub">{{ fmt0(s.seller.cnt) }} шт · включая отмены по просрочке</div>
    </div>
    <div class="page-fbs-cancels__kpi-card page-fbs-cancels__kpi-card--click" @click="emit('show', 'buyer_cancel')" title="Показать заказы">
      <div class="page-fbs-cancels__kpi-label">Отменил покупатель</div>
      <div class="page-fbs-cancels__kpi-value">{{ fmt0(s.buyer.cnt) }} <span class="page-fbs-cancels__kpi-unit">шт</span></div>
      <div class="page-fbs-cancels__kpi-sub">≈{{ fmtMoney(s.buyer.sum) }} · это спрос, а не потеря</div>
    </div>
    <div class="page-fbs-cancels__kpi-card page-fbs-cancels__kpi-card--click" @click="emit('show', 'declined')" title="Показать заказы">
      <div class="page-fbs-cancels__kpi-label">Отказ при получении</div>
      <div class="page-fbs-cancels__kpi-value">{{ fmt0(s.declined.cnt) }} <span class="page-fbs-cancels__kpi-unit">шт</span></div>
      <div class="page-fbs-cancels__kpi-sub">≈{{ fmtMoney(s.declined.sum) }} · логистика уже оплачена</div>
    </div>
    <div class="page-fbs-cancels__kpi-card page-fbs-cancels__kpi-card--click" @click="emit('show', 'all')" title="Показать заказы">
      <div class="page-fbs-cancels__kpi-label">Всего отменено</div>
      <div class="page-fbs-cancels__kpi-value">{{ fmtPct1(s.total.pct) }}</div>
      <div class="page-fbs-cancels__kpi-sub">≈{{ fmtMoney(s.total.canceled_sum) }} отменено из {{ fmt0(s.total.tasks_cnt) }} заданий · все три причины</div>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ s: any }>()
const emit = defineEmits<{ (e: 'show', bucket: string): void }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
</script>
<style scoped>
.page-fbs-cancels__kpi { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.page-fbs-cancels__kpi-card { flex: 1 1 200px; background: #fff; border: 1px solid #d5dae1; box-shadow: 0 1px 3px rgba(16,24,40,.08); border-radius: 10px; padding: 14px 16px; min-width: 180px; }
.page-fbs-cancels__kpi-card--danger { background: #fef2f2; border-color: #fecaca; }
.page-fbs-cancels__kpi-card--danger .page-fbs-cancels__kpi-value { color: #b91c1c; }
.page-fbs-cancels__kpi-label { font-size: 11px; color: #6b7280; text-transform: uppercase; margin-bottom: 4px; }
.page-fbs-cancels__kpi-value { font-size: 24px; font-weight: 800; color: #111827; white-space: nowrap; }
.page-fbs-cancels__kpi-unit { font-size: 14px; font-weight: 400; color: #6b7280; }
.page-fbs-cancels__kpi-card--click { cursor: pointer; }
.page-fbs-cancels__kpi-card--click:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.page-fbs-cancels__kpi-sub { font-size: 11px; color: #6b7280; margin-top: 4px; }
</style>
