<template>
  <div class="container-xxl page-stock-docs">
    <!-- Шапка блока «Документы»: заголовок + правое меню (пилюли темы) -->
    <WbWorkspaceHead
      :title="$route.meta.title || 'Документы склада'"
      :workspace-tabs="STOCK_DOCS_TABS"
      workspace-active="docs"
    />

    <!-- Действия — в шапке блока (theme.md §5.7.9: кнопки действий в шапке таблицы) -->
    <div class="tbl-card">
      <div class="card__hd">
        <span>Документы склада</span>
        <span class="hd-badge">{{ total }}</span>
        <span class="spacer"></span>
        <button
          v-for="t in DOC_TYPES"
          :key="t.value"
          type="button"
          class="hd-btn"
          :disabled="!canManage"
          :title="canManage ? '' : 'Нужно право «Работа со складом FBS» (manageFbs)'"
          @click="create(t.value)"
        >
          <i class="bi bi-plus-lg me-1"></i>{{ t.label }}
        </button>
      </div>

      <!-- Фильтр по типу — панель темы -->
      <div class="wb-filter-panel page-stock-docs__filter">
        <div class="row g-2">
          <div class="col-auto">
            <label class="wb-field__label">Тип</label>
            <select v-model="typeFilter" class="wb-select" @change="reload">
              <option value="">Все типы</option>
              <option v-for="t in DOC_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>
        </div>
      </div>

      <div v-if="loading" class="page-stock-docs__loading">
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span>Загрузка данных…</span>
      </div>
      <div v-else-if="!rows.length" class="page-stock-docs__empty">Документов пока нет</div>
      <div v-else class="tbl-wrap">
        <table class="tbl page-stock-docs__table">
          <thead>
            <tr>
              <th class="t-center">ID</th>
              <th class="t-left">Дата</th>
              <th class="t-left">Тип</th>
              <th class="t-left">Статус</th>
              <th class="t-left">Склад</th>
              <th class="t-center">Позиций</th>
              <th class="t-left">Комментарий</th>
              <th class="t-right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in rows" :key="d.id" :class="{ 'page-stock-docs__row--inactive': d.status === 'canceled' }">
              <td class="t-center num">{{ d.id }}</td>
              <td class="t-left">{{ formatDate(d.date) }}</td>
              <td class="t-left">{{ d.type_label }}</td>
              <td class="t-left">
                <span class="badge" :class="statusClass(d.status)">{{ d.status_label }}</span>
              </td>
              <td class="t-left">
                {{ d.warehouse_name || d.warehouseId }}
                <span v-if="d.type === 'TRANSFER'">
                  <i class="bi bi-arrow-right"></i> {{ d.to_warehouse_name || d.to_warehouseId }}
                </span>
              </td>
              <td class="t-center num">{{ d.items_count }}</td>
              <td class="t-left page-stock-docs__comment">{{ d.comment || '' }}</td>
              <td class="t-right text-nowrap">
                <router-link class="btn btn--outline btn-sm" :to="`/wb-doc/${d.id}`" title="Открыть">
                  <i class="bi bi-eye"></i>
                </router-link>
                <button v-if="d.status !== 'posted' && canManage" class="btn btn--outline btn-sm ms-1" title="Править" @click="edit(d)">
                  <i class="bi bi-pencil"></i>
                </button>
                <button v-if="d.status === 'draft' && canManage" class="btn btn--outline-ok btn-sm ms-1" title="Провести" @click="post(d)">
                  <i class="bi bi-check2-circle"></i>
                </button>
                <button v-if="d.status === 'posted' && canManage" class="btn btn--outline-bad btn-sm ms-1" title="Отменить" @click="cancel(d)">
                  <i class="bi bi-arrow-counterclockwise"></i>
                </button>
                <button v-if="d.status !== 'posted' && canManage" class="btn btn--danger btn-sm ms-1" title="Удалить" @click="remove(d)">
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="wb-pager">
        <button class="btn btn--outline btn-sm" :disabled="page <= 1" @click="page--; reload()">‹ Назад</button>
        <span class="wb-pager__label">Стр. {{ page }} / {{ pages }} · всего {{ total }}</span>
        <button class="btn btn--outline btn-sm" :disabled="page >= pages" @click="page++; reload()">Вперёд ›</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-stock-docs.css'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'
import { DOC_TYPES, type DocStatus, type DocType, type StockDoc } from '@/api/stockDocs'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { STOCK_DOCS_TABS } from '@/components/common/workspaceTabs'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const qc = useQueryClient()
const auth = useAuthStore()

// Просмотр документов — по viewFbs, правка (создание/проведение/отмена/удаление) — по manageFbs.
const canManage = computed(() => auth.canDomain('manageFbs'))

const typeFilter = ref('')
const page = ref(1)
const pageSize = 20

const { data, isLoading: loading } = useQuery({
  queryKey: ['stock-docs', typeFilter.value, page.value],
  queryFn: () => api.get('/api/stock-docs', {
    params: { type: typeFilter.value || undefined, page: page.value, page_size: pageSize },
  }).then(r => r.data),
})

const rows = computed<StockDoc[]>(() => (data.value?.rows as StockDoc[]) || [])
const total = computed(() => Number(data.value?.total || 0))
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const reload = () => qc.invalidateQueries({ queryKey: ['stock-docs'] })

const formatDate = (s: string) => (s ? String(s).slice(0, 16).replace('T', ' ') : '—')

const statusClass = (s: DocStatus) => ({
  draft: 'badge--neutral',
  posted: 'badge--ok',
  canceled: 'badge--bad',
}[s] || 'badge--neutral')

const create = (t: DocType) => router.push({ path: '/wb-doc/create', query: { type: t } })
const edit = (d: StockDoc) => router.push({ path: `/wb-doc/${d.id}/edit` })

const post = async (d: StockDoc) => {
  if (!confirm(`Провести документ №${d.id}? Остатки изменятся.`)) return
  try {
    await api.post(`/api/stock-docs/${d.id}/post`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось провести')
    return
  }
  reload()
}

const cancel = async (d: StockDoc) => {
  if (!confirm(`Отменить документ №${d.id}? Будет создано сторно.`)) return
  try {
    await api.post(`/api/stock-docs/${d.id}/cancel`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось отменить')
    return
  }
  reload()
}

const remove = async (d: StockDoc) => {
  if (!confirm(`Удалить документ №${d.id}?`)) return
  try {
    await api.delete(`/api/stock-docs/${d.id}`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось удалить')
    return
  }
  reload()
}
</script>
