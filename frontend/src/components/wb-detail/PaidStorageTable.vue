<template>
  <div class="card grid_wbstat mt-3" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
    <div class="card-header text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; font-size:13px; line-height:1.5; padding:4px 8px">Платное хранение ({{ dateFrom }} — {{ dateTo }})</div>
    <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
    <template v-else>
      <div class="expandable-container" :class="{'is-expanded': expanded}" :style="{maxHeight: expanded ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}" style="overflow-x:auto" ref="wrapRef">
        <table ref="tbl" class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:12px; width:100%; table-layout:auto">
          <thead><tr>
            <th style="text-align:left; padding:4px">Тип расчёта</th>
            <th style="text-align:center; width:60px; white-space:nowrap; padding:4px">Дней</th>
            <th style="text-align:center; width:90px; white-space:nowrap; padding:4px">Ед×дни</th>
            <th style="text-align:center; width:70px; white-space:nowrap; padding:4px">Объём</th>
            <th style="text-align:center; width:90px; white-space:nowrap; padding:4px">Сумма ₽</th>
            <th style="text-align:center; width:80px; white-space:nowrap; padding:4px">₽/ед.</th>
          </tr>
          <tr v-if="rows.length" class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px"><td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td><td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td><td class="text-end" style="color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(rows.reduce((a,b)=>a+(Number(b.total_units)||0),0)) }}</td><td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td><td class="text-end" style="color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(rows.reduce((a,b)=>a+(Number(b.total_price)||0),0)) }}</td><td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td></tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length"><td colspan="6" class="text-center text-muted">Нет данных за период</td></tr>
            <tr v-for="r in rows" :key="r.calcType">
              <td style="text-align:left; font-size:12px; white-space:nowrap; padding:4px">{{ r.calcType }}</td>
              <td style="text-align:right; padding:4px">{{ r.days_cnt }}</td>
              <td style="text-align:right; padding:4px">{{ fmt0(r.total_units) }}</td>
              <td style="text-align:right; padding:4px">{{ fmt2(r.avg_volume) }}</td>
              <td style="text-align:right; padding:4px">{{ fmt2(r.total_price) }}</td>
              <td style="text-align:right; padding:4px">{{ fmt2(r.price_per_unit) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="rows.length" class="expand-btn-wrapper" style="text-align:center; margin:10px 0 8px">
        <button class="btn btn-outline-primary btn-sm" style="font-size:12px; padding:4px 16px; border-radius:6px" @click="expanded=!expanded">{{ expanded ? 'Свернуть' : 'Увидеть больше' }}</button>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
const props=defineProps<{ nmId:string|number, dateFrom:string, dateTo:string }>()
const rows=ref<any[]>([])
const loading=ref(false)
const expanded=ref(false)
const tbl=ref<HTMLTableElement|null>(null)
const fmt0=(v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2=(v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const fetchData=async()=>{
  if(!props.nmId) return
  loading.value=true
  try{
    const r=await fetch(`/api/wb/detail/paid-storage?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`)
    rows.value=await r.json()
  }catch{ rows.value=[] } finally{ loading.value=false; nextTick(enableResize) }
}
const enableResize=()=>{
  const t=tbl.value; if(!t) return
  t.querySelectorAll('th').forEach((th:Element)=>{
    const el=th as HTMLTableCellElement
    if(el.querySelector('.col-resizer')) return
    el.style.position='relative'
    const c=document.createElement('div')
    c.className='col-resizer'
    c.style.cssText='position:absolute;top:0;right:0;width:6px;height:100%;cursor:col-resize;user-select:none'
    el.appendChild(c)
    let sx=0, sw=0
    const onMove=(e:MouseEvent)=>{ const w=Math.max(40, sw+e.clientX-sx); el.style.width=w+'px'; (el.style as any).minWidth=w+'px'; t.style.width='100%'; t.style.tableLayout='fixed' }
    const onUp=()=>{ document.removeEventListener('mousemove',onMove); document.removeEventListener('mouseup',onUp); document.body.style.cursor='' }
    c.addEventListener('mousedown',(e:MouseEvent)=>{ sx=e.clientX; sw=el.offsetWidth; document.body.style.cursor='col-resize'; document.addEventListener('mousemove',onMove); document.addEventListener('mouseup',onUp); e.preventDefault() })
  })
  t.style.width='100%'
}
onMounted(fetchData)
watch(()=>[props.nmId, props.dateFrom, props.dateTo], fetchData)
</script>
<style scoped>
.expandable-container:not(.is-expanded)::after{content:""; position:absolute; bottom:0; left:0; width:100%; height:50px; background:linear-gradient(transparent, white); pointer-events:none}
/* Bootstrap 5 table-striped красит ячейки inset box-shadow поверх фона tr — гасим его, фон задаем самим td */
.kv-totals > td{background-color:#f2e7c3 !important; box-shadow:none !important}
</style>
