<template>
  <div class="container-xxl page-competitor">
    <h2 class="page-competitor__title">Конкуренты — анализ</h2>
    <p class="text-muted">Товары, по которым собраны данные конкурентов. Выберите товар для анализа.</p>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="loading" class="text-muted">Загрузка…</div>

    <div v-if="!loading && !rows.length" class="alert alert-info">Нет данных о конкурентах.</div>
    <table v-else class="wb-admin-table page-competitor__grid">
      <thead>
        <tr>
          <th class="page-competitor__col-product">Товар</th>
          <th>Бренд</th>
          <th class="text-center page-competitor__col-num" title="Уникальных конкурентов в выдаче по всем фразам">Конкуренты</th>
          <th class="text-center page-competitor__col-num" title="Поисковых фраз, по которым собраны конкуренты">Фразы</th>
          <th class="text-center page-competitor__col-num" title="Конкурентов с готовым AI-разбором">Разобрано</th>
          <th class="page-competitor__col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.source_nm_id">
          <td>
            <div class="page-competitor__product">
              <img :src="r.photo || '/images/no-photo.png'" alt="" class="page-competitor__thumb" />
              <div class="page-competitor__product-text">
                <div class="page-competitor__product-title" :title="r.title || ''">{{ r.title || '—' }}</div>
                <div class="page-competitor__product-sub">
                  <a :href="`/wb/detail?nm_id=${r.source_nm_id}`" target="_blank" class="page-competitor__wb-link" :title="`Открыть карточку ${r.source_nm_id}`">WB: {{ r.source_nm_id }}</a>
                  <span v-if="r.vendor_code"> · {{ r.vendor_code }}</span>
                </div>
              </div>
            </div>
          </td>
          <td>{{ r.brand || '—' }}</td>
          <td class="text-center"><span class="badge bg-primary" :title="`${r.cnt} конкурентов в выдаче`">{{ r.cnt }}</span></td>
          <td class="text-center"><span class="badge bg-secondary" :title="`${r.phrases} поисковых фраз`">{{ r.phrases }}</span></td>
          <td class="text-center">
            <span v-if="r.analyzed" class="badge bg-success" :title="`${r.analyzed} с готовым AI-разбором`">{{ r.analyzed }}</span>
            <span v-else class="page-competitor__dash" title="AI-разборов пока нет">—</span>
          </td>
          <td class="page-competitor__actions">
            <router-link :to="`/competitor/select/${r.source_nm_id}`" class="btn btn-sm btn-outline-primary" title="Выбрать поисковые фразы и позиции для отбора">
              <i class="bi bi-search"></i> Выбрать фразы
            </router-link>
            <router-link :to="`/competitor/results/${r.source_nm_id}`" class="btn btn-sm btn-outline-secondary" title="Все конкуренты с ценами и рейтингами">
              <i class="bi bi-bar-chart"></i> Результаты
            </router-link>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import { ref, onMounted } from 'vue'
import { competitorApi, type CompetitorSourceRow } from '../api/competitor'

const rows = ref<CompetitorSourceRow[]>([])
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    rows.value = (await competitorApi.sources()).rows
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
})
</script>
