<template>
  <div class="card wb-grid-card page-fbs-pvz__table-card">
    <div class="page-fbs-pvz__table-head">Путь заказа до пункта выдачи — по складам и направлениям
      <label class="page-fbs-pvz__dirs-label">Направлений:
        <select :value="dirsCount" @change="emit('update:dirsCount', Number(($event.target as HTMLSelectElement).value))" class="form-select form-select-sm page-fbs-pvz__dirs-select">
          <option :value="7">7</option>
          <option :value="10">10</option>
          <option :value="15">15</option>
          <option :value="0">Все</option>
        </select>
      </label>
    </div>
    <div class="wb-table-wrap">
      <table class="table table-bordered table-striped table-hover kv-grid-table mb-0">
        <thead>
          <tr>
            <th class="page-fbs-pvz__first">Склад отгрузки</th>
            <th v-for="d in dirs" :key="d" class="page-fbs-pvz__dir"><span v-for="(line, i) in dirLines(d)" :key="i" class="page-fbs-pvz__dir-line">{{ line }}</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!matrix.length"><td :colspan="dirs.length + 1" class="text-center text-muted">Нет данных</td></tr>
          <tr v-for="w in matrix" :key="String(w.warehouse_id)">
            <td>{{ w.warehouse_name }}{{ w.warehouse_id ? ' ' + w.warehouse_id : '' }} <span class="text-muted">· {{ w.cnt }}</span></td>
            <td v-for="d in dirs" :key="d" class="page-fbs-pvz__num">{{ fmtDur(w.cells[d]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  <div class="card wb-grid-card page-fbs-pvz__table-card">
    <div class="page-fbs-pvz__table-head">По товарам ({{ products.length }}) <span class="text-muted" style="font-weight:400">— склад отвечающий, где мы медленные; товар — что именно едет долго</span></div>
    <div class="wb-table-wrap">
      <table class="table table-bordered table-striped table-hover kv-grid-table mb-0">
        <thead>
          <tr>
            <th class="page-fbs-pvz__first">Товар</th>
            <th @click="sortBy('avg_total_h')" class="page-fbs-pvz__sort">Заказ → ПВЗ {{ mark('avg_total_h') }}</th>
            <th @click="sortBy('avg_leg1_h')" class="page-fbs-pvz__sort">Заказ → СЦ {{ mark('avg_leg1_h') }}</th>
            <th @click="sortBy('avg_leg2_h')" class="page-fbs-pvz__sort">СЦ → ПВЗ {{ mark('avg_leg2_h') }}</th>
            <th @click="sortBy('cnt')" class="page-fbs-pvz__sort">Заказов {{ mark('cnt') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!sorted.length"><td colspan="5" class="text-center text-muted">Нет данных</td></tr>
          <tr v-for="p in sorted" :key="String(p.nm_id)">
            <td>
              <div class="page-fbs-pvz__product">
                <img :src="photo(p)" class="page-fbs-pvz__photo" @error="(e:any)=>e.target.src='/images/no-photo.png'" />
                <div>
                  <div class="page-fbs-pvz__product-title" :title="p.title || ''">{{ p.title || '(нет карточки)' }}</div>
                  <div class="page-fbs-pvz__product-sub">{{ p.subject_name || '' }}{{ p.card_brand ? ' • ' + p.card_brand : '' }}</div>
                  <div class="page-fbs-pvz__product-sub">{{ p.vendor_code || '' }}</div>
                  <div class="page-fbs-pvz__product-sub"><a :href="'/wb/detail?nm_id=' + p.nm_id" target="_blank" class="page-fbs-pvz__wb-link">WB: {{ p.nm_id }}</a></div>
                </div>
              </div>
            </td>
            <td class="page-fbs-pvz__num">{{ fmtDur(p.avg_total_h) }}</td>
            <td class="page-fbs-pvz__num">{{ fmtDur(p.avg_leg1_h) }}</td>
            <td class="page-fbs-pvz__num">{{ fmtDur(p.avg_leg2_h) }}</td>
            <td class="page-fbs-pvz__num"><a :href="'/wb-order/index?nm_id=' + p.nm_id + '&date_from=' + props.dateFrom + '&date_to=' + props.dateTo" target="_blank" class="page-fbs-pvz__wb-link" :title="'Заказы товара ' + p.nm_id">{{ fmt0(p.cnt) }}</a></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
const props = defineProps<{ matrix: any[], dirs: string[], products: any[], dirsCount: number, dateFrom: string, dateTo: string }>()
const emit = defineEmits<{ (e: 'update:dirsCount', v: number): void }>()
const dirLabel = (d: string) => d === 'all' ? 'Все направления' : d === 'rest' ? 'Остальные' : d
// Направление в 3 строки: страна / первая половина региона / вторая половина.
const dirLines = (d: string): string[] => {
  if (d === 'all') return ['Все', 'направления']
  if (d === 'rest') return ['Остальные']
  const idx = d.indexOf(',')
  if (idx < 0) return [d]
  const head = d.slice(0, idx + 1)
  const words = d.slice(idx + 1).trim().split(/\s+/)
  const mid = Math.ceil(words.length / 2)
  return [head, words.slice(0, mid).join(' '), words.slice(mid).join(' ')].filter((s) => s && s !== ',')
}
const sortKey = ref('avg_total_h')
const sortDir = ref(-1)
const sortBy = (k: string) => {
  if (sortKey.value === k) sortDir.value = -sortDir.value
  else { sortKey.value = k; sortDir.value = -1 }
}
const mark = (k: string) => sortKey.value === k ? (sortDir.value > 0 ? '▲' : '▼') : '⇅'
const sorted = computed(() => {
  const arr = [...(props.products || [])]
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
const fmtDur = (v: any) => {
  if (v == null) return '—'
  const h = Number(v)
  const d = Math.floor(h / 24)
  const hh = Math.round(h % 24)
  return (d > 0 ? d + ' дн ' : '') + hh + ' ч'
}
</script>
<style scoped>
.page-fbs-pvz__table-card { margin-bottom: 16px; }
.page-fbs-pvz__table-head { font-size: 13px; font-weight: 700; color: #111827; padding: 12px 18px; background: #fff; border-bottom: 1px solid #e5e7eb; border-radius: 10px 10px 0 0; }
.page-fbs-pvz__first { text-align: center; min-width: 220px; }
.page-fbs-pvz__dir { text-align: center; font-size: 11px; min-width: 110px; }
.page-fbs-pvz__dir-line { display: block; line-height: 1.3; }
.page-fbs-pvz__sort { text-align: center; cursor: pointer; white-space: nowrap; }
.page-fbs-pvz__num { text-align: right; white-space: nowrap; }
.page-fbs-pvz__dirs-label { margin-left: auto; font-size: 12px; font-weight: 400; color: #6b7280; display: flex; align-items: center; gap: 6px; }
.page-fbs-pvz__dirs-select { width: auto; display: inline-block; }
.page-fbs-pvz__table-head { display: flex; align-items: center; }
.page-fbs-pvz__product { display: flex; gap: 8px; align-items: center; }
.page-fbs-pvz__photo { width: 40px; height: 52px; object-fit: cover; border-radius: 4px; flex-shrink: 0; }
.page-fbs-pvz__product-title { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 260px; }
.page-fbs-pvz__product-sub { font-size: 11px; color: #6b7280; }
.page-fbs-pvz__wb-link { color: #7c3aed; text-decoration: none; }
.page-fbs-pvz__wb-link:hover { text-decoration: underline; }
</style>
