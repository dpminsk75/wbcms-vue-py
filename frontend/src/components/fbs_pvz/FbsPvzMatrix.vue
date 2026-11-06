<template>
  <div class="tbl-card fbs-tbl__card">
    <div class="card__hd">
      <span>Путь заказа до пункта выдачи — по складам и направлениям</span>
      <span class="spacer"></span>
      <label class="fbs-tbl__dirs-label">Направлений:
        <select :value="dirsCount" @change="emit('update:dirsCount', Number(($event.target as HTMLSelectElement).value))" class="wb-select fbs-tbl__dirs-select">
          <option :value="7">7</option>
          <option :value="10">10</option>
          <option :value="15">15</option>
          <option :value="0">Все</option>
        </select>
      </label>
    </div>
    <div class="tbl-wrap">
      <table class="tbl fbs-tbl">
        <thead>
          <tr>
            <th class="t-left fbs-tbl__first">Склад отгрузки</th>
            <th v-for="d in dirs" :key="d" class="fbs-tbl__dir"><span v-for="(line, i) in dirLines(d)" :key="i" class="fbs-tbl__dir-line">{{ line }}</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!matrix.length"><td :colspan="dirs.length + 1" class="fbs-tbl__empty">Нет данных</td></tr>
          <tr v-for="w in matrix" :key="String(w.warehouse_id)">
            <td class="t-left">{{ w.warehouse_name }}{{ w.warehouse_id ? ' ' + w.warehouse_id : '' }} <span class="text-muted">· {{ w.cnt }}</span></td>
            <td v-for="d in dirs" :key="d" class="t-right num">{{ fmtDur(w.cells[d]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  <div class="tbl-card fbs-tbl__card">
    <div class="card__hd">
      <span>По товарам ({{ products.length }})</span>
      <span class="spacer"></span>
      <span class="fbs-note mb-0">— склад отвечающий, где мы медленные; товар — что именно едет долго</span>
    </div>
    <div class="tbl-wrap">
      <table class="tbl fbs-tbl">
        <thead>
          <tr>
            <th class="t-left fbs-tbl__first">Товар</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('avg_total_h')">Заказ → ПВЗ {{ mark('avg_total_h') }}</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('avg_leg1_h')">Заказ → СЦ {{ mark('avg_leg1_h') }}</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('avg_leg2_h')">СЦ → ПВЗ {{ mark('avg_leg2_h') }}</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('cnt')">Заказов {{ mark('cnt') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!sorted.length"><td colspan="5" class="fbs-tbl__empty">Нет данных</td></tr>
          <tr v-for="p in sorted" :key="p.nm_id">
            <td class="t-left">
              <ProductCell
                compact
                :photo="p.photos"
                :title="p.title || ''"
                :vendor="p.vendor_code || ''"
                :brand="p.card_brand || ''"
                :subject="p.subject_name || ''"
                :nm-id="p.nm_id"
                :link="'/wb/detail?nm_id=' + p.nm_id"
                :link-label="'WB: ' + p.nm_id"
                copy-nm
                copy-link
              />
            </td>
            <td class="t-right num">{{ fmtDur(p.avg_total_h) }}</td>
            <td class="t-right num">{{ fmtDur(p.avg_leg1_h) }}</td>
            <td class="t-right num">{{ fmtDur(p.avg_leg2_h) }}</td>
            <td class="t-right num"><a :href="'/wb-order/index?nm_id=' + p.nm_id + '&date_from=' + props.dateFrom + '&date_to=' + props.dateTo" target="_blank" class="fbs-tbl__wb-link" :title="'Заказы товара ' + p.nm_id">{{ fmt0(p.cnt) }}</a></td>
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
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtDur = (v: any) => {
  if (v == null) return '—'
  const h = Number(v)
  const d = Math.floor(h / 24)
  const hh = Math.round(h % 24)
  return (d > 0 ? d + ' дн ' : '') + hh + ' ч'
}
</script>
