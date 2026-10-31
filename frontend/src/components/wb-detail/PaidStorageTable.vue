<template>
  <div class="tbl-card tbl-card--compact mt-3">
    <div class="card__hd">Платное хранение ({{ dateFrom }} — {{ dateTo }})</div>
    <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
    <template v-else>
      <div class="expandable-container tbl-wrap" :class="{'is-expanded': expanded}" :style="{maxHeight: expanded ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}" ref="wrapRef">
        <table ref="tbl" class="tbl" style="width:100%; table-layout:auto">
          <thead><tr>
            <th class="t-left">Тип расчёта</th>
            <th class="t-center">Дней</th>
            <th class="t-center">Ед×дни</th>
            <th class="t-center">Объём</th>
            <th class="t-center">Сумма ₽</th>
            <th class="t-center">₽/ед.</th>
          </tr>
          <tr v-if="rows.length" class="tbl__total tbl__total--top"><td></td><td></td><td>{{ fmt0(rows.reduce((a,b)=>a+(Number(b.total_units)||0),0)) }}</td><td></td><td>{{ fmt2(rows.reduce((a,b)=>a+(Number(b.total_price)||0),0)) }}</td><td></td></tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length"><td colspan="6" class="text-center text-muted">Нет данных за период</td></tr>
            <tr v-for="r in rows" :key="r.calcType">
              <td class="t-left">{{ r.calcType }}</td>
              <td>{{ r.days_cnt }}</td>
              <td>{{ fmt0(r.total_units) }}</td>
              <td>{{ fmt2(r.avg_volume) }}</td>
              <td>{{ fmt2(r.total_price) }}</td>
              <td>{{ fmt2(r.price_per_unit) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="rows.length" class="expand-btn-wrapper" style="text-align:center; margin:10px 0 8px">
        <button class="btn btn--outline btn-sm page-wb-detail__more-btn" @click="expanded=!expanded">{{ expanded ? 'Свернуть' : 'Увидеть больше' }}</button>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { api } from '@/api/client'
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
    const { data:d } = await api.get(`/api/wb/detail/paid-storage?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`)
    rows.value=d
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
.expandable-container:not(.is-expanded)::after{content:""; position:absolute; bottom:0; left:0; width:100%; height:50px; background:linear-gradient(transparent, var(--surface)); pointer-events:none}
</style>
