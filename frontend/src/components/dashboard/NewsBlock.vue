<template>
  <div v-if="rows.length" class="page-news-min">
    <div class="page-news-min__head">
      <router-link to="/news" class="page-news-min__title">Новости ({{ rows.length }})</router-link>
    </div>
    <div ref="trackRef" class="page-news-min__track"
      @pointerdown="dragStart" @pointermove="dragMove" @pointerup="dragEnd" @pointerleave="dragEnd">
      <div v-for="r in rows" :key="r.id" class="page-news-min__item" :class="{ 'page-news-min__item--read': r.is_read }" @click="open(r)" title="Нажмите, чтобы открыть новость">
        <div class="page-news-min__date">{{ newsDate(r.date) }}</div>
        <div class="page-news-min__name" :title="r.header">{{ r.header }}</div>
        <div class="mt-1">
          <span v-for="t in r.types.slice(0, 2)" :key="t.id" class="badge border me-1" :class="{ 'text-bg-light': !newsBadgeStyle(t.name) }" :style="newsBadgeStyle(t.name)"><i v-if="newsBadgeIcon(t.name)" :class="newsBadgeIcon(t.name) + ' me-1'"></i>{{ t.name }}</span>
        </div>
      </div>
    </div>
    <NewsPopup :news="selected" @close="close()" />
  </div>
</template>

<script setup lang="ts">
import { ref, inject, onMounted } from 'vue'
import NewsPopup from '../news/NewsPopup.vue'
import { newsBadgeStyle, newsBadgeIcon } from '../news/newsBadges'
import { newsApi, type NewsRow } from '../../api/news'

const rows = ref<NewsRow[]>([])
const selected = ref<NewsRow | null>(null)
const trackRef = ref<HTMLElement | null>(null)
const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})

const MONTHS = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
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
let dragX = 0
let dragScroll = 0
function dragStart(e: PointerEvent) {
  const el = trackRef.value
  if (!el) return
  dragging.value = true
  dragged.value = false
  dragX = e.clientX
  dragScroll = el.scrollLeft
  el.setPointerCapture?.(e.pointerId)
}
function dragMove(e: PointerEvent) {
  const el = trackRef.value
  if (!dragging.value || !el) return
  const dx = e.clientX - dragX
  if (Math.abs(dx) > 5) dragged.value = true
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

<style scoped>
.page-news-min__head { margin-bottom: 8px; }
.page-news-min__title { font-size: 20px; font-weight: 700; color: #111827; text-decoration: none; }
.page-news-min__title:hover { color: #8A2BE0; }
.page-news-min__track { display: flex; gap: 24px; overflow-x: auto; scrollbar-width: none; cursor: grab; padding-bottom: 4px; }
.page-news-min__track::-webkit-scrollbar { display: none; }
.page-news-min__item { flex: 0 0 300px; cursor: pointer; background: #fff; border: 1px solid #d3d9e0; border-radius: 12px; padding: 12px 14px; box-shadow: 0 1px 4px rgba(16,24,40,.08); }
.page-news-min__item:hover { border-color: #8A2BE0; }
.page-news-min__item--read { opacity: .62; }
.page-news-min__date { font-size: 12px; color: #6c757d; margin-bottom: 4px; }
.page-news-min__name { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; font-size: 15px; font-weight: 600; color: #111827; }
</style>
