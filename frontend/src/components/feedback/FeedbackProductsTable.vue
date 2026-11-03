<template>
  <!-- Таблица «Обзор товаров» — блок темы: .tbl-card (шапка .card__hd, .tbl-wrap, .tbl). -->
  <div class="tbl-card page-feedback-dashboard__products">
    <div class="card__hd">
      <span>
        Обзор товаров
        <span class="page-feedback-dashboard__products-sub">(ТОП по заказам, только с отзывами)</span>
      </span>
      <div class="page-feedback-dashboard__products-tabs" role="group">
        <button v-for="n in [20, 50, 100]" :key="n" type="button"
                class="page-feedback-dashboard__limit-btn"
                :class="{ 'page-feedback-dashboard__limit-btn--on': limit === n }"
                @click="$emit('update:limit', n)">
          ТОП-{{ n }}
        </button>
      </div>
    </div>

    <div v-if="ordersNote" class="page-feedback-dashboard__orders-note">
      <i class="bi bi-info-circle me-1"></i>{{ ordersNote }}
    </div>

    <div v-if="loading" class="page-feedback-dashboard__loading">Загрузка…</div>
    <div v-else class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th class="page-feedback-dashboard__products-first">Товар</th>
            <th class="t-center">Заказов</th>
            <th class="t-center">Отзывов</th>
            <th class="t-center">С текстом</th>
            <th class="t-center">С тегами</th>
            <th class="t-center">Ср. оценка</th>
            <th class="t-center">NPS</th>
            <th class="page-feedback-dashboard__col-tone">Тональность</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="8" class="t-center page-feedback-dashboard__empty-row">
              {{ emptyText || 'Нет данных' }}
            </td>
          </tr>
          <tr v-for="r in items" :key="r.nm_id">
            <td>
              <ProductCell
                compact
                :photo="r.photos"
                :title="r.title || ''"
                :brand="r.brand || ''"
                :subject="r.subject_name || ''"
                :vendor="r.vendor_code || ''"
                :nm-id="r.nm_id"
                :link="'/wb/detail?nm_id=' + r.nm_id"
                :link-label="'WB: ' + r.nm_id"
                copy-nm
                copy-link
              />
            </td>
            <td class="t-center">{{ r.orders_cnt }}</td>
            <td class="t-center">{{ r.reviews_cnt }}</td>
            <td class="t-center">{{ r.with_text_cnt }}</td>
            <td class="t-center">{{ r.with_tags_cnt }}</td>
            <td class="t-center">
              <span v-if="r.avg_rating != null" class="page-feedback-dashboard__rate">
                <span class="page-feedback-dashboard__star">★</span>{{ r.avg_rating }}
              </span>
              <span v-else class="page-feedback-dashboard__muted">—</span>
            </td>
            <td class="t-center">
              <span v-if="r.nps != null" :class="r.nps >= 0 ? 't-pos' : 't-neg'">{{ r.nps }}</span>
              <span v-else class="page-feedback-dashboard__muted">—</span>
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
                  <span class="t-pos">+{{ posPct(r) }}%</span>
                  <span class="t-neg">−{{ negPct(r) }}%</span>
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
import ProductCell from '@/components/common/ProductCell.vue'
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

const tonePct = (r: DashCard, key: 'pos_cnt' | 'neg_cnt') => {
  const total = (r.pos_cnt || 0) + (r.neg_cnt || 0)
  if (!total) return 0
  return Math.round((r[key] || 0) * 100 / total)
}
const posPct = (r: DashCard) => tonePct(r, 'pos_cnt')
const negPct = (r: DashCard) => tonePct(r, 'neg_cnt')
</script>
