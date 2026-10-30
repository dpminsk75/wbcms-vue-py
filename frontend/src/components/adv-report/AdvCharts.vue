<template>
  <div>
    <div class="row mb-3">
      <div :class="expanded===0 ? 'col-12' : 'col-md-7'" v-show="expanded===null || expanded===0" class="div-chart">
        <div class="wb-panel">
          <div class="card__hd">
            <span>Расходы и показатели компании</span>
            <span class="spacer"></span>
            <div class="ch-seg">
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': tlUnit==='day' }" @click="tlUnit='day'">D</button>
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': tlUnit==='week' }" @click="tlUnit='week'">W</button>
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': tlUnit==='month' }" @click="tlUnit='month'">M</button>
            </div>
            <button type="button" class="ch-icon-btn" @click="showTl=!showTl" :title="showTl ? 'Скрыть значения' : 'Показать значения'">
              <i :class="showTl ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
            </button>
            <button type="button" class="ch-icon-btn" @click="toggleExpand(0)" :title="expanded===0 ? 'Свернуть' : 'На всю строку'">
              <i :class="expanded===0 ? 'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen'"></i>
            </button>
          </div>
          <div class="wb-panel__bd"><VChart :option="tlOption" autoresize style="height:400px" /></div>
        </div>
      </div>
      <div :class="expanded===1 ? 'col-12' : 'col-md-5'" v-if="appChart.length" v-show="expanded===null || expanded===1" class="div-chart">
        <div class="wb-panel">
          <div class="card__hd">
            <span>Устр-ва: заказы, корзины, показы</span>
            <span class="spacer"></span>
            <div class="ch-seg">
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': appUnit==='day' }" @click="appUnit='day'">D</button>
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': appUnit==='week' }" @click="appUnit='week'">W</button>
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': appUnit==='month' }" @click="appUnit='month'">M</button>
            </div>
            <button type="button" class="ch-icon-btn" @click="showApp=!showApp" :title="showApp ? 'Скрыть значения' : 'Показать значения'">
              <i :class="showApp ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
            </button>
            <button type="button" class="ch-icon-btn" @click="toggleExpand(1)" :title="expanded===1 ? 'Свернуть' : 'На всю строку'">
              <i :class="expanded===1 ? 'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen'"></i>
            </button>
          </div>
          <div class="wb-panel__bd"><VChart :option="appOption" autoresize style="height:400px" /></div>
        </div>
      </div>
    </div>
    <div class="row mb-3">
      <div :class="expanded===2 ? 'col-12' : 'col-md-6'" v-show="expanded===null || expanded===2" class="div-chart">
        <div class="wb-panel">
          <div class="card__hd">
            <span>Показатели: CPM, CPO</span>
            <span class="spacer"></span>
            <div class="ch-seg">
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': cpmUnit==='day' }" @click="cpmUnit='day'">D</button>
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': cpmUnit==='week' }" @click="cpmUnit='week'">W</button>
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': cpmUnit==='month' }" @click="cpmUnit='month'">M</button>
            </div>
            <button type="button" class="ch-icon-btn" @click="showCpm=!showCpm" :title="showCpm ? 'Скрыть значения' : 'Показать значения'">
              <i :class="showCpm ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
            </button>
            <button type="button" class="ch-icon-btn" @click="toggleExpand(2)" :title="expanded===2 ? 'Свернуть' : 'На всю строку'">
              <i :class="expanded===2 ? 'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen'"></i>
            </button>
          </div>
          <div class="wb-panel__bd"><VChart :option="cpmOption" autoresize style="height:400px" /></div>
        </div>
      </div>
      <div :class="expanded===3 ? 'col-12' : 'col-md-6'" v-show="expanded===null || expanded===3" class="div-chart">
        <div class="wb-panel">
          <div class="card__hd">
            <span>Показатели: CTR, CR</span>
            <span class="spacer"></span>
            <div class="ch-seg">
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': ctrUnit==='day' }" @click="ctrUnit='day'">D</button>
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': ctrUnit==='week' }" @click="ctrUnit='week'">W</button>
              <button type="button" class="ch-seg__btn" :class="{ 'is-on': ctrUnit==='month' }" @click="ctrUnit='month'">M</button>
            </div>
            <button type="button" class="ch-icon-btn" @click="showCtr=!showCtr" :title="showCtr ? 'Скрыть значения' : 'Показать значения'">
              <i :class="showCtr ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
            </button>
            <button type="button" class="ch-icon-btn" @click="toggleExpand(3)" :title="expanded===3 ? 'Свернуть' : 'На всю строку'">
              <i :class="expanded===3 ? 'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen'"></i>
            </button>
          </div>
          <div class="wb-panel__bd"><VChart :option="ctrOption" autoresize style="height:400px" /></div>
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
import { useNumFmt } from '@/composables/useNumFmt'
use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DatasetComponent, CanvasRenderer])

// Данные 1в1 WbAdvReportController: ChartStats (odate/views/clicks/atbs/orders/sum/CPM/CPC/CPO/CTR/CR)
// + ChartAppStats flat(date, clicks|orders|atbs|views|sum_price _1|_32|_64). Группировка W/M суммой,
// производные CPM/CPC/CPO/CTR/CR пересчетом из сумм (точнее чем AmCharts average).
const props = defineProps<{ chart: any[], appChart: any[] }>()

/* Палитра серий — фиксированная (не зависит от акцента темы, как решили для /wb/detail).
   Вариант «ПВ — современные» (выбран заказчиком 2026-10-29):
   синий #2563EB · розовый #DB2777 · зелёный #059669 · оранжевый #EA580C. */
const P = {
  clicks: '#2563EB',
  atbs:   '#059669',
  orders: '#DB2777',
  sum:    '#EA580C',
  views:  '#2563EB',
  cpm:    '#2563EB',
  cpo:    '#059669',
  ctr:    '#DB2777',
  cr:     '#2563EB',
}

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

/* Разворот графика на всю строку — как на /wb/detail (DetailCharts.vue):
   карточка растягивается (col-12), соседняя в этой строке скрывается. */
const expanded = ref<number|null>(null)
const toggleExpand = (i:number)=>{ expanded.value = expanded.value===i ? null : i }

const { fmt0, fmt2 } = useNumFmt()

/** Цвета текста осей и легенды — из токенов темы. */
const cssVar = (n:string)=> (typeof document!=='undefined' ? getComputedStyle(document.documentElement).getPropertyValue(n).trim() : '')

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
    b.views += Number(r.views)||0; b.clicks += Number(r.clicks)||0; b.atbs += Number(r.atbs)||0; b.orders += Number(r.orders)||0; b.sum += Number(r.sum)||0; b.sum_price += Number(r.sum_price||r.sum)||0; b.canceled += Number(r.canceled)||0
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
// x rotate 30 interval 0 margin 16 11px, y 11px в цвет серии + ru-RU формат,
// подписи серий с белым фоном/рамкой (иначе голые цифры наезжают друг на друга).
const lbl = (color:string, show:boolean, money=false)=> show ? {
  show:true, position:'top', distance:10, fontSize:11, fontWeight:700, color,
  backgroundColor:'#ffffff', borderColor:color, borderWidth:1.5, borderRadius:6, padding:[3,6],
  formatter: money ? (p:any)=> fmt0(p.value) + ' ₽' : undefined,
} : { show:false }
const lblLayout = { hideOverlap:false, moveOverlap:'shiftY', minMargin:3 }
const axQtyFmt = (v:any)=> fmt0(v)
const axMoneyFmt = (v:any)=> fmt0(v)

/** Тултип: у денежных серий добавляем знак рубля. */
const moneyNames = ['Расходы','Сумма','Расход']
const tooltipRows = (params:any)=>{
  const arr = Array.isArray(params) ? params : [params]
  if(!arr.length) return ''
  const head = arr[0]?.axisValueLabel ?? arr[0]?.name ?? ''
  const body = arr.map((p:any)=>{
    const val = (p.value === null || p.value === undefined) ? '—' : fmt0(p.value)
    const money = moneyNames.includes(String(p.seriesName))
    return `${p.marker || ''}${p.seriesName}: ${money ? val + ' ₽' : val}`
  }).join('<br/>')
  return head ? `${head}<br/>${body}` : body
}
/** Запас по оси: линия расхода не должна накладываться на «клики» — увеличиваем максимум оси. */
const axisMax = (k = 1.3)=> (v:any)=> Math.ceil((Number(v?.max) || 0) * k)

const tlOption = computed(()=>{
  const d = tlData.value; if(!d.length) return {}
  const cats = d.map((r:any)=> r.odate)
  const axis = cssVar('--ink-muted') || '#969CA1'
  return {
    tooltip:{trigger:'axis', formatter: tooltipRows},
    legend:{data:['Клики','Корзины','Заказы','Расходы'], bottom:20, itemGap:16, padding:[0,0,0,0], textStyle:{fontSize:11, color: cssVar('--ink') || '#111315'}},
    grid:{left:50, right:50, top:40, bottom:60, containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:axis}},
    yAxis:[
      {type:'value', name:'Кол-во (шт)', min:0, axisLabel:{color:axis, fontSize:11, formatter:axQtyFmt}, nameTextStyle:{color:axis}, splitLine:{show:false}},
      {type:'value', name:'Сумма (₽)', min:0, opposite:true, max: axisMax(1.3), axisLabel:{color:axis, fontSize:11, formatter:axMoneyFmt}, nameTextStyle:{color:axis}},
    ],
    series:[
      {name:'Клики', type:'line', smooth:true, data:d.map((r:any)=> r.clicks), lineStyle:{width:2}, itemStyle:{color:P.clicks}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl(P.clicks, showTl.value), labelLayout:lblLayout},
      {name:'Корзины', type:'line', smooth:true, data:d.map((r:any)=> r.atbs), lineStyle:{width:2}, itemStyle:{color:P.atbs}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl(P.atbs, showTl.value), labelLayout:lblLayout},
      {name:'Заказы', type:'line', data:d.map((r:any)=> r.orders), lineStyle:{width:2}, itemStyle:{color:P.orders}, yAxisIndex:0, z:11, symbol:'circle', symbolSize:6, label:lbl(P.orders, showTl.value), labelLayout:lblLayout},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> Math.round(Number(r.sum)||0)), lineStyle:{width:3}, itemStyle:{color:P.sum}, yAxisIndex:1, z:12, symbol:'circle', symbolSize:6, label:lbl(P.sum, showTl.value, true), labelLayout:lblLayout},
    ]
  }
})
const appOption = computed(()=>{
  const d = appData.value; if(!d.length) return {}
  const cats = d.map((r:any)=> r.date)
  const axis = cssVar('--ink-muted') || '#969CA1'
  // _appchart.php:137-141 — заказы/корзины на левой оси, показы на правой; агрегация sum
  const groups = [
    {label:'Заказы', key:'orders', color:P.orders, axis:0},
    {label:'Кор-ны', key:'atbs', color:P.atbs, axis:0},
    {label:'Показы', key:'views', color:P.views, axis:1},
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
    legend:{data:series.map(s=>s.name), bottom:15, itemGap:8, padding:[0,0,0,0], textStyle:{fontSize:10, color: cssVar('--ink') || '#111315'}, width:320},
    grid:{left:50, right:50, top:40, bottom:85, containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:axis}},
    yAxis:[
      {type:'value', name:'Заказы/Корзины', min:0, axisLabel:{color:axis, fontSize:11, formatter:axQtyFmt}, nameTextStyle:{color:axis}, splitLine:{show:false}},
      {type:'value', name:'Показы', min:0, opposite:true, max: axisMax(1.3), axisLabel:{color:axis, fontSize:11, formatter:axQtyFmt}, nameTextStyle:{color:axis}},
    ], series}
})
const cpmOption = computed(()=>{
  const d=cpmData.value; if(!d.length) return {}
  const cats=d.map((r:any)=> r.odate)
  const axis = cssVar('--ink-muted') || '#969CA1'
  return {
    tooltip:{trigger:'axis', formatter: tooltipRows},
    legend:{data:['CPM, ₽','CPO, ₽','Расходы'], bottom:20, itemGap:16, padding:[0,0,0,0], textStyle:{fontSize:11, color: cssVar('--ink') || '#111315'}},
    grid:{left:50, right:50, top:40, bottom:60, containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:axis}},
    yAxis:[
      {type:'value', name:'Показатель (₽)', min:0, axisLabel:{color:axis, fontSize:11, formatter:(v:any)=> fmt2(v)}, nameTextStyle:{color:axis}, splitLine:{show:false}},
      {type:'value', name:'Сумма (₽)', min:0, opposite:true, max: axisMax(1.3), axisLabel:{color:axis, fontSize:11, formatter:axMoneyFmt}, nameTextStyle:{color:axis}},
    ],
    series:[
      {name:'CPM, ₽', type:'line', smooth:true, data:d.map((r:any)=> +(Number(r.CPM)||0).toFixed(2)), itemStyle:{color:P.cpm}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl(P.cpm, showCpm.value), labelLayout:lblLayout},
      {name:'CPO, ₽', type:'line', smooth:true, data:d.map((r:any)=> +(Number(r.CPO)||0).toFixed(2)), itemStyle:{color:P.cpo}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl(P.cpo, showCpm.value), labelLayout:lblLayout},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> Math.round(Number(r.sum)||0)), itemStyle:{color:P.sum}, lineStyle:{width:3}, yAxisIndex:1, z:11, symbol:'circle', symbolSize:6, label:lbl(P.sum, showCpm.value, true), labelLayout:lblLayout},
    ]
  }
})
const ctrOption = computed(()=>{
  const d=ctrData.value; if(!d.length) return {}
  const cats=d.map((r:any)=> r.odate)
  const axis = cssVar('--ink-muted') || '#969CA1'
  return {
    tooltip:{trigger:'axis', formatter: tooltipRows},
    legend:{data:['CTR, %','CR, %','Расходы'], bottom:20, itemGap:16, padding:[0,0,0,0], textStyle:{fontSize:11, color: cssVar('--ink') || '#111315'}},
    grid:{left:50, right:50, top:40, bottom:60, containLabel:true},
    xAxis:{type:'category', data:cats, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:axis}},
    yAxis:[
      {type:'value', name:'Показатель (%)', min:0, axisLabel:{color:axis, fontSize:11, formatter:(v:any)=> fmt2(v)}, nameTextStyle:{color:axis}, splitLine:{show:false}},
      {type:'value', name:'Сумма (₽)', min:0, opposite:true, max: axisMax(1.3), axisLabel:{color:axis, fontSize:11, formatter:axMoneyFmt}, nameTextStyle:{color:axis}},
    ],
    series:[
      {name:'CTR, %', type:'line', smooth:true, data:d.map((r:any)=> +(Number(r.CTR)||0).toFixed(2)), itemStyle:{color:P.ctr}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl(P.ctr, showCtr.value), labelLayout:lblLayout},
      {name:'CR, %', type:'line', smooth:true, data:d.map((r:any)=> +(Number(r.CR)||0).toFixed(2)), itemStyle:{color:P.cr}, yAxisIndex:0, z:10, symbol:'circle', symbolSize:6, label:lbl(P.cr, showCtr.value), labelLayout:lblLayout},
      {name:'Расходы', type:'line', smooth:true, data:d.map((r:any)=> Math.round(Number(r.sum)||0)), itemStyle:{color:P.sum}, lineStyle:{width:3}, yAxisIndex:1, z:11, symbol:'circle', symbolSize:6, label:lbl(P.sum, showCtr.value, true), labelLayout:lblLayout},
    ]
  }
})
</script>
<style scoped>
/* сегментный переключатель и кнопка-иконка — как на /wb/detail */
.ch-seg{display:inline-flex;border-radius:6px;overflow:hidden;border:1px solid color-mix(in srgb, currentColor 45%, transparent)}
.ch-seg__btn{border:0;background:transparent;color:inherit;font:inherit;font-size:11px;font-weight:700;padding:3px 9px;cursor:pointer;line-height:1.5}
.ch-seg__btn.is-on{background:#ffffff;color:#111111}
.ch-icon-btn{
  border:1px solid color-mix(in srgb, currentColor 45%, transparent); background:transparent; color:inherit;
  border-radius:6px; width:26px; height:24px; line-height:1; cursor:pointer;
  display:inline-flex; align-items:center; justify-content:center; padding:0;
}
.ch-icon-btn:hover{background:color-mix(in srgb, currentColor 18%, transparent)}
</style>
