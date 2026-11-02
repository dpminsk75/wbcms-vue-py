<template>
  <div class="container-xxl page-competitor">
    <WbWorkspaceHead title="Конкуренты: Анализ" :subtabs="COMPETITOR_SUB_TABS" workspace-active="competitors" />
    <p class="text-muted">Товары, по которым собраны данные конкурентов. Выберите товар для анализа.</p>

    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="loading" class="text-muted">Загрузка…</div>

    <div v-if="!loading && !rows.length" class="wb-panel page-competitor__empty">
      <div class="wb-panel__bd">Нет данных о конкурентах.</div>
    </div>

    <div v-else class="tbl-card">
      <div class="card__hd">
        <span>Наши карточки с собранными конкурентами</span>
        <span class="spacer"></span>
        <span class="hd-badge">Карточек: {{ rows.length }}</span>
      </div>
      <div class="tbl-wrap">
      <table class="tbl page-competitor__grid">
      <thead>
        <tr>
          <th class="t-left page-competitor__col-product">Товар</th>
          <th class="t-left">Бренд</th>
          <th class="t-center page-competitor__col-num" title="Уникальных конкурентов в выдаче по всем фразам">Конкуренты</th>
          <th class="t-center page-competitor__col-num" title="Поисковых фраз, по которым собраны конкуренты">Фразы</th>
          <th class="t-center page-competitor__col-num" title="Конкурентов с готовым AI-разбором">Разобрано</th>
          <th class="page-competitor__col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.source_nm_id">
          <td class="t-left">
            <ProductCell
              compact
              :nm-id="r.source_nm_id"
              :photo="r.photo || ''"
              :title="r.title || ''"
              :vendor="r.vendor_code || ''"
              :brand="r.brand || ''"
              :subject="r.subject_name || ''"
              :link="`/wb/detail?nm_id=${r.source_nm_id}`"
              :link-label="'WB: ' + r.source_nm_id"
              copy-nm
              copy-link
            />
          </td>
          <td class="t-left">{{ r.brand || '—' }}</td>
          <td class="t-center"><span class="badge badge--brand" :title="`${r.cnt} конкурентов в выдаче`">{{ r.cnt }}</span></td>
          <td class="t-center"><span class="badge badge--neutral" :title="`${r.phrases} поисковых фраз`">{{ r.phrases }}</span></td>
          <td class="t-center">
            <span v-if="r.analyzed" class="badge badge--ok" :title="`${r.analyzed} с готовым AI-разбором`">{{ r.analyzed }}</span>
            <span v-else class="page-competitor__dash" title="AI-разборов пока нет">—</span>
          </td>
          <td class="page-competitor__actions">
            <router-link :to="`/competitor/select/${r.source_nm_id}`" class="btn btn-sm btn--brand" title="Выбрать поисковые фразы и позиции для отбора">
              <i class="bi bi-search"></i> Выбрать фразы
            </router-link>
            <router-link :to="`/competitor/results/${r.source_nm_id}`" class="btn btn-sm btn--outline" title="Все конкуренты с ценами и рейтингами">
              <i class="bi bi-bar-chart"></i> Результаты
            </router-link>
          </td>
        </tr>
      </tbody>
      </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor.css'
import { ref, onMounted } from 'vue'
import { competitorApi, type CompetitorSourceRow } from '../api/competitor'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import ProductCell from '@/components/common/ProductCell.vue'
import { COMPETITOR_SUB_TABS } from '@/components/common/workspaceTabs'

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
