<template>
  <div class="container-xxl page-feedback-tags">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="page-title mb-0">{{ $route.meta.title || 'Разметка тегов отзывов' }}</h1>
      <button class="btn btn-outline-secondary btn-sm" :disabled="syncing" @click="onSync">
        <i class="bi bi-arrow-repeat me-1"></i>{{ syncing ? 'Синхронизация...' : 'Синхронизировать' }}
      </button>
    </div>

    <p class="text-muted page-feedback-tags__hint">
      Теги подтягиваются из поля <code>bables</code> отзывов.
      <span v-if="syncResult" class="ms-2 text-success">{{ syncResult }}</span>
    </p>

    <div class="mb-3 d-flex gap-2">
      <button class="btn btn-sm" :class="filt === 'unclassified' ? 'btn-primary' : 'btn-outline-primary'" @click="setFilter('unclassified')">Только неразмеченные</button>
      <button class="btn btn-sm" :class="filt === 'all' ? 'btn-primary' : 'btn-outline-primary'" @click="setFilter('all')">Все теги</button>
    </div>

    <div v-if="isLoading" class="text-center p-5">
      <div class="spinner-border text-primary" role="status"></div>
      <div class="mt-2 text-muted">Загрузка данных...</div>
    </div>
    <p v-else-if="!rows.length" class="text-muted">{{ filt === 'unclassified' ? 'Все теги уже размечены 🎉' : 'Теги пока не собраны — нажмите «Синхронизировать».' }}</p>
    <div v-else class="card">
      <div class="page-feedback-tags__table-wrap wb-table-wrap">
        <table class="table table-striped table-bordered align-middle mb-0">
          <thead>
            <tr>
              <th>Тег</th>
              <th>Встречается</th>
              <th>Текущий статус</th>
              <th>Отметить как</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in rows" :key="t.id">
              <td>{{ t.tag_text }}</td>
              <td>{{ t.usage_count }}</td>
              <td><span class="badge" :class="badgeClass(t.sentiment)">{{ labelOf(t.sentiment) }}</span></td>
              <td>
                <span class="page-feedback-tags__actions">
                  <button class="btn btn-sm" :class="t.sentiment === 'positive' ? 'btn-success' : 'btn-outline-success'" @click="setSentiment(t, 'positive')">Позитивный</button>
                  <button class="btn btn-sm" :class="t.sentiment === 'negative' ? 'btn-danger' : 'btn-outline-danger'" @click="setSentiment(t, 'negative')">Негативный</button>
                  <button class="btn btn-sm" :class="t.sentiment === 'neutral' ? 'btn-secondary' : 'btn-outline-secondary'" @click="setSentiment(t, 'neutral')">Сбросить</button>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-feedback-tags.css'
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { feedbackApi, type FeedbackTag } from '@/api/feedback'

const route = useRoute()
const router = useRouter()
const filt = ref(String(route.query.filter || 'unclassified'))
const rows = ref<FeedbackTag[]>([])
const isLoading = ref(false)
const syncing = ref(false)
const syncResult = ref('')

const LABELS: Record<string, string> = { positive: 'Позитивный', negative: 'Негативный', neutral: 'Не размечен' }

function labelOf(s: string) {
  return LABELS[s] || s
}
function badgeClass(s: string) {
  return s === 'positive' ? 'bg-success' : s === 'negative' ? 'bg-danger' : 'bg-secondary'
}

async function fetchData() {
  isLoading.value = true
  try {
    rows.value = await feedbackApi.tags(filt.value)
  } catch {
    rows.value = []
  } finally {
    isLoading.value = false
  }
}
function setFilter(f: string) {
  filt.value = f
  router.replace({ path: '/wb-feedback-tags', query: f === 'all' ? { filter: 'all' } : {} })
  fetchData()
}
async function setSentiment(t: FeedbackTag, s: string) {
  try {
    await feedbackApi.setSentiment(t.id, s)
    t.sentiment = s
    if (filt.value === 'unclassified' && s !== 'neutral') {
      rows.value = rows.value.filter((x) => x.id !== t.id)
    }
  } catch (e: any) {
    alert(e?.response?.data?.detail || String(e))
  }
}
async function onSync() {
  syncing.value = true
  syncResult.value = ''
  try {
    const r = await feedbackApi.syncTags()
    syncResult.value = `Строк: ${r.rows_scanned}, уникальных: ${r.unique_tags}, новых: ${r.new_tags}, обновлено: ${r.updated_tags}`
    await fetchData()
  } catch (e: any) {
    alert(e?.response?.data?.detail || String(e))
  } finally {
    syncing.value = false
  }
}

onMounted(fetchData)
watch(() => route.query.filter, (v) => {
  filt.value = String(v || 'unclassified')
  fetchData()
})
</script>
