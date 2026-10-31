<template>
  <div class="container-xxl">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="page-title mb-0">Производственный план — остатки и потребность</h1>
      <div class="d-flex gap-2 align-items-center">
        <input v-model="period" type="month" class="form-control form-control-sm" style="width:170px">
        <button class="btn btn-sm btn-light" @click="showPlan = true">
          <i class="bi bi-list-ul me-1"></i>Список товаров
        </button>
        <button class="btn btn-sm btn-primary" @click="reload()">
          <i class="bi bi-search me-1"></i>Показать
        </button>
      </div>
    </div>

    <div class="alert alert-info py-2 small">
      Остаток на WB — срез по компании на последнее доступное число
      <template v-if="data?.wb_now_date">(<code>{{ data.wb_now_date }}</code>)</template>;
      срез начала периода <template v-if="data?.wb_start_date"><code>{{ data.wb_start_date }}</code>.</template>
      Карточки, которых нет в срезе, считаются остатком 0. Скорость — заказы за 30 дней.
      «К производству» = скорость × целевое покрытие − остаток.
    </div>

    <div class="card shadow-sm">
      <div class="card-body p-0">
        <div v-if="loading" class="text-center p-5">
          <div class="spinner-border text-primary" role="status"></div>
        </div>
        <div v-else-if="!rows.length" class="p-4 text-center text-muted">
          В плане пока нет товаров — добавьте их через «Список товаров».
        </div>
        <div v-else class="table-responsive">
          <table class="table table-bordered table-striped table-hover align-middle mb-0">
            <thead>
              <tr>
                <th>Товар</th>
                <th class="text-end">WB на нач. периода</th>
                <th class="text-end">WB сейчас</th>
                <th class="text-end" title="Расчётный остаток Смоленска: последний снапшот + движения">СМЛ сейчас</th>
                <th class="text-end" title="Движения Смоленска за выбранный период (приход − списания)">СМЛ за период</th>
                <th class="text-end" title="Сколько дней покроет остаток Смоленска при текущей скорости">Покрытие СМЛ, дн.</th>
                <th class="text-end">Заказы с нач. периода</th>
                <th class="text-end">Заказы за 30 дн.</th>
                <th class="text-end">Среднее/день</th>
                <th class="text-end">Дней до конца</th>
                <th>Закончится</th>
                <th class="text-end">Точка заказа, дн.</th>
                <th class="text-end">К производству</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.nm_id">
                <td>
                  <div class="fw-bold">{{ r.vendor_code }}</div>
                  <div class="small text-muted">{{ r.nm_id }} — {{ r.title }}</div>
                </td>
                <td class="text-end">{{ r.wb_start }}</td>
                <td class="text-end fw-bold">{{ r.wb_now }}</td>
                <td class="text-end">{{ r.smolensk_now }}</td>
                <td class="text-end">{{ r.smolensk_movements }}</td>
                <td class="text-end">{{ r.smolensk_coverage_days ?? '—' }}</td>
                <td class="text-end">{{ r.orders_since_period }}</td>
                <td class="text-end">{{ r.orders_last_30 }}</td>
                <td class="text-end">{{ r.avg_daily }}</td>
                <td class="text-end">{{ r.days_left ?? '—' }}</td>
                <td class="small">{{ r.eta_date || '—' }}</td>
                <td class="text-end" :title="'Произв. + логистика Смоленск + логистика WB + буфер'">
                  {{ r.reorder_point_days }}
                </td>
                <td class="text-end fw-bold" :class="r.recommended_qty > 0 ? 'text-danger' : ''">
                  {{ r.recommended_qty > 0 ? r.recommended_qty : '—' }}
                </td>
                <td>
                  <span class="badge" :class="statusClass(r.status)">{{ statusLabel(r.status) }}</span>
                </td>
              </tr>
            </tbody>
            <tfoot v-if="rows.length">
              <tr class="fw-bold">
                <td colspan="12">Итого к производству</td>
                <td class="text-end">{{ totals.recommended_qty }}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>

    <!-- план -->
    <div class="modal fade" :class="{ show: showPlan }" tabindex="-1" @click.self="showPlan = false">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title">Список товаров для производственного плана</h6>
            <button type="button" class="btn-close" @click="showPlan = false"></button>
          </div>
          <div class="modal-body">
            <div class="d-flex gap-2 mb-2">
              <input v-model="availQ" class="form-control form-control-sm" style="width:280px"
                     placeholder="поиск карточки (артикул/название)" @keyup.enter="loadAvailable">
              <button class="btn btn-sm btn-outline-primary" @click="loadAvailable">Найти</button>
            </div>
            <table class="table table-sm table-bordered table-striped align-middle mb-2">
              <thead>
                <tr>
                  <th style="width:120px">Арт WB</th><th>Название</th>
                  <th style="width:110px">Срок, дн.</th>
                  <th style="width:110px">-&gt; СМЛ</th>
                  <th style="width:110px">-&gt; WB</th>
                  <th style="width:110px">Буфер</th>
                  <th style="width:110px">Покрытие</th>
                  <th style="width:60px"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="it in planRows" :key="it.nm_id">
                  <td>{{ it.nm_id }}</td>
                  <td class="small">{{ it.vendorCode }} — {{ it.title }}</td>
                  <td><input v-model.number="it.production_days" type="number" class="form-control form-control-sm"></td>
                  <td><input v-model.number="it.logistics_smolensk_days" type="number" class="form-control form-control-sm"></td>
                  <td><input v-model.number="it.logistics_wb_days" type="number" class="form-control form-control-sm"></td>
                  <td><input v-model.number="it.buffer_days" type="number" class="form-control form-control-sm"></td>
                  <td><input v-model.number="it.target_coverage_days" type="number" class="form-control form-control-sm"></td>
                  <td class="text-end">
                    <button class="btn btn-sm btn-outline-danger" @click="removeItem(it)">
                      <i class="bi bi-trash"></i>
                    </button>
                  </td>
                </tr>
                <tr v-if="!planRows.length">
                  <td colspan="8" class="text-center text-muted py-2">В плане пока нет товаров</td>
                </tr>
              </tbody>
            </table>

            <div class="border-top pt-2">
              <div class="fw-bold small mb-1">Доступные карточки</div>
              <div class="d-flex flex-wrap gap-1">
                <button v-for="a in available" :key="a.nmID" class="btn btn-sm btn-outline-secondary"
                        @click="addItem(a)">
                  {{ a.vendorCode || a.nmID }}
                </button>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-sm btn-light" @click="showPlan = false">Закрыть</button>
            <button class="btn btn-sm btn-primary" @click="savePlan" :disabled="saving">
              {{ saving ? 'Сохранение...' : 'Сохранить список' }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showPlan" class="modal-backdrop fade show"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'

const qc = useQueryClient()

const period = ref(new Date().toISOString().slice(0, 7))
const showPlan = ref(false)
const saving = ref(false)
const planRows = ref<any[]>([])
const available = ref<any[]>([])
const availQ = ref('')

const { data, isLoading: loading } = useQuery({
  queryKey: computed(() => ['production-report', period.value] as const),
  queryFn: () => api.get('/api/production/report', { params: { period: period.value } })
    .then(r => r.data),
})

const rows = computed<any[]>(() => (data.value?.rows as any[]) || [])
const totals = computed(() => (data.value?.totals as any) || { recommended_qty: 0 })

const statusClass = (s: string) => ({
  danger: 'bg-danger',
  warn: 'bg-warning text-dark',
  ok: 'bg-success',
  unknown: 'bg-secondary',
}[s] || 'bg-secondary')

const statusLabel = (s: string) => ({
  danger: 'В печать',
  warn: 'Скоро',
  ok: 'Норма',
  unknown: 'Нет данных',
}[s] || s)

const reload = () => qc.invalidateQueries({ queryKey: ['production-report'] })

const loadPlan = async () => {
  const res = await api.get('/api/production/plan').then(r => r.data).catch(() => ({ rows: [], defaults: {} }))
  planRows.value = (res.rows || []).map((r: any) => ({ ...r }))
}

const loadAvailable = async () => {
  const res = await api.get('/api/production/available', {
    params: { q: availQ.value || undefined, limit: 50 },
  }).then(r => r.data).catch(() => ({ rows: [] }))
  available.value = res.rows || []
}

watch(showPlan, (v) => {
  if (v) {
    loadPlan()
    loadAvailable()
  }
})

onMounted(reload)

const addItem = (a: any) => {
  if (planRows.value.some(p => p.nm_id === a.nmID)) return
  planRows.value.push({
    nm_id: a.nmID,
    vendorCode: a.vendorCode,
    title: a.title,
    production_days: 20,
    logistics_smolensk_days: 5,
    logistics_wb_days: 5,
    buffer_days: 7,
    target_coverage_days: 90,
  })
}

const removeItem = (it: any) => {
  planRows.value = planRows.value.filter(p => p.nm_id !== it.nm_id)
}

const savePlan = async () => {
  saving.value = true
  try {
    await api.put('/api/production/plan', {
      items: planRows.value.map(p => ({
        nm_id: p.nm_id,
        production_days: p.production_days,
        logistics_smolensk_days: p.logistics_smolensk_days,
        logistics_wb_days: p.logistics_wb_days,
        buffer_days: p.buffer_days,
        target_coverage_days: p.target_coverage_days,
      })),
    })
    await loadPlan()
    reload()
  } catch (e: any) {
    alert(e?.response?.data?.detail || 'Не удалось сохранить план')
  } finally {
    saving.value = false
  }
}
</script>
