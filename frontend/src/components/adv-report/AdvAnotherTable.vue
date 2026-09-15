<template>
  <!-- Другие товары в заказах — AnotherGoodsProvider pageSize 10 + showPageSummary POS_TOP (index.php:558-586) -->
  <div v-if="rows.length" class="row mb-3">
    <div class="col-12"><div class="card" style="border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
      <div class="card-header text-white d-flex justify-content-between align-items-center" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; font-size:13px; line-height:1.5; padding:4px 8px;">
        <span>Другие товары в заказах</span>
        <button class="btn btn-sm btn-light" style="font-size:11px; padding:2px 10px; border-radius:6px" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
      </div>
      <div class="expandable-container" :class="{'is-expanded': exp}" :style="{maxHeight: exp ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}" style="overflow-x:auto"><table class="table table-bordered table-striped table-hover kv-grid-table mb-0 adv-grid" style="font-size:12px; width:100%; table-layout:auto">
        <thead><tr>
          <th style="width:90px; text-align:center">Арт WB</th><th style="min-width:420px; text-align:center">Товар / Артикул</th><th style="width:100px; text-align:center">Корзины</th><th style="width:100px; text-align:center">Заказы</th><th style="width:100px; text-align:center">Отмена</th><th style="width:100px; text-align:center">Сумма, ₽</th>
        </tr>
        <!-- POS_TOP: итоги сверху, без слова «Итого» -->
        <tr class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px">
          <td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td>
          <td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(sum('atbs')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(sum('orders')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(sum('canceled')) }}</td>
          <td style="text-align:right; color:#5A1C9C; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt2(sum('sum_price')) }}</td>
        </tr></thead>
        <tbody><tr v-for="r in rows.slice(0, exp?500:10)" :key="r.nm_id">
          <td style="text-align:center; padding:4px"><a :href="'/wb/detail?nm_id='+r.nm_id" target="_blank" class="adv-link">{{ r.nm_id }}</a></td>
          <td style="padding:4px"><div style="font-weight:700;">{{ r.title }}</div><div style="color:#666; font-size:11px;">Артикул: <b>{{ r.vendorCode }}</b></div></td>
          <td style="text-align:right; padding:4px">{{ fmt0(r.atbs) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.orders) }}</td><td style="text-align:right; padding:4px">{{ fmt0(r.canceled) }}</td><td style="text-align:right; padding:4px">{{ fmt2(r.sum_price) }}</td>
        </tr></tbody>
      </table></div>
      <div v-if="rows.length>10" class="expand-btn-wrapper" style="text-align:center; margin:10px 0 8px">
        <button class="btn btn-outline-primary btn-sm" style="font-size:12px; padding:4px 16px; border-radius:6px" @click="exp=!exp">{{ exp ? 'Свернуть' : 'Увидеть больше' }}</button>
      </div>
    </div></div>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
const props = defineProps<{ rows: any[], campaignId: string|number, dateFrom: string, dateTo: string }>()
const exp = ref(false)
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const sum = (k:string)=> props.rows.reduce((a,r)=> a + (Number(r[k])||0),0)
const exportExcel = async()=>{
  if(!props.rows.length) return
  const XLSX = await import('xlsx')
  const data = props.rows.map((r:any)=>({
    'Арт WB': r.nm_id, 'Товар': r.title, 'Артикул': r.vendorCode, 'Корзины': r.atbs, 'Заказы': r.orders, 'Отмена': r.canceled, 'Сумма': r.sum_price,
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{wch:10},{wch:40},{wch:14},{wch:10},{wch:10},{wch:10},{wch:12}]
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Другие'); XLSX.writeFile(wb, `adv-another_${props.campaignId}_${props.dateFrom}_${props.dateTo}.xlsx`)
}
</script>
<style scoped>
.adv-grid th{white-space:normal; overflow-wrap:break-word; font-weight:500; font-size:11px; text-align:center; vertical-align:middle; padding:4px !important;}
.adv-grid td{font-size:12px; vertical-align:middle;}
.adv-link{color:#8A2BE0; font-weight:600; text-decoration:none;}
.kv-totals > td{background-color:#f2e7c3 !important; box-shadow:none !important;}
</style>
