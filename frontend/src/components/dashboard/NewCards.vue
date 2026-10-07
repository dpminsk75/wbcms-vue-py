<template>
  <div v-if="busy || hasData || isError">
    <div class="page-new-cards__head">
      <router-link to="/site/new-cards" class="page-new-cards__title">Новые карточки ({{ rows.length }})</router-link>
    </div>
    <div style="text-align:center; font-size:12px; padding:20px" v-if="isLoading">Загрузка...</div>
    <div v-else-if="rows.length===0" style="text-align:center; font-size:12px; color:#6b7280; padding:20px">Новинок нет</div>
    <div v-else ref="trackRef" class="page-new-cards__track"
      @pointerdown="dragStart" @pointermove="dragMove" @pointerup="dragEnd" @pointerleave="dragEnd">
      <div v-for="c in rows" :key="c.nmID" class="page-new-cards__item">
        <div class="d-flex p-2 h-100" style="background:#fff; border:1px solid #d3d9e0; border-radius:12px; align-items:center; box-shadow:0 1px 4px rgba(16,24,40,0.08)">
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
</template>
<script setup lang="ts">
import { ref, computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
const auth = useAuthStore()
const report = inject<(n:string,h:boolean)=>void>('dashReport', ()=>{})
const { data: rowsRaw, isLoading, isFetching, isError } = useQuery({ queryKey: computed(() => ['new-cards', auth.companyId] as const), queryFn: ()=> (dashboardApi as any).newCards({}), initialData: [] as any })
const busy = computed(() => isLoading.value || isFetching.value)
const rows = computed(()=> {
  const v = rowsRaw.value as any
  if(Array.isArray(v)) return v
  return v?.items ?? []
})
const imgSrc = (c:any)=>{  if(!c.photos) return null
  try{
    let list = typeof c.photos==='string' ? JSON.parse(c.photos) : c.photos
    if(typeof list==='string') list = JSON.parse(list)
    if(Array.isArray(list) && list.length) return list[0]
  }catch{}
  return null
}
import { useDateFmt } from '../../composables/useDateFmt'
const { fmtDate } = useDateFmt()
const trackRef = ref<HTMLElement | null>(null)
let dragOn = false
let dragX = 0
let dragScroll = 0
function dragStart(e: PointerEvent) {
  const el = trackRef.value
  if (!el) return
  dragOn = true
  dragX = e.clientX
  dragScroll = el.scrollLeft
  el.setPointerCapture?.(e.pointerId)
}
function dragMove(e: PointerEvent) {
  const el = trackRef.value
  if (!dragOn || !el) return
  el.scrollLeft = dragScroll - (e.clientX - dragX)
}
function dragEnd() {
  dragOn = false
}
const hasData = computed(() => rows.value.length > 0)
watchEffect(() => { if (!busy.value) report('new-cards', hasData.value || !!isError.value) })
</script>
<style scoped>
.page-new-cards__head { margin-bottom: 8px; }
.page-new-cards__title { font-size: 20px; font-weight: 700; color: #111827; text-decoration: none; }
.page-new-cards__title:hover { color: #8A2BE0; }
.page-new-cards__head { margin-bottom: 8px; }
.page-new-cards__title { font-size: 20px; font-weight: 700; color: #111827; text-decoration: none; }
.page-new-cards__title:hover { color: #8A2BE0; }
.page-new-cards__track { display: grid; grid-auto-flow: column; grid-template-rows: repeat(2, auto); gap: 12px; overflow-x: auto; scrollbar-width: none; cursor: grab; padding-bottom: 4px; }
.page-new-cards__track::-webkit-scrollbar { display: none; }
.page-new-cards__item { width: 340px; }
</style>
