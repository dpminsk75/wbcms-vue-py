<template>
  <div class="fbs-kpi">
    <div class="fbs-kpi__card fbs-kpi__card--danger fbs-kpi__card--click" @click="emit('show', 'seller_cancel')" title="Показать заказы">
      <div class="fbs-kpi__label">Потеряно · отменил продавец</div>
      <div class="fbs-kpi__value">≈{{ fmtMoney(s.seller.sum) }}</div>
      <div class="fbs-kpi__sub">{{ fmt0(s.seller.cnt) }} шт · включая отмены по просрочке</div>
    </div>
    <div class="fbs-kpi__card fbs-kpi__card--click" @click="emit('show', 'buyer_cancel')" title="Показать заказы">
      <div class="fbs-kpi__label">Отменил покупатель</div>
      <div class="fbs-kpi__value">{{ fmt0(s.buyer.cnt) }} <span class="fbs-kpi__unit">шт</span></div>
      <div class="fbs-kpi__sub">≈{{ fmtMoney(s.buyer.sum) }} · это спрос, а не потеря</div>
    </div>
    <div class="fbs-kpi__card fbs-kpi__card--click" @click="emit('show', 'declined')" title="Показать заказы">
      <div class="fbs-kpi__label">Отказ при получении</div>
      <div class="fbs-kpi__value">{{ fmt0(s.declined.cnt) }} <span class="fbs-kpi__unit">шт</span></div>
      <div class="fbs-kpi__sub">≈{{ fmtMoney(s.declined.sum) }} · логистика уже оплачена</div>
    </div>
    <div class="fbs-kpi__card fbs-kpi__card--click" @click="emit('show', 'all')" title="Показать заказы">
      <div class="fbs-kpi__label">Всего отменено</div>
      <div class="fbs-kpi__value">{{ fmtPct1(s.total.pct) }}</div>
      <div class="fbs-kpi__sub">≈{{ fmtMoney(s.total.canceled_sum) }} отменено из {{ fmt0(s.total.tasks_cnt) }} заданий · все три причины</div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
defineProps<{ s: any }>()
const emit = defineEmits<{ (e: 'show', bucket: string): void }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
</script>
