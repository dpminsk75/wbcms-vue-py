<template>
  <div class="site-index container-xxl" style="padding:20px 15px">
    <div class="row" style="margin-bottom:20px">
      <div class="nav_div col-md-2">
        <SideMenu />
      </div>
      <div class="dash_div col-md-10">
        <div style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap">
          <input v-model="dateFrom" type="date" class="form-control" style="width:auto" />
          <input v-model="dateTo" type="date" class="form-control" style="width:auto" />
          <span class="text-muted" style="align-self:center; font-size:12px; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">{{ dateFrom }} → {{ dateTo }}</span>
        </div>

        <div v-if="allLoaded && !anyData" class="alert alert-info" style="border-radius:12px; padding:24px; text-align:center; font-size:14px">
          Данных еще нет. Если вы заполнили <router-link :to="companyEditLink">WB API key</router-link>,
          то обратитесь в поддержку.
        </div>
        <div class="dash-stack">
          <NewCards />
          <TopMetrics :date-from="dateFrom" :date-to="dateTo" />
          <AdvCampaigns :date-from="dateFrom" :date-to="dateTo" />
          <OrdersSummary />
          <TodayStatsWidget />
          <LastOrders :date-from="dateFrom" :date-to="dateTo" />
          <LastSales :date-from="dateFrom" :date-to="dateTo" />
        </div>
      </div>
      <div class="col-12 mobile-hide-block" style="margin-top:16px; padding-left:0; padding-right:0">
        <MonthlyFinance />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, provide } from 'vue'
import TopMetrics from '../components/dashboard/TopMetrics.vue'
import AdvCampaigns from '../components/dashboard/AdvCampaigns.vue'
import OrdersSummary from '../components/dashboard/OrdersSummary.vue'
import TodayStatsWidget from '../components/dashboard/TodayStatsWidget.vue'
import LastOrders from '../components/dashboard/LastOrders.vue'
import LastSales from '../components/dashboard/LastSales.vue'
import MonthlyFinance from '../components/dashboard/MonthlyFinance.vue'
import NewCards from '../components/dashboard/NewCards.vue'
import SideMenu from '../components/dashboard/SideMenu.vue'
import { useAuthStore } from '../stores/auth'

const dateFrom = ref(new Date(Date.now()-3*864e5).toISOString().slice(0,10))
const dateTo = ref(new Date().toISOString().slice(0,10))

// Пустые блоки: каждый виджет докладывает report(name, hasData) когда загрузка завершена.
// v-if внутри виджетов убирает их из DOM, отступы dash-stack схлопываются сами.
// Если данных нет нигде — показываем заглушку со ссылкой на свою компанию.
const blockNames = ['new-cards','top-metrics','adv','orders-summary','today','last-orders','last-sales','monthly']
const blocks = reactive<Record<string, boolean>>({})
const report = (name: string, has: boolean) => { blocks[name] = has }
provide('dashReport', report)
const allLoaded = computed(() => blockNames.every((n) => blocks[n] !== undefined))
const anyData = computed(() => blockNames.some((n) => blocks[n] === true))

const auth = useAuthStore()
const companyEditLink = computed(() => typeof auth.companyId === 'number' ? `/companies/${auth.companyId}` : '/companies')
</script>

<style scoped>
@media (max-width: 767px){ .nav_div{display:none !important} .dash_div{width:100% !important; flex:0 0 100%; max-width:100%} .mobile-hide-block{display:none !important} }
.dash-stack > * { margin-bottom:16px; }
.dash-stack > *:last-child { margin-bottom:0; }
</style>
