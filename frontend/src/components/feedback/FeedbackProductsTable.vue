<template>
  <div class="page-feedback-dashboard__products card wb-grid-card">
    <div class="page-feedback-dashboard__products-head">
      <span class="page-feedback-dashboard__products-title">
        Обзор товаров <span class="text-muted small">(ТОП по заказам, только с отзывами)</span>
      </span>
      <div class="page-feedback-dashboard__products-tabs" role="group">
        <button v-for="n in [20, 50, 100]" :key="n"
                :class="['btn', 'btn-sm', limit === n ? 'btn-primary' : 'btn-outline-secondary']"
                @click="$emit('update:limit', n)">
          ТОП-{{ n }}
        </button>
      </div>
    </div>

    <div v-if="ordersNote" class="page-feedback-dashboard__orders-note">
      <i class="bi bi-info-circle me-1"></i>{{ ordersNote }}
    </div>

    <div v-if="loading" class="p-4 text-center text-muted">Загрузка…</div>
    <div v-else class="wb-table-wrap">
      <table class="table table-bordered table-striped table-hover mb-0">
        <thead>
          <tr>
            <th class="page-feedback-dashboard__products-first">Товар</th>
            <th class="page-feedback-dashboard__col-num">Заказов</th>
            <th class="page-feedback-dashboard__col-num">Отзывов</th>
            <th class="page-feedback-dashboard__col-num">С текстом</th>
            <th class="page-feedback-dashboard__col-num">С тегами</th>
            <th class="page-feedback-dashboard__col-num">Ср. оценка</th>
            <th class="page-feedback-dashboard__col-num">NPS</th>
            <th class="page-feedback-dashboard__col-tone">Тональность</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="8" class="text-center text-muted">
              {{ emptyText || 'Нет данных' }}
            </td>
          </tr>
          <tr v-for="r in items" :key="r.nm_id">
            <td>
              <div class="fbs-product">
                <img :src="photo(r)" @error="(e:any)=>e.target.src='/images/no-photo.png'"
                     class="fbs-product__photo" />
                <div>
                  <div class="fbs-product__title">{{ r.title || '(нет карточки)' }}</div>
                  <div class="fbs-product__sub">{{ r.brand || '' }}</div>
                  <div class="fbs-product__sub">{{ r.vendor_code || '' }}</div>
                  <div class="fbs-product__sub">
                    <a :href="'/wb/detail?nm_id=' + r.nm_id" target="_blank"
                       class="fbs-product__link">WB: {{ r.nm_id }}</a>
                  </div>
                </div>
              </div>
            </td>
            <td class="text-center">{{ r.orders_cnt }}</td>
            <td class="text-center">{{ r.reviews_cnt }}</td>
            <td class="text-center">{{ r.with_text_cnt }}</td>
            <td class="text-center">{{ r.with_tags_cnt }}</td>
            <td class="text-center">
              <span v-if="r.avg_rating != null" class="page-feedback-dashboard__rate">
                <span class="page-feedback-dashboard__star">★</span>{{ r.avg_rating }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="text-center">
              <span v-if="r.nps != null"
                    :class="r.nps >= 0 ? 'text-success' : 'text-danger'">{{ r.nps }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <div class="page-feedback-dashboard__tone">
                <div class="page-feedback-dashboard__tone-bar">
                  <div class="page-feedback-dashboard__tone-pos"
                       :style="{ width: posPct(r) + '%' }"></div>
                  <div class="page-feedback-dashboard__tone-neg"
                       :style="{ width: negPct(r) + '%' }"></div>
                </div>
                <div class="page-feedback-dashboard__tone-labels">
                  <span class="text-success">+{{ posPct(r) }}%</span>
                  <span class="text-danger">−{{ negPct(r) }}%</span>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DashCard } from '@/api/feedbackDashboard'

defineProps<{
  items: DashCard[]
  limit: number
  loading?: boolean
  /** Подпись про заказы, если их нет в кубе агрегации. */
  ordersNote?: string
  /** Текст вместо «Нет данных», когда таблица пуста. */
  emptyText?: string
}>()
defineEmits<{ (e: 'update:limit', v: number): void }>()

const photo = (r: DashCard) => {
  try {
    let p: any = r.photos
    if (typeof p === 'string') p = JSON.parse(p)
    if (typeof p === 'string') p = JSON.parse(p)
    if (Array.isArray(p) && p[0]) return p[0]
  } catch { /* noop */ }
  return '/images/no-photo.png'
}

const tonePct = (r: DashCard, key: 'pos_cnt' | 'neg_cnt') => {
  const total = (r.pos_cnt || 0) + (r.neg_cnt || 0)
  if (!total) return 0
  return Math.round((r[key] || 0) * 100 / total)
}
const posPct = (r: DashCard) => tonePct(r, 'pos_cnt')
const negPct = (r: DashCard) => tonePct(r, 'neg_cnt')
</script>

<style scoped>
.page-feedback-dashboard__products { margin-bottom: 16px; }
/* ячейки по центру по вертикали: по умолчанию vertical-align: baseline,
   из-за чего числа прижаты к верху строки, а в первой ячейке карточка с фото */
.page-feedback-dashboard__products td { vertical-align: middle; }
.page-feedback-dashboard__products-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  border-bottom: 1px solid #e5e7eb;
}
.page-feedback-dashboard__products-title { font-weight: 700; font-size: 13px; }
.page-feedback-dashboard__orders-note {
  padding: 6px 14px;
  font-size: 12px;
  color: #8a6d3b;
  background: #fff8e6;
  border-bottom: 1px solid #f0e3c0;
}
.page-feedback-dashboard__products-tabs { display: flex; gap: 6px; }
.page-feedback-dashboard__products-first { min-width: 300px; }
.page-feedback-dashboard__col-num { width: 90px; text-align: center; }
.page-feedback-dashboard__col-tone { width: 190px; }
.page-feedback-dashboard__rate { white-space: nowrap; font-weight: 600; }
.page-feedback-dashboard__star { color: #f59e0b; }
.page-feedback-dashboard__tone-bar {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  background: #eef0f3;
}
.page-feedback-dashboard__tone-pos { background: #4f7d5b; }
.page-feedback-dashboard__tone-neg { background: #e0a16f; }
.page-feedback-dashboard__tone-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  margin-top: 2px;
}
</style>
