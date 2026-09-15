<template>
  <!-- Общая статистика по дням — statsProvider pageSize 50 + showPageSummary (index.php:595-618), итоги снизу -->
  <div class="row custom-compact-grid">
    <div class="col-12"><div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
      <div class="card-header text-white d-flex justify-content-between align-items-center" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; font-size:13px; line-height:1.5; padding:4px 8px;">
        <span>Общая статистика по дням</span>
        <button class="btn btn-sm btn-light" style="font-size:11px; padding:2px 10px; border-radius:6px" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
      </div>
      <div style="overflow-x:auto" ref="wrapRef"><table ref="tbl" class="table table-bordered table-striped table-hover kv-grid-table mb-0 adv-grid" style="font-size:12px; width:100%; table-layout:auto">
        <thead><tr>
          <th style="width:130px; text-align:center">Дата</th><th style="width:90px; text-align:center">Арт WB</th><th style="min-width:420px; text-align:center">Товар / Артикул</th>
          <th style="width:100px; text-align:center">Показы</th><th style="width:100px; text-align:center">Клики</th><th style="width:100px; text-align:center">Корзины</th><th style="width:100px; text-align:center">Заказы</th><th style="width:100px; text-align:center">Отмена</th>
          <th style="width:100px; text-align:center">CTR, %</th><th style="width:100px; text-align:center">CR, %</th><th style="width:100px; text-align:center">Затраты, ₽</th><th style="width:100px; text-align:center">CPM, ₽</th><th style="width:100px; text-align:center">CPC, ₽</th><th style="width:100px; text-align:center">CPO, ₽</th>
        </tr></thead>
        <tbody><tr v-for="r in rows" :key="r.date + '-' + r.nm_id">
          <td style="text-align:center; white-space:nowrap; padding:4px">{{ fmtDate(r.date) }}</td><td style="text-align:center; padding:4px"><a :href="'/wb/detail?nm_id='+r.nm_id" target="_blank" class="adv-link">{{ r.nm_id }}</a></td>
          <td style="padding:4px"><div style="font-weight:700;">{{ r.title }}</div><div style="color:#666; font-size:11px;">Артикул: <b>{{ r.vendorCode }}</b></div></td>
          <td style="text-align:right; padding:4px">{{ fmt0(r.views) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.clicks) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.atbs) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.orders) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.canceled) }}</td>
          <td style="text-align:right; padding:4px">{{ r.views>0 ? fmt2(r.clicks/r.views*100) : '' }}</td><td style="text-align:right; padding:4px">{{ r.clicks>0 ? fmt2(r.atbs/r.clicks*100) : '' }}</td>
          <td style="text-align:right; padding:4px">{{ fmt2(r.sum) }}</td><td style="text-align:right; padding:4px">{{ r.views>0 ? fmt2(r.sum/r.views*1000) : '' }}</td><td style="text-align:right; padding:4px">{{ r.clicks>0 ? fmt2(r.sum/r.clicks) : '' }}</td><td style="text-align:right; padding:4px">{{ r.orders>0 ? fmt2(r.sum/r.orders) : '' }}</td>
        </tr></tbody>
        <tfoot v-if="rows.length"><tr class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px">
          <td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
          <td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
          <td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('views')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('clicks')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('atbs')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('orders')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('canceled')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ tCtr }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ tCr }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt2(sum('sum')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ tCpm }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ tCpc }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-top:2px solid #8A2BE0">{{ tCpo }}</td>
        </tr></tfoot>
      </table></div>
    </div></div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
const props = defineProps<{ rows: any[], campaignId: string|number, dateFrom: string, dateTo: string }>()
const tbl = ref<HTMLTableElement|null>(null)
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const fmtDate = (v:any)=> v ? new Date(v).toLocaleDateString('ru-RU') : '—'
const sum = (k:string)=> props.rows.reduce((a,r)=> a + (Number(r[k])||0),0)
const tCtr = computed(()=> sum('views')>0 ? fmt2(sum('clicks')/sum('views')*100) : '')
const tCr = computed(()=> sum('clicks')>0 ? fmt2(sum('atbs')/sum('clicks')*100) : '')
const tCpm = computed(()=> sum('views')>0 ? fmt2(sum('sum')/sum('views')*1000) : '')
const tCpc = computed(()=> sum('clicks')>0 ? fmt2(sum('sum')/sum('clicks')) : '')
const tCpo = computed(()=> (sum('orders')-sum('canceled'))>0 ? fmt2(sum('sum')/(sum('orders')-sum('canceled'))) : '')
const enableResize = ()=>{
  const t = tbl.value; if(!t) return
  t.querySelectorAll('th').forEach((th:Element)=>{
    const el = th as HTMLTableCellElement
    if(el.querySelector('.col-resizer')) return
    el.style.position='relative'
    const c=document.createElement('div')
    c.className='col-resizer'
    c.style.cssText='position:absolute;top:0;right:0;width:6px;height:100%;cursor:col-resize;user-select:none;z-index:1'
    el.appendChild(c)
    let sx=0, sw=0
    const onMove=(e:MouseEvent)=>{ const w=Math.max(40, sw+e.clientX-sx); el.style.width=w+'px'; (el.style as any).minWidth=w+'px'; t.style.tableLayout='fixed'; t.style.width='100%' }
    const onUp=()=>{ document.removeEventListener('mousemove',onMove); document.removeEventListener('mouseup',onUp); document.body.style.cursor='' }
    c.addEventListener('mousedown',(e:MouseEvent)=>{ sx=e.clientX; sw=el.offsetWidth; document.body.style.cursor='col-resize'; document.addEventListener('mousemove',onMove); document.addEventListener('mouseup',onUp); e.preventDefault() })
  })
  t.style.width='100%'
}
onMounted(()=> nextTick(enableResize))
watch(()=> props.rows, ()=> nextTick(enableResize))
const exportExcel = async()=>{
  if(!props.rows.length) return
  const XLSX = await import('xlsx')
  const data = props.rows.map((r:any)=>({
    'Дата': r.date, 'Арт WB': r.nm_id, 'Товар': r.title, 'Артикул': r.vendorCode,
    'Показы': r.views, 'Клики': r.clicks, 'Корзины': r.atbs, 'Заказы': r.orders, 'Отмена': r.canceled,
    'CTR %': r.views? +(r.clicks/r.views*100).toFixed(2):'', 'CR %': r.clicks? +(r.atbs/r.clicks*100).toFixed(2):'',
    'Затраты': r.sum, 'CPM': r.views? +(r.sum/r.views*1000).toFixed(2):'', 'CPC': r.clicks? +(r.sum/r.clicks).toFixed(2):'', 'CPO': r.orders? +(r.sum/r.orders).toFixed(2):'',
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{wch:12},{wch:10},{wch:40},{wch:14},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:12},{wch:10},{wch:10},{wch:10}]
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'По дням'); XLSX.writeFile(wb, `adv-daily_${props.campaignId}_${props.dateFrom}_${props.dateTo}.xlsx`)
}
</script>
<style scoped>
.adv-grid th{white-space:normal; overflow-wrap:break-word; font-weight:500; font-size:11px; text-align:center; vertical-align:middle; padding:4px !important;}
.adv-grid td{font-size:12px; vertical-align:middle;}
.adv-link{color:#8A2BE0; font-weight:600; text-decoration:none;}
.kv-totals > td{background-color:#f2e7c3 !important; box-shadow:none !important;}
</style>
