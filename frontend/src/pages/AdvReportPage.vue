<template>
  <div class="container-xxl" style="padding:20px 15px; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
    <!-- title наследование 1в1 PageHeaderWidget.php:13 + WbAdvReportController.php:26 ($this->title='Аналитика рекламы WB' → route.meta.title, динамика 'Компания: name') -->
    <PageHeaderWidget v-if="detail?.campaign" :title="'Компания: ' + detail.campaign.name" :nm-id="detail.campaign.campaign_id" />
    <h1 v-else style="font-size:20px; font-weight:700; margin-bottom:12px">Аналитика рекламы WB</h1>

    <!-- фильтр: UniversalFilter (campaign_id + даты), т.к. WbFilterBar только для nm_id/date_from/date_to.
         Кнопки -Q/-Y/LY/TD + Применить/Сбросить 1в1 WbFilterBar (TD правит только date_to). -->
    <div class="row mb-3">
      <div class="col-md-6">
        <UniversalFilter
          label="Выберите кампанию" placeholder="Поиск по ID или названию..."
          :data="campaignList" v-model="filters.campaign_id"
          v-model:date-from="filters.date_from" v-model:date-to="filters.date_to"
          @apply="fetchDetail" @reset="reset" />
      </div>
      <div class="col-md-6 p-0">
        <AdvCampaignInfo :detail="detail" />
      </div>
    </div>

    <!-- графики 4 шт как в php 163 — ECharts вместо AmCharts5, оси как DetailCharts.vue -->
    <template v-if="detail?.campaign">
      <AdvCharts :chart="detail.chart||[]" :app-chart="detail.appChart||[]" />
      <AdvSummaryTable :rows="detail.shortStats||[]" :campaign-id="filters.campaign_id" :date-from="filters.date_from" :date-to="filters.date_to" />
      <AdvAnotherTable :rows="detail.another||[]" :campaign-id="filters.campaign_id" :date-from="filters.date_from" :date-to="filters.date_to" />
      <AdvDailyTable :rows="detail.stats||[]" :campaign-id="filters.campaign_id" :date-from="filters.date_from" :date-to="filters.date_to" />
      <AdvQueriesTable :rows="detail.queries||[]" :campaign-id="filters.campaign_id" :date-from="filters.date_from" :date-to="filters.date_to" />
    </template>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import PageHeaderWidget from '../components/common/PageHeaderWidget.vue'
import UniversalFilter from '../components/common/UniversalFilter.vue'
import AdvCampaignInfo from '../components/adv-report/AdvCampaignInfo.vue'
import AdvCharts from '../components/adv-report/AdvCharts.vue'
import AdvSummaryTable from '../components/adv-report/AdvSummaryTable.vue'
import AdvAnotherTable from '../components/adv-report/AdvAnotherTable.vue'
import AdvDailyTable from '../components/adv-report/AdvDailyTable.vue'
import AdvQueriesTable from '../components/adv-report/AdvQueriesTable.vue'

const route = useRoute()
const router = useRouter()
const campaignList = ref<any[]>([])
const filters = ref({ campaign_id: '', date_from: '', date_to: '' })
const detail = ref<any>(null)
const isLoading = ref(false)

// init dates -14д .. сегодня как WbAdvReportController.php:23
const initDates = ()=>{
  const to = new Date().toISOString().slice(0,10)
  const from = new Date(Date.now() - 14*864e5).toISOString().slice(0,10)
  filters.value.date_from = from
  filters.value.date_to = to
}
initDates()

const fetchDetail = async()=>{
  if(!filters.value.campaign_id) return
  isLoading.value=true
  const q = new URLSearchParams({id: filters.value.campaign_id, date_from: filters.value.date_from, date_to: filters.value.date_to} as any)
  // синхроним query для прямых ссылок /wb-adv-report?id=&date_from=
  router.replace({path: '/wb-adv-report', query: {id: filters.value.campaign_id, date_from: filters.value.date_from, date_to: filters.value.date_to}})
  const { data:j } = await api.get(`/api/adv-report?${q}`)
  if(j.campaign){
    detail.value = j
    document.title = `Компания: ${j.campaign.name} — wbcms`
  } else { detail.value = null; document.title = 'Аналитика рекламы WB — wbcms' }
  isLoading.value=false
}
const reset = ()=>{
  filters.value.campaign_id=''; initDates(); detail.value=null
  router.replace({path:'/wb-adv-report'})
}

onMounted(async()=>{
  // campaignList для селекта + query из URL
  try{
    const { data:d } = await api.get('/api/adv-report/campaigns'); campaignList.value = Array.isArray(d) ? d : []
  }catch{}
  const q:any = route.query
  if(q.id) filters.value.campaign_id = String(q.id)
  if(q.date_from) filters.value.date_from = String(q.date_from)
  if(q.date_to) filters.value.date_to = String(q.date_to)
  if(filters.value.campaign_id) fetchDetail()
})
</script>
