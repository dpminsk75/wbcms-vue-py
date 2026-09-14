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

        <NewCards />
        <div style="height:16px"></div>
        <TopMetrics :date-from="dateFrom" :date-to="dateTo" />
        <div style="height:16px"></div>
        <AdvCampaigns :date-from="dateFrom" :date-to="dateTo" />
        <div style="height:16px"></div>
        <OrdersSummary />
        <div style="height:16px"></div>
        <TodayStatsWidget />
        <div style="height:16px"></div>
        <LastOrders :date-from="dateFrom" :date-to="dateTo" />
        <div style="height:16px"></div>
        <LastSales :date-from="dateFrom" :date-to="dateTo" />
      </div>
      <div class="col-12 mobile-hide-block" style="margin-top:16px; padding-left:0; padding-right:0">
        <MonthlyFinance />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TopMetrics from '../components/dashboard/TopMetrics.vue'
import AdvCampaigns from '../components/dashboard/AdvCampaigns.vue'
import OrdersSummary from '../components/dashboard/OrdersSummary.vue'
import TodayStatsWidget from '../components/dashboard/TodayStatsWidget.vue'
import LastOrders from '../components/dashboard/LastOrders.vue'
import LastSales from '../components/dashboard/LastSales.vue'
import MonthlyFinance from '../components/dashboard/MonthlyFinance.vue'
import NewCards from '../components/dashboard/NewCards.vue'
import SideMenu from '../components/dashboard/SideMenu.vue'

const dateFrom = ref(new Date(Date.now()-3*864e5).toISOString().slice(0,10))
const dateTo = ref(new Date().toISOString().slice(0,10))
</script>

<style scoped>
@media (max-width: 767px){ .nav_div{display:none !important} .dash_div{width:100% !important; flex:0 0 100%; max-width:100%} .mobile-hide-block{display:none !important} }
</style>
