<template>
  <section v-if="busy || hasData || isError" class="tbl-card">
    <div class="card__hd">
      <span>Реклама (с {{ fmtDate(dateFrom) }})</span>
      <span class="spacer"></span>
      <span class="hd-badge">Показаны 1-{{ displayRows.length }} из {{ rows.length }}</span>
    </div>
    <div v-if="isLoading" class="dsp__empty">Загрузка…</div>
    <div v-else class="tbl-wrap">
      <table class="tbl dsp-tbl">
        <thead>
          <tr>
            <th class="t-center sortable" style="width: 220px" @click="sortBy('name')">
              Кампания <span class="dsp-sortmark">{{ sortKey === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : '⇅' }}</span>
            </th>
            <th class="t-center sortable" style="width: 110px" @click="sortBy('status')">
              Ст <span class="dsp-sortmark">{{ sortKey === 'status' ? (sortDir === 'asc' ? '▲' : '▼') : '⇅' }}</span>
            </th>
            <th class="t-center num">Показы</th>
            <th class="t-center num">Клики</th>
            <th class="t-center num">Корзины</th>
            <th class="t-center num">Заказы</th>
            <th class="t-center num">Отмена</th>
            <th class="t-center num">CTR, %</th>
            <th class="t-center num">CR, %</th>
            <th class="t-center num">Затраты, ₽</th>
            <th class="t-center num">CPM, ₽</th>
            <th class="t-center num">CPC, ₽</th>
            <th class="t-center num">CPO ₽</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in displayRows" :key="r.campaign_id">
            <td class="t-left">
              <a class="dsp-tbl__link" :href="'/wb-adv-report?id=' + r.campaign_id + '&date_from=' + dateFrom + '&date_to=' + dateTo" target="_blank">{{ r.name }}</a>
            </td>
            <td class="t-center"><span class="badge" :class="statusClass(r.status)">{{ statusLabel(r.status) }}</span></td>
            <td class="num">{{ fmt(r.views) }}</td>
            <td class="num">{{ fmt(r.clicks) }}</td>
            <td class="num">{{ fmt(r.atbs) }}</td>
            <td class="num">{{ fmt(r.orders) }}</td>
            <td class="num">{{ fmt(r.canceled) }}</td>
            <td class="num">{{ ctr(r) }}</td>
            <td class="num">{{ cr(r) }}</td>
            <td class="num" style="font-weight: 600">{{ fmt2(r.sum) }}</td>
            <td class="num">{{ cpm(r) }}</td>
            <td class="num">{{ cpc(r) }}</td>
            <td class="num">{{ cpo(r) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="wb-pager">
      <button v-if="hasMore" class="btn btn--outline btn-sm" @click="shown += 10">Увидеть больше</button>
      <span class="wb-pager__label">Показаны <b>{{ displayRows.length }}</b> из <b>{{ rows.length }}</b> записей.</span>
    </div>
  </section>
</template>

<script setup lang="ts">
/** Реклама (черновик) — таблица темы вместо dashboard/AdvCampaigns.vue. */
import { ref, computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import { useDateFmt } from '../../composables/useDateFmt'

const props = defineProps<{ dateFrom: string, dateTo: string }>()
const auth = useAuthStore()
const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})
/** Показываем порциями: сначала 5 строк, «Увидеть больше» добавляет по 10. */
const shown = ref(5)
const sortKey = ref<'name' | 'status' | null>(null)
const sortDir = ref<'asc' | 'desc'>('asc')

const { data: rows, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => ['adv', props.dateFrom, props.dateTo, auth.companyId] as const),
  queryFn: () => (dashboardApi as any).adv({ dateFrom: props.dateFrom, dateTo: props.dateTo }),
  initialData: [] as any,
})
const hasData = computed(() => ((rows.value as any[]) || []).length > 0)
const busy = computed(() => isLoading.value || isFetching.value)
watchEffect(() => { if (!busy.value) report('adv', hasData.value || !!isError.value) })

const sorted = computed(() => {
  const arr = [...(rows.value as any[])]
  if (sortKey.value === 'name') {
    arr.sort((a, b) => (sortDir.value === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)))
    return arr
  }
  if (sortKey.value === 'status') {
    arr.sort((a, b) => (sortDir.value === 'asc' ? a.status - b.status : b.status - a.status))
    return arr
  }
  const prio = (s: number) => (s === 9 ? 1 : s === 11 ? 2 : s === 7 ? 4 : s === 4 ? 5 : s === -1 ? 6 : 5)
  arr.sort((a, b) => prio(a.status) - prio(b.status) || a.name.localeCompare(b.name))
  return arr
})
const displayRows = computed(() => sorted.value.slice(0, shown.value))
const hasMore = computed(() => sorted.value.length > shown.value)
const sortBy = (k: 'name' | 'status') => {
  if (sortKey.value === k) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortKey.value = k; sortDir.value = 'asc' }
}

const fmt = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(v || 0))
const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0)
const ctr = (r: any) => (r.views ? (r.clicks / r.views * 100).toFixed(2) : '0.00')
const cr = (r: any) => (r.clicks ? (r.atbs / r.clicks * 100).toFixed(2) : '0.00')
const cpm = (r: any) => (r.views ? (r.sum / r.views * 1000).toFixed(2) : '0.00')
const cpc = (r: any) => (r.clicks ? (r.sum / r.clicks).toFixed(2) : '0.00')
const cpo = (r: any) => (r.orders ? (r.sum / r.orders).toFixed(2) : '0.00')

const statusMap: Record<string, string> = { '9': 'Активна', '7': 'Завершена', '11': 'Пауза', '8': 'Отклонена', '4': 'Готова', '-1': 'Удалена' }
const statusClassMap: Record<string, string> = {
  '9': 'badge--ok', '7': 'badge--neutral', '11': 'badge--warn',
  '8': 'badge--bad', '4': 'badge--info', '-1': 'badge--neutral',
}
const statusLabel = (s: number | string) => statusMap[String(s)] || String(s)
const statusClass = (s: number | string) => statusClassMap[String(s)] || 'badge--neutral'

const { fmtDate } = useDateFmt()
</script>
