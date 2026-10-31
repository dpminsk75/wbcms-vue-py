<template>
  <div class="row">
    <div class="col-md-6">
      <div class="tbl-card tbl-card--compact">
        <div class="card__hd">На складах</div>
        <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
        <div v-else class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr><th>Склад</th><th class="t-center">Доступно (шт)</th></tr>
              <tr v-if="warehouse.length" class="tbl__total tbl__total--top"><td></td><td>{{ fmt0(warehouse.reduce((a,b)=>a+(b.quantity||0),0)) }}</td></tr>
            </thead>
            <tbody>
              <tr v-if="!warehouse.length"><td colspan="2" class="text-center text-muted">Нет остатков</td></tr>
              <tr v-for="r in warehouse" :key="r.warehouse_name"><td>{{ r.warehouse_name }}</td><td>{{ fmt0(r.quantity) }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="tbl-card tbl-card--compact">
        <div class="card__hd">В пути</div>
        <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span></div>
        <div v-else class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr><th>Склад отправки</th><th class="t-center">К клиенту</th><th class="t-center">От клиента</th></tr>
              <tr v-if="inWay.length" class="tbl__total tbl__total--top"><td></td><td>{{ fmt0(inWay.reduce((a,b)=>a+(b.in_way_to_client||0),0)) }}</td><td>{{ fmt0(inWay.reduce((a,b)=>a+(b.in_way_from_client||0),0)) }}</td></tr>
            </thead>
            <tbody>
              <tr v-if="!inWay.length"><td colspan="3" class="text-center text-muted">Нет в пути</td></tr>
              <tr v-for="r in inWay" :key="r.warehouse_name"><td>{{ r.warehouse_name }}</td><td>{{ fmt0(r.in_way_to_client) }}</td><td>{{ fmt0(r.in_way_from_client) }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { api } from '@/api/client'
const props = defineProps<{ nmId: string|number }>()
const warehouse=ref<any[]>([])
const inWay=ref<any[]>([])
const loading=ref(false)
const fmt0=(v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fetchStocks=async()=>{
  if(!props.nmId) return
  loading.value=true
  try{
    const { data:d } = await api.get(`/api/wb/detail/stocks?nm_id=${props.nmId}`)
    warehouse.value=d.warehouse||[]; inWay.value=d.inWay||[]
  }catch{ warehouse.value=[]; inWay.value=[] } finally{ loading.value=false }
}
onMounted(fetchStocks)
watch(()=>props.nmId, fetchStocks)
</script>
