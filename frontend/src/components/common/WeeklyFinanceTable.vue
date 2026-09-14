<template>
  <div class="card grid_wbstat" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
    <div class="card-header text-white d-flex justify-content-between align-items-center" style="background:#1a9a6b; font-weight:700">
      <span>{{ title }}</span>
      <button class="btn btn-sm btn-light" style="font-size:12px; padding:4px 12px; border-radius:6px" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
    </div>
    <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
    <div v-else style="overflow-x:auto" ref="wrapRef">
      <table ref="tbl" class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:12px; width:100%">
        <thead>
          <tr>
            <th style="width:90px; text-align:center; vertical-align:middle">Год-Неделя</th>
            <th style="text-align:center; vertical-align:middle">Кол-во</th>
            <th style="text-align:center; vertical-align:middle">Продажи</th>
            <th style="text-align:center; vertical-align:middle">Ком. WB</th>
            <th style="text-align:center; vertical-align:middle">Эквайринг</th>
            <th style="text-align:center; vertical-align:middle">Логистика</th>
            <th style="text-align:center; vertical-align:middle">Штрафы</th>
            <th style="text-align:center; vertical-align:middle">Отзывы</th>
            <th style="text-align:center; vertical-align:middle">Реклама</th>
            <th style="text-align:center; vertical-align:middle">Кэшбек</th>
            <th style="text-align:center; vertical-align:middle; background:#e8f8f5">Общий итог</th>
            <th style="text-align:center; vertical-align:middle">НДС</th>
            <th style="text-align:center; vertical-align:middle">Себ-ть</th>
            <th style="text-align:center; vertical-align:middle; background:#fcf3cf">Прибыль</th>
            <th style="text-align:center; vertical-align:middle; color:#d35400">Налог (7%)</th>
            <th style="text-align:center; vertical-align:middle; background:#d4efdf">Маржа</th>
            <th style="text-align:center; vertical-align:middle">Продажа/шт</th>
            <th style="text-align:center; vertical-align:middle">Итог/шт</th>
            <th style="text-align:center; vertical-align:middle">Маржа/шт</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length"><td colspan="19" class="text-center text-muted">Нет данных</td></tr>
          <tr v-for="r in rows" :key="r.sdate">
            <td style="text-align:center; font-weight:bold; color:#2c3e50">{{ r.sdate }}</td>
            <td style="text-align:right">{{ fmt0(r.qnt) }}</td>
            <td style="text-align:right; font-weight:bold">{{ fmt0(r.amount) }}</td>
            <td style="text-align:right; color:#c0392b">{{ fmt0(r.commission) }}</td>
            <td style="text-align:right; color:#c0392b">{{ fmt0(r.f_acquiring_fee) }}</td>
            <td style="text-align:right; color:#c0392b; font-weight:500">{{ fmt0(r.f_delivery) }}</td>
            <td style="text-align:right; color:#c0392b">{{ fmt0(r.f_penalty) }}</td>
            <td style="text-align:right; color:#16a085">{{ fmt0(r.f_otziv) }}</td>
            <td style="text-align:right; color:#2980b9">{{ fmt0(r.f_adv) }}</td>
            <td style="text-align:right; color:#c0392b">{{ fmt0(r.f_cashback) }}</td>
            <td :class="r.net_profit<0?'table-danger text-danger fw-bold':'table-success text-success fw-bold'" style="text-align:right">{{ fmt0(r.net_profit) }}</td>
            <td style="text-align:right">{{ fmt0(r.total_nds) }}</td>
            <td style="text-align:right">{{ fmt0(r.total_cost) }}</td>
            <td :class="r.profit_before_tax<0?'text-danger':'text-success'" style="text-align:right; font-weight:bold; background:#fefde7">{{ fmt0(r.profit_before_tax) }}</td>
            <td style="text-align:right; color:#e67e22">{{ fmt0(r.tax_amount) }}</td>
            <td :class="r.clean_margin<0?'table-danger text-danger fw-bold':'table-success text-success fw-bold'" style="text-align:right">{{ fmt0(r.clean_margin) }}</td>
            <td style="text-align:right; font-style:italic; background:#fafafa">{{ fmt2(r.amount_per_item) }}</td>
            <td :class="r.profit_per_item<0?'text-danger':'text-success'" style="text-align:right; font-weight:bold; font-style:italic; background:#fafafa">{{ fmt2(r.profit_per_item) }}</td>
            <td :class="r.clear_per_item<0?'text-danger':'text-success'" style="text-align:right; font-weight:bold; font-style:italic; background:#fafafa">{{ fmt2(r.clear_per_item) }}</td>
          </tr>
        </tbody>
        <tfoot v-if="rows.length">
          <tr class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px">
            <td style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('qnt')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('amount')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('commission')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('f_acquiring_fee')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('f_delivery')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('f_penalty')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('f_otziv')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('f_adv')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('f_cashback')) }}</td>
            <td style="text-align:right; color:#27ae60; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('net_profit')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('total_nds')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('total_cost')) }}</td>
            <td style="text-align:right; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('profit_before_tax')) }}</td>
            <td style="text-align:right; color:#e67e22; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('tax_amount')) }}</td>
            <td style="text-align:right; color:#196f3d; padding:4px 6px; border-top:2px solid #8A2BE0">{{ fmt0(sum('clean_margin')) }}</td>
            <td colspan="3" style="padding:4px 6px; border-top:2px solid #8A2BE0"></td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
const props = withDefaults(defineProps<{
  rows: any[]
  isLoading?: boolean
  title?: string
}>(), { isLoading:false, title:'Аналитика продаж по неделям' })
const tbl = ref<HTMLTableElement|null>(null)
const wrapRef = ref<HTMLDivElement|null>(null)
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const sum = (k:string)=> props.rows.reduce((a:number,r:any)=> a+(Number(r[k])||0),0)
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
watch(()=>props.rows, ()=> nextTick(enableResize))
const exportExcel = async()=>{
  if(!props.rows.length) return
  const XLSX=await import('xlsx')
  const data=props.rows.map((r:any)=>({
    'Год-Неделя':r.sdate,'Кол-во':r.qnt,'Продажи':r.amount,'Ком WB':r.commission,'Эквайринг':r.f_acquiring_fee,'Логистика':r.f_delivery,'Штрафы':r.f_penalty,'Отзывы':r.f_otziv,'Реклама':r.f_adv,'Кэшбек':r.f_cashback,'Общий итог':r.net_profit,'НДС':r.total_nds,'Себ-ть':r.total_cost,'Прибыль':r.profit_before_tax,'Налог':r.tax_amount,'Маржа':r.clean_margin,'Продажа/шт':r.amount_per_item,'Итог/шт':r.profit_per_item,'Маржа/шт':r.clear_per_item
  }))
  const ws=XLSX.utils.json_to_sheet(data)
  const wb=XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb,ws,'Недели')
  XLSX.writeFile(wb,`weekly_${Date.now()}.xlsx`)
}
</script>
<style scoped>
/* резина B как OrdersFeed: th normal break-word, td 12px; condensed-паддинги как gridv.css */
.grid_wbstat th{white-space:normal !important; word-break:break-word; font-weight:500 !important; color:#444; text-align:center; vertical-align:middle; padding:4px !important}
.grid_wbstat td{padding:4px !important}
.grid_wbstat td:not(:first-child){font-size:12px !important; vertical-align:middle}
/* Bootstrap 5 table-striped красит ячейки inset box-shadow поверх фона tr — гасим его, фон задаем самим td */
.kv-totals > td{background-color:#f2e7c3 !important; box-shadow:none !important}
.col-resizer:hover{background:#4A3A8C; opacity:.2}
</style>
