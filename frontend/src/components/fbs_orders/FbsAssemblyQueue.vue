<template>
  <div>
    <div class="fbs-section-line">Сроки сборки
      <span class="fbs-help" title="Задание ждёт дольше 18 ч — базового срока по оферте Wildberries. Это ещё не отмена, а деньги: за каждый час сверх базового срока растёт надбавка к комиссии. Более того, ставка повышается на 30-м и 36-м часе и применяется ко ВСЕМ накопленным часам сразу. Поэтому дожимать в первую очередь надо задания на 29-м и 35-м часу: там один час меняет цену всей просрочки.">?</span>
      <span class="fbs-kpi__sub d-inline">· базовый срок 18 ч · автоотмена 120 ч</span>
    </div>
    <div class="fbs-kpi">
      <div class="fbs-kpi__card fbs-kpi__card--danger fbs-kpi__card--click" @click="openModal('Комиссия уже растёт', q.orders?.overdue)" title="Показать заказы">
        <div class="fbs-kpi__label">Комиссия уже растёт</div>
        <div class="fbs-kpi__value">{{ fmt0(q.overdue_cnt) }} <span class="fbs-kpi__unit">шт · {{ fmtPct1(q.overdue_pct) }}</span></div>
        <div class="fbs-kpi__sub">на {{ fmtMoney(q.overdue_sum) }}</div>
      </div>
      <div class="fbs-kpi__card fbs-kpi__card--click" @click="openModal('Истекает через 2 ч', q.orders?.soon)" title="Показать заказы">
        <div class="fbs-kpi__label">Истекает через 2 ч</div>
        <div class="fbs-kpi__value">{{ fmt0(q.soon2h_cnt) }} <span class="fbs-kpi__unit">шт</span></div>
      </div>
      <div class="fbs-kpi__card fbs-kpi__card--click" @click="openModal('Скоро автоотмена', q.orders?.pre_cancel)" title="Показать заказы">
        <div class="fbs-kpi__label">Скоро автоотмена</div>
        <div class="fbs-kpi__value">{{ fmt0(q.pre_cancel_cnt) }} <span class="fbs-kpi__unit">шт</span></div>
      </div>
      <div class="fbs-kpi__card fbs-kpi__card--ok fbs-kpi__card--click" @click="openModal('Запас есть', q.orders?.ok)" title="Показать заказы">
        <div class="fbs-kpi__label">Запас есть</div>
        <div class="fbs-kpi__value">{{ fmt0(q.ok_cnt) }} <span class="fbs-kpi__unit">шт · {{ fmtPct1(q.ok_pct) }}</span></div>
        <div class="fbs-kpi__sub">на {{ fmtMoney(q.ok_sum) }}</div>
      </div>
      <div class="fbs-kpi__card fbs-kpi__card--ok" title="Сдано за &lt;42 ч: скидка −5/−3,5 п.п. с комиссии">
        <div class="fbs-kpi__label">Сдано с экономией</div>
        <div class="fbs-kpi__value">{{ fmt0(q.economy?.cnt) }} <span class="fbs-kpi__unit">шт · {{ fmtPct1(q.economy?.pct) }}</span></div>
        <div class="fbs-kpi__sub">−{{ fmtMoney(q.economy?.discount_sum) }} комиссии · {{ fmt0(q.economy?.cnt) }} из {{ fmt0(q.economy?.tasks) }} заданий ({{ fmtPct1(q.economy?.share_pct) }})</div>
      </div>
    </div>
    <FbsLiveOrdersModal :title="modalTitle" :orders="modalOrders" @close="modalOrders = null" />
    <div class="fbs-risk">
      В риске сейчас: <b>{{ fmtMoney(risk.sum) }}</b> · {{ fmt0(risk.waiting_scan_cnt) }} заказов ждут скана поставки · из них зависло: {{ fmt0(risk.stuck_cnt) }}
    </div>
    <div class="fbs-section-line">Очередь и скорость по складам</div>
    <div class="fbs-wh__grid">
      <div v-for="w in warehouses" :key="String(w.warehouse_id)" class="fbs-wh__card">
        <div class="fbs-wh__name">{{ w.warehouse_name }}</div>
        <div class="fbs-wh__nums">
          <span><b>{{ fmt0(w.new) }}</b><i>Новые</i></span>
          <span><b>{{ fmt0(w.assembling) }}</b><i>На сборке</i></span>
          <span><b>{{ fmt0(w.transit) }}</b><i>В доставке</i></span>
          <span><b>{{ fmt0(w.sorted) }}</b><i>Сортировка</i></span>
        </div>
        <div class="fbs-wh__sub">До сдачи {{ fmtHours(w.median_to_handover_h) }} · измерено {{ fmt0(w.measured_cnt) }} заданий</div>
        <div class="fbs-wh__risk">Сроки <b>{{ fmt0(w.growing_cnt) }}</b> {{ fmtMoney(w.growing_sum) }} с растущей комиссией · из них {{ fmt0(w.stuck_cnt) }} зависло</div>
        <div class="fbs-wh__eco">С экономией <b>{{ fmt0(w.economy_cnt) }}</b> · −{{ fmtMoney(w.economy_discount) }} ({{ fmtPct1(w.economy_share) }} заданий)</div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
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
  const h = Number(v) || 0
  if (h < 48) return Math.round(h) + ' ч'
  return Math.floor(h / 24) + ' дн ' + Math.round(h % 24) + ' ч'
}
</script>
