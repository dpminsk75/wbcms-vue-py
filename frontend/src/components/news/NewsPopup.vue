<template>
  <div v-if="news" class="wb-modal-backdrop news-popup" @click.self="$emit('close')">
    <div class="wb-modal-box news-popup__card" role="dialog" aria-modal="true" :aria-label="news.header">
      <div class="d-flex justify-content-between align-items-start gap-2">
        <h4 class="fw-bold mb-1">{{ news.header }}</h4>
        <button class="btn btn--ghost btn-sm" @click="$emit('close')" title="Закрыть"><i class="bi bi-x-lg"></i></button>
      </div>
      <div class="text-muted mb-2">{{ newsDate(news.date) }}</div>
      <div class="news-popup__body">
        <template v-for="(b, i) in blocks" :key="i">
          <ul v-if="b.t === 'ul'" class="news-popup__ul">
            <li v-for="(it, j) in b.items" :key="j"><template v-for="(p, k) in it" :key="k"><a v-if="p.t === 'a'" :href="p.s" target="_blank" rel="noopener">{{ p.s }}</a><template v-else>{{ p.s }}</template></template></li>
          </ul>
          <p v-else class="news-popup__p"><template v-for="(p, k) in b.parts" :key="k"><a v-if="p.t === 'a'" :href="p.s" target="_blank" rel="noopener">{{ p.s }}</a><template v-else>{{ p.s }}</template></template></p>
        </template>
      </div>
      <div class="mt-2 d-flex justify-content-between align-items-center flex-wrap gap-2">
        <div>
          <span v-for="t in news.types" :key="t.id" class="badge me-1" :class="newsBadgeClass(t.name)"><i v-if="newsBadgeIcon(t.name)" :class="newsBadgeIcon(t.name) + ' me-1'"></i>{{ t.name }}</span>
        </div>
        <a :href="`https://seller.wildberries.ru/news-v2/news-details?id=${news.id}`" target="_blank" rel="noopener" class="btn btn--outline btn-sm">Читать в WB Partners <i class="bi bi-box-arrow-up-right"></i></a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { newsApi, type NewsRow } from '../../api/news'
import { newsBadgeClass, newsBadgeIcon } from './newsBadges'

const props = defineProps<{ news: NewsRow | null }>()
defineEmits<{ close: [] }>()

const MONTHS = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
function newsDate(iso: string | null): string {
  const m = iso ? /^(\d{4})-(\d{2})-(\d{2})/.exec(iso) : null
  if (!m) return iso || '—'
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`
}

interface Part { t: 't' | 'a'; s: string }
function inline(s: string): Part[] {
  const out: Part[] = []
  const re = /(https?:\/\/\S+)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(s))) {
    if (m.index > last) out.push({ t: 't', s: s.slice(last, m.index) })
    out.push({ t: 'a', s: m[1] })
    last = m.index + m[1].length
  }
  if (last < s.length) out.push({ t: 't', s: s.slice(last) })
  return out.length ? out : [{ t: 't', s }]
}

const MARKER = /Что (изменилось|нового|добавили)[\s:]/

const blocks = computed(() => {
  const raw = (props.news?.content || '').replace(MARKER, '\n$&')
  const lines = raw.split('\n')
  const out: Array<{ t: 'p'; parts: Part[] } | { t: 'ul'; items: Part[][] }> = []
  let ul: Part[][] | null = null
  const flush = () => { if (ul) { out.push({ t: 'ul', items: ul }); ul = null } }
  for (const raw of lines) {
    const s = raw.trim()
    if (!s) { flush(); continue }
    const bull = /^[•\-–—]\s+(.*)$/.exec(s)
    if (bull) {
      if (!ul) ul = []
      ul.push(inline(bull[1]))
    } else {
      flush()
      out.push({ t: 'p', parts: inline(s) })
    }
  }
  flush()
  return out
})

watch(() => props.news?.id, (id) => {
  if (id) newsApi.markRead(id).catch(() => {})
}, { immediate: true })
</script>

<style scoped>
/* Каркас модалки — общий темы (.wb-modal-backdrop + .wb-modal-box). */
.news-popup { align-items: flex-start; padding: 8vh 16px 16px; }
.news-popup__card { max-width: 720px; width: 100%; max-height: 84vh; overflow: auto; }
.news-popup__body { font-size: calc(13px * var(--fs)); line-height: 1.7; color: var(--ink); }
.news-popup__p { margin: 0 0 14px; }
.news-popup__ul { margin: 0 0 14px; padding-left: 20px; }
.news-popup__ul li { margin-bottom: 6px; }
</style>
