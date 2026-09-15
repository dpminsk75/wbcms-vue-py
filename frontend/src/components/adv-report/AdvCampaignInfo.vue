<template>
  <div v-if="detail?.campaign" class="card shadow p-3 ms-3 me-0" style="border:1px solid #e5e7eb; border-radius:12px;">
    <div class="panel panel-info">
      <div class="panel-heading">Кампания: <b>{{ detail.campaign.name }}</b> ID: <a :href="'https://cmp.wildberries.ru/campaigns/edit/' + detail.campaign.campaign_id" target="_blank"><b>{{ detail.campaign.campaign_id }}</b></a></div>
      <div class="panel-body font_11px grey" style="font-size:11px; color:#555; margin-top:6px">
        Статус: <span class="label" :class="statusClass(detail.campaign.status)">{{ detail.statusLabel }}</span>
        Тип: <b>{{ detail.typeLabel }}</b>
        Бюджет: <b>{{ fmt0(detail.campaign.daily_budget) }} ₽</b>
        Изменена: <b>{{ fmtDateTime(detail.campaign.change_time) }}</b>
      </div>
    </div>
    <div class="alert alert-default font_13px" style="background:#f1f1f1; border-left:5px solid #337ab7; margin:10px 0 0; font-size:12px;">
      <strong>Товары в кампании</strong>
      <div style="margin-top:6px;"><ul style="margin:0; padding-left:18px">
        <li v-for="it in detail.items" :key="it.nm_id"><a :href="'/wb-get-sales-funnel/wbcard?nmId=' + it.nm_id" target="_blank">{{ it.nm_id }}</a> | {{ it.card_name || 'Без названия' }} | {{ it.vendorCode }}</li>
      </ul></div>
    </div>
  </div>
  <div v-else class="row m-3 alert alert-warning" style="font-size:12px">Выберите кампанию и период, чтобы увидеть аналитику.</div>
</template>
<script setup lang="ts">
// index.php:127-158 — правая карточка кампании 1в1
defineProps<{ detail: any }>()
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmtDateTime = (v:any)=> v ? new Date(v).toLocaleString('ru-RU') : '—'
const statusClass = (s:number)=>{
  const m:any = {9:'label-success',11:'label-warning',7:'label-primary',4:'label-info',8:'label-danger', '-1':'label-default'}
  return m[String(s)] || 'label-default'
}
</script>
