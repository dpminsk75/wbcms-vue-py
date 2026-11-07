<template>
  <section v-if="rows.length" class="dsp-news">
    <div class="dsp-news__head">
      <router-link to="/news" class="dsp-news__title">Новости ({{ rows.length }})</router-link>
    </div>
    <div
      ref="trackRef" class="dsp-news__track"
      @pointerdown="dragStart" @pointermove="dragMove" @pointerup="dragEnd" @pointercancel="dragEnd" @pointerleave="dragEnd"
    >
      <div
        v-for="r in rows" :key="r.id" class="dsp-news__item"
        :style="r.is_read ? 'opacity:.62' : ''" @click="open(r)" title="Нажмите, чтобы открыть новость"
      >
        <div class="dsp-news__date">{{ newsDate(r.date) }}</div>
        <div class="dsp-news__name" :title="r.header">{{ r.header }}</div>
        <div style="margin-top: 7px">
          <span v-for="t in r.types.slice(0, 2)" :key="t.id" class="badge me-1" :class="newsBadgeClass(t.name)">
            <i v-if="newsBadgeIcon(t.name)" :class="newsBadgeIcon(t.name) + ' me-1'"></i>{{ t.name }}
          </span>
        </div>
      </div>
    </div>
    <NewsPopup :news="selected" @close="close()" />
  </section>
</template>

<script setup lang="ts">
/**
 * Новости (черновик) — блок темы вместо dashboard/NewsBlock.vue.
 * Дизайн блока сохранён боевой (заголовок-ссылка + рельс карточек, без панели
 * с тёмной шапкой) — переведены только цвета/радиусы/тени на токены темы.
 */
import { ref, inject, onMounted } from 'vue'
import NewsPopup from '../news/NewsPopup.vue'
import { newsBadgeClass, newsBadgeIcon } from '../news/newsBadges'
import { newsApi, type NewsRow } from '../../api/news'

const rows = ref<NewsRow[]>([])
const selected = ref<NewsRow | null>(null)
const trackRef = ref<HTMLElement | null>(null)
const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})

const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
function newsDate(iso: string | null): string {
  const m = iso ? /^(\d{4})-(\d{2})-(\d{2})/.exec(iso) : null
  if (!m) return iso || '—'
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]}`
}

function open(r: NewsRow) {
  if (dragged.value) { dragged.value = false; return }
  selected.value = r
}
function close() {
  if (selected.value) selected.value.is_read = true
  selected.value = null
}

const dragging = ref(false)
const dragged = ref(false)
const DRAG_THRESHOLD = 6
let dragX = 0
let dragScroll = 0
function dragStart(e: PointerEvent) {
  const el = trackRef.value
  if (!el) return
  dragging.value = true
  dragged.value = false
  dragX = e.clientX
  dragScroll = el.scrollLeft
}
function dragMove(e: PointerEvent) {
  const el = trackRef.value
  if (!dragging.value || !el) return
  const dx = e.clientX - dragX
  if (!dragged.value) {
    if (Math.abs(dx) <= DRAG_THRESHOLD) return
    dragged.value = true
    el.setPointerCapture?.(e.pointerId)
  }
  el.scrollLeft = dragScroll - dx
}
function dragEnd() {
  dragging.value = false
}

onMounted(async () => {
  try {
    rows.value = await newsApi.feed(3, 12)
  } catch { rows.value = [] }
  report('news', rows.value.length > 0)
})
</script>
