<template>
  <!-- Другие товары в заказах — AnotherGoodsProvider pageSize 10 + showPageSummary POS_TOP (index.php:558-586) -->
  <div v-if="rows.length" class="tbl-card">
    <div class="card__hd">
      <span>Другие товары в заказах</span>
      <span class="spacer"></span>
      <ExcelButton :disabled="!rows.length" @click="exportExcel" />
    </div>
    <div class="expandable-container tbl-wrap" :class="{ 'is-expanded': exp }">
      <table class="tbl" style="width:100%; table-layout:auto">
        <thead><tr>
          <th class="t-left">Товар</th><th class="t-center">Корзины</th><th class="t-center">Заказы</th><th class="t-center">Отмена</th><th class="t-center">Сумма, ₽</th>
        </tr>
        <!-- POS_TOP: итоги сверху, без слова «Итого» -->
        <tr class="tbl__total tbl__total--top">
          <td></td>
          <td>{{ fmt0(sum('atbs')) }}</td>
          <td>{{ fmt0(sum('orders')) }}</td>
          <td>{{ fmt0(sum('canceled')) }}</td>
          <td>{{ fmt2(sum('sum_price')) }}</td>
        </tr></thead>
        <tbody><tr v-for="r in rows.slice(0, exp?500:3)" :key="r.nm_id">
          <td class="t-left">
            <ProductCell
              :photo="r.photos"
              :title="r.title"
              :vendor="r.vendorCode"
              :link="'/wb/detail?nm_id=' + r.nm_id"
              :link-label="'WB: ' + r.nm_id"
            />
          </td>
          <td class="num">{{ fmt0(r.atbs) }}</td><td class="num">{{ fmt0(r.orders) }}</td><td class="num">{{ fmt0(r.canceled) }}</td><td class="num">{{ fmt2(r.sum_price) }}</td>
        </tr></tbody>
      </table>
    </div>
    <!-- Кнопка — если строк больше трёх (строка с карточкой товара высокая) -->
    <div v-if="exp || rows.length > 3" class="expand-btn-wrapper page-adv-report__more-wrap">
      <button class="btn btn--outline btn-sm page-adv-report__more-btn" @click="exp=!exp">{{ exp ? 'Свернуть' : 'Увидеть больше' }}</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import ExcelButton from '../common/ExcelButton.vue'
import ProductCell from '../common/ProductCell.vue'
import { useNumFmt } from '@/composables/useNumFmt'
import { exportXlsx } from '@/utils/exportXlsx'

const props = defineProps<{ rows: any[], campaignId: string|number, dateFrom: string, dateTo: string }>()
const exp = ref(false)
const { fmt0, fmt2 } = useNumFmt()
const sum = (k:string)=> props.rows.reduce((a,r)=> a + (Number(r[k])||0),0)

const exportExcel = async()=>{
  if(!props.rows.length) return
  const data = props.rows.map((r:any)=>({
    'Арт WB': r.nm_id, 'Товар': r.title, 'Артикул': r.vendorCode, 'Корзины': r.atbs, 'Заказы': r.orders, 'Отмена': r.canceled, 'Сумма': r.sum_price,
  }))
  await exportXlsx({
    rows: data,
    filename: `adv-another_${props.campaignId}_${props.dateFrom}_${props.dateTo}.xlsx`,
    sheetName: 'Другие',
    cols: [{wch:10},{wch:40},{wch:14},{wch:10},{wch:10},{wch:10},{wch:12}],
  })
}
</script>
