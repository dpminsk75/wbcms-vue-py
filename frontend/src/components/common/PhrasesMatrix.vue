<template>
  <div class="card" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
    <div class="card-header text-white d-flex justify-content-between align-items-center" style="background:#2c7be5; font-weight:700">
      <span><i class="fas fa-chart-line me-2"></i> {{ heading ?? 'Динамика позиций' }}</span>
      <button v-if="showExcel" class="btn btn-sm btn-light" style="font-size:12px; padding:4px 12px; border-radius:6px" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
    </div>
    <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
    <div v-else id="grid-scroll" style="max-height:70vh; overflow:auto; position:relative" ref="wrapRef">
      <table ref="tbl" class="table table-bordered table-hover kv-grid-table mb-0" style="font-size:12px; width:auto; min-width:100%; table-layout:auto">
        <thead style="position:sticky; top:0; z-index:10; background:#fff">
          <tr>
            <template v-if="props.mode === 'by-card'">
              <th class="kv-sticky-column" style="width:100px; min-width:80px; white-space:nowrap; text-align:center; background:#fff; cursor:pointer; user-select:none" @click="sortBy('nmID')">Арт WB <span v-if="sortKey==='nmID'">{{ sortDir==='asc'?'▲':'▼' }}</span><span v-else>⇅</span></th>
              <th class="kv-sticky-column" style="width:300px; min-width:280px; white-space:normal; text-align:left; background:#fff; cursor:pointer; user-select:none" @click="sortBy('title')">Товар / Позиция <span v-if="sortKey==='title'">{{ sortDir==='asc'?'▲':'▼' }}</span><span v-else>⇅</span></th>
            </template>
            <template v-else>
              <th class="kv-sticky-column" style="width:220px; min-width:200px; white-space:normal; text-align:left; background:#fff; cursor:pointer; user-select:none" @click="sortBy('phrase')">Поисковый запрос <span v-if="sortKey==='phrase'">{{ sortDir==='asc'?'▲':'▼' }}</span><span v-else>⇅</span></th>
              <th style="width:100px; white-space:nowrap; text-align:center; cursor:pointer; user-select:none" title="Средняя частотность за неделю" @click="sortBy('avg_freq')">Ср. част <span v-if="sortKey==='avg_freq'">{{ sortDir==='asc'?'▲':'▼' }}</span><span v-else>⇅</span></th>
            </template>
            <th style="width:100px; white-space:nowrap; text-align:center; cursor:pointer; user-select:none" @click="sortBy('total_clicks')">Клики <span v-if="sortKey==='total_clicks'">{{ sortDir==='asc'?'▲':'▼' }}</span><span v-else>⇅</span></th>
            <th style="width:95px; white-space:nowrap; text-align:center; cursor:pointer; user-select:none" @click="sortBy('total_orders')">Заказы <span v-if="sortKey==='total_orders'">{{ sortDir==='asc'?'▲':'▼' }}</span><span v-else>⇅</span></th>
            <th v-for="d in dates" :key="d" class="text-center small" style="min-width:35px; padding:4px 2px; font-size:11px; text-align:center">{{ fmtDate(d) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length"><td :colspan="4+dates.length" class="text-center text-muted">Нет данных</td></tr>
          <tr v-for="r in sortedRows" :key="props.mode === 'by-card' ? r.nmID : r.phrase" class="clickable-row" style="cursor:pointer" @click="sel = props.mode === 'by-card' ? String(r.nmID) : r.phrase" :class="{'selected-row': sel === (props.mode === 'by-card' ? String(r.nmID) : r.phrase)}">
            <template v-if="props.mode === 'by-card'">
              <td class="kv-sticky-column text-muted small" style="text-align:center; background:#fff"><router-link :to="`/wb/detail?nm_id=${r.nmID}`" target="_blank">{{ r.nmID }}</router-link></td>
              <td class="kv-sticky-column" style="min-width:300px; white-space:normal; background:#fff"><router-link :to="`/wb-search/card?nm_id=${r.nmID}`">{{ r.title }}</router-link></td>
            </template>
            <template v-else>
              <td class="kv-sticky-column text-muted" style="width:220px; white-space:normal; background:#fff"><a :href="'https://www.wildberries.ru/catalog/0/search.aspx?search='+encodeURIComponent(r.phrase)" target="_blank">{{ r.phrase }}</a></td>
              <td class="text-secondary" style="background:#fcfcfc; text-align:center">{{ r.avg_freq ?? '' }}</td>
            </template>
            <td class="text-primary" style="background:#fcfcfc; text-align:center">{{ r.total_clicks ?? '' }}</td>
            <td class="text-primary" style="background:#f8f9ff; text-align:center">{{ r.total_orders ?? '' }}</td>
            <td v-for="d in dates" :key="d" :class="cellCls(r,d)" :title="cellTitle(r,d)" style="text-align:center; padding:4px 2px">{{ cellPos(r,d) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { api } from '@/api/client'
const props = withDefaults(defineProps<{
  rows: any[]
  dates: string[] // uniqueDates yyyy-mm-dd
  isLoading?: boolean
  showExcel?: boolean // в /wb-search/* Excel не было — скрывать кнопкой
  mode?: 'by-phrase' | 'by-card' // by-card: строки=карточки (phrase.php зеркальная матрица)
  heading?: string | null // by-card: «Товары по запросу: {phrase}»
}>(), { isLoading:false, showExcel:true, mode:'by-phrase', heading:null })
const tbl = ref<HTMLTableElement|null>(null)
const wrapRef = ref<HTMLDivElement|null>(null)
const sel = ref('')
// сортировка как phraseDataProvider в WbController.php:878 (дефолт total_orders DESC)
const sortKey = ref<'phrase'|'nmID'|'title'|'avg_freq'|'total_clicks'|'total_orders'>('total_orders')
const sortDir = ref<'asc'|'desc'>('desc')
const sortedRows = computed(()=>{
  const arr=[...props.rows]
  const k=sortKey.value, d=sortDir.value==='asc'?1:-1
  arr.sort((a:any,b:any)=>{
    if(k==='phrase' || k==='title') return String(a[k]||'').localeCompare(String(b[k]||''),'ru')*d
    return ((Number(a[k])||0)-(Number(b[k])||0))*d
  })
  return arr
})
const sortBy=(k:'phrase'|'nmID'|'title'|'avg_freq'|'total_clicks'|'total_orders')=>{
  if(sortKey.value===k) sortDir.value=sortDir.value==='asc'?'desc':'asc'
  else{ sortKey.value=k; sortDir.value= (k==='phrase'||k==='title')?'asc':'desc' }
}
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
const fetchPhrases = async () => {
  if (!props.nmId || !props.dateFrom || !props.dateTo) return
  isLoading.value = true
  try {
    const { data:j } = await api.get(`/api/wb/detail/phrases?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`)
    rows.value = j.models || []
  } catch {
    rows.value = []
  } finally {
    isLoading.value = false
  }
}
onMounted(fetchPhrases)
const exportExcel = async()=>{
  if(!props.rows.length) return
  const XLSX=await import('xlsx')
  const data=sortedRows.value.map((r:any)=>{
    if(props.mode==='by-card'){
      const base:any={'Арт WB':r.nmID,'Товар':r.title,'Клики':r.total_clicks,'Заказы':r.total_orders}
      props.dates.forEach((d:string)=> base[fmtDate(d)] = cellPos(r,d))
      return base
    }
    const base:any={'Поисковый запрос':r.phrase,'Ср част':r.avg_freq,'Клики':r.total_clicks,'Заказы':r.total_orders}
    props.dates.forEach((d:string)=> base[fmtDate(d)] = cellPos(r,d))
    return base
  })
  const ws=XLSX.utils.json_to_sheet(data)
  const wb=XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb,ws, props.mode==='by-card' ? 'Товары' : 'Фразы')
  XLSX.writeFile(wb, props.mode==='by-card' ? `phrase-cards_${Date.now()}.xlsx` : `phrases_${Date.now()}.xlsx`)
}
</script>
<style scoped>
.table-bordered td, .table-bordered th{border:1px solid #f1f1f1 !important}
#grid-scroll .kv-sticky-column{position:sticky !important; left:0 !important; background:#fff !important; z-index:5 !important; border-right:2px solid #dee2e6 !important}
#grid-scroll th.kv-sticky-column{z-index:11 !important; top:0}
.pos-top-10{background:#ebfbee !important; color:#2b8a3e !important; font-weight:500}
.pos-top-50{background:#fff9db !important; color:#856404 !important}
.has-orders{font-weight:900 !important; box-shadow:inset 0 0 0 1px rgba(0,123,255,.1)}
#grid-scroll td a{text-decoration:none}
.table>tbody>tr.selected-row>td, .table>tbody>tr.selected-row>th{background:#ffb7f8 !important; color:#000 !important}
.table>tbody>tr.selected-row>td.pos-top-10{background:#f37be7 !important}
.table>tbody>tr.selected-row>td.pos-top-50{background:#f897ee !important}
#grid-scroll .table{table-layout:auto !important; width:auto !important; min-width:100% !important; display:table !important; overflow:visible !important}
/* condensed как в оригинале: в окно влезает больше строк */
#grid-scroll th, #grid-scroll td{padding:4px !important}
#grid-scroll tbody td{font-size:11px}
</style>
