<template>
  <div class="container-xxl page-adv-report">
    <!-- title наследование 1в1 PageHeaderWidget.php:13 + WbAdvReportController.php:26 ($this->title='Аналитика рекламы WB' → route.meta.title, динамика 'Компания: name') -->
    <PageHeaderWidget v-if="detail?.campaign" :title="'Компания: ' + detail.campaign.name" :nm-id="detail.campaign.campaign_id" />
    <h1 v-else class="page-title">Аналитика рекламы WB</h1>

    <!-- Фильтр: стандартная панель (как в тепловой карте) — пресеты, даты, кампания
         и кнопки Применить/Сбросить. Кнопки рисует страница (не компонент дат),
         всегда видны, независимо от того, загружен ли отчёт. -->
    <div class="row mb-3">
      <div class="col-md-6">
        <div class="wb-filter-panel page-adv-report__filter">
          <WbDateRangeFilter v-model:from="filters.date_from" v-model:to="filters.date_to" default-preset="14" bare @apply="onDates" @reset="onReset">
            <template #extra>
              <div class="wb-field page-adv-report__campaign">
                <label class="wb-field__label">Кампания</label>
                <!-- Свой выпадающий список (был Select2 в UniversalFilter): поиск + статус кампании.
                     Статус виден и в свёрнутом поле, и в каждой строке списка. -->
                <div class="page-adv-report__pick" ref="pickRef">
                  <button type="button" class="wb-input page-adv-report__pick-btn d-flex align-items-center justify-content-between gap-2"
                          :aria-expanded="pickOpen" @click="pickOpen = !pickOpen">
                    <span class="d-flex align-items-center gap-2 page-adv-report__pick-text">
                      <span class="page-adv-report__pick-label" :class="{ 'is-empty': !filters.campaign_id }">{{ campaignTitle(filters.campaign_id) || 'Выберите кампанию...' }}</span>
                      <span v-if="filters.campaign_id" class="badge flex-shrink-0" :class="statusBadge(selectedStatus)">{{ statusText(selectedStatus) }}</span>
                    </span>
                    <span class="d-flex align-items-center gap-2 flex-shrink-0">
                      <i v-if="filters.campaign_id" class="bi bi-x-circle page-adv-report__pick-clear" title="Очистить" @click.stop="clearCampaign"></i>
                      <i class="bi" :class="pickOpen ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                    </span>
                  </button>
                  <div v-if="pickOpen" class="page-adv-report__pick-pop">
                    <div class="page-adv-report__pick-search">
                      <input v-model="pickQuery" class="wb-input" placeholder="Поиск: название или ID" @keydown.esc="pickOpen = false" />
                    </div>
                    <div class="page-adv-report__pick-list">
                      <div v-if="!pickFiltered.length" class="page-adv-report__pick-empty">Ничего не найдено</div>
                      <button v-for="c in pickFiltered" :key="campaignId(c)" type="button"
                              class="page-adv-report__pick-row d-flex align-items-center justify-content-between gap-2"
                              :class="{ 'is-active': campaignId(c) === filters.campaign_id }"
                              @click="selectCampaign(campaignId(c))">
                        <span class="page-adv-report__pick-name">{{ campaignName(c) }}</span>
                        <span class="badge flex-shrink-0" :class="statusBadge(campaignStatus(c))">{{ statusText(campaignStatus(c)) }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </WbDateRangeFilter>
          <div class="wb-filter-panel__btns">
            <button class="btn btn--brand wb-filter-panel__apply" @click="applyFilters">Применить</button>
            <button class="btn btn--outline wb-filter-panel__apply" @click="onReset">Сбросить</button>
          </div>
        </div>
      </div>
      <div class="col-md-6">
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
import '@/assets/css/pages/page-adv-report.css'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import PageHeaderWidget from '../components/common/PageHeaderWidget.vue'
import WbDateRangeFilter from '../components/common/WbDateRangeFilter.vue'
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
// (ровно 14 суток включительно — как пресет «14 дней», локальное время, без UTC-сдвига)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const initDates = ()=>{
  const to = new Date()
  const from = new Date(to.getTime())
  from.setDate(from.getDate() - 13)
  filters.value.date_from = fmtD(from)
  filters.value.date_to = fmtD(to)
}
initDates()

const fetchDetail = async()=>{
  if(!filters.value.campaign_id){ detail.value = null; document.title = 'Аналитика рекламы WB — SelBI'; return }
  isLoading.value=true
  const q = new URLSearchParams({id: filters.value.campaign_id, date_from: filters.value.date_from, date_to: filters.value.date_to} as any)
  // синхроним query для прямых ссылок /wb-adv-report?id=&date_from=
  router.replace({path: '/wb-adv-report', query: {id: filters.value.campaign_id, date_from: filters.value.date_from, date_to: filters.value.date_to}})
  const { data:j } = await api.get(`/api/adv-report?${q}`)
  if(j.campaign){
    detail.value = j
    document.title = `Компания: ${j.campaign.name} — SelBI`
  } else { detail.value = null; document.title = 'Аналитика рекламы WB — SelBI' }
  isLoading.value=false
}
/** Смена периода в блоке дат: только запоминаем даты (применение — кнопкой внизу). */
const onDates = (p: { from: string, to: string })=>{
  filters.value.date_from = p.from
  filters.value.date_to = p.to
}

/** Применение фильтра: даты из полей + выбранная кампания. */
const applyFilters = ()=>{
  if(!filters.value.campaign_id){ detail.value = null; document.title = 'Аналитика рекламы WB — SelBI'; return }
  fetchDetail()
}

const onReset = ()=>{
  filters.value.campaign_id = ''
  initDates()
  detail.value = null
  document.title = 'Аналитика рекламы WB — SelBI'
  router.replace({path:'/wb-adv-report'})
}

/** id кампании в разных ответах API: id / campaign_id. */
const campaignId = (c:any)=> String(c?.id ?? c?.campaign_id ?? '')
const campaignName = (c:any)=> String(c?.name ?? c?.label ?? c?.title ?? c?.id ?? '')

/* ---- Выпадающий список кампаний (поиск + статус) ---- */
const STATUS_TEXT: Record<string,string> = { '9':'Активна', '11':'Пауза', '7':'Завершена', '4':'Готова к запуску', '8':'Отклонена', '-1':'Удалена' }
const STATUS_BADGE: Record<string,string> = { '9':'badge--ok', '11':'badge--warn', '7':'badge--brand', '4':'badge--info', '8':'badge--bad', '-1':'badge--neutral' }
const campaignStatus = (c:any)=> String(c?.status ?? '')
const statusText = (s:string)=> STATUS_TEXT[String(s)] ?? '???'
const statusBadge = (s:string)=> STATUS_BADGE[String(s)] ?? 'badge--neutral'

const pickRef = ref<HTMLElement|null>(null)
const pickOpen = ref(false)
const pickQuery = ref('')

/** Кампании, подходящие под поиск (по названию или ID). */
const pickFiltered = computed(()=>{
  const q = pickQuery.value.trim().toLowerCase()
  if(!q) return campaignList.value
  return campaignList.value.filter(c =>
    campaignName(c).toLowerCase().includes(q) || campaignId(c).toLowerCase().includes(q)
  )
})
/** Название выбранной кампании (пусто — если её нет в списке). */
const campaignTitle = (id:string)=>{
  const c = campaignList.value.find(x=>campaignId(x)===String(id))
  return c ? campaignName(c) : ''
}
/** Статус выбранной кампании (для бейджа в свёрнутом поле). */
const selectedStatus = computed(()=>{
  const c = campaignList.value.find(x=>campaignId(x)===String(filters.value.campaign_id))
  return c ? campaignStatus(c) : ''
})
const selectCampaign = (id:string)=>{
  filters.value.campaign_id = id
  pickOpen.value = false
  pickQuery.value = ''
}
const clearCampaign = ()=>{
  filters.value.campaign_id = ''
  pickQuery.value = ''
}
/** Клик вне списка — закрыть. */
const onDocClick = (e:MouseEvent)=>{
  if(!pickOpen.value) return
  const el = pickRef.value
  if(el && !el.contains(e.target as Node)) pickOpen.value = false
}

onMounted(async()=>{
  // campaignList для списка кампаний + query из URL
  document.addEventListener('mousedown', onDocClick)
  try{
    const { data:d } = await api.get('/api/adv-report/campaigns'); campaignList.value = Array.isArray(d) ? d : []
  }catch{}
  const q:any = route.query
  if(q.id) filters.value.campaign_id = String(q.id)
  if(q.date_from) filters.value.date_from = String(q.date_from)
  if(q.date_to) filters.value.date_to = String(q.date_to)
  if(filters.value.campaign_id) fetchDetail()
})

onBeforeUnmount(()=> document.removeEventListener('mousedown', onDocClick))
</script>
