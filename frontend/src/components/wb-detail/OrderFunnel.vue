<template>
  <div class="order-funnel-widget">
    <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
    <template v-else-if="data">
      <div class="order-funnel-bar">
        <div class="of-seg of-bg-bought" :style="{width: data.bought_percent+'%'}" :title="'Выкупленные: '+data.bought_percent+'%'"></div>
        <div class="of-seg of-bg-delivery" :style="{width: data.delivery_percent+'%'}" :title="'В доставке: '+data.delivery_percent+'%'"></div>
        <div class="of-seg of-bg-cancel" :style="{width: data.cancel_percent+'%'}" :title="'Отменённые: '+data.cancel_percent+'%'"></div>
        <div class="of-seg of-bg-returns" :style="{width: data.returns_percent+'%'}" :title="'Возвраты: '+data.returns_percent+'%'"></div>
      </div>
      <div class="order-funnel-cards">
        <div class="of-card">
          <div class="of-label">Заказы <i class="bi bi-question-circle-fill of-hint" title="Все заказы за выбранный период"></i></div>
          <div class="of-value">{{ fmtMoney(data.total_sum) }}</div>
          <div class="of-qty"><b>{{ fmtQty(data.total_qty) }}</b> шт.</div>
        </div>
        <div class="of-card">
          <div class="of-label"><span class="of-dot of-bg-bought"></span>Выкупленные <i class="bi bi-question-circle-fill of-hint" title="Заказы, по которым дошла продажа"></i></div>
          <div class="of-value">{{ fmtMoney(data.bought_sum) }}</div>
          <div class="of-pct">{{ data.bought_percent }}%</div>
          <div class="of-qty"><b>{{ fmtQty(data.bought_qty) }}</b> шт.</div>
        </div>
        <div class="of-card">
          <div class="of-label"><span class="of-dot of-bg-delivery"></span>В доставке <i class="bi bi-question-circle-fill of-hint" title="Заказы без финального статуса: ещё не выкуплены и не отменены"></i></div>
          <div class="of-value">{{ fmtMoney(data.delivery_sum) }}</div>
          <div class="of-pct">{{ data.delivery_percent }}%</div>
          <div class="of-qty"><b>{{ fmtQty(data.delivery_qty) }}</b> шт.</div>
        </div>
        <div class="of-card">
          <div class="of-label"><span class="of-dot of-bg-cancel"></span>Отменённые <i class="bi bi-question-circle-fill of-hint" title="Заказы с признаком отмены (is_cancel)"></i></div>
          <div class="of-value">{{ fmtMoney(data.cancel_sum) }}</div>
          <div class="of-pct">{{ data.cancel_percent }}%</div>
          <div class="of-qty"><b>{{ fmtQty(data.cancel_qty) }}</b> шт.</div>
        </div>
        <div class="of-card">
          <div class="of-label"><span class="of-dot of-bg-returns"></span>Возвраты <i class="bi bi-question-circle-fill of-hint" title="Продажи с saleID вида R... — возврат товара покупателем"></i></div>
          <div class="of-value">{{ fmtMoney(data.returns_sum) }}</div>
          <div class="of-pct">{{ data.returns_percent }}%</div>
          <div class="of-qty"><b>{{ fmtQty(data.returns_qty) }}</b> шт.</div>
        </div>
        <div class="of-card of-card-total">
          <div class="of-label">Процент выкупа</div>
          <div class="of-buyout" :class="buyoutClass">{{ data.buyout_percent }}%</div>
        </div>
      </div>
    </template>
    <div v-else class="text-center p-3 text-muted">Нет данных</div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
const props=defineProps<{ nmId:string|number, dateFrom:string, dateTo:string }>()
const data=ref<any>(null)
const loading=ref(false)
const fmtMoney=(v:any)=> new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Math.round(Number(v)||0)) + ' ₽'
const fmtQty=(v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const buyoutClass=computed(()=>{
  const p = Number(data.value?.buyout_percent)||0
  return p > 90 ? 'of-buyout-good' : p > 80 ? 'of-buyout-warn' : 'of-buyout-bad'
})
const fetchData=async()=>{
  if(!props.nmId) return
  loading.value=true
  try{
    const r=await fetch(`/api/wb/detail/funnel?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`)
    data.value=await r.json()
  }catch{ data.value=null } finally{ loading.value=false }
}
onMounted(fetchData)
watch(()=>[props.nmId, props.dateFrom, props.dateTo], fetchData)
</script>
<style scoped>
.order-funnel-widget{background:#fff; border:1px solid #e6e8eb; border-radius:12px; padding:16px 18px 12px; margin-bottom:0; box-shadow:0 4px 16px rgba(20,30,50,.08), 0 1px 3px rgba(20,30,50,.06)}
.order-funnel-bar{display:flex; width:100%; height:15px; border-radius:4px; overflow:hidden; background:#eef0f2; margin-bottom:16px}
.of-seg{height:100%}
.of-bg-bought{background:#4c8bf5}
.of-bg-delivery{background:#9aa1ab}
.of-bg-cancel{background:#f7941d}
.of-bg-returns{background:#f2637b}
.order-funnel-cards{display:flex; flex-wrap:wrap; gap:10px}
.of-card{flex:1 1 150px; min-width:130px; padding-right:10px; border-right:1px solid #eef0f2}
.of-card:last-child{border-right:none}
.of-label{font-size:12px; color:#6b7280; margin-bottom:6px; white-space:nowrap}
.of-hint{font-size:10px; color:#b7bcc3; cursor:help}
.of-dot{display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:4px}
.of-value{font-size:18px; font-weight:700; color:#1f2328; line-height:1.2}
.of-pct{font-size:12px; color:#6b7280}
.of-qty{font-size:12px; color:#6b7280}
.of-card-total .of-buyout{font-size:26px; font-weight:800; line-height:1.2}
.of-buyout-good{color:#1cb56d}
.of-buyout-warn{color:#f7941d}
.of-buyout-bad{color:#f2637b}
@media (max-width:991px){
  .order-funnel-cards{flex-direction:column}
  .of-card{border-right:none; border-bottom:1px solid #eef0f2; padding-bottom:8px}
  .of-card:last-child{border-bottom:none}
}
</style>
