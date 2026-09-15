<template>
  <!-- Сводные показатели per nm_id — ShortStatsProvider + showPageSummary tfoot снизу (index.php:531-555) -->
  <div class="row mb-3 custom-compact-grid">
    <div class="col-12">
      <div class="card wb-grid-card">
        <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header wb-card-header--sm">
          <span>Сводные показатели</span>
          <button class="btn btn-sm btn-light wb-excel-btn--sm" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
        </div>
        <div class="wb-table-wrap" ref="wrapRef"><table ref="tbl" class="table table-bordered table-striped table-hover kv-grid-table mb-0 adv-grid">
          <thead><tr>
            <th style="width:90px; text-align:center">Арт WB</th>
            <th style="min-width:420px; text-align:center">Товар / Артикул</th>
            <th style="width:100px; text-align:center">Показы</th><th style="width:100px; text-align:center">Клики</th><th style="width:100px; text-align:center">Корзины</th><th style="width:100px; text-align:center">Заказы</th><th style="width:100px; text-align:center">Отмена</th>
            <th style="width:100px; text-align:center">CTR, %</th><th style="width:100px; text-align:center">CR, %</th><th style="width:100px; text-align:center">Затраты, ₽</th>
            <th style="width:100px; text-align:center">CPM, ₽</th><th style="width:100px; text-align:center">CPC, ₽</th><th style="width:100px; text-align:center">CPO, ₽</th>
          </tr></thead>
          <tbody><tr v-for="r in rows" :key="r.nm_id">
            <td style="text-align:center; padding:4px"><a :href="'/wb/detail?nm_id='+r.nm_id" target="_blank" class="adv-link">{{ r.nm_id }}</a></td>
            <td style="padding:4px"><div style="font-weight:700; font-size:13px; color:#2c3e50;">{{ r.title || '—' }}</div><div style="color:#666; font-size:11px;">Артикул: <b>{{ r.vendorCode }}</b></div></td>
            <td style="text-align:right; padding:4px">{{ fmt0(r.views) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.clicks) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.atbs) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.orders) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.canceled) }}</td>
            <td style="text-align:right; padding:4px">{{ r.views>0 ? fmt2(r.clicks/r.views*100) : '' }}</td><td style="text-align:right; padding:4px">{{ r.clicks>0 ? fmt2(r.atbs/r.clicks*100) : '' }}</td>
            <td style="text-align:right; padding:4px">{{ fmt2(r.sum) }}</td>
            <td style="text-align:right; padding:4px">{{ r.views>0 ? fmt2(r.sum/r.views*1000) : '' }}</td><td style="text-align:right; padding:4px">{{ r.clicks>0 ? fmt2(r.sum/r.clicks) : '' }}</td><td style="text-align:right; padding:4px">{{ r.orders>0 ? fmt2(r.sum/r.orders) : '' }}</td>
          </tr></tbody>
          <!-- Итоги Kartik pageSummary → Vue: слова «Итого» нет, первые ячейки пустые -->
          <tfoot v-if="rows.length"><tr class="kv-totals">
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
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
const props = defineProps<{ rows: any[], campaignId: string|number, dateFrom: string, dateTo: string }>()
const tbl = ref<HTMLTableElement|null>(null)
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const sum = (k:string)=> props.rows.reduce((a,r)=> a + (Number(r[k])||0),0)
// Итоги 1в1 index.php:253-271: CTR=clicks/views, CR=atbs/clicks, CPM=sum/views*1000, CPC=sum/clicks, CPO=sum/(orders-canceled)
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
    'Арт WB': r.nm_id, 'Товар': r.title, 'Артикул': r.vendorCode,
    'Показы': r.views, 'Клики': r.clicks, 'Корзины': r.atbs, 'Заказы': r.orders, 'Отмена': r.canceled,
    'CTR %': r.views? +(r.clicks/r.views*100).toFixed(2):'', 'CR %': r.clicks? +(r.atbs/r.clicks*100).toFixed(2):'',
    'Затраты': r.sum, 'CPM': r.views? +(r.sum/r.views*1000).toFixed(2):'', 'CPC': r.clicks? +(r.sum/r.clicks).toFixed(2):'', 'CPO': r.orders? +(r.sum/r.orders).toFixed(2):'',
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{wch:10},{wch:40},{wch:14},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:12},{wch:10},{wch:10},{wch:10}]
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Сводные'); XLSX.writeFile(wb, `adv-short_${props.campaignId}_${props.dateFrom}_${props.dateTo}.xlsx`)
}
</script>
