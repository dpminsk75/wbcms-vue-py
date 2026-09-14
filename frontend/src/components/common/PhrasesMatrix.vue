<template>
  <div class="card" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
    <div class="card-header text-white d-flex justify-content-between align-items-center" style="background:#2c7be5; font-weight:700">
      <span><i class="fas fa-chart-line me-2"></i> Динамика позиций</span>
      <button class="btn btn-sm btn-light" style="font-size:12px; padding:4px 12px; border-radius:6px" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
    </div>
    <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
    <div v-else id="grid-scroll" style="max-height:70vh; overflow:auto; position:relative" ref="wrapRef">
      <table ref="tbl" class="table table-bordered table-hover kv-grid-table mb-0" style="font-size:12px; width:auto; min-width:100%; table-layout:auto">
        <thead style="position:sticky; top:0; z-index:10; background:#fff">
          <tr>
            <th class="kv-sticky-column" style="width:300px; min-width:300px; white-space:normal; text-align:left; background:#fff">Поисковый запрос</th>
            <th style="width:80px; text-align:center" title="Средняя частотность за неделю">Ср. част</th>
            <th style="width:90px; text-align:center">Клики</th>
            <th style="width:70px; text-align:center">Заказы</th>
            <th v-for="d in dates" :key="d" class="text-center small" style="min-width:55px; text-align:center">{{ fmtDate(d) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length"><td :colspan="4+dates.length" class="text-center text-muted">Нет данных</td></tr>
          <tr v-for="r in rows" :key="r.phrase" class="clickable-row" style="cursor:pointer" @click="sel=r.phrase" :class="{'selected-row': sel===r.phrase}">
            <td class="kv-sticky-column text-muted" style="width:300px; white-space:normal; background:#fff"><a :href="'https://www.wildberries.ru/catalog/0/search.aspx?search='+encodeURIComponent(r.phrase)" target="_blank">{{ r.phrase }}</a></td>
            <td class="text-secondary" style="background:#fcfcfc; text-align:center">{{ r.avg_freq ?? '' }}</td>
            <td class="text-primary" style="background:#fcfcfc; text-align:center">{{ r.total_clicks ?? '' }}</td>
            <td class="text-primary" style="background:#f8f9ff; text-align:center">{{ r.total_orders ?? '' }}</td>
            <td v-for="d in dates" :key="d" :class="cellCls(r,d)" :title="cellTitle(r,d)" style="text-align:center">{{ cellPos(r,d) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
const props = withDefaults(defineProps<{
  rows: any[]
  dates: string[] // uniqueDates yyyy-mm-dd
  isLoading?: boolean
}>(), { isLoading:false })
const tbl = ref<HTMLTableElement|null>(null)
const wrapRef = ref<HTMLDivElement|null>(null)
const sel = ref('')
const fmtDate = (d:string)=> { try{ const t=new Date(d); return `${String(t.getDate()).padStart(2,'0')}.${String(t.getMonth()+1).padStart(2,'0')}` }catch{ return d } }
const cellData = (r:any,d:string)=> r[d] ?? null
const cellPos = (r:any,d:string)=> cellData(r,d)?.pos ?? ''
const cellTitle = (r:any,d:string)=> { const o=cellData(r,d)?.orders; return o>0?`Заказов: ${o}`:'' }
const cellCls = (r:any,d:string)=>{
  const data=cellData(r,d); if(!data) return ''
  const c:string[]=[]
  const p=data.pos||0, o=data.orders||0
  if(p>0 && p<=10) c.push('pos-top-10')
  else if(p>10 && p<=50) c.push('pos-top-50')
  if(o>0) c.push('has-orders')
  return c.join(' ')
}
watch(()=>props.rows, ()=> nextTick(()=>{}))
onMounted(()=>{})
const exportExcel = async()=>{
  if(!props.rows.length) return
  const XLSX=await import('xlsx')
  const data=props.rows.map((r:any)=>{ const base:any={'Поисковый запрос':r.phrase,'Ср част':r.avg_freq,'Клики':r.total_clicks,'Заказы':r.total_orders}; props.dates.forEach((d:string)=> base[fmtDate(d)] = cellPos(r,d)); return base })
  const ws=XLSX.utils.json_to_sheet(data)
  const wb=XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb,ws,'Фразы')
  XLSX.writeFile(wb,`phrases_${Date.now()}.xlsx`)
}
</script>
<style scoped>
.table-bordered td, .table-bordered th{border:1px solid #f1f1f1 !important}
#grid-scroll .kv-sticky-column{position:sticky !important; left:0 !important; background:#fff !important; z-index:5 !important; border-right:2px solid #dee2e6 !important}
#grid-scroll th.kv-sticky-column{z-index:11 !important; top:0}
.pos-top-10{background:#ebfbee !important; color:#2b8a3e !important; font-weight:500}
.pos-top-50{background:#fff9db !important; color:#856404 !important}
.has-orders{font-weight:900 !important; box-shadow:inset 0 0 0 1px rgba(0,123,255,.1)}
.table>tbody>tr.selected-row>td, .table>tbody>tr.selected-row>th{background:#ffb7f8 !important; color:#000 !important}
.table>tbody>tr.selected-row>td.pos-top-10{background:#f37be7 !important}
.table>tbody>tr.selected-row>td.pos-top-50{background:#f897ee !important}
#grid-scroll .table{table-layout:auto !important; width:auto !important; min-width:100% !important; display:table !important; overflow:visible !important}
</style>
