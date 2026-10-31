<template>
  <div v-if="detail?.campaign" class="wb-panel page-adv-report__campaign-info">
    <div class="card__hd">
      <span>Кампания: <b>{{ detail.campaign.name }}</b></span>
      <span class="spacer"></span>
      <span class="page-adv-report__campaign-id">ID:
        <a :href="'https://cmp.wildberries.ru/campaigns/edit/' + detail.campaign.campaign_id" target="_blank" class="page-adv-report__link"><b>{{ detail.campaign.campaign_id }}</b></a>
      </span>
    </div>
    <div class="wb-panel__bd">
      <div class="page-adv-report__campaign-meta">
        Статус: <span class="badge" :class="statusBadge(detail.campaign.status)">{{ detail.statusLabel }}</span>
        Тип: <b>{{ detail.typeLabel }}</b>
        Бюджет: <b>{{ fmt0(detail.campaign.daily_budget) }} ₽</b>
        Изменена: <b>{{ fmtDateTime(detail.campaign.change_time) }}</b>
      </div>
      <div class="page-adv-report__campaign-items">
        <div class="page-adv-report__campaign-items-title">Товары в кампании</div>
        <ul class="page-adv-report__campaign-items-list">
          <li v-for="it in detail.items" :key="it.nm_id">
            <a :href="'/wb-get-sales-funnel/wbcard?nmId=' + it.nm_id" target="_blank" class="page-adv-report__link">{{ it.nm_id }}</a>
            | {{ it.card_name || 'Без названия' }} | {{ it.vendorCode }}
          </li>
        </ul>
      </div>
    </div>
  </div>
  <div v-else class="alert alert-warning mb-3 page-adv-report__hint">Выберите кампанию и период, чтобы увидеть аналитику.</div>
</template>
<script setup lang="ts">
// index.php:127-158 — правая карточка кампании 1в1
import { useNumFmt } from '@/composables/useNumFmt'
import { useDateFmt } from '../../composables/useDateFmt'

defineProps<{ detail: any }>()
const { fmt0 } = useNumFmt()
const { fmtDateTime } = useDateFmt()

/** Статус кампании — бейджи темы. */
const statusBadge = (s:number)=>{
  const m:any = {9:'badge--ok', 11:'badge--warn', 7:'badge--brand', 4:'badge--info', 8:'badge--bad', '-1':'badge--neutral'}
  return m[String(s)] || 'badge--neutral'
}
</script>
