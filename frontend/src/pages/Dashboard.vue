<template>
  <div class="container-xxl site-index page-dashboard">
    <div class="row">
      <div class="nav_div col-md-2">
        <SideMenu />
      </div>
      <div class="col-md-10">
        <div class="dsp__head">
          <PageTitle class="mb-0 flex-shrink-0" />
          <span class="spacer"></span>
          <div class="dsp__dates">
            <WbDateInput v-model="dateFrom" style="width: 160px" />
            <WbDateInput v-model="dateTo" style="width: 160px" />
          </div>
        </div>

        <div v-if="allLoaded && !anyData" class="dsp__empty dsp__empty--warn">
          Данных еще нет. Если вы заполнили <router-link :to="companyEditLink">WB API key</router-link>,
          то обратитесь в поддержку.
        </div>

        <WbTokenAlert />

        <div class="dsp__stack">
          <NewsBlock v-if="show.news" />
          <NewCards v-if="show.newCards" />
          <TopMetrics v-if="show.topMetrics" />
          <AdvCampaigns v-if="show.adv" :date-from="dateFrom" :date-to="dateTo" />
          <OrdersSummary v-if="show.ordersSummary" />
          <TodayStatsWidget v-if="show.today" />
          <LastOrders v-if="show.lastOrders" :date-from="dateFrom" :date-to="dateTo" />
          <LastSales v-if="show.lastSales" :date-from="dateFrom" :date-to="dateTo" />
        </div>
      </div>

      <!-- Финансовая аналитика — на всю ширину блока (под вертикальным меню) -->
      <div v-if="show.monthly" class="col-12 dsp__wide mobile-hide-block">
        <MonthlyProfitTable @report="(ok: boolean) => report('monthly', ok)" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Дашборд — блоки на теме (theme.md §5.7.11).
 *
 * Порядок и набор блоков прежние, но разметка собрана на блоках темы
 * (`.tile`, `.tbl-card`, `.wb-panel`), цвета статей расходов — код данных
 * (`--d-*` в theme/tokens.css), графики — с опциями боевых виджетов 1:1.
 */
import '@/assets/css/pages/page-dashboard.css'
import { ref, reactive, computed, provide } from 'vue'
import TopMetrics from '../components/dashboard/TopMetrics.vue'
import AdvCampaigns from '../components/dashboard/AdvCampaigns.vue'
import OrdersSummary from '../components/dashboard/OrdersSummary.vue'
import TodayStatsWidget from '../components/dashboard/TodayStatsWidget.vue'
import LastOrders from '../components/dashboard/LastOrders.vue'
import LastSales from '../components/dashboard/LastSales.vue'
import NewCards from '../components/dashboard/NewCards.vue'
import NewsBlock from '../components/dashboard/NewsBlock.vue'
import WbTokenAlert from '../components/dashboard/WbTokenAlert.vue'
import MonthlyProfitTable from '../components/profit/MonthlyProfitTable.vue'
import SideMenu from '../components/dashboard/SideMenu.vue'
import WbDateInput from '../components/common/WbDateInput.vue'
import PageTitle from '../components/common/PageTitle.vue'
import { useAuthStore } from '../stores/auth'

const dateFrom = ref(new Date(Date.now() - 3 * 864e5).toISOString().slice(0, 10))
const dateTo = ref(new Date().toISOString().slice(0, 10))

/* Гейты прав — по доменам (v3); в старом режиме (AUTH_V3=0) доменные гейты выключены. */
const auth = useAuthStore()
if (auth.authV3 && !auth.memberships.length) auth.loadMemberships().catch(() => {})
const show = computed(() => ({
  news: !auth.authV3 || auth.isAnyAdmin,
  newCards: !auth.authV3 || auth.isAnyAdmin,
  topMetrics: auth.canDomain('viewOrders'),
  adv: auth.canDomain('viewAdv'),
  ordersSummary: auth.canDomain('viewOrders'),
  today: auth.canDomain('viewOrders'),
  lastOrders: auth.canDomain('viewOrders'),
  lastSales: auth.canDomain('viewOrders'),
  monthly: auth.canDomain('viewFinance'),
}))

/* Пустые блоки: каждый виджет докладывает report(name, hasData), когда загрузка завершена. */
const blocks = reactive<Record<string, boolean>>({})
const REPORT_NAME: Record<string, string> = {
  news: 'news', newCards: 'new-cards', topMetrics: 'top-metrics', adv: 'adv',
  ordersSummary: 'orders-summary', today: 'today', lastOrders: 'last-orders',
  lastSales: 'last-sales', monthly: 'monthly',
}
const report = (name: string, has: boolean) => { blocks[name] = has }
provide('dashReport', report)
const blockNames = computed(() => Object.keys(show.value).map((k) => REPORT_NAME[k] || k))
const allLoaded = computed(() => blockNames.value.every((n) => blocks[n] !== undefined))
const anyData = computed(() => blockNames.value.some((n) => blocks[n] === true))

const companyEditLink = computed(() => (typeof auth.companyId === 'number' ? `/companies/${auth.companyId}` : '/companies'))
</script>
