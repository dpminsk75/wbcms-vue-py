<template>
  <div class="row mt-3">
    <div :class="expanded ? 'col-12' : 'col-md-6'">
      <div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden">
        <div class="card-header text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; display:flex; justify-content:space-between; align-items:center">
          <span>Заказы: Цена и Кол-во</span>
          <div class="d-flex align-items-center gap-2">
            <div class="btn-group" style="height:28px">
              <button class="btn btn-sm" :class="period==='day'?'btn-light':'btn-outline-light'" @click="period='day'">D</button>
              <button class="btn btn-sm" :class="period==='week'?'btn-light':'btn-outline-light'" @click="period='week'">W</button>
              <button class="btn btn-sm" :class="period==='month'?'btn-light':'btn-outline-light'" @click="period='month'">M</button>
            </div>
            <button class="btn btn-sm" :class="showValues1?'btn-light':'btn-outline-light'" style="width:32px; height:28px; padding:0" @click="showValues1=!showValues1" :title="showValues1?'Скрыть значения':'Показать значения'">
              <i :class="showValues1?'bi bi-eye':'bi bi-eye-slash'"></i>
            </button>
            <button class="btn btn-sm btn-outline-light" style="width:32px; height:28px; padding:0" @click="expanded=!expanded" :title="expanded?'Свернуть':'На всю строку'">
              <i :class="expanded?'bi bi-fullscreen-exit':'bi bi-arrows-fullscreen'"></i>
            </button>
          </div>
        </div>
        <div ref="timelineRef" style="width:100%; height:480px"></div>
      </div>
    </div>
    <div v-show="!expanded" class="col-md-6">
      <div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden">
        <div class="card-header text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; display:flex; justify-content:space-between; align-items:center">
          <span>Продажи по годам</span>
          <button class="btn btn-sm" :class="showValues2?'btn-light':'btn-outline-light'" style="width:32px; height:28px; padding:0" @click="showValues2=!showValues2" :title="showValues2?'Скрыть значения':'Показать значения'">
            <i :class="showValues2?'bi bi-eye':'bi bi-eye-slash'"></i>
          </button>
        </div>
        <div ref="yearlineRef" style="width:100%; height:480px"></div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'

const props=defineProps<{ nmId:string|number, dateFrom:string, dateTo:string }>()
const timelineRef=ref<HTMLDivElement|null>(null)
const yearlineRef=ref<HTMLDivElement|null>(null)
let chart1:any=null, chart2:any=null
const period=ref<'day'|'week'|'month'>('day')
const showValues1=ref(true)
const showValues2=ref(true)
const expanded=ref(false)
let hasAutoInitForKey=''

const mondayOfWeek=(d:Date)=>{ const day=d.getDay(); const diff=day===0?-6:1-day; const m=new Date(d); m.setDate(d.getDate()+diff); m.setHours(0,0,0,0); return m }
const monthKey=(d:Date)=> `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`

const fetchTimeline=async()=>{
  if(!props.nmId || !timelineRef.value) return
  const r=await fetch(`/api/wb/detail/orders-daily?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`).then(x=>x.json()).catch(()=>[])
  const rows=Array.isArray(r)? r : r.items||[]
  // начальный вид как в оригинале: >50 → month, >14 → week, иначе day
  const key=`${props.nmId}|${props.dateFrom}|${props.dateTo}`
  if(key!==hasAutoInitForKey){
    const initialUnit = rows.length>50 ? 'month' : rows.length>14 ? 'week' : 'day'
    if(period.value!==initialUnit){
      period.value=initialUnit as any
      hasAutoInitForKey=key
      return // watch(period) вызовет повторный fetch с правильным периодом
    }
    hasAutoInitForKey=key
  }
  const sorted=[...rows].reverse() // ASC

  // 3 серии как в _linechart.php: Кол-во (cnt bar #660ec8) + Цена в заказе finished_price #f965cf + Цена со скидкой apwd #2ca02c
  let agg:{odate:string,cnt:number,finished_price:number,apwd:number}[]=[]
  if(period.value==='day'){
    agg=sorted.map((x:any)=>({odate:String(x.odate), cnt:Number(x.cnt)||0, finished_price:Number(x.finished_price)||0, apwd:Number(x.apwd)||0}))
  } else if(period.value==='week'){
    const tmp=new Map<string,{cnt:number, fin:number, pwd:number, c:number}>()
    sorted.forEach((x:any)=>{
      const wk=mondayOfWeek(new Date(x.odate)).toISOString().slice(0,10)
      const cur=tmp.get(wk)||{cnt:0,fin:0,pwd:0,c:0}
      cur.cnt+=Number(x.cnt)||0; cur.fin+=Number(x.finished_price)||0; cur.pwd+=Number(x.apwd)||0; cur.c++; tmp.set(wk,cur)
    })
    agg=[...tmp.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([k,v])=>({odate:k, cnt:v.cnt, finished_price:v.c? v.fin/v.c :0, apwd:v.c? v.pwd/v.c :0}))
  } else {
    const tmp=new Map<string,{cnt:number, fin:number, pwd:number, c:number}>()
    sorted.forEach((x:any)=>{
      const k=monthKey(new Date(x.odate))
      const cur=tmp.get(k)||{cnt:0,fin:0,pwd:0,c:0}
      cur.cnt+=Number(x.cnt)||0; cur.fin+=Number(x.finished_price)||0; cur.pwd+=Number(x.apwd)||0; cur.c++; tmp.set(k,cur)
    })
    agg=[...tmp.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([k,v])=>({odate:k, cnt:v.cnt, finished_price:v.c? v.fin/v.c :0, apwd:v.c? v.pwd/v.c :0}))
  }

  const dates=agg.map(x=> x.odate)
  const cnts=agg.map(x=> x.cnt)
  const finPrice=agg.map(x=> Math.round(x.finished_price))
  const withDisc=agg.map(x=> Math.round(x.apwd))
  if(!chart1) chart1=echarts.init(timelineRef.value)
  chart1.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['Кол-во','Цена в заказе','Цена со скидкой'], bottom:0, top:undefined, itemGap:16, padding:[10,0,0,0]},
    grid:{left:50, right:50, top:40, bottom:90},
    xAxis:{type:'category', data:dates, axisLabel:{rotate:30, interval:0, margin:16, fontSize:11, color:'#333'}},
    yAxis:[
      {type:'value', name:'₽', min:0, axisLabel:{color:'#f965cf', fontSize:11}},
      {type:'value', name:'Кол-во (шт)', min:0, opposite:true, axisLabel:{color:'#660ec8', fontSize:11}}
    ],
    series:[
      {name:'Кол-во', type:'bar', data:cnts, yAxisIndex:1, z:1, zlevel:1, itemStyle:{color:'#660ec8', opacity:0.35, borderColor:'#660ec8', borderWidth:1}, barWidth:'55%', label:{show:showValues1.value, position:'insideBottom', distance:6, fontSize:12, fontWeight:700, color:'#5a3cc0', opacity:1, backgroundColor:'#ffffff', borderColor:'#660ec8', borderWidth:1.5, borderRadius:6, padding:[3,7]}, labelLayout:{hideOverlap:false, moveOverlap:'shiftY', minMargin:3}},
      {name:'Цена в заказе', type:'line', smooth:true, tension:0.5, data:finPrice, yAxisIndex:0, z:10, zlevel:3, lineStyle:{color:'#f965cf', width:2.5, opacity:1}, itemStyle:{color:'#f965cf', opacity:1, borderColor:'#ffffff', borderWidth:1.5}, symbol:'circle', symbolSize:8, label:{show:showValues1.value, position:'top', distance:10, fontSize:11, fontWeight:700, color:'#f965cf', opacity:1, backgroundColor:'#ffffff', borderColor:'#f965cf', borderWidth:1.5, borderRadius:6, padding:[3,6]}, labelLayout:{hideOverlap:false, moveOverlap:'shiftY', minMargin:3}},
      {name:'Цена со скидкой', type:'line', smooth:true, tension:0.5, data:withDisc, yAxisIndex:0, z:11, zlevel:3, lineStyle:{color:'#2ca02c', width:2.5, opacity:1}, itemStyle:{color:'#2ca02c', opacity:1, borderColor:'#ffffff', borderWidth:1.5}, symbol:'circle', symbolSize:8, label:{show:showValues1.value, position:'top', distance:10, fontSize:11, fontWeight:700, color:'#2ca02c', opacity:1, backgroundColor:'#ffffff', borderColor:'#2ca02c', borderWidth:1.5, borderRadius:6, padding:[3,6]}, labelLayout:{hideOverlap:false, moveOverlap:'shiftY', minMargin:3}}
    ]
  }, true)
  // при расширении — ресайз
  setTimeout(()=> chart1?.resize(), 50)
}

const fetchYearline=async()=>{
  if(!props.nmId || !yearlineRef.value) return
  const r=await fetch(`/api/wb/detail/sales-daily?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`).then(x=>x.json()).catch(()=>[])
  const rows=Array.isArray(r)? r : r.items||[]
  // как am5 DateAxis в detail.php:914 — ось только по месяцам из диапазона дат
  const d1=new Date(props.dateFrom), d2=new Date(props.dateTo)
  let mIdx:number[]=[]
  if(!isNaN(+d1) && !isNaN(+d2) && d1.getFullYear()===d2.getFullYear()){
    for(let m=d1.getMonth(); m<=d2.getMonth(); m++) mIdx.push(m)
  } else {
    mIdx=Array.from({length:12},(_,i)=>i)
  }
  if(!mIdx.length) mIdx=Array.from({length:12},(_,i)=>i)
  // собрать по годам: year -> monthIdx -> cnt (пустые месяцы — null, линия соединяет точки как в am5)
  const byYear:Record<string, Record<number, number>>={}
  rows.forEach((x:any)=>{
    const d=new Date(x.odate); if(isNaN(+d)) return
    const y=String(d.getFullYear()); const m=d.getMonth()
    if(!byYear[y]) byYear[y]={}
    byYear[y][m]=(byYear[y][m]||0)+(Number(x.cnt)||0)
  })
  const allMonths=['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
  const cats=mIdx.map(m=> allMonths[m])
  const colors:Record<string,string>={'2024':'#B287F8','2025':'#f965cf','2026':'#007bff'}
  const series=Object.entries(byYear).map(([y, mm], i)=>{
    const c=colors[y]||['#888','#e377c2','#7f7f7f','#bcbd22'][i%4]
    return {
      name:y, type:'line', smooth:true, connectNulls:true,
      data:mIdx.map(m=> mm[m] ?? null),
      z:10+i, zlevel:3,
      lineStyle:{color:c, width:2, opacity:1},
      itemStyle:{color:c, opacity:1, borderColor:'#ffffff', borderWidth:1.5},
      symbol:'circle', symbolSize:8,
      label:{show:showValues2.value, position:'top', distance:10, fontSize:11, fontWeight:700, color:c, opacity:1, backgroundColor:'#ffffff', borderColor:c, borderWidth:1.5, borderRadius:6, padding:[3,6], formatter:'{c}'},
      labelLayout:{hideOverlap:false, moveOverlap:'shiftY', minMargin:3}
    }
  })
  if(!chart2) chart2=echarts.init(yearlineRef.value)
  chart2.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:Object.keys(byYear), bottom:0, top:undefined, itemGap:16},
    grid:{left:40, right:40, top:50, bottom:50},
    xAxis:{type:'category', data:cats, axisLabel:{margin:12, fontSize:11}},
    yAxis:{type:'value', min:0, max:(v:any)=> Math.ceil((v.max||0)*1.2)},
    series
  }, true)
}

const onResize=()=>{ chart1?.resize(); chart2?.resize() }

watch(()=>[props.nmId, props.dateFrom, props.dateTo], ()=>{ hasAutoInitForKey=''; nextTick(()=>{ fetchTimeline(); fetchYearline() }) })
watch(period, fetchTimeline)
watch(showValues1, fetchTimeline)
watch(showValues2, fetchYearline)
watch(expanded, ()=> nextTick(()=>{ onResize(); fetchTimeline(); fetchYearline() }))
onMounted(()=>{ nextTick(()=>{ fetchTimeline(); fetchYearline() }); window.addEventListener('resize', onResize) })
onBeforeUnmount(()=>{ window.removeEventListener('resize', onResize); chart1?.dispose(); chart2?.dispose() })
</script>
