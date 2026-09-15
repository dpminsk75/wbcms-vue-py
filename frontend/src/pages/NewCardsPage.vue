<template>
  <div class="site-index container-xxl page-new-cards">
    <div class="row" style="margin-bottom:20px">
      <div class="nav_div col-md-2">
        <SideMenu />
      </div>
      <div class="col-md-10">
        <div class="d-flex flex-wrap align-items-center justify-content-between mb-3">
          <h1 class="h4 mb-2 mb-md-0">Новые карточки</h1>
          <span class="badge bg-secondary" style="font-size:13px">Найдено: {{ rows.length }}</span>
        </div>

        <div class="card mb-4" style="border:1px solid var(--bs-border-color-translucent)">
          <div class="card-body p-3 bg-light">
            <div class="row g-3 align-items-end">
              <div class="col-12 col-md-2">
                <label class="form-label" style="font-size:12px; font-weight:600">Дата с</label>
                <input type="date" v-model="dateFrom" class="form-control form-control-sm">
              </div>
              <div class="col-12 col-md-2">
                <label class="form-label" style="font-size:12px; font-weight:600">Дата по</label>
                <input type="date" v-model="dateTo" class="form-control form-control-sm">
              </div>
              <div class="col-12 col-md-3">
                <label class="form-label" style="font-size:12px; font-weight:600">Часть названия</label>
                <input type="text" v-model="title" placeholder="например, журнал" class="form-control form-control-sm" @keyup.enter="applyFilters">
              </div>
              <div class="col-12 col-md-3">
                <label class="form-label" style="font-size:12px; font-weight:600">Сортировка</label>
                <select v-model="sort" class="form-select form-select-sm">
                  <option value="created_desc">По дате (новые → старые)</option>
                  <option value="created_asc">По дате (старые → новые)</option>
                  <option value="nmid_asc">По nmID (↑)</option>
                  <option value="nmid_desc">По nmID (↓)</option>
                  <option value="title_asc">По названию (А → Я)</option>
                  <option value="title_desc">По названию (Я → А)</option>
                </select>
              </div>
              <div class="col-12 col-md-2 d-flex gap-2">
                <button class="btn btn-primary btn-sm flex-grow-1" @click="applyFilters">Показать</button>
                <button class="btn btn-outline-secondary btn-sm" @click="resetFilters">Сброс</button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm me-2"></span> Загрузка...</div>
        <div v-else-if="rows.length===0" class="alert alert-warning">Карточки за выбранный период не найдены. Попробуйте изменить даты или фильтр по названию.</div>
        <div v-else class="card mb-4" style="border:1px solid var(--bs-border-color-translucent); border-radius:8px; overflow:hidden">
          <div class="card-header text-white" style="font-size:13px; font-weight:700; background-color:#4b4b4b; padding:10px 15px">
            Новые карточки: {{ dateFrom }} — {{ dateTo }} ({{ rows.length }})<span v-if="title"> · фильтр: «{{ title }}»</span>
          </div>
          <div class="card-body p-3 bg-light">
            <div class="row g-3">
              <div v-for="c in rows" :key="c.nmID" class="col-lg-4 col-md-6 col-12">
                <div class="d-flex p-2 h-100" style="background:#fff; border:1px solid #e2e8f0; border-radius:8px; align-items:center; box-shadow:0 1px 3px rgba(0,0,0,0.04)">
                  <div class="flex-shrink-0 me-3" style="width:80px; height:110px; border-radius:6px; overflow:hidden; background:#f1f1f1; display:flex; align-items:center; justify-content:center; border:1px solid #e2e8f0">
                    <img v-if="imgSrc(c)" :src="imgSrc(c)!" alt="Фото" style="width:100%; height:100%; object-fit:cover">
                    <div v-else style="color:#4e4e53"><svg fill="none" height="24" viewBox="-2 -2 24 24" width="24" xmlns="http://www.w3.org/2000/svg"><path clip-rule="evenodd" d="M2 0H18C19.1046 0 20 0.89543 20 2V18C20 19.1046 19.1046 20 18 20H2C0.89543 20 0 19.1046 0 18V2C0 0.89543 0.89543 0 2 0ZM2 2V13.5858L6 9.58579L9.5 13.0858L16 6.58579L18 8.58579V2H2ZM2 18V16.4142L6 12.4142L11.5858 18H2ZM18 18H14.4142L10.9142 14.5L16 9.41421L18 11.4142V18ZM12 6C12 4.34315 10.6569 3 9 3C7.34315 3 6 4.34315 6 6C6 7.65685 7.34315 9 9 9C10.6569 9 12 7.65685 12 6ZM8 6C8 5.44772 8.44771 5 9 5C9.55229 5 10 5.44772 10 6C10 6.55228 9.55229 7 9 7C8.44771 7 8 6.55228 8 6Z" fill="#4e4e53" fill-rule="evenodd"/></svg></div>
                  </div>
                  <div class="flex-grow-1" style="display:flex; flex-direction:column; justify-content:center; min-width:0">
                    <div style="font-size:14px; font-weight:500; color:#2c3e50; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis" :title="c.title || 'Без названия'">{{ c.title || 'Без названия' }}</div>
                    <div style="font-size:12px; color:#6c757d; margin-bottom:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">Журналы · {{ c.brand || 'Делаем сами. Толока' }}</div>
                    <div style="font-size:12px; color:#495057; margin-bottom:2px">Арт WB: <a :href="'/wb/detail?DPFilterForm[nm_id]='+c.nmID" target="_blank" style="text-decoration:none; color:#0d6efd; font-weight:500">{{ c.nmID }}</a></div>
                    <div style="font-size:12px; color:#495057; white-space:nowrap; overflow:hidden; text-overflow:ellipsis" :title="c.vendorCode || '—'">Арт прод: {{ c.vendorCode || '—' }}</div>
                    <div style="font-size:11px; color:#adb5bd; margin-top:4px; border-top:1px dashed #e9ecef; padding-top:4px">Добавлена: {{ fmtDate(c.created_at) }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-new-cards.css'
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../api/dashboard'
import SideMenu from '../components/dashboard/SideMenu.vue'

const route = useRoute()
const router = useRouter()

const today = new Date()
const defFrom = new Date(Date.now() - 14*864e5).toISOString().slice(0,10)
const defTo = today.toISOString().slice(0,10)

const dateFrom = ref((route.query.dateFrom as string) || defFrom)
const dateTo = ref((route.query.dateTo as string) || defTo)
const title = ref((route.query.title as string) || '')
const sort = ref((route.query.sort as string) || 'created_desc')

const q = computed(()=> ({ dateFrom: dateFrom.value, dateTo: dateTo.value, title: title.value, sort: sort.value }))

const { data: rowsRaw, isLoading } = useQuery({
  queryKey: computed(()=> ['new-cards-page', q.value.dateFrom, q.value.dateTo, q.value.title, q.value.sort] as const),
  queryFn: ()=> (dashboardApi as any).newCards({ dateFrom: q.value.dateFrom, dateTo: q.value.dateTo, title: q.value.title, sort: q.value.sort }),
  initialData: [] as any,
})
const rows = computed(()=> {
  const v = rowsRaw.value as any
  return Array.isArray(v) ? v : (v?.items ?? [])
})

const applyFilters = ()=>{
  router.replace({ query: { ...route.query, dateFrom: dateFrom.value, dateTo: dateTo.value, title: title.value || undefined, sort: sort.value } })
}
const resetFilters = ()=>{
  dateFrom.value = defFrom
  dateTo.value = defTo
  title.value = ''
  sort.value = 'created_desc'
  router.replace({ query: {} })
}

watch(()=> route.query, (nq:any)=>{
  if(nq.dateFrom) dateFrom.value = nq.dateFrom as string
  if(nq.dateTo) dateTo.value = nq.dateTo as string
  if(nq.sort) sort.value = nq.sort as string
  if(nq.title !== undefined) title.value = nq.title as string
})

const imgSrc = (c:any)=>{
  if(!c.photos) return null
  try{ let l = typeof c.photos==='string' ? JSON.parse(c.photos) : c.photos; if(typeof l==='string') l=JSON.parse(l); if(Array.isArray(l)&&l.length) return l[0] }catch{}
  return null
}
const fmtDate = (d:string)=> d ? new Date(d).toLocaleDateString('ru-RU') : '—'
</script>
