<template>
  <section v-if="busy || hasData || isError" class="tbl-card" data-head="wb">
    <div class="card__hd">
      <span>Сумма заказов за последние 30 дней</span>
      <span class="spacer"></span>
      <span class="hd-badge">{{ list.length }} каналов</span>
    </div>
    <div v-if="isLoading" class="dsp__empty">Загрузка…</div>
    <div v-else class="tbl-wrap">
      <table class="tbl dsp-tbl">
        <thead>
          <tr>
            <th class="t-left">Показатель</th>
            <th class="t-right num">Вчера</th>
            <th class="t-right num">Позавчера</th>
            <th class="t-right num">Прошедшие 7 дней</th>
            <th class="t-right num">Предыдущая неделя</th>
            <th class="t-right num">Прошедшие 30 дней</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in list" :key="r.price_type">
            <td class="t-left" style="font-weight: 600">{{ r.price_type }}</td>
            <td class="num">{{ fmt2(r.ieri) }}</td>
            <td class="num">{{ fmt2(r.pazyera) }}</td>
            <td class="num">{{ fmt2(r.past_7_days) }}</td>
            <td class="num" style="color: var(--ink-muted)">{{ fmt2(r.week_before) }}</td>
            <td class="num" style="font-weight: 600">{{ fmt2(r.past_30_days) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td class="t-left">Итого</td>
            <td class="num">{{ fmt2(total('ieri')) }}</td>
            <td class="num">{{ fmt2(total('pazyera')) }}</td>
            <td class="num">{{ fmt2(total('past_7_days')) }}</td>
            <td class="num">{{ fmt2(total('week_before')) }}</td>
            <td class="num">{{ fmt2(total('past_30_days')) }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
/** Сумма заказов (черновик) — таблица темы вместо dashboard/OrdersSummary.vue. */
import { computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const { data: rows, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => ['orders-summary', auth.companyId] as const),
  queryFn: dashboardApi.ordersSummary as any,
  initialData: [] as any,
})
/* UNION всегда возвращает 4 строки — пусто значит все нули */
const list = computed(() => (rows.value as any[]) || [])
const hasData = computed(() => list.value.some((r: any) =>
  ['ieri', 'pazyera', 'past_7_days', 'week_before', 'past_30_days'].some((k) => Number(r?.[k]) !== 0)))
const busy = computed(() => isLoading.value || isFetching.value)
const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})
watchEffect(() => { if (!busy.value) report('orders-summary', hasData.value || !!isError.value) })

const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0)
const total = (key: string) => list.value.reduce((s, r) => s + (Number(r?.[key]) || 0), 0)
</script>
