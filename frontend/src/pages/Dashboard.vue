<template>
  <div class="site-index container-xxl page-dashboard">
    <div class="row" style="margin-bottom:20px">
      <div class="nav_div col-md-2">
        <SideMenu />
      </div>
      <div class="dash_div col-md-10">
        <div style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap">
          <WbDateInput v-model="dateFrom" style="width:190px" />
          <WbDateInput v-model="dateTo" style="width:190px" />
          <span class="text-muted" style="align-self:center; font-size:12px; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">{{ dateFrom }} → {{ dateTo }}</span>
        </div>

        <div v-if="allLoaded && !anyData" class="alert alert-info" style="border-radius:12px; padding:24px; text-align:center; font-size:14px">
          Данных еще нет. Если вы заполнили <router-link :to="companyEditLink">WB API key</router-link>,
          то обратитесь в поддержку.
        </div>
        <WbTokenAlert />
        <div class="dash-stack">
          <NewsBlock v-if="show.news" />
          <NewCards v-if="show.newCards" />
          <TopMetrics v-if="show.topMetrics" :date-from="dateFrom" :date-to="dateTo" />
          <AdvCampaigns v-if="show.adv" :date-from="dateFrom" :date-to="dateTo" />
          <OrdersSummary v-if="show.ordersSummary" />
          <TodayStatsWidget v-if="show.today" />
          <LastOrders v-if="show.lastOrders" :date-from="dateFrom" :date-to="dateTo" />
          <LastSales v-if="show.lastSales" :date-from="dateFrom" :date-to="dateTo" />
        </div>
      </div>
      <div v-if="show.monthly" class="col-12 mobile-hide-block" style="margin-top:16px; padding-left:0; padding-right:0">
        <MonthlyProfitTable @report="(ok) => report('monthly', ok)" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-dashboard.css'
import { ref, reactive, computed, provide } from 'vue'
import TopMetrics from '../components/dashboard/TopMetrics.vue'
import AdvCampaigns from '../components/dashboard/AdvCampaigns.vue'
import OrdersSummary from '../components/dashboard/OrdersSummary.vue'
import TodayStatsWidget from '../components/dashboard/TodayStatsWidget.vue'
import LastOrders from '../components/dashboard/LastOrders.vue'
import LastSales from '../components/dashboard/LastSales.vue'
import MonthlyProfitTable from '../components/profit/MonthlyProfitTable.vue'
import NewCards from '../components/dashboard/NewCards.vue'
import NewsBlock from '../components/dashboard/NewsBlock.vue'
import SideMenu from '../components/dashboard/SideMenu.vue'
import WbTokenAlert from '../components/dashboard/WbTokenAlert.vue'
import WbDateInput from '../components/common/WbDateInput.vue'
import { useAuthStore } from '../stores/auth'

const dateFrom = ref(new Date(Date.now()-3*864e5).toISOString().slice(0,10))
const dateTo = ref(new Date().toISOString().slice(0,10))

// Пустые блоки: каждый виджет докладывает report(name, hasData) когда загрузка завершена.
// v-if внутри виджетов убирает их из DOM, отступы dash-stack схлопываются сами.
// Если данных нет нигде — показываем заглушку со ссылкой на свою компанию.
// В v3 (AUTH_V3=1) блоки закрыты доменными пермами; список блоков считается по тем же гейтам,
// иначе скрытые блоки не отчитаются и заглушка «данных нет» не появится.
const auth = useAuthStore()
// v3:news/new-cards закрыты на «админские»; isAnyAdmin для админа компании считаем
// по memberships — на прямом заходе на дашборд они ещё не загружены (роутер грузит их
// лениво только на /admin/*). Догружаем единожды, блоки появятся реактивно.
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
const blocks = reactive<Record<string, boolean>>({})
// Ключ блока в интерфейсе → имя, которым виджет отчитывается (dashReport).
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

const companyEditLink = computed(() => typeof auth.companyId === 'number' ? `/companies/${auth.companyId}` : '/companies')
</script>

<style scoped>
@media (max-width: 767px){ .nav_div{display:none !important} .dash_div{width:100% !important; flex:0 0 100%; max-width:100%} .mobile-hide-block{display:none !important} }
.dash-stack > * { margin-bottom:16px; }
.dash-stack > *:last-child { margin-bottom:0; }
</style>
