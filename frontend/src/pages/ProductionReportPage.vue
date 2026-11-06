<template>
  <div class="container-xxl page-production">
    <!-- Шапка блока «Производство»: заголовок + правое меню (пилюли темы) -->
    <WbWorkspaceHead
      title="Производственный план"
      :workspace-tabs="STOCK_PRODUCTION_TABS"
      workspace-active="plan"
    />

    <!-- Фильтр — панель темы -->
    <div class="wb-filter-panel">
      <div class="row g-2">
        <div class="col-auto">
          <label class="wb-field__label">Период</label>
          <input v-model="period" type="month" class="wb-input">
        </div>
      </div>
      <div class="wb-filter-panel__btns">
        <button class="btn btn--brand wb-filter-panel__apply" @click="reload()">
          <i class="bi bi-search me-1"></i>Показать
        </button>
        <button class="btn btn--outline" @click="showPlan = true">
          <i class="bi bi-list-ul me-1"></i>Список товаров
        </button>
      </div>
    </div>

    <!-- Пояснение — тонированная панель темы -->
    <div class="wb-panel page-production__note">
      <div class="wb-panel__bd">
        Остаток на WB — срез по компании на последнее доступное число
        <template v-if="data?.wb_now_date">(<code>{{ data.wb_now_date }}</code>)</template>;
        срез начала периода <template v-if="data?.wb_start_date"><code>{{ data.wb_start_date }}</code></template>.
        Карточки, которых нет в срезе, считаются остатком 0. Скорость — заказы за 30 дней.
        «К производству» = скорость × целевое покрытие − остаток.
      </div>
    </div>

    <!-- План — широкая таблица темы .tbl-card (плотная) -->
    <div class="tbl-card">
      <div class="card__hd">
        <span>Производственный план</span>
        <span class="hd-badge">{{ rows.length }} поз.</span>
      </div>

      <div v-if="loading" class="page-production__loading">
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span>Загрузка данных…</span>
      </div>
      <div v-else-if="!rows.length" class="page-production__empty">
        В плане пока нет товаров — добавьте их через «Список товаров».
      </div>
      <div v-else class="tbl-wrap">
        <table class="tbl page-production__table">
          <thead>
            <tr>
              <th class="t-left">Товар</th>
              <th class="t-right num">WB на нач. периода</th>
              <th class="t-right num">WB сейчас</th>
              <th class="t-right num" title="Расчётный остаток Смоленска: последний снапшот + движения">СМЛ сейчас</th>
              <th class="t-right num" title="Движения Смоленска за выбранный период (приход − списания)">СМЛ за период</th>
              <th class="t-right num" title="Сколько дней покроет остаток Смоленска при текущей скорости">Покрытие СМЛ, дн.</th>
              <th class="t-right num">Заказы с нач. периода</th>
              <th class="t-right num">Заказы за 30 дн.</th>
              <th class="t-right num">Среднее/день</th>
              <th class="t-right num">Дней до конца</th>
              <th class="t-left">Закончится</th>
              <th class="t-right num">Точка заказа, дн.</th>
              <th class="t-right num">К производству</th>
              <th class="t-left">Статус</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.nm_id">
              <td class="t-left">
                <ProductCell
                  compact
                  :photo="r.photos"
                  :title="r.title || ''"
                  :vendor="r.vendor_code || ''"
                  :brand="r.brand || ''"
                  :subject="r.subject_name || ''"
                  :nm-id="r.nm_id"
                  :link="'/wb/detail?nm_id=' + r.nm_id"
                  :link-label="'WB: ' + r.nm_id"
                  copy-nm
                  copy-link
                />
              </td>
              <td class="t-right num">{{ r.wb_start }}</td>
              <td class="t-right num page-production__strong">{{ r.wb_now }}</td>
              <td class="t-right num">{{ r.smolensk_now }}</td>
              <td class="t-right num">{{ r.smolensk_movements }}</td>
              <td class="t-right num">{{ r.smolensk_coverage_days ?? '—' }}</td>
              <td class="t-right num">{{ r.orders_since_period }}</td>
              <td class="t-right num">{{ r.orders_last_30 }}</td>
              <td class="t-right num">{{ r.avg_daily }}</td>
              <td class="t-right num">{{ r.days_left ?? '—' }}</td>
              <td class="t-left">{{ r.eta_date || '—' }}</td>
              <td class="t-right num" :title="'Произв. + логистика Смоленск + логистика WB + буфер'">
                {{ r.reorder_point_days }}
              </td>
              <td class="t-right num page-production__strong" :class="r.recommended_qty > 0 ? 't-neg' : ''">
                {{ r.recommended_qty > 0 ? r.recommended_qty : '—' }}
              </td>
              <td class="t-left">
                <span class="badge" :class="statusClass(r.status)">{{ statusLabel(r.status) }}</span>
              </td>
            </tr>
          </tbody>
          <tfoot v-if="rows.length">
            <tr class="tbl__total">
              <td class="t-left" colspan="12">Итого к производству</td>
              <td class="t-right num">{{ totals.recommended_qty }}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
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
              <input v-model="availQ" class="wb-input page-production__avail-search"
                     placeholder="поиск карточки (артикул/название)" @keyup.enter="loadAvailable">
              <button class="btn btn--outline btn-sm" @click="loadAvailable">Найти</button>
            </div>
            <table class="tbl page-production__plan-table">
              <thead>
                <tr>
                  <th class="t-left page-production__col-nm">Арт WB</th><th class="t-left">Название</th>
                  <th class="t-right page-production__col-num">Срок, дн.</th>
                  <th class="t-right page-production__col-num">-&gt; СМЛ</th>
                  <th class="t-right page-production__col-num">-&gt; WB</th>
                  <th class="t-right page-production__col-num">Буфер</th>
                  <th class="t-right page-production__col-num">Покрытие</th>
                  <th class="t-right page-production__col-act"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="it in planRows" :key="it.nm_id">
                  <td class="t-left num">{{ it.nm_id }}</td>
                  <td class="t-left">{{ it.vendorCode }} — {{ it.title }}</td>
                  <td class="t-right"><input v-model.number="it.production_days" type="number" class="wb-input wb-input--num"></td>
                  <td class="t-right"><input v-model.number="it.logistics_smolensk_days" type="number" class="wb-input wb-input--num"></td>
                  <td class="t-right"><input v-model.number="it.logistics_wb_days" type="number" class="wb-input wb-input--num"></td>
                  <td class="t-right"><input v-model.number="it.buffer_days" type="number" class="wb-input wb-input--num"></td>
                  <td class="t-right"><input v-model.number="it.target_coverage_days" type="number" class="wb-input wb-input--num"></td>
                  <td class="t-right">
                    <button class="btn btn--danger btn-sm" title="Убрать из плана" @click="removeItem(it)">
                      <i class="bi bi-trash"></i>
                    </button>
                  </td>
                </tr>
                <tr v-if="!planRows.length">
                  <td colspan="8" class="t-center page-production__empty">В плане пока нет товаров</td>
                </tr>
              </tbody>
            </table>

            <div class="border-top pt-2 mt-3">
              <div class="fw-bold page-production__avail-title mb-1">Доступные карточки</div>
              <div class="d-flex flex-wrap gap-1">
                <button v-for="a in available" :key="a.nmID" class="btn btn--outline btn-sm"
                        @click="addItem(a)">
                  {{ a.vendorCode || a.nmID }}
                </button>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn--outline btn-sm" @click="showPlan = false">Закрыть</button>
            <button class="btn btn--brand btn-sm" @click="savePlan" :disabled="saving">
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
import '@/assets/css/pages/page-production.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '@/api/client'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import ProductCell from '@/components/common/ProductCell.vue'
import { STOCK_PRODUCTION_TABS } from '@/components/common/workspaceTabs'

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
  danger: 'badge--bad',
  warn: 'badge--warn',
  ok: 'badge--ok',
  unknown: 'badge--neutral',
}[s] || 'badge--neutral')

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
