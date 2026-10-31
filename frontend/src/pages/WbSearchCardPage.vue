<template>
  <div class="container-xxl page-wb-search-card">
    <div class="row mb-3">
      <PageHeaderWidget
        v-if="cardInfo"
        :title="cardInfo.title || `Арт ${filters.nm_id}`"
        :nm-id="cardInfo.nmID"
      />
      <h1 v-else class="page-title">Анализ поисковых фраз для карточки</h1>
    </div>

    <!-- Фильтр: общий WbUniversalFilter (пресеты дат + быстрый выбор карточки + «Применить/Сбросить»),
         выбор карточки — в слоте #fields (общий WbCardSelect). -->
    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:product="filters.nm_id"
      :show-product="false"
      :show-brand-category="false"
      :show-quick="true"
      @apply="onApply"
      @reset="onReset"
    >
      <template #fields>
        <div class="wb-field wb-field--wide">
          <label class="wb-field__label">Карточка WB (артикул или название)</label>
          <WbCardSelect v-model:nm-id="filters.nm_id" placeholder="Выберите артикул..." />
        </div>
      </template>
    </WbUniversalFilter>

    <div class="row page-wb-search-card__grid mb-5">
      <div class="col-md-12">
        <PhrasesMatrix :rows="models" :dates="uniqueDates" :is-loading="isLoading" :show-excel="true" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-wb-search-card.css'
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WbUniversalFilter from '@/components/common/WbUniversalFilter.vue'
import WbCardSelect from '@/components/common/WbCardSelect.vue'
import PageHeaderWidget from '@/components/common/PageHeaderWidget.vue'
import PhrasesMatrix from '@/components/common/PhrasesMatrix.vue'
import { wbSearchApi } from '@/api/search'

const route = useRoute()
const router = useRouter()

const today = new Date()
const defTo = today.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 30 * 864e5).toISOString().slice(0, 10)

const filters = reactive({
  nm_id: String(route.query.nm_id || ''),
  date_from: String(route.query.date_from || defFrom),
  date_to: String(route.query.date_to || defTo),
})

const models = ref<any[]>([])
const uniqueDates = ref<string[]>([])
const cardInfo = ref<{ nmID: number; title: string } | null>(null)
const isLoading = ref(false)
const error = ref('')

async function fetchData() {
  if (!filters.nm_id) {
    models.value = []
    uniqueDates.value = []
    cardInfo.value = null
    return
  }
  isLoading.value = true
  error.value = ''
  try {
    const data = await wbSearchApi.card(filters.nm_id, filters.date_from, filters.date_to)
    models.value = data.models || []
    uniqueDates.value = data.uniqueDates || []
    cardInfo.value = data.cardInfo
    document.title = 'Анализ поисковых фраз для карточки'
  } catch {
    error.value = 'load'
    models.value = []
  } finally {
    isLoading.value = false
  }
}

function syncRoute() {
  router.replace({
    path: '/wb-search/card',
    query: { nm_id: filters.nm_id || undefined, date_from: filters.date_from, date_to: filters.date_to },
  })
}

function onApply() {
  syncRoute()
  fetchData()
}

function onReset() {
  filters.nm_id = ''
  filters.date_from = defFrom
  filters.date_to = defTo
  syncRoute()
  fetchData()
}

onMounted(fetchData)

watch(() => route.query.nm_id, (v) => {
  if (v && String(v) !== filters.nm_id) {
    filters.nm_id = String(v)
    fetchData()
  }
})
</script>
