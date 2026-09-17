<template>
  <div class="container-xxl page-cost-import">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="page-title mb-0">Загрузка себестоимости</h1>
      <router-link to="/cost-import/list" class="btn btn-outline-secondary btn-sm">Просмотр и редактирование</router-link>
    </div>

    <div class="card shadow-sm mb-3 page-cost-import__filter-card">
      <form class="card-body d-flex align-items-end flex-wrap page-cost-import__form" @submit.prevent="onPreview">
        <div>
          <label class="form-label mb-1 fw-bold" for="load-date">Дата загрузки</label>
          <input id="load-date" v-model="loadDate" type="date" class="form-control" required />
        </div>
        <div class="page-cost-import__file">
          <label class="form-label mb-1 fw-bold" for="cost-file">Файл (.xlsx)</label>
          <input id="cost-file" ref="fileRef" type="file" class="form-control" accept=".xlsx,.xls" required />
        </div>
        <div>
          <button type="submit" class="btn btn-primary" :disabled="previewLoading">
            <i class="bi bi-upload me-1"></i>{{ previewLoading ? 'Разбор...' : 'Загрузить и проверить' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="previewError" class="alert alert-danger">{{ previewError }}</div>

    <div v-if="showResults">
      <div class="card shadow-sm mb-3 sticky-top page-cost-import__summary">
        <div class="card-body d-flex justify-content-between align-items-center flex-wrap gap-2 py-2">
          <div>
            Найдено позиций: <strong>{{ items.length }}</strong>
            <span class="text-success">(новых: {{ newCount }}, перезапись: {{ updCount }})</span>
            &nbsp;·&nbsp;
            Ошибок: <strong class="text-danger">{{ errors.length }}</strong>
            <span class="text-muted small ms-2">тестовый режим — в базу ничего не записано</span>
          </div>
          <div class="d-flex align-items-center gap-3">
            <span v-if="saveStatus" :class="saveOk ? 'text-success' : 'text-danger'">{{ saveStatus }}</span>
            <button class="btn btn-success" :disabled="!items.length || saveLoading" @click="onSave">
              <i class="bi bi-database-check me-1"></i>{{ saveLoading ? 'Сохранение...' : 'Сохранить в базу' }}
            </button>
          </div>
        </div>
      </div>

      <div class="row g-3">
        <div class="col-md-8">
          <div class="card shadow-sm">
            <div class="card-header d-flex justify-content-between align-items-center wb-card-header">
              <span>Найденные позиции</span>
              <span class="badge bg-light text-dark">{{ items.length }}</span>
            </div>
            <div class="card-body p-0">
              <div class="page-cost-import__table-wrap">
                <table class="table table-sm table-bordered table-striped table-hover mb-0 page-cost-import__table">
                  <thead><tr><th class="page-cost-import__cell--center">Стр</th><th>Артикул WB</th><th>Товар</th><th>Баркод</th><th class="page-cost-import__cell--num">Цена</th><th class="page-cost-import__cell--center">Статус</th></tr></thead>
                  <tbody>
                    <tr v-for="it in items" :key="`${it.nmID}-${it.sku}`">
                      <td class="page-cost-import__cell--center">{{ it.row }}</td>
                      <td class="page-cost-import__cell--nowrap">{{ it.nmID }}</td>
                      <td class="page-cost-import__cell--product">{{ it.title || it.vendorCode || '' }}</td>
                      <td class="page-cost-import__cell--nowrap">{{ it.sku }}</td>
                      <td class="page-cost-import__cell--num">{{ it.price }}</td>
                      <td class="page-cost-import__cell--center">
                        <span v-if="it.action === 'update'" class="badge bg-warning text-dark" title="Такая связка на эту дату уже есть — цена перезапишется">перезапись</span>
                        <span v-else class="badge bg-success">новая</span>
                      </td>
                    </tr>
                    <tr v-if="!items.length"><td colspan="6" class="text-center text-muted py-3">Нет позиций — загрузите файл</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div class="col-md-4">
          <div class="card shadow-sm">
            <div class="card-header d-flex justify-content-between align-items-center wb-card-header">
              <span>Ошибки</span>
              <span class="badge" :class="errors.length ? 'bg-danger' : 'bg-success'">{{ errors.length }}</span>
            </div>
            <div class="card-body p-0">
              <div class="page-cost-import__table-wrap">
                <table class="table table-sm table-bordered table-striped table-hover mb-0 page-cost-import__table">
                  <thead><tr><th class="page-cost-import__cell--center">Строка</th><th>Причина</th><th>Значение</th></tr></thead>
                  <tbody>
                    <tr v-for="(e, i) in errors" :key="i">
                      <td class="page-cost-import__cell--center">{{ e.row }}</td><td>{{ e.reason }}</td><td>{{ e.raw }}</td>
                    </tr>
                    <tr v-if="!errors.length"><td colspan="3" class="text-center text-muted py-3">Ошибок нет</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-cost-import.css'
import { ref, computed } from 'vue'
import { costApi } from '@/api/cost'

const today = new Date().toISOString().slice(0, 10)
const loadDate = ref(today)
const fileRef = ref<HTMLInputElement | null>(null)
const previewLoading = ref(false)
const previewError = ref('')
const showResults = ref(false)
const items = ref<any[]>([])
const errors = ref<any[]>([])
const saveLoading = ref(false)
const saveStatus = ref('')
const saveOk = ref(false)

const newCount = computed(() => items.value.filter((i) => i.action !== 'update').length)
const updCount = computed(() => items.value.filter((i) => i.action === 'update').length)

async function onPreview() {
  const file = fileRef.value?.files?.[0]
  if (!file || !loadDate.value) return
  previewLoading.value = true
  previewError.value = ''
  showResults.value = false
  saveStatus.value = ''
  try {
    const XLSX = await import('xlsx')
    const buf = await file.arrayBuffer()
    const wb = XLSX.read(buf, { type: 'array' })
    const ws = wb.Sheets[wb.SheetNames[0]]
    const grid: any[][] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
    const res = await costApi.preview(loadDate.value, grid)
    if (!res.success) {
      previewError.value = res.message || 'Ошибка разбора'
      return
    }
    items.value = res.items || []
    errors.value = res.errors || []
    showResults.value = true
    document.title = 'Загрузка себестоимости'
  } catch (e: any) {
    previewError.value = e?.response?.data?.message || e?.message || String(e)
  } finally {
    previewLoading.value = false
  }
}

async function onSave() {
  if (!items.value.length || !loadDate.value) return
  if (!confirm(`Сохранить ${items.value.length} позиций на ${loadDate.value}? Перезапишется: ${updCount.value}.`)) return
  saveLoading.value = true
  saveStatus.value = ''
  try {
    const res = await costApi.save(loadDate.value, items.value.map((p) => ({
      nmID: p.nmID, price: p.price, chrtID: p.chrtID, sku: p.sku,
    })))
    saveOk.value = res.success
    saveStatus.value = res.message
  } catch (e: any) {
    saveOk.value = false
    saveStatus.value = e?.response?.data?.message || String(e)
  } finally {
    saveLoading.value = false
  }
}
</script>
