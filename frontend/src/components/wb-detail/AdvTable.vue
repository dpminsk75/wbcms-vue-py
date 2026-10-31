<template>
  <div class="tbl-card tbl-card--compact mt-3">
    <div class="card__hd">Реклама ({{ dateFrom }} — {{ dateTo }})</div>
    <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
    <div v-else-if="!rows.length" class="alert alert-info m-3">Нет рекламы за период.</div>
    <div v-else class="tbl-wrap" ref="wrapRef">
      <table ref="tbl" class="tbl" style="width:100%; table-layout:auto">
        <thead><tr>
          <th>Компания</th>
          <th class="t-center">Ст</th>
          <th class="t-center">Заказы</th>
          <th class="t-center">Σ зак, ₽</th>
          <th class="t-center">Затраты, ₽</th>
          <th class="t-center">CPO ₽</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.campaign_id">
            <td class="t-left">
              <span :title="Number(r.adv)===1?'Реклама':'Органика'" style="margin-right:6px"><i :class="Number(r.adv)===1?'bi bi-arrow-right-circle t-neg':'bi bi-arrow-repeat text-muted'"></i></span><a :href="'/wb-adv-report?id='+r.campaign_id+'&date_from='+dateFrom+'&date_to='+dateTo" target="_blank" style="text-decoration:none; font-weight:600">{{ r.name }}</a>
            </td>
            <td class="t-center"><span :style="statusStyle(r.status)">{{ statusLabel(r.status) }}</span></td>
            <td>{{ fmt0(r.orders) }}</td>
            <td>{{ fmt2(r.sum_price) }}</td>
            <td>{{ fmt2(r.sum) }}</td>
            <td>{{ r.orders? fmt2(Number(r.sum)/Number(r.orders)) : '—' }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="tbl__total">
            <td></td>
            <td></td>
            <td>{{ fmt0(rows.reduce((a,b)=>a+(Number(b.orders)||0),0)) }}</td>
            <td>{{ fmt2(rows.reduce((a,b)=>a+(Number(b.sum_price)||0),0)) }}</td>
            <td>{{ fmt2(rows.reduce((a,b)=>a+(Number(b.sum)||0),0)) }}</td>
            <td></td>
          </tr>
        </tfoot>
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
// пастельные бейджи статусов — цвета темы
const statusStyle=(s:any)=> {
  const n=String(Number(s))
  const m: Record<string,string> = {
    '9': 'background:var(--good-tint); color:var(--good-deep)',
    '7': 'background:var(--brand-tint); color:var(--brand-deep)',
    '11': 'background:var(--warn-tint); color:var(--warn-deep)',
    '4': 'background:var(--info-tint); color:var(--info-deep)',
    '8': 'background:var(--bad-tint); color:var(--bad-deep)',
    '-1': 'background:var(--surface-3); color:var(--ink-soft)'
  }
  return `display:inline-block; padding:2px 6px; border-radius:6px; font-size:11px; font-weight:400; white-space:nowrap; ${m[n] ?? 'background:var(--surface-3); color:var(--ink-soft)'}`
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
