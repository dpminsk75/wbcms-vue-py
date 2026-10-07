<template>
  <div v-if="rows.length">
    <div class="card" style="border:1px solid var(--bs-border-color-translucent); border-radius:8px; background:#fff">
      <div class="card-header text-white d-flex justify-content-between align-items-center" style="font-size:13px; font-weight:700; background-color:#4b4b4b; padding:10px 15px">
        <span>Новости WB за последние 3 дня ({{ rows.length }})</span>
        <span class="d-flex gap-1 align-items-center">
          <button v-if="canSlide" class="btn btn-sm btn-light py-0 px-2" style="font-size:11px; font-weight:600" @click="slide(-1)" title="Назад">‹</button>
          <button v-if="canSlide" class="btn btn-sm btn-light py-0 px-2" style="font-size:11px; font-weight:600" @click="slide(1)" title="Вперёд">›</button>
          <router-link to="/news" class="btn btn-sm btn-light py-0 px-2" style="font-size:11px; font-weight:600; text-decoration:none">Все новости →</router-link>
        </span>
      </div>
      <div class="card-body p-3" style="background:#f8fafc">
        <div ref="trackRef" class="page-news-block__track" :class="{ 'page-news-block__track--drag': dragging }"
      @pointerdown="dragStart" @pointermove="dragMove" @pointerup="dragEnd" @pointerleave="dragEnd">
          <div v-for="r in rows" :key="r.id" class="page-news-block__card" :class="{ 'page-news-block__card--read': r.is_read }" @click="open(r)">
            <div class="page-news-block__date">{{ newsDate(r.date) }}</div>
            <div class="page-news-block__title" :title="r.header">{{ r.header }}</div>
            <div class="mt-1">
              <span v-for="t in r.types.slice(0, 2)" :key="t.id" class="badge border me-1" :class="{ 'text-bg-light': !newsBadgeStyle(t.name) }" :style="newsBadgeStyle(t.name)"><i v-if="newsBadgeIcon(t.name)" :class="newsBadgeIcon(t.name) + ' me-1'"></i>{{ t.name }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <NewsPopup :news="selected" @close="close()" />
  </div>
</template>

<script setup lang="ts">
import { ref, inject, onMounted, nextTick } from 'vue'
import NewsPopup from '../news/NewsPopup.vue'
import { newsBadgeStyle, newsBadgeIcon } from '../news/newsBadges'
import { newsApi, type NewsRow } from '../../api/news'

const rows = ref<NewsRow[]>([])
const selected = ref<NewsRow | null>(null)
const trackRef = ref<HTMLElement | null>(null)
const canSlide = ref(false)
const dragging = ref(false)
const dragged = ref(false)
let dragX = 0
let dragScroll = 0
const report = inject<(n: string, h: boolean) => void>('dashReport', () => {})

const MONTHS = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
function newsDate(iso: string | null): string {
  if (!iso) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return iso
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]}`
}

function open(r: NewsRow) {
  if (dragged.value) { dragged.value = false; return }  // был drag, не клик
  selected.value = r
}
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
function close() {
  if (selected.value) selected.value.is_read = true
  selected.value = null
}
function slide(dir: number) {
  const el = trackRef.value
  if (el) el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: 'smooth' })
}

onMounted(async () => {
  try {
    rows.value = await newsApi.feed(3, 12)
  } catch { rows.value = [] }
  report('news', rows.value.length > 0)
  await nextTick()
  const el = trackRef.value
  canSlide.value = !!el && el.scrollWidth > el.clientWidth + 8
})
</script>

<style scoped>
.page-news-block__track { display: flex; gap: 12px; overflow-x: auto; scrollbar-width: none; cursor: grab; }
.page-news-block__track::-webkit-scrollbar { display: none; }
.page-news-block__track--drag { cursor: grabbing; }
.page-news-block__track--drag .page-news-block__card { pointer-events: none; }
.page-news-block__card { flex: 0 0 calc(25% - 9px); min-width: 220px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.page-news-block__card:hover { border-color: #8A2BE0; }
.page-news-block__card--read { opacity: .62; }
.page-news-block__date { font-size: 12px; color: #6c757d; margin-bottom: 4px; }
.page-news-block__title { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-size: 14px; font-weight: 500; color: #2c3e50; }
@media (max-width: 1199px) { .page-news-block__card { flex-basis: calc(100%/3 - 8px); } }
@media (max-width: 767px) { .page-news-block__card { flex-basis: 82%; } }
</style>
