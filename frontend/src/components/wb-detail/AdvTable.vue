<template>
  <div class="card grid_wbstat mt-3" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
    <div class="card-header text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; font-size:13px; line-height:1.5; padding:4px 8px">Реклама ({{ dateFrom }} — {{ dateTo }})</div>
    <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
    <div v-else-if="!rows.length" class="alert alert-info m-3">Нет рекламы за период.</div>
    <div v-else style="overflow-x:auto" ref="wrapRef">
      <table ref="tbl" class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:12px; width:100%; table-layout:auto">
        <thead><tr>
          <th style="text-align:center; padding:4px">Компания</th>
          <th style="width:80px; text-align:center; white-space:nowrap; padding:4px">Ст</th>
          <th style="text-align:center; white-space:nowrap; padding:4px">Заказы</th>
          <th style="text-align:center; white-space:nowrap; padding:4px">Σ зак, ₽</th>
          <th style="text-align:center; white-space:nowrap; padding:4px">Затраты, ₽</th>
          <th style="text-align:center; white-space:nowrap; padding:4px">CPO ₽</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.campaign_id">
            <td style="white-space:nowrap; padding:4px"><span :title="Number(r.adv)===1?'Реклама':'Органика'" style="margin-right:6px"><i :class="Number(r.adv)===1?'bi bi-arrow-right-circle text-danger':'bi bi-arrow-repeat text-muted'"></i></span><a :href="'/wb-adv-report/index?id='+r.campaign_id" target="_blank" style="text-decoration:none; color:#8A2BE0; font-weight:600">{{ r.name }}</a></td>
            <td style="text-align:center; padding:4px"><span :style="statusStyle(r.status)">{{ statusLabel(r.status) }}</span></td>
            <td style="text-align:right; padding:4px">{{ fmt0(r.orders) }}</td>
            <td style="text-align:right; padding:4px">{{ fmt2(r.sum_price) }}</td>
            <td style="text-align:right; padding:4px">{{ fmt2(r.sum) }}</td>
            <td style="text-align:right; padding:4px">{{ r.orders? fmt2(Number(r.sum)/Number(r.orders)) : '—' }}</td>
          </tr>
        </tbody>
        <tfoot><tr class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px"><td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td><td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td><td class="text-end" style="color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(rows.reduce((a,b)=>a+(Number(b.orders)||0),0)) }}</td><td class="text-end" style="color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt2(rows.reduce((a,b)=>a+(Number(b.sum_price)||0),0)) }}</td><td class="text-end" style="color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt2(rows.reduce((a,b)=>a+(Number(b.sum)||0),0)) }}</td><td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td></tr></tfoot>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { api } from '@/api/client'
const props=defineProps<{ nmId:string|number, dateFrom:string, dateTo:string }>()
const rows=ref<any[]>([])
const loading=ref(false)
const tbl=ref<HTMLTableElement|null>(null)
const fmt0=(v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2=(v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
// как WbCampaign::getStatusMap/renderStatusLabel — текст, не цифра
const statusLabel=(s:any)=> {
  const n=String(Number(s))
  const map: Record<string,string> = {'-1':'Удалена','4':'Готова к запуску','7':'Завершена','8':'Отклонена','9':'Активна','11':'Пауза'}
  return map[n] ?? `Неизвестно (${s})`
}
// пастельные бейджи как .label-success/.label-primary в gridv.css:169-172 (вес 400, не сплошная заливка)
const statusStyle=(s:any)=> {
  const n=String(Number(s))
  const m: Record<string,string> = {
    '9': 'background:#E4F5EF; color:#1E9E7C',
    '7': 'background:#F2E9FB; color:#8A2BE0',
    '11': 'background:#FEF3E2; color:#B45309',
    '4': 'background:#E0F2FE; color:#0284C7',
    '8': 'background:#FBEBEC; color:#E0525C',
    '-1': 'background:#F1F1F4; color:#6E6A80'
  }
  return `display:inline-block; padding:2px 4px; border-radius:6px; font-size:11px; font-weight:400; white-space:nowrap; ${m[n] ?? 'background:#F1F1F4; color:#6E6A80'}`
}
const fetchData=async()=>{
  if(!props.nmId) return
  loading.value=true
  try{
    const { data:d } = await api.get(`/api/wb/detail/adv?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`)
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
/* Bootstrap 5 table-striped красит ячейки inset box-shadow поверх фона tr — гасим его, фон задаем самим td */
.kv-totals > td{background-color:#f2e7c3 !important; box-shadow:none !important}
</style>
