<template>
  <div class="container-xxl page-news">
    <h2 class="page-news__title">Новости WB</h2>
    <div class="row">
      <div class="col-md-3">
        <div class="card page-news__side">
          <div class="card-body">
            <div class="page-news__search">
              <input v-model="q" @keyup.enter="load" placeholder="Поиск новости" class="form-control form-control-sm" />
            </div>
            <div class="page-news__filters-title">Фильтры</div>
            <div class="page-news__pills">
              <button v-for="t in types" :key="t.id" type="button"
                :class="['page-news__pill', { 'page-news__pill--on': typeSel.includes(t.id) }]"
                @click="toggle(t.id)">{{ t.name }}</button>
            </div>
            <div class="page-news__dates">
              <WbDateInput v-model="dateFrom" input-class="form-control-sm" />
              <WbDateInput v-model="dateTo" input-class="form-control-sm" />
            </div>
            <div class="d-flex gap-2 mt-2">
              <button class="btn btn-sm btn-primary" @click="load">Применить</button>
              <button class="btn btn-sm btn-outline-secondary" @click="reset">Сбросить</button>
            </div>
          </div>
        </div>
      </div>
      <div class="col-md-9">
        <div v-if="error" class="wb-error">{{ error }}</div>
        <div v-if="loading" class="text-muted">Загрузка…</div>
        <div v-else-if="!rows.length" class="alert alert-info">Новостей нет.</div>
        <div v-else class="page-news__feed">
          <div v-for="r in rows" :key="r.id" class="card page-news__card" :class="{ 'page-news__card--read': r.is_read }" @click="open(r)">
            <div class="card-body">
              <div class="page-news__date">{{ newsDate(r.date) }}</div>
              <div class="page-news__head">{{ r.header }}</div>
              <div class="mt-1">
                <span v-for="t in r.types" :key="t.id" class="badge border me-1" :class="{ 'text-bg-light': !newsBadgeStyle(t.name) }" :style="newsBadgeStyle(t.name)"><i v-if="newsBadgeIcon(t.name)" :class="newsBadgeIcon(t.name) + ' me-1'"></i>{{ t.name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <NewsPopup :news="selected" @close="close()" />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-news.css'
import { ref, onMounted } from 'vue'
import NewsPopup from '../components/news/NewsPopup.vue'
import WbDateInput from '../components/common/WbDateInput.vue'
import { newsBadgeStyle, newsBadgeIcon } from '../components/news/newsBadges'
import { newsApi, type NewsRow, type NewsType } from '../api/news'

const rows = ref<NewsRow[]>([])
const types = ref<NewsType[]>([])
const typeSel = ref<number[]>([])
const dateFrom = ref('')
const dateTo = ref('')
const q = ref('')
const loading = ref(false)
const error = ref('')
const selected = ref<NewsRow | null>(null)

const MONTHS = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
function newsDate(iso: string | null): string {
  const m = iso ? /^(\d{4})-(\d{2})-(\d{2})/.exec(iso) : null
  if (!m) return iso || '—'
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`
}

function toggle(id: number) {
  typeSel.value = typeSel.value.includes(id)
    ? typeSel.value.filter((x) => x !== id)
    : [...typeSel.value, id]
  load()
}
function open(r: NewsRow) { selected.value = r }
function close() {
  if (selected.value) selected.value.is_read = true
  selected.value = null
}
function reset() {
  dateFrom.value = ''
  dateTo.value = ''
  typeSel.value = []
  q.value = ''
  load()
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await newsApi.all({
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      types: typeSel.value.length ? typeSel.value.join(',') : undefined,
      q: q.value.trim() || undefined,
    })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try { types.value = await newsApi.types() } catch { types.value = [] }
  load()
})
</script>
