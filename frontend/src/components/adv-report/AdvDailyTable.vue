<template>
  <!-- Общая статистика по дням — statsProvider pageSize 50 + showPageSummary (index.php:595-618), итоги снизу -->
  <div class="tbl-card tbl-card--compact">
    <div class="card__hd">
      <span>Общая статистика по дням</span>
      <span class="spacer"></span>
      <ExcelButton :disabled="!rows.length" @click="exportExcel" />
    </div>
    <div class="tbl-wrap" ref="wrapRef">
      <table ref="tbl" class="tbl" style="width:100%; table-layout:auto">
        <thead><tr>
          <th class="t-center">Дата</th><th class="t-left">Товар</th>
          <th class="t-center">Показы</th><th class="t-center">Клики</th><th class="t-center">Корзины</th><th class="t-center">Заказы</th><th class="t-center">Отмена</th>
          <th class="t-center">CTR, %</th><th class="t-center">CR, %</th><th class="t-center">Затраты, ₽</th><th class="t-center">CPM, ₽</th><th class="t-center">CPC, ₽</th><th class="t-center">CPO, ₽</th>
        </tr></thead>
        <tbody><tr v-for="r in rows" :key="r.date + '-' + r.nm_id">
          <td class="t-center num">{{ fmtDate(r.date) }}</td>
          <td class="t-left">
            <ProductCell
              :photo="r.photos"
              :title="r.title"
              :vendor="r.vendorCode"
              :link="'/wb/detail?nm_id=' + r.nm_id"
              :link-label="'WB: ' + r.nm_id"
            />
          </td>
          <td class="num">{{ fmt0(r.views) }}</td><td class="num">{{ fmt0(r.clicks) }}</td><td class="num">{{ fmt0(r.atbs) }}</td><td class="num">{{ fmt0(r.orders) }}</td><td class="num">{{ fmt0(r.canceled) }}</td>
          <td class="num">{{ r.views>0 ? fmt2(r.clicks/r.views*100) : '' }}</td><td class="num">{{ r.clicks>0 ? fmt2(r.atbs/r.clicks*100) : '' }}</td>
          <td class="num">{{ fmt2(r.sum) }}</td>
          <td class="num">{{ r.views>0 ? fmt2(r.sum/r.views*1000) : '' }}</td><td class="num">{{ r.clicks>0 ? fmt2(r.sum/r.clicks) : '' }}</td><td class="num">{{ r.orders>0 ? fmt2(r.sum/r.orders) : '' }}</td>
        </tr></tbody>
        <tfoot v-if="rows.length"><tr class="tbl__total">
          <td></td>
          <td></td>
          <td>{{ fmt0(sum('views')) }}</td>
          <td>{{ fmt0(sum('clicks')) }}</td>
          <td>{{ fmt0(sum('atbs')) }}</td>
          <td>{{ fmt0(sum('orders')) }}</td>
          <td>{{ fmt0(sum('canceled')) }}</td>
          <td>{{ tCtr }}</td>
          <td>{{ tCr }}</td>
          <td>{{ fmt2(sum('sum')) }}</td>
          <td>{{ tCpm }}</td>
          <td>{{ tCpc }}</td>
          <td>{{ tCpo }}</td>
        </tr></tfoot>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import ExcelButton from '../common/ExcelButton.vue'
import ProductCell from '../common/ProductCell.vue'
import { useTableResize } from '@/composables/useTableResize'
import { useNumFmt } from '@/composables/useNumFmt'
import { useDateFmt } from '../../composables/useDateFmt'
import { exportXlsx } from '@/utils/exportXlsx'

const props = defineProps<{ rows: any[], campaignId: string|number, dateFrom: string, dateTo: string }>()
const tbl = ref<HTMLTableElement|null>(null)
const { fmt0, fmt2 } = useNumFmt()
const { fmtDate } = useDateFmt()
useTableResize(tbl, { storeKey: 'adv-daily' })
const sum = (k:string)=> props.rows.reduce((a,r)=> a + (Number(r[k])||0),0)
const tCtr = computed(()=> sum('views')>0 ? fmt2(sum('clicks')/sum('views')*100) : '')
const tCr = computed(()=> sum('clicks')>0 ? fmt2(sum('atbs')/sum('clicks')*100) : '')
const tCpm = computed(()=> sum('views')>0 ? fmt2(sum('sum')/sum('views')*1000) : '')
const tCpc = computed(()=> sum('clicks')>0 ? fmt2(sum('sum')/sum('clicks')) : '')
const tCpo = computed(()=> (sum('orders')-sum('canceled'))>0 ? fmt2(sum('sum')/(sum('orders')-sum('canceled'))) : '')

const exportExcel = async()=>{
  if(!props.rows.length) return
  const data = props.rows.map((r:any)=>({
    'Дата': r.date, 'Арт WB': r.nm_id, 'Товар': r.title, 'Артикул': r.vendorCode,
    'Показы': r.views, 'Клики': r.clicks, 'Корзины': r.atbs, 'Заказы': r.orders, 'Отмена': r.canceled,
    'CTR %': r.views? +(r.clicks/r.views*100).toFixed(2):'', 'CR %': r.clicks? +(r.atbs/r.clicks*100).toFixed(2):'',
    'Затраты': r.sum, 'CPM': r.views? +(r.sum/r.views*1000).toFixed(2):'', 'CPC': r.clicks? +(r.sum/r.clicks).toFixed(2):'', 'CPO': r.orders? +(r.sum/r.orders).toFixed(2):'',
  }))
  await exportXlsx({
    rows: data,
    filename: `adv-daily_${props.campaignId}_${props.dateFrom}_${props.dateTo}.xlsx`,
    sheetName: 'По дням',
    cols: [{wch:12},{wch:10},{wch:40},{wch:14},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:10},{wch:12},{wch:10},{wch:10},{wch:10}],
  })
}
</script>
