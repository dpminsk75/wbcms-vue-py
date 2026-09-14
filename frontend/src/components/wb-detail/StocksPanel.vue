<template>
  <div class="row">
    <div class="col-md-6">
      <div class="card grid_wbstat" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
        <div class="card-header text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; font-size:13px; line-height:1.5; padding:4px 8px">На складах</div>
        <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
        <div v-else style="overflow-x:auto">
          <table class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:12px; width:100%; table-layout:auto">
            <thead>
              <tr><th style="text-align:center; padding:4px">Склад</th><th style="text-align:center; white-space:nowrap; padding:4px">Доступно (шт)</th></tr>
              <tr v-if="warehouse.length" class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px"><td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td><td style="text-align:right; color:#5A1C9C; font-weight:700; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(warehouse.reduce((a,b)=>a+(b.quantity||0),0)) }}</td></tr>
            </thead>
            <tbody>
              <tr v-if="!warehouse.length"><td colspan="2" class="text-center text-muted">Нет остатков</td></tr>
              <tr v-for="r in warehouse" :key="r.warehouse_name"><td style="padding:4px">{{ r.warehouse_name }}</td><td class="text-end" style="padding:4px">{{ fmt0(r.quantity) }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card grid_wbstat" style="border:1px solid var(--bs-border-color-translucent); border-radius:12px; overflow:hidden">
        <div class="card-header text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); font-weight:700; font-size:13px; line-height:1.5; padding:4px 8px">В пути</div>
        <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
        <div v-else style="overflow-x:auto">
          <table class="table table-bordered table-striped table-hover kv-grid-table mb-0" style="font-size:12px; width:100%; table-layout:auto">
            <thead>
              <tr><th style="text-align:center; padding:4px">Склад отправки</th><th class="text-end" style="white-space:nowrap; padding:4px">К клиенту</th><th class="text-end" style="white-space:nowrap; padding:4px">От клиента</th></tr>
              <tr v-if="inWay.length" class="kv-totals" style="font-weight:700; background:#f2e7c3; font-size:11px"><td style="padding:4px 6px; border-bottom:2px solid #8A2BE0"></td><td style="text-align:right; color:#5A1C9C; font-weight:700; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(inWay.reduce((a,b)=>a+(b.in_way_to_client||0),0)) }}</td><td style="text-align:right; color:#5A1C9C; font-weight:700; padding:4px 6px; border-bottom:2px solid #8A2BE0">{{ fmt0(inWay.reduce((a,b)=>a+(b.in_way_from_client||0),0)) }}</td></tr>
            </thead>
            <tbody>
              <tr v-if="!inWay.length"><td colspan="3" class="text-center text-muted">Нет в пути</td></tr>
              <tr v-for="r in inWay" :key="r.warehouse_name"><td style="padding:4px">{{ r.warehouse_name }}</td><td class="text-end" style="padding:4px">{{ fmt0(r.in_way_to_client) }}</td><td class="text-end" style="padding:4px">{{ fmt0(r.in_way_from_client) }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
const props = defineProps<{ nmId: string|number }>()
const warehouse=ref<any[]>([])
const inWay=ref<any[]>([])
const loading=ref(false)
const fmt0=(v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fetchStocks=async()=>{
  if(!props.nmId) return
  loading.value=true
  try{
    const r=await fetch(`/api/wb/detail/stocks?nm_id=${props.nmId}`)
    const d=await r.json()
    warehouse.value=d.warehouse||[]; inWay.value=d.inWay||[]
  }catch{ warehouse.value=[]; inWay.value=[] } finally{ loading.value=false }
}
onMounted(fetchStocks)
watch(()=>props.nmId, fetchStocks)
</script>
<style scoped>
.grid_wbstat th{white-space:normal !important; word-break:break-word; font-weight:500 !important; text-align:center; vertical-align:middle}
/* Bootstrap 5 table-striped красит ячейки inset box-shadow поверх фона tr — гасим его, фон задаем самим td */
.kv-totals > td{background-color:#f2e7c3 !important; box-shadow:none !important}
</style>
