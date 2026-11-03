<template>
  <div class="container-xxl page-feedback-tags">
    <WbWorkspaceHead :title="$route.meta.title || 'Разметка тегов отзывов'" :workspace-tabs="FEEDBACK_TABS" workspace-active="tags" />

    <p class="page-feedback-tags__hint">
      Теги подтягиваются из поля <code>bables</code> отзывов.
      <span v-if="syncResult" class="page-feedback-tags__ok">{{ syncResult }}</span>
    </p>

    <!-- Таблица тегов — блок темы .tbl-card (theme.md §5.7.9) -->
    <div class="tbl-card page-feedback-tags__card">
      <div class="card__hd">
        <span>Теги отзывов</span>
        <span class="spacer"></span>
        <!-- переключатель «неразмеченные / все» — чипы темы (§5.6.3) -->
        <WbChipGroup v-model="filt" :options="filterOptions" />
        <button type="button" class="hd-btn" :disabled="syncing" @click="onSync">
          <i class="bi bi-arrow-repeat me-1"></i>{{ syncing ? 'Синхронизация...' : 'Синхронизировать' }}
        </button>
      </div>

      <div v-if="isLoading" class="page-feedback-tags__loading">Загрузка данных…</div>
      <p v-else-if="!rows.length" class="page-feedback-tags__empty">
        {{ filt === 'unclassified' ? 'Все теги уже размечены 🎉' : 'Теги пока не собраны — нажмите «Синхронизировать».' }}
      </p>
      <div v-else class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="t-left">Тег</th>
              <th class="t-center">Встречается</th>
              <th class="t-center">Текущий статус</th>
              <th class="t-left">Отметить как</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in rows" :key="t.id">
              <td class="t-left">{{ t.tag_text }}</td>
              <td class="t-center">{{ t.usage_count }}</td>
              <td class="t-center"><span class="badge" :class="badgeClass(t.sentiment)">{{ labelOf(t.sentiment) }}</span></td>
              <td class="t-left">
                <span class="page-feedback-tags__actions">
                  <button class="btn btn--outline-ok btn-sm" :class="{ 'is-on': t.sentiment === 'positive' }"
                          @click="setSentiment(t, 'positive')">Позитивный</button>
                  <button class="btn btn--outline-bad btn-sm" :class="{ 'is-on': t.sentiment === 'negative' }"
                          @click="setSentiment(t, 'negative')">Негативный</button>
                  <button class="btn btn--secondary btn-sm"
                          @click="setSentiment(t, 'neutral')">Сбросить</button>
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
import WbChipGroup from '@/components/common/WbChipGroup.vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { FEEDBACK_TABS } from '@/components/common/workspaceTabs'

const route = useRoute()
const router = useRouter()
const filt = ref(String(route.query.filter || 'unclassified'))
const rows = ref<FeedbackTag[]>([])
const isLoading = ref(false)
const syncing = ref(false)
const syncResult = ref('')

/** Переключатель «неразмеченные / все теги» — чипы темы (§5.6.3). */
const filterOptions = [
  { value: 'unclassified', label: 'Только неразмеченные' },
  { value: 'all', label: 'Все теги' },
]

const LABELS: Record<string, string> = { positive: 'Позитивный', negative: 'Негативный', neutral: 'Не размечен' }

function labelOf(s: string) {
  return LABELS[s] || s
}
function badgeClass(s: string) {
  return s === 'positive' ? 'badge--ok' : s === 'negative' ? 'badge--bad' : 'badge--neutral'
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
/** Переключатель чипов меняет фильтр и перезагружает список. */
watch(filt, (f) => {
  router.replace({ path: '/wb-feedback-tags', query: f === 'all' ? { filter: 'all' } : {} })
  fetchData()
})
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
/* Смена фильтра в адресной строке («назад/вперёд», переход по ссылке) —
   обновляем чипы; сам список перезагружает watch(filt). */
watch(() => route.query.filter, (v) => {
  const next = String(v || 'unclassified')
  if (next !== filt.value) filt.value = next
})
</script>
