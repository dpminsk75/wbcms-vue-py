<template>
  <div class="container-xxl page-news">
    <h1 class="page-title">Новости WB</h1>
    <div class="row">
      <!-- Фильтры: панель темы (.wb-panel), поле — .wb-field/.wb-input,
           даты — общий WbDateRangeFilter (bare),
           кнопки — внизу панели слева (.wb-filter-panel__btns). -->
      <div class="col-md-3">
        <div class="wb-panel page-news__side">
          <div class="wb-panel__bd">
            <div class="wb-field page-news__search">
              <label class="wb-field__label" for="news-search">Поиск</label>
              <input
                id="news-search"
                v-model="q"
                class="wb-input"
                placeholder="Заголовок новости"
                @keyup.enter="load"
              />
            </div>
            <div class="page-news__dates">
              <WbDateRangeFilter v-model:from="dateFrom" v-model:to="dateTo" bare />
            </div>
            <div class="wb-filter-panel__btns">
              <button class="btn btn--brand" @click="load">Применить</button>
              <button class="btn btn--outline" @click="reset">Сбросить</button>
            </div>
          </div>
        </div>
      </div>
      <div class="col-md-9">
        <!-- Типы новостей — общие чипы темы (.opt), в широкой колонке над лентой:
             в сайдбаре чипы ложились бы в 3+ ряда. Применяются сразу. -->
        <div class="wb-field page-news__types">
          <span class="wb-field__label">Тип</span>
          <WbChipGroup v-model="typeSel" :options="typeOptions" multiple @update:model-value="load" />
        </div>
        <div v-if="error" class="wb-error">{{ error }}</div>
        <div v-if="loading" class="text-muted">Загрузка…</div>
        <div v-else-if="!rows.length" class="wb-panel">
          <div class="wb-panel__bd text-muted">Новостей нет.</div>
        </div>
        <div v-else class="page-news__feed">
          <div v-for="r in rows" :key="r.id" class="wb-panel page-news__card" :class="{ 'page-news__card--read': r.is_read }" @click="open(r)">
            <div class="wb-panel__bd">
              <div class="page-news__date">{{ newsDate(r.date) }}</div>
              <div class="page-news__head">{{ r.header }}</div>
              <div class="mt-1">
                <span v-for="t in r.types" :key="t.id" class="badge me-1" :class="newsBadgeClass(t.name)"><i v-if="newsBadgeIcon(t.name)" :class="newsBadgeIcon(t.name) + ' me-1'"></i>{{ t.name }}</span>
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
import { ref, computed, onMounted } from 'vue'
import NewsPopup from '../components/news/NewsPopup.vue'
import WbDateRangeFilter from '../components/common/WbDateRangeFilter.vue'
import WbChipGroup from '../components/common/WbChipGroup.vue'
import { newsBadgeClass, newsBadgeIcon } from '../components/news/newsBadges'
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

/** Типы новостей — варианты для общих чипов темы (.opt), множественный выбор. */
const typeOptions = computed(() => types.value.map((t) => ({ value: t.id, label: t.name })))

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
