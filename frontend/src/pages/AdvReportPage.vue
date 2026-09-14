<template>
  <div class="container-xxl" style="padding:20px 15px; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
    <!-- title наследование 1в1 PageHeaderWidget.php:13 + WbAdvReportController.php:26 -->
    <PageHeaderWidget v-if="detail?.campaign" :title="'Компания: ' + detail.campaign.name" :nm-id="detail.campaign.campaign_id" />
    <h1 v-else style="font-size:20px; font-weight:700; margin-bottom:12px">Аналитика рекламы WB</h1>

    <!-- фильтр: универсальный как UniversalFilterWidget.php:9 — searchable Select2 + даты, аналог WbFilterBar для всех где не подходит WbFilterBar -->
    <div class="row mb-3">
      <div class="col-md-6">
        <UniversalFilter
          label="Выберите кампанию" placeholder="Поиск по ID или названию..."
          :data="campaignList" v-model="filters.campaign_id"
          v-model:date-from="filters.date_from" v-model:date-to="filters.date_to"
          @apply="fetchDetail" @reset="reset" />
      </div>
      <div class="col-md-6 p-0">
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
      </div>
    </div>

    <!-- графики 4 шт как в php 163 — сохраняем, ECharts вместо AmCharts5 -->
    <template v-if="detail?.campaign">
      <div class="row mb-3">
        <div class="col-md-7 div-chart">
          <div class="card p-0 panel panel-default" style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
            <div class="panel-heading d-flex align-items-center p-3" style="justify-content:center; min-height:40px;">
              <span class="mx-auto"><b>Расходы и показатели компании</b></span>
              <div class="btn-group btn-group-sm ms-2" role="group">
                <button v-for="u in ['day','week','month']" :key="u" class="btn btn-outline-secondary" :class="{active: tlUnit===u}" @click="tlUnit=u">{{ u==='day'?'D':u==='week'?'W':'M' }}</button>
                <button class="btn btn-secondary ms-2 active" title="Подписи"><i class="bi bi-tag"></i></button>
              </div>
            </div>
            <div class="panel-body"><VChart :option="tlOption" autoresize style="height:400px" /></div>
          </div>
        </div>
        <div class="col-md-5 div-chart" v-if="appChart.length">
          <div class="card ms-3 me-0 p-0 panel panel-default" style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
            <div class="panel-heading d-flex align-items-center p-3" style="justify-content:center; min-height:40px;">
              <span class="mx-auto"><b>Устр-ва: заказы, корзины, показы</b></span>
              <div class="btn-group btn-group-sm ms-2" role="group">
                <button v-for="u in ['day','week','month']" :key="u" class="btn btn-outline-secondary" :class="{active: appUnit===u}" @click="appUnit=u">{{ u==='day'?'D':u==='week'?'W':'M' }}</button>
              </div>
            </div>
            <div class="panel-body"><VChart :option="appOption" autoresize style="height:400px" /></div>
          </div>
        </div>
      </div>
      <div class="row mb-3">
        <div class="col-md-6 div-chart">
          <div class="card p-0 panel panel-default" style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
            <div class="panel-heading d-flex align-items-center p-3" style="justify-content:center; min-height:40px;">
              <span class="mx-auto"><b>Показатели: CPM, CPO</b></span>
              <div class="btn-group btn-group-sm ms-2"><button v-for="u in ['day','week','month']" :key="u" class="btn btn-outline-secondary" :class="{active: cpmUnit===u}" @click="cpmUnit=u">{{ u==='day'?'D':u==='week'?'W':'M' }}</button></div>
            </div>
            <div class="panel-body"><VChart :option="cpmOption" autoresize style="height:400px" /></div>
          </div>
        </div>
        <div class="col-md-6 div-chart">
          <div class="card ms-3 me-0 p-0 panel panel-default" style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
            <div class="panel-heading d-flex align-items-center p-3" style="justify-content:center; min-height:40px;">
              <span class="mx-auto"><b>Показатели: CTR, CR</b></span>
              <div class="btn-group btn-group-sm ms-2"><button v-for="u in ['day','week','month']" :key="u" class="btn btn-outline-secondary" :class="{active: ctrUnit===u}" @click="ctrUnit=u">{{ u==='day'?'D':u==='week'?'W':'M' }}</button></div>
            </div>
            <div class="panel-body"><VChart :option="ctrOption" autoresize style="height:400px" /></div>
          </div>
        </div>
      </div>

      <!-- таблицы — ленты/гриды 10+ колонок паттерн B: width 100% auto, якорные ширины, Excel -->
      <!-- Сводные показатели (per nm_id) -->
      <div class="row mb-3 custom-compact-grid">
        <div class="col-12">
          <div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
            <div class="card-header text-white d-flex justify-content-between align-items-center" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700;">
              <span>Сводные показатели</span>
              <button class="btn btn-sm btn-light" style="font-size:12px; padding:4px 12px; border-radius:6px" @click="exportShort" :disabled="!detail.shortStats.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
            </div>
            <div style="overflow-x:auto" ref="tblShortWrap"><table ref="tblShort" class="table table-bordered table-striped table-hover kv-grid-table mb-0 wb-adv-report-index" style="font-size:12px; width:100%">
              <thead><tr>
                <th style="width:90px; text-align:center">Арт WB</th>
                <th style="width:280px; text-align:center">Товар / Артикул</th>
                <th style="width:85px; text-align:center">Показы</th><th style="width:85px; text-align:center">Клики</th><th style="width:85px; text-align:center">Корзины</th><th style="width:85px; text-align:center">Заказы</th><th style="width:85px; text-align:center">Отмена</th>
                <th style="width:85px; text-align:center">CTR, %</th><th style="width:85px; text-align:center">CR, %</th><th style="width:90px; text-align:center">Затраты, ₽</th>
                <th style="width:85px; text-align:center">CPM, ₽</th><th style="width:85px; text-align:center">CPC, ₽</th><th style="width:85px; text-align:center">CPO, ₽</th>
              </tr></thead>
              <tbody><tr v-for="r in detail.shortStats" :key="r.nm_id">
                <td style="text-align:center"><a :href="'/wb/detail?nm_id='+r.nm_id" target="_blank" style="text-decoration:none">{{ r.nm_id }}</a></td>
                <td><div style="font-weight:700; font-size:13px; color:#2c3e50;">{{ r.title || '—' }}</div><div style="color:#666; font-size:11px;">Артикул: <b>{{ r.vendorCode }}</b></div></td>
                <td style="text-align:right">{{ fmt0(r.views) }}</td><td style="text-align:right">{{ fmt0(r.clicks) }}</td><td style="text-align:right">{{ fmt0(r.atbs) }}</td><td style="text-align:right">{{ fmt0(r.orders) }}</td><td style="text-align:right">{{ fmt0(r.canceled) }}</td>
                <td style="text-align:right">{{ r.views>0 ? fmt2(r.clicks/r.views*100) : '' }}</td><td style="text-align:right">{{ r.clicks>0 ? fmt2(r.atbs/r.clicks*100) : '' }}</td>
                <td style="text-align:right">{{ fmt2(r.sum) }}</td>
                <td style="text-align:right">{{ r.views>0 ? fmt2(r.sum/r.views*1000) : '' }}</td><td style="text-align:right">{{ r.clicks>0 ? fmt2(r.sum/r.clicks) : '' }}</td><td style="text-align:right">{{ r.orders>0 ? fmt2(r.sum/r.orders) : '' }}</td>
              </tr></tbody>
              <tfoot v-if="detail.shortStats.length"><tr style="font-weight:700; background:#f2e7c3">
                <td colspan="2" style="text-align:right">Итого</td>
                <td style="text-align:right">{{ fmt0(sumField(detail.shortStats,'views')) }}</td><td style="text-align:right">{{ fmt0(sumField(detail.shortStats,'clicks')) }}</td><td style="text-align:right">{{ fmt0(sumField(detail.shortStats,'atbs')) }}</td><td style="text-align:right">{{ fmt0(sumField(detail.shortStats,'orders')) }}</td><td style="text-align:right">{{ fmt0(sumField(detail.shortStats,'canceled')) }}</td>
                <td style="text-align:right">{{ totalViews>0 ? fmt2(totalClicks/totalViews*100) : '' }}</td><td style="text-align:right">{{ totalClicks>0 ? fmt2(totalAtbs/totalClicks*100) : '' }}</td>
                <td style="text-align:right">{{ fmt2(sumField(detail.shortStats,'sum')) }}</td><td colspan="3"></td>
              </tr></tfoot>
            </table></div>
          </div>
        </div>
      </div>

      <!-- Другие товары -->
      <div v-if="detail.another.length" class="row mb-3">
        <div class="col-12"><div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
          <div class="card-header text-white d-flex justify-content-between align-items-center" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700;">
            <span>Другие товары в заказах</span>
            <button class="btn btn-sm btn-light" style="font-size:12px; padding:4px 12px; border-radius:6px" @click="exportAnother" :disabled="!detail.another.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
          </div>
          <div style="overflow-x:auto"><table class="table table-bordered table-striped table-hover kv-grid-table mb-0 wb-adv-report-index" style="font-size:12px; width:100%">
            <thead><tr>
              <th style="width:90px; text-align:center">Арт WB</th><th style="width:280px; text-align:center">Товар / Артикул</th><th style="width:85px; text-align:center">Корзины</th><th style="width:85px; text-align:center">Заказы</th><th style="width:85px; text-align:center">Отмена</th><th style="width:90px; text-align:center">Сумма, ₽</th>
            </tr></thead>
            <tbody><tr v-for="r in detail.another.slice(0,50)" :key="r.nm_id">
              <td style="text-align:center"><a :href="'/wb/detail?nm_id='+r.nm_id" target="_blank" style="text-decoration:none">{{ r.nm_id }}</a></td>
              <td><div style="font-weight:700;">{{ r.title }}</div><div style="color:#666; font-size:11px;">Артикул: <b>{{ r.vendorCode }}</b></div></td>
              <td style="text-align:right">{{ fmt0(r.atbs) }}</td><td style="text-align:right">{{ fmt0(r.orders) }}</td><td style="text-align:right">{{ fmt0(r.canceled) }}</td><td style="text-align:right">{{ fmt2(r.sum_price) }}</td>
            </tr></tbody>
          </table></div>
        </div></div>
      </div>

      <!-- Общая статистика по дням -->
      <div class="row custom-compact-grid">
        <div class="col-12"><div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
          <div class="card-header text-white d-flex justify-content-between align-items-center" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700;">
            <span>Общая статистика по дням</span>
            <button class="btn btn-sm btn-light" style="font-size:12px; padding:4px 12px; border-radius:6px" @click="exportStats" :disabled="!detail.stats.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
          </div>
          <div style="overflow-x:auto" ref="tblStatsWrap"><table ref="tblStats" class="table table-bordered table-striped table-hover kv-grid-table mb-0 wb-adv-report-index" style="font-size:12px; width:100%">
            <thead><tr>
              <th style="width:90px; text-align:center">Дата</th><th style="width:90px; text-align:center">Арт WB</th><th style="width:280px; text-align:center">Товар / Артикул</th>
              <th style="width:80px; text-align:center">Показы</th><th style="width:80px; text-align:center">Клики</th><th style="width:80px; text-align:center">Корзины</th><th style="width:80px; text-align:center">Заказы</th><th style="width:80px; text-align:center">Отмена</th>
              <th style="width:80px; text-align:center">CTR, %</th><th style="width:80px; text-align:center">CR, %</th><th style="width:90px; text-align:center">Затраты, ₽</th><th style="width:80px; text-align:center">CPM, ₽</th><th style="width:80px; text-align:center">CPC, ₽</th><th style="width:80px; text-align:center">CPO, ₽</th>
            </tr></thead>
            <tbody><tr v-for="r in detail.stats" :key="r.date + '-' + r.nm_id">
              <td style="text-align:center; white-space:nowrap">{{ fmtDate(r.date) }}</td><td style="text-align:center"><a :href="'/wb/detail?nm_id='+r.nm_id" target="_blank" style="text-decoration:none">{{ r.nm_id }}</a></td>
              <td><div style="font-weight:700;">{{ r.title }}</div><div style="color:#666; font-size:11px;">Артикул: <b>{{ r.vendorCode }}</b></div></td>
              <td style="text-align:right">{{ fmt0(r.views) }}</td><td style="text-align:right">{{ fmt0(r.clicks) }}</td><td style="text-align:right">{{ fmt0(r.atbs) }}</td><td style="text-align:right">{{ fmt0(r.orders) }}</td><td style="text-align:right">{{ fmt0(r.canceled) }}</td>
              <td style="text-align:right">{{ r.views>0 ? fmt2(r.clicks/r.views*100) : '' }}</td><td style="text-align:right">{{ r.clicks>0 ? fmt2(r.atbs/r.clicks*100) : '' }}</td>
              <td style="text-align:right">{{ fmt2(r.sum) }}</td><td style="text-align:right">{{ r.views>0 ? fmt2(r.sum/r.views*1000) : '' }}</td><td style="text-align:right">{{ r.clicks>0 ? fmt2(r.sum/r.clicks) : '' }}</td><td style="text-align:right">{{ r.orders>0 ? fmt2(r.sum/r.orders) : '' }}</td>
            </tr></tbody>
          </table></div>
        </div></div>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeaderWidget from '../components/common/PageHeaderWidget.vue'
import UniversalFilter from '../components/common/UniversalFilter.vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DatasetComponent, CanvasRenderer])

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

const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const fmtDate = (v:any)=> v ? new Date(v).toLocaleDateString('ru-RU') : '—'
const fmtDateTime = (v:any)=> v ? new Date(v).toLocaleString('ru-RU') : '—'
const sumField = (arr:any[], k:string)=> arr.reduce((a,r)=> a + (Number(r[k])||0),0)
const totalViews = computed(()=> sumField(detail.value?.shortStats||[],'views'))
const totalClicks = computed(()=> sumField(detail.value?.shortStats||[],'clicks'))
const totalAtbs = computed(()=> sumField(detail.value?.shortStats||[],'atbs'))
const statusClass = (s:number)=>{
  const m:any = {9:'label-success',11:'label-warning',7:'label-primary',4:'label-info',8:'label-danger', '-1':'label-default'}
  return m[String(s)] || 'label-default'
}

// charts — ECharts вместо AmCharts5, D/W/M группировка суммой
const tlUnit = ref<'day'|'week'|'month'>('week')
const appUnit = ref<'day'|'week'|'month'>('day')
const cpmUnit = ref<'day'|'week'|'month'>('week')
const ctrUnit = ref<'day'|'week'|'month'>('week')

function groupByInterval(data:any[], unit:string){
  if(unit==='day' || !data.length) return data
  const buckets:Record<string, any> = {}
  for(const r of data){
    const d = new Date(r.odate || r.date)
    let key: string
    if(unit==='month'){ key = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') }
    else { // week — понедельник
      const w = new Date(d); const day = (w.getDay()+6)%7; w.setDate(w.getDate()-day)
      key = w.toISOString().slice(0,10)
    }
    if(!buckets[key]) buckets[key] = {odate:key, views:0, clicks:0, atbs:0, orders:0, shks:0, sum:0, sum_price:0, canceled:0, CPM:0, CPC:0, CPO:0, CTR:0, CR:0, cnt:0}
    const b = buckets[key]
    b.views += Number(r.views)||0; b.clicks+=Number(r.clicks)||0; b.atbs+=Number(r.atbs)||0; b.orders+=Number(r.orders)||0; b.sum+=Number(r.sum)||0; b.sum_price+=Number(r.sum_price||r.sum)||0; b.canceled+=Number(r.canceled)||0
    b.cnt++
  }
  const out = Object.values(buckets).sort((a:any,b:any)=> a.odate.localeCompare(b.odate))
  for(const b of out as any[]){
    b.CPM = b.views ? b.sum/b.views*1000 : 0
    b.CPC = b.clicks ? b.sum/b.clicks : 0
    b.CPO = b.orders ? b.sum/b.orders : 0
    b.CTR = b.views ? b.clicks/b.views*100 : 0
    b.CR = b.clicks ? b.atbs/b.clicks*100 : 0
  }
  return out
}
function groupApp(data:any[], unit:string){
  if(unit==='day' || !data.length) return data
  const buckets:Record<string, any> = {}
  for(const r of data){
    const d = new Date(r.date)
    let key: string
    if(unit==='month'){ key = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-01' }
    else { const w=new Date(d); const day=(w.getDay()+6)%7; w.setDate(w.getDate()-day); key=w.toISOString().slice(0,10) }
    if(!buckets[key]) buckets[key]={date:key, clicks_1:0,clicks_32:0,clicks_64:0, orders_1:0,orders_32:0,orders_64:0, atbs_1:0,atbs_32:0,atbs_64:0, views_1:0,views_32:0,views_64:0, sum_price_1:0,sum_price_32:0,sum_price_64:0}
    const b=buckets[key]
    for(const k of ['clicks_1','clicks_32','clicks_64','orders_1','orders_32','orders_64','atbs_1','atbs_32','atbs_64','views_1','views_32','views_64']){
      b[k] += Number(r[k])||0
    }
    for(const k of ['sum_price_1','sum_price_32','sum_price_64']) b[k]+=Number(r[k])||0
  }
  return Object.values(buckets).sort((a:any,b:any)=> a.date.localeCompare(b.date))
}

const tlData = computed(()=> groupByInterval(detail.value?.chart||[], tlUnit.value))
const appChart = computed(()=> detail.value?.appChart||[])
const appData = computed(()=> groupApp(appChart.value, appUnit.value))
const cpmData = computed(()=> groupByInterval(detail.value?.chart||[], cpmUnit.value))
const ctrData = computed(()=> groupByInterval(detail.value?.chart||[], ctrUnit.value))

const tlOption = computed(()=>{
  const d = tlData.value; if(!d.length) return {}
  const cats = d.map((r:any)=> r.odate)
  return {
    tooltip:{trigger:'axis'},
    legend:{data:['Клики','Корзины','Заказы','Расходы'], top:0, textStyle:{fontSize:11}},
    grid:{left:50,right:30,top:30,bottom:50,containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{fontSize:11, rotate:-45}},
    yAxis:[{type:'value', name:'Кол-во', min:0}, {type:'value', name:'Сумма ₽', min:0}],
    series:[
      {name:'Клики', type:'line', smooth:true, data:d.map((r:any)=> r.clicks), lineStyle:{width:2}, itemStyle:{color:'#f965cf'}, yAxisIndex:0, symbol:'circle', symbolSize:4},
      {name:'Корзины', type:'line', smooth:true, data:d.map((r:any)=> r.atbs), lineStyle:{width:2}, itemStyle:{color:'#660ec8'}, yAxisIndex:0, symbol:'circle', symbolSize:4},
      {name:'Заказы', type:'line', data:d.map((r:any)=> r.orders), lineStyle:{width:2}, itemStyle:{color:'#5067de'}, yAxisIndex:0, label:{show:true, fontSize:10}, symbol:'circle', symbolSize:4},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> r.sum), lineStyle:{width:3}, itemStyle:{color:'#f96666'}, yAxisIndex:1, label:{show:true, fontSize:10}, symbol:'circle', symbolSize:4},
    ]
  }
})
const appOption = computed(()=>{
  const d = appData.value; if(!d.length) return {}
  const cats = d.map((r:any)=> r.date)
  const groups = [
    {label:'Заказы', key:'orders', color:'#660ec8'},
    {label:'Кор-ны', key:'atbs', color:'#f96666'},
    {label:'Показы', key:'views', color:'#f965cf'},
  ]
  const series:any[] = []
  const types=[1,32,64]
  const appNames:any = {1:'💻',32:'🤖',64:'🍎'}
  for(const g of groups){
    for(let i=0;i<types.length;i++){
      const t=types[i]
      series.push({name: appNames[t]+' '+g.label, type:'bar', stack:g.key, data:d.map((r:any)=> r[`${g.key}_${t}`]||0), itemStyle:{color: g.color, opacity: 0.6 + i*0.2}, barWidth:'60%', tooltip:{valueFormatter:(v:any)=> fmt0(v)}})
    }
  }
  return {tooltip:{trigger:'axis'}, legend:{data:series.map(s=>s.name), top:0, textStyle:{fontSize:10}}, grid:{left:40,right:20,top:30,bottom:40,containLabel:true}, xAxis:{type:'category', data:cats, axisLabel:{fontSize:11, rotate:-45}}, yAxis:[{type:'value'},{type:'value'}], series}
})
const cpmOption = computed(()=>{
  const d=cpmData.value; if(!d.length) return {}
  const cats=d.map((r:any)=> r.odate)
  return {
    tooltip:{trigger:'axis'}, legend:{data:['CPM, ₽','CPO, ₽','Расходы'], top:0, textStyle:{fontSize:11}},
    grid:{left:50,right:30,top:30,bottom:50,containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{fontSize:11, rotate:-45}},
    yAxis:[{type:'value', name:'Показатель'},{type:'value', name:'Сумма ₽'}],
    series:[
      {name:'CPM, ₽', type:'line', smooth:true, data:d.map((r:any)=> r.CPM), itemStyle:{color:'#2196f3'}, yAxisIndex:0, label:{show:true}, symbol:'circle', symbolSize:4},
      {name:'CPO, ₽', type:'line', smooth:true, data:d.map((r:any)=> r.CPO), itemStyle:{color:'#c767dc'}, yAxisIndex:0, label:{show:true}, symbol:'circle', symbolSize:4},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> r.sum), itemStyle:{color:'#f44336'}, lineStyle:{width:3}, yAxisIndex:1, label:{show:true}, symbol:'circle', symbolSize:4},
    ]
  }
})
const ctrOption = computed(()=>{
  const d=ctrData.value; if(!d.length) return {}
  const cats=d.map((r:any)=> r.odate)
  return {
    tooltip:{trigger:'axis'}, legend:{data:['CTR, %','CR, %','Расходы'], top:0, textStyle:{fontSize:11}},
    grid:{left:50,right:30,top:30,bottom:50,containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{fontSize:11, rotate:-45}},
    yAxis:[{type:'value', name:'Показатель %'},{type:'value', name:'Сумма ₽'}],
    series:[
      {name:'CTR, %', type:'line', smooth:true, data:d.map((r:any)=> r.CTR), itemStyle:{color:'#9c27b0'}, yAxisIndex:0, label:{show:true}, symbol:'circle', symbolSize:4},
      {name:'CR, %', type:'line', smooth:true, data:d.map((r:any)=> r.CR), itemStyle:{color:'#660ec8'}, yAxisIndex:0, label:{show:true}, symbol:'circle', symbolSize:4},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> r.sum), itemStyle:{color:'#f44336'}, lineStyle:{width:3}, yAxisIndex:1, label:{show:true}, symbol:'circle', symbolSize:4},
    ]
  }
})

// col-resize паттерн B как в OrdersFeedAggregated
const tblShort = ref<HTMLTableElement|null>(null)
const tblStats = ref<HTMLTableElement|null>(null)
const enableResize = (tbl: HTMLTableElement | null)=>{
  if(!tbl) return
  const ths = tbl.querySelectorAll('th') as NodeListOf<HTMLTableCellElement>
  ths.forEach(th=>{
    if(th.querySelector('.col-resizer')) return
    th.style.position='relative'
    const r=document.createElement('div')
    r.className='col-resizer'
    r.style.cssText='position:absolute; top:0; right:0; width:6px; height:100%; cursor:col-resize; user-select:none; z-index:1'
    th.appendChild(r)
    let sx=0, sw=0
    const onMove=(e:MouseEvent)=>{ const w=Math.max(40, sw + e.clientX - sx); th.style.width=w+'px'; th.style.minWidth=w+'px'; tbl.style.tableLayout='fixed'; tbl.style.width='100%' }
    const onUp=()=>{ document.removeEventListener('mousemove',onMove); document.removeEventListener('mouseup',onUp); document.body.style.cursor='' }
    r.addEventListener('mousedown',(e:MouseEvent)=>{ sx=e.clientX; sw=th.offsetWidth; document.body.style.cursor='col-resize'; document.addEventListener('mousemove',onMove); document.addEventListener('mouseup',onUp); e.preventDefault() })
  })
  const fit=()=>{ if(tbl) tbl.style.width='100%' }
  window.addEventListener('resize', fit); fit()
}

const fetchDetail = async()=>{
  if(!filters.value.campaign_id) return
  isLoading.value=true
  const q = new URLSearchParams({id: filters.value.campaign_id, date_from: filters.value.date_from, date_to: filters.value.date_to} as any)
  // синхроним query для прямых ссылок /wb-adv-report?id=&date_from=
  router.replace({path: '/wb-adv-report', query: {id: filters.value.campaign_id, date_from: filters.value.date_from, date_to: filters.value.date_to}})
  const r = await fetch(`/api/adv-report?${q}`)
  const j = await r.json()
  if(j.campaign){
    detail.value = j
    document.title = `Компания: ${j.campaign.name} — wbcms`
  } else { detail.value = null; document.title = 'Аналитика рекламы WB — wbcms' }
  isLoading.value=false
  nextTick(()=>{ enableResize(tblShort.value); enableResize(tblStats.value) })
}
const reset = ()=>{
  filters.value.campaign_id=''; initDates(); detail.value=null
  router.replace({path:'/wb-adv-report'})
}

const exportShort = async()=>{
  if(!detail.value?.shortStats?.length) return
  const XLSX = await import('xlsx')
  const data = detail.value.shortStats.map((r:any)=>({
    'Арт WB': r.nm_id, 'Товар': r.title, 'Артикул': r.vendorCode,
    'Показы': r.views, 'Клики': r.clicks, 'Корзины': r.atbs, 'Заказы': r.orders, 'Отмена': r.canceled,
    'CTR %': r.views? +(r.clicks/r.views*100).toFixed(2):'', 'CR %': r.clicks? +(r.atbs/r.clicks*100).toFixed(2):'',
    'Затраты': r.sum, 'CPM': r.views? +(r.sum/r.views*1000).toFixed(2):'', 'CPC': r.clicks? +(r.sum/r.clicks).toFixed(2):'', 'CPO': r.orders? +(r.sum/r.orders).toFixed(2):'',
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Сводные'); XLSX.writeFile(wb, `adv-short_${filters.value.campaign_id}_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
}
const exportStats = async()=>{
  if(!detail.value?.stats?.length) return
  const XLSX = await import('xlsx')
  const data = detail.value.stats.map((r:any)=>({
    'Дата': r.date, 'Арт WB': r.nm_id, 'Товар': r.title, 'Артикул': r.vendorCode,
    'Показы': r.views, 'Клики': r.clicks, 'Корзины': r.atbs, 'Заказы': r.orders, 'Отмена': r.canceled,
    'CTR %': r.views? +(r.clicks/r.views*100).toFixed(2):'', 'CR %': r.clicks? +(r.atbs/r.clicks*100).toFixed(2):'',
    'Затраты': r.sum, 'CPM': r.views? +(r.sum/r.views*1000).toFixed(2):'', 'CPC': r.clicks? +(r.sum/r.clicks).toFixed(2):'', 'CPO': r.orders? +(r.sum/r.orders).toFixed(2):'',
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'По дням'); XLSX.writeFile(wb, `adv-daily_${filters.value.campaign_id}_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
}
const exportAnother = async()=>{
  if(!detail.value?.another?.length) return
  const XLSX = await import('xlsx')
  const data = detail.value.another.map((r:any)=>({
    'Арт WB': r.nm_id, 'Товар': r.title, 'Артикул': r.vendorCode, 'Корзины': r.atbs, 'Заказы': r.orders, 'Отмена': r.canceled, 'Сумма': r.sum_price,
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Другие'); XLSX.writeFile(wb, `adv-another_${filters.value.campaign_id}_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
}

onMounted(async()=>{
  // campaignList для селекта + query из URL
  try{
    const r = await fetch('/api/adv-report/campaigns'); const d=await r.json(); campaignList.value = Array.isArray(d) ? d : []
  }catch{}
  const q:any = route.query
  if(q.id) filters.value.campaign_id = String(q.id)
  if(q.date_from) filters.value.date_from = String(q.date_from)
  if(q.date_to) filters.value.date_to = String(q.date_to)
  if(filters.value.campaign_id) fetchDetail()
})
watch(()=> detail.value?.shortStats, ()=> nextTick(()=> enableResize(tblShort.value)))
watch(()=> detail.value?.stats, ()=> nextTick(()=> enableResize(tblStats.value)))
</script>
<style>
.wb-adv-report-index .table { font-size:12px; width:100%; }
.wb-adv-report-index .table td, .wb-adv-report-index .table th { padding:4px 8px !important; }
</style>
