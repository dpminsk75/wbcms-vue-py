<template>
  <div v-if="orders !== null" class="page-fbs-cancels__modal-overlay" @mousedown.self="emit('close')">
    <div class="page-fbs-cancels__modal" role="dialog" aria-modal="true">
      <div class="page-fbs-cancels__modal-head">
        <b>{{ title }} <span class="page-fbs-cancels__modal-count">{{ orders.length }} шт</span></b>
        <button class="btn btn-sm btn-light" @click="emit('close')">× Закрыть (Esc)</button>
      </div>
      <div class="page-fbs-cancels__modal-body">
        <div v-if="loading" class="p-4 text-center text-muted">Загрузка...</div>
        <table v-else class="table table-hover table-sm mb-0 page-fbs-cancels__modal-table">
          <thead>
            <tr>
              <th>SRID</th><th>Дата</th><th>Склад</th><th>Состав</th><th class="text-end">Сумма</th><th>Кем</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!orders.length"><td colspan="6" class="text-center text-muted">Нет заказов</td></tr>
            <tr v-for="o in orders" :key="String(o.wb_order_id)">
              <td>
                <a :href="'/wb-order/index?srid=' + o.srid + '&detail=1'" target="_blank" :title="'Открыть заказ ' + o.srid" class="page-fbs-cancels__modal-link page-fbs-cancels__modal-mono">{{ o.srid }}</a>
                <button class="page-fbs-cancels__modal-copy" @click="copySrid(o.srid)" title="Скопировать SRID"><i class="bi" :class="copied === o.srid ? 'bi-check-lg' : 'bi-clipboard'"></i></button>
              </td>
              <td class="text-nowrap text-muted">{{ o.date }}</td>
              <td>{{ o.warehouse }}</td>
              <td>
                <div>{{ o.title || '(нет карточки)' }}</div>
                <div class="text-muted page-fbs-cancels__modal-sub">WB: {{ o.nm_id }}{{ o.vendor_code ? ' · ' + o.vendor_code : '' }}</div>
                <div v-if="o.tech_size || o.barcode" class="text-muted page-fbs-cancels__modal-sub">{{ o.tech_size || '' }}{{ o.tech_size && o.barcode ? ' · ' : '' }}{{ o.barcode || '' }}</div>
              </td>
              <td class="text-nowrap text-end"><b>{{ fmtMoney(o.price) }}</b></td>
              <td class="text-nowrap"><span class="page-fbs-cancels__modal-who" :class="'page-fbs-cancels__modal-who--' + o.bucket">{{ who(o.bucket) }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
defineProps<{ title: string, orders: any[] | null, loading: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()
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
const who = (b: string) => b === 'seller_cancel' ? 'Продавец' : b === 'buyer_cancel' ? 'Покупатель' : b === 'declined' ? 'Отказ' : b
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') emit('close') }
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>
<style scoped>
.page-fbs-cancels__modal-overlay { position: fixed; inset: 0; background: rgba(17,24,39,.5); z-index: 1050; display: flex; align-items: flex-start; justify-content: center; padding: 40px 16px; overflow: auto; }
.page-fbs-cancels__modal { background: #fff; border-radius: 14px; max-width: 1040px; width: 100%; box-shadow: 0 12px 40px rgba(0,0,0,.28); overflow: hidden; }
.page-fbs-cancels__modal-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px 18px; background: #f8fafc; border-bottom: 1px solid #e5e7eb; font-size: 14px; }
.page-fbs-cancels__modal-count { display: inline-block; font-size: 11px; font-weight: 600; color: #7c3aed; background: #f2e9fb; border-radius: 10px; padding: 1px 8px; margin-left: 6px; vertical-align: middle; }
.page-fbs-cancels__modal-body { padding: 10px 14px 14px; max-height: 70vh; overflow: auto; }
.page-fbs-cancels__modal-table { font-size: 12.5px; }
.page-fbs-cancels__modal-table thead th { position: sticky; top: 0; background: #f8fafc; z-index: 1; font-size: 10.5px; text-transform: uppercase; letter-spacing: .03em; color: #9ca3af; border-bottom: 1px solid #e5e7eb; padding: 6px 8px; }
.page-fbs-cancels__modal-table tbody td { padding: 6px 8px; vertical-align: middle; }
.page-fbs-cancels__modal-table tbody tr:hover { background: #f8f7ff; }
.page-fbs-cancels__modal-sub { font-size: 10.5px; }
.page-fbs-cancels__modal-mono { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; word-break: break-all; }
.page-fbs-cancels__modal-copy { border: 0; background: transparent; color: #9ca3af; font-size: 12px; padding: 0 0 0 4px; cursor: pointer; vertical-align: middle; }
.page-fbs-cancels__modal-copy:hover { color: #7c3aed; }
.page-fbs-cancels__modal-link { font-weight: 600; font-size: 13px; color: #7c3aed; text-decoration: none; }
.page-fbs-cancels__modal-link:hover { text-decoration: underline; }
.page-fbs-cancels__modal-who { display: inline-block; font-size: 11px; font-weight: 600; border-radius: 6px; padding: 1px 7px; background: #f1f5f9; color: #374151; }
.page-fbs-cancels__modal-who--seller_cancel { background: #fee2e2; color: #b91c1c; }
.page-fbs-cancels__modal-who--buyer_cancel { background: #ffedd5; color: #c2410c; }
.page-fbs-cancels__modal-who--declined { background: #fce7f3; color: #be185d; }
</style>
