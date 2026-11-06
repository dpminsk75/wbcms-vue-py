<template>
  <div v-if="orders" class="fbs-modal__overlay" @mousedown.self="emit('close')">
    <div class="fbs-modal__box" role="dialog" aria-modal="true">
      <div class="fbs-modal__head">
        <b>{{ title }} <span class="fbs-modal__count">{{ orders.length }} шт</span></b>
        <button class="btn btn--outline btn-sm" @click="emit('close')">× Закрыть (Esc)</button>
      </div>
      <div class="fbs-modal__body">
        <table class="tbl fbs-modal__table">
          <thead>
            <tr>
              <th class="t-left">Заказ</th><th class="t-left">Дата</th><th class="t-left">Склад</th>
              <th class="t-left">Состав</th><th class="t-left">Возраст</th><th class="t-right">Сумма</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!orders.length"><td colspan="6" class="fbs-tbl__empty">Нет заказов</td></tr>
            <tr v-for="o in orders" :key="String(o.wb_order_id)">
              <td class="t-left">
                <a :href="'/wb-order/index?srid=' + o.srid + '&detail=1'" target="_blank" :title="'Открыть заказ ' + o.srid" class="fbs-modal__link fbs-modal__mono">{{ o.srid }}</a>
                <button class="fbs-modal__copy" @click="copySrid(o.srid)" title="Скопировать SRID"><i class="bi" :class="copied === o.srid ? 'bi-check-lg' : 'bi-clipboard'"></i></button>
              </td>
              <td class="t-left text-nowrap text-muted">{{ o.date }}</td>
              <td class="t-left">{{ o.warehouse }}</td>
              <td class="t-left">
                <div>{{ o.title || '(нет карточки)' }}</div>
                <div class="text-muted fbs-modal__sub">WB: {{ o.nm_id }}{{ o.vendor_code ? ' · ' + o.vendor_code : '' }}</div>
                <div v-if="o.tech_size || o.barcode" class="text-muted fbs-modal__sub">{{ o.tech_size || '' }}{{ o.tech_size && o.barcode ? ' · ' : '' }}{{ o.barcode || '' }}</div>
              </td>
              <td class="t-left text-nowrap"><span class="fbs-modal__age">{{ fmtAge(o.age_h) }}</span></td>
              <td class="t-right text-nowrap"><b>{{ fmtMoney(o.price) }}</b></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { ref, onMounted, onBeforeUnmount } from 'vue'
defineProps<{ title: string, orders: any[] | null }>()
const copied = ref<string | null>(null)
let copyTimer: ReturnType<typeof setTimeout> | null = null
const copySrid = async (s: any) => {
  const v = String(s || '')
  try { await navigator.clipboard.writeText(v) }
  catch {
    const ta = document.createElement('textarea')
    ta.value = v
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
  copied.value = v
  if (copyTimer) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => (copied.value = null), 1200)
}
const emit = defineEmits<{ (e: 'close'): void }>()
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'

const fmtAge = (v: any) => {
  const h = Number(v) || 0
  if (h < 48) return Math.round(h) + ' ч'
  return Math.floor(h / 24) + ' дн ' + Math.round(h % 24) + ' ч'
}
const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') emit('close') }
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>
