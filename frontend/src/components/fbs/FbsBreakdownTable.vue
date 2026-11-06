<template>
  <div class="tbl-card fbs-tbl__card">
    <div class="card__hd">
      <span>Разрез периода</span>
      <span class="spacer"></span>
      <div class="fbs-tbl__tabs" role="group">
        <button :class="{ 'is-on': mode === 'products' }" @click="emit('update:mode', 'products')">По товарам</button>
        <button :class="{ 'is-on': mode === 'warehouses' }" @click="emit('update:mode', 'warehouses')">По складам</button>
      </div>
    </div>
    <div v-if="loading" class="fbs-empty">Загрузка данных…</div>
    <div v-else class="tbl-wrap">
      <table class="tbl fbs-tbl">
        <thead>
          <tr>
            <th class="t-left fbs-tbl__first">{{ mode === 'products' ? 'Товар' : 'Склад' }}</th>
            <th v-for="c in cols" :key="c.key" class="t-right fbs-tbl__sort" @click="sortBy(c.key)">
              {{ c.label }} {{ sortKey === c.key ? (sortDir > 0 ? '▲' : '▼') : '⇅' }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!sorted.length"><td :colspan="cols.length + 1" class="fbs-tbl__empty">Нет данных</td></tr>
          <tr v-for="r in sorted" :key="mode === 'products' ? r.nm_id : String(r.warehouse_id)">
            <td class="t-left">
              <ProductCell
                v-if="mode === 'products'"
                compact
                :photo="r.photos"
                :title="r.title || ''"
                :vendor="r.vendor_code || ''"
                :brand="r.card_brand || ''"
                :nm-id="r.nm_id"
                :link="'/wb/detail?nm_id=' + r.nm_id"
                :link-label="'WB: ' + r.nm_id"
                copy-nm
                copy-link
              />
              <template v-else>{{ r.warehouse_name }}</template>
            </td>
            <td class="t-right num">{{ fmt0(r.cnt) }}</td>
            <td class="t-right num">{{ fmtMoney(r.orders_sum) }}</td>
            <td class="t-right num">{{ fmtPct1(r.buyout_pct) }}</td>
            <td class="t-right num">{{ fmt0(r.in_transit_cnt) }}</td>
            <td class="t-right num">{{ fmt0(r.canceled_seller) }}</td>
            <td class="t-right num">{{ fmt0(r.canceled_buyer) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { ref, computed } from 'vue'
import ProductCell from '@/components/common/ProductCell.vue'

const props = defineProps<{ items: any[], mode: string, loading: boolean }>()
const emit = defineEmits<{ (e: 'update:mode', v: string): void }>()

const cols = [
  { key: 'cnt', label: 'Заказов' },
  { key: 'orders_sum', label: 'Сумма заказов' },
  { key: 'buyout_pct', label: 'Выкуп' },
  { key: 'in_transit_cnt', label: 'В движении' },
  { key: 'canceled_seller', label: 'Отменил продавец' },
  { key: 'canceled_buyer', label: 'Отменил покупатель' },
]
const sortKey = ref('cnt')
const sortDir = ref(-1)
const sortBy = (k: string) => {
  if (sortKey.value === k) sortDir.value = -sortDir.value
  else { sortKey.value = k; sortDir.value = -1 }
}
const sorted = computed(() => {
  const arr = [...(props.items || [])]
  const k = sortKey.value, d = sortDir.value
  arr.sort((a: any, b: any) => ((Number(a[k]) || 0) - (Number(b[k]) || 0)) * d)
  return arr
})

const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
</script>
