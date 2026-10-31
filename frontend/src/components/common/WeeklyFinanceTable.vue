<template>
  <div class="tbl-card tbl-card--compact tbl-card--stickycol">
    <div class="card__hd">
      <span>{{ title }}</span>
      <span class="spacer"></span>
      <button class="hd-btn" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
    </div>
    <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
    <div v-else class="tbl-wrap" ref="wrapRef">
      <table ref="tbl" class="tbl" style="width:100%">
        <thead>
          <tr>
            <th class="t-center">Год-Неделя</th>
            <th class="t-center">Кол-во</th>
            <th class="t-center">Продажи</th>
            <th class="t-center">Ком. WB</th>
            <th class="t-center">Эквайринг</th>
            <th class="t-center">Приёмка</th>
            <th class="t-center">Логистика</th>
            <th class="t-center">Хранение</th>
            <th class="t-center">Штрафы</th>
            <th class="t-center">Отзывы</th>
            <th class="t-center">Реклама</th>
            <th class="t-center">Кэшбек</th>
            <th class="t-center">Общий итог</th>
            <th class="t-center">НДС</th>
            <th class="t-center">Себ-ть</th>
            <th class="t-center">Прибыль</th>
            <th class="t-center">Налог (7%)</th>
            <th class="t-center">Маржа</th>
            <th class="t-center">Продажа/шт</th>
            <th class="t-center">Итог/шт</th>
            <th class="t-center">Маржа/шт</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length"><td colspan="21" class="text-center text-muted">Нет данных</td></tr>
          <tr v-for="r in rows" :key="r.sdate">
            <td class="week-pos">
              <button class="week-eye" title="Структура затрат за неделю" @click.stop="openBreakdown(r)">
                <i class="bi bi-eye"></i>
              </button>&nbsp;&nbsp;{{ r.sdate }}
            </td>
            <td>{{ fmt0(r.qnt) }}</td>
            <td style="font-weight:bold">{{ fmt0(r.amount) }}</td>
            <td class="col-cost">{{ fmt0(r.commission) }}</td>
            <td class="col-cost">{{ fmt0(r.f_acquiring_fee) }}</td>
            <td class="col-cost"><button v-if="num(r.f_acceptance)" class="wb-cell-link" title="Детализация приёмки" @click.stop="openCell('acceptance', r)">{{ fmt0(r.f_acceptance) }}</button><template v-else>{{ fmt0(r.f_acceptance) }}</template></td>
            <td class="col-cost" style="font-weight:500"><button v-if="num(r.f_delivery)" class="wb-cell-link" title="Детализация логистики" @click.stop="openCell('delivery', r)">{{ fmt0(r.f_delivery) }}</button><template v-else>{{ fmt0(r.f_delivery) }}</template></td>
            <td class="col-cost" style="font-weight:500"><button v-if="num(r.f_storage_fee)" class="wb-cell-link" title="Детализация хранения" @click.stop="openCell('storage', r)">{{ fmt0(r.f_storage_fee) }}</button><template v-else>{{ fmt0(r.f_storage_fee) }}</template></td>
            <td class="col-cost"><button v-if="num(r.f_penalty)" class="wb-cell-link" title="Детализация штрафов" @click.stop="openCell('penalty', r)">{{ fmt0(r.f_penalty) }}</button><template v-else>{{ fmt0(r.f_penalty) }}</template></td>
            <td class="col-good"><button v-if="num(r.f_otziv)" class="wb-cell-link" title="Детализация отзывов" @click.stop="openCell('otziv', r)">{{ fmt0(r.f_otziv) }}</button><template v-else>{{ fmt0(r.f_otziv) }}</template></td>
            <td class="col-info"><button v-if="num(r.f_adv)" class="wb-cell-link" title="Детализация рекламы" @click.stop="openCell('adv', r)">{{ fmt0(r.f_adv) }}</button><template v-else>{{ fmt0(r.f_adv) }}</template></td>
            <td class="col-cost"><button v-if="num(r.f_cashback)" class="wb-cell-link" title="Детализация кэшбекка" @click.stop="openCell('cashback', r)">{{ fmt0(r.f_cashback) }}</button><template v-else>{{ fmt0(r.f_cashback) }}</template></td>
            <td :class="r.net_profit<0?'t-neg fw-bold':'t-pos fw-bold'">{{ fmt0(r.net_profit) }}</td>
            <td>{{ fmt0(r.total_nds) }}</td>
            <td>{{ fmt0(r.total_cost) }}</td>
            <td :class="[r.profit_before_tax<0?'t-neg':'t-pos','col-profit']" style="font-weight:bold">{{ fmt0(r.profit_before_tax) }}</td>
            <td class="col-warn">{{ fmt0(r.tax_amount) }}</td>
            <td :class="r.clean_margin<0?'t-neg fw-bold':'t-pos fw-bold'">{{ fmt0(r.clean_margin) }}</td>
            <td class="col-per-item" style="font-style:italic">{{ fmt2(r.amount_per_item) }}</td>
            <td :class="[r.profit_per_item<0?'t-neg':'t-pos','col-per-item']" style="font-weight:bold; font-style:italic">{{ fmt2(r.profit_per_item) }}</td>
            <td :class="[r.clear_per_item<0?'t-neg':'t-pos','col-per-item']" style="font-weight:bold; font-style:italic">{{ fmt2(r.clear_per_item) }}</td>
          </tr>
        </tbody>
        <tfoot v-if="rows.length">
          <tr class="tbl__total">
            <td></td>
            <td>{{ fmt0(sum('qnt')) }}</td>
            <td>{{ fmt0(sum('amount')) }}</td>
            <td>{{ fmt0(sum('commission')) }}</td>
            <td>{{ fmt0(sum('f_acquiring_fee')) }}</td>
            <td>{{ fmt0(sum('f_acceptance')) }}</td>
            <td>{{ fmt0(sum('f_delivery')) }}</td>
            <td>{{ fmt0(sum('f_storage_fee')) }}</td>
            <td>{{ fmt0(sum('f_penalty')) }}</td>
            <td>{{ fmt0(sum('f_otziv')) }}</td>
            <td>{{ fmt0(sum('f_adv')) }}</td>
            <td>{{ fmt0(sum('f_cashback')) }}</td>
            <td>{{ fmt0(sum('net_profit')) }}</td>
            <td>{{ fmt0(sum('total_nds')) }}</td>
            <td>{{ fmt0(sum('total_cost')) }}</td>
            <td>{{ fmt0(sum('profit_before_tax')) }}</td>
            <td>{{ fmt0(sum('tax_amount')) }}</td>
            <td>{{ fmt0(sum('clean_margin')) }}</td>
            <td colspan="3"></td>
          </tr>
        </tfoot>
      </table>
    </div>
    <MarginBreakdownPopup v-if="breakdownRow" :open="true" :row="breakdownRow" :period="weekPeriod(breakdownRow.sdate)" @close="breakdownRow = null" @logistics="onLogistics" />
    <MarginBreakdownModal
      v-if="cellModal"
      :kind="cellModal.kind"
      basis="product"
      :date-from="cellModal.dateFrom"
      :date-to="cellModal.dateTo"
      :nm-id="cellModal.nmId"
      @close="cellModal = null"
    />
  </div>
</template>
<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import MarginBreakdownPopup from '../profit/MarginBreakdownPopup.vue'
import MarginBreakdownModal from '../profit/MarginBreakdownModal.vue'
import type { MarginKind } from '@/api/margin'
const props = withDefaults(defineProps<{
  rows: any[]
  isLoading?: boolean
  title?: string
  card?: any
  nmId?: string | number
}>(), { isLoading:false, title:'Аналитика продаж по неделям' })
const tbl = ref<HTMLTableElement|null>(null)
const wrapRef = ref<HTMLDivElement|null>(null)
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const num = (v:any)=> Number(v)||0
const sum = (k:string)=> props.rows.reduce((a:number,r:any)=> a+(Number(r[k])||0),0)

// Попап «Структура затрат» по неделе (данные карточки — из card, nm_id — из строки отчёта)
const breakdownRow = ref<any>(null)
const card = computed(()=> props.card || {})
const weekPeriod = (sdate: string) => {
  if (!sdate) return ''
  const end = new Date(new Date(sdate + 'T00:00:00Z').getTime() + 6 * 864e5).toISOString().slice(0, 10)
  return `${sdate} — ${end}`
}
const openBreakdown = (r: any) => {
  breakdownRow.value = {
    ...r,
    title: card.value.title || '',
    nm_id: card.value.nmID || props.nmId || '',
    vendor_code: card.value.vendorCode || '',
  }
}

// Модалка-расшифровка значения колонки затрат (период = неделя строки)
const cellModal = ref<{ kind: MarginKind, dateFrom: string, dateTo: string, nmId: number | null } | null>(null)
const openCell = (kind: MarginKind, r: any) => {
  if (!r?.sdate) return
  const end = new Date(new Date(r.sdate + 'T00:00:00Z').getTime() + 6 * 864e5).toISOString().slice(0, 10)
  cellModal.value = {
    kind,
    dateFrom: r.sdate,
    dateTo: end,
    nmId: Number(card.value.nmID || props.nmId) || null,
  }
}
// Расшифровка «Логистики» из попапа затрат — тот же период, что у строки недели.
const onLogistics = (p: { dateFrom: string, dateTo: string }) => {
  breakdownRow.value = null
  cellModal.value = { kind: 'delivery', dateFrom: p.dateFrom, dateTo: p.dateTo, nmId: Number(card.value.nmID || props.nmId) || null }
}
const enableResize = ()=>{
  const t=tbl.value; if(!t) return
  t.querySelectorAll('th').forEach((th: Element)=>{
    const el=th as HTMLTableCellElement
    if(el.querySelector('.col-resizer')) return
    el.style.position='relative'
    const r=document.createElement('div')
    r.className='col-resizer'
    r.style.cssText='position:absolute;top:0;right:0;width:6px;height:100%;cursor:col-resize;user-select:none;z-index:1'
    el.appendChild(r)
    let sx=0, sw=0
    const onMove=(e:MouseEvent)=>{ const w=Math.max(40, sw+e.clientX - sx); el.style.width=w+'px'; (el.style as any).minWidth=w+'px'; t.style.width='100%' }
    const onUp=()=>{ document.removeEventListener('mousemove',onMove); document.removeEventListener('mouseup',onUp); document.body.style.cursor='' }
    r.addEventListener('mousedown',(e:MouseEvent)=>{ sx=e.clientX; sw=el.offsetWidth; document.body.style.cursor='col-resize'; document.addEventListener('mousemove',onMove); document.addEventListener('mouseup',onUp); e.preventDefault() })
  })
  const fit=()=>{ if(!t) return; t.style.width='100%' }
  window.addEventListener('resize', fit); fit()
}
onMounted(()=> nextTick(enableResize))
watch(()=>props.rows, ()=>nextTick(enableResize))
const exportExcel = async()=>{
  if(!props.rows.length) return
  const XLSX=await import('xlsx')
  const data=props.rows.map((r:any)=>({
    'Год-Неделя':r.sdate,'Кол-во':r.qnt,'Продажи':r.amount,'Ком WB':r.commission,'Эквайринг':r.f_acquiring_fee,'Приёмка':r.f_acceptance,'Логистика':r.f_delivery,'Хранение':r.f_storage_fee,'Штрафы':r.f_penalty,'Отзывы':r.f_otziv,'Реклама':r.f_adv,'Кэшбек':r.f_cashback,'Общий итог':r.net_profit,'НДС':r.total_nds,'Себ-ть':r.total_cost,'Прибыль':r.profit_before_tax,'Налог':r.tax_amount,'Маржа':r.clean_margin,'Продажа/шт':r.amount_per_item,'Итог/шт':r.profit_per_item,'Маржа/шт':r.clear_per_item
  }))
  const ws=XLSX.utils.json_to_sheet(data)
  const wb=XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb,ws,'Недели')
  XLSX.writeFile(wb,`weekly_${Date.now()}.xlsx`)
}
</script>
<style scoped>
/* цвета колонок — из токенов темы */
.col-cost{color:var(--bad)}
.col-good{color:var(--good)}
.col-info{color:var(--info)}
.col-warn{color:var(--warn)}
/* подсветка «прибыли» и «на единицу» — перебиваем зебру темы */
.tbl tbody td.col-profit{background:var(--warn-tint)}
.tbl tbody td.col-per-item{background:var(--surface-2)}
/* Глазик структуры затрат в первой колонке (слева от недели), абсолютом — не ломает высоту строки */
.week-pos{position:relative; text-align:center; font-weight:bold; color:var(--ink); white-space:nowrap}
/* резерв слева, чтобы глазик не наезжал на дату (перекрываем компактные padding темы) */
.tbl tbody td.week-pos{padding-left:20px}
.week-eye{position:absolute; left:5px; top:50%; transform:translateY(-50%); border:0; background:transparent; color:var(--ink-muted); padding:0; font-size:11px; line-height:1; cursor:pointer}
.week-eye:hover{color:var(--brand)}
</style>
