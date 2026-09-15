<template>
  <div class="row mt-3 align-items-start">
    <div class="col-md-6">
      <div class="card grid_wbstat" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
        <div class="card-header text-white d-flex justify-content-between align-items-center" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; font-size:13px; line-height:1.5; padding:4px 8px"><span>Заказы по дням</span><button class="btn btn-sm btn-light" style="font-size:11px; padding:2px 10px; border-radius:6px" @click="exportExcel('orders')" :disabled="!orders.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button></div>
        <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
        <template v-else>
          <div class="expandable-container" :class="{'is-expanded': expO}" :style="{maxHeight: expO ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}" style="overflow-x:auto">
            <table class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:11px; width:100%">
              <thead>
                <tr>
                  <th style="width:30px; text-align:center"></th>
                  <th style="text-align:center">Дата</th>
                  <th style="text-align:center">Кол-во</th>
                  <th style="text-align:center">Отмена</th>
                  <th style="text-align:center">Сумма</th>
                  <th style="text-align:center">Цена Рзн</th>
                  <th style="text-align:center">Скидка,%</th>
                  <th style="text-align:center">Цена со ск</th>
                  <th style="text-align:center">СПП,%</th>
                  <th style="text-align:center; width:80px">Цена зак</th>
                </tr>
                <tr v-if="orders.length" class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px">
                  <td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td>
                  <td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(sumO('cnt')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(sumO('cns')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt1(sumO('sum')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgO('tp')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgO('dsc')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgO('apwd')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgO('spp')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgO('finished_price')) }}</td>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!orders.length"><td colspan="10" class="text-center text-muted">Нет данных</td></tr>
                <tr v-for="r in orders" :key="r.odate">
                  <td style="text-align:center"><a :href="`/wb-order/index?WbOrderSearch[nm_id]=${r.nm_id}&WbOrderSearch[date]=${r.odate}`" target="_blank" class="text-primary"><i class="bi bi-eye"></i></a></td>
                  <td style="font-weight:600">{{ fmtDate(r.odate) }}</td>
                  <td style="text-align:right; font-weight:bold">{{ r.cnt }}</td>
                  <td style="text-align:right; font-weight:bold">{{ r.cns }}</td>
                  <td style="text-align:right; font-weight:bold">{{ fmt2(r.sum) }}</td>
                  <td style="text-align:right">{{ fmt2(r.tp) }}</td>
                  <td style="text-align:right">{{ fmt2(r.dsc) }}</td>
                  <td style="text-align:right">{{ fmt2(r.apwd) }}</td>
                  <td style="text-align:right">{{ fmt2(r.spp) }}</td>
                  <td style="text-align:right; font-weight:bold">{{ fmt2(r.finished_price) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="orders.length>6" class="expand-btn-wrapper" style="text-align:center; margin:10px 0 8px">
            <button class="btn btn-outline-primary btn-sm" style="font-size:12px; padding:4px 16px; border-radius:6px" @click="expO=!expO">{{ expO ? 'Свернуть' : 'Увидеть больше' }}</button>
          </div>
        </template>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card grid_wbstat" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
        <div class="card-header text-white d-flex justify-content-between align-items-center" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; font-size:13px; line-height:1.5; padding:4px 8px"><span>Продажи по дням</span><button class="btn btn-sm btn-light" style="font-size:11px; padding:2px 10px; border-radius:6px" @click="exportExcel('sales')" :disabled="!sales.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button></div>
        <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
        <template v-else>
          <div class="expandable-container" :class="{'is-expanded': expS}" :style="{maxHeight: expS ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}" style="overflow-x:auto">
            <table class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:11px; width:100%">
              <thead>
                <tr>
                  <th style="width:30px; text-align:center"></th>
                  <th style="text-align:center">Дата</th>
                  <th style="text-align:center">Кол-во</th>
                  <th style="text-align:center">Сумма</th>
                  <th style="text-align:center">К оплате</th>
                  <th style="text-align:center">Цена со ск</th>
                  <th style="text-align:center">СПП,%</th>
                  <th style="text-align:center; width:80px">Цена зак</th>
                  <th style="text-align:center; width:80px">К оплате</th>
                </tr>
                <tr v-if="sales.length" class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px">
                  <td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td>
                  <td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(sumS('cnt')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt1(sumS('sum')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt1(sumS('sFP')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgS('apwd')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgS('spp')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgS('finished_price')) }}</td>
                  <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(avgS('forPay')) }}</td>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!sales.length"><td colspan="9" class="text-center text-muted">Нет данных</td></tr>
                <tr v-for="r in sales" :key="r.odate">
                  <td style="text-align:center"><a :href="`/wb-sales/index?WbSalesSearch[nmId]=${r.nm_id}&WbSalesSearch[date]=${r.odate}`" target="_blank" class="text-primary"><i class="bi bi-eye"></i></a></td>
                  <td style="font-weight:600">{{ fmtDate(r.odate) }}</td>
                  <td style="text-align:right; font-weight:bold">{{ r.cnt }}</td>
                  <td style="text-align:right; font-weight:bold">{{ fmt2(r.sum) }}</td>
                  <td style="text-align:right; font-weight:bold">{{ fmt2(r.sFP) }}</td>
                  <td style="text-align:right">{{ fmt2(r.apwd) }}</td>
                  <td style="text-align:right">{{ fmt2(r.spp) }}</td>
                  <td style="text-align:right; font-weight:bold">{{ fmt2(r.finished_price) }}</td>
                  <td style="text-align:right; font-weight:bold">{{ fmt2(r.forPay) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="sales.length>6" class="expand-btn-wrapper" style="text-align:center; margin:10px 0 8px">
            <button class="btn btn-outline-primary btn-sm" style="font-size:12px; padding:4px 16px; border-radius:6px" @click="expS=!expS">{{ expS ? 'Свернуть' : 'Увидеть больше' }}</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { api } from '@/api/client'
const props=defineProps<{ nmId:string|number, dateFrom:string, dateTo:string }>()
const orders=ref<any[]>([])
const sales=ref<any[]>([])
const loading=ref(false)
const expO=ref(false)
const expS=ref(false)
const fmt2=(v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const fmt0=(v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt1=(v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:1, maximumFractionDigits:1}).format(Number(v)||0)
const fmtDate=(d:string)=>{ try{ return new Date(d).toLocaleDateString('ru-RU') }catch{ return d } }
const sumO=(k:string)=> orders.value.reduce((a:number,r:any)=> a+(Number(r[k])||0),0)
const sumS=(k:string)=> sales.value.reduce((a:number,r:any)=> a+(Number(r[k])||0),0)
const avgO=(k:string)=> orders.value.length? orders.value.reduce((a:number,r:any)=> a+(Number(r[k])||0),0)/orders.value.length : 0
const avgS=(k:string)=> sales.value.length? sales.value.reduce((a:number,r:any)=> a+(Number(r[k])||0),0)/sales.value.length : 0
const fetchData=async()=>{
  if(!props.nmId) return
  loading.value=true
  try{
    const [ro, rs]=await Promise.all([
      api.get(`/api/wb/detail/orders-daily?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`).then(r=>r.data),
      api.get(`/api/wb/detail/sales-daily?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`).then(r=>r.data)
    ])
    orders.value=Array.isArray(ro)? ro : ro.items||[]
    sales.value=Array.isArray(rs)? rs : rs.items||[]
  }catch{ orders.value=[]; sales.value=[] } finally{ loading.value=false }
}
onMounted(fetchData)
watch(()=>[props.nmId, props.dateFrom, props.dateTo], fetchData)
// как kartik ExportMenu EXCEL в _lo_table.php:98 / _ls_table.php — выгрузка видимых строк
const exportExcel=async(kind:'orders'|'sales')=>{
  const XLSX=await import('xlsx')
  const tag=`${props.nmId}_${props.dateFrom}_${props.dateTo}`
  if(kind==='orders'){
    const data=orders.value.map((r:any)=>({'Дата':r.odate,'Кол-во':r.cnt,'Отмена':r.cns,'Сумма':Number(r.sum)||0,'Цена Рзн':Number(r.tp)||0,'Скидка, %':Number(r.dsc)||0,'Цена со ск':Number(r.apwd)||0,'СПП, %':Number(r.spp)||0,'Цена зак':Number(r.finished_price)||0}))
    const ws=XLSX.utils.json_to_sheet(data)
    const wb=XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb,ws,'Заказы по дням'); XLSX.writeFile(wb,`orders-daily_${tag}.xlsx`)
  }else{
    const data=sales.value.map((r:any)=>({'Дата':r.odate,'Кол-во':r.cnt,'Сумма':Number(r.sum)||0,'К оплате':Number(r.sFP)||0,'Цена со ск':Number(r.apwd)||0,'СПП, %':Number(r.spp)||0,'Цена зак':Number(r.finished_price)||0,'К оплате (ср)':Number(r.forPay)||0}))
    const ws=XLSX.utils.json_to_sheet(data)
    const wb=XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb,ws,'Продажи по дням'); XLSX.writeFile(wb,`sales-daily_${tag}.xlsx`)
  }
}
</script>
<style scoped>
.expandable-container:not(.is-expanded)::after{content:""; position:absolute; bottom:0; left:0; width:100%; height:50px; background:linear-gradient(transparent, white); pointer-events:none}
.grid_wbstat th{white-space:normal !important; word-break:break-word; font-weight:500 !important; text-align:center; vertical-align:middle; font-size:11px}
/* Bootstrap 5 table-striped красит ячейки inset box-shadow поверх фона tr — гасим его, фон задаем самим td */
.kv-totals > td{background-color:#f2e7c3 !important; box-shadow:none !important}
</style>
