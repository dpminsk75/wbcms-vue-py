<template>
  <div class="tbl-card">
    <div class="card__hd">
      <span>Акции</span>
      <span class="hd-badge">{{ rows.length }}</span>
      <span class="spacer"></span>
      <span v-if="fetchedAt" class="hd-badge">обновлено {{ fetchedAt }}</span>
    </div>

    <div v-if="loading" class="page-wb-promotions__loading">
      <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
      <span>Загрузка…</span>
    </div>
    <div v-else-if="!rows.length" class="page-wb-promotions__empty">
      Нет акций за выбранный период — кэш обновляется воркером ежечасно,
      можно перезабрать сейчас кнопкой «Перезабрать сейчас»
    </div>
    <div v-else class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th class="t-left">Акция</th>
            <th class="t-left">Тип</th>
            <th class="t-left">Начало</th>
            <th class="t-left">Конец</th>
            <th class="t-left">Статус</th>
            <th class="t-right">Товаров</th>
            <th class="t-left"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in rows" :key="p.promo_id" class="page-wb-promotions__row" @click="$emit('open', p)">
            <td class="t-left">
              <div class="page-wb-promotions__name">{{ p.name }}</div>
              <!-- Преимущества акции — бейджами под названием (не отдельной колонкой) -->
              <div v-if="advantages(p).length" class="page-wb-promotions__adv">
                <span v-for="(a, i) in advantages(p)" :key="a">{{ a }}</span>
              </div>
              <div v-else-if="promoStatus(p) === 'announce'" class="page-wb-promotions__sub">
                свойства ещё не заданы — появятся, когда WB раскроет условия
              </div>
            </td>
            <td class="t-left">
              <span class="badge badge--neutral">{{ promoTypeLabel(p) }}</span>
            </td>
            <td class="t-left num">{{ fmtDate(p.start_date) }}</td>
            <td class="t-left num">{{ fmtDate(p.end_date) }}</td>
            <td class="t-left">
              <span class="badge" :class="statusClass(p)">{{ promoStatusLabel(p) }}</span>
            </td>
            <td class="t-right num">{{ joinText(p) }}</td>
            <td class="t-left">
              <button class="btn btn--outline btn-sm" @click.stop="$emit('open', p)">Подобрать</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  promoDate,
  promoStatus,
  promoStatusLabel,
  promoTypeLabel,
  type PromoRow,
} from '@/api/promotions'

defineProps<{
  rows: PromoRow[]
  loading?: boolean
  fetchedAt?: string
}>()

defineEmits<{ (e: 'open', p: PromoRow): void }>()

function fmtDate(iso: string): string {
  const d = promoDate(iso)
  if (!d) return '—'
  return String(d.getDate()).padStart(2, '0') + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + d.getFullYear()
}

const statusClass = (p: PromoRow) => {
  const s = promoStatus(p)
  if (s === 'announce') return 'badge--neutral'
  if (s === 'finished') return 'badge--neutral'
  return p.promo_type === 'auto' ? 'badge--info' : 'badge--brand'
}

/** Преимущества акции (WB: advantages) — первые 3, дальше свёрнуто в «+N». */
const advantages = (p: PromoRow) => {
  const list = Array.isArray(p.advantages) ? p.advantages.map(String).filter(Boolean) : []
  if (list.length <= 3) return list
  return [...list.slice(0, 3), `+${list.length - 3}`]
}

/** «N из M товаров участвуют» — как в ЛК: участвуют / от всех подходящих. */
const joinText = (p: PromoRow) => {
  const join = Number(p.in_promo_total || 0)
  const notJoin = Number(p.not_in_promo_total || 0)
  const total = join + notJoin
  if (!total) return '—'
  return `${join} / ${total}`
}
</script>
