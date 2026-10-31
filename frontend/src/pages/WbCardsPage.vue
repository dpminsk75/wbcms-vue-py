<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">Карточки WB</h1>
      <span class="badge bg-secondary">Всего: {{ total }}</span>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-body py-2">
        <div class="row g-2 align-items-end">
          <div class="col-auto">
            <label class="form-label small mb-1">nmID</label>
            <input v-model="f.nm_id" type="number" class="form-control form-control-sm" style="width:130px">
          </div>
          <div class="col-auto">
            <label class="form-label small mb-1">Артикул</label>
            <input v-model="f.vendor" type="text" class="form-control form-control-sm" style="width:150px">
          </div>
          <div class="col-auto">
            <label class="form-label small mb-1">Бренд</label>
            <select v-model="f.brand" class="form-select form-select-sm" style="width:160px">
              <option value="">—</option>
              <option v-for="b in filterOpts.brands" :key="b" :value="b">{{ b }}</option>
            </select>
          </div>
          <div class="col-auto">
            <label class="form-label small mb-1">Предмет</label>
            <select v-model="f.subject_name" class="form-select form-select-sm" style="width:200px">
              <option value="">—</option>
              <option v-for="s in filterOpts.subjectNames" :key="s" :value="s">{{ s }}</option>
            </select>
          </div>
          <div class="col-auto">
            <label class="form-label small mb-1">Название</label>
            <input v-model="f.title" type="text" class="form-control form-control-sm" style="width:220px">
          </div>
          <div class="col-auto">
            <div class="form-check mb-0">
              <input id="only-unused" v-model="f.only_unused" type="checkbox" class="form-check-input">
              <label class="form-check-label small" for="only-unused">Не в линейках</label>
            </div>
          </div>
          <div class="col-auto">
            <button class="btn btn-primary btn-sm" @click="search">
              <i class="bi bi-search me-1"></i>Показать
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="card shadow-sm">
      <div class="card-body p-0">
        <div v-if="loading" class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
        <div v-else-if="!rows.length" class="p-4 text-center text-muted">Ничего не найдено по фильтрам</div>
        <div v-else class="table-responsive">
          <table class="table table-bordered table-striped table-hover align-middle mb-0">
            <thead>
              <tr>
                <th style="width:110px">nmID</th>
                <th style="width:110px">imtID</th>
                <th>Артикул</th>
                <th>Название</th>
                <th>Бренд</th>
                <th>Предмет</th>
                <th class="text-center" style="width:110px">В линейках</th>
                <th style="width:110px">Создана</th>
                <th style="width:90px"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.nmID">
                <td>{{ r.nmID }}</td>
                <td>{{ r.imtID || '—' }}</td>
                <td class="fw-bold">{{ r.vendorCode }}</td>
                <td class="small text-truncate" style="max-width:340px" :title="r.title">{{ r.title }}</td>
                <td>{{ r.brand }}</td>
                <td class="small">{{ r.subjectName }}</td>
                <td class="text-center">
                  <span v-if="r.links_cnt" class="badge bg-success">{{ r.links_cnt }}</span>
                  <span v-else class="text-muted small">нет</span>
                </td>
                <td class="small">{{ fmtDate(r.created_at) }}</td>
                <td class="text-end text-nowrap">
                  <router-link :to="`/wb/detail?nm_id=${r.nmID}`" class="btn btn-sm btn-outline-primary" target="_blank">
                    <i class="bi bi-box-arrow-up-right"></i>
                  </router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div v-if="total > f.page_size" class="card-footer d-flex justify-content-between align-items-center">
        <span class="small text-muted">Страница {{ f.page }} · всего {{ total }}</span>
        <div class="btn-group">
          <button class="btn btn-sm btn-outline-secondary" :disabled="f.page <= 1" @click="f.page--; doLoad()">←</button>
          <button class="btn btn-sm btn-outline-secondary" :disabled="f.page * f.page_size >= total" @click="f.page++; doLoad()">→</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'

const f = reactive({
  nm_id: '', vendor: '', brand: '', subject_name: '', title: '',
  only_unused: false, page: 1, page_size: 20,
})

// опции фильтров грузим один раз
const { data: filterOptsData } = useQuery({
  queryKey: ['wb-cards-filters'],
  queryFn: () => api.get('/api/wb-cards/filters').then(r => r.data),
})
const filterOpts = computed<any>(() => filterOptsData.value || { brands: [], subjectNames: [] })

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)

const params = () => {
  const p: any = { page: f.page, page_size: f.page_size }
  if (f.nm_id) p.nm_id = f.nm_id
  if (f.vendor) p.vendor = f.vendor
  if (f.brand) p.brand = f.brand
  if (f.subject_name) p.subject_name = f.subject_name
  if (f.title) p.title = f.title
  if (f.only_unused) p.only_unused = 1
  return p
}

const doLoad = async () => {
  loading.value = true
  try {
    const res = await api.get('/api/wb-cards', { params: params() }).then(r => r.data)
    rows.value = res.rows || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

const search = () => { f.page = 1; doLoad() }

const fmtDate = (v: any) => {
  if (!v) return '—'
  if (typeof v === 'number') return new Date(v * (String(v).length === 10 ? 1000 : 1)).toISOString().slice(0, 10)
  return String(v).slice(0, 10)
}

onMounted(doLoad)
</script>
