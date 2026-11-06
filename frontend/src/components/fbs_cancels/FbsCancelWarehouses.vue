<template>
  <div>
    <div class="fbs-section-line">Отмены по складам</div>
    <div class="fbs-wh__grid">
      <div v-for="w in items" :key="String(w.warehouse_id)" class="fbs-wh__card fbs-wh__card--click" @click="emit('show', w.warehouse_id)" :title="'Показать отмены: ' + w.warehouse_name">
        <div class="fbs-wh__name">Склад «{{ w.warehouse_name }}»{{ w.warehouse_id ? ' ' + w.warehouse_id : '' }}</div>
        <div class="fbs-wh__nums">
          <span><b class="fbs-tbl__num--red">{{ fmt0(w.seller_cnt) }}</b><i>Продавец</i></span>
          <span><b>{{ fmt0(w.buyer_cnt) }}</b><i>Покупатель</i></span>
          <span><b>{{ fmt0(w.declined_cnt) }}</b><i>Отказ</i></span>
        </div>
        <div class="fbs-wh__lost">≈{{ fmtMoney(w.lost_sum) }} потеряно</div>
        <div class="fbs-wh__sub">всего отменено ≈{{ fmtMoney(w.total_sum) }}</div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
defineProps<{ items: any[] }>()
const emit = defineEmits<{ (e: 'show', warehouseId: number | null): void }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
</script>
