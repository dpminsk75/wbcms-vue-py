<template>
  <div class="container-xxl page-tax-settings">
    <!-- Заголовок страницы (h1) + вкладки раздела -->
    <h1 class="wsp__title page-tax-settings__title">Налоги</h1>

    <!-- Вкладки раздела: История / Настройки / Ставки НДС / Пример расчёта -->
    <WbSectionTabs v-model="tab" :tabs="tabs" class="mb-3" />

    <div v-if="!canManage" class="wb-panel page-tax-settings__alert mb-3">
      <div class="wb-panel__bd">
        <span class="badge badge--warn">viewFinance</span>
        Просмотр доступен, правки требуют права <code>manageSettings</code>.
      </div>
    </div>

    <!-- ==================== 1. ИСТОРИЯ ==================== -->
    <template v-if="tab === 'history'">
      <div class="grid-3 mb-3">
        <KpiTile
          label="Действующая ставка"
          :value="currentVersion ? `${currentVersion.main_rate}%` : '—'"
          variant="tile--1"
          :foot="currentVersion ? `${currentVersion.mode_label}, с ${currentVersion.valid_from}` : 'настроек пока нет'"
        />
        <KpiTile
          label="Версий настроек"
          :value="versions.length"
          variant="tile--1"
          foot="история не перезаписывается"
        />
        <KpiTile
          label="Карточек без ставки НДС"
          :value="coverage.missing"
          variant="tile--10"
          foot="не попадут в расчёт НДС"
        />
      </div>

      <div class="tbl-card">
        <div class="card__hd">
          История версий
          <span class="hd-badge">{{ versions.length }} версий</span>
          <span class="spacer"></span>
          <button class="hd-btn" type="button" :disabled="!versions.length" @click="exportVersions">
            <i class="bi bi-file-earmark-excel me-1"></i>Excel
          </button>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">Действует с</th>
                <th class="t-left">по</th>
                <th class="t-left">Режим</th>
                <th>Ставка</th>
                <th class="t-left">НДС</th>
                <th class="t-left">Причина</th>
                <th class="t-left">Кто</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="v in versions" :key="v.id">
                <td class="t-left">
                  {{ v.valid_from }}
                  <span v-if="v.is_current" class="badge badge--ok ms-1">действует</span>
                </td>
                <td class="t-left">{{ v.valid_to || 'бессрочно' }}</td>
                <td class="t-left">{{ v.mode_label }}</td>
                <td class="num">{{ v.mode === 'none' ? '—' : `${v.main_rate}%` }}</td>
                <td class="t-left">{{ v.vat_source === 'cards' ? 'по ставке карточки' : 'не выделять' }}</td>
                <td class="t-left">{{ v.reason || '—' }}</td>
                <td class="t-left">{{ v.created_by_name || v.created_by || '—' }}</td>
              </tr>
              <tr v-if="!versions.length">
                <td colspan="7" class="text-center text-muted py-3">Настроек пока нет</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ==================== 2. НАСТРОЙКИ ==================== -->
    <template v-else-if="tab === 'settings'">
      <div class="wb-panel">
        <div class="card__hd">
          Новая версия настроек
          <span class="spacer"></span>
          <span class="badge badge--warn">влияет на будущие периоды</span>
        </div>
        <div class="wb-panel__bd">
          <div class="page-tax-settings__fields">
            <div class="wb-field">
              <label class="wb-field__label">Режим налогообложения</label>
              <select v-model="form.mode" class="wb-select">
                <option v-for="m in meta.modes" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </div>
            <div class="wb-field">
              <label class="wb-field__label">Ставка налога, %</label>
              <input
                v-model.number="form.rate"
                class="wb-input"
                type="number"
                min="0"
                max="100"
                step="0.1"
                placeholder="например, 7"
              >
            </div>
            <div class="wb-field">
              <label class="wb-field__label">НДС</label>
              <select v-model="form.vat_source" class="wb-select">
                <option v-for="v in meta.vat_sources" :key="v.value" :value="v.value">{{ v.label }}</option>
              </select>
            </div>
            <div class="wb-field">
              <label class="wb-field__label">Действует с</label>
              <WbDateInput v-model="form.valid_from" />
            </div>
            <div class="wb-field page-tax-settings__field--wide">
              <label class="wb-field__label">Причина изменения</label>
              <input v-model="form.reason" class="wb-input" placeholder="попадёт в историю">
            </div>
          </div>

          <div v-if="saveMsg" class="mt-3">
            <span class="badge" :class="saveOk ? 'badge--ok' : 'badge--bad'">{{ saveMsg }}</span>
          </div>

          <div class="btn-row mt-3">
            <button class="btn btn--brand" type="button" :disabled="!canManage || saving" @click="save">
              <i class="bi bi-check-lg me-1"></i>{{ saving ? 'Сохраняю…' : 'Сохранить как новую версию' }}
            </button>
            <button class="btn btn--outline" type="button" :disabled="saving" @click="resetForm">
              Сбросить
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- ==================== 3. СТАВКИ НДС ==================== -->
    <template v-else-if="tab === 'nds'">
      <div v-if="coverageErr" class="wb-panel page-tax-settings__alert mb-3">
        <div class="wb-panel__bd">
          <span class="badge badge--bad">Ошибка</span>
          Не удалось загрузить покрытие НДС: {{ coverageErr }}
        </div>
      </div>

      <div class="grid-3 mb-3">
        <KpiTile label="Карточек в базе" :value="coverage.total" variant="tile--1" :foot="`из них со ставкой — ${coverage.with_rate}`" />
        <KpiTile label="Без ставки" :value="coverage.missing" variant="tile--10" foot="не попадут в расчёт НДС" />
        <KpiTile label="Последний срез" :value="coverage.last_load_date || '—'" variant="tile--1" foot="обновление wbcards_nds" />
      </div>

      <div class="tbl-card">
        <div class="card__hd">
          Карточки без ставки НДС
          <span class="hd-badge">{{ missing.length }} штук</span>
          <span class="spacer"></span>
          <button class="hd-btn" type="button" :disabled="!missing.length" @click="exportMissing">
            <i class="bi bi-file-earmark-excel me-1"></i>Excel
          </button>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">Артикул</th>
                <th>nmId</th>
                <th class="t-left">Название</th>
                <th class="t-left">В расчёте</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in missing" :key="c.nmID">
                <td class="t-left">{{ c.vendorCode || '—' }}</td>
                <td class="num">{{ c.nmID }}</td>
                <td class="t-left">{{ c.title || '—' }}</td>
                <td class="t-left"><span class="badge badge--warn">без ставки НДС</span></td>
              </tr>
              <tr v-if="!missing.length">
                <td colspan="4" class="text-center text-muted py-3">У всех карточек есть ставка</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ==================== 4. ПРИМЕР РАСЧЁТА ==================== -->
    <template v-else>
      <div class="wb-filter-panel mb-3">
        <div class="row g-2 align-items-end">
          <div class="col-auto">
            <div class="wb-field">
              <label class="wb-field__label">Дата с</label>
              <WbDateInput v-model="pvFrom" />
            </div>
          </div>
          <div class="col-auto">
            <div class="wb-field">
              <label class="wb-field__label">Дата по</label>
              <WbDateInput v-model="pvTo" />
            </div>
          </div>
          <div class="col-auto">
            <div class="wb-field">
              <label class="wb-field__label">Режим</label>
              <select v-model="pvMode" class="wb-select">
                <option value="">из настроек</option>
                <option v-for="m in meta.modes" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </div>
          </div>
          <div class="col-auto">
            <button class="btn btn--brand" type="button" :disabled="pvBusy" @click="runPreview">
              <i class="bi bi-calculator me-1"></i>{{ pvBusy ? 'Считаю…' : 'Посчитать' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="previewMsg" class="wb-panel page-tax-settings__alert mb-3">
        <div class="wb-panel__bd">
          <span class="badge badge--bad">Ошибка</span> {{ previewMsg }}
        </div>
      </div>

      <template v-if="preview">
        <div class="grid-4 mb-3">
          <KpiTile label="Оборот за вычетом возвратов" :value="money(preview.totals.net)" variant="tile--1" />
          <KpiTile label="НДС" :value="money(preview.totals.vat)" variant="tile--12" />
          <KpiTile label="Основной налог" :value="money(preview.totals.tax)" variant="tile--1" />
          <KpiTile label="Всего налогов" :value="money(preview.totals.total_tax)" variant="tile--8" />
        </div>

        <div v-if="preview.partial" class="page-tax-settings__note mb-3">
          НДС посчитан не по всем позициям: {{ preview.totals.vat_missing_rows }} строк без ставки
          (на {{ money(preview.totals.vat_missing_amount) }}). Суммы налогов по ним занижены.
        </div>

        <div class="tbl-card">
          <div class="card__hd">
            Расчёт по дням
            <span class="hd-badge">отчёты не меняются</span>
          </div>
          <div class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th class="t-left">Дата</th><th>Продажи</th><th>Возвраты</th><th>Оборот</th>
                  <th>НДС</th><th>Расходы</th><th>Прибыль</th><th>Налог</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="d in preview.days" :key="d.date">
                  <td class="t-left">{{ d.date }}</td>
                  <td class="num">{{ money(d.sales) }}</td>
                  <td class="num">{{ money(d.returns) }}</td>
                  <td class="num">{{ money(d.net) }}</td>
                  <td class="num">{{ money(d.vat) }}</td>
                  <td class="num">{{ money(dExpenses(d)) }}</td>
                  <td class="num">{{ money(d.profit_base) }}</td>
                  <td class="num">{{ money(d.tax) }}</td>
                </tr>
                <tr v-if="!preview.days.length">
                  <td colspan="8" class="text-center text-muted py-3">За период нет данных</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-tax-settings.css'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { taxSettingsApi, type NdsCoverage, type TaxPreview, type TaxVersion } from '@/api/taxSettings'
import KpiTile from '@/components/common/KpiTile.vue'
import WbDateInput from '@/components/common/WbDateInput.vue'
import WbSectionTabs from '@/components/common/WbSectionTabs.vue'
import { useAuthStore } from '@/stores/auth'
import { exportXlsx } from '@/utils/exportXlsx'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
// v3: перм manageSettings (у owner/admin компании он выдаётся автоматически).
// legacy (AUTH_V3=0): перма нет — правят владельцы/админы компании.
const canManage = computed(() => auth.can('manageSettings') || (!auth.authV3 && auth.managesAny))

const today = new Date().toISOString().slice(0, 10)

const tab = ref(String(route.query.tab || 'history'))

const tabs = computed(() => [
  { id: 'history', label: 'История', count: versions.value.length },
  { id: 'settings', label: 'Настройки' },
  { id: 'nds', label: 'Ставки НДС', count: coverage.value.missing },
  { id: 'calc', label: 'Пример расчёта' },
])

const meta = ref<{ modes: { value: string; label: string }[]; vat_sources: { value: string; label: string }[] }>(
  { modes: [], vat_sources: [] })

const form = ref({
  mode: 'income',
  rate: 7 as number | null,
  vat_source: 'cards',
  valid_from: today,
  reason: '',
})

const versions = ref<TaxVersion[]>([])
const currentVersion = ref<TaxVersion | null>(null)
const coverage = ref<NdsCoverage>({ total: 0, with_rate: 0, missing: 0, last_load_date: null })
const coverageErr = ref('')
const missing = ref<{ nmID: number; vendorCode: string; title: string }[]>([])
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(true)

const pvFrom = ref(new Date(Date.now() - 6 * 864e5).toISOString().slice(0, 10))
const pvTo = ref(today)
const pvMode = ref('')
const pvBusy = ref(false)
const previewMsg = ref('')
const preview = ref<TaxPreview | null>(null)

function money(v: number) {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(v || 0)) + ' ₽'
}
function dExpenses(d: any) {
  // f_otziv и f_adv — часть f_deduction, поэтому не вычитаются повторно.
  return d.cost + d.commission + d.acquiring + d.acceptance + d.delivery + d.storage
    + d.penalty + d.deduction + d.cashback + d.manual
}

/** Подставить действующую версию в форму (режим, ставка, НДС). */
function fillFormFromCurrent(v: TaxVersion | null) {
  if (!v) return
  form.value.mode = v.mode
  form.value.rate = v.mode === 'none' ? null : Number(v.main_rate)
  form.value.vat_source = v.vat_source
}
function resetForm() {
  fillFormFromCurrent(currentVersion.value)
  form.value.valid_from = today
  form.value.reason = ''
  saveMsg.value = ''
}

watch(tab, (next) => {
  router.replace({ path: route.path, query: next === 'history' ? {} : { tab: next } })
})

async function loadAll() {
  const [m, v, cur, miss] = await Promise.all([
    taxSettingsApi.meta().catch(() => null),
    taxSettingsApi.versions().catch(() => [] as TaxVersion[]),
    taxSettingsApi.current().catch(() => null),
    taxSettingsApi.ndsMissing('', 500).catch(() => [] as { nmID: number; vendorCode: string; title: string }[]),
  ])
  if (m) meta.value = m
  versions.value = v
  currentVersion.value = cur
  missing.value = miss
  if (!form.value.rate && cur) fillFormFromCurrent(cur)

  // Покрытие НДС — отдельно: при ошибке показываем её, а не нули.
  coverageErr.value = ''
  try {
    coverage.value = await taxSettingsApi.ndsCoverage()
  } catch (e: any) {
    coverageErr.value = e?.response?.data?.detail || e?.message || String(e)
  }
}

async function save() {
  saveMsg.value = ''
  if (!form.value.reason.trim()) {
    saveMsg.value = 'Укажите причину изменения — она попадёт в историю.'
    saveOk.value = false
    return
  }
  saving.value = true
  try {
    await taxSettingsApi.create({
      mode: form.value.mode,
      main_rate: form.value.mode === 'none' ? 0 : Number(form.value.rate || 0),
      vat_source: form.value.vat_source,
      profit_rate: null,
      valid_from: form.value.valid_from,
      reason: form.value.reason.trim(),
    })
    saveOk.value = true
    saveMsg.value = `Сохранено: новая версия настроек с ${form.value.valid_from}. Предыдущая версия закрыта и осталась в истории.`
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
    'по': v.valid_to || 'бессрочно',
    'Режим': v.mode_label,
    'Ставка, %': v.mode === 'none' ? '' : v.main_rate,
    'НДС': v.vat_source === 'cards' ? 'по ставке карточки' : 'не выделять',
    'Причина': v.reason || '',
    'Кто': v.created_by_name || v.created_by || '',
  }))
  await exportXlsx({ rows, filename: 'налоговые-настройки.xlsx', sheetName: 'Настройки' })
}

async function exportMissing() {
  await exportXlsx({
    rows: missing.value.map((r) => ({
      'nmID WB': r.nmID,
      'Артикул': r.vendorCode,
      'Название': r.title,
      'Ставка НДС': '',
    })),
    filename: 'карточки-без-ндс.xlsx',
    sheetName: 'Без ставки',
  })
}

onMounted(loadAll)
</script>
