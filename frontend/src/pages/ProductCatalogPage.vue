<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">Линейки товаров</h1>
      <button class="btn btn-primary btn-sm" :disabled="!isAdmin" :title="isAdmin ? '' : 'Нужна роль admin'" @click="openProductCreate">
        <i class="bi bi-plus-lg me-1"></i> Добавить линейку
      </button>
    </div>

    <ul class="nav nav-pills mb-3">
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'products' }" @click="tab = 'products'">Линейки</button></li>
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'dicts' }" @click="tab = 'dicts'">Типы и бренды</button></li>
    </ul>

    <!-- ======================= TAB: ЛИНЕЙКИ ======================= -->
    <div v-if="tab === 'products'">
      <div class="d-flex gap-2 mb-2">
        <input v-model="prodQ" class="form-control form-control-sm" style="width:260px" placeholder="поиск (название / бренд / тип / id)" @keyup.enter="loadProducts">
        <button class="btn btn-sm btn-outline-primary" @click="loadProducts"><i class="bi bi-search me-1"></i>Найти</button>
      </div>

      <div class="card shadow-sm">
        <div class="card-body p-0">
          <div v-if="prodLoading" class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
          <div v-else-if="!prodRows.length" class="p-4 text-center text-muted">Линеек пока нет</div>
          <div v-else class="table-responsive">
            <table class="table table-bordered table-striped table-hover align-middle mb-0">
              <thead>
                <tr>
                  <th style="width:60px">ID</th>
                  <th>Название</th>
                  <th>Тип</th>
                  <th>Бренд</th>
                  <th class="text-end" style="width:120px">Себестоимость</th>
                  <th class="text-center" style="width:110px">Карточек</th>
                  <th style="width:150px"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in prodRows" :key="p.id">
                  <td>{{ p.id }}</td>
                  <td class="fw-bold">{{ p.name }}</td>
                  <td>{{ p.product_type || '—' }}</td>
                  <td>{{ p.brand || '—' }}</td>
                  <td class="text-end">{{ p.cost ?? '—' }}</td>
                  <td class="text-center">
                    <span class="badge" :class="p.links_cnt ? 'bg-success' : 'bg-secondary'">{{ p.links_cnt }}</span>
                  </td>
                  <td class="text-end text-nowrap">
                    <button class="btn btn-sm btn-outline-primary me-1" @click="openLinks(p)"><i class="bi bi-diagram-3 me-1"></i>Состав</button>
                    <button class="btn btn-sm btn-outline-secondary me-1" @click="openProductEdit(p)"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger" @click="deleteProduct(p)"><i class="bi bi-trash"></i></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="small text-muted mt-2">
        Себестоимость — ручная; если пуста, в отчёте «Маржа по линейкам» она считается по формуле отчёта.
      </div>
    </div>

    <!-- ======================= TAB: СПРАВОЧНИКИ ======================= -->
    <div v-if="tab === 'dicts'" class="row g-3">
      <div class="col-md-6">
        <div class="card shadow-sm">
          <div class="card-header d-flex justify-content-between align-items-center">
            <h6 class="mb-0">Типы продуктов</h6>
            <button class="btn btn-sm btn-outline-primary" :disabled="!isAdmin" @click="openTypeCreate"><i class="bi bi-plus-lg"></i></button>
          </div>
          <div class="card-body p-0">
            <table class="table table-sm table-bordered table-striped mb-0">
              <thead><tr><th style="width:60px">ID</th><th>Название</th><th style="width:120px"></th></tr></thead>
              <tbody>
                <tr v-for="t in types" :key="t.id">
                  <td>{{ t.id }}</td><td>{{ t.name }}</td>
                  <td class="text-end">
                    <button class="btn btn-sm btn-outline-secondary me-1" :disabled="!isAdmin" @click="openTypeCreate(t)"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger" :disabled="!isAdmin" @click="deleteType(t)"><i class="bi bi-trash"></i></button>
                  </td>
                </tr>
                <tr v-if="!types.length"><td colspan="3" class="text-center text-muted py-2">Пусто</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card shadow-sm">
          <div class="card-header d-flex justify-content-between align-items-center">
            <h6 class="mb-0">Бренды</h6>
            <button class="btn btn-sm btn-outline-primary" :disabled="!isAdmin" @click="openBrandCreate"><i class="bi bi-plus-lg"></i></button>
          </div>
          <div class="card-body p-0">
            <table class="table table-sm table-bordered table-striped mb-0">
              <thead><tr><th style="width:60px">ID</th><th>Название</th><th style="width:120px"></th></tr></thead>
              <tbody>
                <tr v-for="b in brands" :key="b.id">
                  <td>{{ b.id }}</td><td>{{ b.name }}</td>
                  <td class="text-end">
                    <button class="btn btn-sm btn-outline-secondary me-1" :disabled="!isAdmin" @click="openBrandCreate(b)"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger" :disabled="!isAdmin" @click="deleteBrand(b)"><i class="bi bi-trash"></i></button>
                  </td>
                </tr>
                <tr v-if="!brands.length"><td colspan="3" class="text-center text-muted py-2">Пусто</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- ===================== МОДАЛКА: линейка ===================== -->
    <div class="modal fade" :class="{ show: productModalOpen }" tabindex="-1" @click.self="productModalOpen = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">{{ editing ? 'Линейка: правка' : 'Новая линейка' }}</h6>
            <button type="button" class="btn-close" @click="productModalOpen = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-2">
              <label class="form-label small mb-1">Название *</label>
              <input v-model="pForm.name" class="form-control form-control-sm">
            </div>
            <div class="row g-2 mb-2">
              <div class="col-6">
                <label class="form-label small mb-1">Тип продукта</label>
                <select v-model="pForm.product_type_id" class="form-select form-select-sm">
                  <option :value="null">—</option>
                  <option v-for="t in types" :key="t.id" :value="t.id">{{ t.name }}</option>
                </select>
              </div>
              <div class="col-6">
                <label class="form-label small mb-1">Бренд</label>
                <select v-model="pForm.brand_id" class="form-select form-select-sm">
                  <option :value="null">—</option>
                  <option v-for="b in brands" :key="b.id" :value="b.id">{{ b.name }}</option>
                </select>
              </div>
              <div class="col-4">
                <label class="form-label small mb-1">Себестоимость</label>
                <input v-model="pForm.cost" type="number" step="0.01" class="form-control form-control-sm">
              </div>
              <div class="col-4">
                <label class="form-label small mb-1">Вес, кг</label>
                <input v-model="pForm.weight" type="number" step="0.001" class="form-control form-control-sm">
              </div>
              <div class="col-4">
                <label class="form-label small mb-1">НДС</label>
                <input v-model="pForm.vat_rate" type="text" class="form-control form-control-sm" placeholder="напр. 0.20">
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm btn-light" @click="productModalOpen = false">Отмена</button>
            <button class="btn btn-sm btn-primary" :disabled="!pForm.name.trim()" @click="saveProduct">Сохранить</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="productModalOpen" class="modal-backdrop fade show"></div>

    <!-- ===================== МОДАЛКА: состав линейки ===================== -->
    <div class="modal fade" :class="{ show: linksModalOpen }" tabindex="-1" @click.self="linksModalOpen = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">Состав: {{ linksProduct?.name || '' }}</h6>
            <button type="button" class="btn-close" @click="linksModalOpen = false"></button>
          </div>
          <div class="modal-body">
            <table class="table table-sm table-bordered align-middle mb-2">
              <thead>
                <tr>
                  <th style="width:110px">nmID</th>
                  <th>Артикул / Товар</th>
                  <th style="width:90px">q</th>
                  <th style="width:100px">p, %</th>
                  <th class="text-center" style="width:70px">Сумма p</th>
                  <th style="width:60px"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="it in linkRows" :key="it.nm">
                  <td>{{ it.nm }}</td>
                  <td class="small">{{ it.vendor }} — <span class="text-truncate d-inline-block" style="max-width:280px" :title="it.title">{{ it.title }}</span></td>
                  <td><input v-model.number="it.q" type="number" class="form-control form-control-sm"></td>
                  <td><input v-model.number="it.p" type="number" step="0.01" class="form-control form-control-sm"></td>
                  <td class="text-center small" :class="(pSumMap[it.nm] ?? it.p) === 100 ? 'text-success' : 'text-danger'">
                    {{ pSumMap[it.nm] ?? it.p }}
                  </td>
                  <td class="text-end">
                    <button class="btn btn-sm btn-outline-danger" @click="linkRows = linkRows.filter(x => x.nm !== it.nm)"><i class="bi bi-trash"></i></button>
                  </td>
                </tr>
                <tr v-if="!linkRows.length"><td colspan="6" class="text-center text-muted py-2">Состав пуст — добавьте карточки ниже</td></tr>
              </tbody>
            </table>

            <div class="input-group input-group-sm" style="max-width:480px">
              <input v-model="linkSearchQ" class="form-control" placeholder="поиск карточки (артикул / название / nmID)" @keyup.enter="searchLinkCards">
              <button class="btn btn-outline-primary" @click="searchLinkCards"><i class="bi bi-search"></i></button>
            </div>
            <div class="d-flex flex-wrap gap-1 mt-2">
              <button v-for="c in linkCandidates" :key="c.nmID" class="btn btn-sm btn-outline-secondary"
                      :disabled="linkRows.some(l => l.nm === c.nmID)" @click="addLink(c)">
                {{ c.vendorCode || c.nmID }}
              </button>
            </div>
            <div class="small text-muted mt-2">
              При сохранении сумма «p» по каждой карточке нормируется к 100 по всем её линейкам.
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm btn-light" @click="linksModalOpen = false">Отмена</button>
            <button class="btn btn-sm btn-primary" :disabled="!isAdmin" @click="saveLinks">
              {{ savingLinks ? 'Сохранение...' : 'Сохранить состав' }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="linksModalOpen" class="modal-backdrop fade show"></div>

    <!-- ===================== МОДАЛКА: справочник ===================== -->
    <div class="modal fade" :class="{ show: dictModalOpen }" tabindex="-1" @click.self="dictModalOpen = false">
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">{{ dictKind === 'type' ? (dictId ? 'Тип: правка' : 'Новый тип') : (dictId ? 'Бренд: правка' : 'Новый бренд') }}</h6>
            <button type="button" class="btn-close" @click="dictModalOpen = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-2">
              <label class="form-label small mb-1">Название *</label>
              <input v-model="dictName" class="form-control form-control-sm">
            </div>
            <div v-if="dictKind === 'type'">
              <label class="form-label small mb-1">Описание</label>
              <input v-model="dictDesc" class="form-control form-control-sm">
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm btn-light" @click="dictModalOpen = false">Отмена</button>
            <button class="btn btn-sm btn-primary" @click="saveDict">Сохранить</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="dictModalOpen" class="modal-backdrop fade show"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'

const tab = ref<'products' | 'dicts'>('products')
const isAdmin = (() => {
  try {
    const me = localStorage.getItem('wbcms_me')
    if (me) {
      const m = JSON.parse(me)
      return (m.roles || []).includes('admin') || (m.perms || []).includes('admin')
    }
  } catch { /* noop */ }
  return false
})()

// --- линейки -----------------------------------------------------------
const prodQ = ref('')
const prodRows = ref<any[]>([])
const prodLoading = ref(false)
const loadProducts = async () => {
  prodLoading.value = true
  try {
    const res = await api.get('/api/products', { params: { q: prodQ.value || undefined } }).then(r => r.data)
    prodRows.value = res.rows || []
  } finally { prodLoading.value = false }
}

// --- справочники ---------------------------------------------------------
const types = ref<any[]>([])
const brands = ref<any[]>([])
const loadDicts = async () => {
  const [t, b] = await Promise.all([
    api.get('/api/product-types').then(r => r.data.rows),
    api.get('/api/brands').then(r => r.data.rows),
  ])
  types.value = t || []
  brands.value = b || []
}

// --- модалка линейки -------------------------------------------------------
const productModalOpen = ref(false)
const editing = ref<any>(null)
const pForm = ref<any>({ name: '', product_type_id: null, brand_id: null, cost: '', weight: '', vat_rate: '' })
const openProductCreate = () => {
  editing.value = null
  pForm.value = { name: '', product_type_id: null, brand_id: null, cost: '', weight: '', vat_rate: '' }
  productModalOpen.value = true
}
const openProductEdit = (p: any) => {
  editing.value = p
  pForm.value = { name: p.name, product_type_id: p.product_type_id || null, brand_id: p.brand_id || null,
                  cost: p.cost ?? '', weight: p.weight ?? '', vat_rate: p.vat_rate || '' }
  productModalOpen.value = true
}
const saveProduct = async () => {
  const payload = { ...pForm.value, name: pForm.value.name.trim() }
  delete payload.links_cnt
  try {
    if (editing.value) await api.put(`/api/products/${editing.value.id}`, payload)
    else await api.post('/api/products', payload)
    productModalOpen.value = false
    loadProducts()
  } catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось сохранить') }
}
const deleteProduct = async (p: any) => {
  if (!confirm(`Удалить линейку «${p.name}» вместе со связками?`)) return
  try { await api.delete(`/api/products/${p.id}`); loadProducts() }
  catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось удалить') }
}

// --- модалка состава ----------------------------------------------------------
const linksModalOpen = ref(false)
const linksProduct = ref<any>(null)
const linkRows = ref<any[]>([])
const pSumMap = ref<Record<string, number>>({})
const linkSearchQ = ref('')
const linkCandidates = ref<any[]>([])
const savingLinks = ref(false)

const openLinks = async (p: any) => {
  linksProduct.value = p
  linkSearchQ.value = ''
  linkCandidates.value = []
  linksModalOpen.value = true
  try {
    const res = await api.get(`/api/products/${p.id}/links`).then(r => r.data)
    linkRows.value = (res.rows || []).map((r: any) => ({ nm: r.wb_nm_id, vendor: r.vendorCode, title: r.title, q: r.q, p: r.p, type: r.type }))
    pSumMap.value = res.p_sum || {}
  } catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка загрузки состава') }
}
const searchLinkCards = async () => {
  if (!linkSearchQ.value.trim()) { linkCandidates.value = []; return }
  try {
    const res = await api.get('/api/wb/cards', { params: { q: linkSearchQ.value, limit: 12 } }).then(r => r.data)
    linkCandidates.value = (res || []).filter((c: any) => !linkRows.value.some(l => l.nm === c.nmID))
  } catch { linkCandidates.value = [] }
}
const addLink = (c: any) => {
  linkRows.value.push({ nm: c.nmID, vendor: c.vendorCode, title: c.title, q: 1, p: 100, type: 1 })
  linkCandidates.value = linkCandidates.value.filter(x => x.nmID !== c.nmID)
}
const saveLinks = async () => {
  if (!linksProduct.value) return
  savingLinks.value = true
  try {
    const res = await api.put(`/api/products/${linksProduct.value.id}/links`, {
      items: linkRows.value.map(l => ({ wb_nm_id: l.nm, q: l.q, p: l.p, type: l.type })),
    }).then(r => r.data)
    const norm = res.normalized || []
    if (norm.length) {
      alert('Состав сохранён. Нормировано p до 100 по карточкам:\n' +
            norm.map((n: any) => `${n.wb_nm_id}: было ${n.was} → 100`).join('\n'))
    }
    linksModalOpen.value = false
    loadProducts()
  } catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось сохранить состав') }
  finally { savingLinks.value = false }
}

// --- модалка справочника --------------------------------------------------------
const dictModalOpen = ref(false)
const dictKind = ref<'type' | 'brand'>('type')
const dictId = ref<number | null>(null)
const dictName = ref('')
const dictDesc = ref('')
const openTypeCreate = (t?: any) => {
  dictKind.value = 'type'
  dictId.value = t?.id || null
  dictName.value = t?.name || ''
  dictDesc.value = t?.description || ''
  dictModalOpen.value = true
}
const openBrandCreate = (b?: any) => {
  dictKind.value = 'brand'
  dictId.value = b?.id || null
  dictName.value = b?.name || ''
  dictDesc.value = ''
  dictModalOpen.value = true
}
const saveDict = async () => {
  const base = dictKind.value === 'type' ? '/api/product-types' : '/api/brands'
  const payload = dictKind.value === 'type'
    ? { name: dictName.value, description: dictDesc.value || null }
    : { name: dictName.value }
  try {
    if (dictId.value) await api.put(`${base}/${dictId.value}`, payload)
    else await api.post(base, payload)
    dictModalOpen.value = false
    loadDicts()
  } catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось сохранить') }
}
const deleteType = async (t: any) => {
  if (!confirm(`Удалить тип «${t.name}»?`)) return
  try { await api.delete(`/api/product-types/${t.id}`); loadDicts() }
  catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось удалить') }
}
const deleteBrand = async (b: any) => {
  if (!confirm(`Удалить бренд «${b.name}»?`)) return
  try { await api.delete(`/api/brands/${b.id}`); loadDicts() }
  catch (e: any) { alert(e?.response?.data?.detail || 'Не удалось удалить') }
}

onMounted(() => { loadProducts(); loadDicts() })
</script>
