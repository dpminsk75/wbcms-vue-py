<template>
  <div>
    <div class="page-fbs-cancels__section-line">Отмены по складам</div>
    <div class="page-fbs-cancels__wh-grid">
      <div v-for="w in items" :key="String(w.warehouse_id)" class="page-fbs-cancels__wh-card page-fbs-cancels__wh-card--click" @click="emit('show', w.warehouse_id)" :title="'Показать отмены: ' + w.warehouse_name">
        <div class="page-fbs-cancels__wh-name">Склад «{{ w.warehouse_name }}»{{ w.warehouse_id ? ' ' + w.warehouse_id : '' }}</div>
        <div class="page-fbs-cancels__wh-nums">
          <span><b class="page-fbs-cancels__num--red">{{ fmt0(w.seller_cnt) }}</b><i>Продавец</i></span>
          <span><b>{{ fmt0(w.buyer_cnt) }}</b><i>Покупатель</i></span>
          <span><b>{{ fmt0(w.declined_cnt) }}</b><i>Отказ</i></span>
        </div>
        <div class="page-fbs-cancels__wh-lost">≈{{ fmtMoney(w.lost_sum) }} потеряно</div>
        <div class="page-fbs-cancels__wh-sub">всего отменено ≈{{ fmtMoney(w.total_sum) }}</div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ items: any[] }>()
const emit = defineEmits<{ (e: 'show', warehouseId: number | null): void }>()
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
</script>
<style scoped>
.page-fbs-cancels__section-line { font-size: 13px; font-weight: 600; color: #111827; margin: 4px 0 10px; }
.page-fbs-cancels__wh-grid { display: flex; flex-wrap: wrap; gap: 12px; }
.page-fbs-cancels__wh-card { flex: 1 1 260px; background: #fff; border: 1px solid #d5dae1; box-shadow: 0 1px 3px rgba(16,24,40,.08); border-radius: 10px; padding: 14px 16px; min-width: 240px; }
.page-fbs-cancels__wh-card--click { cursor: pointer; }
.page-fbs-cancels__wh-card--click:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.page-fbs-cancels__wh-name { font-size: 13px; font-weight: 700; color: #111827; margin-bottom: 8px; }
.page-fbs-cancels__wh-nums { display: flex; gap: 16px; margin-bottom: 8px; }
.page-fbs-cancels__wh-nums span { display: flex; flex-direction: column; }
.page-fbs-cancels__wh-nums b { font-size: 18px; color: #111827; }
.page-fbs-cancels__num--red { color: #b91c1c !important; }
.page-fbs-cancels__wh-nums i { font-style: normal; font-size: 10px; color: #9ca3af; }
.page-fbs-cancels__wh-lost { font-size: 13px; font-weight: 700; color: #b91c1c; }
.page-fbs-cancels__wh-sub { font-size: 11px; color: #6b7280; margin-top: 2px; }
</style>
