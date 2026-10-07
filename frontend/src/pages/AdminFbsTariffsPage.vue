<template>
  <div class="container-xxl page-admin-fbs-tariffs">
    <h1 class="page-title">Тарифы сборки FBS</h1>
    <p class="text-muted" style="font-size:12px">Версионная сетка (<code>backend/config/fbs_assembly_tariffs.json</code>). Деньги считаются по версии на дату заказа, отображение — по последней. Применяется сразу без рестарта.</p>
    <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
    <div v-else-if="error && !form" class="alert alert-danger">{{ error }}</div>
    <template v-else-if="form">
      <div v-if="error" class="alert alert-danger">{{ error }}</div>
      <div v-if="saved" class="alert alert-success">Сохранено — применяется сразу.</div>
      <div class="card card-body mb-3">
        <h6>Пороги (часы, общие для всех версий)</h6>
        <div class="row g-2">
          <div v-for="f in numFields" :key="f.key" class="col-md-2 col-6">
            <label class="form-label">{{ f.label }}</label>
            <input v-model.number="form.thresholds[f.key]" type="number" min="0" step="1" class="form-control" />
          </div>
        </div>
      </div>
      <div class="card card-body mb-3">
        <div class="d-flex align-items-center gap-2 mb-2">
          <h6 class="mb-0">Версия сетки</h6>
          <select v-model="verIdx" class="form-select form-select-sm" style="width:auto">
            <option v-for="(v, i) in form.versions" :key="i" :value="i">с {{ v.valid_from }}{{ v.comment ? ' — ' + v.comment : '' }}</option>
          </select>
          <button class="btn btn-sm btn-outline-secondary" @click="addVersion()">+ Новая версия</button>
        </div>
        <div class="row g-2 mb-2">
          <div class="col-md-3">
            <label class="form-label">Действует с</label>
            <input v-model="cur.valid_from" type="date" class="form-control form-control-sm" />
          </div>
          <div class="col-md-9">
            <label class="form-label">Комментарий</label>
            <input v-model="cur.comment" type="text" class="form-control form-control-sm" placeholder="напр. новость WB 06.10.2026" />
          </div>
        </div>
        <table class="table table-bordered table-sm mb-0">
          <thead>
            <tr><th>До, ч (пусто = ∞)</th><th>Вид</th><th>Значение</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(b, i) in cur.buckets" :key="i">
              <td>
                <input v-if="i < cur.buckets.length - 1" v-model.number="b.upto_h" type="number" min="1" step="1" class="form-control form-control-sm" />
                <span v-else class="text-muted">∞</span>
              </td>
              <td>
                <select v-model="b.kind" class="form-select form-select-sm">
                  <option value="discount_pp">скидка, п.п.</option>
                  <option value="base">база</option>
                  <option value="penalty_pct_per_h">штраф, %/ч</option>
                  <option value="penalty_flat_pct">штраф фикс, %</option>
                </select>
              </td>
              <td><input v-model.number="b.value" type="number" step="0.05" class="form-control form-control-sm" /></td>
              <td><button class="btn btn-sm btn-light" @click="delRow(i)" :disabled="cur.buckets.length <= 2" title="Убрать строку">×</button></td>
            </tr>
          </tbody>
        </table>
        <div class="mt-2 d-flex gap-2">
          <button class="btn btn-sm btn-outline-secondary" @click="addRow()">+ Строка</button>
          <button class="btn btn-primary" @click="save()" :disabled="saving">{{ saving ? 'Сохранение...' : 'Сохранить всё' }}</button>
          <button class="btn btn-light" @click="load()">Сбросить</button>
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client'

const numFields = [
  { key: 'base_sla_h', label: 'Базовый срок' },
  { key: 'warn_h', label: 'Предупреждение за' },
  { key: 'pre_cancel_h', label: 'Скоро отмена после' },
  { key: 'auto_cancel_h', label: 'Автоотмена' },
  { key: 'quota_overdue_h', label: 'Просрочка (карточки)' },
  { key: 'overdue_from_h', label: 'Штраф от' },
]
const form = ref<any>(null)
const verIdx = ref(0)
const cur = computed(() => form.value?.versions?.[verIdx.value] ?? { buckets: [] })
const isLoading = ref(false)
const saving = ref(false)
const error = ref('')
const saved = ref(false)

async function load() {
  isLoading.value = true
  error.value = ''
  saved.value = false
  try {
    const { data } = await api.get('/api/admin/fbs-tariffs')
    // Совместимость со старым плоским форматом (без versions).
    if (data && !data.versions && Array.isArray((data as any).buckets)) {
      const { buckets, base_field, _comment, ...th } = data as any
      form.value = { _comment, base_field, thresholds: th, versions: [{ valid_from: '2026-01-01', comment: '', buckets }] }
    } else {
      form.value = JSON.parse(JSON.stringify(data))
    }
    if (!form.value.thresholds) form.value.thresholds = {}
    verIdx.value = Math.max(0, (form.value.versions?.length || 1) - 1)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка загрузки'
  } finally {
    isLoading.value = false
  }
}
const addRow = () => {
  const finite = cur.value.buckets.filter((b: any) => b.upto_h != null)
  const maxUpto = finite.length ? Math.max(...finite.map((b: any) => Number(b.upto_h) || 0)) : 60
  cur.value.buckets.splice(cur.value.buckets.length - 1, 0, { upto_h: maxUpto + 12, kind: 'penalty_pct_per_h', value: 0.5 })
}
const delRow = (i: number) => { cur.value.buckets.splice(i, 1) }
const addVersion = () => {
  const src = cur.value
  form.value.versions.push(JSON.parse(JSON.stringify({ ...src, valid_from: '', comment: '' })))
  verIdx.value = form.value.versions.length - 1
}
async function save() {
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    const { data } = await api.put('/api/admin/fbs-tariffs', form.value)
    form.value = data
    verIdx.value = Math.max(0, (form.value.versions?.length || 1) - 1)
    saved.value = true
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка сохранения'
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>
