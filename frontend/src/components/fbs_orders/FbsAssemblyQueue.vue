<template>
  <div class="page-fbs-orders__assembly">
    <div class="page-fbs-orders__section-line">Сроки сборки
      <span class="page-fbs-orders__help" title="Задание ждёт дольше 18 ч — базового срока по оферте Wildberries. Это ещё не отмена, а деньги: за каждый час сверх базового срока растёт надбавка к комиссии. Причём ставка повышается на 30-м и 36-м часе и применяется ко ВСЕМ накопленным часам сразу. Поэтому дожимать в первую очередь надо задания на 29-м и 35-м часу: там один час меняет цену всей просрочки.">?</span>
      <span class="text-muted">· базовый срок 18 ч · автоотмена 120 ч</span>
    </div>
    <div class="page-fbs-orders__kpi">
      <div class="page-fbs-orders__kpi-card page-fbs-orders__kpi-card--danger page-fbs-orders__kpi-card--click" @click="openModal('Комиссия уже растёт', q.orders?.overdue)" title="Показать заказы">
        <div class="page-fbs-orders__kpi-label">Комиссия уже растёт</div>
        <div class="page-fbs-orders__kpi-value">{{ fmt0(q.overdue_cnt) }} <span class="page-fbs-orders__kpi-unit">шт · {{ fmtPct1(q.overdue_pct) }}</span></div>
        <div class="page-fbs-orders__kpi-sub">на {{ fmtMoney(q.overdue_sum) }}</div>
      </div>
      <div class="page-fbs-orders__kpi-card page-fbs-orders__kpi-card--click" @click="openModal('Истекает через 2 ч', q.orders?.soon)" title="Показать заказы">
        <div class="page-fbs-orders__kpi-label">Истекает через 2 ч</div>
        <div class="page-fbs-orders__kpi-value">{{ fmt0(q.soon2h_cnt) }} <span class="page-fbs-orders__kpi-unit">шт</span></div>
      </div>
      <div class="page-fbs-orders__kpi-card page-fbs-orders__kpi-card--click" @click="openModal('Скоро автоотмена', q.orders?.pre_cancel)" title="Показать заказы">
        <div class="page-fbs-orders__kpi-label">Скоро автоотмена</div>
        <div class="page-fbs-orders__kpi-value">{{ fmt0(q.pre_cancel_cnt) }} <span class="page-fbs-orders__kpi-unit">шт</span></div>
      </div>
      <div class="page-fbs-orders__kpi-card page-fbs-orders__kpi-card--ok page-fbs-orders__kpi-card--click" @click="openModal('Запас есть', q.orders?.ok)" title="Показать заказы">
        <div class="page-fbs-orders__kpi-label">Запас есть</div>
        <div class="page-fbs-orders__kpi-value">{{ fmt0(q.ok_cnt) }} <span class="page-fbs-orders__kpi-unit">шт · {{ fmtPct1(q.ok_pct) }}</span></div>
        <div class="page-fbs-orders__kpi-sub">на {{ fmtMoney(q.ok_sum) }}</div>
      </div>
      <div class="page-fbs-orders__kpi-card page-fbs-orders__kpi-card--ok" title="Сдано за &lt;42 ч: скидка −5/−3,5 п.п. с комиссии">
        <div class="page-fbs-orders__kpi-label">Сдано с экономией</div>
        <div class="page-fbs-orders__kpi-value">{{ fmt0(q.economy?.cnt) }} <span class="page-fbs-orders__kpi-unit">шт · {{ fmtPct1(q.economy?.pct) }}</span></div>
        <div class="page-fbs-orders__kpi-sub">−{{ fmtMoney(q.economy?.discount_sum) }} комиссии · {{ fmt0(q.economy?.cnt) }} из {{ fmt0(q.economy?.tasks) }} заданий ({{ fmtPct1(q.economy?.share_pct) }})</div>
      </div>
    </div>
    <FbsLiveOrdersModal :title="modalTitle" :orders="modalOrders" @close="modalOrders = null" />
    <div class="page-fbs-orders__risk">
      В риске сейчас: <b>{{ fmtMoney(risk.sum) }}</b> · {{ fmt0(risk.waiting_scan_cnt) }} заказов ждут скана поставки · из них зависло: {{ fmt0(risk.stuck_cnt) }}
    </div>
    <div class="page-fbs-orders__section-line">Очередь и скорость по складам</div>
    <div class="page-fbs-orders__wh-grid">
      <div v-for="w in warehouses" :key="String(w.warehouse_id)" class="page-fbs-orders__wh-card">
        <div class="page-fbs-orders__wh-name">{{ w.warehouse_name }}</div>
        <div class="page-fbs-orders__wh-nums">
          <span><b>{{ fmt0(w.new) }}</b><i>Новые</i></span>
          <span><b>{{ fmt0(w.assembling) }}</b><i>На сборке</i></span>
          <span><b>{{ fmt0(w.transit) }}</b><i>В доставке</i></span>
          <span><b>{{ fmt0(w.sorted) }}</b><i>Сортировка</i></span>
        </div>
        <div class="page-fbs-orders__wh-sub">До сдачи {{ fmtHours(w.median_to_handover_h) }} · измерено {{ fmt0(w.measured_cnt) }} заданий</div>
        <div class="page-fbs-orders__wh-risk">Сроки <b>{{ fmt0(w.growing_cnt) }}</b> {{ fmtMoney(w.growing_sum) }} с растущей комиссией · из них {{ fmt0(w.stuck_cnt) }} зависло</div>
        <div class="page-fbs-orders__wh-eco">С экономией <b>{{ fmt0(w.economy_cnt) }}</b> · −{{ fmtMoney(w.economy_discount) }} ({{ fmtPct1(w.economy_share) }} заданий)</div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import FbsLiveOrdersModal from './FbsLiveOrdersModal.vue'
defineProps<{ q: any, risk: any, warehouses: any[] }>()
const modalTitle = ref('')
const modalOrders = ref<any[] | null>(null)
const openModal = (title: string, orders: any[] | undefined) => {
  modalTitle.value = title
  modalOrders.value = orders ?? []
}
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
const fmtHours = (v: any) => {
  if (v == null) return '—'
  const h = Math.floor(Number(v)), m = Math.round((Number(v) - h) * 60)
  return h + ' ч ' + m + ' м'
}
</script>
<style scoped>
.page-fbs-orders__section-line { font-size: 13px; font-weight: 600; color: #111827; margin: 4px 0 10px; }
.page-fbs-orders__kpi { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
.page-fbs-orders__kpi-card { flex: 1 1 160px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; min-width: 150px; }
.page-fbs-orders__kpi-card--danger { background: #fef2f2; border-color: #fecaca; }
.page-fbs-orders__kpi-card--danger .page-fbs-orders__kpi-value { color: #b91c1c; }
.page-fbs-orders__kpi-card--ok .page-fbs-orders__kpi-value { color: #15803d; }
.page-fbs-orders__kpi-label { font-size: 11px; color: #6b7280; text-transform: uppercase; margin-bottom: 4px; }
.page-fbs-orders__kpi-value { font-size: 22px; font-weight: 800; color: #111827; white-space: nowrap; }
.page-fbs-orders__kpi-unit { font-size: 13px; font-weight: 400; color: #6b7280; }
.page-fbs-orders__kpi-sub { font-size: 11px; color: #6b7280; margin-top: 4px; }
.page-fbs-orders__risk { font-size: 12px; color: #374151; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 12px; margin-bottom: 12px; }
.page-fbs-orders__wh-grid { display: flex; flex-wrap: wrap; gap: 12px; }
.page-fbs-orders__wh-card { flex: 1 1 260px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; min-width: 240px; }
.page-fbs-orders__wh-name { font-size: 13px; font-weight: 700; color: #111827; margin-bottom: 8px; }
.page-fbs-orders__wh-nums { display: flex; gap: 12px; margin-bottom: 8px; }
.page-fbs-orders__wh-nums span { display: flex; flex-direction: column; }
.page-fbs-orders__wh-nums b { font-size: 16px; color: #111827; }
.page-fbs-orders__wh-nums i { font-style: normal; font-size: 10px; color: #9ca3af; }
.page-fbs-orders__wh-sub { font-size: 11px; color: #6b7280; }
.page-fbs-orders__wh-risk { font-size: 11px; color: #b91c1c; margin-top: 4px; }
.page-fbs-orders__wh-eco { font-size: 11px; color: #15803d; margin-top: 2px; }
.page-fbs-orders__kpi-card--click { cursor: pointer; }
.page-fbs-orders__kpi-card--click:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.page-fbs-orders__help { display: inline-block; width: 16px; height: 16px; line-height: 14px; text-align: center; font-size: 11px; color: #9ca3af; border: 1px solid #d1d5db; border-radius: 50%; cursor: help; margin: 0 2px; }
</style>
