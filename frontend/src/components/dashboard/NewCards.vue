<template>
  <div v-if="busy || hasData || isError">
    <div class="card expandable-container" :class="{'is-expanded': expanded}" :style="{maxHeight: expanded ? '20000px' : '340px', overflow:'hidden', position:'relative', transition:'max-height .5s', border:'1px solid var(--bs-border-color-translucent)', borderRadius:'8px', background:'#fff'}">
      <div class="card-header text-white d-flex justify-content-between align-items-center" style="font-size:13px; font-weight:700; background-color:#4b4b4b; padding:10px 15px">
        <router-link to="/site/new-cards" class="text-white" style="text-decoration:none">Новые карточки за последние 14 дней ({{ rows.length }})</router-link>
        <router-link to="/site/new-cards" class="btn btn-sm btn-light py-0 px-2" style="font-size:11px; font-weight:600; text-decoration:none">Все карточки →</router-link>
      </div>
      <div class="card-body p-3 bg-light" style="background:#f8fafc">
        <div v-if="isLoading" style="text-align:center; font-size:12px; padding:20px">Загрузка...</div>
        <div v-else-if="rows.length===0" style="text-align:center; font-size:12px; color:#6b7280; padding:20px">Новинок нет</div>
        <div v-else class="row g-3">
          <div v-for="c in rows" :key="c.nmID" class="col-lg-4 col-md-6 col-12">
            <div class="d-flex p-2 h-100" style="background:#fff; border:1px solid #e2e8f0; border-radius:8px; align-items:center; box-shadow:0 1px 3px rgba(0,0,0,0.04)">
              <div class="flex-shrink-0 me-3" style="width:80px; height:110px; border-radius:6px; overflow:hidden; background:#f1f1f1; display:flex; align-items:center; justify-content:center; border:1px solid #e2e8f0">
                <img v-if="imgSrc(c)" :src="imgSrc(c)!" alt="Фото" style="width:100%; height:100%; object-fit:cover">
                <div v-else style="color:#4e4e53">
                  <svg fill="none" height="24" viewBox="-2 -2 24 24" width="24" xmlns="http://www.w3.org/2000/svg"><path clip-rule="evenodd" d="M2 0H18C19.1046 0 20 0.89543 20 2V18C20 19.1046 19.1046 20 18 20H2C0.89543 20 0 19.1046 0 18V2C0 0.89543 0.89543 0 2 0ZM2 2V13.5858L6 9.58579L9.5 13.0858L16 6.58579L18 8.58579V2H2ZM2 18V16.4142L6 12.4142L11.5858 18H2ZM18 18H14.4142L10.9142 14.5L16 9.41421L18 11.4142V18ZM12 6C12 4.34315 10.6569 3 9 3C7.34315 3 6 4.34315 6 6C6 7.65685 7.34315 9 9 9C10.6569 9 12 7.65685 12 6ZM8 6C8 5.44772 8.44771 5 9 5C9.55229 5 10 5.44772 10 6C10 6.55228 9.55229 7 9 7C8.44771 7 8 6.55228 8 6Z" fill="#4e4e53" fill-rule="evenodd"/></svg>
                </div>
              </div>
              <div class="flex-grow-1" style="display:flex; flex-direction:column; justify-content:center; min-width:0">
                <div style="font-size:14px; font-weight:500; color:#2c3e50; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis" :title="c.title || 'Без названия'">{{ c.title || 'Без названия' }}</div>
                <div style="font-size:12px; color:#6c757d; margin-bottom:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">Журналы · {{ c.brand || '—' }}</div>
                <div style="font-size:12px; color:#495057; margin-bottom:2px">Арт WB: <a :href="'/wb/detail?DPFilterForm[nm_id]='+c.nmID" target="_blank" style="text-decoration:none; color:#0d6efd; font-weight:500">{{ c.nmID }}</a></div>
                <div style="font-size:12px; color:#495057; white-space:nowrap; overflow:hidden; text-overflow:ellipsis" :title="c.vendorCode || '—'">Арт прод: {{ c.vendorCode || '—' }}</div>
                <div style="font-size:11px; color:#adb5bd; margin-top:4px; border-top:1px dashed #e9ecef; padding-top:4px">Добавлена: {{ fmtDate(c.created_at) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="expand-btn-wrapper" style="text-align:center; margin:10px 0 20px">
      <button class="btn btn-outline-primary btn-sm" style="font-size:12px; padding:4px 16px; border-radius:6px" @click="expanded=!expanded">{{ expanded ? 'Свернуть' : 'Увидеть больше' }}</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
const auth = useAuthStore()
const report = inject<(n:string,h:boolean)=>void>('dashReport', ()=>{})
const expanded = ref(false)
const { data: rowsRaw, isLoading, isFetching, isError } = useQuery({ queryKey: computed(() => ['new-cards', auth.companyId] as const), queryFn: ()=> (dashboardApi as any).newCards({}), initialData: [] as any })
const busy = computed(() => isLoading.value || isFetching.value)
const rows = computed(()=> {
  const v = rowsRaw.value as any
  if(Array.isArray(v)) return v
  return v?.items ?? []
})
const imgSrc = (c:any)=>{
  if(!c.photos) return null
  try{
    let list = typeof c.photos==='string' ? JSON.parse(c.photos) : c.photos
    if(typeof list==='string') list = JSON.parse(list)
    if(Array.isArray(list) && list.length) return list[0]
  }catch{}
  return null
}
const fmtDate = (d:string)=> d ? new Date(d).toLocaleDateString('ru-RU') : '—'
const hasData = computed(() => rows.value.length > 0)
watchEffect(() => { if (!busy.value) report('new-cards', hasData.value || !!isError.value) })
</script>
<style scoped>
.expandable-container:not(.is-expanded)::after{content:""; position:absolute; bottom:0; left:0; width:100%; height:50px; background:linear-gradient(transparent, #f8fafc); pointer-events:none}
</style>
