<template>
  <div class="container-xxl page-stock-docs">
    <!-- Шапка блока «Документы»: заголовок + правое меню (пилюли темы) -->
    <WbWorkspaceHead
      :title="`Документ №${doc?.id ?? ''}`"
      :workspace-tabs="STOCK_DOCS_TABS"
      workspace-active="docs"
    />

    <div class="page-stock-docs__head no-print">
      <span class="badge badge--brand">{{ doc?.type_label }}</span>
      <span class="badge" :class="statusClass">{{ doc?.status_label }}</span>
      <span class="spacer"></span>
      <button class="btn btn--outline btn-sm" @click="router.push('/wb-doc')">
        <i class="bi bi-arrow-left me-1"></i>К списку
      </button>
      <button v-if="doc?.status !== 'posted' && canManage" class="btn btn--outline btn-sm"
              @click="router.push(`/wb-doc/${docId}/edit`)">
        <i class="bi bi-pencil me-1"></i>Редактировать
      </button>
      <button v-if="doc?.status === 'draft' && canManage" class="btn btn--outline-ok btn-sm" @click="post">
        <i class="bi bi-check2-circle me-1"></i>Провести
      </button>
      <button v-if="doc?.status === 'posted' && canManage" class="btn btn--outline-bad btn-sm" @click="cancel">
        <i class="bi bi-arrow-counterclockwise me-1"></i>Отменить (сторно)
      </button>
      <button v-if="doc?.status !== 'posted' && canManage" class="btn btn--danger btn-sm" @click="remove">
        <i class="bi bi-trash me-1"></i>Удалить
      </button>
      <button class="btn btn--outline btn-sm" @click="printPage">
        <i class="bi bi-printer me-1"></i>Печать
      </button>
    </div>

    <div v-if="loading" class="page-stock-docs__loading">
      <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
      <span>Загрузка данных…</span>
    </div>

    <div v-else-if="doc" class="wb-panel">
      <div class="wb-panel__bd">
        <!-- Реквизиты документа -->
        <div class="row g-3 mb-3">
          <div class="col-md-3">
            <div class="page-stock-docs__label">Тип</div>
            <div class="page-stock-docs__value">{{ doc.type_label }}</div>
          </div>
          <div class="col-md-3">
            <div class="page-stock-docs__label">Склад</div>
            <div class="page-stock-docs__value">{{ doc.warehouse_name || doc.warehouseId }}</div>
          </div>
          <div class="col-md-3">
            <div class="page-stock-docs__label">Дата</div>
            <div class="page-stock-docs__value">{{ formatDate(doc.date) }}</div>
          </div>
          <div class="col-md-3">
            <div class="page-stock-docs__label">Комментарий</div>
            <div class="page-stock-docs__value">{{ doc.comment || '—' }}</div>
          </div>
          <div v-if="doc.type === 'TRANSFER'" class="col-md-3">
            <div class="page-stock-docs__label">Склад (куда)</div>
            <div class="page-stock-docs__value">{{ doc.to_warehouse_name || doc.to_warehouseId }}</div>
          </div>
        </div>
      </div>

      <!-- Позиции — таблица темы .tbl-card -->
      <div class="tbl-card">
        <div class="card__hd">
          <span>Позиции</span>
          <span class="hd-badge">{{ (doc.items || []).length }}</span>
        </div>
        <div class="tbl-wrap">
          <table class="tbl page-stock-docs__table">
            <thead>
              <tr>
                <th class="t-left page-stock-docs__col-sku">Баркод</th>
                <th class="t-left">Товар</th>
                <th v-if="doc.type === 'INVENTORY'" class="t-right page-stock-docs__col-num">По учету</th>
                <th v-if="doc.type === 'INVENTORY'" class="t-right page-stock-docs__col-num">Факт</th>
                <th v-else class="t-right page-stock-docs__col-num">
                  {{ doc.type === 'ADJUSTMENT' ? 'Корректировка' : 'Количество' }}
                </th>
                <th v-if="doc.type === 'INVENTORY'" class="t-right page-stock-docs__col-num">Разница</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in doc.items || []" :key="it.id">
                <td class="t-left num">{{ it.sku }}</td>
                <td class="t-left page-stock-docs__product">
                  <div>{{ it.title || '' }}</div>
                  <div class="page-stock-docs__product-sub">{{ it.vendorCode || '' }}</div>
                </td>
                <td v-if="doc.type === 'INVENTORY'" class="t-right num">{{ it.qty_before ?? 0 }}</td>
                <td v-if="doc.type === 'INVENTORY'" class="t-right num">{{ it.qty_fact ?? it.qty }}</td>
                <td v-else class="t-right num">{{ it.qty }}</td>
                <td v-if="doc.type === 'INVENTORY'" class="t-right num" :class="deltaClass(it)">
                  {{ delta(it) > 0 ? '+' : '' }}{{ delta(it) }}
                </td>
              </tr>
              <tr v-if="!(doc.items || []).length">
                <td :colspan="doc.type === 'INVENTORY' ? 6 : 4" class="t-center page-stock-docs__empty">
                  Позиций нет
                </td>
              </tr>
            </tbody>
            <tfoot v-if="doc.type === 'INVENTORY' && (doc.items || []).length">
              <tr class="tbl__total">
                <td class="t-left" colspan="2">Итого</td>
                <td class="t-right num">{{ sum('qty_before') }}</td>
                <td class="t-right num">{{ sum('qty_fact') }}</td>
                <td class="t-right num" :class="sumDelta > 0 ? 't-pos' : (sumDelta < 0 ? 't-neg' : '')">
                  {{ sumDelta > 0 ? '+' : '' }}{{ sumDelta }}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-stock-docs.css'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { StockDoc } from '@/api/stockDocs'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { STOCK_DOCS_TABS } from '@/components/common/workspaceTabs'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const docId = computed(() => Number(route.params.id || 0))
const doc = ref<StockDoc | null>(null)
const loading = ref(true)

// Просмотр — по viewFbs, правка — по manageFbs.
const canManage = computed(() => auth.canDomain('manageFbs'))

const statusClass = computed(() => ({
  draft: 'badge--neutral',
  posted: 'badge--ok',
  canceled: 'badge--bad',
}[doc.value?.status || 'draft']))

const formatDate = (s: string) => (s ? String(s).slice(0, 16).replace('T', ' ') : '—')

const delta = (it: any) => Number(it.qty_fact ?? it.qty ?? 0) - Number(it.qty_before ?? 0)
const deltaClass = (it: any) => {
  const d = delta(it)
  return d > 0 ? 't-pos' : (d < 0 ? 't-neg' : '')
}
const sum = (key: string) => (doc.value?.items || []).reduce(
  (a: number, it: any) => a + Number(key === 'qty_fact' ? (it.qty_fact ?? it.qty ?? 0) : (it[key] ?? 0)), 0)
const sumDelta = computed(() => (doc.value?.items || []).reduce((a: number, it: any) => a + delta(it), 0))

const load = async () => {
  loading.value = true
  try {
    doc.value = await api.get(`/api/stock-docs/${docId.value}`).then(r => r.data)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const post = async () => {
  if (!confirm('Провести документ? Остатки изменятся.')) return
  try {
    await api.post(`/api/stock-docs/${docId.value}/post`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось провести')
    return
  }
  load()
}

const cancel = async () => {
  if (!confirm('Отменить документ? Будет создано сторно.')) return
  try {
    await api.post(`/api/stock-docs/${docId.value}/cancel`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось отменить')
    return
  }
  load()
}

const remove = async () => {
  if (!confirm('Удалить документ?')) return
  try {
    await api.delete(`/api/stock-docs/${docId.value}`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось удалить')
    return
  }
  router.push('/wb-doc')
}

const printPage = () => window.print()
</script>

