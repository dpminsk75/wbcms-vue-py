<template>
  <div class="container-xxl page-tax-settings">
    <!-- Шапка -->
    <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
      <div>
        <h1 class="page-title mb-1">Настройка налогов и НДС</h1>
        <div class="text-muted" style="font-size:12.5px">
          Режим и ставка основного налога компании + покрытие НДС по карточкам (wbcards_nds).
          Существующие отчёты (/wb-profit, Dashboard) этим расчётом пока не затронуты.
        </div>
      </div>
      <div class="d-flex align-items-center gap-2">
        <span class="badge badge--neutral">нужен перм manageSettings для правок</span>
      </div>
    </div>

    <div v-if="!canManage" class="alert alert-info">
      У вас есть просмотр (<code>viewFinance</code>), но нет права <code>manageSettings</code> —
      настройки и историю можно смотреть, но не менять.
    </div>

    <div class="row g-3">
      <!-- Настройка системы -->
      <div class="col-12 col-xl-7">
        <div class="tbl-card">
          <div class="card__hd">
            <span>Настройка системы</span>
            <span class="spacer"></span>
            <span class="hd-badge">{{ meta.modes.length }} режима</span>
          </div>
          <div class="card-body">
            <div class="wb-field-group">
              <div class="wb-field">
                <label class="wb-field__label">Режим</label>
                <div class="page-tax-settings__modes">
                  <label
                    v-for="m in meta.modes"
                    :key="m.value"
                    class="page-tax-settings__mode"
                    :class="{ 'page-tax-settings__mode--on': form.mode === m.value }"
                  >
                    <input v-model="form.mode" type="radio" :value="m.value" name="tax-mode">
                    <b>{{ m.label }}</b>
                    <span>{{ modeHint(m.value) }}</span>
                  </label>
                </div>
              </div>
            </div>

            <div class="row g-3 mt-1">
              <div class="col-6 col-md-3">
                <div class="wb-field">
                  <label class="wb-field__label">Ставка УСН / основного налога, %</label>
                  <select v-model="form.ratePreset" class="wb-select">
                    <option v-for="r in meta.main_rates" :key="r" :value="r">{{ r }}%</option>
                    <option value="custom">своя…</option>
                  </select>
                </div>
              </div>
              <div class="col-6 col-md-3">
                <div class="wb-field">
                  <label class="wb-field__label">Своя ставка, %</label>
                  <input
                    v-model.number="form.customRate"
                    class="wb-input"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    :disabled="form.ratePreset !== 'custom'"
                    placeholder="напр. 7"
                  >
                </div>
              </div>
              <div v-if="form.mode === 'osno'" class="col-6 col-md-3">
                <div class="wb-field">
                  <label class="wb-field__label">Налог на прибыль / НДФЛ, %</label>
                  <input v-model.number="form.profitRate" class="wb-input" type="number" min="0" max="100" step="0.1">
                </div>
              </div>
              <div class="col-6 col-md-3">
                <div class="wb-field">
                  <label class="wb-field__label">Действует с</label>
                  <input v-model="form.valid_from" class="wb-input" type="date">
                </div>
              </div>
            </div>

            <div class="wb-field mt-3">
              <label class="wb-field__label">НДС</label>
              <div class="page-tax-settings__modes">
                <label
                  v-for="v in meta.vat_sources"
                  :key="v.value"
                  class="page-tax-settings__mode"
                  :class="{ 'page-tax-settings__mode--on': form.vat_source === v.value }"
                >
                  <input v-model="form.vat_source" type="radio" :value="v.value" name="tax-vat">
                  <b>{{ v.label }}</b>
                  <span>{{ v.value === 'cards'
                    ? 'ставка каждого товара своя: без НДС / 10% / 22% — берём из карточки на дату продажи'
                    : 'НДС в расчёте не выделяется (цены считаются как без НДС)' }}</span>
                </label>
              </div>
            </div>

            <div class="wb-field mt-3">
              <label class="wb-field__label">Причина изменения <span class="text-danger">*</span></label>
              <input v-model="form.reason" class="wb-input" placeholder="почему меняем — попадёт в историю">
            </div>

            <div class="page-tax-settings__result">
              <div class="page-tax-settings__result-row"><span>Компания</span><b>{{ companyName }}</b></div>
              <div class="page-tax-settings__result-row"><span>Режим</span><b>{{ modeLabel(form.mode) }}</b></div>
              <div class="page-tax-settings__result-row"><span>Основная ставка</span><b>{{ form.mode === 'none' ? '—' : effectiveRate + '%' }}</b></div>
              <div class="page-tax-settings__result-row"><span>НДС</span><b>{{ vatLabel }}</b></div>
              <div class="page-tax-settings__result-row"><span>Действует с</span><b>{{ form.valid_from }}</b></div>
              <div class="page-tax-settings__result-row"><span>Причина</span><b>{{ form.reason || '—' }}</b></div>
            </div>

            <div class="d-flex align-items-center gap-2 mt-3">
              <button class="btn btn--brand" :disabled="!canManage || saving" @click="save">
                <i class="bi bi-check-lg me-1"></i>{{ saving ? 'Сохраняю…' : 'Сохранить как новую версию' }}
              </button>
              <span class="text-muted" style="font-size:12px">
                Старая версия не перезаписывается — она закрывается датой и остаётся в истории.
              </span>
            </div>
            <div v-if="saveMsg" class="mt-2" :class="saveOk ? 'text-success' : 'text-danger'">{{ saveMsg }}</div>
          </div>
        </div>
      </div>

      <!-- Покрытие НДС -->
      <div class="col-12 col-xl-5">
        <div class="tbl-card">
          <div class="card__hd">
            <span>НДС по карточкам (wbcards_nds)</span>
            <span class="spacer"></span>
            <span class="hd-badge" :class="coverage.missing ? 'badge--warn' : 'badge--ok'">
              {{ coverage.with_rate }} / {{ coverage.total }}
            </span>
          </div>
          <div class="card-body">
            <div class="row g-2 mb-3">
              <div class="col-4"><div class="page-tax-settings__kpi"><b>{{ coverage.total }}</b><span>карточек</span></div></div>
              <div class="col-4"><div class="page-tax-settings__kpi page-tax-settings__kpi--ok"><b>{{ coverage.with_rate }}</b><span>со ставкой</span></div></div>
              <div class="col-4"><div class="page-tax-settings__kpi page-tax-settings__kpi--warn"><b>{{ coverage.missing }}</b><span>без ставки</span></div></div>
            </div>
            <div v-if="coverage.rates?.length" class="mb-3">
              <div class="wb-field__label mb-1">Распределение ставок</div>
              <div class="page-tax-settings__rates">
                <span v-for="r in coverage.rates" :key="r.rate" class="badge badge--info">
                  {{ r.rate }}% — {{ r.cards }} шт
                </span>
              </div>
            </div>
            <div class="text-muted mb-2" style="font-size:12px">
              Последний срез ставок: {{ coverage.last_load_date || '—' }}.
              Карточка без ставки попадает в расчёт как <code>NDS_MISSING</code>, а не как 0%.
            </div>
            <button class="btn btn--outline btn-sm" @click="exportMissing">
              <i class="bi bi-download me-1"></i>Скачать {{ coverage.missing }} без ставки (Excel)
            </button>
          </div>
        </div>
      </div>

      <!-- История версий -->
      <div class="col-12">
        <div class="tbl-card">
          <div class="card__hd">
            <span>История настроек</span>
            <span class="spacer"></span>
            <button class="hd-btn" @click="exportVersions">
              <i class="bi bi-download me-1"></i>Выгрузить в Excel
            </button>
          </div>
          <div class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="t-left">Действует с</th>
                  <th class="t-left">по</th>
                  <th class="t-left">Режим</th>
                  <th class="t-right">Ставка</th>
                  <th class="t-left">НДС</th>
                  <th class="t-left">Причина</th>
                  <th class="t-left">Кто</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="v in versions" :key="v.id">
                  <td class="t-left">{{ v.valid_from }} <span v-if="v.is_current" class="badge badge--ok ms-1">действует</span></td>
                  <td class="t-left">{{ v.valid_to || '—' }}</td>
                  <td class="t-left">{{ v.mode_label }}</td>
                  <td class="t-right num">{{ v.mode === 'none' ? '—' : v.main_rate + '%' }}</td>
                  <td class="t-left">{{ v.vat_source === 'cards' ? 'из карточек' : 'не исчисляется' }}</td>
                  <td class="t-left">{{ v.reason || '—' }}</td>
                  <td class="t-left">{{ v.created_by_name || v.created_by || '—' }}</td>
                </tr>
                <tr v-if="!versions.length"><td colspan="7" class="text-center text-muted py-3">Настроек пока нет</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Живой пример -->
      <div class="col-12">
        <div class="tbl-card">
          <div class="card__hd">
            <span>Живой пример: как посчитается день</span>
            <span class="spacer"></span>
            <span class="hd-badge">отчёты не меняются</span>
          </div>
          <div class="card-body">
            <div class="row g-2 align-items-end mb-3">
              <div class="col-auto"><div class="wb-field"><label class="wb-field__label">С</label><input v-model="pvFrom" class="wb-input" type="date"></div></div>
              <div class="col-auto"><div class="wb-field"><label class="wb-field__label">по</label><input v-model="pvTo" class="wb-input" type="date"></div></div>
              <div class="col-auto"><div class="wb-field"><label class="wb-field__label">Режим</label><select v-model="pvMode" class="wb-select"><option value="">из настроек</option><option v-for="m in meta.modes" :key="m.value" :value="m.value">{{ m.label }}</option></select></div></div>
              <div class="col-auto"><button class="btn btn--brand" :disabled="pvBusy" @click="runPreview"><i class="bi bi-calculator me-1"></i>{{ pvBusy ? 'Считаю…' : 'Посчитать' }}</button></div>
            </div>
            <div v-if="previewMsg" class="alert alert-danger mb-3">{{ previewMsg }}</div>
            <template v-if="preview">
              <div class="page-tax-settings__notes mb-3">
                <div v-for="(n, i) in preview.notes" :key="i" class="page-tax-settings__note"><i class="bi bi-info-circle me-1"></i>{{ n }}</div>
              </div>
              <div class="row g-2 mb-3">
                <div class="col-6 col-md-3"><div class="page-tax-settings__kpi"><b>{{ money(preview.totals.net) }}</b><span>оборот за вычетом возвратов</span></div></div>
                <div class="col-6 col-md-3"><div class="page-tax-settings__kpi page-tax-settings__kpi--info"><b>{{ money(preview.totals.vat) }}</b><span>НДС по карточкам</span></div></div>
                <div class="col-6 col-md-3"><div class="page-tax-settings__kpi"><b>{{ money(preview.totals.tax) }}</b><span>основной налог</span></div></div>
                <div class="col-6 col-md-3"><div class="page-tax-settings__kpi page-tax-settings__kpi--ok"><b>{{ money(preview.totals.total_tax) }}</b><span>всего налогов</span></div></div>
              </div>
              <div v-if="preview.partial" class="alert alert-warning">
                НДС посчитан не по всем позициям: {{ preview.totals.vat_missing_rows }} строк без ставки (на {{ money(preview.totals.vat_missing_amount) }} ₽).
                Суммы налогов по ним занижены.
              </div>
              <div class="tbl-wrap">
                <table class="tbl">
                  <thead>
                    <tr>
                      <th class="t-left">Дата</th><th class="t-right">Продажи</th><th class="t-right">Возвраты</th>
                      <th class="t-right">Оборот</th><th class="t-right">НДС</th><th class="t-right">Доход без НДС</th>
                      <th class="t-right">Расходы</th><th class="t-right">База Д−Р</th><th class="t-right">Налог</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="d in preview.days" :key="d.date">
                      <td class="t-left">{{ d.date }}</td>
                      <td class="t-right num">{{ money(d.sales) }}</td>
                      <td class="t-right num">{{ money(d.returns) }}</td>
                      <td class="t-right num">{{ money(d.net) }}</td>
                      <td class="t-right num">{{ money(d.vat) }} <span v-if="d.vat_missing_rows" class="badge badge--warn">NDS_MISSING</span></td>
                      <td class="t-right num">{{ money(d.income_base) }}</td>
                      <td class="t-right num">{{ money(dExpenses(d)) }}</td>
                      <td class="t-right num">{{ money(d.profit_base) }}</td>
                      <td class="t-right num">{{ money(d.tax) }}</td>
                    </tr>
                    <tr v-if="!preview.days.length"><td colspan="9" class="text-center text-muted py-3">За период нет данных</td></tr>
                  </tbody>
                </table>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-tax-settings.css'
import { computed, onMounted, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { taxSettingsApi, type NdsCoverage, type TaxPreview, type TaxVersion } from '@/api/taxSettings'
import { useAuthStore } from '@/stores/auth'
import { exportXlsx } from '@/utils/exportXlsx'

const auth = useAuthStore()
// v3: перм manageSettings (у owner/admin компании он выдаётся автоматически).
// legacy (AUTH_V3=0): перма нет — правят владельцы/админы компании.
const canManage = computed(() => auth.can('manageSettings') || (!auth.authV3 && auth.managesAny))
const companyName = computed(() =>
  auth.companies.find((c) => c.id === auth.companyId)?.name || (auth.companyId === 'all' ? 'все компании' : '—'))

const meta = ref<{ modes: { value: string; label: string }[]; vat_sources: { value: string; label: string }[]; main_rates: number[] }>(
  { modes: [], vat_sources: [], main_rates: [] })

const form = ref({
  mode: 'income',
  ratePreset: '7',
  customRate: 7,
  profitRate: 25,
  vat_source: 'cards',
  valid_from: new Date().toISOString().slice(0, 10),
  reason: '',
})

const versions = ref<TaxVersion[]>([])
const coverage = ref<NdsCoverage>({ total: 0, with_rate: 0, missing: 0, last_load_date: null, rates: [] })
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(true)

const pvFrom = ref(new Date(Date.now() - 6 * 864e5).toISOString().slice(0, 10))
const pvTo = ref(new Date().toISOString().slice(0, 10))
const pvMode = ref('')
const pvBusy = ref(false)
const previewMsg = ref('')
const preview = ref<TaxPreview | null>(null)

const effectiveRate = computed(() => {
  if (form.value.ratePreset === 'custom') return Number(form.value.customRate || 0)
  return Number(form.value.ratePreset || 0)
})
const vatLabel = computed(() => (form.value.vat_source === 'cards' ? 'из wbcards_nds' : 'не исчисляется'))

function modeLabel(v: string) {
  return meta.value.modes.find((m) => m.value === v)?.label || v
}
function modeHint(v: string) {
  if (v === 'income') return 'налог со ставки от дохода без НДС'
  if (v === 'profit') return 'доход без НДС минус расходы'
  if (v === 'osno') return 'НДС по карточкам + налог на прибыль'
  return 'показываем прибыль до налога'
}
function money(v: number) {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(v || 0)) + ' ₽'
}
function dExpenses(d: any) {
  return d.cost + d.commission + d.acquiring + d.acceptance + d.delivery + d.storage
    + d.penalty + d.deduction + d.otziv + d.adv + d.cashback + d.manual
}

async function loadAll() {
  const [m, v, c] = await Promise.all([
    taxSettingsApi.meta().catch(() => null),
    taxSettingsApi.versions().catch(() => [] as TaxVersion[]),
    taxSettingsApi.ndsCoverage().catch(() => null),
  ])
  if (m) meta.value = m
  versions.value = v
  if (c) coverage.value = c
}

async function save() {
  saveMsg.value = ''
  if (!form.value.reason.trim()) { saveMsg.value = 'Укажите причину изменения — она попадёт в историю.'; saveOk.value = false; return }
  saving.value = true
  try {
    await taxSettingsApi.create({
      mode: form.value.mode,
      main_rate: form.value.mode === 'none' ? 0 : effectiveRate.value,
      vat_source: form.value.vat_source,
      profit_rate: form.value.mode === 'osno' ? Number(form.value.profitRate || 0) : null,
      valid_from: form.value.valid_from,
      reason: form.value.reason.trim(),
    })
    saveOk.value = true
    saveMsg.value = 'Сохранено: новая версия настроек с ' + form.value.valid_from + '. Предыдущая версия закрыта и осталась в истории.'
    form.value.reason = ''
    await loadAll()
  } catch (e: any) {
    saveOk.value = false
    saveMsg.value = e?.response?.data?.detail || e?.message || String(e)
  } finally {
    saving.value = false
  }
}

async function runPreview() {
  previewMsg.value = ''
  preview.value = null
  pvBusy.value = true
  try {
    preview.value = await taxSettingsApi.preview({
      date_from: pvFrom.value,
      date_to: pvTo.value,
      mode: pvMode.value || undefined,
    })
  } catch (e: any) {
    previewMsg.value = e?.response?.data?.detail || e?.message || String(e)
  } finally {
    pvBusy.value = false
  }
}

async function exportVersions() {
  const rows = versions.value.map((v) => ({
    'Действует с': v.valid_from,
    'по': v.valid_to || '',
    'Режим': v.mode_label,
    'Ставка, %': v.main_rate,
    'НДС': v.vat_source === 'cards' ? 'из карточек' : 'не исчисляется',
    'Причина': v.reason || '',
    'Кто': v.created_by_name || v.created_by || '',
  }))
  await exportXlsx({ rows, filename: 'налоговые-настройки.xlsx', sheetName: 'Настройки' })
}

async function exportMissing() {
  const rows = await taxSettingsApi.ndsMissing('', 1000)
  await exportXlsx({
    rows: rows.map((r) => ({ 'nmID WB': r.nmID, 'Артикул': r.vendorCode, 'Название': r.title, 'Ставка НДС': '' })),
    filename: 'карточки-без-ндс.xlsx',
    sheetName: 'Без ставки',
  })
}

onMounted(loadAll)
</script>
