<template>
  <section v-if="busy || hasData || isError" class="dsp-cards">
    <div class="dsp-cards__head">
      <router-link to="/site/new-cards" class="dsp-cards__title">Новые карточки ({{ rows.length }})</router-link>
    </div>
    <div v-if="isLoading" class="dsp__empty">Загрузка...</div>
    <div v-else-if="rows.length === 0" class="dsp__empty">Новинок нет</div>
    <div
      v-else ref="trackRef" class="dsp-cards__track"
      @pointerdown="dragStart" @pointermove="dragMove" @pointerup="dragEnd" @pointercancel="dragEnd" @pointerleave="dragEnd"
    >
      <div v-for="c in rows" :key="c.nmID" class="dsp-cards__item">
        <div class="dsp-cards__card">
          <div class="dsp-cards__img">
            <CardPhoto :src="c.photos" :alt="c.title || ''" fit="cover" />
          </div>
          <div class="dsp-cards__text">
            <div class="dsp-cards__name" :title="c.title || 'Без названия'">{{ c.title || 'Без названия' }}</div>
            <div class="dsp-cards__sub" :title="c.brand || '—'">Журналы · {{ c.brand || '—' }}</div>
            <div class="dsp-cards__row">Арт WB: <a :href="'/wb/detail?DPFilterForm[nm_id]=' + c.nmID" target="_blank">{{ c.nmID }}</a></div>
            <div class="dsp-cards__row" :title="c.vendorCode || '—'">Арт прод: {{ c.vendorCode || '—' }}</div>
            <div class="dsp-cards__date">Добавлена: {{ fmtDate(c.created_at) }}</div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * Новые карточки (черновик) — блок темы вместо dashboard/NewCards.vue.
 * Дизайн блока сохранён боевой (две строки карточек, фото слева 80×110, текст
 * справа) — переведены только цвета/радиусы/тени на токены темы.
 */
import { ref, computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
import { useDateFmt } from '../../composables/useDateFmt'
import CardPhoto from '../common/CardPhoto.vue'

const auth = useAuthStore()
const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})
const { data: rowsRaw, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => ['new-cards', auth.companyId] as const),
  queryFn: () => (dashboardApi as any).newCards({}),
  initialData: [] as any,
})
const busy = computed(() => isLoading.value || isFetching.value)
const rows = computed(() => {
  const v = rowsRaw.value as any
  if (Array.isArray(v)) return v
  return v?.items ?? []
})
const hasData = computed(() => rows.value.length > 0)
watchEffect(() => { if (!busy.value) report('new-cards', hasData.value || !!isError.value) })

const { fmtDate } = useDateFmt()

const trackRef = ref<HTMLElement | null>(null)
const DRAG_THRESHOLD = 6
let dragOn = false
let dragged = false
let dragX = 0
let dragScroll = 0
function dragStart(e: PointerEvent) {
  const el = trackRef.value
  if (!el) return
  dragOn = true
  dragged = false
  dragX = e.clientX
  dragScroll = el.scrollLeft
}
function dragMove(e: PointerEvent) {
  const el = trackRef.value
  if (!dragOn || !el) return
  const dx = e.clientX - dragX
  if (!dragged) {
    if (Math.abs(dx) <= DRAG_THRESHOLD) return
    dragged = true
    el.setPointerCapture?.(e.pointerId)
  }
  el.scrollLeft = dragScroll - dx
}
function dragEnd() {
  dragOn = false
}
</script>
