<template>
  <!-- Другие товары в заказах — AnotherGoodsProvider pageSize 10 + showPageSummary POS_TOP (index.php:558-586) -->
  <div v-if="rows.length" class="row mb-3">
    <div class="col-12"><div class="card wb-grid-card">
      <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header wb-card-header--sm">
        <span>Другие товары в заказах</span>
        <button class="btn btn-sm btn-light wb-excel-btn--sm" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
      </div>
      <div class="expandable-container wb-table-wrap" :class="{'is-expanded': exp}" :style="{maxHeight: exp ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}"><table class="table table-bordered table-striped table-hover kv-grid-table mb-0 adv-grid">
        <thead><tr>
          <th style="width:90px; text-align:center">Арт WB</th><th style="min-width:420px; text-align:center">Товар / Артикул</th><th style="width:100px; text-align:center">Корзины</th><th style="width:100px; text-align:center">Заказы</th><th style="width:100px; text-align:center">Отмена</th><th style="width:100px; text-align:center">Сумма, ₽</th>
        </tr>
        <!-- POS_TOP: итоги сверху, без слова «Итого» -->
        <tr class="kv-totals">
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
