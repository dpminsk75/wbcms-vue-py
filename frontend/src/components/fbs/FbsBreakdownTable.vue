<template>
  <div class="page-fbs-report__breakdown card wb-grid-card">
    <div class="page-fbs-report__breakdown-head">
      <span class="page-fbs-report__breakdown-title">Разрез периода</span>
      <div class="page-fbs-report__breakdown-tabs" role="group">
        <button :class="mode === 'products' ? 'active' : ''" @click="emit('update:mode', 'products')">По товарам</button>
        <button :class="mode === 'warehouses' ? 'active' : ''" @click="emit('update:mode', 'warehouses')">По складам</button>
      </div>
    </div>
    <div v-if="loading" class="p-4 text-center text-muted">Загрузка...</div>
    <div v-else class="wb-table-wrap">
      <table class="table table-bordered table-striped table-hover kv-grid-table mb-0">
        <thead>
          <tr>
            <th class="page-fbs-report__breakdown-first">{{ mode === 'products' ? 'Товар' : 'Склад' }}</th>
            <th v-for="c in cols" :key="c.key" @click="sortBy(c.key)" class="page-fbs-report__breakdown-sort">
              {{ c.label }} {{ sortKey === c.key ? (sortDir > 0 ? '▲' : '▼') : '⇅' }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!sorted.length"><td :colspan="cols.length + 1" class="text-center text-muted">Нет данных</td></tr>
          <tr v-for="r in sorted" :key="mode === 'products' ? r.nm_id : String(r.warehouse_id)">
            <td v-if="mode === 'products'">
              <div class="fbs-product">
                <img :src="photo(r)" @error="(e:any)=>e.target.src='/images/no-photo.png'" class="fbs-product__photo" />
                <div>
                  <div class="fbs-product__title">{{ r.title || '(нет карточки)' }}</div>
                  <div class="fbs-product__sub">{{ r.card_brand || '' }}</div>
                  <div class="fbs-product__sub">{{ r.vendor_code || '' }}</div>
                  <div class="fbs-product__sub"><a :href="'/wb/detail?nm_id=' + r.nm_id" target="_blank" class="fbs-product__link">WB: {{ r.nm_id }}</a></div>
                </div>
              </div>
            </td>
            <td v-else>{{ r.warehouse_name }}</td>
            <td class="page-fbs-report__num">{{ fmt0(r.cnt) }}</td>
            <td class="page-fbs-report__num">{{ fmtMoney(r.orders_sum) }}</td>
            <td class="page-fbs-report__num">{{ fmtPct1(r.buyout_pct) }}</td>
            <td class="page-fbs-report__num">{{ fmt0(r.in_transit_cnt) }}</td>
            <td class="page-fbs-report__num">{{ fmt0(r.canceled_seller) }}</td>
            <td class="page-fbs-report__num">{{ fmt0(r.canceled_buyer) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'

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

const photo = (r: any) => {
  try {
    let p = r.photos
    if (typeof p === 'string') p = JSON.parse(p)
    if (typeof p === 'string') p = JSON.parse(p)
    if (Array.isArray(p) && p[0]) return p[0]
  } catch { /* noop */ }
  return '/images/no-photo.png'
}
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
</script>
<style scoped>
.page-fbs-report__breakdown { margin-top: 8px; margin-bottom: 16px; border-color: #d5dae1; box-shadow: 0 1px 3px rgba(16,24,40,.08); }
.page-fbs-report__breakdown-head { display: flex; align-items: center; gap: 12px; padding: 12px 18px; background: #fff; border-bottom: 1px solid #e5e7eb; border-radius: 10px 10px 0 0; }
.page-fbs-report__breakdown-title { font-size: 13px; font-weight: 700; color: #111827; }
.page-fbs-report__breakdown-tabs { display: flex; gap: 4px; background: #f1f5f9; border-radius: 8px; padding: 3px; }
.page-fbs-report__breakdown-tabs button { border: 0; background: transparent; font-size: 12px; color: #6b7280; border-radius: 6px; padding: 4px 12px; cursor: pointer; }
.page-fbs-report__breakdown-tabs button.active { background: #fff; color: #7c3aed; font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
.page-fbs-report__breakdown-first { text-align: center; min-width: 240px; }
.page-fbs-report__breakdown-sort { text-align: center; cursor: pointer; white-space: nowrap; }

.page-fbs-report__num { text-align: right; white-space: nowrap; }
</style>
