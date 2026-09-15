<template>
  <div>
    <div class="row mb-3">
      <div class="col-md-7 div-chart">
        <div class="card p-0 panel panel-default" style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
          <div class="panel-heading d-flex align-items-center p-3" style="justify-content:center; min-height:40px;">
            <span class="mx-auto"><b>Расходы и показатели компании</b></span>
            <div class="btn-group btn-group-sm ms-2" role="group">
              <button v-for="u in ['day','week','month']" :key="u" class="btn btn-outline-secondary" :class="{active: tlUnit===u}" @click="tlUnit=(u as any)">{{ u==='day'?'D':u==='week'?'W':'M' }}</button>
              <button class="btn ms-2" :class="showTl?'btn-secondary active':'btn-outline-secondary'" title="Подписи" @click="showTl=!showTl"><i class="bi bi-tag"></i></button>
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
              <button v-for="u in ['day','week','month']" :key="u" class="btn btn-outline-secondary" :class="{active: appUnit===u}" @click="appUnit=(u as any)">{{ u==='day'?'D':u==='week'?'W':'M' }}</button>
              <button class="btn ms-2" :class="showApp?'btn-secondary active':'btn-outline-secondary'" title="Подписи" @click="showApp=!showApp"><i class="bi bi-tag"></i></button>
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
            <div class="btn-group btn-group-sm ms-2">
              <button v-for="u in ['day','week','month']" :key="u" class="btn btn-outline-secondary" :class="{active: cpmUnit===u}" @click="cpmUnit=(u as any)">{{ u==='day'?'D':u==='week'?'W':'M' }}</button>
              <button class="btn ms-2" :class="showCpm?'btn-secondary active':'btn-outline-secondary'" title="Подписи" @click="showCpm=!showCpm"><i class="bi bi-tag"></i></button>
            </div>
          </div>
          <div class="panel-body"><VChart :option="cpmOption" autoresize style="height:400px" /></div>
        </div>
      </div>
      <div class="col-md-6 div-chart">
        <div class="card ms-3 me-0 p-0 panel panel-default" style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
          <div class="panel-heading d-flex align-items-center p-3" style="justify-content:center; min-height:40px;">
            <span class="mx-auto"><b>Показатели: CTR, CR</b></span>
            <div class="btn-group btn-group-sm ms-2">
              <button v-for="u in ['day','week','month']" :key="u" class="btn btn-outline-secondary" :class="{active: ctrUnit===u}" @click="ctrUnit=(u as any)">{{ u==='day'?'D':u==='week'?'W':'M' }}</button>
              <button class="btn ms-2" :class="showCtr?'btn-secondary active':'btn-outline-secondary'" title="Подписи" @click="showCtr=!showCtr"><i class="bi bi-tag"></i></button>
            </div>
          </div>
          <div class="panel-body"><VChart :option="ctrOption" autoresize style="height:400px" /></div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DatasetComponent, CanvasRenderer])

// Данные 1в1 WbAdvReportController: ChartStats (odate/views/clicks/atbs/orders/sum/CPM/CPC/CPO/CTR/CR)
// + ChartAppStats flat(date, clicks|orders|atbs|views|sum_price _1|_32|_64). Группировка W/M суммой,
// производные CPM/CPC/CPO/CTR/CR пересчетом из сумм (точнее чем AmCharts average).
const props = defineProps<{ chart: any[], appChart: any[] }>()

// Стартовый интервал 1в1 php, по длине ряда (сброс только при смене кампании/периода, ручной выбор не трогаем):
// timeline/cpm/ctr — week, длина>28 → month (_linechart.php:261-266, day по дефолту не бывает);
// app — day, длина>8 → month (ветка week в _appchart.php:401 недостижима — оставлена как есть).
const tlUnit = ref<'day'|'week'|'month'>('week')
const appUnit = ref<'day'|'week'|'month'>('day')
const cpmUnit = ref<'day'|'week'|'month'>('week')
const ctrUnit = ref<'day'|'week'|'month'>('week')
watch(()=> (props.chart||[]).length, (n)=> {
  const u = (n>28 ? 'month' : 'week') as 'day'|'week'|'month'
  tlUnit.value = u; cpmUnit.value = u; ctrUnit.value = u
}, {immediate:true})
watch(()=> (props.appChart||[]).length, (n)=> { appUnit.value = (n>8 ? 'month' : 'day') as 'day'|'week'|'month' }, {immediate:true})
const showTl = ref(true)
const showApp = ref(false) // бары + подписи шумят, по дефолту скрыты
const showCpm = ref(true)
const showCtr = ref(true)

const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)

function groupByInterval(data:any[], unit:string){
  if(unit==='day' || !data.length) return data
  const buckets:Record<string, any> = {}
  for(const r of data){
    const d = new Date(r.odate || r.date)
    let key: string
    if(unit==='month'){ key = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') }
    else { const w = new Date(d); const day = (w.getDay()+6)%7; w.setDate(w.getDate()-day); key = w.toISOString().slice(0,10) }
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
    for(const k of ['clicks_1','clicks_32','clicks_64','orders_1','orders_32','orders_64','atbs_1','atbs_32','atbs_64','views_1','views_32','views_64']) b[k] += Number(r[k])||0
    for(const k of ['sum_price_1','sum_price_32','sum_price_64']) b[k]+=Number(r[k])||0
  }
  return Object.values(buckets).sort((a:any,b:any)=> a.date.localeCompare(b.date))
}

const tlData = computed(()=> groupByInterval(props.chart||[], tlUnit.value))
const appData = computed(()=> groupApp(props.appChart||[], appUnit.value))
const cpmData = computed(()=> groupByInterval(props.chart||[], cpmUnit.value))
const ctrData = computed(()=> groupByInterval(props.chart||[], ctrUnit.value))

// Оформление осей как в DetailCharts.vue: легенда снизу, сетка 50/50/40/90,
// x rotate 30 interval 0 margin 16 11px #333, y 11px в цвет серии + ru-RU формат,
// подписи серий с белым фоном/рамкой (иначе голые цифры наезжают друг на друга).
const lbl = (color:string, show:boolean)=> show ? {
  show:true, position:'top', distance:10, fontSize:11, fontWeight:700, color,
  backgroundColor:'#ffffff', borderColor:color, borderWidth:1.5, borderRadius:6, padding:[3,6],
} : { show:false }
const lblLayout = { hideOverlap:false, moveOverlap:'shiftY', minMargin:3 }
const axQtyFmt = (v:any)=> fmt0(v)
const axMoneyFmt = (v:any)=> fmt0(v)

const tlOption = computed(()=>{
  const d = tlData.value; if(!d.length) return {}
  const cats = d.map((r:any)=> r.odate)
  return {
    tooltip:{trigger:'axis', valueFormatter:(v:any)=> fmt0(v)},
    legend:{data:['Клики','Корзины','Заказы','Расходы'], bottom:0, itemGap:16, padding:[10,0,0,0], textStyle:{fontSize:11}},
    grid:{left:50, right:50, top:40, bottom:90, containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:'#333'}},
    yAxis:[
      {type:'value', name:'Кол-во (шт)', min:0, axisLabel:{color:'#5067de', fontSize:11, formatter:axQtyFmt}, splitLine:{show:false}},
      {type:'value', name:'Сумма (₽)', min:0, opposite:true, axisLabel:{color:'#f96666', fontSize:11, formatter:axMoneyFmt}},
    ],
    series:[
      {name:'Клики', type:'line', smooth:true, data:d.map((r:any)=> r.clicks), lineStyle:{width:2}, itemStyle:{color:'#f965cf'}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl('#f965cf', showTl.value), labelLayout:lblLayout},
      {name:'Корзины', type:'line', smooth:true, data:d.map((r:any)=> r.atbs), lineStyle:{width:2}, itemStyle:{color:'#660ec8'}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl('#660ec8', showTl.value), labelLayout:lblLayout},
      {name:'Заказы', type:'line', data:d.map((r:any)=> r.orders), lineStyle:{width:2}, itemStyle:{color:'#5067de'}, yAxisIndex:0, z:11, symbol:'circle', symbolSize:6, label:lbl('#5067de', showTl.value), labelLayout:lblLayout},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> Math.round(Number(r.sum)||0)), lineStyle:{width:3}, itemStyle:{color:'#f96666'}, yAxisIndex:1, z:12, symbol:'circle', symbolSize:6, label:lbl('#f96666', showTl.value), labelLayout:lblLayout},
    ]
  }
})
const appOption = computed(()=>{
  const d = appData.value; if(!d.length) return {}
  const cats = d.map((r:any)=> r.date)
  // _appchart.php:137-141 — заказы/корзины на левой оси, показы на правой; агрегация sum
  const groups = [
    {label:'Заказы', key:'orders', color:'#660ec8', axis:0},
    {label:'Кор-ны', key:'atbs', color:'#f96666', axis:0},
    {label:'Показы', key:'views', color:'#f965cf', axis:1},
  ]
  const series:any[] = []
  const types=[1,32,64]
  const appNames:any = {1:'💻',32:'🤖',64:'🍎'}
  for(const g of groups){
    for(let i=0;i<types.length;i++){
      const t=types[i]
      series.push({name: appNames[t]+' '+g.label, type:'bar', stack:g.key, yAxisIndex:g.axis,
        data:d.map((r:any)=> r[`${g.key}_${t}`]||0),
        // 3 кластера на категорию (заказы/корзины/показы): ширина кластера ~18% полосы,
        // иначе 3×60% > 100% и колонки налезают друг на друга
        itemStyle:{color: g.color, opacity: 0.6 + i*0.2}, barWidth:'18%', barGap:'30%', barCategoryGap:'20%',
        label: showApp.value ? {show:true, position:'inside', fontSize:10, color:'#fff', formatter:(p:any)=> p.value>=2 ? fmt0(p.value) : ''} : {show:false},
        tooltip:{valueFormatter:(v:any)=> fmt0(v)}})
    }
  }
  return {tooltip:{trigger:'axis', valueFormatter:(v:any)=> fmt0(v)},
    legend:{data:series.map(s=>s.name), bottom:0, itemGap:8, padding:[10,0,0,0], textStyle:{fontSize:10}},
    grid:{left:50, right:50, top:40, bottom:90, containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:'#333'}},
    yAxis:[
      {type:'value', name:'Заказы/Корзины', min:0, axisLabel:{color:'#660ec8', fontSize:11, formatter:axQtyFmt}, splitLine:{show:false}},
      {type:'value', name:'Показы', min:0, opposite:true, axisLabel:{color:'#f965cf', fontSize:11, formatter:axQtyFmt}},
    ], series}
})
const cpmOption = computed(()=>{
  const d=cpmData.value; if(!d.length) return {}
  const cats=d.map((r:any)=> r.odate)
  return {
    tooltip:{trigger:'axis', valueFormatter:(v:any)=> fmt2(v)},
    legend:{data:['CPM, ₽','CPO, ₽','Расходы'], bottom:0, itemGap:16, padding:[10,0,0,0], textStyle:{fontSize:11}},
    grid:{left:50, right:50, top:40, bottom:90, containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:'#333'}},
    yAxis:[
      {type:'value', name:'Показатель (₽)', min:0, axisLabel:{color:'#2196f3', fontSize:11, formatter:(v:any)=> fmt2(v)}, splitLine:{show:false}},
      {type:'value', name:'Сумма (₽)', min:0, opposite:true, axisLabel:{color:'#f44336', fontSize:11, formatter:axMoneyFmt}},
    ],
    series:[
      {name:'CPM, ₽', type:'line', smooth:true, data:d.map((r:any)=> +(Number(r.CPM)||0).toFixed(2)), itemStyle:{color:'#2196f3'}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl('#2196f3', showCpm.value), labelLayout:lblLayout},
      {name:'CPO, ₽', type:'line', smooth:true, data:d.map((r:any)=> +(Number(r.CPO)||0).toFixed(2)), itemStyle:{color:'#c767dc'}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl('#c767dc', showCpm.value), labelLayout:lblLayout},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> Math.round(Number(r.sum)||0)), itemStyle:{color:'#f44336'}, lineStyle:{width:3}, yAxisIndex:1, z:11, symbol:'circle', symbolSize:6, label:lbl('#f44336', showCpm.value), labelLayout:lblLayout},
    ]
  }
})
const ctrOption = computed(()=>{
  const d=ctrData.value; if(!d.length) return {}
  const cats=d.map((r:any)=> r.odate)
  return {
    tooltip:{trigger:'axis', valueFormatter:(v:any)=> fmt2(v)},
    legend:{data:['CTR, %','CR, %','Расходы'], bottom:0, itemGap:16, padding:[10,0,0,0], textStyle:{fontSize:11}},
    grid:{left:50, right:50, top:40, bottom:90, containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:'#333'}},
    yAxis:[
      {type:'value', name:'Показатель (%)', min:0, axisLabel:{color:'#660ec8', fontSize:11, formatter:(v:any)=> fmt2(v)}, splitLine:{show:false}},
      {type:'value', name:'Сумма (₽)', min:0, opposite:true, axisLabel:{color:'#f44336', fontSize:11, formatter:axMoneyFmt}},
    ],
    series:[
      {name:'CTR, %', type:'line', smooth:true, data:d.map((r:any)=> +(Number(r.CTR)||0).toFixed(2)), itemStyle:{color:'#9c27b0'}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl('#9c27b0', showCtr.value), labelLayout:lblLayout},
      {name:'CR, %', type:'line', smooth:true, data:d.map((r:any)=> +(Number(r.CR)||0).toFixed(2)), itemStyle:{color:'#660ec8'}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl('#660ec8', showCtr.value), labelLayout:lblLayout},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> Math.round(Number(r.sum)||0)), itemStyle:{color:'#f44336'}, lineStyle:{width:3}, yAxisIndex:1, z:11, symbol:'circle', symbolSize:6, label:lbl('#f44336', showCtr.value), labelLayout:lblLayout},
    ]
  }
})
</script>
