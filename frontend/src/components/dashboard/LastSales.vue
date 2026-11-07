<template>
  <section v-if="busy || hasData || isError" class="tbl-card">
    <div class="card__hd">
      <span>Продажи (с {{ fmtDate(dateFrom) }})</span>
      <a class="hd-btn" :href="'/wb-order/feed-aggregated?DPFilterForm%5Bdate_from%5D=' + dateFrom + '&DPFilterForm%5Bdate_to%5D=' + dateTo" target="_blank" title="Сводка по товарам">
        <i class="bi bi-graph-up"></i> Сводка по товарам
      </a>
      <span class="spacer"></span>
      <span class="hd-badge">Показаны 1-{{ displayRows.length }} из {{ totalItems }}</span>
    </div>
    <div v-if="isLoading" class="dsp__empty">Загрузка…</div>
    <div v-else class="tbl-wrap">
      <table class="tbl dsp-tbl">
        <thead>
          <tr>
            <th class="t-left">Товар / Артикул</th>
            <th class="t-center num">Кол-во</th>
            <th class="t-right num">Σ в РЦ</th>
            <th class="t-right num">Σ к опл</th>
            <th class="t-right num">Σ WB нам</th>
            <th class="t-right num">Цена</th>
            <th class="t-right num">СПП, %</th>
            <th class="t-right num">Цена пр.</th>
            <th class="t-right num">К опл</th>
          </tr>
        </thead>
        <tbody>
          <tr class="tbl__total tbl__total--top">
            <td class="t-left dsp-tbl__sum">Итого {{ totalCnt }} пр | Σ в РЦ: {{ fmt1(totalPwd) }} | Σ прод: {{ fmt1(totalFp) }} | WB нам: {{ fmt1(totalForpay) }}</td>
            <td class="t-center num">{{ totalCnt }}</td>
            <td class="num">{{ fmt1(totalPwd) }}</td>
            <td class="num">{{ fmt0(totalFp) }}</td>
            <td class="num">{{ fmt0(totalForpay) }}</td>
            <td class="num"></td>
            <td class="num"></td>
            <td class="num"></td>
            <td class="num"></td>
          </tr>
          <tr v-for="r in displayRows" :key="r.nm_id">
            <td class="t-left">
              <ProductCell
                compact copy-nm copy-link :photo="r.photos" :title="r.title" :sub="'Артикул: ' + (r.vendorCode || '—')"
                :link="wbLink(r.nm_id)" :link-label="'WB: ' + r.nm_id" :nm-id="r.nm_id"
              />
            </td>
            <td class="t-center num">
              <b>{{ r.cnt }}</b><br>
              <span class="dsp-metric__qty">{{ r.cnt_3 }} | {{ r.cnt_2 }} | {{ r.cnt_1 }} | {{ r.cnt_0 }}</span>
            </td>
            <td class="num">{{ fmt1(r.pwd) }}</td>
            <td class="num">{{ fmt0(r.fp) }}</td>
            <td class="num">{{ fmt0(r.forpay) }}</td>
            <td class="num">{{ Math.round(r.apwd || 0).toLocaleString('ru-RU') }}</td>
            <td class="num">{{ (r.aspp || 0).toFixed(1) }}</td>
            <td class="num">{{ Math.round(r.afp || 0).toLocaleString('ru-RU') }}</td>
            <td class="num" style="font-weight: 700">{{ Math.round(r.aforpay || 0).toLocaleString('ru-RU') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="wb-pager">
      <button v-if="hasMore" class="btn btn--outline btn-sm" @click="shown += 10">Увидеть больше</button>
      <span class="wb-pager__label">Показаны <b>{{ displayRows.length }}</b> из <b>{{ totalItems }}</b> записей.</span>
    </div>
  </section>
</template>

<script setup lang="ts">
/** Продажи (черновик) — таблица темы вместо dashboard/LastSales.vue. */
import { ref, computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import { useDateFmt } from '../../composables/useDateFmt'
import ProductCell from '../common/ProductCell.vue'

const props = defineProps<{ dateFrom: string, dateTo: string }>()
const auth = useAuthStore()
const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})
/** Показываем порциями: сначала 5 строк, «Увидеть больше» добавляет по 10. */
const shown = ref(5)

const { data: raw, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => ['last-sales', props.dateFrom, props.dateTo, auth.companyId] as const),
  queryFn: () => (dashboardApi as any).lastSales({ dateFrom: props.dateFrom, dateTo: props.dateTo }),
  initialData: { items: [], totals: { cnt: 0, pwd: 0, fp: 0, forpay: 0 } } as any,
})
const busy = computed(() => isLoading.value || isFetching.value)
const items = computed(() => (Array.isArray(raw.value) ? (raw.value as any[]) : ((raw.value?.items as any[]) ?? [])))
const totals = computed(() => (Array.isArray(raw.value) ? null : ((raw.value?.totals as any) ?? null)))
const displayRows = computed(() => items.value.slice(0, shown.value))
const hasMore = computed(() => items.value.length > shown.value)
const totalCnt = computed(() => (totals.value ? totals.value.cnt : items.value.reduce((s: number, r: any) => s + (r.cnt || 0), 0)))
const totalPwd = computed(() => (totals.value ? totals.value.pwd : items.value.reduce((s: number, r: any) => s + (r.pwd || 0), 0)))
const totalFp = computed(() => (totals.value ? totals.value.fp : items.value.reduce((s: number, r: any) => s + (r.fp || 0), 0)))
const totalForpay = computed(() => (totals.value ? totals.value.forpay : items.value.reduce((s: number, r: any) => s + (r.forpay || 0), 0)))
const totalItems = computed(() => items.value.length)
const hasData = computed(() => items.value.length > 0 || (totals.value?.cnt || 0) > 0)
watchEffect(() => { if (!busy.value) report('last-sales', hasData.value || !!isError.value) })

const fmt1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v || 0)
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(v || 0))
const wbLink = (nmId: number | string) => `https://www.wildberries.ru/catalog/${nmId}/detail.aspx`

const { fmtDate } = useDateFmt()
</script>
