<template>
  <div class="row mt-3 align-items-start">
    <div class="col-md-6">
      <div class="tbl-card tbl-card--compact">
        <div class="card__hd">
          <span>Заказы по дням</span>
          <span class="spacer"></span>
          <button class="hd-btn" @click="exportExcel('orders')" :disabled="!orders.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
        </div>
        <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
        <template v-else>
          <div class="expandable-container tbl-wrap" :class="{'is-expanded': expO}" :style="{maxHeight: expO ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}" ref="wrapRef">
            <table class="tbl" style="width:100%">
              <thead>
                <tr>
                  <th class="t-center" style="width:30px"></th>
                  <th class="t-center">Дата</th>
                  <th class="t-center">Кол-во</th>
                  <th class="t-center">Отмена</th>
                  <th class="t-center">Сумма</th>
                  <th class="t-center">Цена Рзн</th>
                  <th class="t-center">Скидка,%</th>
                  <th class="t-center">Цена со ск</th>
                  <th class="t-center">СПП,%</th>
                  <th class="t-center" style="width:80px">Цена зак</th>
                </tr>
                <tr v-if="orders.length" class="tbl__total tbl__total--top">
                  <td></td>
                  <td></td>
                  <td>{{ fmt0(sumO('cnt')) }}</td>
                  <td>{{ fmt0(sumO('cns')) }}</td>
                  <td>{{ fmt1(sumO('sum')) }}</td>
                  <td>{{ fmt2(avgO('tp')) }}</td>
                  <td>{{ fmt2(avgO('dsc')) }}</td>
                  <td>{{ fmt2(avgO('apwd')) }}</td>
                  <td>{{ fmt2(avgO('spp')) }}</td>
                  <td>{{ fmt2(avgO('finished_price')) }}</td>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!orders.length"><td colspan="10" class="text-center text-muted">Нет данных</td></tr>
                <tr v-for="r in orders" :key="r.odate">
                  <td class="t-center"><a :href="`/wb-order/index?WbOrderSearch[nm_id]=${r.nm_id}&WbOrderSearch[date]=${r.odate}`" target="_blank" class="text-primary"><i class="bi bi-eye"></i></a></td>
                  <td class="t-center" style="font-weight:600">{{ fmtDate(r.odate) }}</td>
                  <td style="font-weight:bold">{{ r.cnt }}</td>
                  <td style="font-weight:bold">{{ r.cns }}</td>
                  <td style="font-weight:bold">{{ fmt2(r.sum) }}</td>
                  <td>{{ fmt2(r.tp) }}</td>
                  <td>{{ fmt2(r.dsc) }}</td>
                  <td>{{ fmt2(r.apwd) }}</td>
                  <td>{{ fmt2(r.spp) }}</td>
                  <td style="font-weight:bold">{{ fmt2(r.finished_price) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="orders.length>6" class="expand-btn-wrapper" style="text-align:center; margin:10px 0 8px">
            <button class="btn btn--outline btn-sm page-wb-detail__more-btn" @click="expO=!expO">{{ expO ? 'Свернуть' : 'Увидеть больше' }}</button>
          </div>
        </template>
      </div>
    </div>
    <div class="col-md-6">
      <div class="tbl-card tbl-card--compact">
        <div class="card__hd">
          <span>Продажи по дням</span>
          <span class="spacer"></span>
          <button class="hd-btn" @click="exportExcel('sales')" :disabled="!sales.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
        </div>
        <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
        <template v-else>
          <div class="expandable-container tbl-wrap" :class="{'is-expanded': expS}" :style="{maxHeight: expS ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}" ref="wrapRef">
            <table class="tbl" style="width:100%">
              <thead>
                <tr>
                  <th class="t-center" style="width:30px"></th>
                  <th class="t-center">Дата</th>
                  <th class="t-center">Кол-во</th>
                  <th class="t-center">Сумма</th>
                  <th class="t-center">К оплате</th>
                  <th class="t-center">Цена со ск</th>
                  <th class="t-center">СПП,%</th>
                  <th class="t-center" style="width:80px">Цена зак</th>
                  <th class="t-center" style="width:80px">К оплате</th>
                </tr>
                <tr v-if="sales.length" class="tbl__total tbl__total--top">
                  <td></td>
                  <td></td>
                  <td>{{ fmt0(sumS('cnt')) }}</td>
                  <td>{{ fmt1(sumS('sum')) }}</td>
                  <td>{{ fmt1(sumS('sFP')) }}</td>
                  <td>{{ fmt2(avgS('apwd')) }}</td>
                  <td>{{ fmt2(avgS('spp')) }}</td>
                  <td>{{ fmt2(avgS('finished_price')) }}</td>
                  <td>{{ fmt2(avgS('forPay')) }}</td>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!sales.length"><td colspan="9" class="text-center text-muted">Нет данных</td></tr>
                <tr v-for="r in sales" :key="r.odate">
                  <td class="t-center"><a :href="`/wb-sales/index?WbSalesSearch[nmId]=${r.nm_id}&WbSalesSearch[date]=${r.odate}`" target="_blank" class="text-primary"><i class="bi bi-eye"></i></a></td>
                  <td class="t-center" style="font-weight:600">{{ fmtDate(r.odate) }}</td>
                  <td style="font-weight:bold">{{ r.cnt }}</td>
                  <td style="font-weight:bold">{{ fmt2(r.sum) }}</td>
                  <td style="font-weight:bold">{{ fmt2(r.sFP) }}</td>
                  <td>{{ fmt2(r.apwd) }}</td>
                  <td>{{ fmt2(r.spp) }}</td>
                  <td style="font-weight:bold">{{ fmt2(r.finished_price) }}</td>
                  <td style="font-weight:bold">{{ fmt2(r.forPay) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="sales.length>6" class="expand-btn-wrapper" style="text-align:center; margin:10px 0 8px">
            <button class="btn btn--outline btn-sm page-wb-detail__more-btn" @click="expS=!expS">{{ expS ? 'Свернуть' : 'Увидеть больше' }}</button>
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
import { useDateFmt } from '../../composables/useDateFmt'
const { fmtDate } = useDateFmt()
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
.expandable-container:not(.is-expanded)::after{content:""; position:absolute; bottom:0; left:0; width:100%; height:50px; background:linear-gradient(transparent, var(--surface)); pointer-events:none}
</style>
